"""Conformité F-gas d'un fluide frigorigène : PRP, tCO2e d'une charge, contrôle d'étanchéité, interdictions.

Lit trois tables du socle de savoir (dimensionnement/savoir/fluides/, versionnées, maintenues par Adrien) :
    prp.csv                     PRP à 100 ans de chaque fluide, sa source, son rapport du GIEC, sa classe
    compositions-melanges.csv   fractions massiques des mélanges (PRP recalculé selon l'annexe VI, en contrôle)
    reglementation-fgas.csv     règles du règlement (UE) 2024/573 (et 2024/590 pour le R22). TABLE NON RELUE
                                tant que la colonne relu_par est vide : chaque règle rendue porte alors la
                                mention « table non relue », avec son article et sa source.
Chaque nombre rendu est une Valeur (valeur.py) avec sa source et son statut. Un fluide inconnu donne
« à confirmer », jamais une exception. Aucune dépendance hors bibliothèque standard (pas de CoolProp ici).

Usage (bibliothèque, importée par calculs.py) :
    from fgas import prp, prp_melange_calcule, tco2e, seuil_controle_etancheite, regles_applicables
    from fgas import verdict_fluide, comparer_fluides
    prp("R449A")                                   → Valeur 1396, sans unité, « sourcé » (prp.csv)
    t = tco2e(Valeur(215, "kg", "plaque, photo p02-1", "sourcé", id="charge-a"), "R449A")
    t.texte()                                      → « 300,14 tCO2e »
    seuil_controle_etancheite(t)["frequence"]      → « au moins tous les 6 mois (12 mois avec système … ) »
    v = verdict_fluide("R449A", "centrale", 215)   → dict ; v["texte"] = 3 à 5 lignes pour le bloc D
    comparer_fluides("R449A", "R744", "centrale", 215)

Usage (ligne de commande, depuis la racine du dépôt) :
    python .claude/skills/froid-dimensionnement/scripts/fgas.py R449A --type centrale --charge 150
    python .claude/skills/froid-dimensionnement/scripts/fgas.py R449A --cible R744 --type centrale --charge 150
    options : --capacite <kW> (capacité nominale : départage les centrales ≥ 40 kW), --date AAAA-MM-JJ,
              --charge-cible <kg>, --json (sortie JSON avec les Valeur)
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import io
import re
import sys
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from valeur import A_CONFIRMER, ESPACE, SOURCE, Valeur, a_confirmer, calculer, en_json, nombre_fr  # noqa: E402

# ---------- chemins (calculés comme dans shared/savoir.py : racine = 4 niveaux au-dessus de scripts/) ----------
RACINE = Path(__file__).resolve().parents[4]        # scripts → froid-dimensionnement → skills → .claude → racine
DOSSIER_FLUIDES = RACINE / "dimensionnement" / "savoir" / "fluides"
PRP_CSV = "prp.csv"
COMPOSITIONS_CSV = "compositions-melanges.csv"
REGLEMENTATION_CSV = "reglementation-fgas.csv"

COLONNES_PRP = ("fluide", "type", "prp_100ans", "rapport_giec", "classe_securite_ashrae34", "source", "note")
COLONNES_COMPOSITIONS = ("melange", "composant", "fraction_massique", "source")
COLONNES_REGLEMENTATION = ("regle", "champ_application", "seuil_prp", "date_effet", "article", "source",
                           "relu_par", "date_relecture")

# ---------- constantes ----------
# 1 t = 1 000 kg : Brochure SI du BIPM, 9e édition (2019), tableau 8 (la tonne). Avec tCO2e = masse (t) × PRP
# (règlement (UE) 2024/573 art. 3 points 1 et 3, annexe VI ; ligne « PRP d'un mélange » de reglementation-fgas.csv).
KG_PAR_TONNE = 1000.0
# ± 1 % : tolérance de l'annexe VI du règlement (UE) 2024/573 (reprise dans reglementation-fgas.csv). Le texte la
# rattache aux fractions massiques ; ici elle sert de seuil d'alerte entre le PRP recalculé et celui de prp.csv
# (convention de contrôle, pas une règle du règlement).
TOLERANCE_PRP_PCT = 1.0
# Somme des fractions massiques d'un mélange : 1 à 0,001 près (compositions ASHRAE 34 données à 3 décimales au plus).
TOLERANCE_SOMME_FRACTIONS = 0.001
POURCENT = 100.0                                     # définition du pourcentage
MENTION_NON_RELUE = "table non relue"

# ---------- familles de fluides ----------
HFC = "HFC"
HFO = "HFO"
HCFC = "HCFC"
NON_FLUORE = "non fluoré"
FLUORES = frozenset({HFC, HFO})
TOUTES_FAMILLES = frozenset({HFC, HFO, HCFC, NON_FLUORE})

# Famille réglementaire des fluides purs de prp.csv (un mélange prend la famille de ses composants) :
#   HFC         annexe I section 1 du règlement (UE) 2024/573 : seuils en tCO2e ;
#   HFO         annexe II section 1 du même règlement (hydrofluorocarbures insaturés) : seuils en kg ;
#   HCFC        annexe I du règlement (UE) 2024/590 (substances appauvrissant la couche d'ozone) ;
#   non fluoré  molécule sans fluor (CO2, propane, isobutane, ammoniac) : PRP de l'annexe VI ou de l'art. 3,
#               mais hors des obligations du règlement 2024/573.
# Source : colonnes « source » et « note » de prp.csv (annexe citée ligne par ligne, lues le 2026-10-06).
FAMILLES_PURS = {
    "R22": HCFC,
    "R134a": HFC, "R32": HFC, "R125": HFC, "R143a": HFC, "R152a": HFC,
    "R1234yf": HFO, "R1234ze(E)": HFO,
    "R290": NON_FLUORE, "R600a": NON_FLUORE, "R744": NON_FLUORE, "R717": NON_FLUORE,
}

# Autres noms courants → nom de prp.csv (les noms CoolProp « R449A.mix », « CO2 »… sont reconnus aussi).
# Clés déjà normalisées (minuscules, sans accents, sans espace ni tiret).
ALIAS_FLUIDES = {
    "co2": "R744", "dioxydedecarbone": "R744", "carbondioxide": "R744",
    "propane": "R290", "isobutane": "R600a",
    "ammoniac": "R717", "ammonia": "R717", "nh3": "R717",
    "r1234ze": "R1234ze(E)",
}

# ---------- équipements : table de synonymes ----------
REFRIGERATION = "réfrigération"
CLIMATISATION = "climatisation"
CENTRALE = "centrale"
GROUPE = "groupe de condensation"
AUTONOME = "autonome"
REFROIDISSEUR = "refroidisseur"
BIBLOC = "bi-bloc"
ARTICLES_SOUS_TYPES = {CENTRALE: "une centrale", GROUPE: "un groupe de condensation",
                       AUTONOME: "un équipement autonome", REFROIDISSEUR: "un refroidisseur",
                       BIBLOC: "un système bi-bloc"}

# Type d'équipement dicté → (famille, sous-type, description). Lu dans l'ordre, le premier motif trouvé gagne
# (« groupe d'eau glacée » avant « groupe », « centrale » avant « chambre froide »). Motifs sans accents, cherchés
# en début de mot. Vocabulaire : dimensionnement/CLAUDE.md (« centrale », « groupe / unité de condensation ») et
# définitions du règlement (UE) 2024/573 citées dans reglementation-fgas.csv (centrale : art. 3 point 34 ;
# autonome : art. 3 point 38 ; refroidisseur : art. 3 point 44).
TYPES_EQUIPEMENT = (
    (("refroidisseur", "groupe d'eau glacee", "groupe eau glacee", "eau glacee", "chiller"),
     REFRIGERATION, REFROIDISSEUR, "refroidisseur (groupe d'eau glacée)"),
    (("split", "bi-bloc", "bibloc", "bi bloc"),
     CLIMATISATION, BIBLOC, "climatisation ou pompe à chaleur bi-bloc"),
    (("monobloc", "climatiseur mobile"),
     CLIMATISATION, AUTONOME, "climatiseur ou pompe à chaleur autonome (monobloc)"),
    (("centrale", "centralise", "multiposte", "rack"),
     REFRIGERATION, CENTRALE, "centrale (système centralisé multipostes, compresseurs en parallèle)"),
    (("groupe de condensation", "unite de condensation", "groupe frigorifique", "condensing unit", "groupe"),
     REFRIGERATION, GROUPE, "groupe de condensation (raccordé sur place)"),
    (("chambre froide", "chambre"),
     REFRIGERATION, GROUPE, "chambre froide, supposée desservie par un groupe de condensation "
                            "(si elle est sur une centrale : type « centrale »)"),
    (("meuble", "vitrine", "autonome", "plug-in", "plug in", "refrigerateur", "congelateur", "armoire"),
     REFRIGERATION, AUTONOME, "équipement de réfrigération autonome (meuble, vitrine)"),
    (("climatisation", "climatiseur", "clim", "pompe a chaleur", "pac"),
     CLIMATISATION, None, "climatisation ou pompe à chaleur (type non précisé)"),
    (("froid commercial", "refrigeration", "froid", "frigorifique"),
     REFRIGERATION, None, "réfrigération (type d'équipement non précisé)"),
)

# Champs d'application génériques de reglementation-fgas.csv (s'appliquent à tout équipement).
CHAMPS_GENERAUX = ("tous ", "tout ", "personnel", "installation, entretien", "en belgique", "appauvrissant")

# ---------- natures des règles ----------
NATURE_ENTRETIEN = "interdiction d'entretien"
NATURE_MARCHE = "interdiction de mise sur le marché"
NATURE_UTILISATION = "interdiction d'utilisation"
NATURE_SERVICE = "interdiction de mise en service"
NATURE_TOLERANCE = "tolérance"
NATURE_CALCUL = "règle de calcul"
NATURE_OBLIGATION = "obligation"

EN_VIGUEUR = "en vigueur"
A_VENIR = "à venir"
SANS_DATE = "sans date"
DATE_ILLISIBLE = "date illisible"
_RANG_ETAT = {EN_VIGUEUR: 0, SANS_DATE: 1, DATE_ILLISIBLE: 1, A_VENIR: 2}

MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre")

_N = r"(\d+(?:[.,]\d+)?)"                            # nombre dans le texte d'une règle (« 5 », « 0,5 »)
_OPERATEURS = {"≥": lambda a, b: a >= b, "≤": lambda a, b: a <= b, ">": lambda a, b: a > b, "<": lambda a, b: a < b}


# =====================================================================================================
# Outils de texte
# =====================================================================================================
def _norm(texte: Any) -> str:
    """Minuscules, sans accents, apostrophes droites, espaces simples (« ≥ », « − » sont gardés)."""
    t = unicodedata.normalize("NFKD", "" if texte is None else str(texte))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("’", "'").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", t).strip().lower()


def _cle(nom: Any) -> str:
    """Clé de recherche d'un fluide : « R-449A », « r449a », « R449A.mix », « HFC-134a » → « r449a », « r134a »."""
    t = re.sub(r"[\s\-_]", "", _norm(nom))
    if t.endswith(".mix"):
        t = t[:-4]
    m = re.match(r"(hcfc|hfc|hfo)(\d.*)", t)
    return "r" + m.group(2) if m else t


def _f(texte: str) -> float:
    return float(texte.replace(",", "."))


def _nombre_csv(texte: str) -> float | None:
    """« 1396 », « 0.501 », « 2 500 », « 0,02 » → float ; vide ou illisible → None."""
    t = re.sub(r"[\s  ]", "", texte or "").replace(",", ".")
    try:
        return float(t) if t else None
    except ValueError:
        return None


def _fmt(x: float) -> str:
    """Seuil écrit sans décimale inutile : 5.0 → « 5 », 2500.0 → « 2 500 », 0.5 → « 0,5 »."""
    if float(x).is_integer():
        return nombre_fr(x, 0)
    return nombre_fr(x, 3).rstrip("0").rstrip(",")


def date_fr(d: dt.date) -> str:
    """2025-01-01 → « 1er janvier 2025 »."""
    return f"{'1er' if d.day == 1 else d.day} {MOIS[d.month - 1]} {d.year}"


def _marque(v: Valeur, decimales: int) -> str:
    return v.texte(decimales)[len(v.texte(decimales, marque=False)):]


def texte_prp(v: Valeur) -> str:
    """Rendu d'un PRP (sans unité) : « 1 396 », « 146 », « 0,501 », « 0,02 », « 1 », « à confirmer »."""
    if v.nombre is None:
        return A_CONFIRMER
    d = 0 if (v.nombre >= 100 or float(v.nombre).is_integer()) else 3
    t = nombre_fr(v.nombre, d)
    if "," in t:
        t = t.rstrip("0").rstrip(",")
    return t + _marque(v, d)


def _texte_tco2e(v: Valeur) -> str:
    if v.nombre is not None and 0 < v.nombre < 0.01:
        return f"< 0,01{ESPACE}tCO2e" + _marque(v, 2)
    return v.texte()


def _texte_kg(v: Valeur) -> str:
    if v.nombre is None:
        return A_CONFIRMER
    return v.texte(0 if float(v.nombre).is_integer() else 1)


def _texte_mesure(v: Valeur, unite: str) -> str:
    return _texte_tco2e(v) if unite == "tCO2e" else _texte_kg(v)


# =====================================================================================================
# Chargement des tables (une fois par dossier ; vider_cache() après modification d'un CSV)
# =====================================================================================================
@dataclass(frozen=True)
class Regle:
    """Une ligne de reglementation-fgas.csv (ligne = numéro de ligne dans le fichier, commentaire compris)."""
    ligne: int
    regle: str
    champ_application: str
    seuil_prp: float | None
    date_effet: dt.date | None
    date_brute: str
    article: str
    source: str
    relu_par: str
    date_relecture: str


@dataclass(frozen=True)
class _Tranche:
    bornes_t: tuple | None
    bornes_kg: tuple | None
    mois: int
    mois_detection: int
    regle: Regle


@dataclass(frozen=True)
class _Etancheite:
    obligation: Regle | None
    seuil_t: float | None
    seuil_kg: float | None
    tranches: tuple
    detection: Regle | None
    detection_t: float | None
    detection_kg: float | None


@dataclass
class _Tables:
    prp: dict
    compositions: dict
    alias: dict
    regles: list
    etancheite: _Etancheite


_CACHE: dict[str, _Tables] = {}


def vider_cache() -> None:
    """Oublie les tables lues (à appeler après avoir modifié un CSV dans la même session Python)."""
    _CACHE.clear()
    _profil_champ.cache_clear()


def _lire_csv(nom: str, colonnes: tuple[str, ...]) -> list[tuple[int, dict]]:
    """Lit un CSV du socle ; ignore les lignes de commentaire « # » en tête. Rend (numéro de ligne, ligne)."""
    chemin = DOSSIER_FLUIDES / nom
    try:
        texte = chemin.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise FileNotFoundError(f"table introuvable : {chemin} (socle de savoir dimensionnement/savoir/fluides/)") from None
    lignes = texte.splitlines()
    debut = 0
    while debut < len(lignes) and (not lignes[debut].strip() or lignes[debut].lstrip().startswith("#")):
        debut += 1
    lecteur = csv.DictReader(io.StringIO("\n".join(lignes[debut:])))
    manquantes = [c for c in colonnes if c not in (lecteur.fieldnames or ())]
    if manquantes:
        raise ValueError(f"{nom} : colonne(s) manquante(s) {', '.join(manquantes)} ; "
                         f"colonnes attendues : {', '.join(colonnes)}")
    resultat = []
    for brute in lecteur:
        ligne = {k: (v or "").strip() for k, v in brute.items() if k}
        if any(ligne.values()):
            resultat.append((debut + lecteur.line_num, ligne))
    return resultat


def _bornes(n: str, unite: str) -> tuple | None:
    """Bornes de charge écrites dans une règle (texte normalisé) pour l'unité « tco2e » ou « kg » :
    « ≥ 5 et < 50 » → (5, 50) ; « ≥ 500 », « à partir de 5 », « ou de 1 », « ou 100 » → (x, None) ;
    « moins de 3 » → (None, 3). Aucune → None."""
    u = re.escape(unite)
    m = re.search(rf"≥\s*{_N}\s*et\s*<\s*{_N}\s*{u}\b", n)
    if m:
        return (_f(m[1]), _f(m[2]))
    m = re.search(rf"(?:≥|\ba partir de|\bou de|\bou)\s*{_N}\s*{u}\b", n)
    if m:
        return (_f(m[1]), None)
    m = re.search(rf"\bmoins de\s*{_N}\s*{u}\b", n)
    if m:
        return (None, _f(m[1]))
    return None


def _lire_etancheite(regles: list[Regle]) -> _Etancheite:
    """Seuils du contrôle d'étanchéité lus dans les règles (art. 5(1), 5(6), 6(1)), jamais codés en dur."""
    obligation = detection = None
    tranches = []
    for r in regles:
        n = _norm(r.regle)
        if n.startswith("controle d'etancheite obligatoire") and obligation is None:
            obligation = r
        elif n.startswith("frequence du controle d'etancheite"):
            m = re.search(r"tous les (\d+) mois \((\d+) mois avec", n)
            if m:
                tranches.append(_Tranche(_bornes(n, "tco2e"), _bornes(n, "kg"), int(m[1]), int(m[2]), r))
        elif n.startswith("systeme de detection des fuites obligatoire") and detection is None:
            detection = r

    def bas(r: Regle | None, unite: str) -> float | None:
        b = _bornes(_norm(r.regle), unite) if r else None
        return b[0] if b else None

    return _Etancheite(obligation, bas(obligation, "tco2e"), bas(obligation, "kg"), tuple(tranches),
                       detection, bas(detection, "tco2e"), bas(detection, "kg"))


def _charger() -> _Tables:
    prp_lignes = {}
    for num, l in _lire_csv(PRP_CSV, COLONNES_PRP):
        prp_lignes[l["fluide"]] = dict(l, _ligne=num)
    compositions: dict[str, list] = {}
    for num, l in _lire_csv(COMPOSITIONS_CSV, COLONNES_COMPOSITIONS):
        compositions.setdefault(l["melange"], []).append(
            (l["composant"], _nombre_csv(l["fraction_massique"]), l["source"], num))
    alias = {_cle(nom): nom for nom in list(compositions) + list(prp_lignes)}
    regles = []
    for num, l in _lire_csv(REGLEMENTATION_CSV, COLONNES_REGLEMENTATION):
        try:
            date_effet = dt.date.fromisoformat(l["date_effet"]) if l["date_effet"] else None
        except ValueError:
            date_effet = None
        regles.append(Regle(num, l["regle"], l["champ_application"], _nombre_csv(l["seuil_prp"]), date_effet,
                            l["date_effet"], l["article"], l["source"], l["relu_par"], l["date_relecture"]))
    return _Tables(prp_lignes, compositions, alias, regles, _lire_etancheite(regles))


def _tables() -> _Tables:
    cle = str(DOSSIER_FLUIDES)
    if cle not in _CACHE:
        _CACHE[cle] = _charger()
    return _CACHE[cle]


def regles_table() -> list[Regle]:
    """Toutes les règles de reglementation-fgas.csv, dans l'ordre du fichier."""
    return list(_tables().regles)


def _relecture(r: Regle) -> str:
    if not r.relu_par:
        return MENTION_NON_RELUE
    return f"relue par {r.relu_par}" + (f" le {r.date_relecture}" if r.date_relecture
                                         else " (date de relecture non renseignée)")


def _source_regle(r: Regle) -> str:
    return f"{REGLEMENTATION_CSV} ligne {r.ligne} ({_relecture(r)}) : {r.source or 'source non renseignée'}"


# =====================================================================================================
# Fluides : nom, famille, PRP
# =====================================================================================================
def nom_canonique(fluide: Any) -> str | None:
    """Nom du fluide tel qu'écrit dans prp.csv ou compositions-melanges.csv ; None s'il est inconnu."""
    t = _tables()
    k = _cle(fluide)
    if k in t.alias:
        return t.alias[k]
    cible = ALIAS_FLUIDES.get(k)
    return cible if cible in t.prp or cible in t.compositions else None


def _famille_nom(nom: str, vus: frozenset = frozenset()) -> str:
    if nom in FAMILLES_PURS:
        return FAMILLES_PURS[nom]
    comps = _tables().compositions.get(nom)
    if not comps or nom in vus:
        return A_CONFIRMER
    familles = {_famille_nom(c, vus | {nom}) for c, _, _, _ in comps}
    for f in (HFC, HFO, HCFC):              # un mélange qui contient un HFC relève de l'annexe I, etc.
        if f in familles:
            return f
    return NON_FLUORE if familles == {NON_FLUORE} else A_CONFIRMER


def famille(fluide: Any) -> str:
    """« HFC », « HFO », « HCFC », « non fluoré » ou « à confirmer » (fluide inconnu)."""
    nom = nom_canonique(fluide)
    return A_CONFIRMER if nom is None else _famille_nom(nom)


def _libelle_famille(nom: str, fam: str) -> str:
    comps = _tables().compositions.get(nom)
    if not comps:
        return fam
    if fam == HFC:
        return "mélange HFC/HFO" if any(_famille_nom(c) == HFO for c, _, _, _ in comps) else "mélange de HFC"
    return f"mélange {fam}"


def _id_fluide(fluide: Any) -> str:
    nom = nom_canonique(fluide)
    if nom:
        return nom
    t = re.sub(r"\s+", "-", str(fluide).strip()) if fluide is not None else ""
    return t or "inconnu"


def prp(fluide: str, id: str = "") -> Valeur:
    """PRP à 100 ans (sans unité) lu dans prp.csv ; source = colonne source + rapport du GIEC.
    Fluide inconnu → « à confirmer » (pas d'exception)."""
    ident = id or f"prp-{_id_fluide(fluide)}"
    nom = nom_canonique(fluide)
    ligne = _tables().prp.get(nom) if nom else None
    if ligne is None:
        return a_confirmer("", f"fluide « {fluide} » absent de {PRP_CSV} (dimensionnement/savoir/fluides/) : "
                               "PRP à confirmer", id=ident)
    n = _nombre_csv(ligne["prp_100ans"])
    if n is None:
        return a_confirmer("", f"{PRP_CSV} ligne {ligne['_ligne']} ({nom}) : PRP illisible « {ligne['prp_100ans']} »",
                           id=ident)
    rapport = ligne["rapport_giec"]
    ref = (f"rapport GIEC : {rapport}" if rapport.upper().startswith("AR")
           else f"référence : {rapport or 'non renseignée'}")
    return Valeur(n, "", f"{PRP_CSV} ({nom}) : {ligne['source']} ; {ref}", SOURCE, id=ident)


def prp_melange_calcule(fluide: str, id: str = "") -> Valeur:
    """PRP d'un mélange recalculé selon l'annexe VI du règlement (UE) 2024/573 : Σ fraction massique × PRP du
    composant (compositions-melanges.csv, prp.csv). Sert de contrôle de prp.csv : l'écart est écrit dans la
    source, et signalé s'il dépasse 1 %. Fluide pur ou inconnu → « à confirmer »."""
    nom = nom_canonique(fluide)
    ident = id or f"prp-calc-{_id_fluide(fluide)}"
    comps = _tables().compositions.get(nom) if nom else None
    if not comps:
        return a_confirmer("", f"« {fluide} » n'est pas un mélange de {COMPOSITIONS_CSV} : "
                               "pas de PRP recalculé (annexe VI)", id=ident)
    fractions = []
    for c, x, src, num in comps:
        if x is None:
            fractions.append(a_confirmer("", f"{COMPOSITIONS_CSV} ligne {num} ({nom}, {c}) : fraction illisible",
                                         id=f"x-{nom}-{c}"))
        else:
            fractions.append(Valeur(x, "", f"{COMPOSITIONS_CSV} ({nom}, {c}) : {src}", SOURCE, id=f"x-{nom}-{c}"))
    prps = [prp(c) for c, _, _, _ in comps]
    entrees = [v for paire in zip(fractions, prps) for v in paire]
    formule = " + ".join(f"{x.id} × {p.id}" for x, p in zip(fractions, prps))
    source = (f"calcul selon l'annexe VI du règlement (UE) 2024/573 : moyenne des PRP des composants pondérée par "
              f"les fractions massiques ({COMPOSITIONS_CSV}, {PRP_CSV})")
    if all(x.nombre is not None for x in fractions):
        somme_x = sum(x.nombre for x in fractions)
        if abs(somme_x - 1) > TOLERANCE_SOMME_FRACTIONS:
            source += f" ; attention : somme des fractions = {nombre_fr(somme_x, 3)} (≠ 1)"
    resultat = calculer(lambda: sum(x.nombre * p.nombre for x, p in zip(fractions, prps)), "", formule, entrees,
                        source=source, id=ident)
    if resultat.nombre is None:
        return resultat
    ref = prp(nom)
    if ref.nombre is None:
        controle = f"contrôle impossible : {nom} absent de {PRP_CSV} ou PRP illisible"
    elif ref.nombre == 0:
        controle = f"contrôle : {PRP_CSV} donne 0, écart relatif non calculable"
    else:
        ecart = (resultat.nombre - ref.nombre) / ref.nombre * POURCENT
        e = ("+" if ecart > 0 else "") + nombre_fr(ecart, 2) + ESPACE + "%"
        if abs(ecart) > TOLERANCE_PRP_PCT:
            controle = (f"ÉCART de {e} avec {PRP_CSV} ({texte_prp(ref)}) : supérieur à la tolérance de "
                        f"{_fmt(TOLERANCE_PRP_PCT)} %, à vérifier")
        else:
            controle = (f"contrôle : écart de {e} avec {PRP_CSV} ({texte_prp(ref)}), dans la tolérance de "
                        f"{_fmt(TOLERANCE_PRP_PCT)} %")
    return dataclasses.replace(resultat, source=f"{resultat.source} ; {controle}")


# =====================================================================================================
# Charge et tCO2e
# =====================================================================================================
def _valeur_charge(charge: Any, id: str = "charge") -> Valeur:
    """Valeur en kg ; un nombre devient « sourcé : charge donnée en argument » ; None → « à confirmer »."""
    if charge is None:
        return a_confirmer("kg", "charge non fournie", id=id)
    if isinstance(charge, Valeur):
        if charge.unite != "kg":
            raise ValueError(f"charge « {charge.reference()} » en « {charge.unite} » : unité attendue « kg »")
        v = charge
    elif isinstance(charge, bool) or not isinstance(charge, (int, float)):
        raise TypeError(f"charge invalide {charge!r} : attendu une Valeur en kg, un nombre ou None")
    else:
        v = Valeur(float(charge), "kg", "charge donnée en argument", SOURCE, id=id)
    if v.nombre is not None and v.nombre < 0:
        raise ValueError(f"charge « {v.reference()} » négative : {v.nombre}")
    return v


def _regle_calcul() -> Regle | None:
    return next((r for r in _tables().regles if "moyenne ponderee" in _norm(r.regle)), None)


def tco2e(charge_kg: Valeur, fluide: str, id: str = "") -> Valeur:
    """tCO2e d'une charge : charge (kg) × PRP ÷ 1000, avec la formule et les entrées. Charge ou PRP inconnu →
    « à confirmer » (la source dit ce qui bloque). Accepte aussi un nombre (kg) ou None."""
    charge = _valeur_charge(charge_kg)
    p = prp(fluide)
    r = _regle_calcul()
    reference = (f"{REGLEMENTATION_CSV} ligne {r.ligne}, {r.article} ({_relecture(r)})" if r
                 else "règlement (UE) 2024/573, annexe VI")
    return calculer(lambda: charge.nombre * p.nombre / KG_PAR_TONNE, "tCO2e",
                    f"{charge.reference()} × {p.reference()} ÷ 1000", [charge, p],
                    source=f"calcul : tCO2e = charge (kg) × PRP ÷ 1000 ; {reference}",
                    id=id or f"tco2e-{_id_fluide(fluide)}")


# =====================================================================================================
# Contrôle d'étanchéité
# =====================================================================================================
def _dans_bornes(x: float, bornes: tuple) -> bool:
    mini, maxi = bornes
    return (mini is None or x >= mini) and (maxi is None or x < maxi)


def _texte_bornes(bornes: tuple, unite: str) -> str:
    mini, maxi = bornes
    if mini is not None and maxi is not None:
        return f"≥ {_fmt(mini)} et < {_fmt(maxi)} {unite}"
    if mini is not None:
        return f"≥ {_fmt(mini)} {unite}"
    return f"< {_fmt(maxi)} {unite}"


def _seuil_etancheite(mesure: Valeur, unite: str) -> dict:
    """Seuil et fréquence du contrôle d'étanchéité pour une charge en tCO2e (annexe I) ou en kg (annexe II)."""
    e = _tables().etancheite
    tco2 = unite == "tCO2e"
    seuil = e.seuil_t if tco2 else e.seuil_kg
    detection = e.detection_t if tco2 else e.detection_kg
    tranches = [(tr.bornes_t if tco2 else tr.bornes_kg, tr) for tr in e.tranches]
    tranches = [(b, tr) for b, tr in tranches if b]
    res = {"mesure": mesure, "unite": unite, "soumis": None, "tranche": A_CONFIRMER, "frequence": A_CONFIRMER,
           "frequence_mois": None, "frequence_mois_avec_detection": None, "detection_fuites_obligatoire": None,
           "seuils": sorted({b[0] for b, _ in tranches if b[0] is not None}), "texte": "", "article": "",
           "source": "", "relecture": ""}
    if e.obligation is None or seuil is None or not tranches:
        res.update(texte=f"Contrôle d'étanchéité : seuils introuvables dans {REGLEMENTATION_CSV}, à confirmer.",
                   source=REGLEMENTATION_CSV, relecture=MENTION_NON_RELUE)
        return res
    ob = e.obligation
    base = dict(article=ob.article, source=_source_regle(ob), relecture=_relecture(ob))
    if mesure.nombre is None:
        mois = ", ".join(str(tr.mois) for _, tr in tranches)
        res.update(base, texte=(f"Contrôle d'étanchéité : charge à confirmer ; obligatoire à partir de {_fmt(seuil)} "
                                f"{unite} ({ob.article}), puis tous les {mois} mois selon la tranche."))
        return res
    x = mesure.nombre
    if x < seuil:
        res.update(base, soumis=False, tranche=_texte_bornes((None, seuil), unite), frequence="aucune (sous le seuil)",
                   detection_fuites_obligatoire=False,
                   texte=(f"Contrôle d'étanchéité : non obligatoire, {_texte_mesure(mesure, unite)} sous le seuil "
                          f"de {_fmt(seuil)} {unite} ({ob.article})."))
        return res
    choix = next(((b, tr) for b, tr in tranches if _dans_bornes(x, b)), None)
    if choix is None:
        res.update(base, soumis=True,
                   texte=(f"Contrôle d'étanchéité : obligatoire ({ob.article}), mais aucune tranche de "
                          f"{REGLEMENTATION_CSV} ne contient {_texte_mesure(mesure, unite)} : à confirmer."))
        return res
    bornes, tr = choix
    det = detection is not None and x >= detection
    frequence = f"au moins tous les {tr.mois} mois ({tr.mois_detection} mois avec système de détection des fuites)"
    regles = [tr.regle] + ([e.detection] if det else [])
    texte = (f"Contrôle d'étanchéité : {frequence}, charge de {_texte_mesure(mesure, unite)} dans la tranche "
             f"{_texte_bornes(bornes, unite)} ({tr.regle.article})")
    if det:
        texte += f" ; système de détection des fuites obligatoire ({e.detection.article})"
    relectures = {_relecture(r) for r in regles}
    res.update(soumis=True, tranche=_texte_bornes(bornes, unite), frequence=frequence, frequence_mois=tr.mois,
               frequence_mois_avec_detection=tr.mois_detection, detection_fuites_obligatoire=det, texte=texte + ".",
               article=" ; ".join(r.article for r in regles), source=" | ".join(_source_regle(r) for r in regles),
               relecture=MENTION_NON_RELUE if MENTION_NON_RELUE in relectures else " ; ".join(sorted(relectures)))
    return res


def seuil_controle_etancheite(tco2e: Valeur) -> dict:
    """Contrôle d'étanchéité pour une charge en tCO2e (gaz de l'annexe I) : seuils 5, 50, 500 tCO2e lus dans
    reglementation-fgas.csv. Clés : mesure, unite, soumis (bool | None), tranche, frequence, frequence_mois,
    frequence_mois_avec_detection, detection_fuites_obligatoire, seuils, texte, article, source, relecture."""
    if not isinstance(tco2e, Valeur):
        raise TypeError(f"seuil_controle_etancheite : Valeur en tCO2e attendue, reçu {tco2e!r}")
    if tco2e.unite != "tCO2e":
        raise ValueError(f"seuil_controle_etancheite : « {tco2e.reference()} » en « {tco2e.unite} », "
                         "unité attendue « tCO2e »")
    return _seuil_etancheite(tco2e, "tCO2e")


# =====================================================================================================
# Équipement et champ d'application des règles
# =====================================================================================================
@dataclass(frozen=True)
class Equipement:
    type_dicte: str
    famille: str | None
    sous_type: str | None
    hermetique: bool | None
    capacite_kw: float | None
    reconnu: bool
    description: str

    def vers_dict(self) -> dict:
        return dataclasses.asdict(self)


def _capacite(capacite_kw: Any) -> float | None:
    if capacite_kw is None:
        return None
    if isinstance(capacite_kw, Valeur):
        if capacite_kw.unite != "kW":
            raise ValueError(f"capacité « {capacite_kw.reference()} » en « {capacite_kw.unite} » : "
                             "unité attendue « kW »")
        return capacite_kw.nombre
    if isinstance(capacite_kw, bool) or not isinstance(capacite_kw, (int, float)):
        raise TypeError(f"capacité invalide {capacite_kw!r} : attendu un nombre de kW, une Valeur ou None")
    return float(capacite_kw)


def decrire_equipement(type_equipement: str, capacite_kw: Any = None) -> Equipement:
    """Type dicté (« centrale », « groupe de condensation », « chambre froide », « climatisation »…) → famille et
    sous-type par la table TYPES_EQUIPEMENT. Type non reconnu : famille et sous-type None (règles sous conditions)."""
    t = _norm(type_equipement)
    famille_eq = sous_type = None
    reconnu = False
    description = (f"type « {type_equipement} » non reconnu : chaque règle est listée avec son champ "
                   "d'application en condition")
    for motifs, fam, st, desc in TYPES_EQUIPEMENT:
        if any(re.search(r"(?<![a-z0-9])" + re.escape(m), t) for m in motifs):
            famille_eq, sous_type, description, reconnu = fam, st, desc, True
            break
    if re.search(r"(?<!non )hermetique", t):
        hermetique = True
    elif "non hermetique" in t or sous_type in (CENTRALE, GROUPE, BIBLOC):
        hermetique = False                   # raccordé sur place : supposé non hermétiquement scellé
    else:
        hermetique = None
    return Equipement(str(type_equipement or ""), famille_eq, sous_type, hermetique, _capacite(capacite_kw),
                      reconnu, description)


@dataclass(frozen=True)
class _Profil:
    familles: frozenset
    sous_type: str | None
    hermetique: bool | None
    exclus: frozenset
    exclus_points: tuple
    capacite: tuple
    variante: str
    autres: bool
    soumis: bool
    vise_annexe_iv: bool
    exemptions: str
    interprete: bool


@lru_cache(maxsize=None)
def _profil_champ(champ: str) -> _Profil:
    """Lecture d'une chaîne « champ_application » du CSV : familles, sous-type exigé, exclusions (« sauf … »),
    capacité nominale, exemptions (« ; exemptés : … »)."""
    morceaux = re.split(r"\s*;\s*exempt[ée]s?\s*:\s*", champ or "", maxsplit=1)
    exemptions = morceaux[1].strip() if len(morceaux) > 1 else ""
    n = _norm(morceaux[0])
    m = re.search(r"\bsauf\b", n)
    positif, exclusion = (n[:m.start()], n[m.start():]) if m else (n, "")
    familles = set()
    if re.search(r"climati|pompes? a chaleur|bi-blocs?|\bsplit\b", positif):
        familles.add(CLIMATISATION)
    if re.search(r"refrigera|refroidisseur", positif):
        familles.add(REFRIGERATION)
    sous_type = None
    if "refroidisseur" in positif:
        sous_type = REFROIDISSEUR
    elif re.search(r"centralise|\bcentrales?\b", positif):
        sous_type = CENTRALE
    elif re.search(r"bi-blocs?|\bsplit\b", positif):
        sous_type = BIBLOC
    elif re.search(r"autonome|refrigerateurs et congelateurs|monobloc", positif):
        sous_type = AUTONOME
    hermetique = False if "non hermetiquement" in positif else (True if "hermetiquement scelle" in positif else None)
    exclus = frozenset({REFROIDISSEUR}) if "refroidisseur" in exclusion else frozenset()
    mp = re.search(r"\bpoints?\b(.*?)(?:de l'annexe|$)", exclusion)
    points = tuple(re.findall(r"\d+", re.sub(r"\([^)]*\)", "", mp.group(1)))) if mp else ()
    capacite = []
    motif = r"capacite nominale\s*([≥≤<>])\s*" + _N + r"\s*kw(?:\s*et\s*([≥≤<>])\s*" + _N + r"\s*kw)?"
    for op1, v1, op2, v2 in re.findall(motif, positif):
        capacite.append((op1, _f(v1)))
        if op2:
            capacite.append((op2, _f(v2)))
    variante = "air-eau" if "air-eau" in positif else ("air-air" if "air-air" in positif else "")
    soumis = "soumis" in positif and "5(1)" in positif
    vise = "vises par" in positif and "annexe iv" in positif
    interprete = (bool(familles or sous_type or hermetique is not None or soumis or vise or capacite)
                  or any(g in positif for g in CHAMPS_GENERAUX))
    return _Profil(frozenset(familles), sous_type, hermetique, exclus, points, tuple(capacite), variante,
                   positif.startswith("autres"), soumis, vise, exemptions, interprete)


def _profil_point(point: str) -> _Profil | None:
    """Profil du champ de la règle qui porte « annexe IV point <n> » (pour résoudre « sauf points 4 et 6 »)."""
    for r in _tables().regles:
        if re.search(rf"annexe iv point {re.escape(point)}\b", _norm(r.article)):
            return _profil_champ(r.champ_application)
    return None


def _evaluer_profil(p: _Profil, eq: Equipement, points: bool = True) -> tuple[bool | None, list[str], list[str]]:
    """(True, [], []) : s'applique ; (False, …) : ne s'applique pas ; (None, si…, sauf si…) : sous conditions."""
    pos: list[str] = []
    neg: list[str] = []
    if p.familles:
        if eq.famille is None:
            pos.append("l'équipement relève de la " + " ou de la ".join(sorted(p.familles)))
        elif eq.famille not in p.familles:
            return False, [], []
    if p.sous_type:
        if eq.sous_type is None:
            pos.append(f"l'équipement est {ARTICLES_SOUS_TYPES[p.sous_type]}")
        elif eq.sous_type != p.sous_type:
            return False, [], []
    if p.hermetique is not None:
        if eq.hermetique is None:
            pos.append("l'équipement " + ("est" if p.hermetique else "n'est pas") + " hermétiquement scellé")
        elif eq.hermetique != p.hermetique:
            return False, [], []
    for x in sorted(p.exclus):
        if eq.sous_type == x:
            return False, [], []
        if eq.sous_type is None:
            neg.append(f"l'équipement est {ARTICLES_SOUS_TYPES[x]}")
    for op, val in p.capacite:
        if eq.capacite_kw is None:
            pos.append(f"capacité nominale {op} {_fmt(val)} kW")
        elif not _OPERATEURS[op](eq.capacite_kw, val):
            return False, [], []
    if p.variante:
        pos.append(f"système {p.variante}")
    if p.autres:
        pos.append("capacité hors des tranches des lignes voisines du même point (à vérifier)")
    if points:
        for point in p.exclus_points:
            q = _profil_point(point)
            if q is None:
                neg.append(f"l'équipement relève de l'annexe IV point {point}")
                continue
            etat, qpos, _ = _evaluer_profil(q, eq, points=False)
            if etat is True:
                return False, [], []
            if etat is None:
                neg.append(" et ".join(qpos) + f" (annexe IV point {point})")
    return (None if pos or neg else True), pos, neg


# =====================================================================================================
# Règles applicables
# =====================================================================================================
def _nature(regle: str) -> str:
    n = _norm(regle)
    if n.startswith(("fin de la tolerance", "exception")):
        return NATURE_TOLERANCE
    if "utilisation interdite" in n:
        return NATURE_UTILISATION
    if re.search(r"\b(entretien|maintenance)\b", n) and re.search(r"\binterdite?s?\b", n):
        return NATURE_ENTRETIEN
    if "mise sur le marche interdite" in n:
        return NATURE_MARCHE
    if "mise en service interdite" in n:
        return NATURE_SERVICE
    if "moyenne ponderee" in n:
        return NATURE_CALCUL
    return NATURE_OBLIGATION


def _interdit_marche(regle: str, nature: str) -> bool:
    return nature == NATURE_MARCHE or (nature == NATURE_UTILISATION
                                       and re.search(r"mise sur le marche.*interdite", _norm(regle)) is not None)


def _familles_fluide(regle: str, champ: str) -> frozenset:
    """Familles de fluides visées par une règle, d'après son texte (« des HFC », « gaz de l'annexe I »,
    « gaz fluorés », « HCFC »…). Rien de précis : gaz fluorés (HFC et HFO), objet du règlement 2024/573."""
    n, c = _norm(regle), _norm(champ)
    if "hcfc" in n or "appauvrissant" in c:
        return frozenset({HCFC})
    if c.startswith("tous gaz"):
        return TOUTES_FAMILLES
    familles = set()
    if re.search(r"\bdes hfc\b", n) or re.search(r"\bannexe i\b", n):
        familles.add(HFC)
    if re.search(r"\bannexe ii section 1\b", n):
        familles.add(HFO)
    if re.search(r"\bgaz fluores?\b", n):
        familles |= FLUORES
    return frozenset(familles) or FLUORES


def _texte_familles(familles: frozenset) -> str:
    if familles == frozenset({HFC}):
        return "un HFC ou un mélange contenant des HFC"
    if familles == FLUORES:
        return "un gaz fluoré (HFC ou HFO)"
    return " ou ".join(sorted(familles))


def _etat(r: Regle, jour: dt.date) -> tuple[str, str]:
    if r.date_effet is None:
        if r.date_brute:
            return DATE_ILLISIBLE, f"date d'effet illisible dans la table (« {r.date_brute} »)"
        return SANS_DATE, "date d'effet non renseignée dans la table"
    if r.date_effet <= jour:
        return EN_VIGUEUR, f"en vigueur depuis le {date_fr(r.date_effet)}"
    return A_VENIR, f"à venir le {date_fr(r.date_effet)}"


@dataclass(frozen=True)
class _Contexte:
    nom: str
    connu: bool
    famille: str
    prp: Valeur
    charge: Valeur
    tco2e: Valeur
    equipement: Equipement
    jour: dt.date


def _jour(date: Any) -> dt.date:
    if date is None:
        return dt.date.today()
    if isinstance(date, dt.datetime):
        return date.date()
    if isinstance(date, dt.date):
        return date
    try:
        return dt.date.fromisoformat(str(date).strip())
    except ValueError:
        raise ValueError(f"date illisible « {date} » (format attendu : AAAA-MM-JJ)") from None


def _contexte(fluide: Any, type_equipement: str, charge_kg: Any, date: Any, capacite_kw: Any) -> _Contexte:
    nom = nom_canonique(fluide)
    charge = _valeur_charge(charge_kg)
    return _Contexte(nom or _id_fluide(fluide), nom is not None,
                     A_CONFIRMER if nom is None else _famille_nom(nom), prp(fluide), charge, tco2e(charge, fluide),
                     decrire_equipement(type_equipement, capacite_kw), _jour(date))


def _evaluer_regle(r: Regle, ctx: _Contexte) -> dict | None:
    conditions: list[str] = []
    familles = _familles_fluide(r.regle, r.champ_application)
    if ctx.famille == A_CONFIRMER:
        if familles != TOUTES_FAMILLES:
            conditions.append(f"si le fluide est {_texte_familles(familles)}")
    elif ctx.famille not in familles:
        return None
    if r.seuil_prp is not None:
        if ctx.prp.nombre is None:
            conditions.append(f"si le PRP du fluide est ≥ {_fmt(r.seuil_prp)} (PRP à confirmer)")
        elif ctx.prp.nombre < r.seuil_prp:
            return None
    profil = _profil_champ(r.champ_application)
    etat_champ, pos, neg = _evaluer_profil(profil, ctx.equipement)
    if etat_champ is False:
        return None
    conditions += [f"si {p}" for p in pos] + [f"sauf si {x}" for x in neg]
    # charge : bornes écrites dans la règle, ou seuil du contrôle d'étanchéité (« équipements soumis à l'art. 5(1) »)
    n = _norm(r.regle)
    bornes_t, bornes_kg = _bornes(n, "tco2e"), _bornes(n, "kg")
    if profil.soumis:
        e = _tables().etancheite
        bornes_t = bornes_t or ((e.seuil_t, None) if e.seuil_t is not None else None)
        bornes_kg = bornes_kg or ((e.seuil_kg, None) if e.seuil_kg is not None else None)
    bornes = None
    if ctx.famille == HFO and bornes_kg:
        bornes, unite, mesure = bornes_kg, "kg", ctx.charge
    elif bornes_t:
        bornes, unite, mesure = bornes_t, "tCO2e", ctx.tco2e
    elif bornes_kg:
        bornes, unite, mesure = bornes_kg, "kg", ctx.charge
    if bornes:
        if mesure.nombre is None:
            conditions.append(f"si la charge est {_texte_bornes(bornes, unite)} (charge à confirmer)")
        elif not _dans_bornes(mesure.nombre, bornes):
            return None
    if not profil.interprete:
        conditions.append("champ d'application non interprété par le script : à lire")
    statut, etat = _etat(r, ctx.jour)
    nature = _nature(r.regle)
    return {
        "ligne": r.ligne,
        "regle": r.regle,
        "champ_application": r.champ_application,
        "nature": nature,
        "interdit_entretien": nature in (NATURE_ENTRETIEN, NATURE_UTILISATION),
        "interdit_mise_sur_le_marche": _interdit_marche(r.regle, nature),
        "seuil_prp": r.seuil_prp,
        "date_effet": r.date_effet.isoformat() if r.date_effet else None,
        "statut": statut,
        "etat": etat,
        "applicable": None if conditions else True,
        "conditions": conditions,
        "exemptions": profil.exemptions,
        "article": r.article,
        "source": r.source,
        "relecture": _relecture(r),
    }


def _regles(ctx: _Contexte) -> list[dict]:
    retenues, visees = [], []
    for r in _tables().regles:
        d = _evaluer_regle(r, ctx)
        if d is not None:
            (visees if _profil_champ(r.champ_application).vise_annexe_iv else retenues).append(d)
    marche = [d for d in retenues if d["interdit_mise_sur_le_marche"]]
    if marche:                     # « équipements visés par l'annexe IV » : seulement si une interdiction les vise
        sure = any(d["applicable"] is True for d in marche)
        for d in visees:
            if not sure:
                d["conditions"].append("si l'une des interdictions de mise sur le marché listées s'applique")
                d["applicable"] = None
            retenues.append(d)
    return sorted(retenues, key=lambda d: d["ligne"])


def regles_applicables(fluide: str, type_equipement: str, charge_kg: Any = None, date: Any = None,
                       capacite_kw: Any = None) -> list[dict]:
    """Règles de reglementation-fgas.csv qui visent ce fluide et cet équipement, filtrées par famille du fluide,
    seuil de PRP (la règle s'applique si PRP ≥ seuil), champ d'application (table de synonymes), charge et date
    (passée : « en vigueur », future : « à venir le … »). Une donnée manquante n'écarte jamais une règle : elle
    devient une condition. Clés de chaque règle : ligne, regle, champ_application, nature, interdit_entretien,
    interdit_mise_sur_le_marche, seuil_prp, date_effet (AAAA-MM-JJ | None), statut, etat, applicable
    (True | None = sous conditions), conditions, exemptions, article, source, relecture (« table non relue »)."""
    return _regles(_contexte(fluide, type_equipement, charge_kg, date, capacite_kw))


# =====================================================================================================
# Verdict d'un fluide et comparaison
# =====================================================================================================
def _quand(statut: str, date_iso: str | None, ref: str) -> str:
    """« depuis le 1er janvier 2025 (ref) », « à partir du … (ref) » ou « (ref ; date d'effet non renseignée …) »."""
    if statut == EN_VIGUEUR and date_iso:
        return f"depuis le {date_fr(dt.date.fromisoformat(date_iso))} ({ref})"
    if statut == A_VENIR and date_iso:
        return f"à partir du {date_fr(dt.date.fromisoformat(date_iso))} ({ref})"
    return f"({ref} ; date d'effet non renseignée dans la table)"


def _tri_interdiction(d: dict) -> tuple:
    return (0 if d["applicable"] is True else 1, _RANG_ETAT.get(d["statut"], 1), d["date_effet"] or "")


def _synthese(regles: list[dict], cle: str, ctx: _Contexte) -> dict:
    candidats = sorted((d for d in regles if d[cle]), key=_tri_interdiction)
    cas = [{k: d[k] for k in ("ligne", "statut", "etat", "date_effet", "seuil_prp", "article", "conditions",
                              "applicable", "relecture")} for d in candidats]
    res = {"statut": "aucune", "statut_regle": "", "date": None, "seuil_prp": None, "article": "", "source": "",
           "conditions": [], "relecture": "", "tolerances": [], "cas": cas, "texte": ""}
    if not ctx.connu:
        res["statut"] = A_CONFIRMER
        return res
    if not candidats:
        return res
    choix = candidats[0]
    res.update(statut=choix["statut"] if choix["applicable"] is True else "sous conditions",
               statut_regle=choix["statut"], date=choix["date_effet"], seuil_prp=choix["seuil_prp"],
               article=choix["article"], source=f"{REGLEMENTATION_CSV} ligne {choix['ligne']} : {choix['source']}",
               conditions=list(choix["conditions"]), relecture=choix["relecture"])
    if cle == "interdit_entretien":
        res["tolerances"] = [{k: d[k] for k in ("ligne", "regle", "statut", "etat", "date_effet", "article",
                                                 "relecture")}
                             for d in regles if d["nature"] == NATURE_TOLERANCE and d["seuil_prp"] == choix["seuil_prp"]]
    return res


def _texte_entretien(s: dict) -> str:
    debut = "Entretien et recharge : "
    if s["statut"] == A_CONFIRMER:
        return debut + f"à confirmer (fluide absent de {PRP_CSV})."
    if s["statut"] == "aucune":
        return debut + "aucune interdiction dans la table pour ce fluide et cet équipement."
    seuil = f"PRP ≥ {_fmt(s['seuil_prp'])}, " if s["seuil_prp"] is not None else ""
    quand = _quand(s["statut_regle"], s["date"], f"{seuil}{s['article']}")
    t = f"encore autorisés, interdits {quand}" if s["statut_regle"] == A_VENIR else f"interdits {quand}"
    if s["conditions"]:
        t += ", " + ", ".join(s["conditions"])
    for tol in s["tolerances"]:
        n = _norm(tol["regle"])
        if n.startswith("fin de la tolerance") and tol["date_effet"]:
            fin = date_fr(dt.date.fromisoformat(tol["date_effet"]))
            t += f" ; gaz régénéré ou recyclé toléré jusqu'au {fin} ({tol['article']})"
        elif "regenere" in n:
            t += f" ; exception pour le gaz régénéré ou recyclé ({tol['article']})"
        else:
            t += f" ; exception ({tol['article']})"
    return debut + t + "."


def _texte_marche(s: dict) -> str:
    debut = "Équipement neuf de ce type avec ce fluide : "
    if s["statut"] == A_CONFIRMER:
        return debut + f"à confirmer (fluide absent de {PRP_CSV})."
    if s["statut"] == "aucune":
        return debut + "aucune interdiction de mise sur le marché dans la table."
    cas = s["cas"]
    if cas and cas[0]["applicable"] is True:            # une interdiction sûre : les autres sûres n'apportent rien
        cas = [cas[0]] + [c for c in cas[1:] if c["applicable"] is not True]
    morceaux = []
    for c in cas[:3]:
        m = f"mise sur le marché interdite {_quand(c['statut'], c['date_effet'], c['article'])}"
        if c["conditions"]:
            m += " " + ", ".join(c["conditions"])
        morceaux.append(m)
    t = debut + " ; ".join(morceaux)
    if len(cas) > 3:
        t += f" ; et {len(cas) - 3} autre(s) cas sous conditions (voir la liste des règles)"
    return t + "."


def _etancheite_fluide(ctx: _Contexte) -> dict:
    hors_table = {"mesure": ctx.tco2e, "unite": "tCO2e", "frequence_mois": None, "frequence_mois_avec_detection": None,
                  "seuils": [], "article": "", "relecture": "",
                  "source": f"famille du fluide (FAMILLES_PURS de fgas.py, d'après {PRP_CSV})"}
    if ctx.famille == NON_FLUORE:
        return dict(hors_table, soumis=False, tranche="non concerné", frequence="aucune (hors règlement F-gas)",
                    detection_fuites_obligatoire=False,
                    texte=("Contrôle d'étanchéité F-gas : non concerné (fluide non fluoré, hors du règlement "
                           "(UE) 2024/573)."))
    if ctx.famille == HCFC:
        return dict(hors_table, soumis=None, tranche=A_CONFIRMER, frequence=A_CONFIRMER,
                    detection_fuites_obligatoire=None,
                    texte="Contrôle d'étanchéité : HCFC, relève du règlement (UE) 2024/590, non couvert par la table.")
    if ctx.famille == HFO:
        return _seuil_etancheite(ctx.charge, "kg")
    return _seuil_etancheite(ctx.tco2e, "tCO2e")


def _texte_verdict(ctx: _Contexte, ligne_prp: dict | None, etancheite: dict, entretien: dict, marche: dict,
                   regles: list[dict]) -> str:
    lignes = []
    if not ctx.connu:
        lignes.append(f"Fluide « {ctx.nom} » absent de {PRP_CSV} : famille, PRP et tCO2e à confirmer "
                      "(ajouter le fluide au socle de savoir avant de conclure).")
        lignes.append(f"Règles F-gas : à confirmer ; {len(regles)} règle(s) possible(s) listée(s) sous conditions.")
    else:
        classe = (ligne_prp or {}).get("classe_securite_ashrae34") or A_CONFIRMER
        charge = (f"charge {_texte_kg(ctx.charge)}, soit {_texte_tco2e(ctx.tco2e)}" if ctx.charge.nombre is not None
                  else "charge à confirmer (tCO2e à confirmer)")
        lignes.append(f"{ctx.nom} ({_libelle_famille(ctx.nom, ctx.famille)}, classe {classe}) : "
                      f"PRP {texte_prp(ctx.prp)} ; {charge}.")
        lignes.append(etancheite["texte"])
        if ctx.famille == NON_FLUORE:
            lignes.append("Règles de sécurité hors F-gas (EN 378, équipements sous pression) : "
                          "non couvertes par cette table.")
        else:
            lignes.append(entretien["texte"])
            lignes.append(marche["texte"])
    fin = []
    if not ctx.equipement.reconnu:
        fin.append(f"Type d'équipement « {ctx.equipement.type_dicte} » non reconnu : règles listées sous conditions.")
    if any(not r.relu_par for r in _tables().regles):
        fin.append("Table F-gas non relue : à vérifier sur EUR-Lex avant de s'en servir devant un client.")
    if fin:
        lignes.append(" ".join(fin))
    return "\n".join(lignes)


def verdict_fluide(fluide: str, type_equipement: str, charge_kg: Any = None, date: Any = None,
                   capacite_kw: Any = None) -> dict:
    """Bloc D d'un fluide : PRP, tCO2e, contrôle d'étanchéité, interdiction d'entretien, interdiction de mise sur
    le marché, règles applicables et un texte français de 3 à 5 lignes. Clés : fluide, fluide_connu, famille,
    type_fluide, classe_securite, equipement, date, prp, charge, tco2e, etancheite, interdiction_entretien,
    interdiction_mise_sur_le_marche, regles, relecture, texte."""
    ctx = _contexte(fluide, type_equipement, charge_kg, date, capacite_kw)
    t = _tables()
    ligne_prp = t.prp.get(ctx.nom) if ctx.connu else None
    regles = _regles(ctx)
    etancheite = _etancheite_fluide(ctx)
    entretien = _synthese(regles, "interdit_entretien", ctx)
    marche = _synthese(regles, "interdit_mise_sur_le_marche", ctx)
    entretien["texte"] = _texte_entretien(entretien)
    marche["texte"] = _texte_marche(marche)
    non_relues = sum(1 for r in t.regles if not r.relu_par)
    type_fluide = (ligne_prp or {}).get("type") or ("mélange" if ctx.nom in t.compositions else A_CONFIRMER)
    return {
        "fluide": ctx.nom,
        "fluide_connu": ctx.connu,
        "famille": ctx.famille,
        "type_fluide": type_fluide,
        "classe_securite": (ligne_prp or {}).get("classe_securite_ashrae34") or A_CONFIRMER,
        "equipement": ctx.equipement.vers_dict(),
        "date": ctx.jour.isoformat(),
        "prp": ctx.prp,
        "charge": ctx.charge,
        "tco2e": ctx.tco2e,
        "etancheite": etancheite,
        "interdiction_entretien": entretien,
        "interdiction_mise_sur_le_marche": marche,
        "regles": regles,
        "relecture": (f"{MENTION_NON_RELUE} ({non_relues} règle(s) sur {len(t.regles)} sans relecture)"
                      if non_relues else "table relue"),
        "texte": _texte_verdict(ctx, ligne_prp, etancheite, entretien, marche, regles),
    }


def comparer_fluides(fluide_actuel: str, fluide_cible: str, type_equipement: str, charge_kg_actuelle: Any = None,
                     charge_kg_cible: Any = None, date: Any = None, capacite_kw: Any = None) -> dict:
    """Les deux verdicts côte à côte + rapport PRP cible / PRP actuel. La charge du fluide cible est « à confirmer »
    sauf si elle est donnée. Clés : actuel, cible, rapport_prp (Valeur), variation_prp (Valeur en %), texte."""
    actuel = verdict_fluide(fluide_actuel, type_equipement, charge_kg_actuelle, date, capacite_kw)
    cible = verdict_fluide(fluide_cible, type_equipement, _valeur_charge(charge_kg_cible, id="charge-cible"), date,
                           capacite_kw)
    pa, pc = actuel["prp"], cible["prp"]
    suffixe = f"{actuel['fluide']}-{cible['fluide']}"
    rapport = calculer(lambda: pc.nombre / pa.nombre, "", f"{pc.reference()} ÷ {pa.reference()}", [pc, pa],
                       id=f"rapport-prp-{suffixe}")
    variation = calculer(lambda: (pc.nombre / pa.nombre - 1) * POURCENT, "%",
                         f"({pc.reference()} ÷ {pa.reference()} − 1) × 100", [pc, pa], id=f"variation-prp-{suffixe}")
    if rapport.nombre is None or variation.nombre is None:
        ligne1 = (f"{actuel['fluide']} → {cible['fluide']} : PRP {texte_prp(pa)} → {texte_prp(pc)} ; "
                  "rapport non calculable (PRP à confirmer ou nul).")
    else:
        part = rapport.nombre * POURCENT
        d = 1 if part >= 1 else (2 if part >= 0.01 else 4)
        sens = "baisse" if variation.nombre < 0 else "hausse"
        ligne1 = (f"{actuel['fluide']} → {cible['fluide']} : PRP {texte_prp(pa)} → {texte_prp(pc)}, soit "
                  f"{nombre_fr(part, d)}{ESPACE}% du PRP actuel ({sens} de "
                  f"{nombre_fr(abs(variation.nombre), 1)}{ESPACE}%).")
    resume_cible = (cible["etancheite"]["texte"] if cible["famille"] == NON_FLUORE
                    else cible["interdiction_mise_sur_le_marche"]["texte"])
    lignes = [ligne1,
              f"Actuel ({actuel['fluide']}) : " + actuel["interdiction_entretien"]["texte"],
              f"Cible ({cible['fluide']}, {cible['famille']}, classe {cible['classe_securite']}) : " + resume_cible]
    if MENTION_NON_RELUE in actuel["relecture"] or MENTION_NON_RELUE in cible["relecture"]:
        lignes.append("Table F-gas non relue : à vérifier sur EUR-Lex avant de s'en servir devant un client.")
    return {"actuel": actuel, "cible": cible, "rapport_prp": rapport, "variation_prp": variation,
            "texte": "\n".join(lignes)}


# =====================================================================================================
# Ligne de commande
# =====================================================================================================
def _nombre_argument(texte: str) -> float:
    try:
        return float(texte.replace(",", "."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"nombre attendu, reçu « {texte} »") from None


def _afficher_regles(regles: list[dict]) -> list[str]:
    sortie = [f"Règles applicables : {len(regles)}"]
    for d in regles:
        sortie.append(f"  [{d['etat']}] {d['regle']} — {d['article'] or 'article non renseigné'} "
                      f"(ligne {d['ligne']}, {d['relecture']})")
        if d["conditions"]:
            sortie.append("      " + " ; ".join(d["conditions"]))
    return sortie


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parseur = argparse.ArgumentParser(prog="fgas.py", description="Conformité F-gas d'un fluide (bloc D).")
    parseur.add_argument("fluide", help="fluide actuel, ex. R449A")
    parseur.add_argument("--type", required=True, dest="type_equipement",
                         help="type d'équipement : centrale, groupe de condensation, chambre froide, climatisation…")
    parseur.add_argument("--charge", type=_nombre_argument, help="charge du fluide actuel en kg")
    parseur.add_argument("--cible", help="fluide cible pour une comparaison, ex. R744")
    parseur.add_argument("--charge-cible", type=_nombre_argument, help="charge du fluide cible en kg")
    parseur.add_argument("--capacite", type=_nombre_argument, help="capacité nominale en kW (centrales ≥ 40 kW)")
    parseur.add_argument("--date", help="date d'analyse AAAA-MM-JJ (défaut : aujourd'hui)")
    parseur.add_argument("--json", action="store_true", help="sortie JSON (Valeur sérialisées)")
    a = parseur.parse_args(argv)
    charge = Valeur(a.charge, "kg", "valeur donnée en argument", SOURCE, id="charge") if a.charge is not None else None
    try:
        if a.cible:
            charge_cible = (Valeur(a.charge_cible, "kg", "valeur donnée en argument", SOURCE, id="charge-cible")
                            if a.charge_cible is not None else None)
            r = comparer_fluides(a.fluide, a.cible, a.type_equipement, charge, charge_cible, a.date, a.capacite)
        else:
            r = verdict_fluide(a.fluide, a.type_equipement, charge, a.date, a.capacite)
    except (ValueError, TypeError) as exc:
        print(f"refusé : {exc}", file=sys.stderr)
        return 2
    if a.json:
        print(en_json(r))
        return 0
    if a.cible:
        print(r["texte"])
        print()
    for v in ([r["actuel"], r["cible"]] if a.cible else [r]):
        print(f"=== {v['fluide']} · {v['equipement']['description']} · au "
              f"{date_fr(dt.date.fromisoformat(v['date']))} ===")
        print(v["texte"])
        print()
        print(f"PRP : {texte_prp(v['prp'])}   ({v['prp'].source_texte()})")
        print(f"tCO2e : {_texte_tco2e(v['tco2e'])}   ({v['tco2e'].source_texte()})")
        print()
        print("\n".join(_afficher_regles(v["regles"])))
        print()
    return 0


__all__ = [
    "prp", "prp_melange_calcule", "tco2e", "seuil_controle_etancheite", "regles_applicables", "verdict_fluide",
    "comparer_fluides", "famille", "nom_canonique", "decrire_equipement", "texte_prp", "date_fr", "regles_table",
    "vider_cache", "Regle", "Equipement",
]

if __name__ == "__main__":
    sys.exit(main())
