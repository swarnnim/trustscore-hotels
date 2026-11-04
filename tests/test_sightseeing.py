"""Tests for the sightseeing extension (plain asserts).

Run: python3 tests/test_sightseeing.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trustscore.sightseeing import SAMPLE_ACTIVITIES, build_activity_groups  # noqa: E402


def main():
    groups = build_activity_groups()
    by_truth = {}
    for g in groups:
        for t in g["truth_ids"]:
            by_truth.setdefault(t, []).append(g)

    # 1. Four real attractions, each grouped exactly once, no cross-merges.
    assert len(groups) == 4, f"expected 4 groups, got {len(groups)}"
    for t, gs in by_truth.items():
        assert len(gs) == 1 and len(gs[0]["truth_ids"]) == 1, f"group impurity at {t}"

    # 2. A1: the cheaper ticket-only variant is called out as not like-for-like.
    a1 = by_truth["A1"][0]
    assert len(a1["variants"]) == 3
    assert any("not like-for-like" in n for n in a1["notes"]), a1["notes"]

    # 3. A2: meals difference between the two Goa variants is surfaced.
    a2 = by_truth["A2"][0]
    cheaper = a2["variants"][0]
    assert "meals" in cheaper["missing_vs_richest"], cheaper

    # 4. A3: the non-refundable variant triggers the cancellation note.
    a3 = by_truth["A3"][0]
    assert any("non-refundable" in n for n in a3["notes"]), a3["notes"]

    # 5. A4 stands alone (single supplier offers it) and stays its own group.
    assert len(by_truth["A4"][0]["variants"]) == 1

    print(f"SIGHTSEEING TESTS PASSED — {len(SAMPLE_ACTIVITIES)} records -> "
          f"{len(groups)} attraction groups, differences preserved")


if __name__ == "__main__":
    main()
