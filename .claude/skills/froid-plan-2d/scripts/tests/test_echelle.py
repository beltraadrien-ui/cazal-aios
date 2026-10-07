"""Tests de echelle.py : px_par_m, choix de l'échelle et de l'orientation, conversions, barre, règle.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -p "test_echelle.py" -v
Bibliothèque standard uniquement (unittest ; pytest les collecte aussi). Données génériques, aucune donnée client.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # dossier scripts/
from echelle import (ECHELLES, PAGES_PX, PX_PAR_MM, Echelle, ErreurEchelle, barre_echelle_m,  # noqa: E402
                     capacite_m, choisir_echelle, px_par_m)

# (largeur m, hauteur m) → (S attendu, orientation attendue). Zone de dessin A4 : 249 × 140 mm en paysage,
# 162 × 227 mm en portrait (marges 10 mm, cartouche 22 mm, réserve 14 mm).
BATIMENTS = {
    "3x4_chambre": ((3, 4), (50, "paysage")),
    "5x10_local_etroit": ((5, 10), (50, "portrait")),
    "12x8_superette": ((12, 8), (75, "paysage")),          # 1:100 avait été annoncé « à titre indicatif »
    "8x12_meme_en_long": ((8, 12), (75, "portrait")),
    "boucherie_test": ((18.7, 13.62), (100, "paysage")),
    "40x25_entrepot": ((40, 25), (200, "paysage")),
    "60x20_hall": ((60, 20), (250, "paysage")),
    "20x60_hall_en_long": ((20, 60), (300, "portrait")),
    "100x60_plateforme": ((100, 60), (500, "paysage")),
    "240x130_site": ((240, 130), (1000, "paysage")),
}


class TestPxParM(unittest.TestCase):
    def test_constante_px_par_mm(self):
        self.assertAlmostEqual(PX_PAR_MM, 3.937007874, places=9)

    def test_pages_a4(self):
        self.assertEqual(PAGES_PX["A4"]["portrait"], (827, 1169))
        self.assertEqual(PAGES_PX["A4"]["paysage"], (1169, 827))

    def test_valeurs_du_plan(self):
        self.assertAlmostEqual(px_par_m(100), 39.37007874, places=6)
        self.assertAlmostEqual(px_par_m(50), 78.74015748, places=6)
        self.assertAlmostEqual(px_par_m(200), 19.68503937, places=6)


def _fabrique_px_par_m(S):
    def test(self):
        e = Echelle(S)
        self.assertAlmostEqual(e.px_par_m, 1000 * PX_PAR_MM / S, places=9)
        # 1 m du modèle mesure 1000/S mm sur le papier
        self.assertAlmostEqual(e.longueur_px(1.0) / PX_PAR_MM, 1000.0 / S, places=9)
    return test


for _S in ECHELLES:
    setattr(TestPxParM, f"test_px_par_m_1_{_S}", _fabrique_px_par_m(_S))


class TestChoix(unittest.TestCase):
    def test_echelle_minimale_et_orientation(self):
        # Contrôle croisé : aucune échelle plus petite ne tient, quelle que soit l'orientation.
        for nom, ((w, h), (S, o)) in BATIMENTS.items():
            with self.subTest(nom):
                e = choisir_echelle((0, 0, w, h), {"orientation": "auto"})
                for s in ECHELLES:
                    if s >= e.S:
                        break
                    for orient in ("paysage", "portrait"):
                        cw, ch = capacite_m(s, orient)
                        self.assertFalse(w <= cw and h <= ch, f"{nom} tiendrait au 1:{s} {orient}")

    def test_dessin_centre_dans_la_zone(self):
        bbox = (-0.7, -2.02, 18.0, 11.6)
        e = choisir_echelle(bbox, {})
        self.assertTrue(e.tient(bbox))
        x0, y0, x1, y1 = e.boite_px(bbox)
        zx0, zy0, zx1, zy1 = e.zone_dessin_px
        self.assertAlmostEqual((x0 + x1) / 2, (zx0 + zx1) / 2, delta=0.02)
        self.assertAlmostEqual((y0 + y1) / 2, (zy0 + zy1) / 2, delta=0.02)

    def test_echelle_imposee_qui_tient(self):
        e = choisir_echelle((0, 0, 12, 8), {"echelle": 100})
        self.assertEqual((e.S, e.orientation), (100, "paysage"))

    def test_echelle_imposee_impossible(self):
        with self.assertRaises(ErreurEchelle) as ctx:
            choisir_echelle((0, 0, 40, 25), {"echelle": 100})
        self.assertIn("1:200", str(ctx.exception))     # l'échelle minimale possible est proposée
        self.assertIn("ne tient pas", str(ctx.exception))

    def test_echelle_non_normalisee(self):
        with self.assertRaises(ErreurEchelle):
            choisir_echelle((0, 0, 3, 4), {"echelle": 130})

    def test_orientation_imposee(self):
        e = choisir_echelle((0, 0, 12, 8), {"orientation": "portrait"})
        self.assertEqual((e.S, e.orientation), (75, "portrait"))

    def test_orientation_inconnue(self):
        with self.assertRaises(ErreurEchelle):
            choisir_echelle((0, 0, 3, 4), {"orientation": "diagonale"})

    def test_trop_grand_pour_un_a4(self):
        with self.assertRaises(ErreurEchelle):
            choisir_echelle((0, 0, 300, 300), {})

    def test_egalite_donne_paysage(self):
        self.assertEqual(choisir_echelle((0, 0, 3, 4), {}).orientation, "paysage")


def _fabrique_choix(nom, w, h, S, o):
    def test(self):
        e = choisir_echelle((0, 0, w, h), {"format": "A4", "orientation": "auto", "echelle": None})
        self.assertEqual((e.S, e.orientation), (S, o), nom)
        self.assertTrue(e.tient((0, 0, w, h)))
    return test


for _nom, ((_w, _h), (_S, _o)) in BATIMENTS.items():
    setattr(TestChoix, f"test_choix_{_nom}", _fabrique_choix(_nom, _w, _h, _S, _o))


class TestConversions(unittest.TestCase):
    def test_aller_retour_au_millimetre(self):
        for S in ECHELLES:
            e = Echelle(S, "paysage", origine_px=(123.45, 67.89))
            for x, y in ((0, 0), (12.5, 8.0), (-3.2, -1.5), (14.8, 9.25), (7.123, 4.567)):
                px = e.m_vers_px(x, y)
                xm, ym = e.px_vers_m(*px)
                self.assertLess(abs(xm - x), 0.001)
                self.assertLess(abs(ym - y), 0.001)

    def test_aller_retour_apres_arrondi_xml(self):
        # La géométrie est écrite à 0,01 px : au 1:1000 l'erreur reste sous 1,3 mm.
        e = Echelle(1000, "paysage")
        for x in (0.0, 1.234, 99.999):
            px = round(e.m_vers_px(x, 0)[0], 2)
            self.assertLess(abs(e.px_vers_m(px, e.origine_px[1])[0] - x), 0.0013)

    def test_origine_mm(self):
        e = Echelle(100, "portrait", origine_px=(100.0, 200.0))
        self.assertAlmostEqual(e.origine_mm[0], 100 / PX_PAR_MM, places=9)
        self.assertAlmostEqual(e.origine_mm[1], 200 / PX_PAR_MM, places=9)

    def test_origine_arrondie_au_centieme(self):
        e = Echelle(100, "paysage", origine_px=(10.123456, 20.987654))
        self.assertEqual(e.origine_px, (10.12, 20.99))

    def test_zone_utile_et_cartouche(self):
        e = Echelle(100, "paysage")
        self.assertEqual(e.zone_utile_mm, (10.0, 10.0, 287.0, 178.0))
        self.assertEqual(e.cartouche_mm, (10.0, 178.0, 287.0, 200.0))
        p = Echelle(100, "portrait")
        self.assertEqual(p.zone_utile_mm, (10.0, 10.0, 200.0, 265.0))
        # R1 : rien à moins de 20 px du bord (la marge de 10 mm = 39,4 px)
        self.assertGreater(e.zone_utile_px[0], 20.0)

    def test_grille_dix_centimetres(self):
        self.assertEqual(Echelle(100).grille_px, 4)
        self.assertEqual(Echelle(50).grille_px, 8)
        self.assertEqual(Echelle(1000).grille_px, 1)


class TestBarreEtRegle(unittest.TestCase):
    def test_longueur_nominale(self):
        self.assertEqual([barre_echelle_m(S) for S in (50, 100, 125, 200, 250, 1000)], [1, 1, 2, 2, 5, 5])

    def test_barre_en_px_et_sur_papier(self):
        for S in ECHELLES:
            e = Echelle(S)
            self.assertAlmostEqual(e.barre_echelle_px, e.barre_echelle_m * e.px_par_m, places=9)
            self.assertAlmostEqual(e.barre_echelle_px / PX_PAR_MM, e.barre_echelle_m * 1000 / S, places=9)
        self.assertAlmostEqual(Echelle(100).barre_echelle_mm, 10.0)

    def test_regle_de_controle_100_mm(self):
        self.assertAlmostEqual(Echelle(250).regle_controle_px, 393.70, delta=0.01)
        self.assertAlmostEqual(Echelle(50).regle_controle_px, 100 * PX_PAR_MM, places=9)

    def test_echelle_invalide(self):
        for S in (0, -100, float("nan")):
            with self.assertRaises(ErreurEchelle):
                Echelle(S)
        with self.assertRaises(ErreurEchelle):
            Echelle(100, "oblique")


if __name__ == "__main__":
    unittest.main()
