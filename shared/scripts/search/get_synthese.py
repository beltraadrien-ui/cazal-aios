"""Lit la synthèse la plus récente d'un type dans la table Supabase `syntheses`.

Utilisé par les skills moteur (ex. `veille-niche`) et pour vérifier ce que les skills de
surface liront via le connecteur MCP. Sortie JSON sur stdout.

Usage :
    python shared/scripts/search/get_synthese.py --type digest-perf
    python shared/scripts/search/get_synthese.py --type rapport-concurrents --meta-only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.database import get_derniere_synthese  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--type", default="digest-perf")
    p.add_argument("--meta-only", action="store_true",
                   help="sans le contenu (juste type/titre/run_date/source)")
    args = p.parse_args()

    row = get_derniere_synthese(args.type)
    if row is None:
        print(json.dumps({"found": False, "type": args.type}, ensure_ascii=False))
        return
    if args.meta_only:
        row = {k: v for k, v in row.items() if k != "contenu"}
    print(json.dumps({"found": True, **row}, ensure_ascii=False))


if __name__ == "__main__":
    main()
