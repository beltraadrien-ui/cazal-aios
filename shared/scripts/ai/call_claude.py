"""Helper : appelle Claude via le CLI (abonnement, pas de coût API).

Cloné du wrapper de l'AIOS BeltraTech (`C:\\GitHub\\.claude\\shared\\scripts\\ai\\call_claude.py`).
Écrit le prompt dans un fichier temporaire (active/) pour contourner les limites de
longueur de ligne de commande Windows, puis demande au CLI de le lire. Le CLI tourne
avec cwd = racine du projet → il peut Read les fichiers du repo (dont les frames
extraites dans active/).

Seule fonction externe : call_claude(prompt, timeout=600) -> str

CLI (smoke test) :
    python shared/scripts/ai/call_claude.py "Reponds 'PONG' uniquement."
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.config import ROOT  # noqa: E402


def _find_claude_cmd() -> str:
    """Trouve l'exécutable claude (PATH ou .cmd npm Windows)."""
    found = shutil.which("claude")
    if found:
        return found
    cmd_path = os.path.expanduser("~/AppData/Roaming/npm/claude.cmd")
    if os.path.isfile(cmd_path):
        return cmd_path
    raise FileNotFoundError(
        "claude CLI introuvable. Installer avec : npm install -g @anthropic-ai/claude-code"
    )


def call_claude(prompt: str, timeout: int = 600) -> str:
    """Envoie un prompt à Claude via le CLI headless. Retourne la réponse texte trimée.

    Raises: Exception si le CLI retourne un code non-zéro ou une réponse vide.
    """
    active_dir = ROOT / "active"
    active_dir.mkdir(exist_ok=True)
    temp_path = active_dir / f"_claude_prompt_{os.getpid()}_{threading.get_ident()}.md"
    temp_path.write_text(prompt, encoding="utf-8")

    try:
        result = subprocess.run(
            [
                _find_claude_cmd(),
                "-p",
                f'Lis le contenu du fichier "{temp_path}" et suis les instructions. '
                f"Retourne UNIQUEMENT la reponse demandee, sans commentaire ni explication supplementaire.",
                "--model",
                "sonnet",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ROOT),
            encoding="utf-8",
        )
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass

    if result.returncode != 0:
        raise Exception(f"Claude CLI code {result.returncode} : {(result.stderr or '')[:500]}")
    out = (result.stdout or "").strip()
    if not out:
        raise Exception(
            f"Claude CLI a retourné une réponse vide. stderr : {(result.stderr or '')[:300]}"
        )
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[ERROR] Usage: python shared/scripts/ai/call_claude.py <prompt>")
        sys.exit(1)
    sys.stdout.reconfigure(encoding="utf-8")
    response = call_claude(" ".join(sys.argv[1:]), timeout=120)
    print(f"[OK] Claude a répondu ({len(response)} chars)")
    print(response)
