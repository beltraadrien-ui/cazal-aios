"""Pousse une synthèse (digest de perf ou rapport daté) dans la table Supabase `syntheses`.

Utilisé en fin de run par `rapport-performance` / `rapport-concurrents` (le fichier markdown
reste la source rédigée ; ici on le publie tel quel en base pour lecture live via le
connecteur MCP). Upsert idempotent sur (type, run_date).

Usage :
    python shared/scripts/post/upsert_synthese.py --type digest-perf --file references/rapport-perf-digest.md
    python shared/scripts/post/upsert_synthese.py --type rapport-performance --run-date 2026-06-24 \
        --source rapport-performance --file active/analyse/rapport-performance-2026-06-24.md
    echo '<markdown>' | python shared/scripts/post/upsert_synthese.py --type digest-perf
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.database import upsert_synthese  # noqa: E402

TYPES = ("digest-perf", "rapport-performance", "rapport-concurrents")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--type", required=True, choices=TYPES)
    p.add_argument("--run-date", default=date.today().isoformat(),
                   help="date du run (AAAA-MM-JJ, défaut : aujourd'hui)")
    p.add_argument("--titre", default=None)
    p.add_argument("--source", default=None, help="skill producteur")
    p.add_argument("--file", default=None,
                   help="fichier markdown à pousser ; sinon contenu lu sur stdin")
    args = p.parse_args()

    if args.file:
        path = Path(args.file)
        if not path.exists():
            sys.exit(f"fichier introuvable : {path}")
        contenu = path.read_text(encoding="utf-8")
    else:
        contenu = sys.stdin.read()
    if not contenu.strip():
        sys.exit("contenu vide — rien à pousser")

    row = {"type": args.type, "contenu": contenu, "run_date": args.run_date}
    if args.titre:
        row["titre"] = args.titre
    if args.source:
        row["source"] = args.source

    sid = upsert_synthese(row)
    print(json.dumps({"upserted": 1, "id": sid, "type": args.type,
                      "run_date": args.run_date, "chars": len(contenu)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
