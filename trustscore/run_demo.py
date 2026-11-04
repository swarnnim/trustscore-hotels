"""TrustScore Hotels demo: BEFORE (raw multi-supplier results) vs
AFTER (canonical, trust-scored listings) on the sample dataset.

Usage:  python3 -m trustscore.run_demo
Writes demo.html next to the project root and prints the run summary.
"""
import html
import json
import os

from .data_gen import generate
from .engine import build_listings, evaluate

ROOT = os.path.join(os.path.dirname(__file__), "..")


def esc(x):
    return html.escape(str(x))


def render(records, listings, possible, ev):
    raw_rows = "\n".join(
        f"<tr><td>{esc(r['supplier'])}</td><td>{esc(r['name_raw'])}</td><td>{esc(r['city'])}</td>"
        f"<td>{esc(r['room_raw'])}</td><td>₹{r['price_inr']:,}</td><td>{esc(r['cancellation_raw'])}</td>"
        f"<td>{r['rate_age_hours']}h</td></tr>" for r in records)
    cards = []
    for l in listings:
        badge = "#1d9e75" if l["trust_score"] >= 80 else ("#e8a13a" if l["trust_score"] >= 65 else "#d95f4b")
        reasons = "".join(f"<li>✓ {esc(x)}</li>" for x in l["reasons"])
        flags = "".join(f"<li>⚠ {esc(x)}</li>" for x in l["flags"])
        detail_rows = "".join(
            f"<tr><td>{esc(s['supplier'])}</td><td>{esc(s['name_raw'])}</td>"
            f"<td>{esc(s['room_canonical'])}</td><td>₹{s['price_inr']:,}</td>"
            f"<td>{esc(s['cancellation_raw'])}</td></tr>" for s in l["supplier_records"])
        cards.append(f"""
<article class="card">
  <header><h3>{esc(l['canonical_name'])}</h3>
    <span class="badge" style="background:{badge}">TrustScore {l['trust_score']}</span></header>
  <p class="meta">{esc(l['city'])} · {'★' * l['stars']} · best rate ₹{l['best_price_inr']:,}
     · rooms: {esc(', '.join(l['rooms']))}</p>
  <ul class="reasons">{reasons}{flags}</ul>
  <details><summary>View all {len(l['supplier_records'])} supplier records</summary>
    <table><tr><th>Supplier</th><th>Their name</th><th>Room (normalised)</th><th>Price</th><th>Cancellation</th></tr>
    {detail_rows}</table></details>
</article>""")
    dupes = "".join(f"<li>{a} ↔ {b} — match score {s:.2f}: flagged as possible duplicate, kept separate (conservative merge)</li>"
                    for a, b, s in possible) or "<li>None</li>"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>TrustScore Hotels — Prototype Demo (sample data)</title><style>
body{{font-family:system-ui,sans-serif;background:#0b1f3a;color:#e8eef7;margin:0;padding:24px}}
h1 span{{color:#2dd4bf}} table{{border-collapse:collapse;width:100%;font-size:13px}}
td,th{{border-bottom:1px solid #24425f;padding:5px 8px;text-align:left}}
.card{{background:#102a4a;border:1px solid #24425f;border-radius:10px;padding:16px;margin:12px 0}}
.card header{{display:flex;justify-content:space-between;align-items:center}}
.badge{{color:#08131f;font-weight:700;border-radius:999px;padding:4px 12px}}
.meta{{color:#9fb6cf}} .reasons{{list-style:none;padding:0}} details{{margin-top:8px}}
.grid{{display:grid;grid-template-columns:1fr;gap:8px}} .stat{{color:#2dd4bf;font-weight:700}}
</style></head><body>
<h1>TrustScore <span>Hotels</span> — prototype demo</h1>
<p>SYNTHETIC SAMPLE DATA (generated, seed 42) — not real supplier data.
{len(records)} raw supplier records → <span class="stat">{len(listings)} canonical listings</span>
({len(records) - len(listings)} duplicates collapsed). Merge quality vs ground truth:
pairwise precision <span class="stat">{ev['pairwise_precision']}</span>,
recall <span class="stat">{ev['pairwise_recall']}</span>.</p>
<h2>Before — what the agent sees today</h2>
<table><tr><th>Supplier</th><th>Name as listed</th><th>City</th><th>Room as listed</th><th>Price</th><th>Cancellation</th><th>Rate age</th></tr>
{raw_rows}</table>
<h2>After — TrustScore listings (ranked by trust, then price)</h2>
{''.join(cards)}
<h2>Possible duplicates — flagged, NOT merged</h2><ul>{dupes}</ul>
<p class="meta">Conservative merge doctrine: a wrong merge is worse than a duplicate, so
mid-confidence pairs stay separate and visible. Team Sam10 Voyagers · VOYAGEHACK 4.0 · Multi Supplier Optimization.</p>
</body></html>"""


def main():
    records = generate()
    listings, possible = build_listings(records)
    ev = evaluate(records, listings)
    out = os.path.join(ROOT, "demo.html")
    with open(out, "w") as f:
        f.write(render(records, listings, possible, ev))
    summary = {
        "records_in": len(records),
        "listings_out": len(listings),
        "duplicates_collapsed": len(records) - len(listings),
        "possible_duplicates_flagged": len(possible),
        "evaluation": ev,
    }
    with open(os.path.join(ROOT, "listings.json"), "w") as f:
        json.dump({"summary": summary, "listings": listings}, f, indent=1)
    print(json.dumps(summary, indent=1))
    print("demo written to", out)


if __name__ == "__main__":
    main()
