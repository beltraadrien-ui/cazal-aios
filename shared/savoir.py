"""Base de savoir « froid » — code commun aux skills froid-savoir (PC) et aux scripts d'ingestion.

Chemins, catalogue des documents, clients Supabase / OpenAI, prix et registre des dépenses OCR.
Secrets : lus par shared/config.py (.env racine) — jamais affichés.

    from shared.savoir import BIBLIO, CACHE, charger_catalogue, supabase_client, openai_client, cout_usd
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from pathlib import Path

from shared.config import ROOT, SUPABASE_ANON_KEY, SUPABASE_PROJECT_URL, OPENAI_API_KEY, status

BIBLIO = ROOT / "dimensionnement" / "bibliotheque"      # LOCAL, gitignoré : documents de Loïc + cache
CACHE = BIBLIO / "_cache"
CATALOGUE = BIBLIO / "catalogue.json"
CARNET = ROOT / "dimensionnement" / "carnet" / "lecons.md"
BUCKET = "savoir-pages"
SIGNED_SECONDS = 365 * 24 * 3600
MODELE_OCR = "gpt-5.4-mini"
MODELE_EMBEDDING = "text-embedding-3-small"

# Prix OpenAI lus le 2026-10-03 (developers.openai.com/api/docs/pricing, Standard, $ par million de tokens) :
# (entrée, entrée en cache, sortie). À mettre à jour si les prix changent.
PRIX = {
    "gpt-5.4-mini": (0.75, 0.075, 4.50),
    "gpt-5.4-nano": (0.20, 0.02, 1.25),
    "gpt-5.4": (2.50, 0.25, 15.00),
    "gpt-4.1-mini": (0.40, 0.10, 1.60),
    "gpt-4.1-nano": (0.10, 0.025, 0.40),
    "gpt-4.1": (2.00, 0.50, 8.00),
    "gpt-5-mini": (0.25, 0.025, 2.00),
    "text-embedding-3-small": (0.02, 0.02, 0.0),
}


class BudgetDepasse(Exception):
    """Le budget fixé pour cette exécution est atteint : on s'arrête proprement, le cache est conservé."""


class QuotaEpuise(Exception):
    """OpenAI refuse (plafond de dépense ou quota) : on s'arrête proprement, le cache est conservé."""


def est_quota_epuise(exc: BaseException) -> bool:
    s = str(exc).lower()
    return "insufficient_quota" in s or "billing" in s or "hard limit" in s or "exceeded your current quota" in s


def cout_usd(modele: str, usage: dict) -> float | None:
    p = PRIX.get(modele)
    if not p:
        return None
    entree = usage.get("input_tokens", 0) - usage.get("cached_tokens", 0)
    return (entree * p[0] + usage.get("cached_tokens", 0) * p[1] + usage.get("output_tokens", 0) * p[2]) / 1e6


# ---------- fichiers ----------
def lire_json(path: Path, defaut=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else defaut


def ecrire_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def slugifier(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower() or "document"


def texte_propre(t: str) -> str:
    """Texte sûr pour Postgres : le caractère nul (puce Word après conversion .doc → PDF) devient une puce,
    les espaces de largeur nulle disparaissent."""
    return (t or "").replace("\x00", "•").replace("\u200b", "")


def dossier_pages(doc_id: str) -> Path:
    return CACHE / "pages" / doc_id


def dossier_ocr(doc_id: str) -> Path:
    return CACHE / "ocr" / doc_id


def dossier_texte(doc_id: str) -> Path:
    return CACHE / "texte" / doc_id


def fichier_sections(doc_id: str) -> Path:
    return CACHE / "sections" / f"{doc_id}.json"


def fichier_charge(doc_id: str) -> Path:
    return CACHE / "charge" / f"{doc_id}.json"


# ---------- catalogue ----------
def charger_catalogue() -> dict:
    cat = lire_json(CATALOGUE, {"documents": []})
    cat.setdefault("documents", [])
    return cat


def sauver_catalogue(cat: dict) -> None:
    ecrire_json(CATALOGUE, cat)


def document(cat: dict, doc_id: str) -> dict:
    for d in cat["documents"]:
        if d["id"] == doc_id:
            return d
    raise SystemExit(f"Document « {doc_id} » absent du catalogue ({CATALOGUE}). Voir : python …/catalogue.py --lister")


def chemin_document(d: dict) -> Path:
    p = Path(d["fichier"])
    return p if p.is_absolute() else BIBLIO / p


# ---------- registre des dépenses OpenAI (pour comparer avec la console) ----------
def depenses_ajouter(doc_id: str, modele: str, usage: dict, pages: int, usd: float | None) -> None:
    path = CACHE / "ocr" / "_depenses.json"
    reg = lire_json(path, {"total_usd": 0.0, "lignes": []})
    reg["lignes"].append({"quand": time.strftime("%Y-%m-%d %H:%M"), "doc": doc_id, "modele": modele, "pages": pages,
                          "input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0),
                          "usd": round(usd or 0.0, 4)})
    reg["total_usd"] = round(sum(l["usd"] for l in reg["lignes"]), 4)
    ecrire_json(path, reg)


def depenses_total() -> float:
    return float(lire_json(CACHE / "ocr" / "_depenses.json", {"total_usd": 0.0}).get("total_usd", 0.0))


# ---------- clients ----------
def project_ref() -> str:
    m = re.search(r"https://([a-z0-9]+)\.supabase\.co", SUPABASE_PROJECT_URL)
    return m.group(1) if m else ""


def supabase_client():
    if status("SUPABASE_PROJECT_URL") != "SET" or status("SUPABASE_ANON_KEY") != "SET":
        raise SystemExit("SUPABASE_PROJECT_URL / SUPABASE_ANON_KEY manquants dans .env")
    from supabase import create_client
    return create_client(SUPABASE_PROJECT_URL, SUPABASE_ANON_KEY)


def openai_client(max_retries: int = 2, timeout: float = 240):
    if status("OPENAI_API_KEY") != "SET":
        raise SystemExit("OPENAI_API_KEY manquant dans .env")
    from openai import OpenAI
    return OpenAI(api_key=OPENAI_API_KEY, max_retries=max_retries, timeout=timeout)


def embeddings(client, textes: list[str]) -> tuple[list[list[float]], int]:
    """Vecteurs par lots de 32 ; renvoie (vecteurs, tokens)."""
    out, tokens = [], 0
    for i in range(0, len(textes), 32):
        lot = [t[:20000] or " " for t in textes[i:i + 32]]
        try:
            r = client.embeddings.create(model=MODELE_EMBEDDING, input=lot)
        except Exception as e:
            if "maximum context length" not in str(e) and "too long" not in str(e).lower():
                raise
            # une page trop dense (tableaux, anglais) dépasse 8 191 tokens : on raccourcit et on recommence
            lot = [t[:9000] or " " for t in lot]
            r = client.embeddings.create(model=MODELE_EMBEDDING, input=lot)
        out.extend(d.embedding for d in r.data)
        tokens += r.usage.total_tokens if r.usage else 0
    return out, tokens


def sortie_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
