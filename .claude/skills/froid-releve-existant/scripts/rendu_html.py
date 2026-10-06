"""Vue lisible d'un dossier d'installation : les fichiers markdown du dossier (mémoire de Claude) → pages HTML
pour l'humain, avec la photo de chaque plaque affichée à côté de sa lecture.

Usage : python .claude/skills/froid-releve-existant/scripts/rendu_html.py <dossier> [--ouvrir]
        python … rendu_html.py dimensionnement/dossiers/<slug> --ouvrir
Entrée : dossier.md, 1-existant.md, 2-dimensionnement.md (ceux qui existent), ou un seul fichier .md du dossier.
Sortie : le même nom en .html à côté (ex. 1-existant.html), chemins d'images relatifs → le dossier reste déplaçable.
Mince adaptateur : le rendu est fait par le module partagé `shared/rendu_html.py` (fonction `convertir`).
Dépendance : markdown (pur Python, dans requirements.txt).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from shared.rendu_html import DOCUMENTS_DOSSIER, convertir, ouvrir_page  # noqa: E402
from shared.savoir import sortie_utf8  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossier", help="dossier d'installation (ou un fichier .md du dossier)")
    ap.add_argument("--ouvrir", action="store_true", help="ouvrir 1-existant.html (ou le premier rendu) dans le navigateur")
    a = ap.parse_args()
    cible = Path(a.dossier)
    dossier = cible.parent if cible.is_file() else cible
    fichiers = [cible] if cible.is_file() else [dossier / f for f in DOCUMENTS_DOSSIER if (dossier / f).exists()]
    if not fichiers:
        raise SystemExit(f"Aucun fichier markdown à rendre dans {dossier}")
    sorties = [convertir(f, racine=dossier) for f in fichiers]
    for s in sorties:
        print(f"Rendu : {s}")
    if a.ouvrir:
        principal = next((s for s in sorties if s.name == "1-existant.html"), sorties[0])
        ouvrir_page(principal)


if __name__ == "__main__":
    sortie_utf8()
    main()
