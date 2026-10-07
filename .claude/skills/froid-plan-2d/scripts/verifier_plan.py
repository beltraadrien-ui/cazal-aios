"""Vérification d'un plan 2D : les 11 contrôles E1 à E11 (décision du 2026-10-07), relus depuis `plan.drawio`.

Principe : on ne fait JAMAIS confiance à la mémoire du générateur. Tout est relu depuis le fichier draw.io
(`drawio.lire`), reconverti en mètres, puis comparé au modèle `plan.json` ou recalculé (métré, croisements) ;
le PDF est mesuré avec PyMuPDF (règle n° 1 : « 15 m de cuivre annoncés = 15 m réels »).

| code | contrôle |
|---|---|
| E1 | échelle du fichier : page A4, pageScale 1, S normalisée, « 1:S » du cartouche, chaque élément relu = modèle à 0,01 m |
| E2 | cotes : longueur dessinée = valeur à 0,01 m, distance(de, a) du modèle = valeur, texte « 12,50 m » |
| E3 | barre d'échelle (longueur exacte à 0,5 px, texte) et règle de contrôle de 100 mm (393,70 px à 0,5 px) |
| E4 | toute la géométrie dans la zone utile (cartouche dans le cartouche) |
| E5 | complétude : chambres (porte, évaporateur, aspiration + liquide vers groupe/centrale, condensats, câble vers un tableau) ; splits (gaz + liquide vers un moteur, câble) ; `exigences` → avertissement motivé |
| E6 | tableaux de la page « Métré » et de `plan.md` = métré recalculé depuis les points RELUS, ligne par ligne |
| E7 | ellipses du calque « Croisements » = groupes recalculés (repères G, même nombre, centre à 0,05 m) ; tableaux = croisements individuels (point à 0,05 m, colonne Repère) |
| E8 | lisibilité : aucune boîte de texte sur une autre, sur une porte ou sur un équipement (sauf son propre élément) ; avertissement si un texte est posé sur le trait d'un autre élément (ligne, cote, attache, flèche) |
| E9 | cohérence : calques présents, rien sur l'emprise d'une porte ou d'une fenêtre, extrémités à 0,15 m de leur équipement, évaporateur face à la porte (avertissement), modèle valide |
| E10 | PDF : page A4 ± 1 pt, règle de contrôle 283,46 pt ± 0,3 pt, barre ± 0,5 pt, trois plus longs murs ± 1 pt |
| E11 | PNG : présent, page × 2 ± 2 px |

Usage (depuis la racine du dépôt) :
    python .claude/skills/froid-plan-2d/scripts/verifier_plan.py <dossier_plan> [--sans-pdf]
Sorties : `verification.md` (tableau code | gravité | élément | attendu | trouvé | conseil, résumé) et
`verification.json`. Code de retour : 0 (aucune erreur), 1 (erreurs), 2 (fichier manquant).
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import croisements as crx  # noqa: E402
import drawio  # noqa: E402
import geometrie as geo  # noqa: E402
import metre as mtr  # noqa: E402
import modele as mod  # noqa: E402
import rendu  # noqa: E402
from echelle import (ECHELLES, PT_PAR_MM, REGLE_CONTROLE_MM, ErreurEchelle, barre_echelle_m,  # noqa: E402
                     choisir_echelle, mm_vers_px, nombre_fr)

ERREUR = "erreur"
AVERTISSEMENT = "avertissement"
CONTROLES = {
    "E1": "Échelle du fichier", "E2": "Cotes", "E3": "Barre d'échelle et règle de contrôle", "E4": "Dans la page",
    "E5": "Complétude", "E6": "Tableaux de métré = recalcul", "E7": "Croisements", "E8": "Lisibilité",
    "E9": "Cohérence", "E10": "PDF à l'échelle", "E11": "Image PNG",
}
TOL_M = 0.01
TOL_BARRE_PX = 0.5
TOL_REGLE_PT = 0.3
TOL_BARRE_PT = 0.5
TOL_MUR_PT = 1.0
TOL_PAGE_PT = 1.0
TOL_PNG_PX = 2
TOL_CROISEMENT_M = 0.05
TOL_EXTREMITE_M = mod.TOLERANCE_EXTREMITE      # 0,15 m
TOL_EMPRISE_M = 0.01
TOL_ZONE_PX = 0.5
FACTEUR_CAR_E8 = 0.55                            # boîte de texte ≈ 0,55 × taille par caractère (E8)
TYPES_TRAITS_E8 = ("ligne", "cote", "decor", "piece_contour", "arete")   # arêtes relues : un texte posé dessus = avertissement
HAUTEUR_LIGNE_E8 = 1.2
A4_PT = (595.28, 841.89)
ANGLE_FACE_PORTE = 60.0
GENRES_PRODUCTION = ("groupe", "centrale", "condenseur")
FACTEUR_PNG = 2                                   # 200 dpi = 2 px par px draw.io
TITRE_CROISEMENTS_PAGE = "Croisements entre réseaux"


class FichierManquant(Exception):
    """Un fichier indispensable manque (code de retour 2)."""


# ======================================================================
# Rapport
# ======================================================================
class Rapport:
    def __init__(self):
        self.constats: list[dict] = []
        self.mesures: dict = {}
        self.ignores: dict[str, str] = {}

    def ajouter(self, code: str, gravite: str, element: str, attendu="", trouve="", conseil="") -> None:
        self.constats.append({"code": code, "gravite": gravite, "element": str(element or "—"),
                              "attendu": str(attendu if attendu is not None else ""),
                              "trouve": str(trouve if trouve is not None else ""), "conseil": str(conseil or "")})

    def erreur(self, code, element, attendu="", trouve="", conseil=""):
        self.ajouter(code, ERREUR, element, attendu, trouve, conseil)

    def avertir(self, code, element, attendu="", trouve="", conseil=""):
        self.ajouter(code, AVERTISSEMENT, element, attendu, trouve, conseil)

    def nombre(self, gravite: str, code: str | None = None) -> int:
        return sum(1 for c in self.constats if c["gravite"] == gravite and (code is None or c["code"] == code))

    def codes(self, gravite: str = ERREUR) -> set[str]:
        return {c["code"] for c in self.constats if c["gravite"] == gravite}


def _pt(p) -> str:
    return "—" if p is None else f"({nombre_fr(p[0])} ; {nombre_fr(p[1])})"


def _m(v, d=2) -> str:
    return "—" if v is None else f"{nombre_fr(v, d)} m"


def _ptx(v) -> str:
    return f"{nombre_fr(v, 2)} pt ({nombre_fr(v / PT_PAR_MM, 2)} mm)"


# ======================================================================
# Outils de lecture
# ======================================================================
def lire_nombre(texte: str) -> float | None:
    """« 1 234,50 (hyp.) » → 1234.5 ; None si illisible."""
    t = str(texte).replace("**", "").replace("(hyp.)", "").replace("(hyp)", "")
    t = re.sub(r"[\s\u00a0\u202f]", "", t).replace(",", ".").replace("\u2212", "-")
    try:
        return float(t)
    except ValueError:
        return None


RE_TR = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
RE_TD = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.S | re.I)


def rangs_html(table_html: str) -> list[list[str]]:
    return [[drawio.texte_brut(c) for c in RE_TD.findall(tr)] for tr in RE_TR.findall(table_html or "")]


def rangs_markdown(md: str, titre: str) -> list[list[str]] | None:
    """Premier tableau markdown qui suit le titre `titre` (ligne « ## … » ou « ### … ») ; None si absent."""
    lignes = md.splitlines()
    debut = None
    for i, l in enumerate(lignes):
        if re.match(r"^#{2,4}\s+" + re.escape(titre) + r"\s*$", l.strip()):
            debut = i + 1
            break
    if debut is None:
        return None
    rangs, dans = [], False
    for l in lignes[debut:]:
        s = l.strip()
        if s.startswith("|"):
            dans = True
            cellules = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s.strip("|"))]
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cellules if c):
                continue
            rangs.append(cellules)
        elif dans:
            break
        elif s.startswith("#"):
            return []
    return rangs


def texte_section(md: str, titre: str) -> str:
    m = re.search(r"^#{2,4}\s+" + re.escape(titre) + r"\s*$(.*?)(?=^#{1,4}\s|\Z)", md, flags=re.S | re.M)
    return m.group(1) if m else ""


def boite_e8(e: dict) -> tuple[float, float, float, float] | None:
    """Boîte d'un texte selon la règle E8 : 0,55 × taille × nb de caractères, 1,2 × taille par ligne, centrée sur la cellule."""
    b, t = e.get("boite_texte_px"), (e.get("texte") or "").strip()
    if not b or not t:
        return None
    taille = e.get("taille_police") or 11.0
    lignes = t.split("\n")
    w = FACTEUR_CAR_E8 * taille * max(len(l) for l in lignes)
    h = HAUTEUR_LIGNE_E8 * taille * len(lignes)
    cx, cy = (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0
    return (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)


def polygone_m(e: dict, ech) -> list[tuple[float, float]] | None:
    if e.get("coins_px"):
        return [ech.px_vers_m(*p) for p in e["coins_px"]]
    if e.get("points_m") and len(e["points_m"]) >= 3:
        return list(e["points_m"])
    return None


def emprise_porte_relue(e: dict) -> list[tuple[float, float]]:
    return mod.emprise_porte({"position": e["position_m"], "largeur": e["largeur_m"],
                              "orientation": e["orientation"], "sens": e.get("sens", "gauche")})


def recouvrement(p: list, q: list) -> float:
    """Profondeur de recouvrement de deux polygones convexes (axes séparateurs) ; ≤ 0 = disjoints."""
    meilleur = math.inf
    for poly in (p, q):
        n = len(poly)
        for i in range(n):
            a, b = poly[i], poly[(i + 1) % n]
            ax, ay = -(b[1] - a[1]), b[0] - a[0]
            l = math.hypot(ax, ay)
            if l < 1e-12:
                continue
            ax, ay = ax / l, ay / l
            pp = [x * ax + y * ay for x, y in p]
            qq = [x * ax + y * ay for x, y in q]
            meilleur = min(meilleur, min(max(pp), max(qq)) - max(min(pp), min(qq)))
    return meilleur


def profondeur_dans(point, poly) -> float:
    """Distance du point au bord s'il est DANS le polygone (bord exclu), sinon 0."""
    if not geo.point_dans_polygone(point, poly, bord=False):
        return 0.0
    n = len(poly)
    return min(geo.distance_point_segment(point, poly[i], poly[(i + 1) % n]) for i in range(n))


def modele_relu(lecture, brut: dict) -> dict:
    """Dict « plan.json » reconstruit depuis la LECTURE du dessin : lignes (type, calque, de, a, points en m relus)
    et types des équipements relus ; hauteurs, diamètres, faisceaux et calques libres repris de plan.json (ils
    ne sont pas dessinés)."""
    d = {k: copy.deepcopy(v) for k, v in brut.items() if k not in ("lignes", "croisements")}
    par_id = {l["id"]: l for l in brut.get("lignes") or [] if isinstance(l, dict) and l.get("id")}
    relues = {i: e for i, e in lecture.elements.items() if e.get("type") == "ligne" and e.get("points_m")}
    ordre = [i for i in par_id if i in relues] + [i for i in relues if i not in par_id]
    lignes = []
    for i in ordre:
        e, base = relues[i], copy.deepcopy(par_id.get(i, {}))
        base.update(id=i, type=e.get("genre") or base.get("type") or e.get("calque"),
                    calque=e.get("calque") or base.get("calque"),
                    de=e.get("de") if e.get("de") is not None else (base.get("de") if i in par_id else None),
                    a=e.get("a") if e.get("a") is not None else (base.get("a") if i in par_id else None),
                    points=[[p[0], p[1]] for p in e["points_m"]])
        lignes.append(base)
    d["lignes"] = lignes
    equipements = []
    for q in brut.get("equipements") or []:
        q = copy.deepcopy(q)
        e = lecture.elements.get(q.get("id"))
        if e and e.get("type") == "equipement" and e.get("genre") not in (None, "autre"):
            q["type"] = e["genre"]
        equipements.append(q)
    d["equipements"] = equipements
    return d


# ======================================================================
# Contexte et contrôles
# ======================================================================
class Contexte:
    def __init__(self, dossier: Path, sans_pdf: bool):
        self.dossier = dossier
        self.sans_pdf = sans_pdf
        self.rapport = Rapport()
        manquants = [n for n in ("plan.json", "plan.drawio", "plan.md") if not (dossier / n).is_file()]
        if manquants:
            raise FichierManquant(", ".join(manquants))
        try:
            self.brut = json.loads((dossier / "plan.json").read_text(encoding="utf-8-sig"))
            self.plan = mod.depuis_dict(self.brut, dossier / "plan.json")
        except (json.JSONDecodeError, mod.ErreurModele) as exc:
            raise FichierManquant(f"plan.json illisible : {exc}") from exc
        self.lecture = drawio.lire(dossier / "plan.drawio")
        self.ech = self.lecture.echelle
        self.md = (dossier / "plan.md").read_text(encoding="utf-8")
        self.elements = self.lecture.elements
        self._relu = None
        self._metre = None
        self._croisements = None

    def par_type(self, t: str) -> list[dict]:
        return [e for e in self.elements.values() if e.get("type") == t]

    @property
    def relu(self) -> dict:
        if self._relu is None:
            self._relu = modele_relu(self.lecture, self.brut)
        return self._relu

    @property
    def metre(self):
        if self._metre is None:
            self._metre = mtr.metrer(self.relu)
        return self._metre

    @property
    def croisements(self) -> list[dict]:
        if self._croisements is None:
            self._croisements = crx.croisements(self.relu)
        return self._croisements


def controle_e1(ctx: Contexte) -> None:
    R, L, ech = ctx.rapport, ctx.lecture, ctx.ech
    page = L.page
    if page.get("format") != "A4":
        R.erreur("E1", "page", "A4 : 1169 × 827 px (paysage) ou 827 × 1169 px (portrait)",
                 f"{nombre_fr(page.get('largeur_px') or 0, 0)} × {nombre_fr(page.get('hauteur_px') or 0, 0)} px",
                 "Remettre la page en A4 (Fichier > Mise en page) ou regénérer avec generer.py.")
    if abs((page.get("page_scale") or 1.0) - 1.0) > 1e-9:
        R.erreur("E1", "page", "pageScale = 1", f"pageScale = {page.get('page_scale')}",
                 "Un pageScale ≠ 1 change la taille de la page PDF : regénérer le plan.")
    if ech.S not in ECHELLES:
        R.erreur("E1", "cartouche-echelle", "échelle normalisée (" + ", ".join(f"1:{s}" for s in ECHELLES) + ")",
                 f"1:{ech.S}", "Regénérer le plan (generer.py choisit une échelle normalisée).")
    cell = L.brut.get("cartouche-echelle")
    texte = drawio.texte_brut(cell["valeur"]) if cell else ""
    s_style = cell["style"].get("plan2dS") if cell else None
    if f"1:{ech.S}" not in texte.replace(" ", "") or (s_style is not None and float(s_style) != float(ech.S)):
        R.erreur("E1", "cartouche-echelle", f"« Échelle 1:{ech.S} » et plan2dS = {ech.S}",
                 f"« {texte} », plan2dS = {s_style}", "Le cartouche doit dire l'échelle du dessin : regénérer.")
    # échelle attendue d'après le modèle
    impose = ctx.plan.page.get("echelle")
    if impose is not None and impose != ech.S:
        R.erreur("E1", "page.echelle", f"1:{impose} (imposée dans plan.json)", f"1:{ech.S} dans plan.drawio",
                 "Regénérer le plan.")
    else:
        try:
            donnees = copy.deepcopy(ctx.brut)
            donnees["croisements"] = crx.groupes_pour_dessin(crx.regrouper(crx.croisements(ctx.brut)))
            plan_x = mod.depuis_dict(donnees)
            attendue = choisir_echelle(plan_x.bbox(), plan_x.page)
            if (attendue.S, attendue.orientation) != (ech.S, ech.orientation):
                R.avertir("E1", "cartouche-echelle", f"1:{attendue.S} {attendue.orientation} (choix automatique "
                          "pour plan.json)", f"1:{ech.S} {ech.orientation}",
                          "plan.drawio n'est plus à jour avec plan.json : regénérer (generer.py).")
        except (ErreurEchelle, crx.ErreurCroisements, mod.ErreurModele, KeyError, TypeError):
            pass
    for e in drawio.comparer(ctx.plan, L, TOL_M):
        if e["categorie"] in ("cote", "croisement"):
            continue
        R.erreur("E1", e["id"], "= plan.json à 0,01 m", e["message"],
                 "Si l'élément a été déplacé à la souris : importer_drawio.py puis generer.py ; sinon regénérer.")
    connus = {x["id"] for col in mod.COLLECTIONS for x in getattr(ctx.plan, col)}
    for e in ctx.par_type("ligne") + ctx.par_type("equipement"):
        if e["id"] not in connus:
            R.avertir("E1", e["id"], "élément présent dans plan.json", f"{e['type']} ajouté(e) dans le dessin",
                      "Lancer importer_drawio.py pour le reprendre dans plan.json.")


def controle_e2(ctx: Contexte) -> None:
    R = ctx.rapport
    for e in drawio.comparer(ctx.plan, ctx.lecture, TOL_M):
        if e["categorie"] == "cote":
            R.erreur("E2", e["id"], "longueur dessinée = valeur à 0,01 m, texte « x,xx m »", e["message"],
                     "Regénérer le plan ; si la cote a été retouchée à la main dans draw.io, corriger plan.json.")
    for c in ctx.plan.cotes:
        d = geo.distance(c["de"], c["a"])
        if abs(d - c["valeur"]) > TOL_M + 1e-9:
            R.erreur("E2", c["id"], f"distance(de, a) = {_m(c['valeur'])}", _m(d, 3),
                     "La description est incohérente : redemander la cote au frigoriste (jamais d'estimation).")
    connues = {c["id"] for c in ctx.plan.cotes}
    for e in ctx.par_type("cote"):
        if e["id"] not in connues:
            R.avertir("E2", e["id"], "cote présente dans plan.json", f"cote « {e.get('texte')} » ajoutée au dessin",
                      "Reporter la cote dans plan.json (de, a, valeur, source).")


def controle_e3(ctx: Contexte) -> None:
    R, L, ech = ctx.rapport, ctx.lecture, ctx.ech
    nominal = barre_echelle_m(ech.S)
    attendu_px = nominal * ech.px_par_m
    if L.barre_echelle_px is None:
        R.erreur("E3", "barre-echelle", f"barre de {_m(nominal, 0)} = {nombre_fr(attendu_px)} px", "absente",
                 "Regénérer le plan.")
    elif abs(L.barre_echelle_px - attendu_px) > TOL_BARRE_PX:
        R.erreur("E3", "barre-echelle", f"{nombre_fr(attendu_px)} px ({_m(nominal, 0)} au 1:{ech.S})",
                 f"{nombre_fr(L.barre_echelle_px)} px", "La barre ne doit jamais être retouchée : regénérer.")
    txt = (L.elements.get("barre-echelle-txt") or {}).get("texte")
    if txt != f"{nombre_fr(nominal, 0)} m":
        R.erreur("E3", "barre-echelle-txt", f"« {nombre_fr(nominal, 0)} m »", f"« {txt} »", "Regénérer le plan.")
    cm = nominal * 1000.0 / ech.S / 10.0
    cm_txt = (f"{cm:.2f}".rstrip("0").rstrip(".")).replace(".", ",")
    mention = (L.elements.get("cartouche-mention") or {}).get("texte") or ""
    if f"{cm_txt} cm" not in mention:
        R.erreur("E3", "cartouche-mention", f"« … la barre doit mesurer {cm_txt} cm … »", f"« {mention} »",
                 "Regénérer le plan.")
    regle_px = mm_vers_px(REGLE_CONTROLE_MM)
    if L.regle_controle_px is None:
        R.erreur("E3", "regle-controle", f"règle de 100 mm = {nombre_fr(regle_px)} px", "absente", "Regénérer le plan.")
    elif abs(L.regle_controle_px - regle_px) > TOL_BARRE_PX:
        R.erreur("E3", "regle-controle", f"{nombre_fr(regle_px)} px (100 mm)", f"{nombre_fr(L.regle_controle_px)} px",
                 "La règle de contrôle ne doit jamais être retouchée : regénérer.")
    ctx.rapport.mesures["barre_px"] = L.barre_echelle_px
    ctx.rapport.mesures["regle_px"] = L.regle_controle_px


def controle_e4(ctx: Contexte) -> None:
    R, ech = ctx.rapport, ctx.ech
    zu, ca = ech.zone_utile_px, ech.cartouche_px
    for e in ctx.elements.values():
        boites = [b for b in (e.get("boite_px"), boite_e8(e)) if b]
        if not boites:
            continue
        zone, nom = (ca, "cartouche") if e.get("calque") == "cartouche" else (zu, "zone utile")
        t = TOL_ZONE_PX if nom == "zone utile" else 1.0
        for b in boites:
            if b[0] < zone[0] - t or b[1] < zone[1] - t or b[2] > zone[2] + t or b[3] > zone[3] + t:
                R.erreur("E4", e["id"], f"dans la {nom} ({nombre_fr(zone[0], 0)}–{nombre_fr(zone[2], 0)} × "
                         f"{nombre_fr(zone[1], 0)}–{nombre_fr(zone[3], 0)} px)",
                         f"boîte {nombre_fr(b[0], 0)}–{nombre_fr(b[2], 0)} × {nombre_fr(b[1], 0)}–{nombre_fr(b[3], 0)} px",
                         "Rapprocher l'élément ou son étiquette (position_etiquette), ou laisser generer.py choisir "
                         "une échelle plus petite.")
                break


def controle_e5(ctx: Contexte) -> None:
    R = ctx.rapport
    equip = {e["id"]: e for e in ctx.par_type("equipement")}
    chambres = {e["id"]: e for e in ctx.par_type("chambre")}
    lignes = ctx.par_type("ligne")
    ids_lignes = {l["id"] for l in lignes}

    def genre(i):
        if i in equip:
            return equip[i].get("genre")
        return "chambre" if i in chambres else None

    def lignes_de(eid, types):
        return [l for l in lignes if l.get("genre") in types and eid in (l.get("de"), l.get("a"))]

    def autre_bout(l, eid):
        return l.get("a") if l.get("de") == eid else l.get("de")

    voisins = defaultdict(set)
    for l in lignes:
        if l.get("genre") in ("cable", "chemin_cables") or l.get("calque") == "electricite":
            for b in (l.get("de"), l.get("a")):
                if b:
                    voisins[l["id"]].add(b)
                    voisins[b].add(l["id"])

    def relie_tableau(depart) -> bool:
        vus, pile = {depart}, [depart]
        while pile:
            n = pile.pop()
            for v in voisins.get(n, ()):
                if v in vus:
                    continue
                vus.add(v)
                if genre(v) == "tableau":
                    return True
                if v in ids_lignes:          # on traverse câbles et chemins de câbles, pas les autres équipements
                    pile.append(v)
        return False

    def manque(element, ids, cle, attendu, conseil):
        for i in ids:
            ex = ctx.plan.exigences.get(i)
            if isinstance(ex, dict) and cle in ex:
                R.avertir("E5", element, attendu, f"absent : exception « {ex.get(cle)} » ({i})",
                          f"Motif écrit dans plan.json : {ex.get('motif') or 'MOTIF MANQUANT'}.")
                return
        R.erreur("E5", element, attendu, "absent", conseil)

    for cid, c in chambres.items():
        poly = c.get("points_m") or []
        porte = ctx.elements.get(f"{cid}-porte")
        if not porte or porte.get("type") != "porte":
            manque(cid, [cid], "porte", "porte de chambre froide",
                   "Ajouter « porte » (charnière, largeur, orientation) à la chambre dans plan.json.")
        evs = [e for e in equip.values() if e.get("genre") == "evaporateur" and e.get("centre_m")
               and geo.point_dans_polygone(e["centre_m"], poly)]
        if not evs:
            manque(cid, [cid], "evaporateur", "au moins un évaporateur dans la chambre",
                   "Placer l'évaporateur (position, dimensions) dans le polygone de la chambre.")
        for ev in evs:
            ids = [ev["id"], cid]
            for t, nom in (("aspiration", "aspiration"), ("liquide", "liquide")):
                if not any(genre(autre_bout(l, ev["id"])) in GENRES_PRODUCTION for l in lignes_de(ev["id"], (t,))):
                    manque(ev["id"], ids, t, f"ligne {nom} de {ev['id']} vers un groupe ou une centrale",
                           f"Tracer la ligne {nom} (de = {ev['id']}, a = le groupe ou la centrale).")
            if not lignes_de(ev["id"], ("condensats",)):
                manque(ev["id"], ids, "condensats", f"ligne de condensats depuis {ev['id']}",
                       "Tracer l'évacuation des condensats (cordon chauffant si chambre négative).")
            if not (relie_tableau(ev["id"]) or relie_tableau(cid)):
                manque(ev["id"], ids, "cable", f"câble de {ev['id']} (ou de {cid}) jusqu'à un tableau",
                       "Tracer le câble (directement ou par un chemin de câbles relié au tableau).")
    for sp in [e for e in equip.values() if e.get("genre") == "split"]:
        moteurs = set()
        for t in ("clim_gaz", "clim_liquide"):
            ls = [l for l in lignes_de(sp["id"], (t,)) if genre(autre_bout(l, sp["id"])) == "moteur"]
            if not ls:
                manque(sp["id"], [sp["id"]], t, f"ligne {t} de {sp['id']} vers un moteur",
                       f"Tracer la ligne {t} (de = {sp['id']}, a = le moteur).")
            moteurs |= {autre_bout(l, sp["id"]) for l in ls}
        if not (relie_tableau(sp["id"]) or any(relie_tableau(m) for m in moteurs)):
            manque(sp["id"], [sp["id"]], "cable", f"câble de {sp['id']} ou de son moteur jusqu'à un tableau",
                   "Tracer l'alimentation du moteur (ou du split) jusqu'au tableau.")


def _comparer_reseaux(ctx: Contexte, rangs: list[list[str]] | None, source: str) -> None:
    R, m = ctx.rapport, ctx.metre
    if not m.lignes:
        return
    if not rangs or len(rangs) < 2:
        R.erreur("E6", source, "tableau « Métré par réseau »", "absent", "Regénérer le plan.")
        return
    entete = rangs[0]
    try:
        i_l = entete.index("Ligne")
        cols = [(entete.index(n), cle, n) for n, cle in (("En plan (m)", "plan_m"), ("Dans le chemin (m)", "chemin_m"),
                                                         ("Vertical (m)", "vertical_m"), ("Réserve (m)", "reserve_m"),
                                                         ("Total (m)", "total_m"))]
    except ValueError:
        R.erreur("E6", source, "colonnes Ligne, En plan, Dans le chemin, Vertical, Réserve, Total", " | ".join(entete),
                 "Regénérer le plan.")
        return
    lignes_tab, totaux_tab = {}, {}
    for r in rangs[1:]:
        if len(r) <= max(i_l, *(c[0] for c in cols)):
            continue
        nom0 = r[0].replace("**", "").strip()
        if r[i_l].strip():
            lignes_tab[r[i_l].strip()] = r
        elif nom0.startswith("Total "):
            totaux_tab[nom0[len("Total "):]] = r
    for lid, l in m.lignes.items():
        r = lignes_tab.get(lid)
        if r is None:
            R.erreur("E6", f"{source} · {lid}", f"ligne {lid} dans le tableau", "absente", "Regénérer le plan.")
            continue
        for i, cle, nom in cols:
            v = lire_nombre(r[i])
            if v is None or abs(v - l[cle]) > TOL_M + 1e-6:
                R.erreur("E6", f"{source} · {lid}", f"{nom} = {mtr.nombre_fr(l[cle])} (recalcul depuis le dessin)",
                         r[i], "Le tableau ne correspond plus au dessin : regénérer (generer.py).")
    for lid in lignes_tab:
        if lid not in m.lignes:
            R.erreur("E6", f"{source} · {lid}", "ligne présente dans le dessin", "ligne du tableau absente du dessin",
                     "Regénérer le plan.")
    i_total = next(c[0] for c in cols if c[1] == "total_m")
    for res in m.par_reseau.values():
        r = totaux_tab.get(res["nom"])
        if r is None:
            R.erreur("E6", f"{source} · Total {res['nom']}", "rang de total", "absent", "Regénérer le plan.")
            continue
        tol = TOL_M * max(1, len(res["lignes"])) + 1e-6       # un arrondi au cm peut basculer par ligne (A2)
        for i, cle, nom in cols:
            v = lire_nombre(r[i])
            if v is None or abs(v - res[cle]) > tol:
                R.erreur("E6", f"{source} · Total {res['nom']}", f"{nom} = {mtr.nombre_fr(res[cle])} (recalcul)",
                         r[i], "Regénérer le plan.")
        valeurs = [lire_nombre(lignes_tab[i][i_total]) for i in res["lignes"] if i in lignes_tab]
        total_tab = lire_nombre(r[i_total])
        if None not in valeurs and total_tab is not None and abs(sum(valeurs) - total_tab) > 0.005 + 1e-6:
            R.erreur("E6", f"{source} · Total {res['nom']}", f"somme des lignes du tableau = {mtr.nombre_fr(sum(valeurs))}",
                     r[i_total], "Total incohérent avec ses lignes : regénérer le plan.")


def _comparer_diametres(ctx: Contexte, rangs: list[list[str]] | None, source: str) -> None:
    R, m = ctx.rapport, ctx.metre
    if not m.lignes:
        return
    if not rangs or len(rangs) < 2:
        R.erreur("E6", source, "tableau « Métré par diamètre »", "absent", "Regénérer le plan.")
        return
    entete = rangs[0]
    try:
        i_d, i_t, i_v = entete.index("Diamètre"), entete.index("Type"), entete.index("Total (m)")
    except ValueError:
        R.erreur("E6", source, "colonnes Diamètre, Type, Total", " | ".join(entete), "Regénérer le plan.")
        return
    tab = {(r[i_t], r[i_d]): r[i_v] for r in rangs[1:] if len(r) > max(i_d, i_t, i_v)}
    for d in m.par_diametre.values():
        cle = (d["libelle_type"], d["diametre"])
        v = lire_nombre(tab.pop(cle)) if cle in tab else None
        if v is None or abs(v - d["total_m"]) > TOL_M * max(1, len(d["lignes"])) + 1e-6:
            R.erreur("E6", f"{source} · {d['libelle_type']} {d['diametre']}",
                     f"{mtr.nombre_fr(d['total_m'])} m (recalcul)", "absent" if v is None else mtr.nombre_fr(v),
                     "Regénérer le plan.")
    for (t, dia) in tab:
        R.erreur("E6", f"{source} · {t} {dia}", "groupe présent dans le recalcul", "groupe en trop dans le tableau",
                 "Regénérer le plan.")


def controle_e6(ctx: Contexte) -> None:
    try:
        ctx.metre
    except mtr.ErreurMetre as exc:
        ctx.rapport.erreur("E6", "métré", "métré recalculable depuis le dessin", str(exc),
                           "Corriger la ligne relue (type, points) puis regénérer.")
        return
    tableaux = dict(ctx.lecture.tableaux)
    _comparer_reseaux(ctx, rangs_html(tableaux.get("Métré par réseau", "")), "page Métré · Métré par réseau")
    _comparer_diametres(ctx, rangs_html(tableaux.get("Métré par diamètre", "")), "page Métré · Métré par diamètre")
    _comparer_reseaux(ctx, rangs_markdown(ctx.md, "Métré par réseau"), "plan.md · Métré par réseau")
    _comparer_diametres(ctx, rangs_markdown(ctx.md, "Métré par diamètre"), "plan.md · Métré par diamètre")


def _points_tableau_croisements(rangs: list[list[str]]) -> dict[str, tuple[float, float] | None]:
    entete = [c.strip() for c in rangs[0]] if rangs else []
    i_p = entete.index("Point (x ; y)") if "Point (x ; y)" in entete else 1
    res = {}
    for r in rangs[1:]:
        if not r or not re.fullmatch(r"X\d+", r[0].strip()):
            continue
        nombres = re.findall(r"-?\d+(?:[.,]\d+)?", r[i_p].replace("\u2212", "-")) if len(r) > i_p else []
        res[r[0].strip()] = ((float(nombres[0].replace(",", ".")), float(nombres[1].replace(",", ".")))
                             if len(nombres) >= 2 else None)
    return res


def _reperes_tableau_croisements(rangs: list[list[str]]) -> dict[str, str] | None:
    """{X1: "G1", …} lu dans la colonne « Repère » ; None si le tableau n'a pas cette colonne."""
    entete = [c.strip() for c in rangs[0]] if rangs else []
    if "Repère" not in entete:
        return None
    i_r = entete.index("Repère")
    return {r[0].strip(): (r[i_r].strip() if len(r) > i_r else "") for r in rangs[1:]
            if r and re.fullmatch(r"X\d+", r[0].strip())}


def controle_e7(ctx: Contexte) -> None:
    R = ctx.rapport
    try:
        attendus = ctx.croisements
    except crx.ErreurCroisements as exc:
        R.erreur("E7", "croisements", "croisements recalculables", str(exc), "Corriger la ligne relue.")
        return
    groupes = crx.regrouper(attendus)                  # un cercle par groupe (≤ 0,50 m de proche en proche)
    ellipses = {e["id"]: e for e in ctx.par_type("croisement")}
    libres = dict(ellipses)
    for g in groupes:
        proche = min(libres.values(), key=lambda e: geo.distance(e["centre_m"], g["point"]), default=None)
        if proche is None or geo.distance(proche["centre_m"], g["point"]) > TOL_CROISEMENT_M + 1e-9:
            R.erreur("E7", f"{g['id']} ({crx.etiquette_groupe(g)})", f"cercle de croisement en {_pt(g['point'])}",
                     "absent du calque « Croisements »", "Regénérer le plan (generer.py recalcule les croisements).")
        else:
            del libres[proche["id"]]
    for e in libres.values():
        R.erreur("E7", e["id"], "croisement recalculé à cet endroit", f"cercle en trop en {_pt(e['centre_m'])}",
                 "Regénérer le plan.")
    for e in ellipses.values():
        if e.get("diametre_m") is not None and abs(e["diametre_m"] - mod.DIAMETRE_CROISEMENT) > TOL_M:
            R.avertir("E7", e["id"], f"cercle de {_m(mod.DIAMETRE_CROISEMENT)}", _m(e["diametre_m"]),
                      "Regénérer le plan.")
    # tableaux : une ligne par croisement individuel (point recalculé à 0,05 m) et son repère G
    par_id = {x["id"]: x for x in attendus}
    repere = {xid: g["id"] for g in groupes for xid in g["croisements"]}
    sources = [("page Métré", rangs_html(dict(ctx.lecture.tableaux).get(TITRE_CROISEMENTS_PAGE, ""))),
               ("plan.md", rangs_markdown(ctx.md, "Croisements et recouvrements") or [])]
    for source, rangs in sources:
        if source == "page Métré" and not rangs:
            R.erreur("E7", source, f"tableau « {TITRE_CROISEMENTS_PAGE} »", "absent", "Regénérer le plan.")
            continue
        if source == "plan.md" and not rangs and "Aucun croisement" not in texte_section(ctx.md, "Croisements et recouvrements"):
            R.erreur("E7", source, "tableau des croisements", "absent", "Regénérer le plan.")
            continue
        tab = _points_tableau_croisements(rangs) if rangs else {}
        if len(tab) != len(attendus):
            R.erreur("E7", f"{source} · croisements", f"{len(attendus)} croisement(s) (recalcul)",
                     f"{len(tab)} dans le tableau", "Regénérer le plan.")
        for xid, p in tab.items():
            x = par_id.get(xid)
            if x is None or p is None or geo.distance(p, x["point"]) > TOL_CROISEMENT_M + 1e-9:
                R.erreur("E7", f"{source} · {xid}", f"point du croisement {xid} "
                         f"{_pt(x['point']) if x else '(absent du recalcul)'}", _pt(p), "Regénérer le plan.")
        reperes = _reperes_tableau_croisements(rangs) if tab else {}
        if reperes is None:
            R.erreur("E7", f"{source} · croisements", "colonne « Repère » (groupe G de chaque croisement)", "absente",
                     "Regénérer le plan.")
        for xid, g in (reperes or {}).items():
            if xid in par_id and repere.get(xid) != g:
                R.erreur("E7", f"{source} · {xid}", f"repère {repere.get(xid)} (recalcul)", g or "vide",
                         "Regénérer le plan.")


def controle_e8(ctx: Contexte) -> None:
    R = ctx.rapport
    textes = [(e, boite_e8(e)) for e in ctx.elements.values()
              if e.get("calque") != "cartouche" and e.get("type") in ("texte", "piece", "cote")]
    textes = [(e, b) for e, b in textes if b]
    obstacles = [e for e in ctx.elements.values() if e.get("type") in ("porte", "equipement") and e.get("boite_px")]
    traits = [e for e in ctx.elements.values() if e.get("type") in TYPES_TRAITS_E8 and e.get("calque") != "cartouche"
              and len(e.get("points_px") or []) >= 2]

    def lies(a, b) -> bool:
        return a.get("parent_element") == b["id"] or b.get("parent_element") == a["id"] or (
            a.get("parent_element") and a.get("parent_element") == b.get("parent_element"))

    for i, (a, ba) in enumerate(textes):
        for b, bb in textes[i + 1:]:
            if not lies(a, b) and geo.boites_se_chevauchent(ba, bb, marge=0.5):
                R.erreur("E8", f"{a['id']} / {b['id']}", "textes séparés",
                         f"« {a['texte'].splitlines()[0]} » chevauche « {b['texte'].splitlines()[0]} »",
                         "Déplacer une des étiquettes (position_etiquette dans plan.json) ou raccourcir le texte.")
        for o in obstacles:
            if not lies(a, o) and geo.boites_se_chevauchent(ba, o["boite_px"], marge=0.5):
                R.erreur("E8", f"{a['id']} / {o['id']}", f"texte hors de {o['type']} {o['id']}",
                         f"« {a['texte'].splitlines()[0]} » sur {o['id']}",
                         "Déplacer l'étiquette (position_etiquette) ou décaler la cote (decalage).")
        for t in traits:                                  # étiquette posée sur le trait d'un autre élément
            if t["id"] == a["id"] or lies(a, t):
                continue
            if any(drawio.segment_coupe_boite(p, q, ba) for p, q in geo.segments(t["points_px"])):
                R.avertir("E8", f"{a['id']} / {t['id']}", f"texte hors du trait de {t['id']}",
                          f"« {a['texte'].splitlines()[0]} » posé sur {t['id']}",
                          "Déplacer l'étiquette (position_etiquette dans plan.json) ou décaler la cote (decalage).")


def controle_e9(ctx: Contexte) -> None:
    R, L, ech = ctx.rapport, ctx.lecture, ctx.ech
    for message in ctx.plan.valider():
        R.erreur("E9", "plan.json", "modèle cohérent", message, "Corriger plan.json puis regénérer.")
    presents = {cle for cle, _ in L.calques}
    for cle, nom in ctx.plan.calques():
        if cle not in presents:
            R.erreur("E9", cle, f"calque « {nom} »", "absent du dessin",
                     "Regénérer le plan (ne pas supprimer de calque dans draw.io : le masquer).")
    portes = [(e, emprise_porte_relue(e)) for e in ctx.par_type("porte") if e.get("position_m")]
    fenetres = [(e, polygone_m(e, ech)) for e in ctx.par_type("fenetre")]
    fenetres = [(e, p) for e, p in fenetres if p]
    for q in ctx.par_type("equipement"):
        pq = polygone_m(q, ech)
        if not pq:
            continue
        for e, emprise in portes + fenetres:
            if recouvrement(pq, emprise) > TOL_EMPRISE_M:
                quoi = "le battant de la porte" if e["type"] == "porte" else "la fenêtre"
                R.erreur("E9", f"{q['id']} / {e['id']}", f"{q['id']} hors de l'emprise de {e['id']}",
                         f"{q['id']} empiète sur {quoi}", "Déplacer l'équipement (position dans plan.json).")
    for l in ctx.par_type("ligne"):
        pts = l.get("points_m") or []
        if len(pts) < 2:
            continue
        for bout, p in (("départ", pts[0]), ("arrivée", pts[-1])):
            for e, emprise in portes + fenetres:
                if profondeur_dans(p, emprise) > TOL_EMPRISE_M:
                    R.erreur("E9", l["id"], f"{bout} hors de l'emprise de {e['id']}", f"{bout} en {_pt(p)} sur {e['id']}",
                             "Déplacer l'extrémité de la ligne (points dans plan.json).")
    # extrémités ↔ équipements
    for l in ctx.par_type("ligne"):
        pts = l.get("points_m") or []
        if len(pts) < 2:
            continue
        for cle, bout, p in (("de", "départ", pts[0]), ("a", "arrivée", pts[-1])):
            ref = l.get(cle)
            if not ref:
                continue
            cible = ctx.elements.get(ref)
            if cible is None:
                R.erreur("E9", l["id"], f"{bout} sur « {ref} »", f"« {ref} » absent du dessin",
                         "Corriger « de » / « a » de la ligne dans plan.json.")
                continue
            if cible.get("type") == "ligne" and cible.get("points_m"):
                d = geo.distance_point_polyligne(p, cible["points_m"])
            else:
                poly = polygone_m(cible, ech)
                if not poly:
                    continue
                d = geo.distance_point_polygone(p, poly)
            if d > TOL_EXTREMITE_M + 1e-9:
                R.erreur("E9", l["id"], f"{bout} à {_m(TOL_EXTREMITE_M)} au plus de {ref}",
                         f"{bout} {_pt(p)} à {_m(d)} de {ref}", "Ramener l'extrémité sur l'équipement (points).")
    # évaporateur face à la porte
    for c in ctx.par_type("chambre"):
        porte = ctx.elements.get(f"{c['id']}-porte")
        if not porte or porte.get("type") != "porte":
            continue
        o, _ = mod.vecteurs_porte(porte["orientation"], porte.get("sens", "gauche"))
        cp = (porte["position_m"][0] + o[0] * porte["largeur_m"] / 2, porte["position_m"][1] + o[1] * porte["largeur_m"] / 2)
        for ev in ctx.par_type("equipement"):
            if ev.get("genre") != "evaporateur" or not geo.point_dans_polygone(ev["centre_m"], c.get("points_m") or []):
                continue
            fl = ctx.elements.get(f"{ev['id']}-fl")
            if fl and fl.get("points_m") and len(fl["points_m"]) >= 2:
                a, b = fl["points_m"][0], fl["points_m"][-1]
                d = (b[0] - a[0], b[1] - a[1])
            else:
                try:
                    d = mod.SOUFFLAGES[ctx.plan.soufflage(ctx.plan.equipement(ev["id"]))]
                except KeyError:
                    continue
            v = (cp[0] - ev["centre_m"][0], cp[1] - ev["centre_m"][1])
            nd, nv = math.hypot(*d), math.hypot(*v)
            if nd < 1e-9 or nv < 1e-9:
                continue
            angle = math.degrees(math.acos(max(-1.0, min(1.0, (d[0] * v[0] + d[1] * v[1]) / (nd * nv)))))
            if angle > ANGLE_FACE_PORTE:
                R.avertir("E9", ev["id"], f"soufflage vers la porte de {c['id']} (écart ≤ {ANGLE_FACE_PORTE:.0f}°)",
                          f"écart de {angle:.0f}°", "Placer l'évaporateur face à la porte, soufflage vers elle "
                          "(sinon le noter dans plan.json).")


def controle_e10(ctx: Contexte) -> None:
    R, L, ech = ctx.rapport, ctx.lecture, ctx.ech
    if ctx.sans_pdf:
        R.ignores["E10"] = "--sans-pdf"
        return
    pdf = ctx.dossier / "plan.pdf"
    if not pdf.is_file():
        R.avertir("E10", "plan.pdf", "PDF mesuré", "absent", "Lancer generer.py (sans --sans-rendu) ou rendu.py.")
        return
    if pdf.stat().st_mtime + 1 < (ctx.dossier / "plan.drawio").stat().st_mtime:
        R.avertir("E10", "plan.pdf", "PDF rendu après plan.drawio", "PDF plus ancien que plan.drawio",
                  "Relancer le rendu (generer.py ou rendu.py).")
    try:
        import pymupdf
        doc = pymupdf.open(pdf)
    except Exception as exc:  # noqa: BLE001
        R.erreur("E10", "plan.pdf", "PDF lisible", str(exc), "Relancer le rendu.")
        return
    with doc:
        page = doc[0]
        w, h = page.rect.width, page.rect.height
        a4 = A4_PT if L.page.get("orientation") == "portrait" else (A4_PT[1], A4_PT[0])
        ctx.rapport.mesures["page_pt"] = [round(w, 2), round(h, 2)]
        if abs(w - a4[0]) > TOL_PAGE_PT or abs(h - a4[1]) > TOL_PAGE_PT:
            R.erreur("E10", "plan.pdf · page", f"A4 {L.page.get('orientation')} : {nombre_fr(a4[0])} × {nombre_fr(a4[1])} pt",
                     f"{nombre_fr(w)} × {nombre_fr(h)} pt", "Relancer le rendu (jamais d'export « ajusté »).")
        rects = rendu.rectangles_pleins(page)
        cell = L.brut.get("regle-controle")
        g = cell.get("geometrie") if cell else None
        boite_regle = (g["x"], g["y"], g["width"], g["height"]) if g else None
        regle = rendu.mesurer_regle(page, boite_regle, rects)
        if regle is None or boite_regle is None:
            R.erreur("E10", "regle-controle", f"règle de 100 mm = {_ptx(rendu.REGLE_PT)}", "introuvable dans le PDF",
                     "Relancer le rendu ; si le problème reste, regénérer le plan.")
            return
        ctx.rapport.mesures["regle_pt"] = round(regle["l"], 3)
        if abs(regle["l"] - rendu.REGLE_PT) > TOL_REGLE_PT:
            R.erreur("E10", "regle-controle", f"{_ptx(rendu.REGLE_PT)} ± {nombre_fr(TOL_REGLE_PT, 1)} pt",
                     _ptx(regle["l"]), "Le PDF n'est pas à l'échelle : relancer rendu.py (il recalibre le facteur s).")
        transfo = rendu.transformation(regle, boite_regle)
        barre = L.brut.get("barre-echelle")
        gb = barre.get("geometrie") if barre else None
        attendu_barre = ech.barre_echelle_mm * PT_PAR_MM
        if gb:
            r = rendu.chercher_rectangle(rects, (gb["x"], gb["y"], gb["width"], gb["height"]), transfo,
                                         rendu.couleur_rgb(barre["style"].get("fillColor", "")))
            ctx.rapport.mesures["barre_pt"] = round(r["l"], 3) if r else None
            if r is None:
                R.erreur("E10", "barre-echelle", _ptx(attendu_barre), "introuvable dans le PDF", "Relancer le rendu.")
            elif abs(r["l"] - attendu_barre) > TOL_BARRE_PT:
                R.erreur("E10", "barre-echelle", f"{_ptx(attendu_barre)} ± {nombre_fr(TOL_BARRE_PT, 1)} pt",
                         _ptx(r["l"]), "Le PDF n'est pas à l'échelle : relancer rendu.py.")
        murs = sorted((e for e in ctx.par_type("mur") if abs(e.get("rotation") or 0.0) < 1e-6 and e.get("longueur_m")),
                      key=lambda e: -e["longueur_m"])[:3]
        ctx.rapport.mesures["murs_pt"] = {}
        for e in murs:
            c = L.brut[e["id"]]
            gm = c["geometrie"]
            attendu = e["longueur_m"] * 1000.0 / ech.S * PT_PAR_MM
            r = rendu.chercher_rectangle(rects, (gm["x"], gm["y"], gm["width"], gm["height"]), transfo,
                                         rendu.couleur_rgb(c["style"].get("fillColor", "")))
            if r is None:
                R.erreur("E10", e["id"], _ptx(attendu), "mur introuvable dans le PDF", "Relancer le rendu.")
                continue
            mesure = max(r["l"], r["h"])
            ctx.rapport.mesures["murs_pt"][e["id"]] = round(mesure, 3)
            if abs(mesure - attendu) > TOL_MUR_PT:
                R.erreur("E10", e["id"], f"{_ptx(attendu)} ± {nombre_fr(TOL_MUR_PT, 0)} pt ({_m(e['longueur_m'])} "
                         f"au 1:{ech.S})", _ptx(mesure), "Le PDF n'est pas à l'échelle : relancer rendu.py.")
        if doc.page_count != rendu.pages_attendues(L) and doc.page_count != 1:
            R.avertir("E10", "plan.pdf", f"{rendu.pages_attendues(L)} page(s)", f"{doc.page_count} page(s)",
                      "Un élément dépasse peut-être de la page : regénérer.")


def controle_e11(ctx: Contexte) -> None:
    R, L = ctx.rapport, ctx.lecture
    if ctx.sans_pdf:
        R.ignores["E11"] = "--sans-pdf"
        return
    png = ctx.dossier / "plan.png"
    attendu = (L.page["largeur_px"] * FACTEUR_PNG, L.page["hauteur_px"] * FACTEUR_PNG)
    if not png.is_file():
        R.erreur("E11", "plan.png", f"image de {nombre_fr(attendu[0], 0)} × {nombre_fr(attendu[1], 0)} px", "absente",
                 "Relancer le rendu (generer.py ou rendu.py).")
        return
    try:
        from PIL import Image
        with Image.open(png) as im:
            w, h = im.size
    except Exception as exc:  # noqa: BLE001
        R.erreur("E11", "plan.png", "image lisible", str(exc), "Relancer le rendu.")
        return
    ctx.rapport.mesures["png_px"] = [w, h]
    if abs(w - attendu[0]) > TOL_PNG_PX or abs(h - attendu[1]) > TOL_PNG_PX:
        R.erreur("E11", "plan.png", f"{nombre_fr(attendu[0], 0)} × {nombre_fr(attendu[1], 0)} px (± {TOL_PNG_PX})",
                 f"{w} × {h} px", "Relancer le rendu (le PNG vient du PDF, 200 dpi).")
    if png.stat().st_mtime + 1 < (ctx.dossier / "plan.drawio").stat().st_mtime:
        R.avertir("E11", "plan.png", "PNG rendu après plan.drawio", "PNG plus ancien que plan.drawio",
                  "Relancer le rendu.")


# ======================================================================
# Orchestration et sorties
# ======================================================================
def ecrire_rapport(dossier: Path, R: Rapport, titre: str, maintenant: datetime, code: int) -> tuple[Path, Path]:
    ne, na = R.nombre(ERREUR), R.nombre(AVERTISSEMENT)
    s = lambda n, mot: f"{n} {mot}{'s' if n > 1 else ''}"  # noqa: E731
    lignes = ["<!-- titre: Vérification du plan -->", "", f"# Vérification du plan : {titre}", "",
              f"**Résultat : {s(ne, 'erreur')}, {s(na, 'avertissement')}** (vérifié le {maintenant:%Y-%m-%d à %H:%M}, "
              "tout relu depuis `plan.drawio`, PDF mesuré avec PyMuPDF).", "", "## Résumé", "",
              "| Code | Contrôle | Erreurs | Avertissements | Statut |", "|---|---|---:|---:|---|"]
    for code_, nom in CONTROLES.items():
        if code_ in R.ignores:
            statut = f"non fait ({R.ignores[code_]})"
        else:
            statut = "à corriger" if R.nombre(ERREUR, code_) else ("OK, à relire" if R.nombre(AVERTISSEMENT, code_) else "OK")
        lignes.append(f"| {code_} | {nom} | {R.nombre(ERREUR, code_)} | {R.nombre(AVERTISSEMENT, code_)} | {statut} |")
    lignes += ["", "## Constats", ""]
    if R.constats:
        lignes += ["| Code | Gravité | Élément | Attendu | Trouvé | Conseil |", "|---|---|---|---|---|---|"]
        ordre = list(CONTROLES)
        for c in sorted(R.constats, key=lambda c: (c["gravite"] != ERREUR, ordre.index(c["code"]))):
            cellules = [c["code"], ("⚠ " if c["gravite"] == ERREUR else "") + c["gravite"], c["element"],
                        c["attendu"], c["trouve"], c["conseil"]]
            lignes.append("| " + " | ".join(str(x).replace("|", "\\|").replace("\n", " ") for x in cellules) + " |")
    else:
        lignes.append("Aucun constat : le plan est conforme aux 11 contrôles.")
    m = R.mesures
    lignes += ["", "## Mesures", ""]
    if m.get("regle_pt") is not None:
        lignes.append(f"- Règle de contrôle dans le PDF : {_ptx(m['regle_pt'])} (attendu {_ptx(rendu.REGLE_PT)}).")
    if m.get("barre_pt") is not None:
        lignes.append(f"- Barre d'échelle dans le PDF : {_ptx(m['barre_pt'])}.")
    for mid, v in (m.get("murs_pt") or {}).items():
        lignes.append(f"- Mur {mid} dans le PDF : {_ptx(v)}.")
    if m.get("png_px"):
        lignes.append(f"- plan.png : {m['png_px'][0]} × {m['png_px'][1]} px.")
    if m.get("barre_px") is not None:
        lignes.append(f"- Barre d'échelle dans le fichier : {nombre_fr(m['barre_px'])} px ; règle : "
                      f"{nombre_fr(m['regle_px'] or 0)} px.")
    lignes.append("")
    md = dossier / "verification.md"
    md.write_text("\n".join(lignes), encoding="utf-8", newline="\n")
    js = dossier / "verification.json"
    js.write_text(json.dumps({
        "date": maintenant.isoformat(timespec="seconds"), "code": code, "erreurs": ne, "avertissements": na,
        "controles": {k: {"erreurs": R.nombre(ERREUR, k), "avertissements": R.nombre(AVERTISSEMENT, k),
                          "ignore": R.ignores.get(k)} for k in CONTROLES},
        "constats": R.constats, "mesures": m}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return md, js


def verifier(dossier_plan, sans_pdf: bool = False, ecrire: bool = True) -> dict:
    """Lance les 11 contrôles. Renvoie {code, erreurs, avertissements, constats, mesures, rapport, fichiers}."""
    dossier = Path(dossier_plan)
    maintenant = datetime.now()
    try:
        ctx = Contexte(dossier, sans_pdf)
    except FichierManquant as exc:
        R = Rapport()
        R.erreur("E1", "dossier", "plan.json, plan.drawio et plan.md", f"manquant : {exc}",
                 "Lancer generer.py sur le dossier.")
        fichiers = ecrire_rapport(dossier, R, dossier.name, maintenant, 2) if ecrire and dossier.is_dir() else ()
        return {"code": 2, "erreurs": 1, "avertissements": 0, "constats": R.constats, "mesures": {}, "rapport": R,
                "fichiers": fichiers}
    except drawio.ErreurLecture as exc:
        R = Rapport()
        R.erreur("E1", "plan.drawio", "fichier draw.io lisible", str(exc), "Regénérer le plan.")
        fichiers = ecrire_rapport(dossier, R, dossier.name, maintenant, 1) if ecrire else ()
        return {"code": 1, "erreurs": 1, "avertissements": 0, "constats": R.constats, "mesures": {}, "rapport": R,
                "fichiers": fichiers}
    R = ctx.rapport
    if ctx.ech is None:
        R.erreur("E1", "cartouche-echelle", "échelle « 1:S » et origine du modèle dans le cartouche",
                 " ; ".join(ctx.lecture.avertissements) or "illisibles", "Regénérer le plan avec generer.py.")
        for code_ in list(CONTROLES)[1:]:
            R.ignores[code_] = "échelle illisible"
    else:
        for f in (controle_e1, controle_e2, controle_e3, controle_e4, controle_e5, controle_e6, controle_e7,
                  controle_e8, controle_e9, controle_e10, controle_e11):
            f(ctx)
    code = 1 if R.nombre(ERREUR) else 0
    fichiers = ecrire_rapport(dossier, R, ctx.plan.titre or dossier.name, maintenant, code) if ecrire else ()
    return {"code": code, "erreurs": R.nombre(ERREUR), "avertissements": R.nombre(AVERTISSEMENT),
            "constats": R.constats, "mesures": R.mesures, "rapport": R, "fichiers": fichiers}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Vérifie un plan 2D (11 contrôles, tout relu depuis plan.drawio).")
    ap.add_argument("dossier_plan")
    ap.add_argument("--sans-pdf", action="store_true", help="ne pas contrôler plan.pdf ni plan.png (E10, E11)")
    a = ap.parse_args(argv)
    r = verifier(a.dossier_plan, sans_pdf=a.sans_pdf)
    for c in r["constats"]:
        print(f"[{c['code']}] {c['gravite']} · {c['element']} : attendu {c['attendu']} ; trouvé {c['trouve']}")
    print(f"{r['erreurs']} erreur(s), {r['avertissements']} avertissement(s).")
    if r["fichiers"]:
        print(f"Rapport : {r['fichiers'][0]}")
    return r["code"]


if __name__ == "__main__":
    sys.exit(main())
