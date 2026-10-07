"""Tests de importer_drawio.py : rien à importer, équipement déplacé, rotation, tracé modifié, coude ajouté,
nouvelle ligne (type déduit, de/a par proximité, question si extrémité libre), dessin déplacé d'un bloc (recalage),
mur / porte / fenêtre, élément supprimé, aperçu sans écriture, sauvegarde préalable, aller-retour
importer → generer → verifier à 0 erreur.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -p "test_importer_drawio.py" -v
Données génériques (boucherie test fictive), aucune donnée client.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import drawio  # noqa: E402
import generer  # noqa: E402
import importer_drawio as imp  # noqa: E402
import modele as mod  # noqa: E402
import outils_tests_plan as ot  # noqa: E402
import verifier_plan as vp  # noqa: E402

PX_20CM = 7.874        # 0,20 m au 1:100 (39,37 px/m)


def lire_plan(d: Path) -> dict:
    return json.loads((d / "plan.json").read_text(encoding="utf-8"))


def par_id(donnees: dict, collection: str) -> dict:
    return {e["id"]: e for e in donnees.get(collection) or []}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.racine = Path(cls.tmp.name)
        cls.base = ot.dossier_boucherie(cls.racine, "base", pdf_fabrique=False)
        cls.n = 0

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def copie(self) -> Path:
        type(self).n += 1
        return ot.copier(self.base, self.racine, f"copie-{self.n}")

    def px(self, d: Path, x: float, y: float) -> tuple[float, float]:
        return drawio.lire(d / "plan.drawio").echelle.m_vers_px(x, y)


class TestImport(Base):
    def test_rien_a_importer(self):
        d = self.copie()
        avant = (d / "plan.json").read_bytes()
        r = imp.importer(d)
        self.assertEqual(r["changements"], [])
        self.assertFalse(r["ecrit"])
        self.assertEqual((d / "plan.json").read_bytes(), avant)
        self.assertEqual(list((d / "versions").glob("plan.json.avant-import-*")), [])

    def test_equipement_deplace_et_sauvegarde(self):
        d = self.copie()
        avant = (d / "plan.json").read_bytes()
        ot.deplacer_sommet(d, "EV2", dx=PX_20CM)
        r = imp.importer(d)
        self.assertTrue(r["ecrit"])
        ev2 = par_id(lire_plan(d), "equipements")["EV2"]
        self.assertAlmostEqual(ev2["position"][0], 6.55, delta=0.002)
        self.assertAlmostEqual(ev2["position"][1], 0.78, delta=0.002)
        self.assertTrue(r["sauvegarde"].name.startswith("plan.json.avant-import-"))
        self.assertEqual(r["sauvegarde"].read_bytes(), avant)
        # le reste est intact
        self.assertEqual(par_id(lire_plan(d), "equipements")["EV1"]["position"], [3.2, 0.8])

    def test_apercu_n_ecrit_rien(self):
        d = self.copie()
        avant = (d / "plan.json").read_bytes()
        ot.deplacer_sommet(d, "EV2", dx=PX_20CM)
        r = imp.importer(d, apercu=True)
        self.assertEqual(len(r["changements"]), 1)
        self.assertFalse(r["ecrit"])
        self.assertEqual((d / "plan.json").read_bytes(), avant)

    def test_rotation(self):
        d = self.copie()
        ot.changer_attribut(d, "GR1", "style", ("plan2d=equipement;", "plan2d=equipement;rotation=90;"))
        imp.importer(d)
        self.assertEqual(par_id(lire_plan(d), "equipements")["GR1"]["rotation"], 90)

    def test_trace_modifie(self):
        d = self.copie()
        avant = par_id(lire_plan(d), "lignes")["LE7"]["points"]
        ot.deplacer_arete(d, "LE7", "points", indice=1, dx=-PX_20CM)
        imp.importer(d)
        apres = par_id(lire_plan(d), "lignes")["LE7"]["points"]
        self.assertEqual(len(apres), 4)
        self.assertAlmostEqual(apres[2][0], 15.16, delta=0.002)
        self.assertEqual([apres[0], apres[1], apres[3]], [avant[0], avant[1], avant[3]])   # points intacts

    def test_coude_ajoute(self):
        d = self.copie()
        x, y = self.px(d, 3.1, -0.5)

        def coude(arbre):
            arr = ot.cellule(arbre, "LE1").find("mxGeometry").find("Array")
            p = arr.makeelement("mxPoint", {"x": f"{x:.2f}", "y": f"{y:.2f}"})
            arr.append(p)
        ot.modifier_xml(d, coude)
        r = imp.importer(d)
        self.assertEqual(len(par_id(lire_plan(d), "lignes")["LE1"]["points"]), 4)
        self.assertIn("LE1 : tracé modifié (3 → 4 points)", r["changements"])

    def test_nouvelle_ligne_liquide(self):
        d = self.copie()
        pts = [self.px(d, *p) for p in ((6.0, 0.56), (6.0, -0.62), (4.9, -0.62), (4.9, -0.85))]
        ot.ajouter_arete(d, "a1b2c3", "froid_cuivres", pts, "endArrow=none;html=1;strokeColor=#C62828;strokeWidth=1.5;")
        r = imp.importer(d)
        l = par_id(lire_plan(d), "lignes")["L-nouveau-1"]
        self.assertEqual((l["type"], l["calque"], l["de"], l["a"]), ("liquide", "froid_cuivres", "EV2", "CP1"))
        self.assertEqual(l["diametre"], "à définir")
        self.assertEqual(l["source"], "drawio")
        self.assertEqual(len(l["points"]), 4)
        self.assertEqual(r["questions"], [])

    def test_nouvelle_ligne_sans_equipement_proche(self):
        d = self.copie()
        pts = [self.px(d, 3.0, 10.2), self.px(d, 8.0, 10.2)]
        ot.ajouter_arete(d, "z9", "electricite", pts, "endArrow=none;html=1;strokeColor=#6A1B9A;strokeWidth=1.5;")
        r = imp.importer(d)
        l = par_id(lire_plan(d), "lignes")["L-nouveau-1"]
        self.assertEqual((l["type"], l["de"], l["a"]), ("cable", None, None))
        self.assertEqual(len(r["questions"]), 2)
        self.assertIn("départ libre", r["questions"][0])

    def test_dessin_deplace_d_un_bloc_recale(self):
        d = self.copie()
        avant = (d / "plan.json").read_bytes()
        ot.decaler_tout(d, 20.0, 10.0)
        r = imp.importer(d)
        self.assertEqual(r["changements"], [])
        self.assertAlmostEqual(r["recalage"][0], 20.0 / 39.37008, delta=0.001)
        self.assertAlmostEqual(r["recalage"][1], 10.0 / 39.37008, delta=0.001)
        self.assertTrue(any("d'un bloc" in a for a in r["avertissements"]))
        self.assertEqual((d / "plan.json").read_bytes(), avant)

    def test_bloc_deplace_puis_equipement_deplace(self):
        d = self.copie()
        ot.decaler_tout(d, 20.0, 10.0)
        ot.deplacer_sommet(d, "EV1", dx=PX_20CM)
        r = imp.importer(d)
        self.assertEqual(len(r["changements"]), 1, r["changements"])
        ev1 = par_id(lire_plan(d), "equipements")["EV1"]
        self.assertAlmostEqual(ev1["position"][0], 3.4, delta=0.002)
        self.assertAlmostEqual(ev1["position"][1], 0.8, delta=0.002)

    def test_mur_modifie_non_reimporte(self):
        d = self.copie()
        ot.deplacer_sommet(d, "M5", dx=4.0)
        r = imp.importer(d)
        self.assertEqual(r["changements"], [])
        self.assertTrue(any("Mur M5" in a and "NON réimporté" in a for a in r["avertissements"]))
        self.assertEqual(par_id(lire_plan(d), "murs")["M5"]["de"], [10.05, 0.2])

    def test_porte_et_fenetre_deplacees(self):
        d = self.copie()
        ot.deplacer_sommet(d, "D3", dx=-PX_20CM)
        ot.deplacer_sommet(d, "F1", dx=PX_20CM)
        imp.importer(d)
        p = lire_plan(d)
        self.assertAlmostEqual(par_id(p, "portes")["D3"]["position"][0], 1.9, delta=0.002)
        self.assertAlmostEqual(par_id(p, "fenetres")["F1"]["position"][0], 3.7, delta=0.002)

    def test_porte_de_chambre_deplacee(self):
        d = self.copie()
        ot.deplacer_sommet(d, "CF1-porte", dx=PX_20CM)
        imp.importer(d)
        self.assertAlmostEqual(par_id(lire_plan(d), "chambres_froides")["CF1"]["porte"]["position"][0], 1.1,
                               delta=0.002)

    def test_ligne_supprimee_avertit_sans_supprimer(self):
        d = self.copie()
        ot.supprimer_cellule(d, "LCO2")
        r = imp.importer(d)
        self.assertIn("LCO2", par_id(lire_plan(d), "lignes"))
        self.assertTrue(any("LCO2 absente du dessin" in a for a in r["avertissements"]))

    def test_aller_retour_generer_verifier(self):
        d = self.copie()
        ot.deplacer_sommet(d, "EV2", dx=PX_20CM)
        imp.importer(d)
        self.assertEqual(generer.generer(d, rendu_pdf=False)["code"], 0)
        r = vp.verifier(d, sans_pdf=True)
        self.assertEqual(r["code"], 0, r["constats"])

    def test_fichier_manquant(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(imp.ErreurImport) as e:
                imp.importer(t)
            self.assertEqual(e.exception.code, 2)

    def test_ligne_de_commande_apercu(self):
        d = self.copie()
        ot.deplacer_sommet(d, "EV2", dx=PX_20CM)
        with contextlib.redirect_stdout(io.StringIO()) as sortie:
            self.assertEqual(imp.main([str(d), "--apercu"]), 0)
        self.assertIn("Aperçu (rien n'est écrit) : 1", sortie.getvalue())


class TestCalqueLibre(unittest.TestCase):
    def test_nouvelle_ligne_dans_un_calque_libre(self):
        donnees = ot.charger_boucherie()
        donnees["calques_libres"] = [{"cle": "eau_chaude", "nom": "Eau chaude", "couleur": "#EF6C00", "trait": "simple"}]
        with tempfile.TemporaryDirectory() as t:
            d = ot.dossier_boucherie(Path(t), donnees=donnees, pdf_fabrique=False)
            L = drawio.lire(d / "plan.drawio")
            pts = [L.echelle.m_vers_px(1.0, 5.0), L.echelle.m_vers_px(4.0, 5.0)]
            ot.ajouter_arete(d, "eau1", "eau_chaude", pts, "endArrow=none;html=1;strokeColor=#EF6C00;")
            imp.importer(d)
            l = par_id(lire_plan(d), "lignes")["L-nouveau-1"]
            self.assertEqual((l["type"], l["calque"]), ("eau_chaude", "eau_chaude"))


class TestDeduireType(unittest.TestCase):
    def setUp(self):
        self.plan = mod.depuis_dict(ot.charger_boucherie())

    def t(self, calque, style, genre=None):
        st, _ = drawio.analyser_style(style)
        return imp.deduire_type({"calque": calque, "style": st, "genre": genre}, self.plan)

    def test_types(self):
        self.assertEqual(self.t("froid_cuivres", "shape=link;strokeColor=#1565C0;")[0], "aspiration")
        self.assertEqual(self.t("froid_cuivres", "dashed=1;strokeColor=#00ACC1;")[0], "condensats")
        self.assertEqual(self.t("electricite", "strokeWidth=4;dashed=1;")[0], "chemin_cables")
        self.assertEqual(self.t("clim_cuivres", "shape=link;")[0], "clim_gaz")
        self.assertEqual(self.t("clim_cuivres", "strokeColor=#2E7D32;")[0], "clim_liquide")
        self.assertEqual(self.t("electricite", "strokeColor=#000000;", genre="cable")[0], "cable")

    def test_type_par_defaut_avec_question(self):
        type_, question = self.t("froid_cuivres", "strokeColor=#000000;")
        self.assertEqual(type_, "aspiration")
        self.assertIn("aspiration, liquide ou condensats", question)

    def test_calque_inconnu(self):
        self.assertEqual(self.t("plan_de_base", "strokeColor=#000000;"), (None, None))


if __name__ == "__main__":
    unittest.main()
