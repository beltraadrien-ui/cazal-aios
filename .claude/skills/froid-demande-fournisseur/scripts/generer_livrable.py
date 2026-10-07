"""froid-demande-fournisseur — étape 3 : rendre la demande de prix (PDF unique + mail court) depuis demande.json.

Entrée : <dossier>/3-demande-fournisseur/<vN>/demande.json, écrit par assembler.py puis relu par Claude
(schéma commun : en-tête, émetteur, site, contexte, tableaux déjà rendus en texte, demande a) à f), postes avec
leurs photos, annexes, mail). Les chemins de photos sont relatifs à la racine du dossier d'installation.

Sorties, dans <dossier>/3-demande-fournisseur/<vN>/ :
    img/<photo>.jpg             photos redimensionnées (800 px de large au plus, JPEG qualité 80) ; les originaux
                                de sources/photos/ ne sont jamais touchés
    demande-<vN>.html           page A4 (gabarit templates/demande.html, CSS d'impression, chemins relatifs vers img/)
    demande-<vN>.pdf            impression de la page par Edge en mode sans tête (Chrome en repli)
    mail-<variante>.txt         objet en première ligne, ligne vide, salutation, corps, formule, signature
    mail-<variante>.html        le même texte en paragraphes, pour le copier-coller (aucun tableau)

Le PDF est vérifié avec PyMuPDF (nombre de pages, poids) ; un avertissement est affiché au-delà de 5 Mo.
Rien n'est calculé ni réécrit ici : chaque texte et chaque chiffre vient tel quel de demande.json (échappé), avec la
seule typographie du rendu (page, PDF et mail ; demande.json n'est jamais modifié) : « CO2 » → « CO₂ », espace
insécable après « et avant », signe moins (U+2212) devant une température négative. « à confirmer » n'est coloré que
dans les cellules de tableau (et la puissance retenue d'un poste), jamais dans le texte courant ni les légendes. Les
annotations de lecture de l'étape 1 (« (Wilo ?) », « (douteux) », « lecture : … ») sont retirées des légendes et des
lignes « Existant » au rendu (sans_annotations) : une plaque n'y garde que ce qui est lu avec certitude.

Usage, depuis la racine du dépôt :
    python .claude/skills/froid-demande-fournisseur/scripts/generer_livrable.py <dossier> <vN> [--ouvrir] [--sans-pdf]
    <dossier>  : chemin du dossier d'installation, ou son nom dans dimensionnement/dossiers/
    <vN>       : v1, v2… (variante grossiste) ou vN-<suffixe> (ex. v1-fabricant), comme le dossier écrit par assembler.py
    --ouvrir   : ouvre le PDF (ou la page HTML avec --sans-pdf) et le mail HTML
    --sans-pdf : s'arrête à la page HTML et au mail (pas de navigateur)

Python :
    from generer_livrable import generer
    resultat = generer(dossier, "v1", pdf=True, ouvrir=False)
    # {"html", "pdf", "mail_txt", "mail_html", "images", "pages", "mo", "navigateur", "commande", "avertissements"}

Dépendances : Pillow pour les photos (repli : PyMuPDF), PyMuPDF pour vérifier le PDF, Edge ou Chrome déjà
présent sur le PC pour l'impression. Mini-moteur de gabarit maison (aucune bibliothèque de gabarits) :
    {{cle}} texte échappé · {{{cle}}} HTML déjà préparé · {{a.b}} clé imbriquée · {{.}} élément courant
    {{#cle}}…{{/cle}} bloc répété (liste) ou conditionnel (valeur non vide) · {{^cle}}…{{/cle}} si vide
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import quote

import pymupdf

try:
    from PIL import Image, ImageOps
except ImportError:  # repli : PyMuPDF redimensionne aussi (sans redressement EXIF)
    Image = ImageOps = None

ROOT = Path(__file__).resolve().parents[4]          # racine du dépôt (…/.claude/skills/<skill>/scripts/)
DOSSIERS = ROOT / "dimensionnement" / "dossiers"
GABARIT = Path(__file__).resolve().parents[1] / "templates" / "demande.html"
SOUS_DOSSIER = "3-demande-fournisseur"

LARGEUR_MAX = 800            # px
QUALITE_JPEG = 80
SEUIL_MO = 5.0               # au-delà : avertissement (le contrôle bloquant est dans controler.py)
OCTETS_PAR_MO = 1024 * 1024
DELAI_IMPRESSION = 90        # s, par essai d'options
MENTION_DEFAUT = "Valeurs indicatives, sélection finale chez le fournisseur."

TITRES_CHAPITRES = {
    "contexte": "Contexte",
    "chambres": "Les chambres à traiter",
    "production": "La production frigorifique existante",
    "evaporateurs": "Les évaporateurs en place",
    "demande": "Notre demande",
    "postes": "Le détail par poste",
    "annexes": "Annexes",
}
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre")

# Navigateurs : Edge d'abord (présent sur tout Windows récent), Chrome en repli.
EMPLACEMENTS = {
    "Edge": (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    "Chrome": (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
               r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
               os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe")),
}
EXECUTABLES = {"Edge": "msedge.exe", "Chrome": "chrome.exe"}
# Essais successifs : nouveau mode sans tête, puis l'ancien (navigateurs plus vieux).
ESSAIS_SANS_TETE = ("--headless=new", "--headless")
OPTIONS_COMMUNES = ("--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf-no-header", "--no-first-run",
                    "--no-default-browser-check", "--disable-extensions")

RE_VERSION = re.compile(r"^v\d+(?:-[a-z0-9]+)*$")      # v1, v2… ou vN-<suffixe> (v1-fabricant)
RE_A_CONFIRMER = re.compile(r"à[ \u00a0]confirmer", re.I)
RE_HYP = re.compile(r"\(hyp\.?\)")
RE_PUCE = re.compile(r"^\s*[-•*]\s+")
RE_CO2 = re.compile(r"(?<![A-Za-z0-9])CO2(?![\w])")                 # pas « tCO2e » ni « kgCO2e/kg »
_ESP = "[ \u00a0\u202f]*"
RE_MOINS_TEMPERATURE = re.compile(                                  # « -30 °C », « -30 / -10 °C », « -30/-10 °C »
    rf"(?<![\w.,\-−])-(?=\d+(?:,\d+)?(?:{_ESP}°C|{_ESP}/{_ESP}[-−+]?\d+(?:,\d+)?{_ESP}°C))")
CLES_SANS_TYPOGRAPHIE = ("fichier", "version", "date", "variante")
# Annotations de lecture de l'étape 1 : valeur douteuse (l'élément part avec elle) ou remarque (seule la remarque part).
RE_VALEUR_DOUTEUSE = re.compile(r"^\s*(?:lecture\s+)?(?:douteu(?:x|se)s?|un chiffre masqu[ée]e?)\s*$", re.I)
RE_REMARQUE_LECTURE = re.compile(r"\?|douteu|masqu|illisible|partiellement lisible", re.I)
PLAQUE_PARTIELLE = "plaque partiellement lisible"


class ErreurLivrable(Exception):
    """Erreur expliquée en français (dossier, demande.json, photo ou navigateur)."""


class ErreurGabarit(ErreurLivrable):
    """Gabarit mal formé ou clé inconnue."""


# ── Mini-moteur de gabarit ───────────────────────────────────────────────────────────────────────────

RE_MARQUE = re.compile(r"\{\{\{\s*([\w.]+)\s*\}\}\}|\{\{\s*([#^/]?)\s*([\w.]+)\s*\}\}")


def _analyser(gabarit: str) -> list:
    """Découpe le gabarit en arbre : texte, ("var", nom), ("brut", nom), ("#" ou "^", nom, enfants)."""
    racine: list = []
    pile: list[tuple[str, list]] = [("", racine)]
    pos = 0
    for m in RE_MARQUE.finditer(gabarit):
        if m.start() > pos:
            pile[-1][1].append(gabarit[pos:m.start()])
        pos = m.end()
        if m.group(1):
            pile[-1][1].append(("brut", m.group(1)))
            continue
        sigle, nom = m.group(2), m.group(3)
        if sigle in ("#", "^"):
            noeud = (sigle, nom, [])
            pile[-1][1].append(noeud)
            pile.append((nom, noeud[2]))
        elif sigle == "/":
            if len(pile) == 1 or pile[-1][0] != nom:
                ouvert = pile[-1][0] or "aucun bloc ouvert"
                raise ErreurGabarit(f"Gabarit : fermeture {{{{/{nom}}}}} inattendue ({ouvert}).")
            pile.pop()
        else:
            pile[-1][1].append(("var", nom))
    if len(pile) > 1:
        raise ErreurGabarit(f"Gabarit : bloc {{{{#{pile[-1][0]}}}}} jamais fermé.")
    if pos < len(gabarit):
        racine.append(gabarit[pos:])
    return racine


def _chercher(nom: str, pile: list):
    """Valeur de `nom` (« a.b » admis, « . » = élément courant), cherchée du contexte le plus proche au plus large."""
    if nom == ".":
        return pile[-1]
    tete, *reste = nom.split(".")
    for ctx in reversed(pile):
        if isinstance(ctx, dict) and tete in ctx:
            valeur = ctx[tete]
            for cle in reste:
                if not isinstance(valeur, dict) or cle not in valeur:
                    raise ErreurGabarit(f"Gabarit : clé inconnue {nom!r}.")
                valeur = valeur[cle]
            return valeur
    raise ErreurGabarit(f"Gabarit : clé inconnue {nom!r}.")


def _texte(valeur) -> str:
    return "" if valeur is None else str(valeur)


def _rendre_noeuds(noeuds: list, pile: list) -> str:
    morceaux = []
    for n in noeuds:
        if isinstance(n, str):
            morceaux.append(n)
        elif n[0] == "var":
            morceaux.append(html.escape(_texte(_chercher(n[1], pile))))
        elif n[0] == "brut":
            morceaux.append(_texte(_chercher(n[1], pile)))
        else:
            sigle, nom, enfants = n
            valeur = _chercher(nom, pile)
            if sigle == "^":
                if not valeur:
                    morceaux.append(_rendre_noeuds(enfants, pile))
            elif isinstance(valeur, (list, tuple)):
                for element in valeur:
                    morceaux.append(_rendre_noeuds(enfants, pile + [element]))
            elif valeur:
                morceaux.append(_rendre_noeuds(enfants, pile + [valeur]))
    return "".join(morceaux)


def rendre(gabarit: str, contexte: dict) -> str:
    """Remplit `gabarit` avec `contexte` (syntaxe décrite en tête du module). Clé absente → ErreurGabarit."""
    return _rendre_noeuds(_analyser(gabarit), [contexte])


# ── Textes ───────────────────────────────────────────────────────────────────────────────────────────

def typographie(texte: str) -> str:
    """Typographie du rendu : « CO2 » → « CO₂ », espace insécable après « et avant », signe moins (U+2212) devant
    une température négative. Les chiffres eux-mêmes ne changent pas."""
    t = RE_CO2.sub("CO₂", texte)
    t = re.sub(r"«[ \u00a0\u202f]*", "«\u00a0", t)
    t = re.sub(r"[ \u00a0\u202f]*»", "\u00a0»", t)
    return RE_MOINS_TEMPERATURE.sub("−", t)


def _decouper(texte: str, separateur: str) -> list[str]:
    """Découpe sur le séparateur hors parenthèses et guillemets."""
    morceaux, courant, prof, i = [], "", 0, 0
    while i < len(texte):
        if prof == 0 and texte.startswith(separateur, i):
            morceaux.append(courant)
            courant, i = "", i + len(separateur)
            continue
        ch = texte[i]
        prof = prof + 1 if ch in "(«" else max(0, prof - 1) if ch in ")»" else prof
        courant += ch
        i += 1
    morceaux.append(courant)
    return [m.strip() for m in morceaux if m.strip()]


def _sans_accents(texte: str) -> str:
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()


def sans_annotations(texte, plaque: bool = True, separateur: str = " · ") -> str:
    """Légende (éléments séparés par « · ») ou ligne « Existant » (« Libellé : a, b, c ») sans les annotations de
    lecture de l'étape 1 : « lecture : … » (et ce qu'elle désigne : « sûre sauf la désignation » retire la désignation),
    valeur suivie de « (douteux) », « (lecture douteuse) », « (un chiffre masqué) », élément « illisible » ou avec « ? »
    (l'élément part) ; remarque entre parenthèses avec « ? » ou « illisible » (seule la remarque part, ex. « (Wilo ?) »).
    plaque=True : « plaque partiellement lisible » est ajouté quand quelque chose a été retiré."""
    t = _texte(texte)
    if not RE_REMARQUE_LECTURE.search(t) and not re.search(r"(?i)\blecture\s*:", t):
        return t
    retire = False
    etiquette = ""
    if separateur == ", ":
        parties = _decouper(t, " : ")
        if len(parties) > 1:
            etiquette, t = parties[0], " : ".join(parties[1:])
    # 1. la note « lecture : … » (dernier élément) et ce qu'elle désigne comme douteux
    elements, designes = [], []
    for el in _decouper(t, " · " if separateur == " · " else ", "):
        m = re.match(r"(?i)^lecture\s*:\s*(.*)$", el)
        if m:
            note = _sans_accents(m.group(1))
            retire = retire or not note.startswith("sure") or "sauf" in note
            designes += re.findall(r"sauf (?:le |la |les |l')?(\w+)", note) + \
                re.findall(r"(\w+) douteu", note) + re.findall(r"\((\w+)\)", note)
            if separateur == ", ":
                break                                         # ligne « Existant » : la note finit la ligne
            continue
        elements.append(el)
    designes = [d for d in designes if len(d) >= 3 and not d.startswith(("douteu", "illisible"))]

    def nettoyer(el: str) -> str | None:
        nonlocal retire
        if any(_sans_accents(el).startswith(d) for d in designes):
            retire = True
            return None
        douteux = False

        def parenthese(m):
            nonlocal douteux, retire
            if RE_VALEUR_DOUTEUSE.match(m.group(1)):
                douteux = True
                return ""
            if RE_REMARQUE_LECTURE.search(m.group(1)):
                retire = True
                return ""
            return m.group(0)
        el = re.sub(r"\s*\(([^()]*)\)", parenthese, el).strip()
        if douteux or RE_REMARQUE_LECTURE.search(el):
            retire = True
            return None
        return el

    gardes = []
    for el in elements:
        if separateur == " · ":
            sous = [x for x in (nettoyer(s) for s in _decouper(el, ", ")) if x]
            if sous:
                gardes.append(", ".join(sous))
        elif (x := nettoyer(el)):
            gardes.append(x)
    if plaque and retire:
        gardes.append(PLAQUE_PARTIELLE)
    corps = separateur.join(gardes)
    if etiquette:
        return f"{etiquette} : {corps}" if corps else etiquette
    return corps[:1].upper() + corps[1:] if corps else ""


def typographier(obj, cle: str = ""):
    """Copie de demande.json avec la typographie du rendu sur chaque texte (sauf chemins, version, date, variante)."""
    if isinstance(obj, dict):
        return {k: typographier(v, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [typographier(v, cle) for v in obj]
    if isinstance(obj, str) and cle not in CLES_SANS_TYPOGRAPHIE:
        return typographie(obj)
    return obj


def echapper(texte) -> str:
    return html.escape(_texte(texte))


def marquer(texte, confirmer: bool = True) -> str:
    """Texte échappé, « (hyp.) » en petit, « à confirmer » en orange (toute la cellule si elle commence ainsi) ;
    confirmer=False (texte courant, listes, légendes) : « à confirmer » n'est pas coloré.
    Les espaces insécables restent tels quels."""
    t = echapper(texte).strip()
    if not t:
        return ""
    if not confirmer:
        return RE_HYP.sub(r'<span class="hyp">\g<0></span>', t)
    if RE_A_CONFIRMER.match(t):
        return f'<span class="a-confirmer">{t}</span>'
    t = RE_HYP.sub(r'<span class="hyp">\g<0></span>', t)
    return RE_A_CONFIRMER.sub(r'<span class="a-confirmer">\g<0></span>', t)


def statut_html(statut) -> str:
    """Statut discret : « (hyp.) » en petit gris, « à confirmer » en orange, le reste en petit entre parenthèses."""
    s = _texte(statut).strip()
    if not s:
        return ""
    if RE_A_CONFIRMER.search(s):
        return f'<span class="a-confirmer">{echapper(s)}</span>'
    if s.lower().lstrip("(").startswith("hyp"):
        s = "(hyp.)"
    elif not s.startswith("("):
        s = f"({s})"
    return f'<span class="statut">{echapper(s)}</span>'


def deja_marque(texte, statut) -> bool:
    """Vrai si `texte` porte déjà la marque de `statut` (« (hyp.) », « à confirmer ») : ne pas la répéter à côté."""
    s, t = _texte(statut).strip(), _texte(texte)
    if s.lower().lstrip("(").startswith("hyp"):
        return bool(RE_HYP.search(t))
    return bool(RE_A_CONFIRMER.search(s)) and bool(RE_A_CONFIRMER.search(t))


def paragraphes_html(texte) -> str:
    """Paragraphes séparés par une ligne vide → <p> (retours à la ligne gardés) ; bloc de lignes « - … » → liste."""
    blocs = [b for b in re.split(r"\n\s*\n", _texte(texte).replace("\r\n", "\n")) if b.strip()]
    sortie = []
    for bloc in blocs:
        lignes = [l for l in bloc.split("\n") if l.strip()]
        if all(RE_PUCE.match(l) for l in lignes):
            items = "".join(f"<li>{marquer(RE_PUCE.sub('', l), confirmer=False)}</li>" for l in lignes)
            sortie.append(f"<ul>{items}</ul>")
        else:
            sortie.append("<p>" + "<br>".join(marquer(l, confirmer=False) for l in lignes) + "</p>")
    return "\n".join(sortie)


def texte_css(texte) -> str:
    """Chaîne sûre pour `content: "…"` dans une feuille de style (guillemets, barres obliques, chevrons)."""
    t = " ".join(_texte(texte).split())
    return t.replace("\\", "\\\\").replace('"', '\\"').replace("<", "\\3c ").replace(">", "\\3e ")


def date_longue(iso: str) -> str:
    """« 2026-10-07 » → « 7 octobre 2026 » (texte d'origine si la date est illisible)."""
    try:
        d = date.fromisoformat(_texte(iso).strip())
    except ValueError:
        return _texte(iso)
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def slug(texte: str) -> str:
    t = unicodedata.normalize("NFKD", _texte(texte)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower() or "x"


# ── Photos ───────────────────────────────────────────────────────────────────────────────────────────

def redimensionner(source: Path, cible: Path, largeur: int = LARGEUR_MAX, qualite: int = QUALITE_JPEG,
                   moteur: str | None = None) -> tuple[int, int]:
    """Copie `source` en JPEG dans `cible` : largeur ≤ `largeur` px (jamais agrandie), qualité `qualite`,
    orientation EXIF appliquée, transparence sur fond blanc. Renvoie (largeur, hauteur) de la copie.
    moteur : "pillow" (défaut si installé) ou "pymupdf" (repli)."""
    source, cible = Path(source), Path(cible)
    if source.resolve() == cible.resolve():
        raise ErreurLivrable(f"Refus d'écraser la photo d'origine : {source}")
    cible.parent.mkdir(parents=True, exist_ok=True)
    moteur = moteur or ("pillow" if Image is not None else "pymupdf")
    if moteur == "pillow":
        if Image is None:
            raise ErreurLivrable("Pillow n'est pas installé (pip install pillow), ou utiliser moteur='pymupdf'.")
        with Image.open(source) as im:
            im = ImageOps.exif_transpose(im)
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                im = im.convert("RGBA")
                fond = Image.new("RGB", im.size, "white")
                fond.paste(im, mask=im.split()[-1])
                im = fond
            elif im.mode != "RGB":
                im = im.convert("RGB")
            if im.width > largeur:
                im = im.resize((largeur, max(1, round(im.height * largeur / im.width))), Image.LANCZOS)
            im.save(cible, "JPEG", quality=qualite, optimize=True)
            return im.size
    pix = pymupdf.Pixmap(str(source))
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    if pix.colorspace is None or pix.colorspace.n not in (1, 3):
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    if pix.width > largeur:
        pix = pymupdf.Pixmap(pix, largeur, max(1, round(pix.height * largeur / pix.width)), None)
    pix.save(str(cible), output="jpg", jpg_quality=qualite)
    return pix.width, pix.height


def photos_referencees(demande: dict) -> list[str]:
    """Chemins de photos de demande.json (postes puis vues d'ensemble), sans doublon, dans l'ordre."""
    vus: list[str] = []
    for poste in demande.get("postes") or []:
        for p in poste.get("photos") or []:
            if p.get("fichier") and p["fichier"] not in vus:
                vus.append(p["fichier"])
    for p in (demande.get("annexes") or {}).get("vues_ensemble") or []:
        if p.get("fichier") and p["fichier"] not in vus:
            vus.append(p["fichier"])
    return vus


def preparer_photos(demande: dict, dossier: Path, dossier_version: Path) -> dict[str, str]:
    """Redimensionne chaque photo référencée dans <vN>/img/ ; renvoie {chemin de demande.json → « img/x.jpg »}.
    Une photo introuvable arrête tout (liste complète dans le message)."""
    fichiers = photos_referencees(demande)
    manquantes = [f for f in fichiers if not (dossier / f).is_file()]
    if manquantes:
        raise ErreurLivrable("Photos introuvables (chemins relatifs au dossier " + str(dossier) + ") :\n  "
                             + "\n  ".join(manquantes))
    carte: dict[str, str] = {}
    pris: set[str] = set()
    for f in fichiers:
        chemin = Path(f)
        nom = slug(chemin.stem)
        if nom in pris:
            nom = f"{slug(chemin.parent.name)}-{nom}"
        base, i = nom, 2
        while nom in pris:
            nom, i = f"{base}-{i}", i + 1
        pris.add(nom)
        redimensionner(dossier / f, dossier_version / "img" / f"{nom}.jpg")
        carte[f] = f"img/{quote(nom)}.jpg"
    return carte


# ── Vue (données prêtes pour le gabarit) ─────────────────────────────────────────────────────────────

def _rangees(photos: list[dict], carte: dict[str, str], plaques: bool = True) -> list[dict]:
    """Photos par rangées de deux (une rangée n'est jamais coupée par un saut de page) ; légendes sans les annotations
    de lecture (plaques=True : photos de plaques des postes, False : vues d'ensemble)."""
    items = []
    for p in photos:
        if p.get("fichier"):
            legende = sans_annotations(p.get("legende"), plaque=plaques)
            items.append({"src": carte[p["fichier"]], "legende_html": marquer(legende, confirmer=False),
                          "alt": legende, "classe": slug(p.get("type") or "photo")})
    return [{"photos": items[i:i + 2]} for i in range(0, len(items), 2)]


def _tableau(lignes: list[dict] | None, cles: tuple[str, ...]) -> list[dict]:
    return [{c: marquer(l.get(c)) for c in cles} for l in (lignes or [])]


def preparer_vue(demande: dict, carte: dict[str, str]) -> dict:
    """Transforme demande.json en données du gabarit : textes échappés et marqués, numéros de chapitres
    (le 4 disparaît si `evaporateurs` est null, les suivants se renumérotent), rangées de photos."""
    titre = _texte(demande.get("titre")) or "Demande de prix"
    version = _texte(demande.get("version"))
    date_iso = _texte(demande.get("date"))
    mention = _texte(demande.get("mention")) or MENTION_DEFAUT
    parties = [p.strip() for p in titre.split(" — ") if p.strip()]
    sous_titre = " — ".join(p for p in parties[1:] if p not in (date_iso, version))

    emetteur = {k: _texte((demande.get("emetteur") or {}).get(k)).strip() for k in
                ("societe", "contact", "telephone", "mail", "adresse")}
    emetteur["coordonnees"] = " · ".join(x for x in (emetteur["telephone"], emetteur["mail"]) if x)
    site = demande.get("site") or {}
    lieu = ", ".join(x for x in (_texte(site.get("nom")), _texte(site.get("localite"))) if x.strip())
    if lieu.casefold() == sous_titre.casefold():
        lieu = ""                                   # déjà dit par le sous-titre de la page de garde
    dest = demande.get("destinataire")
    if dest:
        personne = " ".join(x for x in (_texte(dest.get("prenom")), _texte(dest.get("nom"))) if x.strip())
        destinataire = " — ".join(x for x in (personne, _texte(dest.get("societe"))) if x.strip())
    else:
        destinataire = "Grossistes (consultation)"

    cles = [c for c in TITRES_CHAPITRES if c != "evaporateurs" or demande.get("evaporateurs") is not None]
    n = {c: str(i) for i, c in enumerate(cles, 1)}

    chambres = demande.get("chambres") or {}
    production = demande.get("production") or {}
    lignes_prod = []
    for l in production.get("lignes") or []:
        ligne = {c: marquer(l.get(c)) for c in ("poste", "compresseurs", "volume_balaye", "puissance")}
        ligne["statut_html"] = statut_html(l.get("statut"))
        lignes_prod.append(ligne)
    sous_totaux = [{"libelle": marquer(s.get("libelle")), "puissance": marquer(s.get("puissance")),
                    "statut_html": statut_html(s.get("statut"))} for s in production.get("sous_totaux") or []]
    avec_statut = any(l["statut_html"] for l in lignes_prod + sous_totaux)
    avec_a_confirmer = any("a-confirmer" in v for l in lignes_prod + sous_totaux for v in l.values())

    evap = demande.get("evaporateurs")
    vue_evap = None
    if evap is not None:
        vue_evap = {"lignes": _tableau(evap.get("lignes"), ("chambre", "modele", "annee", "puissance")),
                    "note_html": paragraphes_html(evap.get("note"))}

    dem = demande.get("demande") or {}
    titre_demande = _texte(dem.get("titre")) or TITRES_CHAPITRES["demande"]
    points = [{"lettre": _texte(p.get("lettre")).rstrip(")"), "titre": _texte(p.get("titre")),
               "texte_html": paragraphes_html(p.get("texte")),
               "sous_points": [marquer(s, confirmer=False) for s in p.get("sous_points") or [] if _texte(s).strip()]}
              for p in dem.get("points") or []]
    for p in points:
        p["avec_sous_points"] = bool(p["sous_points"])

    postes = []
    for i, p in enumerate(demande.get("postes") or [], 1):
        puissance = marquer(p.get("puissance"))
        statut = "" if deja_marque(p.get("puissance"), p.get("statut")) else statut_html(p.get("statut"))
        existant = [marquer(sans_annotations(e, separateur=", "), confirmer=False)
                    for e in p.get("existant") or [] if _texte(e).strip()]
        postes.append({
            "ancre": "poste-" + slug(p.get("id") or str(i)), "numero": f"{n['postes']}.{i}",
            "titre": _texte(p.get("titre")) or f"Poste {i}", "dessert": _texte(p.get("dessert")),
            "existant": existant, "avec_existant": bool(existant),
            "puissance_html": (puissance + (" " + statut if statut else "")) if puissance else "",
            "remplacement_html": paragraphes_html(p.get("remplacement")),
            "rangees": _rangees(p.get("photos") or [], carte),
        })

    titres = dict(TITRES_CHAPITRES, demande=titre_demande)
    sommaire = [{"numero": n[c], "titre": titres[c],
                 "sous": [{"numero": p["numero"], "titre": p["titre"]} for p in postes] if c == "postes" else []}
                for c in cles]
    for s in sommaire:
        s["a_sous"] = bool(s["sous"])
    pieces = [_texte(x) for x in (demande.get("annexes") or {}).get("pieces_jointes") or [] if _texte(x).strip()]

    annexes = demande.get("annexes") or {}
    return {
        "titre": titre, "titre_principal": parties[0] if parties else titre, "sous_titre": sous_titre,
        "titre_css": texte_css(titre), "mention": mention, "mention_css": texte_css(mention),
        "date_longue": date_longue(date_iso), "version": version, "destinataire": destinataire,
        "lieu": lieu, "reference": " – ".join(x for x in (_texte(site.get("nom")).strip(),
                                                           _texte(site.get("localite")).strip()) if x),
        "emetteur": emetteur,
        "sommaire": sommaire, "n": n, "t": titres,
        "contexte_html": paragraphes_html((demande.get("contexte") or {}).get("texte")),
        "chambres": {"lignes": _tableau(chambres.get("lignes"),
                                        ("chambre", "regime", "surface", "volume", "nb_evaporateurs")),
                     "note_html": paragraphes_html(chambres.get("note"))},
        "production": {"lignes": lignes_prod, "sous_totaux": sous_totaux, "avec_statut": avec_statut,
                       "avec_a_confirmer": avec_a_confirmer,
                       "note_html": paragraphes_html(production.get("note"))},
        "evaporateurs": vue_evap,
        "demande": {"intro_html": paragraphes_html(dem.get("intro")), "points": points,
                    "resume_html": paragraphes_html(dem.get("resume"))},
        "postes": postes,
        "annexes": {"rangees": _rangees(annexes.get("vues_ensemble") or [], carte, plaques=False),
                    "plan_implantation": _texte(annexes.get("plan_implantation")) or "à suivre",
                    "pieces_jointes": pieces, "avec_pieces": bool(pieces)},
    }


# ── Mail ─────────────────────────────────────────────────────────────────────────────────────────────

def blocs_mail(mail: dict) -> tuple[str, list[str]]:
    """(objet, paragraphes) : salutation, paragraphes du corps, formule, signature (vides ignorés)."""
    corps = [b.strip() for b in re.split(r"\n\s*\n", _texte(mail.get("corps")).replace("\r\n", "\n")) if b.strip()]
    blocs = [_texte(mail.get("salutation")).strip(), *corps, _texte(mail.get("formule")).strip(),
             _texte(mail.get("signature")).strip()]
    return _texte(mail.get("objet")).strip(), [b for b in blocs if b]


def ecrire_mail(demande: dict, dossier_version: Path) -> tuple[Path, Path]:
    """Écrit mail-<variante>.txt (objet, ligne vide, texte) et mail-<variante>.html (paragraphes, aucun tableau)."""
    variante = slug(demande.get("variante") or "grossiste")
    objet, blocs = blocs_mail(demande.get("mail") or {})
    txt = dossier_version / f"mail-{variante}.txt"
    txt.write_text(objet + "\n\n" + "\n\n".join(blocs) + "\n", encoding="utf-8", newline="\n")
    paragraphes = "\n".join("<p>" + "<br>".join(html.escape(l) for l in b.split("\n")) + "</p>" for b in blocs)
    page = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mail — {html.escape(objet)}</title>
<style>
body {{ margin: 0; padding: 28px 16px 48px; background: #fff; color: #1a1a1a; font: 15px/1.55 "Segoe UI", Arial, sans-serif; }}
main {{ max-width: 720px; margin: 0 auto; }}
.aide {{ margin: 0 0 4px; font-size: 12px; color: #6b6b6b; }}
.objet {{ margin: 0 0 20px; padding-bottom: 14px; border-bottom: 1px solid #d0d0d0; font-weight: 600; }}
.corps p {{ margin: 0 0 14px; }}
</style></head>
<body><main>
<p class="aide">Objet (à copier dans le champ Objet) :</p>
<p class="objet">{html.escape(objet)}</p>
<p class="aide">Texte du mail (à copier dans le corps, joindre le PDF) :</p>
<div class="corps">
{paragraphes}
</div>
</main></body></html>
"""
    page_html = dossier_version / f"mail-{variante}.html"
    page_html.write_text(page, encoding="utf-8", newline="\n")
    return txt, page_html


# ── Impression PDF ───────────────────────────────────────────────────────────────────────────────────

def _registre(executable: str) -> list[str]:
    """Chemins déclarés dans « App Paths » du registre Windows (machine puis utilisateur)."""
    try:
        import winreg
    except ImportError:
        return []
    chemins = []
    for ruche in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(ruche, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{executable}") as cle:
                chemins.append(winreg.QueryValue(cle, None))
        except OSError:
            pass
    return chemins


def trouver_navigateur() -> tuple[str, Path] | None:
    """(nom, exécutable) d'Edge, sinon de Chrome ; None si aucun n'est installé."""
    for nom, chemins in EMPLACEMENTS.items():
        for c in [*chemins, *_registre(EXECUTABLES[nom])]:
            if c and Path(c).is_file():
                return nom, Path(c)
        trouve = shutil.which(EXECUTABLES[nom])
        if trouve:
            return nom, Path(trouve)
    return None


def _pdf_pret(pdf: Path, delai: float) -> bool:
    """Attend que le PDF existe, ne grossisse plus et s'ouvre (le lanceur d'Edge rend la main tout de suite)."""
    fin, taille = time.monotonic() + delai, -1
    while time.monotonic() < fin:
        if pdf.exists():
            t = pdf.stat().st_size
            if t > 0 and t == taille:
                try:
                    with pymupdf.open(pdf) as d:
                        if d.page_count > 0:
                            return True
                except Exception:
                    pass
            taille = t
        time.sleep(0.4)
    return False


def imprimer_pdf(page_html: Path, pdf: Path, delai: float = DELAI_IMPRESSION) -> tuple[str, list[str]]:
    """Imprime `page_html` en PDF avec Edge (ou Chrome) sans tête ; renvoie (navigateur, commande utilisée).
    Profil temporaire dédié (n'interfère pas avec un Edge ouvert) ; essaie --headless=new puis --headless."""
    trouve = trouver_navigateur()
    if not trouve:
        raise ErreurLivrable("Ni Edge ni Chrome trouvé sur ce PC : impossible d'imprimer le PDF. "
                             "Relancer avec --sans-pdf et imprimer la page HTML en PDF à la main (Ctrl+P).")
    nom, exe = trouve
    pdf, page_html = Path(pdf).resolve(), Path(page_html).resolve()
    try:
        pdf.unlink(missing_ok=True)
    except PermissionError:
        raise ErreurLivrable(f"Le PDF est ouvert dans un lecteur : le fermer puis relancer ({pdf}).") from None
    profil = Path(tempfile.mkdtemp(prefix="froid-demande-pdf-"))
    discret = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        for sans_tete in ESSAIS_SANS_TETE:
            commande = [str(exe), sans_tete, *OPTIONS_COMMUNES, f"--user-data-dir={profil}",
                        f"--print-to-pdf={pdf}", page_html.as_uri()]
            processus = subprocess.Popen(commande, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                         creationflags=discret)
            if _pdf_pret(pdf, delai):
                try:
                    processus.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pass
                return nom, commande
            processus.kill()
        raise ErreurLivrable(f"{nom} n'a pas produit de PDF (essais : {', '.join(ESSAIS_SANS_TETE)}). "
                             "Relancer avec --sans-pdf et imprimer la page HTML en PDF à la main (Ctrl+P).")
    finally:
        for _ in range(10):                      # le navigateur libère son profil quelques instants après
            shutil.rmtree(profil, ignore_errors=True)
            if not profil.exists():
                break
            time.sleep(0.5)


def verifier_pdf(pdf: Path) -> tuple[int, float]:
    """(nombre de pages, poids en Mo) du PDF, ouvert avec PyMuPDF."""
    with pymupdf.open(pdf) as d:
        pages = d.page_count
    return pages, round(Path(pdf).stat().st_size / OCTETS_PAR_MO, 2)


# ── Chaîne complète ──────────────────────────────────────────────────────────────────────────────────

def resoudre_dossier(dossier: Path | str) -> Path:
    """Chemin du dossier d'installation (chemin direct, ou nom dans dimensionnement/dossiers/)."""
    d = Path(dossier)
    if d.is_dir():
        return d.resolve()
    if (DOSSIERS / d).is_dir():
        return (DOSSIERS / d).resolve()
    raise ErreurLivrable(f"Dossier d'installation introuvable : {dossier}")


def lire_demande(chemin: Path) -> dict:
    """demande.json lu et minimalement vérifié (clés indispensables au rendu)."""
    if not chemin.is_file():
        raise ErreurLivrable(f"demande.json introuvable : {chemin} (lancer d'abord assembler.py).")
    try:
        demande = json.loads(chemin.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErreurLivrable(f"demande.json illisible ({chemin}) : {e}") from None
    manquantes = [c for c in ("version", "titre", "postes", "mail") if c not in demande]
    if manquantes:
        raise ErreurLivrable(f"demande.json incomplet, clés absentes : {', '.join(manquantes)}")
    return demande


def generer(dossier: Path | str, version: str, pdf: bool = True, ouvrir: bool = False) -> dict:
    """Produit le livrable de l'étape 3 pour <dossier>/3-demande-fournisseur/<version>/demande.json.

    pdf    : imprimer le PDF (Edge sans tête, Chrome en repli) et le vérifier ; False = HTML et mail seulement.
    ouvrir : ouvrir le PDF (ou la page HTML) et le mail HTML.
    Renvoie {"html", "pdf", "mail_txt", "mail_html", "images", "pages", "mo", "navigateur", "commande",
    "avertissements"} (pdf, pages, mo, navigateur, commande à None sans PDF). Lève ErreurLivrable si quelque
    chose manque (dossier, demande.json, photo, navigateur).
    """
    if not RE_VERSION.match(version):
        raise ErreurLivrable(f"Version attendue sous la forme v1, v2… ou v1-fabricant (reçu : {version!r}).")
    d = resoudre_dossier(dossier)
    dv = d / SOUS_DOSSIER / version
    demande = lire_demande(dv / "demande.json")

    carte = preparer_photos(demande, d, dv)
    rendu = typographier(demande)                           # typographie du rendu, demande.json inchangé
    page = rendre(GABARIT.read_text(encoding="utf-8"), preparer_vue(rendu, carte))
    page_html = dv / f"demande-{version}.html"
    page_html.write_text(page, encoding="utf-8", newline="\n")
    mail_txt, mail_html = ecrire_mail(rendu, dv)

    resultat = {"html": page_html, "pdf": None, "mail_txt": mail_txt, "mail_html": mail_html,
                "images": [dv / c for c in carte.values()], "pages": None, "mo": None, "navigateur": None,
                "commande": None, "avertissements": []}
    if pdf:
        chemin_pdf = dv / f"demande-{version}.pdf"
        navigateur, commande = imprimer_pdf(page_html, chemin_pdf)
        pages, mo = verifier_pdf(chemin_pdf)
        resultat.update(pdf=chemin_pdf, pages=pages, mo=mo, navigateur=navigateur, commande=commande)
        if mo > SEUIL_MO:
            resultat["avertissements"].append(
                f"Le PDF pèse {mo:.2f} Mo, au-delà de {SEUIL_MO:g} Mo : risque de refus par la messagerie "
                "(retirer des vues d'ensemble ou des doublons de photos).")
    if ouvrir:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from shared.rendu_html import ouvrir_page
        ouvrir_page(resultat["pdf"] or page_html)
        ouvrir_page(mail_html)
    return resultat


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossier", help="dossier d'installation (chemin, ou nom dans dimensionnement/dossiers/)")
    ap.add_argument("version", help="version à rendre : v1, v2… ou vN-<suffixe> (ex. v1-fabricant)")
    ap.add_argument("--ouvrir", action="store_true", help="ouvrir le PDF et le mail HTML")
    ap.add_argument("--sans-pdf", action="store_true", help="ne pas imprimer le PDF (HTML et mail seulement)")
    a = ap.parse_args(argv)
    try:
        r = generer(a.dossier, a.version, pdf=not a.sans_pdf, ouvrir=a.ouvrir)
    except ErreurLivrable as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 1
    print(f"Page HTML : {r['html']}")
    print(f"Photos    : {len(r['images'])} redimensionnées dans {r['html'].parent / 'img'}")
    if r["pdf"]:
        print(f"PDF       : {r['pdf']} ({r['pages']} pages, {r['mo']:.2f} Mo, imprimé par {r['navigateur']})")
    print(f"Mail      : {r['mail_txt']}")
    print(f"            {r['mail_html']}")
    for avertissement in r["avertissements"]:
        print(f"ATTENTION : {avertissement}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
