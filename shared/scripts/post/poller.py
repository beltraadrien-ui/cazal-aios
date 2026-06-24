"""Poller de KPIs — rafraîchit quotidiennement les posts de Loïc dans Supabase.

Calqué sur la logique du workflow n8n `ig-daily-poller.json` de Master-content :
  Fetch media (own) → Reels only → upsert content (idempotent) → create daily snapshot.

Périmètre : comptes `type='own'` UNIQUEMENT (concurrents exclus — eux = scraper à la demande).
Déclenché par une routine LOCALE Claude (cron quotidien) ; ne s'occupe que du traitement.
Lit le `.env` local (Supabase + Apify). Idempotent : ne touche jamais aux champs d'analyse.

Usage :
    python shared/scripts/post/poller.py [--limit 30]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.config import APIFY_API_TOKEN, status  # noqa: E402
from shared.database import get_client, insert_snapshot, upsert_contenu  # noqa: E402
from shared.scripts.post.upsert_contenu_apify import fetch_posts_apify  # noqa: E402


def run(limit: int = 30) -> dict:
    # 1. Vérifier les clés
    if status("APIFY_API_TOKEN") != "SET" or status("SUPABASE_ANON_KEY") != "SET":
        raise EnvironmentError("APIFY_API_TOKEN et/ou SUPABASE_ANON_KEY manquant dans .env")

    # 2. Lister les comptes own
    client = get_client()
    comptes = client.table("comptes").select("id,handle,plateforme").eq(
        "type", "own").execute().data or []
    if not comptes:
        return {"comptes_own": 0, "contenu_rafraichis": 0, "snapshots": 0,
                "note": "aucun compte own configuré (table comptes, type='own')", "erreurs": []}

    n_contenu, n_snap, errors = 0, 0, []
    # 3. Pour chaque compte own
    for c in comptes:
        try:
            posts = fetch_posts_apify(c["handle"], limit)
        except Exception as e:  # noqa: BLE001
            errors.append({"handle": c["handle"], "error": str(e)[:200]})
            continue
        for p in posts:
            if not p["media_id"]:
                continue
            if not p["is_video"]:  # Reels Only (mirror du nœud n8n)
                continue
            try:
                upsert_contenu({
                    "id": p["media_id"], "compte_id": c["id"], "plateforme": "instagram",
                    "url": p.get("url"), "caption": p.get("caption"),
                    "post_date": p.get("post_date"), "thumbnail_url": p.get("thumbnail_url"),
                    "views": p["views"], "likes": p["likes"], "comments": p["comments"],
                })
                n_contenu += 1
                insert_snapshot(p["media_id"], {"views": p["views"], "likes": p["likes"],
                                                "comments": p["comments"]})
                n_snap += 1
            except Exception as e:  # noqa: BLE001  (continueOnFail : un échec n'arrête pas la boucle)
                errors.append({"media_id": p["media_id"], "error": str(e)[:200]})

    return {"comptes_own": len(comptes), "contenu_rafraichis": n_contenu,
            "snapshots": n_snap, "erreurs": errors}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=30)
    args = p.parse_args()
    print(json.dumps(run(args.limit), ensure_ascii=False))


if __name__ == "__main__":
    main()
