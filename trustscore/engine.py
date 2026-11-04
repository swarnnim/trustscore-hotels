"""TrustScore engine: multi-signal hotel matching + explainable trust scoring.

Design (grounded in industry hotel-mapping practice — see README):
- Multi-signal pairwise matching: normalised-name similarity, geo distance,
  phone equality, same city. Single-signal matching misses too many cases.
- CONSERVATIVE MERGE DOCTRINE: a wrong merge is worse than a duplicate.
  Hard geo guard blocks merges beyond 800 m unless phone + near-exact name
  both agree; mid-confidence pairs are flagged 'possible duplicate' and
  kept separate, never silently merged.
- Every TrustScore is emitted WITH its reasons. Nothing hidden.
"""
import difflib
import math
import re

ABBREV = {
    "htl": "hotel", "intl": "international", "ste": "suite", "st": "street",
    "rd": "road", "ave": "avenue", "dlx": "deluxe", "std": "standard",
    "exec": "executive", "fam": "family", "cxl": "cancellation",
    "residences": "residence",
}
STOP = {"the", "a", "an", "and", "&", "at", "in", "of"}
# 'hotel' alone carries no identity (nearly every record has it); words like
# 'suites' / 'resort' / 'residence' DO distinguish properties, so they stay.
GENERIC = {"hotel"}

MERGE_THRESHOLD = 0.72
FLAG_THRESHOLD = 0.62
HARD_GEO_GUARD_M = 800.0


def normalize_name(raw, city=""):
    s = raw.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    toks = [ABBREV.get(t, t) for t in s.split()]
    toks = [t for t in toks if t not in STOP and t not in GENERIC and t != city.lower()]
    return " ".join(toks)


def name_similarity(a, b):
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    if ta <= tb or tb <= ta:
        jaccard = max(jaccard, 0.85)  # one name is the other plus a suffix/prefix
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    return round(0.6 * jaccard + 0.4 * ratio, 4)


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def pair_score(a, b):
    """Return (score, dist_m, detail) for two supplier records."""
    if a["city"] != b["city"]:
        return 0.0, None, {}
    dist = haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
    ns = name_similarity(normalize_name(a["name_raw"], a["city"]),
                         normalize_name(b["name_raw"], b["city"]))
    geo = max(0.0, 1.0 - dist / 1000.0)  # 1.0 at 0 m, 0 at >=1000 m
    phone = 1.0 if a["phone"] and a["phone"] == b["phone"] else 0.0
    score = 0.55 * ns + 0.30 * geo + 0.15 * phone
    return round(score, 4), round(dist, 1), {"name": ns, "geo": round(geo, 3), "phone": phone}


def _mergeable(a, b, score, dist):
    if score >= MERGE_THRESHOLD and dist <= HARD_GEO_GUARD_M:
        return True
    # Phone exception: identical phone + near-exact name rescues a bad GPS fix.
    if (a["phone"] and a["phone"] == b["phone"]
            and dist <= 2000.0
            and score >= 0.60
            and name_similarity(normalize_name(a["name_raw"], a["city"]),
                                normalize_name(b["name_raw"], b["city"])) >= 0.80):
        return True
    return False


ROOM_RULES = [
    ("Executive Suite", ["executive", "suite", "ste"]),
    ("Family Room", ["family", "fam", "quad", "2+2"]),
    ("Deluxe King Room", ["deluxe", "dlx", "king"]),
    ("Standard Room", ["standard", "std", "classic"]),
]


def normalize_room(raw):
    s = raw.lower()
    for canon, keys in ROOM_RULES:
        if any(k in s for k in keys):
            return canon
    return "Standard Room"


def cluster(records):
    """Union-find clustering under the conservative merge doctrine.

    Returns (clusters, possible_dupes): clusters = list of record lists;
    possible_dupes = list of (id_a, id_b, score) flagged but NOT merged.
    """
    parent = {r["record_id"]: r["record_id"] for r in records}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    possible = []
    for i, a in enumerate(records):
        for b in records[i + 1:]:
            score, dist, _ = pair_score(a, b)
            if dist is None:
                continue
            if _mergeable(a, b, score, dist):
                ra, rb = find(a["record_id"]), find(b["record_id"])
                if ra != rb:
                    parent[rb] = ra
            elif score >= FLAG_THRESHOLD:
                possible.append((a["record_id"], b["record_id"], score))
    groups = {}
    for r in records:
        groups.setdefault(find(r["record_id"]), []).append(r)
    return list(groups.values()), possible


def trust_score(members):
    """Score one canonical listing 0-100, with human-readable reasons."""
    reasons, flags = [], []
    rel = sum(m["supplier_reliability"] for m in members) / len(members)
    score = 40.0 * rel + 18.0  # supplier reliability baseline

    if len(members) >= 3:
        score += 14
        reasons.append(f"listed by {len(members)} suppliers — identity cross-verified")
    elif len(members) == 2:
        score += 9
        reasons.append("listed by 2 suppliers — identity cross-verified")
    else:
        flags.append("single-supplier listing — cannot cross-verify identity")

    photo_spread = max(m["photo_count"] for m in members) - min(m["photo_count"] for m in members)
    if len(members) > 1 and photo_spread <= 12:
        score += 8
        reasons.append("photo sets broadly consistent across suppliers")
    elif len(members) > 1:
        flags.append("photo counts differ a lot across suppliers — check imagery")

    freshest = min(m["rate_age_hours"] for m in members)
    if freshest <= 6:
        score += 8
        reasons.append(f"freshest rate is {freshest}h old")
    elif freshest > 48:
        score -= 8
        flags.append(f"all rates stale (freshest is {freshest}h old) — re-price before booking")

    cancels = {m["free_cancel_days"] for m in members}
    # Non-refundable vs any free cancellation is a conflict by itself;
    # otherwise a spread of 3+ days between suppliers counts as one.
    conflict = len(cancels) > 1 and ((min(cancels) == 0 and max(cancels) >= 1)
                                     or (max(cancels) - min(cancels)) >= 3)
    if conflict:
        score -= 12
        flags.append("cancellation terms CONFLICT across suppliers — check before booking")
    elif len(members) > 1:
        score += 6
        reasons.append("cancellation terms consistent across suppliers")

    prices = [m["price_inr"] for m in members]
    spread = (max(prices) - min(prices)) / max(min(prices), 1)
    if spread > 0.30:
        score -= 6
        flags.append(f"wide price spread across suppliers ({spread:.0%}) — verify the cheapest rate")
    return max(0, min(100, round(score))), reasons, flags


def build_listings(records):
    clusters, possible = cluster(records)
    listings = []
    for members in clusters:
        members = sorted(members, key=lambda m: m["price_inr"])
        canonical = max(members, key=lambda m: m["supplier_reliability"])
        score, reasons, flags = trust_score(members)
        listings.append({
            "canonical_name": canonical["name_raw"].title() if canonical["name_raw"].isupper()
                              else canonical["name_raw"],
            "city": canonical["city"],
            "stars": canonical["stars"],
            "suppliers": sorted({m["supplier"] for m in members}),
            "supplier_records": [{
                "record_id": m["record_id"], "supplier": m["supplier"],
                "supplier_hotel_id": m["supplier_hotel_id"], "name_raw": m["name_raw"],
                "room_raw": m["room_raw"], "room_canonical": normalize_room(m["room_raw"]),
                "price_inr": m["price_inr"], "cancellation_raw": m["cancellation_raw"],
                "rate_age_hours": m["rate_age_hours"],
            } for m in members],
            "best_price_inr": members[0]["price_inr"],
            "rooms": sorted({normalize_room(m["room_raw"]) for m in members}),
            "trust_score": score,
            "reasons": reasons,
            "flags": flags,
            "truth_ids": sorted({m["truth_id"] for m in members}),
        })
    listings.sort(key=lambda l: (-l["trust_score"], l["best_price_inr"]))
    return listings, possible


def evaluate(records, listings):
    """Merge quality vs ground truth: pairwise precision/recall + purity."""
    truth_of = {r["record_id"]: r["truth_id"] for r in records}
    merged_pairs = set()
    rid_of = {}
    for idx, l in enumerate(listings):
        for sr in l["supplier_records"]:
            rid_of[sr["record_id"]] = idx
    ids = list(truth_of)
    tp = fp = fn = 0
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            same_truth = truth_of[a] == truth_of[b]
            same_cluster = rid_of[a] == rid_of[b]
            if same_cluster and same_truth:
                tp += 1
            elif same_cluster and not same_truth:
                fp += 1
            elif same_truth and not same_cluster:
                fn += 1
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    impure = [l["canonical_name"] for l in listings if len(l["truth_ids"]) > 1]
    return {"pairwise_precision": round(precision, 4),
            "pairwise_recall": round(recall, 4),
            "impure_clusters": impure}
