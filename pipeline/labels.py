"""The three verdicts. Order is fixed: it is the row order of every exported weight matrix."""

LABELS = ("keep", "shorter", "email")

DISPLAY = {
    "keep": "Keep the meeting",
    "shorter": "Make it shorter",
    "email": "This is an email",
}


def label_index(label: str) -> int:
    """Index of a label in LABELS; raises ValueError for anything else."""
    if label not in LABELS:
        raise ValueError(f"unknown label {label!r}; expected one of {LABELS}")
    return LABELS.index(label)
