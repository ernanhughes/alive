"""ALIVE-11 uses the existing native journey; paid execution needs a deliberate opt-in."""

import argparse
import asyncio
import hashlib
import html
import json
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from alive.config import Settings
from alive.provenance import file_digest
from alive.providers import MetaProvider
from scripts import native10 as harness
from scripts.native11_cases import CASES, GOAL, RATINGS, content

ROOT = Path(__file__).resolve().parents[1]


class WorkbenchPage(harness.PageHandler):
    provider_mode = "synthetic"

    def do_GET(self):
        if self.path != "/native10":
            self.send_error(404)
            return
        mode = (
            "SYNTHETIC PROVIDER · NO META INFERENCE"
            if self.provider_mode == "synthetic"
            else "OWNER-AUTHORISED META QUALIFICATION"
        )
        body = (
            "<!doctype html><meta charset='utf-8'><title>ALIVE-11 research workbench</title>"
            "<style>body{font:22px/1.65 system-ui;background:#eff3e8;color:#16352b;"
            "margin:70px;max-width:900px}small{font-size:13px;letter-spacing:2px}"
            "main{padding:35px;background:white;border-left:4px solid #537548}"
            "aside{font-size:16px;margin-top:35px;color:#54665a}</style>"
            f"<small>{mode}</small><h1>A continuing research companion</h1>"
            f"<p>{html.escape(GOAL)}</p><main id='content'>{html.escape(content('initial'))}</main>"
            "<aside>Controlled, authorised research excerpts. Background information, "
            "diagnostic evidence and usefulness are assessed separately. Operator feedback "
            "in this qualification exercises the policy; it is not a user study.</aside>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def clean_environment(run_dir, backend, stub, page_url):
    env = harness.backend_env(run_dir, backend, stub, page_url)
    for name in [
        "ALIVE_META_URL",
        "ALIVE_DSN",
        "MODEL_API_KEY",
        "META_API_KEY",
        "ALIVE_ROLE_MODELS",
        "ALIVE_EMBEDDING_ENABLED",
    ]:
        env.pop(name, None)
    env["ALIVE_META_URL"] = f"http://127.0.0.1:{stub}/v1/chat/completions"
    env["ALIVE_COMPANION_MICRO_USD_LIMIT"] = "100000"
    env["ALIVE_EMBEDDING_ENABLED"] = "false"
    return env


async def qualify(args):
    if args.provider == "meta" and not args.allow_paid:
        raise ValueError("Paid execution requires owner approval and --allow-paid; no call made")
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--", "alive", "extension", "scripts", "tests"],
        cwd=ROOT,
        text=True,
    ).strip()
    if dirty and not args.allow_dirty_diagnostic:
        raise ValueError("Commit qualification code first, or explicitly label a dirty diagnostic")
    if dirty and args.provider == "meta":
        raise ValueError("Paid qualification requires committed source")
    live_settings = (
        Settings(_env_file=args.credentials_env_file) if args.provider == "meta" else None
    )
    if live_settings:
        endpoint = urlsplit(live_settings.alive_meta_url or live_settings.alive_meta_base_url)
        if endpoint.scheme != "https" or endpoint.hostname != "api.meta.ai":
            raise ValueError("Unexpected real provider endpoint; no call made")
        if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise ValueError("Credential-bearing or parameterised provider URL rejected")
        if (
            not live_settings.alive_meta_api_key
            or live_settings.alive_meta_model != "muse-spark-1.3"
        ):
            raise ValueError("Missing credential or changed model pin; no call made")
        catalog = await MetaProvider(live_settings).discover()
        if "muse-spark-1.3" not in catalog.get("models", []):
            raise ValueError("Pinned model unavailable; no inference or substitution")

    def environment(run_dir, backend, stub, page_url):
        env = clean_environment(run_dir, backend, stub, page_url)
        if live_settings:
            env["ALIVE_META_BASE_URL"] = "https://api.meta.ai/v1"
            env["ALIVE_META_URL"] = "https://api.meta.ai/v1/chat/completions"
            env["ALIVE_META_API_KEY"] = live_settings.alive_meta_api_key
            env["ALIVE_META_MODEL"] = "muse-spark-1.3"
        return env

    runtime_before = None
    records = []

    async def checkpoint(stage, **ctx):
        nonlocal runtime_before
        backend, panel, run_dir = ctx["backend"], ctx["panel"], ctx["run_dir"]
        code, identity = await harness.api_json(backend, "GET", "/provenance")
        assert code == 200
        expected_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        assert identity["source_commit"] == expected_commit, "Unexpected backend commit"
        assert identity["module_sha256"] == {
            str(p.relative_to(ROOT)).replace("\\", "/"): file_digest(p)
            for p in sorted((ROOT / "alive").rglob("*.py"))
        }, "Backend module mismatch"
        expected_db = hashlib.sha256(str((run_dir / "native.db").resolve()).encode()).hexdigest()
        assert identity["database"]["fingerprint"] == expected_db, "Unexpected database"
        assert urlsplit(backend).port != 8000
        if stage == "connected":
            runtime_before = identity
            proof = await panel.evaluate(
                "(await chrome.storage.session.get('backendProvenance')).backendProvenance"
            )
            assert proof == identity, "Extension did not verify this backend"
            assert (
                await panel.evaluate("(await chrome.storage.local.get('backend')).backend")
                == backend
            )
            assert ctx["evidence"]["environment"]["panel_opened_as_ordinary_tab"] is False
            status, _ = await harness.api_json(
                backend,
                "POST",
                "/cognition/configuration",
                {
                    "session_calls": 8,
                    "experiment_calls": 8,
                    "session_tokens": 12000,
                    "experiment_tokens": 12000,
                    "output_tokens": 512,
                    "request_tokens": 8000,
                    "investigation_tokens": 8000,
                },
            )
            assert status == 200
            corpus = {
                key: {
                    "text": value[0],
                    "source_adequate_label": value[1],
                    "source": value[2],
                    "sha256": harness.digest(value[0]),
                    "operator_rating": RATINGS.get(key),
                }
                for key, value in CASES.items()
            }
            (run_dir / "protocol.json").write_text(
                json.dumps(
                    {
                        "version": "alive11-native-v1",
                        "frozen_at": datetime.now(UTC).isoformat(),
                        "source_commit": expected_commit,
                        "provider": args.provider,
                        "model": "muse-spark-1.3",
                        "max_calls": 8,
                        "max_tokens": 12000,
                        "max_estimated_usd": 0.10,
                        "automatic_retries": 0,
                        "goal": GOAL,
                        "corpus": corpus,
                        "ratings_are_operator_interventions": True,
                        "utility_advantage_claim": False,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            extension = run_dir / "extension"
            assert "8000" not in (extension / "config.js").read_text()
            ctx["evidence"]["isolation"] = {
                "backend_identity": identity,
                "extension_sha256": {
                    p.name: file_digest(p) for p in extension.iterdir() if p.is_file()
                },
                "legacy_backend_not_in_allowed_config": True,
                "provider_origin": identity["provider_origin"],
                "started_at": datetime.now(UTC).isoformat(),
            }
            # Guard probes run against this same isolated backend, without dispatch.
            _, audit_goal = await harness.api_json(
                backend, "POST", harness.ROOT_API + "/goals", {"instruction": GOAL}
            )
            guards = {}
            for mode in ["expired", "revoked"]:
                _, grant = await harness.api_json(
                    backend,
                    "POST",
                    harness.ROOT_API + "/grants",
                    {
                        "goal_id": audit_goal["id"],
                        "url": ctx["page"].url,
                        "tab_key": "isolated-permission-audit",
                        "approved": True,
                    },
                )
                _, shot = await harness.api_json(
                    backend,
                    "POST",
                    harness.ROOT_API + "/snapshots",
                    {
                        "grant_id": grant["id"],
                        "url": ctx["page"].url,
                        "title": "Permission audit",
                        "text": content("initial"),
                        "reviewed_sha256": harness.digest(content("initial")),
                    },
                )
                if mode == "expired":
                    data = grant["data"] | {
                        "expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
                    }
                    with sqlite3.connect(run_dir / "native.db") as db:
                        db.execute(
                            "UPDATE web_experiences SET data=? WHERE id=?",
                            (json.dumps(data), grant["id"]),
                        )
                else:
                    await harness.api_json(
                        backend, "POST", harness.ROOT_API + "/grants/" + grant["id"] + "/revoke", {}
                    )
                status, _ = await harness.api_json(
                    backend,
                    "POST",
                    harness.ROOT_API + "/analyse",
                    {
                        "snapshot_id": shot["snapshot"]["id"],
                        "reviewed_sha256": harness.digest(content("initial")),
                        "send_to_meta": True,
                        "owner_correction": True,
                    },
                )
                assert status == 403
                guards[mode + "_grant_correction"] = status
            assert harness.note_count(run_dir / "native.db") == 0
            ctx["evidence"]["isolated_api_guard_probes"] = guards
        if stage == "distinct-1":
            selected = await panel.evaluate(
                "(await chrome.storage.session.get('selected')).selected"
            )
            note_id = await panel.evaluate("(await chrome.storage.session.get('noteId')).noteId")
            before = (await harness.api_json(backend, "GET", harness.ROOT_API))[1]["policy"]["data"]
            status, duplicate = await harness.api_json(
                backend,
                "POST",
                harness.ROOT_API + "/feedback",
                {"note_id": note_id, "useful": False},
            )
            assert status == 200 and duplicate["idempotent"] is True
            data = selected["snapshot"]["data"]
            await harness.api_json(
                backend,
                "POST",
                harness.ROOT_API + "/snapshots",
                {
                    "grant_id": selected["snapshot"]["parent_id"],
                    "url": data["url"],
                    "title": "Repeated controlled excerpt",
                    "text": data["text"],
                    "reviewed_sha256": data["sha256"],
                },
            )
            after = (await harness.api_json(backend, "GET", harness.ROOT_API))[1]["policy"]["data"]
            assert before == after
            ctx["evidence"]["repeat_evidence_probe"] = {"unchanged_policy": True, "support": 1}
        if stage == "suppressed":
            selected = await panel.evaluate(
                "(await chrome.storage.session.get('selected')).selected"
            )
            before = (await harness.api_json(backend, "GET", harness.ROOT_API))[1]
            await harness.api_json(
                backend, "POST", "/cognition/configuration", {"session_calls": 0}
            )
            status, _ = await harness.api_json(
                backend,
                "POST",
                harness.ROOT_API + "/analyse",
                {
                    "snapshot_id": selected["snapshot"]["id"],
                    "reviewed_sha256": selected["snapshot"]["data"]["sha256"],
                    "send_to_meta": True,
                    "owner_correction": True,
                },
            )
            after = (await harness.api_json(backend, "GET", harness.ROOT_API))[1]
            assert status == 409 and before["policy"] == after["policy"]
            assert before["corrections"] == after["corrections"]
            await harness.api_json(
                backend,
                "POST",
                "/cognition/configuration",
                {
                    "session_calls": 8,
                    "experiment_calls": 8,
                    "session_tokens": 12000,
                    "experiment_tokens": 12000,
                    "output_tokens": 512,
                    "request_tokens": 8000,
                    "investigation_tokens": 8000,
                },
            )
            ctx["evidence"]["rejected_correction"] = {
                "http": 409,
                "policy_unchanged": True,
                "corrections_unchanged": True,
            }
        if stage == "probe_due":
            with sqlite3.connect(run_dir / "native.db") as db:
                paused = [
                    json.loads(r[1]) | {"id": r[0]}
                    for r in db.execute("SELECT id,data FROM web_experiences WHERE kind='snapshot'")
                    if json.loads(r[1])["text"] in [content(f"paused-{i}") for i in range(1, 4)]
                ]
            before = len(ctx["stub_server"].calls)
            for shot in paused:
                response = await harness.api(
                    backend,
                    "POST",
                    harness.ROOT_API + "/analyse",
                    {
                        "snapshot_id": shot["id"],
                        "reviewed_sha256": shot["sha256"],
                        "send_to_meta": True,
                    },
                )
                assert response.status_code == 409
            assert len(ctx["stub_server"].calls) == before
            ctx["evidence"]["stale_probe_checks"] = {"rejected_snapshots": len(paused), "http": 409}
            assert len(paused) == 3
        if stage == "restarted":
            assert identity["runtime_instance"] != runtime_before["runtime_instance"]
            assert identity["database"] == runtime_before["database"]
            await harness.connect_panel(panel, backend)
        if stage in {"distinct-1", "distinct-3", "suppressed", "recovered"}:
            await panel.screenshot(run_dir / (stage + ".png"))
        records.append(
            {
                "stage": stage,
                "at": datetime.now(UTC).isoformat(),
                "runtime_instance": identity["runtime_instance"],
            }
        )
        (run_dir / "checkpoints.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        if stage == "finished":
            # Three real pipeline analyses share identical inputs between the two
            # nonadaptive arms; do not invent a second paid copy of each response.
            await harness.api_json(
                backend,
                "POST",
                "/cognition/configuration",
                {
                    "session_calls": 8,
                    "experiment_calls": 8,
                    "session_tokens": 12000,
                    "experiment_tokens": 12000,
                    "output_tokens": 512,
                    "request_tokens": 8000,
                    "investigation_tokens": 8000,
                },
            )
            await panel.evaluate("document.querySelector('#goal').value=" + json.dumps(GOAL))
            await panel.click("#save-goal")
            await panel.wait("document.querySelector('#status').textContent.includes('Goal saved')")
            await harness.start_page(panel, ctx["page"].url, "post-restart", content)
            baseline = []
            previous = None
            for marker in ["suppressed-1", "paused-2", "probe-1"]:
                selected, _ = await harness.send_observation(
                    panel, ctx["page"], marker, previous, content
                )
                previous = selected["snapshot"]["id"]
                assert selected["decision"]["action"] == "analyse"
                await panel.click("#analyse")
                note = await harness.settle_note(panel, backend, selected)
                assert note["status"] == "validated", note["data"].get("error")
                baseline.append(
                    {
                        "case": marker,
                        "sha256": selected["snapshot"]["data"]["sha256"],
                        "note_id": note["id"],
                        "usage": note["data"]["usage"],
                        "estimated_usd": note["data"]["estimated_usd"],
                        "owner_usefulness": None,
                        "quote_valid": True,
                    }
                )
            (run_dir / "native-baselines.json").write_text(
                json.dumps(
                    {
                        "kind": "native pipeline, three matched relevant excerpts",
                        "arms": ["frozen_nonadaptive", "constant_analyse_when_authorised"],
                        "identical_requests_share_responses": True,
                        "independent_arm_replications": False,
                        "responses": baseline,
                        "utility_advantage_claim": False,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            with sqlite3.connect(run_dir / "native.db") as db:
                rows = [
                    {"id": r[0], "kind": r[1], "status": r[2], "data": json.loads(r[3])}
                    for r in db.execute("SELECT id,kind,status,data FROM web_experiences")
                ]
            (run_dir / "experience.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
            assert all(n["data"]["model"] == "muse-spark-1.3" for n in rows if n["kind"] == "note")
            assert len([r for r in rows if r["kind"] == "note"]) == 8
        if stage == args.capture_stage and args.hold_seconds:
            print("Docked qualification ready for window capture: " + stage, flush=True)
            await asyncio.sleep(min(args.hold_seconds, 60))

    args.run_name = "native11"
    args.headful = True
    args.require_docked = True
    WorkbenchPage.provider_mode = args.provider
    await harness.main(
        args,
        content_fn=content,
        checkpoint=checkpoint,
        environment_fn=environment,
        goal=GOAL,
        page_handler=WorkbenchPage,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["synthetic", "meta"], default="synthetic")
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--credentials-env-file", type=Path)
    parser.add_argument("--hold-seconds", type=int, default=0)
    parser.add_argument(
        "--capture-stage", choices=["suppressed", "recovered", "finished"], default="recovered"
    )
    parser.add_argument("--allow-dirty-diagnostic", action="store_true")
    asyncio.run(qualify(parser.parse_args()))
