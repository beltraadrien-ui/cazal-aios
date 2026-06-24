"""Scrape Instagram via Apify puis UPSERT dans Supabase (comptes + contenu + snapshot).

Brique engine du moteur de perf. Deux usages partagent le **même fetch** (`fetch_posts_apify`) :
- `scraper-contenu-cazal` (à la demande) : découverte / ajout de comptes (own + concurrents).
- `poller.py` (récurrent) : rafraîchissement des KPIs du compte de Loïc.

Usage CLI (scraper à la demande) :
    python shared/scripts/post/upsert_contenu_apify.py <handle1> [<handle2> ...] \
        [--type own|concurrent] [--limit 30]

Prérequis : APIFY_API_TOKEN dans .env. JSON normalisé archivé dans active/contenu/.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.config import APIFY_API_TOKEN, APIFY_INSTAGRAM_ACTOR, ROOT  # noqa: E402
from shared.database import insert_snapshot, upsert_compte, upsert_contenu  # noqa: E402

ARCHIVE = ROOT / "active" / "contenu"


def _apify(payload: dict) -> list[dict]:
    if not APIFY_API_TOKEN or APIFY_API_TOKEN.startswith("REPLACE_WITH_"):
        raise EnvironmentError("APIFY_API_TOKEN manquant dans .env")
    url = (f"https://api.apify.com/v2/acts/{APIFY_INSTAGRAM_ACTOR}"
           f"/run-sync-get-dataset-items?token={APIFY_API_TOKEN}")
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Apify HTTP {e.code} : {e.read().decode('utf-8','ignore')[:400]}") from e


def _normalize(it: dict) -> dict:
    """Mappe un item Apify brut vers un dict normalisé (clés stables)."""
    media_id = it.get("id") or it.get("shortCode")
    return {
        "media_id": str(media_id) if media_id else None,
        "handle": it.get("ownerUsername"),
        "url": it.get("url"),
        "caption": it.get("caption"),
        "post_date": (it.get("timestamp") or "")[:19] or None,
        "thumbnail_url": it.get("displayUrl"),
        "video_url": it.get("videoUrl"),  # lien CDN .mp4 (expire vite → utiliser tout de suite)
        "is_video": it.get("type") == "Video",
        "views": it.get("videoViewCount") or it.get("videoPlayCount") or 0,
        "likes": it.get("likesCount") or 0,
        "comments": it.get("commentsCount") or 0,
    }


def fetch_posts_apify(handle: str, limit: int = 30) -> list[dict]:
    """Récupère les posts récents d'un handle via Apify et les renvoie normalisés.
    SOURCE DE VÉRITÉ du fetch — utilisée par le scraper ET le poller."""
    payload = {
        "directUrls": [f"https://www.instagram.com/{handle.lstrip('@')}/"],
        "resultsType": "posts",
        "resultsLimit": limit,
    }
    return [_normalize(it) for it in _apify(payload)]


def _row_from(post: dict, compte_id: str) -> dict:
    return {
        "id": post["media_id"],
        "compte_id": compte_id,
        "plateforme": "instagram",
        "url": post.get("url"),
        "caption": post.get("caption"),
        "post_date": post.get("post_date"),
        "thumbnail_url": post.get("thumbnail_url"),
        "views": post.get("views", 0),
        "likes": post.get("likes", 0),
        "comments": post.get("comments", 0),
    }


def run(handles: list[str], type_: str, limit: int) -> dict:
    if not handles:
        raise ValueError("aucun handle fourni")
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    compte_ids: dict[str, str] = {}
    n_contenu, archive_all = 0, []
    for handle in handles:
        posts = fetch_posts_apify(handle, limit)
        archive_all.extend(posts)
        for p in posts:
            if not p["media_id"] or not p["handle"]:
                continue
            if p["handle"] not in compte_ids:
                compte_ids[p["handle"]] = upsert_compte(p["handle"], "instagram", type_)
            cid = compte_ids[p["handle"]]
            upsert_contenu(_row_from(p, cid))
            insert_snapshot(p["media_id"], {"views": p["views"], "likes": p["likes"],
                                            "comments": p["comments"]})
            n_contenu += 1
    (ARCHIVE / f"scrape-{date.today().isoformat()}.json").write_text(
        json.dumps(archive_all, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"comptes": len(compte_ids), "contenu": n_contenu}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("handles", nargs="+")
    p.add_argument("--type", choices=["own", "concurrent"], default="concurrent")
    p.add_argument("--limit", type=int, default=30)
    args = p.parse_args()
    print(json.dumps({"ok": True, **run(args.handles, args.type, args.limit)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
