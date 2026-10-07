"""Tests du Lot 6 : lecture des photos de tracés (lire_photo.py) sur photos synthétiques (photo_synthetique.py).

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -p "test_lire_photo.py"
(compatible pytest). Fixture : tests/fixtures/a3-plan.json + a3-plan-base.json (plan fictif, 1:50 paysage).
Règle n° 1 : la longueur lue sur la photo doit être à ≤ 3 % de la longueur tracée.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))   # dossier scripts/
import feuille as fe  # noqa: E402
import lire_photo as lp  # noqa: E402
import photo_synthetique as ps  # noqa: E402

FIXTURES = ICI / "fixtures"
RESEAU = "froid_cuivres"
BASE = json.loads((FIXTURES / "a3-plan-base.json").read_text(encoding="utf-8"))
TOLERANCE_LONGUEUR = 0.03
TOLERANCE_REPROJECTION_MM = 0.5

# graine : (couleur, traits en m, liaisons attendues {de, a} par tronçon (None exclus))
CAS = {
    1: ("rouge", [[(9.4, 1.6), (5.5, 1.6), (5.5, 4.8), (1.5, 4.8)]], [{"EV1", "GR1"}]),
    2: ("rouge", [[(9.4, 4.4), (5.0, 4.4), (5.0, 5.4), (1.5, 5.4), (1.5, 4.8)]], [{"EV2", "GR1"}]),
    3: ("rouge", [[(9.4, 1.6), (10.5, 1.6), (10.5, 4.4), (9.4, 4.4)]], [{"EV1", "EV2"}]),
    4: ("rouge", [[(1.5, 4.8), (1.5, 0.8), (6.0, 0.8), (6.0, 1.6), (9.4, 1.6)]], [{"GR1", "EV1"}]),
    5: ("bleu", [[(9.4, 4.4), (6.0, 4.4), (3.0, 2.6), (1.5, 2.6), (1.5, 4.8)]], [{"EV2", "GR1"}]),
    6: ("bleu", [[(9.4, 1.6), (6.0, 1.6), (6.0, 3.0), (3.5, 3.0), (3.5, 4.8), (1.5, 4.8)]], [{"EV1", "GR1"}]),
    7: ("vert", [[(1.5, 4.8), (1.5, 5.8), (8.0, 5.8), (8.0, 4.4), (9.4, 4.4)]], [{"GR1", "EV2"}]),
    8: ("vert", [[(9.4, 1.6), (4.0, 1.6), (4.0, 4.8), (1.5, 4.8)],
                 [(9.4, 4.4), (3.0, 4.4), (3.0, 5.6), (1.5, 5.6), (1.5, 4.8)]], [{"EV1", "GR1"}, {"EV2", "GR1"}]),
    9: ("rouge", [[(3.0, 1.0), (3.0, 3.5), (5.0, 3.5)]], [set()]),
    10: ("rouge", [[(9.4, 1.6), (6.2, 1.6), (6.2, 2.0), (0.15, 2.0)]], [{"EV1"}]),
}


def en_mm(traits_m):
    return [fe.m_vers_mm(t, BASE).tolist() for t in traits_m]


def longueur(points) -> float:
    p = np.asarray(points, dtype=float)
    return float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum())


_TMP: Path | None = None
_MODELE: Path | None = None
_CACHE: dict = {}


def setUpModule():
    global _TMP, _MODELE
    _TMP = Path(tempfile.mkdtemp(prefix="a3-lire-photo-"))
    _MODELE = _TMP / "modele" / "plan"
    _MODELE.mkdir(parents=True)
    shutil.copy(FIXTURES / "a3-plan.json", _MODELE / "plan.json")
    shutil.copy(FIXTURES / "a3-plan-base.json", _MODELE / "plan-base.json")
    fe.fabriquer_feuille(_MODELE, RESEAU, "aspiration", pdf=False, date="2026-10-07")
    fe.fabriquer_feuille(_MODELE, "electricite", "cable", pdf=False, date="2026-10-07")


def tearDownModule():
    if _TMP is not None:
        shutil.rmtree(_TMP, ignore_errors=True)


def nouveau_dossier(nom: str) -> Path:
    """Copie indépendante du dossier plan (pour les tests qui écrivent dans plan.json)."""
    d = _TMP / nom / "plan"
    shutil.copytree(_MODELE, d)
    return d


def photo(graine: int, couleur: str, traits_m, reseau: str = RESEAU, **options):
    feuille = fe.chemins_feuille(_MODELE, reseau)
    sortie = _TMP / "photos" / f"p-{graine}-{couleur}-{len(_CACHE)}.jpg"
    return ps.fabriquer(feuille["png"], feuille["json"], en_mm(traits_m), graine, couleur=couleur,
                        sortie=sortie, **options)


def resultat_cas(graine: int):
    """Photo synthétique du cas `graine` lue avec le marqueur en automatique (mise en cache)."""
    if graine not in _CACHE:
        couleur, traits, _ = CAS[graine]
        jpeg, verite = photo(graine, couleur, traits)
        _CACHE[graine] = (lp.lire_photo(_MODELE, jpeg, RESEAU), verite, jpeg)
    return _CACHE[graine][:2]


def jpeg_cas(graine: int) -> str:
    resultat_cas(graine)
    return _CACHE[graine][2]


class TestPhotosSynthetiques(unittest.TestCase):
    """10 photos synthétiques à graines fixes : repères, reprojection, longueur (≤ 3 %), accrochage."""


def _ajouter_tests_cas(graine: int):
    def t_reperes(self):
        r, v = resultat_cas(graine)
        self.assertEqual(sorted(r["reperes_photo_px"]), ["0", "1", "2", "3"])
        px_par_mm = r["photo_px_par_mm"]
        for i in range(4):
            ecart_px = np.abs(np.array(r["reperes_photo_px"][str(i)]) - np.array(v["reperes_photo_px"][str(i)])).max()
            self.assertLessEqual(ecart_px / px_par_mm, TOLERANCE_REPROJECTION_MM, f"repère {i}")

    def t_reprojection(self):
        r, _ = resultat_cas(graine)
        self.assertLessEqual(r["erreur_reprojection_mm"], TOLERANCE_REPROJECTION_MM)
        self.assertLessEqual(r["erreur_reprojection_max_mm"], TOLERANCE_REPROJECTION_MM)

    def t_longueur(self):
        r, v = resultat_cas(graine)
        verite = v["longueur_totale_m"]
        mesure = r["longueur_totale_plan_m"]
        self.assertLessEqual(abs(mesure - verite) / verite, TOLERANCE_LONGUEUR,
                             f"mesuré {mesure} m, vérité {verite} m")

    def t_accrochage(self):
        r, _ = resultat_cas(graine)
        couleur, _, liaisons = CAS[graine]
        self.assertEqual(r["marqueur"], couleur)
        obtenues = sorted((sorted({p["de"], p["a"]} - {None}) for p in r["polylignes"]))
        self.assertEqual(obtenues, sorted(sorted(l) for l in liaisons))

    for nom, f in (("reperes_detectes", t_reperes), ("reprojection", t_reprojection),
                   ("longueur_3_pourcent", t_longueur), ("accrochage", t_accrochage)):
        f.__name__ = f"test_photo_{graine:02d}_{nom}"
        setattr(TestPhotosSynthetiques, f.__name__, f)


for _g in CAS:
    _ajouter_tests_cas(_g)


class TestGeometrieDesTraces(unittest.TestCase):
    def test_sommets_proches_de_la_verite(self):
        """Cas 6 (5 coudes) : chaque sommet lu est à ≤ 0,10 m (2 mm sur la feuille au 1:50) du sommet tracé."""
        r, v = resultat_cas(6)
        pts = np.array(r["polylignes"][0]["points_m"])
        vrai = np.array(v["traits_m"][0])
        if np.linalg.norm(pts[0] - vrai[0]) > np.linalg.norm(pts[0] - vrai[-1]):
            pts = pts[::-1]
        self.assertEqual(len(pts), len(vrai))
        self.assertLessEqual(np.abs(pts - vrai).max(), 0.10)

    def test_angles_droits_exacts(self):
        r, _ = resultat_cas(1)
        pts = np.array(r["polylignes"][0]["points_m"])
        for a, b in zip(pts[:-1], pts[1:]):
            self.assertTrue(a[0] == b[0] or a[1] == b[1], f"segment {a} → {b} non redressé")

    def test_diagonale_conservee(self):
        """Cas 5 : le segment à 31° n'est pas redressé."""
        r, _ = resultat_cas(5)
        pts = np.array(r["polylignes"][0]["points_m"])
        angles = [abs(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))) % 180 for a, b in zip(pts[:-1], pts[1:])]
        self.assertTrue(any(20 < min(x, 180 - x) < 70 for x in angles), angles)

    def test_croisement_deux_troncons(self):
        """Cas 8 : deux tracés qui se croisent → 2 tronçons, chacun traverse le croisement tout droit."""
        r, _ = resultat_cas(8)
        self.assertEqual(len(r["polylignes"]), 2)

    def test_extremites_libres_questions(self):
        r, _ = resultat_cas(9)
        p = r["polylignes"][0]
        self.assertIsNone(p["de"])
        self.assertIsNone(p["a"])
        self.assertEqual(len(r["questions"]), 2)
        self.assertIn("relier à quel équipement", r["questions"][0])

    def test_accroche_au_mur(self):
        """Cas 10 : extrémité à 5 cm du mur M2 → accrochée à sa face (x = 0,10 m)."""
        r, _ = resultat_cas(10)
        p = r["polylignes"][0]
        self.assertEqual(p["de"], "EV1")
        self.assertEqual(p["mur_a"], "M2")
        self.assertAlmostEqual(p["points_m"][-1][0], 0.10, places=3)

    def test_ordre_evaporateur_vers_groupe(self):
        """Cas 4 tracé du groupe vers l'évaporateur : la ligne est orientée de EV1 vers GR1."""
        r, _ = resultat_cas(4)
        self.assertEqual((r["polylignes"][0]["de"], r["polylignes"][0]["a"]), ("EV1", "GR1"))

    def test_angle_de_4_degres_redresse(self):
        """Tracé en L dont la première branche est à 4° de l'horizontale : redressée à 0°, angle droit exact."""
        y = 1.6 + 3.9 * math.tan(math.radians(4))
        traits = [[(9.4, 1.6), (5.5, y), (5.5, 4.8), (1.5, 4.8)]]
        jpeg, _ = photo(21, "rouge", traits)
        r = lp.lire_photo(_MODELE, jpeg, RESEAU)
        pts = np.array(r["polylignes"][0]["points_m"])
        self.assertEqual(len(pts), 4)
        for a, b in zip(pts[:-1], pts[1:]):
            self.assertTrue(a[0] == b[0] or a[1] == b[1], f"segment {a} → {b} non redressé")
        self.assertEqual(pts[1][1], 1.6)

    def test_impression_reduite_reste_juste(self):
        """Impression « ajuster à la page » (94 %) : les longueurs restent justes grâce aux repères."""
        couleur, traits, _ = CAS[6]
        jpeg, v = photo(22, couleur, traits, echelle_impression=0.94)
        r = lp.lire_photo(_MODELE, jpeg, RESEAU)
        self.assertLessEqual(abs(r["longueur_totale_plan_m"] - v["longueur_totale_m"]) / v["longueur_totale_m"],
                             TOLERANCE_LONGUEUR)

    def test_photo_haute_resolution(self):
        """Photo de 4000 px de large : détection sur image réduite puis affinage, redressement après réduction."""
        couleur, traits, _ = CAS[1]
        jpeg, v = photo(23, couleur, traits, largeur_photo=4000)
        r = lp.lire_photo(_MODELE, jpeg, RESEAU)
        self.assertLessEqual(r["erreur_reprojection_mm"], TOLERANCE_REPROJECTION_MM)
        self.assertLessEqual(abs(r["longueur_totale_plan_m"] - v["longueur_totale_m"]) / v["longueur_totale_m"],
                             TOLERANCE_LONGUEUR)

    def test_accrochage_bord(self):
        """Mode « bord » : tracé arrêté 8 cm à gauche de GR1 → accroché au bord le plus proche, pas au centre."""
        traits = [[(9.4, 1.6), (5.5, 1.6), (5.5, 4.8), (0.92, 4.8)]]
        jpeg, _ = photo(24, "rouge", traits)
        r = lp.lire_photo(_MODELE, jpeg, RESEAU, accrochage="bord")
        p = r["polylignes"][0]
        self.assertEqual((p["de"], p["a"]), ("EV1", "GR1"))
        self.assertAlmostEqual(p["points_m"][-1][0], 1.0, delta=0.01)


class TestMarqueurs(unittest.TestCase):
    def test_marqueur_noir(self):
        _, traits, _ = CAS[1]
        jpeg, v = photo(31, "noir", traits)
        for choix in ("noir", "auto"):
            r = lp.lire_photo(_MODELE, jpeg, RESEAU, marqueur=choix)
            self.assertEqual(r["marqueur"], "noir")
            self.assertLessEqual(abs(r["longueur_totale_plan_m"] - v["longueur_totale_m"]) / v["longueur_totale_m"],
                                 TOLERANCE_LONGUEUR)
            self.assertEqual({r["polylignes"][0]["de"], r["polylignes"][0]["a"]}, {"EV1", "GR1"})

    def test_marqueur_bleu_impose(self):
        _, traits, _ = CAS[3]
        jpeg, v = photo(32, "bleu", traits)
        r = lp.lire_photo(_MODELE, jpeg, RESEAU, marqueur="bleu")
        self.assertEqual(r["marqueur"], "bleu")
        self.assertLessEqual(abs(r["longueur_totale_plan_m"] - v["longueur_totale_m"]) / v["longueur_totale_m"],
                             TOLERANCE_LONGUEUR)

    def test_autre_reseau_aucun_trait_de_la_couleur(self):
        """Photo d'un autre réseau (tracé vert, feuille électricité) lue en rouge : code 1, message clair."""
        _, traits, _ = CAS[3]
        jpeg, _ = photo(33, "vert", traits, reseau="electricite")
        with self.assertRaises(lp.ErreurPhoto) as ctx:
            lp.lire_photo(_MODELE, jpeg, "electricite", marqueur="rouge")
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("aucun trait rouge", str(ctx.exception))
        self.assertIn("vert", str(ctx.exception))
        sortie = io.StringIO()
        with contextlib.redirect_stderr(sortie):
            code = lp.main([str(_MODELE), jpeg, "--reseau", "electricite", "--marqueur", "rouge"])
        self.assertEqual(code, 1)
        self.assertIn("aucun trait rouge", sortie.getvalue())

    def test_feuille_sans_trait(self):
        jpeg, _ = photo(34, "rouge", [])
        with self.assertRaises(lp.ErreurPhoto) as ctx:
            lp.lire_photo(_MODELE, jpeg, RESEAU)
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("aucun trait", str(ctx.exception))


class TestReperesEtFichiers(unittest.TestCase):
    def test_photo_sans_reperes_code_1(self):
        jpeg, _ = photo(41, "rouge", CAS[1][1], masquer_reperes=(0, 1, 2, 3))
        sortie = io.StringIO()
        with contextlib.redirect_stderr(sortie):
            code = lp.main([str(_MODELE), jpeg, "--reseau", RESEAU])
        self.assertEqual(code, 1)
        for i in range(4):
            self.assertIn(f"{i} ({fe.POSITIONS_REPERES[i]})", sortie.getvalue())

    def test_un_repere_manquant_est_nomme(self):
        jpeg, _ = photo(42, "rouge", CAS[1][1], masquer_reperes=(2,))
        with self.assertRaises(lp.ErreurPhoto) as ctx:
            lp.lire_photo(_MODELE, jpeg, RESEAU)
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("2 (bas-droite)", str(ctx.exception))
        self.assertNotIn("0 (haut-gauche)", str(ctx.exception))

    def test_photo_absente_code_2(self):
        sortie = io.StringIO()
        with contextlib.redirect_stderr(sortie):
            code = lp.main([str(_MODELE), str(_TMP / "absente.jpg"), "--reseau", RESEAU])
        self.assertEqual(code, 2)

    def test_feuille_absente_code_2(self):
        with self.assertRaises(lp.ErreurPhoto) as ctx:
            lp.lire_photo(_MODELE, jpeg_cas(1), "eau_chaude")
        self.assertEqual(ctx.exception.code, 2)

    def test_fichiers_de_sortie(self):
        r, _ = resultat_cas(1)
        calque = json.loads(Path(r["fichiers"]["calque"]).read_text(encoding="utf-8"))
        for cle in ("reseau", "type", "source", "photo", "S", "polylignes", "erreur_reprojection_mm", "avertissements"):
            self.assertIn(cle, calque)
        self.assertEqual((calque["reseau"], calque["type"], calque["source"], calque["S"]), (RESEAU, "aspiration", "photo", 50))
        p = calque["polylignes"][0]
        for cle in ("id", "points_m", "longueur_plan_m", "de", "a", "confiance"):
            self.assertIn(cle, p)
        self.assertTrue(p["id"].startswith(f"{RESEAU}-photo-"))
        self.assertTrue(0 <= p["confiance"] <= 1)
        controle = fe.lire_image(r["fichiers"]["controle"])
        self.assertEqual(controle.shape[:2], (840, 1188))


class TestFusion(unittest.TestCase):
    def test_fusionner_ajoute_et_sauvegarde(self):
        d = nouveau_dossier("fusion-1")
        avant = (d / "plan.json").read_text(encoding="utf-8")
        jpeg, _ = photo(51, "rouge", CAS[1][1])
        r = lp.lire_photo(d, jpeg, RESEAU, fusionner=True)
        self.assertTrue(r["fusion"]["faite"])
        sauvegarde = Path(r["fusion"]["sauvegarde"])
        self.assertTrue(sauvegarde.name.startswith("plan.json.avant-fusion-"))
        self.assertEqual(sauvegarde.parent, d / "versions")
        self.assertEqual(sauvegarde.read_text(encoding="utf-8"), avant)
        plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
        ids = [l["id"] for l in plan["lignes"]]
        self.assertIn("L1", ids)
        nouvelles = [l for l in plan["lignes"] if l.get("source") == "photo"]
        self.assertEqual(len(nouvelles), 1)
        l = nouvelles[0]
        self.assertEqual((l["type"], l["calque"], l["de"], l["a"], l["diametre"]),
                         ("aspiration", RESEAU, "EV1", "GR1", "à définir"))
        self.assertEqual(l["points"], r["polylignes"][0]["points_m"])

    def test_fusionner_deux_fois_remplace(self):
        d = nouveau_dossier("fusion-2")
        jpeg, _ = photo(52, "rouge", CAS[1][1])
        lp.lire_photo(d, jpeg, RESEAU, fusionner=True)
        r = lp.lire_photo(d, jpeg, RESEAU, fusionner=True)
        plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(len([l for l in plan["lignes"] if l.get("source") == "photo"]), 1)
        self.assertTrue(any("remplacée" in a for a in r["avertissements"]))
        self.assertEqual(len(list((d / "versions").glob("plan.json.avant-fusion-*"))), 2)

    def test_fusion_extremite_libre_pose_une_question(self):
        d = nouveau_dossier("fusion-3")
        jpeg, _ = photo(53, "rouge", CAS[9][1])
        r = lp.lire_photo(d, jpeg, RESEAU, fusionner=True)
        plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
        l = [l for l in plan["lignes"] if l.get("source") == "photo"][0]
        self.assertIsNone(l["de"])
        self.assertIsNone(l["a"])
        self.assertTrue(any("extrémité libre à (" in a and "relier à quel équipement" in a for a in r["avertissements"]))

    def test_longueur_attendue_hors_seuil_bloque_la_fusion(self):
        d = nouveau_dossier("fusion-4")
        jpeg, v = photo(54, "rouge", CAS[1][1])
        r = lp.lire_photo(d, jpeg, RESEAU, fusionner=True, longueur_attendue_m=v["longueur_totale_m"] * 1.2)
        self.assertFalse(r["controle_longueur"]["ok"])
        self.assertFalse(r["fusion"]["faite"])
        self.assertTrue(any("écart" in a for a in r["avertissements"]))
        plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
        self.assertFalse(any(l.get("source") == "photo" for l in plan["lignes"]))
        r = lp.lire_photo(d, jpeg, RESEAU, fusionner=True, confirmer=True,
                          longueur_attendue_m=v["longueur_totale_m"] * 1.2)
        self.assertTrue(r["fusion"]["faite"])

    def test_type_suppose_ecrit_dans_le_calque_et_le_plan(self):
        """Feuille clim_cuivres sans --type : type supposé clim_gaz, repris dans le calque et dans plan.json."""
        d = nouveau_dossier("fusion-5")
        f = fe.fabriquer_feuille(d, "clim_cuivres", pdf=False, date="2026-10-07")
        self.assertTrue(any("type supposé" in a for a in f["avertissements"]))
        jpeg, _ = ps.fabriquer(f["png"], f["json"], en_mm(CAS[3][1]), 55, couleur="vert", sortie=_TMP / "photos" / "clim.jpg")
        r = lp.lire_photo(d, jpeg, "clim_cuivres", fusionner=True)
        self.assertEqual(r["type"], "clim_gaz")
        calque = json.loads(Path(r["fichiers"]["calque"]).read_text(encoding="utf-8"))
        self.assertEqual(calque["type"], "clim_gaz")
        plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
        l = [l for l in plan["lignes"] if l.get("source") == "photo"][0]
        self.assertEqual((l["type"], l["calque"]), ("clim_gaz", "clim_cuivres"))

    def test_longueur_attendue_dans_le_seuil(self):
        r, v = resultat_cas(2)
        res = lp.lire_photo(_MODELE, jpeg_cas(2), RESEAU, longueur_attendue_m=v["longueur_totale_m"] + 0.25)
        self.assertTrue(res["controle_longueur"]["ok"])
        self.assertFalse(any("écart" in a for a in res["avertissements"]))


class TestBriques(unittest.TestCase):
    def test_squelette_barre_epaisse(self):
        img = np.zeros((60, 200), np.uint8)
        cv2.line(img, (20, 30), (180, 30), 1, 11)
        sq = lp.squelette_zhang_suen(img)
        self.assertLessEqual(int(sq.sum(axis=0).max()), 1)     # un pixel d'épaisseur
        ys = np.nonzero(sq)[0]
        self.assertTrue(np.all(np.abs(ys - 30) <= 1))
        self.assertGreater(int(sq.sum()), 150)

    def test_vectoriser_croix_traversee(self):
        img = np.zeros((200, 200), np.uint8)
        cv2.line(img, (20, 100), (180, 100), 1, 9)
        cv2.line(img, (100, 20), (100, 180), 1, 9)
        polys = lp.vectoriser(lp.squelette_zhang_suen(img), ergot_px=12, longueur_min_px=12, contraction_px=10)
        self.assertEqual(len(polys), 2)
        for p in polys:
            self.assertGreater(longueur(p["points"]), 140)

    def test_redresser_seuil_7_degres(self):
        pts, _ = lp.redresser_polyligne([(0, 0), (10, 10 * math.tan(math.radians(5)))])
        self.assertEqual(pts[0][1], pts[1][1])
        pts, _ = lp.redresser_polyligne([(0, 0), (10, 10 * math.tan(math.radians(10)))])
        self.assertNotEqual(pts[0][1], pts[1][1])

    def test_conversion_mm_vers_m(self):
        self.assertTrue(np.allclose(fe.mm_vers_m([44.0, 24.0], BASE), [1.0, 0.0]))
        self.assertTrue(np.allclose(fe.m_vers_mm([10.0, 6.0], BASE), [224.0, 144.0]))


class TestAccrochageMurAligne(unittest.TestCase):
    """C2 (écart n° 2 de V) : mur à `alignement` « droite » (boucherie, M2 de (16 ; 0) à (16 ; 11), épaisseur 0,20) :
    sa face intérieure est à x = 15,80 (et non 15,90 comme avec un mur centré sur son axe)."""

    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((FIXTURES / "a1-boucherie-plan.json").read_text(encoding="utf-8"))
        cls.murs = {m["id"]: (m, fe.rectangle_mur(m)) for m in cls.plan["murs"]}

    def accrocher(self, x, y):
        return lp._accrocher(np.array([x, y]), {}, self.murs, "centre")

    def test_bout_a_2_cm_de_la_face(self):
        cible, epingle, info = self.accrocher(15.78, 5.0)
        self.assertEqual(info, {"type": "mur", "id": "M2"})
        self.assertAlmostEqual(cible[0], 15.80, places=9)
        self.assertAlmostEqual(epingle["x"], 15.80, places=9)

    def test_bout_5_cm_dans_le_mur(self):
        cible, _, info = self.accrocher(15.85, 5.0)               # face la plus proche : l'intérieure
        self.assertEqual(info["id"], "M2")
        self.assertAlmostEqual(cible[0], 15.80, places=9)
        self.assertAlmostEqual(self.accrocher(15.95, 5.0)[0][0], 16.00, places=9)   # près de la face extérieure

    def test_photo_tracee_jusqu_au_mur(self):
        d = _TMP / "boucherie" / "plan"
        d.mkdir(parents=True)
        shutil.copy(FIXTURES / "a1-boucherie-plan.json", d / "plan.json")
        base = {"S": 100, "orientation": "paysage", "origine_mm": [61.9989, 46.101]}
        (d / "plan-base.json").write_text(json.dumps(base), encoding="utf-8")
        fe.fabriquer_feuille(d, RESEAU, "aspiration", pdf=False, date="2026-10-07")
        feuille = fe.chemins_feuille(d, RESEAU)
        trait = [(13.5, 5.0), (15.78, 5.0)]                         # s'arrête 2 cm avant la face intérieure de M2
        jpeg, _ = ps.fabriquer(feuille["png"], feuille["json"], [fe.m_vers_mm(trait, base).tolist()], 31,
                               couleur="rouge", sortie=_TMP / "photos" / "boucherie-m2.jpg")
        with contextlib.redirect_stdout(io.StringIO()):
            r = lp.lire_photo(d, jpeg, RESEAU)
        p = r["polylignes"][0]
        bout = p["points_m"][-1] if p["mur_a"] == "M2" else p["points_m"][0]
        self.assertEqual("M2", p["mur_a"] or p["mur_de"])
        self.assertAlmostEqual(bout[0], 15.80, delta=0.005)


if __name__ == "__main__":
    unittest.main()
