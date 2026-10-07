"""Photo d'une feuille tracée au marqueur → calque du réseau en mètres (Lot 6 du skill froid-plan-2d).

Étapes : repères ArUco (4 coins de chacun des 4 repères = 16 points) → homographie photo → mm de la
feuille (+ erreur de reprojection) → redressement à 4 px/mm → retrait du plan imprimé (masque de la
feuille rendue, dilaté de 3 px) → segmentation du marqueur (HSV rouge/bleu/vert, ou sombre pour le noir)
→ nettoyage morphologique → squelette Zhang-Suen (numpy) → suivi du squelette en polylignes (jonctions,
extrémités, croisements traversés tout droit) → simplification (1,5 mm) → conversion mm → m →
découpe aux équipements, accrochage (équipements 0,15 m, murs 0,10 m) et redressement des angles
(≤ 7° de 0/90°) → `calques/<reseau>.json` + `calques/<reseau>-controle.png` ; `--fusionner` ajoute les
lignes dans `plan.json` (ancienne version sauvegardée dans `versions/`).

Les longueurs sont mesurées par rapport aux repères : ni la perspective ni une impression réduite
uniformément ne les faussent.

Usage (racine du dépôt) :
    python .claude/skills/froid-plan-2d/scripts/lire_photo.py <dossier_plan> <photo> --reseau <cle>
           [--fusionner] [--confirmer] [--marqueur rouge|bleu|vert|noir|auto]
           [--longueur-attendue 12.5] [--accrochage centre|bord]
Codes de retour : 0 calque produit ; 1 repères manquants ou aucun trait trouvé ; 2 fichier manquant.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

import feuille as fe

# --- Paramètres -----------------------------------------------------------------------------------
PX_PAR_MM = 4                          # résolution de la photo redressée
DILATATION_MASQUE_PX = 3               # masque du plan imprimé dilaté de 3 px (0,75 mm)
SEUIL_IMPRIME = 245                    # pixel de la feuille rendue < 245 = imprimé
PX_PAR_MM_MAX_AVANT_REDRESSEMENT = 6.0 # photo plus fine : réduite (INTER_AREA) avant le redressement
SAT_MIN, VAL_MIN = 90, 50              # couleur franche : saturation ≥ 0,35 et valeur ≥ 0,20 (image normalisée)
PLAGES_TEINTE = {"rouge": [(0, 10), (160, 179)], "vert": [(35, 90)], "bleu": [(91, 135)]}  # teinte OpenCV 0-179
NOIR_MAX, NOIR_STRICT = 0.40, 0.30     # noir : valeur normalisée < 0,40 hors plan imprimé, < 0,30 sur le plan imprimé
AIRE_MIN_MM2 = 2.0                     # composantes plus petites supprimées
AIRE_MIN_COULEUR_MM2 = 10.0            # surface minimale pour considérer qu'une couleur est présente
TROU_MAX_MM2 = 4.0                     # trous (reflets) bouchés dans le trait
EPSILON_SIMPLIFICATION_MM = 1.5
LONGUEUR_MIN_MM = 3.0                  # polyligne isolée plus courte : bruit
ERGOT_MIN_MM = 3.0                     # branche libre plus courte que max(3 mm, 1,5 × largeur du trait) : supprimée
ANGLE_TRAVERSEE_DEG = 150.0            # deux branches d'une jonction à ≥ 150° : même trait (croisement)
TOLERANCE_ANGLE_DEG = 7.0              # segment à ≤ 7° de 0/90° : redressé
ACCROCHE_EQUIPEMENT_M = 0.15
ACCROCHE_MUR_M = 0.10
MARGE_DECOUPE_EQUIPEMENT_M = 0.05      # sommet intérieur dans un équipement : la polyligne y est coupée
ECART_RELATIF_MAX, ECART_ABSOLU_MAX_M = 0.05, 0.30  # seuil provisoire (question 14 de Loïc)
REPROJECTION_ALERTE_MM = 1.0
TYPES_DEPART = {"evaporateur", "split"}
TYPES_ARRIVEE = {"groupe", "centrale", "condenseur", "moteur", "tableau"}
CALQUES_STANDARD = {"plan_de_base", "cotes", "froid_equipements", "froid_cuivres", "electricite",
                    "clim_equipements", "clim_cuivres", "croisements", "cartouche"}
COULEURS = ("rouge", "bleu", "vert", "noir")


class ErreurPhoto(Exception):
    """Erreur lisible ; `code` = code de retour (1 repères manquants / aucun trait, 2 fichier manquant)."""

    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


def _f(v: float, n: int = 2) -> str:
    return f"{v:.{n}f}".replace(".", ",")


# --- Géométrie privée (mètres) ---------------------------------------------------------------------
def _longueur(points) -> float:
    p = np.asarray(points, dtype=float)
    return float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()) if len(p) > 1 else 0.0


def _point_dans_polygone(p, poly) -> bool:
    x, y = p
    dedans = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            dedans = not dedans
    return dedans


def _plus_proche_segment(p, a, b):
    p, a, b = (np.asarray(v, dtype=float) for v in (p, a, b))
    ab = b - a
    l2 = float(ab @ ab)
    t = 0.0 if l2 < 1e-18 else min(1.0, max(0.0, float((p - a) @ ab) / l2))
    return a + t * ab


def _plus_proche_contour(p, poly):
    meilleur, dmin = None, math.inf
    for i in range(len(poly)):
        q = _plus_proche_segment(p, poly[i], poly[(i + 1) % len(poly)])
        d = float(np.linalg.norm(q - np.asarray(p, dtype=float)))
        if d < dmin:
            meilleur, dmin = q, d
    return meilleur, dmin


def _distance_polygone(p, poly) -> float:
    """0 si le point est dans le polygone, sinon distance au contour."""
    if _point_dans_polygone(p, poly):
        return 0.0
    return _plus_proche_contour(p, poly)[1]


def redresser_polyligne(points, epingles: dict | None = None, tolerance_deg: float = TOLERANCE_ANGLE_DEG):
    """Redresse à 0/90° les segments à ≤ tolerance_deg ; `epingles` = {indice: {"x": v, "y": v}} imposés.

    Les sommets reliés par des segments horizontaux partagent un même y (moyenne, ou valeur épinglée),
    idem pour x et les segments verticaux. Renvoie (points, avertissements).
    """
    pts = np.array(points, dtype=float)
    epingles = epingles or {}
    n = len(pts)
    avert = []
    parents = {"x": list(range(n)), "y": list(range(n))}

    def racine(axe, i):
        while parents[axe][i] != i:
            parents[axe][i] = parents[axe][parents[axe][i]]
            i = parents[axe][i]
        return i

    for i in range(n - 1):
        dx, dy = pts[i + 1] - pts[i]
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            continue
        a = abs(math.degrees(math.atan2(dy, dx))) % 180.0
        if min(a, 180.0 - a) <= tolerance_deg:
            parents["y"][racine("y", i + 1)] = racine("y", i)
        elif abs(a - 90.0) <= tolerance_deg:
            parents["x"][racine("x", i + 1)] = racine("x", i)
    for k, axe in enumerate(("x", "y")):
        groupes: dict[int, list[int]] = {}
        for i in range(n):
            groupes.setdefault(racine(axe, i), []).append(i)
        for membres in groupes.values():
            imposes = [epingles[i][axe] for i in membres if axe in epingles.get(i, {})]
            if imposes:
                if max(imposes) - min(imposes) > 1e-6:
                    avert.append("segment non redressé : ses deux extrémités sont accrochées à des points non alignés")
                    for i in membres:
                        pts[i, k] = epingles[i][axe] if axe in epingles.get(i, {}) else float(np.mean(imposes))
                    continue
                valeur = imposes[0]
            else:
                valeur = float(np.mean(pts[membres, k]))
            pts[membres, k] = valeur
    return _nettoyer_polyligne(pts), avert


def _nettoyer_polyligne(pts: np.ndarray) -> np.ndarray:
    """Retire les doublons consécutifs et les sommets intermédiaires alignés."""
    garde = [pts[0]]
    for p in pts[1:]:
        if np.linalg.norm(p - garde[-1]) > 1e-6:
            garde.append(p)
    i = 1
    while i < len(garde) - 1:
        a, b, c = garde[i - 1], garde[i], garde[i + 1]
        u, v = b - a, c - b
        if abs(u[0] * v[1] - u[1] * v[0]) < 1e-9 * max(1.0, np.linalg.norm(u) * np.linalg.norm(v)) and u @ v > 0:
            garde.pop(i)
        else:
            i += 1
    return np.array(garde)


# --- Traitement d'image ------------------------------------------------------------------------------
def _noyau(diametre: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (diametre, diametre))


def _normaliser(bgr: np.ndarray, ppm: float) -> np.ndarray:
    """Divise chaque canal par le fond local (filtre max 6 mm puis flou) : papier = 1, dégradés et dominante retirés."""
    img = bgr.astype(np.float32) / 255.0
    k = int(round(6 * ppm)) | 1
    fond = cv2.dilate(img, _noyau(k))
    fond = cv2.GaussianBlur(fond, (0, 0), 2 * ppm)
    return np.clip(img / np.maximum(fond, 1e-3), 0, 1)


def _hsv(norm: np.ndarray) -> np.ndarray:
    return cv2.cvtColor((norm * 255 + 0.5).astype(np.uint8), cv2.COLOR_BGR2HSV)


def segmenter(norm: np.ndarray, couleur: str, hsv: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(segmentation, segmentation stricte pour les pixels sur le plan imprimé), booléens."""
    hsv = _hsv(norm) if hsv is None else hsv
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    if couleur == "noir":
        return v < NOIR_MAX * 255, v < NOIR_STRICT * 255
    franc = (s >= SAT_MIN) & (v >= VAL_MIN)
    teinte = np.zeros(h.shape, bool)
    for lo, hi in PLAGES_TEINTE[couleur]:
        teinte |= (h >= lo) & (h <= hi)
    seg = franc & teinte
    return seg, seg


def _boucher_trous(b: np.ndarray, aire_max_px: float) -> np.ndarray:
    fond = (~b).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fond, connectivity=4)
    h, w = b.shape
    trous = np.zeros(n, bool)
    for i in range(1, n):
        x, y, lw, lh, aire = stats[i]
        if aire <= aire_max_px and x > 0 and y > 0 and x + lw < w and y + lh < h:
            trous[i] = True
    return b | trous[lab]


def squelette_zhang_suen(binaire: np.ndarray) -> np.ndarray:
    """Squelette de Zhang-Suen (vectorisé numpy), suivi d'un affinement des marches d'escalier
    (points simples au sens de la connexité 8, en 4 sous-champs) : squelette 8-connexe d'un pixel."""
    img = (np.asarray(binaire) > 0).astype(np.uint8)
    ys, xs = np.nonzero(img)
    if len(ys) == 0:
        return img
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    p = np.pad(img[y0:y1, x0:x1], 1)

    def voisins(q):
        return (q[:-2, 1:-1], q[:-2, 2:], q[1:-1, 2:], q[2:, 2:], q[2:, 1:-1], q[2:, :-2], q[1:-1, :-2], q[:-2, :-2])

    while True:
        change = False
        for etape in (0, 1):
            p2, p3, p4, p5, p6, p7, p8, p9 = voisins(p)
            centre = p[1:-1, 1:-1]
            b = p2.astype(np.int16) + p3 + p4 + p5 + p6 + p7 + p8 + p9
            seq = (p2, p3, p4, p5, p6, p7, p8, p9, p2)
            a = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.int16) for i in range(8))
            if etape == 0:
                m1, m2 = p2 * p4 * p6, p4 * p6 * p8
            else:
                m1, m2 = p2 * p4 * p8, p2 * p6 * p8
            sup = (centre == 1) & (b >= 2) & (b <= 6) & (a == 1) & (m1 == 0) & (m2 == 0)
            if sup.any():
                centre[sup] = 0
                change = True
        if not change:
            break
    # Affinement : retire les points simples (nombre de connexité 8 de Yokoi = 1) non terminaux.
    lignes, colonnes = np.mgrid[0:p.shape[0] - 2, 0:p.shape[1] - 2]
    for _ in range(10):
        change = False
        for (ry, rx) in ((0, 0), (0, 1), (1, 0), (1, 1)):
            p2, p3, p4, p5, p6, p7, p8, p9 = voisins(p)
            centre = p[1:-1, 1:-1]
            # ordre de Yokoi : x1=E, x2=NE, x3=N, x4=NO, x5=O, x6=SO, x7=S, x8=SE
            x = [1 - q.astype(np.int16) for q in (p4, p3, p2, p9, p8, p7, p6, p5)]
            x.append(x[0])
            x.append(x[1])
            n8 = sum(x[k] - x[k] * x[k + 1] * x[k + 2] for k in (0, 2, 4, 6))
            nb = p2.astype(np.int16) + p3 + p4 + p5 + p6 + p7 + p8 + p9
            sup = (centre == 1) & (n8 == 1) & (nb >= 2) & (lignes % 2 == ry) & (colonnes % 2 == rx)
            if sup.any():
                centre[sup] = 0
                change = True
        if not change:
            break
    out = np.zeros_like(img)
    out[y0:y1, x0:x1] = p[1:-1, 1:-1]
    return out


# --- Vectorisation du squelette ------------------------------------------------------------------------
_VOISINS = ((-1, 0), (0, 1), (1, 0), (0, -1), (-1, 1), (1, 1), (1, -1), (-1, -1))  # 4-voisins d'abord


def _nb_voisins(b: np.ndarray) -> np.ndarray:
    k = np.ones((3, 3), np.float32)
    k[1, 1] = 0
    return np.rint(cv2.filter2D(b.astype(np.float32), -1, k, borderType=cv2.BORDER_CONSTANT)).astype(np.int32)


def vectoriser(squelette: np.ndarray, ergot_px: float, longueur_min_px: float, contraction_px: float,
               bloquant=None) -> list[dict]:
    """Squelette → polylignes en px (x, y). Jonctions = pixels à ≥ 3 voisins (regroupés) ; branches libres
    courtes (ergots) supprimées ; jonctions proches fusionnées ; branches alignées (≥ 150°) d'une jonction
    traversées tout droit ; `bloquant(x, y)` = True interdit toute fusion au nœud (nœud sur un équipement).
    Renvoie [{"points": array (n, 2), "libre_debut": bool, "libre_fin": bool}]."""
    sk = (squelette > 0).astype(np.uint8)
    nb = _nb_voisins(sk) * sk
    jonction = (nb >= 3) & (sk > 0)
    nj, lab_j, _, centres_j = cv2.connectedComponentsWithStats(jonction.astype(np.uint8), connectivity=8)
    noeuds = {j: {"pos": np.array(centres_j[j], dtype=float), "jonction": True} for j in range(1, nj)}
    chemin = (sk > 0) & ~jonction
    n, lab = cv2.connectedComponents(chemin.astype(np.uint8), connectivity=8)
    ys, xs = np.nonzero(lab)
    etiquettes = lab[ys, xs]
    ordre = np.argsort(etiquettes, kind="stable")
    ys, xs, etiquettes = ys[ordre], xs[ordre], etiquettes[ordre]
    bornes = np.flatnonzero(np.diff(etiquettes)) + 1
    h, w = sk.shape
    aretes: dict[int, dict] = {}
    compteur = [0]
    prochain_libre = -1

    def jonctions_adjacentes(y, x):
        ids = []
        for dy, dx in _VOISINS:
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w and lab_j[yy, xx] and lab_j[yy, xx] not in ids:
                ids.append(int(lab_j[yy, xx]))
        return ids

    for groupe_y, groupe_x in zip(np.split(ys, bornes), np.split(xs, bornes)):
        restants = set(zip(groupe_y.tolist(), groupe_x.tolist()))
        while restants:
            debut = None
            for p in restants:
                if sum((p[0] + dy, p[1] + dx) in restants for dy, dx in _VOISINS) <= 1:
                    debut = p
                    break
            if debut is None:
                debut = min(restants)
            trace = [debut]
            restants.discard(debut)
            while True:
                y, x = trace[-1]
                suivant = next(((y + dy, x + dx) for dy, dx in _VOISINS if (y + dy, x + dx) in restants), None)
                if suivant is None:
                    break
                trace.append(suivant)
                restants.discard(suivant)
            j_debut = jonctions_adjacentes(*trace[0])
            j_fin = jonctions_adjacentes(*trace[-1])
            a = j_debut[0] if j_debut else None
            b = next((j for j in j_fin if j != a or len(trace) > 1), None) if j_fin else None
            if len(trace) == 1 and a is not None and b == a:
                b = None
            pts = [np.array([float(x), float(y)]) for y, x in trace]
            boucle = (a is None and b is None and len(trace) > 3 and
                      max(abs(trace[-1][0] - trace[0][0]), abs(trace[-1][1] - trace[0][1])) <= 1)
            if boucle:
                pts.append(pts[0].copy())
            if a is None:
                a = prochain_libre
                noeuds[a] = {"pos": pts[0].copy(), "jonction": False}
                prochain_libre -= 1
            else:
                pts.insert(0, noeuds[a]["pos"].copy())
            if b is None:
                if boucle:
                    b = a
                else:
                    b = prochain_libre
                    noeuds[b] = {"pos": pts[-1].copy(), "jonction": False}
                    prochain_libre -= 1
            else:
                pts.append(noeuds[b]["pos"].copy())
            aretes[compteur[0]] = {"pts": np.array(pts), "a": a, "b": b}
            compteur[0] += 1

    def incidentes(nid):
        return [e for e, ar in aretes.items() if ar["a"] == nid or ar["b"] == nid]

    def degre(nid):
        return sum((ar["a"] == nid) + (ar["b"] == nid) for ar in aretes.values())

    def est_bloque(nid):
        return bloquant is not None and bloquant(*noeuds[nid]["pos"])

    def fusionner_aretes(e1, e2, nid):
        a1, a2 = aretes.pop(e1), aretes.pop(e2)
        p1 = a1["pts"] if a1["b"] == nid else a1["pts"][::-1]
        autre1 = a1["a"] if a1["b"] == nid else a1["b"]
        p2 = a2["pts"] if a2["a"] == nid else a2["pts"][::-1]
        autre2 = a2["b"] if a2["a"] == nid else a2["a"]
        aretes[compteur[0]] = {"pts": np.vstack([p1, p2[1:]]), "a": autre1, "b": autre2}
        compteur[0] += 1

    # 1. Jonctions reliées par une arête très courte (croisement épais) : fusionnées en une seule.
    change = True
    while change:
        change = False
        for e, ar in list(aretes.items()):
            if (ar["a"] != ar["b"] and noeuds[ar["a"]]["jonction"] and noeuds[ar["b"]]["jonction"]
                    and _longueur(ar["pts"]) < contraction_px):
                garde, retire = ar["a"], ar["b"]
                nouvelle = (noeuds[garde]["pos"] + noeuds[retire]["pos"]) / 2
                del aretes[e]
                noeuds[garde]["pos"] = nouvelle
                for ar2 in aretes.values():
                    for cle, idx in (("a", 0), ("b", -1)):
                        if ar2[cle] == retire:
                            ar2[cle] = garde
                    if ar2["a"] == garde:
                        ar2["pts"][0] = nouvelle
                    if ar2["b"] == garde:
                        ar2["pts"][-1] = nouvelle
                del noeuds[retire]
                change = True
                break
    # 2. Ergots, puis fusion des nœuds de degré 2 (sauf nœuds bloqués), en boucle.
    change = True
    while change:
        change = False
        for e, ar in list(aretes.items()):
            libres = [not noeuds[ar[c]]["jonction"] for c in ("a", "b")]
            if sum(libres) == 1 and _longueur(ar["pts"]) < ergot_px:
                j = ar["b"] if libres[0] else ar["a"]
                if degre(j) >= 3:
                    del aretes[e]
                    change = True
        for nid in list(noeuds):
            if nid not in noeuds or not noeuds[nid]["jonction"]:
                continue
            inc = incidentes(nid)
            if len(inc) == 2 and degre(nid) == 2 and not est_bloque(nid):
                fusionner_aretes(inc[0], inc[1], nid)
                noeuds[nid]["jonction"] = False
                change = True
    # 3. Traversée tout droit des jonctions (croisements, T) : appariement des bouts de branches opposés.
    #    Un bout = (arête, "a" | "b") ; une boucle revenant à la jonction y a deux bouts.
    seuil_cos = math.cos(math.radians(ANGLE_TRAVERSEE_DEG))

    def direction(e, bout):
        pts = aretes[e]["pts"] if bout == "a" else aretes[e]["pts"][::-1]
        cumul = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
        k = int(np.searchsorted(cumul, min(cumul[-1], 2 * contraction_px)))
        d = pts[min(k, len(pts) - 1)] - pts[0]
        return d / max(np.linalg.norm(d), 1e-9)

    for nid in list(noeuds):
        if not noeuds[nid]["jonction"] or est_bloque(nid):
            continue
        while True:
            bouts = [(e, c) for e, ar in aretes.items() for c in ("a", "b") if ar[c] == nid]
            if len(bouts) < 2:
                break
            dirs = {b: direction(*b) for b in bouts}
            meilleure = min(((float(dirs[b1] @ dirs[b2]), b1, b2) for i, b1 in enumerate(bouts)
                             for b2 in bouts[i + 1:] if b1[0] != b2[0]), default=None, key=lambda t: t[0])
            if meilleure is None or meilleure[0] > seuil_cos:
                break
            _, (e1, c1), (e2, c2) = meilleure
            a1, a2 = aretes.pop(e1), aretes.pop(e2)
            p1 = a1["pts"] if c1 == "b" else a1["pts"][::-1]          # se termine au nœud
            p2 = a2["pts"] if c2 == "a" else a2["pts"][::-1]          # part du nœud
            autre1 = a1["a"] if c1 == "b" else a1["b"]
            autre2 = a2["b"] if c2 == "a" else a2["a"]
            aretes[compteur[0]] = {"pts": np.vstack([p1, p2[1:]]), "a": autre1, "b": autre2}
            compteur[0] += 1
    # 4. Bruit : polylignes isolées trop courtes.
    sortie = []
    for ar in aretes.values():
        libre_a, libre_b = not noeuds[ar["a"]]["jonction"], not noeuds[ar["b"]]["jonction"]
        if libre_a and libre_b and _longueur(ar["pts"]) < longueur_min_px:
            continue
        sortie.append({"points": ar["pts"], "libre_debut": libre_a, "libre_fin": libre_b})
    return sortie


# --- Fichiers ----------------------------------------------------------------------------------------
def _lire_json(chemin: Path) -> dict:
    if not chemin.is_file():
        raise ErreurPhoto(f"fichier manquant : {chemin}", code=2)
    return json.loads(chemin.read_text(encoding="utf-8"))


def _lire_photo_couleur(chemin: Path) -> np.ndarray:
    if not chemin.is_file():
        raise ErreurPhoto(f"photo introuvable : {chemin}", code=2)
    img = cv2.imdecode(np.fromfile(str(chemin), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ErreurPhoto(f"photo illisible (format non reconnu) : {chemin}", code=2)
    return img


def _ecrire_json_atomique(chemin: Path, donnees: dict) -> None:
    tmp = chemin.with_name(chemin.name + ".tmp")
    tmp.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, chemin)


# --- Pipeline ----------------------------------------------------------------------------------------
def _redresser_photo(photo: np.ndarray, reperes: dict, infos: dict):
    """Homographie des 16 coins (photo px → mm feuille), erreur de reprojection, image redressée à 4 px/mm."""
    src = np.vstack([reperes[i] for i in range(4)]).astype(np.float64)
    dst = np.vstack([np.asarray(infos["reperes"][str(i)]["coins_mm"], dtype=float) for i in range(4)])
    hom, _ = cv2.findHomography(src, dst, 0)
    if hom is None:
        raise ErreurPhoto("homographie impossible : repères mal détectés (photo trop floue ou trop inclinée)")
    proj = cv2.perspectiveTransform(src.reshape(-1, 1, 2), hom).reshape(-1, 2)
    erreurs = np.linalg.norm(proj - dst, axis=1)
    cote_px = float(np.mean([np.linalg.norm(np.roll(reperes[i], 1, axis=0) - reperes[i], axis=1).mean() for i in range(4)]))
    px_par_mm_photo = cote_px / float(infos["reperes"]["0"].get("cote_mm", fe.REPERE_COTE_MM))
    source, hom_source = photo, hom
    if px_par_mm_photo > PX_PAR_MM_MAX_AVANT_REDRESSEMENT:
        f = PX_PAR_MM_MAX_AVANT_REDRESSEMENT / px_par_mm_photo
        source = cv2.resize(photo, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        sf = np.array([[f, 0, 0.5 * f - 0.5], [0, f, 0.5 * f - 0.5], [0, 0, 1]])
        hom_source = hom @ np.linalg.inv(sf)
    page = infos["page_mm"]
    l, h = int(round(page[0] * PX_PAR_MM)), int(round(page[1] * PX_PAR_MM))
    t = np.array([[PX_PAR_MM, 0, -0.5], [0, PX_PAR_MM, -0.5], [0, 0, 1]])
    redresse = cv2.warpPerspective(source, t @ hom_source, (l, h), flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    return hom, redresse, float(np.sqrt(np.mean(erreurs ** 2))), float(erreurs.max()), px_par_mm_photo


def _masques(infos: dict, feuille_png: Path, forme: tuple[int, int]):
    """(masque du plan imprimé dilaté, imprimé non dilaté, zones exclues) à 4 px/mm."""
    rendu = fe.lire_image(feuille_png)
    if rendu is None:
        raise ErreurPhoto(f"feuille rendue illisible : {feuille_png}", code=2)
    if rendu.ndim == 3:
        rendu = cv2.cvtColor(rendu, cv2.COLOR_BGR2GRAY)
    h, l = forme
    reduit = cv2.resize(rendu, (l, h), interpolation=cv2.INTER_AREA)
    imprime = reduit < SEUIL_IMPRIME
    masque = cv2.dilate(imprime.astype(np.uint8), _noyau(2 * DILATATION_MASQUE_PX + 1)) > 0
    exclu = np.zeros((h, l), bool)
    for rep in infos["reperes"].values():
        (x0, y0), (x1, y1) = rep["coins_mm"][0], rep["coins_mm"][2]
        exclu[max(0, int((y0 - 1) * PX_PAR_MM)):int(math.ceil((y1 + 1) * PX_PAR_MM)),
              max(0, int((x0 - 1) * PX_PAR_MM)):int(math.ceil((x1 + 1) * PX_PAR_MM))] = True
    x0, y0, x1, y1 = infos.get("cadre_identification_mm") or fe.zone_bande_mm(tuple(infos["page_mm"]))
    exclu[max(0, int((y0 - 1) * PX_PAR_MM)):int(math.ceil((y1 + 1) * PX_PAR_MM)),
          max(0, int((x0 - 1) * PX_PAR_MM)):int(math.ceil((x1 + 1) * PX_PAR_MM))] = True
    bord = int(2 * PX_PAR_MM)
    exclu[:bord, :] = exclu[-bord:, :] = True
    exclu[:, :bord] = exclu[:, -bord:] = True
    return masque, imprime, exclu


def _aires_couleurs(norm, hsv, lisible_hors_plan) -> dict[str, float]:
    aires = {}
    for c in COULEURS:
        seg, _ = segmenter(norm, c, hsv)
        seg = cv2.morphologyEx((seg & lisible_hors_plan).astype(np.uint8), cv2.MORPH_OPEN, _noyau(3)) > 0
        aires[c] = float(seg.sum()) / PX_PAR_MM ** 2
    return aires


def _extraire_trait(norm, hsv, couleur, masque, exclu) -> np.ndarray:
    seg, strict = segmenter(norm, couleur, hsv)
    total = ((seg & ~masque) | (strict & masque)) & ~exclu
    total = cv2.morphologyEx(total.astype(np.uint8), cv2.MORPH_OPEN, _noyau(3))
    total = cv2.morphologyEx(total, cv2.MORPH_CLOSE, _noyau(5)) > 0
    total = _boucher_trous(total, TROU_MAX_MM2 * PX_PAR_MM ** 2)
    total &= ~exclu
    # garde les composantes ancrées hors du plan imprimé (≥ 2 mm² hors masque) : ni reflets ni franges
    n, lab, stats, _ = cv2.connectedComponentsWithStats(total.astype(np.uint8), connectivity=8)
    hors = np.bincount(lab[total & ~masque].ravel(), minlength=n)
    garder = np.zeros(n, bool)
    garder[1:] = (stats[1:, cv2.CC_STAT_AREA] >= AIRE_MIN_MM2 * PX_PAR_MM ** 2) & \
        (hors[1:] >= AIRE_MIN_MM2 * PX_PAR_MM ** 2)
    return garder[lab]


def _accrocher(p, rects_eq: dict, rects_murs: dict, mode: str):
    """Accroche une extrémité (m). Renvoie (point, epingle, info) ; info = {"type", "id"} ou None."""
    meilleur = None
    for eid, (eq, rect) in rects_eq.items():
        d = _distance_polygone(p, rect)
        if d <= ACCROCHE_EQUIPEMENT_M:
            cle = (d, float(np.linalg.norm(np.asarray(eq["position"], dtype=float) - p)))
            if meilleur is None or cle < meilleur[0]:
                meilleur = (cle, eid, eq, rect)
    if meilleur:
        _, eid, eq, rect = meilleur
        if mode == "centre":
            cible = np.asarray(eq["position"], dtype=float)
        else:
            cible = p.copy() if meilleur[0][0] == 0 else _plus_proche_contour(p, rect)[0]
        return cible, {"x": float(cible[0]), "y": float(cible[1])}, {"type": "equipement", "id": eid}
    meilleur = None
    for mid, (mur, rect) in rects_murs.items():
        d = _distance_polygone(p, rect)
        if d <= ACCROCHE_MUR_M and (meilleur is None or d < meilleur[0]):
            meilleur = (d, mid, mur, rect)
    if meilleur:
        d, mid, mur, rect = meilleur
        cible = _plus_proche_contour(p, rect)[0]          # face la plus proche, même si le bout est dans le mur
        dx, dy = np.asarray(mur["a"], dtype=float) - np.asarray(mur["de"], dtype=float)
        if abs(dy) < 1e-9:
            epingle = {"y": float(cible[1])}
        elif abs(dx) < 1e-9:
            epingle = {"x": float(cible[0])}
        else:
            epingle = {"x": float(cible[0]), "y": float(cible[1])}
        return cible, epingle, {"type": "mur", "id": mid}
    return p, {}, None


def _prolonger_extremites(points: np.ndarray, trait: np.ndarray, largeur_px: float) -> np.ndarray:
    """Le squelette s'arrête avant le bout du trait. Pour chaque extrémité : on avance dans la direction du
    trait jusqu'à sortir de l'encre (bout du trait), et l'extrémité est placée à une demi-largeur en deçà
    (centre de l'arrondi du marqueur). Sans effet aux jonctions (le bout est alors à moins d'une demi-largeur)."""
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2 or largeur_px <= 0:
        return pts
    h, w = trait.shape

    def bout(extremite, interieur):
        d = extremite - interieur
        n = np.linalg.norm(d)
        if n < 1e-9:
            return None
        d /= n
        pas, parcouru = 0.5, 0.0
        while parcouru <= 2 * largeur_px:
            q = extremite + d * (parcouru + pas)
            x, y = int(round(q[0])), int(round(q[1]))
            if not (0 <= x < w and 0 <= y < h) or not trait[y, x]:
                break
            parcouru += pas
        avance = parcouru - largeur_px / 2
        if avance <= 0.5 or parcouru > 2 * largeur_px:
            return None
        return extremite + d * avance

    def point_interieur(chemin):
        cumul = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(chemin, axis=0), axis=1))])
        k = int(np.searchsorted(cumul, min(cumul[-1], 2 * largeur_px)))
        return chemin[min(k, len(chemin) - 1)]

    debut = bout(pts[0], point_interieur(pts))
    fin = bout(pts[-1], point_interieur(pts[::-1]))
    morceaux = ([debut[None, :]] if debut is not None else []) + [pts] + ([fin[None, :]] if fin is not None else [])
    return np.vstack(morceaux)


def _affiner_sommets(brut: np.ndarray, simp: np.ndarray, largeur_px: float) -> np.ndarray:
    """Recale les sommets de la polyligne simplifiée : droite ajustée (moindres carrés) sur les pixels du
    squelette de chaque segment, hors abords des coudes (le squelette y coupe l'angle) ; sommets intérieurs =
    intersection des droites voisines, extrémités = projection sur leur droite."""
    brut = np.asarray(brut, dtype=float)
    simp = np.asarray(simp, dtype=float)
    if len(simp) < 2 or len(brut) < 3:
        return simp
    idx, depart = [], 0
    for v in simp:
        k = depart + int(np.argmin(np.linalg.norm(brut[depart:] - v, axis=1)))
        idx.append(k)
        depart = k
    droites = []
    for i0, i1 in zip(idx[:-1], idx[1:]):
        morceau = brut[i0:i1 + 1]
        cumul = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(morceau, axis=0), axis=1))])
        marge = min(largeur_px, cumul[-1] * 0.25)
        garde = morceau[(cumul >= marge) & (cumul <= cumul[-1] - marge)]
        if len(garde) < 4:
            droites.append(None)
            continue
        c = garde.mean(axis=0)
        _, _, vt = np.linalg.svd(garde - c)
        droites.append((c, vt[0]))

    def projeter(p, droite):
        if droite is None:
            return p
        c, d = droite
        return c + d * float((p - c) @ d)

    sortie = [projeter(simp[0], droites[0])]
    for k in range(1, len(simp) - 1):
        d1, d2 = droites[k - 1], droites[k]
        nouveau = simp[k]
        if d1 is not None and d2 is not None:
            (c1, u1), (c2, u2) = d1, d2
            det = u1[0] * (-u2[1]) - u1[1] * (-u2[0])
            if abs(det) > math.sin(math.radians(10)):
                t = ((c2 - c1)[0] * (-u2[1]) - (c2 - c1)[1] * (-u2[0])) / det
                candidat = c1 + t * u1
                if np.linalg.norm(candidat - simp[k]) <= 2 * max(largeur_px, 1.0):
                    nouveau = candidat
        sortie.append(nouveau)
    sortie.append(projeter(simp[-1], droites[-1]))
    return np.array(sortie)


def _simplifier(points: np.ndarray, epsilon: float) -> np.ndarray:
    """Douglas-Peucker (cv2.approxPolyDP) ; une polyligne fermée est coupée en deux au point le plus éloigné."""
    pts = np.asarray(points, dtype=np.float64)

    def dp(p):
        return cv2.approxPolyDP(p.astype(np.float32).reshape(-1, 1, 2), epsilon, False).reshape(-1, 2).astype(float)

    if len(pts) > 3 and np.linalg.norm(pts[0] - pts[-1]) < 1.5:
        k = int(np.argmax(np.linalg.norm(pts - pts[0], axis=1)))
        return np.vstack([dp(pts[:k + 1]), dp(pts[k:])[1:]])
    return dp(pts)


def _rang_extremite(eid, rects_eq) -> int:
    """Ordre de/a : évaporateur ou split d'abord, puis autre équipement, extrémité libre, groupe/centrale/tableau."""
    if eid is None:
        return 2
    t = rects_eq[eid][0].get("type")
    return 0 if t in TYPES_DEPART else 3 if t in TYPES_ARRIVEE else 1


def _decouper_aux_equipements(pts_m: np.ndarray, rects_eq: dict) -> list[np.ndarray]:
    """Coupe la polyligne à chaque sommet intérieur situé sur un équipement (un tronçon = équipement à équipement)."""
    morceaux, debut = [], 0
    for i in range(1, len(pts_m) - 1):
        if any(_distance_polygone(pts_m[i], rect) <= MARGE_DECOUPE_EQUIPEMENT_M for _, rect in rects_eq.values()):
            morceaux.append(pts_m[debut:i + 1])
            debut = i
    morceaux.append(pts_m[debut:])
    return [m for m in morceaux if len(m) >= 2]


def lire_photo(dossier_plan, photo, reseau: str, marqueur: str = "auto", fusionner: bool = False,
               longueur_attendue_m: float | None = None, confirmer: bool = False,
               accrochage: str = "centre") -> dict:
    """Lit la photo d'une feuille tracée et écrit le calque du réseau. Renvoie le contenu du calque
    (+ "fichiers", "fusion"). Lève ErreurPhoto (code 1 : repères manquants ou aucun trait ; 2 : fichier manquant)."""
    dossier_plan = Path(dossier_plan)
    photo = Path(photo)
    if marqueur not in COULEURS + ("auto",):
        raise ErreurPhoto(f"marqueur inconnu : {marqueur!r} (rouge, bleu, vert, noir ou auto)")
    if accrochage not in ("centre", "bord"):
        raise ErreurPhoto(f"accrochage inconnu : {accrochage!r} (centre ou bord)")
    chemins = fe.chemins_feuille(dossier_plan, reseau)
    plan = _lire_json(dossier_plan / "plan.json")
    infos = _lire_json(chemins["json"])
    if not chemins["png"].is_file():
        raise ErreurPhoto(f"fichier manquant : {chemins['png']}", code=2)
    image = _lire_photo_couleur(photo)
    avert: list[str] = []

    # 1. Repères et homographie
    reperes = fe.detecter_reperes(image)
    manquants = [i for i in range(4) if i not in reperes]
    if manquants:
        noms = ", ".join(f"{i} ({fe.POSITIONS_REPERES[i]})" for i in manquants)
        raise ErreurPhoto(f"repère(s) non détecté(s) : {noms}. Reprendre la photo de dessus, les 4 repères "
                          "entièrement visibles, nets, sans reflet ni ombre portée.")
    hom, redresse, err_rms, err_max, ppm_photo = _redresser_photo(image, reperes, infos)
    if err_max > REPROJECTION_ALERTE_MM:
        avert.append(f"erreur de reprojection élevée ({_f(err_max)} mm au pire) : feuille pas à plat ou photo floue, "
                     "longueurs moins sûres")

    # 2. Plan imprimé, couleur du marqueur, trait
    masque, imprime, exclu = _masques(infos, chemins["png"], redresse.shape[:2])
    norm = _normaliser(redresse, PX_PAR_MM)
    hsv = _hsv(norm)
    lisible_hors_plan = ~masque & ~exclu
    aires = _aires_couleurs(norm, hsv, lisible_hors_plan)
    presentes = [c for c in ("rouge", "bleu", "vert") if aires[c] >= AIRE_MIN_COULEUR_MM2]
    if marqueur == "auto":
        if presentes:
            couleur = max(presentes, key=lambda c: aires[c])
        elif aires["noir"] >= AIRE_MIN_COULEUR_MM2:
            couleur = "noir"
        else:
            raise ErreurPhoto("aucun trait de marqueur trouvé sur la photo (ni rouge, ni bleu, ni vert, ni noir). "
                              "Vérifier que c'est la bonne feuille et que le tracé est bien visible.")
        autres = [c for c in presentes if c != couleur]
        if autres:
            avert.append("plusieurs couleurs sur la feuille : " + ", ".join(f"{c} ({aires[c]:.0f} mm²)" for c in [couleur] + autres)
                         + f" ; seule la couleur {couleur} est lue (une feuille par réseau)")
    else:
        couleur = marqueur
    trait = _extraire_trait(norm, hsv, couleur, masque, exclu)
    if trait.sum() < AIRE_MIN_COULEUR_MM2 * PX_PAR_MM ** 2:
        autres = [c for c in presentes if c != couleur]
        complement = (" Couleur(s) présente(s) sur la photo : " + ", ".join(autres) + " : relancer avec --marqueur "
                      + autres[0] + " si c'est bien ce réseau.") if autres else ""
        raise ErreurPhoto(f"aucun trait {couleur} trouvé sur la photo du réseau « {reseau} »." + complement
                          + " Une photo d'un autre réseau ? Vérifier la feuille et la couleur du marqueur.")

    concordance = None
    attendu = imprime & ~exclu
    if attendu.sum() > 0:
        visible = norm.mean(axis=2) < 0.85
        concordance = float((visible & attendu).sum() / attendu.sum())
        if concordance < 0.35:
            avert.append(f"le plan imprimé ne se retrouve qu'à {concordance:.0%} sur la photo : est-ce bien la feuille "
                         f"de ce dossier ? (photo très claire ou feuille d'un autre plan)")

    # 3. Squelette et polylignes (px de l'image redressée)
    dist = cv2.distanceTransform(trait.astype(np.uint8), cv2.DIST_L2, 5)
    sq = squelette_zhang_suen(trait)
    largeur_mm = float(2 * np.median(dist[sq > 0]) / PX_PAR_MM) if sq.any() else 0.0
    S = float(infos["S"])
    base = {"S": S, "origine_mm": infos["origine_mm"]}
    rects_eq = {eq["id"]: (eq, fe.rectangle_equipement(eq)) for eq in plan.get("equipements", [])
                if eq.get("id") and eq.get("position") is not None}
    rects_murs = {m.get("id", f"mur{i}"): (m, fe.rectangle_mur(m)) for i, m in enumerate(plan.get("murs", []))
                  if m.get("de") is not None and m.get("a") is not None}

    def bloquant(x_px, y_px):
        p_m = fe.mm_vers_m(fe.px_vers_mm([x_px, y_px], PX_PAR_MM), base)
        return any(_distance_polygone(p_m, rect) <= MARGE_DECOUPE_EQUIPEMENT_M for _, rect in rects_eq.values())

    brutes = vectoriser(sq, ergot_px=max(ERGOT_MIN_MM, 1.5 * largeur_mm) * PX_PAR_MM,
                        longueur_min_px=LONGUEUR_MIN_MM * PX_PAR_MM,
                        contraction_px=max(2.5, largeur_mm) * PX_PAR_MM, bloquant=bloquant)

    # 4. Simplification, mm → m, découpe, accrochage, redressement
    polylignes, questions = [], []
    for br in brutes:
        brut = _prolonger_extremites(br["points"], trait, largeur_mm * PX_PAR_MM)
        simp = _affiner_sommets(brut, _simplifier(brut, EPSILON_SIMPLIFICATION_MM * PX_PAR_MM), largeur_mm * PX_PAR_MM)
        if len(simp) < 2:
            continue
        pts_m = fe.mm_vers_m(fe.px_vers_mm(simp, PX_PAR_MM), base)
        for morceau in _decouper_aux_equipements(pts_m, rects_eq):
            if _longueur(morceau) * 1000.0 / S < LONGUEUR_MIN_MM:
                continue
            debut, ep_d, acc_d = _accrocher(morceau[0], rects_eq, rects_murs, accrochage)
            fin, ep_f, acc_f = _accrocher(morceau[-1], rects_eq, rects_murs, accrochage)
            morceau = morceau.copy()
            morceau[0], morceau[-1] = debut, fin
            epingles = {0: ep_d, len(morceau) - 1: ep_f}
            pts, av = redresser_polyligne(morceau, epingles)
            avert += av
            if len(pts) < 2 or _longueur(pts) < 1e-6:
                continue
            de = acc_d["id"] if acc_d and acc_d["type"] == "equipement" else None
            a = acc_f["id"] if acc_f and acc_f["type"] == "equipement" else None
            mur_de = acc_d["id"] if acc_d and acc_d["type"] == "mur" else None
            mur_a = acc_f["id"] if acc_f and acc_f["type"] == "mur" else None
            if _rang_extremite(a, rects_eq) < _rang_extremite(de, rects_eq):
                pts = pts[::-1]
                de, a, mur_de, mur_a = a, de, mur_a, mur_de
            polylignes.append({"points": pts, "de": de, "a": a, "mur_de": mur_de, "mur_a": mur_a})
    if not polylignes:
        raise ErreurPhoto(f"aucun trait exploitable trouvé (couleur {couleur}) : tracé trop court ou trop pâle ?")
    polylignes.sort(key=lambda p: -_longueur(p["points"]))
    sortie_polys = []
    c_reproj = min(1.0, max(0.3, 1.0 - err_max / 2.0))
    for k, pl in enumerate(polylignes, start=1):
        long_m = _longueur(pl["points"])
        nb_acc = sum(x is not None for x in (pl["de"] or pl["mur_de"], pl["a"] or pl["mur_a"]))
        c_len = min(1.0, max(0.3, long_m * 1000.0 / S / 20.0))
        confiance = round(c_reproj * (0.6 + 0.2 * nb_acc) * c_len, 2)
        for cle, idx in (("de", 0), ("a", -1)):
            if pl[cle] is None:
                x, y = pl["points"][idx]
                questions.append(f"{reseau}-photo-{k} : extrémité libre à ({_f(x)} ; {_f(y)}) : relier à quel équipement ?")
        sortie_polys.append({
            "id": f"{reseau}-photo-{k}",
            "points_m": [[round(float(x), 3), round(float(y), 3)] for x, y in pl["points"]],
            "longueur_plan_m": round(long_m, 3),
            "de": pl["de"], "a": pl["a"], "mur_de": pl["mur_de"], "mur_a": pl["mur_a"],
            "confiance": confiance,
        })
    total = round(sum(p["longueur_plan_m"] for p in sortie_polys), 3)

    controle_longueur = None
    if longueur_attendue_m is not None:
        ecart = total - float(longueur_attendue_m)
        seuil = max(ECART_RELATIF_MAX * float(longueur_attendue_m), ECART_ABSOLU_MAX_M)
        controle_longueur = {"attendue_m": float(longueur_attendue_m), "mesuree_m": total, "ecart_m": round(ecart, 3),
                             "seuil_m": round(seuil, 3), "ok": abs(ecart) <= seuil}
        if not controle_longueur["ok"]:
            avert.append(f"longueur tracée {_f(total)} m pour {_f(float(longueur_attendue_m))} m attendus : écart "
                         f"{_f(ecart)} m > seuil {_f(seuil)} m (max 5 % ; 0,30 m)")

    type_ligne = infos.get("type_ligne")
    try:
        photo_rel = os.path.relpath(photo.resolve(), dossier_plan.resolve())
        photo_txt = photo_rel if not photo_rel.startswith("..") else str(photo)
    except ValueError:
        photo_txt = str(photo)
    calque = {
        "reseau": reseau, "type": type_ligne, "source": "photo", "photo": photo_txt.replace("\\", "/"), "S": infos["S"],
        "marqueur": couleur, "date": dt.date.today().isoformat(),
        "polylignes": sortie_polys,
        "longueur_totale_plan_m": total,
        "erreur_reprojection_mm": round(err_rms, 3), "erreur_reprojection_max_mm": round(err_max, 3),
        "photo_px_par_mm": round(ppm_photo, 2), "largeur_trait_mm": round(largeur_mm, 2),
        "concordance_plan_imprime": None if concordance is None else round(concordance, 3),
        "aires_couleurs_mm2": {c: round(v, 1) for c, v in aires.items()},
        "reperes_photo_px": {str(i): np.round(reperes[i], 2).tolist() for i in range(4)},
        "controle_longueur": controle_longueur,
        "questions": questions,
        "avertissements": avert,
    }
    dossier_calques = dossier_plan / "calques"
    dossier_calques.mkdir(parents=True, exist_ok=True)
    chemin_json = dossier_calques / f"{reseau}.json"
    chemin_png = dossier_calques / f"{reseau}-controle.png"
    fe.ecrire_png(chemin_png, _image_controle(redresse, trait, sortie_polys, rects_eq, infos, hom, reperes, base, calque))

    fusion = {"faite": False}
    if fusionner:
        if controle_longueur is not None and not controle_longueur["ok"] and not confirmer:
            fusion = {"faite": False, "motif": "écart de longueur au-delà du seuil : relancer avec --confirmer après vérification"}
            avert.append("FUSION NON FAITE : " + fusion["motif"])
        else:
            fusion = fusionner_dans_plan(dossier_plan, calque)
            avert += fusion["avertissements"]
    _ecrire_json_atomique(chemin_json, calque)
    resultat = dict(calque)
    resultat["fichiers"] = {"calque": str(chemin_json), "controle": str(chemin_png)}
    resultat["fusion"] = fusion
    return resultat


def fusionner_dans_plan(dossier_plan, calque: dict) -> dict:
    """Ajoute les polylignes du calque dans plan["lignes"] après sauvegarde de plan.json dans versions/.
    Les lignes d'une précédente photo du même réseau (source "photo", même calque) sont remplacées."""
    dossier_plan = Path(dossier_plan)
    chemin_plan = dossier_plan / "plan.json"
    plan = _lire_json(chemin_plan)
    versions = dossier_plan / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    horodatage = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    sauvegarde = versions / f"plan.json.avant-fusion-{horodatage}"
    n = 2
    while sauvegarde.exists():
        sauvegarde = versions / f"plan.json.avant-fusion-{horodatage}-{n}"
        n += 1
    shutil.copy2(chemin_plan, sauvegarde)
    reseau = calque["reseau"]
    avert = []
    lignes = plan.setdefault("lignes", [])
    anciennes = [l for l in lignes if l.get("source") == "photo" and l.get("calque") == reseau]
    if anciennes:
        avert.append(f"{len(anciennes)} ligne(s) d'une photo précédente du réseau « {reseau} » remplacée(s)")
    lignes[:] = [l for l in lignes if not (l.get("source") == "photo" and l.get("calque") == reseau)]
    type_ligne = calque.get("type")
    if not type_ligne:
        type_ligne = reseau
        avert.append(f"type de ligne non précisé sur la feuille : type = « {reseau} » (à corriger si besoin)")
    libres = {c.get("cle") for c in plan.get("calques_libres", [])}
    if reseau not in CALQUES_STANDARD and reseau not in libres:
        avert.append(f"le calque « {reseau} » n'est ni un calque standard ni déclaré dans calques_libres : à déclarer")
    ids = {l.get("id") for l in lignes}
    ajoutees = []
    for pl in calque["polylignes"]:
        ident = pl["id"]
        k = 2
        while ident in ids:
            ident = f"{pl['id']}-{k}"
            k += 1
        ids.add(ident)
        lignes.append({"id": ident, "type": type_ligne, "calque": reseau, "de": pl["de"], "a": pl["a"],
                       "points": pl["points_m"], "source": "photo", "diametre": "à définir"})
        ajoutees.append(ident)
    avert += calque.get("questions", [])
    _ecrire_json_atomique(chemin_plan, plan)
    return {"faite": True, "sauvegarde": str(sauvegarde), "lignes_ajoutees": ajoutees, "avertissements": avert}


# --- Image de contrôle -----------------------------------------------------------------------------------
def _image_controle(redresse, trait, polys, rects_eq, infos, hom, reperes, base, calque) -> np.ndarray:
    gris = cv2.cvtColor(cv2.cvtColor(redresse, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    img = cv2.addWeighted(redresse, 0.35, gris, 0.65, 0)
    teinte = np.zeros_like(img)
    teinte[:] = (0, 150, 255)
    img[trait] = cv2.addWeighted(img, 0.55, teinte, 0.45, 0)[trait]

    def px(p_m):
        return tuple(int(round(v)) for v in fe.mm_vers_px(fe.m_vers_mm(p_m, base), PX_PAR_MM))

    accroches = {pl[c] for pl in polys for c in ("de", "a") if pl[c]}
    for eid, (eq, rect) in rects_eq.items():
        pts = np.array([px(p) for p in rect], np.int32).reshape(-1, 1, 2)
        couleur = (0, 170, 0) if eid in accroches else (200, 160, 0)
        cv2.polylines(img, [pts], True, couleur, 3 if eid in accroches else 1, cv2.LINE_AA)
    for pl in polys:
        pts = np.array([px(p) for p in pl["points_m"]], np.int32).reshape(-1, 1, 2)
        cv2.polylines(img, [pts], False, (255, 0, 200), 2, cv2.LINE_AA)
        for p in pl["points_m"][1:-1]:
            cv2.circle(img, px(p), 3, (255, 0, 200), -1, cv2.LINE_AA)
        for cle, p in (("de", pl["points_m"][0]), ("a", pl["points_m"][-1])):
            couleur = (0, 170, 0) if pl[cle] else (0, 140, 255)
            cv2.circle(img, px(p), 7, couleur, 2, cv2.LINE_AA)
    for i in range(4):
        attendus = np.asarray(infos["reperes"][str(i)]["coins_mm"], dtype=float)
        trouves = cv2.perspectiveTransform(np.asarray(reperes[i], dtype=float).reshape(-1, 1, 2), hom).reshape(-1, 2)
        for a, t in zip(attendus, trouves):
            pa = tuple(int(round(v)) for v in fe.mm_vers_px(a, PX_PAR_MM))
            pt = tuple(int(round(v)) for v in fe.mm_vers_px(t, PX_PAR_MM))
            cv2.drawMarker(img, pa, (0, 170, 0), cv2.MARKER_CROSS, 12, 1)
            cv2.circle(img, pt, 3, (0, 0, 255), -1)
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    dessin = ImageDraw.Draw(pil)
    police = fe._police(16)
    texte = (f"Réseau {calque['reseau']} · marqueur {calque['marqueur']} · {len(polys)} tronçon(s) · "
             f"{_f(calque['longueur_totale_plan_m'])} m en plan · reprojection {_f(calque['erreur_reprojection_mm'])} mm")
    x0 = int(30 * PX_PAR_MM)
    dessin.rectangle([x0 - 4, 4, x0 + dessin.textlength(texte, font=police) + 4, 26], fill=(255, 255, 255))
    dessin.text((x0, 6), texte, fill=(0, 0, 0), font=police)
    for pl in polys:
        x, y = px(pl["points_m"][len(pl["points_m"]) // 2])
        dessin.text((x + 6, y + 4), pl["id"].rsplit("-", 1)[-1], fill=(200, 0, 160), font=police)
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Photo d'une feuille tracée au marqueur → calque du réseau (Lot 6).")
    ap.add_argument("dossier_plan")
    ap.add_argument("photo")
    ap.add_argument("--reseau", required=True)
    ap.add_argument("--marqueur", default="auto", choices=COULEURS + ("auto",))
    ap.add_argument("--fusionner", action="store_true", help="ajoute les lignes dans plan.json (sauvegarde préalable)")
    ap.add_argument("--confirmer", action="store_true", help="fusionne même si l'écart de longueur dépasse le seuil")
    ap.add_argument("--longueur-attendue", type=float, default=None, help="longueur de référence du réseau (m)")
    ap.add_argument("--accrochage", default="centre", choices=("centre", "bord"))
    args = ap.parse_args(argv)
    try:
        r = lire_photo(args.dossier_plan, args.photo, args.reseau, marqueur=args.marqueur, fusionner=args.fusionner,
                       longueur_attendue_m=args.longueur_attendue, confirmer=args.confirmer, accrochage=args.accrochage)
    except ErreurPhoto as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return e.code
    print(f"Réseau « {r['reseau']} » lu sur la photo (marqueur {r['marqueur']}) : {len(r['polylignes'])} tronçon(s), "
          f"{_f(r['longueur_totale_plan_m'])} m en plan ; reprojection {_f(r['erreur_reprojection_mm'], 3)} mm.")
    for p in r["polylignes"]:
        print(f"  {p['id']} : {_f(p['longueur_plan_m'])} m, de {p['de'] or '?'} à {p['a'] or '?'}, confiance {_f(p['confiance'])}")
    print(f"  Calque : {r['fichiers']['calque']}\n  Contrôle : {r['fichiers']['controle']}")
    if r["fusion"].get("faite"):
        print(f"  Fusionné dans plan.json ({', '.join(r['fusion']['lignes_ajoutees'])}) ; sauvegarde : {r['fusion']['sauvegarde']}")
    for q in r["questions"]:
        print(f"  QUESTION : {q}")
    for a in r["avertissements"]:
        if a not in r["questions"]:
            print(f"  AVERTISSEMENT : {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
