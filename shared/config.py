"""Config partagée — charge le .env racine (loader walk-up, sans dépendance) et expose
les variables en module. Calqué sur Master-content/shared/config.py.

Usage :
    from shared.config import SUPABASE_PROJECT_URL, SUPABASE_ANON_KEY, OPENAI_API_KEY

Ne logge JAMAIS la valeur d'un secret — seulement SET/MISSING (voir __main__).
"""
from __future__ import annotations

import os
from pathlib import Path


def _find_project_root() -> Path:
    """Remonte depuis ce fichier jusqu'à trouver un .env (CWD-independent)."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / ".env").exists():
            return current
        current = current.parent
    # Fallback : le parent de shared/
    return Path(__file__).resolve().parent.parent


ROOT = _find_project_root()


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_env()  # auto-run à l'import


def _is_set(value: str | None) -> bool:
    return bool(value) and not value.startswith("REPLACE_WITH_")


# --- Variables exposées (style Master-content) ---
SUPABASE_PROJECT_URL = os.environ.get("SUPABASE_PROJECT_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
IG_HANDLE = os.environ.get("IG_HANDLE", "")
APIFY_INSTAGRAM_ACTOR = os.environ.get("APIFY_INSTAGRAM_ACTOR", "apify~instagram-scraper")


def status(key: str) -> str:
    """SET ou MISSING — diagnostic sans révéler la valeur."""
    return "SET" if _is_set(os.environ.get(key, "")) else "MISSING"


if __name__ == "__main__":
    for k in (
        "SUPABASE_PROJECT_URL", "SUPABASE_ANON_KEY", "SUPABASE_ACCESS_TOKEN",
        "APIFY_API_TOKEN", "OPENAI_API_KEY",
        "META_ACCESS_TOKEN", "IG_USER_ID", "IG_HANDLE",
    ):
        print(f"{k}: {status(k)}")
