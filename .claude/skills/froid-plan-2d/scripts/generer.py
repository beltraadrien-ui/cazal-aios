"""Génère le plan 2D d'un dossier : `plan.json` → `plan.drawio`, `plan.md` + `plan.html`, `metre-detail.md`,
`metre.json`, `plan.pdf` + `plan.png`, `plan-base.json`, copie `versions/plan-vN.*`, ligne datée dans `journal.md`.

Chaîne : charger → valider (erreurs → code 1, rien n'est écrit) → métré (A2) → croisements + recouvrements (A2),
regroupés (≤ 0,50 m, repères G) et injectés dans le modèle (un cercle par groupe) → échelle normalisée (A1, boîte englobante croisements compris) → `drawio.ecrire` (page
« Plan » + page « Métré » : tableaux de métré et des croisements) → rendu PDF/PNG mesuré (`rendu.py`) → `plan.md`,
lisible d'abord (Loïc le lit en `plan.html`) : le plan en image, ce qu'il contient (chambres, équipements et leur
emplacement en mots), le métré par réseau en noms (aucun code de ligne) et son récapitulatif, les croisements en
mots, les cotes et ce qu'elles mesurent, les hauteurs de pose, les questions ouvertes, des détails techniques courts
→ `metre-detail.md` (mémoire, non rendue : métré par ligne avec codes et formules, par diamètre, hauteurs,
croisements un par un, calques, notes du relevé ; relu par verifier_plan.py E6 et E7)
→ `metre.json` (contrat du 2026-10-08, lu par la demande fournisseur : longueurs par ligne, par réseau, par type,
origine estimée / mesurée) → `plan.html` (`shared/rendu_html.py`, image du plan en pleine largeur) → `plan-base.json`
(contrat du Lot 6 : un point (x, y) du modèle en m tombe sur la page en `origine_mm + (x, y) × 1000 / S` mm)
→ versions → journal.

Longueurs (décision du 2026-10-08) : toutes sont des estimations d'après le plan (tracé et hauteurs de pose), sauf
celles mesurées sur chantier (`longueur_mesuree` + `mesure` sur la ligne de plan.json) : dans plan.md et la page
« Métré », la phrase `metre.PHRASE_LONGUEURS` en tête du métré, « (mesurée) » sur le total des seules lignes
mesurées, plus de « (hyp.) » ; metre-detail.md garde tout (estimation, mesure, écart, « (hyp.) »).

Usage (depuis la racine du dépôt) :
    python .claude/skills/froid-plan-2d/scripts/generer.py <dossier_plan> [--sans-rendu] [--ouvrir]
Code de retour : 0 (plan généré), 1 (modèle invalide, échelle impossible ou rendu en échec).
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import croisements as crx  # noqa: E402
import drawio  # noqa: E402
import geometrie as geo  # noqa: E402
import metre as mtr  # noqa: E402
import modele as mod  # noqa: E402
import rendu  # noqa: E402
from echelle import ErreurEchelle, PT_PAR_MM, choisir_echelle, nombre_fr  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]          # racine du dépôt (…/.claude/skills/<skill>/scripts/)
HYP = " (hyp.)"
TITRE_TABLEAU_CROISEMENTS = "Croisements entre réseaux"
TITRE_CROISEMENTS_MD = "Croisements"           # section de plan.md (une ligne par repère G, en mots)
ENTETES_RESEAUX = ["Réseau", "Ligne", f"De {mtr.FLECHE} À", "Type", "En plan (m)", "Dans le chemin (m)", "Vertical (m)",
                   "Réserve (m)", "Total (m)", "Diamètre"]
ALIGN_RESEAUX = ["g", "g", "g", "g", "d", "d", "d", "d", "d", "g"]
TITRES_SECTIONS = {
    "reseaux": "Métré par réseau", "diametres": "Métré par diamètre", "croisements": "Croisements et recouvrements",
}
TITRE_MESURES = "Longueurs mesurées sur chantier"     # section de metre-detail.md


class ErreurGeneration(RuntimeError):
    """Plan non généré : message en français."""


# ======================================================================
# Outils
# ======================================================================
def _pt(p) -> str:
    return f"({nombre_fr(p[0])} ; {nombre_fr(p[1])})"


def _table_md(entetes: list[str], rangs: list[list[str]], aligne: list[str] | None = None,
              gras: set[int] | None = None) -> str:
    aligne = aligne or ["g"] * len(entetes)
    gras = gras or set()

    def rang(cellules, en_gras=False):
        cs = [str(c).replace("|", "\\|").replace("\n", " ") for c in cellules]
        if en_gras:
            cs = [f"**{c}**" if c else c for c in cs]
        return "| " + " | ".join(cs) + " |"
    lignes = [rang(entetes), "|" + "|".join("---:" if a == "d" else "---" for a in aligne) + "|"]
    lignes += [rang(r, i in gras) for i, r in enumerate(rangs)]
    return "\n".join(lignes)


def statuts_hauteurs(m: mtr.Metre) -> dict[str, str]:
    return {h["cle"]: h["statut"] for h in m.hypotheses}


def ligne_en_hypothese(l: dict, statuts: dict[str, str]) -> tuple[bool, bool]:
    """(vertical en hypothèse, réserve en hypothèse) d'une ligne métrée : une hauteur prise dans la table
    `hauteurs` non validée par le frigoriste (question 13) rend le métré vertical « hypothèse »."""
    vertical = any(o.startswith("hauteurs.") and statuts.get(o.split(".", 1)[1]) == mtr.HYPOTHESE
                   for o in (l.get("origines_hauteurs") or {}).values())
    reserve = l["type"] == "cable" and statuts.get("reserve_cable") == mtr.HYPOTHESE
    return vertical, reserve


def marque_detail(m: mtr.Metre, ids: list[str], statuts: dict[str, str]) -> str:
    """Marque d'un total dans metre-detail.md : « (mesurée) » si toutes ses lignes sont mesurées, sinon « (hyp.) »
    si une de ses lignes ESTIMÉES dépend d'une hauteur non validée."""
    if m.origine(ids) == mtr.MESUREE:
        return mtr.MARQUE_MESUREE
    estimees = [m.lignes[i] for i in ids if m.lignes[i]["origine"] != mtr.MESUREE]
    return HYP if any(any(ligne_en_hypothese(l, statuts)) for l in estimees) else ""


def tableau_reseaux_md(m: mtr.Metre) -> str:
    """« Métré par réseau » de metre-detail.md (mêmes colonnes que la page Métré du draw.io) : « (hyp.) » après
    chaque valeur qui dépend d'une hauteur non validée, « (mesurée) » après le total d'une ligne mesurée sur
    chantier (ses autres colonnes gardent l'estimation du plan)."""
    statuts = statuts_hauteurs(m)
    rangs, gras = [], set()
    for r in m.par_reseau.values():
        hv_res = hr_res = False
        for lid in r["lignes"]:
            l = m.lignes[lid]
            hv, hr = ligne_en_hypothese(l, statuts)
            hv_res, hr_res = hv_res or hv, hr_res or hr
            rangs.append([r["nom"], lid, f"{l['de'] or mtr.TIRET_VIDE} {mtr.FLECHE} {l['a'] or mtr.TIRET_VIDE}",
                          l["libelle_type"], mtr.nombre_fr(l["plan_m"]), mtr.nombre_fr(l["chemin_m"]),
                          mtr.nombre_fr(l["vertical_m"]) + (HYP if hv else ""),
                          mtr.nombre_fr(l["reserve_m"]) + (HYP if hr else ""),
                          mtr.nombre_fr(l["total_m"]) + marque_detail(m, [lid], statuts), l["diametre"]])
        gras.add(len(rangs))
        rangs.append([f"Total {r['nom']}", "", "", "", mtr.nombre_fr(r["plan_m"]), mtr.nombre_fr(r["chemin_m"]),
                      mtr.nombre_fr(r["vertical_m"]) + (HYP if hv_res else ""),
                      mtr.nombre_fr(r["reserve_m"]) + (HYP if hr_res else ""),
                      mtr.nombre_fr(r["total_m"]) + marque_detail(m, r["lignes"], statuts), ""])
    return _table_md(ENTETES_RESEAUX, rangs, ALIGN_RESEAUX, gras)


def tableau_diametres_md(m: mtr.Metre) -> str:
    statuts = statuts_hauteurs(m)
    rangs = [[d["diametre"], d["libelle_type"], mtr.nombre_fr(d["total_m"]) + marque_detail(m, d["lignes"], statuts),
              ", ".join(d["lignes"])] for d in m.par_diametre.values()]
    return _table_md(["Diamètre", "Type", "Total (m)", "Lignes"], rangs, ["g", "g", "d", "g"])


def tableau_mesures_md(m: mtr.Metre) -> str:
    """Longueurs mesurées sur chantier (metre-detail.md) : estimation du plan, mesure, écart, qui, quand, note."""
    rangs = []
    for lid, l in m.lignes.items():
        if l["origine"] != mtr.MESUREE:
            continue
        mesure = l["mesure"] or {}
        ecart = mtr.ecart_fr(l) + (" (au delà de 20 % : question posée)" if l["ecart_fort"] else "")
        rangs.append([lid, f"{l['de'] or mtr.TIRET_VIDE} {mtr.FLECHE} {l['a'] or mtr.TIRET_VIDE}",
                      mtr.nombre_fr(l["estimation_plan_m"]), mtr.nombre_fr(l["longueur_mesuree_m"]), ecart,
                      mesure.get("par") or "", mesure.get("date") or "", mesure.get("note") or ""])
    return _table_md(["Ligne", f"De {mtr.FLECHE} À", "Estimation du plan (m)", "Mesurée (m)", "Écart", "Par", "Date",
                      "Note"], rangs, ["g", "g", "d", "d", "d", "g", "g", "g"])


def prochaine_version(dossier: Path) -> int:
    n = 0
    for f in (dossier / "versions").glob("plan-v*.*"):
        mm = re.fullmatch(r"plan-v(\d+)\.(drawio|json)", f.name)
        if mm:
            n = max(n, int(mm.group(1)))
    return n + 1


def lire_journal(dossier: Path) -> list[str]:
    chemin = dossier / "journal.md"
    if not chemin.is_file():
        return []
    return [l for l in chemin.read_text(encoding="utf-8").splitlines() if l.startswith("- ")]


# ======================================================================
# Vue lisible (plan.md → plan.html, lue par Loïc) : noms en mots, emplacements, ce que mesure une cote
# ======================================================================
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre")
ARTICLE_PAR_TYPE = {"evaporateur": "l'", "centrale": "la ", "groupe": "le ", "condenseur": "le ", "split": "le ",
                    "moteur": "le ", "tableau": "le ", "chambre_froide": "la "}
MOT_PAR_TYPE = {"evaporateur": "evaporateur", "centrale": "centrale", "groupe": "groupe", "condenseur": "condenseur",
                "split": "split", "moteur": "moteur", "tableau": "tableau", "chambre_froide": "chambre"}
LIGNE_AVEC_ARTICLE = {"aspiration": "l'aspiration", "liquide": "le liquide", "condensats": "les condensats",
                      "clim_gaz": "le gaz clim", "clim_liquide": "le liquide clim",
                      "chemin_cables": "le chemin de câbles"}
COTE_DU_PLAN = {"haut": "en haut du plan", "bas": "en bas du plan", "gauche": "à gauche du plan",
                "droite": "à droite du plan"}
FACADE = {"haut": "façade du haut", "bas": "façade du bas", "gauche": "façade de gauche", "droite": "façade de droite"}
TOL_COTE = 0.03          # m : extrémité d'une cote confondue avec un bout de mur, un bord de chambre ou de pièce
VOYELLES = "aeiouyàâäéèêëîïôöùûüAEIOUYÀÂÄÉÈÊËÎÏÔÖÙÛÜ"
VERSIONS_MONTREES = 5    # « Détails techniques » : les dernières versions seulement (toutes dans journal.md)


def _sans_accent(t: str) -> str:
    return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower()


def _maj(t: str) -> str:
    return t[:1].upper() + t[1:]


def date_fr(texte: str) -> str:
    """« 2026-10-07 » → « 7 octobre 2026 » ; un autre texte est rendu tel quel."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", (texte or "").strip())
    if not m or not 1 <= int(m.group(2)) <= 12:
        return texte
    return f"{int(m.group(3))} {MOIS[int(m.group(2)) - 1]} {m.group(1)}"


def nombre_court(x: float) -> str:
    """1.0 → « 1 » ; 1.3333 → « 1,33 » ; 0.5 → « 0,5 »."""
    t = nombre_fr(x, 2)
    return t.rstrip("0").rstrip(",")


def de_(groupe: str) -> str:
    """« de » devant un groupe nominal, avec contraction (le → du, les → des)."""
    if groupe.startswith("le "):
        return "du " + groupe[3:]
    if groupe.startswith("les "):
        return "des " + groupe[4:]
    return "de " + groupe


def enumerer(items: list[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " et " + items[-1]


def source_en_mots(source) -> str:
    """Source d'une cote en mots : « télémètre », « plan d'architecte (p. 2) », « croquis », « relevé InterFast »."""
    if not source:
        return "non précisée"
    s = _sans_accent(str(source))
    page = re.search(r"\bp\.\s*(\d+)", str(source))
    suffixe = f" (p. {page.group(1)})" if page else ""
    if "telemetre" in s:
        return "télémètre"
    if "architecte" in s:
        return "plan d'architecte" + suffixe
    if "croquis" in s:
        return "croquis"
    if "interfast" in s or "rapport" in s:
        return "relevé InterFast" + suffixe
    return str(source)


class Vue:
    """Ce que plan.md dit en mots, calculé depuis le modèle : noms des équipements (le code entre parenthèses
    seulement s'il est écrit sur le plan), emplacement d'un point, ce que mesure une cote, description d'un tronçon
    ou d'un croisement. Aucun code de ligne (LA1, LE1…) n'en sort."""

    def __init__(self, plan: mod.Plan):
        self.plan = plan
        self.equipements = {q["id"]: q for q in plan.equipements}
        self.chambres = {c["id"]: c for c in plan.chambres_froides}
        self.pieces = {p["id"]: p for p in plan.pieces}
        self.lignes = {l["id"]: l for l in plan.lignes}
        self.rang_ligne = {l["id"]: i for i, l in enumerate(plan.lignes)}
        self.murs = {m["id"]: m for m in plan.murs}
        exterieurs = [m for m in plan.murs if m.get("type") == "exterieur"] or list(plan.murs)
        pts = [tuple(p) for m in exterieurs for p in (m["de"], m["a"])]
        if not pts:
            pts = [tuple(p) for e in list(plan.pieces) + list(plan.chambres_froides) for p in e["polygone"]]
        self.bati = geo.boite_englobante(pts) if pts else None

    # -- noms ------------------------------------------------------------------------------------------------
    @staticmethod
    def _contient_code(texte: str, ident: str) -> bool:
        return bool(re.search(rf"(?<![\w-]){re.escape(ident)}(?![\w-])", texte or ""))

    def code_ecrit(self, e: dict) -> bool:
        """Vrai si l'identifiant de l'élément est écrit sur le plan (son étiquette, sinon son nom, sinon l'id)."""
        dessine = e.get("etiquette") if e.get("etiquette") is not None else (e.get("nom") or e["id"])
        return self._contient_code(dessine, e["id"])

    def _avec_code(self, e: dict, base: str) -> str:
        if self.code_ecrit(e) and not self._contient_code(base, e["id"]):
            return f"{base} ({e['id']})"
        return base

    def nom(self, ident) -> str:
        """Nom dans un tableau : « Évaporateur CF1 (EV1) », « Centrale positive », « chemin de câbles »."""
        if ident is None:
            return mtr.TIRET_VIDE
        e = self.equipements.get(ident) or self.chambres.get(ident)
        if e is not None:
            return self._avec_code(e, e.get("nom") or ident)
        if ident in self.lignes:
            return self.nom_ligne(self.lignes[ident], article=False)
        if ident in self.pieces:
            return f"« {self.pieces[ident].get('nom') or ident} »"
        if ident in self.murs:
            return f"mur {ident}"
        return str(ident)

    def nom_article(self, ident) -> str:
        """Nom dans une phrase : « l'évaporateur CF1 (EV1) », « la centrale positive », « le TD-F (tableau froid) »."""
        e, type_ = self.equipements.get(ident), None
        if e is not None:
            type_ = e.get("type")
        elif ident in self.chambres:
            e, type_ = self.chambres[ident], "chambre_froide"
        if e is None:
            return self.nom_ligne(self.lignes[ident], article=True) if ident in self.lignes else self.nom(ident)
        base = e.get("nom") or ident
        mots = base.split()
        if MOT_PAR_TYPE.get(type_) and mots and _sans_accent(mots[0]) == MOT_PAR_TYPE[type_]:
            base = base[0].lower() + base[1:]
        elif type_ == "chambre_froide":
            base = f"chambre « {base} »"
        article = ARTICLE_PAR_TYPE.get(type_, "")
        if article in ("le ", "la ") and base[:1] in VOYELLES:
            article = "l'"
        return article + self._avec_code(e, base)

    def nom_ligne(self, l: dict, article: bool) -> str:
        t = l.get("type")
        if t == "cable":
            return ("le câble" if article else "câble") + (f" {l['repere']}" if l.get("repere") else "")
        if t in LIGNE_AVEC_ARTICLE:
            return LIGNE_AVEC_ARTICLE[t] if article else mtr.libelle_type(t, self.plan.donnees).lower()
        nom = mtr.libelle_type(t, self.plan.donnees)
        return f"le réseau « {nom} »" if article else f"réseau « {nom} »"

    def decrire_lignes(self, ids: list[str]) -> tuple[str, bool]:
        """(« l'aspiration, le liquide et les condensats de l'évaporateur CF1 (EV1) », pluriel ?) : lignes
        regroupées par équipement de départ, dans l'ordre de plan.json."""
        par_origine: dict = {}
        for lid in sorted(dict.fromkeys(ids), key=lambda i: self.rang_ligne.get(i, len(self.rang_ligne))):
            l = self.lignes.get(lid) or {"id": lid, "type": None}
            origine = None if l.get("type") == "chemin_cables" else l.get("de")
            noms = par_origine.setdefault(origine, [])
            n = self.nom_ligne(l, article=True) if l.get("type") else str(lid)
            if n not in noms:
                noms.append(n)
        morceaux = []
        for origine, noms in par_origine.items():
            texte = enumerer(noms)
            if origine is not None:
                texte += " " + de_(self.nom_article(origine))
            morceaux.append(texte)
        noms_tous = [n for noms in par_origine.values() for n in noms]
        return enumerer(morceaux), len(noms_tous) > 1 or (bool(noms_tous) and noms_tous[0].startswith("les "))

    # -- emplacements ----------------------------------------------------------------------------------------
    def ref_chambre(self, c: dict) -> str:
        return f"la chambre {c['id']}" if self.code_ecrit(c) else f"la chambre « {c.get('nom') or c['id']} »"

    @staticmethod
    def ref_piece(p: dict) -> str:
        return f"« {p.get('nom') or p['id']} »"

    def contenant(self, point) -> tuple[str | None, dict | None]:
        """La plus petite chambre, sinon la plus petite pièce, qui contient le point."""
        for genre, collection in (("chambre", self.chambres.values()), ("piece", self.pieces.values())):
            dedans = [e for e in collection if geo.point_dans_polygone(tuple(point), e["polygone"])]
            if dedans:
                return genre, min(dedans, key=lambda e: geo.surface_polygone(e["polygone"]))
        return None, None

    def lieu(self, point) -> str:
        """« dans la chambre CF1 », « dans « Cuisine » », « à l'extérieur, en haut du plan, au droit de la chambre CF1 »."""
        genre, e = self.contenant(point)
        if genre == "chambre":
            return "dans " + self.ref_chambre(e)
        if genre == "piece":
            return "dans " + self.ref_piece(e)
        if self.bati is None:
            return "hors des pièces dessinées"
        x0, y0, x1, y1 = self.bati
        exces = {"haut": y0 - point[1], "bas": point[1] - y1, "gauche": x0 - point[0], "droite": point[0] - x1}
        cote, d = max(exces.items(), key=lambda kv: kv[1])
        if d <= 1e-9:
            return "dans le bâtiment, hors des pièces dessinées"
        repere = self._au_droit(point, cote)
        return f"à l'extérieur, {COTE_DU_PLAN[cote]}" + (f", au droit de {repere}" if repere else "")

    def _au_droit(self, point, cote: str) -> str | None:
        """Chambre (sinon pièce) la plus proche du point, côté `cote`, dont l'étendue contient sa position."""
        axe = 0 if cote in ("haut", "bas") else 1
        for collection, ref in ((self.chambres.values(), self.ref_chambre), (self.pieces.values(), self.ref_piece)):
            candidats = []
            for e in collection:
                b = geo.boite_englobante(e["polygone"])
                if b[axe] - 1e-9 <= point[axe] <= b[axe + 2] + 1e-9:
                    bord = {"haut": b[1], "bas": b[3], "gauche": b[0], "droite": b[2]}[cote]
                    candidats.append((abs(point[1 - axe] - bord), ref(e)))
            if candidats:
                return min(candidats, key=lambda c: c[0])[1]
        return None

    # -- cotes -----------------------------------------------------------------------------------------------
    def _cote_du_bati(self, point) -> str:
        x0, y0, x1, y1 = self.bati
        d = {"haut": abs(point[1] - y0), "bas": abs(point[1] - y1), "gauche": abs(point[0] - x0),
             "droite": abs(point[0] - x1)}
        return min(d, key=d.get)

    def ce_que_mesure(self, c: dict) -> str:
        """« mur M1, façade du haut », « cloison M6 », « largeur de la chambre CF1 », « profondeur de la pièce
        « Cuisine » », sinon « entre deux points du plan »."""
        de, a = tuple(c["de"]), tuple(c["a"])

        def memes(p, q) -> bool:
            return ((geo.distance(p, de) <= TOL_COTE and geo.distance(q, a) <= TOL_COTE)
                    or (geo.distance(p, a) <= TOL_COTE and geo.distance(q, de) <= TOL_COTE))
        for m in self.plan.murs:
            coins = mod.coins_mur(m)
            segments = [(tuple(m["de"]), tuple(m["a"])), mod.axe_mur(m)]
            segments += [(coins[i], coins[(i + 1) % 4]) for i in range(4)]
            if any(memes(p, q) for p, q in segments):
                if m.get("type") == "exterieur" and self.bati is not None:
                    milieu = ((m["de"][0] + m["a"][0]) / 2.0, (m["de"][1] + m["a"][1]) / 2.0)
                    return f"mur {m['id']}, {FACADE[self._cote_du_bati(milieu)]}"
                return f"cloison {m['id']}" if m.get("type") == "cloison" else f"mur {m['id']}"
        horizontal, vertical = abs(de[1] - a[1]) <= TOL_COTE, abs(de[0] - a[0]) <= TOL_COTE
        for collection, ref in ((self.chambres.values(), self.ref_chambre),
                                (self.pieces.values(), lambda p: "la pièce " + self.ref_piece(p))):
            for e in collection:
                x0, y0, x1, y1 = geo.boite_englobante(e["polygone"])
                xs, ys = sorted((de[0], a[0])), sorted((de[1], a[1]))
                if (horizontal and abs(xs[0] - x0) <= TOL_COTE and abs(xs[1] - x1) <= TOL_COTE
                        and y0 - TOL_COTE <= de[1] <= y1 + TOL_COTE):
                    return f"largeur de {ref(e)}"
                if (vertical and abs(ys[0] - y0) <= TOL_COTE and abs(ys[1] - y1) <= TOL_COTE
                        and x0 - TOL_COTE <= de[0] <= x1 + TOL_COTE):
                    return f"profondeur de {ref(e)}"
        return "entre deux points du plan"

    # -- contenu ---------------------------------------------------------------------------------------------
    @staticmethod
    def _temperature(c: dict) -> str | None:
        for texte in (c.get("etiquette"), c.get("nom")):
            m = re.search(r"([+\-−]?)\s?(\d+(?:[.,]\d+)?)\s?°\s?C", texte or "")
            if m:
                signe = {"-": mtr.MOINS}.get(m.group(1), m.group(1))
                return f"{signe}{m.group(2).replace('.', ',')}{mtr.ESPACE}°C"
        return None

    def rangs_chambres(self) -> list[list[str]]:
        rangs = []
        for c in self.plan.chambres_froides:
            x0, y0, x1, y1 = geo.boite_englobante(c["polygone"])
            dims = f"{mtr.nombre_fr(x1 - x0)} × {mtr.nombre_fr(y1 - y0)}{mtr.ESPACE}m"
            if not geo.est_rectangle_aligne(c["polygone"], 1e-3):
                dims += " (encombrement, forme non rectangulaire)"
            regime = {"positif": "positif", "negatif": "négatif"}.get(c["regime"], c["regime"])
            t = self._temperature(c)
            evaps = [q for q in self.plan.equipements if q["type"] == "evaporateur" and q.get("chambre") == c["id"]]
            production = []
            for ev in evaps:
                for l in self.plan.lignes:
                    if l["type"] in ("aspiration", "liquide") and ev["id"] in (l.get("de"), l.get("a")):
                        autre = l.get("a") if l.get("de") == ev["id"] else l.get("de")
                        if autre and autre not in production:
                            production.append(autre)
            rangs.append([self.nom(c["id"]), dims, regime + (f", {t}" if t else ""),
                          ", ".join(self.nom(q["id"]) for q in evaps) or "aucun",
                          ", ".join(self.nom(p) for p in production) or "non reliée"])
        return rangs

    def autres_equipements(self) -> list[str]:
        return [f"- **{self.nom(q['id'])}** : {self.lieu(q['position'])}" for q in self.plan.equipements
                if q["type"] not in ("evaporateur", "autre")]

    def troncon(self, l: dict) -> str:
        """Tronçon d'une ligne du métré, en noms : « Évaporateur CF1 (EV1) → Centrale positive »."""
        t, de, a = l["type"], l.get("de"), l.get("a")
        libre = "extrémité libre"
        if t == "chemin_cables":
            bout = de or a
            return "Le chemin lui-même" + (f", depuis {self.nom(bout)}" if bout else "")
        depart = self.nom(de) if de else libre
        if t == "cable" and l.get("tableau"):
            return f"{depart} {mtr.FLECHE} {self.nom(l['tableau'])}, par le chemin de câbles"
        arrivee = self.nom(a) if a else ("évacuation à préciser" if t == "condensats" else libre)
        return f"{depart} {mtr.FLECHE} {arrivee}"

    def type_ligne(self, lid: str, l: dict) -> str:
        repere = (self.lignes.get(lid) or {}).get("repere")
        return l["libelle_type"] + (f" {repere}" if l["type"] == "cable" and repere else "")

    def phrase_groupe(self, g: dict, par_id: dict) -> str:
        """« - **G1**, dans « Laboratoire de découpe » : l'aspiration, le liquide et les condensats de
        l'évaporateur CF1 (EV1) croisent le chemin de câbles. »"""
        paires = [par_id[x]["lignes"] for x in g["croisements"] if x in par_id]
        communes = [lid for lid in paires[0] if all(lid in p for p in paires)] if paires else []
        if communes:
            pivot = communes[-1]
            autres = [lid for p in paires for lid in p if lid != pivot]
            gauche, pluriel = self.decrire_lignes(autres)
            droite, _ = self.decrire_lignes([pivot])
            texte = f"{gauche} {'croisent' if pluriel else 'croise'} {droite}"
        else:
            morceaux = []
            for la, lb in paires:
                ga, pluriel = self.decrire_lignes([la])
                morceaux.append(f"{ga} {'croisent' if pluriel else 'croise'} {self.decrire_lignes([lb])[0]}")
            texte = " ; ".join(morceaux)
        return f"- **{g['id']}**, {self.lieu(g['point'])} : {texte}."


def question_ecart(vue: Vue, lid: str, l: dict) -> str:
    """Question posée quand une longueur mesurée s'écarte de plus de 20 % de l'estimation du plan (en mots)."""
    return (f"La ligne « {vue.type_ligne(lid, l)} : {vue.troncon(l)} » mesurée à {mtr.longueur_fr(l['total_m'])} "
            f"s'écarte de l'estimation du plan ({mtr.longueur_fr(l['estimation_plan_m'])}) : le tracé correspond-il "
            "à la réalité ?")


def questions_ouvertes(plan: mod.Plan, m: mtr.Metre, vue: Vue | None = None) -> list[str]:
    """Questions pour Loïc, en mots (aucun code de ligne)."""
    vue = vue or Vue(plan)
    q = []
    for l in plan.lignes:
        if l["type"] == "chemin_cables":
            continue                              # un chemin de câbles a naturellement une extrémité libre
        desc, pluriel = vue.decrire_lignes([l["id"]])
        for cle, bout, point in (("de", "au départ", l["points"][0]), ("a", "à l'arrivée", l["points"][-1])):
            if l.get(cle):
                continue
            if l["type"] == "condensats" and cle == "a":
                q.append(f"{_maj(desc)} s'arrêtent {vue.lieu(point)} : où se raccordent-ils (siphon, descente, "
                         "regard) ?")
            else:
                verbe = "n'ont" if pluriel else "n'a"
                q.append(f"{_maj(desc)} {verbe} pas d'équipement {bout} "
                         f"({vue.lieu(point)}) : à quel équipement {'les' if pluriel else 'la'} relier ?")
    for lid in m.lignes_ecart_fort():
        q.append(question_ecart(vue, lid, m.lignes[lid]))
    a_definir = [l["id"] for l in plan.lignes if mtr.normaliser_diametre(l.get("diametre")) == mtr.A_DEFINIR
                 and l["type"] not in ("chemin_cables",)]
    if a_definir:
        q.append(f"Diamètres des tuyaux et sections des câbles : {mtr.A_DEFINIR_FOURNISSEUR} "
                 f"({len(a_definir)} lignes).")
    if any(h["statut"] == mtr.HYPOTHESE for h in m.hypotheses):
        q.append("Hauteurs de pose à valider (question 13) : tableau « Hauteurs de pose » ci-dessus.")
    for cle, v in plan.exigences.items():
        if isinstance(v, dict):
            details = ", ".join(f"{k} {str(w).replace('_', ' ')}" for k, w in v.items() if k != "motif")
            q.append(f"Exception admise pour {vue.nom(cle)} ({details}) : {v.get('motif') or 'motif à écrire'}.")
    return q


def tableaux_metre_lisibles(m: mtr.Metre, vue: Vue) -> list[str]:
    """Un tableau par réseau (« ### <réseau> » : Tronçon | Type | En plan | [dont chemin de câbles] | Montées et
    descentes | [Réserve] | Total, ligne de total) puis le récapitulatif « Réseau | Total ». Toutes les longueurs
    sont des estimations (phrase en tête du métré) ; « (mesurée) » après le total d'une ligne mesurée sur chantier,
    et après un total (réseau, récapitulatif) dont toutes les lignes le sont ; plus de « (hyp.) »."""
    morceaux, recap = [], []
    for cle, r in m.par_reseau.items():
        lignes = [(lid, m.lignes[lid]) for lid in r["lignes"]]
        avec_chemin = r["chemin_m"] > 0
        avec_reserve = r["reserve_m"] > 0
        avec_diametre = any(l["diametre"] != mtr.A_DEFINIR for _, l in lignes if l["type"] != "chemin_cables")
        entetes = ([mtr.COL_TRONCON, mtr.COL_TYPE] + ([mtr.COL_DIAMETRE] if avec_diametre else []) + [mtr.COL_PLAN]
                   + ([mtr.COL_DONT_CHEMIN] if avec_chemin else []) + [mtr.COL_MONTEES]
                   + ([mtr.COL_RESERVE] if avec_reserve else []) + [mtr.COL_TOTAL])
        aligne = ["g", "g"] + (["g"] if avec_diametre else []) + ["d"] * (len(entetes) - 2 - avec_diametre)
        rangs = []
        for lid, l in lignes:
            support = l["type"] == "chemin_cables"
            rang = [vue.troncon(l), vue.type_ligne(lid, l)]
            if avec_diametre:
                rang.append("" if support else l["diametre"])
            rang.append(mtr.nombre_fr(mtr.arrondi(l["plan_m"] + l["chemin_m"])))
            if avec_chemin:
                rang.append("" if support else mtr.nombre_fr(l["chemin_m"]))
            rang.append(mtr.nombre_fr(l["vertical_m"]))
            if avec_reserve:
                rang.append("" if support else mtr.nombre_fr(l["reserve_m"]))
            rang.append(mtr.nombre_fr(l["total_m"]) + m.marque([lid]))
            rangs.append(rang)
        total = ["Total", ""] + ([""] if avec_diametre else []) + [mtr.nombre_fr(mtr.arrondi(r["plan_m"] + r["chemin_m"]))]
        if avec_chemin:
            total.append(mtr.nombre_fr(r["chemin_m"]))
        total.append(mtr.nombre_fr(r["vertical_m"]))
        if avec_reserve:
            total.append(mtr.nombre_fr(r["reserve_m"]))
        total.append(mtr.nombre_fr(r["total_m"]) + m.marque(r["lignes"]))
        rangs.append(total)
        nom = mtr.nom_reseau_lisible(cle, vue.plan.donnees)
        morceaux += [f"### {nom}", "", _table_md(entetes, rangs, aligne, {len(rangs) - 1}), ""]
        recap.append([nom, mtr.nombre_fr(r["total_m"]) + m.marque(r["lignes"])])
    morceaux += [f"### {mtr.TITRE_RECAPITULATIF}", "",
                 _table_md([mtr.COL_RESEAU, mtr.COL_TOTAL], recap, ["g", "d"]), ""]
    return morceaux


# ======================================================================
# plan.md (lu par Loïc, via plan.html) et metre-detail.md (mémoire de Claude, non rendu)
# ======================================================================
def ecrire_plan_md(chemin: Path, plan: mod.Plan, ech, m: mtr.Metre, liste_x: list[dict], recouv: list[dict],
                   version: int, maintenant: datetime, rendu_info: dict | None, journal: list[str],
                   groupes: list[dict] | None = None, sans_image: str | None = None) -> Path:
    """plan.md, lisible d'abord : le plan (image), ce qu'il contient, le métré par réseau en noms, les croisements
    en mots, les cotes, les hauteurs, les questions, puis des détails techniques courts. `sans_image` : raison
    pour laquelle plan.png n'est pas montré (pas de rendu à cette génération)."""
    vue = Vue(plan)
    groupes = groupes if groupes is not None else crx.regrouper(liste_x)
    titre = plan.titre or "Plan 2D"
    infos = ([f"Dossier {plan.dossier}"] if plan.dossier else []) + (
        [f"relevé du {date_fr(plan.date)}"] if plan.date else []) + [
        f"version {version}", f"échelle 1:{ech.S}", f"{ech.format} {ech.orientation}"]
    morceaux = [f"<!-- titre: Plan : {titre} -->", "", f"# {titre}", "", " · ".join(infos), ""]

    # 2. le plan
    morceaux += ["## Le plan", ""]
    if sans_image:
        morceaux += [f"Image du plan non produite à cette génération ({sans_image}) : relancer `generer.py` "
                     "avec le rendu.", ""]
    else:
        morceaux += ["![Plan](plan.png)", ""]
    morceaux += [f"Imprimer `plan.pdf` à 100 % (taille réelle). Sur le papier, la règle de contrôle du cartouche doit "
                 f"mesurer 100 mm, et 1 m du bâtiment fait {nombre_court(100.0 / ech.S)} cm.", ""]

    # 3. ce que le plan contient
    morceaux += ["## Ce que le plan contient", ""]
    if plan.chambres_froides:
        morceaux += [_table_md(["Chambre", "Dimensions", "Régime / température", "Évaporateur", "Alimentée par"],
                               vue.rangs_chambres()), ""]
    else:
        morceaux += ["Aucune chambre froide sur ce plan.", ""]
    autres = vue.autres_equipements()
    if autres:
        morceaux += ["Autres équipements :", ""] + autres + [""]

    # 4. métré
    morceaux += ["## Métré", ""]
    if m.lignes:
        morceaux += [mtr.PHRASE_LONGUEURS, ""]
        morceaux += tableaux_metre_lisibles(m, vue)
        morceaux += [m.note(), ""]
    else:
        morceaux += ["Aucune ligne à métrer.", ""]

    # 5. croisements
    morceaux += [f"## {TITRE_CROISEMENTS_MD}", ""]
    if groupes:
        n = len(groupes)
        reperes = groupes[0]["id"] if n == 1 else f"{groupes[0]['id']} à {groupes[-1]['id']}"
        morceaux += [f"{n} endroit{'s' if n > 1 else ''} où des réseaux se croisent (sur le chantier, l'un passe "
                     f"au-dessus de l'autre), repéré{'s' if n > 1 else ''} {reperes} sur le plan :", ""]
        par_id = {x["id"]: x for x in liste_x}
        morceaux += [vue.phrase_groupe(g, par_id) for g in groupes] + [""]
    else:
        morceaux += [crx.AUCUN, ""]
    if recouv:
        morceaux += ["Lignes posées l'une sur l'autre (non comptées comme croisements) :", ""]
        for r in recouv:
            milieu = ((r["de"][0] + r["a"][0]) / 2.0, (r["de"][1] + r["a"][1]) / 2.0)
            a_, _ = vue.decrire_lignes([r["lignes"][0]])
            b_, _ = vue.decrire_lignes([r["lignes"][1]])
            morceaux.append(f"- {_maj(a_)} et {b_} : l'un sur l'autre sur {mtr.longueur_fr(r['longueur_m'])}, "
                            f"{vue.lieu(milieu)}.")
        morceaux.append("")

    # 6. cotes
    morceaux += ["## Cotes relevées", ""]
    if plan.cotes:
        morceaux.append(_table_md(["Cote", "Longueur", "Ce qu'elle mesure", "Source"],
                                  [[c["id"], mtr.longueur_fr(c["valeur"]), vue.ce_que_mesure(c),
                                    source_en_mots(c.get("source"))] for c in plan.cotes],
                                  ["g", "d", "g", "g"]))
    else:
        morceaux.append("Aucune cote dans le modèle : demander les cotes au frigoriste (télémètre).")
    morceaux.append("")

    # 7. hauteurs et questions
    hyp = any(h["statut"] == mtr.HYPOTHESE for h in m.hypotheses)
    morceaux += [f"## Hauteurs de pose{' (hypothèses)' if hyp else ''}", ""]
    if m.hypotheses:
        morceaux.append(_table_md(["Élément", "Hauteur", "Statut"],
                                  [[h["libelle"], mtr.longueur_fr(h["valeur"]), h["statut"]] for h in m.hypotheses],
                                  ["g", "d", "g"]))
    else:
        morceaux.append("Aucune hauteur utilisée (aucune ligne à métrer).")
    morceaux.append("")
    q = questions_ouvertes(plan, m, vue)
    morceaux += ["## Questions ouvertes", ""] + ([f"- {x}" for x in q] if q else ["Aucune."]) + [""]

    # 8. détails techniques (court)
    morceaux += ["## Détails techniques", "",
                 "- Fichiers : `plan.drawio` (à ouvrir dans draw.io), `plan.pdf` (à imprimer), `plan.png` (image du "
                 "plan), `metre-detail.md` (détail du calcul par ligne), `verification.md` (dernier contrôle, "
                 "`verifier_plan.py`)."]
    if rendu_info and rendu_info.get("regle_pt"):
        voie = "draw.io Desktop" if rendu_info["voie"] == "drawio" else "Edge + viewer diagrams.net (secours)"
        s_txt = f"{rendu_info['facteur_s']:.6f}".replace(".", ",")
        regle_txt = f"{rendu_info['regle_pt'] / PT_PAR_MM:.3f}".replace(".", ",")
        ecart_txt = f"{rendu_info['ecart_pct']:+.3f}".replace(".", ",").replace("-", mtr.MOINS)
        morceaux.append(f"- Rendu du PDF : {voie}, facteur de correction s = {s_txt}, règle de 100 mm mesurée "
                        f"dans le PDF : {regle_txt} mm (écart {ecart_txt} %).")
    else:
        morceaux.append("- PDF non rendu à cette génération (`--sans-rendu` ou rendu en échec).")
    morceaux.append("- Calques (draw.io, menu Affichage > Calques) : " + ", ".join(n for _, n in plan.calques()) + ".")
    versions = journal[-VERSIONS_MONTREES:]
    if versions:
        entete = ("- Versions :" if len(journal) <= VERSIONS_MONTREES else
                  f"- Versions (les {VERSIONS_MONTREES} dernières ; toutes dans `journal.md`) :")
        morceaux += [entete] + ["    " + v for v in versions]
    morceaux.append("")
    chemin.write_text("\n".join(morceaux), encoding="utf-8", newline="\n")
    return chemin


def ecrire_metre_detail(chemin: Path, plan: mod.Plan, m: mtr.Metre, liste_x: list[dict], recouv: list[dict],
                        version: int, maintenant: datetime, groupes: list[dict] | None = None) -> Path:
    """metre-detail.md : mémoire de Claude (non rendue en HTML), relue par verifier_plan.py (E6 ligne par ligne,
    E7 croisement par croisement). Codes, formules, hauteurs, diamètres, calques, notes du relevé."""
    titre = plan.titre or "Plan 2D"
    morceaux = [f"# Métré détaillé : {titre}", "",
                f"Mémoire du skill froid-plan-2d (v{version}, générée le {maintenant:%Y-%m-%d à %H:%M}), non rendue "
                "en HTML : Loïc lit `plan.html`. Relue par `verifier_plan.py` (E6, E7).", ""]
    morceaux += [f"## {TITRES_SECTIONS['reseaux']}", ""]
    if m.lignes:
        morceaux += [f"Métré d'une ligne = longueur du tracé en plan + |passage {mtr.MOINS} départ| + |passage "
                     f"{mtr.MOINS} arrivée| + réserve (câbles seulement) ; un câble qui s'arrête sur le chemin de "
                     "câbles compte aussi son parcours dans le chemin jusqu'au tableau (colonne « Dans le chemin ») ; "
                     "le chemin de câbles lui-même est métré une fois, à part, sans métré vertical. Dans plan.md, "
                     "« En plan » = en plan + dans le chemin, « Montées et descentes » = vertical.", "",
                     tableau_reseaux_md(m), "", "## Détail du calcul par ligne", ""]
        morceaux += [f"- **{lid}** ({l['libelle_type']}, {l['de'] or mtr.TIRET_VIDE} {mtr.FLECHE} "
                     f"{l['a'] or mtr.TIRET_VIDE}) : {l['formule']}" for lid, l in m.lignes.items()]
        morceaux += ["", f"## {TITRES_SECTIONS['diametres']}", "", tableau_diametres_md(m), ""]
        morceaux += [f"## {TITRE_MESURES}", "", mtr.PHRASE_LONGUEURS + " Une ligne mesurée garde ici son "
                     "estimation du plan (colonnes de « Métré par réseau ») ; son total est la mesure. Au delà de "
                     "20 % d'écart, une question est posée dans plan.md et le vérificateur avertit (E6).", ""]
        if any(l["origine"] == mtr.MESUREE for l in m.lignes.values()):
            morceaux += [tableau_mesures_md(m), ""]
        else:
            morceaux += ["Aucune longueur mesurée sur chantier : toutes sont des estimations d'après le plan.", ""]
    else:
        morceaux += ["Aucune ligne à métrer.", ""]
    morceaux += ["## Hauteurs utilisées", ""]
    if m.hypotheses:
        morceaux += [_table_md(["Hauteur", "Valeur (m)", "Statut", "Lignes"],
                               [[h["libelle"], mtr.nombre_fr(h["valeur"]), h["statut"], ", ".join(h.get("lignes") or [])]
                                for h in m.hypotheses], ["g", "d", "g", "g"]), ""]
    else:
        morceaux += ["Aucune.", ""]
    morceaux += [f"## {TITRES_SECTIONS['croisements']}", "",
                 "Un cercle orange par repère G sur le plan (calque « Croisements ») : les croisements distants de "
                 "0,50 m au plus partagent le même cercle, étiqueté à côté (« X1-X3 ») :", "",
                 crx.tableau_markdown(liste_x, groupes), ""]
    if recouv:
        morceaux += ["Recouvrements (deux lignes superposées en plan, non comptés comme croisements) :", ""]
        morceaux += [f"- {r['id']} : {r['lignes'][0]} et {r['lignes'][1]} superposées sur "
                     f"{mtr.longueur_fr(r['longueur_m'])}, de {_pt(r['de'])} à {_pt(r['a'])} m." for r in recouv]
        morceaux.append("")
    rangs = []
    for cle, nom in plan.calques():
        lignes = [l["id"] for l in plan.lignes if l.get("calque") == cle]
        equip = [q["id"] for q in plan.equipements if q.get("calque") == cle]
        contenu = ([f"équipements {', '.join(equip)}"] if equip else []) + (
            [f"lignes {', '.join(lignes)}"] if lignes else []) + (
            [f"{len(liste_x)} croisement(s)"] if cle == "croisements" else [])
        rangs.append([cle, nom, " ; ".join(contenu) or mtr.TIRET_VIDE])
    morceaux += ["## Calques", "", _table_md(["Calque", "Nom", "Contenu"], rangs), ""]
    if plan.notes:
        morceaux += ["## Notes du relevé", ""] + [f"- {n}" for n in plan.notes] + [""]
    chemin.write_text("\n".join(morceaux), encoding="utf-8", newline="\n")
    return chemin


def contenu_metre_json(plan: mod.Plan, ech, m: mtr.Metre, version: int | None, genere_le: str | None,
                       dossier_plan: Path | None = None, vue: Vue | None = None) -> dict:
    """Contenu de `plan/metre.json` (contrat du 2026-10-08) : tronçons en noms comme dans plan.md, dossier =
    `plan.json` « dossier » (sinon le nom du dossier d'installation)."""
    vue = vue or Vue(plan)
    troncons = {lid: vue.troncon(l) for lid, l in m.lignes.items()}
    dossier = plan.dossier or (Path(dossier_plan).resolve().parent.name if dossier_plan else None)
    return m.contrat_json(troncons, dossier=dossier, plan_version=version, echelle=f"1:{ech.S}", genere_le=genere_le)


def ecrire_metre_json(chemin: Path, plan: mod.Plan, ech, m: mtr.Metre, version: int, maintenant: datetime) -> Path:
    """plan/metre.json : métré pour la demande fournisseur (froid-demande-fournisseur, `assembler.py`)."""
    contenu = contenu_metre_json(plan, ech, m, version, maintenant.isoformat(timespec="seconds"), chemin.parent)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return chemin


RE_IMAGE_PLAN = re.compile(r'<img alt="Plan" src="plan\.png"\s*/?>')


def image_pleine_largeur(chemin_html: Path) -> None:
    """Dans plan.html, l'image du plan prend toute la largeur et s'ouvre en taille réelle au clic (le rendu
    markdown partagé n'a pas de style pour une image seule)."""
    page = chemin_html.read_text(encoding="utf-8")
    nouvelle = RE_IMAGE_PLAN.sub('<a href="plan.png" target="_blank" title="Ouvrir l\'image en taille réelle">'
                                 '<img alt="Plan" src="plan.png" style="display:block;width:100%;height:auto;'
                                 'border:1px solid #d9d9de;border-radius:4px"></a>', page, count=1)
    if nouvelle != page:
        chemin_html.write_text(nouvelle, encoding="utf-8", newline="\n")


# ======================================================================
# Génération
# ======================================================================
def preparer(dossier: Path) -> dict:
    """Charge et valide le modèle, calcule métré, croisements et échelle (rien n'est écrit).
    `ErreurGeneration` (message multi-lignes) si le plan n'est pas générable."""
    chemin = dossier / "plan.json"
    try:
        plan = mod.charger(chemin)
    except mod.ErreurModele as exc:
        raise ErreurGeneration(str(exc)) from exc
    erreurs = plan.valider()
    if erreurs:
        raise ErreurGeneration("plan.json incohérent, rien n'a été généré :\n- " + "\n- ".join(erreurs))
    try:
        m = mtr.metrer(plan.donnees)
        liste_x = crx.croisements(plan.donnees)
        recouv = crx.recouvrements(plan.donnees)
    except (mtr.ErreurMetre, crx.ErreurCroisements) as exc:
        raise ErreurGeneration(f"Métré ou croisements impossibles : {exc}") from exc
    groupes = crx.regrouper(liste_x)
    donnees = copy.deepcopy(plan.donnees)
    donnees["croisements"] = crx.groupes_pour_dessin(groupes)      # un cercle par groupe (repères G)
    plan_x = mod.depuis_dict(donnees, chemin)
    try:
        ech = choisir_echelle(plan_x.bbox(), plan_x.page)
    except ErreurEchelle as exc:
        raise ErreurGeneration(str(exc)) from exc
    return {"plan": plan, "plan_x": plan_x, "metre": m, "croisements": liste_x, "groupes": groupes,
            "recouvrements": recouv, "echelle": ech}


def tableaux_page_metre(m: mtr.Metre, liste_x: list[dict], groupes: list[dict] | None = None) -> list[tuple[str, str]]:
    return m.tableaux_html() + [(TITRE_TABLEAU_CROISEMENTS, crx.tableau_html(liste_x, groupes))]


def generer(dossier_plan, rendu_pdf: bool = True, ouvrir: bool = False, maintenant: datetime | None = None,
            voie: str = "auto") -> dict:
    """Génère tous les fichiers du plan. Renvoie {code, erreurs, avertissements, fichiers, version, echelle,
    rendu, croisements}. Code 1 sans rien écrire si le modèle est invalide ; code 1 (fichiers écrits) si le
    rendu PDF échoue."""
    dossier = Path(dossier_plan)
    res = {"code": 0, "erreurs": [], "avertissements": [], "fichiers": {}, "version": None, "echelle": None,
           "rendu": None, "croisements": []}
    if not (dossier / "plan.json").is_file():
        res.update(code=1, erreurs=[f"plan.json introuvable dans {dossier}."])
        return res
    try:
        p = preparer(dossier)
    except ErreurGeneration as exc:
        res.update(code=1, erreurs=[str(exc)])
        return res
    maintenant = maintenant or datetime.now()
    plan, ech, m, liste_x = p["plan"], p["echelle"], p["metre"], p["croisements"]
    res.update(echelle=ech, croisements=liste_x)
    version = prochaine_version(dossier)
    res["version"] = version

    f = res["fichiers"]
    f["drawio"] = drawio.ecrire(p["plan_x"], ech, dossier / "plan.drawio",
                                tableaux_page_metre(m, liste_x, p["groupes"]),
                                entete=mtr.PHRASE_LONGUEURS if m.lignes else None)

    rendu_info = None
    if rendu_pdf:
        try:
            rendu_info = rendu.rendre(dossier, voie=voie)
            res["rendu"] = rendu_info
            f["pdf"], f["png"] = rendu_info["pdf"], rendu_info["png"]
            res["avertissements"] += rendu_info["avertissements"]
        except (rendu.ErreurRendu, drawio.ErreurLecture) as exc:
            res["code"] = 1
            res["erreurs"].append(f"Rendu PDF/PNG impossible : {exc}")

    rendu_txt = ("sans rendu" if not rendu_pdf else
                 (f"rendu {rendu_info['voie']} (s = {rendu_info['facteur_s']:.6f}, règle "
                  f"{rendu_info['regle_pt'] / PT_PAR_MM:.3f} mm)").replace(".", ",") if rendu_info else "rendu en échec")
    ligne_journal = (f"- {maintenant:%Y-%m-%d %H:%M} · v{version} · 1:{ech.S} {ech.orientation} · "
                     f"{len(plan.lignes)} lignes, {len(liste_x)} croisement(s) · {rendu_txt}")
    journal = lire_journal(dossier) + [ligne_journal]

    sans_image = None if rendu_info else ("`--sans-rendu`" if not rendu_pdf else "rendu en échec")
    f["md"] = ecrire_plan_md(dossier / "plan.md", plan, ech, m, liste_x, p["recouvrements"], version, maintenant,
                             rendu_info, journal, p["groupes"], sans_image=sans_image)
    f["metre_detail"] = ecrire_metre_detail(dossier / "metre-detail.md", plan, m, liste_x, p["recouvrements"],
                                            version, maintenant, p["groupes"])
    f["metre_json"] = ecrire_metre_json(dossier / "metre.json", plan, ech, m, version, maintenant)
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from shared.rendu_html import convertir
        f["html"] = convertir(f["md"], racine=dossier, navigation=[])
        image_pleine_largeur(f["html"])
    except Exception as exc:  # noqa: BLE001 - la vue HTML est un confort : son échec ne bloque pas le plan
        res["avertissements"].append(f"plan.html non produit ({type(exc).__name__} : {exc}).")

    base = {"S": ech.S, "orientation": ech.orientation,
            "origine_mm": [round(ech.origine_mm[0], 4), round(ech.origine_mm[1], 4)]}
    f["plan_base"] = dossier / "plan-base.json"
    f["plan_base"].write_text(json.dumps(base, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    versions = dossier / "versions"
    versions.mkdir(exist_ok=True)
    f["version_drawio"] = versions / f"plan-v{version}.drawio"
    f["version_json"] = versions / f"plan-v{version}.json"
    shutil.copyfile(f["drawio"], f["version_drawio"])
    shutil.copyfile(dossier / "plan.json", f["version_json"])

    chemin_journal = dossier / "journal.md"
    entete = "" if chemin_journal.is_file() else "# Journal des générations du plan\n\n"
    with chemin_journal.open("a", encoding="utf-8", newline="\n") as j:
        j.write(entete + ligne_journal + "\n")
    f["journal"] = chemin_journal

    if ouvrir and f.get("html"):
        from shared.rendu_html import ouvrir_page
        ouvrir_page(f["html"])
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Génère plan.drawio, plan.md/html, plan.pdf/png depuis plan.json.")
    ap.add_argument("dossier_plan", help="dossier plan/ du dossier d'installation (contient plan.json)")
    ap.add_argument("--sans-rendu", action="store_true", help="ne pas produire plan.pdf et plan.png")
    ap.add_argument("--ouvrir", action="store_true", help="ouvrir plan.html dans le navigateur")
    a = ap.parse_args(argv)
    r = generer(a.dossier_plan, rendu_pdf=not a.sans_rendu, ouvrir=a.ouvrir)
    if r["version"] is not None:
        e = r["echelle"]
        print(f"Plan v{r['version']} : échelle 1:{e.S}, {e.orientation}, {len(r['croisements'])} croisement(s).")
        for nom, chemin in r["fichiers"].items():
            if chemin:
                print(f"  {nom} : {chemin}")
        if r["rendu"]:
            ri = r["rendu"]
            print(f"  rendu : {ri['voie']}, s = {ri['facteur_s']:.6f}, règle de 100 mm mesurée "
                  f"{ri['regle_pt'] / PT_PAR_MM:.3f} mm (écart {ri['ecart_pct']:+.3f} %)")
    for m in r["avertissements"]:
        print(f"Avertissement : {m}")
    for m in r["erreurs"]:
        print(f"Erreur : {m}", file=sys.stderr)
    return r["code"]


if __name__ == "__main__":
    sys.exit(main())
