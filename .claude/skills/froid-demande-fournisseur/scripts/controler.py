"""froid-demande-fournisseur — étape 3 : contrôler le livrable (demande.json, page, PDF, mail) avant la relecture.

Lecture seule : rien n'est écrit ni corrigé ici. Un échec se corrige à la cause (données de l'étape 2, assembler.py,
textes de demande.json, photos), puis generer_livrable.py et ce contrôle à nouveau ; jamais en affaiblissant le contrôle.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python .claude/skills/froid-demande-fournisseur/scripts/controler.py <dossier> <vN> [--ouvrir]
    <dossier> : chemin du dossier d'installation, ou son nom dans dimensionnement/dossiers/
    <vN>      : v1, v2… (variante grossiste) ou vN-<suffixe> (ex. v1-fabricant)
    --ouvrir  : si aucun contrôle n'échoue, ouvre le PDF et le mail HTML (relecture par Loïc)
Codes de sortie : 0 aucun échec ; 1 au moins un échec (ou dossier, version, demande.json introuvable).

Python :
    from controler import controler, en_echec, rapport
    controles = controler(dossier, "v1")            # [Controle(numero, titre, statut, resume, details)]
    print(rapport(controles, "<nom du dossier>", "v1"))

Les sept contrôles :
 1. Anonymisation (si demande.json dit "anonymise": true) : aucun identifiant du client lu dans
    identifiants-client.json (liste « recherches » : nom, mots distinctifs, adresse, rue, code postal, localité,
    téléphone, mail et domaine, n° de fiche, slug) n'apparaît, en majuscules, sans accents ou sans espaces, dans
    demande.json (hors chemins de photos, jamais montrés), demande-<vN>.html, mail-*.txt, mail-*.html, ni dans le texte
    et les métadonnées du PDF (PyMuPDF).
 2. Chiffres : chaque nombre des tableaux chambres (régime, surface, volume, nombre d'évaporateurs), production
    (volume balayé, puissance, libellés et puissances des sous-totaux), evaporateurs (puissance) et du champ
    « puissance » de chaque poste existe au même rendu que Valeur.texte() (unité et décimales comprises ; un nombre
    entier peut perdre ses décimales nulles, ex. « -30 °C ») dans 2-resultats.json ou valeurs-derivees.json. Ignorés :
    noms de chambres et de postes, désignations (compresseurs, modèles), n° de série, années, statuts, multiplicateurs
    « 2 × ». Le nombre d'évaporateurs doit être celui d'un poste de 2-resultats.json.
 3. Plaques : chaque photo citée dans les tableaux B, B2 et C de 1-existant.md (références pNN-k) figure une fois et
    une seule dans postes[].photos ou annexes.vues_ensemble, avec une légende non vide ; aucune photo du PDF sans légende.
 4. PDF : demande-<vN>.pdf existe, s'ouvre, a plus d'une page, pèse moins de 5 Mo, n'est pas plus ancien que
    demande.json ; la page HTML existe et chaque image qu'elle cite existe (une par photo de demande.json).
 5. Mail : mail-<variante>.txt existe, objet non vide, aucun « | » ni « <table » (ni dans le .html), il cite au moins
    un chiffre clé, chaque nombre avec unité qu'il cite existe dans 2-resultats.json (même rendu), il renvoie au PDF.
 6. Annexes : annexes.pieces_jointes (liste) et annexes.plan_implantation (texte non vide) présents dans demande.json.
    Plan du local (Lot 7) : si plan/plan.pdf existe, il est dans annexes.documents ; chaque document existe, son titre
    est dans le texte du PDF, le mail cite le plan ; le PDF final a exactement les pages d'Edge (lues dans la
    pagination « Page k / N » du pied de page) + les pages d'annexe, chaque page d'annexe est A4, a la taille de la
    page source et en reprend le texte (≥ 80 % des mots ; le cartouche anonymisé en change quelques-uns).
 7. Longueurs de cuivre (Lot 7), sans objet pour une demande antérieure (ni champ « longueurs » ni plan/metre.json) :
    (a) les longueurs de demande.json et celles du chapitre du PDF (chaque ligne puis le total de chaque réseau, dans
    l'ordre) sont celles des réseaux cuivre_froid et cuivre_clim de plan/metre.json, à 0,01 m près, même version du
    plan ; (b) la phrase d'estimation et « Diamètres et charge de fluide à définir par vos soins. » sont dans le texte
    du PDF ; (c) sans metre.json : aucun chapitre ni tableau de longueurs, et la ligne « Longueurs de lignes non
    relevées, à estimer par vos soins. » dans le PDF ; (e) « (mesurée) » exactement sur les longueurs d'origine
    « mesuree » (lignes, et total d'un réseau entièrement mesuré) ; le mail cite les longueurs si et seulement si
    elles existent, sans tableau.

Dépendances : PyMuPDF ; generer_livrable.py (même dossier) ; valeur.py du skill froid-dimensionnement.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote

import pymupdf

ICI = Path(__file__).resolve().parent
for _chemin in (ICI, ICI.parents[1] / "froid-dimensionnement" / "scripts"):
    if str(_chemin) not in sys.path:
        sys.path.insert(0, str(_chemin))
import generer_livrable as gl  # noqa: E402
from assembler import (FAMILLES_CUIVRE, PHRASE_DIAMETRES, PHRASE_NON_RELEVEES,  # noqa: E402
                       TITRE_ANNEXE_PLAN)
from valeur import DECIMALES, DECIMALES_DEFAUT, Valeur, depuis_json, nombre_fr  # noqa: E402

OK, ECHEC, SANS_OBJET = "OK", "ÉCHEC", "sans objet"
CHAMPS_IDENTIFIANTS = ("noms", "mots_distinctifs", "adresses", "rues", "codes_postaux", "localites", "telephones",
                       "mails", "domaines_mail", "fiches")
METADONNEES_PDF = ("title", "author", "subject", "keywords", "creator", "producer")
# Colonnes contrôlées (les autres sont des noms, des désignations, des n° de série, des années ou des statuts).
COLONNES_CHIFFREES = (("chambres", "lignes", ("regime", "surface", "volume", "nb_evaporateurs")),
                      ("production", "lignes", ("volume_balaye", "puissance")),
                      ("production", "sous_totaux", ("libelle", "puissance")),
                      ("evaporateurs", "lignes", ("puissance",)))
CHIFFRES_MINIMUM_TELEPHONE = 6     # identifiant fait de chiffres seulement : chiffres séparés ou non (0499 11 22 33)

# ── Nombres au rendu de Valeur.texte() ──────────────────────────────────────────────────────────────
ESPACES = "   "
_UNITES = "|".join(re.escape(u) for u in sorted(DECIMALES, key=len, reverse=True))
# Unités qui peuvent suivre le nombre sans espace (« 40°C », « 63,5kW ») ; les autres exigent une espace, sinon
# « AK-SM 800A » ou « 3×400 V » deviendraient des ampères ou des tonnes.
_UNITES_COLLEES = "|".join(re.escape(u) for u in ("m³/h", "m3/h", "kW", "MW", "°C", "%", "m³", "m²", "kg"))
RE_NOMBRE = re.compile(
    r"(?<![\w.,/])"
    r"(?P<nombre>[-−+]?\d{1,3}(?:[  ]\d{3})+(?:,\d+)?|[-−+]?\d+(?:,\d+)?)(?![\d,])"
    rf"(?:[{ESPACES}](?P<unite>{_UNITES})(?![\w²³/])|(?P<collee>{_UNITES_COLLEES})(?![\w²³/]))?")
RE_MULTIPLICATEUR = re.compile(rf"^[{ESPACES}]*[×x][{ESPACES}]")
RE_REF_PHOTO = re.compile(r"(?<![A-Za-z0-9])(p\d{2,}-\d+)(?!\d)")
RE_TABLEAU_PHOTOS = re.compile(r"^#{2,3}\s+(B2|B|C)\b")
RE_IMG = re.compile(r"<img\b[^>]*?\bsrc=\"([^\"]*)\"", re.I)
# Lot 7 : pagination d'Edge, longueurs du chapitre (« 4,21 », « 1 234,50 », « 12,00 (mesurée) » ; unité dans l'en-tête)
RE_PAGINATION = re.compile(r"Page\s+(\d+)\s*/\s*(\d+)")
RE_LONGUEUR = re.compile(r"(?<![\d,.])(\d{1,3}(?:[\u00a0\u202f]\d{3})*,\d{2})(?![\d,])"
                         r"(?:[ \u00a0]?(\(mesurée\)))?")
MARQUE_MESUREE = "(mesurée)"
TOLERANCE_M = 0.01
PART_MOTS_ANNEXE = 0.8


@dataclass
class Controle:
    """Résultat d'un contrôle : statut OK, ÉCHEC ou « sans objet », un résumé, le détail de chaque problème."""
    numero: int
    titre: str
    statut: str = OK
    resume: str = ""
    details: list[str] = field(default_factory=list)

    def echec(self, detail: str) -> None:
        self.statut = ECHEC
        self.details.append(detail)


@dataclass
class Livrable:
    """Tout ce que les contrôles lisent, chargé une fois."""
    dossier: Path
    version: str
    dv: Path
    demande: dict
    pdf: Path
    page: Path
    texte_pdf: str | None = None        # None : PDF absent ou illisible
    pages_pdf: int | None = None
    erreur_pdf: str = ""
    textes_pages: list[str] = field(default_factory=list)                  # texte de chaque page
    tailles_pages: list[tuple[float, float]] = field(default_factory=list)  # (largeur, hauteur) en points


class ErreurControle(Exception):
    """Dossier, version ou demande.json introuvable : rien n'est contrôlable."""


# ── Outils ──────────────────────────────────────────────────────────────────────────────────────────

def normaliser(texte: str) -> str:
    """Sans accents, en minuscules, espaces insécables → espaces (comparaison tolérante des identifiants)."""
    t = unicodedata.normalize("NFKD", texte or "")
    return "".join(c for c in t if not unicodedata.combining(c)).casefold()


def motif_identifiant(identifiant: str) -> re.Pattern | None:
    """Motif qui trouve l'identifiant quels que soient la casse, les accents et les séparateurs entre ses mots (espaces,
    tirets, points, rien : « ETS-Dupont », « etsdupont ») ; chiffres seuls (téléphone) : séparateurs libres entre
    chaque chiffre. Bornes de mot aux deux bouts (« 1234 » ne se trouve pas dans « 12345 »)."""
    morceaux = re.findall(r"[^\W_]+", normaliser(identifiant))
    if not morceaux:
        return None
    chiffres = "".join(morceaux)
    if chiffres.isdigit() and len(chiffres) >= CHIFFRES_MINIMUM_TELEPHONE:
        morceaux = list(chiffres)
    corps = r"[\W_]*".join(re.escape(m) for m in morceaux)
    return re.compile(rf"(?<![^\W_]){corps}(?![^\W_])")


def lire_identifiants(chemin: Path) -> list[str]:
    """Identifiants du client à chercher (liste « recherches », sinon tous les champs), sans doublon."""
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    liste = list(donnees.get("recherches") or [])
    if not liste:
        for cle in CHAMPS_IDENTIFIANTS:
            liste += donnees.get(cle) or []
        liste += [donnees.get("client") or "", donnees.get("slug") or ""]
    vus = []
    for x in liste:
        x = " ".join(str(x).split())
        if x and x not in vus:
            vus.append(x)
    return vus


def textes_json(obj, chemin: str = "") -> list[tuple[str, str]]:
    """(chemin lisible, texte) de chaque chaîne de demande.json, sauf les chemins de photos (clé « fichier »)."""
    sortie = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k != "fichier":
                sortie += textes_json(v, f"{chemin}.{k}" if chemin else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj, 1):
            sortie += textes_json(v, f"{chemin}[{i}]")
    elif isinstance(obj, str):
        sortie.append((chemin, obj))
    return sortie


def mo_fr(mo: float) -> str:
    return f"{mo:.2f}".replace(".", ",")


def compacter(texte: str) -> str:
    """Texte du PDF avec chaque suite d'espaces et de retours à la ligne réduite à un caractère : une espace
    insécable si la suite en contient une (et pas de retour à la ligne), une espace sinon. Les insécables des
    nombres (« 1 234,50 ») restent donc distinguables des espaces ordinaires."""
    def un(m):
        s = m.group()
        return "\u00a0" if ("\u00a0" in s or "\u202f" in s) and "\n" not in s else " "
    return re.sub(r"[ \t\r\n\u00a0\u202f]+", un, texte or "")


def motif_phrase(phrase: str) -> re.Pattern:
    """Motif d'une phrase dans le texte compacté : mots identiques, séparés par n'importe quelle espace."""
    return re.compile(r"[ \u00a0]+".join(re.escape(m) for m in str(phrase).split()))


def m_fr(x: float) -> str:
    return f"{x:.2f}".replace(".", ",") + " m"


def mots(texte: str) -> set[str]:
    """Mots de 3 caractères ou plus, normalisés (comparaison d'une page d'annexe avec sa source)."""
    return set(re.findall(r"[^\W_]{3,}", normaliser(texte)))


def extrait(texte: str, debut: int, fin: int, marge: int = 30) -> str:
    return " ".join(texte[max(0, debut - marge):fin + marge].split())


def cle_rendu(nombre: str, unite: str) -> tuple[str, str]:
    """Forme comparable d'un nombre rendu : signe moins unique, espace fine → insécable, « + » retiré."""
    n = nombre.replace("−", "-").replace(" ", " ").replace(" ", " ")
    return (n[1:] if n.startswith("+") else n), unite


def rendus(valeurs: list[Valeur]) -> set[tuple[str, str]]:
    """Rendus admis : Valeur.texte() aux décimales par défaut, et avec moins de décimales quand rien ne se perd
    (−30,0 °C → « -30 °C »), comme assembler.py pour les températures."""
    admis = set()
    for v in valeurs:
        if v.nombre is None:
            continue
        defaut = DECIMALES.get(v.unite, DECIMALES_DEFAUT)
        exact = Decimal(repr(v.nombre))
        for d in range(defaut + 1):
            if d == defaut or exact == exact.quantize(Decimal(1).scaleb(-d)):
                admis.add(cle_rendu(nombre_fr(v.nombre, d), v.unite))
    return admis


def valeurs_de(obj) -> list[Valeur]:
    """Toutes les Valeur d'une structure relue par depuis_json (2-resultats.json)."""
    if isinstance(obj, Valeur):
        return [obj]
    if isinstance(obj, dict):
        return [v for x in obj.values() for v in valeurs_de(x)]
    if isinstance(obj, list):
        return [v for x in obj for v in valeurs_de(x)]
    return []


def nombres(texte: str):
    """(nombre, unité ou « », position de fin) de chaque nombre du texte."""
    for m in RE_NOMBRE.finditer(texte or ""):
        yield m.group("nombre"), m.group("unite") or m.group("collee") or "", m.end()


# ── Chargement ──────────────────────────────────────────────────────────────────────────────────────

def charger(dossier: Path | str, version: str) -> Livrable:
    if not gl.RE_VERSION.match(version or ""):
        raise ErreurControle(f"Version attendue sous la forme v1, v2… ou v1-fabricant (reçu : {version!r}).")
    try:
        d = gl.resoudre_dossier(dossier)
        dv = d / gl.SOUS_DOSSIER / version
        demande = gl.lire_demande(dv / "demande.json")
    except gl.ErreurLivrable as e:
        raise ErreurControle(str(e)) from None
    liv = Livrable(dossier=d, version=version, dv=dv, demande=demande, pdf=dv / f"demande-{version}.pdf",
                   page=dv / f"demande-{version}.html")
    if not liv.pdf.is_file():
        liv.erreur_pdf = f"{liv.pdf.name} absent (lancer generer_livrable.py)"
        return liv
    try:
        with pymupdf.open(liv.pdf) as doc:
            liv.pages_pdf = doc.page_count
            meta = [str(v) for k, v in (doc.metadata or {}).items() if k in METADONNEES_PDF and v]
            liv.textes_pages = [p.get_text() for p in doc]
            liv.tailles_pages = [(p.rect.width, p.rect.height) for p in doc]
            liv.texte_pdf = "\n".join(liv.textes_pages + meta)
    except Exception as e:                                  # PDF tronqué, chiffré, pas un PDF
        liv.erreur_pdf = f"{liv.pdf.name} ne s'ouvre pas ({e})"
    return liv


# ── 1. Anonymisation ────────────────────────────────────────────────────────────────────────────────

def controle_anonymisation(liv: Livrable) -> Controle:
    c = Controle(1, "Anonymisation")
    if not liv.demande.get("anonymise"):
        c.statut, c.resume = SANS_OBJET, "variante nommée (demande.json : « anonymise » faux)"
        return c
    chemin = liv.dv / "identifiants-client.json"
    if not chemin.is_file():
        c.echec(f"{chemin.name} absent : identifiants du client inconnus, anonymisation non vérifiable "
                "(relancer assembler.py)")
        return c
    identifiants = lire_identifiants(chemin)
    motifs = [(i, m) for i in identifiants if (m := motif_identifiant(i))]
    if not motifs:
        c.echec(f"{chemin.name} ne contient aucun identifiant : anonymisation non vérifiable")
        return c

    sources: list[tuple[str, str]] = [(f"demande.json › {ch}", t) for ch, t in textes_json(liv.demande)]
    fichiers = 1
    if liv.page.is_file():
        sources.append((liv.page.name, html.unescape(liv.page.read_text(encoding="utf-8"))))
        fichiers += 1
    else:
        c.echec(f"{liv.page.name} absent : page non vérifiée")
    for f in sorted(liv.dv.glob("mail-*.txt")) + sorted(liv.dv.glob("mail-*.html")):
        texte = f.read_text(encoding="utf-8")
        sources.append((f.name, html.unescape(texte) if f.suffix == ".html" else texte))
        fichiers += 1
    if liv.texte_pdf is not None:
        sources.append((f"{liv.pdf.name} (texte)", liv.texte_pdf))
    else:
        c.echec(f"texte du PDF non vérifié : {liv.erreur_pdf}")

    for lieu, texte in sources:
        norm = normaliser(texte)
        for identifiant, motif in motifs:
            m = motif.search(norm)
            if m:
                c.echec(f"« {identifiant} » trouvé dans {lieu} : « {extrait(norm, m.start(), m.end())} »")
    c.resume = (f"{len(motifs)} identifiants du client cherchés (casse, accents, espaces) dans {fichiers} fichier"
                + ("s" if fichiers > 1 else "")
                + (" et le texte du PDF" if liv.texte_pdf is not None else ""))
    if c.statut == OK:
        c.resume += " : aucun trouvé"
    return c


# ── 2. Chiffres ─────────────────────────────────────────────────────────────────────────────────────

def charger_valeurs(dossier: Path, dv: Path) -> tuple[list[Valeur], list[Valeur], dict]:
    """(valeurs de 2-resultats.json, valeurs de valeurs-derivees.json, résultats relus)."""
    res = depuis_json((dossier / "2-resultats.json").read_text(encoding="utf-8"))
    derivees = []
    chemin = dv / "valeurs-derivees.json"
    if chemin.is_file():
        derivees = [Valeur.depuis_dict(x) for x in json.loads(chemin.read_text(encoding="utf-8")).get("valeurs") or []]
    return valeurs_de(res), derivees, res


def cellules_chiffrees(demande: dict) -> list[tuple[str, str, str]]:
    """(où, colonne, texte) des cellules contrôlées."""
    cellules = []
    for bloc, liste, colonnes in COLONNES_CHIFFREES:
        for i, ligne in enumerate((demande.get(bloc) or {}).get(liste) or [], 1):
            for col in colonnes:
                if str(ligne.get(col) or "").strip():
                    cellules.append((f"{bloc} › {liste} {i}", col, str(ligne[col])))
    for i, p in enumerate(demande.get("postes") or [], 1):
        if str(p.get("puissance") or "").strip():
            cellules.append((f"postes › {p.get('titre') or i}", "puissance", str(p["puissance"])))
    return cellules


def controle_chiffres(liv: Livrable) -> Controle:
    c = Controle(2, "Chiffres")
    if not (liv.dossier / "2-resultats.json").is_file():
        c.echec("2-resultats.json absent : chiffres non vérifiables")
        return c
    valeurs, derivees, res = charger_valeurs(liv.dossier, liv.dv)
    admis = rendus(valeurs) | rendus(derivees)
    comptes = {len(p.get("evaporateurs") or []) for p in res.get("postes") or []}
    origine = "2-resultats.json" + (" ni dans valeurs-derivees.json" if (liv.dv / "valeurs-derivees.json").is_file()
                                    else " (valeurs-derivees.json absent)")
    total = 0
    for ou, col, texte in cellules_chiffrees(liv.demande):
        for nombre, unite, fin in nombres(texte):
            if not unite and RE_MULTIPLICATEUR.match(texte[fin:]):
                continue                                    # « 2 × 4H-15.2Y » : multiplicateur d'une désignation
            total += 1
            if not unite and col == "nb_evaporateurs":
                if not nombre.isdigit() or int(nombre) not in comptes:
                    c.echec(f"{ou} › {col} « {texte} » : {nombre} évaporateur(s), aucun poste de 2-resultats.json "
                            f"n'en a autant ({', '.join(map(str, sorted(comptes))) or 'aucun'})")
                continue
            if cle_rendu(nombre, unite) not in admis:
                rendu = f"{nombre} {unite}".strip()
                c.echec(f"{ou} › {col} « {texte} » : « {rendu} » introuvable dans {origine}")
    echecs = len(c.details)
    c.resume = (f"{total} nombres des tableaux et des puissances par poste comparés au rendu de 2-resultats.json "
                f"et valeurs-derivees.json" + (f" : {echecs} introuvable(s)" if echecs else " : tous retrouvés"))
    return c


# ── 3. Plaques ──────────────────────────────────────────────────────────────────────────────────────

def photos_citees(existant_md: str) -> dict[str, str]:
    """{référence pNN-k: tableau} des photos citées dans les lignes des tableaux B, B2 et C de 1-existant.md."""
    refs: dict[str, str] = {}
    tableau = None
    for ligne in existant_md.splitlines():
        m = RE_TABLEAU_PHOTOS.match(ligne)
        if m:
            tableau = m.group(1)
            continue
        if re.match(r"^#{1,6}\s", ligne):
            tableau = None
            continue
        if tableau and ligne.lstrip().startswith("|"):
            for r in RE_REF_PHOTO.findall(ligne):
                refs.setdefault(r, tableau)
    return refs


def photos_demande(demande: dict) -> list[tuple[str, str, str]]:
    """(référence, légende, où) de chaque photo de demande.json (postes puis vues d'ensemble)."""
    sortie = []
    for p in demande.get("postes") or []:
        for ph in p.get("photos") or []:
            sortie.append((Path(str(ph.get("fichier") or "")).stem, str(ph.get("legende") or ""),
                           f"poste « {p.get('titre') or p.get('id')} »"))
    for ph in (demande.get("annexes") or {}).get("vues_ensemble") or []:
        sortie.append((Path(str(ph.get("fichier") or "")).stem, str(ph.get("legende") or ""), "annexes"))
    return sortie


def controle_plaques(liv: Livrable) -> Controle:
    c = Controle(3, "Plaques et photos")
    existant = liv.dossier / "1-existant.md"
    if not existant.is_file():
        c.echec("1-existant.md absent : plaques de l'étape 1 inconnues")
        return c
    citees = photos_citees(existant.read_text(encoding="utf-8"))
    presentes = photos_demande(liv.demande)
    for ref, tableau in citees.items():
        trouvees = [p for p in presentes if p[0] == ref]
        if not trouvees:
            c.echec(f"{ref} (tableau {tableau} de 1-existant.md) absente du PDF")
        elif len(trouvees) > 1:
            c.echec(f"{ref} (tableau {tableau}) présente {len(trouvees)} fois : "
                    + ", ".join(p[2] for p in trouvees))
    for ref, legende, ou in presentes:
        if not legende.strip():
            c.echec(f"{ref} ({ou}) : légende vide")
    c.resume = (f"{len(citees)} photos citées aux tableaux B, B2 et C ; {len(presentes)} photos dans le PDF"
                + ("" if c.statut == ECHEC else " : chacune une fois, toutes légendées"))
    if not citees:
        c.echec("aucune photo citée dans les tableaux B, B2 et C de 1-existant.md : relevé incomplet ?")
    return c


# ── 4. PDF ──────────────────────────────────────────────────────────────────────────────────────────

def controle_pdf(liv: Livrable, seuil_mo: float = gl.SEUIL_MO) -> Controle:
    c = Controle(4, "PDF")
    source = liv.dv / "demande.json"
    if liv.page.is_file():
        page = liv.page.read_text(encoding="utf-8")
        srcs = list(dict.fromkeys(RE_IMG.findall(page)))
        for src in srcs:
            if not (liv.dv / unquote(html.unescape(src))).is_file():
                c.echec(f"image manquante dans {liv.page.name} : {src}")
        attendues = len(gl.photos_referencees(liv.demande))
        if len(srcs) != attendues:
            c.echec(f"{liv.page.name} montre {len(srcs)} images pour {attendues} photos dans demande.json")
        if liv.page.stat().st_mtime < source.stat().st_mtime:
            c.echec(f"demande.json modifié après {liv.page.name} : relancer generer_livrable.py")
    else:
        c.echec(f"{liv.page.name} absent (lancer generer_livrable.py)")
    if liv.erreur_pdf:
        c.echec(liv.erreur_pdf)
        c.resume = "PDF non vérifié"
        return c
    mo = liv.pdf.stat().st_size / gl.OCTETS_PAR_MO
    if liv.pages_pdf is None or liv.pages_pdf <= 1:
        c.echec(f"{liv.pdf.name} n'a que {liv.pages_pdf or 0} page")
    if mo >= seuil_mo:
        c.echec(f"{liv.pdf.name} pèse {mo_fr(mo)} Mo, au-delà de {seuil_mo:g} Mo (retirer des vues d'ensemble)")
    if liv.pdf.stat().st_mtime < source.stat().st_mtime:
        c.echec(f"demande.json modifié après {liv.pdf.name} : relancer generer_livrable.py")
    c.resume = f"{liv.pdf.name} : {liv.pages_pdf} pages, {mo_fr(mo)} Mo"
    return c


# ── 5. Mail ─────────────────────────────────────────────────────────────────────────────────────────

def controle_mail(liv: Livrable) -> Controle:
    c = Controle(5, "Mail")
    variante = gl.slug(liv.demande.get("variante") or "grossiste")
    txt, page = liv.dv / f"mail-{variante}.txt", liv.dv / f"mail-{variante}.html"
    if not txt.is_file():
        c.echec(f"{txt.name} absent (lancer generer_livrable.py)")
        return c
    contenu = txt.read_text(encoding="utf-8")
    objet = contenu.split("\n", 1)[0].strip()
    if not objet or not str((liv.demande.get("mail") or {}).get("objet") or "").strip():
        c.echec("objet vide")
    if "|" in contenu:
        c.echec(f"{txt.name} contient « | » (tableau ?) : le mail ne porte aucun tableau, tout est dans le PDF")
    if "<table" in contenu.lower():
        c.echec(f"{txt.name} contient « <table »")
    if page.is_file() and "<table" in page.read_text(encoding="utf-8").lower():
        c.echec(f"{page.name} contient un tableau")
    elif not page.is_file():
        c.echec(f"{page.name} absent (lancer generer_livrable.py)")
    if not (liv.dossier / "2-resultats.json").is_file():
        c.echec("2-resultats.json absent : chiffres du mail non vérifiables")
        return c
    valeurs, _, _ = charger_valeurs(liv.dossier, liv.dv)
    admis = rendus(valeurs)
    cites = []
    for nombre, unite, _ in nombres(contenu):
        if not unite:
            continue                                        # dates, quantités, téléphone : pas des chiffres clés
        rendu = f"{nombre} {unite}"
        cites.append(rendu)
        if cle_rendu(nombre, unite) not in admis:
            c.echec(f"chiffre « {rendu} » du mail introuvable dans 2-resultats.json")
    if not cites:
        c.echec("le mail ne cite aucun chiffre clé (puissances, régimes)")
    if "pdf" not in contenu.lower():
        c.echec("le mail ne renvoie pas au PDF joint")
    c.resume = (f"{txt.name} : objet « {objet} » ; chiffres clés : " + (", ".join(dict.fromkeys(cites)) or "aucun"))
    return c


# ── 6. Annexes ──────────────────────────────────────────────────────────────────────────────────────

def controle_annexes(liv: Livrable) -> Controle:
    c = Controle(6, "Annexes")
    annexes = liv.demande.get("annexes")
    if not isinstance(annexes, dict):
        c.echec("annexes absentes de demande.json")
        return c
    if not isinstance(annexes.get("pieces_jointes"), list):
        c.echec("annexes.pieces_jointes absent (liste attendue, même vide ; le Lot 7 y ajoutera plan et métré)")
    if not str(annexes.get("plan_implantation") or "").strip():
        c.echec("annexes.plan_implantation absent ou vide (« à suivre » en V1)")
    c.resume = (f"plan d'implantation : {annexes.get('plan_implantation') or '—'} ; pièces jointes : "
                f"{len(annexes.get('pieces_jointes') or []) or 'aucune'}")
    docs = annexes.get("documents")
    plan_dossier = liv.dossier / "plan" / "plan.pdf"
    if docs is None:                                     # demande.json antérieur au Lot 7
        if plan_dossier.is_file():
            c.echec("plan/plan.pdf existe mais demande.json n'a pas d'annexes.documents (antérieur au Lot 7) : "
                    "relancer assembler.py puis generer_livrable.py")
        return c
    if not isinstance(docs, list):
        c.echec("annexes.documents : liste attendue")
        return c
    if plan_dossier.is_file() and not any(isinstance(d, dict) and d.get("type") == "plan" for d in docs):
        c.echec("plan/plan.pdf existe mais n'est pas en annexe de la demande : relancer assembler.py puis "
                "generer_livrable.py")
    if docs:
        verifier_annexes_pdf(liv, c, docs)
    return c


def pages_edge(textes: list[str]) -> int | None:
    """Nombre de pages imprimées par Edge, lu dans la pagination « Page k / N » du pied de page (None si absente ou
    incohérente)."""
    totaux = {int(m.group(2)) for t in textes for m in RE_PAGINATION.finditer(t)}
    return totaux.pop() if len(totaux) == 1 else None


def verifier_annexes_pdf(liv: Livrable, c: Controle, docs: list) -> None:
    """(d) Pages d'annexe à la fin du PDF : nombre, format A4, taille et texte de la page source ; titres listés dans
    le PDF ; plan cité dans le mail."""
    sources = []
    for d in docs:
        if not isinstance(d, dict):
            c.echec("annexes.documents : objet attendu")
            continue
        chemin = (liv.dv / str(d.get("fichier") or "")).resolve()
        if not chemin.is_file():
            c.echec(f"annexe « {d.get('titre')} » introuvable : {d.get('fichier')} (relatif à {liv.dv.name}/)")
            continue
        sources.append((d, chemin, int(d.get("pages") or 1)))
    if liv.texte_pdf is None or liv.pages_pdf is None:
        c.echec(f"annexes non vérifiées dans le PDF : {liv.erreur_pdf or 'PDF illisible'}")
        return
    texte = compacter(liv.texte_pdf)
    for d, _, _ in sources:
        if not motif_phrase(d.get("titre") or TITRE_ANNEXE_PLAN).search(texte):
            c.echec(f"titre de l'annexe « {d.get('titre')} » absent du texte du PDF (liste des annexes)")
    n_annexes = sum(n for _, _, n in sources)
    edge = pages_edge(liv.textes_pages)
    if edge is None:
        c.echec("pagination « Page k / N » d'Edge introuvable ou incohérente : nombre de pages d'Edge inconnu, "
                "annexe non vérifiable (relancer generer_livrable.py)")
        return
    if liv.pages_pdf != edge + n_annexes:
        c.echec(f"{liv.pdf.name} : {liv.pages_pdf} pages pour {edge} pages d'Edge + {n_annexes} page(s) d'annexe "
                "(annexe absente ou en double : relancer generer_livrable.py avec Edge ou Chrome)")
        return
    debut = edge
    for d, chemin, n in sources:
        with pymupdf.open(chemin) as source:
            for k in range(min(n, source.page_count)):
                i = debut + k
                largeur, hauteur = liv.tailles_pages[i]
                if not gl.est_a4(pymupdf.Rect(0, 0, largeur, hauteur)):
                    c.echec(f"page {i + 1} (annexe « {d.get('titre')} ») hors format A4 : {largeur:.0f} × {hauteur:.0f} pt")
                r = source[k].rect
                if abs(r.width - largeur) > 1 or abs(r.height - hauteur) > 1:
                    c.echec(f"page {i + 1} : {largeur:.0f} × {hauteur:.0f} pt, la page {k + 1} de {chemin.name} fait "
                            f"{r.width:.0f} × {r.height:.0f} pt (mise à l'échelle ?)")
                attendus = mots(source[k].get_text())
                if attendus and len(attendus & mots(liv.textes_pages[i])) / len(attendus) < PART_MOTS_ANNEXE:
                    c.echec(f"page {i + 1} : ne reprend pas le texte de la page {k + 1} de {chemin.name}")
        debut += n
    variante = gl.slug(liv.demande.get("variante") or "grossiste")
    mail = liv.dv / f"mail-{variante}.txt"
    if mail.is_file() and "plan du local" not in mail.read_text(encoding="utf-8").lower():
        c.echec(f"{mail.name} ne cite pas le plan du local joint en annexe")
    if c.statut == OK:
        c.resume += (f" ; annexe(s) en fin de PDF : " + ", ".join(str(d.get("titre")) for d, _, _ in sources)
                     + f" (page{'s' if n_annexes > 1 else ''} {edge + 1}"
                     + (f" à {edge + n_annexes}" if n_annexes > 1 else "") + f", après {edge} pages d'Edge)")


# ── 7. Longueurs de cuivre ──────────────────────────────────────────────────────────────────────────

def reseaux_cuivre(metre: dict) -> list[dict]:
    """Réseaux cuivre_froid et cuivre_clim de metre.json (lecture indépendante d'assembler.py) :
    [{"cle", "lignes": [(total, mesurée ?)], "total", "mesure"}] ; réseau sans ligne ignoré."""
    reseaux = []
    for r in metre.get("reseaux") or []:
        if not isinstance(r, dict) or r.get("famille") not in FAMILLES_CUIVRE or not r.get("lignes"):
            continue
        lignes = [(float(l["total_m"]), l.get("origine") == "mesuree") for l in r["lignes"]]
        reseaux.append({"cle": r.get("cle"), "lignes": lignes, "total": float(r["total_m"]),
                        "mesure": all(m for _, m in lignes)})
    return reseaux


def controle_longueurs(liv: Livrable) -> Controle:
    c = Controle(7, "Longueurs de cuivre")
    lg = liv.demande.get("longueurs")
    chemin_metre = liv.dossier / "plan" / "metre.json"
    if lg is None:
        if chemin_metre.is_file():
            c.echec("plan/metre.json existe mais demande.json n'a pas de longueurs (antérieur au Lot 7) : relancer "
                    "assembler.py puis generer_livrable.py")
        else:
            c.statut, c.resume = SANS_OBJET, "demande.json antérieur aux longueurs de cuivre, sans plan/metre.json"
        return c
    if not isinstance(lg, dict):
        c.echec("longueurs : objet attendu dans demande.json")
        return c
    if liv.texte_pdf is None:
        c.echec(f"longueurs non vérifiées dans le PDF : {liv.erreur_pdf or 'PDF illisible'}")
        return c
    texte = compacter(liv.texte_pdf)
    page = liv.page.read_text(encoding="utf-8") if liv.page.is_file() else ""
    variante = gl.slug(liv.demande.get("variante") or "grossiste")
    chemin_mail = liv.dv / f"mail-{variante}.txt"
    mail = chemin_mail.read_text(encoding="utf-8").lower() if chemin_mail.is_file() else ""
    titre_chapitre = motif_phrase(gl.TITRES_CHAPITRES["longueurs"])

    if not chemin_metre.is_file():
        # (c) sans métré : aucun tableau, la ligne « non relevées »
        if not lg.get("absentes"):
            c.echec("demande.json porte des longueurs alors que plan/metre.json n'existe pas (retiré ?) : relancer "
                    "assembler.py")
        if not motif_phrase(PHRASE_NON_RELEVEES).search(texte):
            c.echec(f"ligne « {PHRASE_NON_RELEVEES} » absente du texte du PDF")
        if titre_chapitre.search(texte) or 'id="longueurs"' in page or "donnees longueurs" in page:
            c.echec("chapitre ou tableau de longueurs dans le livrable sans plan/metre.json")
        if MARQUE_MESUREE in texte:
            c.echec(f"« {MARQUE_MESUREE} » dans le PDF sans plan/metre.json")
        if "longueurs de cuivre" in mail:
            c.echec(f"{chemin_mail.name} cite des longueurs de cuivre qui n'existent pas")
        c.resume = "pas de plan/metre.json : ligne « non relevées » dans le PDF, aucun tableau de longueurs" \
            if c.statut == OK else "pas de plan/metre.json"
        return c

    try:
        metre = json.loads(chemin_metre.read_text(encoding="utf-8"))
        attendus = reseaux_cuivre(metre)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        c.echec(f"plan/metre.json illisible ou hors contrat ({type(e).__name__} : {e})")
        return c
    if not attendus:                                     # métré sans cuivre : traité comme « non relevées »
        if not lg.get("absentes"):
            c.echec("demande.json porte des longueurs, plan/metre.json n'a aucun réseau de cuivre")
        if not motif_phrase(PHRASE_NON_RELEVEES).search(texte):
            c.echec(f"ligne « {PHRASE_NON_RELEVEES} » absente du texte du PDF")
        c.resume = "plan/metre.json sans réseau de cuivre : longueurs « non relevées »"
        return c
    if lg.get("absentes"):
        c.echec("plan/metre.json a des réseaux de cuivre mais demande.json dit les longueurs absentes : relancer "
                "assembler.py puis generer_livrable.py")
        return c

    # (a) demande.json = metre.json
    if lg.get("plan_version") != metre.get("plan_version"):
        c.echec(f"demande.json reprend le plan v{lg.get('plan_version')}, plan/metre.json est à la v"
                f"{metre.get('plan_version')} : relancer assembler.py")
    if str(lg.get("phrase") or "").strip() != str(metre.get("phrase") or lg.get("phrase") or "").strip():
        c.echec("phrase d'estimation de demande.json différente de celle de plan/metre.json")
    recus = lg.get("reseaux") or []
    if [r.get("cle") for r in recus] != [r["cle"] for r in attendus]:
        c.echec(f"réseaux de demande.json {[r.get('cle') for r in recus]} au lieu de {[r['cle'] for r in attendus]} "
                "(cuivre froid et clim de plan/metre.json, sans électricité ni réseaux libres)")
    else:
        for r, a in zip(recus, attendus):
            lignes = r.get("lignes") or []
            if len(lignes) != len(a["lignes"]):
                c.echec(f"réseau {a['cle']} : {len(lignes)} ligne(s) dans demande.json, {len(a['lignes'])} dans "
                        "plan/metre.json")
                continue
            for k, (l, (total, mesure)) in enumerate(zip(lignes, a["lignes"]), 1):
                if not isinstance(l.get("total_m"), (int, float)) or abs(l["total_m"] - total) > TOLERANCE_M + 1e-9:
                    c.echec(f"réseau {a['cle']}, ligne {k} : {l.get('total_m')} m dans demande.json, "
                            f"{m_fr(total)} dans plan/metre.json")
                if (l.get("origine") == "mesuree") != mesure:
                    c.echec(f"réseau {a['cle']}, ligne {k} : origine « {l.get('origine')} » dans demande.json, "
                            f"« {'mesuree' if mesure else 'estimee'} » dans plan/metre.json")
            if not isinstance(r.get("total_m"), (int, float)) or abs(r["total_m"] - a["total"]) > TOLERANCE_M + 1e-9:
                c.echec(f"réseau {a['cle']} : total {r.get('total_m')} m dans demande.json, {m_fr(a['total'])} dans "
                        "plan/metre.json")

    # (b) phrases dans le PDF
    debut = motif_phrase(lg.get("phrase") or "").search(texte) if lg.get("phrase") else None
    if debut is None:
        c.echec("phrase d'estimation des longueurs absente du texte du PDF")
    fin = motif_phrase(PHRASE_DIAMETRES).search(texte, debut.end() if debut else 0)
    if fin is None:
        c.echec(f"« {PHRASE_DIAMETRES} » absente du texte du PDF (après la phrase d'estimation)")
    if debut is None or fin is None:
        return c

    # (a) et (e) : longueurs et marques « (mesurée) » du chapitre, dans l'ordre
    segment = texte[debut.end():fin.start()]
    trouvees = [(float(re.sub(r"[\u00a0\u202f]", "", m.group(1)).replace(",", ".")), bool(m.group(2)))
                for m in RE_LONGUEUR.finditer(segment)]
    attendues = []
    for a in attendus:
        attendues += [(a["cle"], f"ligne {k}", t, m) for k, (t, m) in enumerate(a["lignes"], 1)]
        attendues.append((a["cle"], "total", a["total"], a["mesure"]))
    if len(trouvees) != len(attendues):
        c.echec(f"chapitre des longueurs du PDF : {len(trouvees)} longueur(s) lue(s), {len(attendues)} attendue(s) "
                f"({len(attendus)} réseau(x) de cuivre de plan/metre.json, lignes et totaux)")
    for (valeur, marque), (cle, ou, total, mesure) in zip(trouvees, attendues):
        if abs(valeur - total) > TOLERANCE_M + 1e-9:
            c.echec(f"PDF, réseau {cle}, {ou} : {m_fr(valeur)} au lieu de {m_fr(total)} (plan/metre.json)")
        if marque != mesure:
            c.echec(f"PDF, réseau {cle}, {ou} : « {MARQUE_MESUREE} » " + ("en trop (longueur estimée)" if marque
                                                                          else "manquante (longueur mesurée)"))
    if segment.count(MARQUE_MESUREE) != sum(1 for *_, m in attendues if m):
        c.echec(f"chapitre des longueurs : {segment.count(MARQUE_MESUREE)} marque(s) « {MARQUE_MESUREE} » pour "
                f"{sum(1 for *_, m in attendues if m)} longueur(s) mesurée(s)")
    if "longueurs de cuivre estimées" not in mail:
        c.echec(f"{chemin_mail.name} ne dit pas que les longueurs de cuivre estimées sont dans le PDF")
    if c.statut == OK:
        mesurees = sum(1 for *_, m in attendues if m)
        c.resume = (f"{len(attendues)} longueurs (plan v{metre.get('plan_version')}, {len(attendus)} réseau(x) de "
                    f"cuivre) identiques à plan/metre.json ; {mesurees} marquée(s) « {MARQUE_MESUREE} » ; phrases "
                    "d'estimation et des diamètres présentes")
    return c


# ── Ensemble ────────────────────────────────────────────────────────────────────────────────────────

CONTROLES = (controle_anonymisation, controle_chiffres, controle_plaques, controle_pdf, controle_mail,
             controle_annexes, controle_longueurs)


def controler(dossier: Path | str, version: str) -> list[Controle]:
    """Les sept contrôles du livrable <dossier>/3-demande-fournisseur/<version>/ ; lève ErreurControle si rien n'est
    contrôlable. Un contrôle qui plante devient un échec expliqué (les autres continuent)."""
    return controler_livrable(charger(dossier, version))


def controler_livrable(liv: Livrable) -> list[Controle]:
    controles = []
    for i, fonction in enumerate(CONTROLES, 1):
        try:
            controles.append(fonction(liv))
        except Exception as e:                              # fichier illisible, JSON mal formé…
            c = Controle(i, fonction.__name__.removeprefix("controle_").capitalize())
            c.echec(f"contrôle impossible : {type(e).__name__} : {e}")
            controles.append(c)
    return controles


def en_echec(controles: list[Controle]) -> bool:
    return any(c.statut == ECHEC for c in controles)


def rapport(controles: list[Controle], dossier: str, version: str, demande: dict | None = None) -> str:
    """Rapport en français, un bloc par contrôle, puis le bilan."""
    entete = f"Contrôle de la demande fournisseur — {dossier} — {version}"
    if demande:
        entete += (f" (variante {demande.get('variante') or '?'}, "
                   + ("anonymisée)" if demande.get("anonymise") else "nommée)"))
    lignes = [entete, ""]
    for c in controles:
        lignes.append(f"{c.numero}. {c.titre} — {c.statut}" + (f" : {c.resume}" if c.resume else ""))
        lignes += [f"     - {d}" for d in c.details]
    n = {s: sum(c.statut == s for c in controles) for s in (OK, ECHEC, SANS_OBJET)}
    lignes += ["", f"Bilan : {n[OK]} OK, {n[ECHEC]} en échec, {n[SANS_OBJET]} sans objet."]
    if n[ECHEC]:
        lignes.append("À corriger avant toute relecture par Loïc : corriger la cause (étape 2, assembler.py, textes "
                      "de demande.json), relancer generer_livrable.py puis ce contrôle. Jamais le contrôle lui-même.")
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossier", help="dossier d'installation (chemin, ou nom dans dimensionnement/dossiers/)")
    ap.add_argument("version", help="version à contrôler : v1, v2… ou vN-<suffixe> (ex. v1-fabricant)")
    ap.add_argument("--ouvrir", action="store_true", help="si aucun échec : ouvrir le PDF et le mail HTML")
    a = ap.parse_args(argv)
    try:
        liv = charger(a.dossier, a.version)
    except ErreurControle as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 1
    controles = controler_livrable(liv)
    print(rapport(controles, liv.dossier.name, a.version, liv.demande))
    if en_echec(controles):
        return 1
    if a.ouvrir:
        if str(gl.ROOT) not in sys.path:
            sys.path.insert(0, str(gl.ROOT))
        from shared.rendu_html import ouvrir_page
        ouvrir_page(liv.pdf)
        variante = gl.slug(liv.demande.get("variante") or "grossiste")
        ouvrir_page(liv.dv / f"mail-{variante}.html")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
