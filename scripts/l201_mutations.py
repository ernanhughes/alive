# ruff: noqa: E501  (mutation patterns are exact source text)
"""L2-01 mutation receipts on disposable immutable copies of HEAD. The working tree is never edited.

Each mutant is applied to a fresh `git archive` copy; the copy shadows the installed package
because pytest runs with the copy as the working directory. A kill requires a behavioural test
failure; a mismatched pattern or a collection/setup error is `invalid`. Survivors are reported.

    uv run python scripts/l201_mutations.py [id ...]
"""

import json
import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
NL = "\n"
ADP = "alive/intent/adapters.py"
CON = "alive/intent/context.py"
REC = "alive/intent/recommend.py"
SVC = "alive/intent/service.py"
MOD = "alive/intent/models.py"
PRO = "alive/admission/profiles.py"
RUN = "alive/workflows/runner.py"
ADM = "alive/admission/service.py"

# (id, [(file, old, new), ...], guard)
MUTANTS = [
    (
        "G01",
        [
            (
                ADP,
                "    preserved = interpretation.explicit_goal == original" + NL,
                "    preserved = True" + NL,
            )
        ],
        "goal preservation check",
    ),
    (
        "G02",
        [
            (
                REC,
                "        key = (item.recipe_id, item.recipe_version)" + NL,
                "        key = (item.recipe_id.strip().lower(), item.recipe_version)" + NL,
            )
        ],
        "no fuzzy recipe-id matching",
    ),
    (
        "G03",
        [
            (
                REC,
                "        key = (item.recipe_id, item.recipe_version)" + NL,
                '        key = (item.recipe_id, "1.0.0")' + NL,
            )
        ],
        "exact recipe version",
    ),
    (
        "G04",
        [
            (
                REC,
                '                "resolution": "eligible" if cand.eligible else "ineligible",' + NL,
                '                "resolution": "eligible",' + NL,
            )
        ],
        "eligibility is authoritative",
    ),
    (
        "G05",
        [
            (
                CON,
                '        if recipe.id == INTERPRETER_RECIPE or recipe.status != "active":' + NL,
                '        if recipe.status != "active":' + NL,
            ),
            (
                REC,
                "        if recipe.id == INTERPRETER_RECIPE:" + NL + "            continue" + NL,
                "",
            ),
        ],
        "interpreter recipe is not offered (compound)",
    ),
    (
        "G06",
        [
            (
                SVC,
                '        require(catalogue_sha256(rows) == result["catalogue_sha256"], "catalogue_changed")'
                + NL,
                "",
            )
        ],
        "compose: catalogue the model saw",
    ),
    (
        "G07",
        [
            (
                ADP,
                "    require("
                + NL
                + '        catalogue_sha256(package["catalogue"]) == inputs["catalogue_sha256"],'
                + NL
                + '        "intent_catalogue_changed",'
                + NL
                + "    )"
                + NL,
                "",
            )
        ],
        "adapter: catalogue digest",
    ),
    (
        "G08",
        [(RUN, '        and context["user_goal"] == grant.inputs["objective"]' + NL, "")],
        "fence: goal equals the approved goal",
    ),
    (
        "G09",
        [
            (
                RUN,
                '        and context["catalogue_sha256"] == grant.inputs["catalogue_sha256"]' + NL,
                "",
            )
        ],
        "fence: catalogue digest",
    ),
    (
        "G10",
        [
            (
                RUN,
                "    return ("
                + NL
                + '        stored["instructions"] == INSTRUCTIONS'
                + NL
                + "        and grant.role_contracts.get(call.role) == role_contract()"
                + NL
                + '        and stored.get("context_sha256") == digest(context)'
                + NL
                + '        and context["user_goal"]',
                "    return ("
                + NL
                + '        stored.get("context_sha256") == digest(context)'
                + NL
                + '        and context["user_goal"]',
            )
        ],
        "fence: instructions and role contract",
    ),
    (
        "G11",
        [
            (
                ADP,
                '        "type": source.source_type,'
                + NL
                + '        "label": source.label,'
                + NL
                + '        "classification": source.classification,'
                + NL
                + '        "inventory": files,',
                '        "type": source.source_type,'
                + NL
                + '        "label": source.label,'
                + NL
                + '        "classification": source.classification,'
                + NL
                + '        "inventory": [{**f, "content": next(x["content"] for x in source.content["files"] if x["path"] == f["path"])} for f in files],',
            )
        ],
        "no file content in the interpreter context",
    ),
    (
        "G12",
        [
            (
                SVC,
                '            profile_of(admission.terms).id == INTENT and admission.run_id, "not_an_interpretation"'
                + NL,
                '            admission.run_id, "not_an_interpretation"' + NL,
            )
        ],
        "compose: only interpretation admissions",
    ),
    (
        "G13",
        [
            (
                SVC,
                '            and digest(message.content) == output["sha256"],' + NL,
                "            and True," + NL,
            )
        ],
        "compose: artifact integrity",
    ),
    (
        "G14",
        [
            (
                PRO,
                "        request <= config.request_tokens and request <= config.investigation_tokens,"
                + NL
                + '        "context_exceeds_governor_request_ceiling",'
                + NL
                + "    )"
                + NL
                + "    return {"
                + NL
                + '        "operation": "intent.interpret",',
                "        True,"
                + NL
                + '        "context_exceeds_governor_request_ceiling",'
                + NL
                + "    )"
                + NL
                + "    return {"
                + NL
                + '        "operation": "intent.interpret",',
            )
        ],
        "review: Governor request ceiling",
    ),
    (
        "G15",
        [
            (
                MOD,
                "def immutable(*_):"
                + NL
                + '    raise ImmutableRecord("intent recommendations are immutable")',
                "def immutable(*_):" + NL + "    return None",
            )
        ],
        "recommendation history is immutable",
    ),
    (
        "G16",
        [
            (
                REC,
                '        key=lambda p: (fit[p["addresses"]], -p["suitability"], p["order"]),' + NL,
                '        key=lambda p: (-p["suitability"], p["order"]),' + NL,
            )
        ],
        "model-judged fit orders eligible proposals",
    ),
    (
        "G17",
        [
            (
                REC,
                "    usable = parsed is not None and goal_preserved" + NL,
                "    usable = parsed is not None" + NL,
            )
        ],
        "assemble: unpreserved goal is unusable",
    ),
    (
        "G18",
        [
            (
                REC,
                '        "authorization": {' + NL + '            "execution": "not_authorized",',
                '        "authorization": {' + NL + '            "execution": "authorized",',
            )
        ],
        "recommendation grants nothing",
    ),
    (
        "G19",
        [
            (
                ADM,
                '                or proposed.inputs.get("catalogue_sha256") == current["catalogue_sha256"]'
                + NL,
                "                or True" + NL,
            )
        ],
        "review: catalogue digest bound to the Grant",
    ),
    (
        "G20",
        [
            (
                SVC,
                "        require("
                + NL
                + '            result["original_goal"] == goal'
                + NL
                + '            and result["catalogue_sha256"] == terms["model_disclosure"]["catalogue_sha256"],',
                "        require("
                + NL
                + '            True and result["catalogue_sha256"] == terms["model_disclosure"]["catalogue_sha256"],',
            )
        ],
        "compose: goal is the approved goal",
    ),
    (
        "C01",
        [
            (
                ADP,
                "    require("
                + NL
                + '        catalogue_sha256(package["catalogue"]) == inputs["catalogue_sha256"],'
                + NL
                + '        "intent_catalogue_changed",'
                + NL
                + "    )"
                + NL,
                "",
            ),
            (
                ADM,
                '                or proposed.inputs.get("catalogue_sha256") == current["catalogue_sha256"]'
                + NL,
                "                or True" + NL,
            ),
            (
                ADM,
                '            current == terms["model_disclosure"]' + NL,
                "            True" + NL,
            ),
        ],
        "catalogue binding: adapter + Grant input + disclosure equality (compound)",
    ),
]
TESTS = [
    "tests/test_intent_interpretation.py",
    "tests/test_intent_evaluation.py",
]


def archive(target):
    tar = subprocess.run(["git", "archive", "HEAD"], cwd=ROOT, capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(target)], input=tar.stdout, check=True)


def run(mutant):
    ident, edits, guard = mutant
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=f"alive-{ident}-") as scratch:
        copy = pathlib.Path(scratch)
        archive(copy)
        for rel, old, new in edits:
            path = copy / rel
            text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
            if text.count(old) != 1:
                return {
                    "id": ident,
                    "status": "invalid",
                    "detail": f"pattern matched {text.count(old)} times",
                    "guard": guard,
                }
            path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")
        done = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
            cwd=copy,
            capture_output=True,
            text=True,
        )
    lines = [x for x in done.stdout.splitlines() if x.startswith(("FAILED", "ERROR"))]
    if done.returncode == 0:
        status = "survived"
    elif any(x.startswith("ERROR") for x in lines) or not lines:
        status = "invalid"
    else:
        status = "killed"
    return {
        "id": ident,
        "status": status,
        "detail": lines[0].split(" - ")[0][:120] if lines else done.stdout[-200:],
        "guard": guard,
        "seconds": round(time.monotonic() - started, 1),
    }


if __name__ == "__main__":
    wanted = set(sys.argv[1:])
    for mutant in MUTANTS:
        if not wanted or mutant[0] in wanted:
            print(json.dumps(run(mutant)), flush=True)
