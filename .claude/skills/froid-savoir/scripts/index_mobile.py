"""Génère l'index bundlé dans le skill mobile froid-question (references/INDEX.md) à partir de la base :
la liste des documents et, pour chacun, ses sections avec leurs pages. Sert de secours au téléphone si la base
est en pause, et de guide pour choisir le bon document.

Usage : python …/index_mobile.py [--max-sections 400]
Ensuite : python shared/scripts/export_skills.py froid-question  → active/skills-zip/froid-question.zip à ré-uploader.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from shared.savoir import ROOT, supabase_client, project_ref, sortie_utf8  # noqa: E402

INDEX = ROOT / ".claude" / "skills" / "froid-question" / "references" / "INDEX.md"


def main() -> None:
    sortie_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-sections", type=int, default=600, help="par document (niveaux 1 puis 2)")
    a = ap.parse_args()
    sb = supabase_client()
    docs = sb.table("savoir_documents").select("id,titre,type,marque,langue,nature,pages_total").order("type").order("id").execute().data
    pages = {d["id"]: (sb.table("savoir_pages").select("id", count="exact").eq("document_id", d["id"]).limit(1).execute().count or 0)
             for d in docs}   # un comptage par document : une requête globale est tronquée à 1 000 lignes
    L = [f"# INDEX de la base de savoir — {len(docs)} documents, {sum(pages.values())} pages",
         "",
         f"> Généré le {time.strftime('%Y-%m-%d')} depuis la base Supabase (projet `{project_ref()}`). Les numéros sont des **pages imprimées**.",
         "> Pour chercher : `select * from rechercher_savoir('mots clés', 5, '<id du document>')` (3ᵉ argument facultatif).",
         "",
         "## Les documents (id · titre · pages)", ""]
    for d in docs:
        L.append(f"- `{d['id']}` · **{d['titre']}** · {d.get('type') or ''}{' · ' + d['marque'] if d.get('marque') else ''} · "
                 f"{pages.get(d['id'], 0)} p. dans la base ({d.get('nature') or '?'}, {d.get('langue') or 'fr'})")
    L.append("")
    from shared.savoir import charger_catalogue
    etat_sections = {d["id"]: (d.get("etat", {}).get("sections") or "") for d in charger_catalogue()["documents"]}
    sans_sommaire = []
    for d in docs:
        if "un titre par page" in etat_sections.get(d["id"], ""):
            sans_sommaire.append(d)
            continue
        secs = sb.table("savoir_sections").select("titre,niveau,page_debut,page_fin").eq("document_id", d["id"]) \
            .order("page_debut").order("niveau").execute().data
        if not secs:
            sans_sommaire.append(d)
            continue
        n1 = [s for s in secs if s["niveau"] == 1]
        n2 = [s for s in secs if s["niveau"] == 2]
        # titres courants : on fusionne les sections consécutives dont les trois premiers mots sont identiques
        fusion = []
        for s_ in n1:
            cle = " ".join(s_["titre"].lower().split()[:3])
            if fusion and fusion[-1]["_cle"] == cle:
                fusion[-1]["page_fin"] = s_.get("page_fin") or fusion[-1]["page_fin"]
            else:
                fusion.append({**s_, "_cle": cle})
        n1 = fusion
        if len(n1) > a.max_sections:
            pas = -(-len(n1) // a.max_sections)
            n1, n2 = n1[::pas], []
        elif len(n1) + len(n2) > a.max_sections:
            n2 = []
        L.append(f"## {d['titre']} (`{d['id']}`)")
        L.append("")
        for s in sorted(n1 + n2, key=lambda s: (s["page_debut"] or 0, s["niveau"])):
            fin = f" à {s['page_fin']}" if s.get("page_fin") and s["page_fin"] != s["page_debut"] else ""
            L.append(f"{'  ' if s['niveau'] == 2 else ''}- {s['titre']} — p. {s['page_debut']}{fin}")
        L.append("")
    if sans_sommaire:
        L.append("## Documents sans sommaire structuré")
        L.append("")
        L.append("*Chercher directement dans la base avec leur `id` en troisième argument.*")
        L.append("")
        for d in sans_sommaire:
            L.append(f"- `{d['id']}` · {d['titre']} · {pages.get(d['id'], 0)} p.")
        L.append("")
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text("\n".join(L), encoding="utf-8")
    print(f"INDEX écrit : {INDEX} ({INDEX.stat().st_size // 1024} Ko, {len(docs)} documents)")


if __name__ == "__main__":
    main()
