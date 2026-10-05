"""Catalogue des documents de la bibliothèque (dimensionnement/bibliotheque/catalogue.json, local).

Usage :
  python …/catalogue.py --lister
  python …/catalogue.py --ajouter "03-regulation-danfoss/AKCC 55.pdf" --id danfoss-ak-cc-55 --titre "Danfoss AK-CC 55 — notice" \
                        --type notice --marque Danfoss [--langue fr] [--decalage 0] [--sommaire 3-12] [--priorite 2] [--notes "…"]
  python …/catalogue.py --retirer <id>
Le chemin est relatif à dimensionnement/bibliotheque/. La nature (scan / natif) et le nombre de pages sont détectés.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from shared.savoir import BIBLIO, charger_catalogue, sauver_catalogue, chemin_document, slugifier, sortie_utf8  # noqa: E402


def detecter(pdf: Path) -> tuple[str, int]:
    """nature ('scan' si la quasi-totalité des pages n'a pas de texte extractible) et nombre de pages."""
    import pymupdf
    d = pymupdf.open(pdf)
    n = len(d)
    echantillon = list(range(0, n, max(1, n // 25)))[:25]
    sans_texte = sum(1 for i in echantillon if len((d[i].get_text() or "").strip()) < 40)
    return ("scan" if sans_texte >= 0.8 * len(echantillon) else "natif"), n


def ajouter(a) -> dict:
    cat = charger_catalogue()
    fichier = a.ajouter
    pdf = BIBLIO / fichier
    if not pdf.exists():
        raise SystemExit(f"Fichier introuvable : {pdf}")
    doc_id = a.id or slugifier(pdf.stem)
    nature, pages = detecter(pdf)
    sommaire = None
    if a.sommaire:
        deb, fin = a.sommaire.split("-")
        sommaire = [int(deb), int(fin)]
    d = {"id": doc_id, "titre": a.titre or pdf.stem, "fichier": fichier.replace("\\", "/"), "type": a.type or "autre",
         "marque": a.marque, "langue": a.langue, "nature": a.nature or nature, "pages_total": pages,
         "decalage_page": a.decalage, "sommaire_pages": sommaire, "priorite": a.priorite, "notes": a.notes,
         "etat": {}}
    cat["documents"] = [x for x in cat["documents"] if x["id"] != doc_id] + [d]
    cat["documents"].sort(key=lambda x: (x.get("priorite", 9), x["id"]))
    sauver_catalogue(cat)
    return d


def main() -> None:
    sortie_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lister", action="store_true")
    ap.add_argument("--ajouter", metavar="FICHIER")
    ap.add_argument("--retirer", metavar="ID")
    ap.add_argument("--id")
    ap.add_argument("--titre")
    ap.add_argument("--type", help="livre | formation | notice | fiche-fournisseur | abaque | guide | autre")
    ap.add_argument("--marque")
    ap.add_argument("--langue", default="fr")
    ap.add_argument("--nature", choices=["scan", "natif"], help="forcer (sinon détecté)")
    ap.add_argument("--decalage", type=int, default=0, help="page imprimée = page PDF - décalage (repli)")
    ap.add_argument("--sommaire", help="pages PDF du sommaire, ex. 3-12 (scan : structuré par OpenAI)")
    ap.add_argument("--priorite", type=int, default=5, help="1 = à ingérer en premier")
    ap.add_argument("--notes")
    a = ap.parse_args()
    if a.ajouter:
        d = ajouter(a)
        print(f"ajouté : {d['id']} · {d['titre']} · {d['nature']} · {d['pages_total']} p. · priorité {d['priorite']}")
    elif a.retirer:
        cat = charger_catalogue()
        cat["documents"] = [x for x in cat["documents"] if x["id"] != a.retirer]
        sauver_catalogue(cat)
        print("retiré du catalogue (les fichiers et la base ne sont pas touchés) :", a.retirer)
    else:
        cat = charger_catalogue()
        print(f"{len(cat['documents'])} document(s) dans {BIBLIO / 'catalogue.json'}")
        for d in cat["documents"]:
            e = d.get("etat", {})
            print(f"  [{d.get('priorite', 9)}] {d['id']:40s} {d['nature'] or '?':5s} {d['pages_total'] or 0:5d} p. · {d['titre'][:50]:50s} "
                  f"· pages {e.get('pages', '-')} · ocr {e.get('ocr', '-')} · base {e.get('charge', '-')}")


if __name__ == "__main__":
    main()
