"""Client Supabase + wrappers CRUD — calqué sur Master-content/shared/database.py.

Client singleton (supabase-py) authentifié avec l'anon key. Toutes les fonctions
lèvent une Exception en cas d'échec (jamais sys.exit). Tables Cazal :
comptes, contenu, contenu_snapshots, compte_stats, idees + vue contenu_avec_scores.
"""
from __future__ import annotations

from datetime import date

from shared.config import SUPABASE_ANON_KEY, SUPABASE_PROJECT_URL

_client = None


def get_client():
    """Retourne le client Supabase singleton (créé à la 1ʳᵉ utilisation)."""
    global _client
    if _client is None:
        from supabase import create_client
        if not SUPABASE_PROJECT_URL or not SUPABASE_ANON_KEY:
            raise EnvironmentError(
                "SUPABASE_PROJECT_URL ou SUPABASE_ANON_KEY manquant dans .env"
            )
        _client = create_client(SUPABASE_PROJECT_URL, SUPABASE_ANON_KEY)
    return _client


# ----------------------------- COMPTES -----------------------------

def upsert_compte(handle: str, plateforme: str = "instagram",
                  type_: str = "concurrent", nom: str | None = None,
                  url: str | None = None) -> str:
    """Crée/retrouve un compte (unique handle+plateforme). Retourne son id (uuid)."""
    if not handle:
        raise ValueError("handle manquant")
    client = get_client()
    row = {"handle": handle, "plateforme": plateforme, "type": type_}
    if nom:
        row["nom"] = nom
    if url:
        row["url"] = url
    res = client.table("comptes").upsert(row, on_conflict="handle,plateforme").execute()
    if not res.data:
        # upsert sans retour → relire
        got = client.table("comptes").select("id").eq("handle", handle).eq(
            "plateforme", plateforme).limit(1).execute()
        if not got.data:
            raise Exception(f"upsert_compte échec pour {handle}")
        return got.data[0]["id"]
    return res.data[0]["id"]


# ----------------------------- CONTENU -----------------------------

def upsert_contenu(row: dict) -> str:
    """UPSERT un contenu (on_conflict id). N'écrase PAS les champs d'analyse non fournis.
    Retourne l'id."""
    if not row.get("id"):
        raise ValueError("row.id manquant")
    client = get_client()
    res = client.table("contenu").upsert(row, on_conflict="id").execute()
    if not res.data:
        raise Exception(f"upsert_contenu échec pour {row['id']}")
    return res.data[0]["id"]


def update_contenu_fields(contenu_id: str, fields: dict) -> dict:
    """PATCH partiel d'un contenu (ex. champs d'analyse IA). Retourne la ligne."""
    if not contenu_id or not fields:
        raise ValueError("contenu_id ou fields vide")
    client = get_client()
    res = client.table("contenu").update(fields).eq("id", contenu_id).execute()
    if not res.data:
        raise Exception(f"update_contenu_fields échec pour {contenu_id}")
    return res.data[0]


def get_contenu_scores(type_: str | None = None, plateforme: str | None = None,
                       limit: int = 200) -> list[dict]:
    """Lit la vue contenu_avec_scores (jointe au compte pour filtrer own/concurrent)."""
    client = get_client()
    q = client.table("contenu_avec_scores").select("*").order(
        "views", desc=True).limit(limit)
    if plateforme:
        q = q.eq("plateforme", plateforme)
    rows = (q.execute().data) or []
    if type_:
        # filtrer par type de compte (own/concurrent) via la table comptes
        ids = {c["id"] for c in client.table("comptes").select("id").eq(
            "type", type_).execute().data or []}
        rows = [r for r in rows if r.get("compte_id") in ids]
    return rows


def get_contenu_a_analyser(limit: int = 20) -> list[dict]:
    """Contenus pas encore analysés (is_analyzed=false)."""
    client = get_client()
    res = client.table("contenu").select(
        "id, url, caption, transcript, plateforme").eq(
        "is_analyzed", False).limit(limit).execute()
    return res.data or []


# ------------------------- SNAPSHOTS / STATS -------------------------

def insert_snapshot(contenu_id: str, metrics: dict,
                    snapshot_date: str | None = None) -> str:
    """Écrit un snapshot du jour (id = <contenu_id>_<date>, upsert idempotent)."""
    d = snapshot_date or date.today().isoformat()
    snap_id = f"{contenu_id}_{d}"
    row = {"id": snap_id, "contenu_id": contenu_id, "snapshot_date": d}
    for k in ("views", "reach", "likes", "comments", "shares", "saves",
              "avg_watch_time", "total_watch_time"):
        if k in metrics and metrics[k] is not None:
            row[k] = metrics[k]
    client = get_client()
    client.table("contenu_snapshots").upsert(row, on_conflict="id").execute()
    return snap_id


# ------------------------------ IDEES ------------------------------

def insert_idee(idee: dict) -> str:
    """Insère une idée dans le pipeline. Retourne l'id."""
    if not idee.get("sujet"):
        raise ValueError("idee.sujet manquant")
    client = get_client()
    res = client.table("idees").insert(idee).execute()
    if not res.data:
        raise Exception("insert_idee échec")
    return res.data[0]["id"]


def list_idees(statut: str | None = "idée", limit: int = 50) -> list[dict]:
    """Liste les idées (par défaut au statut 'idée')."""
    client = get_client()
    q = client.table("idees").select("*").order("created_at", desc=True).limit(limit)
    if statut:
        q = q.eq("statut", statut)
    return q.execute().data or []


def update_idee_statut(idee_id: str, statut: str) -> dict:
    """Met à jour le statut d'une idée (idée/choisie/produite/publiée)."""
    client = get_client()
    res = client.table("idees").update({"statut": statut}).eq("id", idee_id).execute()
    if not res.data:
        raise Exception(f"update_idee_statut échec pour {idee_id}")
    return res.data[0]


if __name__ == "__main__":
    # Smoke test : compter les lignes de chaque table (vérifie la connexion).
    c = get_client()
    for t in ("comptes", "contenu", "contenu_snapshots", "compte_stats", "idees"):
        n = len(c.table(t).select("id").limit(1).execute().data or [])
        print(f"{t}: OK (échantillon {n})")
