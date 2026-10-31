"""Explicit deterministic examples; registration and owner grants remain trusted host actions."""

from alive.capabilities.registry import default_registry


def stage(identifier, operation, version, inputs, dependencies=()):
    capability = default_registry().get(operation, version)
    manifest = capability.manifest
    properties = {
        name: {"type": value["type"]} for name, value in manifest["outputs"]["properties"].items()
    }
    return {
        "id": identifier,
        "title": identifier,
        "type": manifest["execution"]["kind"],
        "operation": operation,
        "capability_version": version,
        "capability_sha256": capability.manifest_sha256,
        "inputs": inputs,
        "depends_on": list(dependencies),
        "output_schema": {"properties": properties, "required": manifest["outputs"]["required"]},
        "limits": {"timeout_seconds": 30},
    }


def finish(stages, producer):
    stages.append(
        stage(
            "compose",
            "report.compose",
            "1.0.0",
            {"records": f"$stage.{producer}.records"},
            (producer,),
        )
    )
    stages.append(
        stage(
            "record",
            "result.record",
            "1.0.0",
            {"result": "$stage.compose.result", "assessment": "$stage.compose.assessment"},
            ("compose",),
        )
    )


def definition(kind):
    batch = {
        "source_ref": {"type": "string"},
        "source_sha256": {"type": "string"},
        "scoped_sha256": {"type": "string"},
        "findings": {"type": "array"},
    }
    inputs = {key: "$input." + key for key in batch}
    if kind == "repository":
        stages = [
            stage(
                "read",
                "repository.inspect",
                "1.1.0",
                {"source_ref": "$input.source_ref", "mode": "read", "paths": "$input.paths"},
            ),
            stage("references", "evidence.validate_references", "1.1.0", inputs, ("read",)),
            stage("locators", "evidence.verify-locators", "1.0.0", inputs, ("references",)),
        ]
        batch["paths"] = {"type": "array"}
        finish(stages, "locators")
    elif kind == "document":
        stages = [
            stage(
                "extract",
                "document.extract",
                "1.0.0",
                {"source_ref": "$input.source_ref", "start": 0, "count": 1, "max_chars": 512},
            ),
            stage("locators", "evidence.verify-locators", "1.0.0", inputs, ("extract",)),
        ]
        finish(stages, "locators")
    elif kind == "comparison":
        batch = {
            f"{side}_{key}": value for side in ("left", "right") for key, value in batch.items()
        }
        batch.update(
            {
                "left_id": {"type": "string"},
                "right_id": {"type": "string"},
                "fields": {"type": "array"},
            }
        )
        stages = [
            stage(
                side,
                "evidence.validate_references",
                "1.1.0",
                {
                    key: f"$input.{side}_{key}"
                    for key in ("source_ref", "source_sha256", "scoped_sha256", "findings")
                },
            )
            for side in ("left", "right")
        ]
        stages.append(
            stage(
                "compare",
                "evidence.compare-claims",
                "1.0.0",
                {
                    "left": "$stage.left.records",
                    "right": "$stage.right.records",
                    "left_id": "$input.left_id",
                    "right_id": "$input.right_id",
                    "mode": "changed",
                    "fields": "$input.fields",
                },
                ("left", "right"),
            )
        )
        finish(stages, "compare")
    else:
        raise ValueError("unsupported deterministic validation example")
    return {
        "schema_version": 1,
        "name": "pi03c-" + kind,
        "version": 1,
        "title": "Captured evidence: " + kind,
        "inputs": batch,
        "stages": stages,
        "limits": {"max_wall_seconds": 120, "max_model_calls": 0, "max_total_output_tokens": 0},
    }
