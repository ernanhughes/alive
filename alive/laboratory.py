"""Synthetic, deterministic environmental facts; never an answer supplied to role prompts."""

import random

from alive.cognitive_models import Laboratory
from alive.models import Memory, record, uid


async def create_lab(kernel, data):
    rng = random.Random(data.seed)
    subject, predicate = (
        ("Helios battery", "endurance_hours")
        if data.scenario != "contradiction"
        else ("Orion coolant", "temperature_c")
    )
    measured = rng.randint(10, 40)
    advertised = measured if data.scenario == "relevant" else measured + rng.randint(5, 20)
    env_id = uid()
    source = {
        "id": f"sensor:{env_id}:1",
        "subject": subject,
        "predicate": predicate,
        "value": str(measured),
        "classification": "synthetic_public",
        "authority": "controlled_measurement",
        "method": "Seeded laboratory instrument fixture, version 1",
    }
    async with kernel.lock, kernel.db.sessions.begin() as session:
        row = Laboratory(
            id=env_id,
            instance_id=kernel.instance_id,
            scenario=data.scenario,
            state={
                "active": False,
                "subject": subject,
                "predicate": predicate,
                "advertised": str(advertised),
                "noise": 0,
                "environment_terminated": False,
            },
            sources=[source],
        )
        session.add(row)
        event = kernel.add_event(session, "lab.created", {"environment_id": env_id})
        await session.flush()
        session.add(
            Memory(
                instance_id=kernel.instance_id,
                content=f"Prior {subject} {predicate} measurement: {measured - 2}. "
                "This older result may need revision.",
                source_event_id=str(event.event_id),
                metadata_json={
                    "environment_id": env_id,
                    "classification": "synthetic_public",
                    "provenance": "prior controlled measurement",
                },
            )
        )
        await session.flush()
        return record(row)


def lab_view(row):
    state = row.state
    if not state["active"]:
        text = "The research habitat is quiet. Waiting for an environmental change."
    elif row.scenario == "noise":
        text = f"Decorative telemetry pulse {state['noise']}. No research content changed."
    else:
        text = f"Claim: {state['subject']} | {state['predicate']} | {state['advertised']};"
    return {
        "id": row.id,
        "text": text,
        "draft": row.draft,
        "version": row.version,
        "environment_terminated": state["environment_terminated"],
    }


async def inject_lab(kernel, env_id):
    async with kernel.lock, kernel.db.sessions.begin() as session:
        row = await session.get(Laboratory, env_id)
        if not row:
            raise KeyError("Laboratory environment not found")
        row.state = row.state | {"active": True, "noise": row.state["noise"] + 1}
        row.version += 1
        kernel.add_event(
            session, "lab.environment_changed", {"environment_id": row.id, "version": row.version}
        )
        return lab_view(row)


def world_html(env_id):
    return """<!doctype html><html lang="en"><meta charset="utf-8"><title>ALIVE World</title>
<style>body{font:18px system-ui;background:#101a18;color:#e4f0d9;
max-width:800px;margin:70px auto;padding:24px}small{color:#a6c48c}
article,aside{padding:24px;border:1px solid #486045;border-radius:9px;margin:24px 0}
h1{font-weight:500}button{padding:12px;background:#c7ed9d;border:0;border-radius:6px}</style>
<small>ALIVE WORLD / CONTROLLED COGNITIVE LABORATORY</small><h1>A changing environment.</h1>
<p>Observe evidence. Form an objective. Investigate within bounds.</p>
<article id="observation" aria-live="polite">Loading habitat…</article>
<aside><small>LOCAL DRAFT</small><p id="draft">No draft recorded.</p></aside>
<script>
const environment=ENVIRONMENT;
let last='';async function update(){try{
const response=await fetch('/api/v1/lab/world/'+environment);const state=await response.json();
if(last!==state.text){document.querySelector('#observation').textContent=state.text;last=state.text}
document.querySelector('#draft').textContent=state.draft||'No draft recorded.'}catch{}}
update();setInterval(update,350);
</script></html>""".replace("ENVIRONMENT", __import__("json").dumps(env_id))
