"""Vue lisible d'un dossier d'installation : les fichiers markdown du dossier (mémoire de Claude) → pages HTML
pour l'humain, avec la photo de chaque plaque affichée à côté de sa lecture.

Usage : python .claude/skills/froid-releve-existant/scripts/rendu_html.py <dossier> [--ouvrir]
        python … rendu_html.py dimensionnement/dossiers/2026-09-14-ets-denis --ouvrir
Entrée : dossier.md, 1-existant.md, 2-dimensionnement.md (ceux qui existent).
Sortie : le même nom en .html à côté (ex. 1-existant.html), chemins d'images relatifs → le dossier reste déplaçable.
Dépendance : markdown (pur Python, dans requirements.txt).
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
from pathlib import Path

import markdown

FICHIERS = ["dossier.md", "1-existant.md", "2-dimensionnement.md"]

CSS = """
:root { --encre: #1d1d1f; --gris: #6e6e73; --ligne: #d9d9de; --fond: #f5f5f7; --accent: #0b5cad; --ok: #1a7f37; --warn: #b45309; }
* { box-sizing: border-box; }
body { margin: 0; padding: 24px 32px 64px; font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: var(--encre); background: #fff; }
main { max-width: 1400px; margin: 0 auto; }
h1 { font-size: 26px; line-height: 1.25; margin: 0 0 8px; }
h2 { font-size: 20px; margin: 36px 0 12px; padding-bottom: 6px; border-bottom: 2px solid var(--accent); color: var(--accent); }
h3 { font-size: 16px; margin: 24px 0 8px; }
blockquote { margin: 12px 0 20px; padding: 10px 16px; background: var(--fond); border-left: 4px solid var(--accent); color: #333; font-size: 14px; }
blockquote p { margin: 4px 0; }
p { margin: 8px 0; }
code { font: 13px/1.4 ui-monospace, Consolas, monospace; background: var(--fond); padding: 1px 5px; border-radius: 4px; }
table { border-collapse: collapse; width: 100%; margin: 10px 0 18px; font-size: 14px; }
th, td { border: 1px solid var(--ligne); padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: var(--fond); position: sticky; top: 0; z-index: 1; font-weight: 600; }
tbody tr:nth-child(even) { background: #fafafa; }
td:first-child { font-weight: 600; white-space: nowrap; max-width: 260px; white-space: normal; }
ul { padding-left: 22px; } li { margin: 4px 0; }
li.tache { list-style: none; margin-left: -22px; }
li.tache::before { content: "☐ "; color: var(--warn); font-size: 16px; }
li.tache.faite::before { content: "☑ "; color: var(--ok); }
.vignette { display: inline-block; margin: 2px 6px 2px 0; text-align: center; vertical-align: top; }
.vignette img { height: 120px; border-radius: 4px; border: 1px solid var(--ligne); display: block; }
.vignette img:hover { outline: 3px solid var(--accent); cursor: zoom-in; }
.vignette span { display: block; font: 11px ui-monospace, Consolas, monospace; color: var(--gris); margin-top: 2px; }
a.photo-ref { color: var(--accent); text-decoration: none; border-bottom: 1px dotted var(--accent); }
.nav { font-size: 13px; color: var(--gris); margin-bottom: 18px; }
.nav a { color: var(--accent); margin-right: 14px; }
.pied { margin-top: 40px; color: var(--gris); font-size: 12px; border-top: 1px solid var(--ligne); padding-top: 10px; }
@media print { body { padding: 0; font-size: 12px; } th { position: static; } .vignette img { height: 80px; } h2 { break-after: avoid; } tr { break-inside: avoid; } .nav { display: none; } }
"""

RE_CODE_PHOTO = re.compile(r"`((?:sources/photos/)?(?:[\w-]+/)?(p\d{2}-\d+\.(?:jpe?g|png)))`")
RE_REF_PHOTO = re.compile(r"(?<![\w/`-])(p\d{2}-\d+)(?![\w./-])")


def carte_photos(dossier: Path) -> dict[str, str]:
    """nom de fichier (p05-2.jpeg) et radical (p05-2) → chemin relatif au dossier."""
    carte: dict[str, str] = {}
    for f in (dossier / "sources" / "photos").rglob("*"):
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png"):
            rel = f.relative_to(dossier).as_posix()
            carte[f.name] = rel
            carte[f.stem] = rel
    return carte


def enrichir(md: str, carte: dict[str, str]) -> str:
    """Remplace les références de photos par une vignette cliquable (code) ou un lien (texte)."""
    def vignette(m: re.Match) -> str:
        nom = m.group(2)
        rel = carte.get(nom)
        if not rel:
            return m.group(0)
        return (f'<a class="vignette" href="{rel}" target="_blank" title="{nom}"><img src="{rel}" alt="{nom}">'
                f"<span>{nom}</span></a>")

    def lien(m: re.Match) -> str:
        rel = carte.get(m.group(1))
        return f'<a class="photo-ref" href="{rel}" target="_blank">{m.group(1)}</a>' if rel else m.group(0)

    lignes = []
    for l in md.split("\n"):
        l = RE_CODE_PHOTO.sub(vignette, l)
        if "<a class=\"vignette\"" in l or l.startswith("|"):
            l = RE_REF_PHOTO.sub(lien, l)
        lignes.append(l)
    return "\n".join(lignes)


def cases_a_cocher(corps: str) -> str:
    corps = corps.replace("<li>[ ] ", '<li class="tache">').replace("<li>[x] ", '<li class="tache faite">')
    return corps


def convertir(md_path: Path, dossier: Path, carte: dict[str, str]) -> Path:
    texte = md_path.read_text(encoding="utf-8")
    titre = next((l[2:].strip() for l in texte.split("\n") if l.startswith("# ")), md_path.stem)
    corps = markdown.markdown(enrichir(texte, carte), extensions=["tables", "sane_lists"])
    corps = cases_a_cocher(corps)
    nav = " ".join(f'<a href="{f[:-3]}.html">{f[:-3]}</a>' for f in FICHIERS if (dossier / f).exists())
    page = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titre)}</title><style>{CSS}</style></head>
<body><main>
<div class="nav">Dossier <code>{html.escape(dossier.name)}</code> · {nav}</div>
{corps}
<div class="pied">Vue générée depuis <code>{md_path.name}</code> par <code>rendu_html.py</code> (skill froid-releve-existant). Le fichier markdown reste la référence ; cette page se régénère à chaque modification. Cliquer une vignette ouvre la photo en taille réelle.</div>
</main></body></html>"""
    out = md_path.with_suffix(".html")
    out.write_text(page, encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossier", help="dossier d'installation (ou un fichier .md du dossier)")
    ap.add_argument("--ouvrir", action="store_true", help="ouvrir 1-existant.html (ou le premier rendu) dans le navigateur")
    a = ap.parse_args()
    cible = Path(a.dossier)
    dossier = cible.parent if cible.is_file() else cible
    fichiers = [cible] if cible.is_file() else [dossier / f for f in FICHIERS if (dossier / f).exists()]
    if not fichiers:
        raise SystemExit(f"Aucun fichier markdown à rendre dans {dossier}")
    carte = carte_photos(dossier)
    sorties = [convertir(f, dossier, carte) for f in fichiers]
    for s in sorties:
        print(f"Rendu : {s}")
    if a.ouvrir:
        principal = next((s for s in sorties if s.name == "1-existant.html"), sorties[0])
        os.startfile(principal)  # Windows : navigateur par défaut


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
