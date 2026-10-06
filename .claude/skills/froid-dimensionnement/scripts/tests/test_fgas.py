"""Tests de fgas.py : PRP, PRP recalculé des mélanges, tCO2e, contrôle d'étanchéité, règles F-gas, verdicts.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-dimensionnement/scripts/tests -v
Bibliothèque standard uniquement (unittest). Les valeurs attendues sont relues dans les CSV du socle
(dimensionnement/savoir/fluides/), pas tirées de mémoire. Données génériques, aucune donnée client.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # dossier scripts/
import fgas  # noqa: E402
from valeur import A_CONFIRMER, CALCULE, ESPACE, HYPOTHESE, SOURCE, Valeur, a_confirmer, depuis_json, en_json  # noqa: E402

RACINE = Path(__file__).resolve().parents[5]                    # tests → scripts → skill → skills → .claude → racine
FLUIDES = RACINE / "dimensionnement" / "savoir" / "fluides"
DATE = "2026-10-06"


def lire_csv(nom: str, dossier: Path = FLUIDES) -> list[dict]:
    """Lecture indépendante de fgas.py (lignes de commentaire « # » ignorées)."""
    lignes = (dossier / nom).read_text(encoding="utf-8").splitlines()
    return list(csv.DictReader(l for l in lignes if not l.lstrip().startswith("#")))


PRP_CSV = {l["fluide"]: float(l["prp_100ans"]) for l in lire_csv("prp.csv")}
MELANGES = sorted({l["melange"] for l in lire_csv("compositions-melanges.csv")})
REGLES_CSV = lire_csv("reglementation-fgas.csv")


def kg(nombre, id="charge-test", statut=SOURCE):
    return Valeur(nombre, "kg", "plaque de test", statut, id=id)


def t(nombre):
    return Valeur(nombre, "tCO2e", "valeur de test", SOURCE, id="t-test")


def lisible(texte: str) -> str:
    return texte.replace(ESPACE, " ")


def regle_par_article(regles: list[dict], fragment: str) -> list[dict]:
    return [d for d in regles if fragment in d["article"]]


class TestChemins(unittest.TestCase):
    def test_racine_du_depot(self):
        self.assertEqual(fgas.DOSSIER_FLUIDES, FLUIDES)
        self.assertTrue((FLUIDES / "reglementation-fgas.csv").exists())

    def test_commentaire_en_tete_ignore(self):
        self.assertEqual(len(fgas.regles_table()), len(REGLES_CSV))
        self.assertTrue(fgas.regles_table()[0].regle.startswith("Entretien"))
        self.assertEqual(fgas.regles_table()[0].ligne, 3)          # ligne 1 : commentaire, ligne 2 : en-tête


class TestPrp(unittest.TestCase):
    def test_prp_lus_dans_prp_csv(self):
        for fluide in ("R404A", "R407C", "R449A", "R454C", "R744", "R290"):
            with self.subTest(fluide=fluide):
                self.assertEqual(fgas.prp(fluide).nombre, PRP_CSV[fluide])

    def test_valeurs_de_prp_csv_au_2026_10_06(self):
        # Valeurs de prp.csv (vague 1 · B) : R449A 1 396 et R454C 146 (HFO à leur PRP AR6, annexe II) ;
        # R290 0,02 (annexe VI, AR6) et non 3 (ancienne valeur AR4).
        attendu = {"R404A": 3922, "R407C": 1774, "R449A": 1396, "R454C": 146, "R744": 1, "R290": 0.02}
        for fluide, valeur in attendu.items():
            with self.subTest(fluide=fluide):
                self.assertEqual(fgas.prp(fluide).nombre, valeur)

    def test_statut_unite_source_id(self):
        p = fgas.prp("R404A")
        self.assertEqual(p.statut, SOURCE)
        self.assertEqual(p.unite, "")
        self.assertIn("prp.csv", p.source)
        self.assertIn("rapport GIEC : AR4", p.source)
        self.assertEqual(p.id, "prp-R404A")
        self.assertIn("référence : WMO 2018", fgas.prp("R600a").source)

    def test_noms_alternatifs(self):
        for nom in ("R-449A", "r449a", "R449A.mix", " R 449A "):
            self.assertEqual(fgas.prp(nom).nombre, PRP_CSV["R449A"])
        self.assertEqual(fgas.prp("CO2").nombre, PRP_CSV["R744"])
        self.assertEqual(fgas.prp("propane").nombre, PRP_CSV["R290"])
        self.assertEqual(fgas.prp("HFC-134a").nombre, PRP_CSV["R134a"])
        self.assertEqual(fgas.prp("R1234ze").nombre, PRP_CSV["R1234ze(E)"])

    def test_fluide_inconnu_a_confirmer_sans_exception(self):
        for nom in ("R999Z", "", None):
            with self.subTest(nom=nom):
                p = fgas.prp(nom)
                self.assertIsNone(p.nombre)
                self.assertEqual(p.statut, A_CONFIRMER)
                self.assertIn("absent de prp.csv", p.source)
        self.assertEqual(fgas.prp("R999Z").texte(), A_CONFIRMER)

    def test_rendu_du_prp(self):
        self.assertEqual(lisible(fgas.texte_prp(fgas.prp("R449A"))), "1 396")
        self.assertEqual(fgas.texte_prp(fgas.prp("R1234yf")), "0,501")
        self.assertEqual(fgas.texte_prp(fgas.prp("R290")), "0,02")
        self.assertEqual(fgas.texte_prp(fgas.prp("R744")), "1")
        self.assertEqual(fgas.texte_prp(fgas.prp("R999Z")), A_CONFIRMER)


class TestPrpMelange(unittest.TestCase):
    def test_tous_les_melanges_egaux_au_csv_a_1_pct(self):
        self.assertGreaterEqual(len(MELANGES), 10)
        for m in MELANGES:
            with self.subTest(melange=m):
                calc = fgas.prp_melange_calcule(m)
                self.assertEqual(calc.statut, CALCULE)
                self.assertLessEqual(abs(calc.nombre - PRP_CSV[m]) / PRP_CSV[m] * 100, 1.0)
                self.assertIn("dans la tolérance", calc.source)

    def test_r404a_formule_et_entrees(self):
        calc = fgas.prp_melange_calcule("R404A")
        self.assertAlmostEqual(calc.nombre, 0.44 * 3500 + 0.52 * 4470 + 0.04 * 1430, places=6)   # 3 921,6
        self.assertIn("x-R404A-R125", calc.entrees)
        self.assertIn("prp-R125", calc.entrees)
        self.assertIn("x-R404A-R125 × prp-R125", calc.formule)
        self.assertIn("annexe VI", calc.source)
        self.assertEqual(calc.id, "prp-calc-R404A")

    def test_fluide_pur_ou_inconnu_a_confirmer(self):
        for nom in ("R744", "R999Z"):
            with self.subTest(nom=nom):
                calc = fgas.prp_melange_calcule(nom)
                self.assertIsNone(calc.nombre)
                self.assertEqual(calc.statut, A_CONFIRMER)

    def test_ecart_superieur_a_1_pct_signale(self):
        with tempfile.TemporaryDirectory() as dossier:
            d = Path(dossier)
            for nom in ("compositions-melanges.csv", "reglementation-fgas.csv"):
                shutil.copy(FLUIDES / nom, d / nom)
            texte = (FLUIDES / "prp.csv").read_text(encoding="utf-8")
            self.assertIn("R404A,mélange,3922,", texte)
            (d / "prp.csv").write_text(texte.replace("R404A,mélange,3922,", "R404A,mélange,3800,"), encoding="utf-8")
            with mock.patch.object(fgas, "DOSSIER_FLUIDES", d):
                fgas.vider_cache()
                try:
                    calc = fgas.prp_melange_calcule("R404A")
                finally:
                    fgas.vider_cache()
        self.assertAlmostEqual(calc.nombre, 3921.6, places=6)
        self.assertIn("supérieur à la tolérance", calc.source)


class TestTco2e(unittest.TestCase):
    def test_215_kg_de_r449a(self):
        r = fgas.tco2e(kg(215), "R449A")
        self.assertAlmostEqual(r.nombre, 215 * PRP_CSV["R449A"] / 1000, places=9)
        self.assertAlmostEqual(r.nombre, 300.1, delta=0.05)
        self.assertEqual(r.unite, "tCO2e")
        self.assertEqual(r.statut, CALCULE)
        self.assertEqual(r.entrees, ("charge-test", "prp-R449A"))
        self.assertEqual(r.formule, "charge-test × prp-R449A ÷ 1000")
        self.assertEqual(lisible(r.texte()), "300,14 tCO2e")

    def test_charge_inconnue_propage_a_confirmer(self):
        r = fgas.tco2e(a_confirmer("kg", "absent de la plaque", id="charge-x"), "R449A")
        self.assertIsNone(r.nombre)
        self.assertEqual(r.statut, A_CONFIRMER)
        self.assertIn("bloqué par : charge-x", r.source)
        self.assertEqual(fgas.tco2e(None, "R449A").statut, A_CONFIRMER)

    def test_charge_hypothese_propagee(self):
        self.assertEqual(fgas.tco2e(kg(100, statut=HYPOTHESE), "R404A").statut, HYPOTHESE)

    def test_fluide_inconnu(self):
        r = fgas.tco2e(kg(10), "R999Z")
        self.assertIsNone(r.nombre)
        self.assertIn("prp-R999Z", r.source)

    def test_nombre_accepte_et_unite_refusee(self):
        self.assertAlmostEqual(fgas.tco2e(150, "R404A").nombre, 150 * PRP_CSV["R404A"] / 1000)
        with self.assertRaises(ValueError):
            fgas.tco2e(Valeur(0.2, "t", "test", SOURCE), "R404A")
        with self.assertRaises(ValueError):
            fgas.tco2e(-5, "R404A")


class TestEtancheite(unittest.TestCase):
    def test_seuils_lus_dans_la_table(self):
        self.assertEqual(fgas.seuil_controle_etancheite(t(10))["seuils"], [5.0, 50.0, 500.0])

    def test_tranches(self):
        cas = [(3, False, None, False), (5, True, 12, False), (49.9, True, 12, False), (50, True, 6, False),
               (300.14, True, 6, False), (500, True, 3, True), (1000, True, 3, True)]
        for valeur, soumis, mois, detection in cas:
            with self.subTest(tco2e=valeur):
                s = fgas.seuil_controle_etancheite(t(valeur))
                self.assertIs(s["soumis"], soumis)
                self.assertEqual(s["frequence_mois"], mois)
                self.assertIs(s["detection_fuites_obligatoire"], detection)
                self.assertTrue(s["texte"].startswith("Contrôle d'étanchéité"))

    def test_article_source_relecture(self):
        s = fgas.seuil_controle_etancheite(t(300.14))
        self.assertEqual(s["article"], "art. 5(6) b)")
        self.assertEqual(s["frequence_mois_avec_detection"], 12)
        self.assertIn("reglementation-fgas.csv ligne", s["source"])
        relue = all(l["relu_par"] for l in REGLES_CSV if l["article"].startswith("art. 5(6)"))
        if not relue:
            self.assertEqual(s["relecture"], fgas.MENTION_NON_RELUE)
        self.assertIn("art. 6(1)", fgas.seuil_controle_etancheite(t(600))["article"])

    def test_a_confirmer_sans_exception(self):
        s = fgas.seuil_controle_etancheite(fgas.tco2e(None, "R449A"))
        self.assertIsNone(s["soumis"])
        self.assertIn("à confirmer", s["texte"])

    def test_unite_refusee(self):
        with self.assertRaises(ValueError):
            fgas.seuil_controle_etancheite(kg(10))


class TestRegles(unittest.TestCase):
    def test_hfc_prp_2500_entretien_interdit_depuis_2025(self):
        self.assertGreaterEqual(PRP_CSV["R404A"], 2500)
        regles = fgas.regles_applicables("R404A", "centrale", 100, date=DATE)
        entretien = [d for d in regles if d["interdit_entretien"] and d["applicable"] is True]
        self.assertTrue(entretien)
        r = min(entretien, key=lambda d: d["date_effet"])
        self.assertEqual(r["date_effet"], "2025-01-01")
        self.assertEqual(r["statut"], "en vigueur")
        self.assertEqual(r["seuil_prp"], 2500)
        self.assertEqual(r["etat"], "en vigueur depuis le 1er janvier 2025")
        v = fgas.verdict_fluide("R404A", "centrale", 100, date=DATE)
        self.assertEqual(v["interdiction_entretien"]["statut"], "en vigueur")
        self.assertEqual(v["interdiction_entretien"]["date"], "2025-01-01")
        self.assertIn("1er janvier 2030", v["interdiction_entretien"]["texte"])      # tolérance régénéré/recyclé

    def test_meme_regle_a_venir_avant_2025(self):
        regles = fgas.regles_applicables("R404A", "groupe de condensation", 30, date="2024-06-01")
        r = [d for d in regles if d["interdit_entretien"] and d["date_effet"] == "2025-01-01"][0]
        self.assertEqual(r["statut"], "à venir")
        self.assertEqual(r["etat"], "à venir le 1er janvier 2025")

    def test_prp_inferieur_a_150_aucune_interdiction(self):
        for fluide in ("R454C", "R744"):
            self.assertLess(PRP_CSV[fluide], 150)
            for type_eq in ("centrale", "groupe de condensation", "chambre froide"):
                with self.subTest(fluide=fluide, type=type_eq):
                    regles = fgas.regles_applicables(fluide, type_eq, 100, date=DATE)
                    self.assertFalse([d for d in regles if d["interdit_entretien"] or d["interdit_mise_sur_le_marche"]])
                    v = fgas.verdict_fluide(fluide, type_eq, 100, date=DATE)
                    self.assertEqual(v["interdiction_entretien"]["statut"], "aucune")
                    self.assertEqual(v["interdiction_mise_sur_le_marche"]["statut"], "aucune")

    def test_source_article_et_mention_table_non_relue(self):
        relu = {i + 3: l["relu_par"] for i, l in enumerate(REGLES_CSV)}
        regles = fgas.regles_applicables("R449A", "centrale", 215, date=DATE)
        self.assertTrue(regles)
        for d in regles:
            with self.subTest(ligne=d["ligne"]):
                self.assertIn("source", d)
                self.assertIn("article", d)
                if not relu[d["ligne"]]:
                    self.assertEqual(d["relecture"], "table non relue")
        if any(not r for r in relu.values()):
            self.assertIn("non relue", fgas.verdict_fluide("R449A", "centrale", 215, date=DATE)["texte"])

    def test_relecture_renseignee(self):
        with tempfile.TemporaryDirectory() as dossier:
            d = Path(dossier)
            for nom in ("prp.csv", "compositions-melanges.csv"):
                shutil.copy(FLUIDES / nom, d / nom)
            lignes = (FLUIDES / "reglementation-fgas.csv").read_text(encoding="utf-8").splitlines()
            lignes = [l[:-2] + ",Relecteur,2026-11-01" if l.endswith(",,") and not l.startswith("#") else l
                      for l in lignes]
            (d / "reglementation-fgas.csv").write_text("\n".join(lignes) + "\n", encoding="utf-8")
            with mock.patch.object(fgas, "DOSSIER_FLUIDES", d):
                fgas.vider_cache()
                try:
                    regles = fgas.regles_applicables("R404A", "centrale", 100, date=DATE)
                    texte = fgas.verdict_fluide("R404A", "centrale", 100, date=DATE)["texte"]
                finally:
                    fgas.vider_cache()
        self.assertTrue(all(d["relecture"] == "relue par Relecteur le 2026-11-01" for d in regles))
        self.assertNotIn("non relue", texte)

    def test_centrale_et_capacite(self):
        sans = fgas.regles_applicables("R449A", "centrale", 215, date=DATE)
        self.assertEqual(regle_par_article(sans, "annexe IV point 6")[0]["conditions"], ["si capacité nominale ≥ 40 kW"])
        self.assertIsNone(regle_par_article(sans, "annexe IV point 5 c)")[0]["applicable"])
        grande = fgas.regles_applicables("R449A", "centrale", 215, date=DATE, capacite_kw=60)
        self.assertIs(regle_par_article(grande, "annexe IV point 6")[0]["applicable"], True)
        self.assertFalse(regle_par_article(grande, "annexe IV point 5"))
        petite = fgas.regles_applicables("R449A", "centrale", 215, date=DATE, capacite_kw=30)
        self.assertFalse(regle_par_article(petite, "annexe IV point 6"))
        self.assertIs(regle_par_article(petite, "annexe IV point 5 c)")[0]["applicable"], True)

    def test_groupe_de_condensation_point_5c(self):
        regles = fgas.regles_applicables("R449A", "groupe de condensation", 20, date=DATE)
        r = regle_par_article(regles, "annexe IV point 5 c)")[0]
        self.assertIs(r["applicable"], True)
        self.assertEqual(r["statut"], "à venir")
        self.assertFalse(regle_par_article(regles, "annexe IV point 6"))

    def test_charge_filtre_les_frequences(self):
        regles = fgas.regles_applicables("R449A", "centrale", 215, date=DATE)
        self.assertEqual([d["article"] for d in regle_par_article(regles, "art. 5(6)")], ["art. 5(6) b)"])
        self.assertFalse(regle_par_article(regles, "art. 6(1)"))
        inconnue = fgas.regles_applicables("R449A", "centrale", None, date=DATE)
        frequences = regle_par_article(inconnue, "art. 5(6)")
        self.assertEqual(len(frequences), 3)
        self.assertTrue(all("charge à confirmer" in " ".join(d["conditions"]) for d in frequences))

    def test_fluide_et_type_inconnus_sans_exception(self):
        regles = fgas.regles_applicables("R999Z", "centrale", 10, date=DATE)
        self.assertTrue(regles)
        # seule la règle de calcul (« Tous gaz et mélanges ») vise tout fluide ; les autres restent sous conditions
        self.assertTrue(all(d["applicable"] is None for d in regles if d["nature"] != fgas.NATURE_CALCUL))
        self.assertFalse([d for d in regles if d["interdit_entretien"] and d["applicable"] is True])
        self.assertTrue(fgas.regles_applicables("R449A", "machin inconnu", 10, date=DATE))

    def test_r22_hcfc(self):
        self.assertEqual(fgas.famille("R22"), fgas.HCFC)
        regles = fgas.regles_applicables("R22", "centrale", 50, date=DATE)
        self.assertEqual(sorted(d["nature"] for d in regles), [fgas.NATURE_UTILISATION, fgas.NATURE_CALCUL])
        r = [d for d in regles if d["nature"] == fgas.NATURE_UTILISATION][0]
        self.assertTrue(r["interdit_entretien"] and r["interdit_mise_sur_le_marche"])
        self.assertEqual(fgas.verdict_fluide("R22", "centrale", 50, date=DATE)["interdiction_entretien"]["statut"],
                         "sans date")

    def test_chaque_champ_d_application_est_interprete(self):
        for r in fgas.regles_table():
            with self.subTest(ligne=r.ligne):
                self.assertTrue(fgas._profil_champ(r.champ_application).interprete, r.champ_application)

    def test_synonymes_des_types_d_equipement(self):
        cas = {"centrale négative": (fgas.REFRIGERATION, fgas.CENTRALE),
               "groupe de condensation": (fgas.REFRIGERATION, fgas.GROUPE),
               "chambre froide": (fgas.REFRIGERATION, fgas.GROUPE),
               "froid commercial": (fgas.REFRIGERATION, None),
               "climatisation": (fgas.CLIMATISATION, None),
               "groupe d'eau glacée": (fgas.REFRIGERATION, fgas.REFROIDISSEUR),
               "meuble frigorifique": (fgas.REFRIGERATION, fgas.AUTONOME)}
        for texte, (fam, sous_type) in cas.items():
            with self.subTest(type=texte):
                eq = fgas.decrire_equipement(texte)
                self.assertTrue(eq.reconnu)
                self.assertEqual((eq.famille, eq.sous_type), (fam, sous_type))
        self.assertFalse(fgas.decrire_equipement("machin").reconnu)

    def test_familles_des_fluides(self):
        self.assertEqual(fgas.famille("R449A"), fgas.HFC)
        self.assertEqual(fgas.famille("R744"), fgas.NON_FLUORE)
        self.assertEqual(fgas.famille("R1234yf"), fgas.HFO)
        self.assertEqual(fgas.famille("R999Z"), A_CONFIRMER)
        for fluide in PRP_CSV:
            with self.subTest(fluide=fluide):
                self.assertNotEqual(fgas.famille(fluide), A_CONFIRMER)


class TestVerdict(unittest.TestCase):
    CLES = {"fluide", "fluide_connu", "famille", "type_fluide", "classe_securite", "equipement", "date", "prp",
            "charge", "tco2e", "etancheite", "interdiction_entretien", "interdiction_mise_sur_le_marche", "regles",
            "relecture", "texte"}

    def test_r449a_centrale_215_kg(self):
        v = fgas.verdict_fluide("R449A", "centrale", kg(215), date=DATE)
        self.assertEqual(set(v), self.CLES)
        self.assertEqual(v["prp"].nombre, PRP_CSV["R449A"])
        self.assertAlmostEqual(v["tco2e"].nombre, 300.1, delta=0.05)
        self.assertEqual(v["etancheite"]["frequence_mois"], 6)
        self.assertEqual(v["interdiction_entretien"]["statut"], "à venir")
        self.assertEqual(v["interdiction_entretien"]["date"], "2032-01-01")
        self.assertEqual(v["interdiction_mise_sur_le_marche"]["statut"], "sous conditions")
        self.assertTrue(3 <= len(v["texte"].splitlines()) <= 5, v["texte"])
        self.assertIn("300,14", lisible(v["texte"]))

    def test_r744_non_fluore(self):
        v = fgas.verdict_fluide("R744", "centrale", 150, date=DATE)
        self.assertEqual(v["famille"], fgas.NON_FLUORE)
        self.assertIs(v["etancheite"]["soumis"], False)
        self.assertTrue(3 <= len(v["texte"].splitlines()) <= 5, v["texte"])

    def test_fluide_inconnu(self):
        v = fgas.verdict_fluide("R999Z", "centrale", 10, date=DATE)
        self.assertFalse(v["fluide_connu"])
        self.assertEqual(v["prp"].statut, A_CONFIRMER)
        self.assertEqual(v["tco2e"].statut, A_CONFIRMER)
        self.assertEqual(v["interdiction_entretien"]["statut"], A_CONFIRMER)
        self.assertIn("à confirmer", v["texte"])
        self.assertTrue(3 <= len(v["texte"].splitlines()) <= 5, v["texte"])

    def test_json_aller_retour(self):
        v = fgas.verdict_fluide("R449A", "centrale", kg(215), date=DATE)
        relu = depuis_json(en_json(v))
        self.assertIsInstance(relu["prp"], Valeur)
        self.assertEqual(relu["tco2e"].nombre, v["tco2e"].nombre)
        self.assertEqual(relu["regles"][0]["relecture"], v["regles"][0]["relecture"])


class TestComparer(unittest.TestCase):
    def test_r449a_vers_r744(self):
        c = fgas.comparer_fluides("R449A", "R744", "centrale", 215, date=DATE)
        self.assertEqual(set(c), {"actuel", "cible", "rapport_prp", "variation_prp", "texte"})
        self.assertAlmostEqual(c["rapport_prp"].nombre, PRP_CSV["R744"] / PRP_CSV["R449A"], places=12)
        self.assertLess(c["variation_prp"].nombre, 0)
        self.assertEqual(c["rapport_prp"].entrees, ("prp-R744", "prp-R449A"))
        self.assertEqual(c["cible"]["charge"].statut, A_CONFIRMER)
        self.assertIn("R449A → R744", c["texte"])

    def test_cible_inconnue_sans_exception(self):
        c = fgas.comparer_fluides("R449A", "R999Z", "centrale", 215, date=DATE)
        self.assertEqual(c["rapport_prp"].statut, A_CONFIRMER)
        self.assertIn("non calculable", c["texte"])


class TestLigneDeCommande(unittest.TestCase):
    def lancer(self, *args):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            code = fgas.main(list(args))
        return code, sortie.getvalue()

    def test_verdict(self):
        code, sortie = self.lancer("R449A", "--type", "centrale", "--charge", "150", "--date", DATE)
        self.assertEqual(code, 0)
        self.assertIn("209,40 tCO2e", lisible(sortie))
        self.assertIn("Règles applicables", sortie)

    def test_comparaison(self):
        code, sortie = self.lancer("R449A", "--cible", "R744", "--type", "centrale", "--charge", "150", "--date", DATE)
        self.assertEqual(code, 0)
        self.assertIn("R449A → R744", sortie)

    def test_json(self):
        code, sortie = self.lancer("R449A", "--type", "centrale", "--charge", "150,5", "--json", "--date", DATE)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(sortie)["charge"]["nombre"], 150.5)


if __name__ == "__main__":
    unittest.main()
