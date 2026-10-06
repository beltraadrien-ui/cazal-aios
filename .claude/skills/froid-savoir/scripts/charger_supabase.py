"""Étape 4 de l'ingestion : charger un document (cache) dans la base Supabase : document, sections, pages, chunks
(plein texte + vecteurs), figures (descriptions, image = la page), renvois, images de pages dans le bucket privé.

Idempotent et reprenable : une page dont le contenu n'a pas changé depuis le dernier chargement est sautée
(empreinte dans bibliotheque/_cache/charge/<doc>.json).
Usage : python …/charger_supabase.py --doc kotza [--sans-vecteurs] [--max-w 1000] [--qualite 62] [--forcer]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from shared.savoir import (texte_propre, BUCKET, SIGNED_SECONDS, MODELE_EMBEDDING, charger_catalogue, sauver_catalogue, document,  # noqa: E402
                           dossier_pages, dossier_ocr, dossier_texte, fichier_sections, fichier_charge, lire_json,
                           ecrire_json, supabase_client, openai_client, embeddings, cout_usd, depenses_ajouter,
                           project_ref, sortie_utf8)

RENVOI = re.compile(r"\bpages?\s+(\d{1,4})(?:\s*(?:à|a|au|-|–|et)\s*(\d{1,4}))?", re.I)


def web_jpeg(src: str, max_w: int, q: int) -> bytes:
    from PIL import Image
    im = Image.open(src).convert("RGB")
    w, h = im.size
    if w > max_w:
        im = im.resize((max_w, int(h * max_w / w)), Image.LANCZOS)
    b = io.BytesIO()
    im.save(b, "JPEG", quality=q, optimize=True)
    return b.getvalue()


def upload(client, path: str, data: bytes) -> str:
    client.storage.from_(BUCKET).upload(path, data, {"content-type": "image/jpeg", "upsert": "true"})
    r = client.storage.from_(BUCKET).create_signed_url(path, SIGNED_SECONDS)
    return r.get("signedURL") or r.get("signedUrl") or r.get("signed_url") or ""


def contenu_page(doc_id: str, nature: str, m: dict) -> dict | None:
    """Texte, métadonnées et figures d'une page depuis le cache (OCR pour un scan, texte PyMuPDF pour un natif)."""
    p = m["page_pdf"]
    if nature == "scan":
        j = lire_json(dossier_ocr(doc_id) / f"{p:04d}.json")
        if not j:
            return None
        return {"texte": texte_propre(j.get("markdown") or "").strip(), "page_lue": j.get("page_lue"), "chapitre": j.get("chapitre"),
                "type": j.get("type_page") or "texte", "confiance": j.get("confiance"), "figures": j.get("figures") or [],
                "ocr": j.get("model")}
    f = dossier_texte(doc_id) / f"{p:04d}.txt"
    if not f.exists():
        return None
    return {"texte": texte_propre(f.read_text(encoding="utf-8")).strip(), "page_lue": None, "chapitre": None, "type": "texte",
            "confiance": None, "figures": [], "ocr": None}


def run(doc_id: str, sans_vecteurs: bool = False, max_w: int = 1000, qualite: int = 62, forcer: bool = False,
        sections_seulement: bool = False) -> dict:
    cat = charger_catalogue()
    d = document(cat, doc_id)
    nature = d.get("nature") or "scan"
    manifest = lire_json(dossier_pages(doc_id) / "manifest.json", [])
    if not manifest:
        raise SystemExit(f"{doc_id}: pas de pages dans le cache")
    sb = supabase_client()
    oa = openai_client() if not sans_vecteurs else None
    decalage = int(d.get("decalage_page") or 0)
    som = d.get("sommaire_pages")
    charge = {} if forcer else lire_json(fichier_charge(doc_id), {})
    t0 = time.time()
    print(f"{doc_id}: chargement dans le projet {project_ref()} (images {max_w} px q{qualite}"
          + (", sans vecteurs" if sans_vecteurs else "") + ")", flush=True)

    pages = []
    for m in manifest:
        c = contenu_page(doc_id, nature, m)
        if c is not None:
            pages.append((m, c))
    if not pages:
        print(f"{doc_id}: rien à charger (pas d'OCR / de texte en cache)", flush=True)
        return {"doc": doc_id, "pages": 0}

    sb.table("savoir_documents").upsert({
        "id": doc_id, "titre": d["titre"], "type": d.get("type"), "marque": d.get("marque"), "langue": d.get("langue", "fr"),
        "nature": nature, "pages_total": d.get("pages_total"), "decalage_page": decalage, "fichier_source": d.get("fichier"),
        "ocr_modele": pages[0][1].get("ocr"), "notes": d.get("notes")}).execute()

    # sections : remplacées à chaque chargement (les pages gardent leur section par recalcul)
    secs = lire_json(fichier_sections(doc_id), [])
    anciennes, debut = [], 0
    while True:   # pagination : PostgREST tronque à 1 000 lignes
        lot = sb.table("savoir_sections").select("id").eq("document_id", doc_id).range(debut, debut + 999).execute().data
        anciennes += [r["id"] for r in lot]
        if len(lot) < 1000:
            break
        debut += 1000
    for i in range(0, len(anciennes), 300):   # par lots : une suppression massive dépasse le délai d'exécution de PostgREST
        sb.table("savoir_sections").delete().in_("id", anciennes[i:i + 300]).execute()
    sec_ids = []
    for i in range(0, len(secs), 200):
        rows = [{"document_id": doc_id, "titre": texte_propre(s["titre"])[:300], "niveau": s.get("niveau", 1),
                 "page_debut": s.get("page_debut"), "page_fin": s.get("page_fin")} for s in secs[i:i + 200]]
        res = sb.table("savoir_sections").insert(rows).execute()
        sec_ids += [(r["id"], r["niveau"], r["page_debut"], r["page_fin"], r["titre"]) for r in res.data]

    def section_de(page_imp):
        best = None
        for sid, niv, deb, fin, titre in sec_ids:
            if deb is not None and deb <= page_imp and (fin is None or page_imp <= fin):
                if best is None or niv >= best[1]:
                    best = (sid, niv, titre)
        return best

    existantes = {}
    debut = 0
    while True:   # pagination : PostgREST tronque à 1 000 lignes
        lot = sb.table("savoir_pages").select("id,page_pdf,page_imprimee").eq("document_id", doc_id).range(debut, debut + 999).execute().data
        for r in lot:
            existantes[r["page_pdf"]] = r["id"]
        if len(lot) < 1000:
            break
        debut += 1000
    if sections_seulement:
        # ne touche ni aux images ni aux vecteurs : recalcule la section de chaque page déjà chargée et le titre de son chunk
        rows, debut = [], 0
        while True:   # pagination : PostgREST tronque à 1 000 lignes
            lot = sb.table("savoir_pages").select("id,page_imprimee").eq("document_id", doc_id).range(debut, debut + 999).execute().data
            rows += lot
            if len(lot) < 1000:
                break
            debut += 1000
        maj = 0
        for r in rows:
            sec = section_de(r["page_imprimee"]) if r["page_imprimee"] is not None else None
            sb.table("savoir_pages").update({"section_id": sec[0] if sec else None}).eq("id", r["id"]).execute()
            sb.table("savoir_chunks").update({"titre_section": sec[2] if sec else ""}).eq("page_id", r["id"]).execute()
            maj += 1
        print(f"{doc_id}: {len(secs)} sections rechargées, {maj} pages réaffectées (images et vecteurs inchangés), {time.time()-t0:.0f}s", flush=True)
        return {"doc": doc_id, "pages": 0, "sections": len(secs), "reaffectees": maj}
    stats = {"pages": 0, "sautees": 0, "figures": 0, "renvois": 0, "ko": [], "tokens": 0}
    a_faire = []
    for m, c in pages:
        descr = "\n".join(f"Figure ({f.get('type')}) : {f.get('description', '')}"
                          + (f" Repères : {f['reperes']}" if f.get("reperes") else "")
                          + (" Mots-clés : " + ", ".join(f.get("mots_cles") or []) if f.get("mots_cles") else "")
                          for f in c["figures"])
        empreinte = hashlib.md5((c["texte"] + "\n" + descr + f"|{max_w}|{qualite}|{int(not sans_vecteurs)}").encode("utf-8")).hexdigest()
        if charge.get(str(m["page_pdf"])) == empreinte and m["page_pdf"] in existantes:
            stats["sautees"] += 1
            continue
        a_faire.append((m, c, descr, empreinte))

    for i in range(0, len(a_faire), 16):
        lot = a_faire[i:i + 16]
        vecteurs = [None] * len(lot)
        if oa is not None:
            textes = []
            for m, c, descr, _ in lot:
                page_imp = c["page_lue"] if c["page_lue"] is not None else m["page_pdf"] - decalage
                sec = section_de(page_imp)
                titre_sec = sec[2] if sec else ""
                textes.append(titre_sec + "\n" + c["texte"] + ("\n\n" + descr if descr else ""))
            vecteurs, tok = embeddings(oa, textes)
            stats["tokens"] += tok
        for (m, c, descr, empreinte), vec in zip(lot, vecteurs):
            p = m["page_pdf"]
            page_imp = c["page_lue"] if c["page_lue"] is not None else p - decalage
            sec = section_de(page_imp)
            img_path = f"{doc_id}/{p:04d}.jpg"
            data = web_jpeg(m["fichier"], max_w, qualite)
            stats["ko"].append(len(data) // 1024)
            url = upload(sb, img_path, data)
            type_page = "sommaire" if (som and som[0] <= p <= som[1]) else c["type"]
            row = {"document_id": doc_id, "page_pdf": p, "page_imprimee": page_imp, "page_lue": c["page_lue"],
                   "section_id": sec[0] if sec else None, "chapitre": c["chapitre"], "type": type_page,
                   "texte": c["texte"], "descriptions_figures": descr, "confiance": c["confiance"],
                   "image_path": img_path, "image_url": url,
                   "image_url_expire": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + SIGNED_SECONDS))}
            res = sb.table("savoir_pages").upsert(row, on_conflict="document_id,page_pdf").execute()
            page_id = res.data[0]["id"]
            if p in existantes:
                for t in ("savoir_chunks", "savoir_figures", "savoir_renvois"):
                    sb.table(t).delete().eq("page_id", page_id).execute()
            titre_sec = sec[2] if sec else ""
            chunk = {"page_id": page_id, "document_id": doc_id, "page_imprimee": page_imp, "titre_section": titre_sec,
                     "contenu": c["texte"] + ("\n\n" + descr if descr else "")}
            if vec is not None:
                chunk["embedding"] = vec
            sb.table("savoir_chunks").insert(chunk).execute()
            frows = [{"id": f"{doc_id}-{p:04d}-{k}", "page_id": page_id, "document_id": doc_id, "page_imprimee": page_imp,
                      "type": f.get("type"), "description": f.get("description"), "reperes": {"texte": f.get("reperes") or ""},
                      "mots_cles": f.get("mots_cles") or [], "image_path": img_path, "image_url": url}
                     for k, f in enumerate(c["figures"], start=1)]
            if frows:
                sb.table("savoir_figures").upsert(frows).execute()
                stats["figures"] += len(frows)
            rrows = []
            for mm in RENVOI.finditer(c["texte"]):
                deb = int(mm.group(1)); fin = int(mm.group(2)) if mm.group(2) else None
                if 1 <= deb <= (d.get("pages_total") or 9999):
                    rrows.append({"page_id": page_id, "page_cible": deb, "page_cible_fin": fin})
            if rrows:
                sb.table("savoir_renvois").insert(rrows).execute()
                stats["renvois"] += len(rrows)
            charge[str(p)] = empreinte
            stats["pages"] += 1
            if stats["pages"] % 25 == 0:
                ecrire_json(fichier_charge(doc_id), charge)
                print(f"  {doc_id}: {stats['pages']}/{len(a_faire)} pages chargées…", flush=True)
    ecrire_json(fichier_charge(doc_id), charge)
    usd = cout_usd(MODELE_EMBEDDING, {"input_tokens": stats["tokens"], "output_tokens": 0}) or 0.0
    if stats["tokens"]:
        depenses_ajouter(doc_id + " (vecteurs)", MODELE_EMBEDDING, {"input_tokens": stats["tokens"], "output_tokens": 0}, stats["pages"], usd)
    d.setdefault("etat", {})["charge"] = f"{len(pages)}/{len(manifest)}"
    sauver_catalogue(cat)
    ko = f", images {statistics.mean(stats['ko']):.0f} Ko en moyenne" if stats["ko"] else ""
    print(f"{doc_id}: {stats['pages']} page(s) chargée(s), {stats['sautees']} inchangée(s), {stats['figures']} figures, "
          f"{stats['renvois']} renvois, vecteurs {stats['tokens']} tokens ({usd:.4f} $){ko}, {time.time()-t0:.0f}s", flush=True)
    return {"doc": doc_id, "pages": stats["pages"], "sautees": stats["sautees"], "figures": stats["figures"], "usd": round(usd, 4)}


def main() -> None:
    sortie_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--sans-vecteurs", action="store_true")
    ap.add_argument("--max-w", type=int, default=1000)
    ap.add_argument("--qualite", type=int, default=62)
    ap.add_argument("--forcer", action="store_true")
    ap.add_argument("--sections-seulement", action="store_true", help="recharger les sections et réaffecter les pages, sans toucher aux images ni aux vecteurs")
    a = ap.parse_args()
    run(a.doc, a.sans_vecteurs, a.max_w, a.qualite, a.forcer, a.sections_seulement)


if __name__ == "__main__":
    main()
