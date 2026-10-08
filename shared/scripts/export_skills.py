"""Exporte les skills mobiles du repo en .zip uploadables sur claude.ai (application Claude).

Convention double-version : la version repo (.claude/skills/<nom>/) est la source de
vérité ; ce script génère la version zip (skills-mobiles/<nom>.zip) pour la surface
mobile de Loïc. Le dossier skills-mobiles/ est VERSIONNÉ : les zips arrivent chez Loïc
avec la mise à jour de l'AIOS (maj-aios), qui lui dit lesquels recharger sur claude.ai.
Re-zipper à chaque modif d'un skill mobile ou d'une référence qu'il bundle, puis committer
le zip avec le reste (pas de sync auto vers claude.ai).

MOBILES = les 8 skills de surface (ceux qui tournent dans l'application Claude). Sans
argument, le script exporte exactement cette liste. Les skills moteur restent dans BUNDLE
pour compatibilité mais ne sont plus exportés : les demander explicitement est refusé.

IMPORTANT : les chemins internes des zips sont écrits avec des slashes '/' (jamais
Compress-Archive, qui met des antislashs et casse l'upload claude.ai "invalid characters").
Les zips sont reproductibles (date fixe, ordre trié) : un zip ne change dans git que si
son contenu change, donc maj-aios ne fait recharger que ce qui a vraiment bougé.

Chaque zip contient :
    <skill>/SKILL.md
    <skill>/<fichiers de support du dossier du skill>   (ex. templates/, references/INDEX.md)
    <skill>/references/<fichiers bundlés>              (selon BUNDLE ci-dessous)

Usage :
    python shared/scripts/export_skills.py            # les 8 skills de MOBILES
    python shared/scripts/export_skills.py idee-contenu script-reel-chantier
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = ROOT / ".claude" / "skills"
REFS_DIR = ROOT / "references"
OUT_DIR = ROOT / "skills-mobiles"

# Les skills de surface (application Claude, téléphone et ordinateur) : les seuls exportés.
MOBILES: list[str] = [
    "veille-niche", "idee-contenu", "script-reel-chantier", "generateur-hooks",
    "scripter-reel", "rediger-article", "resume-vocal-devis", "froid-question",
]

# Références à bundler dans chaque skill (pour que le zip soit autonome sur claude.ai).
# Les skills moteur (engine) n'embarquent rien : ils tournent dans Claude Code.
BUNDLE: dict[str, list[str]] = {
    "resume-vocal-devis": [  # surface ; son template est dans le dossier du skill (templates/)
        "referentiel-unites-interieures-clim.md",
    ],
    "maj-aios": [],
    "froid-question": [],  # surface (mobile) ; son INDEX est dans le dossier du skill (references/), généré par froid-savoir/scripts/index_mobile.py
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

# Date fixe des entrées du zip (zip reproductible : mêmes fichiers = mêmes octets).
DATE_FIXE = (1980, 1, 1, 0, 0, 0)


def _exclu(rel: Path) -> bool:
    """Fichiers qui n'ont rien à faire dans un zip publié (cache Python, secrets, système)."""
    if "__pycache__" in rel.parts:
        return True
    nom = rel.name
    return nom.endswith(".pyc") or nom.startswith(".env") or nom in {".DS_Store", "Thumbs.db"}


def _ajouter(z: zipfile.ZipFile, src: Path, arcname: str) -> None:
    info = zipfile.ZipInfo(arcname, date_time=DATE_FIXE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    z.writestr(info, src.read_bytes())


def export_skill(name: str) -> Path:
    skill_dir = SKILLS_DIR / name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"SKILL.md introuvable pour '{name}' ({skill_md})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{name}.zip"

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        # SKILL.md à la racine du dossier skill dans le zip
        _ajouter(z, skill_md, f"{name}/SKILL.md")
        # Fichiers de support déjà présents dans le dossier du skill (ex. templates/)
        for f in sorted(skill_dir.rglob("*")):
            rel = f.relative_to(skill_dir)
            if f.is_file() and f != skill_md and not _exclu(rel):
                _ajouter(z, f, f"{name}/{rel.as_posix()}")
        # Références bundlées (source de vérité = references/)
        for ref in BUNDLE.get(name, []):
            src = REFS_DIR / ref
            if not src.exists():
                raise FileNotFoundError(f"Référence à bundler manquante : {src}")
            _ajouter(z, src, f"{name}/references/{ref}")
    return out


def main(argv: list[str]) -> int:
    names = argv or list(MOBILES)
    hors = [n for n in names if n not in MOBILES]
    if hors:
        print(
            "Refusé : " + ", ".join(hors) + " ne fait pas partie des skills mobiles.\n"
            "Seuls ces skills ont un zip (skills-mobiles/) : " + ", ".join(MOBILES) + ".\n"
            "Les skills moteur tournent dans Claude Code sur le PC, ils n'ont pas de version mobile.",
            file=sys.stderr,
        )
        return 2
    erreurs = 0
    for name in names:
        out = export_skill(name)
        # Vérif : tous les chemins internes en '/'
        with zipfile.ZipFile(out) as z:
            bad = [n for n in z.namelist() if "\\" in n]
        flag = "  ⚠ antislash détecté" if bad else ""
        erreurs += bool(bad)
        print(f"OK — {out.relative_to(ROOT).as_posix()}{flag}")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
