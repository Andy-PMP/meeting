from collections import Counter

from specs import MEETING_TYPES, sample_specs, spec_from_dict, spec_to_dict


def test_same_seed_same_specs():
    assert sample_specs(50, seed=1) == sample_specs(50, seed=1)
    assert sample_specs(50, seed=1) != sample_specs(50, seed=2)


def test_ids_are_sequential_and_padded():
    specs = sample_specs(12)
    assert [s.spec_id for s in specs] == [f"spec_{i:04d}" for i in range(1, 13)]


def test_hints_are_balanced():
    counts = Counter(s.gen_hint for s in sample_specs(300))
    assert counts == {"keep": 100, "shorter": 100, "email": 100}


def test_attendees_and_duration_fit_the_meeting_type():
    ranges = {name: (rng, durations) for name, rng, durations in MEETING_TYPES}
    for s in sample_specs(400):
        (lo, hi), durations = ranges[s.meeting_type]
        assert lo <= s.attendees <= hi
        assert s.duration_min in durations


def test_messiness_has_at_most_two_distinct_quirks():
    for s in sample_specs(200):
        assert len(s.messiness) <= 2
        assert len(set(s.messiness)) == len(s.messiness)


def test_each_spec_has_its_own_cast_without_the_sender():
    for s in sample_specs(200):
        firsts = [name.split()[0] for name in s.cast]
        assert len(firsts) == len(set(firsts)) == 6
        assert s.sender not in firsts


def test_names_are_spread_out():
    # No first name should dominate: the point is to avoid generator favourites.
    counts = Counter(name.split()[0] for s in sample_specs(800) for name in s.cast)
    assert max(counts.values()) < 3 * (sum(counts.values()) / len(counts))


def test_org_and_project_are_filled_in():
    for s in sample_specs(300):
        assert "{" not in s.org and "{" not in s.project
        assert s.org and s.project


def test_org_names_fit_the_sector():
    for s in sample_specs(300):
        if s.industry == "public school district":
            assert "School" in s.org
        if s.industry == "law firm":
            assert " & " in s.org or "Law" in s.org


def test_round_trip_through_json_dict():
    for s in sample_specs(10):
        assert spec_from_dict(spec_to_dict(s)) == s
