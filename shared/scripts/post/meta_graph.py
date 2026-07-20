"""Client Meta Graph API (Instagram own-account) — port Python du workflow n8n
`ig-daily-poller.json` de Master-content (lessons/1.6-instagram-poller).

Utilisé par `poller.py` en mode Meta (quand META_ACCESS_TOKEN + IG_USER_ID sont SET).
Stdlib uniquement (urllib), aucune dépendance nouvelle.

Endpoints (v21.0, mêmes que le workflow n8n) :
  GET /{IG_USER_ID}/media    → liste paginée (likes/comments inclus), filtre REELS
  GET /{media_id}/insights   → reach, saved, shares, total_interactions,
                               ig_reels_avg_watch_time, ig_reels_video_view_total_time, views

Conversions : watch times Meta = MILLISECONDES → stockés en SECONDES (avg ET total —
corrige l'incohérence du workflow n8n qui ne convertissait que avg). `saved` (API)
→ colonne `saves`.

⚠️ Meta Graph ne marche que sur le compte DONT ON EST PROPRIÉTAIRE (token). Les
concurrents restent scrapés via Apify. Token longue durée ≈ 60 j, renouvellement
manuel : cf. MIGRATION-SUPABASE.md § JOUR J bloc C-bis.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com/v21.0"
MEDIA_FIELDS = ("id,caption,media_type,media_product_type,timestamp,permalink,"
                "like_count,comments_count")
INSIGHT_METRICS = ("reach,saved,shares,total_interactions,"
                   "ig_reels_avg_watch_time,ig_reels_video_view_total_time,views")
MAX_PAGES = 10
PAGE_SLEEP_S = 0.5


def _get_json(url: str) -> dict:
    """GET JSON avec message d'erreur exploitable (token expiré → explicite)."""
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
            err = json.loads(body).get("error", {})
            if err.get("code") == 190:  # OAuthException : token invalide/expiré
                raise EnvironmentError(
                    "META_ACCESS_TOKEN expiré ou invalide (OAuthException 190). "
                    "Régénérer un token longue durée sur developers.facebook.com "
                    "puis remplacer la valeur dans .env (durée ≈ 60 jours)."
                ) from None
        except (json.JSONDecodeError, KeyError):
            pass
        raise Exception(f"Meta Graph HTTP {e.code} : {body[:300]}") from None


def fetch_reels(ig_user_id: str, token: str, limit: int = 100) -> list[dict]:
    """Liste les reels du compte (media_product_type == REELS), paginé façon n8n
    (suit paging.next, max MAX_PAGES pages, pause anti rate-limit)."""
    url = (f"{GRAPH}/{ig_user_id}/media?fields={MEDIA_FIELDS}"
           f"&limit=100&access_token={urllib.parse.quote(token)}")
    reels: list[dict] = []
    for _ in range(MAX_PAGES):
        data = _get_json(url)
        for item in data.get("data", []):
            if item.get("media_product_type") == "REELS":
                reels.append(item)
                if len(reels) >= limit:
                    return reels
        url = (data.get("paging") or {}).get("next")
        if not url:
            break
        time.sleep(PAGE_SLEEP_S)
    return reels


def fetch_insights(media_id: str, token: str) -> dict:
    """Insights d'un reel → {nom_metrique: valeur} (0 si absente)."""
    url = (f"{GRAPH}/{media_id}/insights?metric={INSIGHT_METRICS}"
           f"&access_token={urllib.parse.quote(token)}")
    data = _get_json(url)
    out = {}
    for m in data.get("data", []):
        values = m.get("values") or [{}]
        out[m.get("name")] = values[0].get("value", 0) or 0
    return out


def kpis_reel(media: dict, insights: dict) -> dict:
    """Mappe media + insights → colonnes Supabase (watch times ms → s)."""
    return {
        "views": int(insights.get("views", 0)),
        "reach": int(insights.get("reach", 0)),
        "likes": int(media.get("like_count", 0) or 0),
        "comments": int(media.get("comments_count", 0) or 0),
        "shares": int(insights.get("shares", 0)),
        "saves": int(insights.get("saved", 0)),
        "total_interactions": int(insights.get("total_interactions", 0)),
        "avg_watch_time": round(insights.get("ig_reels_avg_watch_time", 0) / 1000, 1),
        "total_watch_time": round(insights.get("ig_reels_video_view_total_time", 0) / 1000),
    }
