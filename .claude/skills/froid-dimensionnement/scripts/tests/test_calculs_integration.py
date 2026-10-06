"""Test de bout en bout de calculs.py sur un dossier générique (noms fictifs, aucune donnée client).

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-dimensionnement/scripts/tests -v
Le dossier est créé dans un répertoire temporaire du système (rien n'est écrit dans le dépôt). Deux postes, trois
compresseurs : un lu « sûr » dont le modèle a un point catalogue public (4CES-6Y-40S, bitzer-r449a.csv), un
« illisible », un « douteux » sans point catalogue (M1 seule). Une source contient « | » pour vérifier l'échappement.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DOSSIER_SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DOSSIER_SCRIPTS))
import calculs  # noqa: E402
from valeur import A_CONFIRMER, HYPOTHESE, Valeur, a_confirmer, depuis_json, en_json  # noqa: E402

S, H = "sourcé", "hypothèse"


def v(n, u, src, st, id):
    return Valeur(n, u, src, st, id=id)


def entrees_generiques() -> dict:
    """Dossier fictif : 2 postes, 3 compresseurs (sûr avec point catalogue, illisible, douteux sans point)."""
    def regime(p, t0):
        return {"t0": v(t0, "°C", "dicté par Loïc le 2026-01-01 (essai)", S, f"{p}-t0"),
                "tc": v(40, "°C", "dicté par Loïc le 2026-01-01 (essai)", S, f"{p}-tc")}
    return {
        "format": "2-entrees v1",
        "dossier": "2026-01-01-client-fictif",
        "parametres": {"marge_pct": v(10, "%", "dicté par Loïc le 2026-01-01 (essai)", S, "param-marge")},
        "projet": {
            "texte": {"texte": "remplacer les deux groupes par une centrale CO2", "source": "dicté par Loïc le 2026-01-01",
                      "statut": S},
            "fluide_actuel": {"valeur": "R449A", "source": "rapport p. 2 | plaque photo p02-1", "statut": S,
                              "id": "fluide-actuel"},
            "fluide_cible": {"valeur": "R744", "source": "dicté par Loïc le 2026-01-01", "statut": S,
                             "id": "fluide-cible"},
            "type_equipement": {"poste-n": "groupe de condensation", "poste-p": "groupe de condensation"},
            "type_equipement_cible": "centrale",
            "precision": "remise de prix",
            "date_analyse": "2026-01-01",
        },
        "postes": [
            {"id": "poste-n", "nom": "Groupe négatif fictif",
             "dessert": {"texte": "chambre négative fictive", "source": "rapport p. 3", "statut": S},
             "temperature_chambre": v(-20, "°C", "dicté par Loïc le 2026-01-01", S, "n-t-chambre"),
             "volume": v(100, "m³", "rapport p. 3 | calcul 5 × 8 × 2,5", S, "n-volume"),
             "regime": regime("n", -30),
             "charge": v(20, "kg", "rapport p. 3", S, "n-charge"),
             "compresseurs": [
                 {"id": "n-c1", "marque": "Bitzer", "modele": "4CES-6Y-40S", "lecture": "sûre",
                  "volume_balaye": v(32.5, "m³/h", "photo p03-1 | plaque", S, "n-c1-vb"),
                  "frequence": v(50, "Hz", "photo p03-1", S, "n-c1-freq"),
                  "estimation": v(6.0, "kW", "estimation antérieure (essai)", H, "n-c1-estimation")},
                 {"id": "n-c2", "marque": "Bitzer", "modele": "", "lecture": "illisible",
                  "note": "plaque couverte de givre",
                  "volume_balaye": a_confirmer("m³/h", "photo p03-2 : plaque illisible", id="n-c2-vb")}],
             "evaporateurs": [{"id": "n-e1", "modele": "évaporateur fictif", "annee": "2010", "fluide_origine": "R404A",
                               "source": "photo p03-3"}],
             "plaques_ensemble": [],
             "estimations": [{"id": "n-estimation", "texte": "estimation antérieure fictive",
                              "puissance": v(12, "kW", "estimation antérieure (essai)", H, "n-estimation-kw")}]},
            {"id": "poste-p", "nom": "Groupe positif fictif",
             "dessert": {"texte": "chambre positive fictive", "source": "hypothèse : essai", "statut": H},
             "temperature_chambre": a_confirmer("°C", "non écrite dans le rapport", id="p-t-chambre"),
             "volume": v(50, "m³", "rapport p. 4", S, "p-volume"),
             "regime": regime("p", -10),
             "charge": a_confirmer("kg", "absente de la plaque", id="p-charge"),
             "compresseurs": [
                 {"id": "p-c1", "marque": "Fictif", "modele": "MODELE-FICTIF-1", "lecture": "douteuse",
                  "note": "dernier chiffre du modèle masqué",
                  "volume_balaye": v(20.0, "m³/h", "photo p04-1 ; lecture douteuse : dernier chiffre masqué", H,
                                     "p-c1-vb")}],
             "evaporateurs": [],
             "plaques_ensemble": [{"id": "p-plaque", "texte": "plaque d'ensemble fictive",
                                   "puissance": v(9, "kW", "photo p04-2", S, "p-plaque-kw"), "fluide": None,
                                   "regime": None}],
             "estimations": []},
        ],
    }


def ecrire(dossier: Path, entrees: dict) -> None:
    (dossier / calculs.ENTREES).write_text(en_json(entrees, indent=2), encoding="utf-8", newline="\n")


def lancer(*args) -> tuple[int, str]:
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = calculs.main([str(a) for a in args])
    return code, sortie.getvalue()


def colonnes(ligne: str) -> int:
    """Nombre de cellules d'une ligne de tableau markdown (les « \\| » échappés ne comptent pas)."""
    return len(re.findall(r"(?<!\\)\|", ligne)) - 1


class TestCalculsIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dossier = Path(cls._tmp.name) / "2026-01-01-client-fictif"
        cls.dossier.mkdir()
        ecrire(cls.dossier, entrees_generiques())
        cls.code, cls.sortie = lancer(cls.dossier)
        cls.tableaux = (cls.dossier / calculs.TABLEAUX).read_text(encoding="utf-8") if cls.code == 0 else ""
        cls.res = (depuis_json((cls.dossier / calculs.RESULTATS).read_text(encoding="utf-8"))
                   if cls.code == 0 else {})

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def poste(self, pid):
        return next(p for p in self.res["postes"] if p["id"] == pid)

    def comp(self, pid, cid):
        return next(c for c in self.poste(pid)["compresseurs"] if c["id"] == cid)

    def test_fichiers_produits_et_code_zero(self):
        self.assertEqual(self.code, 0, self.sortie)
        self.assertTrue((self.dossier / calculs.RESULTATS).is_file())
        self.assertTrue((self.dossier / calculs.TABLEAUX).is_file())
        self.assertEqual(self.res["format"], calculs.FORMAT_RESULTATS)
        for titre in ("## B. Puissance existante par compresseur", "## C. Besoins par poste", "## D. Fluide et conformité"):
            self.assertIn(titre, self.tableaux)
        self.assertNotIn("\r", (self.dossier / calculs.TABLEAUX).read_bytes().decode("utf-8"))

    def test_point_catalogue_m2_retenue(self):
        c = self.comp("poste-n", "n-c1")
        self.assertEqual(c["regle"], "M2")
        self.assertIsNotNone(c["m1"]["q0"].nombre)
        self.assertIsNotNone(c["m2"]["q0"].nombre)
        self.assertEqual(c["m2"]["cas"], "point exact")
        self.assertTrue(c["m2"]["conversion"])                     # point R404A converti au R449A
        self.assertEqual(c["retenue"].nombre, c["m2"]["q0"].nombre)

    def test_illisible_a_confirmer_et_somme_partielle(self):
        c = self.comp("poste-n", "n-c2")
        self.assertIsNone(c["retenue"].nombre)
        self.assertEqual(c["retenue"].statut, A_CONFIRMER)
        p = self.poste("poste-n")
        self.assertIsNone(p["existante"].nombre)                 # un compresseur à confirmer → poste à confirmer
        self.assertIsNone(p["demandee"].nombre)
        self.assertAlmostEqual(p["somme_partielle"].nombre, self.comp("poste-n", "n-c1")["retenue"].nombre)
        attendu = f"somme des 1 compresseur lu : {p['somme_partielle'].texte()}"
        self.assertIn(attendu, self.tableaux)
        ligne_c = next(l for l in self.tableaux.splitlines() if l.startswith("| Groupe négatif fictif |"))
        self.assertIn("| à confirmer |", ligne_c)                # la colonne « Puissance existante » reste à confirmer

    def test_douteuse_statut_hypothese_et_m1_seule(self):
        c = self.comp("poste-p", "p-c1")
        self.assertEqual(c["regle"], "M1")                        # pas de point catalogue pour ce modèle fictif
        self.assertEqual(c["retenue"].statut, HYPOTHESE)
        p = self.poste("poste-p")
        self.assertEqual(p["existante"].statut, HYPOTHESE)       # le statut se propage à la somme
        self.assertEqual(p["demandee"].statut, HYPOTHESE)
        self.assertAlmostEqual(p["demandee"].nombre, p["existante"].nombre * 1.1)   # marge 10 %
        self.assertIn("lecture douteuse", self.tableaux)
        self.assertIn("M2 indisponible, M1 seule", self.tableaux)

    def test_echappement_des_barres_verticales(self):
        self.assertIn("photo p03-1 \\| plaque", self.tableaux)
        for bloc in ("## B.", "## C.", "## D."):
            lignes = self.tableaux[self.tableaux.index(bloc):].splitlines()
            debut = next(i for i, l in enumerate(lignes) if l.startswith("|"))
            fin = next((i for i in range(debut, len(lignes)) if not lignes[i].startswith("|")), len(lignes))
            tableau = lignes[debut:fin]
            self.assertGreater(len(tableau), 2, bloc)
            self.assertEqual({colonnes(l) for l in tableau}, {colonnes(tableau[0])}, bloc)

    def test_bloc_d_et_mention_relecture(self):
        p = self.poste("poste-n")
        self.assertAlmostEqual(p["tco2e"].nombre, 20 * 1396 / 1000)
        self.assertIn("Table F-gas non relue", self.tableaux)
        self.assertIn("Projet : fluide cible", self.tableaux)
        self.assertIsNotNone(self.res["fluide_cible"])

    def test_estimation_par_compresseur(self):
        c = self.comp("poste-n", "n-c1")
        e = c["estimation"]
        m1, ret = c["m1"]["q0"].nombre, c["retenue"].nombre
        self.assertAlmostEqual(e["m1_sur_estimation"].nombre, (m1 - 6.0) / 6.0 * 100)
        self.assertAlmostEqual(e["retenue_sur_m1"].nombre, (ret - m1) / m1 * 100)
        self.assertAlmostEqual(e["retenue_sur_estimation"].nombre, (ret - 6.0) / 6.0 * 100)
        self.assertIn("## G-estimations.", self.tableaux)
        self.assertIsNone(self.comp("poste-p", "p-c1")["estimation"])

    def test_fluide_source_pas_de_variante(self):
        p = self.poste("poste-n")
        self.assertEqual(p["tco2e"].statut, "calculé")         # charge et PRP sourcés, fluide sourcé
        self.assertEqual(p["variantes_fluide"], [])
        self.assertNotIn("## G-variantes.", self.tableaux)

    def test_fluide_suppose_plafonne_fgas_et_variante(self):
        e = entrees_generiques()
        e["projet"]["fluide_actuel"] = {"valeur": "R449A", "statut": H, "id": "fluide-actuel",
                                        "source": "hypothèse : rapport p. 2, plaque d'origine au R404A"}
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            ecrire(d, e)
            code, sortie = lancer(d)
            self.assertEqual(code, 0, sortie)
            res = depuis_json((d / calculs.RESULTATS).read_text(encoding="utf-8"))
            tableaux = (d / calculs.TABLEAUX).read_text(encoding="utf-8")
        p = next(x for x in res["postes"] if x["id"] == "poste-n")
        self.assertEqual(p["tco2e"].statut, HYPOTHESE)          # jamais plus sûr que le fluide
        self.assertEqual(p["verdict"]["prp"].statut, HYPOTHESE)
        for cle in ("etancheite", "interdiction_entretien", "interdiction_mise_sur_le_marche"):
            self.assertEqual(p["verdict"][cle]["fiabilite"], HYPOTHESE, cle)
        ligne_d = next(l for l in tableaux[tableaux.index("## D."):].splitlines()
                       if l.startswith("| Groupe négatif fictif"))
        self.assertIn("(hyp.)", ligne_d.split(" | ")[5])         # cellule « Contrôle d'étanchéité »
        va = p["variantes_fluide"]                               # évaporateur n-e1 au R404A
        self.assertEqual([x["fluide"] for x in va], ["R404A"])
        self.assertAlmostEqual(va[0]["tco2e"].nombre, 20 * 3922 / 1000)
        self.assertEqual(va[0]["tco2e"].statut, HYPOTHESE)
        self.assertIn("## G-variantes.", tableaux)
        self.assertIn("était resté au R404A", tableaux)

    def test_plaque_au_fluide_d_origine_sans_conversion(self):
        e = entrees_generiques()
        poste = e["postes"][0]
        poste["compresseurs"] = poste["compresseurs"][:1]        # seulement n-c1 (4CES-6Y-40S, point catalogue R404A)
        poste["plaques_ensemble"] = [{"id": "n-plaque", "texte": "plaque d'ensemble fictive au R507",
                                      "puissance": v(7, "kW", "photo p03-4", S, "n-plaque-kw"),
                                      "fluide": {"valeur": "R507A", "source": "photo p03-4", "statut": S,
                                                 "id": "n-plaque-fluide"},
                                      "regime": None}]
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            ecrire(d, e)
            code, sortie = lancer(d)
            self.assertEqual(code, 0, sortie)
            res = depuis_json((d / calculs.RESULTATS).read_text(encoding="utf-8"))
            tableaux = (d / calculs.TABLEAUX).read_text(encoding="utf-8")
        pl = next(x for x in res["postes"] if x["id"] == "poste-n")["plaques"][0]
        self.assertEqual(pl["fluide"], "R507A")
        self.assertIsNotNone(pl["reference"].nombre)             # recalcul au R507A (conversion depuis le R404A)
        self.assertAlmostEqual(pl["sans_conversion"].nombre, pl["recalcul"][0]["q0_base"].nombre)
        self.assertIn("sans conversion", tableaux)
        self.assertIsNone(pl["depassement"])                     # régime de la plaque inconnu : indicatif

    def test_plaque_sans_regime_indicative(self):
        pl = self.poste("poste-p")["plaques"][0]
        self.assertIsNone(pl["depassement"])
        self.assertIn("indicatif", pl["portee"])
        self.assertIsNotNone(pl["ecart"].nombre)

    def test_meme_entree_meme_resultat(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            ecrire(d, entrees_generiques())
            self.assertEqual(lancer(d)[0], 0)
            self.assertEqual((d / calculs.TABLEAUX).read_text(encoding="utf-8"), self.tableaux)

    def test_verifier_n_ecrit_rien(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            ecrire(d, entrees_generiques())
            code, sortie = lancer(d, "--verifier")
            self.assertEqual(code, 0, sortie)
            self.assertFalse((d / calculs.RESULTATS).exists())
            self.assertFalse((d / calculs.TABLEAUX).exists())

    def test_incoherences_code_1(self):
        cas = {}
        e = entrees_generiques()
        e["postes"][1]["compresseurs"][0]["volume_balaye"] = v(20.0, "m³/h", "photo p04-1", S, "n-c1-vb")   # id en double
        cas["id en double"] = e
        e = entrees_generiques()
        e["postes"][1]["compresseurs"][0]["volume_balaye"] = v(20.0, "m³/h", "photo p04-1", S, "p-c1-vb")   # douteuse sourcée
        cas["douteuse sourcée"] = e
        e = entrees_generiques()
        e["postes"][0]["charge"] = v(20, "t", "rapport p. 3", S, "n-charge")                              # mauvaise unité
        cas["unité"] = e
        for nom, entrees in cas.items():
            with self.subTest(nom), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)
                ecrire(d, entrees)
                code, sortie = lancer(d)
                self.assertEqual(code, 1, sortie)
                self.assertIn("ERREUR", sortie)
                self.assertFalse((d / calculs.RESULTATS).exists())

    def test_valeur_invalide_et_fichier_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.assertEqual(lancer(d)[0], 2)                      # pas de 2-entrees.json
            (d / calculs.ENTREES).write_text("{ pas du json", encoding="utf-8")
            self.assertEqual(lancer(d)[0], 2)
            e = json.loads(en_json(entrees_generiques()))
            e["postes"][0]["charge"]["source"] = ""                # Valeur sans source
            (d / calculs.ENTREES).write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
            code, sortie = lancer(d)
            self.assertEqual(code, 1, sortie)
            self.assertIn("source vide", sortie)

    def test_ligne_de_commande(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            ecrire(d, entrees_generiques())
            env = dict(os.environ, PYTHONUTF8="1")
            r = subprocess.run([sys.executable, str(DOSSIER_SCRIPTS / "calculs.py"), str(d)], capture_output=True,
                               text=True, encoding="utf-8", env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("Groupe positif fictif", r.stdout)


if __name__ == "__main__":
    unittest.main()
