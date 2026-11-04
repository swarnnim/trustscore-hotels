"""Sightseeing extension: group equivalent activities across suppliers
WITHOUT merging away their real differences.

The Multi Supplier Optimization statement asks for sightseeing dedup that
distinguishes inclusions (transfers, meals, duration, access, cancellation).
So unlike hotels — where duplicates collapse into one listing — sightseeing
products group under one attraction while every variant stays visible, with
an explicit like-for-like comparison: a cheaper variant that drops transfers
and meals is NOT the same product, and the output says so.

Matching uses the same multi-signal idea as hotels, adapted: attraction
names vary far more than hotel names ("Goa North Tour — Beaches & Fort
Aguada" vs "North Goa Sightseeing Full Day" share one content word), so the
score combines an IDF-weighted token similarity (rare landmark tokens count
most) with geo proximity of the attraction itself.
"""
import math

INCLUSION_KEYS = ["hotel_pickup", "transfers", "meals", "guide",
                  "entry_tickets", "skip_the_line"]

# Synthetic sample data — same honesty rule as the hotel set.
# lat/lon are the attraction's location as reported by each supplier.
SAMPLE_ACTIVITIES = [
    {"record_id": "S01", "supplier": "BedBank Alpha", "supplier_reliability": 0.94,
     "name_raw": "Burj Khalifa At The Top — Level 124 & 125", "city": "Dubai",
     "lat": 25.1972, "lon": 55.2744,
     "duration_h": 2.0, "price_inr": 3900, "free_cancel_days": 3,
     "inclusions": {"entry_tickets": True, "skip_the_line": True},
     "truth_id": "A1"},
    {"record_id": "S02", "supplier": "GlobalRooms", "supplier_reliability": 0.90,
     "name_raw": "BURJ KHALIFA AT THE TOP TICKETS LVL 124", "city": "Dubai",
     "lat": 25.1975, "lon": 55.2740,
     "duration_h": 2.0, "price_inr": 3650, "free_cancel_days": 3,
     "inclusions": {"entry_tickets": True},
     "truth_id": "A1"},
    {"record_id": "S03", "supplier": "TravelWholesale Co", "supplier_reliability": 0.85,
     "name_raw": "Burj Khalifa Tour with Hotel Pickup", "city": "Dubai",
     "lat": 25.1968, "lon": 55.2751,
     "duration_h": 3.5, "price_inr": 5200, "free_cancel_days": 1,
     "inclusions": {"entry_tickets": True, "skip_the_line": True,
                    "hotel_pickup": True, "transfers": True},
     "truth_id": "A1"},
    {"record_id": "S04", "supplier": "BedBank Alpha", "supplier_reliability": 0.94,
     "name_raw": "Goa North Tour — Beaches & Fort Aguada", "city": "Goa",
     "lat": 15.4924, "lon": 73.7737,
     "duration_h": 8.0, "price_inr": 2400, "free_cancel_days": 5,
     "inclusions": {"transfers": True, "guide": True, "meals": True},
     "truth_id": "A2"},
    {"record_id": "S05", "supplier": "DirectConnect", "supplier_reliability": 0.97,
     "name_raw": "North Goa Sightseeing Full Day", "city": "Goa",
     "lat": 15.4931, "lon": 73.7729,
     "duration_h": 8.5, "price_inr": 1950, "free_cancel_days": 5,
     "inclusions": {"transfers": True, "guide": True},
     "truth_id": "A2"},
    {"record_id": "S06", "supplier": "GlobalRooms", "supplier_reliability": 0.90,
     "name_raw": "Bangkok Grand Palace & Wat Pho Half Day", "city": "Bangkok",
     "lat": 13.7500, "lon": 100.4913,
     "duration_h": 4.0, "price_inr": 2100, "free_cancel_days": 2,
     "inclusions": {"entry_tickets": True, "guide": True, "transfers": True},
     "truth_id": "A3"},
    {"record_id": "S07", "supplier": "TravelWholesale Co", "supplier_reliability": 0.85,
     "name_raw": "Grand Palace + Temple Tour BKK", "city": "Bangkok",
     "lat": 13.7496, "lon": 100.4920,
     "duration_h": 4.5, "price_inr": 2300, "free_cancel_days": 0,
     "inclusions": {"entry_tickets": True, "guide": True},
     "truth_id": "A3"},
    {"record_id": "S08", "supplier": "DirectConnect", "supplier_reliability": 0.97,
     "name_raw": "Dubai Desert Safari with BBQ Dinner", "city": "Dubai",
     "lat": 25.0657, "lon": 55.4010,
     "duration_h": 6.0, "price_inr": 4800, "free_cancel_days": 7,
     "inclusions": {"transfers": True, "meals": True, "guide": True},
     "truth_id": "A4"},
]

DURATION_TOLERANCE_H = 2.0   # pickup-including variants run longer; group, don't split
GROUP_THRESHOLD = 0.45
ACTIVITY_GENERIC = {"tour", "tours", "day", "full", "half", "tickets", "ticket",
                    "with", "sightseeing", "trip", "experience"}
LOCAL_ABBREV = {"lvl": "level", "bkk": "bangkok"}


def _tokens(record):
    from .engine import normalize_name
    toks = normalize_name(record["name_raw"], record["city"]).split()
    return {LOCAL_ABBREV.get(t, t) for t in toks} - ACTIVITY_GENERIC


def _idf_weights(records):
    df = {}
    for r in records:
        for t in _tokens(r):
            df[t] = df.get(t, 0) + 1
    n = len(records)
    return {t: math.log(1 + n / c) for t, c in df.items()}


def _weighted_sim(a, b, weights):
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = sum(weights.get(t, 1.0) for t in ta & tb)
    union = sum(weights.get(t, 1.0) for t in ta | tb)
    smaller = min(sum(weights.get(t, 1.0) for t in ta),
                  sum(weights.get(t, 1.0) for t in tb))
    jaccard = inter / union if union else 0.0
    containment = inter / smaller if smaller else 0.0
    return 0.5 * jaccard + 0.5 * containment


def _same_attraction(a, b, weights):
    from .engine import haversine_m
    if a["city"] != b["city"]:
        return False
    if abs(a["duration_h"] - b["duration_h"]) > DURATION_TOLERANCE_H:
        return False
    dist = haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
    geo = max(0.0, 1.0 - dist / 2000.0)
    score = 0.6 * _weighted_sim(a, b, weights) + 0.4 * geo
    return score >= GROUP_THRESHOLD


def group_activities(records):
    weights = _idf_weights(records)
    parent = {r["record_id"]: r["record_id"] for r in records}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(records):
        for b in records[i + 1:]:
            if _same_attraction(a, b, weights):
                ra, rb = find(a["record_id"]), find(b["record_id"])
                if ra != rb:
                    parent[rb] = ra
    groups = {}
    for r in records:
        groups.setdefault(find(r["record_id"]), []).append(r)
    return list(groups.values())


def compare_group(members):
    """Build the like-for-like comparison for one attraction group."""
    members = sorted(members, key=lambda m: m["price_inr"])
    all_inc = set()
    for m in members:
        all_inc |= {k for k, v in m["inclusions"].items() if v}
    variants, notes = [], []
    richest = max(members, key=lambda m: sum(m["inclusions"].values()))
    for m in members:
        missing = sorted(k for k in
                         {k for k, v in richest["inclusions"].items() if v}
                         if not m["inclusions"].get(k))
        variants.append({
            "supplier": m["supplier"], "name_raw": m["name_raw"],
            "duration_h": m["duration_h"], "price_inr": m["price_inr"],
            "free_cancel_days": m["free_cancel_days"],
            "inclusions": sorted(k for k, v in m["inclusions"].items() if v),
            "missing_vs_richest": missing,
        })
        if missing and m is not richest:
            notes.append(
                f"{m['supplier']} is ₹{richest['price_inr'] - m['price_inr']:,} cheaper than "
                f"{richest['supplier']} but excludes {', '.join(missing)} — not like-for-like")
    cancels = {m["free_cancel_days"] for m in members}
    if len(cancels) > 1 and min(cancels) == 0:
        notes.append("cancellation terms differ — one variant is non-refundable")
    return {
        "attraction": richest["name_raw"],
        "city": richest["city"],
        "suppliers": sorted({m["supplier"] for m in members}),
        "inclusions_seen": sorted(all_inc),
        "variants": variants,
        "notes": notes,
        "truth_ids": sorted({m["truth_id"] for m in members}),
    }


def build_activity_groups(records=None):
    records = records if records is not None else SAMPLE_ACTIVITIES
    return [compare_group(g) for g in group_activities(records)]
