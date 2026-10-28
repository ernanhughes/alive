"""C1B-1 owner-selected reliance anchor API regressions."""

from tests.test_research_memory import ROOT, historical


def test_anchor_unique_quote_and_revision_compare_and_swap(client, monkeypatch):
    _, _, _, _, saved = historical(client, monkeypatch)
    excerpt = saved["data"]["excerpt"]
    # The source fixture contains multiple complete sentences; choose one exact span.
    quote = next(
        (
            part.strip() + "."
            for part in excerpt.split(".")
            if len(part.strip()) >= 16 and (part.strip() + ".") in excerpt
        ),
        None,
    )
    assert quote is not None
    payload = {
        "quote": quote,
        "expected_sha256": saved["data"]["sha256"],
        "expected_revision": 0,
    }
    response = client.post(ROOT + f"/research/memories/{saved['id']}/anchor", json=payload)
    assert response.status_code == 200, response.text
    anchor = response.json()["data"]["reliance_anchor"]
    assert anchor["revision"] == 1
    assert excerpt[anchor["start"] : anchor["end"]] == quote
    stale = client.post(ROOT + f"/research/memories/{saved['id']}/anchor", json=payload)
    assert stale.status_code != 200


def test_withdrawal_scrubs_anchor_quote(client, monkeypatch):
    from alive.claim_comparison import _bounded_sentence

    _, _, _, _, saved = historical(client, monkeypatch)
    excerpt = saved["data"]["excerpt"]
    quote = next(
        (
            part.strip() + "."
            for part in excerpt.split(".")
            if len(part.strip()) >= 16 and _bounded_sentence(excerpt, part.strip() + ".")
        ),
        None,
    )
    assert quote is not None
    payload = {
        "quote": quote,
        "expected_sha256": saved["data"]["sha256"],
        "expected_revision": 0,
    }
    anchored = client.post(ROOT + f"/research/memories/{saved['id']}/anchor", json=payload)
    assert anchored.status_code == 200, anchored.text
    withdrawn = client.post(ROOT + f"/research/memories/{saved['id']}/withdraw", json={})
    assert withdrawn.status_code == 200, withdrawn.text
    anchor = withdrawn.json()["data"]["reliance_anchor"]
    assert "quote" not in anchor
    assert anchor["revision"] == 1
