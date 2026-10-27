"""Read-only presentation of completed, hashed simulator evidence."""

import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends

ROOT = Path(".alive/learning")


def artifact(name):
    manifest = json.loads((ROOT / "manifest.json").read_text())
    data = (ROOT / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest[name]:
        raise ValueError("Learning evidence checksum mismatch")
    return json.loads(data)


def router(ready):
    route = APIRouter(prefix="/api/v1/learning", dependencies=[Depends(ready)])

    @route.get("")
    async def status():
        if not (ROOT / "manifest.json").is_file():
            return {
                "available": False,
                "simulation_only": True,
                "reason": "No completed simulation qualification has been published locally",
            }
        return {"available": True, **artifact("result.json")}

    @route.get("/demonstration")
    async def demonstration():
        if not (ROOT / "manifest.json").is_file():
            return {"available": False}
        return {"available": True, **artifact("demonstration.json")}

    return route
