"""Tests du Lot 6 : feuille A4 à imprimer (feuille.py).

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -p "test_feuille.py"
(compatible pytest). Fixture : tests/fixtures/a3-plan.json + a3-plan-base.json (plan fictif, 1:50 paysage).
Les positions sont vérifiées indépendamment de feuille.py (valeurs attendues écrites ici, détection ArUco refaite).
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))   # dossier scripts/
import feuille as fe  # noqa: E402

FIXTURES = ICI / "fixtures"
RESEAU = "froid_cuivres"
A4_PAYSAGE_PT = (841.89, 595.28)
# Coins attendus des repères en paysage (297 × 210 mm) : carrés de 16 mm, centres à 14 mm des bords.
COINS_PAYSAGE = {0: [[6, 6], [22, 6], [22, 22], [6, 22]], 1: [[275, 6], [291, 6], [291, 22], [275, 22]],
                 2: [[275, 188], [291, 188], [291, 204], [275, 204]], 3: [[6, 188], [22, 188], [22, 204], [6, 204]]}

_TMP: Path | None = None
_DOSSIER: Path | None = None
_RESULTAT: dict | None = None


def setUpModule():
    global _TMP, _DOSSIER, _RESULTAT
    _TMP = Path(tempfile.mkdtemp(prefix="a3-feuille-"))
    _DOSSIER = preparer("principal")
    _RESULTAT = fe.fabriquer_feuille(_DOSSIER, RESEAU, "aspiration", date="2026-10-07")


def tearDownModule():
    if _TMP is not None:
        shutil.rmtree(_TMP, ignore_errors=True)


def preparer(nom: str, base: dict | None = None) -> Path:
    d = _TMP / nom / "plan"
    d.mkdir(parents=True)
    shutil.copy(FIXTURES / "a3-plan.json", d / "plan.json")
    if base is None:
        shutil.copy(FIXTURES / "a3-plan-base.json", d / "plan-base.json")
    else:
        (d / "plan-base.json").write_text(json.dumps(base), encoding="utf-8")
    return d


def detecter(gris: np.ndarray) -> dict[int, np.ndarray]:
    """Détection indépendante (paramètres par défaut + affinage sous-pixel)."""
    p = cv2.aruco.DetectorParameters()
    p.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    det = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), p)
    coins, ids, _ = det.detectMarkers(gris)
    return {} if ids is None else {int(i): c.reshape(4, 2) for c, i in zip(coins, ids.ravel())}


def png() -> np.ndarray:
    return cv2.imdecode(np.fromfile(_RESULTAT["png"], dtype=np.uint8), cv2.IMREAD_GRAYSCALE)


class TestFeuillePaysage(unittest.TestCase):
    def test_fichiers_produits(self):
        for cle, suffixe in (("png", ".png"), ("pdf", ".pdf"), ("json", ".json")):
            chemin = Path(_RESULTAT[cle])
            self.assertTrue(chemin.is_file(), cle)
            self.assertEqual(chemin.name, f"feuille-{RESEAU}{suffixe}")
            self.assertEqual(chemin.parent, _DOSSIER / "feuilles")
        self.assertEqual(_RESULTAT["controle"]["erreurs"], [])

    def test_png_dimensions_8_px_par_mm(self):
        self.assertEqual(png().shape, (1680, 2376))
        with Image.open(_RESULTAT["png"]) as im:
            self.assertAlmostEqual(im.info["dpi"][0], 203.2, delta=0.1)

    def test_pdf_page_a4_paysage(self):
        doc = pymupdf.open(_RESULTAT["pdf"])
        try:
            self.assertEqual(doc.page_count, 1)
            r = doc[0].rect
            self.assertAlmostEqual(r.width, A4_PAYSAGE_PT[0], delta=0.5)
            self.assertAlmostEqual(r.height, A4_PAYSAGE_PT[1], delta=0.5)
            images = doc[0].get_image_info()
            self.assertEqual(len(images), 1)
            for v, attendu in zip(images[0]["bbox"], (0, 0, r.width, r.height)):
                self.assertAlmostEqual(v, attendu, delta=0.5)
        finally:
            doc.close()

    def test_json_complet(self):
        infos = json.loads(Path(_RESULTAT["json"]).read_text(encoding="utf-8"))
        for cle in ("S", "orientation", "origine_mm", "page_mm", "reseau", "type_ligne", "reperes", "px_par_mm",
                    "date", "dossier", "barre_echelle"):
            self.assertIn(cle, infos)
        self.assertEqual((infos["S"], infos["orientation"], infos["origine_mm"]), (50, "paysage", [24.0, 24.0]))
        self.assertEqual(infos["page_mm"], [297.0, 210.0])
        self.assertEqual((infos["reseau"], infos["type_ligne"], infos["px_par_mm"]), (RESEAU, "aspiration", 8))
        self.assertEqual((infos["date"], infos["dossier"]), ("2026-10-07", "2026-10-07-atelier-test-a3"))

    def test_reperes_json_aux_bonnes_positions(self):
        infos = json.loads(Path(_RESULTAT["json"]).read_text(encoding="utf-8"))
        self.assertEqual(sorted(infos["reperes"]), ["0", "1", "2", "3"])
        for i, coins in COINS_PAYSAGE.items():
            self.assertEqual(infos["reperes"][str(i)]["coins_mm"], coins, f"repère {i}")
        self.assertEqual(infos["reperes"]["0"]["position"], "haut-gauche")
        self.assertEqual(infos["reperes"]["2"]["position"], "bas-droite")

    def test_reperes_detectes_sur_le_png_a_03_mm(self):
        trouves = detecter(png())
        self.assertEqual(sorted(trouves), [0, 1, 2, 3])
        for i, coins in COINS_PAYSAGE.items():
            mm = (trouves[i] + 0.5) / 8.0
            self.assertLessEqual(np.abs(mm - np.array(coins)).max(), 0.3, f"repère {i}")

    def test_reperes_detectes_sur_le_pdf_a_05_mm(self):
        doc = pymupdf.open(_RESULTAT["pdf"])
        try:
            zoom = 8 * 25.4 / 72
            pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY, alpha=False)
            gris = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)[:, :pix.width].copy()
        finally:
            doc.close()
        ppm = pix.width / 297.0
        trouves = detecter(gris)
        self.assertEqual(sorted(trouves), [0, 1, 2, 3])
        for i, coins in COINS_PAYSAGE.items():
            self.assertLessEqual(np.abs((trouves[i] + 0.5) / ppm - np.array(coins)).max(), 0.5, f"repère {i}")

    def test_bordure_blanche_autour_des_reperes(self):
        img = png()                                   # 8 px/mm ; repère 0 de 6 à 22 mm, bordure blanche de 4 à 24 mm
        self.assertTrue(np.all(img[4 * 8:6 * 8, 4 * 8:24 * 8] == 255))     # au-dessus du repère 0
        self.assertTrue(np.all(img[4 * 8:24 * 8, 4 * 8:6 * 8] == 255))     # à gauche
        self.assertTrue(np.all(img[22 * 8:24 * 8, 4 * 8:21 * 8] == 255))   # dessous (le mur M2 commence à 22 mm)
        self.assertTrue(np.all(img[4 * 8:21 * 8, 22 * 8:24 * 8] == 255))   # à droite (le mur M1 commence à 22 mm)
        infos = json.loads(Path(_RESULTAT["json"]).read_text(encoding="utf-8"))
        self.assertEqual(infos["reperes"]["0"]["cote_mm"], 16.0)
        self.assertEqual(infos["reperes"]["0"]["zone_blanche_mm"], [4.0, 4.0, 24.0, 24.0])

    def test_plan_de_base_gris_a_la_bonne_place(self):
        img = png()
        # Mur M1 (axe y = 0, épaisseur 0,20 m) : face extérieure à y = 24 − 2 = 22 mm, à x = 5 m → 124 mm.
        self.assertTrue(110 <= int(img[22 * 8, 124 * 8]) <= 200, int(img[22 * 8, 124 * 8]))
        # Groupe GR1 : bord gauche x = 1,0 m → 44 mm ; y = 4,8 m → 120 mm.
        self.assertTrue(110 <= int(img[120 * 8, 44 * 8]) <= 200)
        # Intérieur du local (3 m ; 3 m) → (84 mm ; 84 mm) : blanc.
        self.assertEqual(int(img[84 * 8, 84 * 8]), 255)
        # Aucun noir dans la zone du plan : le plan est en gris clair.
        self.assertGreaterEqual(int(img[28 * 8:170 * 8, 28 * 8:260 * 8].min()), 120)

    def test_barre_echelle_1_m_au_1_50(self):
        infos = json.loads(Path(_RESULTAT["json"]).read_text(encoding="utf-8"))
        barre = infos["barre_echelle"]
        self.assertEqual((barre["longueur_m"], barre["longueur_mm"]), (1, 20.0))
        img = png()
        y = int(round((barre["de_mm"][1] + barre["hauteur_mm"] / 2) * 8))
        x0, x1 = int(barre["de_mm"][0] * 8) - 40, int(barre["a_mm"][0] * 8) + 40
        sombres = np.flatnonzero(img[y, x0:x1] < 128)
        self.assertAlmostEqual(sombres.max() - sombres.min() + 1, 160, delta=2)

    def test_longueur_barre_selon_echelle(self):
        self.assertEqual([fe.longueur_barre_m(s) for s in (50, 100, 125, 200, 250, 1000)], [1, 1, 2, 2, 5, 5])

    def test_cadre_identification(self):
        img = png()
        cadre = img[(210 - 30) * 8:(210 - 8) * 8, 30 * 8:(297 - 30) * 8]
        self.assertLess(int(cadre.min()), 80)                         # textes présents
        self.assertTrue(np.all(img[(210 - 30) * 8 + 1, 40 * 8:250 * 8] < 128))   # bord haut du cadre
        infos = json.loads(Path(_RESULTAT["json"]).read_text(encoding="utf-8"))
        self.assertEqual(infos["cadre_identification_mm"], [30.0, 180.0, 267.0, 202.0])
        self.assertIn("ajuster à la page", fe.CONSIGNES)
        self.assertIn("Imprimer à 100 %", fe.CONSIGNES)

    def test_conversion_modele_vers_feuille(self):
        base = {"S": 50, "origine_mm": [24.0, 24.0]}
        self.assertTrue(np.allclose(fe.m_vers_mm([[0, 0], [10, 6]], base), [[24, 24], [224, 144]]))
        self.assertTrue(np.allclose(fe.mm_vers_m(fe.m_vers_mm([3.21, 4.56], base), base), [3.21, 4.56]))


class TestVariantes(unittest.TestCase):
    def test_portrait_1_100(self):
        d = preparer("portrait", {"S": 100, "orientation": "portrait", "origine_mm": [24.0, 24.0]})
        r = fe.fabriquer_feuille(d, "electricite", "cable", date="2026-10-07")
        img = cv2.imdecode(np.fromfile(r["png"], dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        self.assertEqual(img.shape, (2376, 1680))
        doc = pymupdf.open(r["pdf"])
        try:
            self.assertAlmostEqual(doc[0].rect.width, 595.28, delta=0.5)
            self.assertAlmostEqual(doc[0].rect.height, 841.89, delta=0.5)
        finally:
            doc.close()
        trouves = detecter(img)
        attendus = {0: (14, 14), 1: (196, 14), 2: (196, 283), 3: (14, 283)}
        self.assertEqual(sorted(trouves), [0, 1, 2, 3])
        for i, c in attendus.items():
            self.assertLessEqual(np.abs((trouves[i].mean(axis=0) + 0.5) / 8 - np.array(c)).max(), 0.3)
        infos = json.loads(Path(r["json"]).read_text(encoding="utf-8"))
        self.assertEqual(infos["barre_echelle"]["longueur_mm"], 10.0)

    def test_sans_pdf(self):
        d = preparer("sans-pdf")
        r = fe.fabriquer_feuille(d, RESEAU, pdf=False)
        self.assertIsNone(r["pdf"])
        self.assertFalse((d / "feuilles" / f"feuille-{RESEAU}.pdf").exists())
        self.assertTrue(Path(r["png"]).is_file())

    def test_type_suppose_pour_les_calques_standard(self):
        d = preparer("types")
        for reseau, attendu in (("froid_cuivres", "aspiration"), ("clim_cuivres", "clim_gaz"), ("electricite", "cable")):
            r = fe.fabriquer_feuille(d, reseau, pdf=False)
            infos = json.loads(Path(r["json"]).read_text(encoding="utf-8"))
            self.assertEqual(infos["type_ligne"], attendu, reseau)
            self.assertTrue(any("type supposé" in a and "--type" in a for a in r["avertissements"]), reseau)
            self.assertTrue(any("type supposé" in a for a in infos["avertissements"]), reseau)

    def test_type_calque_libre_et_type_impose(self):
        d = preparer("types-libres")
        r = fe.fabriquer_feuille(d, "eau_chaude", pdf=False)
        self.assertEqual(json.loads(Path(r["json"]).read_text(encoding="utf-8"))["type_ligne"], "eau_chaude")
        self.assertFalse(any("type supposé" in a for a in r["avertissements"]))
        r = fe.fabriquer_feuille(d, "froid_cuivres", "liquide", pdf=False)
        self.assertEqual(json.loads(Path(r["json"]).read_text(encoding="utf-8"))["type_ligne"], "liquide")
        self.assertFalse(any("type supposé" in a for a in r["avertissements"]))

    def test_reseau_inconnu_erreur(self):
        d = preparer("reseau-inconnu")
        for reseau in ("plomberie", "cotes"):
            with self.assertRaises(fe.ErreurFeuille) as ctx:
                fe.fabriquer_feuille(d, reseau, pdf=False)
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("réseau inconnu", str(ctx.exception))
            self.assertFalse((d / "feuilles" / f"feuille-{reseau}.png").exists())

    def test_avertissement_plan_sous_un_repere(self):
        d = preparer("deborde", {"S": 50, "orientation": "paysage", "origine_mm": [8.0, 8.0]})
        r = fe.fabriquer_feuille(d, RESEAU, pdf=False)
        self.assertTrue(any("repère 0" in a for a in r["avertissements"]), r["avertissements"])

    def test_cli_ok(self):
        d = preparer("cli")
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = fe.main([str(d), "--reseau", "eau_chaude", "--sans-pdf"])
        self.assertEqual(code, 0)
        self.assertIn("feuille-eau_chaude.png", sortie.getvalue())

    def test_plan_base_manquant_code_2(self):
        d = preparer("sans-base")
        (d / "plan-base.json").unlink()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(fe.main([str(d), "--reseau", RESEAU]), 2)

    def test_plan_json_manquant_code_2(self):
        d = preparer("sans-plan")
        (d / "plan.json").unlink()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(fe.main([str(d), "--reseau", RESEAU]), 2)

    def test_reseau_invalide_code_1(self):
        d = preparer("reseau-invalide")
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur):
            self.assertEqual(fe.main([str(d), "--reseau", "../evasion"]), 1)
        self.assertIn("clé de réseau invalide", erreur.getvalue())

    def test_orientation_invalide_code_1(self):
        d = preparer("orientation", {"S": 50, "orientation": "carré", "origine_mm": [24, 24]})
        with self.assertRaises(fe.ErreurFeuille) as ctx:
            fe.fabriquer_feuille(d, RESEAU, pdf=False)
        self.assertEqual(ctx.exception.code, 1)


BOUCHERIE_BASE = {"S": 100, "orientation": "paysage", "origine_mm": [61.9989, 46.101]}   # plan-base.json généré


def _centres_des_traits(valeurs: np.ndarray, seuil: int = 230) -> list[float]:
    """Centres (mm) des suites de pixels gris consécutifs d'une ligne ou d'une colonne du PNG à 8 px/mm."""
    idx = np.where(valeurs < seuil)[0]
    if len(idx) == 0:
        return []
    coupures = np.where(np.diff(idx) > 1)[0]
    debuts = np.concatenate([[idx[0]], idx[coupures + 1]])
    fins = np.concatenate([idx[coupures], [idx[-1]]])
    return [((a + b) / 2.0 + 0.5) / fe.PX_PAR_MM for a, b in zip(debuts, fins)]


class TestMursAlignes(unittest.TestCase):
    """C2 (écart n° 2 de V) : `alignement` des murs appliqué comme dans le plan draw.io. Boucherie (fixture a1),
    contour décrit par les faces extérieures, alignement « droite » : 16 × 11 m au 1:100 = 160 × 110 mm."""

    @classmethod
    def setUpClass(cls):
        d = _TMP / "boucherie" / "plan"
        d.mkdir(parents=True)
        shutil.copy(FIXTURES / "a1-boucherie-plan.json", d / "plan.json")
        (d / "plan-base.json").write_text(json.dumps(BOUCHERIE_BASE), encoding="utf-8")
        cls.r = fe.fabriquer_feuille(d, RESEAU, "aspiration", pdf=False, date="2026-10-07")
        cls.murs = {m["id"]: m for m in json.loads((d / "plan.json").read_text(encoding="utf-8"))["murs"]}
        cls.img = np.asarray(Image.open(cls.r["png"]).convert("L"))

    def test_rectangles_des_murs_exterieurs(self):
        # Faces attendues, écrites à la main : épaisseur 0,20 vers l'intérieur du bâtiment.
        attendu = {"M1": (0, 0, 16, 0.2), "M2": (15.8, 0, 16, 11), "M3": (0, 10.8, 16, 11), "M4": (0, 0, 0.2, 11)}
        for mid, boite in attendu.items():
            r = fe.rectangle_mur(self.murs[mid])
            np.testing.assert_allclose([*r.min(axis=0), *r.max(axis=0)], boite, atol=1e-9, err_msg=mid)

    def test_cloison_sans_alignement_reste_centree(self):
        r = fe.rectangle_mur(self.murs["M5"])                       # axe x = 10,05, épaisseur 0,10
        np.testing.assert_allclose([r[:, 0].min(), r[:, 0].max()], [10.0, 10.1], atol=1e-9)

    def test_contour_exterieur_160_x_110_mm_sur_la_feuille(self):
        o = BOUCHERIE_BASE["origine_mm"]
        ligne = self.img[int((o[1] + 25.0) * fe.PX_PAR_MM)]                     # y = 2,50 m
        xs = _centres_des_traits(ligne)
        self.assertAlmostEqual(xs[0], o[0], delta=0.2)
        self.assertAlmostEqual(xs[-1] - xs[0], 160.0, delta=0.2)
        colonne = self.img[:int(175 * fe.PX_PAR_MM), int((o[0] + 75.0) * fe.PX_PAR_MM)]   # x = 7,50 m, hors cadre
        ys = _centres_des_traits(colonne)
        self.assertAlmostEqual(ys[0], o[1], delta=0.2)
        self.assertAlmostEqual(ys[-1] - ys[0], 110.0, delta=0.2)


if __name__ == "__main__":
    unittest.main()
