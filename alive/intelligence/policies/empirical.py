"""Immutable bridge to the existing two-action Aster empirical policy."""

import json

from pydantic import Field, model_validator

from alive import living_policy

from ..contracts import Contract, Number, Origin, digest


class NotSupported(ValueError):
    """The existing empirical context or vocabulary cannot represent this request."""


class Cell(Contract):
    n: int = Field(default=0, ge=0, le=100000000)
    total: Number = 0

    @model_validator(mode="after")
    def bounds(self):
        if not -1.15 * self.n <= self.total <= self.n:
            raise ValueError("Inconsistent empirical samples")
        return self


class EmpiricalPolicy(Contract):
    origin: Origin
    revision: int = Field(default=0, ge=0, le=200000000)
    monitor: Cell = Cell()
    retrieve: Cell = Cell()

    @model_validator(mode="after")
    def sample_revision(self):
        if self.revision != self.monitor.n + self.retrieve.n:
            raise ValueError("Revision must match sample count")
        if self.origin == "simulator":
            raise ValueError("not_supported: empirical simulator context")
        return self

    @property
    def context_key(self):
        suffix = "/controlled-fixture" if self.origin == "fixture" else ""
        return living_policy.CONTEXT + suffix

    def data(self):
        return {
            "version": self.revision,
            "contexts": {
                self.context_key: {
                    a: {"n": getattr(self, a).n, "sum": getattr(self, a).total}
                    for a in living_policy.ACTIONS
                }
            },
        }

    @property
    def hash(self):
        return digest(self)

    def rank(self, candidates):
        if any(c.action not in living_policy.ACTIONS for c in candidates):
            raise NotSupported("not_supported: empirical action")
        original = living_policy.choose(self.data(), self.context_key)
        # Restrict the existing ordered ranking to caller-permitted candidates.
        allowed = {c.action: c for c in candidates}
        action = max(
            (a for a in living_policy.ACTIONS if a in allowed),
            key=lambda a: original["predictions"][a]["mean"],
            default=None,
        )
        return allowed.get(action), original

    def updated(self, action, reward):
        raw = living_policy.update(self.data(), action, reward, self.context_key)
        cells = raw["contexts"][self.context_key]
        return EmpiricalPolicy(
            origin=self.origin,
            revision=raw["version"],
            **{a: Cell(n=cells[a]["n"], total=cells[a]["sum"]) for a in living_policy.ACTIONS},
        )

    def snapshot_json(self):
        """Portable frozen state; no automatic file or service persistence."""
        return json.dumps(self.model_dump(), sort_keys=True)
