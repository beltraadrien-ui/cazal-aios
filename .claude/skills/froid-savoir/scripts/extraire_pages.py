"""Étape 1 de l'ingestion : un document du catalogue → images de pages (cache) et, pour un PDF natif, son texte.

Sortie : bibliotheque/_cache/pages/<doc>/NNNN.jpg (largeur max 1800 px, pour l'OCR et l'affichage) + manifest.json ;
         bibliotheque/_cache/texte/<doc>/NNNN.txt pour un natif (texte extrait par PyMuPDF, gratuit).
Scan « 1 image par page » : l'image est extraite telle quelle (rapide) ; sinon la page est rendue par PyMuPDF.
Reprise : une page déjà présente dans le manifeste est sautée.
Usage : python …/extraire_pages.py --doc kotza [--pages 1-50] [--max-w 1800]
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from shared.savoir import (texte_propre, charger_catalogue, sauver_catalogue, document, chemin_document, dossier_pages,  # noqa: E402
                           dossier_texte, lire_json, ecrire_json, sortie_utf8)


def plage(spec: str, n: int) -> list[int]:
    if not spec:
        return list(range(1, n + 1))
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return [p for p in out if 1 <= p <= n]


def run(doc_id: str, pages: str = "", max_w: int = 1800) -> dict:
    import pymupdf
    from PIL import Image

    cat = charger_catalogue()
    d = document(cat, doc_id)
    pdf = chemin_document(d)
    doc = pymupdf.open(pdf)
    dest, dest_txt = dossier_pages(doc_id), dossier_texte(doc_id)
    dest.mkdir(parents=True, exist_ok=True)
    natif = d.get("nature") == "natif"
    if natif:
        dest_txt.mkdir(parents=True, exist_ok=True)
    man_path = dest / "manifest.json"
    manifest = lire_json(man_path, [])
    deja = {m["page_pdf"] for m in manifest}
    t0, faites = time.time(), 0
    for p in plage(pages, len(doc)):
        if p in deja:
            continue
        page = doc[p - 1]
        im = None
        if not natif:
            imgs = page.get_images(full=True)
            if len(imgs) == 1:
                try:
                    info = doc.extract_image(imgs[0][0])
                    im = Image.open(io.BytesIO(info["image"]))
                    im = im.convert("L") if im.mode in ("1", "L", "LA") else im.convert("RGB")
                    if im.size[0] < 800:          # image trop petite pour être la page entière → rendu
                        im = None
                except Exception:
                    im = None
        if im is None:
            zoom = max_w / page.rect.width
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        w, h = im.size
        if w > max_w:
            im = im.resize((max_w, int(h * max_w / w)), Image.LANCZOS)
        f = dest / f"{p:04d}.jpg"
        im.save(f, "JPEG", quality=80, optimize=True)
        entree = {"doc": doc_id, "page_pdf": p, "page_imprimee_attendue": p - int(d.get("decalage_page") or 0),
                  "fichier": str(f), "ko": f.stat().st_size // 1024, "px": list(im.size)}
        if natif:
            texte = texte_propre(page.get_text("text") or "")
            (dest_txt / f"{p:04d}.txt").write_text(texte, encoding="utf-8")
            entree["caracteres"] = len(texte.strip())
        manifest.append(entree)
        faites += 1
    manifest.sort(key=lambda m: m["page_pdf"])
    ecrire_json(man_path, manifest)
    d.setdefault("etat", {})["pages"] = f"{len(manifest)}/{len(doc)}"
    sauver_catalogue(cat)
    tot = sum(m["ko"] for m in manifest)
    res = {"doc": doc_id, "pages": len(manifest), "nouvelles": faites, "mo": round(tot / 1024, 1), "secondes": round(time.time() - t0, 1)}
    print(f"{doc_id}: {len(manifest)}/{len(doc)} pages dans le cache (+{faites}), {res['mo']} Mo, {res['secondes']}s"
          + (f" · texte natif extrait" if natif else ""), flush=True)
    return res


def main() -> None:
    sortie_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--pages", default="")
    ap.add_argument("--max-w", type=int, default=1800)
    a = ap.parse_args()
    run(a.doc, a.pages, a.max_w)


if __name__ == "__main__":
    main()
