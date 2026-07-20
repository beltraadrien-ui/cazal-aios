"""Poller de KPIs — rafraîchit quotidiennement les posts de Loïc dans Supabase.

DUAL-MODE (décision 2026-07-20) :
  - **Mode Meta** (préféré) : si META_ACCESS_TOKEN + IG_USER_ID sont SET dans .env →
    Meta Graph API (own-account), métriques riches : views, reach, likes, comments,
    shares, saves, total_interactions, avg/total watch time. Port du workflow n8n
    `ig-daily-poller.json` de Master-content (module `meta_graph.py`).
  - **Mode Apify** (fallback) : sinon, comportement historique — métriques publiques
    (views, likes, comments) via l'actor Instagram.

Périmètre : comptes `type='own'` UNIQUEMENT (concurrents exclus — eux = scraper à la demande).
Déclenché par une routine LOCALE Claude (cron quotidien) ; ne s'occupe que du traitement.
Lit le `.env` local. Idempotent : ne touche jamais aux champs d'analyse.
`compte_stats` est rempli par le trigger SQL à chaque upsert de `contenu`.

Usage :
    python shared/scripts/post/poller.py [--limit 30]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.config import IG_HANDLE, IG_USER_ID, META_ACCESS_TOKEN, status  # noqa: E402
from shared.database import get_client, insert_snapshot, upsert_contenu  # noqa: E402
from shared.scripts.post.upsert_contenu_apify import fetch_posts_apify  # noqa: E402

SNAPSHOT_KEYS = ("views", "reach", "likes", "comments", "shares", "saves",
                 "avg_watch_time", "total_watch_time")


def _comptes_own(client) -> list[dict]:
    return client.table("comptes").select("id,handle,plateforme").eq(
        "type", "own").execute().data or []


def _run_meta(client, comptes: list[dict], limit: int) -> dict:
    """Mode Meta Graph : media paginé + insights par reel (pause anti rate-limit)."""
    from shared.scripts.post.meta_graph import fetch_insights, fetch_reels, kpis_reel

    # Le token Meta ne couvre qu'UN compte : celui d'IG_USER_ID. On rattache les
    # contenus au compte own correspondant (IG_HANDLE si présent, sinon le seul own).
    compte = next((c for c in comptes if IG_HANDLE and c["handle"] == IG_HANDLE), comptes[0])
    if len(comptes) > 1 and not IG_HANDLE:
        print(f"[warn] plusieurs comptes own, IG_HANDLE absent -> {compte['handle']}",
              file=sys.stderr)

    n_contenu, n_snap, errors = 0, 0, []
    reels = fetch_reels(IG_USER_ID, META_ACCESS_TOKEN, limit=limit)
    for m in reels:
        media_id = m.get("id")
        if not media_id:
            continue
        try:
            kpis = kpis_reel(m, fetch_insights(media_id, META_ACCESS_TOKEN))
            upsert_contenu({
                "id": media_id, "compte_id": compte["id"], "plateforme": "instagram",
                "url": m.get("permalink"), "caption": m.get("caption"),
                "post_date": (m.get("timestamp") or "")[:19] or None,
                **kpis,
            })
            n_contenu += 1
            insert_snapshot(media_id, {k: kpis[k] for k in SNAPSHOT_KEYS})
            n_snap += 1
        except Exception as e:  # noqa: BLE001  (continueOnFail : un échec n'arrête pas la boucle)
            errors.append({"media_id": media_id, "error": str(e)[:200]})
        time.sleep(0.5)  # throttle insights (mirror du requestInterval n8n)

    return {"source": "meta", "comptes_own": len(comptes), "reels_vus": len(reels),
            "contenu_rafraichis": n_contenu, "snapshots": n_snap, "erreurs": errors}


def _run_apify(client, comptes: list[dict], limit: int) -> dict:
    """Mode Apify (historique) : métriques publiques views/likes/comments."""
    if status("APIFY_API_TOKEN") != "SET":
        raise EnvironmentError("Ni Meta (META_ACCESS_TOKEN+IG_USER_ID) ni APIFY_API_TOKEN "
                               "configurés dans .env — le poller n'a aucune source.")
    n_contenu, n_snap, errors = 0, 0, []
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
            except Exception as e:  # noqa: BLE001
                errors.append({"media_id": p["media_id"], "error": str(e)[:200]})

    return {"source": "apify", "comptes_own": len(comptes),
            "contenu_rafraichis": n_contenu, "snapshots": n_snap, "erreurs": errors}


def run(limit: int = 30) -> dict:
    if status("SUPABASE_ANON_KEY") != "SET":
        raise EnvironmentError("SUPABASE_ANON_KEY manquant dans .env")
    client = get_client()
    comptes = _comptes_own(client)
    if not comptes:
        return {"comptes_own": 0, "contenu_rafraichis": 0, "snapshots": 0,
                "note": "aucun compte own configuré (table comptes, type='own')", "erreurs": []}

    if status("META_ACCESS_TOKEN") == "SET" and status("IG_USER_ID") == "SET":
        return _run_meta(client, comptes, limit)
    return _run_apify(client, comptes, limit)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=30)
    args = p.parse_args()
    print(json.dumps(run(args.limit), ensure_ascii=False))


if __name__ == "__main__":
    main()
