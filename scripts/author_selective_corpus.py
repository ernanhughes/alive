"""Author the AI-FIRST-04 frozen corpus (``selective-corpus/v2``).

Every case carries a hand-written ``expected`` outcome that is independent of the reference
implementation; ``scripts/audit_selective_corpus.py`` cross-checks implementation, reference,
expectation and label before anything is frozen. Task ids are neutral (they leak a family, never
whether the implementation is defective). Run once; the output is then locked.
"""

import json
from pathlib import Path
from textwrap import dedent

OUT = Path(__file__).resolve().parents[1] / "docs/intelligence/selective-corpus-v2.json"
SPLITS = {1: "train", 2: "train", 3: "train", 4: "dev", 5: "dev"}


def v(x):
    return {"value": x}


def err(name):
    return {"error": name}


def task(
    ident,
    contract,
    code,
    cases,
    *,
    reference=None,
    tier="standard",
    mechanisms,
    label="defective",
    files=None,
    input_state="unchanged",
    tolerance=0,
):
    family, number = ident.split("-")
    full = {
        "num": "numeric",
        "par": "parsing",
        "sta": "state",
        "aut": "authorization",
        "def": "defaults",
        "err": "errors",
    }[family]
    code = dedent(code).lstrip("\n")
    reference = dedent(reference).lstrip("\n") if reference else code
    assert (label == "defective") == (reference != code), ident
    return {
        "id": ident,
        "family": full,
        "split": SPLITS.get(int(number), "heldout"),
        "tier": tier,
        "label": label,
        "mechanisms": mechanisms,
        "contract": contract,
        "code": code,
        "reference": reference,
        "input_state": input_state,
        "tolerance": tolerance,
        "cases": [
            {"id": f"c{i}", "input": value, "expected": expected}
            for i, (value, expected) in enumerate(cases, 1)
        ],
    } | ({"files": {k: dedent(t).lstrip("\n") for k, t in files.items()}} if files else {})


TASKS = [
    # ------------------------------------------------------------------ numeric
    task(
        "num-01",
        "Return the whole-dollar amount of an integer number of cents, rounding toward negative "
        "infinity, so -150 cents is -2 dollars.",
        """
        def solve(p):
            return int(p / 100)
        """,
        [(250, v(2)), (100, v(1)), (-150, v(-2)), (-100, v(-1)), (0, v(0))],
        reference="""
        def solve(p):
            return p // 100
        """,
        mechanisms=["numeric.signed_values"],
    ),
    task(
        "num-02",
        "Return the arithmetic mean of a list of numbers. An empty list returns 0.",
        """
        def solve(p):
            return sum(p) / len(p)
        """,
        [([2, 4], v(3)), ([5], v(5)), ([], v(0)), ([-1, 1], v(0))],
        reference="""
        def solve(p):
            return sum(p) / len(p) if p else 0
        """,
        mechanisms=["numeric.empty_or_zero"],
    ),
    task(
        "num-03",
        "Return true when the number lies between 0 and 100, both ends included.",
        """
        def solve(p):
            return 0 < p < 100
        """,
        [(0, v(True)), (50, v(True)), (100, v(True)), (101, v(False)), (-1, v(False))],
        reference="""
        def solve(p):
            return 0 <= p <= 100
        """,
        mechanisms=["numeric.boundary"],
    ),
    task(
        "num-04",
        "Round a non-negative price to two decimals, rounding exact halves up when the decimal "
        "text shows a 5, so 2.675 becomes 2.68.",
        """
        def solve(p):
            return round(p, 2)
        """,
        [(2.675, v(2.68)), (1.005, v(1.01)), (0.125, v(0.13)), (3.14159, v(3.14)), (10, v(10.0))],
        reference="""
        from decimal import ROUND_HALF_UP, Decimal

        def solve(p):
            return float(Decimal(str(p)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        """,
        tier="hard",
        mechanisms=["numeric.rounding"],
    ),
    task(
        "num-05",
        "Return how many integers lie in the inclusive range [a, b] given as the pair [a, b]. "
        "If b is smaller than a the answer is 0.",
        """
        def solve(p):
            return max(0, p[1] - p[0] + 1)
        """,
        [([1, 5], v(5)), ([3, 3], v(1)), ([5, 1], v(0)), ([-2, 2], v(5))],
        label="correct",
        mechanisms=["numeric.counting", "numeric.boundary"],
    ),
    task(
        "num-06",
        "Return the remainder of dividing a by b for the pair [a, b], with b positive. The "
        "remainder is never negative.",
        """
        import math

        def solve(p):
            return math.fmod(p[0], p[1])
        """,
        [([7, 3], v(1)), ([-7, 3], v(2)), ([0, 5], v(0)), ([-1, 5], v(4)), ([10, 5], v(0))],
        reference="""
        def solve(p):
            return p[0] % p[1]
        """,
        mechanisms=["numeric.signed_values"],
    ),
    task(
        "num-07",
        "Split a whole number of seconds into [minutes, seconds] using floor semantics, so -90 "
        "seconds is [-2, 30]. Seconds are always from 0 to 59.",
        """
        def solve(p):
            return [int(p / 60), p % 60]
        """,
        [
            (125, v([2, 5])),
            (60, v([1, 0])),
            (-90, v([-2, 30])),
            (-60, v([-1, 0])),
            (0, v([0, 0])),
        ],
        reference="""
        def solve(p):
            return [p // 60, p % 60]
        """,
        tier="hard",
        mechanisms=["numeric.signed_values"],
    ),
    task(
        "num-08",
        "Return the integer part of a number by dropping its fraction, so -2.7 gives -2.",
        """
        def solve(p):
            return int(p)
        """,
        [(2.7, v(2)), (-2.7, v(-2)), (0.5, v(0)), (-0.5, v(0)), (5, v(5))],
        label="correct",
        mechanisms=["numeric.signed_values"],
    ),
    task(
        "num-09",
        "Return the mean of the values after clamping each into [lo, hi]. Input is "
        "[values, lo, hi]. An empty list returns null.",
        """
        def clamp(x, lo, hi):
            return max(lo, min(x, hi))

        def solve(p):
            values, lo, hi = p
            if not values:
                return None
            total = 0
            count = 0
            for v in values:
                total += clamp(v, lo, hi)
                if lo <= v <= hi:
                    count += 1
            return total / count
        """,
        [
            ([[1, 5, 9], 2, 6], v(13 / 3)),
            ([[3, 4], 0, 10], v(3.5)),
            ([[], 0, 1], v(None)),
            ([[-5, 20], 0, 10], v(5.0)),
        ],
        reference="""
        def clamp(x, lo, hi):
            return max(lo, min(x, hi))

        def solve(p):
            values, lo, hi = p
            if not values:
                return None
            return sum(clamp(v, lo, hi) for v in values) / len(values)
        """,
        tier="hard",
        mechanisms=["numeric.counting"],
        tolerance=1e-9,
    ),
    # ------------------------------------------------------------------ parsing
    task(
        "par-01",
        "Split 'key=value' text at the FIRST equals sign into [key, value]. The value may itself "
        "contain equals signs.",
        """
        def solve(p):
            return p.split("=")[:2]
        """,
        [
            ("a=1", v(["a", "1"])),
            ("url=x=y", v(["url", "x=y"])),
            ("k=", v(["k", ""])),
            ("a=b=c=d", v(["a", "b=c=d"])),
        ],
        reference="""
        def solve(p):
            return p.split("=", 1)
        """,
        mechanisms=["parsing.delimiter_position"],
    ),
    task(
        "par-02",
        "Return the extension of a file name in lower case without the dot. A name with no dot "
        "has the empty extension.",
        """
        def solve(p):
            return p.split(".")[-1].lower()
        """,
        [("a.TXT", v("txt")), ("archive.tar.gz", v("gz")), ("README", v("")), ("x.", v(""))],
        reference="""
        def solve(p):
            return p.rsplit(".", 1)[1].lower() if "." in p else ""
        """,
        mechanisms=["parsing.delimiter_position"],
    ),
    task(
        "par-03",
        "Split a comma-separated line into its fields, keeping empty fields. The empty line has "
        "no fields at all.",
        """
        def solve(p):
            return p.split(",")
        """,
        [("a,b", v(["a", "b"])), ("a,,b", v(["a", "", "b"])), ("", v([])), (",", v(["", ""]))],
        reference="""
        def solve(p):
            return p.split(",") if p else []
        """,
        mechanisms=["parsing.empty_fields"],
    ),
    task(
        "par-04",
        "Remove the prefix '0x' from text when it starts with that prefix. Any other text is "
        "returned unchanged.",
        """
        def solve(p):
            return p.lstrip("0x")
        """,
        [
            ("0xff", v("ff")),
            ("0x0f", v("0f")),
            ("abc", v("abc")),
            ("0x", v("")),
            ("00ab", v("00ab")),
            ("xyz", v("xyz")),
        ],
        reference="""
        def solve(p):
            return p[2:] if p.startswith("0x") else p
        """,
        tier="hard",
        mechanisms=["parsing.trim_and_case"],
    ),
    task(
        "par-05",
        "Split a path into [directory, name] at the LAST slash. A path with no slash has the "
        "empty directory.",
        """
        def solve(p):
            head, _, tail = p.rpartition("/")
            return [head, tail]
        """,
        [
            ("a/b/c", v(["a/b", "c"])),
            ("c", v(["", "c"])),
            ("/x", v(["", "x"])),
            ("a/", v(["a", ""])),
        ],
        label="correct",
        mechanisms=["parsing.delimiter_position"],
    ),
    task(
        "par-06",
        "Parse a string of digits into an integer. The empty string parses to 0.",
        """
        def solve(p):
            return int(p)
        """,
        [("42", v(42)), ("007", v(7)), ("", v(0)), ("0", v(0))],
        reference="""
        def solve(p):
            return int(p) if p else 0
        """,
        mechanisms=["parsing.type_coercion", "parsing.empty_fields"],
    ),
    task(
        "par-07",
        "Return the host part of 'user@host': everything after the LAST at-sign. Text with no "
        "at-sign is returned whole.",
        """
        def solve(p):
            return p.split("@")[1] if "@" in p else p
        """,
        [
            ("u@h", v("h")),
            ("a@b@c.com", v("c.com")),
            ("host", v("host")),
            ("x@", v("")),
            ("@y", v("y")),
        ],
        reference="""
        def solve(p):
            return p.rsplit("@", 1)[1] if "@" in p else p
        """,
        tier="hard",
        mechanisms=["parsing.delimiter_position"],
    ),
    task(
        "par-08",
        "Normalize a tag by trimming surrounding whitespace and lower-casing it. Spaces inside "
        "the tag are kept.",
        """
        def solve(p):
            return p.strip().lower()
        """,
        [
            (" Hello World ", v("hello world")),
            ("ABC", v("abc")),
            ("   ", v("")),
            ("a  b", v("a  b")),
        ],
        label="correct",
        mechanisms=["parsing.trim_and_case"],
    ),
    task(
        "par-09",
        "Read the text 'true' or 'false' in any letter case as a boolean. Any other text is an "
        "error of type ValueError.",
        """
        from text import normalize

        def solve(p):
            return normalize(p) == "true"
        """,
        [
            ("True", v(True)),
            ("FALSE", v(False)),
            ("maybe", err("ValueError")),
            ("", err("ValueError")),
            ("true", v(True)),
        ],
        reference="""
        from text import normalize

        def solve(p):
            word = normalize(p)
            if word not in ("true", "false"):
                raise ValueError(p)
            return word == "true"
        """,
        files={
            "text.py": """
            def normalize(text):
                return text.strip().lower()
            """
        },
        tier="hard",
        mechanisms=["parsing.type_coercion"],
    ),
    # ------------------------------------------------------------------ state
    task(
        "sta-01",
        "Return the strings sorted by length, shortest first. Strings of equal length keep "
        "their original relative order.",
        """
        def solve(p):
            return sorted(p, key=lambda s: (len(s), s))
        """,
        [
            (["cc", "bb", "a"], v(["a", "cc", "bb"])),
            (["b", "a"], v(["b", "a"])),
            ([], v([])),
            (["xyz", "ab", "c"], v(["c", "ab", "xyz"])),
        ],
        reference="""
        def solve(p):
            return sorted(p, key=len)
        """,
        mechanisms=["state.ordering"],
    ),
    task(
        "sta-02",
        "A closed ticket can never be reopened. Input is [state, action] with state 'open' or "
        "'closed'. 'close' always returns 'closed'. 'reopen' returns 'open' for an open ticket "
        "and raises ValueError for a closed one. Any other action raises ValueError.",
        """
        def solve(p):
            state, action = p
            if action == "close":
                return "closed"
            if action == "reopen":
                return "open"
            raise ValueError(action)
        """,
        [
            (["open", "close"], v("closed")),
            (["closed", "reopen"], err("ValueError")),
            (["open", "reopen"], v("open")),
            (["closed", "close"], v("closed")),
            (["open", "pause"], err("ValueError")),
        ],
        reference="""
        def solve(p):
            state, action = p
            if action == "close":
                return "closed"
            if action == "reopen":
                if state == "closed":
                    raise ValueError(action)
                return "open"
            raise ValueError(action)
        """,
        mechanisms=["state.transition_guard"],
    ),
    task(
        "sta-03",
        "Return the list with its first element moved to the end. The argument must not be "
        "modified, and an empty list stays empty.",
        """
        def solve(p):
            p.append(p.pop(0))
            return p
        """,
        [([1, 2, 3], v([2, 3, 1])), ([7], v([7])), ([], v([])), (["a", "b"], v(["b", "a"]))],
        reference="""
        def solve(p):
            return p[1:] + p[:1]
        """,
        mechanisms=["state.input_mutation"],
    ),
    task(
        "sta-04",
        "Collapse each run of identical neighbouring items into one item, keeping the order. "
        "The same item may appear again later.",
        """
        def solve(p):
            return list(dict.fromkeys(p))
        """,
        [
            ([1, 1, 2, 2, 1], v([1, 2, 1])),
            ([3, 3, 3], v([3])),
            ([1, 2, 1], v([1, 2, 1])),
            ([], v([])),
        ],
        reference="""
        def solve(p):
            out = []
            for item in p:
                if not out or out[-1] != item:
                    out.append(item)
            return out
        """,
        tier="hard",
        mechanisms=["state.repeat_application", "state.ordering"],
    ),
    task(
        "sta-05",
        "Return the items in ascending order without modifying the argument.",
        """
        def solve(p):
            q = list(p)
            q.sort()
            return q
        """,
        [
            ([3, 1, 2], v([1, 2, 3])),
            ([], v([])),
            ([2, 2, 1], v([1, 2, 2])),
            (["b", "a"], v(["a", "b"])),
        ],
        label="correct",
        mechanisms=["state.input_mutation"],
    ),
    task(
        "sta-06",
        "Return the squares of the numbers in order. The argument must not be modified.",
        """
        def solve(p):
            for i in range(len(p)):
                p[i] = p[i] * p[i]
            return p
        """,
        [([1, 2, 3], v([1, 4, 9])), ([-2], v([4])), ([], v([])), ([0, 5], v([0, 25]))],
        reference="""
        def solve(p):
            return [x * x for x in p]
        """,
        mechanisms=["state.input_mutation"],
    ),
    task(
        "sta-07",
        "An order moves pending to paid to shipped, and shipped stays shipped. Input is the "
        "current status; return the next status. A cancelled order cannot advance and any "
        "unknown status raises ValueError.",
        """
        NEXT = {"pending": "paid", "paid": "shipped", "shipped": "shipped"}

        def solve(p):
            return NEXT[p]
        """,
        [
            ("pending", v("paid")),
            ("paid", v("shipped")),
            ("shipped", v("shipped")),
            ("cancelled", err("ValueError")),
            ("lost", err("ValueError")),
        ],
        reference="""
        NEXT = {"pending": "paid", "paid": "shipped", "shipped": "shipped"}

        def solve(p):
            if p not in NEXT:
                raise ValueError(p)
            return NEXT[p]
        """,
        tier="hard",
        mechanisms=["state.transition_guard", "errors.wrong_type"],
    ),
    task(
        "sta-08",
        "Connection events: from 'idle' only 'connect' is allowed (result 'connected'); from "
        "'connected' 'send' keeps 'connected' and 'close' gives 'closed'; a 'closed' connection "
        "accepts nothing. Input is [state, event]. A disallowed event raises ValueError.",
        """
        ALLOWED = {"idle": {"connect"}, "connected": {"send", "close"}, "closed": set()}
        RESULT = {"connect": "connected", "send": "connected", "close": "closed"}

        def solve(p):
            state, event = p
            if event not in ALLOWED[state]:
                raise ValueError(event)
            return RESULT[event]
        """,
        [
            (["idle", "connect"], v("connected")),
            (["connected", "send"], v("connected")),
            (["closed", "connect"], err("ValueError")),
            (["idle", "send"], err("ValueError")),
            (["connected", "close"], v("closed")),
        ],
        label="correct",
        tier="hard",
        mechanisms=["state.transition_guard"],
    ),
    task(
        "sta-09",
        "Return the two most frequent words, most frequent first. Words with the same count are "
        "ordered by which appeared first in the input.",
        """
        from collections import Counter

        def solve(p):
            counts = Counter(p)
            return sorted(counts, key=lambda w: (-counts[w], w))[:2]
        """,
        [
            (["b", "a", "a", "b", "c"], v(["b", "a"])),
            (["x", "y", "x"], v(["x", "y"])),
            (["q"], v(["q"])),
            ([], v([])),
            (["b", "a", "c", "a"], v(["a", "b"])),
        ],
        reference="""
        from collections import Counter

        def solve(p):
            return [word for word, _ in Counter(p).most_common(2)]
        """,
        tier="hard",
        mechanisms=["state.ordering"],
    ),
    # ------------------------------------------------------------------ authorization
    task(
        "aut-01",
        "Decide whether a role may perform an action. Input is [policy, role, action] where the "
        "policy maps each action to the list of roles allowed. An action absent from the policy "
        "is denied for everyone.",
        """
        def solve(p):
            policy, role, action = p
            return role in policy.get(action, [role])
        """,
        [
            ([{"read": ["a", "b"]}, "a", "read"], v(True)),
            ([{"read": ["a"]}, "b", "read"], v(False)),
            ([{"read": ["a"]}, "a", "delete"], v(False)),
            ([{}, "a", "read"], v(False)),
        ],
        reference="""
        def solve(p):
            policy, role, action = p
            return role in policy.get(action, [])
        """,
        mechanisms=["authz.default_deny"],
    ),
    task(
        "aut-02",
        "Return true when the role is exactly one of the allowed roles. Input is "
        "[role, allowed_roles].",
        """
        def solve(p):
            return p[0] in " ".join(p[1])
        """,
        [
            (["admin", ["admin", "editor"]], v(True)),
            (["edit", ["editor"]], v(False)),
            (["admin", ["superadmin"]], v(False)),
            (["guest", ["admin", "editor"]], v(False)),
            (["editor", ["admin", "editor"]], v(True)),
        ],
        reference="""
        def solve(p):
            return p[0] in p[1]
        """,
        mechanisms=["authz.substring_match"],
    ),
    task(
        "aut-03",
        "Allow access when the user is active AND (is an administrator OR owns the resource). "
        "Input is [active, is_admin, owns].",
        """
        def solve(p):
            return p[0] and p[1] or p[2]
        """,
        [
            ([True, True, False], v(True)),
            ([False, False, True], v(False)),
            ([True, False, True], v(True)),
            ([True, False, False], v(False)),
            ([False, True, True], v(False)),
        ],
        reference="""
        def solve(p):
            return p[0] and (p[1] or p[2])
        """,
        mechanisms=["authz.precedence"],
    ),
    task(
        "aut-04",
        "A user may open a document only when the document's tenant id equals the user's tenant "
        "id exactly. Input is [user_tenant, document_tenant].",
        """
        def solve(p):
            return p[1].startswith(p[0])
        """,
        [
            (["acme", "acme"], v(True)),
            (["acme", "acme2"], v(False)),
            (["acme", "acm"], v(False)),
            (["", "x"], v(False)),
            (["a-1", "a-1"], v(True)),
        ],
        reference="""
        def solve(p):
            return p[0] == p[1]
        """,
        tier="hard",
        mechanisms=["authz.scope_boundary", "authz.substring_match"],
    ),
    task(
        "aut-05",
        "Return true only for an action name that appears in the allowed list, compared "
        "exactly. Input is [allowed_actions, action].",
        """
        def solve(p):
            try:
                return p[0].index(p[1]) >= 0
            except ValueError:
                return False
        """,
        [
            ([["read", "write"], "read"], v(True)),
            ([[], "read"], v(False)),
            ([["read"], "write"], v(False)),
            ([["Read"], "read"], v(False)),
        ],
        label="correct",
        mechanisms=["authz.default_deny"],
    ),
    task(
        "aut-06",
        "Look up the permissions of a role. Input is [role_table, role]. A role that is "
        "missing from the table, including null, has no permissions: return an empty list.",
        """
        def solve(p):
            table, role = p
            return table.get(role, table["guest"])
        """,
        [
            ([{"admin": ["rw"], "guest": ["r"]}, "admin"], v(["rw"])),
            ([{"admin": ["rw"], "guest": ["r"]}, "ghost"], v([])),
            ([{"admin": ["rw"], "guest": ["r"]}, None], v([])),
            ([{"admin": ["rw"], "guest": ["r"]}, "guest"], v(["r"])),
        ],
        reference="""
        def solve(p):
            table, role = p
            return table.get(role, [])
        """,
        tier="hard",
        mechanisms=["authz.default_deny"],
    ),
    task(
        "aut-07",
        "A suspended user is always denied, even an administrator. Otherwise allow "
        "administrators and users holding the permission. Input is "
        "[suspended, is_admin, has_permission].",
        """
        def solve(p):
            if p[1]:
                return True
            return (not p[0]) and p[2]
        """,
        [
            ([False, True, False], v(True)),
            ([True, True, False], v(False)),
            ([True, False, True], v(False)),
            ([False, False, True], v(True)),
            ([False, False, False], v(False)),
        ],
        reference="""
        def solve(p):
            if p[0]:
                return False
            return p[1] or p[2]
        """,
        tier="hard",
        mechanisms=["authz.precedence"],
    ),
    task(
        "aut-08",
        "A path is inside a directory when the directory is a path prefix ending on a '/' "
        "boundary: '/data' contains '/data' and '/data/x' but not '/database'. Input is "
        "[directory, path].",
        """
        def solve(p):
            return p[1].startswith(p[0])
        """,
        [
            (["/data", "/data/x"], v(True)),
            (["/data", "/database"], v(False)),
            (["/data", "/data"], v(True)),
            (["/data", "/dat"], v(False)),
            (["/a/b", "/a/b/c/d"], v(True)),
        ],
        reference="""
        def solve(p):
            return p[1] == p[0] or p[1].startswith(p[0] + "/")
        """,
        tier="hard",
        mechanisms=["authz.substring_match", "authz.scope_boundary"],
    ),
    task(
        "aut-09",
        "A path is inside a directory when the directory is a path prefix ending on a '/' "
        "boundary; a trailing slash on the directory is ignored and '/' contains every "
        "absolute path. Input is [directory, path].",
        """
        def solve(p):
            return p[1] == p[0] or p[1].startswith(p[0].rstrip("/") + "/")
        """,
        [
            (["/data", "/data/x"], v(True)),
            (["/data/", "/data/x"], v(True)),
            (["/data", "/database"], v(False)),
            (["/", "/etc"], v(True)),
            (["/data", "/da"], v(False)),
        ],
        label="correct",
        mechanisms=["authz.scope_boundary"],
    ),
    # ------------------------------------------------------------------ defaults
    task(
        "def-01",
        "Build the effective settings from [defaults, user, env] (three dicts). Start from the "
        "defaults, apply the user's values, then the environment's values; a later source "
        "overrides an earlier one.",
        """
        def solve(p):
            return {**p[2], **p[1], **p[0]}
        """,
        [
            ([{"a": 1}, {}, {}], v({"a": 1})),
            ([{"a": 1}, {"a": 2}, {}], v({"a": 2})),
            ([{"a": 1}, {"a": 2}, {"a": 3}], v({"a": 3})),
            ([{}, {"b": 1}, {"c": 2}], v({"b": 1, "c": 2})),
        ],
        reference="""
        def solve(p):
            return {**p[0], **p[1], **p[2]}
        """,
        mechanisms=["defaults.override_precedence"],
    ),
    task(
        "def-02",
        "Return the display name: the 'nickname' value when the key is present, whatever that "
        "value is (an empty string and null included), otherwise the 'name' value.",
        """
        def solve(p):
            return p.get("nickname") or p["name"]
        """,
        [
            ({"name": "Ann"}, v("Ann")),
            ({"name": "Ann", "nickname": "A"}, v("A")),
            ({"name": "Ann", "nickname": ""}, v("")),
            ({"name": "Bo", "nickname": None}, v(None)),
        ],
        reference="""
        def solve(p):
            return p["nickname"] if "nickname" in p else p["name"]
        """,
        mechanisms=["defaults.falsy_vs_missing"],
    ),
    task(
        "def-03",
        "Merge the configurations [base, override]. Where both sides hold a dict, merge those "
        "dicts the same way recursively; otherwise the override's value replaces the base's.",
        """
        def solve(p):
            return {**p[0], **p[1]}
        """,
        [
            ([{"a": {"x": 1}}, {"a": {"y": 2}}], v({"a": {"x": 1, "y": 2}})),
            ([{"a": 1}, {"b": 2}], v({"a": 1, "b": 2})),
            ([{"a": {"x": 1}}, {"a": 5}], v({"a": 5})),
            ([{}, {}], v({})),
        ],
        reference="""
        def merge(a, b):
            out = dict(a)
            for k, val in b.items():
                if isinstance(val, dict) and isinstance(out.get(k), dict):
                    out[k] = merge(out[k], val)
                else:
                    out[k] = val
            return out

        def solve(p):
            return merge(p[0], p[1])
        """,
        mechanisms=["defaults.merge_depth"],
    ),
    task(
        "def-04",
        "Return the page size: 20 when 'size' is missing or null, otherwise the given value. An "
        "explicit 0 is kept.",
        """
        def solve(p):
            return p["size"] if p.get("size") else 20
        """,
        [({}, v(20)), ({"size": None}, v(20)), ({"size": 0}, v(0)), ({"size": 50}, v(50))],
        reference="""
        def solve(p):
            return 20 if p.get("size") is None else p["size"]
        """,
        tier="hard",
        mechanisms=["defaults.falsy_vs_missing"],
    ),
    task(
        "def-05",
        "Return the first value in the list that is not null, or the text 'none' when every "
        "value is null or the list is empty.",
        """
        def solve(p):
            for item in p:
                if item is not None:
                    return item
            return "none"
        """,
        [
            ([None, 0, 5], v(0)),
            ([None, None, None], v("none")),
            (["", None, 1], v("")),
            ([], v("none")),
        ],
        label="correct",
        mechanisms=["defaults.falsy_vs_missing"],
    ),
    task(
        "def-06",
        "Fill gaps in a record from a template. Input is [template, record]. Keys missing from "
        "the record are copied from the template, recursively for nested dicts; the record's "
        "own values always win. Return the filled record and do not modify either argument.",
        """
        from fill import fill

        def solve(p):
            return fill(p[0], p[1])
        """,
        [
            (
                [{"a": 1, "n": {"x": 1, "y": 2}}, {"n": {"x": 9}}],
                v({"a": 1, "n": {"x": 9, "y": 2}}),
            ),
            ([{"a": 1}, {}], v({"a": 1})),
            ([{"a": 1}, {"a": 0}], v({"a": 0})),
            ([{}, {"z": 1}], v({"z": 1})),
        ],
        reference="""
        def fill(template, record):
            out = dict(record)
            for key, value in template.items():
                if key not in out:
                    out[key] = value
                elif isinstance(value, dict) and isinstance(out[key], dict):
                    out[key] = fill(value, out[key])
            return out

        def solve(p):
            return fill(p[0], p[1])
        """,
        files={
            "fill.py": """
            def fill(template, record):
                for key, value in template.items():
                    if key not in record:
                        record[key] = value
                return record
            """
        },
        tier="hard",
        mechanisms=["defaults.merge_depth", "state.input_mutation"],
    ),
    task(
        "def-07",
        "Return the retry count. Use 'retries' when that key is present, whatever its value, "
        "otherwise use 'max_retries' when present, otherwise 3.",
        """
        def solve(p):
            return p.get("retries", p.get("max_retries", 3))
        """,
        [
            ({}, v(3)),
            ({"retries": 0}, v(0)),
            ({"max_retries": 7}, v(7)),
            ({"retries": 2, "max_retries": 7}, v(2)),
            ({"retries": None}, v(None)),
        ],
        label="correct",
        tier="hard",
        mechanisms=["defaults.falsy_vs_missing"],
    ),
    task(
        "def-08",
        "Resolve a setting from [cli, env, file]. Use the command-line value when it is not "
        "null, else the environment value when it is not null, else the file value when it is "
        "not null, else 10. A value of 0 is a real value.",
        """
        def solve(p):
            return p[0] or p[1] or p[2] or 10
        """,
        [
            ([None, None, None], v(10)),
            ([5, None, None], v(5)),
            ([None, 7, 3], v(7)),
            ([0, 7, 3], v(0)),
            ([None, 0, 3], v(0)),
            ([None, None, 0], v(0)),
        ],
        reference="""
        def solve(p):
            for value in p:
                if value is not None:
                    return value
            return 10
        """,
        tier="hard",
        mechanisms=["defaults.override_precedence", "defaults.falsy_vs_missing"],
    ),
    task(
        "def-09",
        "Combine two dicts of lists [base, extra]. For a key in both, the result is the base "
        "list followed by the extra list; keys in only one dict are kept as they are.",
        """
        def solve(p):
            return {**p[0], **p[1]}
        """,
        [
            ([{"a": [1]}, {"a": [2], "b": [3]}], v({"a": [1, 2], "b": [3]})),
            ([{}, {}], v({})),
            ([{"a": [1]}, {}], v({"a": [1]})),
            ([{"a": []}, {"a": [9]}], v({"a": [9]})),
        ],
        reference="""
        def solve(p):
            out = {k: list(items) for k, items in p[0].items()}
            for k, items in p[1].items():
                out[k] = out.get(k, []) + items
            return out
        """,
        mechanisms=["defaults.merge_depth"],
    ),
    # ------------------------------------------------------------------ errors
    task(
        "err-01",
        "Parse an integer from text. Text that is not an integer must raise ValueError and "
        "never produce a default value.",
        """
        def solve(p):
            try:
                return int(p)
            except ValueError:
                return 0
        """,
        [("12", v(12)), ("x", err("ValueError")), ("", err("ValueError")), ("-3", v(-3))],
        reference="""
        def solve(p):
            return int(p)
        """,
        mechanisms=["errors.swallowed"],
    ),
    task(
        "err-02",
        "Return the value stored under a key in a dict. Input is [dict, key]. A missing key "
        "must raise KeyError.",
        """
        def solve(p):
            d, k = p
            if k not in d:
                raise ValueError(k)
            return d[k]
        """,
        [
            ([{"a": 1}, "a"], v(1)),
            ([{"a": 1}, "b"], err("KeyError")),
            ([{}, "a"], err("KeyError")),
            ([{"a": None}, "a"], v(None)),
        ],
        reference="""
        def solve(p):
            return p[0][p[1]]
        """,
        mechanisms=["errors.wrong_type"],
    ),
    task(
        "err-03",
        "Move money between accounts. Input is [balances, source, target, amount] where "
        "balances maps names to numbers. If the source holds less than the amount raise "
        "ValueError and change nothing. Otherwise return the new balances without modifying "
        "the argument.",
        """
        def solve(p):
            balances, source, target, amount = p
            balances[source] -= amount
            balances[target] += amount
            if balances[source] < 0:
                raise ValueError("insufficient")
            return balances
        """,
        [
            ([{"a": 10, "b": 0}, "a", "b", 4], v({"a": 6, "b": 4})),
            ([{"a": 3, "b": 0}, "a", "b", 5], err("ValueError")),
            ([{"a": 5, "b": 5}, "b", "a", 5], v({"a": 10, "b": 0})),
            ([{"a": 5, "b": 1}, "a", "b", 0], v({"a": 5, "b": 1})),
        ],
        reference="""
        def solve(p):
            balances, source, target, amount = p
            if balances[source] < amount:
                raise ValueError("insufficient")
            out = dict(balances)
            out[source] -= amount
            out[target] += amount
            return out
        """,
        mechanisms=["errors.partial_state", "state.input_mutation"],
    ),
    task(
        "err-04",
        "Add up a list of numeric strings. Any entry that is not an integer must raise "
        "ValueError instead of being skipped.",
        """
        def solve(p):
            total = 0
            for item in p:
                try:
                    total += int(item)
                except ValueError:
                    pass
            return total
        """,
        [
            (["1", "2"], v(3)),
            (["1", "x"], err("ValueError")),
            ([], v(0)),
            (["", "2"], err("ValueError")),
        ],
        reference="""
        def solve(p):
            return sum(int(item) for item in p)
        """,
        tier="hard",
        mechanisms=["errors.swallowed"],
    ),
    task(
        "err-05",
        "Divide a by b for the pair [a, b]. Division by zero must raise ZeroDivisionError.",
        """
        def solve(p):
            return p[0] / p[1]
        """,
        [([6, 3], v(2)), ([1, 0], err("ZeroDivisionError")), ([0, 5], v(0)), ([-4, 2], v(-2))],
        label="correct",
        mechanisms=["errors.wrong_type"],
    ),
    task(
        "err-06",
        "Read a value from nested dicts by a dotted path. Input is [dict, path] such as "
        "'a.b'. A missing key raises KeyError, and stepping into a value that is not a dict "
        "raises TypeError.",
        """
        def solve(p):
            d, path = p
            for part in path.split("."):
                try:
                    d = d[part]
                except (KeyError, TypeError):
                    return None
            return d
        """,
        [
            ([{"a": {"b": 1}}, "a.b"], v(1)),
            ([{"a": {"b": 1}}, "a.c"], err("KeyError")),
            ([{"a": 1}, "a.b"], err("TypeError")),
            ([{}, "x"], err("KeyError")),
            ([{"a": None}, "a"], v(None)),
        ],
        reference="""
        def solve(p):
            d, path = p
            for part in path.split("."):
                d = d[part]
            return d
        """,
        tier="hard",
        mechanisms=["errors.swallowed"],
    ),
    task(
        "err-07",
        "Append every item of the second list onto the first list, in place, and return the "
        "first list. Input is [target, items]. If any item is negative raise ValueError "
        "before the first list is changed at all.",
        """
        from check import reject_negative

        def solve(p):
            target, items = p
            for item in items:
                target.append(item)
                reject_negative(item)
            return target
        """,
        [
            ([[1], [2, 3]], v([1, 2, 3])),
            ([[1], [2, -1, 3]], err("ValueError")),
            ([[], []], v([])),
            ([[5], [-1]], err("ValueError")),
        ],
        reference="""
        from check import reject_negative

        def solve(p):
            target, items = p
            for item in items:
                reject_negative(item)
            target.extend(items)
            return target
        """,
        files={
            "check.py": """
            def reject_negative(item):
                if item < 0:
                    raise ValueError(item)
            """
        },
        input_state="per_case",
        tier="hard",
        mechanisms=["errors.partial_state"],
    ),
    task(
        "err-08",
        "Convert text to a positive integer. Text that is not a number, zero and negative "
        "numbers must all raise ValueError.",
        """
        def solve(p):
            n = int(p)
            assert n > 0
            return n
        """,
        [
            ("5", v(5)),
            ("0", err("ValueError")),
            ("-2", err("ValueError")),
            ("x", err("ValueError")),
        ],
        reference="""
        def solve(p):
            n = int(p)
            if n <= 0:
                raise ValueError(p)
            return n
        """,
        mechanisms=["errors.wrong_type"],
    ),
    task(
        "err-09",
        "Return the integer value of the text, or null when the text is not an integer. This "
        "function never raises.",
        """
        def solve(p):
            try:
                return int(p)
            except ValueError:
                return None
        """,
        [("12", v(12)), ("x", v(None)), ("", v(None)), ("1.5", v(None)), (" 7 ", v(7))],
        label="correct",
        mechanisms=["errors.swallowed"],
    ),
]

# err-07 mutates its input by contract: expected states are explicit.
AFTER = {
    ("err-07", "c1"): [[1, 2, 3], [2, 3]],
    ("err-07", "c2"): [[1], [2, -1, 3]],
    ("err-07", "c3"): [[], []],
    ("err-07", "c4"): [[5], [-1]],
}


def main():
    for t in TASKS:
        for c in t["cases"]:
            if (t["id"], c["id"]) in AFTER:
                c["expected"]["input_after"] = AFTER[(t["id"], c["id"])]
    ids = [t["id"] for t in TASKS]
    assert len(ids) == len(set(ids)) == 54
    OUT.write_text(
        json.dumps({"schema": "selective-corpus/v2", "tasks": TASKS}, indent=1, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    counts = {}
    for t in TASKS:
        key = (t["split"], t["label"])
        counts[key] = counts.get(key, 0) + 1
    print(sorted(counts.items()))


if __name__ == "__main__":
    main()
