"""Modèle `plan.json` d'un plan 2D de frigoriste : chargement, valeurs par défaut, validation, géométrie.

Mètres ; x vers la droite, y vers le bas ; origine = coin haut-gauche du bâtiment. Schéma : conventions du
skill (`references/conventions-plan-froid.md`, décision du 2026-10-07).

- `charger(chemin) -> Plan` : lit le JSON, applique les défauts (dimensions par type d'équipement,
  épaisseurs de murs, hauteurs, calques standard des lignes). `ErreurModele` (message en français, toutes
  les fautes listées d'un coup) si le fichier est illisible ou si un champ obligatoire manque.
- `Plan.valider() -> list[str]` : incohérences (cote fausse, ligne qui ne touche pas son équipement,
  chambre sans porte, identifiant en double, calque ou type inconnu, orientation invalide…). [] = cohérent.
- `Plan.donnees` = le dict brut du fichier (jamais modifié) ; `Plan.murs`, `.portes`, `.lignes`… = listes
  de dicts normalisés (points en tuples de flottants, défauts appliqués, clés inconnues conservées).
- `Plan.bbox()` : boîte englobante (m) de tout ce qui est dessiné, cotes comprises avec leur décalage.

Usage :
    from modele import charger
    plan = charger(".../plan/plan.json")
    for message in plan.valider(): print(message)
"""
from __future__ import annotations

import copy
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geometrie as geo  # noqa: E402

VERSION = 1

# ---------- calques (ordre d'affichage : le premier est dessous) ----------
CALQUES_AVANT = (
    ("plan_de_base", "Plan de base"),
    ("cotes", "Cotes"),
    ("froid_equipements", "Froid – évaporateurs et centrales"),
    ("froid_cuivres", "Froid – cuivres et condensats"),
    ("electricite", "Électricité (froid + clim)"),
    ("clim_equipements", "Clim – splits et moteur"),
    ("clim_cuivres", "Clim – cuivres"),
)
CALQUES_APRES = (("croisements", "Croisements"), ("cartouche", "Cartouche"))
NOMS_CALQUES = dict(CALQUES_AVANT + CALQUES_APRES)
LEGENDE_COURTE = {
    "plan_de_base": "Plan de base", "cotes": "Cotes", "froid_equipements": "Froid : équip.",
    "froid_cuivres": "Froid : cuivres", "electricite": "Électricité", "clim_equipements": "Clim : équip.",
    "clim_cuivres": "Clim : cuivres", "croisements": "Croisements",
}
CALQUES_RESEAUX = ("froid_cuivres", "electricite", "clim_cuivres")   # + calques libres

# ---------- équipements ----------
DIMENSIONS_PAR_TYPE = {   # [longueur, profondeur] en m, avant rotation
    "evaporateur": (1.2, 0.5), "centrale": (1.5, 0.8), "groupe": (1.0, 0.6), "condenseur": (1.2, 0.5),
    "split": (0.9, 0.3), "moteur": (0.9, 0.35), "tableau": (0.6, 0.2), "autre": (0.5, 0.5),
}
CALQUE_PAR_TYPE_EQUIPEMENT = {
    "evaporateur": "froid_equipements", "centrale": "froid_equipements", "groupe": "froid_equipements",
    "condenseur": "froid_equipements", "split": "clim_equipements", "moteur": "clim_equipements",
    "tableau": "electricite", "autre": "plan_de_base",
}
SOUFFLAGES = {"gauche": (-1.0, 0.0), "droite": (1.0, 0.0), "haut": (0.0, -1.0), "bas": (0.0, 1.0)}

# ---------- lignes ----------
TYPES_LIGNE = {   # type → calque standard
    "aspiration": "froid_cuivres", "liquide": "froid_cuivres", "condensats": "froid_cuivres",
    "clim_gaz": "clim_cuivres", "clim_liquide": "clim_cuivres",
    "cable": "electricite", "chemin_cables": "electricite",
}
HAUTEURS_DEFAUT = {
    "evaporateur": 2.30, "passage_froid": 2.60, "raccord_groupe": 0.50,
    "tableau": 1.50, "chemin_cables": 2.80, "reserve_cable": 1.00,
    "split": 2.20, "passage_clim": 2.20, "raccord_moteur": 0.50,
    "passage_condensats": 2.30, "evacuation_condensats": 0.10,
}
TRAITS = ("simple", "double")

# ---------- murs, portes, chambres, cotes ----------
EPAISSEUR_PAR_TYPE_MUR = {"exterieur": 0.20, "cloison": 0.10}
ALIGNEMENTS = ("axe", "gauche", "droite")
ORIENTATIONS = (0, 90, 180, 270)
SENS_PORTE = ("gauche", "droite")
PANNEAU_PAR_REGIME = {"positif": 80, "negatif": 120}
COTES_COTE = ("haut", "bas", "gauche", "droite")
DECALAGE_COTE_DEFAUT = 0.6
EPAISSEUR_FENETRE_DEFAUT = 0.20
DIAMETRE_CROISEMENT = 0.40

TOLERANCE_COTE = 0.01        # |distance(de, a) − valeur| admis (m)
TOLERANCE_EXTREMITE = 0.15   # extrémité de ligne ↔ son équipement (m)
TOLERANCE_MUR = 0.05         # charnière de porte / centre de fenêtre ↔ son mur (m)

FORMATS = ("A4",)
ORIENTATIONS_PAGE = ("auto", "paysage", "portrait")
ECHELLES = (50, 75, 100, 125, 150, 200, 250, 300, 400, 500, 750, 1000)   # = echelle.ECHELLES

MOTIF_ID = re.compile(r"^\w[\w.\-]{0,59}$")
MOTIF_COULEUR = re.compile(r"^#[0-9A-Fa-f]{6}$")
IDS_RESERVES = {"0", "1"}
PREFIXES_RESERVES = ("cartouche", "legende", "barre-echelle", "regle-controle", "metre")
SUFFIXES_RESERVES = {"txt", "int", "porte", "porte-ouv", "ouv", "fl", "a1", "a2", "contour"}

COLLECTIONS = ("murs", "pieces", "chambres_froides", "portes", "fenetres", "equipements", "cotes", "lignes")


class ErreurModele(ValueError):
    """`plan.json` illisible ou incomplet : le message liste toutes les fautes, en français."""


def nombre_fr(v: float, decimales: int = 2) -> str:
    return f"{v:.{decimales}f}".replace(".", ",")


def _pt(p) -> str:
    return f"({nombre_fr(p[0])} ; {nombre_fr(p[1])})"


# ======================================================================
# Géométrie dérivée du modèle (utilisée par drawio.py, la comparaison et la validation)
# ======================================================================
def vecteurs_porte(orientation: float, sens: str = "gauche") -> tuple[tuple[float, float], tuple[float, float]]:
    """(direction d'ouverture le long du mur depuis la charnière, direction du battant) d'une porte.

    `mxgraph.floorplan.doorLeft` (sens « gauche ») à 0° : charnière à gauche, ouverture vers +x, battant
    vers +y. `doorRight` (sens « droite ») : ouverture vers −x, battant vers +y. La rotation draw.io tourne
    les deux vecteurs dans le sens horaire.
    """
    ouverture = geo.rotation_vecteur((1.0, 0.0) if sens != "droite" else (-1.0, 0.0), orientation)
    battant = geo.rotation_vecteur((0.0, 1.0), orientation)
    return ouverture, battant


def emprise_porte(porte: dict) -> list[tuple[float, float]]:
    """Quatre coins du carré balayé par le battant : charnière, bout de l'ouverture, etc. (m)."""
    o, b = vecteurs_porte(porte["orientation"], porte.get("sens", "gauche"))
    (x, y), w = porte["position"], porte["largeur"]
    return [(x, y), (x + o[0] * w, y + o[1] * w), (x + (o[0] + b[0]) * w, y + (o[1] + b[1]) * w),
            (x + b[0] * w, y + b[1] * w)]


def axe_mur(mur: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    """Axe réel du mur (de, a) une fois l'alignement appliqué : « axe » (défaut) = de/a sont sur l'axe ;
    « droite » = l'épaisseur est à droite du sens de/a vu sur le plan (contour décrit dans le sens horaire
    → épaisseur vers l'intérieur) ; « gauche » = à gauche."""
    (x1, y1), (x2, y2) = mur["de"], mur["a"]
    al = mur.get("alignement", "axe")
    l = math.hypot(x2 - x1, y2 - y1)
    if al not in ("gauche", "droite") or l < 1e-12:
        return (x1, y1), (x2, y2)
    ux, uy = (x2 - x1) / l, (y2 - y1) / l
    rx, ry = -uy, ux                      # normale « à droite » (y vers le bas)
    k = mur["epaisseur"] / 2.0 * (1.0 if al == "droite" else -1.0)
    return (x1 + rx * k, y1 + ry * k), (x2 + rx * k, y2 + ry * k)


def coins_mur(mur: dict) -> list[tuple[float, float]]:
    (x1, y1), (x2, y2) = axe_mur(mur)
    l = math.hypot(x2 - x1, y2 - y1)
    centre = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
    angle = math.degrees(math.atan2(y2 - y1, x2 - x1)) if l > 1e-12 else 0.0
    return geo.rotation_rectangle(centre, (l, mur["epaisseur"]), angle)


def coins_equipement(eq: dict) -> list[tuple[float, float]]:
    return geo.rotation_rectangle(eq["position"], eq["dimensions"], eq.get("rotation", 0))


def coins_fenetre(fenetre: dict) -> list[tuple[float, float]]:
    return geo.rotation_rectangle(fenetre["position"], (fenetre["largeur"], fenetre["epaisseur"]),
                                  fenetre.get("orientation", 0))


def rectangle_chambre(chambre: dict) -> tuple[float, float, float, float]:
    return geo.boite_englobante(chambre["polygone"])


def normale_cote(cote: dict) -> tuple[float, float] | None:
    """Vecteur unitaire de décalage de la ligne de cote vers son côté (haut, bas, gauche, droite), ou None
    si le côté est incompatible avec la direction (cote horizontale « à gauche », par exemple)."""
    (x1, y1), (x2, y2) = cote["de"], cote["a"]
    l = math.hypot(x2 - x1, y2 - y1)
    if l < 1e-12:
        return None
    n = (-(y2 - y1) / l, (x2 - x1) / l)
    cote_ = cote.get("cote")
    axe, signe = {"haut": (1, -1), "bas": (1, 1), "gauche": (0, -1), "droite": (0, 1)}.get(cote_, (None, None))
    if axe is None or abs(n[axe]) < 1e-9:
        return None
    if n[axe] * signe < 0:
        n = (-n[0], -n[1])
    return (n[0] + 0.0, n[1] + 0.0)


def ligne_de_cote(cote: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    """Extrémités de la ligne de cote dessinée (m) : de/a décalés de `decalage` vers le côté `cote`."""
    n = normale_cote(cote) or (0.0, 0.0)
    d = cote.get("decalage", DECALAGE_COTE_DEFAUT)
    (x1, y1), (x2, y2) = cote["de"], cote["a"]
    return (x1 + n[0] * d, y1 + n[1] * d), (x2 + n[0] * d, y2 + n[1] * d)


def texte_cote(valeur: float) -> str:
    """12.5 → « 12,50 m »."""
    return f"{nombre_fr(valeur)} m"


def _direction_dominante(dx: float, dy: float) -> str:
    if abs(dx) >= abs(dy):
        return "droite" if dx >= 0 else "gauche"
    return "bas" if dy >= 0 else "haut"


# ======================================================================
# Normalisation (chargement)
# ======================================================================
class _Normaliseur:
    def __init__(self):
        self.fautes: list[str] = []

    def faute(self, ou: str, message: str) -> None:
        self.fautes.append(f"{ou} : {message}")

    @staticmethod
    def _est_nombre(v) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

    def nombre(self, d: dict, cle: str, ou: str, obligatoire: bool = False, defaut=None):
        if cle not in d or d[cle] is None:
            if obligatoire:
                self.faute(ou, f"champ « {cle} » manquant (nombre attendu)")
            return defaut
        v = d[cle]
        if not self._est_nombre(v):
            self.faute(ou, f"« {cle} » doit être un nombre, trouvé {v!r}")
            return defaut
        return float(v)

    def point(self, v, ou: str, cle: str, obligatoire: bool = True):
        if v is None:
            if obligatoire:
                self.faute(ou, f"champ « {cle} » manquant (point [x, y] en m attendu)")
            return None
        if not isinstance(v, (list, tuple)) or len(v) != 2 or not all(self._est_nombre(c) for c in v):
            self.faute(ou, f"« {cle} » doit être un point [x, y] en mètres, trouvé {v!r}")
            return None
        return (float(v[0]), float(v[1]))

    def points(self, v, ou: str, cle: str):
        if v is None:
            self.faute(ou, f"champ « {cle} » manquant (liste de points [[x, y], …] attendue)")
            return None
        if not isinstance(v, (list, tuple)):
            self.faute(ou, f"« {cle} » doit être une liste de points, trouvé {v!r}")
            return None
        res = []
        for i, p in enumerate(v):
            q = self.point(p, ou, f"{cle}[{i}]")
            if q is None:
                return None
            res.append(q)
        return res

    def texte(self, d: dict, cle: str, ou: str, obligatoire: bool = False, defaut=None):
        if cle not in d or d[cle] is None:
            if obligatoire:
                self.faute(ou, f"champ « {cle} » manquant (texte attendu)")
            return defaut
        if not isinstance(d[cle], str):
            self.faute(ou, f"« {cle} » doit être un texte, trouvé {d[cle]!r}")
            return defaut
        return d[cle]

    def liste(self, donnees: dict, cle: str) -> list:
        v = donnees.get(cle)
        if v is None:
            return []
        if not isinstance(v, list):
            self.faute(cle, f"doit être une liste, trouvé {type(v).__name__}")
            return []
        return v

    def element(self, collection: str, i: int, e) -> tuple[dict | None, str]:
        ou = f"{collection}[{i}]"
        if not isinstance(e, dict):
            self.faute(ou, f"doit être un objet JSON, trouvé {e!r}")
            return None, ou
        ident = e.get("id")
        if not isinstance(ident, str) or not ident.strip():
            self.faute(ou, "champ « id » manquant ou vide")
            return None, ou
        return dict(e), f"{collection}[{i}] « {ident} »"


def _normaliser(donnees: dict) -> dict:
    n = _Normaliseur()
    r: dict = {}

    page = donnees.get("page") or {}
    if not isinstance(page, dict):
        n.faute("page", "doit être un objet {format, orientation, echelle}")
        page = {}
    r["page"] = {"format": "A4", "orientation": "auto", "echelle": None, **page}

    hauteurs = donnees.get("hauteurs") or {}
    if not isinstance(hauteurs, dict):
        n.faute("hauteurs", "doit être un objet {nom: hauteur en m}")
        hauteurs = {}
    h = dict(HAUTEURS_DEFAUT)
    for cle, v in hauteurs.items():
        val = n.nombre(hauteurs, cle, f"hauteurs.{cle}", defaut=None)
        if val is not None:
            h[cle] = val
    r["hauteurs"] = h
    validees = donnees.get("hauteurs_validees", False)
    if validees is None:
        validees = False
    if not isinstance(validees, bool) and not (isinstance(validees, list)
                                               and all(isinstance(x, str) for x in validees)):
        n.faute("hauteurs_validees", "doit être un booléen ou une liste de noms de hauteurs")
        validees = False
    r["hauteurs_validees"] = validees

    # murs
    murs = []
    for i, e in enumerate(n.liste(donnees, "murs")):
        m, ou = n.element("murs", i, e)
        if m is None:
            continue
        de, a = n.point(m.get("de"), ou, "de"), n.point(m.get("a"), ou, "a")
        m["type"] = n.texte(m, "type", ou, defaut="exterieur")
        m["epaisseur"] = n.nombre(m, "epaisseur", ou, defaut=EPAISSEUR_PAR_TYPE_MUR.get(m["type"], 0.20))
        m["alignement"] = n.texte(m, "alignement", ou, defaut="axe")
        if de is None or a is None:
            continue
        m["de"], m["a"] = de, a
        murs.append(m)
    r["murs"] = murs
    murs_par_id = {m["id"]: m for m in murs}

    # pièces
    pieces = []
    for i, e in enumerate(n.liste(donnees, "pieces")):
        p, ou = n.element("pieces", i, e)
        if p is None:
            continue
        poly = n.points(p.get("polygone"), ou, "polygone")
        p["nom"] = n.texte(p, "nom", ou, defaut="")
        p["etiquette"] = n.texte(p, "etiquette", ou, defaut=None)
        p["position_etiquette"] = n.point(p.get("position_etiquette"), ou, "position_etiquette", obligatoire=False)
        p["contour"] = bool(p.get("contour", False))
        if poly is None:
            continue
        p["polygone"] = poly
        pieces.append(p)
    r["pieces"] = pieces

    def porte_normalisee(d: dict, ou: str) -> dict | None:
        q = dict(d)
        pos = n.point(q.get("position"), ou, "position")
        q["largeur"] = n.nombre(q, "largeur", ou, obligatoire=True)
        q["orientation"] = n.nombre(q, "orientation", ou, defaut=0.0)
        q["sens"] = n.texte(q, "sens", ou, defaut="gauche")
        if pos is None or q["largeur"] is None:
            return None
        q["position"] = pos
        return q

    # chambres froides
    chambres = []
    for i, e in enumerate(n.liste(donnees, "chambres_froides")):
        c, ou = n.element("chambres_froides", i, e)
        if c is None:
            continue
        poly = n.points(c.get("polygone"), ou, "polygone")
        c["nom"] = n.texte(c, "nom", ou, defaut="")
        c["regime"] = n.texte(c, "regime", ou, defaut="positif")
        c["panneau_mm"] = n.nombre(c, "panneau_mm", ou, defaut=float(PANNEAU_PAR_REGIME.get(c["regime"], 80)))
        c["etiquette"] = n.texte(c, "etiquette", ou, defaut=None)
        c["position_etiquette"] = n.point(c.get("position_etiquette"), ou, "position_etiquette", obligatoire=False)
        porte = c.get("porte")
        if porte is not None:
            if not isinstance(porte, dict):
                n.faute(ou, f"« porte » doit être un objet {{position, largeur, orientation}}, trouvé {porte!r}")
                porte = None
            else:
                porte = porte_normalisee(porte, f"{ou}.porte")
        c["porte"] = porte
        if poly is None:
            continue
        c["polygone"] = poly
        chambres.append(c)
    r["chambres_froides"] = chambres

    # portes
    portes = []
    for i, e in enumerate(n.liste(donnees, "portes")):
        p, ou = n.element("portes", i, e)
        if p is None:
            continue
        p["dans"] = n.texte(p, "dans", ou, defaut=None)
        q = porte_normalisee(p, ou)
        if q is not None:
            portes.append(q)
    r["portes"] = portes

    # fenêtres
    fenetres = []
    for i, e in enumerate(n.liste(donnees, "fenetres")):
        f, ou = n.element("fenetres", i, e)
        if f is None:
            continue
        pos = n.point(f.get("position"), ou, "position")
        f["largeur"] = n.nombre(f, "largeur", ou, obligatoire=True)
        f["orientation"] = n.nombre(f, "orientation", ou, defaut=0.0)
        f["dans"] = n.texte(f, "dans", ou, defaut=None)
        mur = murs_par_id.get(f["dans"]) if f["dans"] else None
        f["epaisseur"] = n.nombre(f, "epaisseur", ou,
                                  defaut=mur["epaisseur"] if mur else EPAISSEUR_FENETRE_DEFAUT)
        if pos is None or f["largeur"] is None:
            continue
        f["position"] = pos
        fenetres.append(f)
    r["fenetres"] = fenetres

    # équipements
    equipements = []
    for i, e in enumerate(n.liste(donnees, "equipements")):
        q, ou = n.element("equipements", i, e)
        if q is None:
            continue
        q["type"] = n.texte(q, "type", ou, obligatoire=True)
        pos = n.point(q.get("position"), ou, "position")
        defaut = DIMENSIONS_PAR_TYPE.get(q["type"], DIMENSIONS_PAR_TYPE["autre"])
        dims = q.get("dimensions")
        if dims is None:
            q["dimensions"] = tuple(defaut)
        else:
            d = n.point(dims, ou, "dimensions")
            q["dimensions"] = d if d is not None else tuple(defaut)
        q["rotation"] = n.nombre(q, "rotation", ou, defaut=0.0)
        q["nom"] = n.texte(q, "nom", ou, defaut="")
        q["chambre"] = n.texte(q, "chambre", ou, defaut=None)
        q["soufflage"] = n.texte(q, "soufflage", ou, defaut=None)
        q["calque"] = n.texte(q, "calque", ou, defaut=CALQUE_PAR_TYPE_EQUIPEMENT.get(q["type"], "plan_de_base"))
        q["etiquette"] = n.texte(q, "etiquette", ou, defaut=None)
        q["position_etiquette"] = n.point(q.get("position_etiquette"), ou, "position_etiquette", obligatoire=False)
        q["hauteur"] = n.nombre(q, "hauteur", ou, defaut=None)
        if pos is None or q["type"] is None:
            continue
        q["position"] = pos
        equipements.append(q)
    r["equipements"] = equipements

    # cotes
    cotes = []
    for i, e in enumerate(n.liste(donnees, "cotes")):
        c, ou = n.element("cotes", i, e)
        if c is None:
            continue
        de, a = n.point(c.get("de"), ou, "de"), n.point(c.get("a"), ou, "a")
        c["valeur"] = n.nombre(c, "valeur", ou, obligatoire=True)
        c["source"] = n.texte(c, "source", ou, defaut=None)
        c["decalage"] = n.nombre(c, "decalage", ou, defaut=DECALAGE_COTE_DEFAUT)
        cote_ = n.texte(c, "cote", ou, defaut=None)
        if de is None or a is None or c["valeur"] is None:
            continue
        if cote_ is None:
            cote_ = "haut" if abs(a[0] - de[0]) >= abs(a[1] - de[1]) else "gauche"
        c["de"], c["a"], c["cote"] = de, a, cote_
        cotes.append(c)
    r["cotes"] = cotes

    # calques libres
    libres = []
    for i, e in enumerate(n.liste(donnees, "calques_libres")):
        ou = f"calques_libres[{i}]"
        if not isinstance(e, dict):
            n.faute(ou, f"doit être un objet {{cle, nom, couleur, trait}}, trouvé {e!r}")
            continue
        q = dict(e)
        q["cle"] = n.texte(q, "cle", ou, obligatoire=True)
        q["nom"] = n.texte(q, "nom", ou, defaut=q["cle"])
        q["couleur"] = n.texte(q, "couleur", ou, defaut="#455A64")
        q["trait"] = n.texte(q, "trait", ou, defaut="simple")
        for cle in ("hauteur_depart", "hauteur_passage", "hauteur_arrivee"):
            q[cle] = n.nombre(q, cle, ou, defaut=None)
        if q["cle"] is None:
            continue
        libres.append(q)
    r["calques_libres"] = libres
    cles_libres = {q["cle"] for q in libres}

    # lignes
    lignes = []
    for i, e in enumerate(n.liste(donnees, "lignes")):
        l, ou = n.element("lignes", i, e)
        if l is None:
            continue
        l["type"] = n.texte(l, "type", ou, obligatoire=True)
        pts = n.points(l.get("points"), ou, "points")
        calque_defaut = TYPES_LIGNE.get(l["type"]) or (l["type"] if l["type"] in cles_libres else None)
        l["calque"] = n.texte(l, "calque", ou, defaut=calque_defaut)
        l["de"] = n.texte(l, "de", ou, defaut=None)
        l["a"] = n.texte(l, "a", ou, defaut=None)
        l["diametre"] = l.get("diametre", "à définir")
        l["faisceau"] = l.get("faisceau")
        for cle in ("hauteur_depart", "hauteur_arrivee", "hauteur_passage"):
            l[cle] = n.nombre(l, cle, ou, defaut=None)
        l["repere"] = n.texte(l, "repere", ou, defaut=None)
        l["etiquette"] = n.texte(l, "etiquette", ou, defaut=None)
        # longueur mesurée sur chantier par le frigoriste (décision du 2026-10-08) : retenue par le métré
        l["longueur_mesuree"] = n.nombre(l, "longueur_mesuree", ou, defaut=None)
        mesure = l.get("mesure")
        if mesure is not None and not isinstance(mesure, dict):
            n.faute(ou, f"« mesure » doit être un objet {{par, date, note}}, trouvé {mesure!r}")
            l["mesure"] = None
        elif isinstance(mesure, dict):
            for cle in ("par", "date", "note"):
                n.texte(mesure, cle, f"{ou}, mesure")
            l["mesure"] = dict(mesure)
        else:
            l["mesure"] = None
        l["position_etiquette"] = n.point(l.get("position_etiquette"), ou, "position_etiquette", obligatoire=False)
        if pts is None or l["type"] is None:
            continue
        l["points"] = pts
        lignes.append(l)
    r["lignes"] = lignes

    # exigences, notes, croisements
    ex = donnees.get("exigences") or {}
    if not isinstance(ex, dict):
        n.faute("exigences", "doit être un objet {identifiant: {…, motif}}")
        ex = {}
    r["exigences"] = ex
    notes = donnees.get("notes") or []
    if not isinstance(notes, list) or not all(isinstance(x, str) for x in notes):
        n.faute("notes", "doit être une liste de textes")
        notes = []
    r["notes"] = notes
    croisements = []
    for i, e in enumerate(n.liste(donnees, "croisements")):
        x, ou = n.element("croisements", i, e)
        if x is None:
            continue
        pt = n.point(x.get("point"), ou, "point")
        if pt is None:
            continue
        x["point"] = pt
        croisements.append(x)
    r["croisements"] = croisements

    if n.fautes:
        raise ErreurModele("plan.json incomplet ou mal formé :\n- " + "\n- ".join(n.fautes))
    return r


# ======================================================================
# Plan
# ======================================================================
class Plan:
    """Modèle normalisé d'un plan. Voir le docstring du module."""

    def __init__(self, donnees: dict, chemin: str | Path | None = None):
        if not isinstance(donnees, dict):
            raise ErreurModele(f"plan.json : la racine doit être un objet JSON, trouvé {type(donnees).__name__}.")
        self.donnees = copy.deepcopy(donnees)
        self.chemin = Path(chemin) if chemin else None
        r = _normaliser(donnees)
        self.version = donnees.get("version", VERSION)
        self.titre = donnees.get("titre") or ""
        self.dossier = donnees.get("dossier") or ""
        self.date = donnees.get("date") or ""
        self.page = r["page"]
        self.hauteurs = r["hauteurs"]
        self.hauteurs_validees = r["hauteurs_validees"]   # bool, ou liste des hauteurs validées par le frigoriste
        self.murs = r["murs"]
        self.pieces = r["pieces"]
        self.chambres_froides = r["chambres_froides"]
        self.portes = r["portes"]
        self.fenetres = r["fenetres"]
        self.equipements = r["equipements"]
        self.cotes = r["cotes"]
        self.lignes = r["lignes"]
        self.calques_libres = r["calques_libres"]
        self.exigences = r["exigences"]
        self.notes = r["notes"]
        self.croisements = r["croisements"]

    # ---------- accès ----------
    def _index(self) -> dict[str, tuple[str, dict]]:
        idx: dict[str, tuple[str, dict]] = {}
        for col in COLLECTIONS:
            for e in getattr(self, col):
                idx.setdefault(e["id"], (col, e))
        for x in self.croisements:
            idx.setdefault(x["id"], ("croisements", x))
        return idx

    def element(self, ident: str) -> tuple[str, dict]:
        """(collection, élément) pour un identifiant ; KeyError s'il n'existe pas."""
        idx = self._index()
        if ident not in idx:
            raise KeyError(f"identifiant inconnu dans le plan : {ident}")
        return idx[ident]

    def equipement(self, ident: str) -> dict:
        for e in self.equipements:
            if e["id"] == ident:
                return e
        raise KeyError(f"équipement inconnu : {ident}")

    def ligne(self, ident: str) -> dict:
        for e in self.lignes:
            if e["id"] == ident:
                return e
        raise KeyError(f"ligne inconnue : {ident}")

    def chambre(self, ident: str) -> dict:
        for e in self.chambres_froides:
            if e["id"] == ident:
                return e
        raise KeyError(f"chambre froide inconnue : {ident}")

    def mur(self, ident: str) -> dict:
        for e in self.murs:
            if e["id"] == ident:
                return e
        raise KeyError(f"mur inconnu : {ident}")

    def calques(self) -> list[tuple[str, str]]:
        """Calques draw.io dans l'ordre d'affichage : standard, puis calques libres, puis croisements, cartouche."""
        libres = [(q["cle"], q["nom"]) for q in self.calques_libres]
        return list(CALQUES_AVANT) + libres + list(CALQUES_APRES)

    def calque_libre(self, cle: str) -> dict | None:
        for q in self.calques_libres:
            if q["cle"] == cle:
                return q
        return None

    def soufflage(self, eq: dict) -> str:
        """Sens de soufflage d'un évaporateur : celui du modèle, sinon vers la porte de sa chambre, sinon « bas »."""
        if eq.get("soufflage") in SOUFFLAGES:
            return eq["soufflage"]
        if eq.get("chambre"):
            try:
                ch = self.chambre(eq["chambre"])
            except KeyError:
                ch = None
            if ch and ch.get("porte"):
                p = ch["porte"]
                o, _ = vecteurs_porte(p["orientation"], p.get("sens", "gauche"))
                cx = p["position"][0] + o[0] * p["largeur"] / 2.0
                cy = p["position"][1] + o[1] * p["largeur"] / 2.0
                return _direction_dominante(cx - eq["position"][0], cy - eq["position"][1])
        return "bas"

    def contour_objet(self, ident: str) -> tuple[str, list] | None:
        """Géométrie d'un objet auquel une ligne peut se raccorder : ("polygone" | "polyligne", points)."""
        try:
            col, e = self.element(ident)
        except KeyError:
            return None
        if col == "equipements":
            return "polygone", coins_equipement(e)
        if col == "chambres_froides":
            return "polygone", list(e["polygone"])
        if col == "murs":
            return "polygone", coins_mur(e)
        if col == "pieces":
            return "polygone", list(e["polygone"])
        if col == "lignes":
            return "polyligne", list(e["points"])
        return None

    def distance_a_objet(self, point, ident: str) -> float | None:
        c = self.contour_objet(ident)
        if c is None:
            return None
        genre, pts = c
        if genre == "polyligne":
            return geo.distance_point_polyligne(point, pts)
        return geo.distance_point_polygone(point, pts)

    # ---------- boîte englobante ----------
    def bbox(self) -> tuple[float, float, float, float]:
        """(xmin, ymin, xmax, ymax) en m de tout ce qui est dessiné (murs, pièces, chambres, portes et leur
        battant, fenêtres, équipements, lignes, cotes à leur décalage, croisements, ancres d'étiquettes)."""
        pts: list = []
        for m in self.murs:
            pts += coins_mur(m)
        for p in self.pieces:
            pts += p["polygone"]
            if p.get("position_etiquette"):
                pts.append(p["position_etiquette"])
        for c in self.chambres_froides:
            pts += c["polygone"]
            if c.get("porte"):
                pts += emprise_porte(c["porte"])
            if c.get("position_etiquette"):
                pts.append(c["position_etiquette"])
        for p in self.portes:
            pts += emprise_porte(p)
        for f in self.fenetres:
            pts += coins_fenetre(f)
        for e in self.equipements:
            pts += coins_equipement(e)
            if e.get("position_etiquette"):
                pts.append(e["position_etiquette"])
        for l in self.lignes:
            pts += l["points"]
            if l.get("position_etiquette"):
                pts.append(l["position_etiquette"])
        for c in self.cotes:
            pts += [c["de"], c["a"], *ligne_de_cote(c)]
        r = DIAMETRE_CROISEMENT / 2.0
        for x in self.croisements:
            (cx, cy) = x["point"]
            pts += [(cx - r, cy - r), (cx + r, cy + r)]
        if not pts:
            return (0.0, 0.0, 0.0, 0.0)
        return geo.boite_englobante(pts)

    # ---------- validation ----------
    def valider(self) -> list[str]:
        """Liste des incohérences du modèle (messages en français) ; [] si tout est cohérent."""
        err: list[str] = []
        E = err.append

        if self.version != VERSION:
            E(f"Version du modèle {self.version!r} inconnue (attendu : {VERSION}).")
        pg = self.page
        if pg.get("format") not in FORMATS:
            E(f"Page : format « {pg.get('format')} » non géré (seul l'A4 est prévu).")
        if pg.get("orientation") not in ORIENTATIONS_PAGE:
            E(f"Page : orientation « {pg.get('orientation')} » invalide (attendu : auto, paysage ou portrait).")
        ech = pg.get("echelle")
        if ech is not None and (isinstance(ech, bool) or ech not in ECHELLES):
            E(f"Page : échelle imposée 1:{ech} non normalisée (valeurs possibles : "
              + ", ".join(str(s) for s in ECHELLES) + ").")
        for cle, v in self.hauteurs.items():
            if v < 0:
                E(f"Hauteur « {cle} » négative ({nombre_fr(v)} m).")
        if isinstance(self.hauteurs_validees, list):
            for cle in self.hauteurs_validees:
                if cle not in self.hauteurs:
                    E(f"hauteurs_validees : « {cle} » n'est pas une hauteur du plan.")

        # identifiants
        libres = [q["cle"] for q in self.calques_libres]
        calques_connus = set(NOMS_CALQUES) | set(libres)
        vus: dict[str, str] = {}
        tous = [(col, e["id"]) for col in COLLECTIONS for e in getattr(self, col)]
        tous += [("croisements", x["id"]) for x in self.croisements]
        for col, ident in tous:
            if ident in vus:
                E(f"Identifiant « {ident} » en double ({vus[ident]} et {col}) : chaque élément doit avoir son "
                  "propre identifiant (il devient l'identifiant de la cellule draw.io).")
            else:
                vus[ident] = col
            if not MOTIF_ID.match(ident):
                E(f"Identifiant « {ident} » ({col}) invalide : lettres, chiffres, « _ », « . », « - » seulement, "
                  "sans espace, 60 caractères au plus.")
            if ident in IDS_RESERVES or ident in calques_connus or ident.lower().startswith(PREFIXES_RESERVES):
                E(f"Identifiant « {ident} » ({col}) réservé (calque, cartouche ou cellule technique de draw.io).")
        for ident in vus:
            for autre in vus:
                if autre.startswith(ident + "-"):
                    suffixe = autre[len(ident) + 1:]
                    if suffixe in SUFFIXES_RESERVES or re.fullmatch(r"v\d+", suffixe):
                        E(f"Identifiant « {autre} » en conflit avec le sous-élément « -{suffixe} » de « {ident} ».")

        # murs
        murs = {m["id"]: m for m in self.murs}
        for m in self.murs:
            if m["type"] not in EPAISSEUR_PAR_TYPE_MUR:
                E(f"Mur {m['id']} : type « {m['type']} » inconnu (attendu : exterieur ou cloison).")
            if m["epaisseur"] is None or m["epaisseur"] <= 0:
                E(f"Mur {m['id']} : épaisseur nulle ou négative.")
            if geo.distance(m["de"], m["a"]) < 1e-6:
                E(f"Mur {m['id']} : longueur nulle (« de » = « a » = {_pt(m['de'])}).")
            if m["alignement"] not in ALIGNEMENTS:
                E(f"Mur {m['id']} : alignement « {m['alignement']} » inconnu (attendu : axe, gauche ou droite).")

        # pièces
        for p in self.pieces:
            if len(p["polygone"]) < 3 or geo.surface_polygone(p["polygone"]) < 1e-6:
                E(f"Pièce {p['id']} : polygone de moins de 3 points ou de surface nulle.")

        def verifier_porte(p: dict, nom: str) -> None:
            if p["orientation"] not in ORIENTATIONS:
                E(f"{nom} : orientation {nombre_fr(p['orientation'], 0)} invalide (attendu : 0, 90, 180 ou 270).")
            if p.get("sens", "gauche") not in SENS_PORTE:
                E(f"{nom} : sens « {p.get('sens')} » invalide (attendu : gauche ou droite).")
            if p["largeur"] <= 0:
                E(f"{nom} : largeur nulle ou négative.")

        def verifier_dans_mur(e: dict, nom: str, point, direction) -> None:
            if not e.get("dans"):
                return
            mur = murs.get(e["dans"])
            if mur is None:
                E(f"{nom} : mur « {e['dans']} » inconnu.")
                return
            d = geo.distance_point_polygone(point, coins_mur(mur))
            if d > TOLERANCE_MUR:
                E(f"{nom} : à {nombre_fr(d)} m du mur {mur['id']} (tolérance {nombre_fr(TOLERANCE_MUR)} m) ; "
                  "vérifier la position.")
            (x1, y1), (x2, y2) = axe_mur(mur)
            l = math.hypot(x2 - x1, y2 - y1)
            if l > 1e-9 and abs(direction[0] * (y2 - y1) / l - direction[1] * (x2 - x1) / l) > 0.01:
                E(f"{nom} : l'orientation {nombre_fr(e['orientation'], 0)}° n'est pas parallèle au mur {mur['id']}.")

        # chambres froides
        for c in self.chambres_froides:
            nom = f"Chambre froide {c['id']}"
            if not geo.est_rectangle_aligne(c["polygone"]):
                E(f"{nom} : seuls les rectangles aux côtés horizontaux et verticaux sont gérés (polygone de "
                  f"{len(c['polygone'])} points).")
            if c["regime"] not in PANNEAU_PAR_REGIME:
                E(f"{nom} : régime « {c['regime']} » inconnu (attendu : positif ou negatif).")
            if c["panneau_mm"] is None or c["panneau_mm"] <= 0:
                E(f"{nom} : épaisseur de panneau nulle ou négative.")
            if not c.get("porte"):
                E(f"{nom} : aucune porte (champ « porte » obligatoire : position de la charnière, largeur, "
                  "orientation).")
            else:
                verifier_porte(c["porte"], f"{nom}, porte")
                if len(c["polygone"]) >= 3:
                    n_ = len(c["polygone"])
                    d = min(geo.distance_point_segment(c["porte"]["position"], c["polygone"][k],
                                                       c["polygone"][(k + 1) % n_]) for k in range(n_))
                    if d > TOLERANCE_MUR:
                        E(f"{nom}, porte : charnière à {nombre_fr(d)} m du contour de la chambre.")

        # portes
        for p in self.portes:
            nom = f"Porte {p['id']}"
            verifier_porte(p, nom)
            if p["orientation"] in ORIENTATIONS:
                o, _ = vecteurs_porte(p["orientation"], p.get("sens", "gauche"))
                verifier_dans_mur(p, nom, p["position"], o)

        # fenêtres
        for f in self.fenetres:
            nom = f"Fenêtre {f['id']}"
            if f["orientation"] not in ORIENTATIONS:
                E(f"{nom} : orientation {nombre_fr(f['orientation'], 0)} invalide (attendu : 0, 90, 180 ou 270).")
            if f["largeur"] <= 0 or f["epaisseur"] <= 0:
                E(f"{nom} : largeur ou épaisseur nulle ou négative.")
            if f["orientation"] in ORIENTATIONS:
                verifier_dans_mur(f, nom, f["position"], geo.rotation_vecteur((1.0, 0.0), f["orientation"]))

        # équipements
        chambres = {c["id"]: c for c in self.chambres_froides}
        for q in self.equipements:
            nom = f"Équipement {q['id']}"
            if q["type"] not in DIMENSIONS_PAR_TYPE:
                E(f"{nom} : type « {q['type']} » inconnu (attendu : " + ", ".join(DIMENSIONS_PAR_TYPE) + ").")
            if q["dimensions"][0] <= 0 or q["dimensions"][1] <= 0:
                E(f"{nom} : dimensions nulles ou négatives.")
            if q.get("chambre") and q["chambre"] not in chambres:
                E(f"{nom} : chambre froide « {q['chambre']} » inconnue.")
            if q.get("soufflage") is not None and q["soufflage"] not in SOUFFLAGES:
                E(f"{nom} : soufflage « {q['soufflage']} » invalide (attendu : gauche, droite, haut ou bas).")
            if q["calque"] not in calques_connus or q["calque"] in ("croisements", "cartouche"):
                E(f"{nom} : calque « {q['calque']} » inconnu.")
            if q.get("hauteur") is not None and q["hauteur"] < 0:
                E(f"{nom} : hauteur négative.")

        # cotes
        for c in self.cotes:
            nom = f"Cote {c['id']}"
            d = geo.distance(c["de"], c["a"])
            if c["valeur"] <= 0:
                E(f"{nom} : valeur nulle ou négative.")
            if abs(d - c["valeur"]) > TOLERANCE_COTE + 1e-9:
                E(f"{nom} : la distance entre « de » {_pt(c['de'])} et « a » {_pt(c['a'])} vaut {nombre_fr(d, 3)} m "
                  f"mais la valeur mesurée est {nombre_fr(c['valeur'], 3)} m (écart {nombre_fr(abs(d - c['valeur']), 3)} m "
                  f"> {nombre_fr(TOLERANCE_COTE)} m) : la description est incohérente, demander la bonne cote.")
            if c["cote"] not in COTES_COTE:
                E(f"{nom} : côté « {c['cote']} » invalide (attendu : haut, bas, gauche ou droite).")
            elif d > 1e-9 and normale_cote(c) is None:
                E(f"{nom} : le côté « {c['cote']} » est incompatible avec une cote "
                  f"{'horizontale' if abs(c['a'][1] - c['de'][1]) < 1e-9 else 'verticale'}.")
            if c["decalage"] < 0:
                E(f"{nom} : décalage négatif.")

        # calques libres
        cles_vues = set()
        for q in self.calques_libres:
            cle = q["cle"]
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", cle):
                E(f"Calque libre « {cle} » : clé invalide (minuscules, chiffres et « _ », sans accent ni espace).")
            if cle in NOMS_CALQUES:
                E(f"Calque libre « {cle} » : la clé reprend celle d'un calque standard.")
            if cle in cles_vues:
                E(f"Calque libre « {cle} » déclaré deux fois.")
            cles_vues.add(cle)
            if not MOTIF_COULEUR.match(q["couleur"] or ""):
                E(f"Calque libre « {cle} » : couleur « {q['couleur']} » invalide (attendu : #RRGGBB).")
            if q["trait"] not in TRAITS:
                E(f"Calque libre « {cle} » : trait « {q['trait']} » invalide (attendu : simple ou double).")
            for h in ("hauteur_depart", "hauteur_passage", "hauteur_arrivee"):
                if q.get(h) is not None and q[h] < 0:
                    E(f"Calque libre « {cle} » : {h} négative.")

        # lignes
        for l in self.lignes:
            nom = f"Ligne {l['id']}"
            if l["type"] not in TYPES_LIGNE and l["type"] not in cles_vues:
                E(f"{nom} : type « {l['type']} » inconnu (attendu : " + ", ".join(TYPES_LIGNE)
                  + ", ou la clé d'un calque libre déclaré).")
            if l["calque"] is None or l["calque"] not in calques_connus or l["calque"] in (
                    "plan_de_base", "cotes", "croisements", "cartouche"):
                E(f"{nom} : calque « {l['calque']} » inconnu ou non prévu pour une ligne.")
            for h in ("hauteur_depart", "hauteur_passage", "hauteur_arrivee"):
                if l.get(h) is not None and l[h] < 0:
                    E(f"{nom} : {h} négative.")
            lm, mesure = l.get("longueur_mesuree"), l.get("mesure")
            if lm is not None and lm <= 0:
                E(f"{nom} : longueur mesurée de {nombre_fr(lm)} m : une longueur mesurée est positive (en mètres).")
            if lm is not None and not (isinstance(mesure, dict) and str(mesure.get("par") or "").strip()
                                       and str(mesure.get("date") or "").strip()):
                E(f"{nom} : longueur mesurée sans « mesure » complète : écrire qui l'a mesurée et quand "
                  '(« mesure » : {"par": "Loïc", "date": "AAAA-MM-JJ", "note": "…"}).')
            if mesure is not None and lm is None:
                E(f"{nom} : « mesure » sans « longueur_mesuree » : écrire la longueur mesurée (m) ou retirer « mesure ».")
            if isinstance(mesure, dict) and mesure.get("date") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}",
                                                                                    str(mesure["date"])):
                E(f"{nom} : date de mesure « {mesure['date']} » : format AAAA-MM-JJ attendu.")
            pts = l["points"]
            if len(pts) < 2:
                E(f"{nom} : il faut au moins deux points (départ et arrivée).")
            for k in range(len(pts) - 1):
                if geo.distance(pts[k], pts[k + 1]) < 1e-6:
                    E(f"{nom} : points {k} et {k + 1} confondus {_pt(pts[k])}.")
            for bout, cle, point in (("le point de départ", "de", pts[0] if pts else None),
                                     ("le point d'arrivée", "a", pts[-1] if pts else None)):
                ref = l.get(cle)
                if ref is None or point is None:
                    continue
                if ref == l["id"]:
                    E(f"{nom} : « {cle} » ne peut pas désigner la ligne elle-même.")
                    continue
                d = self.distance_a_objet(point, ref)
                if d is None:
                    E(f"{nom} : « {cle} » désigne « {ref} », qui n'est ni un équipement, ni une chambre, ni une "
                      "ligne, ni un mur du plan.")
                elif d > TOLERANCE_EXTREMITE + 1e-9:
                    E(f"{nom} : {bout} {_pt(point)} est à {nombre_fr(d)} m de « {ref} » "
                      f"(tolérance {nombre_fr(TOLERANCE_EXTREMITE)} m) : la ligne ne touche pas son équipement.")

        # exigences
        for cle, v in self.exigences.items():
            if cle not in vus:
                E(f"Exigence « {cle} » : identifiant inconnu dans le plan.")
            if not isinstance(v, dict):
                E(f"Exigence « {cle} » : doit être un objet {{…, motif}}.")
            elif not str(v.get("motif") or "").strip():
                E(f"Exigence « {cle} » : motif obligatoire (pourquoi l'exception).")
        return err


# ======================================================================
# Chargement
# ======================================================================
def depuis_dict(donnees: dict, chemin: str | Path | None = None) -> Plan:
    """Construit un `Plan` depuis un dict déjà chargé (tests, import draw.io)."""
    return Plan(donnees, chemin)


def charger(chemin: str | Path) -> Plan:
    """Lit `plan.json` (UTF-8) → `Plan`. `ErreurModele` si le fichier manque, n'est pas du JSON valide,
    ou si un champ obligatoire manque ou est mal typé (toutes les fautes sont listées)."""
    p = Path(chemin)
    if not p.is_file():
        raise ErreurModele(f"plan.json introuvable : {p}")
    try:
        texte = p.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise ErreurModele(f"plan.json illisible ({p}) : {exc}") from exc
    try:
        donnees = json.loads(texte)
    except json.JSONDecodeError as exc:
        raise ErreurModele(f"plan.json n'est pas du JSON valide ({p.name}, ligne {exc.lineno}, colonne {exc.colno}) : "
                           f"{exc.msg}.") from exc
    return Plan(donnees, p)
