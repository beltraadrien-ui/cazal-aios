"""Tests de generer.py sur une copie de la boucherie test : fichiers produits, plan-base.json (contrat du Lot 6),
plan.md lisible (sections dans l'ordre, aucun code de ligne, chambres et équipements en mots, métré par réseau en
noms et récapitulatif, croisements en mots, ce que mesure chaque cote, « (hyp.) »), metre-detail.md (mémoire :
codes, formules, croisements un par un), image du plan en pleine largeur dans plan.html, croisements injectés,
versions et journal, page « Métré » sans tableau coupé, modèle invalide (rien n'est écrit), chaîne complète avec
draw.io (sautée s'il est absent).

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -p "test_generer.py" -v
Données génériques (boucherie test fictive), aucune donnée client.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import croisements as crx  # noqa: E402
import drawio  # noqa: E402
import generer  # noqa: E402
import modele as mod  # noqa: E402
import outils_tests_plan as ot  # noqa: E402
import rendu  # noqa: E402
from echelle import PX_PAR_MM, choisir_echelle  # noqa: E402

SECTIONS = ("## Le plan", "## Ce que le plan contient", "## Métré", "### Froid : cuivres et condensats",
            "### Électricité (froid et clim)", "### Clim : cuivres", "### Récapitulatif", "## Croisements",
            "## Cotes relevées", "## Hauteurs de pose (hypothèses)", "## Questions ouvertes", "## Détails techniques")
CODES_DE_LIGNE = re.compile(r"\b(LA|LL|LCO|LE|LCG|LCL|CC)\d+\b")


def section(md: str, titre: str) -> str:
    """Texte d'une section « ## titre » jusqu'à la section ## suivante."""
    return md.split(f"## {titre}\n", 1)[1].split("\n## ", 1)[0].replace(" ", " ")


class TestGenererBoucherie(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dossier = Path(cls.tmp.name) / "plan"
        ot.ecrire_plan(cls.dossier, ot.charger_boucherie())
        cls.r = generer.generer(cls.dossier, rendu_pdf=False)
        cls.md = (cls.dossier / "plan.md").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_code_0_et_fichiers(self):
        self.assertEqual(self.r["code"], 0, self.r["erreurs"])
        for nom in ("plan.drawio", "plan.md", "plan.html", "metre-detail.md", "plan-base.json", "journal.md",
                    "versions/plan-v1.drawio", "versions/plan-v1.json"):
            self.assertTrue((self.dossier / nom).is_file(), nom)
        self.assertFalse((self.dossier / "plan.pdf").exists())          # --sans-rendu
        self.assertFalse((self.dossier / "metre-detail.html").exists())  # mémoire : jamais rendue

    def test_plan_base_contrat_lot6(self):
        base = json.loads((self.dossier / "plan-base.json").read_text(encoding="utf-8"))
        self.assertEqual(set(base), {"S", "orientation", "origine_mm"})
        ech = self.r["echelle"]
        self.assertEqual((base["S"], base["orientation"]), (ech.S, ech.orientation))
        self.assertAlmostEqual(base["origine_mm"][0], ech.origine_mm[0], places=3)
        self.assertAlmostEqual(base["origine_mm"][1], ech.origine_mm[1], places=3)
        # même correspondance que le dessin : (x, y) m → origine_mm + (x, y) × 1000 / S mm = m_vers_px / PX_PAR_MM
        for x, y in ((0, 0), (16, 11), (4.1, -1.2)):
            px = ech.m_vers_px(x, y)
            self.assertAlmostEqual(base["origine_mm"][0] + x * 1000 / base["S"], px[0] / PX_PAR_MM, places=3)
            self.assertAlmostEqual(base["origine_mm"][1] + y * 1000 / base["S"], px[1] / PX_PAR_MM, places=3)

    def test_echelle_lue_dans_le_dessin(self):
        L = drawio.lire(self.dossier / "plan.drawio")
        self.assertEqual(L.echelle.S, 100)
        self.assertEqual(L.echelle.orientation, "paysage")
        self.assertEqual(L.echelle.origine_px, self.r["echelle"].origine_px)

    def test_plan_md_sections_dans_l_ordre(self):
        self.assertTrue(self.md.startswith("<!-- titre: Plan : Boucherie test : plan froid et clim -->"))
        self.assertIn("\n# Boucherie test : plan froid et clim\n", self.md)
        self.assertIn("Dossier 2026-09-28-boucherie-test · relevé du 7 octobre 2026 · version 1 · échelle 1:100 · "
                      "A4 paysage", self.md)
        positions = [self.md.index(s + "\n") for s in SECTIONS]
        self.assertEqual(positions, sorted(positions))
        for ancienne in ("## Identité", "## Comment vérifier l'échelle", "## Calques", "## Journal des versions",
                         "Détail du calcul par ligne", "Métré par diamètre"):
            self.assertNotIn(ancienne, self.md)
        self.assertIn("Imprimer `plan.pdf` à 100 % (taille réelle). Sur le papier, la règle de contrôle du cartouche "
                      "doit mesurer 100 mm, et 1 m du bâtiment fait 1 cm.", self.md)

    def test_plan_md_sans_code_de_ligne(self):
        # les codes de lignes (LA1, LE1, CC1…) ne sont pas sur le plan : plan.md n'en montre aucun
        self.assertIsNone(CODES_DE_LIGNE.search(self.md), CODES_DE_LIGNE.search(self.md))
        self.assertNotIn("| De |", self.md)
        self.assertNotIn("(x ; y)", self.md)

    def test_ce_que_le_plan_contient(self):
        s = section(self.md, "Ce que le plan contient")
        self.assertIn("| Chambre | Dimensions | Régime / température | Évaporateur | Alimentée par |", s)
        self.assertIn("| Chambre positive viande (CF1) | 4,00 × 3,00 m | positif, +2 °C | Évaporateur CF1 (EV1) "
                      "| Centrale positive |", s)
        self.assertIn("| Chambre négative surgelés (CF3) | 2,50 × 2,50 m | négatif, −20 °C | Évaporateur CF3 (EV3) "
                      "| Groupe négatif |", s)
        # le code n'est entre parenthèses que s'il est écrit sur le plan (CP1 : non ; MS1 : oui)
        self.assertIn("- **Centrale positive** : à l'extérieur, en haut du plan, au droit de la chambre CF1", s)
        self.assertIn("- **TD-F (tableau froid)** : dans « Laboratoire de découpe »", s)
        self.assertIn("- **Split cuisine** : dans « Cuisine »", s)
        self.assertIn("- **Moteur multi-split (MS1)** : à l'extérieur, à droite du plan", s)
        self.assertNotIn("Comptoir", s)                                  # équipement « autre » : hors étude froid

    def test_plan_md_cotes_et_questions(self):
        s = section(self.md, "Cotes relevées")
        self.assertIn("| Cote | Longueur | Ce qu'elle mesure | Source |", s)
        self.assertIn("| CT1 | 16,00 m | mur M3, façade du bas | télémètre |", s)
        self.assertIn("| CT2 | 11,00 m | mur M4, façade de gauche | télémètre |", s)
        self.assertIn("| CT3 | 3,20 m | profondeur de la pièce « Vestiaire et sanitaires » | télémètre |", s)
        self.assertIn("| CT6 | 2,80 m | largeur de la pièce « Plonge » | télémètre |", s)
        self.assertIn("| CT8 | 4,00 m | largeur de la chambre CF1 | télémètre |", s)
        q = section(self.md, "Questions ouvertes")
        self.assertIn("- Les condensats de l'évaporateur CF1 (EV1) s'arrêtent à l'extérieur, en haut du plan, au droit "
                      "de la chambre CF1 : où se raccordent-ils (siphon, descente, regard) ?", q)
        self.assertIn("question 13", q)
        self.assertIn("(20 lignes)", q)

    def test_hypotheses_marquees(self):
        s = section(self.md, "Métré")
        self.assertIn("| Tronçon | Type | En plan (m) | Montées et descentes (m) | Total (m) |", s)
        # longueur en plan : jamais une hypothèse ; montées, descentes et total : « (hyp.) »
        self.assertIn("| Évaporateur CF1 (EV1) → Centrale positive | Aspiration | 1,81 | 2,40 (hyp.) | 4,21 (hyp.) |", s)
        self.assertIn("| Évaporateur CF1 (EV1) → évacuation à préciser | Condensats | 0,79 | 2,20 (hyp.) | 2,99 (hyp.) |", s)
        self.assertIn("| **Total** |  | **15,02** | **21,00 (hyp.)** | **36,02 (hyp.)** |", s)
        self.assertIn("Les montées et descentes utilisent les hauteurs de pose ci-dessous, à valider (question 13) : "
                      "les totaux sont marqués (hyp.) tant qu'elles ne le sont pas. Les diamètres sont à définir par "
                      "le dimensionnement.", s)
        h = section(self.md, "Hauteurs de pose (hypothèses)")
        self.assertIn("| Élément | Hauteur | Statut |", h)
        self.assertIn("| Tableau électrique | 1,50 m | hypothèse |", h)

    def test_metre_electricite_et_recapitulatif(self):
        s = section(self.md, "Métré")
        self.assertIn("| Tronçon | Type | En plan (m) | dont chemin de câbles (m) | Montées et descentes (m) | "
                      "Réserve (m) | Total (m) |", s)
        # câble arrêté sur le chemin : en plan = 1,60 + 10,10 dans le chemin ; 11,70 + 3,60 + 1,00 = 16,30
        self.assertIn("| Centrale positive → TD-F (tableau froid), par le chemin de câbles | Câble C1 | 11,70 | 10,10 "
                      "| 3,60 (hyp.) | 1,00 (hyp.) | 16,30 (hyp.) |", s)
        self.assertIn("| Le chemin lui-même, depuis TD-F (tableau froid) | Chemin de câbles | 10,50 |  | 0,00 |  "
                      "| 10,50 |", s)
        self.assertIn("| **Total** |  | **61,88** | **35,94** | **18,00 (hyp.)** | **7,00 (hyp.)** | "
                      "**86,88 (hyp.)** |", s)
        recap = s.split("### Récapitulatif", 1)[1]
        for rang in ("| Froid : cuivres et condensats | 36,02 (hyp.) |", "| Électricité (froid et clim) | 86,88 (hyp.) |",
                     "| Clim : cuivres | 13,12 (hyp.) |"):
            self.assertIn(rang, recap)
        self.assertNotIn("Diamètre", s)                                  # tous « à définir » : pas de colonne

    def test_croisements_en_mots(self):
        s = section(self.md, "Croisements")
        self.assertIn("3 endroits où des réseaux se croisent (sur le chantier, l'un passe au-dessus de l'autre), "
                      "repérés G1 à G3 sur le plan :", s)
        self.assertIn("- **G1**, dans « Laboratoire de découpe » : l'aspiration, le liquide et les condensats de "
                      "l'évaporateur CF1 (EV1) croisent le chemin de câbles.", s)
        self.assertIn("- **G3**, dans « Laboratoire de découpe » : l'aspiration, le liquide et les condensats de "
                      "l'évaporateur CF3 (EV3) croisent le chemin de câbles.", s)
        self.assertNotIn("| X", s)

    def test_details_techniques_courts(self):
        s = section(self.md, "Détails techniques")
        lignes = [l for l in s.splitlines() if l.strip()]
        self.assertLessEqual(len(lignes), 10)
        self.assertIn("`metre-detail.md`", s)
        self.assertIn("Calques (draw.io, menu Affichage > Calques) : Plan de base, Cotes,", s)
        self.assertIn("· v1 ·", s)

    def test_croisements_injectes_dans_le_dessin(self):
        # C : un cercle par GROUPE de croisements (≤ 0,50 m de proche en proche), repères G1…
        L = drawio.lire(self.dossier / "plan.drawio")
        ellipses = {e["id"]: e for e in L.elements.values() if e["type"] == "croisement"}
        attendus = crx.regrouper(crx.croisements(ot.charger_boucherie()))
        self.assertEqual(len(crx.croisements(ot.charger_boucherie())), 9)
        self.assertEqual(len(ellipses), len(attendus))
        self.assertEqual(len(ellipses), 3)
        for g in attendus:
            self.assertLess(((ellipses[g["id"]]["centre_m"][0] - g["point"][0]) ** 2
                             + (ellipses[g["id"]]["centre_m"][1] - g["point"][1]) ** 2) ** 0.5, 0.01)
        self.assertNotIn("croisements", json.loads((self.dossier / "plan.json").read_text(encoding="utf-8")))

    def test_etiquette_de_groupe_a_cote_du_cercle(self):
        L = drawio.lire(self.dossier / "plan.drawio")
        textes = {e["texte"]: e for e in L.elements.values() if e.get("parent_element") in ("G1", "G2", "G3")}
        self.assertEqual(set(textes), {"X1-X3", "X4-X6", "X7-X9"})
        for t in textes.values():
            cercle = L.elements[t["parent_element"]]
            self.assertEqual(t["calque"], "croisements")
            cx, cy = cercle["centre_px"]
            r = cercle["dimensions_px"][0] / 2
            x0, y0, x1, y1 = t["boite_px"]
            plus_proche = (min(max(cx, x0), x1), min(max(cy, y0), y1))     # point de la boîte le plus proche du centre
            d = ((plus_proche[0] - cx) ** 2 + (plus_proche[1] - cy) ** 2) ** 0.5
            self.assertGreater(d, r, t["texte"])                            # à côté, pas sur le cercle
            self.assertLess(d, r + 50.0, t["texte"])                        # mais tout près

    def test_tableau_croisements_par_croisement_avec_repere(self):
        detail = (self.dossier / "metre-detail.md").read_text(encoding="utf-8")
        section = detail.split("## Croisements et recouvrements", 1)[1].split("## Calques", 1)[0]
        self.assertIn("| N° | Repère | Point (x ; y) | Lignes | Calques |", section)
        rangs = [l for l in section.splitlines() if l.startswith("| X")]
        self.assertEqual(len(rangs), 9)
        self.assertTrue(rangs[0].startswith("| X1 | G1 |"))
        self.assertTrue(rangs[8].startswith("| X9 | G3 |"))
        L = drawio.lire(self.dossier / "plan.drawio")
        html = dict(L.tableaux)[generer.TITRE_TABLEAU_CROISEMENTS]
        self.assertIn("Repère", html)
        self.assertEqual(html.count("<tr>"), 1 + 9)

    def test_page_metre_tableaux(self):
        L = drawio.lire(self.dossier / "plan.drawio")
        titres = [t for t, _ in L.tableaux]
        self.assertEqual(titres, ["Métré par réseau", "Métré par diamètre", "Hauteurs utilisées",
                                  generer.TITRE_TABLEAU_CROISEMENTS])

    def test_page_metre_aucun_tableau_coupe(self):
        L = drawio.lire(self.dossier / "plan.drawio")
        page = next(p for p in L.pages if p["id"] == "metre")
        h = page["hauteur_px"]
        for c in page["cellules"]:
            if c["id"] and c["id"].startswith("metre-tableau-") and not c["id"].endswith("-titre"):
                g = c["geometrie"]
                self.assertEqual(int(g["y"] // h), int((g["y"] + g["height"] - 1e-6) // h), c["id"])

    def test_metre_detail_memoire(self):
        detail = (self.dossier / "metre-detail.md").read_text(encoding="utf-8").replace(" ", " ")
        for titre in ("## Métré par réseau", "## Détail du calcul par ligne", "## Métré par diamètre",
                      "## Hauteurs utilisées", "## Croisements et recouvrements", "## Calques", "## Notes du relevé"):
            self.assertIn(titre, detail)
        self.assertIn("| Froid – cuivres et condensats | LA1 | EV1 → CP1 | Aspiration | 1,81 | 0,00 | 2,40 (hyp.) | "
                      "0,00 | 4,21 (hyp.) | à définir |", detail)
        self.assertIn("- **LE1** (Câble, CP1 → CC1) : 1,60 m en plan + 10,10 m dans le chemin de câbles CC1 jusqu'à "
                      "TD + |2,80 − 0,50| + |2,80 − 1,50| + 1,00 m de réserve = 16,30 m", detail)
        self.assertIn("| à définir | Câble | 76,38 (hyp.) | LE1, LE2, LE3, LE4, LE5, LE6, LE7 |", detail)

    def test_plan_html_produit(self):
        html = (self.dossier / "plan.html").read_text(encoding="utf-8")
        self.assertIn("<title>Plan : Boucherie test", html)
        self.assertIn('class="hyp"', html)
        # sans rendu : pas d'image du plan (elle serait périmée), une phrase le dit
        self.assertNotIn("<img", html)
        self.assertIn("Image du plan non produite à cette génération", self.md)


class TestGenererCas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_deuxieme_generation_version_2_et_journal(self):
        d = self.racine / "plan"
        ot.ecrire_plan(d, ot.charger_boucherie())
        generer.generer(d, rendu_pdf=False)
        r = generer.generer(d, rendu_pdf=False)
        self.assertEqual(r["version"], 2)
        self.assertTrue((d / "versions" / "plan-v2.drawio").is_file())
        journal = [l for l in (d / "journal.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
        self.assertEqual(len(journal), 2)
        self.assertIn("· v2 ·", journal[1])
        self.assertIn(journal[1], (d / "plan.md").read_text(encoding="utf-8"))

    def test_modele_invalide_rien_n_est_ecrit(self):
        donnees = ot.charger_boucherie()
        donnees["cotes"][0]["valeur"] = 16.5                       # cote incohérente avec de/a
        d = self.racine / "plan"
        ot.ecrire_plan(d, donnees)
        r = generer.generer(d, rendu_pdf=False)
        self.assertEqual(r["code"], 1)
        self.assertIn("CT1", r["erreurs"][0])
        self.assertFalse((d / "plan.drawio").exists())
        self.assertFalse((d / "versions").exists())

    def test_plan_json_absent(self):
        r = generer.generer(self.racine / "vide", rendu_pdf=False)
        self.assertEqual(r["code"], 1)

    def test_echelle_imposee_impossible(self):
        donnees = ot.charger_boucherie()
        donnees["page"]["echelle"] = 50
        d = self.racine / "plan"
        ot.ecrire_plan(d, donnees)
        r = generer.generer(d, rendu_pdf=False)
        self.assertEqual(r["code"], 1)
        self.assertIn("1:50", r["erreurs"][0])

    def test_hauteurs_validees_sans_hyp(self):
        donnees = ot.charger_boucherie()
        donnees["hauteurs_validees"] = True
        d = self.racine / "plan"
        ot.ecrire_plan(d, donnees)
        generer.generer(d, rendu_pdf=False)
        md = (d / "plan.md").read_text(encoding="utf-8")
        self.assertNotIn("(hyp.)", md.split("## Métré", 1)[1].split("## Croisements", 1)[0])
        self.assertIn("validée", md)
        self.assertNotIn("question 13", md)
        self.assertIn("Les montées et descentes utilisent les hauteurs de pose ci-dessous, validées.", md)
        self.assertIn("## Hauteurs de pose\n", md)

    def test_image_du_plan_en_pleine_largeur(self):
        """Avec un rendu : `![Plan](plan.png)` dans plan.md ; dans plan.html, chemin relatif, pleine largeur,
        lien vers l'image en taille réelle."""
        from unittest import mock
        d = self.racine / "plan"
        ot.ecrire_plan(d, ot.charger_boucherie())
        info = {"voie": "drawio", "facteur_s": 1.002457, "regle_pt": 283.4646, "ecart_pct": 0.0, "pdf": d / "plan.pdf",
                "png": d / "plan.png", "avertissements": []}
        with mock.patch.object(generer.rendu, "rendre", return_value=info):
            r = generer.generer(d)
        self.assertEqual(r["code"], 0, r["erreurs"])
        md = (d / "plan.md").read_text(encoding="utf-8")
        self.assertIn("## Le plan\n\n![Plan](plan.png)\n", md)
        self.assertIn("règle de 100 mm mesurée dans le PDF : 100,000 mm", md)
        html = (d / "plan.html").read_text(encoding="utf-8")
        self.assertEqual(html.count("<img"), 1)
        self.assertIn('<a href="plan.png" target="_blank"', html)
        self.assertRegex(html, r'<img alt="Plan" src="plan\.png" style="display:block;width:100%;height:auto;')

    def test_versions_limitees_aux_cinq_dernieres(self):
        d = self.racine / "plan"
        ot.ecrire_plan(d, ot.charger_boucherie())
        for _ in range(6):
            generer.generer(d, rendu_pdf=False)
        md = (d / "plan.md").read_text(encoding="utf-8")
        s = md.split("## Détails techniques\n", 1)[1]
        self.assertIn("- Versions (les 5 dernières ; toutes dans `journal.md`) :", s)
        self.assertNotIn("· v1 ·", s)
        self.assertIn("· v6 ·", s)
        self.assertLessEqual(len([l for l in s.splitlines() if l.strip()]), 10)

    def test_ligne_cli(self):
        d = self.racine / "plan"
        ot.ecrire_plan(d, ot.charger_boucherie())
        with contextlib.redirect_stdout(io.StringIO()) as sortie:
            self.assertEqual(generer.main([str(d), "--sans-rendu"]), 0)
        self.assertIn("Plan v1 : échelle 1:100", sortie.getvalue())
        self.assertTrue((d / "plan.drawio").is_file())

    def test_rendu_impossible_code_1_fichiers_ecrits(self):
        import os
        from unittest import mock
        d = self.racine / "plan"
        ot.ecrire_plan(d, ot.charger_boucherie())
        with mock.patch.dict(os.environ, {"FROID_PLAN_DRAWIO": "aucun"}):
            r = generer.generer(d, voie="drawio")
        self.assertEqual(r["code"], 1)
        self.assertIn("Rendu", r["erreurs"][0])
        self.assertTrue((d / "plan.md").is_file())
        self.assertIn("rendu en échec", (d / "journal.md").read_text(encoding="utf-8"))


class TestVueLisible(unittest.TestCase):
    """Les mots de plan.md : noms, emplacements, ce que mesure une cote, sources, descriptions de lignes."""

    @classmethod
    def setUpClass(cls):
        cls.vue = generer.Vue(mod.depuis_dict(ot.charger_boucherie()))

    def test_noms_avec_code_seulement_s_il_est_sur_le_plan(self):
        self.assertEqual(self.vue.nom("EV1"), "Évaporateur CF1 (EV1)")         # étiquette « EV1 · C3 »
        self.assertEqual(self.vue.nom("CP1"), "Centrale positive")             # étiquette sans « CP1 »
        self.assertEqual(self.vue.nom("TD"), "TD-F (tableau froid)")           # « TD-F » n'est pas le code « TD »
        self.assertEqual(self.vue.nom("CF3"), "Chambre négative surgelés (CF3)")
        self.assertEqual(self.vue.nom_article("EV1"), "l'évaporateur CF1 (EV1)")
        self.assertEqual(self.vue.nom_article("CP1"), "la centrale positive")
        self.assertEqual(self.vue.nom_article("GR1"), "le groupe négatif")

    def test_description_de_lignes(self):
        self.assertEqual(self.vue.decrire_lignes(["LCO1", "LA1", "LL1"]),
                         ("l'aspiration, le liquide et les condensats de l'évaporateur CF1 (EV1)", True))
        self.assertEqual(self.vue.decrire_lignes(["LE1"]), ("le câble C1 de la centrale positive", False))
        self.assertEqual(self.vue.decrire_lignes(["CC1"]), ("le chemin de câbles", False))

    def test_lieux(self):
        self.assertEqual(self.vue.lieu((2.0, 2.0)), "dans la chambre CF1")
        self.assertEqual(self.vue.lieu((15.0, 1.0)), "dans « WC »")                # la plus petite pièce
        self.assertEqual(self.vue.lieu((17.0, 5.0)), "à l'extérieur, à droite du plan, au droit de « Cuisine »")
        self.assertEqual(self.vue.lieu((8.6, -1.1)), "à l'extérieur, en haut du plan, au droit de la chambre CF3")

    def test_ce_que_mesure_une_cote(self):
        cote = lambda de, a: {"id": "CTX", "de": de, "a": a, "valeur": 1.0}  # noqa: E731
        self.assertEqual(self.vue.ce_que_mesure(cote([16, 0], [0, 0])), "mur M1, façade du haut")
        self.assertEqual(self.vue.ce_que_mesure(cote([10.1, 3.45], [15.8, 3.45])), "cloison M6")
        self.assertEqual(self.vue.ce_que_mesure(cote([7.3, 0.4], [7.3, 2.9])), "profondeur de la chambre CF3")
        self.assertEqual(self.vue.ce_que_mesure(cote([1.0, 1.0], [3.0, 2.5])), "entre deux points du plan")

    def test_sources_et_formats(self):
        self.assertEqual(generer.source_en_mots("telemetre"), "télémètre")
        self.assertEqual(generer.source_en_mots("télémètre, dicté par Loïc le 2026-10-07"), "télémètre")
        self.assertEqual(generer.source_en_mots("plan architecte p. 2, cote écrite"), "plan d'architecte (p. 2)")
        self.assertEqual(generer.source_en_mots("croquis sources/c1.jpeg, cote écrite"), "croquis")
        self.assertEqual(generer.source_en_mots(None), "non précisée")
        self.assertEqual(generer.date_fr("2026-10-07"), "7 octobre 2026")
        self.assertEqual(generer.nombre_court(100 / 75), "1,33")
        self.assertEqual(generer.nombre_court(100 / 100), "1")
        self.assertEqual(generer.nombre_court(100 / 200), "0,5")


@unittest.skipIf(rendu.trouver_drawio() is None, "draw.io Desktop absent : chaîne complète non testée")
class TestChaineComplete(unittest.TestCase):
    def test_generer_avec_rendu(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "plan"
            ot.ecrire_plan(d, ot.charger_boucherie())
            r = generer.generer(d)
            self.assertEqual(r["code"], 0, r["erreurs"])
            self.assertEqual(r["rendu"]["voie"], "drawio")
            self.assertTrue((d / "plan.pdf").is_file() and (d / "plan.png").is_file())
            md = (d / "plan.md").read_text(encoding="utf-8")
            self.assertIn("règle de 100 mm mesurée dans le PDF : 100,0", md)
            self.assertIn("![Plan](plan.png)", md)
            self.assertIn('src="plan.png"', (d / "plan.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
