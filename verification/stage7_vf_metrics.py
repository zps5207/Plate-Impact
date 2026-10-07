"""Pure-Python numerical helpers for Stage 7 verification."""


def rel(a, b, zero_guard=1.0e-30):
    """Return true relative error with an explicit near-zero guard."""
    denominator = abs(b)
    if denominator <= zero_guard:
        return 0.0 if abs(a - b) <= zero_guard else float("inf")
    return abs(a - b) / denominator
