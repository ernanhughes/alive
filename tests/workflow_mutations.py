"""Opt-in pytest-only mutation plugin. Never imported by the application."""

import os

import pytest

from alive.workflows import context, runner
from alive.workflows.models import WorkflowRun


@pytest.fixture(autouse=True)
def controlled_mutation(monkeypatch):
    mutation = os.environ.get("ALIVE_PI02B_MUTATION", "")
    guards = {
        "operation": (runner, "operation_not_authorized_or_executable"),
        "hash": (context, "definition_integrity"),
        "budget": (runner, "workflow_budget"),
        "admission": (context, "model_stage_claim_required"),
        "pi_success": (runner, "unsettled_pi"),
        "evidence": (context, "context_scope_or_integrity"),
    }
    if mutation in guards:
        module, category = guards[mutation]
        original = module.require
        monkeypatch.setattr(
            module,
            "require",
            lambda value, reason: None if reason == category else original(value, reason),
        )
    elif mutation == "output":
        monkeypatch.setattr(runner, "output_valid", lambda *_: None)
    elif mutation == "ambiguity":
        monkeypatch.setattr(runner.states, "UNKNOWN", "COMPLETED")
    elif mutation == "dispatch_fence":
        from alive.pi.egress import PiEgress

        original = PiEgress._dispatch

        async def allow(_session, _call):
            return True

        async def unfenced(self, request_id):
            self.workflow_guard = allow
            return await original(self, request_id)

        monkeypatch.setattr(PiEgress, "_dispatch", unfenced)
    elif mutation in ("claim", "replay"):
        original = runner.update

        class WithoutPendingGuard:
            def where(self, *conditions):
                return original(WorkflowRun).where(
                    *[
                        condition
                        for condition in conditions
                        if not (
                            getattr(getattr(condition, "left", None), "key", None) == "status"
                            and getattr(getattr(condition, "right", None), "value", None)
                            == "PENDING"
                        )
                    ]
                )

        monkeypatch.setattr(
            runner,
            "update",
            lambda model: WithoutPendingGuard() if model is WorkflowRun else original(model),
        )
