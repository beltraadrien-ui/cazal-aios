"""Tests des corrections H2 (test « session neuve » du 2026-10-08) côté étape 2 : écritures de plaque des fluides
(« R507 », « R-507A », « r404a », « R 449 A ») et contrôle du nombre saisi contre sa formule (--verifier).

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-dimensionnement/scripts/tests -v
Dossier fictif (celui de test_calculs_integration.py), créé dans un répertoire temporaire du système.
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

DOSSIER_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DOSSIER_SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import calculs  # noqa: E402
import fluides  # noqa: E402
from test_calculs_integration import ecrire, entrees_generiques  # noqa: E402
from valeur import Valeur, depuis_json, en_json  # noqa: E402

S = "sourcé"


def lancer(*args) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = calculs.main([str(a) for a in args])
    return code, sortie.getvalue()


class TestDesignation(unittest.TestCase):
    def test_ecritures_de_plaque_courantes(self):
        for ecrit, attendu in (("R507", "R507A"), ("R-507A", "R507A"), ("r507a", "R507A"), ("R 507", "R507A"),
                               ("R404a", "R404A"), ("R404", "R404A"), ("R 449 A", "R449A"), ("R-449A", "R449A"),
                               ("R134A", "R134a"), ("R744", "R744"), ("R449A", "R449A")):
            self.assertEqual(fluides.designation(ecrit), attendu, ecrit)
        self.assertEqual(fluides.nom_coolprop("R507"), "R507A.mix")
        self.assertEqual(fluides.nom_coolprop("R 449 A"), "R449A.mix")

    def test_series_ambigues_et_textes_refuses(self):
        for ecrit in ("R449", "R407", "R410", "CO2", "non indiqué", "", None, "R1234yf"):
            self.assertIsNone(fluides.designation(ecrit), ecrit)
        with self.assertRaises(ValueError):
            fluides.nom_coolprop("R449")                       # R449A, B ou C : la lettre change le fluide


class TestFluidesNormalises(unittest.TestCase):
    """Un dossier saisi avec les écritures de la plaque passe --verifier et calcule comme avec les désignations."""

    def test_normalisation_dans_calculs(self):
        e = entrees_generiques()
        e["projet"]["fluide_actuel"]["valeur"] = "R 449 A"
        e["postes"][1]["plaques_ensemble"][0]["fluide"] = {"valeur": "R507", "source": "photo p04-2 (écrit R507)",
                                                          "statut": S, "id": "p-plaque-fluide"}
        e["postes"][0]["evaporateurs"][0]["fluide_origine"] = "R507"
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp) / "2026-01-01-client-fictif"
            dossier.mkdir()
            ecrire(dossier, e)
            code, sortie = lancer(dossier, "--verifier")
            self.assertEqual(code, 0, sortie)
            self.assertIn("fluide « R 449 A » lu « R449A »", sortie)
            self.assertIn("fluide « R507 » lu « R507A »", sortie)
            code, sortie = lancer(dossier)
            self.assertEqual(code, 0, sortie)
            res = depuis_json((dossier / calculs.RESULTATS).read_text(encoding="utf-8"))
            self.assertEqual(res["projet"]["fluide_actuel"]["valeur"], "R449A")
            n = next(p for p in res["postes"] if p["id"] == "poste-n")
            self.assertEqual(n["evaporateurs"][0]["fluide_origine"], "R507")            # texte lu, gardé tel quel

    def test_variante_depuis_le_fluide_d_origine_ecrit_sur_la_plaque(self):
        e = depuis_json(en_json(entrees_generiques()))
        e["projet"]["fluide_actuel"] = {"valeur": "R449A", "source": "hypothèse : rapport p. 2", "statut": "hypothèse",
                                        "id": "fluide-actuel"}
        e["postes"][0]["evaporateurs"][0]["fluide_origine"] = "R507"
        calculs.normaliser_fluides(e)
        poste = e["postes"][0]
        variantes = calculs._variantes_fluide(poste, "R449A", "groupe de condensation", poste["charge"], "2026-01-01",
                                              None)
        self.assertEqual([v["fluide"] for v in variantes], ["R507A"])


class TestFormule(unittest.TestCase):
    def test_valeur_formule(self):
        self.assertAlmostEqual(calculs.valeur_formule("14,6 × 50 × 2,7"), 1971.0)
        self.assertAlmostEqual(calculs.valeur_formule("14,6x 11,6 x 2,4"), 406.464)
        self.assertAlmostEqual(calculs.valeur_formule("(10 + 4) × 2"), 28.0)
        for f in ("", "c1-vb × c1-lambda", "1 450 × 2", None, "×"):
            self.assertIsNone(calculs.valeur_formule(f), f)

    def test_verifier_compare_nombre_et_formule(self):
        def avec_volume(nombre, formule):
            e = entrees_generiques()
            e["postes"][0]["volume"] = Valeur(nombre, "m³", "rapport p. 3", S, formule, id="n-volume")
            return calculs.verifier(depuis_json(en_json(e)))
        erreurs, attentions = avec_volume(406.5, "14,6 × 11,6 × 2,4")              # arrondi saisi : toléré
        self.assertEqual(erreurs, [])
        self.assertFalse(any("formule" in a for a in attentions if "poste-n" in a), attentions)
        _, attentions = avec_volume(420.0, "14,6 × 11,6 × 2,4")                   # écart de 3,3 % : signalé
        self.assertTrue(any("différent de sa formule" in a and "406,464" in a for a in attentions), attentions)
        _, attentions = avec_volume(100.0, "")                                     # pas de formule : surface perdue
        self.assertTrue(any("poste-n" in a and "pas de « formule »" in a for a in attentions), attentions)


if __name__ == "__main__":
    unittest.main()
