"""Script di prova — non committare."""
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.feed_reader import download_feed, load_postings, prefilter

CACHE_DIR = Path(__file__).resolve().parent.parent / "feeds_cache"

print("Scarico il feed...")
db = download_feed(CACHE_DIR)
print(f"DB: {db}\n")

postings = load_postings(db)
kept, discarded = prefilter(postings)

# --- 1. Totali ---
print("=" * 50)
print(f"Totali : {len(postings)}")
print(f"Tenuti : {len(kept)}")
print(f"Scartati: {len(discarded)}")

# --- 2. Conteggio scartati per motivo ---
print("\n--- Scartati per motivo ---")
counts = Counter(d["_discard_reason"] for d in discarded)
for motivo, n in counts.most_common():
    print(f"  {n:5d}  {motivo}")

# --- 3. Sopravvissuti per priorità ---
print("\n--- Sopravvissuti per priorità ---")
by_priority: dict[int, list[dict]] = defaultdict(list)
for p in kept:
    by_priority[p["_role_priority"]].append(p)

LABEL = {1: "analytics_ai", 2: "consulting_security", 3: "software", 4: "support_qa"}
for pri in sorted(by_priority):
    items = by_priority[pri]
    print(f"\n  Priorità {pri} — {LABEL.get(pri, '?')} : {len(items)} annunci")
    for p in random.sample(items, min(5, len(items))):
        print(f"    [{p.get('country_code') or '??'}]  {p['title']}  —  {p['company_name']}")
