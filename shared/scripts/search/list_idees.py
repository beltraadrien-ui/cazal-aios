"""Lit les idées de la table Supabase `idees`. Sortie JSON sur stdout.

Utilisé par `veille-niche` pour : (1) la dédup (lire toutes les idées existantes avant
d'en proposer de nouvelles), (2) régénérer le snapshot markdown `references/base-idees.md`.
Calqué sur search/list_contenu_scores.py.

Usage :
    python shared/scripts/search/list_idees.py [--statut idée|choisie|produite|publiée|all] [--limit 200]

`--statut all` → lit TOUS les statuts (None passé à list_idees) ; utile pour la dédup
(ne pas re-proposer une idée déjà choisie/produite/publiée).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.database import list_idees  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--statut", default="idée",
                   help="filtre de statut ; 'all' pour tous (défaut: idée)")
    p.add_argument("--limit", type=int, default=200)
    args = p.parse_args()

    statut = None if args.statut == "all" else args.statut
    rows = list_idees(statut=statut, limit=args.limit)
    print(json.dumps({"count": len(rows), "rows": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
