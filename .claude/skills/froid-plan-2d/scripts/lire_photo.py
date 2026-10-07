"""Photo d'une feuille tracée au marqueur ou au stylo → calque du réseau en mètres (Lot 6 du skill froid-plan-2d).

Étapes : repères ArUco (4 coins de chacun des 4 repères = 16 points) → homographie photo → mm de la feuille
(+ erreur de reprojection) → redressement à la résolution utile (4 px/mm ; photo plus faible : au plus 1,5 × sa
résolution, avertissement « photo de faible résolution ») → plan imprimé (feuille rendue, recalée sur la photo par
ECC, dilatée de 0,75 mm) → image normalisée par le fond de papier local, canaux équilibrés sur le gris neutre du
plan imprimé → encres : couleur = chroma Lab relative au fond + teinte HSV (rouge 2 plages, bleu 95-135, vert
35-90), par hystérésis (graines franches, croissance des pixels pâles d'un stylo bille, halos JPEG retirés) ;
noir = sombre et peu chromatique hors du plan imprimé, nettement plus sombre que le gris du plan dessus →
croisements entre couleurs pontés → annotations manuscrites loin du bâtiment écartées (`annotations_ignorees`) →
équipements dessinés (`formes_fermees` : contours fermés, petits rectangles pleins) → bord du trait à mi-hauteur
pour un marqueur, sans ouverture morphologique (un trait de stylo fait 1-2 px) → squelette Zhang-Suen (numpy) →
suivi du squelette en polylignes (jonctions, extrémités, croisements traversés tout droit) → simplification
(1,5 mm) → conversion mm → m → découpe aux équipements, accrochage (équipements 0,15 m, formes fermées, murs
0,10 m) et redressement des angles (≤ 7° de 0/90°) → flèches et écritures écartées (tracé hors du bâtiment relié à
rien, extrémité libre près d'une annotation, tracé courbe venant de l'extérieur) → `calques/<reseau>.json` +
`calques/<reseau>-controle.png` ; `--fusionner` ajoute les lignes de la couleur principale dans `plan.json`
(ancienne version sauvegardée dans `versions/`).

`--marqueur auto` lit toutes les couleurs d'encre (résultat par couleur dans `par_couleur`, couleur principale =
celle qui porte le plus long réseau) ; une couleur imposée ne lit que ses traits, mais les formes fermées de toutes
les couleurs servent à l'accrochage (identifiants F1, F2… identiques d'un appel à l'autre).

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
PX_PAR_MM = 4                          # résolution de travail (photo redressée)
SURECHANTILLONNAGE_MAX = 1.5           # photo plus faible que 4 / 1,5 px/mm : travail à 1,5 × sa résolution
PX_PAR_MM_MIN = 2.0
RESOLUTION_FAIBLE_PX_MM = 4.0          # en dessous (sur la zone du plan) : avertissement « envoyer l'original »
DILATATION_MASQUE_MM = 0.75            # masque du plan imprimé dilaté de 0,75 mm (3 px à 4 px/mm)
SEUIL_IMPRIME = 245                    # pixel de la feuille rendue < 245 = imprimé
PX_PAR_MM_MAX_AVANT_REDRESSEMENT = 6.0 # photo plus fine : réduite (INTER_AREA) avant le redressement
RECALAGE_MAX_MM = 2.0                  # recalage ECC du plan imprimé refusé s'il le déplace de plus de 2 mm
GRIS_PLAN = 158 / 255                  # gris du plan imprimé (#9E9E9E), si la photo ne permet pas de le mesurer
# Encres de couleur, sur l'image normalisée (papier = 1) : chroma Lab C, obscurité D = 1 − L, relatif = C / (100 D + 4)
CHROMA_FORT, CHROMA_FAIBLE = 8.0, 5.0        # bruit du papier : C ≤ 3 (99,9 %) ; franges de l'écriture noire ≤ 6,5
SOMBRE_FORT, SOMBRE_FAIBLE = 0.12, 0.05
RELATIF_FORT, RELATIF_FAIBLE = 0.15, 0.08
PART_SOMBRE_MIN = 0.35                       # composante de couleur dont < 35 % des pixels sont sombres : halo JPEG
PLAGES_TEINTE = {"rouge": [(0, 10), (160, 179)], "vert": [(35, 90)], "bleu": [(95, 135)]}   # teinte OpenCV 0-179 (graines)
PLAGES_TEINTE_LARGES = {"rouge": [(0, 14), (152, 179)], "vert": [(32, 92)], "bleu": [(93, 142)]}  # croissance
# Noir : sombre, peu chromatique ; hors du plan imprimé, ou nettement plus sombre que le gris du plan dessus
NOIR_FORT, NOIR_FAIBLE = 0.35, 0.18          # obscurité hors du plan imprimé (graines, croissance)
NOIR_SUR_IMPRIME = 0.55                      # sur le plan imprimé : L < 0,55 × gris du plan mesuré sur la photo
NOIR_RELATIF_MAX = 0.10
NOIR_ANCRAGE_MM, NOIR_ANCRAGE_MM2 = 1.5, 1.0 # composante noire gardée si ≥ 1 mm² à plus de 1,5 mm du plan imprimé
NOIR_PRES_COULEUR_PX = 2                     # bord d'un trait de couleur : pas du noir
PONT_CROISEMENT_MM = 2.5                     # trait coupé par une autre encre sur ≤ 2,5 mm : ponté…
PONT_SOMBRE_MM = 2.0                         # … ou par un tracé sombre (plan imprimé) sur ≤ 2 mm
TRAIT_MARQUEUR_MM = 1.25                     # 80 % du trait ≥ 1,25 mm à mi-hauteur : marqueur, sinon stylo
AIRE_MIN_MM2 = 2.0                     # composantes plus petites supprimées (trait fin : 3 mm × largeur, ≥ 0,6 mm²)
AIRE_MIN_COULEUR_MM2 = 10.0            # surface minimale pour considérer qu'une couleur est présente…
LONGUEUR_MIN_COULEUR_MM = 15.0         # … ou 15 mm de trait fin
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
# Formes fermées (équipements dessinés) : trou clair entouré de tracé, bordé à ≥ 50 % par une même encre
SOMBRE_CONTOUR = 0.15                  # pixel « tracé » (encre ou plan imprimé) pour chercher les contours fermés
FORME_PART_MIN = 0.5
FORME_AUTRE_ENCRE_MAX = 0.3            # bord à ≥ 30 % d'une autre encre : fente entre deux traits, pas une forme
FORME_RECTANGULARITE_MIN = 0.7
FORME_ELANCEMENT_MAX = 10.0
FORME_COTE_MIN_MM, FORME_GRAND_COTE_MIN_MM = 1.2, 3.0                # dans le bâtiment (sur le papier)
FORME_DEHORS_COTE_MIN_MM, FORME_DEHORS_GRAND_COTE_MIN_MM = 3.0, 5.0  # dehors : plus grand que l'écriture
FORME_COTE_MAX_MM, FORME_COTE_MAX_M = 40.0, 4.0
FORME_PLEINE_EPAISSEUR_MM = 1.5        # rectangle plein : ≥ 1,5 mm d'épaisseur (un trait de stylo en fait 0,5)…
FORME_PLEINE_RECTANGULARITE_MIN = 0.75 # … rectangulaire à ≥ 75 %…
FORME_PLEINE_ELANCEMENT_MAX = 6.0      # … et pas plus de 6 fois plus long que large
FORME_PLEINE_CONFIANCE = 0.8           # confiance réduite : contour non vu
FORME_RETRAIT_MM = 1.0                 # contour d'une forme retiré du trait de sa couleur avec 1 mm de marge
FORME_BRANCHE_MM = 3.0                 # ≥ 2 traits de sa couleur qui en partent sur ≥ 3 mm : boucle du réseau
ACCROCHE_FORME_MM = 2.5                # accrochage à une forme : max(0,15 m, 2,5 mm sur le papier)
# Annotations manuscrites
MARGE_BATIMENT_M = 2.0                 # composante dont la boîte ne touche pas le bâtiment agrandi de 2 m : ignorée…
RELIEE_MM = 1.0                        # … sauf à moins de 1 mm d'un trait gardé
FLECHE_MM = 5.0                        # extrémité libre hors du bâtiment à ≤ 5 mm d'une annotation : flèche
ALIGNE_MIN = 0.35                      # tracé dont < 35 % de la longueur suit les axes (à 7° près) : courbe, flèche
TOLERANCE_BATIMENT_M = 0.05
TYPES_DEPART = {"evaporateur", "split"}
TYPES_ARRIVEE = {"groupe", "centrale", "condenseur", "moteur", "tableau"}
CALQUES_STANDARD = {"plan_de_base", "cotes", "froid_equipements", "froid_cuivres", "electricite",
                    "clim_equipements", "clim_cuivres", "croisements", "cartouche"}
COULEURS = ("rouge", "bleu", "vert", "noir")
CHROMATIQUES = ("rouge", "bleu", "vert")
FEMININ = {"rouge": "rouge", "bleu": "bleue", "vert": "verte", "noir": "noire"}
TEINTE_CONTROLE = {"rouge": (60, 60, 255), "bleu": (255, 140, 30), "vert": (40, 190, 40), "noir": (90, 90, 90)}
TRAIT_CONTROLE = {"rouge": (0, 0, 190), "bleu": (180, 40, 0), "vert": (0, 120, 0), "noir": (20, 20, 20)}


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


def _distance_boite(p, boite) -> float:
    x0, y0, x1, y1 = boite
    dx = max(x0 - p[0], 0.0, p[0] - x1)
    dy = max(y0 - p[1], 0.0, p[1] - y1)
    return math.hypot(dx, dy)


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


def _cartes(norm: np.ndarray) -> dict:
    """Cartes de l'image normalisée : L (clarté 0-1), D = 1 − L, C (chroma Lab), H (teinte HSV OpenCV 0-179), relatif."""
    lab = cv2.cvtColor(norm.astype(np.float32), cv2.COLOR_BGR2Lab)
    clarte = lab[:, :, 0] / 100.0
    sombre = np.clip(1.0 - clarte, 0.0, 1.0)
    chroma = np.hypot(lab[:, :, 1], lab[:, :, 2])
    teinte = cv2.cvtColor((norm * 255 + 0.5).astype(np.uint8), cv2.COLOR_BGR2HSV)[:, :, 0]
    return {"L": clarte, "D": sombre, "C": chroma, "H": teinte, "rel": chroma / (100.0 * sombre + 4.0), "norm": norm}


def _equilibrer_canaux(norm: np.ndarray, imprime: np.ndarray, exclu: np.ndarray, cartes: dict,
                       ppm: float = PX_PAR_MM):
    """Le plan imprimé est gris neutre : son obscurité doit être la même dans les trois canaux. Un canal saturé sur
    le papier (photo surexposée) ou une dominante non linéaire teinte le gris ; on corrige l'obscurité de chaque
    canal (1 − valeur) d'un facteur mesuré sur le plan imprimé : global (pixels gris du plan, chroma < 10), puis
    local sur l'image ainsi corrigée (fenêtre de 25 mm, pixels de chroma < 5 seulement : un trait de couleur posé sur
    un mur n'est pas pris pour du gris à neutraliser) ; facteurs bornés à 0,8-1,25. Renvoie (image normalisée
    corrigée, facteurs globaux B, V, R)."""
    m = imprime & ~exclu & (cartes["C"] < 10.0) & (cartes["D"] >= SOMBRE_CONTOUR)
    if m.sum() < 200:
        return norm, (1.0, 1.0, 1.0)
    sombre = (1.0 - norm).astype(np.float32)
    d = np.median(sombre[m], axis=0)
    if np.any(d <= 0.02):
        return norm, (1.0, 1.0, 1.0)
    globaux = d.mean() / d
    if np.any(globaux < 0.8) or np.any(globaux > 1.25):
        return norm, (1.0, 1.0, 1.0)
    sombre = sombre * globaux.astype(np.float32)[None, None, :]
    lab = cv2.cvtColor(np.clip(1.0 - sombre, 0.0, 1.0).astype(np.float32), cv2.COLOR_BGR2Lab)
    m &= np.hypot(lab[:, :, 1], lab[:, :, 2]) < 5.0
    k = int(round(25 * ppm)) | 1
    mf = m.astype(np.float32)
    n = cv2.boxFilter(mf, -1, (k, k), normalize=False)
    moyens = np.dstack([cv2.boxFilter(sombre[:, :, c] * mf, -1, (k, k), normalize=False) for c in range(3)])
    assez = n >= 0.02 * k * k
    moyens = moyens / np.maximum(n, 1.0)[:, :, None]
    locaux = np.where(assez[:, :, None], moyens.mean(axis=2, keepdims=True) / np.maximum(moyens, 1e-3), 1.0)
    locaux = np.clip(locaux, 0.8, 1.25)
    locaux = cv2.GaussianBlur(locaux.astype(np.float32), (0, 0), 5 * ppm)
    corrige = 1.0 - sombre * locaux
    return np.clip(corrige, 0.0, 1.0).astype(np.float32), tuple(round(float(f), 3) for f in globaux)


def _dans_plages(teinte: np.ndarray, plages) -> np.ndarray:
    m = np.zeros(teinte.shape, bool)
    for lo, hi in plages:
        m |= (teinte >= lo) & (teinte <= hi)
    return m


def _hysteresis(faible: np.ndarray, fort: np.ndarray) -> np.ndarray:
    """Composantes 8-connexes de `faible` qui contiennent au moins un pixel `fort`."""
    n, lab = cv2.connectedComponents(faible.astype(np.uint8), connectivity=8)
    garde = np.zeros(n, bool)
    garde[np.unique(lab[fort & faible])] = True
    garde[0] = False
    return garde[lab]


def _mi_hauteur(valeur: np.ndarray, seg: np.ndarray, ppm: float) -> np.ndarray:
    """Pixels dont la valeur atteint la moitié du maximum local du trait (rayon 0,75 mm) : bord d'un trait pris à
    mi-hauteur, sans le halo pâle (flou, sous-échantillonnage de la couleur en JPEG)."""
    k = int(round(1.5 * ppm)) | 1
    maxi = cv2.dilate(np.where(seg, valeur, 0).astype(np.float32), _noyau(k))
    return valeur >= 0.5 * maxi


def segmenter_couleur(cartes: dict, couleur: str, ppm: float = PX_PAR_MM) -> tuple[np.ndarray, np.ndarray]:
    """Encre rouge, bleue ou verte : chroma relative au fond de papier (image normalisée), teinte, hystérésis.
    La croissance traverse les pixels sombres sur ≤ 1,5 mm (là où un trait fin passe sur le plan imprimé, sa couleur
    se dilue dans le gris). Les composantes surtout claires (halo complémentaire d'un trait en JPEG) sont retirées.
    Renvoie (encre, mi-hauteur de la chroma)."""
    d, c, h, rel = cartes["D"], cartes["C"], cartes["H"], cartes["rel"]
    fort = (c >= CHROMA_FORT) & (d >= SOMBRE_FORT) & (rel >= RELATIF_FORT) & _dans_plages(h, PLAGES_TEINTE[couleur])
    faible = (c >= CHROMA_FAIBLE) & (d >= SOMBRE_FAIBLE) & (rel >= RELATIF_FAIBLE) & \
        _dans_plages(h, PLAGES_TEINTE_LARGES[couleur])
    if faible.any():
        k = int(round(PONT_SOMBRE_MM * ppm)) | 1
        faible |= (cv2.morphologyEx(faible.astype(np.uint8), cv2.MORPH_CLOSE, _noyau(k)) > 0) & (d >= NOIR_FAIBLE)
    seg = _hysteresis(faible, fort)
    if seg.any():
        n, lab = cv2.connectedComponents(seg.astype(np.uint8), connectivity=8)
        total = np.bincount(lab.ravel(), minlength=n)
        sombres = np.bincount(lab[seg & (d >= SOMBRE_CONTOUR)].ravel(), minlength=n)
        garder = sombres >= PART_SOMBRE_MIN * total
        garder[0] = False
        seg = garder[lab]
    return seg, _mi_hauteur(c, seg, ppm)


def segmenter_noir(cartes: dict, masque: np.ndarray, imprime: np.ndarray, exclu: np.ndarray, colores: np.ndarray,
                   ppm: float) -> tuple[np.ndarray, float, np.ndarray]:
    """Encre noire : sombre et peu chromatique hors du plan imprimé ; sur le plan imprimé, nettement plus sombre que
    son gris (mesuré sur la photo). Composantes gardées si ancrées loin du plan imprimé (ni résidu ni reflet).
    Renvoie (masque, gris du plan mesuré, mi-hauteur)."""
    clarte, d, rel = cartes["L"], cartes["D"], cartes["rel"]
    achro = rel < NOIR_RELATIF_MAX
    ref = imprime & ~exclu & achro
    gris = float(np.percentile(clarte[ref], 10)) if ref.sum() >= 100 else GRIS_PLAN
    fort = (d >= NOIR_FORT) & achro & ~masque & ~exclu
    faible = achro & ~exclu & (((d >= NOIR_FAIBLE) & ~masque) | ((clarte < NOIR_SUR_IMPRIME * gris) & masque))
    pres = cv2.dilate(colores.astype(np.uint8), _noyau(2 * NOIR_PRES_COULEUR_PX + 1)) > 0
    seg = _hysteresis(faible & ~pres, fort & ~pres)
    if not seg.any():
        return seg, gris, seg
    loin = cv2.distanceTransform((~imprime).astype(np.uint8), cv2.DIST_L2, 5) > NOIR_ANCRAGE_MM * ppm
    n, lab = cv2.connectedComponents(seg.astype(np.uint8), connectivity=8)
    ancre = np.bincount(lab[seg & loin].ravel(), minlength=n)
    garder = ancre >= NOIR_ANCRAGE_MM2 * ppm ** 2
    garder[0] = False
    seg = garder[lab]
    return seg, gris, _mi_hauteur(d, seg, ppm)


def _ponter(seg: np.ndarray, autres: np.ndarray, sombre: np.ndarray, ppm: float) -> np.ndarray:
    """Comble les coupures d'un trait : là où une autre encre le croise (≤ 2,5 mm ; seuls les ajouts qui relient
    deux morceaux du trait sont gardés, pas d'ergot vers un dessin voisin d'une autre couleur) ; là où il passe sur
    un tracé sombre (≤ 1,5 mm : plan imprimé sous un trait repassé plusieurs fois)."""
    if not seg.any():
        return seg
    _, lab = cv2.connectedComponents(seg.astype(np.uint8), connectivity=8)
    k = int(round(PONT_SOMBRE_MM * ppm)) | 1
    sortie = seg | ((cv2.morphologyEx(seg.astype(np.uint8), cv2.MORPH_CLOSE, _noyau(k)) > 0) & sombre)
    for dist_mm, sous in ((PONT_CROISEMENT_MM, autres),):
        k = int(round(dist_mm * ppm)) | 1
        ajout = (cv2.morphologyEx(seg.astype(np.uint8), cv2.MORPH_CLOSE, _noyau(k)) > 0) & sous & ~sortie
        if not ajout.any():
            continue
        n, lab_a, stats, _ = cv2.connectedComponentsWithStats(ajout.astype(np.uint8), connectivity=8)
        h, w = seg.shape
        for i in range(1, n):
            x, y, lw, lh, _ = stats[i]
            x0, y0, x1, y1 = max(0, x - 1), max(0, y - 1), min(w, x + lw + 1), min(h, y + lh + 1)
            m = lab_a[y0:y1, x0:x1] == i
            voisins = lab[y0:y1, x0:x1][cv2.dilate(m.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0]
            if len(set(voisins.tolist()) - {0}) >= 2:
                sortie[y0:y1, x0:x1] |= m
    return sortie


def _largeur_px(b: np.ndarray, centile: float = 50.0) -> float:
    """Largeur d'un trait (px) : 2 × distance au bord sur les crêtes de la transformée de distance (médiane, ou
    centile demandé : le 20e centile dit si tout le trait est épais)."""
    if not b.any():
        return 0.0
    dist = cv2.distanceTransform(b.astype(np.uint8), cv2.DIST_L2, 5)
    crete = (dist >= cv2.dilate(dist, np.ones((3, 3), np.uint8)) - 1e-6) & b
    return float(2 * np.percentile(dist[crete], centile)) if crete.any() else 0.0


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


def _nettoyer_trait(seg: np.ndarray, ppm: float, mi_hauteur: np.ndarray | None = None) -> tuple[np.ndarray, float]:
    """Aucune ouverture (elle effacerait un trait de stylo de 1-2 px ; miettes et ergots sont retirés plus loin).
    Marqueur (80 % du trait ≥ 1,25 mm à mi-hauteur) : bord pris à mi-hauteur (le halo pâle l'élargirait), fermeture
    5 px. Stylo : trait avec son halo (il réunit les passages repassés et ferme les petits rectangles), fermeture
    3 px. Trous ≤ 4 mm² bouchés, miettes retirées (aire minimale en mm² à l'échelle). Renvoie (trait, largeur
    médiane en px)."""
    rogne = seg if mi_hauteur is None else seg & mi_hauteur
    if _largeur_px(rogne, 20.0) >= TRAIT_MARQUEUR_MM * ppm:
        b = cv2.morphologyEx(rogne.astype(np.uint8), cv2.MORPH_CLOSE, _noyau(5))
    else:
        b = cv2.morphologyEx(seg.astype(np.uint8), cv2.MORPH_CLOSE, _noyau(3))
    t = _boucher_trous(b > 0, TROU_MAX_MM2 * ppm ** 2)
    largeur = _largeur_px(t)
    aire_min = min(AIRE_MIN_MM2, max(0.6, 3.0 * largeur / ppm))
    return _retirer_miettes(t, aire_min * ppm ** 2), largeur


def _retirer_miettes(b: np.ndarray, aire_min_px: float) -> np.ndarray:
    if not b.any():
        return b
    n, lab, stats, _ = cv2.connectedComponentsWithStats(b.astype(np.uint8), connectivity=8)
    garder = stats[:, cv2.CC_STAT_AREA] >= aire_min_px
    garder[0] = False
    return garder[lab]


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


# --- Redressement et plan imprimé ------------------------------------------------------------------
def _resolution_locale(hom: np.ndarray, infos: dict) -> float:
    """Résolution de la photo (px par mm de feuille) la plus faible sur la zone du plan : racine du jacobien de
    l'homographie inverse (feuille mm → photo px), sur une grille 5 × 5."""
    inv = np.linalg.inv(hom)
    x0, y0, x1, y1 = infos.get("zone_plan_mm") or (0.0, 0.0, *infos["page_mm"])
    mini = math.inf
    for x in np.linspace(x0, x1, 5):
        for y in np.linspace(y0, y1, 5):
            p = inv @ np.array([x, y, 1.0])
            w = p[2]
            jac = (inv[:2, :2] * w - np.outer(p[:2], inv[2, :2])) / w ** 2
            mini = min(mini, math.sqrt(abs(float(np.linalg.det(jac)))))
    return mini


def _px_par_mm_travail(ppm_photo: float) -> float:
    """4 px/mm, sauf photo trop faible : pas plus de 1,5 × sa résolution (un suréchantillonnage n'ajoute rien)."""
    if ppm_photo * SURECHANTILLONNAGE_MAX >= PX_PAR_MM:
        return float(PX_PAR_MM)
    return max(PX_PAR_MM_MIN, round(ppm_photo * SURECHANTILLONNAGE_MAX, 2))


def _redresser_photo(photo: np.ndarray, reperes: dict, infos: dict, ppm: float = PX_PAR_MM):
    """Homographie des 16 coins (photo px → mm feuille), erreur de reprojection, image redressée à `ppm` px/mm."""
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
    l, h = int(round(page[0] * ppm)), int(round(page[1] * ppm))
    t = np.array([[ppm, 0, -0.5], [0, ppm, -0.5], [0, 0, 1]])
    redresse = cv2.warpPerspective(source, t @ hom_source, (l, h), flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    return hom, redresse, float(np.sqrt(np.mean(erreurs ** 2))), float(erreurs.max()), px_par_mm_photo


def _dilater_masque(imprime: np.ndarray, ppm: float) -> np.ndarray:
    r = max(1, int(round(DILATATION_MASQUE_MM * ppm)))
    return cv2.dilate(imprime.astype(np.uint8), _noyau(2 * r + 1)) > 0


def _masques(infos: dict, feuille_png: Path, forme: tuple[int, int], ppm: float = PX_PAR_MM):
    """(masque du plan imprimé dilaté, imprimé non dilaté, zones exclues) à `ppm` px/mm."""
    rendu = fe.lire_image(feuille_png)
    if rendu is None:
        raise ErreurPhoto(f"feuille rendue illisible : {feuille_png}", code=2)
    if rendu.ndim == 3:
        rendu = cv2.cvtColor(rendu, cv2.COLOR_BGR2GRAY)
    h, l = forme
    reduit = cv2.resize(rendu, (l, h), interpolation=cv2.INTER_AREA)
    imprime = reduit < SEUIL_IMPRIME
    exclu = np.zeros((h, l), bool)
    for rep in infos["reperes"].values():
        (x0, y0), (x1, y1) = rep["coins_mm"][0], rep["coins_mm"][2]
        exclu[max(0, int((y0 - 1) * ppm)):int(math.ceil((y1 + 1) * ppm)),
              max(0, int((x0 - 1) * ppm)):int(math.ceil((x1 + 1) * ppm))] = True
    x0, y0, x1, y1 = infos.get("cadre_identification_mm") or fe.zone_bande_mm(tuple(infos["page_mm"]))
    exclu[max(0, int((y0 - 1) * ppm)):int(math.ceil((y1 + 1) * ppm)),
          max(0, int((x0 - 1) * ppm)):int(math.ceil((x1 + 1) * ppm))] = True
    bord = int(round(2 * ppm))
    exclu[:bord, :] = exclu[-bord:, :] = True
    exclu[:, :bord] = exclu[:, -bord:] = True
    return _dilater_masque(imprime, ppm), imprime, exclu


def _recaler_imprime(imprime: np.ndarray, cartes: dict, exclu: np.ndarray, ppm: float,
                     zone_mm=None) -> tuple[np.ndarray, float]:
    """Recale la feuille rendue sur le tracé gris de la photo (ECC, homographie, à demi-résolution) : rattrape le
    gondolage et la distorsion résiduels (≈ 0,5 mm) avant de séparer l'encre noire du plan imprimé.
    Renvoie (imprimé recalé, déplacement maximal en mm) ; inchangé si l'ECC échoue ou déplace de plus de 2 mm."""
    h, w = imprime.shape
    gris = (cartes["D"] * (cartes["C"] < 8.0)).astype(np.float32)
    gris[exclu] = 0.0
    rendu = imprime.astype(np.float32)
    rendu[exclu] = 0.0
    f = 0.5
    petit = (int(round(w * f)), int(round(h * f)))
    modele = cv2.GaussianBlur(cv2.resize(gris, petit, interpolation=cv2.INTER_AREA), (0, 0), 1.0)
    source = cv2.GaussianBlur(cv2.resize(rendu, petit, interpolation=cv2.INTER_AREA), (0, 0), 1.0)
    warp = np.eye(3, dtype=np.float32)
    try:
        _, warp = cv2.findTransformECC(modele, source, warp, cv2.MOTION_HOMOGRAPHY,
                                       (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-5), None, 5)
    except cv2.error:
        return imprime, 0.0
    echelle = np.diag([1 / f, 1 / f, 1.0])
    complet = echelle @ warp.astype(np.float64) @ np.linalg.inv(echelle)
    x0, y0, x1, y1 = (np.asarray(zone_mm, dtype=float) * ppm) if zone_mm else (0.0, 0.0, float(w), float(h))
    coins = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], np.float64).reshape(-1, 1, 2)
    depl = cv2.perspectiveTransform(coins, complet) - coins
    deplacement = float(np.abs(depl).max()) / ppm
    if not np.isfinite(deplacement) or deplacement > RECALAGE_MAX_MM:
        return imprime, 0.0
    recale = cv2.warpPerspective(imprime.astype(np.uint8), complet, (w, h),
                                 flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP) > 0
    return recale, deplacement


# --- Bâtiment, annotations, formes fermées ---------------------------------------------------------------
def _boite_batiment_m(plan: dict, rects_murs: dict):
    """Boîte englobante (m) des murs, pièces et chambres froides ; None si le plan n'en a pas."""
    pts = [np.asarray(r, dtype=float) for _, r in rects_murs.values()]
    for cle in ("pieces", "chambres_froides"):
        pts += [np.asarray(p["polygone"], dtype=float) for p in plan.get(cle, []) if p.get("polygone")]
    if not pts:
        return None
    tous = np.vstack(pts)
    return (*tous.min(axis=0).tolist(), *tous.max(axis=0).tolist())


def _dans_boite(p, boite, marge: float = 0.0) -> bool:
    return boite is None or (boite[0] - marge <= p[0] <= boite[2] + marge and boite[1] - marge <= p[1] <= boite[3] + marge)


def _boite_px(boite_m, base: dict, ppm: float, marge_m: float):
    if boite_m is None:
        return None
    a = fe.mm_vers_px(fe.m_vers_mm([boite_m[0] - marge_m, boite_m[1] - marge_m], base), ppm)
    b = fe.mm_vers_px(fe.m_vers_mm([boite_m[2] + marge_m, boite_m[3] + marge_m], base), ppm)
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


def _filtrer_annotations(traits: dict, zone_px, ppm: float) -> tuple[dict, list[dict]]:
    """Composantes dont la boîte englobante ne touche pas le bâtiment agrandi (`zone_px`) et qui ne sont pas à moins
    de 1 mm d'un trait gardé : annotations manuscrites, retirées et listées (position en mm)."""
    if zone_px is None:
        return traits, []
    zx0, zy0, zx1, zy1 = zone_px
    etiq, candidats = {}, {}
    gardes = np.zeros(next(iter(traits.values())).shape, bool)
    for c, t in traits.items():
        n, lab, stats, _ = cv2.connectedComponentsWithStats(t.astype(np.uint8), connectivity=8)
        etiq[c] = (lab, stats)
        candidats[c] = []
        for i in range(1, n):
            x, y, w, h, _ = stats[i]
            if x + w - 1 < zx0 or x > zx1 or y + h - 1 < zy0 or y > zy1:
                candidats[c].append(i)
            else:
                gardes |= lab == i
    rayon = max(1, int(round(RELIEE_MM * ppm)))
    for _ in range(3):
        proche = cv2.dilate(gardes.astype(np.uint8), _noyau(2 * rayon + 1)) > 0
        change = False
        for c, ids in candidats.items():
            lab = etiq[c][0]
            for i in list(ids):
                m = lab == i
                if (m & proche).any():
                    ids.remove(i)
                    gardes |= m
                    change = True
        if not change:
            break
    sortie, annotations = {}, []
    for c, t in traits.items():
        lab, stats = etiq[c]
        retire = np.zeros(len(stats), bool)
        retire[candidats[c]] = True
        sortie[c] = t & ~retire[lab]
        for i in candidats[c]:
            x, y, w, h, aire = stats[i]
            if aire < 0.5 * ppm ** 2:
                continue
            annotations.append({"couleur": c, "boite_mm": [round(x / ppm, 1), round(y / ppm, 1), round((x + w) / ppm, 1),
                                                           round((y + h) / ppm, 1)],
                                "aire_mm2": round(aire / ppm ** 2, 1), "motif": "loin du bâtiment (plus de 2 m)"})
    return sortie, annotations


def _piece_de(p, plan: dict) -> str:
    """Nom de la chambre froide ou de la pièce qui contient le point (m), sinon la plus proche à ≤ 0,30 m, sinon
    « extérieur »."""
    polys = [(q.get("nom") or q.get("id") or "?", q["polygone"]) for cle in ("chambres_froides", "pieces")
             for q in plan.get(cle, []) if q.get("polygone")]
    for nom, poly in polys:
        if _point_dans_polygone(p, poly):
            return nom
    proches = [(_plus_proche_contour(p, poly)[1], nom) for nom, poly in polys]
    proches = [x for x in proches if x[0] <= 0.30]
    return min(proches)[1] if proches else "extérieur"


def _iou_boites(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _couleur_contour(cartes: dict, masque: np.ndarray | None = None, ppm: float = PX_PAR_MM):
    """Pour chaque pixel : chroma Lab et teinte HSV de la couleur moyenne des pixels sombres (≥ 0,15) à ≤ 2 px
    (côté pâle d'un rectangle au stylo, couleur diluée dans le gris), et « sombre loin du plan imprimé » (stylo
    noir pâle). Calculé une fois pour toute l'image."""
    sombre = (cartes["D"] >= SOMBRE_CONTOUR).astype(np.float32)
    n = cv2.boxFilter(sombre, -1, (5, 5), normalize=False)
    somme = cv2.boxFilter(cartes["norm"].astype(np.float32) * sombre[:, :, None], -1, (5, 5), normalize=False)
    moyen = (somme / np.maximum(n, 1.0)[:, :, None]).astype(np.float32)
    lab = cv2.cvtColor(moyen, cv2.COLOR_BGR2Lab)
    chroma = np.where(n > 0, np.hypot(lab[:, :, 1], lab[:, :, 2]), 0.0)
    teinte = cv2.cvtColor((np.clip(moyen, 0, 1) * 255 + 0.5).astype(np.uint8), cv2.COLOR_BGR2HSV)[:, :, 0]
    if masque is None:
        hors_plan = np.zeros(n.shape, bool)
    else:
        r = max(1, int(round(ppm)))
        hors_plan = (n > 0) & ~(cv2.dilate(masque.astype(np.uint8), _noyau(2 * r + 1)) > 0)
    return chroma, teinte, hors_plan


def _teinte_contour(couleur_contour, points: np.ndarray, k: np.ndarray, ok: np.ndarray):
    """Points du bord d'un trou sans encre reconnue à côté : chroma ≥ 4 et teinte d'une couleur → cette couleur ;
    sombre, sans couleur et loin du plan imprimé (à plus de 1 mm du masque) → noir."""
    chroma, teinte, hors_plan = couleur_contour
    k, ok = k.copy(), ok.copy()
    indices = np.flatnonzero(~ok)
    c = chroma[points[:, 1], points[:, 0]]
    t = teinte[points[:, 1], points[:, 0]]
    for i, nom in enumerate(COULEURS[:3]):
        m = (c >= 4.0) & _dans_plages(t, PLAGES_TEINTE_LARGES[nom]) & ~ok[indices]
        k[indices[m]] = i
        ok[indices[m]] = True
    m = (c < 4.0) & hors_plan[points[:, 1], points[:, 0]] & ~ok[indices]
    k[indices[m]] = COULEURS.index("noir")
    ok[indices[m]] = True
    return k, ok


def _formes_fermees(cartes: dict, traits: dict, exclu: np.ndarray, ppm: float, base: dict, plan: dict,
                    rects_murs: dict, batiment, zone_m, diagnostic: list | None = None,
                    masque: np.ndarray | None = None) -> list[dict]:
    """Équipements dessinés : contours fermés (rectangles, boucles) et petits rectangles pleins.

    1. Trous clairs du tracé (encre ou plan imprimé, sombre ≥ 0,15), bordés à ≥ 50 % par une même encre (le reste
       peut être un mur imprimé, ou une autre encre sur moins de 30 % : sinon c'est la fente entre deux traits).
       Neuf tracés : clarté seule (le halo de couleur d'un stylo comble
       l'intérieur d'un petit rectangle), fermée par un disque de 3 ou 5 px ou par un segment de 5 px vertical ou
       horizontal (coin ouvert de 1 à 4 px sans combler un intérieur étroit dans l'autre sens) ; clarté + encres,
       fermée de même (côté trop pâle d'un rectangle).
    2. Composantes d'encre pleines et trapues (≥ 1,5 mm d'épaisseur, rectangulaires à ≥ 75 %, allongement ≤ 6) :
       petit rectangle au stylo dont l'intérieur est noyé par le halo de couleur d'une photo faible.
    Puis : assez rectangulaires, à l'échelle d'un équipement (plus grand que l'écriture hors du bâtiment), pas dans un
    mur, pas une pièce, et d'où ne partent pas ≥ 2 traits de leur couleur (boucle formée par le réseau). Doublons
    fusionnés (la plus grande gardée). Identifiants F1, F2… par couleur puis de haut en bas : identiques d'un appel à
    l'autre quelle que soit la couleur lue."""
    h, w = cartes["D"].shape
    trace = (cartes["D"] >= SOMBRE_CONTOUR) | exclu
    union = trace.copy()
    for t in traits.values():
        union |= t

    def fermer(m, k):
        noyau = _noyau(k) if isinstance(k, int) else np.ones(k, np.uint8)
        return cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, noyau) > 0

    traces = (trace, fermer(trace, 3), fermer(trace, 5), fermer(trace, (5, 1)), fermer(trace, (1, 5)),
              union, fermer(union, 3), fermer(union, (5, 1)), fermer(union, (1, 5)))
    pile = np.stack([cv2.distanceTransform((~traits[c]).astype(np.uint8), cv2.DIST_L2, 3) for c in COULEURS])
    pres_encre = pile.min(axis=0) <= 3.0
    couleur_contour = _couleur_contour(cartes, masque, ppm)
    largeurs = {c: (_largeur_px(traits[c]) or 2.0) for c in COULEURS}
    S = float(base["S"])
    murs = [r for _, r in rects_murs.values()]
    pieces = [np.asarray(q["polygone"], dtype=float) for cle in ("chambres_froides", "pieces")
              for q in plan.get(cle, []) if q.get("polygone")]
    boites_pieces = [(*p.min(axis=0), *p.max(axis=0)) for p in pieces]
    marge = int(math.ceil((FORME_RETRAIT_MM + FORME_BRANCHE_MM) * ppm + max(largeurs.values()))) + 8
    candidats: list[dict] = []

    def noter(motif, centre, couleur, *details):
        if diagnostic is not None:
            diagnostic.append((np.round(centre, 1).tolist(), couleur, motif, *details))

    def evaluer(couleur, part, plein, x0, y0, passe, pleine=False, parts=None):
        """Géométrie et filtres d'un candidat (`plein` : région pleine dans la fenêtre x0, y0) ; ajoute s'il passe."""
        cnts, _ = cv2.findContours(plein.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cnt = max(cnts, key=cv2.contourArea)
        boite = cv2.minAreaRect(cnt)
        (cx, cy), _, _ = boite
        coins = cv2.boxPoints(boite)
        e1, e2 = coins[1] - coins[0], coins[2] - coins[1]
        ang1 = (math.degrees(math.atan2(e1[1], e1[0])) + 90.0) % 180.0 - 90.0
        if abs(ang1) <= 45.0:
            lx, ly, angle = float(np.linalg.norm(e1)) + 1, float(np.linalg.norm(e2)) + 1, ang1
        else:
            lx, ly = float(np.linalg.norm(e2)) + 1, float(np.linalg.norm(e1)) + 1
            angle = (math.degrees(math.atan2(e2[1], e2[0])) + 90.0) % 180.0 - 90.0
        rectangularite = float(plein.sum()) / max(lx * ly, 1.0)
        if abs(angle) <= TOLERANCE_ANGLE_DEG:
            angle = 0.0
        dx_mm, dy_mm = max(lx - largeurs[couleur], 1.0) / ppm, max(ly - largeurs[couleur], 1.0) / ppm
        petit, grand = min(dx_mm, dy_mm), max(dx_mm, dy_mm)
        centre_mm = fe.px_vers_mm([cx + x0, cy + y0], ppm)
        centre_m = fe.mm_vers_m(centre_mm, base)
        dedans = _dans_boite(centre_m, batiment)
        cmin, gmin = ((FORME_COTE_MIN_MM, FORME_GRAND_COTE_MIN_MM) if dedans
                      else (FORME_DEHORS_COTE_MIN_MM, FORME_DEHORS_GRAND_COTE_MIN_MM))
        rect_min = FORME_PLEINE_RECTANGULARITE_MIN if pleine else FORME_RECTANGULARITE_MIN
        allong_max = FORME_PLEINE_ELANCEMENT_MAX if pleine else FORME_ELANCEMENT_MAX
        if (rectangularite < rect_min or grand / petit > allong_max or petit < cmin or grand < gmin
                or grand > FORME_COTE_MAX_MM or grand * S / 1000.0 > FORME_COTE_MAX_M):
            noter("geometrie", centre_mm, couleur, round(rectangularite, 2), round(petit, 2), round(grand, 2), passe)
            return
        if not _dans_boite(centre_m, zone_m) or any(_point_dans_polygone(centre_m, m) for m in murs):
            return
        demi = np.array([dx_mm, dy_mm]) * S / 2000.0
        boite_m = (*(centre_m - demi), *(centre_m + demi))
        if any(_iou_boites(boite_m, b) >= 0.5 for b in boites_pieces):
            return
        # traits de la même couleur qui partent de la forme sur ≥ 3 mm : composantes distinctes de l'encre reliée
        # au contour, comptées au-delà de 1 + 3 mm (un trait épais repassé autour d'un trou en a 2)
        ph, pw = plein.shape
        d_ext = cv2.distanceTransform((1 - plein).astype(np.uint8), cv2.DIST_L2, 3)
        encre = traits[couleur][y0:y0 + ph, x0:x0 + pw]
        branches = 0
        if encre.any():
            _, lab_b = cv2.connectedComponents(encre.astype(np.uint8), connectivity=8)
            reliees = np.isin(lab_b, np.unique(lab_b[encre & (d_ext <= FORME_RETRAIT_MM * ppm + 2)])) & encre
            loin = reliees & (d_ext >= (FORME_RETRAIT_MM + FORME_BRANCHE_MM) * ppm)
            if loin.any():
                branches = cv2.connectedComponents(loin.astype(np.uint8), connectivity=8)[0] - 1
        if branches >= 2:
            noter("branches", centre_mm, couleur, branches, passe)
            return
        confiance = (min(1.0, part / 0.8) * min(1.0, rectangularite / 0.9) * (1.0 if branches == 0 else 0.9)
                     * (FORME_PLEINE_CONFIANCE if pleine else 1.0))
        candidats.append({"couleur": couleur, "centre_mm": centre_mm, "centre_m": centre_m, "passe": passe,
                          "aire_px": int(plein.sum()), "pleine": pleine,
                          "dimensions_m": [dx_mm * S / 1000.0, dy_mm * S / 1000.0], "angle_deg": round(angle, 1),
                          "dedans": dedans, "part_couleur": round(part, 2), "rectangularite": round(rectangularite, 2),
                          "branches": branches, "confiance": round(confiance, 2), "plein": (x0, y0, plein.astype(bool)),
                          "parts": parts or {couleur: 1.0}})

    # 1. Trous bordés d'encre
    for passe, t in enumerate(traces):
        n, lab, stats, _ = cv2.connectedComponentsWithStats((~t).astype(np.uint8), connectivity=4)
        for i in range(1, n):
            x, y, lw, lh, aire = stats[i]
            if x == 0 or y == 0 or x + lw >= w or y + lh >= h or aire < 2 or max(lw, lh) > FORME_COTE_MAX_MM * ppm:
                continue
            if not pres_encre[y:y + lh, x:x + lw].any():
                continue                                   # aucune encre au bord : pièce, mur, porte imprimés
            x0, y0 = max(0, x - marge), max(0, y - marge)
            x1, y1 = min(w, x + lw + marge), min(h, y + lh + marge)
            trou = lab[y0:y1, x0:x1] == i
            contours, _ = cv2.findContours(trou.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            bord = np.vstack([c.reshape(-1, 2) for c in contours])
            d = pile[:, bord[:, 1] + y0, bord[:, 0] + x0]
            k = np.argmin(d, axis=0)
            ok = d[k, np.arange(len(k))] <= 2.5
            if (~ok).any():
                k, ok = _teinte_contour(couleur_contour, bord[~ok] + [x0, y0], k, ok)
            parts = {c: float(np.mean(ok & (k == j))) for j, c in enumerate(COULEURS)}
            couleur = max(parts, key=parts.get)
            if max(v for c, v in parts.items() if c != couleur) >= FORME_AUTRE_ENCRE_MAX:
                noter("autre encre", fe.px_vers_mm([x + lw / 2, y + lh / 2], ppm), couleur, parts, passe)
                continue
            if parts[couleur] < FORME_PART_MIN:
                if parts[couleur] > 0.2:
                    noter("part", fe.px_vers_mm([x + lw / 2, y + lh / 2], ppm), couleur, round(parts[couleur], 2), passe)
                continue
            r = max(2, int(round(largeurs[couleur])) + 2)
            anneau = cv2.dilate(trou.astype(np.uint8), _noyau(2 * r + 1)) > 0
            ext = (trou | (anneau & t[y0:y1, x0:x1])).astype(np.uint8)
            cnts, _ = cv2.findContours(ext, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            plein = np.zeros_like(ext)
            cv2.drawContours(plein, [max(cnts, key=cv2.contourArea)], -1, 1, thickness=-1)
            evaluer(couleur, parts[couleur], plein, x0, y0, passe, parts=parts)
    # 2. Rectangles pleins (intérieur noyé dans le halo de couleur)
    for couleur in COULEURS:
        n, lab, stats, _ = cv2.connectedComponentsWithStats(traits[couleur].astype(np.uint8), connectivity=8)
        for i in range(1, n):
            x, y, lw, lh, aire = stats[i]
            if (max(lw, lh) > FORME_COTE_MAX_MM * ppm or min(lw, lh) < FORME_PLEINE_EPAISSEUR_MM * ppm
                    or aire < (FORME_PLEINE_EPAISSEUR_MM * ppm) ** 2):
                continue
            x0, y0 = max(0, x - marge), max(0, y - marge)
            x1, y1 = min(w, x + lw + marge), min(h, y + lh + marge)
            comp = (lab[y0:y1, x0:x1] == i).astype(np.uint8)
            cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            plein = np.zeros_like(comp)
            cv2.drawContours(plein, [max(cnts, key=cv2.contourArea)], -1, 1, thickness=-1)
            epaisseur = 2.0 * float(cv2.distanceTransform(plein, cv2.DIST_L2, 5).max()) / ppm
            if epaisseur < FORME_PLEINE_EPAISSEUR_MM:
                continue
            evaluer(couleur, 1.0, plein, x0, y0, "pleine", pleine=True)
    # doublons : on garde la plus grande des formes de même couleur qui se recouvrent (≥ 30 % de la plus petite) ;
    # à surface voisine, un contour l'emporte sur un rectangle plein
    def boite(f):
        demi = np.asarray(f["dimensions_m"]) / 2
        return (*(f["centre_m"] - demi), *(f["centre_m"] + demi))

    def recouvrement(a, b):
        ba, bb = boite(a), boite(b)
        ix = max(0.0, min(ba[2], bb[2]) - max(ba[0], bb[0]))
        iy = max(0.0, min(ba[3], bb[3]) - max(ba[1], bb[1]))
        petite = min((ba[2] - ba[0]) * (ba[3] - ba[1]), (bb[2] - bb[0]) * (bb[3] - bb[1]))
        return ix * iy / petite if petite > 0 else 0.0

    formes: list[dict] = []
    for cand in sorted(candidats, key=lambda f: (-f["aire_px"] * (0.7 if f["pleine"] else 1.0))):
        if any(f["couleur"] == cand["couleur"] and recouvrement(f, cand) >= 0.3 for f in formes):
            continue
        formes.append(cand)
    formes.sort(key=lambda f: (COULEURS.index(f["couleur"]), round(float(f["centre_m"][1]), 1), float(f["centre_m"][0])))
    for k, f in enumerate(formes, start=1):
        f["id"] = f"F{k}"
        f["piece"] = _piece_de(f["centre_m"], plan)
        dx, dy = f["dimensions_m"]
        rot = f["angle_deg"] if dx >= dy else f["angle_deg"] + 90.0
        f["equipement"] = {"id": f["id"], "type": None, "position": [float(v) for v in f["centre_m"]],
                           "dimensions": [max(dx, dy), min(dx, dy)], "rotation": round(rot % 180.0, 1),
                           "forme": True, "tolerance_m": max(ACCROCHE_EQUIPEMENT_M, ACCROCHE_FORME_MM * S / 1000.0)}
    return formes


def _retirer_formes(traits: dict, formes: list[dict], ppm: float) -> dict:
    """Retire du trait de sa couleur le contour de chaque forme fermée (avec 1 mm de marge) : il reste les réseaux."""
    sortie = {c: t.copy() for c, t in traits.items()}
    r = max(1, int(round(FORME_RETRAIT_MM * ppm)))
    for f in formes:
        x0, y0, plein = f["plein"]
        zone = cv2.dilate(plein.astype(np.uint8), _noyau(2 * r + 1)) > 0
        hh, ww = zone.shape
        sortie[f["couleur"]][y0:y0 + hh, x0:x0 + ww] &= ~zone
    return sortie


# --- Accrochage et lecture d'une couleur -----------------------------------------------------------------
def _accrocher(p, rects_eq: dict, rects_murs: dict, mode: str):
    """Accroche une extrémité (m). Renvoie (point, epingle, info) ; info = {"type", "id"} ou None.
    Les formes fermées dessinées sont des équipements (`tolerance_m` propre)."""
    meilleur = None
    for eid, (eq, rect) in rects_eq.items():
        d = _distance_polygone(p, rect)
        if d <= eq.get("tolerance_m", ACCROCHE_EQUIPEMENT_M):
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


def _accrocher_morceau(morceau: np.ndarray, rects_eq: dict, rects_murs: dict, mode: str):
    """Accroche les deux bouts d'un tronçon. Bout posé à côté d'une forme dessinée (mode centre) : coude
    perpendiculaire jusqu'à son centre (le trait longe un mur, l'appareil est à côté) au lieu de déplacer le bout."""
    pts = [np.asarray(p, dtype=float) for p in morceau]
    infos = {}
    for bout in ("debut", "fin"):
        i = 0 if bout == "debut" else len(pts) - 1
        p = pts[i]
        cible, epingle, info = _accrocher(p, rects_eq, rects_murs, mode)
        forme = info and info["type"] == "equipement" and rects_eq[info["id"]][0].get("forme")
        if forme and mode == "centre" and not _point_dans_polygone(p, rects_eq[info["id"]][1]):
            voisin = pts[1] if bout == "debut" else pts[-2]
            u = p - voisin
            nu = float(np.linalg.norm(u))
            proj = None
            if nu > 1e-9:
                u /= nu
                t = float((cible - voisin) @ u)
                if t > 0:
                    proj = voisin + u * t
            if bout == "debut":
                if proj is not None:
                    pts[0] = proj
                pts.insert(0, cible.copy())
            else:
                if proj is not None:
                    pts[-1] = proj
                pts.append(cible.copy())
        else:
            pts[i] = cible
        infos[bout] = (epingle, info)
    epingles = {0: infos["debut"][0], len(pts) - 1: infos["fin"][0]}
    acc_d, acc_f = infos["debut"][1], infos["fin"][1]
    de = acc_d["id"] if acc_d and acc_d["type"] == "equipement" else None
    a = acc_f["id"] if acc_f and acc_f["type"] == "equipement" else None
    mur_de = acc_d["id"] if acc_d and acc_d["type"] == "mur" else None
    mur_a = acc_f["id"] if acc_f and acc_f["type"] == "mur" else None
    return np.array(pts), epingles, de, a, mur_de, mur_a


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


def _lire_couleur(trait: np.ndarray, ctx: dict) -> tuple[list[dict], float, list[str]]:
    """Trait d'une couleur → polylignes en m (de, a, mur_de, mur_a, groupe = composante du trait)."""
    ppm, base, S = ctx["ppm"], ctx["base"], ctx["S"]
    rects_eq, rects_murs = ctx["rects_eq"], ctx["rects_murs"]
    dist = cv2.distanceTransform(trait.astype(np.uint8), cv2.DIST_L2, 5)
    sq = squelette_zhang_suen(trait)
    largeur_mm = float(2 * np.median(dist[sq > 0]) / ppm) if sq.any() else 0.0
    _, etiquettes = cv2.connectedComponents(trait.astype(np.uint8), connectivity=8)
    h, w = trait.shape

    def bloquant(x_px, y_px):
        p_m = fe.mm_vers_m(fe.px_vers_mm([x_px, y_px], ppm), base)
        return any(_distance_polygone(p_m, rect) <= MARGE_DECOUPE_EQUIPEMENT_M for _, rect in rects_eq.values())

    brutes = vectoriser(sq, ergot_px=max(ERGOT_MIN_MM, 1.5 * largeur_mm) * ppm,
                        longueur_min_px=LONGUEUR_MIN_MM * ppm,
                        contraction_px=max(2.5, largeur_mm) * ppm, bloquant=bloquant)
    polylignes, avert = [], []
    for ib, br in enumerate(brutes):
        brut = _prolonger_extremites(br["points"], trait, largeur_mm * ppm)
        simp = _affiner_sommets(brut, _simplifier(brut, EPSILON_SIMPLIFICATION_MM * ppm), largeur_mm * ppm)
        if len(simp) < 2:
            continue
        mx, my = np.round(br["points"][len(br["points"]) // 2]).astype(int)
        groupe = int(etiquettes[min(max(my, 0), h - 1), min(max(mx, 0), w - 1)])
        aligne, total = _longueur_alignee(simp)
        pts_m = fe.mm_vers_m(fe.px_vers_mm(simp, ppm), base)
        for morceau in _decouper_aux_equipements(pts_m, rects_eq):
            if _longueur(morceau) * 1000.0 / S < LONGUEUR_MIN_MM:
                continue
            morceau, epingles, de, a, mur_de, mur_a = _accrocher_morceau(morceau, rects_eq, rects_murs, ctx["accrochage"])
            pts, av = redresser_polyligne(morceau, epingles)
            avert += av
            if len(pts) < 2 or _longueur(pts) < 1e-6:
                continue
            if _rang_extremite(a, rects_eq) < _rang_extremite(de, rects_eq):
                pts = pts[::-1]
                de, a, mur_de, mur_a = a, de, mur_a, mur_de
            polylignes.append({"points": pts, "de": de, "a": a, "mur_de": mur_de, "mur_a": mur_a, "groupe": groupe,
                               "brute": ib, "long_aligne": aligne, "long_brute": total})
    return polylignes, largeur_mm, avert


def _longueur_alignee(points) -> tuple[float, float]:
    """(longueur des segments à ≤ 7° de 0/90°, longueur totale) : un réseau suit les murs, une flèche à main levée
    est courbe ou en biais."""
    p = np.asarray(points, dtype=float)
    if len(p) < 2:
        return 0.0, 0.0
    v = np.diff(p, axis=0)
    longueurs = np.linalg.norm(v, axis=1)
    a = np.abs(np.degrees(np.arctan2(v[:, 1], v[:, 0]))) % 90.0
    aligne = (np.minimum(a, 90.0 - a) <= TOLERANCE_ANGLE_DEG)
    return float(longueurs[aligne].sum()), float(longueurs.sum())


def _ecarter_annotations(polylignes: list[dict], couleur: str, ctx: dict) -> tuple[list[dict], list[dict]]:
    """Par composante du trait : tracé entièrement hors du bâtiment et relié à rien (flèche, texte proche) ;
    extrémité libre hors du bâtiment à ≤ 5 mm d'une annotation écartée (flèche qui part du texte) ; tracé surtout
    courbe ou en biais (< 35 % de sa longueur suit les axes) dont une extrémité libre est hors du bâtiment (flèche
    qui vient de l'extérieur). Renvoie (gardées, annotations)."""
    batiment, base = ctx["batiment"], ctx["base"]
    groupes: dict[int, list[dict]] = {}
    for pl in polylignes:
        groupes.setdefault(pl["groupe"], []).append(pl)
    gardees, annotations = [], []
    for pls in groupes.values():
        dehors = all(not _dans_boite(p, batiment, TOLERANCE_BATIMENT_M) for pl in pls for p in pl["points"])
        relie = any(pl[c] for pl in pls for c in ("de", "a", "mur_de", "mur_a"))
        motif = "tracé hors du bâtiment, relié à rien (flèche ou écriture ?)" if dehors and not relie else None
        if motif is None and batiment is not None:
            brutes = {pl.get("brute"): (pl.get("long_aligne", 0.0), pl.get("long_brute", 0.0)) for pl in pls}
            total = sum(t for _, t in brutes.values())
            tout_courbe = total > 0 and sum(a for a, _ in brutes.values()) < ALIGNE_MIN * total
            for pl in pls:
                for cle, mur, idx in (("de", "mur_de", 0), ("a", "mur_a", -1)):
                    p = pl["points"][idx]
                    if pl[cle] or pl[mur] or _dans_boite(p, batiment, TOLERANCE_BATIMENT_M):
                        continue
                    p_mm = fe.m_vers_mm(p, base)
                    if any(_distance_boite(p_mm, an["boite_mm"]) <= FLECHE_MM for an in ctx["annotations_loin"]):
                        motif = "flèche partant d'une annotation"
                    elif tout_courbe:
                        motif = "tracé courbe venant de l'extérieur (flèche ?)"
        if motif is None:
            gardees += pls
            continue
        tous = fe.m_vers_mm(np.vstack([pl["points"] for pl in pls]), base)
        x0, y0 = tous.min(axis=0)
        x1, y1 = tous.max(axis=0)
        annotations.append({"couleur": couleur, "boite_mm": [round(float(v), 1) for v in (x0, y0, x1, y1)],
                            "longueur_plan_m": round(sum(_longueur(pl["points"]) for pl in pls), 2), "motif": motif})
    return gardees, annotations


def _formater_polylignes(polylignes: list[dict], prefixe: str, S: float, c_reproj: float) -> tuple[list[dict], list[str]]:
    polylignes = sorted(polylignes, key=lambda p: -_longueur(p["points"]))
    sortie, questions = [], []
    for k, pl in enumerate(polylignes, start=1):
        long_m = _longueur(pl["points"])
        nb_acc = sum(x is not None for x in (pl["de"] or pl["mur_de"], pl["a"] or pl["mur_a"]))
        c_len = min(1.0, max(0.3, long_m * 1000.0 / S / 20.0))
        ident = f"{prefixe}{k}"
        for cle, idx in (("de", 0), ("a", -1)):
            if pl[cle] is None:
                x, y = pl["points"][idx]
                questions.append(f"{ident} : extrémité libre à ({_f(x)} ; {_f(y)}) : relier à quel équipement ?")
        sortie.append({
            "id": ident,
            "points_m": [[round(float(x), 3), round(float(y), 3)] for x, y in pl["points"]],
            "longueur_plan_m": round(long_m, 3),
            "de": pl["de"], "a": pl["a"], "mur_de": pl["mur_de"], "mur_a": pl["mur_a"],
            "confiance": round(c_reproj * (0.6 + 0.2 * nb_acc) * c_len, 2),
        })
    return sortie, questions


def _question_formes(couleur: str, formes: list[dict]) -> str:
    n = len(formes)
    s = "s" if n > 1 else ""
    dedans = [f["dedans"] for f in formes]
    if all(dedans):
        idee = "ventilo-convecteurs, évaporateurs, splits ?"
    elif not any(dedans):
        idee = "groupe, centrale, condenseur ?"
    else:
        idee = "dedans : ventilo-convecteurs, évaporateurs ? dehors : groupe, condenseur ?"
    ids = ", ".join(f["id"] for f in formes)
    return (f"{n} forme{s} {FEMININ[couleur]}{s} dessinée{s} ({ids}) : quel{s} équipement{s} ? ({idee})")


def _sortie_forme(f: dict) -> dict:
    return {"id": f["id"], "couleur": f["couleur"],
            "centre_m": [round(float(v), 3) for v in f["centre_m"]],
            "dimensions_m": [round(float(v), 2) for v in f["dimensions_m"]], "angle_deg": f["angle_deg"],
            "piece": f["piece"], "confiance": f["confiance"],
            "centre_mm": [round(float(v), 1) for v in f["centre_mm"]],
            "part_couleur": f["part_couleur"], "rectangularite": f["rectangularite"]}


# --- Pipeline ----------------------------------------------------------------------------------------
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

    # 1. Repères, homographie, résolution utile
    reperes = fe.detecter_reperes(image)
    manquants = [i for i in range(4) if i not in reperes]
    if manquants:
        noms = ", ".join(f"{i} ({fe.POSITIONS_REPERES[i]})" for i in manquants)
        raise ErreurPhoto(f"repère(s) non détecté(s) : {noms}. Reprendre la photo de dessus, les 4 repères "
                          "entièrement visibles, nets, sans reflet ni ombre portée.")
    src = np.vstack([reperes[i] for i in range(4)]).astype(np.float64)
    dst = np.vstack([np.asarray(infos["reperes"][str(i)]["coins_mm"], dtype=float) for i in range(4)])
    hom0, _ = cv2.findHomography(src, dst, 0)
    if hom0 is None:
        raise ErreurPhoto("homographie impossible : repères mal détectés (photo trop floue ou trop inclinée)")
    ppm_locale = _resolution_locale(hom0, infos)
    ppm = _px_par_mm_travail(ppm_locale)
    hom, redresse, err_rms, err_max, ppm_photo = _redresser_photo(image, reperes, infos, ppm)
    if ppm_locale < RESOLUTION_FAIBLE_PX_MM:
        avert.append(f"photo de faible résolution (≈ {_f(ppm_locale, 1)} px/mm sur la feuille) : envoyer l'original "
                     "du téléphone (pas une capture d'écran ni une image recompressée par la messagerie) ; les "
                     "traits fins au stylo sont lus moins sûrement")
    if err_max > REPROJECTION_ALERTE_MM:
        avert.append(f"erreur de reprojection élevée ({_f(err_max)} mm au pire) : feuille pas à plat ou photo floue, "
                     "longueurs moins sûres")

    # 2. Plan imprimé, encres de toutes les couleurs
    masque, imprime, exclu = _masques(infos, chemins["png"], redresse.shape[:2], ppm)
    norm = _normaliser(redresse, ppm)
    cartes = _cartes(norm)
    imprime, recalage_mm = _recaler_imprime(imprime, cartes, exclu, ppm, infos.get("zone_plan_mm"))
    masque = _dilater_masque(imprime, ppm)
    norm, equilibre = _equilibrer_canaux(norm, imprime, exclu, cartes, ppm)
    cartes = _cartes(norm)
    segs, mi_hauteur = {}, {}
    for c in CHROMATIQUES:
        segs[c], mi_hauteur[c] = segmenter_couleur(cartes, c, ppm)
        segs[c] &= ~exclu
    colores = segs["rouge"] | segs["bleu"] | segs["vert"]
    segs["noir"], gris_plan, mi_hauteur["noir"] = segmenter_noir(cartes, masque, imprime, exclu, colores, ppm)
    sombre = cartes["D"] >= NOIR_FAIBLE
    pontes = {}
    for c in COULEURS:
        autres = np.zeros_like(sombre)
        for c2 in COULEURS:
            if c2 != c:
                autres |= segs[c2]
        pontes[c] = _ponter(segs[c], autres & ~exclu, sombre & ~exclu, ppm)
    traits, largeurs_px = {}, {}
    for c in COULEURS:
        traits[c], largeurs_px[c] = _nettoyer_trait(pontes[c], ppm, mi_hauteur[c] | (pontes[c] & ~segs[c]))
        traits[c] &= ~exclu

    # 3. Bâtiment, annotations écartées, formes fermées
    S = float(infos["S"])
    base = {"S": S, "origine_mm": infos["origine_mm"]}
    rects_plan = {eq["id"]: (eq, fe.rectangle_equipement(eq)) for eq in plan.get("equipements", [])
                  if eq.get("id") and eq.get("position") is not None}
    rects_murs = {m.get("id", f"mur{i}"): (m, fe.rectangle_mur(m)) for i, m in enumerate(plan.get("murs", []))
                  if m.get("de") is not None and m.get("a") is not None}
    batiment = _boite_batiment_m(plan, rects_murs)
    zone_m = None if batiment is None else (batiment[0] - MARGE_BATIMENT_M, batiment[1] - MARGE_BATIMENT_M,
                                            batiment[2] + MARGE_BATIMENT_M, batiment[3] + MARGE_BATIMENT_M)
    traits, annotations_loin = _filtrer_annotations(traits, _boite_px(batiment, base, ppm, MARGE_BATIMENT_M), ppm)
    formes = _formes_fermees(cartes, traits, exclu, ppm, base, plan, rects_murs, batiment, zone_m, masque=masque)
    aires = {c: float(traits[c].sum()) / ppm ** 2 for c in COULEURS}
    lignes = _retirer_formes(traits, formes, ppm)
    for c in COULEURS:
        lignes[c] = _retirer_miettes(lignes[c], min(AIRE_MIN_MM2, max(0.6, 3.0 * largeurs_px[c] / ppm)) * ppm ** 2)

    def presente(c):
        largeur_mm = max(largeurs_px[c], 1.0) / ppm
        return (aires[c] >= min(AIRE_MIN_COULEUR_MM2, LONGUEUR_MIN_COULEUR_MM * largeur_mm)
                or any(f["couleur"] == c for f in formes))

    presentes = [c for c in CHROMATIQUES if presente(c)]
    if marqueur == "auto":
        a_lire = [c for c in COULEURS if presente(c)]
        if not a_lire:
            raise ErreurPhoto("aucun trait de marqueur trouvé sur la photo (ni rouge, ni bleu, ni vert, ni noir). "
                              "Vérifier que c'est la bonne feuille et que le tracé est bien visible.")
    else:
        a_lire = [marqueur]
        if not presente(marqueur):
            autres = [c for c in presentes if c != marqueur]
            complement = (" Couleur(s) présente(s) sur la photo : " + ", ".join(autres) + " : relancer avec --marqueur "
                          + autres[0] + " si c'est bien ce réseau.") if autres else ""
            raise ErreurPhoto(f"aucun trait {marqueur} trouvé sur la photo du réseau « {reseau} »." + complement
                              + " Une photo d'un autre réseau ? Vérifier la feuille et la couleur du marqueur.")

    concordance = None
    attendu = imprime & ~exclu
    if attendu.sum() > 0:
        visible = norm.mean(axis=2) < 0.85
        concordance = float((visible & attendu).sum() / attendu.sum())
        if concordance < 0.35:
            avert.append(f"le plan imprimé ne se retrouve qu'à {concordance:.0%} sur la photo : est-ce bien la feuille "
                         f"de ce dossier ? (photo très claire ou feuille d'un autre plan)")

    # 4. Polylignes par couleur (les formes fermées de toutes les couleurs servent d'équipements pour l'accrochage)
    rects_eq = dict(rects_plan)
    for f in formes:
        rects_eq[f["id"]] = (f["equipement"], fe.rectangle_equipement(f["equipement"]))
    ctx = {"ppm": ppm, "base": base, "S": S, "rects_eq": rects_eq, "rects_murs": rects_murs, "accrochage": accrochage,
           "batiment": batiment, "annotations_loin": annotations_loin}
    lues, annotations = {}, list(annotations_loin)
    for c in a_lire:
        brutes, largeur_mm, av = _lire_couleur(lignes[c], ctx) if lignes[c].any() else ([], 0.0, [])
        avert += av
        gardees, ecartees = _ecarter_annotations(brutes, c, ctx)
        annotations += ecartees
        # bout de trait qui part d'une forme dessinée et y revient (reste de son contour) : pas un tronçon
        gardees = [pl for pl in gardees if not (pl["de"] and pl["de"] == pl["a"] and rects_eq[pl["de"]][0].get("forme")
                                                and _longueur(pl["points"]) < 3 * max(rects_eq[pl["de"]][0]["dimensions"]))]
        lues[c] = {"polylignes": gardees, "largeur_mm": largeur_mm}

    def cle_principale(c):
        long_ = sum(_longueur(p["points"]) for p in lues[c]["polylignes"])
        return (long_ > 0, c != "noir", long_, sum(f["couleur"] == c for f in formes), aires[c])

    couleur = max(lues, key=cle_principale) if marqueur == "auto" else marqueur
    if not lues[couleur]["polylignes"] and not any(f["couleur"] == couleur for f in formes):
        raise ErreurPhoto(f"aucun trait exploitable trouvé (couleur {couleur}) : tracé trop court ou trop pâle ?")

    # 5. Sorties par couleur
    c_reproj = min(1.0, max(0.3, 1.0 - err_max / 2.0))
    par_couleur, questions, references = {}, [], set()
    for c in [couleur] + [c for c in lues if c != couleur]:
        prefixe = f"{reseau}-photo-" if c == couleur else f"{reseau}-photo-{c}-"
        polys, qs = _formater_polylignes(lues[c]["polylignes"], prefixe, S, c_reproj)
        references |= {p[k] for p in polys for k in ("de", "a") if p[k] and p[k].startswith("F")}
        formes_c = [f for f in formes if f["couleur"] == c]
        if formes_c:
            qs.append(_question_formes(c, formes_c))
        questions += qs
        par_couleur[c] = {"polylignes": polys, "longueur_totale_plan_m": round(sum(p["longueur_plan_m"] for p in polys), 3),
                          "largeur_trait_mm": round(lues[c]["largeur_mm"], 2), "formes_fermees": [f["id"] for f in formes_c],
                          "questions": qs}
    sortie_polys = par_couleur[couleur]["polylignes"]
    total = par_couleur[couleur]["longueur_totale_plan_m"]
    formes_sortie = [f for f in formes if f["couleur"] in lues or f["id"] in references]
    autres_lues = [c for c in lues if c != couleur and (par_couleur[c]["polylignes"] or par_couleur[c]["formes_fermees"])]
    if autres_lues:
        avert.append("plusieurs couleurs sur la feuille : " + ", ".join(
            f"{c} ({len(par_couleur[c]['polylignes'])} tronçon(s), {len(par_couleur[c]['formes_fermees'])} forme(s))"
            for c in [couleur] + autres_lues) + f" ; réseau principal = {couleur} (seul fusionné dans plan.json), "
            "les autres couleurs sont dans par_couleur")
    elif marqueur == "auto":
        hors = [c for c in presentes if c not in lues]
        if hors:
            avert.append("couleur(s) présente(s) mais sans trait exploitable : " + ", ".join(hors))
    if annotations:
        avert.append(f"{len(annotations)} annotation(s) manuscrite(s) ignorée(s) (texte, flèches) : voir "
                     "annotations_ignorees et le PNG de contrôle")

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
        "formes_fermees": [_sortie_forme(f) for f in formes_sortie],
        "equipements_proposes": [{"forme": f["id"], "couleur": f["couleur"], "type": None,
                                  "position": [round(float(v), 2) for v in f["centre_m"]],
                                  "dimensions": [round(float(v), 2) for v in f["equipement"]["dimensions"]],
                                  "rotation": f["equipement"]["rotation"], "piece": f["piece"]} for f in formes_sortie],
        "annotations_ignorees": annotations,
        "couleurs_lues": list(par_couleur),
        "par_couleur": par_couleur,
        "erreur_reprojection_mm": round(err_rms, 3), "erreur_reprojection_max_mm": round(err_max, 3),
        "photo_px_par_mm": round(ppm_photo, 2), "photo_px_par_mm_min": round(ppm_locale, 2),
        "px_par_mm_travail": ppm, "largeur_trait_mm": par_couleur[couleur]["largeur_trait_mm"],
        "recalage_plan_imprime_mm": round(recalage_mm, 2), "gris_plan_photo": round(gris_plan, 3),
        "equilibre_canaux_bvr": list(equilibre),
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
    fe.ecrire_png(chemin_png, _image_controle(redresse, {c: lignes[c] for c in par_couleur}, par_couleur, formes_sortie,
                                              annotations, rects_plan, infos, hom, reperes, base, calque, ppm))

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
    formes = {f["id"] for f in calque.get("formes_fermees", [])}
    if any(pl.get(k) in formes for pl in calque["polylignes"] for k in ("de", "a")):
        avert.append("des lignes sont accrochées à des formes dessinées (F1…) : ajouter ces équipements à plan.json "
                     "(equipements_proposes, type à préciser) avant de générer")
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
def _image_controle(redresse, traits, par_couleur, formes, annotations, rects_eq, infos, hom, reperes, base, calque,
                    ppm) -> np.ndarray:
    gris = cv2.cvtColor(cv2.cvtColor(redresse, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    img = cv2.addWeighted(redresse, 0.35, gris, 0.65, 0)
    for c, t in traits.items():
        teinte = np.zeros_like(img)
        teinte[:] = TEINTE_CONTROLE[c]
        img[t] = cv2.addWeighted(img, 0.5, teinte, 0.5, 0)[t]

    def px(p_m):
        return tuple(int(round(v)) for v in fe.mm_vers_px(fe.m_vers_mm(p_m, base), ppm))

    def px_mm(p_mm):
        return tuple(int(round(v)) for v in fe.mm_vers_px(p_mm, ppm))

    polys = [(c, pl) for c, r in par_couleur.items() for pl in r["polylignes"]]
    accroches = {pl[k] for _, pl in polys for k in ("de", "a") if pl[k]}
    for eid, (eq, rect) in rects_eq.items():
        pts = np.array([px(p) for p in rect], np.int32).reshape(-1, 1, 2)
        couleur = (0, 170, 0) if eid in accroches else (200, 160, 0)
        cv2.polylines(img, [pts], True, couleur, 3 if eid in accroches else 1, cv2.LINE_AA)
    for f in formes:
        rect = fe.rectangle_equipement(f["equipement"])
        pts = np.array([px(p) for p in rect], np.int32).reshape(-1, 1, 2)
        cv2.polylines(img, [pts], True, TRAIT_CONTROLE[f["couleur"]], 3 if f["id"] in accroches else 2, cv2.LINE_AA)
    for an in annotations:
        x0, y0, x1, y1 = an["boite_mm"]
        cv2.rectangle(img, px_mm([x0, y0]), px_mm([x1, y1]), (150, 150, 150), 1, cv2.LINE_AA)
    principale = calque["marqueur"]
    for c, pl in polys:
        trait = TRAIT_CONTROLE[c]
        pts = np.array([px(p) for p in pl["points_m"]], np.int32).reshape(-1, 1, 2)
        cv2.polylines(img, [pts], False, trait if c != principale else (255, 0, 200), 2, cv2.LINE_AA)
        for p in pl["points_m"][1:-1]:
            cv2.circle(img, px(p), 3, trait if c != principale else (255, 0, 200), -1, cv2.LINE_AA)
        for cle, p in (("de", pl["points_m"][0]), ("a", pl["points_m"][-1])):
            couleur = (0, 170, 0) if pl[cle] else (0, 140, 255)
            cv2.circle(img, px(p), 7, couleur, 2, cv2.LINE_AA)
    for i in range(4):
        attendus = np.asarray(infos["reperes"][str(i)]["coins_mm"], dtype=float)
        trouves = cv2.perspectiveTransform(np.asarray(reperes[i], dtype=float).reshape(-1, 1, 2), hom).reshape(-1, 2)
        for a, t in zip(attendus, trouves):
            cv2.drawMarker(img, px_mm(a), (0, 170, 0), cv2.MARKER_CROSS, 12, 1)
            cv2.circle(img, px_mm(t), 3, (0, 0, 255), -1)
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    dessin = ImageDraw.Draw(pil)
    police = fe._police(16)
    petite = fe._police(13)
    resume = " · ".join(
        f"{c} : {len(r['polylignes'])} tronçon(s) {_f(r['longueur_totale_plan_m'])} m"
        + (f", {len(r['formes_fermees'])} forme(s)" if r["formes_fermees"] else "") for c, r in par_couleur.items())
    lignes_titre = [f"Réseau {calque['reseau']} · marqueur {principale} · {resume}",
                    f"reprojection {_f(calque['erreur_reprojection_mm'])} mm · {len(annotations)} annotation(s) ignorée(s)"
                    f" (cadres gris) · photo {_f(calque['photo_px_par_mm_min'], 1)} px/mm"]
    x0, y = int(30 * ppm), 4
    for texte in lignes_titre:
        dessin.rectangle([x0 - 4, y, x0 + dessin.textlength(texte, font=police) + 4, y + 21], fill=(255, 255, 255))
        dessin.text((x0, y + 2), texte, fill=(0, 0, 0), font=police)
        y += 22
    for c, pl in polys:
        x, y = px(pl["points_m"][len(pl["points_m"]) // 2])
        etiquette = pl["id"].rsplit("-", 1)[-1] if c == principale else c[0] + pl["id"].rsplit("-", 1)[-1]
        rgb = TRAIT_CONTROLE[c][::-1] if c != principale else (200, 0, 160)
        dessin.text((x + 6, y + 4), etiquette, fill=rgb, font=police)
    for f in formes:
        x, y = px(f["centre_m"])
        dessin.text((x + 8, y - 18), f["id"], fill=TRAIT_CONTROLE[f["couleur"]][::-1], font=police)
    for an in annotations:
        dessin.text(px_mm(an["boite_mm"][:2]), "A", fill=(120, 120, 120), font=petite)
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
    for c, res in r["par_couleur"].items():
        for p in res["polylignes"]:
            print(f"  [{c}] {p['id']} : {_f(p['longueur_plan_m'])} m, de {p['de'] or p['mur_de'] or '?'} "
                  f"à {p['a'] or p['mur_a'] or '?'}, confiance {_f(p['confiance'])}")
    for f in r["formes_fermees"]:
        print(f"  [{f['couleur']}] forme {f['id']} : centre ({_f(f['centre_m'][0])} ; {_f(f['centre_m'][1])}), "
              f"{_f(f['dimensions_m'][0])} × {_f(f['dimensions_m'][1])} m, {f['piece']}, confiance {_f(f['confiance'])}")
    if r["annotations_ignorees"]:
        print(f"  {len(r['annotations_ignorees'])} annotation(s) ignorée(s)")
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
