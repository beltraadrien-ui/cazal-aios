"""Carnet de leçons : noter une correction ou une règle apprise de Loïc (dimensionnement/carnet/lecons.md, local).

Usage : python …/lecon.py "Sur une centrale au R449A, compter 10 % de marge sur la puissance existante" [--dossier 2026-09-14-boucherie-test] [--theme dimensionnement]
        python …/lecon.py --lister
Chaque leçon est datée ; le carnet est relu au début de chaque dossier (étapes 1 à 3) et consolidé dans savoir/ par Adrien.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from shared.savoir import CARNET, sortie_utf8  # noqa: E402

ENTETE = """# Carnet de leçons — ce que Loïc a corrigé ou appris au système

> Local, jamais versionné. Une ligne par leçon, datée. Relu par les skills au début de chaque dossier.
> Adrien fait passer les leçons stables dans `dimensionnement/savoir/` (socle versionné) à chaque maintenance.

| Date | Dossier | Thème | Leçon |
|---|---|---|---|
"""


def main() -> None:
    sortie_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("texte", nargs="?")
    ap.add_argument("--dossier", default="—")
    ap.add_argument("--theme", default="général")
    ap.add_argument("--lister", action="store_true")
    a = ap.parse_args()
    if a.lister or not a.texte:
        print(CARNET.read_text(encoding="utf-8") if CARNET.exists() else "Carnet vide.")
        return
    CARNET.parent.mkdir(parents=True, exist_ok=True)
    if not CARNET.exists():
        CARNET.write_text(ENTETE, encoding="utf-8")
    texte = a.texte.replace("|", "/").replace("\n", " ").strip()
    with CARNET.open("a", encoding="utf-8") as f:
        f.write(f"| {time.strftime('%Y-%m-%d')} | {a.dossier} | {a.theme} | {texte} |\n")
    print(f"leçon notée dans {CARNET}")


if __name__ == "__main__":
    main()
