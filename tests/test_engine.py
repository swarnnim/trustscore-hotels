"""Plain-assert tests for the TrustScore engine (no pytest needed).

Run: python3 tests/test_engine.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trustscore.data_gen import generate          # noqa: E402
from trustscore.engine import build_listings, evaluate, normalize_room  # noqa: E402


def main():
    records = generate()
    listings, possible = build_listings(records)
    ev = evaluate(records, listings)
    by_truth = {}
    for l in listings:
        for t in l["truth_ids"]:
            by_truth.setdefault(t, []).append(l)

    # 1. No impure clusters: a wrong merge is worse than a duplicate.
    assert not ev["impure_clusters"], f"impure clusters: {ev['impure_clusters']}"

    # 2. The Dubai lookalikes must NOT merge (similar names, ~900 m apart).
    orchid = by_truth["H02"][0]
    assert orchid is not by_truth["H03"][0], "Grand Orchid Hotel merged with Grand Orchid Suites!"
    assert len(by_truth["H02"]) == 1 and len(by_truth["H03"]) == 1

    # 3. The bad-GPS record (720 m jitter, same phone) still merges.
    assert len(by_truth["H05"]) == 1, "H05 split — phone exception failed"

    # 4. Cancellation conflict on H02 is flagged, with the exact wording.
    assert any("CONFLICT" in f for f in orchid["flags"]), "H02 cancellation conflict not flagged"

    # 5. Single-supplier hotel is flagged, never silently trusted.
    solo = by_truth["H09"][0]
    assert any("single-supplier" in f for f in solo["flags"])

    # 6. Every listing has a score in range and at least one reason or flag.
    for l in listings:
        assert 0 <= l["trust_score"] <= 100
        assert l["reasons"] or l["flags"], f"unexplained score for {l['canonical_name']}"

    # 7. Room normalisation collapses supplier labels into the shared taxonomy.
    assert normalize_room("DLX King") == "Deluxe King Room"
    assert normalize_room("FAM Room 4 Pax") == "Family Room"
    assert normalize_room("Executive Ste") == "Executive Suite"

    # 8. Strong merge quality on the sample set.
    assert ev["pairwise_precision"] == 1.0, ev
    assert ev["pairwise_recall"] >= 0.90, ev

    print(f"ALL TESTS PASSED — {len(records)} records -> {len(listings)} listings, "
          f"precision {ev['pairwise_precision']}, recall {ev['pairwise_recall']}, "
          f"{len(possible)} possible-duplicate flags")


if __name__ == "__main__":
    main()
