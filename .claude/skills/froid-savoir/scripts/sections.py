"""Étape 3 de l'ingestion : les sections d'un document (le « sommaire »), en pages imprimées.

Quatre cas, dans l'ordre :
  1. scan dont les pages portent des titres courants (# et ## lus par l'OCR sur ≥ 40 % des pages) → sections exactes
     page par page, niveau 1 = titre #, niveau 2 = sous-titre ## (gratuit) ;
  2. le catalogue indique des pages de sommaire (scan) → le texte OCR de ces pages est structuré par OpenAI (un appel) ;
  3. le PDF a des signets (outline) → sections prises telles quelles (gratuit) ;
  4. sinon → une section par page, titrée par le premier titre de la page (gratuit).
Sortie : bibliotheque/_cache/sections/<doc>.json = [{"titre", "niveau", "page_debut", "page_fin"}]
Usage : python …/sections.py --doc kotza [--model gpt-5.4-mini] [--forcer]
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from shared.savoir import (texte_propre, MODELE_OCR, charger_catalogue, document, chemin_document, dossier_pages, dossier_ocr,  # noqa: E402
                           dossier_texte, fichier_sections, lire_json, ecrire_json, cout_usd, depenses_ajouter,
                           openai_client, sortie_utf8)

PROMPT = """Voici le texte OCR (avec erreurs possibles) des pages de SOMMAIRE du document « {titre} ».
Transforme-le en une liste ordonnée de sections avec leur page imprimée de début.
Règles : niveau 1 = grand thème ou chapitre ; niveau 2 = sous-entrée (exercice, quiz, paragraphe) avec le thème rappelé
avant un tiret (ex. « Panne du manque de charge — Analyse des symptômes ») ; page_debut = numéro de page imprimé lu
(entier) ; conserve l'ordre du livre ; corrige les fautes d'OCR évidentes ; ignore les mentions décoratives.
TEXTE :
<<<
{texte}
>>>
"""
SCHEMA = {"type": "object", "properties": {"sections": {"type": "array", "items": {
    "type": "object", "properties": {"titre": {"type": "string"}, "niveau": {"type": "integer"}, "page_debut": {"type": "integer"}},
    "required": ["titre", "niveau", "page_debut"], "additionalProperties": False}}},
    "required": ["sections"], "additionalProperties": False}


def fins(secs: list[dict]) -> list[dict]:
    for i, s in enumerate(secs):
        fin = None
        for n in secs[i + 1:]:
            if n["niveau"] <= s["niveau"]:
                fin = n["page_debut"] - 1 if n["page_debut"] > s["page_debut"] else s["page_debut"]
                break
        s["page_fin"] = fin
    return secs


ACRONYME = re.compile(r"^(?=.*[A-Z])(?:[A-Z]{1,3}|[A-Z0-9/]*\d[A-Z0-9/]*|VRV|DRV|PAC|CTA|HFC|HFO|GWP|EER|COP|MOP|TXV|EEV|AKV)$")
PETITS_MOTS = {"DE", "DU", "DES", "LA", "LE", "LES", "EN", "ET", "OU", "UN", "UNE", "A", "AU", "AUX", "SUR", "PAR", "POUR", "SANS", "DANS", "THE", "OF", "SI", "NE", "SE", "CE"}


def sentence_case(t: str) -> str:
    """Un titre tout en capitales devient une phrase, en gardant les sigles (HP, V4V, R407C)."""
    lettres = [c for c in t if c.isalpha()]
    if not lettres or sum(c.isupper() for c in lettres) < 0.8 * len(lettres):
        return t
    mots = t.split()
    out = []
    for i, w in enumerate(mots):
        noyau = w.strip("(),.:;!?«»\"'")
        if ACRONYME.match(noyau) and noyau not in PETITS_MOTS:
            out.append(w)
        else:
            out.append(w.capitalize() if i == 0 else w.lower())
    return " ".join(out)


def nettoyer_titre(t: str) -> str:
    t = re.sub(r"[*_`]+", "", t).strip(" #:-–—")
    t = re.sub(r"\s+", " ", t)
    return sentence_case(t)[:160]


NUMERO_SOUS_TITRE = re.compile(r"^\d{1,2}\.\d{1,2}\b")   # « 40.14 Autres méthodes… » : sous-titre, même lu en #
TITRES_IGNORES = {"solution", "solutions", "exercice", "exercices", "notespersonnelles", "notes", "sommaire",
                  "tabledesmatieres", "index", "resume", "conclusion"}


def normaliser(t: str | None) -> str:
    t = unicodedata.normalize("NFKD", t or "")
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in t if not unicodedata.combining(c)).lower())


def pages_imprimees_fiables(pages: list[tuple[int, int | None]], decalage: int) -> list[int]:
    """Numéro imprimé de chaque page PDF : le numéro lu par l'OCR, sauf s'il s'écarte de plus de 5 du décalage
    local (médiane des écarts PDF − lu sur ±10 pages) : un numéro de figure pris pour un numéro de page ne doit
    pas étirer une section sur mille pages."""
    offs = {p: p - pl for p, pl in pages if pl is not None}
    out = []
    for p, pl in pages:
        w = [offs[q] for q in range(p - 10, p + 11) if q in offs and q != p]
        off = statistics.median(w) if len(w) >= 3 else decalage
        attendu = int(round(p - off))
        out.append(pl if pl is not None and abs(pl - attendu) <= 5 else attendu)
    return out


def sections_par_titres_courants(doc_id: str, manifest: list[dict], decalage: int, titre_doc: str = "") -> list[dict]:
    """Scan avec titres courants : niveau 1 = premier « # » de la page, niveau 2 = premier « ## » ; les pages
    sans titre prolongent la section en cours. Rend [] si moins de 40 % des pages portent un « # »."""
    brut = []
    for m in manifest:
        j = lire_json(dossier_ocr(doc_id) / f"{m['page_pdf']:04d}.json")
        if not j:
            continue
        md = j.get("markdown") or ""
        h1 = re.search(r"^#\s+(.+)$", md, re.M)
        h2 = re.search(r"^##\s+(.+)$", md, re.M)
        brut.append((m["page_pdf"], j.get("page_lue"), h1.group(1).strip() if h1 else None, h2.group(1).strip() if h2 else None))
    if not brut or sum(1 for _, _, h1, _ in brut if h1) < 0.4 * len(brut):
        return []
    nums = pages_imprimees_fiables([(p, pl) for p, pl, _, _ in brut], decalage)
    n_titre = normaliser(titre_doc)
    pages = []
    for (_, _, h1, h2), pi in zip(brut, nums):
        n1 = normaliser(h1)
        # titre courant du livre lui-même (pages de gauche) ou rubrique récurrente : pas une section
        if h1 and (n1 in TITRES_IGNORES or (len(n1) >= 6 and n1 in n_titre)):
            h1 = None
        if h1 and NUMERO_SOUS_TITRE.match(h1):   # « 40.14 … » lu en # : c'est un sous-titre
            h2, h1 = h1, None
        if h2 and normaliser(h2) in TITRES_IGNORES:
            h2 = None
        pages.append((pi, h1, h2))
    secs, cur1, cur2 = [], None, None
    for pi, h1, h2 in pages:
        if h1 and normaliser(h1) != normaliser(cur1["brut"] if cur1 else None):
            if cur2: cur2["page_fin"] = max(cur2["page_fin"], pi - 1); cur2 = None
            if cur1: cur1["page_fin"] = max(cur1["page_fin"], pi - 1)
            cur1 = {"titre": nettoyer_titre(h1), "brut": h1, "niveau": 1, "page_debut": pi, "page_fin": pi}
            secs.append(cur1)
        if h2 and not cur1:   # sous-titre avant tout chapitre : il ouvre la première section
            cur1 = {"titre": nettoyer_titre(h2), "brut": h2, "niveau": 1, "page_debut": pi, "page_fin": pi}
            secs.append(cur1)
            h2 = None
        if h2 and cur1 and normaliser(h2) != normaliser(cur2["brut"] if cur2 else None):
            if cur2: cur2["page_fin"] = max(cur2["page_fin"], pi - 1)
            cur2 = {"titre": f"{cur1['titre']} — {nettoyer_titre(h2)}", "brut": h2, "niveau": 2, "page_debut": pi, "page_fin": pi}
            secs.append(cur2)
        for c in (cur1, cur2):
            if c: c["page_fin"] = max(c["page_fin"], pi)
    for s_ in secs:
        s_.pop("brut", None)
    return secs


def titre_de_page(doc_id: str, m: dict) -> str:
    md = dossier_ocr(doc_id) / f"{m['page_pdf']:04d}.md"
    txt = dossier_texte(doc_id) / f"{m['page_pdf']:04d}.txt"
    t = ""
    if md.exists():
        t = texte_propre(re.sub(r"<!--.*?-->\n?", "", md.read_text(encoding="utf-8")))
        mm = re.search(r"^#+\s*(.+)$", t, re.M) or re.search(r"^\*\*(.+?)\*\*", t, re.M)
        if mm:
            return mm.group(1).strip()[:120]
    elif txt.exists():
        t = texte_propre(txt.read_text(encoding="utf-8"))
    for l in t.strip().split("\n"):
        l = l.strip(" #*|-")
        if 3 <= len(l) <= 90 and not re.fullmatch(r"[\d\s.,/%°-]+", l):
            return l
    return f"page {m['page_pdf']}"


def run(doc_id: str, modele: str = MODELE_OCR, forcer: bool = False, effort: str = "low") -> dict:
    cat = charger_catalogue()
    d = document(cat, doc_id)
    out = fichier_sections(doc_id)
    if out.exists() and not forcer:
        secs = lire_json(out, [])
        print(f"{doc_id}: {len(secs)} sections déjà en cache", flush=True)
        return {"doc": doc_id, "sections": len(secs), "source": "cache"}
    manifest = lire_json(dossier_pages(doc_id) / "manifest.json", [])
    decalage = int(d.get("decalage_page") or 0)
    secs, source = [], ""

    if d.get("nature") == "scan":
        secs = sections_par_titres_courants(doc_id, manifest, decalage, d.get("titre") or "")
        if secs:
            source = "titres courants des pages (OCR)"
    som = d.get("sommaire_pages")
    if not secs and som:
        parts = []
        for p in range(som[0], som[1] + 1):
            f = dossier_ocr(doc_id) / f"{p:04d}.md"
            if f.exists():
                parts.append(f"--- page PDF {p} ---\n" + re.sub(r"<!--.*?-->\n?", "", f.read_text(encoding="utf-8")))
        if parts:
            client = openai_client()
            kwargs = dict(model=modele, input=PROMPT.format(titre=d["titre"], texte="\n".join(parts)[:80000]),
                          text={"format": {"type": "json_schema", "name": "sommaire", "schema": SCHEMA, "strict": True}},
                          max_output_tokens=60000)
            if modele.startswith("gpt-5"):
                kwargs["reasoning"] = {"effort": effort}
            r = client.responses.create(**kwargs)
            secs = [s for s in json.loads(r.output_text)["sections"] if isinstance(s.get("page_debut"), int)]
            usage = {"input_tokens": r.usage.input_tokens, "output_tokens": r.usage.output_tokens}
            c = cout_usd(modele, usage)
            depenses_ajouter(doc_id + " (sommaire)", modele, usage, 0, c)
            source = f"sommaire OCR structuré par {modele} ({c or 0:.3f} $)"
    if not secs:
        import pymupdf
        toc = pymupdf.open(chemin_document(d)).get_toc(simple=True)
        if toc:
            secs = [{"titre": t.strip(), "niveau": max(1, min(int(lvl), 3)), "page_debut": int(p) - decalage}
                    for lvl, t, p in toc if t and t.strip() and int(p) > 0]
            source = "signets du PDF"
    if not secs and manifest:
        for m in manifest:
            pi = m["page_pdf"] - decalage
            secs.append({"titre": titre_de_page(doc_id, m), "niveau": 1, "page_debut": pi, "page_fin": pi})
        source = "un titre par page"
    elif source != "titres courants des pages (OCR)":
        secs = fins(secs)
    ecrire_json(out, secs)
    d.setdefault("etat", {})["sections"] = f"{len(secs)} ({source})"
    from shared.savoir import sauver_catalogue
    sauver_catalogue(cat)
    print(f"{doc_id}: {len(secs)} sections ({source})", flush=True)
    return {"doc": doc_id, "sections": len(secs), "source": source}


def main() -> None:
    sortie_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--model", default=MODELE_OCR)
    ap.add_argument("--forcer", action="store_true")
    ap.add_argument("--effort", default="low", help="effort de raisonnement pour structurer un sommaire : low | medium | high")
    a = ap.parse_args()
    run(a.doc, a.model, a.forcer, a.effort)


if __name__ == "__main__":
    main()
