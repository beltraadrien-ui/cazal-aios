"""Métré des lignes d'un plan 2D froid et clim : par ligne, par réseau, par diamètre, avec la formule écrite.

Règle (décision du 2026-10-07, conventions du skill) :
    métré d'une ligne = longueur du tracé en plan + |passage − départ| + |passage − arrivée| + réserve (câbles)
Un câble qui s'arrête sur un chemin de câbles (son `a` est l'identifiant du chemin, ou, si `a` ne désigne pas un
équipement, son dernier point est à 0,10 m ou moins du chemin) compte en plus son parcours DANS le chemin
(`chemin_m`) : longueur le long du chemin, de la projection de ce dernier point jusqu'à l'extrémité du chemin côté
tableau (le `a` ou le `de` du chemin s'il désigne un tableau, sinon l'extrémité la plus proche d'un tableau) ; son
arrivée verticale est alors celle de ce tableau. Le chemin de câbles lui-même reste métré une fois, à part.

Les trois hauteurs viennent, dans cet ordre de priorité :
    1. la ligne elle-même (`hauteur_depart`, `hauteur_passage`, `hauteur_arrivee`) ;
    2. l'équipement relié, s'il porte un champ `hauteur` (départ ou arrivée seulement) ;
    3. le calque libre (`calques_libres[].hauteur_depart|hauteur_passage|hauteur_arrivee`), lignes libres seulement ;
    4. la table `hauteurs` de plan.json ;
    5. les valeurs par défaut ci-dessous (HAUTEURS_DEFAUT), marquées « hypothèse » tant que
       `plan["hauteurs_validees"]` n'est pas vrai (question 13 : hauteurs de pose à faire valider).
Le chemin de câbles n'a pas de métré vertical (seule la longueur en plan compte).

Arrondi : chaque composante d'une ligne est arrondie au centimètre (au plus proche, 0,005 → 0,01), puis les totaux
sont des sommes de valeurs arrondies : les tableaux s'additionnent exactement. La longueur en plan non arrondie
reste disponible (`plan_brut_m`) pour les comparaisons fines.

Usage (bibliothèque, importée par generer.py et verifier_plan.py) :
    from metre import metrer
    m = metrer(plan)                 # plan = dict brut lu dans plan.json
    m.lignes["L1"]["total_m"]        → 8.8
    m.lignes["L1"]["formule"]        → « 6,40 m en plan + |2,60 − 2,30| + |2,60 − 0,50| = 8,80 m »
    m.par_reseau["froid_cuivres"]["total_m"], m.par_diametre[("aspiration", "à définir")]["total_m"]
    m.markdown(), m.html(), m.tableaux_html()

En ligne de commande (contrôle rapide) :
    python metre.py <plan.json> [--html]
"""
from __future__ import annotations

import argparse
import html as _html
import json
import math
import sys
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

# Espace insécable (U+00A0) avant l'unité et entre les milliers ; signe moins typographique (U+2212) dans les formules.
ESPACE = "\u00a0"
MOINS = "\u2212"
FLECHE = "\u2192"
TIRET_VIDE = "\u2014"

HYPOTHESE = "hypothèse"
VALIDEE = "validée"
IMPOSEE_LIGNE = "imposée sur la ligne"
IMPOSEE_EQUIPEMENT = "imposée sur l'équipement"
IMPOSEE_CALQUE = "imposée sur le calque"

A_DEFINIR = "à définir"

# Hauteurs en mètres (décision du 2026-10-07). Hypothèses tant qu'elles ne sont pas validées (question 13).
HAUTEURS_DEFAUT: dict[str, float] = {
    "evaporateur": 2.30,
    "passage_froid": 2.60,
    "raccord_groupe": 0.50,
    "tableau": 1.50,
    "chemin_cables": 2.80,
    "reserve_cable": 1.00,
    "split": 2.20,
    "passage_clim": 2.20,
    "raccord_moteur": 0.50,
    "evacuation_condensats": 0.10,
    "raccord_libre": 0.00,
}
# « passage_condensats » n'a pas de valeur fixe : par défaut, elle suit `hauteurs["evaporateur"]` (2,30 m).
ORDRE_HAUTEURS = ("evaporateur", "passage_froid", "raccord_groupe", "passage_condensats", "evacuation_condensats",
                  "split", "passage_clim", "raccord_moteur", "tableau", "chemin_cables", "reserve_cable",
                  "raccord_libre")
LIBELLES_HAUTEURS = {
    "evaporateur": "Évaporateurs (départ des cuivres et des condensats)",
    "passage_froid": "Passage des cuivres froid (et des réseaux libres)",
    "raccord_groupe": "Raccords des groupes et centrales",
    "passage_condensats": "Passage des condensats",
    "evacuation_condensats": "Évacuation des condensats",
    "split": "Splits (départ des cuivres clim)",
    "passage_clim": "Passage des cuivres clim",
    "raccord_moteur": "Raccords du moteur de clim",
    "tableau": "Tableau électrique",
    "chemin_cables": "Chemin de câbles",
    "reserve_cable": "Réserve par câble (longueur)",
    "raccord_libre": "Départ et arrivée des réseaux libres",
}

TYPES_STANDARD = ("aspiration", "liquide", "condensats", "clim_gaz", "clim_liquide", "cable", "chemin_cables")
CALQUE_STANDARD = {
    "aspiration": "froid_cuivres", "liquide": "froid_cuivres", "condensats": "froid_cuivres",
    "clim_gaz": "clim_cuivres", "clim_liquide": "clim_cuivres",
    "cable": "electricite", "chemin_cables": "electricite",
}
NOMS_CALQUES = {
    "froid_cuivres": "Froid – cuivres et condensats",
    "electricite": "Électricité (froid + clim)",
    "clim_cuivres": "Clim – cuivres",
}
ORDRE_RESEAUX = ("froid_cuivres", "electricite", "clim_cuivres")
# Vue lisible (plan.md / plan.html, lue par Loïc) : noms de réseau sans tiret et en-têtes des tableaux par réseau.
# generer.py les écrit, verifier_plan.py (E6) les relit.
NOMS_RESEAUX_LISIBLES = {
    "froid_cuivres": "Froid : cuivres et condensats",
    "electricite": "Électricité (froid et clim)",
    "clim_cuivres": "Clim : cuivres",
}
COL_TRONCON = "Tronçon"
COL_TYPE = "Type"
COL_PLAN = "En plan (m)"
COL_DONT_CHEMIN = "dont chemin de câbles (m)"
COL_MONTEES = "Montées et descentes (m)"
COL_RESERVE = "Réserve (m)"
COL_TOTAL = "Total (m)"
COL_DIAMETRE = "Diamètre"
COL_RESEAU = "Réseau"
TITRE_RECAPITULATIF = "Récapitulatif"
LIBELLES_TYPES = {
    "aspiration": "Aspiration", "liquide": "Liquide", "condensats": "Condensats",
    "clim_gaz": "Clim gaz", "clim_liquide": "Clim liquide",
    "cable": "Câble", "chemin_cables": "Chemin de câbles",
}

# Hauteur (départ, passage, arrivée) par type de ligne : clé de `hauteurs`. Pour le câble, départ et arrivée
# = hauteur de l'équipement relié (EQUIPEMENT), avec repli sur REPLI_CABLE si l'équipement est inconnu.
EQUIPEMENT = "<équipement>"
REGLES_HAUTEURS = {
    "aspiration": ("evaporateur", "passage_froid", "raccord_groupe"),
    "liquide": ("evaporateur", "passage_froid", "raccord_groupe"),
    "condensats": ("evaporateur", "passage_condensats", "evacuation_condensats"),
    "clim_gaz": ("split", "passage_clim", "raccord_moteur"),
    "clim_liquide": ("split", "passage_clim", "raccord_moteur"),
    "cable": (EQUIPEMENT, "chemin_cables", EQUIPEMENT),
}
REGLE_LIBRE = ("raccord_libre", "passage_froid", "raccord_libre")
REPLI_CABLE = {"depart": "evaporateur", "arrivee": "tableau"}
HAUTEUR_PAR_TYPE_EQUIPEMENT = {
    "evaporateur": "evaporateur", "groupe": "raccord_groupe", "centrale": "raccord_groupe",
    "condenseur": "raccord_groupe", "split": "split", "moteur": "raccord_moteur", "tableau": "tableau",
    "chambre_froide": "evaporateur",   # câble « de la chambre » (E5) : boîtier en partie haute
}
ROLES = ("depart", "passage", "arrivee")
NOMS_ROLES = {"depart": "départ", "passage": "passage", "arrivee": "arrivée"}
TOL_JONCTION_CHEMIN = 0.10      # m : dernier point d'un câble à 0,10 m ou moins d'un chemin de câbles = il s'y arrête
HYP = " (hyp.)"                 # valeur qui dépend d'une hauteur « hypothèse » (même marque que plan.md)
NOTE_HYP = ("(hyp.) : valeur qui dépend d'une hauteur de pose « hypothèse » (tableau « Hauteurs utilisées »), "
            "à faire valider (question 13) ; elle changera avec elle.")


class ErreurMetre(ValueError):
    """Donnée de plan.json inutilisable pour le métré (message en français)."""


# ---------------------------------------------------------------------------------------------------------------
# Format français
# ---------------------------------------------------------------------------------------------------------------

def arrondi(x: float, decimales: int = 2) -> float:
    """Arrondi au plus proche, 0,005 → 0,01 (pas d'arrondi bancaire), sur la valeur décimale affichée."""
    q = Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
    return float(q) + 0.0                                      # + 0.0 : pas de « -0.0 »


def nombre_fr(x: float, decimales: int = 2) -> str:
    """1234.5 → « 1 234,50 » (espace insécable entre les milliers, virgule décimale, arrondi au plus proche)."""
    q = Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
    if q == 0:
        q = abs(q)                                             # pas de « -0,00 »
    signe = "-" if q < 0 else ""
    entier, _, frac = f"{abs(q):f}".partition(".")
    groupes = []
    while len(entier) > 3:
        groupes.insert(0, entier[-3:])
        entier = entier[:-3]
    groupes.insert(0, entier)
    return signe + ESPACE.join(groupes) + ("," + frac if frac else "")


def longueur_fr(x: float) -> str:
    """8.8 → « 8,80 m » (espace insécable avant « m »)."""
    return f"{nombre_fr(x)}{ESPACE}m"


# ---------------------------------------------------------------------------------------------------------------
# Lecture du dict brut de plan.json
# ---------------------------------------------------------------------------------------------------------------

def _est_nombre(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _hauteur_valide(v: Any, ou: str) -> float:
    if not _est_nombre(v):
        raise ErreurMetre(f"{ou} : la hauteur doit être un nombre en mètres, trouvé {v!r}")
    if v < 0:
        raise ErreurMetre(f"{ou} : hauteur négative ({v}) ; les hauteurs se comptent depuis le sol, en mètres")
    return float(v)


def hauteurs_effectives(plan: dict) -> dict[str, float]:
    """Défauts + `plan["hauteurs"]` (une valeur null = défaut) ; `passage_condensats` suit `evaporateur` si absente."""
    brutes = plan.get("hauteurs") or {}
    if not isinstance(brutes, dict):
        raise ErreurMetre("hauteurs : un objet {nom: valeur en m} est attendu")
    h = dict(HAUTEURS_DEFAUT)
    for cle, v in brutes.items():
        if v is not None:
            h[cle] = _hauteur_valide(v, f"hauteurs.{cle}")
    if brutes.get("passage_condensats") is None:
        h["passage_condensats"] = h["evaporateur"]
    return h


def calque_ligne(ligne: dict) -> str:
    """Calque (= réseau) d'une ligne : son champ `calque`, sinon le calque standard de son type, sinon son type."""
    return ligne.get("calque") or CALQUE_STANDARD.get(ligne.get("type")) or str(ligne.get("type"))


def _calques_libres(plan: dict) -> dict[str, dict]:
    libres = {}
    for c in plan.get("calques_libres") or []:
        if isinstance(c, dict) and c.get("cle"):
            libres[c["cle"]] = c
    return libres


def nom_calque(cle: str, plan: dict | None = None) -> str:
    """« froid_cuivres » → « Froid – cuivres et condensats » ; calque libre → son `nom` ; inconnu → la clé."""
    if cle in NOMS_CALQUES:
        return NOMS_CALQUES[cle]
    libre = _calques_libres(plan or {}).get(cle)
    return (libre or {}).get("nom") or cle


def nom_reseau_lisible(cle: str, plan: dict | None = None) -> str:
    """Nom d'un réseau dans plan.md (titre de son tableau, récapitulatif) : sans tiret pour les réseaux standard,
    le `nom` du calque libre sinon."""
    return NOMS_RESEAUX_LISIBLES.get(cle) or nom_calque(cle, plan)


def libelle_type(type_: str, plan: dict | None = None) -> str:
    """« cable » → « Câble » ; type libre → nom du calque libre de même clé, sinon la clé."""
    if type_ in LIBELLES_TYPES:
        return LIBELLES_TYPES[type_]
    return nom_calque(type_, plan)


def normaliser_diametre(d: Any) -> str:
    """None, « », « à définir », « à définir par le dimensionnement », « a definir » → « à définir »."""
    if d is None:
        return A_DEFINIR
    texte = str(d).strip()
    simple = texte.lower().replace("à", "a").replace("é", "e")
    if not texte or simple.startswith("a definir"):
        return A_DEFINIR
    return texte


def _points(ligne: dict, ou: str) -> list[tuple[float, float]]:
    brut = ligne.get("points")
    if not isinstance(brut, (list, tuple)) or len(brut) < 2:
        raise ErreurMetre(f"{ou} : il faut au moins 2 points [x, y] (en m) dans `points`")
    pts = []
    for i, p in enumerate(brut):
        if not isinstance(p, (list, tuple)) or len(p) != 2 or not all(_est_nombre(c) for c in p):
            raise ErreurMetre(f"{ou} : point n° {i + 1} invalide ({p!r}) ; attendu [x, y] en mètres")
        pts.append((float(p[0]), float(p[1])))
    return pts


def _longueur_polyligne(pts: list[tuple[float, float]]) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def _projection_polyligne(p: tuple[float, float], pts: list[tuple[float, float]]) -> tuple[float, float]:
    """(distance de p à la polyligne, abscisse le long de la polyligne de sa projection, depuis le premier point)."""
    meilleur, cumul = (math.inf, 0.0), 0.0
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 < 1e-24 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
        d = math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))
        if d < meilleur[0] - 1e-12:
            meilleur = (d, cumul + t * math.sqrt(l2))
        cumul += math.sqrt(l2)
    return meilleur


# ---------------------------------------------------------------------------------------------------------------
# Métré
# ---------------------------------------------------------------------------------------------------------------

@dataclass
class Metre:
    """Résultat du métré. Les dicts gardent l'ordre : lignes dans l'ordre de plan.json, réseaux dans l'ordre des calques."""
    lignes: dict[str, dict] = field(default_factory=dict)
    par_reseau: dict[str, dict] = field(default_factory=dict)
    par_diametre: dict[tuple[str, str], dict] = field(default_factory=dict)
    hypotheses: list[dict] = field(default_factory=list)
    hauteurs: dict[str, float] = field(default_factory=dict)

    # -- données des tableaux (communes au markdown et au HTML) ---------------------------------------------------

    def en_hypothese(self, lid: str) -> tuple[bool, bool]:
        """(vertical en hypothèse, réserve en hypothèse) d'une ligne : une hauteur prise dans la table `hauteurs` et
        non validée (question 13) rend son métré vertical « hypothèse » (même règle que plan.md)."""
        statuts = {h["cle"]: h["statut"] for h in self.hypotheses}
        l = self.lignes[lid]
        vertical = any(o.startswith("hauteurs.") and statuts.get(o.split(".", 1)[1]) == HYPOTHESE
                       for o in (l.get("origines_hauteurs") or {}).values())
        reserve = l["type"] == "cable" and statuts.get("reserve_cable") == HYPOTHESE
        return vertical, reserve

    def _tableau_reseaux(self) -> tuple[list[str], list[list[str]], list[str], set[int]]:
        entetes = ["Réseau", "Ligne", f"De {FLECHE} À", "Type", "En plan (m)", "Dans le chemin (m)", "Vertical (m)",
                   "Réserve (m)", "Total (m)", "Diamètre"]
        aligne = ["g", "g", "g", "g", "d", "d", "d", "d", "d", "g"]
        rangs, gras = [], set()
        for r in self.par_reseau.values():
            hv_res = hr_res = False
            for lid in r["lignes"]:
                l = self.lignes[lid]
                hv, hr = self.en_hypothese(lid)
                hv_res, hr_res = hv_res or hv, hr_res or hr
                rangs.append([r["nom"], lid, f"{l['de'] or TIRET_VIDE} {FLECHE} {l['a'] or TIRET_VIDE}",
                              l["libelle_type"], nombre_fr(l["plan_m"]), nombre_fr(l["chemin_m"]),
                              nombre_fr(l["vertical_m"]) + (HYP if hv else ""),
                              nombre_fr(l["reserve_m"]) + (HYP if hr else ""),
                              nombre_fr(l["total_m"]) + (HYP if hv or hr else ""), l["diametre"]])
            gras.add(len(rangs))
            rangs.append([f"Total {r['nom']}", "", "", "", nombre_fr(r["plan_m"]), nombre_fr(r["chemin_m"]),
                          nombre_fr(r["vertical_m"]) + (HYP if hv_res else ""),
                          nombre_fr(r["reserve_m"]) + (HYP if hr_res else ""),
                          nombre_fr(r["total_m"]) + (HYP if hv_res or hr_res else ""), ""])
        return entetes, rangs, aligne, gras

    def _tableau_diametres(self) -> tuple[list[str], list[list[str]], list[str], set[int]]:
        rangs = [[d["diametre"], d["libelle_type"], nombre_fr(d["total_m"])
                  + (HYP if any(any(self.en_hypothese(lid)) for lid in d["lignes"]) else "")]
                 for d in self.par_diametre.values()]
        return ["Diamètre", "Type", "Total (m)"], rangs, ["g", "g", "d"], set()

    def _tableau_hauteurs(self) -> tuple[list[str], list[list[str]], list[str], set[int]]:
        rangs = [[h["libelle"], nombre_fr(h["valeur"]), h["statut"]] for h in self.hypotheses]
        return ["Hauteur", "Valeur (m)", "Statut"], rangs, ["g", "d", "g"], set()

    def _note_hypotheses(self) -> str:
        if any(h["statut"] == HYPOTHESE for h in self.hypotheses):
            return ("Les hauteurs marquées « hypothèse » sont des valeurs par défaut, à confirmer avant de commander "
                    "le matériel ; les métrés qui en dépendent (marqués (hyp.)) changeront avec elles.")
        return ""

    # -- sorties -------------------------------------------------------------------------------------------------

    def markdown(self, niveau: int = 3) -> str:
        """Tableaux « Métré par réseau », « Détail du calcul par ligne », « Métré par diamètre », « Hauteurs utilisées »."""
        t = "#" * niveau
        if not self.lignes:
            return f"{t} Métré par réseau\n\nAucune ligne à métrer.\n"
        morceaux = [
            f"{t} Métré par réseau", "",
            f"Métré d'une ligne = longueur du tracé en plan + |passage {MOINS} départ| + |passage {MOINS} arrivée| "
            "+ réserve (câbles seulement). Un câble qui s'arrête sur le chemin de câbles compte aussi son parcours "
            "dans le chemin jusqu'au tableau. Le chemin de câbles n'a pas de métré vertical.", "",
            _table_md(*self._tableau_reseaux()), "",
            f"{t} Détail du calcul par ligne", "",
        ]
        for lid, l in self.lignes.items():
            morceaux.append(f"- **{lid}** ({l['libelle_type']}, {l['de'] or TIRET_VIDE} {FLECHE} "
                            f"{l['a'] or TIRET_VIDE}) : {l['formule']}")
        morceaux += ["", f"{t} Métré par diamètre", "", _table_md(*self._tableau_diametres()), "",
                     f"{t} Hauteurs utilisées", "", _table_md(*self._tableau_hauteurs()), ""]
        note = self._note_hypotheses()
        if note:
            morceaux += [note, ""]
        return "\n".join(morceaux)

    def tableaux_html(self) -> list[tuple[str, str]]:
        """[(titre, HTML d'un <table>)] pour la page « Métré » de plan.drawio : HTML simple, styles en ligne."""
        if not self.lignes:
            return [("Métré par réseau", _table_html(["Métré"], [["Aucune ligne à métrer."]], ["g"], set()))]
        note = NOTE_HYP if any(h["statut"] == HYPOTHESE for h in self.hypotheses) else ""
        return [("Métré par réseau", _table_html(*self._tableau_reseaux(), note=note)),
                ("Métré par diamètre", _table_html(*self._tableau_diametres())),
                ("Hauteurs utilisées", _table_html(*self._tableau_hauteurs()))]

    def html(self) -> str:
        """Fragment HTML bien formé (lisible aussi comme XML) : titres, tableaux, détail des formules, note."""
        e = _html.escape
        morceaux = ['<div class="metre">']
        for titre, table in self.tableaux_html():
            morceaux.append(f"<h3>{e(titre)}</h3>")
            morceaux.append(table)
            if titre == "Métré par réseau" and self.lignes:
                morceaux.append("<h3>Détail du calcul par ligne</h3>")
                morceaux.append("<ul>")
                for lid, l in self.lignes.items():
                    morceaux.append(f"<li><b>{e(lid)}</b> ({e(l['libelle_type'])}, {e(l['de'] or TIRET_VIDE)} "
                                    f"{FLECHE} {e(l['a'] or TIRET_VIDE)}) : {e(l['formule'])}</li>")
                morceaux.append("</ul>")
        note = self._note_hypotheses()
        if note:
            morceaux.append(f"<p>{e(note)}</p>")
        morceaux.append("</div>")
        return "\n".join(morceaux)

    def en_dict(self) -> dict:
        """Version JSON (clés de `par_diametre` écrites « type|diamètre »)."""
        return {"lignes": self.lignes, "par_reseau": self.par_reseau,
                "par_diametre": {f"{t}|{d}": v for (t, d), v in self.par_diametre.items()},
                "hypotheses": self.hypotheses, "hauteurs": self.hauteurs}


class _Contexte:
    """Ce dont le calcul d'une ligne a besoin : hauteurs effectives, équipements, calques libres, suivi des hypothèses."""

    def __init__(self, plan: dict):
        self.plan = plan
        self.h = hauteurs_effectives(plan)
        self.libres = _calques_libres(plan)
        self.equipements: dict[str, dict] = {}
        for eq in plan.get("equipements") or []:
            if isinstance(eq, dict) and eq.get("id"):
                self.equipements[eq["id"]] = eq
        for cf in plan.get("chambres_froides") or []:
            if isinstance(cf, dict) and cf.get("id") and cf["id"] not in self.equipements:
                self.equipements[cf["id"]] = {"id": cf["id"], "type": "chambre_froide"}
        self.utilisees: dict[str, list[str]] = {}                   # clé de hauteurs → lignes
        self.imposees: list[dict] = []                              # surcharges (ligne, équipement, calque)
        self.chemins: dict[str, tuple[dict, list[tuple[float, float]]]] = {}   # chemin de câbles : (ligne, points)
        for l in plan.get("lignes") or []:
            if isinstance(l, dict) and l.get("type") == "chemin_cables" and l.get("id"):
                try:
                    self.chemins[l["id"]] = (l, _points(l, f"ligne {l['id']}"))
                except ErreurMetre:
                    pass                                            # signalé au métré du chemin lui-même

    def chemin_du_cable(self, ligne: dict, pts: list[tuple[float, float]]) -> str | None:
        """Chemin de câbles sur lequel le câble s'arrête : son `a` s'il désigne un chemin ; sinon, si `a` ne désigne
        pas un équipement, le chemin le plus proche de son dernier point (à TOL_JONCTION_CHEMIN ou moins)."""
        a = ligne.get("a")
        if isinstance(a, str) and a in self.chemins:
            return a
        if isinstance(a, str) and a in self.equipements:
            return None                                             # le câble arrive à un équipement
        meilleur = None
        for cid, (_, cpts) in self.chemins.items():
            d = _projection_polyligne(pts[-1], cpts)[0]
            if d <= TOL_JONCTION_CHEMIN + 1e-9 and (meilleur is None or d < meilleur[0]):
                meilleur = (d, cid)
        return meilleur[1] if meilleur else None

    def bout_tableau(self, cid: str) -> tuple[int | None, str | None]:
        """Extrémité du chemin côté tableau (0 = premier point, -1 = dernier) et identifiant du tableau : le `a` (puis
        le `de`) du chemin s'il désigne un tableau, sinon l'extrémité la plus proche du centre d'un tableau."""
        ligne, pts = self.chemins[cid]
        for cle, idx in (("a", -1), ("de", 0)):
            eq = self.equipements.get(ligne.get(cle)) if isinstance(ligne.get(cle), str) else None
            if eq is not None and eq.get("type") == "tableau":
                return idx, eq["id"]
        meilleur = None
        for eq in self.equipements.values():
            pos = eq.get("position")
            if eq.get("type") != "tableau" or not (isinstance(pos, (list, tuple)) and len(pos) == 2
                                                   and all(_est_nombre(c) for c in pos)):
                continue
            for idx in (0, -1):
                d = math.hypot(pts[idx][0] - pos[0], pts[idx][1] - pos[1])
                if meilleur is None or d < meilleur[0]:
                    meilleur = (d, idx, eq["id"])
        return (meilleur[1], meilleur[2]) if meilleur else (None, None)

    def statut(self, cle: str) -> str:
        v = self.plan.get("hauteurs_validees")
        if v is True or (isinstance(v, (list, tuple)) and cle in v):
            return VALIDEE
        return HYPOTHESE

    def _note_cle(self, cle: str, lid: str) -> None:
        lignes = self.utilisees.setdefault(cle, [])
        if lid not in lignes:
            lignes.append(lid)

    def _note_imposee(self, cle: str, libelle: str, valeur: float, statut: str, lid: str) -> None:
        for i in self.imposees:
            if i["cle"] == cle:
                if lid not in i["lignes"]:
                    i["lignes"].append(lid)
                return
        self.imposees.append({"cle": cle, "libelle": libelle, "valeur": valeur, "statut": statut, "lignes": [lid]})

    def hauteur(self, ligne: dict, lid: str, role: str, regle: str, libre: dict | None) -> tuple[float, str]:
        """(valeur, origine) d'une hauteur de la ligne, selon l'ordre de priorité du module."""
        champ = f"hauteur_{role}"
        if ligne.get(champ) is not None:
            v = _hauteur_valide(ligne[champ], f"ligne {lid}, {champ}")
            self._note_imposee(f"ligne:{lid}:{role}", f"{lid} · {NOMS_ROLES[role]}", v, IMPOSEE_LIGNE, lid)
            return v, "ligne"
        if role != "passage":
            eq_id = ligne.get("de") if role == "depart" else ligne.get("a")
            eq = self.equipements.get(eq_id) if eq_id is not None else None
            if eq is not None and eq.get("hauteur") is not None:
                v = _hauteur_valide(eq["hauteur"], f"équipement {eq_id}, hauteur")
                self._note_imposee(f"equipement:{eq_id}", f"{eq_id} · hauteur de raccordement", v,
                                   IMPOSEE_EQUIPEMENT, lid)
                return v, f"équipement {eq_id}"
            if regle == EQUIPEMENT:
                regle = HAUTEUR_PAR_TYPE_EQUIPEMENT.get((eq or {}).get("type")) or REPLI_CABLE[role]
        if libre is not None and libre.get(champ) is not None:
            v = _hauteur_valide(libre[champ], f"calque libre {libre['cle']}, {champ}")
            self._note_imposee(f"calque:{libre['cle']}:{role}", f"{libre.get('nom') or libre['cle']} · "
                               f"{NOMS_ROLES[role]}", v, IMPOSEE_CALQUE, lid)
            return v, f"calque {libre['cle']}"
        self._note_cle(regle, lid)
        return self.h[regle], f"hauteurs.{regle}"


def _metrer_ligne(ligne: dict, ctx: _Contexte) -> dict:
    lid = ligne["id"]
    ou = f"ligne {lid}"
    type_ = ligne.get("type")
    if not type_ or not isinstance(type_, str):
        raise ErreurMetre(f"{ou} : `type` manquant (aspiration, liquide, condensats, clim_gaz, clim_liquide, cable, "
                          "chemin_cables, ou la clé d'un calque libre)")
    calque = calque_ligne(ligne)
    libre = None
    if type_ not in TYPES_STANDARD:
        cle_libre = type_ if type_ in ctx.libres else (calque if calque in ctx.libres else None)
        if cle_libre is None:
            raise ErreurMetre(f"{ou} : type « {type_} » inconnu ; types standard : {', '.join(TYPES_STANDARD)} ; "
                              "pour un réseau libre, déclarer le calque dans `calques_libres` (clé = type ou calque)")
        libre = ctx.libres[cle_libre]
    pts = _points(ligne, ou)
    plan_brut = _longueur_polyligne(pts)
    plan_m = arrondi(plan_brut)
    chemin_id, chemin_m, bout, tableau_id = None, 0.0, None, None
    ligne_h = ligne                                                 # ligne vue par le calcul des hauteurs
    if type_ == "cable":
        chemin_id = ctx.chemin_du_cable(ligne, pts)
        if chemin_id is not None:
            bout, tableau_id = ctx.bout_tableau(chemin_id)
            if bout is not None:
                cpts = ctx.chemins[chemin_id][1]
                s = _projection_polyligne(pts[-1], cpts)[1]
                chemin_m = arrondi(s if bout == 0 else _longueur_polyligne(cpts) - s)
                ligne_h = {**ligne, "a": tableau_id}                # arrivée verticale : celle du tableau

    if type_ == "chemin_cables":
        utilisees: dict[str, float] = {}
        origines: dict[str, str] = {}
        vertical_m = reserve_m = 0.0
        total_m = plan_m
        formule = f"{longueur_fr(plan_m)} en plan (chemin de câbles : pas de métré vertical) = {longueur_fr(total_m)}"
    else:
        regles = REGLES_HAUTEURS.get(type_, REGLE_LIBRE)
        utilisees, origines = {}, {}
        for role, regle in zip(ROLES, regles):
            v, origine = ctx.hauteur(ligne_h, lid, role, regle, libre)
            utilisees[role], origines[role] = arrondi(v), origine
        d, p, a = utilisees["depart"], utilisees["passage"], utilisees["arrivee"]
        vertical_m = arrondi(abs(p - d) + abs(p - a))
        reserve_m = 0.0
        if type_ == "cable":
            reserve_m = arrondi(ctx.h["reserve_cable"])
            ctx._note_cle("reserve_cable", lid)
        total_m = arrondi(plan_m + chemin_m + vertical_m + reserve_m)
        formule = f"{longueur_fr(plan_m)} en plan"
        if chemin_id is not None and bout is not None:
            formule += f" + {longueur_fr(chemin_m)} dans le chemin de câbles {chemin_id} jusqu'à {tableau_id}"
        elif chemin_id is not None:
            formule += (f" (parcours dans le chemin de câbles {chemin_id} non compté : aucun tableau au bout du "
                        "chemin)")
        formule += f" + |{nombre_fr(p)} {MOINS} {nombre_fr(d)}| + |{nombre_fr(p)} {MOINS} {nombre_fr(a)}|"
        if type_ == "cable":
            formule += f" + {longueur_fr(reserve_m)} de réserve"
        formule += f" = {longueur_fr(total_m)}"

    return {
        "plan_m": plan_m, "plan_brut_m": plan_brut, "chemin_m": chemin_m, "chemin": chemin_id,
        "tableau": tableau_id if chemin_id is not None and bout is not None else None,
        "vertical_m": vertical_m, "reserve_m": reserve_m, "total_m": total_m, "formule": formule,
        "type": type_, "libelle_type": libelle_type(type_, ctx.plan),
        "calque": calque, "reseau": calque, "nom_reseau": nom_calque(calque, ctx.plan),
        "de": ligne.get("de"), "a": ligne.get("a"), "faisceau": ligne.get("faisceau"),
        "diametre": normaliser_diametre(ligne.get("diametre")),
        "hauteurs_utilisees": utilisees, "origines_hauteurs": origines,
    }


def _ordre_reseaux(cles: list[str], plan: dict) -> list[str]:
    libres = [c for c in _calques_libres(plan) if c not in ORDRE_RESEAUX]
    rang = {c: i for i, c in enumerate(list(ORDRE_RESEAUX) + libres)}
    apparition = {c: i for i, c in enumerate(cles)}
    return sorted(cles, key=lambda c: (rang.get(c, len(rang)), apparition[c]))


def metrer(plan: dict) -> Metre:
    """Métré complet d'un plan (dict brut de plan.json). Lève ErreurMetre si une ligne est inutilisable."""
    if not isinstance(plan, dict):
        raise ErreurMetre("plan : un objet JSON (dict) est attendu")
    ctx = _Contexte(plan)
    lignes: dict[str, dict] = {}
    for i, ligne in enumerate(plan.get("lignes") or []):
        if not isinstance(ligne, dict) or not ligne.get("id"):
            raise ErreurMetre(f"lignes[{i}] : chaque ligne doit avoir un `id`")
        if ligne["id"] in lignes:
            raise ErreurMetre(f"ligne {ligne['id']} : identifiant en double")
        lignes[ligne["id"]] = _metrer_ligne(ligne, ctx)

    # Par réseau (= calque).
    par_reseau: dict[str, dict] = {}
    for cle in _ordre_reseaux(list(dict.fromkeys(l["reseau"] for l in lignes.values())), plan):
        ids = [lid for lid, l in lignes.items() if l["reseau"] == cle]
        par_type: dict[str, dict] = {}
        for lid in ids:
            l = lignes[lid]
            t = par_type.setdefault(l["type"], {"plan_m": 0.0, "total_m": 0.0, "lignes": []})
            t["plan_m"] = arrondi(t["plan_m"] + l["plan_m"])
            t["total_m"] = arrondi(t["total_m"] + l["total_m"])
            t["lignes"].append(lid)
        par_reseau[cle] = {
            "reseau": cle, "nom": nom_calque(cle, plan), "lignes": ids,
            "plan_m": arrondi(sum(lignes[i]["plan_m"] for i in ids)),
            "chemin_m": arrondi(sum(lignes[i]["chemin_m"] for i in ids)),
            "vertical_m": arrondi(sum(lignes[i]["vertical_m"] for i in ids)),
            "reserve_m": arrondi(sum(lignes[i]["reserve_m"] for i in ids)),
            "total_m": arrondi(sum(lignes[i]["total_m"] for i in ids)),
            "par_type": par_type,
        }

    # Par type et diamètre (« à définir » regroupé, en dernier dans son type).
    libres = list(_calques_libres(plan))
    rang_type = {t: i for i, t in enumerate(list(TYPES_STANDARD) + libres)}
    groupes: dict[tuple[str, str], list[str]] = {}
    for lid, l in lignes.items():
        groupes.setdefault((l["type"], l["diametre"]), []).append(lid)
    apparition = {k: i for i, k in enumerate(groupes)}
    cles_tri = sorted(groupes, key=lambda k: (rang_type.get(k[0], len(rang_type)), k[1] == A_DEFINIR,
                                              apparition[k]))
    par_diametre = {}
    for k in cles_tri:
        ids = groupes[k]
        par_diametre[k] = {"type": k[0], "libelle_type": libelle_type(k[0], plan), "diametre": k[1], "lignes": ids,
                           "plan_m": arrondi(sum(lignes[i]["plan_m"] for i in ids)),
                           "total_m": arrondi(sum(lignes[i]["total_m"] for i in ids))}

    # Hauteurs utilisées : d'abord la table `hauteurs` (ordre fixe), puis les surcharges.
    hypotheses = []
    for cle in sorted(ctx.utilisees, key=lambda c: (ORDRE_HAUTEURS.index(c) if c in ORDRE_HAUTEURS
                                                    else len(ORDRE_HAUTEURS), c)):
        libelle = LIBELLES_HAUTEURS.get(cle, cle)
        if cle == "passage_condensats" and (plan.get("hauteurs") or {}).get("passage_condensats") is None:
            libelle += " (= évaporateurs)"
        hypotheses.append({"cle": cle, "libelle": libelle, "valeur": arrondi(ctx.h[cle]), "statut": ctx.statut(cle),
                           "lignes": ctx.utilisees[cle]})
    for i in ctx.imposees:
        hypotheses.append({**i, "valeur": arrondi(i["valeur"])})

    return Metre(lignes=lignes, par_reseau=par_reseau, par_diametre=par_diametre, hypotheses=hypotheses,
                 hauteurs=dict(ctx.h))


# ---------------------------------------------------------------------------------------------------------------
# Rendu des tableaux
# ---------------------------------------------------------------------------------------------------------------

def _cellule_md(texte: str) -> str:
    return str(texte).replace("|", "\\|").replace("\n", " ")


def _table_md(entetes: list[str], rangs: list[list[str]], aligne: list[str], gras: set[int]) -> str:
    def rang(cellules: list[str], en_gras: bool) -> str:
        cs = [_cellule_md(c) for c in cellules]
        if en_gras:
            cs = [f"**{c}**" if c else c for c in cs]
        return "| " + " | ".join(cs) + " |"
    lignes = [rang(entetes, False), "|" + "|".join("---:" if a == "d" else "---" for a in aligne) + "|"]
    lignes += [rang(r, i in gras) for i, r in enumerate(rangs)]
    return "\n".join(lignes)


STYLE_TABLE = "border-collapse:collapse;font-family:Arial,Helvetica,sans-serif;font-size:9px"
STYLE_CELLULE = "border:1px solid #9E9E9E;padding:1px 4px"
FOND_ENTETE = "#ECEFF1"
FOND_TOTAL = "#F5F5F5"


def _table_html(entetes: list[str], rangs: list[list[str]], aligne: list[str], gras: set[int], note: str = "") -> str:
    """<table> simple (table, tr, td, b) avec styles en ligne : affichable dans une cellule draw.io. `note` : dernier
    rang d'une seule cellule sur toute la largeur (légende « (hyp.) »)."""
    e = _html.escape

    def td(texte: str, a: str, en_gras: bool, fond: str | None) -> str:
        style = STYLE_CELLULE + (";text-align:right" if a == "d" else "") + (f";background:{fond}" if fond else "")
        contenu = e(texte)
        if en_gras and contenu:
            contenu = f"<b>{contenu}</b>"
        return f'<td style="{style}">{contenu}</td>'

    morceaux = [f'<table style="{STYLE_TABLE}">']
    morceaux.append("<tr>" + "".join(td(h, "g", True, FOND_ENTETE) for h in entetes) + "</tr>")
    for i, r in enumerate(rangs):
        g = i in gras
        morceaux.append("<tr>" + "".join(td(c, a, g, FOND_TOTAL if g else None) for c, a in zip(r, aligne)) + "</tr>")
    if note:
        morceaux.append(f'<tr><td colspan="{len(entetes)}" style="{STYLE_CELLULE};font-style:italic">{e(note)}</td></tr>')
    morceaux.append("</table>")
    return "".join(morceaux)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Métré d'un plan 2D (plan.json) : affiche les tableaux.")
    p.add_argument("plan_json", type=Path)
    p.add_argument("--html", action="store_true", help="affiche le fragment HTML au lieu du markdown")
    args = p.parse_args(argv)
    try:
        plan = json.loads(args.plan_json.read_text(encoding="utf-8"))
        m = metrer(plan)
    except (OSError, json.JSONDecodeError, ErreurMetre) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    print(m.html() if args.html else m.markdown())
    return 0


if __name__ == "__main__":
    sys.exit(main())
