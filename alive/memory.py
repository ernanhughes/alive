"""Pinned local MiniLM ONNX embeddings and provenance-aware bounded retrieval."""

import asyncio
import json
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

import numpy as np
from sqlalchemy import func, literal_column, select, text

from alive.attention import fingerprint, redact
from alive.cognitive_models import HistoryImport, MemoryVector
from alive.models import Memory, record, uid

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
GENERAL_MEMORY_TYPES = ("experience", "cognitive_analysis", "authorised_history")


class EmbeddingProvider(Protocol):
    provider_id: str
    model_id: str
    dimension: int
    revision: str

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbedding:
    provider_id, model_id, dimension, revision = "local-onnx", EMBED_MODEL, 384, EMBED_REVISION

    def __init__(self, settings):
        self.path = Path(settings.alive_embedding_path)
        self.enabled = settings.alive_embedding_enabled
        self.session = self.tokenizer = None
        self.lock = asyncio.Lock()

    @property
    def available(self):
        metadata = self.path / "provenance.json"
        if (
            not self.enabled
            or not metadata.is_file()
            or not all((self.path / name).is_file() for name in ("model.onnx", "tokenizer.json"))
        ):
            return False
        try:
            return json.loads(metadata.read_text()) == {
                "model": self.model_id,
                "revision": self.revision,
                "dimension": self.dimension,
            }
        except (ValueError, OSError):
            return False

    def _embed(self, texts):
        if not self.available:
            raise RuntimeError("Pinned local embedding files are unavailable")
        if self.session is None:
            import onnxruntime as ort
            from tokenizers import Tokenizer

            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            self.session = ort.InferenceSession(
                str(self.path / "model.onnx"),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            self.tokenizer = Tokenizer.from_file(str(self.path / "tokenizer.json"))
            self.tokenizer.enable_truncation(max_length=256)
            self.tokenizer.enable_padding()
        encoded = self.tokenizer.encode_batch([t[:8000] for t in texts])
        arrays = {
            "input_ids": np.array([x.ids for x in encoded], dtype=np.int64),
            "attention_mask": np.array([x.attention_mask for x in encoded], dtype=np.int64),
            "token_type_ids": np.array([x.type_ids for x in encoded], dtype=np.int64),
        }
        outputs = self.session.run(
            None, {i.name: arrays[i.name] for i in self.session.get_inputs()}
        )[0]
        mask = arrays["attention_mask"][..., None]
        pooled = (outputs * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
        pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
        if pooled.shape[1] != self.dimension or not np.isfinite(pooled).all():
            raise ValueError("Incompatible or non-finite embedding output")
        return pooled.tolist()

    async def embed(self, texts):
        if not 1 <= len(texts) <= 32:
            raise ValueError("Embedding batch must contain 1–32 texts")
        async with self.lock:
            return await asyncio.to_thread(self._embed, texts)


class MemoryService:
    def __init__(self, kernel):
        self.k = kernel
        self.embedding = LocalEmbedding(kernel.settings)

    async def index(self, limit=32):
        if not self.embedding.available:
            return {"indexed": 0, "available": False}
        e, k = self.embedding, self.k
        async with k.db.sessions() as session:
            exists = select(MemoryVector.memory_id).where(
                MemoryVector.model == e.model_id, MemoryVector.revision == e.revision
            )
            rows = (
                await session.scalars(
                    select(Memory)
                    .where(~Memory.id.in_(exists))
                    .order_by(Memory.created_at.desc())
                    .limit(limit)
                )
            ).all()
        if not rows:
            return {"indexed": 0, "available": True}
        values = await e.embed([row.content for row in rows])
        if e.dimension != 384 or any(len(v) != 384 or not np.isfinite(v).all() for v in values):
            raise ValueError("Embedding dimension or values are incompatible with vector(384)")
        async with k.lock, k.db.sessions.begin() as session:
            for row, vector in zip(rows, values, strict=True):
                if not await session.get(Memory, row.id):
                    continue
                key = (row.id, e.model_id, e.revision)
                if await session.get(MemoryVector, key):
                    continue
                session.add(
                    MemoryVector(
                        memory_id=row.id,
                        model=e.model_id,
                        revision=e.revision,
                        dimension=e.dimension,
                        values_json=vector,
                    )
                )
                await session.flush()
                if k.db.pg and k.vector_storage:
                    await session.execute(
                        text(
                            "UPDATE memory_vectors SET embedding=CAST(:vector AS vector) "
                            "WHERE memory_id=:id AND model=:model AND revision=:revision"
                        ),
                        {
                            "vector": json.dumps(vector),
                            "id": row.id,
                            "model": e.model_id,
                            "revision": e.revision,
                        },
                    )
        return {
            "indexed": len(rows),
            "available": True,
            "model": e.model_id,
            "revision": e.revision,
        }

    async def retrieve(self, query, mode="text", top_k=5, exclude_event=None, memory_types=None):
        if not 1 <= top_k <= 20:
            raise ValueError("top_k must be 1-20")
        k, e = self.k, self.embedding
        if memory_types is None:
            memory_types = GENERAL_MEMORY_TYPES
        memory_types = tuple(memory_types)
        if mode in ("vector", "hybrid") and not e.available:
            if mode == "vector":
                raise ValueError(
                    "Semantic search unavailable: pinned local embedding model not loaded"
                )
            mode = "text"
        text_ids, vector_ids, rows_by_id = [], [], {}
        async with k.db.sessions() as session:
            base = select(Memory)
            if memory_types:
                base = base.where(Memory.memory_type.in_(memory_types))
            if exclude_event:
                base = base.where(
                    (Memory.source_event_id != exclude_event) | Memory.source_event_id.is_(None)
                )
            if mode in ("text", "hybrid"):
                if k.db.pg:
                    terms = func.websearch_to_tsquery("english", " OR ".join(query.split()[:12]))
                    doc = literal_column("search_document")
                    request = base.where(doc.op("@@")(terms)).order_by(
                        func.ts_rank(doc, terms).desc()
                    )
                else:
                    terms = query.split()[:12]
                    from sqlalchemy import or_

                    request = base.where(
                        or_(*[Memory.content.icontains(t, autoescape=True) for t in terms])
                    )
                rows = (await session.scalars(request.limit(top_k * 3))).all()
                text_ids = [r.id for r in rows]
                rows_by_id.update({r.id: r for r in rows})
            if mode in ("vector", "hybrid"):
                vector = (await e.embed([query]))[0]
                if len(vector) != 384 or not np.isfinite(vector).all():
                    raise ValueError("Query embedding is incompatible with vector(384)")
                if k.db.pg and k.vector_storage:
                    ids = (
                        (
                            await session.execute(
                                text(
                                    "SELECT v.memory_id FROM memory_vectors v "
                                    "JOIN memories m ON m.id=v.memory_id "
                                    "WHERE v.model=:model AND v.revision=:revision "
                                    "AND v.dimension=384 AND v.embedding IS NOT NULL "
                                    "AND (CAST(:exclude AS text) IS NULL OR "
                                    "m.source_event_id IS DISTINCT FROM CAST(:exclude AS text)) "
                                    "ORDER BY v.embedding <=> CAST(:vector AS vector) LIMIT :limit"
                                ),
                                {
                                    "model": e.model_id,
                                    "revision": e.revision,
                                    "vector": json.dumps(vector),
                                    "exclude": exclude_event,
                                    "limit": top_k * 3,
                                },
                            )
                        )
                        .scalars()
                        .all()
                    )
                    rows = (await session.scalars(base.where(Memory.id.in_(ids)))).all()
                    vector_ids = list(ids)
                else:
                    entries = (
                        await session.scalars(
                            select(MemoryVector)
                            .where(
                                MemoryVector.model == e.model_id,
                                MemoryVector.revision == e.revision,
                                MemoryVector.dimension == e.dimension,
                            )
                            .limit(2000)
                        )
                    ).all()
                    entries.sort(key=lambda v: float(np.dot(vector, v.values_json)), reverse=True)
                    vector_ids = [v.memory_id for v in entries[: top_k * 3]]
                    rows = (await session.scalars(base.where(Memory.id.in_(vector_ids)))).all()
                rows_by_id.update({r.id: r for r in rows})
        scores = {}
        for ids in [text_ids, vector_ids]:
            for i, item in enumerate(ids):
                scores[item] = scores.get(item, 0) + 1 / (60 + i + 1)
        ordered = sorted(scores, key=lambda key: (-scores[key], key))
        return {
            "mode": "hybrid_rrf"
            if mode == "hybrid"
            else "vector_cosine"
            if mode == "vector"
            else "postgresql_fts"
            if k.db.pg
            else "sqlite_substring",
            "embedding": {"model": e.model_id, "revision": e.revision} if vector_ids else None,
            "results": [
                record(rows_by_id[i]) | {"retrieval_score": scores[i]}
                for i in ordered
                if i in rows_by_id
            ][:top_k],
        }

    async def preview_import(self, data):
        entries = []
        for entry in data.entries:
            url = urlsplit(entry.url)
            if url.scheme not in ("http", "https") or url.username or url.password:
                raise ValueError("Only credential-free HTTP URLs can be imported")
            if any(
                word in url.path.lower() for word in ["/login", "/account", "/checkout", "/auth"]
            ):
                raise ValueError("Sensitive URL path is excluded")
            entries.append(
                {
                    "url": f"{url.scheme}://{url.netloc}{url.path}",
                    "title": redact(entry.title),
                    "content": redact(entry.content),
                    "visited_at": entry.visited_at.isoformat() if entry.visited_at else None,
                }
            )
        async with self.k.lock, self.k.db.sessions.begin() as session:
            row = HistoryImport(id=uid(), instance_id=self.k.instance_id, entries=entries)
            session.add(row)
            await session.flush()
            return record(row)

    async def approve_import(self, import_id, approved):
        k = self.k
        async with k.lock, k.db.sessions.begin() as session:
            row = await session.get(HistoryImport, import_id)
            if not row:
                raise KeyError("Import not found")
            if row.status != "preview":
                return record(row)
            if not approved:
                row.status = "rejected"
                return record(row)
            ids = []
            for entry in row.entries:
                key = fingerprint(k.instance_id, entry["url"], entry["content"])
                memory_id = "import-" + key[:29]
                if await session.get(Memory, memory_id):
                    continue
                session.add(
                    Memory(
                        id=memory_id,
                        instance_id=k.instance_id,
                        content=entry["content"],
                        memory_type="authorised_history",
                        metadata_json={
                            "import_id": row.id,
                            "url": entry["url"],
                            "title": entry["title"],
                            "fingerprint": key,
                            "classification": "user_approved",
                        },
                    )
                )
                ids.append(memory_id)
            row.memory_ids, row.status = ids, "imported"
            k.add_event(
                session, "memory.history_imported", {"import_id": row.id, "count": len(ids)}
            )
            return record(row)

    async def revoke_import(self, import_id):
        k = self.k
        async with k.lock, k.db.sessions.begin() as session:
            row = await session.get(HistoryImport, import_id)
            if not row:
                raise KeyError("Import not found")
            for memory_id in row.memory_ids:
                for vector in (
                    await session.scalars(
                        select(MemoryVector).where(MemoryVector.memory_id == memory_id)
                    )
                ).all():
                    await session.delete(vector)
                memory = await session.get(Memory, memory_id)
                if memory:
                    await session.delete(memory)
            row.status, row.entries = "revoked", []
            k.add_event(session, "memory.history_revoked", {"import_id": row.id})
            return {"status": "revoked", "deleted": len(row.memory_ids)}
