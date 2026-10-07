"""Feuille A4 à imprimer pour tracer UN réseau au marqueur (Lot 6 du skill froid-plan-2d).

Le frigoriste imprime la feuille (plan de base en gris clair + 4 repères ArUco aux coins), trace un
réseau au marqueur de couleur, la photographie ; `lire_photo.py` relit ensuite la photo. Toutes les
mesures de la photo sont faites par rapport aux repères : une impression réduite uniformément
(« ajuster à la page ») reste juste.

Correspondance plan → feuille (la même que celle du plan draw.io, fournie par `plan-base.json`) :
    point du modèle (x_m, y_m)  →  origine_mm + (x_m, y_m) × 1000 / S   (mm, origine coin haut-gauche
    de la page, x vers la droite, y vers le bas).

Usage (racine du dépôt) :
    python .claude/skills/froid-plan-2d/scripts/feuille.py <dossier_plan> --reseau <cle> [--type aspiration] [--sans-pdf]
Sorties : <dossier_plan>/feuilles/feuille-<reseau>.png, .pdf, .json
Réseau = un calque réseau standard (froid_cuivres, clim_cuivres, electricite) ou une clé de calques_libres ;
sans --type, type supposé (aspiration, clim_gaz, cable) ou clé du calque libre.
Codes de retour : 0 feuille produite et contrôlée ; 1 contenu invalide ou contrôle en échec ; 2 fichier manquant.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import modele as mod  # noqa: E402  (rectangle d'un mur : le même que celui du plan draw.io)

# --- Constantes de la feuille -------------------------------------------------------------------
PX_PAR_MM = 8                         # résolution du rendu raster (8 px/mm = 203,2 dpi)
A4_MM = (210.0, 297.0)                # largeur, hauteur en portrait
A4_PT = (595.28, 841.89)
PT_PAR_MM = 72.0 / 25.4
GRIS_PLAN = 158                       # #9E9E9E
GRIS_TEXTE = 60                       # textes du cadre et barre d'échelle (gris foncé)
TRAIT_PLAN_MM = 0.5
REPERE_COTE_MM = 16.0
REPERE_CENTRE_MM = 14.0               # centre des repères à 14 mm des bords : le carré occupe 6 à 22 mm
REPERE_BORDURE_MM = 2.0               # bordure blanche autour du repère (4 à 24 mm : libre jusqu'à l'origine du plan)
DICTIONNAIRE_ARUCO = cv2.aruco.DICT_4X4_50
POSITIONS_REPERES = {0: "haut-gauche", 1: "haut-droite", 2: "bas-droite", 3: "bas-gauche"}
BANDE_MARGE_X_MM = 30.0               # cadre d'identification : x de 30 mm à largeur − 30 mm
BANDE_HAUT_MM = 30.0                  # y de hauteur − 30 mm ...
BANDE_BAS_MM = 8.0                    # ... à hauteur − 8 mm
SEUIL_MASQUAGE_MM2 = 15.0            # au-delà, avertissement : un repère ou le cadre cache une partie du plan
TOLERANCE_REPERE_PNG_MM = 0.3
TOLERANCE_REPERE_PDF_MM = 0.5
TOLERANCE_PAGE_PT = 0.5
EPAISSEUR_MUR_DEFAUT_M = 0.20
DIMENSIONS_DEFAUT = {"evaporateur": (1.2, 0.5), "centrale": (1.5, 0.8), "groupe": (1.0, 0.6),
                     "condenseur": (1.2, 0.5), "split": (0.9, 0.3), "moteur": (0.9, 0.35),
                     "tableau": (0.6, 0.2), "autre": (0.5, 0.5)}
CONSIGNES = ("Tracer ce réseau au marqueur de couleur (rouge, bleu ou vert), un trait continu par tronçon"
             " · Une feuille par réseau · Photo prise de dessus, les 4 repères visibles, sans flash"
             " · Imprimer à 100 % ; si l'imprimante coupe les repères, choisir « ajuster à la page »"
             " (les mesures restent justes)")
# Type de ligne supposé quand --type est absent, pour les calques standard qui portent un réseau.
TYPE_PAR_DEFAUT = {"froid_cuivres": "aspiration", "clim_cuivres": "clim_gaz", "electricite": "cable"}
MOTIF_RESEAU = re.compile(r"^[A-Za-z0-9_-]{1,60}$")


class ErreurFeuille(Exception):
    """Erreur lisible ; `code` = code de retour de la ligne de commande (1 contenu/contrôle, 2 fichier manquant)."""

    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


# --- Géométrie de la page -----------------------------------------------------------------------
def page_mm(orientation: str) -> tuple[float, float]:
    """(largeur, hauteur) de la page A4 en mm selon l'orientation (« paysage » ou « portrait »)."""
    if orientation == "paysage":
        return A4_MM[1], A4_MM[0]
    if orientation == "portrait":
        return A4_MM
    raise ErreurFeuille(f"orientation inconnue : {orientation!r} (attendu « paysage » ou « portrait »)")


def page_pt(orientation: str) -> tuple[float, float]:
    return (A4_PT[1], A4_PT[0]) if orientation == "paysage" else A4_PT


def centres_reperes_mm(page: tuple[float, float]) -> dict[int, tuple[float, float]]:
    l, h = page
    c = REPERE_CENTRE_MM
    return {0: (c, c), 1: (l - c, c), 2: (l - c, h - c), 3: (c, h - c)}


def coins_reperes_mm(page: tuple[float, float]) -> dict[int, list[list[float]]]:
    """Coins de chaque repère dans l'ordre d'OpenCV : haut-gauche, haut-droite, bas-droite, bas-gauche."""
    d = REPERE_COTE_MM / 2
    return {i: [[cx - d, cy - d], [cx + d, cy - d], [cx + d, cy + d], [cx - d, cy + d]]
            for i, (cx, cy) in centres_reperes_mm(page).items()}


def zones_reperes_mm(page: tuple[float, float]) -> dict[int, tuple[float, float, float, float]]:
    """Carré du repère + bordure blanche : (x0, y0, x1, y1) en mm."""
    d = REPERE_COTE_MM / 2 + REPERE_BORDURE_MM
    return {i: (cx - d, cy - d, cx + d, cy + d) for i, (cx, cy) in centres_reperes_mm(page).items()}


def zone_bande_mm(page: tuple[float, float]) -> tuple[float, float, float, float]:
    l, h = page
    return (BANDE_MARGE_X_MM, h - BANDE_HAUT_MM, l - BANDE_MARGE_X_MM, h - BANDE_BAS_MM)


def mm_vers_px(v, ppm: float = PX_PAR_MM):
    """mm → coordonnée pixel (convention OpenCV : centre du pixel i en i)."""
    return np.asarray(v, dtype=float) * ppm - 0.5


def px_vers_mm(v, ppm: float = PX_PAR_MM):
    return (np.asarray(v, dtype=float) + 0.5) / ppm


def m_vers_mm(points_m, base: dict) -> np.ndarray:
    """Points du modèle (m) → position sur la feuille (mm)."""
    p = np.asarray(points_m, dtype=float)
    return np.asarray(base["origine_mm"], dtype=float) + p * 1000.0 / float(base["S"])


def mm_vers_m(points_mm, base: dict) -> np.ndarray:
    p = np.asarray(points_mm, dtype=float)
    return (p - np.asarray(base["origine_mm"], dtype=float)) * float(base["S"]) / 1000.0


def longueur_barre_m(S: float) -> int:
    """Barre d'échelle : 1 m jusqu'à 1:100, 2 m jusqu'à 1:200, 5 m au-delà."""
    if S <= 100:
        return 1
    if S <= 200:
        return 2
    return 5


# --- Géométrie du plan (schéma de plan.json, dict brut) ---------------------------------------------------
def _rotation(points: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rotation (degrés, sens horaire à l'écran puisque y va vers le bas)."""
    a = math.radians(angle_deg or 0.0)
    r = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    return points @ r.T


def dimensions_equipement(eq: dict) -> tuple[float, float]:
    dims = eq.get("dimensions")
    if dims and len(dims) == 2:
        return float(dims[0]), float(dims[1])
    return DIMENSIONS_DEFAUT.get(eq.get("type", "autre"), DIMENSIONS_DEFAUT["autre"])


def rectangle_equipement(eq: dict) -> np.ndarray:
    """4 coins (m) du rectangle de l'équipement (centre, dimensions [longueur, profondeur], rotation)."""
    lo, pr = dimensions_equipement(eq)
    coins = np.array([[-lo / 2, -pr / 2], [lo / 2, -pr / 2], [lo / 2, pr / 2], [-lo / 2, pr / 2]])
    return _rotation(coins, float(eq.get("rotation") or 0.0)) + np.asarray(eq["position"], dtype=float)


def rectangle_mur(mur: dict) -> np.ndarray:
    """4 coins (m) du mur, `alignement` (axe, gauche, droite) appliqué : `modele.coins_mur`, le rectangle que dessine
    `drawio.py` ; épaisseur absente = défaut du modèle par type de mur (extérieur 0,20, cloison 0,10)."""
    e = mur.get("epaisseur") or mod.EPAISSEUR_PAR_TYPE_MUR.get(mur.get("type") or "exterieur", EPAISSEUR_MUR_DEFAUT_M)
    m = {**mur, "de": (float(mur["de"][0]), float(mur["de"][1])), "a": (float(mur["a"][0]), float(mur["a"][1])),
         "epaisseur": float(e)}
    return np.array(mod.coins_mur(m), dtype=float)


def _decaler_polygone(poly, d: float) -> np.ndarray:
    """Décale un polygone simple de `d` vers l'intérieur (sommets en onglet)."""
    p = np.asarray(poly, dtype=float)
    n = len(p)
    if n < 3:
        return p
    aire = 0.5 * sum(p[i, 0] * p[(i + 1) % n, 1] - p[(i + 1) % n, 0] * p[i, 1] for i in range(n))
    signe = 1.0 if aire > 0 else -1.0
    lignes = []
    for i in range(n):
        a, b = p[i], p[(i + 1) % n]
        t = b - a
        lt = np.linalg.norm(t)
        t = t / lt if lt > 1e-12 else np.array([1.0, 0.0])
        normale = signe * np.array([-t[1], t[0]])
        lignes.append((a + normale * d, t))
    sortie = []
    for i in range(n):
        (p1, t1), (p2, t2) = lignes[i - 1], lignes[i]
        det = t1[0] * (-t2[1]) - t1[1] * (-t2[0])
        if abs(det) < 1e-9:
            sortie.append(p2)
            continue
        rhs = p2 - p1
        s = (rhs[0] * (-t2[1]) - rhs[1] * (-t2[0])) / det
        sortie.append(p1 + s * t1)
    return np.array(sortie)


def _porte_m(porte: dict, n_arc: int = 24) -> list[np.ndarray]:
    """Porte : ouverture le long du mur, battant perpendiculaire, arc d'un quart de tour (polylignes en m)."""
    p = np.asarray(porte["position"], dtype=float)
    w = float(porte.get("largeur") or 0.9)
    a = math.radians(float(porte.get("orientation") or 0.0))
    u = np.array([math.cos(a), math.sin(a)])
    v = np.array([-math.sin(a), math.cos(a)])
    angles = np.linspace(0, math.pi / 2, n_arc)
    arc = np.array([p + w * (math.cos(t) * u + math.sin(t) * v) for t in angles])
    return [np.array([p, p + w * u]), np.array([p, p + w * v]), arc]


def _fenetre_m(fen: dict, murs: dict) -> list[np.ndarray]:
    c = np.asarray(fen["position"], dtype=float)
    w = float(fen.get("largeur") or 1.0)
    mur = murs.get(fen.get("dans"))
    e = float(mur.get("epaisseur") or EPAISSEUR_MUR_DEFAUT_M) if mur else EPAISSEUR_MUR_DEFAUT_M
    a = math.radians(float(fen.get("orientation") or 0.0))
    u = np.array([math.cos(a), math.sin(a)])
    v = np.array([-math.sin(a), math.cos(a)])
    rect = np.array([c - u * w / 2 - v * e / 2, c + u * w / 2 - v * e / 2,
                     c + u * w / 2 + v * e / 2, c - u * w / 2 + v * e / 2, c - u * w / 2 - v * e / 2])
    return [rect, np.array([c - u * w / 2, c + u * w / 2])]


def elements_plan_m(plan: dict) -> dict[str, list]:
    """Toutes les polylignes du plan de base (m) : {"murs": [...], "chambres": [...], ...}."""
    murs_par_id = {m.get("id"): m for m in plan.get("murs", [])}
    out = {"murs": [], "chambres": [], "portes": [], "fenetres": [], "equipements": []}
    for mur in plan.get("murs", []):
        r = rectangle_mur(mur)
        out["murs"].append(np.vstack([r, r[:1]]))
    for cf in plan.get("chambres_froides", []):
        poly = np.asarray(cf.get("polygone") or [], dtype=float)
        if len(poly) >= 3:
            out["chambres"].append(np.vstack([poly, poly[:1]]))
            interieur = _decaler_polygone(poly, float(cf.get("panneau_mm") or 80) / 1000.0)
            out["chambres"].append(np.vstack([interieur, interieur[:1]]))
        if cf.get("porte"):
            out["portes"].extend(_porte_m(cf["porte"]))
    for porte in plan.get("portes", []):
        out["portes"].extend(_porte_m(porte))
    for fen in plan.get("fenetres", []):
        out["fenetres"].extend(_fenetre_m(fen, murs_par_id))
    for eq in plan.get("equipements", []):
        r = rectangle_equipement(eq)
        out["equipements"].append(np.vstack([r, r[:1]]))
    return out


# --- Rendu ---------------------------------------------------------------------------------------
def _police(taille_px: int, gras: bool = False):
    noms = ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if gras else ["arial.ttf", "DejaVuSans.ttf"]
    for nom in noms:
        for chemin in (nom, str(Path("C:/Windows/Fonts") / nom)):
            try:
                return ImageFont.truetype(chemin, taille_px)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=taille_px)
    except TypeError:  # Pillow ancien
        return ImageFont.load_default()


def _tracer(img: np.ndarray, pts_mm, couleur: int, epaisseur_mm: float, ferme: bool = False,
            ppm: float = PX_PAR_MM) -> None:
    pts = np.round(mm_vers_px(pts_mm, ppm) * 16).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(img, [pts], ferme, int(couleur), max(1, int(round(epaisseur_mm * ppm))), cv2.LINE_AA, shift=4)


def _rect_px(zone_mm, ppm: float = PX_PAR_MM) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = zone_mm
    return int(round(x0 * ppm)), int(round(y0 * ppm)), int(round(x1 * ppm)), int(round(y1 * ppm))


def _boite(points_mm: np.ndarray) -> tuple[float, float, float, float]:
    return float(points_mm[:, 0].min()), float(points_mm[:, 1].min()), float(points_mm[:, 0].max()), float(points_mm[:, 1].max())


def _se_chevauchent(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _envelopper(texte: str, police, largeur_px: float, dessin: ImageDraw.ImageDraw) -> list[str]:
    lignes, courante = [], ""
    for mot in texte.split(" "):
        essai = (courante + " " + mot).strip()
        if dessin.textlength(essai, font=police) <= largeur_px or not courante:
            courante = essai
        else:
            lignes.append(courante)
            courante = mot
    if courante:
        lignes.append(courante)
    return lignes


def _format_mm(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def dessiner_feuille(plan: dict, base: dict, reseau: str, type_ligne: str | None, date: str,
                     dossier: str) -> tuple[np.ndarray, dict]:
    """Rend la feuille (niveaux de gris, 8 px/mm). Renvoie (image, infos) — infos sans les chemins."""
    S = float(base["S"])
    page = page_mm(base["orientation"])
    l_px, h_px = int(round(page[0] * PX_PAR_MM)), int(round(page[1] * PX_PAR_MM))
    img = np.full((h_px, l_px), 255, np.uint8)
    avertissements: list[str] = []

    # 1. Plan de base en gris clair (traits 0,5 mm)
    elements = elements_plan_m(plan)
    tous_mm = []
    for groupe, polys in elements.items():
        for poly in polys:
            pts_mm = m_vers_mm(poly, base)
            tous_mm.append(pts_mm)
            _tracer(img, pts_mm, GRIS_PLAN, TRAIT_PLAN_MM)
    zone_plan = _boite(np.vstack(tous_mm)) if tous_mm else None
    if zone_plan is None:
        avertissements.append("plan.json ne contient aucun élément dessinable (murs, chambres, équipements…)")
    else:
        if zone_plan[0] < 0 or zone_plan[1] < 0 or zone_plan[2] > page[0] or zone_plan[3] > page[1]:
            avertissements.append("le plan déborde de la feuille : vérifier S, l'orientation et origine_mm de plan-base.json")
        for i, z in zones_reperes_mm(page).items():
            x0, y0, x1, y1 = _rect_px(z)
            encre_mm2 = float((img[max(0, y0):y1, max(0, x0):x1] < 250).sum()) / PX_PAR_MM ** 2
            if encre_mm2 > SEUIL_MASQUAGE_MM2:
                avertissements.append(f"le repère {i} ({POSITIONS_REPERES[i]}) et sa bordure blanche masquent "
                                      f"{encre_mm2:.0f} mm² du plan de base")
        x0, y0, x1, y1 = _rect_px(zone_bande_mm(page))
        encre_mm2 = float((img[y0:y1, x0:x1] < 250).sum()) / PX_PAR_MM ** 2
        if encre_mm2 > SEUIL_MASQUAGE_MM2:
            avertissements.append(f"le cadre d'identification (bande du bas) masque {encre_mm2:.0f} mm² du plan de base")

    # 2. Repères ArUco (bordure blanche de 2 mm, puis le repère)
    dico = cv2.aruco.getPredefinedDictionary(DICTIONNAIRE_ARUCO)
    cote_px = int(round(REPERE_COTE_MM * PX_PAR_MM))
    for i, z in zones_reperes_mm(page).items():
        x0, y0, x1, y1 = _rect_px(z)
        img[max(0, y0):y1, max(0, x0):x1] = 255
        coin = coins_reperes_mm(page)[i][0]
        cx, cy = int(round(coin[0] * PX_PAR_MM)), int(round(coin[1] * PX_PAR_MM))
        img[cy:cy + cote_px, cx:cx + cote_px] = cv2.aruco.generateImageMarker(dico, i, cote_px, borderBits=1)

    # 3. Cadre d'identification (fond blanc, bordure gris foncé)
    bande = zone_bande_mm(page)
    bx0, by0, bx1, by1 = _rect_px(bande)
    img[by0:by1, bx0:bx1] = 255
    cv2.rectangle(img, (bx0, by0), (bx1 - 1, by1 - 1), GRIS_TEXTE, 2)

    # 4. Barre d'échelle (à droite dans le cadre)
    n_m = longueur_barre_m(S)
    l_barre_mm = n_m * 1000.0 / S
    barre_x1 = bande[2] - 6.0
    barre_x0 = barre_x1 - l_barre_mm
    barre_y = bande[1] + 12.0
    hauteur_barre = 1.2
    x0p, x1p = int(round(barre_x0 * PX_PAR_MM)), int(round(barre_x1 * PX_PAR_MM))
    y0p, y1p = int(round(barre_y * PX_PAR_MM)), int(round((barre_y + hauteur_barre) * PX_PAR_MM))
    img[y0p:y1p, x0p:x1p] = GRIS_TEXTE
    for xt in (x0p, x1p - 2):
        img[y0p - 12:y1p + 12, xt:xt + 2] = GRIS_TEXTE
    barre = {"longueur_m": n_m, "longueur_mm": round(l_barre_mm, 3),
             "de_mm": [round(barre_x0, 3), round(barre_y, 3)], "a_mm": [round(barre_x1, 3), round(barre_y, 3)],
             "hauteur_mm": hauteur_barre}

    # 5. Textes (Pillow : accents) — identifiants des équipements + cadre
    pil = Image.fromarray(img)
    dessin = ImageDraw.Draw(pil)
    police_eq = _police(int(round(2.0 * PX_PAR_MM)))
    for eq in plan.get("equipements", []):
        if eq.get("id") and eq.get("position") is not None:
            cx, cy = mm_vers_px(m_vers_mm(eq["position"], base))
            dessin.text((float(cx), float(cy)), str(eq["id"]), fill=GRIS_PLAN, font=police_eq, anchor="mm")
    libelle = f"{n_m} m = {_format_mm(l_barre_mm)} mm"
    police_barre = _police(int(round(2.4 * PX_PAR_MM)))
    dessin.text(((barre_x0 + barre_x1) / 2 * PX_PAR_MM, (barre_y - 2.2) * PX_PAR_MM), libelle,
                fill=GRIS_TEXTE, font=police_barre, anchor="ms")
    dessin.text(((barre_x0 + barre_x1) / 2 * PX_PAR_MM, (barre_y + hauteur_barre + 4.6) * PX_PAR_MM),
                f"1:{int(S) if float(S).is_integer() else S}", fill=GRIS_TEXTE, font=police_barre, anchor="ms")

    titre = f"Réseau : {reseau}" + (f" ({type_ligne})" if type_ligne else "") + \
        f"  ·  Échelle 1:{int(S) if float(S).is_integer() else S}  ·  Dossier : {dossier}  ·  {date}"
    zone_texte_px = ((bande[0] + 3) * PX_PAR_MM, (bande[1] + 2) * PX_PAR_MM,
                     (barre_x0 - 8) * PX_PAR_MM, (bande[3] - 1.5) * PX_PAR_MM)
    largeur_txt = zone_texte_px[2] - zone_texte_px[0]
    for facteur in (1.0, 0.9, 0.8, 0.7, 0.6):
        p_titre = _police(int(round(3.4 * PX_PAR_MM * facteur)), gras=True)
        p_cons = _police(int(round(2.8 * PX_PAR_MM * facteur)))
        l_titre = _envelopper(titre, p_titre, largeur_txt, dessin)
        l_cons = _envelopper(CONSIGNES, p_cons, largeur_txt, dessin)
        pas_t, pas_c = 3.4 * PX_PAR_MM * facteur * 1.25, 2.8 * PX_PAR_MM * facteur * 1.3
        if len(l_titre) * pas_t + 0.6 * PX_PAR_MM + len(l_cons) * pas_c <= zone_texte_px[3] - zone_texte_px[1]:
            break
    y = zone_texte_px[1]
    for ligne in l_titre:
        dessin.text((zone_texte_px[0], y), ligne, fill=0, font=p_titre)
        y += pas_t
    y += 0.6 * PX_PAR_MM
    for ligne in l_cons:
        dessin.text((zone_texte_px[0], y), ligne, fill=GRIS_TEXTE, font=p_cons)
        y += pas_c
    img = np.array(pil)

    infos = {
        "version": 1,
        "dossier": dossier,
        "reseau": reseau,
        "type_ligne": type_ligne,
        "S": base["S"],
        "orientation": base["orientation"],
        "origine_mm": [float(v) for v in base["origine_mm"]],
        "page_mm": [page[0], page[1]],
        "px_par_mm": PX_PAR_MM,
        "reperes": {str(i): {"position": POSITIONS_REPERES[i], "cote_mm": REPERE_COTE_MM,
                             "centre_mm": list(centres_reperes_mm(page)[i]), "coins_mm": coins_reperes_mm(page)[i],
                             "zone_blanche_mm": list(zones_reperes_mm(page)[i])}
                    for i in range(4)},
        "dictionnaire_aruco": "DICT_4X4_50",
        "barre_echelle": barre,
        "cadre_identification_mm": list(bande),
        "zone_plan_mm": [round(v, 3) for v in zone_plan] if zone_plan else None,
        "date": date,
    }
    return img, {"infos": infos, "avertissements": avertissements}


# --- Détection des repères (partagée avec lire_photo.py) ---------------------------------------
def _parametres_detection():
    p = cv2.aruco.DetectorParameters()
    p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    p.cornerRefinementWinSize = 5
    p.cornerRefinementMaxIterations = 50
    p.cornerRefinementMinAccuracy = 0.01
    p.adaptiveThreshWinSizeMin = 3
    p.adaptiveThreshWinSizeMax = 63
    p.adaptiveThreshWinSizeStep = 6
    p.minMarkerPerimeterRate = 0.02
    p.polygonalApproxAccuracyRate = 0.05
    return p


def detecter_reperes(image: np.ndarray, ids_attendus=(0, 1, 2, 3), cote_max_px: int = 2200) -> dict[int, np.ndarray]:
    """Détecte les repères ArUco (DICT_4X4_50). Renvoie {id: coins (4, 2) en px de l'image d'origine}.

    Essais successifs : image en gris, gris égalisé (CLAHE), puis image réduite (si grande) ; les coins
    trouvés sur une image réduite sont affinés en sous-pixel sur l'image d'origine.
    """
    gris = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    detecteur = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(DICTIONNAIRE_ARUCO), _parametres_detection())
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    essais = []
    plus_grand = max(gris.shape)
    if plus_grand > cote_max_px:
        f = cote_max_px / plus_grand
        petit = cv2.resize(gris, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        essais += [(petit, f), (clahe.apply(petit), f)]
    essais += [(gris, 1.0), (clahe.apply(gris), 1.0)]
    if plus_grand > 1200:
        f = 1000 / plus_grand
        essais.append((cv2.resize(gris, None, fx=f, fy=f, interpolation=cv2.INTER_AREA), f))
    trouves: dict[int, np.ndarray] = {}
    for img, f in essais:
        coins, ids, _ = detecteur.detectMarkers(img)
        if ids is None:
            continue
        for c, i in zip(coins, ids.ravel()):
            i = int(i)
            if i not in ids_attendus or i in trouves:
                continue
            pts = c.reshape(4, 2).astype(np.float64)
            if f != 1.0:
                pts = (pts + 0.5) / f - 0.5
                cote = float(np.mean(np.linalg.norm(pts - np.roll(pts, 1, axis=0), axis=1)))
                fen = int(max(3, min(15, round(cote / 12))))
                raffine = pts.astype(np.float32).reshape(-1, 1, 2).copy()
                cv2.cornerSubPix(gris, raffine, (fen, fen), (-1, -1),
                                 (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.01))
                pts = raffine.reshape(4, 2).astype(np.float64)
            trouves[i] = pts
        if all(i in trouves for i in ids_attendus):
            break
    return trouves


def _controler_reperes(image: np.ndarray, page: tuple[float, float], ppm: float, tolerance_mm: float,
                       origine: str) -> list[str]:
    erreurs = []
    trouves = detecter_reperes(image)
    attendus = coins_reperes_mm(page)
    for i in range(4):
        if i not in trouves:
            erreurs.append(f"{origine} : repère {i} ({POSITIONS_REPERES[i]}) non détecté")
            continue
        ecart = np.abs(px_vers_mm(trouves[i], ppm) - np.asarray(attendus[i])).max()
        if ecart > tolerance_mm:
            erreurs.append(f"{origine} : repère {i} décalé de {ecart:.2f} mm (tolérance {tolerance_mm} mm)")
    return erreurs


# --- Fichiers ------------------------------------------------------------------------------------
def _lire_json(chemin: Path) -> dict:
    if not chemin.is_file():
        raise ErreurFeuille(f"fichier manquant : {chemin}", code=2)
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErreurFeuille(f"{chemin.name} n'est pas un JSON valide : {e}") from e


def charger_plan_base(dossier_plan: Path) -> dict:
    base = _lire_json(Path(dossier_plan) / "plan-base.json")
    try:
        S = float(base["S"])
        orientation = base["orientation"]
        origine = [float(v) for v in base["origine_mm"]]
    except (KeyError, TypeError, ValueError) as e:
        raise ErreurFeuille(f"plan-base.json incomplet (attendu S, orientation, origine_mm) : {e}") from e
    if S <= 0 or len(origine) != 2:
        raise ErreurFeuille("plan-base.json : S doit être > 0 et origine_mm doit avoir 2 valeurs")
    page_mm(orientation)
    return {"S": base["S"], "orientation": orientation, "origine_mm": origine}


def chemins_feuille(dossier_plan, reseau: str) -> dict[str, Path]:
    d = Path(dossier_plan) / "feuilles"
    return {"png": d / f"feuille-{reseau}.png", "pdf": d / f"feuille-{reseau}.pdf", "json": d / f"feuille-{reseau}.json"}


def lire_image(chemin) -> np.ndarray | None:
    """Lecture d'image compatible avec les chemins accentués sous Windows (BGR ou gris selon le fichier)."""
    try:
        donnees = np.fromfile(str(chemin), dtype=np.uint8)
    except OSError:
        return None
    if donnees.size == 0:
        return None
    return cv2.imdecode(donnees, cv2.IMREAD_UNCHANGED)


def ecrire_png(chemin, image: np.ndarray) -> None:
    ok, tampon = cv2.imencode(".png", image)
    if not ok:
        raise ErreurFeuille(f"échec d'encodage PNG : {chemin}")
    tampon.tofile(str(chemin))


def _ecrire_pdf(png: Path, pdf: Path, orientation: str) -> None:
    import pymupdf
    l, h = page_pt(orientation)
    doc = pymupdf.open()
    page = doc.new_page(width=l, height=h)
    page.insert_image(page.rect, filename=str(png))
    doc.save(str(pdf), deflate=True)
    doc.close()


def _controler_pdf(pdf: Path, orientation: str, page: tuple[float, float]) -> tuple[list[str], dict]:
    import pymupdf
    erreurs, mesures = [], {}
    doc = pymupdf.open(str(pdf))
    try:
        if doc.page_count != 1:
            erreurs.append(f"PDF : {doc.page_count} pages (attendu 1)")
        p = doc[0]
        attendu = page_pt(orientation)
        mesures["page_pt"] = [round(p.rect.width, 3), round(p.rect.height, 3)]
        if abs(p.rect.width - attendu[0]) > TOLERANCE_PAGE_PT or abs(p.rect.height - attendu[1]) > TOLERANCE_PAGE_PT:
            erreurs.append(f"PDF : page {p.rect.width:.2f} × {p.rect.height:.2f} pt (attendu A4 {attendu[0]} × {attendu[1]} pt)")
        infos_img = p.get_image_info()
        if len(infos_img) != 1:
            erreurs.append(f"PDF : {len(infos_img)} images sur la page (attendu 1)")
        else:
            bb = infos_img[0]["bbox"]
            mesures["image_bbox_pt"] = [round(v, 3) for v in bb]
            if max(abs(bb[0]), abs(bb[1]), abs(bb[2] - p.rect.width), abs(bb[3] - p.rect.height)) > TOLERANCE_PAGE_PT:
                erreurs.append(f"PDF : l'image ne couvre pas exactement la page ({bb})")
        zoom = PX_PAR_MM / PT_PAR_MM
        pix = p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY, alpha=False)
        raster = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)[:, :pix.width]
        ppm_x = pix.width / page[0]
        erreurs += _controler_reperes(raster, page, ppm_x, TOLERANCE_REPERE_PDF_MM, "PDF")
    finally:
        doc.close()
    return erreurs, mesures


def type_du_reseau(plan: dict, reseau: str, type_ligne: str | None) -> tuple[str, list[str]]:
    """Type de ligne retenu pour la feuille : `--type` s'il est donné ; sinon la clé elle-même pour un calque
    libre, ou le type supposé d'un calque standard (avec avertissement). Tout autre réseau : erreur."""
    libres = [c.get("cle") for c in plan.get("calques_libres", []) if c.get("cle")]
    if reseau not in libres and reseau not in TYPE_PAR_DEFAUT:
        raise ErreurFeuille(f"réseau inconnu : « {reseau} ». Attendu un calque réseau standard "
                            f"({', '.join(TYPE_PAR_DEFAUT)}) ou une clé de calques_libres du plan"
                            + (f" ({', '.join(libres)})" if libres else " (aucune déclarée)"))
    if type_ligne:
        return type_ligne, []
    if reseau in libres:
        return reseau, []
    suppose = TYPE_PAR_DEFAUT[reseau]
    return suppose, [f"type supposé « {suppose} » pour le réseau « {reseau} », précise --type si c'est un autre réseau"]


def fabriquer_feuille(dossier_plan, reseau: str, type_ligne: str | None = None, pdf: bool = True,
                      date: str | None = None) -> dict:
    """Fabrique et contrôle la feuille d'un réseau. Renvoie {png, pdf, json, avertissements, controle}.

    Lève ErreurFeuille (code 2 si plan.json / plan-base.json manquent, 1 si contenu invalide ou contrôle en échec).
    """
    dossier_plan = Path(dossier_plan)
    if not MOTIF_RESEAU.match(reseau or ""):
        raise ErreurFeuille(f"clé de réseau invalide : {reseau!r} (lettres, chiffres, _ et - uniquement)")
    plan = _lire_json(dossier_plan / "plan.json")
    base = charger_plan_base(dossier_plan)
    type_ligne, avert_type = type_du_reseau(plan, reseau, type_ligne)
    date = date or dt.date.today().isoformat()
    dossier = str(plan.get("dossier") or dossier_plan.parent.name or dossier_plan.name)
    image, rendu = dessiner_feuille(plan, base, reseau, type_ligne, date, dossier)
    rendu["avertissements"] = avert_type + rendu["avertissements"]
    chemins = chemins_feuille(dossier_plan, reseau)
    chemins["png"].parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image).save(str(chemins["png"]), dpi=(PX_PAR_MM * 25.4, PX_PAR_MM * 25.4))

    page = page_mm(base["orientation"])
    controle = {"png_dimensions_px": [int(image.shape[1]), int(image.shape[0])]}
    attendu_px = (int(round(page[0] * PX_PAR_MM)), int(round(page[1] * PX_PAR_MM)))
    erreurs = []
    relu = lire_image(chemins["png"])
    if relu is None or (relu.shape[1], relu.shape[0]) != attendu_px:
        erreurs.append(f"PNG : dimensions {None if relu is None else relu.shape[1::-1]} (attendu {attendu_px})")
    else:
        erreurs += _controler_reperes(relu, page, PX_PAR_MM, TOLERANCE_REPERE_PNG_MM, "PNG")
    if pdf:
        _ecrire_pdf(chemins["png"], chemins["pdf"], base["orientation"])
        e_pdf, mesures = _controler_pdf(chemins["pdf"], base["orientation"], page)
        erreurs += e_pdf
        controle.update(mesures)
    controle["erreurs"] = erreurs
    infos = dict(rendu["infos"])
    infos["fichiers"] = {"png": chemins["png"].name, "pdf": chemins["pdf"].name if pdf else None}
    infos["avertissements"] = rendu["avertissements"]
    chemins["json"].write_text(json.dumps(infos, ensure_ascii=False, indent=2), encoding="utf-8")
    if erreurs:
        raise ErreurFeuille("contrôle de la feuille en échec : " + " ; ".join(erreurs))
    return {"png": str(chemins["png"]), "pdf": str(chemins["pdf"]) if pdf else None, "json": str(chemins["json"]),
            "avertissements": rendu["avertissements"], "controle": controle}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Feuille A4 à imprimer pour tracer un réseau au marqueur (Lot 6).")
    ap.add_argument("dossier_plan", help="dossier plan/ contenant plan.json et plan-base.json")
    ap.add_argument("--reseau", required=True, help="clé du réseau (ex. froid_cuivres, electricite, eau_chaude)")
    ap.add_argument("--type", dest="type_ligne", default=None, help="type de ligne (défaut : la clé pour un calque libre ; aspiration, "
                    "clim_gaz ou cable pour froid_cuivres, clim_cuivres, electricite)")
    ap.add_argument("--sans-pdf", action="store_true", help="ne produit que le PNG et le JSON")
    args = ap.parse_args(argv)
    try:
        r = fabriquer_feuille(args.dossier_plan, args.reseau, args.type_ligne, pdf=not args.sans_pdf)
    except ErreurFeuille as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return e.code
    print(f"Feuille du réseau « {args.reseau} » produite et contrôlée :")
    for cle in ("pdf", "png", "json"):
        if r[cle]:
            print(f"  {cle.upper()} : {r[cle]}")
    for a in r["avertissements"]:
        print(f"  AVERTISSEMENT : {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
