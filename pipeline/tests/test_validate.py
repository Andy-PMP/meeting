from validate import check_invites, check_labels, check_test


def invite(i, text="Sync on Thursday about the launch plan.", spec="spec_0001"):
    return {
        "id": f"inv_{i:04d}",
        "text": text,
        "source": "synthetic",
        "spec_id": spec,
        "gen_model": "m",
        "prompt_version": "v1",
        "created": "2026-10-21T00:00:00+00:00",
    }


def label(id_, lab="keep", discarded=False, pass_=1):
    return {
        "id": id_,
        "label": lab,
        "discarded": discarded,
        "note": "",
        "pass": pass_,
        "labeled_at": "t",
    }


def test_good_invites_pass():
    assert check_invites([invite(1), invite(2)], {"spec_0001"}) == []


def test_invite_errors_are_reported():
    errs = check_invites(
        [invite(1), invite(1, text=" "), invite(3, spec="spec_9999")], {"spec_0001"}
    )
    assert any("duplicate id" in e for e in errs)
    assert any("empty text" in e for e in errs)
    assert any("unknown spec_id" in e for e in errs)


def test_label_rules():
    ids = {"inv_0001"}
    assert check_labels([label("inv_0001"), label("inv_0001", None, discarded=True)], ids) == []
    errs = check_labels(
        [
            label("inv_0002"),
            label("inv_0001", "maybe"),
            label("inv_0001", "keep", True),
            label("inv_0001", pass_=3),
        ],
        ids,
    )
    assert len(errs) == 4


def test_test_set_leakage_is_an_error():
    text = "Quarterly planning: decide which two of the five roadmap bets we fund. Bring numbers."
    test = [{"id": "test_001", "text": text, "label": "keep", "note": ""}]
    assert check_test(test, ["Totally different invite about parking passes."]) == []
    errs = check_test(test, [text.replace("five", "six")])
    assert errs and "near-duplicates" in errs[0]
