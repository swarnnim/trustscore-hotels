"""Deterministic generator of a SAMPLE multi-supplier hotel dataset.

The data is synthetic and clearly labelled as sample data. It mimics the
messiness described in industry hotel-mapping practice: no universal hotel
ID, variant names, jittered GPS, clashing room labels, stale cached rates,
and cancellation policies written in incompatible formats.

Ground truth (`truth_id`) is stored on every record so the engine's merge
quality can be measured (precision / recall), never hidden.
"""
import json
import math
import os
import random

SUPPLIERS = {
    # fictional sample suppliers with a reliability prior (used by scoring)
    "BedBank Alpha": 0.94,
    "GlobalRooms": 0.90,
    "TravelWholesale Co": 0.85,
    "DirectConnect": 0.97,
}

# (truth_id, canonical name, city, lat, lon, phone, stars, base price INR)
HOTELS = [
    ("H01", "Azure Palm Resort & Spa", "Goa", 15.4909, 73.8278, "+91-832-555-0101", 5, 12400),
    ("H02", "Grand Orchid Hotel", "Dubai", 25.2048, 55.2708, "+971-4-555-0142", 4, 9800),
    ("H03", "Grand Orchid Suites", "Dubai", 25.2130, 55.2780, "+971-4-555-0199", 4, 8600),
    ("H04", "Riverside Lotus Hotel", "Bangkok", 13.7435, 100.4930, "+66-2-555-0117", 4, 5400),
    ("H05", "The Banyan Courtyard", "Bangkok", 13.7563, 100.5018, "+66-2-555-0130", 5, 11200),
    ("H06", "Seaside Meridian", "Goa", 15.2993, 74.1240, "+91-832-555-0176", 4, 7600),
    ("H07", "Hotel Surya International", "Jaipur", 26.9124, 75.7873, "+91-141-555-0124", 3, 3900),
    ("H08", "Marina Skyline Hotel", "Dubai", 25.0805, 55.1403, "+971-4-555-0111", 5, 15900),
    ("H09", "Old Town Heritage Inn", "Jaipur", 26.9239, 75.8267, "+91-141-555-0158", 3, 3100),
    ("H10", "Palm Grove Beach Resort", "Goa", 15.5516, 73.7547, "+91-832-555-0129", 4, 8900),
    ("H11", "Siam Orchid Residence", "Bangkok", 13.7308, 100.5417, "+66-2-555-0163", 4, 6700),
    ("H12", "Crystal Dunes Hotel", "Dubai", 25.2695, 55.3095, "+971-4-555-0177", 4, 10500),
]

NAME_VARIANTS = {
    "H01": ["Azure Palm Resort & Spa", "AZURE PALM RESORT AND SPA", "Azure Palm Resort", "Azure Palm Resort & Spa Goa"],
    "H02": ["Grand Orchid Hotel", "GRAND ORCHID HTL", "Grand Orchid Hotel Dubai", "Hotel Grand Orchid"],
    "H03": ["Grand Orchid Suites", "Grand Orchid Suites Dubai", "GRAND ORCHID SUITES"],
    "H04": ["Riverside Lotus Hotel", "Riverside Lotus", "RIVERSIDE LOTUS HOTEL BANGKOK", "Lotus Riverside Hotel"],
    "H05": ["The Banyan Courtyard", "Banyan Courtyard Hotel", "THE BANYAN COURTYARD"],
    "H06": ["Seaside Meridian", "Seaside Meridian Hotel Goa", "SEASIDE MERIDIAN"],
    "H07": ["Hotel Surya International", "Surya Intl Hotel", "HOTEL SURYA INTL", "Surya International"],
    "H08": ["Marina Skyline Hotel", "Marina Skyline", "MARINA SKYLINE HOTEL DUBAI"],
    "H09": ["Old Town Heritage Inn", "Old Town Heritage", "OLD TOWN HERITAGE INN JAIPUR"],
    "H10": ["Palm Grove Beach Resort", "Palm Grove Resort", "PALM GROVE BEACH RESORT GOA", "Palm Grove Beach Resort & Spa"],
    "H11": ["Siam Orchid Residence", "Siam Orchid Residences", "SIAM ORCHID RESIDENCE BANGKOK"],
    "H12": ["Crystal Dunes Hotel", "Crystal Dunes", "CRYSTAL DUNES HOTEL"],
}

ROOM_VARIANTS = [
    ("Standard Room", ["Standard Room", "STD Room", "Standard", "Classic Room"]),
    ("Deluxe King Room", ["Deluxe King Room", "DLX King", "Deluxe Room - King Bed", "King Deluxe"]),
    ("Executive Suite", ["Executive Suite", "Exec Suite", "Suite - Executive", "Executive Ste"]),
    ("Family Room", ["Family Room", "FAM Room 4 Pax", "Family Quad", "Family Room (2+2)"]),
]

CANCEL_FORMATS = [
    "Free cancellation until {d} days before check-in",
    "FREE CXL {d}D PRIOR",
    "Cancellation: free up to {d} days prior to arrival",
    "free_cancellation_days={d}",
]


def _jitter(rng, lat, lon, meters):
    """Move a point by roughly `meters` in a random direction."""
    dx = rng.uniform(-1, 1)
    dy = rng.uniform(-1, 1)
    norm = math.hypot(dx, dy) or 1.0
    dlat = (meters * dy / norm) / 111_320.0
    dlon = (meters * dx / norm) / (111_320.0 * math.cos(math.radians(lat)))
    return round(lat + dlat, 6), round(lon + dlon, 6)


def generate(seed=42):
    rng = random.Random(seed)
    records = []
    rid = 0
    for truth_id, name, city, lat, lon, phone, stars, base in HOTELS:
        variants = NAME_VARIANTS[truth_id]
        # H09 is the single-supplier edge case; most hotels appear 3-4 times.
        if truth_id == "H09":
            suppliers = ["DirectConnect"]
        else:
            suppliers = rng.sample(list(SUPPLIERS), rng.choice([3, 4, 4]))
        for sup in suppliers:
            rid += 1
            # GPS jitter: mostly small, one deliberately bad fix for H05.
            meters = rng.uniform(15, 260)
            if truth_id == "H05" and sup == "TravelWholesale Co":
                meters = 720  # bad GPS: must still merge via phone + name
            rlat, rlon = _jitter(rng, lat, lon, meters)
            # Conflicting cancellation for H02 via one supplier.
            free_days = rng.choice([1, 2, 3, 5, 7])
            if truth_id == "H02" and sup == "TravelWholesale Co":
                free_days = 0  # non-refundable outlier vs. others' 5-7 days
            room_label = rng.choice(ROOM_VARIANTS[1][1])
            records.append({
                "record_id": f"R{rid:03d}",
                "supplier": sup,
                "supplier_reliability": SUPPLIERS[sup],
                "supplier_hotel_id": f"{sup.split()[0][:2].upper()}-{1000 + rid * 7}",
                "name_raw": rng.choice(variants),
                "city": city,
                "lat": rlat,
                "lon": rlon,
                "phone": phone if rng.random() > 0.15 else "",
                "stars": stars,
                "room_raw": room_label,
                "price_inr": int(base * rng.uniform(0.86, 1.16)),
                "photo_count": rng.randint(6, 34),
                "cancellation_raw": ("Non-refundable" if free_days == 0
                                     else rng.choice(CANCEL_FORMATS).format(d=free_days)),
                "free_cancel_days": free_days,
                "rate_age_hours": rng.choice([1, 3, 6, 14, 26, 49, 80]),
                "truth_id": truth_id,
            })
    rng.shuffle(records)
    return records


if __name__ == "__main__":
    data = generate()
    out = os.path.join(os.path.dirname(__file__), "..", "sample_data.json")
    with open(out, "w") as f:
        json.dump({"note": "SYNTHETIC SAMPLE DATA - not real supplier data",
                   "records": data}, f, indent=1)
    print(f"wrote {out}: {len(data)} records, "
          f"{len({r['truth_id'] for r in data})} real hotels")
