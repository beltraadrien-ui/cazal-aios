"""Vue HTML lisible d'un document markdown (module partagé entre les skills du dimensionnement).

Le markdown reste la mémoire de Claude ; l'humain lit cette page : tableaux lisibles, vignettes cliquables des
photos, cases à cocher, statuts colorés, en-tête daté, impression propre.

Ligne de commande :
    python shared/rendu_html.py <fichier.md | dossier> [--ouvrir] [--sortie X.html] [--titre T]
                                [--racine DOSSIER] [--mention "texte"] [--pages-par-section]
    python shared/rendu_html.py dimensionnement/dossiers/<slug>/2-dimensionnement.md --ouvrir \
        --mention "Valeurs indicatives, sélection finale chez le fournisseur."
    Un dossier en argument rend dossier.md, 1-existant.md, 2-dimensionnement.md (ceux qui existent) ;
    --ouvrir ouvre alors le document de l'étape la plus avancée.

Python :
    from shared.rendu_html import convertir
    convertir(dossier / "2-dimensionnement.md", mention="Valeurs indicatives, sélection finale chez le fournisseur.",
              ouvrir=True)

Ce que fait le rendu :
- bibliothèque `markdown` (extensions tables, sane_lists, fenced_code ; pur Python, dans requirements.txt) ;
- photos : `p05-2.jpeg` ou `sources/photos/<poste>/p05-2.jpeg` entre accents graves → vignette cliquable ;
  `p05-2` nu (dans une ligne de tableau ou à côté d'une vignette) → lien. Les photos sont cherchées dans
  `<racine>/sources/photos/` (racine = dossier du markdown par défaut) ; les liens sont relatifs à la page HTML ;
- cases à cocher `- [ ]` / `- [x]` ; espaces insécables (U+00A0) gardés tels quels ;
- statuts dans les cellules : « (hyp.) » en petit, « à confirmer » en orange, cellule qui commence par « ⚠ »
  ou contient « ALERTE » en rouge ;
- en-tête (titre = premier `# `, date de génération), pied avec mention facultative, tableaux larges défilant
  horizontalement, feuille d'impression (saut de page avant chaque `## ` sauf le premier si pages_par_section).
Sortie par défaut : le même nom en .html à côté du markdown (UTF-8, fins de ligne LF).

Directives dans le markdown (facultatives, en tête du fichier, avant tout autre contenu ; retirées de la page) :
    <!-- mention: Valeurs indicatives, sélection finale chez le fournisseur. -->
    <!-- titre: Dimensionnement du remplacement -->
Elles servent quand le paramètre `mention` / `titre` vaut None (le paramètre explicite garde la priorité) :
la mention survit ainsi à toute régénération, quel que soit le script qui rend la page.
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import markdown

DOCUMENTS_DOSSIER = ("dossier.md", "1-existant.md", "2-dimensionnement.md")  # ordre du parcours d'un dossier
EXTENSIONS = ["tables", "sane_lists", "fenced_code"]
IMAGES = (".jpg", ".jpeg", ".png")

CSS = """
:root { --encre: #1d1d1f; --gris: #6e6e73; --ligne: #d9d9de; --fond: #f5f5f7; --accent: #0b5cad; --ok: #1a7f37; --warn: #b45309;
        --orange: #c2410c; --rouge: #b42318; --rouge-fond: #fef3f2; }
* { box-sizing: border-box; }
body { margin: 0; padding: 24px 32px 64px; font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: var(--encre); background: #fff; }
main { max-width: 1400px; margin: 0 auto; }
h1 { font-size: 26px; line-height: 1.25; margin: 0 0 8px; }
.entete { margin-bottom: 18px; }
.entete .sous-titre { margin: 0 0 4px; font-size: 16px; color: #333; }
.entete .genere { margin: 0; font-size: 12px; color: var(--gris); }
h2 { font-size: 20px; margin: 36px 0 12px; padding-bottom: 6px; border-bottom: 2px solid var(--accent); color: var(--accent); }
h3 { font-size: 16px; margin: 24px 0 8px; }
blockquote { margin: 12px 0 20px; padding: 10px 16px; background: var(--fond); border-left: 4px solid var(--accent); color: #333; font-size: 14px; }
blockquote p { margin: 4px 0; }
p { margin: 8px 0; }
code { font: 13px/1.4 ui-monospace, Consolas, monospace; background: var(--fond); padding: 1px 5px; border-radius: 4px; }
pre { background: var(--fond); padding: 10px 12px; border-radius: 6px; overflow-x: auto; }
pre code { padding: 0; }
.tableau { overflow-x: auto; margin: 10px 0 18px; }
.tableau.ajuste { overflow: visible; }
table { border-collapse: collapse; width: 100%; margin: 0; font-size: 14px; font-variant-numeric: tabular-nums; }
th, td { border: 1px solid var(--ligne); padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: var(--fond); position: sticky; top: 0; z-index: 1; font-weight: 600; }
tbody tr:nth-child(even) { background: #fafafa; }
td:first-child { font-weight: 600; white-space: nowrap; max-width: 260px; white-space: normal; }
td.alerte { color: var(--rouge); background: var(--rouge-fond); font-weight: 600; }
.a-confirmer { color: var(--orange); font-weight: 600; }
.hyp { font-size: 0.78em; color: var(--gris); font-weight: normal; }
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
.nav a.ici { color: var(--encre); font-weight: 600; text-decoration: none; }
.pied { margin-top: 40px; color: var(--gris); font-size: 12px; border-top: 1px solid var(--ligne); padding-top: 10px; }
.pied p { margin: 4px 0; }
.pied .mention { color: var(--encre); font-size: 13px; font-weight: 600; }
@media (max-width: 700px) { body { padding: 16px 16px 48px; } h1 { font-size: 22px; } }
@page { margin: 12mm; }
@media print {
  body { padding: 0; font-size: 12px; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  main { max-width: none; }
  .nav { display: none; }
  th { position: static; }
  .tableau, .tableau.ajuste { overflow: visible; }
  table { font-size: 11px; }
  thead { display: table-header-group; }
  .vignette img { height: 80px; }
  .vignette img:hover { outline: none; }
  a { color: inherit; }
  h1, h2, h3 { break-after: avoid; }
  tr, .vignette, blockquote, pre { break-inside: avoid; }
  body.pages-par-section article > h2 ~ h2 { break-before: page; }
}
"""

# Les tableaux qui tiennent dans la page gardent l'en-tête de colonnes collant ; les autres défilent horizontalement.
SCRIPT = """
(function () {
  function ajuster() {
    document.querySelectorAll(".tableau").forEach(function (d) {
      d.classList.toggle("ajuste", d.scrollWidth <= d.clientWidth + 1);
    });
  }
  window.addEventListener("load", ajuster);
  window.addEventListener("resize", ajuster);
})();
"""

RE_CODE_PHOTO = re.compile(r"`((?:sources/photos/)?(?:[\w-]+/)?(p\d{2}-\d+\.(?:jpe?g|png)))`")
RE_REF_PHOTO = re.compile(r"(?<![\w/`-])(p\d{2}-\d+)(?![\w./-])")
RE_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
RE_H1 = re.compile(r"<h1>(.*?)</h1>\n?", re.S)
RE_BALISE = re.compile(r"(<[^>]+>)")
RE_TD = re.compile(r"<td([^>]*)>(.*?)</td>", re.S)
RE_HYP = re.compile(r"\(hyp\.?\)")
RE_A_CONFIRMER = re.compile(r"à[  ]confirmer", re.I)
RE_CASE = re.compile(r"<li>(\s*<p>)?\[([ xX])\] ")
RE_DIRECTIVE = re.compile(r"^\s*<!--\s*(mention|titre)\s*:\s*(.*?)\s*-->\s*$", re.I)


def lire_directives(md: str) -> tuple[dict[str, str], str]:
    """Lit les commentaires `<!-- mention: … -->` / `<!-- titre: … -->` en tête du markdown (lignes vides admises)
    et renvoie (directives, markdown sans ces commentaires)."""
    lignes = md.split("\n")
    directives: dict[str, str] = {}
    i = 0
    while i < len(lignes):
        m = RE_DIRECTIVE.match(lignes[i])
        if m:
            directives[m.group(1).lower()] = m.group(2)
        elif lignes[i].strip():
            break
        i += 1
    if not directives:
        return directives, md
    return directives, "\n".join(lignes[i:])


def lien_relatif(cible: Path, depuis: Path) -> str:
    """Adresse de `cible` vue depuis le dossier `depuis`, prête pour un href (slashes, encodée) ;
    file:/// si les deux ne sont pas sur le même lecteur Windows."""
    try:
        return quote(Path(os.path.relpath(cible, depuis)).as_posix(), safe="/")
    except ValueError:
        return Path(cible).resolve().as_uri()


def carte_photos(racine: Path, dossier_html: Path) -> dict[str, str]:
    """Nom de fichier (p05-2.jpeg) et radical (p05-2) → adresse de la photo depuis le dossier de la page HTML."""
    carte: dict[str, str] = {}
    photos = racine / "sources" / "photos"
    if not photos.is_dir():
        return carte
    for f in sorted(photos.rglob("*")):
        if f.is_file() and f.suffix.lower() in IMAGES:
            adresse = lien_relatif(f, dossier_html)
            carte[f.name] = adresse
            carte[f.stem] = adresse
    return carte


def enrichir(md: str, carte: dict[str, str]) -> str:
    """Remplace les références de photos par une vignette cliquable (code) ou un lien (texte), hors blocs de code."""
    def vignette(m: re.Match) -> str:
        nom = m.group(2)
        adresse = carte.get(nom)
        if not adresse:
            return m.group(0)
        a, n = html.escape(adresse), html.escape(nom)
        return f'<a class="vignette" href="{a}" target="_blank" title="{n}"><img src="{a}" alt="{n}"><span>{n}</span></a>'

    def lien(m: re.Match) -> str:
        adresse = carte.get(m.group(1))
        if not adresse:
            return m.group(0)
        return f'<a class="photo-ref" href="{html.escape(adresse)}" target="_blank">{m.group(1)}</a>'

    lignes, bloc_code = [], None
    for ligne in md.split("\n"):
        f = RE_FENCE.match(ligne)
        if f and (bloc_code is None or f.group(1)[0] == bloc_code):
            bloc_code = f.group(1)[0] if bloc_code is None else None
        elif bloc_code is None:
            ligne = RE_CODE_PHOTO.sub(vignette, ligne)
            if '<a class="vignette"' in ligne or ligne.startswith("|"):
                ligne = RE_REF_PHOTO.sub(lien, ligne)
        lignes.append(ligne)
    return "\n".join(lignes)


def cases_a_cocher(corps: str) -> str:
    """`- [ ]` → case vide, `- [x]` → case cochée (listes serrées ou aérées)."""
    def case(m: re.Match) -> str:
        classe = "tache" if m.group(2) == " " else "tache faite"
        return f'<li class="{classe}">{m.group(1) or ""}'
    return RE_CASE.sub(case, corps)


def marquer_statuts(corps: str) -> str:
    """Dans chaque cellule : « (hyp.) » discret, « à confirmer » orange, « ⚠… » ou « ALERTE » → cellule rouge.
    Seul le texte est touché (jamais les balises ni leurs attributs) ; les espaces insécables restent."""
    def cellule(m: re.Match) -> str:
        attributs, contenu = m.group(1), m.group(2)
        morceaux = RE_BALISE.split(contenu)  # indices pairs = texte, impairs = balises
        for i in range(0, len(morceaux), 2):
            t = RE_HYP.sub(r'<span class="hyp">\g<0></span>', morceaux[i])
            morceaux[i] = RE_A_CONFIRMER.sub(r'<span class="a-confirmer">\g<0></span>', t)
        texte = html.unescape(RE_BALISE.sub("", contenu)).strip()
        if texte.startswith("⚠") or "ALERTE" in texte:
            if 'class="' in attributs:
                attributs = attributs.replace('class="', 'class="alerte ', 1)
            else:
                attributs += ' class="alerte"'
        return f"<td{attributs}>{''.join(morceaux)}</td>"
    return RE_TD.sub(cellule, corps)


def envelopper_tableaux(corps: str) -> str:
    return corps.replace("<table>", '<div class="tableau"><table>').replace("</table>", "</table></div>")


def ouvrir_page(chemin: Path) -> None:
    """Ouvre la page dans le navigateur par défaut."""
    if hasattr(os, "startfile"):
        os.startfile(chemin)  # Windows
    else:
        webbrowser.open(Path(chemin).resolve().as_uri())


def convertir(chemin_md: Path, chemin_html: Path | None = None, titre: str | None = None, racine: Path | None = None,
              ouvrir: bool = False, mention: str | None = None, pages_par_section: bool = False,
              navigation: list[str] | tuple[str, ...] | None = None) -> Path:
    """Rend `chemin_md` en page HTML et renvoie le chemin de la page.

    chemin_html        : page à écrire (défaut : même nom en .html à côté du markdown) ; dossiers créés au besoin.
    titre              : titre de la page (défaut : directive `<!-- titre: … -->`, sinon premier `# ` du markdown,
                         sinon le nom du fichier).
    racine             : dossier où chercher `sources/photos/` et les documents voisins (défaut : dossier du markdown).
    ouvrir             : ouvrir la page dans le navigateur après l'écriture.
    mention            : phrase affichée en pied de page (ex. « Valeurs indicatives, sélection finale chez le
                         fournisseur. ») ; défaut : directive `<!-- mention: … -->` du markdown, sinon aucune.
    pages_par_section  : à l'impression, saut de page avant chaque `## ` (sauf le premier).
    navigation         : documents (.md, relatifs à la racine) à lier en haut de page ; défaut : DOCUMENTS_DOSSIER
                         présents dans la racine ; [] pour aucun lien.
    """
    chemin_md = Path(chemin_md)
    sortie = Path(chemin_html) if chemin_html else chemin_md.with_suffix(".html")
    racine = (Path(racine) if racine else chemin_md.parent).resolve()
    dossier_html = sortie.resolve().parent

    directives, texte = lire_directives(chemin_md.read_text(encoding="utf-8"))
    titre = titre if titre is not None else directives.get("titre") or None
    mention = mention if mention is not None else directives.get("mention") or None
    corps = markdown.markdown(enrichir(texte, carte_photos(racine, dossier_html)), extensions=EXTENSIONS)
    corps = envelopper_tableaux(marquer_statuts(cases_a_cocher(corps)))

    # En-tête : le premier titre `# ` du document sort du corps pour devenir le titre de la page.
    m = RE_H1.search(corps)
    h1 = m.group(1).strip() if m else None
    if m:
        corps = corps[:m.start()] + corps[m.end():]
    texte_h1 = html.unescape(RE_BALISE.sub("", h1)).strip() if h1 else None
    titre_page = titre or texte_h1 or chemin_md.stem
    titre_html = html.escape(titre) if titre else (h1 or html.escape(chemin_md.stem))
    sous_titre = f'<p class="sous-titre">{h1}</p>' if titre and h1 and texte_h1 != titre else ""
    date = datetime.now().strftime("%d/%m/%Y à %H:%M")

    noms = DOCUMENTS_DOSSIER if navigation is None else navigation
    liens = []
    for n in noms:
        if (racine / n).exists():
            cible = (racine / n).with_suffix(".html")
            ici = ' class="ici"' if cible == sortie.resolve() else ""
            liens.append(f'<a href="{html.escape(lien_relatif(cible, dossier_html))}"{ici}>{html.escape(Path(n).stem)}</a>')
    nav = (f'<div class="nav">Dossier <code>{html.escape(racine.name)}</code> · {" ".join(liens)}</div>\n'
           if liens else "")

    astuce = " Cliquer une vignette ouvre la photo en taille réelle." if 'class="vignette"' in corps else ""
    pied_mention = f'<p class="mention">{html.escape(mention)}</p>' if mention else ""
    classe_body = ' class="pages-par-section"' if pages_par_section else ""

    page = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titre_page)}</title><style>{CSS}</style></head>
<body{classe_body}><main>
{nav}<header class="entete"><h1>{titre_html}</h1>{sous_titre}<p class="genere">Générée le {date}</p></header>
<article>
{corps}
</article>
<footer class="pied">{pied_mention}<p>Vue générée depuis <code>{html.escape(chemin_md.name)}</code> par <code>rendu_html.py</code>. Le fichier markdown reste la référence ; cette page se régénère à chaque modification.{astuce}</p></footer>
</main><script>{SCRIPT}</script></body></html>
"""
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(page, encoding="utf-8", newline="\n")
    if ouvrir:
        ouvrir_page(sortie)
    return sortie


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cible", help="fichier .md à rendre, ou dossier d'installation (dossier.md, 1-existant.md, 2-dimensionnement.md)")
    ap.add_argument("--ouvrir", action="store_true", help="ouvrir la page (ou celle de l'étape la plus avancée) dans le navigateur")
    ap.add_argument("--sortie", help="chemin du .html (un seul fichier ; défaut : à côté du .md)")
    ap.add_argument("--titre", help="titre de la page (un seul fichier ; défaut : premier titre # du markdown)")
    ap.add_argument("--racine", help="dossier où chercher sources/photos/ (défaut : dossier du .md)")
    ap.add_argument("--mention", help="phrase en pied de page, ex. « Valeurs indicatives, sélection finale chez le fournisseur. »")
    ap.add_argument("--pages-par-section", action="store_true", help="à l'impression, saut de page avant chaque section ##")
    a = ap.parse_args(argv)

    cible = Path(a.cible)
    if cible.is_file():
        fichiers = [cible]
    elif cible.is_dir():
        fichiers = [cible / f for f in DOCUMENTS_DOSSIER if (cible / f).exists()]
    else:
        raise SystemExit(f"Introuvable : {cible}")
    if not fichiers:
        raise SystemExit(f"Aucun fichier markdown à rendre dans {cible}")
    if len(fichiers) > 1 and (a.sortie or a.titre):
        raise SystemExit("--sortie et --titre ne s'utilisent qu'avec un seul fichier .md")
    racine = Path(a.racine) if a.racine else (cible if cible.is_dir() else None)
    sorties = [convertir(f, Path(a.sortie) if a.sortie else None, a.titre, racine, mention=a.mention,
                         pages_par_section=a.pages_par_section) for f in fichiers]
    for s in sorties:
        print(f"Rendu : {s}")
    if a.ouvrir:
        ouvrir_page(sorties[-1])


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from shared.savoir import sortie_utf8
    sortie_utf8()
    main()
