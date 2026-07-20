"""Copie les données de la base Supabase SOURCE (Adrien) vers la base CIBLE (Loïc).

Migration one-shot « copie de lignes » (decisions/log.md 2026-07-20) : préserve les
ids, les dates et toutes les analyses IA déjà payées (Whisper/GPT). Les uuid sont
copiés tels quels → les liens entre tables (compte_id, contenu_id) restent valides.
Idempotent : chaque table est copiée en UPSERT, le script est rejouable sans doublon.

Prérequis (le schéma doit déjà exister sur la cible : shared/sql/schema.sql) :
- .env : SUPABASE_PROJECT_URL / SUPABASE_ANON_KEY (source, déjà en place)
         + CIBLE_SUPABASE_URL / CIBLE_SUPABASE_ANON_KEY (la nouvelle base de Loïc).

Usage :
    python shared/scripts/post/migrer_donnees.py          # dry-run : états + comptages
    python shared/scripts/post/migrer_donnees.py --go     # copie réelle
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import shared.config  # noqa: E402,F401 — charge le .env
from shared.database import get_client  # noqa: E402

# Ordre de copie = ordre des dépendances (comptes d'abord, car contenu/idees y pointent).
# (table, clé on_conflict, colonnes à retirer avant upsert)
ORDRE: list[tuple[str, str, set[str]]] = [
    ("comptes", "id", set()),
    ("contenu", "id", set()),
    ("contenu_snapshots", "id", set()),
    # compte_stats : le trigger de la cible crée déjà des lignes (compte_id, aujourd'hui)
    # pendant la copie de `contenu` → conflit sur la contrainte unique, pas sur l'id.
    ("compte_stats", "compte_id,snapshot_date", {"id"}),
    ("idees", "id", set()),
    ("syntheses", "type,run_date", {"id"}),
]

PAGE = 1000
CHUNK = 200


def _client_cible():
    url = os.environ.get("CIBLE_SUPABASE_URL", "")
    key = os.environ.get("CIBLE_SUPABASE_ANON_KEY", "")
    if (not url or url.startswith("REPLACE_WITH_")
            or not key or key.startswith("REPLACE_WITH_")):
        raise EnvironmentError(
            "CIBLE_SUPABASE_URL / CIBLE_SUPABASE_ANON_KEY manquants dans .env "
            "(remplacer les placeholders par les valeurs du projet Supabase de Loïc)"
        )
    if url.rstrip("/") == os.environ.get("SUPABASE_PROJECT_URL", "").rstrip("/"):
        raise EnvironmentError("CIBLE_SUPABASE_URL identique à la source — refus de copier sur soi-même")
    from supabase import create_client
    return create_client(url, key)


def _compter(client, table: str) -> int:
    res = client.table(table).select("id", count="exact").limit(1).execute()
    return res.count or 0


def _lire_tout(client, table: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        batch = (client.table(table).select("*").order("created_at", desc=False)
                 .range(offset, offset + PAGE - 1).execute().data) or []
        rows.extend(batch)
        if len(batch) < PAGE:
            return rows
        offset += PAGE


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--go", action="store_true", help="exécute la copie (sinon dry-run)")
    args = p.parse_args()

    source = get_client()

    if not args.go:
        # Dry-run : comptages source + état de la cible, aucune écriture.
        etat = {"mode": "dry-run", "source": {}, "cible": None}
        for table, _, _ in ORDRE:
            etat["source"][table] = _compter(source, table)
        try:
            cible = _client_cible()
            etat["cible"] = {t: _compter(cible, t) for t, _, _ in ORDRE}
        except EnvironmentError as e:
            etat["cible"] = f"NON PRÊTE — {e}"
        print(json.dumps(etat, ensure_ascii=False, indent=2))
        return

    cible = _client_cible()
    resultat: dict[str, int] = {}
    for table, on_conflict, a_retirer in ORDRE:
        rows = _lire_tout(source, table)
        print(f"{table}: {len(rows)} lignes lues…", file=sys.stderr)
        if a_retirer:
            rows = [{k: v for k, v in r.items() if k not in a_retirer} for r in rows]
        for i in range(0, len(rows), CHUNK):
            cible.table(table).upsert(rows[i:i + CHUNK], on_conflict=on_conflict).execute()
        resultat[table] = len(rows)
    print(json.dumps({"mode": "copie", "copie": resultat}, ensure_ascii=False))


if __name__ == "__main__":
    main()
