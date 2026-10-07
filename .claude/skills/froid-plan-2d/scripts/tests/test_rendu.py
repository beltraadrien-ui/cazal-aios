"""Tests de rendu.py : recherche des outils, mesure PyMuPDF de la règle de contrôle et des rectangles, page HTML
du viewer (voie de secours), calibrage réel par draw.io Desktop (sauté s'il est absent) et par Edge (sauté si
Edge ou internet manque).

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -p "test_rendu.py" -v
Données génériques (boucherie test fictive), aucune donnée client.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import drawio  # noqa: E402
import rendu  # noqa: E402
import outils_tests_plan as ot  # noqa: E402
from echelle import PT_PAR_MM  # noqa: E402

DRAWIO = rendu.trouver_drawio()
EDGE = rendu.trouver_edge()


def internet() -> bool:
    try:
        requete = urllib.request.Request(rendu.VIEWER_EN_LIGNE, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-99"})
        with urllib.request.urlopen(requete, timeout=8) as r:
            return bool(r.read(100))
    except Exception:  # noqa: BLE001
        return False


class TestOutils(unittest.TestCase):
    def test_regle_exacte_en_points(self):
        self.assertAlmostEqual(rendu.REGLE_PT, 100.0 * 72.0 / 25.4, places=6)
        self.assertAlmostEqual(rendu.PT_PAR_PX, 0.72)

    def test_trouver_drawio_absent_impose(self):
        with mock.patch.dict(os.environ, {"FROID_PLAN_DRAWIO": "aucun"}):
            self.assertIsNone(rendu.trouver_drawio())

    def test_trouver_drawio_chemin_impose(self):
        with mock.patch.dict(os.environ, {"FROID_PLAN_DRAWIO": sys.executable}):
            self.assertEqual(rendu.trouver_drawio(), Path(sys.executable))

    def test_couleur_rgb(self):
        self.assertEqual(rendu.couleur_rgb("#FF0000"), (1.0, 0.0, 0.0))
        self.assertAlmostEqual(rendu.couleur_rgb("#424242")[0], 0x42 / 255)
        self.assertIsNone(rendu.couleur_rgb("rouge"))

    def test_chaine_powershell_apostrophes(self):
        self.assertEqual(rendu._ps("C:\\l'atelier\\a.pdf"), "'C:\\l''atelier\\a.pdf'")


class TestMesure(unittest.TestCase):
    """Mesures sur des PDF fabriqués avec PyMuPDF (dimensions connues)."""

    def page(self, rectangles):
        doc = pymupdf.open()
        p = doc.new_page(width=841.92, height=594.96)
        for r, fill in rectangles:
            p.draw_rect(pymupdf.Rect(*r), color=None, fill=fill)
        return doc, p

    def test_regle_mesuree(self):
        doc, p = self.page([((34.0, 550.0, 34.0 + 283.4646, 551.44), (0, 0, 0))])
        r = rendu.mesurer_regle(p)
        self.assertAlmostEqual(r["l"], 283.4646, places=3)
        doc.close()

    def test_regle_absente(self):
        doc, p = self.page([((34.0, 550.0, 200.0, 551.44), (0, 0, 0)), ((10, 10, 400, 12), (0.5, 0.5, 0.5))])
        self.assertIsNone(rendu.mesurer_regle(p))
        doc.close()

    def test_regle_departagee_par_la_position(self):
        # deux traits noirs plausibles : celui attendu à l'emplacement de la cellule l'emporte
        doc, p = self.page([((34.0, 550.0, 34.0 + 280.0, 551.4), (0, 0, 0)),
                            ((34.0, 100.0, 34.0 + 283.46, 101.4), (0, 0, 0))])
        boite = (34.0 / 0.72, 550.0 / 0.72, 393.7, 2.0)
        self.assertAlmostEqual(rendu.mesurer_regle(p, boite)["l"], 280.0, places=3)
        self.assertAlmostEqual(rendu.mesurer_regle(p)["l"], 283.46, places=3)
        doc.close()

    def test_transformation_et_rectangle(self):
        k = 0.718236
        regle_px = (47.24, 764.96, 393.7, 2.0)
        mur_px = (240.0, 180.0, 630.0, 7.87)
        doc, p = self.page([((0.36 + 47.24 * k, 764.96 * k, 0.36 + (47.24 + 393.7) * k, 766.96 * k), (0, 0, 0)),
                            ((0.36 + 240 * k, 180 * k, 0.36 + 870 * k, (180 + 7.87) * k), (0x42 / 255,) * 3)])
        rects = rendu.rectangles_pleins(p)
        regle = rendu.mesurer_regle(p, regle_px, rects)
        transfo = rendu.transformation(regle, regle_px)
        self.assertAlmostEqual(transfo[0], k, places=5)
        r = rendu.chercher_rectangle(rects, mur_px, transfo, rendu.couleur_rgb("#424242"))
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r["l"], 630.0 * k, places=2)
        self.assertIsNone(rendu.chercher_rectangle(rects, mur_px, transfo, rendu.couleur_rgb("#757575")))
        doc.close()

    def test_rasteriser_200_dpi(self):
        with tempfile.TemporaryDirectory() as t:
            pdf, png = Path(t) / "a.pdf", Path(t) / "a.png"
            doc = pymupdf.open()
            doc.new_page(width=841.92, height=594.96)
            doc.save(pdf)
            doc.close()
            w, h = rendu.rasteriser(pdf, png)
            self.assertTrue(png.is_file())
            self.assertLessEqual(abs(w - 2338), 2)
            self.assertLessEqual(abs(h - 1654), 2)


class TestSurPlanGenere(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dossier = ot.dossier_boucherie(Path(cls.tmp.name), pdf_fabrique=False)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pages_attendues(self):
        L = drawio.lire(self.dossier / "plan.drawio")
        n = rendu.pages_attendues(L)
        self.assertGreaterEqual(n, 2)                  # le plan + au moins une feuille de métré

    def test_page_html_viewer(self):
        html = rendu.page_html_viewer(self.dossier / "plan.drawio", Path(self.tmp.name) / "v.html", 1.0,
                                      "viewer.js").read_text(encoding="utf-8")
        self.assertIn("size: 297mm 210mm; margin: 0", html)
        self.assertIn("scale(0.960000)", html)
        self.assertIn("__page__", html)
        self.assertIn("&quot;border&quot;: 0", html)
        self.assertNotIn("toolbar", html)                 # la clé toolbar décale le dessin de 26 px (R1)
        self.assertIn('src="viewer.js"', html)

    def test_rendre_voie_drawio_imposee_absente(self):
        with mock.patch.dict(os.environ, {"FROID_PLAN_DRAWIO": "aucun"}):
            with self.assertRaises(rendu.ErreurRendu):
                rendu.rendre(self.dossier, voie="drawio")

    def test_rendre_sans_drawio(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(rendu.ErreurRendu):
                rendu.rendre(t)

    def test_rendre_rien_demande(self):
        r = rendu.rendre(self.dossier, pdf=False, png=False)
        self.assertIsNone(r["pdf"])
        self.assertIsNone(r["voie"])


@unittest.skipIf(DRAWIO is None, "draw.io Desktop absent de ce PC : rendu réel non testé")
class TestRenduDrawio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dossier = ot.dossier_boucherie(Path(cls.tmp.name), pdf_fabrique=False)
        cls.r1 = rendu.rendre(cls.dossier, voie="drawio")
        cls.r2 = rendu.rendre(cls.dossier, voie="drawio")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pdf_a4_et_regle_a_0_3_pt(self):
        with pymupdf.open(self.r1["pdf"]) as d:
            p = d[0]
            self.assertLessEqual(abs(p.rect.width - 841.89), 1.0)
            self.assertLessEqual(abs(p.rect.height - 595.28), 1.0)
            L = drawio.lire(self.dossier / "plan.drawio")
            g = L.brut["regle-controle"]["geometrie"]
            regle = rendu.mesurer_regle(p, (g["x"], g["y"], g["width"], g["height"]))
        self.assertLessEqual(abs(regle["l"] - rendu.REGLE_PT), 0.3)
        self.assertLess(abs(self.r1["ecart_pct"]), 0.05)

    def test_facteur_corrige_la_reduction_de_draw_io(self):
        # draw.io sort son PDF ~0,245 % trop petit (R1) : le facteur calibré vaut ~1,0025
        self.assertGreater(self.r1["facteur_s"], 1.0015)
        self.assertLess(self.r1["facteur_s"], 1.0035)

    def test_memoire_rendu_json_reutilisee(self):
        memoire = json.loads((self.dossier / "rendu.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(memoire["facteurs"]["drawio"]["A4-paysage"], self.r2["facteur_s"], places=5)
        self.assertEqual(self.r2["essais"], 1)            # facteur mémorisé : un seul export, revérifié

    def test_png_dimensions(self):
        self.assertTrue(self.r1["png"].is_file())
        w, h = self.r1["png_px"]
        self.assertLessEqual(abs(w - 1169 * 2), 2)
        self.assertLessEqual(abs(h - 827 * 2), 2)

    def test_pdf_toutes_pages(self):
        self.assertEqual(self.r1["pages"], self.r1["pages_attendues"])
        self.assertEqual(self.r1["avertissements"], [])

    def test_barre_et_murs_a_l_echelle(self):
        L = drawio.lire(self.dossier / "plan.drawio")
        with pymupdf.open(self.r1["pdf"]) as d:
            rects = rendu.rectangles_pleins(d[0])
            g = L.brut["regle-controle"]["geometrie"]
            boite = (g["x"], g["y"], g["width"], g["height"])
            transfo = rendu.transformation(rendu.mesurer_regle(d[0], boite, rects), boite)
            gm = L.brut["M1"]["geometrie"]
            r = rendu.chercher_rectangle(rects, (gm["x"], gm["y"], gm["width"], gm["height"]), transfo,
                                         rendu.couleur_rgb("#424242"))
        self.assertAlmostEqual(max(r["l"], r["h"]) / PT_PAR_MM, 160.0, delta=1.0 / PT_PAR_MM)   # 16 m au 1:100


@unittest.skipIf(EDGE is None or not internet(), "Edge absent ou viewer diagrams.net injoignable : voie de secours non testée")
class TestRenduEdge(unittest.TestCase):
    def test_voie_de_secours_a_l_echelle(self):
        with tempfile.TemporaryDirectory() as t:
            dossier = ot.dossier_boucherie(Path(t), pdf_fabrique=False)
            r = rendu.rendre(dossier, voie="edge")
            self.assertEqual(r["voie"], "edge")
            self.assertEqual(r["pages"], 1)
            self.assertLessEqual(abs(r["regle_pt"] - rendu.REGLE_PT), 0.3)
            self.assertTrue(any("secours" in a for a in r["avertissements"]))
            self.assertFalse((dossier / "plan.rendu-viewer.html").exists())


if __name__ == "__main__":
    unittest.main()
