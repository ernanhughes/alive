# AI-FIRST-02B implementation note

Base: PR #91 implementation `536b910`, pending its merge. This work is stacked on that branch.

Use existing events for conversation membership and frozen context snapshots; existing admission,
Cognition, Governor, source custody, Pi and `result.record` remain the execution path. Retained
workflow artifacts are the authoritative prior findings. General `Memory`/MiniLM retrieval and
goal-scoped research memory were inspected: neither directly provides this conversation's exact
owner/source-disclosure boundary, so the first slice reads bounded, explicitly linked artifacts
rather than disclosing general memory or adding a second evidence store.

An opt-in standing session adds one concrete read-only contextual reasoning procedure. Initial
questions keep the existing interpretation/analysis path. Subsequent turns receive a frozen,
bounded selection of prior goals, findings and revisions from that conversation only. The model
resolves natural/ambiguous references and distinguishes owner assertions from source observations
and unverified model assessments. Revision outputs link earlier item IDs without overwriting them.
Snapshots are hashed, charged and revalidated at admission and Pi dispatch. New conversation
means no inherited history. Legacy exchanges remain readable and unchanged.
