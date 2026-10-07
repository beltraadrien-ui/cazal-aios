"""Écriture et lecture de `plan.drawio` (XML mxGraph non compressé, 2 pages : « Plan » et « Métré »).

Écriture : `ecrire(plan, echelle, chemin, tableaux_html=None) -> Path`
- page A4 selon `echelle` (pageScale = 1, grille = 10 cm) ; calques = cellules `parent="0"` dans l'ordre
  de `Plan.calques()` (plan_de_base … croisements, cartouche) ;
- identifiant de cellule = identifiant du modèle (M1, D1, F1, CF1, EV1, L1, C1, X1…) ; sous-éléments
  suffixés : `-txt` (étiquette), `-int` (paroi intérieure de chambre), `-porte` / `-porte-ouv` (porte de
  chambre et son ouverture), `-ouv` (ouverture de mur sous une porte), `-v1…` (ventilateurs), `-fl`
  (flèche de soufflage), `-a1` / `-a2` (lignes d'attache des cotes), `-contour` (contour de pièce) ;
- croisements : `plan.croisements` reçoit de generer.py les GROUPES (croisements.groupes_pour_dessin, repères
  G1…) : un cercle par groupe et son étiquette « X1-X3 » (`G1-txt`) posée à côté du cercle, à la première place
  libre (ni ligne, ni mur, ni équipement, ni autre texte) en tournant autour du cercle ;
- chaque cellule porte dans son style des clés `plan2d=<rôle>` (+ `plan2dGenre`, `plan2dParent`,
  `plan2dDe`, `plan2dA`, `plan2dAxe`) : draw.io les conserve, la lecture s'en sert (repli par déduction) ;
- toute la géométrie du modèle passe par `echelle.m_vers_px` / `echelle.longueur_px`, écrite à 0,01 px ;
- lignes = arêtes à `sourcePoint` / `targetPoint` / `Array` explicites, SANS `source=` / `target=` ;
- cartouche : titre, dossier, date, « Échelle 1:S » (cellule `cartouche-echelle`, qui garde aussi l'origine
  du modèle dans son style), barre d'échelle (`barre-echelle`, longueur exacte), règle de contrôle de
  100 mm (`regle-controle`), mention d'impression, légende des calques ;
- page 2 « Métré » : les `tableaux_html` [(titre, html), …] dans des cellules texte `html=1`.

Lecture : `lire(chemin) -> Lecture` (fichier écrit ici, ou modifié par draw.io Desktop, compressé ou non) :
`Lecture.echelle` (reconstruite depuis le cartouche), `.page`, `.calques` [(id, nom)], `.elements`
{id: {type, calque, … en mètres}}, `.brut` {id: cellule telle que dans le XML}, `.pages`, `.tableaux`,
`.barre_echelle_px`, `.regle_controle_px`, `.avertissements`. On retrouve tout par identifiant et par
clés de style, jamais par position dans le fichier.

Comparaison : `comparer(plan, lecture, tolerance=0.01) -> [écarts]` : chaque élément du modèle relu depuis
le XML et reconverti en mètres doit égaler `plan.json` à 1 cm (contrôles E1 / E2 du vérificateur).
"""
from __future__ import annotations

import base64
import html as _html
import math
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geometrie as geo  # noqa: E402
import modele as mod  # noqa: E402
from echelle import PAGES_PX, Echelle, ErreurEchelle, mm_vers_px, nombre_fr  # noqa: E402

TAG = "plan2d"
HOTE = "froid-plan-2d"
CADRE_PORTE_PX = 5.0          # mxgraph.floorplan.doorLeft : bandeau de 5 px, hauteur = largeur + 5

# ---------- styles (décision du 2026-10-07, conventions du skill et exemple validé v2) ----------
STYLE_MUR = {"exterieur": "rounded=0;html=1;fillColor=#424242;strokeColor=none;",
             "cloison": "rounded=0;html=1;fillColor=#757575;strokeColor=none;"}
STYLE_OUVERTURE = "rounded=0;html=1;fillColor=#FFFFFF;strokeColor=none;"
STYLE_PORTE = "html=1;fillColor=#FFFFFF;strokeColor=#424242;"
STYLE_FENETRE = "shape=mxgraph.floorplan.window;html=1;fillColor=#FFFFFF;strokeColor=#424242;"
STYLE_CHAMBRE = {"positif": ("#B0BEC5", "#37474F"), "negatif": ("#78909C", "#263238")}
STYLE_CONTOUR_PIECE = "endArrow=none;html=1;strokeColor=#90A4AE;dashed=1;rounded=0;edgeStyle=none;"
EQUIPEMENTS = {   # type : (style du corps, couleur du trait des ventilateurs, épaisseur ventilateur, couleur étiquette)
    "evaporateur": ("rounded=0;html=1;fillColor=#E1F5FE;strokeColor=#0277BD;strokeWidth=1.5;", "#0277BD", 1, "#0277BD"),
    "centrale": ("rounded=0;html=1;fillColor=#E3F2FD;strokeColor=#0D47A1;strokeWidth=2;", "#0D47A1", 1.5, "#0D47A1"),
    "groupe": ("rounded=0;html=1;fillColor=#E3F2FD;strokeColor=#0D47A1;strokeWidth=2;", "#0D47A1", 1.5, "#0D47A1"),
    "condenseur": ("rounded=0;html=1;fillColor=#E3F2FD;strokeColor=#0D47A1;strokeWidth=2;", "#0D47A1", 1.5, "#0D47A1"),
    "split": ("rounded=1;arcSize=20;html=1;fillColor=#BBDEFB;strokeColor=#1565C0;strokeWidth=2;", None, 0, "#1565C0"),
    "moteur": ("rounded=0;html=1;fillColor=#E8F5E9;strokeColor=#1B5E20;strokeWidth=2;", "#1B5E20", 1.5, "#1B5E20"),
    "tableau": ("rounded=0;html=1;fillColor=#F3E5F5;strokeColor=#6A1B9A;strokeWidth=1.5;", None, 0, "#6A1B9A"),
    "autre": ("rounded=0;html=1;fillColor=#ECEFF1;strokeColor=#90A4AE;", None, 0, "#607D8B"),
}
STYLE_SOUFFLAGE = "endArrow=block;endFill=1;endSize=5;html=1;strokeColor=#0277BD;strokeWidth=1.5;dashed=1;edgeStyle=none;"
STYLES_LIGNE = {
    "aspiration": "shape=link;width=3;endArrow=none;html=1;strokeColor=#1565C0;strokeWidth=1.2;",
    "liquide": "endArrow=none;html=1;strokeColor=#C62828;strokeWidth=1.5;",
    "condensats": "endArrow=open;endSize=4;html=1;strokeColor=#00ACC1;strokeWidth=1.5;dashed=1;dashPattern=3 3;",
    "clim_gaz": "shape=link;width=2;endArrow=none;html=1;strokeColor=#2E7D32;strokeWidth=1.2;",
    "clim_liquide": "endArrow=none;html=1;strokeColor=#2E7D32;strokeWidth=1.5;",
    "cable": "endArrow=none;html=1;strokeColor=#6A1B9A;strokeWidth=1.5;",
    "chemin_cables": "endArrow=none;html=1;strokeColor=#6A1B9A;strokeWidth=4;dashed=1;dashPattern=6 3;",
}
COULEUR_LIGNE = {"aspiration": "#1565C0", "liquide": "#C62828", "condensats": "#00ACC1", "clim_gaz": "#2E7D32",
                 "clim_liquide": "#2E7D32", "cable": "#6A1B9A", "chemin_cables": "#6A1B9A"}
STYLE_COTE = ("endArrow=block;startArrow=block;endFill=1;startFill=1;endSize=4;startSize=4;html=1;"
              "strokeColor=#546E7A;fontSize=9;fontColor=#37474F;labelBackgroundColor=#FFFFFF;edgeStyle=none;")
STYLE_ATTACHE = "endArrow=none;html=1;strokeColor=#B0BEC5;edgeStyle=none;"
STYLE_CROISEMENT = "html=1;fillColor=none;strokeColor=#FF6D00;strokeWidth=2.5;"
COULEUR_CALQUE = {"plan_de_base": "#424242", "cotes": "#546E7A", "froid_equipements": "#0277BD",
                  "froid_cuivres": "#1565C0", "electricite": "#6A1B9A", "clim_equipements": "#1B5E20",
                  "clim_cuivres": "#2E7D32", "croisements": "#FF6D00"}
POLICE_COTE = 9
LARGEUR_CAR = 0.6             # largeur d'un caractère ≈ 0,6 × taille (boîtes de texte un peu larges)
HAUTEUR_LIGNE = 1.2

SUFFIXE_ETIQUETTE = "-txt"


class ErreurEcriture(ValueError):
    """Le plan ne peut pas être écrit (identifiant de cellule en double, typiquement : valider d'abord)."""


class ErreurLecture(ValueError):
    """Fichier draw.io illisible."""


# ======================================================================
# Outils communs
# ======================================================================
def _f(v: float) -> str:
    """Nombre écrit dans le XML : 2 décimales, zéros inutiles retirés."""
    s = f"{float(v):.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def boite_texte_px(texte: str, taille: float, gras: bool = False) -> tuple[float, float]:
    """(largeur, hauteur) estimées d'un texte en px : ≈ 0,6 × taille par caractère, 1,2 × taille par ligne."""
    lignes = (texte or "").split("\n") or [""]
    facteur = LARGEUR_CAR + (0.05 if gras else 0.0)
    return (max(len(l) for l in lignes) * taille * facteur + 4.0, len(lignes) * taille * HAUTEUR_LIGNE + 2.0)


def segment_coupe_boite(p, q, boite, marge: float = 0.5) -> bool:
    """Vrai si le segment [p, q] entre dans la boîte (xmin, ymin, xmax, ymax) de plus de `marge` (un trait qui
    longe le bord ou le touche ne compte pas). Découpage de Liang-Barsky."""
    x0, y0, x1, y1 = boite[0] + marge, boite[1] + marge, boite[2] - marge, boite[3] - marge
    if x0 > x1 or y0 > y1:
        return False
    t0, t1 = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for pk, qk in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if abs(pk) < 1e-12:
            if qk < 0:
                return False
            continue
        t = qk / pk
        if pk < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def _html_valeur(texte: str) -> str:
    return "<br>".join(_html.escape(l, quote=False) for l in (texte or "").split("\n"))


def texte_brut(valeur: str) -> str:
    """Valeur HTML d'une cellule → texte (« <br> » → saut de ligne, balises retirées, entités décodées)."""
    if not valeur:
        return ""
    t = re.sub(r"<\s*br\s*/?\s*>", "\n", valeur, flags=re.I)
    t = re.sub(r"</\s*(div|p|li|tr)\s*>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = _html.unescape(t).replace("\xa0", " ")
    return "\n".join(l.strip() for l in t.strip().split("\n"))


def analyser_style(style: str | None) -> tuple[dict, list]:
    """Style mxGraph « a=b;nom;c=d » → ({a: b, c: d}, [noms sans valeur])."""
    d: dict = {}
    noms: list = []
    for morceau in (style or "").split(";"):
        morceau = morceau.strip()
        if not morceau:
            continue
        if "=" in morceau:
            k, v = morceau.split("=", 1)
            d[k.strip()] = v.strip()
        else:
            noms.append(morceau)
    return d, noms


def _tags(role: str, genre: str | None = None, parent: str | None = None, **autres) -> str:
    s = f"{TAG}={role};"
    if genre:
        s += f"{TAG}Genre={genre};"
    if parent:
        s += f"{TAG}Parent={parent};"
    for k, v in autres.items():
        if v is not None:
            s += f"{TAG}{k}={v};"
    return s


def _est_quart(angle: float) -> int | None:
    a = geo.normaliser_angle(angle)
    for q in (0, 90, 180, 270):
        if abs(a - q) < 1e-6:
            return q
    return None


# ======================================================================
# Écriture
# ======================================================================
class _Ecrivain:
    def __init__(self, plan: mod.Plan, echelle: Echelle):
        self.plan = plan
        self.ech = echelle
        self.calques = plan.calques()
        self.cellules: dict[str, list[ET.Element]] = {cle: [] for cle, _ in self.calques}
        self.etiquettes: dict[str, list[ET.Element]] = {cle: [] for cle, _ in self.calques}
        self.ids: set[str] = {"0"} | {cle for cle, _ in self.calques}

    # ----- cellules -----
    def _cellule(self, ident: str, calque: str, valeur: str, style: str, sommet: bool,
                 dessus: bool = False) -> ET.Element:
        if ident in self.ids:
            raise ErreurEcriture(f"Identifiant de cellule en double : « {ident} » (valider le plan avant d'écrire).")
        if calque not in self.cellules:
            raise ErreurEcriture(f"Calque inconnu « {calque} » pour la cellule « {ident} ».")
        self.ids.add(ident)
        c = ET.Element("mxCell", {"id": ident, "value": valeur, "style": style})
        c.set("vertex" if sommet else "edge", "1")
        c.set("parent", calque)
        (self.etiquettes if dessus else self.cellules)[calque].append(c)
        return c

    def sommet(self, ident, calque, x, y, w, h, style, valeur="", rotation=0.0, dessus=False) -> ET.Element:
        if rotation and _est_quart(rotation) != 0:
            style += f"rotation={_f(geo.normaliser_angle(rotation))};"
        c = self._cellule(ident, calque, valeur, style, True, dessus)
        ET.SubElement(c, "mxGeometry", {"x": _f(x), "y": _f(y), "width": _f(w), "height": _f(h), "as": "geometry"})
        return c

    def arete(self, ident, calque, points_px, style, valeur="", dessus=False) -> ET.Element:
        c = self._cellule(ident, calque, valeur, style, False, dessus)
        g = ET.SubElement(c, "mxGeometry", {"relative": "1", "as": "geometry"})
        (x0, y0), (x1, y1) = points_px[0], points_px[-1]
        ET.SubElement(g, "mxPoint", {"x": _f(x0), "y": _f(y0), "as": "sourcePoint"})
        ET.SubElement(g, "mxPoint", {"x": _f(x1), "y": _f(y1), "as": "targetPoint"})
        if len(points_px) > 2:
            arr = ET.SubElement(g, "Array", {"as": "points"})
            for x, y in points_px[1:-1]:
                ET.SubElement(arr, "mxPoint", {"x": _f(x), "y": _f(y)})
        return c

    def texte(self, ident, calque, centre_px, texte, taille, couleur, gras=False, parent=None,
              role="etiquette", align="center", dessus=True) -> ET.Element:
        w, h = boite_texte_px(texte, taille, gras)
        style = (f"text;{_tags(role, parent=parent)}html=1;align={align};verticalAlign=middle;whiteSpace=wrap;"
                 f"fontSize={_f(taille)};fontColor={couleur};" + ("fontStyle=1;" if gras else ""))
        return self.sommet(ident, calque, centre_px[0] - w / 2.0, centre_px[1] - h / 2.0, w, h, style,
                           valeur=_html_valeur(texte), dessus=dessus)

    def rect_oriente(self, ident, calque, centre_m, longueur_m, epaisseur_m, angle, style):
        """Rectangle dont la longueur suit `angle` : géométrie alignée si l'angle est un quart de tour."""
        cx, cy = self.ech.m_vers_px(*centre_m)
        L, e = self.ech.longueur_px(longueur_m), self.ech.longueur_px(epaisseur_m)
        q = _est_quart(angle)
        if q in (0, 180):
            return self.sommet(ident, calque, cx - L / 2, cy - e / 2, L, e, style + _tags_axe("x"))
        if q in (90, 270):
            return self.sommet(ident, calque, cx - e / 2, cy - L / 2, e, L, style + _tags_axe("y"))
        return self.sommet(ident, calque, cx - L / 2, cy - e / 2, L, e, style + _tags_axe("x"), rotation=angle)

    def px(self, p):
        return self.ech.m_vers_px(p[0], p[1])

    # ----- éléments du modèle -----
    def murs(self):
        for m in self.plan.murs:
            (x1, y1), (x2, y2) = mod.axe_mur(m)
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            style = _tags("mur", m["type"]) + STYLE_MUR.get(m["type"], STYLE_MUR["exterieur"])
            self.rect_oriente(m["id"], "plan_de_base", ((x1 + x2) / 2, (y1 + y2) / 2), math.hypot(x2 - x1, y2 - y1),
                              m["epaisseur"], angle, style)

    def ouverture_mur(self, porte: dict):
        """Rectangle blanc qui coupe le mur sous la porte (toute l'épaisseur, de la charnière au bout)."""
        try:
            mur = self.plan.mur(porte["dans"])
        except KeyError:
            return
        a1, a2 = mod.axe_mur(mur)
        l = geo.distance(a1, a2)
        if l < 1e-9:
            return
        u = ((a2[0] - a1[0]) / l, (a2[1] - a1[1]) / l)
        o, _ = mod.vecteurs_porte(porte["orientation"], porte.get("sens", "gauche"))
        h = porte["position"]
        fin = (h[0] + o[0] * porte["largeur"], h[1] + o[1] * porte["largeur"])
        s1 = (h[0] - a1[0]) * u[0] + (h[1] - a1[1]) * u[1]
        s2 = (fin[0] - a1[0]) * u[0] + (fin[1] - a1[1]) * u[1]
        sm = (s1 + s2) / 2.0
        centre = (a1[0] + u[0] * sm, a1[1] + u[1] * sm)
        angle = math.degrees(math.atan2(u[1], u[0]))
        epaisseur = mur["epaisseur"] + self.ech.longueur_m(1.0)
        self.rect_oriente(f"{porte['id']}-ouv", "plan_de_base", centre, abs(s2 - s1), epaisseur, angle,
                          _tags("ouverture", parent=porte["id"]) + STYLE_OUVERTURE)

    def porte(self, porte: dict, ident: str, couleur: str = "#424242", parent: str | None = None):
        hx, hy = self.px(porte["position"])
        w = self.ech.longueur_px(porte["largeur"])
        h = w + CADRE_PORTE_PX
        sens = porte.get("sens", "gauche")
        hloc = (-w / 2.0 if sens != "droite" else w / 2.0, CADRE_PORTE_PX - h / 2.0)
        r = geo.rotation_vecteur(hloc, porte["orientation"])
        cx, cy = hx - r[0], hy - r[1]
        forme = "doorRight" if sens == "droite" else "doorLeft"
        style = (f"shape=mxgraph.floorplan.{forme};" + _tags("porte", parent=parent)
                 + STYLE_PORTE.replace("#424242", couleur))
        self.sommet(ident, "plan_de_base", cx - w / 2, cy - h / 2, w, h, style, rotation=porte["orientation"])

    def portes(self):
        for p in self.plan.portes:
            if p.get("dans"):
                self.ouverture_mur(p)
        for p in self.plan.portes:
            self.porte(p, p["id"])

    def fenetres(self):
        for f in self.plan.fenetres:
            cx, cy = self.px(f["position"])
            w, h = self.ech.longueur_px(f["largeur"]), self.ech.longueur_px(f["epaisseur"])
            style = STYLE_FENETRE.replace("shape=mxgraph.floorplan.window;",
                                          "shape=mxgraph.floorplan.window;" + _tags("fenetre"))
            self.sommet(f["id"], "plan_de_base", cx - w / 2, cy - h / 2, w, h, style, rotation=f["orientation"])

    def chambres(self):
        for c in self.plan.chambres_froides:
            xmin, ymin, xmax, ymax = mod.rectangle_chambre(c)
            fond, trait = STYLE_CHAMBRE.get(c["regime"], STYLE_CHAMBRE["positif"])
            x0, y0 = self.px((xmin, ymin))
            x1, y1 = self.px((xmax, ymax))
            self.sommet(c["id"], "plan_de_base", x0, y0, x1 - x0, y1 - y0,
                        _tags("chambre", c["regime"]) + f"rounded=0;html=1;fillColor={fond};strokeColor={trait};")
            t = c["panneau_mm"] / 1000.0
            ix0, iy0 = self.px((xmin + t, ymin + t))
            ix1, iy1 = self.px((xmax - t, ymax - t))
            self.sommet(f"{c['id']}-int", "plan_de_base", ix0, iy0, max(ix1 - ix0, 0.0), max(iy1 - iy0, 0.0),
                        _tags("chambre-int", parent=c["id"]) + f"rounded=0;html=1;fillColor=#FFFFFF;strokeColor={trait};")
            if c.get("porte"):
                self.ouverture_chambre(c, t)
                self.porte(c["porte"], f"{c['id']}-porte", couleur=trait, parent=c["id"])

    def ouverture_chambre(self, c: dict, t: float):
        p = c["porte"]
        xmin, ymin, xmax, ymax = mod.rectangle_chambre(c)
        (hx, hy) = p["position"]
        o, _ = mod.vecteurs_porte(p["orientation"], p.get("sens", "gauche"))
        fx, fy = hx + o[0] * p["largeur"], hy + o[1] * p["largeur"]
        bords = {"haut": abs(hy - ymin), "bas": abs(hy - ymax), "gauche": abs(hx - xmin), "droite": abs(hx - xmax)}
        bord = min(bords, key=bords.get)
        marge = self.ech.longueur_m(1.0)
        if bord in ("haut", "bas"):
            y0 = ymin if bord == "haut" else ymax - t
            boite = (min(hx, fx), y0 - marge, max(hx, fx), y0 + t + marge)
        else:
            x0 = xmin if bord == "gauche" else xmax - t
            boite = (x0 - marge, min(hy, fy), x0 + t + marge, max(hy, fy))
        a = self.px(boite[:2])
        b = self.px(boite[2:])
        self.sommet(f"{c['id']}-porte-ouv", "plan_de_base", a[0], a[1], b[0] - a[0], b[1] - a[1],
                    _tags("ouverture", parent=c["id"]) + STYLE_OUVERTURE)

    def pieces(self):
        for p in self.plan.pieces:
            if p.get("contour"):
                pts = [self.px(q) for q in p["polygone"]] + [self.px(p["polygone"][0])]
                self.arete(f"{p['id']}-contour", "plan_de_base", pts,
                           _tags("piece-contour", parent=p["id"]) + STYLE_CONTOUR_PIECE)

    def etiquettes_pieces(self):
        for p in self.plan.pieces:
            texte = p["etiquette"] if p.get("etiquette") is not None else p.get("nom") or p["id"]
            centre = p.get("position_etiquette") or geo.centroide_polygone(p["polygone"])
            self.texte(p["id"], "plan_de_base", self.px(centre), texte, 9, "#37474F", gras=True, role="piece")
        for c in self.plan.chambres_froides:
            texte = c["etiquette"] if c.get("etiquette") is not None else c.get("nom") or c["id"]
            if not texte:
                continue
            centre = c.get("position_etiquette") or geo.centroide_polygone(c["polygone"])
            self.texte(f"{c['id']}{SUFFIXE_ETIQUETTE}", "plan_de_base", self.px(centre), texte, 8, "#263238",
                       parent=c["id"])

    def equipements(self):
        for q in self.plan.equipements:
            genre = q["type"] if q["type"] in EQUIPEMENTS else "autre"
            corps, trait_v, ep_v, _ = EQUIPEMENTS[genre]
            calque = q["calque"] if q["calque"] in self.cellules else "plan_de_base"
            cx, cy = self.px(q["position"])
            L, P = self.ech.longueur_px(q["dimensions"][0]), self.ech.longueur_px(q["dimensions"][1])
            self.sommet(q["id"], calque, cx - L / 2, cy - P / 2, L, P, _tags("equipement", genre) + corps,
                        rotation=q["rotation"])
            if trait_v:
                lm, pm = q["dimensions"]
                n = 1 if genre == "moteur" else max(1, int(lm / 0.65))
                d_m = min(0.7 * pm, 0.8 * lm / n)
                d = self.ech.longueur_px(d_m)
                for i in range(n):
                    local = (-lm / 2 + (i + 0.5) * lm / n, 0.0)
                    v = geo.rotation_vecteur(local, q["rotation"])
                    fx, fy = self.px((q["position"][0] + v[0], q["position"][1] + v[1]))
                    self.sommet(f"{q['id']}-v{i + 1}", calque, fx - d / 2, fy - d / 2, d, d,
                                f"ellipse;{_tags('ventilateur', parent=q['id'])}html=1;fillColor=#FFFFFF;"
                                f"strokeColor={trait_v};" + (f"strokeWidth={_f(ep_v)};" if ep_v != 1 else ""))
            if genre == "evaporateur":
                self.fleche_soufflage(q, calque)

    def fleche_soufflage(self, q: dict, calque: str):
        d = mod.SOUFFLAGES[self.plan.soufflage(q)]
        coins = mod.coins_equipement(q)
        demi = max((c[0] - q["position"][0]) * d[0] + (c[1] - q["position"][1]) * d[1] for c in coins)
        ecart = self.ech.longueur_m(3.0)
        longueur = max(0.6, self.ech.longueur_m(18.0))
        debut = (q["position"][0] + d[0] * (demi + ecart), q["position"][1] + d[1] * (demi + ecart))
        fin = (debut[0] + d[0] * longueur, debut[1] + d[1] * longueur)
        self.arete(f"{q['id']}-fl", calque, [self.px(debut), self.px(fin)],
                   _tags("soufflage", parent=q["id"]) + STYLE_SOUFFLAGE)

    def etiquettes_equipements(self):
        for q in self.plan.equipements:
            texte = q["etiquette"] if q.get("etiquette") is not None else (q.get("nom") or q["id"])
            if not texte:
                continue
            genre = q["type"] if q["type"] in EQUIPEMENTS else "autre"
            calque = q["calque"] if q["calque"] in self.cellules else "plan_de_base"
            couleur = EQUIPEMENTS[genre][3]
            if q.get("position_etiquette"):
                centre = self.px(q["position_etiquette"])
            else:
                bx0, by0, bx1, by1 = geo.boite_englobante(self.px(c) for c in mod.coins_equipement(q))
                if genre == "autre":
                    centre = ((bx0 + bx1) / 2, (by0 + by1) / 2)
                else:
                    _, h = boite_texte_px(texte, 8, True)
                    centre = ((bx0 + bx1) / 2, by0 - 2.0 - h / 2)
            self.texte(f"{q['id']}{SUFFIXE_ETIQUETTE}", calque, centre, texte, 8, couleur,
                       gras=genre != "autre", parent=q["id"])

    def style_ligne(self, l: dict) -> str:
        if l["type"] in STYLES_LIGNE:
            corps = STYLES_LIGNE[l["type"]]
        else:
            libre = self.plan.calque_libre(l["calque"]) or self.plan.calque_libre(l["type"]) or {}
            couleur = libre.get("couleur", "#455A64")
            if libre.get("trait") == "double":
                corps = f"shape=link;width=3;endArrow=none;html=1;strokeColor={couleur};strokeWidth=1.2;"
            else:
                corps = f"endArrow=none;html=1;strokeColor={couleur};strokeWidth=1.5;"
        return (_tags("ligne", l["type"], De=l.get("de"), A=l.get("a")) + corps
                + "rounded=0;edgeStyle=none;")

    def calque_ligne(self, l: dict) -> str:
        return l["calque"] if l.get("calque") in self.cellules else "froid_cuivres"

    def lignes(self):
        for l in self.plan.lignes:
            self.arete(l["id"], self.calque_ligne(l), [self.px(p) for p in l["points"]], self.style_ligne(l))

    def etiquettes_lignes(self):
        for l in self.plan.lignes:
            texte = l["etiquette"] if l.get("etiquette") is not None else l.get("repere")
            if not texte:
                continue
            couleur = COULEUR_LIGNE.get(l["type"])
            if couleur is None:
                couleur = (self.plan.calque_libre(l["calque"]) or {}).get("couleur", "#455A64")
            w, h = boite_texte_px(texte, 8, True)
            if l.get("position_etiquette"):
                centre = self.px(l["position_etiquette"])
            else:
                pts = [self.px(p) for p in l["points"]]
                a, b = max(geo.segments(pts), key=lambda s: geo.distance(*s))
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                if abs(b[0] - a[0]) >= abs(b[1] - a[1]):
                    centre = (mx, my - h / 2 - 3.0)
                else:
                    centre = (mx + w / 2 + 3.0, my)
            self.texte(f"{l['id']}{SUFFIXE_ETIQUETTE}", self.calque_ligne(l), centre, texte, 8, couleur,
                       gras=True, parent=l["id"])

    def cotes(self):
        for c in self.plan.cotes:
            p1, p2 = mod.ligne_de_cote(c)
            q1, q2 = self.px(p1), self.px(p2)
            self.arete(c["id"], "cotes", [q1, q2], _tags("cote") + STYLE_COTE, valeur=mod.texte_cote(c["valeur"]))
            n = mod.normale_cote(c)
            if n is None:
                continue
            for k, (mesure, trace) in enumerate(((c["de"], q1), (c["a"], q2)), start=1):
                m = self.px(mesure)
                d = geo.distance(m, trace)
                debut = (m[0] + n[0] * 2.0, m[1] + n[1] * 2.0) if d > 6.0 else m
                fin = (trace[0] + n[0] * 4.0, trace[1] + n[1] * 4.0)
                self.arete(f"{c['id']}-a{k}", "cotes", [debut, fin], _tags("attache", parent=c["id"]) + STYLE_ATTACHE)

    def croisements(self):
        d = self.ech.longueur_px(mod.DIAMETRE_CROISEMENT)
        for x in self.plan.croisements:
            cx, cy = self.px(x["point"])
            self.sommet(x["id"], "croisements", cx - d / 2, cy - d / 2, d, d,
                        f"ellipse;{_tags('croisement')}" + STYLE_CROISEMENT)

    def _obstacles(self) -> tuple[list, list]:
        """(boîtes, segments) en px de tout ce qui est déjà dessiné hors cartouche : murs, portes, équipements,
        textes, cercles = boîtes ; lignes, cotes, attaches, flèches et côtés des chambres = segments."""
        boites, segs = [], []
        for cle, _ in self.calques:
            if cle == "cartouche":
                continue
            for c in self.cellules[cle] + self.etiquettes[cle]:
                st, _ = analyser_style(c.get("style"))
                g = c.find("mxGeometry")
                if g is None:
                    continue
                if c.get("vertex") == "1":
                    x, y = float(g.get("x", 0)), float(g.get("y", 0))
                    w, h = float(g.get("width", 0)), float(g.get("height", 0))
                    coins = geo.rotation_rectangle((x + w / 2, y + h / 2), (w, h), float(st.get("rotation", 0) or 0))
                    if st.get(TAG) in ("chambre", "chambre-int"):
                        segs += [(coins[i], coins[(i + 1) % 4]) for i in range(4)]
                    else:
                        boites.append((c.get("id"), geo.boite_englobante(coins)))
                else:
                    pts = [g.find("mxPoint[@as='sourcePoint']")]
                    arr = g.find("Array")
                    pts += list(arr) if arr is not None else []
                    pts.append(g.find("mxPoint[@as='targetPoint']"))
                    pts = [(float(m.get("x", 0)), float(m.get("y", 0))) for m in pts if m is not None]
                    segs += geo.segments(pts)
        return boites, segs

    def etiquettes_croisements(self):
        """Étiquette « X1-X3 » de chaque groupe, à côté de son cercle (jamais dessus) : on essaie 8 directions
        (diagonales d'abord : les lignes qui se croisent partent à l'horizontale ou à la verticale) à des écarts
        croissants et on garde la première place libre ; sinon celle qui touche le moins de choses."""
        r = self.ech.longueur_px(mod.DIAMETRE_CROISEMENT) / 2.0
        boites, segs = self._obstacles()
        zx0, zy0, zx1, zy1 = self.ech.zone_dessin_px
        k = math.sqrt(0.5)
        for x in self.plan.croisements:
            texte = x.get("etiquette")
            if not texte:
                continue
            cx, cy = self.px(x["point"])
            w, h = boite_texte_px(texte, 8, True)
            autres = [b for ident, b in boites if ident != x["id"]]
            meilleure = None
            for ecart in (2.0, 8.0, 14.0, 20.0, 28.0, 36.0, 46.0):
                d = r + ecart
                for dx, dy in ((1, -1), (1, 1), (-1, -1), (-1, 1), (1, 0), (-1, 0), (0, -1), (0, 1)):
                    if dx and dy:
                        x0 = cx + d * k if dx > 0 else cx - d * k - w
                        y0 = cy + d * k if dy > 0 else cy - d * k - h
                    elif dx:
                        x0, y0 = (cx + d if dx > 0 else cx - d - w), cy - h / 2
                    else:
                        x0, y0 = cx - w / 2, (cy + d if dy > 0 else cy - d - h)
                    b = (x0, y0, x0 + w, y0 + h)
                    if b[0] < zx0 or b[1] < zy0 or b[2] > zx1 or b[3] > zy1:
                        continue
                    n = (sum(geo.boites_se_chevauchent(b, o) for o in autres)
                         + sum(segment_coupe_boite(a, q, b, 0.0) for a, q in segs))
                    if meilleure is None or n < meilleure[0]:
                        meilleure = (n, b)
                    if n == 0:
                        break
                if meilleure and meilleure[0] == 0:
                    break
            if meilleure is None:
                meilleure = (0, (cx + r + 2.0, cy - h / 2, cx + r + 2.0 + w, cy + h / 2))
            b = meilleure[1]
            boites.append((f"{x['id']}{SUFFIXE_ETIQUETTE}", b))
            self.texte(f"{x['id']}{SUFFIXE_ETIQUETTE}", "croisements", ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), texte,
                       8, COULEUR_CALQUE["croisements"], gras=True, parent=x["id"])

    # ----- cartouche -----
    def cartouche(self):
        e = self.ech
        cx0, cy0, cx1, cy1 = e.cartouche_px
        W = cx1 - cx0
        H = cy1 - cy0
        mm = mm_vers_px
        largeur_gauche = mm(112.0) if e.orientation == "portrait" else mm(160.0)
        C = "cartouche"
        t = _tags("cartouche")
        self.sommet("cartouche-cadre", C, cx0, cy0, W, H, t + "rounded=0;html=1;fillColor=#FFFFFF;strokeColor=#90A4AE;")
        self.arete("cartouche-separateur", C, [(cx0 + largeur_gauche, cy0), (cx0 + largeur_gauche, cy1)],
                   t + "endArrow=none;html=1;strokeColor=#CFD8DC;edgeStyle=none;")
        x = cx0 + mm(2.0)
        lg = largeur_gauche - mm(4.0)

        def txt(ident, y_mm, h_mm, texte, taille, gras=False, x_px=None, w_px=None, extra=""):
            style = (f"text;{t}html=1;align=left;verticalAlign=middle;whiteSpace=wrap;fontSize={_f(taille)};"
                     f"fontColor=#263238;" + ("fontStyle=1;" if gras else "") + extra)
            self.sommet(ident, C, x if x_px is None else x_px, cy0 + mm(y_mm), lg if w_px is None else w_px,
                        mm(h_mm), style, valeur=_html_valeur(texte))

        txt("cartouche-titre", 0.8, 5.0, self.plan.titre or "Plan", 11, gras=True)
        txt("cartouche-dossier", 6.0, 3.6, f"Dossier : {self.plan.dossier or '—'}", 8, w_px=lg * 0.62)
        txt("cartouche-date", 6.0, 3.6, f"Date : {self.plan.date or '—'}", 8, x_px=x + lg * 0.64, w_px=lg * 0.36)
        txt("cartouche-echelle", 10.0, 4.0, f"Échelle {e.texte}", 9, gras=True, w_px=mm(24.0),
            extra=f"{TAG}Ox={_f(e.origine_px[0])};{TAG}Oy={_f(e.origine_px[1])};{TAG}S={e.S};")
        bx = cx0 + mm(27.0)
        self.sommet("barre-echelle", C, bx, cy0 + mm(11.3), e.barre_echelle_px, 6.0,
                    _tags("barre_echelle") + "rounded=0;html=1;fillColor=#212121;strokeColor=none;")
        txt("barre-echelle-txt", 10.0, 4.0, f"{nombre_fr(e.barre_echelle_m, 0)} m", 8,
            x_px=bx + e.barre_echelle_px + mm(1.5), w_px=mm(8.0))
        cm = e.barre_echelle_mm / 10.0
        cm_txt = (f"{cm:.2f}".rstrip("0").rstrip(".")).replace(".", ",")
        txt("cartouche-mention", 9.6, 4.8, "Imprimer à 100 %, sans ajustement à la page : la barre doit mesurer "
            f"{cm_txt} cm à la règle.", 7, x_px=cx0 + mm(58.0), w_px=largeur_gauche - mm(60.0))
        rx, ry = cx0 + mm(2.0), cy0 + mm(16.3)
        self.sommet("regle-controle", C, rx, ry, e.regle_controle_px, 2.0,
                    _tags("regle_controle") + "rounded=0;html=1;fillColor=#000000;strokeColor=none;")
        for k in range(11):
            gx = rx + mm(10.0 * k)
            self.sommet(f"regle-controle-g{k}", C, gx - 0.5, ry - mm(1.0), 1.0, mm(1.0) + 2.0,
                        _tags("regle_graduation") + "rounded=0;html=1;fillColor=#000000;strokeColor=none;")
        txt("regle-controle-txt", 17.8, 3.6, "Règle de contrôle : 100 mm (imprimer à 100 %)", 7)
        # légende des calques
        lx = cx0 + largeur_gauche + mm(2.0)
        largeur_legende = W - largeur_gauche - mm(3.0)
        txt("legende-titre", 0.8, 3.6, "Calques", 8, gras=True, x_px=lx, w_px=largeur_legende)
        entrees = [(cle, nom) for cle, nom in self.calques if cle != "cartouche"]
        lignes_max = 5
        ncol = max(1, math.ceil(len(entrees) / lignes_max))
        lcol = largeur_legende / ncol
        for i, (cle, nom) in enumerate(entrees):
            col, rang = divmod(i, lignes_max)
            ex = lx + col * lcol
            ey = cy0 + mm(5.0 + 3.4 * rang)
            libre = self.plan.calque_libre(cle)
            couleur = COULEUR_CALQUE.get(cle) or (libre or {}).get("couleur", "#455A64")
            forme = "ellipse;" if cle == "croisements" else ""
            fond = "none" if cle == "croisements" else couleur
            self.sommet(f"legende-{cle}", C, ex, ey + mm(0.7), mm(5.0), mm(2.0),
                        f"{forme}{t}rounded=0;html=1;fillColor={fond};strokeColor={couleur};")
            court = mod.LEGENDE_COURTE.get(cle) or (nom if len(nom) <= 16 else nom[:15] + "…")
            txt(f"legende-{cle}-txt", 5.0 + 3.4 * rang, 3.4, court, 7, x_px=ex + mm(6.0), w_px=lcol - mm(6.5))


def _tags_axe(axe: str) -> str:
    return f"{TAG}Axe={axe};"


def _modele_graphe(diagramme: ET.Element, page_px: tuple[int, int], grille: int) -> ET.Element:
    w, h = page_px
    return ET.SubElement(diagramme, "mxGraphModel", {
        "dx": str(w), "dy": str(h), "grid": "1", "gridSize": str(grille), "guides": "1", "tooltips": "1",
        "connect": "1", "arrows": "1", "fold": "1", "page": "1", "pageScale": "1", "pageWidth": str(w),
        "pageHeight": str(h), "math": "0", "shadow": "0"})


def construire(plan: mod.Plan, echelle: Echelle, tableaux_html: list[tuple[str, str]] | None = None) -> ET.Element:
    """Arbre XML `<mxfile>` complet (2 pages) ; `ecrire` le sérialise."""
    ec = _Ecrivain(plan, echelle)
    ec.pieces()
    ec.murs()
    ec.fenetres()
    ec.portes()
    ec.chambres()
    ec.equipements()
    ec.lignes()
    ec.cotes()
    ec.croisements()
    ec.etiquettes_pieces()
    ec.etiquettes_equipements()
    ec.etiquettes_lignes()
    ec.etiquettes_croisements()
    ec.cartouche()

    mxfile = ET.Element("mxfile", {"host": HOTE, "type": "device"})
    d1 = ET.SubElement(mxfile, "diagram", {"name": "Plan", "id": "plan"})
    racine = ET.SubElement(_modele_graphe(d1, echelle.page_px, echelle.grille_px), "root")
    ET.SubElement(racine, "mxCell", {"id": "0"})
    for cle, nom in ec.calques:
        ET.SubElement(racine, "mxCell", {"id": cle, "value": nom, "parent": "0"})
    for cle, _ in ec.calques:
        for c in ec.cellules[cle] + ec.etiquettes[cle]:
            racine.append(c)

    d2 = ET.SubElement(mxfile, "diagram", {"name": "Métré", "id": "metre"})
    racine2 = ET.SubElement(_modele_graphe(d2, echelle.page_px, echelle.grille_px), "root")
    ET.SubElement(racine2, "mxCell", {"id": "0"})
    ET.SubElement(racine2, "mxCell", {"id": "metre-calque", "value": "Métré", "parent": "0"})
    marge = mm_vers_px(10.0)
    largeur = echelle.page_px[0] - 2 * marge

    def texte2(ident, x, y, w, h, valeur, style):
        c = ET.SubElement(racine2, "mxCell", {"id": ident, "value": valeur, "style": style, "vertex": "1",
                                              "parent": "metre-calque"})
        ET.SubElement(c, "mxGeometry", {"x": _f(x), "y": _f(y), "width": _f(w), "height": _f(h), "as": "geometry"})

    style_titre = "text;html=1;align=left;verticalAlign=middle;whiteSpace=wrap;fontSize=14;fontStyle=1;fontColor=#212121;"
    texte2("metre-titre", marge, marge, largeur, 24, _html_valeur(f"Métré : {plan.titre or 'plan'}"), style_titre)
    y = marge + 32
    if not tableaux_html:
        texte2("metre-vide", marge, y, largeur, 20, _html_valeur("Aucun tableau de métré dans cette version."),
               "text;html=1;align=left;verticalAlign=middle;fontSize=10;fontColor=#607D8B;")
    hauteur_page = echelle.page_px[1]
    for i, (titre, contenu) in enumerate(tableaux_html or [], start=1):
        rangs = 1 + len(re.findall(r"<(tr|br|li|p)\b", contenu or "", flags=re.I))
        h = 16.0 * rangs + 12.0
        # B1 : un tableau qui ne tient pas dans le reste de la feuille A4 commence en haut de la suivante (draw.io
        # imprime la page « Métré » en plusieurs feuilles A4 : sans ce saut, un tableau est coupé entre deux feuilles).
        haut_feuille = math.floor(y / hauteur_page) * hauteur_page
        if y + 22 + h > haut_feuille + hauteur_page - marge and y > haut_feuille + marge + 32 + 1e-6:
            y = haut_feuille + hauteur_page + marge
        texte2(f"metre-tableau-{i}-titre", marge, y, largeur, 20, _html_valeur(titre),
               "text;html=1;align=left;verticalAlign=middle;whiteSpace=wrap;fontSize=12;fontStyle=1;fontColor=#263238;")
        y += 22
        texte2(f"metre-tableau-{i}", marge, y, largeur, h, contenu or "",
               "text;html=1;align=left;verticalAlign=top;whiteSpace=wrap;overflow=visible;fontSize=10;fontColor=#263238;")
        y += h + 14
    return mxfile


def ecrire(plan: mod.Plan, echelle: Echelle, chemin: str | Path,
           tableaux_html: list[tuple[str, str]] | None = None) -> Path:
    """Écrit `plan.drawio` (XML non compressé, UTF-8, indenté). Renvoie le chemin écrit."""
    arbre = ET.ElementTree(construire(plan, echelle, tableaux_html))
    ET.indent(arbre, space="  ")
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    texte = ET.tostring(arbre.getroot(), encoding="unicode")
    chemin.write_text(texte + "\n", encoding="utf-8", newline="\n")
    return chemin


# ======================================================================
# Lecture
# ======================================================================
@dataclass
class Lecture:
    """Contenu d'un `plan.drawio` relu, en mètres. Voir `lire()`."""
    chemin: Path
    echelle: Echelle | None
    page: dict
    calques: list[tuple[str, str]]
    elements: dict[str, dict]
    pages: list[dict]
    brut: dict[str, dict]
    barre_echelle_px: float | None = None
    regle_controle_px: float | None = None
    tableaux: list[tuple[str, str]] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    def par_type(self, type_: str) -> list[dict]:
        return [e for e in self.elements.values() if e["type"] == type_]

    def par_calque(self, calque: str) -> list[dict]:
        return [e for e in self.elements.values() if e.get("calque") == calque]


def _decompresser(texte: str) -> str:
    """Contenu d'un `<diagram>` compressé par draw.io : base64 → deflate brut → URL-décodage."""
    donnees = base64.b64decode(texte.strip())
    brut = zlib.decompress(donnees, -15).decode("utf-8")
    return urllib.parse.unquote(brut)


def _diagrammes(racine: ET.Element) -> list[tuple[dict, ET.Element]]:
    if racine.tag == "mxGraphModel":
        return [({"id": "plan", "nom": "Plan"}, racine)]
    if racine.tag != "mxfile":
        raise ErreurLecture(f"Racine XML « {racine.tag} » inattendue (attendu : mxfile).")
    res = []
    for d in racine.findall("diagram"):
        m = d.find("mxGraphModel")
        if m is None and (d.text or "").strip():
            try:
                m = ET.fromstring(_decompresser(d.text))
            except (ValueError, zlib.error, ET.ParseError) as exc:
                raise ErreurLecture(f"Page « {d.get('name')} » compressée illisible : {exc}") from exc
        if m is not None:
            res.append(({"id": d.get("id"), "nom": d.get("name")}, m))
    if not res:
        raise ErreurLecture("Aucune page (« diagram ») dans le fichier.")
    return res


def _flottant(v, defaut=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return defaut


def _cellules_brutes(modele: ET.Element, page_id: str) -> list[dict]:
    root = modele.find("root")
    if root is None:
        return []
    res = []
    for el in root:
        if el.tag == "mxCell":
            cell, attrs = el, {}
            ident, valeur = el.get("id"), el.get("value", "")
        elif el.tag in ("object", "UserObject"):
            cell = el.find("mxCell")
            if cell is None:
                continue
            attrs = {k: v for k, v in el.attrib.items() if k not in ("id", "label")}
            ident, valeur = el.get("id"), el.get("label", "")
        else:
            continue
        style_brut = cell.get("style") or ""
        style, noms = analyser_style(style_brut)
        g = cell.find("mxGeometry")
        geo_d = None
        points, sp, tp = [], None, None
        if g is not None:
            geo_d = {k: _flottant(g.get(k)) for k in ("x", "y", "width", "height")}
            geo_d["relative"] = g.get("relative") == "1"
            for p in g.findall("mxPoint"):
                q = (_flottant(p.get("x")), _flottant(p.get("y")))
                if p.get("as") == "sourcePoint":
                    sp = q
                elif p.get("as") == "targetPoint":
                    tp = q
            arr = g.find("Array")
            if arr is not None:
                points = [(_flottant(p.get("x")), _flottant(p.get("y"))) for p in arr.findall("mxPoint")]
        res.append({"id": ident, "page": page_id, "valeur": valeur, "style_brut": style_brut, "style": style,
                    "noms_style": noms, "parent": cell.get("parent"), "vertex": cell.get("vertex") == "1",
                    "edge": cell.get("edge") == "1", "source": cell.get("source"), "target": cell.get("target"),
                    "geometrie": geo_d, "points": points, "source_point": sp, "target_point": tp,
                    "attributs": attrs})
    return res


class _Interprete:
    """Transforme les cellules brutes de la page « Plan » en éléments en mètres."""

    def __init__(self, cellules: list[dict], echelle: Echelle | None):
        self.c = {c["id"]: c for c in cellules if c["id"] is not None}
        self.ech = echelle
        racines = [c["id"] for c in cellules if c["parent"] is None]
        self.racine = racines[0] if racines else "0"
        self.calques = [c for c in cellules if c["parent"] == self.racine and not c["vertex"] and not c["edge"]]
        self.ids_calques = {c["id"] for c in self.calques}
        self.avertissements: list[str] = []

    def calque(self, ident: str) -> str | None:
        vus = set()
        while ident is not None and ident not in vus:
            vus.add(ident)
            if ident in self.ids_calques:
                return ident
            cell = self.c.get(ident)
            if cell is None:
                return None
            ident = cell["parent"]
        return None

    def decalage(self, cell: dict) -> tuple[float, float]:
        """Décalage absolu dû aux groupes / conteneurs (cellules sommets parents)."""
        dx = dy = 0.0
        p = self.c.get(cell["parent"])
        vus = set()
        while p is not None and p["id"] not in vus and p["id"] not in self.ids_calques:
            vus.add(p["id"])
            if p["vertex"] and p["geometrie"] and not p["geometrie"]["relative"]:
                dx += p["geometrie"]["x"]
                dy += p["geometrie"]["y"]
            p = self.c.get(p["parent"])
        return dx, dy

    def boite(self, cell: dict) -> tuple[float, float, float, float] | None:
        g = cell["geometrie"]
        if g is None or g["relative"]:
            return None
        dx, dy = self.decalage(cell)
        return (g["x"] + dx, g["y"] + dy, g["width"], g["height"])

    def rotation(self, cell: dict) -> float:
        return geo.normaliser_angle(_flottant(cell["style"].get("rotation"), 0.0))

    def m(self, p):
        if self.ech is None or p is None:
            return None
        x, y = self.ech.px_vers_m(p[0], p[1])
        return (x, y)

    def lm(self, v):
        return None if self.ech is None or v is None else self.ech.longueur_m(v)

    def point_terminal(self, ident: str, vers, est_source: bool, style: dict):
        t = self.c.get(ident)
        if t is None or not t["vertex"]:
            return None
        b = self.boite(t)
        if b is None:
            return None
        x, y, w, h = b
        c = (x + w / 2, y + h / 2)
        rot = self.rotation(t)
        cles = ("exitX", "exitY") if est_source else ("entryX", "entryY")
        if cles[0] in style and cles[1] in style:
            p = (x + _flottant(style[cles[0]]) * w, y + _flottant(style[cles[1]]) * h)
            return geo.rotation_point(p, c, rot)
        if vers is None:
            return c
        v = geo.rotation_point(vers, c, -rot)
        dx, dy = v[0] - c[0], v[1] - c[1]
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return c
        tx = (w / 2) / abs(dx) if abs(dx) > 1e-9 else math.inf
        ty = (h / 2) / abs(dy) if abs(dy) > 1e-9 else math.inf
        k = min(tx, ty, 1.0)
        return geo.rotation_point((c[0] + dx * k, c[1] + dy * k), c, rot)

    def points_arete(self, cell: dict) -> list:
        dx, dy = self.decalage(cell)
        milieu = [(x + dx, y + dy) for x, y in cell["points"]]
        sp = (cell["source_point"][0] + dx, cell["source_point"][1] + dy) if cell["source_point"] else None
        tp = (cell["target_point"][0] + dx, cell["target_point"][1] + dy) if cell["target_point"] else None

        def centre(ident):
            t = self.c.get(ident)
            b = self.boite(t) if t else None
            return (b[0] + b[2] / 2, b[1] + b[3] / 2) if b else None

        if cell["source"]:
            vers = milieu[0] if milieu else (tp if not cell["target"] else centre(cell["target"]))
            sp = self.point_terminal(cell["source"], vers, True, cell["style"]) or sp
        if cell["target"]:
            vers = milieu[-1] if milieu else (sp if sp else centre(cell["source"]))
            tp = self.point_terminal(cell["target"], vers, False, cell["style"]) or tp
        pts = ([sp] if sp else []) + milieu + ([tp] if tp else [])
        return pts

    def element(self, cell: dict) -> dict | None:
        if cell["id"] in self.ids_calques or cell["parent"] is None:
            return None
        st = cell["style"]
        role = st.get(TAG)
        calque = self.calque(cell["id"])
        texte = texte_brut(cell["valeur"])
        e = {"id": cell["id"], "calque": calque, "role": role, "genre": st.get(f"{TAG}Genre"),
             "parent_element": st.get(f"{TAG}Parent"), "texte": texte, "style": st,
             "taille_police": _flottant(st.get("fontSize"), 11.0)}
        if role is None:
            role = self.deduire_role(cell, calque)
            e["role"] = role
            e["deduit"] = True
        if e["parent_element"] is None and e.get("deduit") and "-" in cell["id"]:
            tete = cell["id"].rsplit("-", 1)[0]
            while tete:
                if tete in self.c and tete not in self.ids_calques:
                    e["parent_element"] = tete
                    break
                if "-" not in tete:
                    break
                tete = tete.rsplit("-", 1)[0]
        if cell["vertex"]:
            self.sommet(cell, e, role)
        elif cell["edge"]:
            self.arete(cell, e, role)
        return e

    def deduire_role(self, cell: dict, calque: str | None) -> str:
        st, noms = cell["style"], cell["noms_style"]
        forme = st.get("shape", "")
        if calque == "cartouche":
            return "cartouche"
        if cell["edge"]:
            if calque == "cotes":
                return "cote" if cell["valeur"] else "attache"
            if calque in mod.CALQUES_RESEAUX or (calque and calque not in mod.NOMS_CALQUES):
                return "ligne"
            return "arete"
        if "doorLeft" in forme or "doorRight" in forme:
            return "porte"
        if "floorplan.window" in forme:
            return "fenetre"
        if "ellipse" in noms and calque == "croisements":
            return "croisement"
        if "text" in noms:
            return "etiquette"
        return "forme"

    def sommet(self, cell: dict, e: dict, role: str):
        b = self.boite(cell)
        rot = self.rotation(cell)
        e["rotation"] = rot
        if b is None:
            e["type"] = "texte" if role in ("etiquette", "piece") else "forme"
            return
        x, y, w, h = b
        c = (x + w / 2, y + h / 2)
        coins = geo.rotation_rectangle(c, (w, h), rot)
        e["centre_px"] = c
        e["dimensions_px"] = (w, h)
        e["boite_px"] = geo.boite_englobante(coins)
        e["coins_px"] = coins
        e["centre_m"] = self.m(c)
        e["boite_m"] = (geo.boite_englobante([self.m(p) for p in coins]) if self.ech else None)
        if role == "mur":
            axe = cell["style"].get(f"{TAG}Axe") or ("x" if w >= h else "y")
            L, ep = (w, h) if axe == "x" else (h, w)
            v = geo.rotation_vecteur((1.0, 0.0) if axe == "x" else (0.0, 1.0), rot)
            p1 = (c[0] - v[0] * L / 2, c[1] - v[1] * L / 2)
            p2 = (c[0] + v[0] * L / 2, c[1] + v[1] * L / 2)
            e.update(type="mur", points_px=[p1, p2], points_m=[self.m(p1), self.m(p2)],
                     longueur_m=self.lm(L), epaisseur_m=self.lm(ep))
        elif role == "porte":
            forme = cell["style"].get("shape", "")
            sens = "droite" if "doorRight" in forme else "gauche"
            orientation = rot
            if cell["style"].get("flipH") == "1":
                sens = "droite" if sens == "gauche" else "gauche"
            if cell["style"].get("flipV") == "1":
                sens = "droite" if sens == "gauche" else "gauche"
                orientation = geo.normaliser_angle(orientation + 180.0)
            hloc = (-w / 2 if sens == "gauche" else w / 2, CADRE_PORTE_PX - h / 2)
            r = geo.rotation_vecteur(hloc, orientation)
            charniere = (c[0] + r[0], c[1] + r[1])
            e.update(type="porte", position_px=charniere, position_m=self.m(charniere), largeur_m=self.lm(w),
                     orientation=orientation, sens=sens)
        elif role == "fenetre":
            e.update(type="fenetre", largeur_m=self.lm(w), epaisseur_m=self.lm(h), orientation=rot)
        elif role == "chambre":
            pts = [self.m(p) for p in coins] if self.ech else None
            e.update(type="chambre", points_px=coins, points_m=pts, dimensions_m=(self.lm(w), self.lm(h)))
        elif role == "equipement":
            e.update(type="equipement", dimensions_m=(self.lm(w), self.lm(h)))
        elif role == "croisement":
            e.update(type="croisement", diametre_m=self.lm((w + h) / 2))
        elif role in ("piece", "etiquette"):
            e["type"] = "piece" if role == "piece" else "texte"
            e["boite_texte_px"] = e["boite_px"]
            e["boite_texte_m"] = e["boite_m"]
        elif role == "barre_echelle":
            e.update(type="barre_echelle", longueur_px=w)
        elif role == "regle_controle":
            e.update(type="regle_controle", longueur_px=w)
        elif role == "cartouche" or role == "regle_graduation":
            e["type"] = "cartouche"
            if texte_brut(cell["valeur"]):
                e["boite_texte_px"] = e["boite_px"]
                e["boite_texte_m"] = e["boite_m"]
        elif role in ("chambre-int", "ventilateur", "ouverture"):
            e["type"] = "decor"
        else:
            e["type"] = "texte" if e["texte"] else "forme"
            if e["texte"]:
                e["boite_texte_px"] = e["boite_px"]
                e["boite_texte_m"] = e["boite_m"]

    def arete(self, cell: dict, e: dict, role: str):
        pts = self.points_arete(cell)
        e["points_px"] = pts
        e["points_m"] = [self.m(p) for p in pts] if self.ech else None
        e["longueur_px"] = geo.longueur_polyligne(pts)
        e["longueur_m"] = self.lm(e["longueur_px"])
        if pts:
            e["boite_px"] = geo.boite_englobante(pts)
            e["boite_m"] = geo.boite_englobante(e["points_m"]) if self.ech else None
        style = cell["style"]
        if style.get("edgeStyle") not in (None, "none"):
            e["avertissement"] = (f"tracé recalculé par draw.io (edgeStyle={style.get('edgeStyle')}) : "
                                  "les points relus sont approximatifs")
        if cell["source"] or cell["target"]:
            e["raccordee"] = {"source": cell["source"], "target": cell["target"]}
        if role == "ligne":
            e.update(type="ligne", de=style.get(f"{TAG}De"), a=style.get(f"{TAG}A"))
        elif role == "cote":
            m = re.search(r"-?\d+(?:[.,]\d+)?", e["texte"] or "")
            e.update(type="cote", valeur_m=float(m.group(0).replace(",", ".")) if m else None)
        elif role in ("soufflage", "attache", "piece-contour"):
            e["type"] = "decor" if role != "piece-contour" else "piece_contour"
        elif role == "cartouche":
            e["type"] = "cartouche"
        else:
            e["type"] = "arete"
        if e["texte"] and pts:
            total = e["longueur_px"]
            reste, milieu = total / 2.0, pts[0]
            for a, b in geo.segments(pts):
                l = geo.distance(a, b)
                if l >= reste and l > 0:
                    milieu = (a[0] + (b[0] - a[0]) * reste / l, a[1] + (b[1] - a[1]) * reste / l)
                    break
                reste -= l
            tw, th = boite_texte_px(e["texte"], e["taille_police"])
            bt = (milieu[0] - tw / 2, milieu[1] - th / 2, milieu[0] + tw / 2, milieu[1] + th / 2)
            e["boite_texte_px"] = bt
            e["boite_texte_m"] = (geo.boite_englobante([self.m(bt[:2]), self.m(bt[2:])]) if self.ech else None)


def _echelle_depuis_cartouche(cellules: dict, page: dict) -> tuple[Echelle | None, list[str]]:
    avert = []
    cell = cellules.get("cartouche-echelle")
    if cell is None:
        return None, ["Cartouche sans cellule « cartouche-echelle » : échelle introuvable."]
    m = re.search(r"1\s*[:/]\s*(\d+(?:[.,]\d+)?)", texte_brut(cell["valeur"]))
    S = None
    if m:
        S = float(m.group(1).replace(",", "."))
    elif cell["style"].get(f"{TAG}S"):
        S = _flottant(cell["style"].get(f"{TAG}S"), None)
        avert.append("Texte d'échelle « 1:S » illisible dans le cartouche : S repris du style.")
    if not S:
        return None, avert + ["Échelle « 1:S » introuvable dans le cartouche."]
    ox, oy = cell["style"].get(f"{TAG}Ox"), cell["style"].get(f"{TAG}Oy")
    if ox is None or oy is None:
        return None, avert + ["Origine du modèle absente du cartouche (clés plan2dOx / plan2dOy) : "
                              "conversion px → m impossible."]
    try:
        ech = Echelle(S, page["orientation"], origine_px=(_flottant(ox), _flottant(oy)))
    except ErreurEchelle as exc:
        return None, avert + [str(exc)]
    return ech, avert


def lire(chemin: str | Path) -> Lecture:
    """Relit un `.drawio` (écrit par `ecrire` ou modifié par draw.io Desktop) → `Lecture` (mètres)."""
    chemin = Path(chemin)
    if not chemin.is_file():
        raise ErreurLecture(f"Fichier draw.io introuvable : {chemin}")
    try:
        racine = ET.parse(chemin).getroot()
    except ET.ParseError as exc:
        raise ErreurLecture(f"XML mal formé dans {chemin.name} : {exc}") from exc
    diagrammes = _diagrammes(racine)
    pages = []
    for info, m in diagrammes:
        w, h = _flottant(m.get("pageWidth"), 0.0), _flottant(m.get("pageHeight"), 0.0)
        cellules = _cellules_brutes(m, info["id"])
        pages.append({"id": info["id"], "nom": info["nom"], "largeur_px": w, "hauteur_px": h,
                      "page_scale": _flottant(m.get("pageScale"), 1.0), "grille_px": _flottant(m.get("gridSize"), 0.0),
                      "cellules": cellules})
    plan_page = next((p for p in pages if p["id"] == "plan" or p["nom"] == "Plan"), pages[0])
    w, h = plan_page["largeur_px"], plan_page["hauteur_px"]
    orientation = "paysage" if w > h else "portrait"
    format_ = None
    for f, dims in PAGES_PX.items():
        if abs(w - dims[orientation][0]) <= 1 and abs(h - dims[orientation][1]) <= 1:
            format_ = f
    page = {"format": format_, "orientation": orientation, "largeur_px": w, "hauteur_px": h,
            "page_scale": plan_page["page_scale"], "grille_px": plan_page["grille_px"]}
    brut = {c["id"]: c for c in plan_page["cellules"] if c["id"] is not None}
    ech, avert = _echelle_depuis_cartouche(brut, page)
    interp = _Interprete(plan_page["cellules"], ech)
    calques = [(c["id"], c["valeur"]) for c in interp.calques]
    elements = {}
    for c in plan_page["cellules"]:
        e = interp.element(c)
        if e is not None:
            elements[c["id"]] = e
    barre = brut.get("barre-echelle")
    regle = brut.get("regle-controle")
    barre_px = barre["geometrie"]["width"] if barre and barre["geometrie"] else None
    regle_px = regle["geometrie"]["width"] if regle and regle["geometrie"] else None
    tableaux = []
    page_metre = next((p for p in pages if p is not plan_page and (p["id"] == "metre" or p["nom"] == "Métré")), None)
    if page_metre:
        par_id = {c["id"]: c for c in page_metre["cellules"]}
        numeros = sorted(int(m.group(1)) for i in par_id if (m := re.fullmatch(r"metre-tableau-(\d+)", i or "")))
        for k in numeros:
            titre = texte_brut(par_id.get(f"metre-tableau-{k}-titre", {}).get("valeur", ""))
            tableaux.append((titre, par_id[f"metre-tableau-{k}"]["valeur"]))
    return Lecture(chemin=chemin, echelle=ech, page=page, calques=calques, elements=elements, pages=pages,
                   brut=brut, barre_echelle_px=barre_px, regle_controle_px=regle_px, tableaux=tableaux,
                   avertissements=avert + interp.avertissements)


# ======================================================================
# Comparaison modèle ↔ dessin relu (E1, E2)
# ======================================================================
def comparer(plan: mod.Plan, lecture: Lecture, tolerance: float = 0.01) -> list[dict]:
    """Écarts entre `plan.json` et le dessin relu (en m) : [{id, categorie, message, attendu, trouve}].

    Murs (axe et épaisseur), portes (charnière, largeur, orientation, sens), fenêtres, chambres (et leur
    porte), équipements (centre, dimensions, rotation), lignes (point par point), cotes (ligne dessinée,
    longueur = valeur, texte « 12,50 m »), croisements. Liste vide = le dessin est le modèle à `tolerance` près.
    """
    ecarts: list[dict] = []

    def ecart(ident, cat, message, attendu=None, trouve=None):
        ecarts.append({"id": ident, "categorie": cat, "message": message, "attendu": attendu, "trouve": trouve})

    if lecture.echelle is None:
        ecart("cartouche-echelle", "echelle", "échelle illisible dans le fichier : comparaison impossible")
        return ecarts

    def chercher(ident, type_, cat):
        e = lecture.elements.get(ident)
        if e is None:
            ecart(ident, cat, f"{ident} absent du dessin")
            return None
        if e.get("type") != type_:
            ecart(ident, cat, f"{ident} relu comme « {e.get('type')} » au lieu de « {type_} »")
            return None
        return e

    def proche(p, q) -> bool:
        return p is not None and q is not None and geo.distance(p, q) <= tolerance + 1e-9

    def egal(a, b) -> bool:
        return a is not None and b is not None and abs(a - b) <= tolerance + 1e-9

    def angle_egal(a, b, modulo=360.0) -> bool:
        d = abs(geo.normaliser_angle(a) - geo.normaliser_angle(b)) % modulo
        return min(d, modulo - d) < 0.01

    for m in plan.murs:
        e = chercher(m["id"], "mur", "mur")
        if not e:
            continue
        a1, a2 = mod.axe_mur(m)
        p1, p2 = e["points_m"]
        if not ((proche(a1, p1) and proche(a2, p2)) or (proche(a1, p2) and proche(a2, p1))):
            ecart(m["id"], "mur", f"mur {m['id']} déplacé : axe attendu {mod._pt(a1)}–{mod._pt(a2)}, "
                  f"relu {mod._pt(p1)}–{mod._pt(p2)}", (a1, a2), (p1, p2))
        if not egal(m["epaisseur"], e["epaisseur_m"]):
            ecart(m["id"], "mur", f"mur {m['id']} : épaisseur {nombre_fr(e['epaisseur_m'], 3)} m au lieu de "
                  f"{nombre_fr(m['epaisseur'], 3)} m", m["epaisseur"], e["epaisseur_m"])

    def verifier_porte(p, ident, cat):
        e = chercher(ident, "porte", cat)
        if not e:
            return
        if not proche(p["position"], e["position_m"]):
            ecart(ident, cat, f"porte {ident} : charnière relue en {mod._pt(e['position_m'])} au lieu de "
                  f"{mod._pt(p['position'])}", p["position"], e["position_m"])
        if not egal(p["largeur"], e["largeur_m"]):
            ecart(ident, cat, f"porte {ident} : largeur {nombre_fr(e['largeur_m'], 3)} m au lieu de "
                  f"{nombre_fr(p['largeur'], 3)} m", p["largeur"], e["largeur_m"])
        if not angle_egal(p["orientation"], e["orientation"]) or p.get("sens", "gauche") != e["sens"]:
            ecart(ident, cat, f"porte {ident} : orientation {nombre_fr(e['orientation'], 0)}° / sens {e['sens']} "
                  f"au lieu de {nombre_fr(p['orientation'], 0)}° / {p.get('sens', 'gauche')}",
                  (p["orientation"], p.get("sens", "gauche")), (e["orientation"], e["sens"]))

    for p in plan.portes:
        verifier_porte(p, p["id"], "porte")

    for f in plan.fenetres:
        e = chercher(f["id"], "fenetre", "fenetre")
        if not e:
            continue
        if not proche(f["position"], e["centre_m"]):
            ecart(f["id"], "fenetre", f"fenêtre {f['id']} : centre relu en {mod._pt(e['centre_m'])} au lieu de "
                  f"{mod._pt(f['position'])}", f["position"], e["centre_m"])
        if not egal(f["largeur"], e["largeur_m"]) or not egal(f["epaisseur"], e["epaisseur_m"]):
            ecart(f["id"], "fenetre", f"fenêtre {f['id']} : {nombre_fr(e['largeur_m'], 3)} × "
                  f"{nombre_fr(e['epaisseur_m'], 3)} m au lieu de {nombre_fr(f['largeur'], 3)} × "
                  f"{nombre_fr(f['epaisseur'], 3)} m", (f["largeur"], f["epaisseur"]), (e["largeur_m"], e["epaisseur_m"]))
        if not angle_egal(f["orientation"], e["orientation"], 180.0):
            ecart(f["id"], "fenetre", f"fenêtre {f['id']} : orientation {nombre_fr(e['orientation'], 0)}° au lieu de "
                  f"{nombre_fr(f['orientation'], 0)}°", f["orientation"], e["orientation"])

    for c in plan.chambres_froides:
        e = chercher(c["id"], "chambre", "chambre")
        if e:
            attendu = mod.rectangle_chambre(c)
            trouve = geo.boite_englobante(e["points_m"])
            if any(abs(a - b) > tolerance + 1e-9 for a, b in zip(attendu, trouve)):
                ecart(c["id"], "chambre", f"chambre {c['id']} : rectangle relu "
                      f"{mod._pt(trouve[:2])}–{mod._pt(trouve[2:])} au lieu de {mod._pt(attendu[:2])}–"
                      f"{mod._pt(attendu[2:])}", attendu, trouve)
        if c.get("porte"):
            verifier_porte(c["porte"], f"{c['id']}-porte", "chambre")

    for q in plan.equipements:
        e = chercher(q["id"], "equipement", "equipement")
        if not e:
            continue
        if not proche(q["position"], e["centre_m"]):
            ecart(q["id"], "equipement", f"équipement {q['id']} : centre relu en {mod._pt(e['centre_m'])} au lieu "
                  f"de {mod._pt(q['position'])}", q["position"], e["centre_m"])
        if not (egal(q["dimensions"][0], e["dimensions_m"][0]) and egal(q["dimensions"][1], e["dimensions_m"][1])):
            ecart(q["id"], "equipement", f"équipement {q['id']} : {nombre_fr(e['dimensions_m'][0], 3)} × "
                  f"{nombre_fr(e['dimensions_m'][1], 3)} m au lieu de {nombre_fr(q['dimensions'][0], 3)} × "
                  f"{nombre_fr(q['dimensions'][1], 3)} m", q["dimensions"], e["dimensions_m"])
        if not angle_egal(q["rotation"], e["rotation"]):
            ecart(q["id"], "equipement", f"équipement {q['id']} : rotation {nombre_fr(e['rotation'], 0)}° au lieu "
                  f"de {nombre_fr(q['rotation'], 0)}°", q["rotation"], e["rotation"])

    for l in plan.lignes:
        e = chercher(l["id"], "ligne", "ligne")
        if not e:
            continue
        trouve = e["points_m"] or []
        if len(trouve) != len(l["points"]):
            ecart(l["id"], "ligne", f"ligne {l['id']} : {len(trouve)} points relus au lieu de {len(l['points'])}",
                  len(l["points"]), len(trouve))
            continue
        for k, (p, q) in enumerate(zip(l["points"], trouve)):
            if not proche(p, q):
                ecart(l["id"], "ligne", f"ligne {l['id']}, point {k} : relu en {mod._pt(q)} au lieu de {mod._pt(p)}",
                      p, q)

    for c in plan.cotes:
        e = chercher(c["id"], "cote", "cote")
        if not e:
            continue
        p1, p2 = mod.ligne_de_cote(c)
        trouve = e["points_m"] or []
        if len(trouve) != 2 or not ((proche(p1, trouve[0]) and proche(p2, trouve[1]))
                                    or (proche(p1, trouve[1]) and proche(p2, trouve[0]))):
            ecart(c["id"], "cote", f"cote {c['id']} : ligne de cote déplacée", (p1, p2), trouve)
        if not egal(c["valeur"], e["longueur_m"]):
            ecart(c["id"], "cote", f"cote {c['id']} : longueur dessinée {nombre_fr(e['longueur_m'], 3)} m pour une "
                  f"cote de {nombre_fr(c['valeur'], 3)} m", c["valeur"], e["longueur_m"])
        attendu = mod.texte_cote(c["valeur"])
        if e["texte"] != attendu:
            ecart(c["id"], "cote", f"cote {c['id']} : texte « {e['texte']} » au lieu de « {attendu} »",
                  attendu, e["texte"])

    for x in plan.croisements:
        e = chercher(x["id"], "croisement", "croisement")
        if e and not proche(x["point"], e["centre_m"]):
            ecart(x["id"], "croisement", f"croisement {x['id']} : relu en {mod._pt(e['centre_m'])} au lieu de "
                  f"{mod._pt(x['point'])}", x["point"], e["centre_m"])
    return ecarts
