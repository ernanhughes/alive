"""Reproducible inventory; AST coverage is explicitly not semantic review."""
import ast
import csv
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
files = subprocess.check_output(["git", "ls-tree", "-r", "--name-only",
    "1b6da07b856e497b3a44a9e1b9794e94adff55ab"], cwd=ROOT, text=True).splitlines()
records, tests, surfaces = [], [], []
reviewed = {
    "alive/app.py", "alive/agents.py", "alive/browser.py", "alive/config.py", "alive/db.py",
    "alive/kernel.py", "alive/model_gateway.py", "alive/providers.py", "alive/transport.py",
    "alive/society.py", "alive/attention.py", "alive/demo_live_01.py", "alive/claim_comparison.py",
    "alive/cognitive_schema.py", "alive/models.py", "alive/provenance.py",
}
partial = {
    "alive/cognition.py", "alive/web_experience.py", "alive/research_memory.py",
    "alive/research_relationships.py", "alive/evidence_qualification.py", "alive/cognitive_api.py",
    "alive/experiment/service.py", "alive/experiment_budget.py", "alive/experiment_approval.py",
    "alive/living.py", "alive/memory.py", "alive/research_blind.py", "alive/learning/controller.py",
    "alive/learning/experiment.py", "alive/experience_lab.py", "skill_forge/__init__.py",
    "scripts/alive14r5_experiment.py", "scripts/native_demo_live_01.py", "scripts/native10.py",
    "scripts/archive11.py", "scripts/docker-e2e.py", "scripts/docker-smoke-test.py",
}
for name in files:
    path = ROOT / name
    content = path.read_bytes()
    row = {"path": name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    if path.suffix in (".py", ".js", ".cjs", ".ts", ".tsx", ".ps1", ".sh", ".yaml"):
        row["lines"] = len(content.splitlines())
    if path.suffix == ".py":
        tree = ast.parse(content.decode("utf-8-sig"), filename=name)
        row["ast_parsed"] = True
        row["symbols"] = [{"name": n.name, "line": n.lineno, "end": n.end_lineno,
                           "type": type(n).__name__} for n in ast.walk(tree)
                          if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
        row["imports"] = sorted({n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
                                | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names})
        row["loops"] = [n.lineno for n in ast.walk(tree) if isinstance(n, (ast.For, ast.AsyncFor, ast.While))]
        row["broad_handlers"] = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)
            and (n.type is None or isinstance(n.type, ast.Name) and n.type.id in ("Exception", "BaseException"))]
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_"):
                tests.append({"path": name, "name": n.name, "line": n.lineno,
                    "assertions": sum(isinstance(x, ast.Assert) for x in ast.walk(n)),
                    "raises_contexts": sum(isinstance(x, ast.Attribute) and x.attr == "raises" for x in ast.walk(n)),
                    "decorators": [ast.unparse(d) for d in n.decorator_list]})
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in n.decorator_list:
                    if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in {
                        "get", "post", "delete", "put", "patch", "websocket"} and d.args:
                        surfaces.append({"module": name, "function": n.name, "line": n.lineno,
                                         "decorator": ast.unparse(d)})
    row["semantic_review"] = "detailed" if name in reviewed else "selected critical paths" if name in partial else "not completed"
    records.append(row)
(OUT / "repository-inventory.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
(OUT / "test-inventory.json").write_text(json.dumps(tests, indent=2), encoding="utf-8")
(OUT / "api-surfaces.json").write_text(json.dumps(surfaces, indent=2), encoding="utf-8")
with (OUT / "coverage.csv").open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["path", "lines", "ast_parsed", "semantic_review"])
    writer.writeheader()
    writer.writerows({key: r.get(key, "") for key in writer.fieldnames} for r in records
                    if r["path"].startswith(("alive/", "scripts/", "migrations/", "skill_forge/", "extension/", "dashboard/src/")))
print(json.dumps({"tracked_files": len(records), "python_modules": sum(r.get("ast_parsed", False) for r in records),
                  "test_functions": len(tests), "route_decorators": len(surfaces),
                  "detailed_files": len(reviewed), "selected_path_files": len(partial)}, indent=2))
