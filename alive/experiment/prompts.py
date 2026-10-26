from alive.society import ROLE_SPEC_VERSION, role_prompt

MODEL = "muse-spark-1.3"
PROMPT_VERSION = "selective-review-v1"


def prompt(role):
    base = role_prompt("proposer" if role == "initial" else "critic")
    return base + (
        " Experiment selective-review-v1: this is a read-only numerical evidence task. "
        "Only verified same-window facts may establish an answer. If any required field is absent "
        "or equally authoritative values conflict, recommend abstain and return claims=[]. "
        "Otherwise return exactly one claim: subject equals the supplied subject, predicate "
        "computed_result, value is a numeric string, evidence_refs cites verified sources covering "
        "every required field. Carry out the requested operation; do not just copy an input. "
        "Use actions=[]; no browser, code or external actions execute. "
        "Confidence is your expressed uncertainty, not proof. "
        + (
            "Produce the initial conclusion."
            if role == "initial"
            else "Review the supplied initial decision against the SAME evidence. Your claims and "
            "recommendation are your final reviewed conclusion; correct errors when warranted "
            "and preserve a correct answer when it is supported. Record "
            "concise criticisms, not private reasoning."
        )
    )


def specification():
    return {
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "base_role_version": ROLE_SPEC_VERSION,
        "initial": prompt("initial"),
        "critic": prompt("critic"),
        "intervention": "Additional critical review with a separately recorded revised conclusion",
        "shared_artifact": "Identical initial model decision is shared across all three arms",
        "independence": (
            "Shared initial output is not three independent live trials; "
            "Critic outputs remain separate."
        ),
    }
