"""Étape 2 de l'ingestion (scans seulement) : OCR de chaque page par un modèle de vision OpenAI (Responses API).

Une passe par page rend : markdown fidèle, numéro de page imprimé, chapitre, pied de page, type de page,
et la description de chaque figure (pas de découpe : l'image de référence est la page entière).
Sortie : bibliotheque/_cache/ocr/<doc>/NNNN.json + .md, _usage.json (tokens par page), registre _depenses.json.
Arrêt propre : budget de l'exécution atteint (--budget-usd) ou plafond OpenAI (quota) → les pages faites restent en cache.
Codes de sortie : 0 ok · 3 budget atteint · 4 quota OpenAI épuisé.
Usage : python …/ocr_openai.py --doc kotza [--model gpt-5.4-mini] [--workers 4] [--budget-usd 5] [--pages 1-20] [--effort none]
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import threading
import time
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from shared.savoir import (MODELE_OCR, BudgetDepasse, QuotaEpuise, est_quota_epuise, cout_usd, charger_catalogue,  # noqa: E402
                           sauver_catalogue, document, dossier_pages, dossier_ocr, lire_json, ecrire_json,
                           depenses_ajouter, openai_client, sortie_utf8)

PROMPT = """Tu es un OCR de très haute fidélité pour un document technique de froid, climatisation, régulation ou électrotechnique (français).
Document : {titre}. Page PDF {page_pdf}.
Transcris TOUT le texte lisible de la page en markdown, fidèlement :
- titres en # / ## / ### selon la hiérarchie visuelle ; listes à puces conservées ; gras/italique si évidents ;
- les TABLEAUX en vrais tableaux markdown (| colonne | colonne |), flèches de tendance recopiées (↗ ↘ → …) ;
- les valeurs chiffrées et formules exactement comme imprimées (−10 °C, 24 K, 7 bar, P = √3 · U · I · cos φ) ;
- la page entière peut être scannée tournée de 90° (paysage) : ce n'est PAS un texte à l'envers, transcris-la normalement ;
- un bloc imprimé TÊTE EN BAS (à 180° par rapport au reste, ex. corrigé d'exercice) est transcrit à l'endroit, précédé de la ligne « [TEXTE IMPRIMÉ À L'ENVERS] » ;
- chaque figure, schéma, photo, graphique ou tableau graphique est signalé à sa place par une ligne « [FIGURE : légende courte] » ; ne représente JAMAIS une figure par un tableau, de l'ASCII ou une description longue dans le markdown ;
- ne transcris pas l'onglet vertical de marge ni le texte fantôme du verso ; ne complète jamais un mot illisible : écris « [illisible] » ;
- une page blanche ou sans texte → markdown vide.

Champs à renseigner :
- page_lue : le numéro de page imprimé sur la page (entier), sinon null ;
- chapitre : l'onglet de marge ou le titre de chapitre courant visible en tête (ex. FROID, DÉPANNAGE, ÉLECTRICITÉ, CLIM), sinon null ;
- pied_de_page : le texte du pied de page (titre courant, auteur, date), sinon null ;
- type_page : texte | exercice | corrige | quiz | tableau | figure | sommaire | mixte ;
- texte_inverse : true si une partie du texte est imprimée tête en bas ;
- confiance : ta confiance globale dans la transcription, entre 0 et 1 ;
- figures : une entrée par figure signalée dans le markdown, dans l'ordre, avec : type (schema-circuit | schema-electrique | photo | graphique | tableau | synthese | icone | autre),
  description (2 à 4 phrases factuelles : ce que montre la figure, composants, valeurs lisibles, sens des flèches ; rien d'inventé),
  reperes (texte « 1 = … ; 2 = … » si des repères numérotés sont lisibles, sinon chaîne vide), mots_cles (5 à 12 mots-clés techniques).
  Un pictogramme ou un bandeau décoratif : type icone, description courte.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "markdown": {"type": "string"},
        "page_lue": {"type": ["integer", "null"]},
        "chapitre": {"type": ["string", "null"]},
        "pied_de_page": {"type": ["string", "null"]},
        "type_page": {"type": "string", "enum": ["texte", "exercice", "corrige", "quiz", "tableau", "figure", "sommaire", "mixte"]},
        "texte_inverse": {"type": "boolean"},
        "confiance": {"type": "number"},
        "figures": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["schema-circuit", "schema-electrique", "photo", "graphique", "tableau", "synthese", "icone", "autre"]},
                "description": {"type": "string"},
                "reperes": {"type": "string"},
                "mots_cles": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["type", "description", "reperes", "mots_cles"], "additionalProperties": False}},
    },
    "required": ["markdown", "page_lue", "chapitre", "pied_de_page", "type_page", "texte_inverse", "confiance", "figures"],
    "additionalProperties": False,
}


def ocr_page(client, modele: str, titre: str, m: dict, detail: str, effort: str) -> tuple[dict, dict]:
    b64 = base64.b64encode(Path(m["fichier"]).read_bytes()).decode()
    kwargs = dict(
        model=modele,
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": PROMPT.format(titre=titre, page_pdf=m["page_pdf"])},
            {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}", "detail": detail},
        ]}],
        text={"format": {"type": "json_schema", "name": "ocr_page", "schema": SCHEMA, "strict": True}},
        max_output_tokens=9000,
    )
    if modele.startswith("gpt-5") and effort:
        kwargs["reasoning"] = {"effort": effort}
    t1 = time.time()
    r = client.responses.create(**kwargs)
    data = json.loads(r.output_text)
    u = r.usage
    usage = {"input_tokens": u.input_tokens,
             "cached_tokens": getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0,
             "output_tokens": u.output_tokens,
             "reasoning_tokens": getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", 0) or 0,
             "secondes": round(time.time() - t1, 1)}
    return data, usage


def run(doc_id: str, modele: str = MODELE_OCR, workers: int = 4, budget_usd: float | None = None, pages: str = "",
        detail: str = "high", effort: str = "none") -> dict:
    cat = charger_catalogue()
    d = document(cat, doc_id)
    manifest = lire_json(dossier_pages(doc_id) / "manifest.json", [])
    if not manifest:
        raise SystemExit(f"{doc_id}: pas de pages dans le cache, lancer extraire_pages.py d'abord")
    voulues = None
    if pages:
        voulues = set()
        for part in pages.split(","):
            a, _, b = part.partition("-")
            voulues |= set(range(int(a), int(b or a) + 1))
    out_dir = dossier_ocr(doc_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    usage_path = out_dir / "_usage.json"
    recap = lire_json(usage_path, {"modele": modele, "pages": {}})
    todo = [m for m in manifest if (voulues is None or m["page_pdf"] in voulues) and not (out_dir / f"{m['page_pdf']:04d}.json").exists()]
    client = openai_client(max_retries=2, timeout=240)
    print(f"{doc_id}: {len(todo)} page(s) à transcrire par {modele} ({workers} en parallèle"
          + (f", budget {budget_usd:.2f} $" if budget_usd is not None else "") + ")", flush=True)
    lock, t0 = threading.Lock(), time.time()
    etat = {"faites": 0, "usd": 0.0, "tokens_in": 0, "tokens_out": 0, "echecs": [], "arret": None}

    def travail(m: dict):
        with lock:
            if etat["arret"]:
                return None
        data, usage = ocr_page(client, modele, d["titre"], m, detail, effort)
        md = data.get("markdown", "") or ""
        base = out_dir / f"{m['page_pdf']:04d}"
        res = {"model": modele, "detail": detail, "effort": effort, "usage": usage,
               "page_lue": data.get("page_lue"), "chapitre": data.get("chapitre"), "pied_de_page": data.get("pied_de_page"),
               "type_page": data.get("type_page"), "texte_inverse": data.get("texte_inverse"),
               "confiance": data.get("confiance"), "figures": data.get("figures") or [], "markdown": md}
        ecrire_json(base.with_suffix(".json"), res)
        base.with_suffix(".md").write_text(
            f"<!-- doc={doc_id} page_pdf={m['page_pdf']} page_lue={data.get('page_lue')} type={data.get('type_page')} ocr={modele} -->\n"
            + md.strip() + "\n", encoding="utf-8")
        return m, data, md, usage

    ex = ThreadPoolExecutor(max_workers=workers)
    futs = {ex.submit(travail, m): m for m in todo}
    try:
        for fut in as_completed(futs):
            m = futs[fut]
            try:
                r = fut.result()
            except Exception as e:
                if isinstance(e, CancelledError):
                    continue
                if est_quota_epuise(e):
                    with lock:
                        deja = etat["arret"]
                        etat["arret"] = etat["arret"] or "quota"
                    if not deja:
                        print(f"{doc_id} {m['page_pdf']}: PLAFOND OPENAI atteint ({str(e)[:100]}) → arrêt propre", flush=True)
                    continue
                etat["echecs"].append(m["page_pdf"])
                print(f"{doc_id} {m['page_pdf']}: ÉCHEC {type(e).__name__} {str(e)[:140]}", flush=True)
                continue
            if r is None:
                continue
            m, data, md, usage = r
            c = cout_usd(modele, usage) or 0.0
            with lock:
                etat["faites"] += 1
                etat["usd"] += c
                etat["tokens_in"] += usage["input_tokens"]
                etat["tokens_out"] += usage["output_tokens"]
                recap["pages"][str(m["page_pdf"])] = {**usage, "usd": round(c, 5)}
                ecrire_json(usage_path, recap)
                nouvel_arret = budget_usd is not None and etat["usd"] >= budget_usd and not etat["arret"]
                if nouvel_arret:
                    etat["arret"] = "budget"
            nfig = len(data.get("figures") or [])
            print(f"{doc_id} {m['page_pdf']}: {len(md)} car. | p. lue {data.get('page_lue')} | {data.get('type_page')} | {nfig} fig. "
                  f"| conf {data.get('confiance')} | in {usage['input_tokens']} out {usage['output_tokens']} | {c:.4f} $ | {usage['secondes']}s", flush=True)
            if nouvel_arret:
                print(f"{doc_id}: BUDGET de l'exécution atteint ({etat['usd']:.2f} $ ≥ {budget_usd:.2f} $) → arrêt propre, "
                      f"les pages en vol se terminent", flush=True)
    finally:
        ex.shutdown(wait=True, cancel_futures=True)

    depenses_ajouter(doc_id, modele, {"input_tokens": etat["tokens_in"], "output_tokens": etat["tokens_out"]}, etat["faites"], etat["usd"])
    nb_ocr = len([f for f in out_dir.glob("*.json") if f.stem.isdigit()])
    d.setdefault("etat", {})["ocr"] = f"{nb_ocr}/{len(manifest)}"
    sauver_catalogue(cat)
    print(f"{doc_id}: {etat['faites']} page(s) transcrite(s) en {time.time()-t0:.0f}s, {len(etat['echecs'])} échec(s), "
          f"{etat['usd']:.3f} $ cette fois · OCR {nb_ocr}/{len(manifest)} pages au total", flush=True)
    res = {"doc": doc_id, "faites": etat["faites"], "usd": round(etat["usd"], 4), "ocr_total": nb_ocr, "pages_total": len(manifest),
           "echecs": etat["echecs"], "arret": etat["arret"]}
    if etat["arret"] == "quota":
        raise QuotaEpuise(json.dumps(res))
    if etat["arret"] == "budget":
        raise BudgetDepasse(json.dumps(res))
    return res


def main() -> None:
    sortie_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--model", default=MODELE_OCR)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--budget-usd", type=float)
    ap.add_argument("--pages", default="")
    ap.add_argument("--detail", default="high")
    ap.add_argument("--effort", default="none")
    a = ap.parse_args()
    try:
        run(a.doc, a.model, a.workers, a.budget_usd, a.pages, a.detail, a.effort)
    except BudgetDepasse:
        sys.exit(3)
    except QuotaEpuise:
        sys.exit(4)


if __name__ == "__main__":
    main()
