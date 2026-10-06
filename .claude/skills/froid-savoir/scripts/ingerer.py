"""Orchestrateur de l'ingestion : un document (ou tout le catalogue, par priorité) → pages → OCR si scan → sections → base.

Usage :
  python …/ingerer.py --doc danfoss-ak-cc-55
  python …/ingerer.py --tout [--priorite-max 3] [--budget-usd 10] [--sans-vecteurs] [--workers 4]
  python …/ingerer.py --etat                      (catalogue, dépenses OpenAI estimées, contenu de la base)
Arrêt propre quand le budget de l'exécution est atteint ou quand OpenAI refuse (plafond mensuel) : ce qui est
déjà transcrit est chargé dans la base, le reste attend la prochaine exécution (reprise automatique, rien n'est repayé).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
sys.path.insert(0, str(ICI.parents[3]))
from shared.savoir import (BudgetDepasse, QuotaEpuise, charger_catalogue, depenses_total, project_ref,  # noqa: E402
                           supabase_client, sortie_utf8)
import extraire_pages, ocr_openai, sections, charger_supabase  # noqa: E402


def ingerer_un(d: dict, budget_restant: float | None, sans_vecteurs: bool, workers: int) -> tuple[dict, float]:
    """Renvoie (résumé, dollars dépensés). Lève BudgetDepasse / QuotaEpuise après avoir chargé ce qui est prêt."""
    doc_id, depense, arret = d["id"], 0.0, None
    print(f"\n===== {doc_id} · {d['titre']} · {d.get('nature') or '?'} · {d.get('pages_total')} p. · priorité {d.get('priorite')}", flush=True)
    extraire_pages.run(doc_id)
    if d.get("nature") == "scan":
        try:
            r = ocr_openai.run(doc_id, workers=workers, budget_usd=budget_restant)
            depense += r["usd"]
        except (BudgetDepasse, QuotaEpuise) as e:
            arret = e
            depense += json.loads(str(e)).get("usd", 0.0)
    try:
        sections.run(doc_id)
        r = charger_supabase.run(doc_id, sans_vecteurs=sans_vecteurs)
    except BaseException as e:   # l'OCR déjà payé reste compté dans le bilan et le budget de l'exécution
        e.usd_depense = depense
        raise
    depense += r.get("usd", 0.0)
    if arret:
        raise arret
    return r, depense


def etat() -> None:
    cat = charger_catalogue()
    print(f"Projet Supabase : {project_ref()} · dépenses OpenAI estimées (registre local) : {depenses_total():.2f} $\n")
    sb = supabase_client()
    docs = {r["id"]: r for r in sb.table("savoir_documents").select("id,titre,pages_total,nature").execute().data}
    pages = sb.table("savoir_pages").select("id", count="exact").limit(1).execute()
    par_doc: dict[str, int] = {}
    for doc_id in docs:   # un comptage par document (une requête globale serait tronquée à 1 000 lignes)
        par_doc[doc_id] = sb.table("savoir_pages").select("id", count="exact").eq("document_id", doc_id).limit(1).execute().count or 0
    print(f"{'id':40s} {'nature':6s} {'pages':>6s} {'cache':>9s} {'ocr':>9s} {'base':>6s}")
    for d in cat["documents"]:
        e = d.get("etat", {})
        print(f"{d['id']:40s} {d.get('nature') or '?':6s} {d.get('pages_total') or 0:6d} {e.get('pages', '-'):>9s} {e.get('ocr', '-'):>9s} {par_doc.get(d['id'], 0):6d}")
    print(f"\n{len(docs)} document(s) et {pages.count} page(s) dans la base.")


def main() -> None:
    sortie_utf8()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc")
    ap.add_argument("--tout", action="store_true")
    ap.add_argument("--priorite-max", type=int, default=9)
    ap.add_argument("--budget-usd", type=float, help="plafond de dépense OpenAI pour cette exécution (OCR + sommaires)")
    ap.add_argument("--sans-vecteurs", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--etat", action="store_true")
    a = ap.parse_args()
    if a.etat:
        etat()
        return
    cat = charger_catalogue()
    if a.doc:
        docs = [d for d in cat["documents"] if d["id"] == a.doc]
        if not docs:
            raise SystemExit(f"« {a.doc} » absent du catalogue")
    elif a.tout:
        docs = sorted([d for d in cat["documents"] if d.get("priorite", 9) <= a.priorite_max], key=lambda d: (d.get("priorite", 9), d["id"]))
    else:
        raise SystemExit("préciser --doc <id>, --tout ou --etat")
    t0, depense, bilan = time.time(), 0.0, []
    print(f"Ingestion de {len(docs)} document(s) dans le projet {project_ref()}"
          + (f" · budget {a.budget_usd:.2f} $" if a.budget_usd is not None else "") + f" · registre : {depenses_total():.2f} $ déjà estimés", flush=True)
    for d in docs:
        restant = None if a.budget_usd is None else max(0.0, a.budget_usd - depense)
        if a.budget_usd is not None and restant <= 0.01 and d.get("nature") == "scan":
            bilan.append((d["id"], "non commencé (budget)"))
            continue
        try:
            r, usd = ingerer_un(d, restant, a.sans_vecteurs, a.workers)
            depense += usd
            bilan.append((d["id"], f"ok · {r.get('pages', 0)} pages chargées · {usd:.3f} $"))
        except BudgetDepasse as e:
            depense += json.loads(str(e)).get("usd", 0.0)
            bilan.append((d["id"], f"ARRÊT budget · OCR {json.loads(str(e)).get('ocr_total')}/{json.loads(str(e)).get('pages_total')} pages · chargé ce qui est prêt"))
            break
        except QuotaEpuise as e:
            depense += json.loads(str(e)).get("usd", 0.0)
            bilan.append((d["id"], f"ARRÊT plafond OpenAI · OCR {json.loads(str(e)).get('ocr_total')}/{json.loads(str(e)).get('pages_total')} pages · chargé ce qui est prêt"))
            break
        except SystemExit as e:
            depense += getattr(e, "usd_depense", 0.0)
            print(f"{d['id']}: ERREUR {e}", flush=True)
            bilan.append((d["id"], f"ERREUR {e} · {getattr(e, 'usd_depense', 0.0):.3f} $ d'OCR déjà payés (en cache)"))
        except Exception as e:
            depense += getattr(e, "usd_depense", 0.0)
            print(f"{d['id']}: ERREUR {type(e).__name__} {str(e)[:300]}", flush=True)
            bilan.append((d["id"], f"ERREUR {type(e).__name__} {str(e)[:160]} · {getattr(e, 'usd_depense', 0.0):.3f} $ d'OCR déjà payés (en cache)"))
    print(f"\n===== Bilan ({time.time()-t0:.0f}s, {depense:.3f} $ dépensés cette fois, registre total {depenses_total():.2f} $)", flush=True)
    for doc_id, b in bilan:
        print(f"  {doc_id:40s} {b}", flush=True)


if __name__ == "__main__":
    main()
