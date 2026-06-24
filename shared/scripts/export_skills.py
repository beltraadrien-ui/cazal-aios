"""Exporte chaque skill du repo en .zip uploadable sur claude.ai (Claude Desktop).

Convention double-version : la version repo (.claude/skills/<nom>/) est la source de
vérité ; ce script génère la version zip (active/skills-zip/<nom>.zip) pour la surface
mobile de Loïc. Re-zipper + re-uploader à chaque modif (pas de sync auto).

IMPORTANT : les zips sont écrits avec des slashes '/' (jamais Compress-Archive, qui
met des antislashs et casse l'upload claude.ai "invalid characters").

Chaque zip contient :
    <skill>/SKILL.md
    <skill>/references/<fichiers bundlés>   (selon BUNDLE ci-dessous)

Usage :
    python shared/scripts/export_skills.py            # tous les skills
    python shared/scripts/export_skills.py idee-contenu script-reel-chantier
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = ROOT / ".claude" / "skills"
REFS_DIR = ROOT / "references"
OUT_DIR = ROOT / "active" / "skills-zip"

# Références à bundler dans chaque skill (pour que le zip soit autonome sur claude.ai).
# Les skills moteur (engine) n'embarquent rien : ils tournent dans Claude Code.
BUNDLE: dict[str, list[str]] = {
    "maj-aios": [],
    "scraper-contenu-cazal": [],
    "analyser-contenu": [],
    "rapport-performance": [],
    "rapport-concurrents": [],
    "veille-niche": [
        "rapport-perf-digest.md", "angles-signature-cazal.md", "base-idees.md",
    ],
    "idee-contenu": [
        "base-idees.md", "rapport-perf-digest.md", "angles-signature-cazal.md", "voice.md",
    ],
    "script-reel-chantier": [
        "framework-hook.md", "voice.md", "angles-signature-cazal.md",
        "rapport-perf-digest.md", "format-reel.md", "format-realisation.md", "format-gmb.md",
    ],
    "generateur-hooks": [
        "framework-hook.md", "voice.md", "rapport-perf-digest.md", "angles-signature-cazal.md",
    ],
    "scripter-reel": [
        "framework-hook.md", "voice.md", "angles-signature-cazal.md",
        "rapport-perf-digest.md", "format-reel.md", "base-idees.md",
    ],
    "rediger-article": [
        "format-article.md", "voice.md", "angles-signature-cazal.md",
        "rapport-perf-digest.md", "base-idees.md",
    ],
}


def export_skill(name: str) -> Path:
    skill_dir = SKILLS_DIR / name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"SKILL.md introuvable pour '{name}' ({skill_md})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{name}.zip"

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        # SKILL.md à la racine du dossier skill dans le zip
        z.write(skill_md, f"{name}/SKILL.md")
        # Fichiers de support déjà présents dans le dossier du skill (ex. templates/)
        for f in skill_dir.rglob("*"):
            if f.is_file() and f != skill_md:
                rel = f.relative_to(skill_dir).as_posix()
                z.write(f, f"{name}/{rel}")
        # Références bundlées (source de vérité = references/)
        for ref in BUNDLE.get(name, []):
            src = REFS_DIR / ref
            if not src.exists():
                raise FileNotFoundError(f"Référence à bundler manquante : {src}")
            z.write(src, f"{name}/references/{ref}")
    return out


def main(argv: list[str]) -> None:
    names = argv or list(BUNDLE.keys())
    for name in names:
        out = export_skill(name)
        # Vérif : tous les chemins internes en '/'
        with zipfile.ZipFile(out) as z:
            bad = [n for n in z.namelist() if "\\" in n]
        flag = "  ⚠ antislash détecté" if bad else ""
        print(f"OK — {out.relative_to(ROOT).as_posix()}{flag}")


if __name__ == "__main__":
    main(sys.argv[1:])
