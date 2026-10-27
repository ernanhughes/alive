"""Transparent empirical action values, updated only from completed browser feedback."""

import copy
import hashlib
import json
import re

CONTEXT = "controlled-source-replaced/resolve-current-claim/v1"
POLICY_VERSION = "empirical-outcome-mean-v1"
ACTIONS = ("monitor", "retrieve")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def choose(policy, context=CONTEXT):
    cells = policy.get("contexts", {}).get(context, {})
    predictions = {}
    for action in ACTIONS:
        cell = cells.get(action, {"n": 0, "sum": 0})
        predictions[action] = {
            "n": cell["n"],
            "mean": cell["sum"] / cell["n"] if cell["n"] else 0.0,
            "status": "observed mean; small-sample uncertainty"
            if cell["n"]
            else "unknown; zero prior",
        }
    action = max(ACTIONS, key=lambda a: predictions[a]["mean"])
    return {
        "action": action,
        "predictions": predictions,
        "policy_hash": digest(policy),
        "policy_version": policy.get("version", 0),
        "algorithm": POLICY_VERSION,
        "reason": "Highest observed mean reward; unseen actions use zero prior. "
        "Ties prefer lower-resource monitoring. No model-generated choice.",
    }


def update(policy, action, reward, context=CONTEXT):
    if action not in ACTIONS or not -1.15 <= reward <= 1:
        raise ValueError("Invalid completed transition")
    result = copy.deepcopy(policy)
    cell = (
        result.setdefault("contexts", {})
        .setdefault(context, {})
        .setdefault(action, {"n": 0, "sum": 0.0})
    )
    cell["n"] += 1
    cell["sum"] += reward
    result["version"] = result.get("version", 0) + 1
    return result


def state_from_dom(text, provider="meta"):
    claim = re.search(r"Claim: Aster endurance_hours (\d+);", text)
    if not claim or "History event: source_replaced;" not in text:
        raise ValueError("Controlled browser observation lacks the required claim/history")
    state = {
        "subject": "Aster",
        "predicate": "endurance_hours",
        "claim": claim.group(1),
        "recent_event": "source_replaced",
        "goal": "resolve-current-claim",
    }
    context = CONTEXT if provider == "meta" else CONTEXT + "/controlled-fixture"
    return state | {"context": context, "feature_hash": digest(state)}


def visible_measurement(text, feedback=False):
    prefix = "Feedback measurement" if feedback else "Instrument reading"
    match = re.search(prefix + r": (\d+) hours;", text)
    if not match:
        raise ValueError("Required browser evidence is absent")
    return match.group(1)


def world_html():
    # Hidden text is excluded by Browsers.SAFE_TEXT until an explicit permitted click.
    # This is a controlled fixture, not a blind experiment or a production sensor.
    return """<!doctype html><html lang="en"><meta charset="utf-8">
<title>ALIVE · Living research habitat</title>
<style>body{background:#101a18;color:#e4f0d9;font:18px system-ui;max-width:850px;
margin:60px auto;padding:24px}section{border:1px solid #516245;padding:24px;margin:20px 0}
button{background:#c7ed9d;padding:14px;border:0;border-radius:6px;margin:12px 0}</style>
<h1>A claim, an action, an experience.</h1><p>Controlled synthetic public research habitat.</p>
<main id="situation"><section id="claim">Claim: Aster endurance_hours 32;</section>
<section id="history">History event: source_replaced; the measurement source has changed.
Prior results do not establish the current measurement.</section></main>
<button id="retrieve" data-alive-allow="click"
onclick="document.getElementById('instrument').hidden=false;this.disabled=true">
Retrieve the current instrument evidence</button>
<section id="instrument" hidden>Instrument reading: 20 hours;
Source: current controlled measurement. This is synthetic instrument evidence.</section>
<button id="feedback-button" data-alive-allow="click"
onclick="document.getElementById('feedback').hidden=false;this.disabled=true">
Publish the independent end-of-episode feedback</button>
<section id="feedback" hidden>Feedback measurement: 20 hours;
The current claim needed verification. A supported current conclusion resolves the goal.
Synthetic goal reward: resolved +1, unresolved -0.5; retrieval cost 0.15 resource units.</section>
</html>"""


def numeric_equal(value, measured):
    try:
        return float(value) == float(measured)
    except ValueError:
        return False
