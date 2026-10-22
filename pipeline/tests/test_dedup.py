from dedup import find_duplicates, find_leaks, normalize

A = "Weekly sync: please come ready with status updates for the Q3 launch. Thursday 2pm, room 4B."
B = "Budget review for the facilities team. We need to approve the HVAC quote before Friday."
C = "Quick chat about the interview loop for the designer role? 15 min, whenever works."


def test_normalize_ignores_case_punctuation_and_spacing():
    assert normalize("Hello,   WORLD!\n") == "hello world"


def test_exact_duplicates_after_normalization():
    dups = find_duplicates([A, B, A.upper() + "!!"])
    assert dups == {2: (0, "exact")}


def test_near_duplicate_with_small_edit():
    near = A.replace("Thursday 2pm", "Thursday at 2pm")
    assert find_duplicates([A, B, near]) == {2: (0, "near")}


def test_distinct_texts_are_kept():
    assert find_duplicates([A, B, C]) == {}


def test_first_occurrence_survives():
    near = A.replace("room 4B", "room 4C")
    dups = find_duplicates([B, A, near, A])
    assert 1 not in dups
    assert dups[2][0] == 1 and dups[3][0] == 1


def test_leaks_between_test_and_train():
    leaky = A.replace("Q3", "Q4")
    leaks = find_leaks([C, leaky], [A, B])
    assert [(i, j) for i, j, _ in leaks] == [(1, 0)]


def test_no_leaks_when_sets_are_distinct():
    assert find_leaks([C], [A, B]) == []
    assert find_leaks([], [A]) == []
