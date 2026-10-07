"""Tests de generer.py sur une copie de la boucherie test : fichiers produits, plan-base.json (contrat du Lot 6),
plan.md (sections, « (hyp.) »), croisements injectés, versions et journal, page « Métré » sans tableau coupé,
modèle invalide (rien n'est écrit), chaîne complète avec draw.io (sautée s'il est absent).

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -p "test_generer.py" -v
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
import croisements as crx  # noqa: E402
import drawio  # noqa: E402
import generer  # noqa: E402
import modele as mod  # noqa: E402
import outils_tests_plan as ot  # noqa: E402
import rendu  # noqa: E402
from echelle import PX_PAR_MM, choisir_echelle  # noqa: E402

SECTIONS = ("## Identité", "## Comment vérifier l'échelle", "## Cotes relevées", "## Hypothèses de hauteur",
            "## Métré", "### Métré par réseau", "### Métré par diamètre", "## Croisements et recouvrements",
            "## Calques", "## Questions ouvertes", "## Journal des versions")


class TestGenererBoucherie(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dossier = Path(cls.tmp.name) / "plan"
        ot.ecrire_plan(cls.dossier, ot.charger_boucherie())
        cls.r = generer.generer(cls.dossier, rendu_pdf=False)
        cls.md = (cls.dossier / "plan.md").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_code_0_et_fichiers(self):
        self.assertEqual(self.r["code"], 0, self.r["erreurs"])
        for nom in ("plan.drawio", "plan.md", "plan.html", "plan-base.json", "journal.md",
                    "versions/plan-v1.drawio", "versions/plan-v1.json"):
            self.assertTrue((self.dossier / nom).is_file(), nom)
        self.assertFalse((self.dossier / "plan.pdf").exists())          # --sans-rendu

    def test_plan_base_contrat_lot6(self):
        base = json.loads((self.dossier / "plan-base.json").read_text(encoding="utf-8"))
        self.assertEqual(set(base), {"S", "orientation", "origine_mm"})
        ech = self.r["echelle"]
        self.assertEqual((base["S"], base["orientation"]), (ech.S, ech.orientation))
        self.assertAlmostEqual(base["origine_mm"][0], ech.origine_mm[0], places=3)
        self.assertAlmostEqual(base["origine_mm"][1], ech.origine_mm[1], places=3)
        # même correspondance que le dessin : (x, y) m → origine_mm + (x, y) × 1000 / S mm = m_vers_px / PX_PAR_MM
        for x, y in ((0, 0), (16, 11), (4.1, -1.2)):
            px = ech.m_vers_px(x, y)
            self.assertAlmostEqual(base["origine_mm"][0] + x * 1000 / base["S"], px[0] / PX_PAR_MM, places=3)
            self.assertAlmostEqual(base["origine_mm"][1] + y * 1000 / base["S"], px[1] / PX_PAR_MM, places=3)

    def test_echelle_lue_dans_le_dessin(self):
        L = drawio.lire(self.dossier / "plan.drawio")
        self.assertEqual(L.echelle.S, 100)
        self.assertEqual(L.echelle.orientation, "paysage")
        self.assertEqual(L.echelle.origine_px, self.r["echelle"].origine_px)

    def test_plan_md_sections(self):
        self.assertTrue(self.md.startswith("<!-- titre: Plan 2D : Boucherie test"))
        for s in SECTIONS:
            self.assertIn(s, self.md, s)
        self.assertIn("**100 mm**", self.md)
        self.assertIn("Imprimer `plan.pdf` **à 100 %**", self.md)
        self.assertIn("1:100", self.md)

    def test_plan_md_cotes_et_questions(self):
        self.assertIn("| C1 | (0,00 ; 11,00) | (16,00 ; 11,00) | 16,00 m | telemetre |", self.md)
        self.assertIn("LCO1 (Condensats) : évacuation libre", self.md)
        self.assertIn("question 13", self.md)

    def test_hypotheses_marquees(self):
        rangs = [l for l in self.md.splitlines() if l.startswith("| Froid") and "| LA1 |" in l]
        self.assertEqual(len(rangs), 1)
        self.assertIn("(hyp.)", rangs[0])
        self.assertIn("1,81 |", rangs[0])                               # longueur en plan : pas une hypothèse

    def test_croisements_injectes_dans_le_dessin(self):
        # C : un cercle par GROUPE de croisements (≤ 0,50 m de proche en proche), repères G1…
        L = drawio.lire(self.dossier / "plan.drawio")
        ellipses = {e["id"]: e for e in L.elements.values() if e["type"] == "croisement"}
        attendus = crx.regrouper(crx.croisements(ot.charger_boucherie()))
        self.assertEqual(len(crx.croisements(ot.charger_boucherie())), 9)
        self.assertEqual(len(ellipses), len(attendus))
        self.assertEqual(len(ellipses), 3)
        for g in attendus:
            self.assertLess(((ellipses[g["id"]]["centre_m"][0] - g["point"][0]) ** 2
                             + (ellipses[g["id"]]["centre_m"][1] - g["point"][1]) ** 2) ** 0.5, 0.01)
        self.assertNotIn("croisements", json.loads((self.dossier / "plan.json").read_text(encoding="utf-8")))

    def test_etiquette_de_groupe_a_cote_du_cercle(self):
        L = drawio.lire(self.dossier / "plan.drawio")
        textes = {e["texte"]: e for e in L.elements.values() if e.get("parent_element") in ("G1", "G2", "G3")}
        self.assertEqual(set(textes), {"X1-X3", "X4-X6", "X7-X9"})
        for t in textes.values():
            cercle = L.elements[t["parent_element"]]
            self.assertEqual(t["calque"], "croisements")
            cx, cy = cercle["centre_px"]
            r = cercle["dimensions_px"][0] / 2
            x0, y0, x1, y1 = t["boite_px"]
            plus_proche = (min(max(cx, x0), x1), min(max(cy, y0), y1))     # point de la boîte le plus proche du centre
            d = ((plus_proche[0] - cx) ** 2 + (plus_proche[1] - cy) ** 2) ** 0.5
            self.assertGreater(d, r, t["texte"])                            # à côté, pas sur le cercle
            self.assertLess(d, r + 50.0, t["texte"])                        # mais tout près

    def test_tableau_croisements_par_croisement_avec_repere(self):
        section = self.md.split("## Croisements et recouvrements", 1)[1].split("## Calques", 1)[0]
        self.assertIn("| N° | Repère | Point (x ; y) | Lignes | Calques |", section)
        rangs = [l for l in section.splitlines() if l.startswith("| X")]
        self.assertEqual(len(rangs), 9)
        self.assertTrue(rangs[0].startswith("| X1 | G1 |"))
        self.assertTrue(rangs[8].startswith("| X9 | G3 |"))
        L = drawio.lire(self.dossier / "plan.drawio")
        html = dict(L.tableaux)[generer.TITRE_TABLEAU_CROISEMENTS]
        self.assertIn("Repère", html)
        self.assertEqual(html.count("<tr>"), 1 + 9)

    def test_page_metre_tableaux(self):
        L = drawio.lire(self.dossier / "plan.drawio")
        titres = [t for t, _ in L.tableaux]
        self.assertEqual(titres, ["Métré par réseau", "Métré par diamètre", "Hauteurs utilisées",
                                  generer.TITRE_TABLEAU_CROISEMENTS])

    def test_page_metre_aucun_tableau_coupe(self):
        L = drawio.lire(self.dossier / "plan.drawio")
        page = next(p for p in L.pages if p["id"] == "metre")
        h = page["hauteur_px"]
        for c in page["cellules"]:
            if c["id"] and c["id"].startswith("metre-tableau-") and not c["id"].endswith("-titre"):
                g = c["geometrie"]
                self.assertEqual(int(g["y"] // h), int((g["y"] + g["height"] - 1e-6) // h), c["id"])

    def test_plan_html_produit(self):
        html = (self.dossier / "plan.html").read_text(encoding="utf-8")
        self.assertIn("Plan 2D : Boucherie test", html)
        self.assertIn('class="hyp"', html)


class TestGenererCas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_deuxieme_generation_version_2_et_journal(self):
        d = self.racine / "plan"
        ot.ecrire_plan(d, ot.charger_boucherie())
        generer.generer(d, rendu_pdf=False)
        r = generer.generer(d, rendu_pdf=False)
        self.assertEqual(r["version"], 2)
        self.assertTrue((d / "versions" / "plan-v2.drawio").is_file())
        journal = [l for l in (d / "journal.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
        self.assertEqual(len(journal), 2)
        self.assertIn("· v2 ·", journal[1])
        self.assertIn(journal[1], (d / "plan.md").read_text(encoding="utf-8"))

    def test_modele_invalide_rien_n_est_ecrit(self):
        donnees = ot.charger_boucherie()
        donnees["cotes"][0]["valeur"] = 16.5                       # cote incohérente avec de/a
        d = self.racine / "plan"
        ot.ecrire_plan(d, donnees)
        r = generer.generer(d, rendu_pdf=False)
        self.assertEqual(r["code"], 1)
        self.assertIn("C1", r["erreurs"][0])
        self.assertFalse((d / "plan.drawio").exists())
        self.assertFalse((d / "versions").exists())

    def test_plan_json_absent(self):
        r = generer.generer(self.racine / "vide", rendu_pdf=False)
        self.assertEqual(r["code"], 1)

    def test_echelle_imposee_impossible(self):
        donnees = ot.charger_boucherie()
        donnees["page"]["echelle"] = 50
        d = self.racine / "plan"
        ot.ecrire_plan(d, donnees)
        r = generer.generer(d, rendu_pdf=False)
        self.assertEqual(r["code"], 1)
        self.assertIn("1:50", r["erreurs"][0])

    def test_hauteurs_validees_sans_hyp(self):
        donnees = ot.charger_boucherie()
        donnees["hauteurs_validees"] = True
        d = self.racine / "plan"
        ot.ecrire_plan(d, donnees)
        generer.generer(d, rendu_pdf=False)
        md = (d / "plan.md").read_text(encoding="utf-8")
        self.assertNotIn("(hyp.)", md.split("## Métré", 1)[1].split("## Croisements", 1)[0])
        self.assertIn("validée", md)
        self.assertNotIn("question 13", md)

    def test_ligne_cli(self):
        d = self.racine / "plan"
        ot.ecrire_plan(d, ot.charger_boucherie())
        with contextlib.redirect_stdout(io.StringIO()) as sortie:
            self.assertEqual(generer.main([str(d), "--sans-rendu"]), 0)
        self.assertIn("Plan v1 : échelle 1:100", sortie.getvalue())
        self.assertTrue((d / "plan.drawio").is_file())

    def test_rendu_impossible_code_1_fichiers_ecrits(self):
        import os
        from unittest import mock
        d = self.racine / "plan"
        ot.ecrire_plan(d, ot.charger_boucherie())
        with mock.patch.dict(os.environ, {"FROID_PLAN_DRAWIO": "aucun"}):
            r = generer.generer(d, voie="drawio")
        self.assertEqual(r["code"], 1)
        self.assertIn("Rendu", r["erreurs"][0])
        self.assertTrue((d / "plan.md").is_file())
        self.assertIn("rendu en échec", (d / "journal.md").read_text(encoding="utf-8"))


@unittest.skipIf(rendu.trouver_drawio() is None, "draw.io Desktop absent : chaîne complète non testée")
class TestChaineComplete(unittest.TestCase):
    def test_generer_avec_rendu(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "plan"
            ot.ecrire_plan(d, ot.charger_boucherie())
            r = generer.generer(d)
            self.assertEqual(r["code"], 0, r["erreurs"])
            self.assertEqual(r["rendu"]["voie"], "drawio")
            self.assertTrue((d / "plan.pdf").is_file() and (d / "plan.png").is_file())
            self.assertIn("règle de 100 mm mesurée dans le PDF : 100,0", (d / "plan.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
