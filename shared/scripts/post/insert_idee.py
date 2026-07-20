"""Insère une ou plusieurs idées dans la table Supabase `idees`.

Utilisé par la veille (mode batch, ex. poller/automatisation) et utilitaire CLI.
Accepte un JSON (objet ou liste) sur --json ou stdin.

Usage :
    python shared/scripts/post/insert_idee.py --json '{"sujet":"...","archetype":"...","format":"reel"}'
    echo '[{...},{...}]' | python shared/scripts/post/insert_idee.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.database import insert_idee  # noqa: E402

ALLOWED = {"sujet", "archetype", "angle", "cadrage", "format", "statut",
           "pourquoi", "origine", "compte_id", "notes", "source_url"}


def _clean(d: dict) -> dict:
    row = {k: v for k, v in d.items() if k in ALLOWED and v is not None}
    row.setdefault("statut", "idée")
    row.setdefault("origine", "veille")
    return row


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--json", default=None, help="objet ou liste JSON ; sinon lu sur stdin")
    args = p.parse_args()

    raw = args.json if args.json else sys.stdin.read()
    data = json.loads(raw)
    items = data if isinstance(data, list) else [data]

    ids = []
    for it in items:
        ids.append(insert_idee(_clean(it)))
    print(json.dumps({"inserted": len(ids), "ids": ids}, ensure_ascii=False))


if __name__ == "__main__":
    main()
