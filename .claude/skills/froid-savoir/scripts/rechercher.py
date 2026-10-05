"""Interroger la base de savoir depuis le PC : par mots (plein texte français) et par sens (vecteurs OpenAI).

Usage : python …/rechercher.py "symptômes d'un détendeur trop petit" [--doc kotza] [--limit 5] [--mots | --sens | --les-deux]
        python …/rechercher.py --test                 (jeu de questions de contrôle, bonne page attendue dans le top 3)
        python …/rechercher.py --documents            (liste des documents de la base)
Sortie : markdown (document · page imprimée · section · extrait · figures · lien image).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from shared.savoir import MODELE_EMBEDDING, supabase_client, openai_client, sortie_utf8  # noqa: E402

TESTS = [  # (question en mots-clés comme le skill les formule, document, pages imprimées acceptées — livre complet)
    ("symptômes détendeur trop petit", "kotza", {105, 106, 107, 108, 109, 110, 111, 112, 113, 879}),
    ("dimensionner la bouteille liquide", "kotza", {131}),
    ("V4V mode hiver refoulement compresseur", "kotza", {454, 455, 456}),
    ("tirage au vide automatique inconvénient", "kotza", {299, 300}),
    ("panne manque de charge HP BP symptômes", "kotza", {135, 136, 137, 138, 139, 140}),
    ("dégivrage AK-CC 55 réglage", "danfoss-ak-cc-55-manuel", None),
    ("gas cooler CO2 transcritique température extérieure", "advansor-module-1", None),
]


def mots(sb, q, limit=5, doc=None):
    return sb.rpc("rechercher_savoir", {"q": q, "limite": limit, "doc": doc}).execute().data or []


def sens(sb, q, limit=5, doc=None):
    e = openai_client().embeddings.create(model=MODELE_EMBEDDING, input=[q]).data[0].embedding
    return sb.rpc("rechercher_savoir_vec", {"q_embedding": json.dumps(e), "limite": limit, "doc": doc}).execute().data or []


def afficher(rows, mode):
    if not rows:
        print(f"_({mode}) aucun résultat_")
        return
    for i, r in enumerate(rows, 1):
        score = r.get("rang", r.get("similarite"))
        print(f"\n**{i}. {r['titre_document']} · p. {r['page_imprimee']}** · {r.get('titre_section') or ''} · score {score:.3f}"
              + (f" · {r['mode']}" if r.get("mode") else ""))
        print("   " + (r.get("extrait") or "").replace("\n", " ")[:400])
        for f in r.get("figures") or []:
            print(f"   - figure ({f.get('type')}) : {(f.get('description') or '')[:160]}")
        if r.get("renvois"):
            print(f"   - voir aussi p. {', '.join(str(x) for x in r['renvois'])}")
        if r.get("image_url"):
            print(f"   - image de la page : {r['image_url']}")


def main() -> None:
    sortie_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="?")
    ap.add_argument("--doc")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--mots", action="store_true")
    ap.add_argument("--sens", action="store_true")
    ap.add_argument("--les-deux", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--documents", action="store_true")
    a = ap.parse_args()
    sb = supabase_client()
    if a.documents:
        for r in sb.table("savoir_documents").select("id,titre,nature,pages_total,type,marque").order("id").execute().data:
            print(f"  {r['id']:40s} {r['nature'] or '?':5s} {r['pages_total'] or 0:5d} p. · {r['titre']}")
        return
    if a.test:
        ok_m = ok_s = 0
        for q, doc, attendu in TESTS:
            rm = [r["page_imprimee"] for r in mots(sb, q, 3, doc)]
            rs = [r["page_imprimee"] for r in sens(sb, q, 3, doc)]
            if attendu is None:   # simple contrôle de présence (document natif)
                hm, hs = bool(rm), bool(rs)
            else:
                hm, hs = bool(set(rm) & attendu), bool(set(rs) & attendu)
            ok_m += hm; ok_s += hs
            print(f"{q[:52]:54s} {doc[:22]:22s} mots {str(rm):>18s} {'✓' if hm else '✗'}  sens {str(rs):>16s} {'✓' if hs else '✗'}")
        print(f"\nscore : mots {ok_m}/{len(TESTS)} · sens {ok_s}/{len(TESTS)}")
        return
    if not a.question:
        sys.exit("question manquante")
    if a.les_deux or not a.sens:
        print(f"### Par mots : « {a.question} »")
        afficher(mots(sb, a.question, a.limit, a.doc), "mots")
    if a.les_deux or a.sens:
        print(f"\n### Par sens : « {a.question} »")
        afficher(sens(sb, a.question, a.limit, a.doc), "sens")


if __name__ == "__main__":
    main()
