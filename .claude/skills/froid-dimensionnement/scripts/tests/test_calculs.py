"""Tests des calculs du skill froid-dimensionnement : fluides (CoolProp), M1 cylindrée, M2 point catalogue.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-dimensionnement/scripts/tests -v
Bibliothèque standard uniquement (unittest) ; CoolProp 8.0.0 requis (requirements.txt). Données génériques ou
lues dans le CSV public dimensionnement/savoir/materiel/points-catalogue/bitzer-r449a.csv ; aucune donnée client.
Chiffres de référence : exemple de dimensionnement/savoir/methodes/puissance-existante.md § 8.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # dossier scripts/
import fluides  # noqa: E402
from compresseurs import (CHEMIN_POINTS_DEFAUT, charger_points, choix, m1_cylindree, m2_point_catalogue,  # noqa: E402
                          parametres_par_defaut, puissance_compresseur)
from valeur import A_CONFIRMER, CALCULE, ESPACE, HYPOTHESE, SOURCE, Valeur, a_confirmer, en_json  # noqa: E402

POINTS = charger_points()


def t(x, id=""):
    """Température sourcée de test (°C)."""
    return Valeur(x, "°C", "régime de test", SOURCE, id=id)


def vb(x):
    return Valeur(x, "m³/h", "volume balayé de test", SOURCE, id="vb")


def point_csv(modele, fluide, t0, tc):
    """La puissance publiée lue directement dans le CSV (pas par le code testé)."""
    trouves = [p for p in POINTS if p["modele"] == modele and p["fluide"] == fluide
               and p["t_evaporation_c"] == t0 and p["t_condensation_c"] == tc]
    assert len(trouves) == 1, (modele, fluide, t0, tc, len(trouves))
    return trouves[0]["puissance_frigo_kw"]


# Conditions de l'exemple de puissance-existante.md § 8 : surchauffe 10 K, sous-refroidissement 0 K, rosée.
SURCHAUFFE_10 = {"surchauffe": Valeur(10.0, "K", "exemple de methodes/puissance-existante.md § 8", HYPOTHESE)}
# Paramètres entièrement sourcés (cas où Loïc aurait répondu) : seul le calcul fixe le statut.
SOURCES = {"convention": choix("rosee", "réponse de test", SOURCE, "c"),
           "gaz_aspire": Valeur(20.0, "°C", "réponse de test", SOURCE),
           "sous_refroidissement": Valeur(0.0, "K", "réponse de test", SOURCE)}


class TestFluides(unittest.TestCase):
    def test_noms_coolprop(self):
        attendus = {"R449A": "R449A.mix", "R448A": "R448A.mix", "R407F": "R407F.mix", "R404A": "R404A.mix",
                    "R744": "CO2", "CO2": "CO2", "r-449a": "R449A.mix", "R134a": "R134a", "R290": "R290",
                    "R717": "R717", "R449A.mix": "R449A.mix"}
        for fluide, nom in attendus.items():
            self.assertEqual(fluides.nom_coolprop(fluide), nom, fluide)
            self.assertGreater(fluides.pression_pa(fluide, -10), 0)        # CoolProp connaît bien ce nom
        with self.assertRaises(ValueError):
            fluides.nom_coolprop("R999")

    def test_r404a_mix_equivalent_au_pseudo_corps_pur(self):
        # Choix documenté dans fluides.py : « R404A.mix » ; l'écart avec le pseudo-corps pur reste négligeable.
        mix = fluides._cycle("R404A.mix", -30.0, 40.0, 20.0, None, 0.0, "rosee")
        pur = fluides._cycle("R404A", -30.0, 40.0, 20.0, None, 0.0, "rosee")
        rho_dh = lambda c: c["densite"] * c["delta_h"]  # noqa: E731
        self.assertLess(abs(rho_dh(mix) / rho_dh(pur) - 1), 0.001)

    def test_densite_r449a_vapeur_saturee(self):
        e = fluides.etat_aspiration("R449A", -30, surchauffe_k=0)
        self.assertAlmostEqual(e["densite"].nombre, 7.31, delta=0.02)        # rapport du 2026-10-06
        self.assertEqual(e["densite"].unite, "kg/m³")
        self.assertEqual(e["enthalpie"].unite, "kJ/kg")
        self.assertIn("CoolProp 8.0.0, R449A.mix, convention rosée", e["densite"].source)

    def test_pressions_et_delta_h_de_l_exemple(self):
        self.assertAlmostEqual(fluides.p_saturation("R449A", -30).nombre, 1.5997, places=3)
        self.assertAlmostEqual(fluides.p_saturation("R449A", 40).nombre, 16.5217, places=3)
        self.assertAlmostEqual(fluides.p_saturation("R404A", -30).nombre, 2.0223, places=3)
        self.assertAlmostEqual(fluides.delta_h_evaporateur("R449A", -30, 40, surchauffe_k=10).nombre, 138.40, delta=0.05)
        self.assertAlmostEqual(fluides.delta_h_evaporateur("R404A", -30, 40, gaz_aspire_c=20).nombre, 132.85, delta=0.05)
        self.assertAlmostEqual(fluides.taux_compression("R449A", -30, 40).nombre, 10.328, places=2)

    def test_convention_moyenne_et_glissement(self):
        p_moy = fluides.p_saturation("R449A", -30, "moyenne")
        self.assertIn("convention moyenne", p_moy.source)
        self.assertGreater(p_moy.nombre, fluides.p_saturation("R449A", -30, "rosee").nombre)
        self.assertLess(p_moy.nombre, fluides.p_saturation("R449A", -30, "bulle").nombre)
        self.assertAlmostEqual(fluides.t_saturation("R449A", p_moy, "moyenne").nombre, -30, places=4)
        self.assertGreater(fluides.glissement("R449A", 1.6).nombre, 3)
        self.assertEqual(fluides.glissement("R134a", 1.6).nombre, 0)

    def test_co2_sous_le_point_triple_refuse(self):
        with self.assertRaisesRegex(ValueError, "point triple"):
            fluides.p_saturation("CO2", -60)
        with self.assertRaisesRegex(ValueError, "point triple"):
            fluides.t_saturation("R744", 4.0)
        with self.assertRaisesRegex(ValueError, "point triple"):
            fluides.etat_aspiration("R744", -57, surchauffe_k=5)
        self.assertGreater(fluides.p_saturation("CO2", -50).nombre, 6)        # au-dessus : accepté

    def test_hors_domaine_refuse(self):
        with self.assertRaisesRegex(ValueError, "critique"):
            fluides.p_saturation("CO2", 40)                                     # transcritique
        with self.assertRaisesRegex(ValueError, "rosée"):
            fluides.etat_aspiration("R449A", -30, gaz_aspire_c=-40)            # gaz aspiré sous la rosée
        with self.assertRaises(ValueError):
            fluides.delta_h_evaporateur("R449A", 10, 5, surchauffe_k=10)        # Tc sous T0

    def test_entree_a_confirmer(self):
        r = fluides.p_saturation("R449A", a_confirmer("°C", "T0 absente"))
        self.assertIsNone(r.nombre)
        self.assertEqual(r.statut, A_CONFIRMER)
        r = fluides.p_saturation("R449A", Valeur(-30, "°C", "dicté", HYPOTHESE, id="t0"))
        self.assertEqual(r.statut, HYPOTHESE)
        self.assertEqual(r.entrees, ("t0",))


class TestM1(unittest.TestCase):
    def test_exemple_4he_negatif(self):
        r = m1_cylindree(vb(73.7), "R449A", t(-30), t(40), SURCHAUFFE_10, id="c1")
        self.assertAlmostEqual(r["q0"].nombre, 13.11, delta=13.11 * 0.02)
        self.assertEqual(r["q0"].statut, HYPOTHESE)
        self.assertEqual(r["q0"].id, "c1-m1")
        self.assertIn("table A", r["q0"].source)
        self.assertIn("CoolProp 8.0.0", r["q0"].source)
        self.assertTrue(r["q0"].formule)
        self.assertAlmostEqual(r["lambda"].nombre, 0.6650, places=3)

    def test_exemple_4ces_positif(self):
        r = m1_cylindree(vb(32.5), "R449A", t(-10), t(40), SURCHAUFFE_10)
        self.assertAlmostEqual(r["q0"].nombre, 16.89, delta=16.89 * 0.02)

    def test_variante_efpme(self):
        p = {**SURCHAUFFE_10, "lambda_methode": choix("efpme", "variante de test", HYPOTHESE, "l")}
        r = m1_cylindree(vb(73.7), "R449A", t(-30), t(40), p)
        self.assertAlmostEqual(r["q0"].nombre, 9.53, delta=0.05)              # puissance-existante.md § 8
        self.assertIn("EFPME", r["lambda"].source)

    def test_tau_hors_plage_a_confirmer(self):
        for t0, tc in ((-40, 50), (0, 10)):                                      # τ ≈ 21 et τ ≈ 1,4
            r = m1_cylindree(vb(73.7), "R449A", t(t0), t(tc))
            self.assertIsNone(r["q0"].nombre)
            self.assertEqual(r["q0"].statut, A_CONFIRMER)
            self.assertIn("hors du domaine", r["raison"])

    def test_co2_sous_point_triple_a_confirmer(self):
        r = m1_cylindree(vb(10), "CO2", t(-60), t(-10))
        self.assertIsNone(r["q0"].nombre)
        self.assertIn("point triple", r["raison"])


class TestM2(unittest.TestCase):
    def test_exemple_4he_conversion_r404a_r449a(self):
        r = m2_point_catalogue("4HE-18Y-40P", "R449A", t(-30), t(40), POINTS, SURCHAUFFE_10)
        self.assertAlmostEqual(r["q0"].nombre, 13.92, delta=13.92 * 0.02)
        self.assertEqual(r["q0"].statut, HYPOTHESE)
        self.assertEqual(r["cas"], "point exact")
        self.assertTrue(r["conversion"])
        self.assertEqual(r["q0_base"].nombre, point_csv("4HE-18Y-40P", "R404A", -30, 40))
        for morceau in ("conversion R404A → R449A", "λ table A", "KP-104-3", "p. ", "https://", "lu le 2026-10-06"):
            self.assertIn(morceau, r["q0"].source)

    def test_exemple_4ces_positif(self):
        r = m2_point_catalogue("4CES-6Y-40S", "R449A", t(-10), t(40), POINTS, SURCHAUFFE_10)
        self.assertAlmostEqual(r["q0"].nombre, 16.89, delta=16.89 * 0.02)

    def test_point_exact_r404a_lu_dans_le_csv(self):
        attendu = point_csv("4HE-18Y-40P", "R404A", -10, 40)
        r = m2_point_catalogue("4HE-18Y-40P", "R404A", t(-10), t(40), POINTS)
        self.assertAlmostEqual(r["q0"].nombre, attendu, places=9)
        self.assertFalse(r["conversion"])
        self.assertEqual(r["q0"].statut, HYPOTHESE)                                    # paramètres par défaut
        r = m2_point_catalogue("4HE-18Y-40P", "R404A", t(-10), t(40), POINTS, SOURCES)
        self.assertEqual(r["q0"].statut, CALCULE)                                      # tout sourcé : calculé

    def test_correction_exacte_des_conditions(self):
        # Même fluide, même régime, surchauffe 10 K au lieu du gaz aspiré 20 °C : rapport ρ1 × Δh seul, calculé.
        p = {**SOURCES, "gaz_aspire": None, "surchauffe": Valeur(10.0, "K", "réponse de test", SOURCE)}
        r = m2_point_catalogue("4HE-18Y-40P", "R404A", t(-10), t(40), POINTS, p)
        self.assertEqual(r["q0"].statut, CALCULE)
        self.assertLess(r["facteur"].nombre, 1)
        self.assertNotIn("lambda", r["etat_cible"])

    def test_interpolation_a_mi_chemin(self):
        m = "4HE-18Y-40P"
        r = m2_point_catalogue(m, "R404A", t(-27.5), t(40), POINTS)
        self.assertEqual(r["cas"], "interpolation")
        self.assertAlmostEqual(r["q0"].nombre, (point_csv(m, "R404A", -25, 40) + point_csv(m, "R404A", -30, 40)) / 2,
                               places=9)
        r = m2_point_catalogue(m, "R404A", t(-30), t(45), POINTS)
        self.assertAlmostEqual(r["q0"].nombre, (point_csv(m, "R404A", -30, 40) + point_csv(m, "R404A", -30, 50)) / 2,
                               places=9)
        r = m2_point_catalogue(m, "R404A", t(-27.5), t(45), POINTS, SOURCES)
        quatre = [point_csv(m, "R404A", a, b) for a in (-25, -30) for b in (40, 50)]
        self.assertAlmostEqual(r["q0"].nombre, sum(quatre) / 4, places=9)
        self.assertEqual(r["q0"].statut, CALCULE)

    def test_correction_de_regime_et_seuils(self):
        m = "4CES-6Y-40S"
        r = m2_point_catalogue(m, "R404A", t(-10), t(58), POINTS)                # 8 K du point −10 / 50
        self.assertEqual(r["cas"], "correction de régime")
        self.assertEqual(r["q0"].statut, HYPOTHESE)
        self.assertLess(r["q0"].nombre, point_csv(m, "R404A", -10, 50))
        r = m2_point_catalogue(m, "R404A", t(-10), t(62), POINTS)                # 12 K : au-delà de 10 K
        self.assertIsNone(r["q0"].nombre)
        self.assertIn("au-delà des seuils", r["raison"])
        # Grille privée des t0 ≤ −35 °C : −40 °C est à 10 K du point le plus proche (> 5 K) → refus ; −34 °C → corrigé
        tronques = [p for p in POINTS if p["modele"] == m and p["fluide"] == "R404A" and p["t_evaporation_c"] >= -30]
        r = m2_point_catalogue(m, "R404A", t(-40), t(40), tronques)
        self.assertIsNone(r["q0"].nombre)
        self.assertIn("au-delà des seuils", r["raison"])
        r = m2_point_catalogue(m, "R404A", t(-34), t(40), tronques)
        self.assertEqual(r["cas"], "correction de régime")
        self.assertIsNotNone(r["q0"].nombre)

    def test_hors_limites_d_application(self):
        r = m2_point_catalogue("4CES-6Y-40S", "R404A", t(-50), t(40), POINTS)
        self.assertIsNone(r["q0"].nombre)
        self.assertIn("limites d'application", r["raison"])

    def test_60_hz_refuse(self):
        a_60 = [{**p, "frequence_hz": 60.0} for p in POINTS if p["modele"] == "4HE-18Y-40P"]
        r = m2_point_catalogue("4HE-18Y-40P", "R449A", t(-30), t(40), a_60)
        self.assertIsNone(r["q0"].nombre)
        self.assertIn("60 Hz", r["raison"])

    def test_fluide_du_point_different_de_la_base_refuse(self):
        r407f = [p for p in POINTS if p["modele"] == "4HE-18Y-40P" and p["fluide"] == "R407F"]
        r = m2_point_catalogue("4HE-18Y-40P", "R449A", t(-30), t(40), r407f)
        self.assertIsNone(r["q0"].nombre)
        self.assertIn("R407F", r["raison"])
        self.assertIn("fluide de base annoncé", r["raison"])

    def test_conditions_de_reference_absentes_refusees(self):
        sans = [{**p, "gaz_aspire_c": None} for p in POINTS if p["modele"] == "4HE-18Y-40P"]
        r = m2_point_catalogue("4HE-18Y-40P", "R404A", t(-10), t(40), sans)
        self.assertIsNone(r["q0"].nombre)
        self.assertIn("conditions de référence", r["raison"])

    def test_pas_de_conversion_vers_le_co2(self):
        r = m2_point_catalogue("4HE-18Y-40P", "R744", t(-30), t(-5), POINTS)
        self.assertIsNone(r["q0"].nombre)
        self.assertIn("CO2", r["raison"])


class TestPuissanceCompresseur(unittest.TestCase):
    def entree(self, **autres):
        e = {"id": "c1", "modele": "4HE-18Y-40P", "fluide": "R449A", "t0": t(-30, "t0"), "tc": t(40, "tc"),
             "volume_balaye": Valeur(73.7, "m³/h", "plaque de test", SOURCE, id="c1-vb")}
        e.update(autres)
        return e

    def test_m2_retenue_et_ecart(self):
        r = puissance_compresseur(self.entree(), POINTS, SURCHAUFFE_10)
        self.assertEqual(r["regle"], "M2")
        self.assertEqual(r["retenue"].nombre, r["m2"]["q0"].nombre)
        self.assertIn("M2 si disponible, sinon M1", r["retenue"].source)
        self.assertAlmostEqual(r["ecart_sur_m2"].nombre, -5.8, delta=0.3)       # puissance-existante.md § 8
        self.assertFalse(r["ecart"]["depassement"])                               # sous le seuil de 15 %
        self.assertEqual(r["ecart"]["seuil"].nombre, 15.0)
        en_json(r)                                                                 # sérialisable pour 2-resultats.json

    def test_m1_retenue_si_m2_absente(self):
        r = puissance_compresseur(self.entree(modele="XYZ-0"), POINTS)
        self.assertEqual(r["regle"], "M1")
        self.assertEqual(r["retenue"].nombre, r["m1"]["q0"].nombre)
        self.assertIn("à confirmer par le fournisseur", r["retenue"].source)
        self.assertTrue(any("M2 indisponible" in a for a in r["alertes"]))

    def test_propagation_t0_a_confirmer(self):
        r = puissance_compresseur(self.entree(t0=a_confirmer("°C", "régime non dicté", id="t0")), POINTS)
        for v in (r["m1"]["q0"], r["m2"]["q0"], r["retenue"], r["ecart"]["ecart"]):
            self.assertIsNone(v.nombre)
            self.assertEqual(v.statut, A_CONFIRMER)
        self.assertIsNone(r["ecart"]["depassement"])
        self.assertEqual(r["regle"], "aucune")

    def test_frequence_60_hz_refusee(self):
        r = puissance_compresseur(self.entree(frequence=Valeur(60, "Hz", "plaque de test", SOURCE)), POINTS)
        self.assertIsNone(r["retenue"].nombre)
        self.assertIn("60 Hz", r["m1"]["raison"].replace(ESPACE, " "))

    def test_parametres_par_defaut_sources(self):
        p = parametres_par_defaut()
        self.assertEqual(p["convention"]["valeur"], "rosee")
        self.assertEqual(p["convention"]["statut"], HYPOTHESE)
        self.assertEqual(p["gaz_aspire"].nombre, 20.0)
        self.assertIsNone(p["surchauffe"])
        self.assertEqual(p["seuil_ecart"].texte(marque=False).replace(ESPACE, " "), "15,0 %")
        self.assertEqual(p["lambda_methode"]["valeur"], "table_a")
        for cle, v in p.items():
            if v is not None:
                self.assertTrue(v.source.strip() if isinstance(v, Valeur) else v["source"].strip(), cle)
        self.assertTrue(CHEMIN_POINTS_DEFAUT.is_file())


if __name__ == "__main__":
    unittest.main()
