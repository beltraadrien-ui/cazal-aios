"""Scrape forums / Reddit FR (clim, PAC, chauffage, froid) via Apify pour `veille-niche`.

Calqué sur Master-content/.claude/commands/scripts/veille/scrape_reddit.py :
**stratégie batched parallèle** — 3 petits runs Apify sync en parallèle plutôt qu'un
gros run, pour rester sous le timeout 300s du endpoint sync (la limite dépend du nombre
d'items à scraper, ~5s/item, pas du nombre de subs). Un batch de ~10 items finit en ~50s.

Différences avec la version Master-content :
  - plomberie Cazal : `shared/config.py` (load_env / require), variable `APIFY_TOKEN`
    (PAS `APIFY_API_TOKEN`) ;
  - tracks Cazal : `b2c` (particuliers) / `b2b` (pro froid commercial) au lieu de geek/business ;
  - subreddits FR orientés clim / PAC / chauffage / rénovation.

Tant qu'`APIFY_TOKEN` est un placeholder (`.env` non rempli — Bloc 1 de reste-a-faire.md),
le script échoue proprement via config.require() : c'est attendu. `veille-niche` tient alors
sur les 2 sources WebSearch (Google/PAA + actus aides/primes).

Usage : python shared/scripts/scrape_forums.py [--max-items 30] [--out-dir path]
`--max-items` est le TOTAL réparti sur les 3 batches (défaut 30 → 10 par batch).

Actors de secours si `trudax~reddit-scraper-lite` casse :
  - oxylabs/reddit-scraper · apidojo/reddit-scraper · easyapi/reddit-search-scraper
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

# Plomberie Cazal : import package-style depuis la racine du repo (parents[2]).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.config import APIFY_API_TOKEN, ROOT  # noqa: E402


APIFY_ACTOR_ID = "trudax~reddit-scraper-lite"

# Track b2c : particuliers (clim, PAC, chauffage, rénovation, énergie/primes).
SUBS_B2C = {"bricolage", "RenovationFR", "france", "energie", "vosfinances"}

# Track b2b : pros / froid commercial / restauration (signal plus rare).
SUBS_B2B = {"restaurateur", "Entrepreneur"}

# 3 batches parallèles. Chaque batch reste petit pour finir <60s sur le endpoint sync.
# Le tag de track se fait item par item (selon le sub source), pas selon le batch.
BATCHES = [
    {"name": "batch-1-b2c-a", "subs": ["bricolage", "RenovationFR"]},
    {"name": "batch-2-b2c-b", "subs": ["france", "energie", "vosfinances"]},
    {"name": "batch-3-b2b", "subs": ["restaurateur", "Entrepreneur"]},
]


def classify_track(sub_name: str) -> str:
    """Retourne 'b2c' | 'b2b' | 'unknown' pour un nom de subreddit."""
    if sub_name in SUBS_B2C:
        return "b2c"
    if sub_name in SUBS_B2B:
        return "b2b"
    return "unknown"


def run_apify_batch(batch: dict, token: str, max_items_per_batch: int) -> list:
    """Appelle le endpoint Apify sync pour un batch de subs. Retourne la liste de posts.

    Lève en cas d'erreur HTTP pour que l'appelant marque ce batch comme failed
    sans bloquer les autres batches.
    """
    name = batch["name"]
    subs = batch["subs"]
    start_urls = [
        {"url": f"https://www.reddit.com/r/{sub}/top/?t=week"}
        for sub in subs
    ]
    payload = {
        "startUrls": start_urls,
        "maxItems": max_items_per_batch,
        "skipComments": True,
        "proxy": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
    }

    url = (
        f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}"
        f"/run-sync-get-dataset-items?token={token}&timeout=290"
    )
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    t0 = time.time()
    print(
        f"[forums] {name} started ({len(subs)} subs, maxItems={max_items_per_batch})",
        file=sys.stderr,
    )
    with urllib.request.urlopen(req, timeout=310) as resp:
        raw = resp.read().decode("utf-8")

    items = json.loads(raw) if raw else []
    elapsed = time.time() - t0
    print(
        f"[forums] {name} completed in {elapsed:.1f}s -> {len(items)} items",
        file=sys.stderr,
    )
    return items


def extract_sub_from_item(item: dict) -> str:
    """Extraction best-effort du nom de sub depuis un item reddit-scraper-lite."""
    parsed = item.get("parsedUrl") or {}
    candidate = (
        item.get("communityName")
        or item.get("subreddit")
        or parsed.get("communityName")
        or parsed.get("subreddit")
    )
    if candidate:
        return candidate.lstrip("r/").lstrip("/")
    url = item.get("url", "")
    if "/r/" in url:
        parts = url.split("/r/", 1)[1].split("/", 1)
        return parts[0]
    return "unknown"


def run(max_items: int, out_dir: Path) -> Path:
    token = APIFY_API_TOKEN
    if not token or token.startswith("REPLACE_WITH_"):
        raise RuntimeError(
            "Secret manquant : APIFY_API_TOKEN. Renseigne-le dans le .env racine puis "
            "relance. (placeholder non remplacé — cf. Bloc 1 de reste-a-faire.md)"
        )
    today = date.today()

    max_items_per_batch = max(1, max_items // len(BATCHES))
    print(
        f"[forums] running {len(BATCHES)} batches in parallel, "
        f"{max_items_per_batch} items/batch "
        f"(total target: {max_items_per_batch * len(BATCHES)})",
        file=sys.stderr,
    )

    all_items: list = []
    failed_batches: list = []

    with ThreadPoolExecutor(max_workers=len(BATCHES)) as pool:
        futures = {
            pool.submit(run_apify_batch, b, token, max_items_per_batch): b
            for b in BATCHES
        }
        for fut in as_completed(futures):
            batch = futures[fut]
            try:
                all_items.extend(fut.result())
            except Exception as e:  # noqa: BLE001 — on log et on continue
                print(
                    f"[forums] {batch['name']} FAILED: {type(e).__name__}: {e}",
                    file=sys.stderr,
                )
                failed_batches.append(batch["name"])

    out_dir.mkdir(parents=True, exist_ok=True)

    # Réponse brute (debug) avant tag.
    raw_path = out_dir / f"forums_{today.isoformat()}.raw.json"
    raw_path.write_text(
        json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Tag de chaque item avec son track selon le sub source.
    tagged = []
    for item in all_items:
        sub = extract_sub_from_item(item)
        item["subreddit_name"] = sub
        item["track"] = classify_track(sub)
        tagged.append(item)

    out_path = out_dir / f"forums_{today.isoformat()}.json"
    out_path.write_text(
        json.dumps(tagged, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    b2c_count = sum(1 for t in tagged if t["track"] == "b2c")
    b2b_count = sum(1 for t in tagged if t["track"] == "b2b")
    unknown_count = sum(1 for t in tagged if t["track"] == "unknown")
    print(
        f"[forums] wrote {len(tagged)} items "
        f"(b2c={b2c_count}, b2b={b2b_count}, unknown={unknown_count}) -> {out_path}",
        file=sys.stderr,
    )
    if failed_batches:
        print(f"[forums] WARNING failed batches: {failed_batches}", file=sys.stderr)
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-items",
        type=int,
        default=30,
        help="Total items répartis sur les batches (défaut 30 = 10 par batch)",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    out_dir = args.out_dir or (ROOT / "active" / "veille")
    run(max_items=args.max_items, out_dir=out_dir)


if __name__ == "__main__":
    main()
