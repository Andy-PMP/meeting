import json
from types import SimpleNamespace

import pytest

import generate as g
from jsonl import read_jsonl
from specs import sample_specs

TEMPLATE = "Write invites.\n{{SPECS}}\n"


def response(specs, text_for=lambda s: f"Invite text for {s.spec_id}, unique {s.org} {s.tone}"):
    return json.dumps({"invites": [{"spec_id": s.spec_id, "text": text_for(s)} for s in specs]})


def fake_result(bundle_id, specs, text=None, type_="succeeded", stop_reason="end_turn"):
    usage = {"input_tokens": 1000, "output_tokens": 2000}
    msg = SimpleNamespace(
        stop_reason=stop_reason,
        usage=SimpleNamespace(model_dump=lambda mode: usage),
        content=[SimpleNamespace(type="text", text=text if text is not None else response(specs))],
    )
    result = SimpleNamespace(type=type_, message=msg, error="boom")
    return SimpleNamespace(custom_id=bundle_id, result=result)


def test_bundles_are_fixed_chunks_of_five():
    bundles = g.make_bundles(sample_specs(12))
    assert [b for b, _ in bundles] == ["b0001", "b0002", "b0003"]
    assert [len(s) for _, s in bundles] == [5, 5, 2]


def test_prompt_contains_every_spec_and_no_placeholder():
    specs = sample_specs(5)
    text = g.prompt_text(specs, TEMPLATE)
    assert "{{SPECS}}" not in text
    assert all(s.spec_id in text for s in specs)


def test_request_hash_is_stable_and_sensitive_to_prompt_and_specs():
    specs = sample_specs(5)
    h = g.request_hash(specs, TEMPLATE)
    assert h == g.request_hash(specs, TEMPLATE)
    assert h != g.request_hash(specs, TEMPLATE + "Be funnier.\n")
    assert h != g.request_hash(sample_specs(5, seed=99), TEMPLATE)


def test_the_real_prompt_template_has_the_placeholder():
    assert "{{SPECS}}" in g.load_template()


def test_parse_invites_returns_spec_order():
    specs = sample_specs(5)
    shuffled = json.loads(response(specs))
    shuffled["invites"].reverse()
    got = g.parse_invites(json.dumps(shuffled), specs)
    assert [i["spec_id"] for i in got] == [s.spec_id for s in specs]


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        json.dumps({"wrong": []}),
        json.dumps({"invites": [{"spec_id": "spec_0001", "text": "only one"}]}),
    ],
)
def test_parse_invites_rejects_malformed(bad):
    with pytest.raises(ValueError):
        g.parse_invites(bad, sample_specs(5))


def test_parse_invites_rejects_empty_text():
    specs = sample_specs(5)
    with pytest.raises(ValueError):
        g.parse_invites(response(specs, lambda s: "  "), specs)


def test_cost_applies_batch_discount():
    # 1M in at $4 + 1M out at $20 = $24, halved
    assert g.cost_usd({"input_tokens": 1_000_000, "output_tokens": 1_000_000}) == pytest.approx(12)
    assert g.cost_usd(None) == 0


def test_cache_round_trip_and_invalidation(tmp_path):
    specs = sample_specs(5)
    hashes = {"b0001": g.request_hash(specs, TEMPLATE)}
    assert g.record_result(fake_result("b0001", specs), hashes, "batch_1", tmp_path) == "succeeded"
    assert g.cached_invites("b0001", specs, TEMPLATE, tmp_path) is not None
    # a different prompt means a different request: not cached
    assert g.cached_invites("b0001", specs, TEMPLATE + "x", tmp_path) is None


def test_failed_or_invalid_results_are_not_cached(tmp_path):
    specs = sample_specs(5)
    hashes = {"b0001": g.request_hash(specs, TEMPLATE)}
    g.record_result(fake_result("b0001", specs, type_="errored"), hashes, "b", tmp_path)
    assert g.cached_invites("b0001", specs, TEMPLATE, tmp_path) is None
    g.record_result(
        fake_result("b0001", specs, text="{}", stop_reason="refusal"), hashes, "b", tmp_path
    )
    assert g.cached_invites("b0001", specs, TEMPLATE, tmp_path) is None


def test_replaced_responses_are_kept_and_still_counted(tmp_path, monkeypatch):
    specs = sample_specs(5)
    hashes = {"b0001": g.request_hash(specs, TEMPLATE)}
    g.record_result(fake_result("b0001", specs, text="{}"), hashes, "batch_1", tmp_path)
    g.record_result(fake_result("b0001", specs), hashes, "batch_2", tmp_path)
    assert (tmp_path / "superseded" / "b0001-batch_1.json").exists()
    assert g.load_raw("b0001", tmp_path)["batch_id"] == "batch_2"
    usd, n = g.total_cost(tmp_path)
    assert n == 2 and usd == pytest.approx(
        2 * g.cost_usd({"input_tokens": 1000, "output_tokens": 2000})
    )


def test_build_invites_assembles_and_dedups(tmp_path):
    specs = sample_specs(10)
    texts = {
        s.spec_id: f"Invite {s.spec_id} for {s.org}, {s.meeting_type}, {s.tone}" for s in specs
    }
    texts["spec_0006"] = texts["spec_0001"]  # 2nd bundle repeats the very first invite
    for bid, bundle in g.make_bundles(specs):
        body = response(bundle, lambda s: texts[s.spec_id])
        hashes = {bid: g.request_hash(bundle, TEMPLATE)}
        g.record_result(fake_result(bid, bundle, body), hashes, "b", tmp_path)

    out, dup_out = tmp_path / "invites.jsonl", tmp_path / "dups.jsonl"
    stats = g.build_invites(specs, TEMPLATE, tmp_path, out, dup_out)
    assert stats == {"generated": 10, "duplicates": 1, "kept": 9}
    rows = read_jsonl(out)
    assert rows[0]["id"] == "inv_0001" and rows[0]["source"] == "synthetic"
    assert "inv_0006" not in {r["id"] for r in rows}
    assert read_jsonl(dup_out) == [{"id": "inv_0006", "duplicate_of": "inv_0001", "kind": "exact"}]
