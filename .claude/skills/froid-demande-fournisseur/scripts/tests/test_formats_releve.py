"""Tests des corrections H2 (test « session neuve » du 2026-10-08) côté étape 3 : assembler.py ne perd plus un chiffre
en silence à cause de la forme de 1-existant.md ou de 2-entrees.json, et controler.py vérifie les légendes des plaques
contre le relevé et refuse les caractères invisibles.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-demande-fournisseur/scripts/tests -v
Dossiers entièrement fictifs (ceux de test_assembler.py et test_controler.py), dans un répertoire temporaire.
"""
from __future__ import annotations

import contextlib
import dataclasses
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent
for _chemin in (SCRIPTS, SCRIPTS.parents[1] / "froid-dimensionnement" / "scripts", TESTS):
    if str(_chemin) not in sys.path:
        sys.path.insert(0, str(_chemin))
import assembler  # noqa: E402
import controler as ctl  # noqa: E402
import test_assembler as ta  # noqa: E402
import test_controler as tc  # noqa: E402
from valeur import depuis_json, en_json  # noqa: E402


class TestSegmentsParIdentifiant(unittest.TestCase):
    """Légendes des vues du tableau D : par identifiant de photo d'abord, par position ensuite (avec avertissement)."""

    def test_photo_intermediaire_absente_ne_decale_plus(self):
        lu = ("armoire de régulation (`p14-1.jpeg`) ; régulateurs d'évaporateurs (`p14-2.jpeg`) ; "
              "afficheur Danfoss (`p14-3.jpeg`)")
        avert = []
        paires = assembler.segments_par_photo(lu, ["p14-1", "p14-3"], avert, "D")       # p14-2 manque à la ligne
        self.assertEqual([r for r, _ in paires], ["p14-1", "p14-3"])
        self.assertTrue(paires[0][1].startswith("armoire de régulation"))
        self.assertTrue(paires[1][1].startswith("afficheur Danfoss"))                   # par position : « régulateurs »
        self.assertEqual(avert, [])

    def test_segment_mot_guillemets_garde_sa_photo(self):
        lu = ("armoire de régulation (`p14-1.jpeg`) ; armoire « CENTRALE B » avec afficheur (`p14-2.jpeg`) ; "
              "écran (`p14-3.jpeg`)")
        paires = dict(assembler.segments_par_photo(lu, ["p14-1", "p14-2", "p14-3"]))
        self.assertTrue(paires["p14-2"].startswith("armoire « CENTRALE B »"))
        self.assertTrue(paires["p14-3"].startswith("écran"))

    def test_rapprochement_par_position_signale(self):
        avert = []
        paires = assembler.segments_par_photo("armoire de régulation ; armoire « CENTRALE B » avec afficheur",
                                              ["p14-1", "p14-2"], avert, "tableau D, « Régulation »")
        self.assertEqual(paires[0][1], paires[1][1])                                     # partage, comme avant
        self.assertEqual(len(avert), 1)
        self.assertIn("p14-1, p14-2 partagent la légende", avert[0])

    def test_comportement_sans_reference_inchange(self):
        self.assertEqual(assembler.segments_par_photo("Armoire 4 portes ; étiquette « 400 V » ; disjoncteur général",
                                                      ["p01-1", "p01-2"]),
                         [("p01-1", "Armoire 4 portes"), ("p01-2", "disjoncteur général")])


class TestSerieEvaporateur(unittest.TestCase):
    @staticmethod
    def releve(cellule: str) -> "assembler.Releve":
        md = ("## C. Chambres\n\n| Poste / chambre | Évaporateurs | Source |\n|---|---|---|\n"
              f"| Chambre fictive | {cellule} | rapport p. 3 ; photo p03-1 |\n")
        return assembler.lire_releve(md)

    def test_forme_attendue(self):
        r = self.releve("Fictair EVA-1 n° 5555/01, 2010, R404A (`p03-1.jpeg`)")
        self.assertEqual(assembler._serie_evaporateur(r, {"id": "e1", "modele": "Fictair EVA-1"}, ["p03-1"], 0),
                         ("5555/01", "", ""))

    def test_guillemets_lus_et_signales(self):
        for cellule in ("Fictair « EVA-1 » n° 5555/01, 2010", "Fictair EVA-1 n° « 5555/01 », 2010",
                        "Fictair **EVA-1** (n° 5555/01, 2010)"):
            serie, avert, erreur = assembler._serie_evaporateur(self.releve(cellule),
                                                                {"id": "e1", "modele": "Fictair EVA-1"}, ["p03-1"], 0)
            self.assertEqual((serie, erreur), ("5555/01", ""), cellule)
            if "«" in cellule:
                self.assertIn("format inattendu", avert)

    def test_numero_perdu_par_la_forme_est_une_erreur(self):
        serie, _, erreur = assembler._serie_evaporateur(self.releve("Fictair EVA-1 (n° (5555/01), 2010)"),
                                                        {"id": "e1", "modele": "Fictair EVA-1"}, ["p03-1"], 0)
        self.assertEqual(serie, "")
        self.assertIn("illisible pour le script", erreur)
        serie, _, erreur = assembler._serie_evaporateur(self.releve("Fictair EVA-1 (n° illisible), 2010"),
                                                        {"id": "e1", "modele": "Fictair EVA-1"}, ["p03-1"], 0)
        self.assertEqual(erreur, "")                                     # pas de numéro écrit : rien à signaler


class TestAssemblerFormats(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.dossier = ta.construire_dossier(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def lancer(self) -> tuple[int, str]:
        with contextlib.redirect_stdout(io.StringIO()) as sortie:
            code = assembler.main([str(self.dossier), "--variante", "grossiste", "--date", "2026-01-02"])
        return code, sortie.getvalue()

    def test_volume_sans_formule_alors_que_le_releve_a_les_cotes(self):
        chemin = self.dossier / "2-resultats.json"
        res = depuis_json(chemin.read_text(encoding="utf-8"))
        n = next(p for p in res["postes"] if p["id"] == "poste-n")
        n["volume"] = dataclasses.replace(n["volume"], formule="")
        chemin.write_text(en_json(res), encoding="utf-8")
        code, sortie = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("poste-n : surface « à confirmer » alors que 1-existant.md", sortie)
        self.assertIn("champ « formule »", sortie)
        self.assertFalse((self.dossier / "3-demande-fournisseur" / "v1" / "demande.json").exists())

    def test_numero_de_compresseur_perdu_est_une_erreur(self):
        md = (self.dossier / "1-existant.md").read_text(encoding="utf-8")
        md = md.replace("| `01-centrale-negative-fictive/p02-1.jpeg` | sûre | photo p02-1 |", "| ? | sûre | rapport p. 2 |")
        (self.dossier / "1-existant.md").write_text(md, encoding="utf-8")
        code, sortie = self.lancer()
        self.assertEqual(code, 1, sortie)
        self.assertIn("n-c1 : n° de série « non relevé » alors que 1-existant.md (tableau B", sortie)

    def test_guillemets_lus_signales_et_recopies_dans_demande_json(self):
        md = (self.dossier / "1-existant.md").read_text(encoding="utf-8")
        md = md.replace("Fictair **EVA-1** (n° 5555/01, 2010, R404A)", "Fictair « EVA-1 » (n° « 5555/01 », 2010, R404A)")
        (self.dossier / "1-existant.md").write_text(md, encoding="utf-8")
        code, sortie = self.lancer()
        self.assertEqual(code, 0, sortie)
        self.assertIn("attention : n-e1 : n° de série 5555/01 lu malgré un format inattendu", sortie)
        d = json.loads((self.dossier / "3-demande-fournisseur" / "v1" / "demande.json").read_text(encoding="utf-8"))
        legendes = [ph["legende"] for p in d["postes"] for ph in p["photos"]]
        self.assertTrue(any("Fictair EVA-1 · n° 5555/01" in x for x in legendes), legendes)
        self.assertTrue(any("n-e1 : n° de série 5555/01" in a for a in d["avertissements"]), d["avertissements"])
        self.assertEqual(assembler.verifier_schema(d), [])
        texte = json.dumps(d["avertissements"], ensure_ascii=False).lower()
        for ident in ta.IDENTIFIANTS:
            self.assertNotIn(ident, texte)

    def test_dessert_garde_son_statut(self):
        self.assertEqual(assembler._dessert({"dessert": {"texte": "chambre négative A", "statut": "hypothèse"}}),
                         "chambre négative A (hyp.)")
        self.assertEqual(assembler._dessert({"dessert": {"texte": "chambre A", "statut": "à confirmer"}}),
                         "chambre A (à confirmer)")
        self.assertEqual(assembler._dessert({"dessert": {"texte": "chambre A", "statut": "sourcé"}}), "chambre A")
        self.assertEqual(assembler._dessert({}), "à confirmer")
        res = depuis_json((self.dossier / "2-resultats.json").read_text(encoding="utf-8"))
        res["postes"][0]["dessert"]["statut"] = "hypothèse"
        (self.dossier / "2-resultats.json").write_text(en_json(res), encoding="utf-8")
        d = assembler.assembler(self.dossier, "grossiste", date="2026-01-02", ecrire=False)["demande"]
        self.assertTrue(d["postes"][0]["dessert"].endswith("(hyp.)"), d["postes"][0]["dessert"])

    def test_schema_accepte_un_demande_json_anterieur(self):
        d = assembler.assembler(self.dossier, "grossiste", date="2026-01-02", ecrire=False)["demande"]
        self.assertIn("avertissements", d)
        ancien = {k: v for k, v in d.items() if k != "avertissements"}
        self.assertEqual(assembler.verifier_schema(ancien), [])
        d["avertissements"] = [1]
        self.assertTrue(any("avertissements" in e for e in assembler.verifier_schema(d)))


class TestSqueletteEtape1(unittest.TestCase):
    """Le squelette de 1-existant.md écrit par extraire_rapport.py (étape 1) a la forme que lit l'étape 3."""

    def test_squelette_lisible_par_l_etape_3(self):
        chemin = str(SCRIPTS.parents[1] / "froid-releve-existant" / "scripts")
        if chemin not in sys.path:
            sys.path.insert(0, chemin)
        import extraire_rapport as er
        photos = {1: ["sources/photos/01-centrale-negative-a/p02-1.jpeg"],
                  2: ["sources/photos/02-regulation/p03-1.jpeg", "sources/photos/02-regulation/p03-2.jpeg"]}
        s = {"fiche": "IN99999", "client": {"nom": ta.CLIENT}, "intervention": {"date": "01/01/2026"},
             "sous_points": [
                 {"numero": 1, "titre": "CENTRALE NÉGATIVE À", "commentaire": ["2 compresseurs"], "pages": [2],
                  "photos": photos[1], "lu": {"compresseurs": {"valeur": 2, "source": "rapport p. 2"}}},
                 {"numero": 2, "titre": "RÉGULATION EXISTANTE", "commentaire": ["armoire"], "pages": [3],
                  "photos": photos[2], "lu": {}}],
             "photos": [{"fichier": f, "page": 2, "poste": "x", "largeur": 450, "hauteur": 600}
                        for f in photos[1] + photos[2]]}
        with tempfile.TemporaryDirectory() as tmp:
            er.ecrire_existant_md(Path(tmp), s)
            md = (Path(tmp) / "1-existant.md").read_text(encoding="utf-8")
        self.assertIn("| CENTRALE NÉGATIVE À |", md)                         # tableau A : titre tel quel
        self.assertIn("| Centrale négative A — compresseur 1/2 |", md)       # ailleurs : sans capitales forcées
        releve = assembler.lire_releve(md)
        self.assertEqual(len(releve.b), 2)
        self.assertEqual([assembler._col(l, "poste") for l in releve.b2], ["Centrale négative A"])
        d = next(l for l in releve.d if l["Élément"] == "Régulation existante")
        self.assertIn("Photo", d)                                             # colonne Photo explicite
        self.assertEqual(assembler._refs(assembler._col(d, "photo")), ["p03-1", "p03-2"])
        self.assertEqual(ctl.photos_citees(md), {})                           # rien à lire encore : aucune photo citée


class TestControleLegendes(tc.Base):
    """Contrôle 3 étendu : légendes fidèles à 1-existant.md, aucun caractère invisible."""

    def test_numero_remplace_par_non_releve(self):
        def abimer(d):
            d["postes"][0]["photos"][0]["legende"] = "Fictif X-100 · n° de série non relevé · 32,50 m³/h"
        r = self.controler(modifier=abimer)
        self.assertEchec(r[3], "p02-1", "n° de série « 1111111111 » (tableau B) absent", "remplacé par « non relevé »")

    def test_caractere_invisible_dans_une_legende(self):
        def abimer(d):
            d["postes"][0]["photos"][0]["legende"] = "Fictif X-100 · n° \x01 · 32,50 m³/h"
        r = self.controler(modifier=abimer)
        self.assertEchec(r[3], "caractère invisible U+0001", "n° de série « 1111111111 »")

    def test_releve_corrompu(self):
        self.controler()
        existant = self.dossier / "1-existant.md"
        existant.write_text(existant.read_text(encoding="utf-8").replace("1111111111", "\x01"), encoding="utf-8")
        r = tc.par_numero(ctl.controler(self.dossier, tc.VERSION))
        self.assertEchec(r[3], "1-existant.md, ligne", "caractère invisible U+0001")

    def test_numero_d_evaporateur_faux(self):
        def abimer(d):
            d["postes"][0]["photos"][2]["legende"] = "Fictair EVA-1 · n° 9999/99 · 2010 · puissance à confirmer"
        r = self.controler(modifier=abimer)
        self.assertEchec(r[3], "p03-1", "n° de série d'évaporateur « 5555/01 » (tableau C) absent")

    def test_legendes_fideles(self):
        r = self.controler()
        self.assertEqual(r[3].statut, ctl.OK, r[3].details)
        self.assertIn("3 légendes de plaques comparées au relevé", r[3].resume)


if __name__ == "__main__":
    unittest.main()
