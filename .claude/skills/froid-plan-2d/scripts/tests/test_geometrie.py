"""Tests de geometrie.py : polylignes, distances, intersections, polygones, rotations.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -p "test_geometrie.py" -v
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # dossier scripts/
import geometrie as geo  # noqa: E402

L_FORME = [(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)]   # polygone concave en L


class TestPolylignes(unittest.TestCase):
    def test_longueur_ligne_en_l(self):
        self.assertAlmostEqual(geo.longueur_polyligne([(0, 0), (4, 0), (4, 3)]), 7.0)

    def test_longueur_degeneree(self):
        self.assertEqual(geo.longueur_polyligne([(1, 1)]), 0.0)
        self.assertEqual(geo.longueur_polyligne([]), 0.0)

    def test_distance_point_segment(self):
        self.assertAlmostEqual(geo.distance_point_segment((2, 3), (0, 0), (4, 0)), 3.0)
        self.assertAlmostEqual(geo.distance_point_segment((7, 4), (0, 0), (4, 0)), 5.0)   # au-delà du bout
        self.assertAlmostEqual(geo.distance_point_segment((1, 1), (2, 2), (2, 2)), math.sqrt(2))

    def test_distance_point_polyligne(self):
        self.assertAlmostEqual(geo.distance_point_polyligne((5, 1), [(0, 0), (4, 0), (4, 3)]), 1.0)


class TestIntersections(unittest.TestCase):
    def test_croisement_en_x(self):
        p = geo.intersection_segments((0, 0), (4, 4), (0, 4), (4, 0))
        self.assertAlmostEqual(p[0], 2.0)
        self.assertAlmostEqual(p[1], 2.0)

    def test_paralleles_et_colineaires(self):
        self.assertIsNone(geo.intersection_segments((0, 0), (4, 0), (0, 1), (4, 1)))
        self.assertIsNone(geo.intersection_segments((0, 0), (4, 0), (2, 0), (6, 0)))

    def test_sans_contact(self):
        self.assertIsNone(geo.intersection_segments((0, 0), (1, 0), (2, -1), (2, 1)))

    def test_contact_en_bout_non_compte(self):
        # Un « T » (bout d'un segment sur le milieu de l'autre) n'est pas un croisement propre.
        self.assertIsNone(geo.intersection_segments((0, 0), (4, 0), (2, 0), (2, 3)))
        self.assertIsNone(geo.intersection_segments((0, 0), (4, 0), (4, 0), (4, 3)))

    def test_tolerance_d_extremite(self):
        # Croisement à 3 cm du bout d'un segment : écarté avec 5 cm de tolérance, gardé avec 1 cm.
        a, b, c, d = (0, 0), (4, 0), (0.03, -1), (0.03, 1)
        self.assertIsNone(geo.intersection_segments(a, b, c, d, tolerance_extremite=0.05))
        self.assertIsNotNone(geo.intersection_segments(a, b, c, d, tolerance_extremite=0.01))


class TestPolygones(unittest.TestCase):
    def test_point_dans_polygone_concave(self):
        self.assertTrue(geo.point_dans_polygone((1, 3), L_FORME))
        self.assertFalse(geo.point_dans_polygone((3, 3), L_FORME))   # dans l'encoche du L
        self.assertFalse(geo.point_dans_polygone((-1, 1), L_FORME))

    def test_point_sur_le_bord(self):
        self.assertTrue(geo.point_dans_polygone((4, 1), L_FORME, bord=True))
        self.assertFalse(geo.point_dans_polygone((4, 1), L_FORME, bord=False))

    def test_distance_point_polygone(self):
        self.assertEqual(geo.distance_point_polygone((1, 1), L_FORME), 0.0)
        self.assertAlmostEqual(geo.distance_point_polygone((3, 3), L_FORME), 1.0)

    def test_surface_et_centroide(self):
        self.assertAlmostEqual(geo.surface_polygone(L_FORME), 12.0)
        cx, cy = geo.centroide_polygone([(0, 0), (4, 0), (4, 2), (0, 2)])
        self.assertAlmostEqual(cx, 2.0)
        self.assertAlmostEqual(cy, 1.0)

    def test_rectangle_aligne(self):
        self.assertTrue(geo.est_rectangle_aligne([(0, 0), (4, 0), (4, 2), (0, 2)]))
        self.assertFalse(geo.est_rectangle_aligne(L_FORME))
        self.assertFalse(geo.est_rectangle_aligne([(0, 0), (4, 1), (4, 3), (0, 2)]))

    def test_boites(self):
        self.assertEqual(geo.boite_englobante([(1, 5), (-2, 3), (4, -1)]), (-2, -1, 4, 5))
        with self.assertRaises(ValueError):
            geo.boite_englobante([])
        self.assertEqual(geo.union_boites([(0, 0, 1, 1), (2, -1, 3, 0.5)]), (0, -1, 3, 1))
        self.assertTrue(geo.boites_se_chevauchent((0, 0, 2, 2), (1, 1, 3, 3)))
        self.assertFalse(geo.boites_se_chevauchent((0, 0, 1, 1), (1, 0, 2, 1)))   # simple contact


class TestRotations(unittest.TestCase):
    def test_sens_draw_io(self):
        # Rotation de 90 : la droite devient le bas (sens horaire à l'écran, y vers le bas).
        self.assertEqual(geo.rotation_vecteur((1, 0), 90), (0, 1))
        self.assertEqual(geo.rotation_vecteur((1, 0), 270), (0, -1))
        self.assertEqual(geo.rotation_vecteur((0, 1), 180), (0, -1))

    def test_rectangle_tourne_de_90(self):
        coins = geo.rotation_rectangle((5, 5), (4, 2), 90)
        self.assertEqual(geo.boite_englobante(coins), (4, 3, 6, 7))

    def test_rectangle_tourne_de_45(self):
        coins = geo.rotation_rectangle((0, 0), (2, 2), 45)
        bx = geo.boite_englobante(coins)
        self.assertAlmostEqual(bx[2], math.sqrt(2))
        self.assertAlmostEqual(bx[3], math.sqrt(2))

    def test_rotation_point_et_angles(self):
        p = geo.rotation_point((2, 1), (1, 1), 90)
        self.assertAlmostEqual(p[0], 1.0)
        self.assertAlmostEqual(p[1], 2.0)
        self.assertAlmostEqual(geo.angle_deg((0, 0), (0, 1)), 90.0)
        self.assertAlmostEqual(geo.normaliser_angle(-90), 270.0)
        self.assertAlmostEqual(geo.normaliser_angle(720), 0.0)


if __name__ == "__main__":
    unittest.main()
