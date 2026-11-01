"""Amendment 1 to the AI-FIRST-04 corpus: a computation-heavy "extreme" tier.

Development calibration showed the stateless model solving every development task (12/12, six
of them "hard"), so the corpus had no headroom. Before any held-out inference this adds 6
calibration tasks (arm A only, never used for lessons or held-out claims) and 12 held-out
tasks. The 54 original tasks are byte-identical. All 18 are added unconditionally: nothing is
selected by outcome. Expected values come from an independent third implementation (``spec``,
a deliberately different formulation); the audit checks implementation, reference and spec agree
as the labels require. This is derived, not hand-typed, and is disclosed as such.
"""

import copy
import json
import re
import sys
from pathlib import Path

from scripts.author_selective_corpus import OUT, task

ROOT = Path(__file__).resolve().parents[1]


def expected(spec, value):
    try:
        return {"value": spec(copy.deepcopy(value))}
    except Exception as error:
        return {"error": type(error).__name__}


# ----------------------------------------------------------------------- independent specs
def luhn(p):
    digits = [int(c) for c in p][::-1]
    total = sum(digits[0::2]) + sum(sum(divmod(2 * d, 10)) for d in digits[1::2])
    return total % 10 == 0


def csv_line(p):
    import csv

    return next(csv.reader([p]))


def stack_machine(p):
    stack = []
    table = {
        "push": lambda a: stack.append(int(a[0])),
        "pop": lambda a: stack.pop(),
        "dup": lambda a: stack.append(stack[-1]),
        "swap": lambda a: stack.__setitem__(slice(-2, None), [stack[-1], stack[-2]]),
        "add": lambda a: stack.append(stack.pop() + stack.pop()),
    }
    for command in p:
        name, *args = command.split()
        table[name](args)
    return stack


def policy(p):
    rules, user, groups, action = p
    verdict = False
    for effect, subject, target in rules:
        who = subject in ("*", user) or (
            subject.startswith("group:") and subject.split(":", 1)[1] in groups
        )
        if who and target in (action, "*"):
            verdict = effect == "allow"
    return verdict


def layered(p):
    layers, key = p
    path = key.split(".")

    def resolve(node, parts):
        if not parts:
            return ("found", node)
        if not isinstance(node, dict):
            return ("hidden", None)
        if parts[0] not in node:
            return ("missing", None)
        return resolve(node[parts[0]], parts[1:])

    for layer in layers[::-1]:
        state, value = resolve(layer, path)
        if state == "found":
            return value
        if state == "hidden":
            return None
    return None


def jobs(p):
    results, errors = [], []
    for index, job in enumerate(p):
        try:
            results.append(100 / job)
        except Exception as error:
            errors.append([index, type(error).__name__])
    return [results, errors]


def cents(p):
    total, n = p
    shares = [0] * n
    for i in range(total):
        shares[i % n] += 1
    return shares


def twos_bits(p):
    return format(p % 256, "08b").count("1")


def escaped_pairs(p):
    items = [x.replace("\\;", ";") for x in re.split(r"(?<!\\);", p)]
    return [x.split("=", 1) for x in items if x]


def duration(p):
    if p == "":
        return 0
    match = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", p)
    if not match:
        raise ValueError(p)
    h, m, s = (int(g) if g else 0 for g in match.groups())
    return h * 3600 + m * 60 + s


def ledger(p):
    balance = rejected = 0
    for op in p:
        kind, amount = op.split()
        amount = int(amount)
        if kind == "deposit":
            balance += amount
        elif balance - amount >= 0:
            balance -= amount
        else:
            rejected += 1
    return [balance, rejected]


def rle_decode(p):
    out, i = [], 0
    while i < len(p):
        ch, i = p[i], i + 1
        j = i
        while j < len(p) and p[j].isdigit():
            j += 1
        out.append(ch * int(p[i:j]))
        i = j
    return "".join(out)


def window(p):
    start, end, hour = p
    return hour in {(start + k) % 24 for k in range((end - start) % 24)}


def inherited(p):
    rules, path = p
    for prefix in sorted(rules, key=len, reverse=True):
        base = prefix.rstrip("/")
        if path == prefix or path == base or path.startswith(base + "/"):
            return rules[prefix]
    return False


def fill_records(p):
    defaults, records = p
    return [{**defaults, **record} for record in records]


def env_flags(p):
    out = {}
    for item in p:
        head, sep, tail = item.partition("=")
        out[head] = tail if sep else True
    return out


def attempts(p):
    for number, outcome in enumerate(p[:3], 1):
        if outcome == "ok":
            return number
    raise RuntimeError("exhausted")


def underscored(p):
    if not p or p[0] == "_" or p[-1] == "_" or "__" in p or not p.replace("_", "").isdigit():
        raise ValueError(p)
    return int(p.replace("_", ""))


# ----------------------------------------------------------------------- the tasks
def build(ident, contract, code, inputs, spec, *, reference=None, split, files=None, **extra):
    t = task(
        ident,
        contract,
        code,
        [(value, expected(spec, value)) for value in inputs],
        reference=reference,
        tier="extreme",
        label="defective" if reference else "correct",
        files=files,
        **extra,
    )
    t["split"] = split
    return t


NEW = [
    build(
        "num-10",
        "Return true when the digit string passes the Luhn check: starting from the rightmost "
        "digit and moving left, double every second digit, subtract 9 from any doubled digit "
        "above 9, add everything up, and the total must be a multiple of 10.",
        """
        def solve(p):
            total = 0
            for i, ch in enumerate(p):
                d = int(ch)
                if i % 2 == 0:
                    d *= 2
                    if d > 9:
                        d -= 9
                total += d
            return total % 10 == 0
        """,
        [
            "4539578763621486",
            "4111111111111111",
            "4111111111111112",
            "378282246310005",
            "79927398713",
            "79927398710",
            "0",
        ],
        luhn,
        reference="""
        def solve(p):
            total = 0
            for i, ch in enumerate(reversed(p)):
                d = int(ch)
                if i % 2 == 1:
                    d *= 2
                    if d > 9:
                        d -= 9
                total += d
            return total % 10 == 0
        """,
        split="calibration",
        mechanisms=["numeric.counting"],
    ),
    build(
        "num-11",
        "Split a whole number of cents among n people as evenly as possible. Input is "
        "[total, n]. Return the list of n shares; any remainder goes one cent at a time to "
        "the earliest people.",
        """
        def solve(p):
            share = round(p[0] / p[1])
            return [share] * p[1]
        """,
        [[10, 3], [9, 3], [1, 3], [0, 4], [7, 2], [100, 7]],
        cents,
        reference="""
        def solve(p):
            q, r = divmod(p[0], p[1])
            return [q + 1] * r + [q] * (p[1] - r)
        """,
        split="heldout",
        mechanisms=["numeric.rounding"],
    ),
    build(
        "num-12",
        "Count the 1 bits in the 8-bit two's complement form of an integer from -128 to 127. "
        "For example -1 is 11111111.",
        """
        def solve(p):
            return bin(p).count("1")
        """,
        [5, -1, -128, 127, -5, 0],
        twos_bits,
        reference="""
        def solve(p):
            return bin(p & 0xFF).count("1")
        """,
        split="heldout",
        mechanisms=["numeric.signed_values"],
    ),
    build(
        "par-10",
        "Split one CSV line into fields. A comma inside double quotes does not split. The "
        "surrounding quotes are removed, and two double quotes inside a quoted field stand "
        "for one literal double quote.",
        """
        def solve(p):
            fields, current, quoted = [], "", False
            for ch in p:
                if ch == '"':
                    quoted = not quoted
                elif ch == "," and not quoted:
                    fields.append(current)
                    current = ""
                else:
                    current += ch
            fields.append(current)
            return fields
        """,
        ["a,b,c", 'a,"b,c",d', '"he said ""hi""",x', '"",a', "a,", 'x,"y ""z"" w",,q'],
        csv_line,
        reference="""
        def solve(p):
            fields, current, quoted, i = [], "", False, 0
            while i < len(p):
                ch = p[i]
                if ch == '"':
                    if quoted and p[i + 1:i + 2] == '"':
                        current += '"'
                        i += 1
                    else:
                        quoted = not quoted
                elif ch == "," and not quoted:
                    fields.append(current)
                    current = ""
                else:
                    current += ch
                i += 1
            fields.append(current)
            return fields
        """,
        split="calibration",
        mechanisms=["parsing.delimiter_position"],
    ),
    build(
        "par-11",
        "Parse 'key=value' items separated by semicolons into a list of [key, value] pairs "
        "(a key with no equals sign gives a one-element list). A backslash before a "
        "semicolon makes it part of the text instead of a separator. Empty items are skipped.",
        r"""
        def solve(p):
            return [item.split("=", 1) for item in p.split(";") if item]
        """,
        ["a=1;b=2", "a=x\\;y;b=2", "", "k=;j", "a=1;;b=2", "p=1\\;2\\;3"],
        escaped_pairs,
        reference=r"""
        def solve(p):
            items, current, i = [], "", 0
            while i < len(p):
                if p[i] == "\\" and p[i + 1:i + 2] == ";":
                    current += ";"
                    i += 2
                    continue
                if p[i] == ";":
                    items.append(current)
                    current = ""
                else:
                    current += p[i]
                i += 1
            items.append(current)
            return [item.split("=", 1) for item in items if item]
        """,
        split="heldout",
        mechanisms=["parsing.delimiter_position", "parsing.empty_fields"],
    ),
    build(
        "par-12",
        "Convert text such as '1h30m15s' into seconds. Any of the hours, minutes and seconds "
        "parts may be left out, but they must appear in that order. Empty text is 0 seconds. "
        "Any text that does not follow this form is an error of type ValueError.",
        """
        import re

        def solve(p):
            units = {"h": 3600, "m": 60, "s": 1}
            return sum(int(n) * units[u] for n, u in re.findall(r"(\\d+)([hms])", p))
        """,
        ["1h30m15s", "90m", "45s", "2h", "5x", "1h5", "", "30m1h"],
        duration,
        reference="""
        import re

        def solve(p):
            if not re.fullmatch(r"(\\d+h)?(\\d+m)?(\\d+s)?", p):
                raise ValueError(p)
            units = {"h": 3600, "m": 60, "s": 1}
            return sum(int(n) * units[u] for n, u in re.findall(r"(\\d+)([hms])", p))
        """,
        split="heldout",
        mechanisms=["parsing.type_coercion"],
    ),
    build(
        "sta-10",
        "Run a stack machine over a list of commands, starting from an empty stack, and return "
        "the final stack (bottom first). 'push N' pushes the integer N, 'pop' removes the top, "
        "'dup' pushes a copy of the top, 'swap' exchanges the top two, 'add' replaces the top "
        "two with their sum. Running out of items raises IndexError.",
        """
        def solve(p):
            stack = []
            for command in p:
                parts = command.split()
                if parts[0] == "push":
                    stack.append(int(parts[1]))
                elif parts[0] == "pop":
                    stack.pop()
                elif parts[0] == "dup":
                    stack.append(stack[0])
                elif parts[0] == "swap":
                    stack[-1], stack[-2] = stack[-2], stack[-1]
                elif parts[0] == "add":
                    stack.append(stack.pop() + stack.pop())
            return stack
        """,
        [
            ["push 3", "push 4", "dup", "add"],
            ["push 1", "push 2", "push 3", "dup", "swap", "add"],
            ["push 5", "dup", "dup", "add", "add"],
            ["push 2", "push 7", "swap", "dup", "add", "push 1", "add"],
            [],
            ["pop"],
            ["push 9", "push 1", "push 6", "dup", "add", "swap", "pop", "dup"],
        ],
        stack_machine,
        reference="""
        def solve(p):
            stack = []
            for command in p:
                parts = command.split()
                if parts[0] == "push":
                    stack.append(int(parts[1]))
                elif parts[0] == "pop":
                    stack.pop()
                elif parts[0] == "dup":
                    stack.append(stack[-1])
                elif parts[0] == "swap":
                    stack[-1], stack[-2] = stack[-2], stack[-1]
                elif parts[0] == "add":
                    stack.append(stack.pop() + stack.pop())
            return stack
        """,
        split="calibration",
        mechanisms=["state.ordering"],
    ),
    build(
        "sta-11",
        "Replay account operations such as 'deposit 100' and 'withdraw 30' from a zero "
        "balance. A withdrawal larger than the balance is rejected and changes nothing; a "
        "withdrawal equal to the balance is allowed. Return [final balance, rejected count].",
        """
        def solve(p):
            balance, rejected = 0, 0
            for op in p:
                kind, amount = op.split()
                amount = int(amount)
                if kind == "deposit":
                    balance += amount
                elif amount < balance:
                    balance -= amount
                else:
                    rejected += 1
            return [balance, rejected]
        """,
        [
            ["deposit 100", "withdraw 30", "withdraw 70", "withdraw 1"],
            ["withdraw 5"],
            ["deposit 50", "withdraw 20", "deposit 10", "withdraw 40", "withdraw 1"],
            ["deposit 5", "withdraw 5", "deposit 5", "withdraw 6", "withdraw 5"],
            [],
        ],
        ledger,
        reference="""
        def solve(p):
            balance, rejected = 0, 0
            for op in p:
                kind, amount = op.split()
                amount = int(amount)
                if kind == "deposit":
                    balance += amount
                elif amount <= balance:
                    balance -= amount
                else:
                    rejected += 1
            return [balance, rejected]
        """,
        split="heldout",
        mechanisms=["state.transition_guard"],
    ),
    build(
        "sta-12",
        "Decode run-length text: each character is followed by its repeat count, which may "
        "have several digits, so 'a3b2' is 'aaabb' and 'x12' is twelve x characters.",
        """
        import re

        def solve(p):
            return "".join(ch * int(n) for ch, n in re.findall(r"(\\D)(\\d+)", p))
        """,
        ["a3b2", "x12", "a1b10c2", "z0q3", "", "m11"],
        rle_decode,
        split="heldout",
        mechanisms=["state.repeat_application"],
    ),
    build(
        "aut-10",
        "Decide an action from ordered rules. Input is [rules, user, groups, action] where "
        "each rule is [effect, subject, rule_action]. A rule applies when its subject is '*', "
        "the user's name, or 'group:NAME' for a group the user belongs to, and its rule_action "
        "is the action or '*'. When several rules apply the LAST one decides; effect 'allow' "
        "permits and 'deny' refuses. With no applicable rule the answer is refuse.",
        """
        def solve(p):
            rules, user, groups, action = p
            for effect, subject, rule_action in rules:
                who = subject == "*" or subject == user or (
                    subject.startswith("group:") and subject[6:] in groups
                )
                if who and rule_action in (action, "*"):
                    return effect == "allow"
            return False
        """,
        [
            [[["allow", "*", "read"], ["deny", "bob", "read"]], "bob", [], "read"],
            [[["deny", "group:staff", "*"], ["allow", "ann", "read"]], "ann", ["staff"], "read"],
            [[["allow", "group:ops", "write"]], "cy", ["dev"], "write"],
            [[], "x", [], "read"],
            [
                [["allow", "*", "*"], ["deny", "group:temp", "write"], ["allow", "dan", "write"]],
                "dan",
                ["temp"],
                "write",
            ],
            [
                [["allow", "*", "*"], ["deny", "group:temp", "write"], ["allow", "dan", "write"]],
                "eve",
                ["temp"],
                "write",
            ],
        ],
        policy,
        reference="""
        def solve(p):
            rules, user, groups, action = p
            verdict = False
            for effect, subject, rule_action in rules:
                who = subject == "*" or subject == user or (
                    subject.startswith("group:") and subject[6:] in groups
                )
                if who and rule_action in (action, "*"):
                    verdict = effect == "allow"
            return verdict
        """,
        split="calibration",
        mechanisms=["authz.precedence"],
    ),
    build(
        "aut-11",
        "Access is allowed from hour 'start' up to but not including hour 'end', on a 24 hour "
        "clock. A window such as 22 to 6 runs through midnight. Equal start and end hours mean "
        "an empty window. Input is [start, end, hour].",
        """
        def solve(p):
            start, end, hour = p
            if start <= end:
                return start <= hour < end
            return hour >= start or hour < end
        """,
        [[9, 17, 9], [9, 17, 17], [22, 6, 23], [22, 6, 3], [22, 6, 12], [22, 6, 6], [5, 5, 5]],
        window,
        split="heldout",
        mechanisms=["authz.scope_boundary"],
    ),
    build(
        "aut-12",
        "Permissions inherit down a path. Input is [rules, path] where rules maps path "
        "prefixes to true or false. The rule with the longest prefix that contains the path "
        "decides, and a prefix contains a path only at a '/' boundary ('/a' contains '/a' and "
        "'/a/x' but not '/ab'). A path no rule contains is refused.",
        """
        def solve(p):
            rules, path = p
            for prefix, allowed in rules.items():
                if path.startswith(prefix):
                    return allowed
            return False
        """,
        [
            [{"/": True, "/a": False, "/a/b": True}, "/a/b/c"],
            [{"/": True, "/a": False, "/a/b": True}, "/a/x"],
            [{"/": True, "/a": False, "/a/b": True}, "/z"],
            [{"/": True, "/a": False, "/a/b": True}, "/ab"],
            [{"/": True, "/a": False, "/a/b": True}, "/a"],
            [{"/a": False, "/ab": True}, "/ab/c"],
            [{"/a": True}, "/b"],
        ],
        inherited,
        reference="""
        def solve(p):
            rules, path = p
            best = None
            for prefix in rules:
                if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
                    if best is None or len(prefix) > len(best):
                        best = prefix
            return rules[best] if best is not None else False
        """,
        split="heldout",
        mechanisms=["authz.scope_boundary", "authz.substring_match"],
    ),
    build(
        "def-10",
        "Look up a dotted key such as 'a.b' in a list of configuration layers, later layers "
        "overriding earlier ones. Input is [layers, key]. A layer that holds a plain value (not "
        "a dict) on the way to the key hides that key in that layer and in every earlier "
        "layer, so the answer is null. A layer that simply lacks the key defers to earlier "
        "layers. No layer holding the key gives null.",
        """
        def solve(p):
            layers, key = p
            for layer in reversed(layers):
                node = layer
                found = True
                for part in key.split("."):
                    if isinstance(node, dict) and part in node:
                        node = node[part]
                    else:
                        found = False
                        break
                if found:
                    return node
            return None
        """,
        [
            [[{"a": {"b": 1}}, {"a": 5}], "a.b"],
            [[{"a": {"b": 1}}, {"a": {"c": 2}}], "a.b"],
            [[{"a": {"b": 1}}, {"a": {"b": 2}}], "a.b"],
            [[{"x": 1}], "y"],
            [[{"a": {"b": {"c": 3}}}, {"a": {"b": 4}}], "a.b.c"],
            [[{"a": None}], "a"],
            [[{"a": {"b": 1}}, {}, {"a": {"c": 2}}], "a.b"],
        ],
        layered,
        reference="""
        def solve(p):
            layers, key = p
            for layer in reversed(layers):
                node = layer
                for part in key.split("."):
                    if not isinstance(node, dict):
                        return None
                    if part not in node:
                        break
                    node = node[part]
                else:
                    return node
            return None
        """,
        split="calibration",
        mechanisms=["defaults.merge_depth", "defaults.override_precedence"],
    ),
    build(
        "def-11",
        "Complete records from defaults. Input is [defaults, records]. Each returned record "
        "has every default key it lacks; values the record sets itself, including 0, false, "
        "the empty string and null, are kept. The arguments are not modified.",
        """
        def solve(p):
            defaults, records = p
            out = []
            for record in records:
                merged = dict(defaults)
                for key, value in record.items():
                    if value:
                        merged[key] = value
                out.append(merged)
            return out
        """,
        [
            [{"a": 1, "b": 2}, [{"a": 0}, {"b": None, "c": 3}, {}]],
            [{"x": True}, [{"x": False}, {"x": True}]],
            [{}, [{"k": ""}]],
            [{"a": 1}, []],
            [{"a": "d", "b": "e"}, [{"a": "", "b": "z"}]],
        ],
        fill_records,
        reference="""
        def solve(p):
            defaults, records = p
            out = []
            for record in records:
                merged = dict(defaults)
                merged.update(record)
                out.append(merged)
            return out
        """,
        split="heldout",
        mechanisms=["defaults.falsy_vs_missing"],
    ),
    build(
        "def-12",
        "Read environment-style flags. Input is a list of strings. 'KEY=VALUE' sets KEY to the "
        "text VALUE (which may be empty and may itself contain '='), a bare 'KEY' sets it to "
        "true, and a later entry for the same key replaces an earlier one. Return a dict.",
        """
        def solve(p):
            out = {}
            for item in p:
                key, _, value = item.partition("=")
                out[key] = value or True
            return out
        """,
        [["DEBUG=0", "NAME=", "X"], ["A=1", "A=2"], ["K=a=b"], [], ["A=1", "A"], ["B", "B="]],
        env_flags,
        reference="""
        def solve(p):
            out = {}
            for item in p:
                if "=" in item:
                    key, value = item.split("=", 1)
                    out[key] = value
                else:
                    out[item] = True
            return out
        """,
        split="heldout",
        mechanisms=["defaults.falsy_vs_missing"],
    ),
    build(
        "err-10",
        "Compute 100 divided by each job in a list. A job that raises any exception is "
        "recorded and skipped. Return [results, errors] where results holds the successful "
        "quotients in order and errors holds [index, ExceptionName] for each failed job.",
        """
        def solve(p):
            results, errors = [], []
            for index, job in enumerate(p):
                try:
                    results.append(100 / job)
                except ZeroDivisionError:
                    errors.append([index, "ZeroDivisionError"])
            return [results, errors]
        """,
        [[4, 0, "x", 5], [2, 4], [0], [None, 10, 50], [], [8]],
        jobs,
        reference="""
        def solve(p):
            results, errors = [], []
            for index, job in enumerate(p):
                try:
                    results.append(100 / job)
                except Exception as error:
                    errors.append([index, type(error).__name__])
            return [results, errors]
        """,
        split="calibration",
        mechanisms=["errors.swallowed", "errors.wrong_type"],
    ),
    build(
        "err-11",
        "Simulate retries. Input is a list of attempt outcomes, each 'ok' or 'fail'. Attempts "
        "are made in order and stop at the first 'ok', but at most 3 attempts are made. Return "
        "the number of attempts used. If none of the first 3 succeeds, raise RuntimeError.",
        """
        def solve(p):
            for attempt in range(3):
                if attempt < len(p) and p[attempt] == "ok":
                    return attempt + 1
            raise RuntimeError("exhausted")
        """,
        [
            ["ok"],
            ["fail", "ok"],
            ["fail", "fail", "ok"],
            ["fail", "fail", "fail", "ok"],
            ["fail", "fail", "fail"],
            [],
        ],
        attempts,
        split="heldout",
        mechanisms=["errors.swallowed"],
    ),
    build(
        "err-12",
        "Parse a positive integer written with optional underscores, such as '1_000'. An "
        "underscore is allowed only between two digits. Any other text is an error of type "
        "ValueError.",
        """
        def solve(p):
            return int(p.replace("_", ""))
        """,
        ["1_000", "1__0", "_1", "1_", "10", "1_2_3", "", "x_1"],
        underscored,
        reference="""
        import re

        def solve(p):
            if not re.fullmatch(r"\\d+(_\\d+)*", p):
                raise ValueError(p)
            return int(p.replace("_", ""))
        """,
        split="heldout",
        mechanisms=["errors.swallowed", "parsing.type_coercion"],
    ),
]


def main():
    data = json.loads(OUT.read_text(encoding="utf-8"))
    if data["schema"] == "selective-corpus/v2" and len(data["tasks"]) == 54:
        data["tasks"].extend(NEW)
        OUT.write_text(
            json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
    counts = {}
    for t in data["tasks"]:
        counts[t["split"]] = counts.get(t["split"], 0) + 1
    print(counts, file=sys.stdout)


if __name__ == "__main__":
    main()
