"""Lit la vue contenu_avec_scores (KPIs + outlier + engagement) depuis Supabase.

Utilisé par les skills rapport-performance (type=own) et rapport-concurrents
(type=concurrent). Sortie JSON sur stdout.

Usage :
    python shared/scripts/search/list_contenu_scores.py [--type own|concurrent] [--limit 200]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.database import get_contenu_scores  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=["own", "concurrent"], default=None)
    p.add_argument("--plateforme", default=None)
    p.add_argument("--limit", type=int, default=200)
    args = p.parse_args()

    rows = get_contenu_scores(type_=args.type, plateforme=args.plateforme, limit=args.limit)
    # Champs utiles pour l'analyse (allège la sortie)
    keep = (
        "id", "compte_id", "plateforme", "url", "thumbnail_url", "caption", "post_date",
        "views", "reach", "plays", "replays", "likes", "comments", "shares", "saves",
        "avg_watch_time", "duration",
        "spoken_hook", "hook_structure", "hook_framework", "text_hook", "visual_hook",
        "visual_format", "topic", "topic_summary", "content_structure", "content_type",
        "call_to_action",
        "calc_outlier_score", "calc_outlier_category", "calc_engagement_rate",
    )
    out = [{k: r.get(k) for k in keep} for r in rows]
    print(json.dumps({"count": len(out), "rows": out}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
