"""Échelle des plans 2D : la règle n° 1 (« 15 m de cuivre annoncés = 15 m réels »).

C'est le SEUL module du skill qui convertit des mètres (modèle `plan.json`) en pixels draw.io, et retour.
Tous les autres scripts passent par `Echelle.m_vers_px` / `Echelle.px_vers_m` (ou `longueur_px` /
`longueur_m` pour une longueur), jamais par un facteur écrit à la main.

Conventions :
- draw.io imprime à 100 px par pouce : 1 mm = 100 / 25,4 = 3,937 px (`PX_PAR_MM`). Une page A4 vaut
  827 × 1169 px (portrait) ou 1169 × 827 px (paysage).
- Échelle normalisée 1:S, S pris dans `ECHELLES`. 1 m du modèle = 1000 × PX_PAR_MM / S px
  (1:100 → 39,370 px/m ; 1:50 → 78,740 ; 1:200 → 19,685).
- Page : marge de 10 mm sur les quatre côtés ; cartouche de 22 mm en bas ; « zone utile » = le reste.
  Autour du dessin, réserve de 14 mm (cotes extérieures, étiquettes) : « zone de dessin ».
- Repère du modèle : x vers la droite, y vers le bas, en mètres. L'origine (0, 0) du modèle tombe en
  `origine_px` sur la page (arrondie à 0,01 px, comme toute la géométrie écrite dans le XML).

Usage :
    from echelle import choisir_echelle
    ech = choisir_echelle(plan.bbox(), plan.page)     # S, orientation, origine (dessin centré)
    ech.m_vers_px(12.5, 0.0)  → (x_px, y_px)
    ech.px_vers_m(x_px, y_px) → (12.5, 0.0)
"""
from __future__ import annotations

import math

# ---------- constantes ----------
# draw.io : 100 px par pouce à l'impression (pageScale = 1) ; 1 pouce = 25,4 mm (définition).
# Le sous-agent R1 a mesuré que l'export PDF de draw.io Desktop sort 0,245 % trop petit : la correction
# est l'affaire du rendu ; la règle de contrôle de 100 mm du cartouche sert à le mesurer et à le vérifier.
PX_PAR_MM = 100.0 / 25.4
PT_PAR_MM = 72.0 / 25.4                     # 1 mm = 2,8346 pt (PDF)

FORMATS_MM = {"A4": (210.0, 297.0)}         # (largeur, hauteur) en portrait
PAGES_PX = {"A4": {"portrait": (827, 1169), "paysage": (1169, 827)}}
ECHELLES = (50, 75, 100, 125, 150, 200, 250, 300, 400, 500, 750, 1000)
ORIENTATIONS = ("paysage", "portrait")      # ordre de préférence en cas d'égalité : paysage

MARGE_MM = 10.0                             # sur les quatre côtés
CARTOUCHE_MM = 22.0                         # en bas, sous la zone utile
RESERVE_MM = 14.0                           # autour du dessin, pour les cotes extérieures
REGLE_CONTROLE_MM = 100.0                   # règle de contrôle du cartouche (R1)
DECIMALES = 2                               # géométrie écrite dans le XML avec 2 décimales


class ErreurEchelle(ValueError):
    """Échelle impossible : non normalisée, ou le plan ne tient pas sur la page à l'échelle demandée."""


def px_par_m(S: float) -> float:
    """Pixels draw.io par mètre du modèle à l'échelle 1:S."""
    return 1000.0 * PX_PAR_MM / S


def barre_echelle_m(S: float) -> float:
    """Longueur nominale de la barre d'échelle : 1 m (S ≤ 100), 2 m (S ≤ 200), sinon 5 m."""
    if S <= 100:
        return 1.0
    if S <= 200:
        return 2.0
    return 5.0


def mm_vers_px(v_mm: float) -> float:
    """Millimètres SUR LA PAGE → px draw.io (pas des mètres du modèle)."""
    return v_mm * PX_PAR_MM


def px_vers_mm(v_px: float) -> float:
    """px draw.io → millimètres sur la page."""
    return v_px / PX_PAR_MM


def nombre_fr(v: float, decimales: int = 2) -> str:
    """12.5 → « 12,50 » (virgule décimale, comme sur le plan)."""
    return f"{v:.{decimales}f}".replace(".", ",")


def _dimensions_page_mm(format: str, orientation: str) -> tuple[float, float]:
    l, h = FORMATS_MM[format]
    return (h, l) if orientation == "paysage" else (l, h)


def zone_dessin_mm(format: str = "A4", orientation: str = "paysage") -> tuple[float, float, float, float]:
    """Zone de dessin (zone utile moins la réserve) en mm sur la page : (x0, y0, x1, y1)."""
    w, h = _dimensions_page_mm(format, orientation)
    return (MARGE_MM + RESERVE_MM, MARGE_MM + RESERVE_MM,
            w - MARGE_MM - RESERVE_MM, h - MARGE_MM - CARTOUCHE_MM - RESERVE_MM)


def capacite_m(S: float, orientation: str, format: str = "A4") -> tuple[float, float]:
    """Largeur et hauteur (m) de modèle qui tiennent dans la zone de dessin à l'échelle 1:S."""
    x0, y0, x1, y1 = zone_dessin_mm(format, orientation)
    return ((x1 - x0) * S / 1000.0, (y1 - y0) * S / 1000.0)


class Echelle:
    """Une échelle 1:S posée sur une page (format, orientation) avec l'origine du modèle en `origine_px`.

    Attributs : `S`, `orientation` (« paysage » | « portrait »), `format` (« A4 »), `page_px` (l, h),
    `page_mm`, `px_par_m`, `zone_utile_px` / `zone_utile_mm` (x0, y0, x1, y1), `zone_dessin_px`,
    `cartouche_px` / `cartouche_mm`, `reserve_px`, `origine_px` (point de la page où tombe (0, 0) du modèle),
    `origine_mm`, `barre_echelle_m`, `barre_echelle_px`, `barre_echelle_mm`, `regle_controle_px`, `texte`
    (« 1:100 »), `grille_px` (10 cm arrondis au px).
    """

    def __init__(self, S: float, orientation: str = "paysage", origine_px: tuple[float, float] | None = None,
                 format: str = "A4"):
        if not isinstance(S, (int, float)) or isinstance(S, bool) or not math.isfinite(S) or S <= 0:
            raise ErreurEchelle(f"Échelle 1:{S} invalide : S doit être un nombre positif.")
        if orientation not in ORIENTATIONS:
            raise ErreurEchelle(f"Orientation « {orientation} » inconnue (attendu : paysage ou portrait).")
        if format not in PAGES_PX:
            raise ErreurEchelle(f"Format de page « {format} » non géré (attendu : {', '.join(PAGES_PX)}).")
        self.S = int(S) if float(S).is_integer() else float(S)
        self.orientation = orientation
        self.format = format
        self.page_px = PAGES_PX[format][orientation]
        self.page_mm = _dimensions_page_mm(format, orientation)
        self.px_par_m = px_par_m(self.S)
        w, h = self.page_mm
        self.zone_utile_mm = (MARGE_MM, MARGE_MM, w - MARGE_MM, h - MARGE_MM - CARTOUCHE_MM)
        self.cartouche_mm = (MARGE_MM, h - MARGE_MM - CARTOUCHE_MM, w - MARGE_MM, h - MARGE_MM)
        self.zone_dessin_mm = zone_dessin_mm(format, orientation)
        self.zone_utile_px = tuple(mm_vers_px(v) for v in self.zone_utile_mm)
        self.cartouche_px = tuple(mm_vers_px(v) for v in self.cartouche_mm)
        self.zone_dessin_px = tuple(mm_vers_px(v) for v in self.zone_dessin_mm)
        self.reserve_px = mm_vers_px(RESERVE_MM)
        if origine_px is None:
            origine_px = (self.zone_dessin_px[0], self.zone_dessin_px[1])
        self.origine_px = (round(float(origine_px[0]), DECIMALES), round(float(origine_px[1]), DECIMALES))

    # ---------- grandeurs dérivées ----------
    @property
    def origine_mm(self) -> tuple[float, float]:
        """Position en mm sur la page du point (0, 0) du modèle."""
        return (px_vers_mm(self.origine_px[0]), px_vers_mm(self.origine_px[1]))

    @property
    def texte(self) -> str:
        return f"1:{self.S}"

    @property
    def barre_echelle_m(self) -> float:
        return barre_echelle_m(self.S)

    @property
    def barre_echelle_px(self) -> float:
        """Longueur exacte (non arrondie) de la barre d'échelle en px."""
        return self.barre_echelle_m * self.px_par_m

    @property
    def barre_echelle_mm(self) -> float:
        """Longueur de la barre sur le papier imprimé à 100 % (mm)."""
        return self.barre_echelle_m * 1000.0 / self.S

    @property
    def regle_controle_px(self) -> float:
        """Règle de contrôle du cartouche : 100 mm sur le papier = 393,70 px, indépendante de S."""
        return mm_vers_px(REGLE_CONTROLE_MM)

    @property
    def grille_px(self) -> int:
        """Pas de grille draw.io : 10 cm du modèle, arrondi au px (au moins 1)."""
        return max(1, int(round(0.1 * self.px_par_m)))

    # ---------- conversions (les seules du skill) ----------
    def m_vers_px(self, x_m: float, y_m: float) -> tuple[float, float]:
        """Point du modèle (m) → point de la page (px draw.io)."""
        return (self.origine_px[0] + x_m * self.px_par_m, self.origine_px[1] + y_m * self.px_par_m)

    def px_vers_m(self, x_px: float, y_px: float) -> tuple[float, float]:
        """Point de la page (px draw.io) → point du modèle (m)."""
        return ((x_px - self.origine_px[0]) / self.px_par_m, (y_px - self.origine_px[1]) / self.px_par_m)

    def longueur_px(self, l_m: float) -> float:
        """Longueur du modèle (m) → longueur dessinée (px)."""
        return l_m * self.px_par_m

    def longueur_m(self, l_px: float) -> float:
        """Longueur dessinée (px) → longueur du modèle (m)."""
        return l_px / self.px_par_m

    def boite_px(self, bbox_m: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        x0, y0 = self.m_vers_px(bbox_m[0], bbox_m[1])
        x1, y1 = self.m_vers_px(bbox_m[2], bbox_m[3])
        return (x0, y0, x1, y1)

    def tient(self, bbox_m: tuple[float, float, float, float], tolerance_px: float = 0.02) -> bool:
        """Vrai si la boîte (m) placée avec cette origine tient dans la zone de dessin."""
        x0, y0, x1, y1 = self.boite_px(bbox_m)
        zx0, zy0, zx1, zy1 = self.zone_dessin_px
        t = tolerance_px
        return x0 >= zx0 - t and y0 >= zy0 - t and x1 <= zx1 + t and y1 <= zy1 + t

    def dans_zone_utile(self, x_px: float, y_px: float, tolerance_px: float = 0.02) -> bool:
        zx0, zy0, zx1, zy1 = self.zone_utile_px
        t = tolerance_px
        return zx0 - t <= x_px <= zx1 + t and zy0 - t <= y_px <= zy1 + t

    def __repr__(self) -> str:
        return (f"Echelle(1:{self.S}, {self.orientation}, {self.format}, "
                f"{self.px_par_m:.3f} px/m, origine {self.origine_px})")


def _verifier_bbox(bbox_m) -> tuple[float, float, float, float]:
    try:
        xmin, ymin, xmax, ymax = (float(v) for v in bbox_m)
    except (TypeError, ValueError):
        raise ErreurEchelle(f"Boîte englobante illisible : {bbox_m!r} (attendu : xmin, ymin, xmax, ymax en m).")
    if not all(math.isfinite(v) for v in (xmin, ymin, xmax, ymax)) or xmax < xmin or ymax < ymin:
        raise ErreurEchelle(f"Boîte englobante invalide : {bbox_m!r}.")
    return xmin, ymin, xmax, ymax


def _echelle_centree(S: float, orientation: str, format: str, bbox: tuple[float, float, float, float]) -> Echelle:
    """Échelle dont l'origine centre la boîte englobante dans la zone de dessin."""
    base = Echelle(S, orientation, format=format)
    xmin, ymin, xmax, ymax = bbox
    zx0, zy0, zx1, zy1 = base.zone_dessin_px
    ppm = base.px_par_m
    ox = zx0 + ((zx1 - zx0) - (xmax - xmin) * ppm) / 2.0 - xmin * ppm
    oy = zy0 + ((zy1 - zy0) - (ymax - ymin) * ppm) / 2.0 - ymin * ppm
    return Echelle(S, orientation, origine_px=(ox, oy), format=format)


def _tient(bbox, S, orientation, format) -> bool:
    cap_w, cap_h = capacite_m(S, orientation, format)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    return w <= cap_w + 1e-9 and h <= cap_h + 1e-9


def choisir_echelle(bbox_m, page: dict | None = None) -> Echelle:
    """Choisit l'échelle normalisée et l'orientation, et centre le dessin dans la zone de dessin.

    `bbox_m` = (xmin, ymin, xmax, ymax) du modèle en m, cotes comprises (`Plan.bbox()`).
    `page` = {"format": "A4", "orientation": "auto" | "paysage" | "portrait", "echelle": None | S}.
    Règle : S = la plus petite valeur de `ECHELLES` telle que la boîte tient dans la zone de dessin ;
    orientation = celle qui donne le plus petit S (égalité → paysage). Échelle imposée : respectée si elle
    tient, sinon `ErreurEchelle` explicite (avec l'échelle minimale possible).
    """
    page = dict(page or {})
    format = page.get("format") or "A4"
    if format not in PAGES_PX:
        raise ErreurEchelle(f"Format de page « {format} » non géré : seul l'A4 est prévu.")
    orientation = page.get("orientation") or "auto"
    if orientation == "auto":
        orientations = list(ORIENTATIONS)
    elif orientation in ORIENTATIONS:
        orientations = [orientation]
    else:
        raise ErreurEchelle(f"Orientation « {orientation} » inconnue (attendu : auto, paysage ou portrait).")
    bbox = _verifier_bbox(bbox_m)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    def minimale() -> tuple[float, str] | None:
        for s in ECHELLES:
            for o in orientations:
                if _tient(bbox, s, o, format):
                    return s, o
        return None

    impose = page.get("echelle")
    if impose is not None:
        if isinstance(impose, bool) or not isinstance(impose, (int, float)) or impose not in ECHELLES:
            raise ErreurEchelle(f"Échelle imposée 1:{impose} non normalisée ; valeurs possibles : "
                                + ", ".join(f"1:{s}" for s in ECHELLES) + ".")
        for o in orientations:
            if _tient(bbox, impose, o, format):
                return _echelle_centree(impose, o, format, bbox)
        mini = minimale()
        cap = " ou ".join(f"{nombre_fr(capacite_m(impose, o, format)[0])} × "
                          f"{nombre_fr(capacite_m(impose, o, format)[1])} m en {o}" for o in orientations)
        conseil = (f"échelle minimale possible : 1:{mini[0]} ({mini[1]})" if mini
                   else "le plan ne tient sur un A4 à aucune échelle normalisée")
        raise ErreurEchelle(f"Le plan ({nombre_fr(w)} × {nombre_fr(h)} m, cotes comprises) ne tient pas sur "
                            f"une page {format} à l'échelle imposée 1:{impose} (place disponible : {cap}) ; "
                            f"{conseil}.")
    mini = minimale()
    if mini is None:
        raise ErreurEchelle(f"Le plan ({nombre_fr(w)} × {nombre_fr(h)} m) ne tient sur une page {format} à aucune "
                            f"échelle normalisée (jusqu'au 1:{ECHELLES[-1]}).")
    return _echelle_centree(mini[0], mini[1], format, bbox)
