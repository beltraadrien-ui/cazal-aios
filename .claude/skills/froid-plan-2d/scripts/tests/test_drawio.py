"""Tests de drawio.py : aller-retour plan.json → plan.drawio → lire() = modèle à 1 cm (boucherie test et
3 plans synthétiques), identifiants stables, 2 pages, calques dans l'ordre, page A4, barre d'échelle,
règle de contrôle, cartouche, robustesse de la lecture (fichier retouché par draw.io Desktop, page
compressée, cellule enveloppée, arête raccordée, porte retournée), détection des écarts.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -p "test_drawio.py" -v
Données génériques (« boucherie test » fictive et plans inventés), aucune donnée client.
"""
from __future__ import annotations

import base64
import re
import sys
import tempfile
import unittest
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # dossier scripts/
import drawio  # noqa: E402
import geometrie as geo  # noqa: E402
import modele as mod  # noqa: E402
from echelle import PX_PAR_MM, choisir_echelle  # noqa: E402

BOUCHERIE = Path(__file__).resolve().parent / "fixtures" / "a1-boucherie-plan.json"
TOL = 0.01


def plan_chambre_seule() -> dict:
    """3 × 4 m, 1:50 : chambre négative avec porte « droite », évaporateur sans soufflage (déduit), groupe
    tourné de 90°, tableau dehors, fenêtre verticale, calque libre en trait double, croisement fourni."""
    return {
        "version": 1, "titre": "Synthèse 1 : chambre seule", "dossier": "test-a1-1", "date": "2026-10-07",
        "page": {"format": "A4", "orientation": "auto", "echelle": None},
        "murs": [{"id": f"M{i + 1}", "de": de, "a": a, "epaisseur": 0.2, "alignement": "droite"}
                 for i, (de, a) in enumerate((([0, 0], [3, 0]), ([3, 0], [3, 4]), ([3, 4], [0, 4]), ([0, 4], [0, 0])))],
        "pieces": [{"id": "P1", "nom": "Local", "polygone": [[0.2, 0.2], [2.8, 0.2], [2.8, 3.8], [0.2, 3.8]],
                    "contour": True, "etiquette": "Local technique", "position_etiquette": [1.5, 3.3]}],
        "chambres_froides": [{"id": "CF1", "regime": "negatif", "polygone": [[0.4, 0.4], [2.6, 0.4], [2.6, 2.6], [0.4, 2.6]],
                              "porte": {"position": [2.6, 1.0], "largeur": 0.8, "orientation": 270, "sens": "droite"}}],
        "portes": [{"id": "D1", "position": [2.0, 3.8], "largeur": 0.9, "orientation": 180, "dans": "M3"}],
        "fenetres": [{"id": "F1", "position": [0.1, 3.2], "largeur": 0.6, "orientation": 90, "dans": "M4"}],
        "equipements": [
            {"id": "EV1", "type": "evaporateur", "position": [1.5, 0.75], "chambre": "CF1"},
            {"id": "GR1", "type": "groupe", "position": [4.2, 1.5], "rotation": 90},
            {"id": "TD", "type": "tableau", "position": [-0.4, 2.0], "rotation": 90},
        ],
        "cotes": [
            {"id": "C1", "de": [0, 0], "a": [3, 0], "valeur": 3.0, "cote": "haut", "decalage": 0.5},
            {"id": "C2", "de": [3, 0], "a": [3, 4], "valeur": 4.0, "cote": "droite", "decalage": 2.0},
            {"id": "C3", "de": [0, 4], "a": [3, 4], "valeur": 3.0, "cote": "bas", "decalage": 0.5},
            {"id": "C4", "de": [0, 0], "a": [0, 4], "valeur": 4.0, "cote": "gauche", "decalage": 0.9},
        ],
        "calques_libres": [{"cle": "eau_glacee", "nom": "Eau glacée", "couleur": "#00838F", "trait": "double"}],
        "lignes": [
            {"id": "LA1", "type": "aspiration", "de": "EV1", "a": "GR1", "faisceau": "EV1",
             "points": [[2.1, 0.75], [3.6, 0.75], [3.6, 1.5], [3.9, 1.5]]},
            {"id": "LL1", "type": "liquide", "de": "EV1", "a": "GR1", "faisceau": "EV1",
             "points": [[2.1, 0.9], [3.5, 0.9], [3.5, 1.6], [3.9, 1.6]]},
            {"id": "LE1", "type": "cable", "de": "EV1", "a": "TD", "repere": "C1",
             "points": [[0.9, 0.6], [-0.1, 0.6], [-0.1, 2.0], [-0.3, 2.0]]},
            {"id": "LG1", "type": "eau_glacee", "points": [[-1.0, 3.0], [4.0, 3.0]]},
        ],
        "croisements": [{"id": "X1", "point": [1.5, 3.0]}],
    }


def plan_entrepot() -> dict:
    """40 × 25 m, 1:200 : murs décrits sur leur axe, évaporateurs tournés de 180° et 270°, lignes à 4 points."""
    return {
        "version": 1, "titre": "Synthèse 2 : entrepôt", "dossier": "test-a1-2", "date": "2026-10-07",
        "murs": [
            {"id": "M1", "de": [0, 0.1], "a": [40, 0.1]}, {"id": "M2", "de": [39.9, 0], "a": [39.9, 25]},
            {"id": "M3", "de": [40, 24.9], "a": [0, 24.9]}, {"id": "M4", "de": [0.1, 25], "a": [0.1, 0]},
            {"id": "M5", "de": [20.05, 0.2], "a": [20.05, 24.8], "type": "cloison"},
        ],
        "pieces": [{"id": "P1", "nom": "Stockage froid", "polygone": [[0.2, 0.2], [20, 0.2], [20, 24.8], [0.2, 24.8]]},
                   {"id": "P2", "nom": "Quai", "polygone": [[20.1, 0.2], [39.8, 0.2], [39.8, 24.8], [20.1, 24.8]],
                    "contour": True}],
        "chambres_froides": [
            {"id": "CF1", "regime": "positif", "polygone": [[1, 1], [9, 1], [9, 7], [1, 7]],
             "porte": {"position": [5, 7], "largeur": 1.0, "orientation": 0}},
            {"id": "CF2", "regime": "negatif", "polygone": [[10, 1], [16, 1], [16, 7], [10, 7]],
             "porte": {"position": [12, 7], "largeur": 1.2, "orientation": 0}},
        ],
        "portes": [{"id": "D1", "position": [35, 24.8], "largeur": 3.0, "orientation": 180, "dans": "M3"}],
        "fenetres": [{"id": "F1", "position": [30, 24.9], "largeur": 3.0, "orientation": 0, "dans": "M3"},
                     {"id": "F2", "position": [0.1, 15], "largeur": 2.0, "orientation": 90, "dans": "M4"}],
        "equipements": [
            {"id": "EV1", "type": "evaporateur", "position": [5, 1.6], "dimensions": [2.0, 0.6], "rotation": 180,
             "chambre": "CF1"},
            {"id": "EV2", "type": "evaporateur", "position": [15.5, 4], "dimensions": [1.5, 0.6], "rotation": 270,
             "chambre": "CF2", "soufflage": "gauche"},
            {"id": "CP1", "type": "centrale", "position": [25, -2]},
            {"id": "GR1", "type": "groupe", "position": [30, -2]},
            {"id": "TD", "type": "tableau", "position": [20.4, 12], "rotation": 90},
        ],
        "cotes": [
            {"id": "C1", "de": [0, 0], "a": [40, 0], "valeur": 40.0, "cote": "haut", "decalage": 1.0},
            {"id": "C2", "de": [40, 0], "a": [40, 25], "valeur": 25.0, "cote": "droite", "decalage": 1.0},
            {"id": "C3", "de": [1, 7], "a": [9, 7], "valeur": 8.0, "cote": "bas", "decalage": 1.0},
        ],
        "lignes": [
            {"id": "LA1", "type": "aspiration", "de": "EV1", "a": "CP1", "points": [[5, 1.3], [5, 0.5], [24.5, 0.5], [24.5, -1.6]]},
            {"id": "LA2", "type": "aspiration", "de": "EV2", "a": "GR1", "points": [[15.5, 3.25], [15.5, 0.6], [30, 0.6], [30, -1.7]]},
            {"id": "LE1", "type": "cable", "de": "EV1", "a": "TD", "points": [[6, 1.6], [19, 1.6], [19, 12], [20.3, 12]]},
            {"id": "LE2", "type": "cable", "de": "EV2", "a": "TD", "points": [[15.8, 4], [18.5, 4], [18.5, 11.9], [20.3, 11.9]]},
        ],
        "croisements": [{"id": "X1", "point": [15.5, 1.6]}],
    }


def plan_portrait() -> dict:
    """12 × 30 m en portrait (1:150) : 8 portes (4 orientations × 2 sens), mur oblique aligné à gauche,
    évaporateur à 45°, cote oblique, clim, câble à 5 points."""
    murs = [{"id": f"M{i + 1}", "de": de, "a": a, "epaisseur": 0.2, "alignement": "droite"}
            for i, (de, a) in enumerate((([0, 0], [12, 0]), ([12, 0], [12, 30]), ([12, 30], [0, 30]), ([0, 30], [0, 0])))]
    murs += [{"id": "M5", "de": [0.2, 10.05], "a": [11.8, 10.05], "type": "cloison"},
             {"id": "M6", "de": [0.2, 20.05], "a": [11.8, 20.05], "type": "cloison"},
             {"id": "M7", "de": [2, 21], "a": [6, 24], "type": "cloison", "alignement": "gauche"}]
    return {
        "version": 1, "titre": "Synthèse 3 : bâtiment en long", "dossier": "test-a1-3", "date": "2026-10-07",
        "murs": murs,
        "chambres_froides": [{"id": "CF1", "regime": "positif", "polygone": [[1, 1], [5, 1], [5, 5], [1, 5]],
                              "porte": {"position": [5, 3], "largeur": 0.9, "orientation": 90}}],
        "portes": [
            {"id": "D1", "position": [2.0, 10.1], "largeur": 0.9, "orientation": 0, "dans": "M5"},
            {"id": "D2", "position": [5.0, 10.0], "largeur": 0.9, "orientation": 180, "dans": "M5"},
            {"id": "D3", "position": [7.0, 10.1], "largeur": 0.9, "orientation": 0, "sens": "droite", "dans": "M5"},
            {"id": "D4", "position": [9.0, 10.0], "largeur": 0.9, "orientation": 180, "sens": "droite", "dans": "M5"},
            {"id": "D5", "position": [0.2, 15.0], "largeur": 0.9, "orientation": 270, "dans": "M4"},
            {"id": "D6", "position": [0.2, 22.0], "largeur": 0.9, "orientation": 270, "sens": "droite", "dans": "M4"},
            {"id": "D7", "position": [11.8, 5.0], "largeur": 0.9, "orientation": 90, "dans": "M2"},
            {"id": "D8", "position": [11.8, 25.0], "largeur": 0.9, "orientation": 90, "sens": "droite", "dans": "M2"},
        ],
        "fenetres": [{"id": "F1", "position": [6.0, 0.1], "largeur": 2.0, "dans": "M1"},
                     {"id": "F2", "position": [11.9, 14.0], "largeur": 1.5, "orientation": 90, "dans": "M2"},
                     {"id": "F3", "position": [0.1, 5.0], "largeur": 1.0, "orientation": 270, "dans": "M4"}],
        "equipements": [
            {"id": "EV1", "type": "evaporateur", "position": [3, 2], "rotation": 45, "chambre": "CF1"},
            {"id": "CP1", "type": "centrale", "position": [6, -1.2], "rotation": 180},
            {"id": "SP1", "type": "split", "position": [11.6, 17], "rotation": 270},
            {"id": "MS1", "type": "moteur", "position": [12.6, 17], "rotation": 90},
            {"id": "TD", "type": "tableau", "position": [0.35, 27], "rotation": 90},
        ],
        "cotes": [
            {"id": "C1", "de": [0, 30], "a": [12, 30], "valeur": 12.0, "cote": "bas", "decalage": 0.8},
            {"id": "C2", "de": [0, 0], "a": [0, 30], "valeur": 30.0, "cote": "gauche", "decalage": 0.8},
            {"id": "C3", "de": [2, 21], "a": [6, 24], "valeur": 5.0, "cote": "haut", "decalage": 0.5},
        ],
        "lignes": [
            {"id": "LA1", "type": "aspiration", "de": "EV1", "a": "CP1", "points": [[3, 2], [3, 0.6], [6, 0.6], [6, -0.8]]},
            {"id": "LCG1", "type": "clim_gaz", "de": "SP1", "a": "MS1", "points": [[11.75, 17.0], [12.425, 17.0]]},
            {"id": "LCL1", "type": "clim_liquide", "de": "SP1", "a": "MS1",
             "points": [[11.75, 17.2], [12.1, 17.2], [12.1, 17.3], [12.425, 17.3]]},
            {"id": "LE1", "type": "cable", "de": "MS1", "a": "TD", "repere": "C1",
             "points": [[12.6, 17.45], [12.6, 28.5], [0.6, 28.5], [0.6, 27.0], [0.45, 27.0]]},
        ],
    }


SYNTHESES = {"chambre_seule": (plan_chambre_seule, 50, "paysage"),
             "entrepot": (plan_entrepot, 200, "paysage"),
             "portrait": (plan_portrait, 150, "portrait")}


def _generer(plan: mod.Plan, dossier: Path, nom: str = "plan.drawio", tableaux=None):
    ech = choisir_echelle(plan.bbox(), plan.page)
    chemin = drawio.ecrire(plan, ech, dossier / nom, tableaux)
    return ech, chemin, drawio.lire(chemin)


class _AvecDossier(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dossier = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class TestAllerRetourBoucherie(_AvecDossier):
    def setUp(self):
        super().setUp()
        self.plan = mod.charger(BOUCHERIE)
        self.ech, self.chemin, self.lec = _generer(self.plan, self.dossier)

    def test_modele_valide_et_echelle(self):
        self.assertEqual(self.plan.valider(), [])
        self.assertEqual((self.ech.S, self.ech.orientation), (100, "paysage"))

    def test_lecture_egale_modele_a_1_cm(self):
        self.assertEqual(drawio.comparer(self.plan, self.lec, TOL), [])

    def test_controle_independant_des_points(self):
        # Sans passer par comparer() : équipements, lignes point par point, cotes.
        for q in self.plan.equipements:
            e = self.lec.elements[q["id"]]
            self.assertLessEqual(geo.distance(e["centre_m"], q["position"]), TOL, q["id"])
            self.assertAlmostEqual(e["dimensions_m"][0], q["dimensions"][0], delta=TOL)
        for l in self.plan.lignes:
            relus = self.lec.elements[l["id"]]["points_m"]
            self.assertEqual(len(relus), len(l["points"]), l["id"])
            for p, q in zip(l["points"], relus):
                self.assertLessEqual(geo.distance(p, q), TOL, l["id"])
            self.assertAlmostEqual(self.lec.elements[l["id"]]["longueur_m"], geo.longueur_polyligne(l["points"]),
                                   delta=TOL)
        for c in self.plan.cotes:
            e = self.lec.elements[c["id"]]
            self.assertAlmostEqual(e["longueur_m"], c["valeur"], delta=TOL)
            self.assertEqual(e["texte"], mod.texte_cote(c["valeur"]))
            self.assertAlmostEqual(e["valeur_m"], c["valeur"], delta=1e-9)

    def test_echelle_relue_depuis_le_cartouche(self):
        self.assertEqual(self.lec.echelle.S, 100)
        self.assertEqual(self.lec.echelle.orientation, "paysage")
        self.assertEqual(self.lec.echelle.origine_px, self.ech.origine_px)
        self.assertEqual(self.lec.elements["cartouche-echelle"]["texte"], "Échelle 1:100")
        self.assertEqual(self.lec.avertissements, [])

    def test_identifiants_du_modele_et_sous_elements(self):
        ids = set(self.lec.elements)
        for col in mod.COLLECTIONS:
            for e in getattr(self.plan, col):
                self.assertIn(e["id"], ids)
        for sous in ("EV1-txt", "EV1-v1", "EV1-v2", "EV1-fl", "CF1-int", "CF1-porte", "CF1-porte-ouv", "CF1-txt",
                     "D1-ouv", "CT1-a1", "CT1-a2", "LE1-txt", "barre-echelle", "barre-echelle-txt", "regle-controle",
                     "regle-controle-txt", "regle-controle-g1", "cartouche-titre", "cartouche-mention"):
            self.assertIn(sous, ids)
        self.assertNotIn("LE3-txt", ids)            # étiquette vide demandée
        self.assertEqual(self.lec.elements["EV1-txt"]["parent_element"], "EV1")

    def test_identifiants_stables(self):
        _, chemin2, lec2 = _generer(self.plan, self.dossier, "plan-bis.drawio")
        self.assertEqual(self.chemin.read_bytes(), chemin2.read_bytes())
        self.assertEqual(list(self.lec.elements), list(lec2.elements))

    def test_deux_pages(self):
        self.assertEqual([(p["id"], p["nom"]) for p in self.lec.pages], [("plan", "Plan"), ("metre", "Métré")])

    def test_calques_dans_l_ordre(self):
        self.assertEqual(self.lec.calques, self.plan.calques())
        racine = ET.parse(self.chemin).getroot().find("diagram/mxGraphModel/root")
        calques = [c.get("id") for c in racine if c.get("parent") == "0"]
        self.assertEqual(calques, [c for c, _ in self.plan.calques()])

    def test_page_a4(self):
        m = ET.parse(self.chemin).getroot().find("diagram/mxGraphModel")
        self.assertEqual((m.get("pageWidth"), m.get("pageHeight"), m.get("pageScale")), ("1169", "827", "1"))
        self.assertEqual(m.get("gridSize"), "4")
        self.assertEqual(self.lec.page["format"], "A4")

    def test_barre_d_echelle(self):
        self.assertAlmostEqual(self.lec.barre_echelle_px, self.ech.barre_echelle_px, delta=0.01)
        self.assertAlmostEqual(self.lec.barre_echelle_px, 39.37, delta=0.01)
        self.assertEqual(self.lec.elements["barre-echelle-txt"]["texte"], "1 m")
        self.assertIn("la barre doit mesurer 1 cm à la règle", self.lec.elements["cartouche-mention"]["texte"])

    def test_regle_de_controle(self):
        self.assertAlmostEqual(self.lec.regle_controle_px, 100 * PX_PAR_MM, delta=0.01)
        self.assertEqual(self.lec.elements["regle-controle"]["type"], "regle_controle")
        self.assertIn("100 mm", self.lec.elements["regle-controle-txt"]["texte"])

    def test_tout_dans_la_zone_utile(self):
        zx0, zy0, zx1, zy1 = self.ech.zone_utile_px
        for ident, e in self.lec.elements.items():
            if e.get("calque") == "cartouche" or "boite_px" not in e:
                continue
            b = e.get("boite_texte_px") or e["boite_px"]
            for bb in (e["boite_px"], b):
                self.assertTrue(zx0 - 0.01 <= bb[0] and bb[2] <= zx1 + 0.01 and zy0 - 0.01 <= bb[1]
                                and bb[3] <= zy1 + 0.01, f"{ident} sort de la zone utile : {bb}")

    def test_cartouche_dans_sa_bande(self):
        cx0, cy0, cx1, cy1 = self.ech.cartouche_px
        for ident, e in self.lec.elements.items():
            if e.get("calque") == "cartouche" and "boite_px" in e:
                b = e["boite_px"]
                self.assertTrue(cx0 - 0.01 <= b[0] and b[2] <= cx1 + 0.01 and cy0 - 1.01 <= b[1]
                                and b[3] <= cy1 + 0.01, f"{ident} sort du cartouche : {b}")

    def test_xml_bien_forme_sans_doublon(self):
        racine = ET.parse(self.chemin).getroot()
        for d in racine.findall("diagram"):
            ids = [c.get("id") for c in d.iter("mxCell")]
            self.assertEqual(len(ids), len(set(ids)), d.get("name"))
            for c in d.iter("mxCell"):
                if c.get("parent") is not None:
                    self.assertIn(c.get("parent"), ids)
        for c in racine.find("diagram").iter("mxCell"):
            if c.get("edge") == "1":
                self.assertIsNone(c.get("source"))
                self.assertIsNone(c.get("target"))

    def test_geometrie_a_deux_decimales(self):
        texte = self.chemin.read_text(encoding="utf-8")
        for v in re.findall(r'\b(?:x|y|width|height)="([^"]+)"', texte):
            self.assertRegex(v, r"^-?\d+(\.\d{1,2})?$")


class TestSyntheses(_AvecDossier):
    def test_au_moins_trois_plans_synthetiques(self):
        self.assertGreaterEqual(len(SYNTHESES), 3)


def _fabrique_synthese(fabrique, S, orientation):
    def test(self):
        plan = mod.depuis_dict(fabrique())
        self.assertEqual(plan.valider(), [])
        ech, chemin, lec = _generer(plan, self.dossier)
        self.assertEqual((ech.S, ech.orientation), (S, orientation))
        self.assertEqual(drawio.comparer(plan, lec, TOL), [])
        self.assertEqual(lec.calques, plan.calques())
        self.assertEqual(lec.page["format"], "A4")
        self.assertAlmostEqual(lec.barre_echelle_px, ech.barre_echelle_px, delta=0.01)
    return test


for _nom, (_f, _S, _o) in SYNTHESES.items():
    setattr(TestSyntheses, f"test_aller_retour_{_nom}", _fabrique_synthese(_f, _S, _o))


class TestDetails(_AvecDossier):
    def test_portes_huit_configurations(self):
        plan = mod.depuis_dict(plan_portrait())
        _, _, lec = _generer(plan, self.dossier)
        for p in plan.portes:
            e = lec.elements[p["id"]]
            self.assertEqual((e["orientation"], e["sens"]), (p["orientation"], p.get("sens", "gauche")), p["id"])
            self.assertLessEqual(geo.distance(e["position_m"], p["position"]), TOL)
            style = e["style"]["shape"]
            self.assertEqual(style.endswith("doorRight"), p.get("sens") == "droite")

    def test_mur_oblique_et_equipement_a_45(self):
        plan = mod.depuis_dict(plan_portrait())
        _, _, lec = _generer(plan, self.dossier)
        self.assertAlmostEqual(lec.elements["M7"]["longueur_m"], 5.0, delta=TOL)
        self.assertAlmostEqual(lec.elements["EV1"]["rotation"], 45.0, delta=0.01)

    def test_calque_libre_et_croisement(self):
        plan = mod.depuis_dict(plan_chambre_seule())
        ech, chemin, lec = _generer(plan, self.dossier)
        self.assertEqual(lec.elements["LG1"]["calque"], "eau_glacee")
        self.assertIn("shape=link", lec.brut["LG1"]["style_brut"])
        x = lec.elements["X1"]
        self.assertEqual((x["type"], x["calque"]), ("croisement", "croisements"))
        self.assertAlmostEqual(x["diametre_m"], 0.4, delta=TOL)
        self.assertIn("strokeColor=#FF6D00", lec.brut["X1"]["style_brut"])

    def test_soufflage_vers_la_porte_par_defaut(self):
        plan = mod.depuis_dict(plan_chambre_seule())
        self.assertEqual(plan.soufflage(plan.equipement("EV1")), "droite")
        _, _, lec = _generer(plan, self.dossier)
        p = lec.elements["EV1-fl"]["points_m"]
        self.assertGreater(p[1][0], p[0][0])

    def test_tableaux_page_metre(self):
        plan = mod.depuis_dict(plan_chambre_seule())
        tableaux = [("Métré cuivres", "<table><tr><th>Ligne</th><th>Total</th></tr><tr><td>LA1</td><td>7,40 m</td></tr></table>"),
                    ("Croisements", "<p>1 croisement</p>")]
        _, _, lec = _generer(plan, self.dossier, tableaux=tableaux)
        self.assertEqual(lec.tableaux, tableaux)
        _, _, lec2 = _generer(plan, self.dossier, "sans.drawio")
        self.assertEqual(lec2.tableaux, [])
        self.assertIn("metre-vide", [c["id"] for c in lec2.pages[1]["cellules"]])

    def test_phrase_en_tete_de_la_page_metre(self):
        # F1 (2026-10-08) : la phrase des longueurs estimées sous le titre de la page « Métré », avant les tableaux
        plan = mod.depuis_dict(plan_chambre_seule())
        tableaux = [("Métré cuivres", "<table><tr><td>LA1</td><td>7,40</td></tr></table>")]
        ech = choisir_echelle(plan.bbox(), plan.page)
        lec = drawio.lire(drawio.ecrire(plan, ech, self.dossier / "phrase.drawio", tableaux,
                                        entete="Toutes les longueurs sont des estimations « test ».")).pages[1]
        cellules = {c["id"]: c for c in lec["cellules"]}
        self.assertEqual(drawio.texte_brut(cellules[drawio.ID_PHRASE_METRE]["valeur"]),
                         "Toutes les longueurs sont des estimations « test ».")
        self.assertLess(cellules["metre-titre"]["geometrie"]["y"], cellules[drawio.ID_PHRASE_METRE]["geometrie"]["y"])
        self.assertLess(cellules[drawio.ID_PHRASE_METRE]["geometrie"]["y"] + 18,
                        cellules["metre-tableau-1-titre"]["geometrie"]["y"])
        _, _, sans = _generer(plan, self.dossier, "sans-phrase.drawio", tableaux)
        self.assertNotIn(drawio.ID_PHRASE_METRE, [c["id"] for c in sans.pages[1]["cellules"]])

    def test_identifiant_avec_tiret_sans_parent(self):
        # Une ligne importée par importer_drawio (« LE1-nouveau ») reste un élément principal.
        d = plan_chambre_seule()
        d["lignes"][2]["id"] = "LE1-nouveau"
        plan = mod.depuis_dict(d)
        self.assertEqual(plan.valider(), [])
        _, _, lec = _generer(plan, self.dossier)
        self.assertIsNone(lec.elements["LE1-nouveau"]["parent_element"])
        self.assertEqual(lec.elements["LE1-nouveau-txt"]["parent_element"], "LE1-nouveau")
        self.assertEqual(drawio.comparer(plan, lec, TOL), [])

    def test_identifiant_en_double_refuse(self):
        d = plan_chambre_seule()
        d["equipements"][1]["id"] = "EV1"
        with self.assertRaises(drawio.ErreurEcriture):
            _generer(mod.depuis_dict(d), self.dossier)

    def test_fichier_non_drawio(self):
        p = self.dossier / "autre.xml"
        p.write_text("<html><body/></html>", encoding="utf-8")
        with self.assertRaises(drawio.ErreurLecture):
            drawio.lire(p)


class TestRobustesseLecture(_AvecDossier):
    """La lecture doit marcher sur un fichier retouché par draw.io Desktop."""

    def setUp(self):
        super().setUp()
        self.plan = mod.charger(BOUCHERIE)
        self.ech, self.chemin, _ = _generer(self.plan, self.dossier)
        self.arbre = ET.parse(self.chemin)

    def _cellule(self, ident):
        for c in self.arbre.getroot().find("diagram").iter("mxCell"):
            if c.get("id") == ident:
                return c
        raise KeyError(ident)

    def _relire(self):
        p = self.dossier / "modifie.drawio"
        self.arbre.write(p, encoding="utf-8")
        return drawio.lire(p)

    def test_fichier_retouche(self):
        racine = self.arbre.getroot()
        racine.set("agent", "Mozilla/5.0 draw.io/31.7.0")
        racine.set("modified", "2026-10-07T10:00:00.000Z")
        racine.set("version", "31.7.0")
        modele = racine.find("diagram/mxGraphModel")
        modele.set("background", "#ffffff")
        root = modele.find("root")
        for c in list(root):
            attrs = list(c.attrib.items())[::-1]        # attributs réordonnés
            c.attrib.clear()
            for k, v in attrs:
                c.set(k, v)
            style = c.get("style")
            if style:                                     # style enrichi, clés plan2d déplacées en fin
                morceaux = [m for m in style.split(";") if m]
                tags = [m for m in morceaux if m.startswith("plan2d")]
                autres = [m for m in morceaux if not m.startswith("plan2d")]
                c.set("style", ";".join(autres + ["shadow=0", "sketch=0"] + tags) + ";")
        nouvelle = ET.SubElement(root, "mxCell", {"id": "Abc123-4", "value": "note ajoutée à la main",
                                                  "style": "text;html=1;", "vertex": "1", "parent": "cotes"})
        ET.SubElement(nouvelle, "mxGeometry", {"x": "300", "y": "300", "width": "60", "height": "20", "as": "geometry"})
        # EV1 enveloppé dans un <object> (données ajoutées par « Modifier les données »)
        ev1 = self._cellule("EV1")
        index = list(root).index(ev1)
        root.remove(ev1)
        obj = ET.Element("object", {"label": "", "id": "EV1", "fabricant": "à définir"})
        ev1.attrib.pop("id")
        ev1.attrib.pop("value", None)
        obj.append(ev1)
        root.insert(index, obj)
        lec = self._relire()
        self.assertEqual(drawio.comparer(self.plan, lec, TOL), [])
        self.assertEqual(lec.elements["Abc123-4"]["type"], "texte")
        self.assertEqual(lec.brut["EV1"]["attributs"]["fabricant"], "à définir")

    def test_page_compressee(self):
        racine = self.arbre.getroot()
        d = racine.find("diagram")
        modele = d.find("mxGraphModel")
        xml = ET.tostring(modele, encoding="unicode")
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        brut = comp.compress(urllib.parse.quote(xml, safe="~()*!.'").encode("ascii")) + comp.flush()
        d.remove(modele)
        d.text = base64.b64encode(brut).decode("ascii")
        lec = self._relire()
        self.assertEqual(drawio.comparer(self.plan, lec, TOL), [])

    def test_mur_deplace_de_deux_pixels(self):
        g = self._cellule("M5").find("mxGeometry")
        g.set("x", str(float(g.get("x")) + 2))
        ecarts = drawio.comparer(self.plan, self._relire(), TOL)
        self.assertEqual([e["id"] for e in ecarts], ["M5"])

    def test_cote_modifiee(self):
        self._cellule("CT1").set("value", "16,10 m")
        ecarts = drawio.comparer(self.plan, self._relire(), TOL)
        self.assertEqual([(e["id"], e["categorie"]) for e in ecarts], [("CT1", "cote")])
        self.assertIn("16,10 m", ecarts[0]["message"])

    def test_equipement_deplace_a_la_souris(self):
        g = self._cellule("EV1").find("mxGeometry")
        g.set("x", str(float(g.get("x")) + 10 * PX_PAR_MM))   # 10 mm sur le papier = 1 m au 1:100
        lec = self._relire()
        self.assertAlmostEqual(lec.elements["EV1"]["centre_m"][0], 4.2, delta=TOL)
        self.assertEqual([e["id"] for e in drawio.comparer(self.plan, lec, TOL)], ["EV1"])

    def test_arete_raccordee_aux_equipements(self):
        root = self.arbre.getroot().find("diagram/mxGraphModel/root")
        arete = ET.SubElement(root, "mxCell", {"id": "nouvelle-ligne", "value": "", "edge": "1", "parent": "froid_cuivres",
                                               "source": "EV3", "target": "GR1",
                                               "style": "endArrow=none;html=1;strokeColor=#C62828;"})
        ET.SubElement(arete, "mxGeometry", {"relative": "1", "as": "geometry"})
        e = self._relire().elements["nouvelle-ligne"]
        self.assertEqual(e["type"], "ligne")
        self.assertTrue(e.get("deduit"))
        p0, p1 = e["points_m"]
        ev3 = self.plan.equipement("EV3")
        gr1 = self.plan.equipement("GR1")
        self.assertLessEqual(geo.distance_point_polygone(p0, mod.coins_equipement(ev3)), TOL)
        self.assertLessEqual(geo.distance_point_polygone(p1, mod.coins_equipement(gr1)), TOL)
        self.assertGreater(geo.distance(p0, ev3["position"]), 0.2)   # sur le bord, pas au centre

    def test_porte_retournee(self):
        c = self._cellule("D8")
        c.set("style", c.get("style") + "flipH=1;")
        e = self._relire().elements["D8"]
        self.assertEqual(e["sens"], "droite")

    def test_echelle_illisible(self):
        c = self._cellule("cartouche-echelle")
        c.set("style", re.sub(r"plan2dO[xy]=[^;]*;", "", c.get("style")))
        lec = self._relire()
        self.assertIsNone(lec.echelle)
        self.assertTrue(lec.avertissements)
        self.assertEqual(drawio.comparer(self.plan, lec, TOL)[0]["categorie"], "echelle")


if __name__ == "__main__":
    unittest.main()
