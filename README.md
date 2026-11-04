# TrustScore Hotels — Prototype

**VOYAGEHACK 4.0 · Team Sam10 Voyagers · Problem Statement: Multi Supplier Optimization**

An explainable data-trust layer over multi-supplier hotel search: supplier
records of the same real hotel are merged into ONE canonical listing, room
types are normalised into a shared taxonomy, and every listing carries a
**TrustScore with its reasons shown** — so an agent can sort by the cheapest
*reliable* rate instead of guessing between five near-identical listings.

> The dataset in this prototype is **synthetic sample data** (generated,
> seed 42), modelled on the messiness described in industry hotel-mapping
> practice. It is not real supplier or TBO data. Ground-truth hotel IDs are
> kept on every record purely so merge quality can be measured honestly.

## Run it (Python 3, stdlib only, $0)

```bash
python3 -m trustscore.data_gen     # writes sample_data.json (41 records, 12 real hotels)
python3 -m trustscore.run_demo     # writes demo.html + listings.json, prints summary
python3 tests/test_engine.py       # all tests, plain asserts
```

Open `demo.html` for the before/after view: the raw result list an agent
sees today vs. the ranked TrustScore listings, each with a drill-down to
every underlying supplier record ("nothing hidden, everything explained").

## Verified results on the sample set

| Metric | Value |
|---|---|
| Supplier records in | 41 |
| Canonical listings out | 12 (29 duplicates collapsed) |
| Merge precision (pairwise, vs ground truth) | **1.000** |
| Merge recall (pairwise, vs ground truth) | **1.000** |
| Impure clusters (wrong merges) | **0** |
| Possible-duplicate flags (kept separate) | 2 |

## How it works

1. **Multi-signal matching** (per record pair, same city only):
   normalised-name similarity (abbreviation expansion, generic-word removal,
   token Jaccard + sequence ratio, subset bonus) × 0.55, geo proximity
   (haversine decay) × 0.30, exact phone match × 0.15.
2. **Conservative merge doctrine** — a wrong merge is worse than a duplicate:
   merge at score ≥ 0.72 within an 800 m hard geo guard; a phone + near-exact
   name rescue handles bad GPS fixes; mid-confidence pairs (≥ 0.62) are
   flagged *possible duplicate* and **kept separate**, never silently merged.
   The sample set includes the traps this doctrine exists for: two different
   "Grand Orchid" properties ~900 m apart (must not merge), a 720 m GPS error
   (must merge via phone), and a single-supplier listing (flagged, not trusted).
3. **Room normalisation**: supplier labels (`DLX King`, `FAM Room 4 Pax`,
   `Executive Ste`) collapse into a shared taxonomy.
4. **TrustScore (0–100), always with reasons**: supplier reliability baseline,
   cross-supplier identity verification, photo-set consistency, rate
   freshness, cancellation-term agreement — with explicit flags for
   conflicts ("cancellation terms CONFLICT — check before booking"),
   stale rates, wide price spreads, and single-supplier listings.
5. **Ranking**: TrustScore first, then best price — the safest-to-book order.

## Design sources

- Vervotech, *What Is Hotel Mapping? Complete Guide* — no universal hotel ID;
  supplier overlap "routinely runs past 60%" in major markets; rules-based
  matching = fuzzy name + geo radius + address normalisation; multi-signal
  evaluation beats single-signal matching. (vervotech.com)
- Vervotech, *The Hidden Cost of Duplicate Hotel Listings* — duplicate causes
  (per-supplier IDs, naming inconsistency, rebranding) and room-level mapping
  as a second layer. (vervotech.com)
- GBTA research — 72% of corporate travel buyers cite travellers finding
  cheaper rates outside managed channels as a top pain point.
  (Figures as cited in the team's Idea Submission deck, with sources in its
  speaker notes.)

## Roadmap to the Prototype Round (26 Nov – 24 Dec 2026)

- ~~HTTP API wrapper~~ DONE 2026-11-04: `trustscore/server.py` serves the
  demo page, `/api/listings`, `/api/activities`, `/api/health` (stdlib only).
- ~~Sightseeing extension~~ DONE 2026-11-04: `trustscore/sightseeing.py`
  groups variants per attraction (IDF-weighted landmark tokens + geo) and
  preserves inclusion differences with explicit not-like-for-like notes;
  8 sample records → 4 groups, tests pass.
- Still to do: learn the merge threshold from labelled pairs; add photo-hash
  agreement as a fifth signal; track precision/recall as a regression gate.
- 10-slide prototype deck DRAFT built 2026-11-04 (`voyagehack-4-prototype-deck`
  in the goal files); recorded walkthrough video still to make in-round.

## Team

Sam10 Voyagers — Swarnnim Agnihotri (Leader) · Patel Harshada Vijay ·
Apu Paul · Kartik Jain
