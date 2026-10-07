"""Croisements en plan entre lignes de faisceaux différents (vue de dessus seulement), et recouvrements colinéaires.

Règles (décision du 2026-10-07, conventions du skill) :
- deux lignes d'un même `faisceau` (aspiration + liquide d'un même évaporateur) cheminent ensemble : jamais comptées ;
- deux lignes sans `faisceau` : faisceaux différents, sauf si elles relient les mêmes équipements (`de` et `a`
  identiques, dans un sens ou dans l'autre) ; une ligne avec faisceau et une ligne sans : faisceaux différents ;
- un croisement = intersection de deux segments en plan ; on ignore les contacts à 0,05 m ou moins d'une extrémité
  (premier ou dernier point) de l'une des deux lignes : départ commun, ligne qui s'arrête sur une autre ;
- deux segments colinéaires qui se recouvrent sur plus de 0,05 m ne sont pas un croisement : ils sont signalés à
  part par `recouvrements(plan)` (ex. un câble posé dans le chemin de câbles), et les points où les deux lignes se
  rejoignent ou se quittent le long de ce recouvrement ne comptent pas non plus ;
- identifiants X1…Xn attribués après tri par x, puis y (même plan → mêmes identifiants) ;
- pour le dessin, `regrouper(liste)` réunit les croisements distants de 0,50 m ou moins (de proche en proche) en
  un repère G1…Gn : un seul cercle par groupe, étiqueté « X1-X3 » à côté ; les tableaux gardent une ligne par
  croisement, avec la colonne « Repère » quand on leur passe les groupes.

Usage (bibliothèque) :
    from croisements import croisements, recouvrements, regrouper, tableau_markdown, tableau_html
    liste = croisements(plan)    # plan = dict brut de plan.json
    groupes = regrouper(liste)   # [{"id": "G1", "point", "croisements": ["X1", "X2", "X3"], "lignes", "calques"}]
    liste[0] → {"id": "X1", "point": [5.0, 0.5], "lignes": ["L1", "L3"], "calques": ["froid_cuivres", "electricite"],
                "types": ["aspiration", "cable"], "noms_calques": [...], "libelles_types": [...]}

En ligne de commande (contrôle rapide) :
    python croisements.py <plan.json> [--html]
"""
from __future__ import annotations

import argparse
import html as _html
import itertools
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metre import ESPACE, STYLE_CELLULE, STYLE_TABLE, FOND_ENTETE, calque_ligne, libelle_type, nom_calque, nombre_fr  # noqa: E402

TOLERANCE_EXTREMITE = 0.05      # m : contact ignoré près d'une extrémité de ligne ; recouvrement minimal signalé
TOLERANCE_COLINEAIRE = 0.05     # m : les deux bouts d'un segment à 5 cm ou moins de la droite de l'autre = colinéaires
#                                    (un trait déplacé à la souris dans draw.io peut être décalé de 1-2 px, soit 2,5-5 cm à 1:100)
TOLERANCE_DOUBLON = 0.01        # m : même croisement trouvé deux fois (ligne qui passe par un coude de l'autre)
RAYON_GROUPE = 0.5              # m : croisements à 0,50 m ou moins l'un de l'autre = un seul repère dessiné (groupe G)
_EPS = 1e-9
FOIS = "×"

Point = tuple[float, float]


class ErreurCroisements(ValueError):
    """Ligne inutilisable pour le calcul des croisements (message en français)."""


# ---------------------------------------------------------------------------------------------------------------
# Géométrie privée (vue de dessus, mètres)
# ---------------------------------------------------------------------------------------------------------------

def _est_nombre(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _points(ligne: dict) -> list[Point]:
    brut = ligne.get("points")
    lid = ligne.get("id", "?")
    if not isinstance(brut, (list, tuple)) or len(brut) < 2:
        raise ErreurCroisements(f"ligne {lid} : il faut au moins 2 points [x, y] (en m) dans `points`")
    pts = []
    for i, p in enumerate(brut):
        if not isinstance(p, (list, tuple)) or len(p) != 2 or not all(_est_nombre(c) for c in p):
            raise ErreurCroisements(f"ligne {lid} : point n° {i + 1} invalide ({p!r}) ; attendu [x, y] en mètres")
        pts.append((float(p[0]), float(p[1])))
    return pts


def _segments(pts: list[Point]) -> list[tuple[Point, Point]]:
    return [(a, b) for a, b in zip(pts, pts[1:]) if math.hypot(b[0] - a[0], b[1] - a[1]) > _EPS]


def _distance(p: Point, q: Point) -> float:
    return math.hypot(q[0] - p[0], q[1] - p[1])


def _vectoriel(u: Point, v: Point) -> float:
    return u[0] * v[1] - u[1] * v[0]


def _distance_droite(p: Point, a: Point, b: Point) -> float:
    """Distance de p à la droite (a, b) (a ≠ b)."""
    d = (b[0] - a[0], b[1] - a[1])
    return abs(_vectoriel((p[0] - a[0], p[1] - a[1]), d)) / math.hypot(*d)


def _distance_segment(p: Point, a: Point, b: Point) -> float:
    d = (b[0] - a[0], b[1] - a[1])
    l2 = d[0] ** 2 + d[1] ** 2
    if l2 <= _EPS ** 2:
        return _distance(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * d[0] + (p[1] - a[1]) * d[1]) / l2))
    return _distance(p, (a[0] + t * d[0], a[1] + t * d[1]))


def _intersection(p1: Point, p2: Point, q1: Point, q2: Point) -> tuple[str, Any] | None:
    """("point", (x, y)) si les segments se coupent ou se touchent ; ("recouvrement", (début, fin)) s'ils sont
    colinéaires et se recouvrent ; None sinon."""
    d1 = (p2[0] - p1[0], p2[1] - p1[1])
    d2 = (q2[0] - q1[0], q2[1] - q1[1])
    l1 = math.hypot(*d1)
    if _distance_droite(q1, p1, p2) <= TOLERANCE_COLINEAIRE and _distance_droite(q2, p1, p2) <= TOLERANCE_COLINEAIRE:
        u = (d1[0] / l1, d1[1] / l1)
        s0 = (q1[0] - p1[0]) * u[0] + (q1[1] - p1[1]) * u[1]
        s1 = (q2[0] - p1[0]) * u[0] + (q2[1] - p1[1]) * u[1]
        bas, haut = max(0.0, min(s0, s1)), min(l1, max(s0, s1))
        if haut - bas <= _EPS:
            if haut - bas >= -TOLERANCE_COLINEAIRE:                 # bout à bout : simple contact
                s = (bas + haut) / 2
                return "point", (p1[0] + s * u[0], p1[1] + s * u[1])
            return None
        return "recouvrement", ((p1[0] + bas * u[0], p1[1] + bas * u[1]), (p1[0] + haut * u[0], p1[1] + haut * u[1]))
    den = _vectoriel(d1, d2)
    if abs(den) <= _EPS * l1 * math.hypot(*d2):
        return None                                                  # parallèles distincts
    w = (q1[0] - p1[0], q1[1] - p1[1])
    t = _vectoriel(w, d2) / den
    s = _vectoriel(w, d1) / den
    if -_EPS <= t <= 1 + _EPS and -_EPS <= s <= 1 + _EPS:
        return "point", (p1[0] + t * d1[0], p1[1] + t * d1[1])
    return None


def _fusionner_recouvrements(morceaux: list[tuple[Point, Point]]) -> list[tuple[Point, Point]]:
    """Réunit les morceaux colinéaires qui se touchent (ligne coupée en plusieurs segments alignés)."""
    morceaux = list(morceaux)
    change = True
    while change:
        change = False
        for i, j in itertools.combinations(range(len(morceaux)), 2):
            (a0, a1), (b0, b1) = morceaux[i], morceaux[j]
            if _distance(a0, a1) <= _EPS:
                continue
            if _distance_droite(b0, a0, a1) > TOLERANCE_COLINEAIRE or _distance_droite(b1, a0, a1) > TOLERANCE_COLINEAIRE:
                continue
            la = _distance(a0, a1)
            u = ((a1[0] - a0[0]) / la, (a1[1] - a0[1]) / la)
            proj = lambda p: (p[0] - a0[0]) * u[0] + (p[1] - a0[1]) * u[1]  # noqa: E731
            s_b = sorted((proj(b0), proj(b1)))
            if s_b[0] > la + TOLERANCE_COLINEAIRE or s_b[1] < -TOLERANCE_COLINEAIRE:
                continue                                             # alignés mais disjoints
            bas, haut = min(0.0, s_b[0]), max(la, s_b[1])
            morceaux[i] = ((a0[0] + bas * u[0], a0[1] + bas * u[1]), (a0[0] + haut * u[0], a0[1] + haut * u[1]))
            del morceaux[j]
            change = True
            break
    return morceaux


# ---------------------------------------------------------------------------------------------------------------
# Règles du module
# ---------------------------------------------------------------------------------------------------------------

def meme_faisceau(la: dict, lb: dict) -> bool:
    """Vrai si les deux lignes cheminent ensemble (même `faisceau`, ou sans faisceau et mêmes équipements reliés)."""
    fa, fb = la.get("faisceau") or None, lb.get("faisceau") or None
    if fa is not None or fb is not None:
        return fa is not None and fa == fb
    bouts_a, bouts_b = (la.get("de"), la.get("a")), (lb.get("de"), lb.get("a"))
    if None in bouts_a or None in bouts_b:
        return False
    return sorted(map(str, bouts_a)) == sorted(map(str, bouts_b))


def _analyser_paire(pa: list[Point], pb: list[Point]) -> tuple[list[Point], list[tuple[Point, Point]]]:
    """Croisements retenus et recouvrements (fusionnés, > 0,05 m) entre deux polylignes."""
    candidats: list[Point] = []
    morceaux: list[tuple[Point, Point]] = []
    for s1 in _segments(pa):
        for s2 in _segments(pb):
            r = _intersection(*s1, *s2)
            if r is None:
                continue
            if r[0] == "recouvrement":
                morceaux.append(r[1])
            else:
                candidats.append(r[1])
    tous_recouvrements = _fusionner_recouvrements(morceaux)
    extremites = (pa[0], pa[-1], pb[0], pb[-1])
    retenus: list[Point] = []
    for c in candidats:
        if any(_distance(c, e) <= TOLERANCE_EXTREMITE + _EPS for e in extremites):
            continue                                                 # contact en bout de ligne
        if any(_distance_segment(c, r0, r1) <= TOLERANCE_EXTREMITE + _EPS for r0, r1 in tous_recouvrements):
            continue                                                 # jonction le long d'un recouvrement
        if any(_distance(c, p) <= TOLERANCE_DOUBLON for p in retenus):
            continue                                                 # déjà trouvé (passage par un coude)
        retenus.append(c)
    recouv = [r for r in tous_recouvrements if _distance(*r) > TOLERANCE_EXTREMITE + _EPS]
    return retenus, recouv


def _lignes_valides(plan: dict) -> list[tuple[dict, list[Point]]]:
    if not isinstance(plan, dict):
        raise ErreurCroisements("plan : un objet JSON (dict) est attendu")
    resultat = []
    for i, ligne in enumerate(plan.get("lignes") or []):
        if not isinstance(ligne, dict) or not ligne.get("id"):
            raise ErreurCroisements(f"lignes[{i}] : chaque ligne doit avoir un `id`")
        resultat.append((ligne, _points(ligne)))
    return resultat


def _coord(v: float) -> float:
    return round(v, 3) + 0.0                                         # au mm, sans « -0.0 »


def _decrire(paire: tuple[dict, dict], plan: dict) -> dict:
    la, lb = paire
    calques = [calque_ligne(la), calque_ligne(lb)]
    types = [la.get("type"), lb.get("type")]
    return {"lignes": [la["id"], lb["id"]], "calques": calques, "types": types,
            "noms_calques": [nom_calque(c, plan) for c in calques],
            "libelles_types": [libelle_type(t, plan) for t in types]}


def _analyser(plan: dict) -> tuple[list[dict], list[dict]]:
    lignes = _lignes_valides(plan)
    rang = {l["id"]: i for i, (l, _) in enumerate(lignes)}
    trouves, recouvs = [], []
    for (la, pa), (lb, pb) in itertools.combinations(lignes, 2):
        if meme_faisceau(la, lb):
            continue
        points, recouvrements_paire = _analyser_paire(pa, pb)
        desc = _decrire((la, lb), plan)
        for p in points:
            trouves.append({"point": [_coord(p[0]), _coord(p[1])], **desc})
        for r0, r1 in recouvrements_paire:
            debut, fin = sorted([r0, r1])
            recouvs.append({"de": [_coord(debut[0]), _coord(debut[1])], "a": [_coord(fin[0]), _coord(fin[1])],
                            "longueur_m": round(_distance(r0, r1), 2) + 0.0, **desc})

    def cle(e: dict, champ: str) -> tuple:
        return (e[champ][0], e[champ][1], rang[e["lignes"][0]], rang[e["lignes"][1]])

    trouves.sort(key=lambda e: cle(e, "point"))
    recouvs.sort(key=lambda e: cle(e, "de"))
    croises = [{"id": f"X{i}", **e} for i, e in enumerate(trouves, start=1)]
    recouvs = [{"id": f"R{i}", **e} for i, e in enumerate(recouvs, start=1)]
    return croises, recouvs


def croisements(plan: dict) -> list[dict]:
    """Croisements entre lignes de faisceaux différents, triés par x puis y, identifiants X1…Xn.

    Chaque élément : {"id", "point": [x, y] (m, au mm), "lignes": [idA, idB] (ordre de plan.json), "calques",
    "types", "noms_calques", "libelles_types"}.
    """
    return _analyser(plan)[0]


def recouvrements(plan: dict) -> list[dict]:
    """Tronçons où deux lignes de faisceaux différents se superposent en plan (> 0,05 m), identifiants R1…Rn.

    Chaque élément : {"id", "de": [x, y], "a": [x, y], "longueur_m", "lignes", "calques", "types", ...}.
    """
    return _analyser(plan)[1]


def regrouper(liste: list[dict], rayon: float = RAYON_GROUPE) -> list[dict]:
    """Groupes de croisements pour le dessin : deux croisements distants de `rayon` m ou moins sont dans le même
    groupe, de proche en proche (fermeture transitive) ; un croisement isolé forme son propre groupe.

    Chaque groupe : {"id": "G1", "point": [x, y] (moyenne des points, au mm), "croisements": ["X1", "X2", "X3"],
    "lignes": union (ordre d'apparition), "calques": union}. Groupes numérotés dans l'ordre de leur premier
    croisement (même liste → mêmes repères). `croisements()` ne change pas : les tableaux restent par croisement.
    """
    n = len(liste)
    parent = list(range(n))

    def racine(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in itertools.combinations(range(n), 2):
        pi, pj = liste[i]["point"], liste[j]["point"]
        if _distance((pi[0], pi[1]), (pj[0], pj[1])) <= rayon + _EPS:
            ri, rj = racine(i), racine(j)
            if ri != rj:
                parent[max(ri, rj)] = min(ri, rj)
    membres: dict[int, list[int]] = {}
    for i in range(n):
        membres.setdefault(racine(i), []).append(i)
    groupes = []
    for k, indices in enumerate(sorted(membres.values(), key=min), start=1):
        xs = [liste[i] for i in indices]
        lignes: list = []
        calques: list = []
        for x in xs:
            lignes += [l for l in x.get("lignes") or [] if l not in lignes]
            calques += [c for c in x.get("calques") or [] if c not in calques]
        groupes.append({"id": f"G{k}",
                        "point": [_coord(sum(x["point"][0] for x in xs) / len(xs)),
                                  _coord(sum(x["point"][1] for x in xs) / len(xs))],
                        "croisements": [x["id"] for x in xs], "lignes": lignes, "calques": calques})
    return groupes


def etiquette_groupe(groupe: dict) -> str:
    """Texte dessiné à côté du cercle d'un groupe : « X1-X3 » (numéros qui se suivent), « X4 », « X1-X2, X5 »."""
    ids = list(groupe.get("croisements") or [])
    if not ids or not all(re.fullmatch(r"X\d+", str(i)) for i in ids):
        return ", ".join(map(str, ids))
    nums = sorted(int(str(i)[1:]) for i in ids)
    morceaux, debut, prec = [], nums[0], nums[0]
    for v in nums[1:] + [None]:
        if v is not None and v == prec + 1:
            prec = v
            continue
        morceaux.append(f"X{debut}" if debut == prec else f"X{debut}-X{prec}")
        if v is not None:
            debut = prec = v
    return ", ".join(morceaux)


def groupes_pour_dessin(groupes: list[dict]) -> list[dict]:
    """Groupes au format injecté dans le modèle pour le dessin (`plan.donnees["croisements"]`, jamais écrit dans
    plan.json) : un cercle par groupe (identifiant G…), étiquette « X1-X3 » posée à côté par drawio.py."""
    return [{"id": g["id"], "point": list(g["point"]), "croisements": list(g["croisements"]),
             "lignes": list(g["lignes"]), "etiquette": etiquette_groupe(g)} for g in groupes]


# ---------------------------------------------------------------------------------------------------------------
# Tableaux
# ---------------------------------------------------------------------------------------------------------------

AUCUN = "Aucun croisement entre réseaux."
ENTETES = ["N°", "Point (x ; y)", "Lignes", "Calques"]
ENTETES_REPERE = ["N°", "Repère", "Point (x ; y)", "Lignes", "Calques"]     # avec les groupes (repères G du dessin)


def _rangs(liste: list[dict], groupes: list[dict] | None = None) -> list[list[str]]:
    repere = {xid: g["id"] for g in groupes or [] for xid in g.get("croisements") or []}
    rangs = []
    for c in liste:
        x, y = c["point"]
        types = c.get("libelles_types") or c.get("types") or ["", ""]
        noms = c.get("noms_calques") or c.get("calques") or ["", ""]
        rangs.append([c["id"], f"{nombre_fr(x)}{ESPACE}m ; {nombre_fr(y)}{ESPACE}m",
                      f"{c['lignes'][0]} ({types[0]}) {FOIS} {c['lignes'][1]} ({types[1]})",
                      f"{noms[0]} {FOIS} {noms[1]}"])
        if groupes is not None:
            rangs[-1].insert(1, repere.get(c["id"], ""))
    return rangs


def tableau_markdown(liste: list[dict], groupes: list[dict] | None = None) -> str:
    """Tableau markdown N° | Point (x ; y) | Lignes | Calques (+ colonne « Repère » après N° si `groupes` est
    donné) ; liste vide → « Aucun croisement entre réseaux. »."""
    if not liste:
        return AUCUN
    entetes = ENTETES if groupes is None else ENTETES_REPERE
    lignes = ["| " + " | ".join(entetes) + " |", "|" + "---|" * len(entetes)]
    for r in _rangs(liste, groupes):
        lignes.append("| " + " | ".join(c.replace("|", "\\|") for c in r) + " |")
    return "\n".join(lignes)


def tableau_html(liste: list[dict], groupes: list[dict] | None = None) -> str:
    """Même tableau en HTML simple (table, tr, td, b ; styles en ligne), pour la page « Métré » de plan.drawio."""
    e = _html.escape
    entetes = ENTETES if groupes is None else ENTETES_REPERE
    td = lambda t, fond=None, gras=False: (  # noqa: E731
        f'<td style="{STYLE_CELLULE}{";background:" + fond if fond else ""}">'
        f'{"<b>" + e(t) + "</b>" if gras else e(t)}</td>')
    morceaux = [f'<table style="{STYLE_TABLE}">', "<tr>" + "".join(td(h, FOND_ENTETE, True) for h in entetes) + "</tr>"]
    if not liste:
        morceaux.append(f'<tr><td colspan="{len(entetes)}" style="{STYLE_CELLULE}">{e(AUCUN)}</td></tr>')
    for r in _rangs(liste, groupes):
        morceaux.append("<tr>" + "".join(td(c) for c in r) + "</tr>")
    morceaux.append("</table>")
    return "".join(morceaux)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Croisements entre réseaux d'un plan 2D (plan.json).")
    p.add_argument("plan_json", type=Path)
    p.add_argument("--html", action="store_true", help="affiche le tableau HTML au lieu du markdown")
    args = p.parse_args(argv)
    try:
        plan = json.loads(args.plan_json.read_text(encoding="utf-8"))
        liste = croisements(plan)
        recouv = recouvrements(plan)
    except (OSError, json.JSONDecodeError, ErreurCroisements) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    print(tableau_html(liste) if args.html else tableau_markdown(liste))
    for r in recouv:
        print(f"Recouvrement {r['id']} : {r['lignes'][0]} et {r['lignes'][1]} superposées sur "
              f"{nombre_fr(r['longueur_m'])}{ESPACE}m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
