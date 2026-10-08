"""Tests du métré (metre.py) : cas calculés à la main, défauts par type, surcharges, totaux, format français, HTML.

Usage, depuis la racine du dépôt :
    python -m pytest .claude/skills/froid-plan-2d/scripts/tests/test_metre.py -q
ou, sans pytest (bibliothèque standard) :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -p "test_metre.py" -v
Données génériques (fixtures « a2-* »), aucune donnée client.
"""
from __future__ import annotations

import copy
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # dossier scripts/
from metre import (A_DEFINIR, ESPACE, HYPOTHESE, IMPOSEE_CALQUE, IMPOSEE_EQUIPEMENT, IMPOSEE_LIGNE,  # noqa: E402
                   PHRASE_LONGUEURS, VALIDEE, ErreurMetre, arrondi, longueur_fr, metrer, nombre_fr,
                   normaliser_diametre)
import metre as mtr  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
NB = ESPACE                                                     # espace insécable
MOINS = "−"


def charger(nom: str) -> dict:
    return json.loads((FIXTURES / nom).read_text(encoding="utf-8"))


def plan_minimal(lignes: list[dict], **extra) -> dict:
    plan = {"version": 1, "titre": "test", "equipements": [
        {"id": "EV1", "type": "evaporateur", "position": [0, 0]},
        {"id": "GR1", "type": "groupe", "position": [5, 0]},
        {"id": "TD", "type": "tableau", "position": [0, 5]}], "lignes": lignes}
    plan.update(extra)
    return plan


def html_bien_forme(fragment: str) -> ET.Element:
    """Lève une erreur si le fragment n'est pas du XML bien formé (HTML simple attendu)."""
    return ET.fromstring(f"<racine>{fragment}</racine>")


class TestLigneEnL(unittest.TestCase):
    """Une ligne d'aspiration en L : 4,00 + 2,40 = 6,40 m en plan ; |2,60 − 2,30| + |2,60 − 0,50| = 2,40 m."""

    @classmethod
    def setUpClass(cls):
        cls.m = metrer(charger("a2-ligne-en-l.json"))
        cls.l1 = cls.m.lignes["L1"]

    def test_longueurs(self):
        self.assertEqual(self.l1["plan_m"], 6.40)
        self.assertEqual(self.l1["vertical_m"], 2.40)
        self.assertEqual(self.l1["reserve_m"], 0.0)
        self.assertEqual(self.l1["total_m"], 8.80)
        self.assertAlmostEqual(self.l1["plan_brut_m"], 6.4, places=12)

    def test_formule_en_toutes_lettres(self):
        attendu = f"6,40{NB}m en plan + |2,60 {MOINS} 2,30| + |2,60 {MOINS} 0,50| = 8,80{NB}m"
        self.assertEqual(self.l1["formule"], attendu)

    def test_champs_de_la_ligne(self):
        self.assertEqual(self.l1["type"], "aspiration")
        self.assertEqual(self.l1["calque"], "froid_cuivres")
        self.assertEqual(self.l1["reseau"], "froid_cuivres")
        self.assertEqual((self.l1["de"], self.l1["a"]), ("EV1", "GR1"))
        self.assertEqual(self.l1["diametre"], A_DEFINIR)
        self.assertEqual(self.l1["hauteurs_utilisees"], {"depart": 2.30, "passage": 2.60, "arrivee": 0.50})
        self.assertEqual(self.l1["origines_hauteurs"]["depart"], "hauteurs.evaporateur")


class TestDefautsParType(unittest.TestCase):
    """Sans table `hauteurs` : valeurs par défaut (HAUTEURS_DEFAUT), un cas par type de ligne."""

    @classmethod
    def setUpClass(cls):
        cls.m = metrer(charger("a2-defauts-par-type.json"))

    def total(self, lid):
        l = self.m.lignes[lid]
        return l["plan_m"], l["vertical_m"], l["reserve_m"], l["total_m"]

    def test_aspiration(self):
        self.assertEqual(self.total("L1"), (7.00, 2.40, 0.0, 9.40))

    def test_liquide(self):
        self.assertEqual(self.total("L2"), (6.80, 2.40, 0.0, 9.20))

    def test_condensats(self):
        # départ 2,30 ; passage 2,30 (= évaporateur) ; arrivée 0,10 → 0 + 2,20
        self.assertEqual(self.total("L3"), (1.50, 2.20, 0.0, 3.70))
        self.assertEqual(self.m.lignes["L3"]["hauteurs_utilisees"], {"depart": 2.30, "passage": 2.30, "arrivee": 0.10})

    def test_clim_gaz_et_liquide(self):
        # split 2,20 ; passage 2,20 ; moteur 0,50 → 0 + 1,70
        self.assertEqual(self.total("L4"), (8.00, 1.70, 0.0, 9.70))
        self.assertEqual(self.total("L5"), (8.00, 1.70, 0.0, 9.70))
        self.assertEqual(self.m.lignes["L4"]["calque"], "clim_cuivres")

    def test_cable_avec_reserve(self):
        # évaporateur 2,30 → chemin 2,80 → tableau 1,50 : 0,50 + 1,30 ; + 1,00 de réserve
        self.assertEqual(self.total("L6"), (3.80, 1.80, 1.00, 6.60))
        self.assertIn(f"+ 1,00{NB}m de réserve = 6,60{NB}m", self.m.lignes["L6"]["formule"])

    def test_cable_depart_groupe_et_sens_inverse(self):
        # GR1 (raccord 0,50) → TD : 2,30 + 1,30 ; TD → split (2,20) : 1,30 + 0,60
        self.assertEqual(self.total("L9"), (9.80, 3.60, 1.00, 14.40))
        self.assertEqual(self.total("L10"), (2.80, 1.90, 1.00, 5.70))
        self.assertEqual(self.m.lignes["L10"]["hauteurs_utilisees"], {"depart": 1.50, "passage": 2.80, "arrivee": 2.20})

    def test_cable_equipement_inconnu_repli(self):
        plan = plan_minimal([{"id": "C1", "type": "cable", "de": None, "a": None, "points": [[0, 0], [2, 0]]}])
        l = metrer(plan).lignes["C1"]
        self.assertEqual(l["hauteurs_utilisees"], {"depart": 2.30, "passage": 2.80, "arrivee": 1.50})
        self.assertEqual(l["total_m"], 4.80)                     # 2,00 + 0,50 + 1,30 + 1,00

    def test_cable_depuis_une_chambre_froide(self):
        plan = plan_minimal([{"id": "C1", "type": "cable", "de": "CF1", "a": "TD", "points": [[0, 0], [2, 0]]}],
                            chambres_froides=[{"id": "CF1", "polygone": [[0, 0], [1, 0], [1, 1], [0, 1]]}])
        self.assertEqual(metrer(plan).lignes["C1"]["hauteurs_utilisees"]["depart"], 2.30)

    def test_chemin_cables_sans_vertical(self):
        self.assertEqual(self.total("L7"), (5.80, 0.0, 0.0, 5.80))
        self.assertEqual(self.m.lignes["L7"]["hauteurs_utilisees"], {})
        self.assertIn("pas de métré vertical", self.m.lignes["L7"]["formule"])

    def test_calque_libre(self):
        # départ 0 ; passage = passage_froid 2,60 ; arrivée 0 → 5,20
        self.assertEqual(self.total("L8"), (4.00, 5.20, 0.0, 9.20))
        self.assertEqual(self.m.lignes["L8"]["libelle_type"], "Eau chaude")
        self.assertEqual(self.m.lignes["L8"]["nom_reseau"], "Eau chaude")

    def test_calque_standard_deduit_du_type(self):
        self.assertEqual(self.m.lignes["L3"]["calque"], "froid_cuivres")

    def test_entier_et_flottant_equivalents(self):
        plan = plan_minimal([{"id": "A", "type": "aspiration", "de": "EV1", "a": "GR1", "points": [[0, 0], [5, 0]]}],
                            hauteurs={"evaporateur": 2, "passage_froid": 3, "raccord_groupe": 1})
        self.assertEqual(metrer(plan).lignes["A"]["total_m"], 5 + 1 + 2)


class TestSurcharges(unittest.TestCase):
    """Priorité : ligne > équipement > calque libre > table `hauteurs` > défaut."""

    @classmethod
    def setUpClass(cls):
        cls.m = metrer(charger("a2-surcharges.json"))

    def test_passage_force_sur_la_ligne(self):
        l = self.m.lignes["L1"]
        self.assertEqual(l["hauteurs_utilisees"], {"depart": 2.50, "passage": 3.50, "arrivee": 0.30})
        self.assertEqual(l["origines_hauteurs"]["passage"], "ligne")
        self.assertEqual((l["vertical_m"], l["total_m"]), (4.20, 9.20))

    def test_trois_hauteurs_forcees(self):
        l = self.m.lignes["L2"]
        self.assertEqual((l["plan_m"], l["vertical_m"], l["total_m"]), (5.00, 0.0, 5.00))

    def test_condensats_suivent_la_hauteur_evaporateur(self):
        l = self.m.lignes["L3"]
        self.assertEqual(l["hauteurs_utilisees"], {"depart": 2.50, "passage": 2.50, "arrivee": 0.10})
        self.assertEqual(l["total_m"], 3.40)

    def test_passage_condensats_explicite(self):
        plan = plan_minimal([{"id": "K", "type": "condensats", "de": "EV1", "a": None, "points": [[0, 0], [1, 0]]}],
                            hauteurs={"passage_condensats": 2.00})
        self.assertEqual(metrer(plan).lignes["K"]["hauteurs_utilisees"]["passage"], 2.00)

    def test_hauteur_de_l_equipement_et_reserve_modifiee(self):
        l = self.m.lignes["L4"]
        self.assertEqual(l["hauteurs_utilisees"], {"depart": 2.70, "passage": 3.20, "arrivee": 1.20})
        self.assertEqual(l["origines_hauteurs"]["depart"], "équipement EV2")
        self.assertEqual((l["plan_m"], l["vertical_m"], l["reserve_m"], l["total_m"]), (1.00, 2.50, 2.00, 5.50))

    def test_hauteur_equipement_pour_les_cuivres(self):
        l = self.m.lignes["L7"]
        self.assertEqual(l["hauteurs_utilisees"], {"depart": 2.70, "passage": 3.00, "arrivee": 0.30})
        self.assertEqual(l["total_m"], 12.00)

    def test_hauteurs_du_calque_libre(self):
        l = self.m.lignes["L5"]
        self.assertEqual(l["hauteurs_utilisees"], {"depart": 2.90, "passage": 3.10, "arrivee": 0.0})
        self.assertEqual(l["total_m"], 5.30)

    def test_chemin_cables_ignore_les_hauteurs(self):
        l = self.m.lignes["L6"]
        self.assertEqual((l["vertical_m"], l["total_m"]), (0.0, 2.00))


class TestHypotheses(unittest.TestCase):
    def test_tout_en_hypothese_sans_validation(self):
        m = metrer(charger("a2-defauts-par-type.json"))
        cles = [h["cle"] for h in m.hypotheses]
        self.assertEqual(cles, ["evaporateur", "passage_froid", "raccord_groupe", "passage_condensats",
                                "evacuation_condensats", "split", "passage_clim", "raccord_moteur", "tableau",
                                "chemin_cables", "reserve_cable", "raccord_libre"])
        self.assertTrue(all(h["statut"] == HYPOTHESE for h in m.hypotheses))
        reserve = next(h for h in m.hypotheses if h["cle"] == "reserve_cable")
        self.assertEqual(reserve["lignes"], ["L6", "L9", "L10"])

    def test_seules_les_hauteurs_utilisees(self):
        m = metrer(charger("a2-ligne-en-l.json"))
        self.assertEqual([h["cle"] for h in m.hypotheses], ["evaporateur", "passage_froid", "raccord_groupe"])

    def test_validees_et_surcharges(self):
        m = metrer(charger("a2-surcharges.json"))
        par_cle = {h["cle"]: h for h in m.hypotheses}
        self.assertEqual(par_cle["evaporateur"]["statut"], VALIDEE)
        self.assertEqual(par_cle["ligne:L1:passage"]["statut"], IMPOSEE_LIGNE)
        self.assertEqual(par_cle["ligne:L1:passage"]["valeur"], 3.50)
        self.assertEqual(par_cle["equipement:EV2"]["statut"], IMPOSEE_EQUIPEMENT)
        self.assertEqual(par_cle["equipement:EV2"]["lignes"], ["L4", "L7"])
        self.assertEqual(par_cle["calque:gaine:passage"]["statut"], IMPOSEE_CALQUE)
        self.assertNotIn(HYPOTHESE, {h["statut"] for h in m.hypotheses})

    def test_validation_partielle_par_liste(self):
        plan = charger("a2-ligne-en-l.json")
        plan["hauteurs_validees"] = ["evaporateur"]
        statuts = {h["cle"]: h["statut"] for h in metrer(plan).hypotheses}
        self.assertEqual(statuts, {"evaporateur": VALIDEE, "passage_froid": HYPOTHESE, "raccord_groupe": HYPOTHESE})


class TestTotaux(unittest.TestCase):
    def test_par_reseau_defauts(self):
        m = metrer(charger("a2-defauts-par-type.json"))
        r = m.par_reseau
        self.assertEqual(list(r), ["froid_cuivres", "electricite", "clim_cuivres", "eau_chaude"])
        self.assertEqual((r["froid_cuivres"]["plan_m"], r["froid_cuivres"]["total_m"]), (15.30, 22.30))
        self.assertEqual((r["clim_cuivres"]["plan_m"], r["clim_cuivres"]["total_m"]), (16.00, 19.40))
        self.assertEqual((r["eau_chaude"]["plan_m"], r["eau_chaude"]["total_m"]), (4.00, 9.20))
        e = r["electricite"]
        self.assertEqual((e["plan_m"], e["vertical_m"], e["reserve_m"], e["total_m"]), (22.20, 7.30, 3.00, 32.50))
        self.assertEqual(e["lignes"], ["L6", "L7", "L9", "L10"])
        self.assertEqual(e["nom"], "Électricité (froid + clim)")

    def test_detail_par_type_dans_un_reseau(self):
        e = metrer(charger("a2-defauts-par-type.json")).par_reseau["electricite"]["par_type"]
        self.assertEqual(e["cable"]["total_m"], 26.70)
        self.assertEqual(e["chemin_cables"]["total_m"], 5.80)

    def test_par_diametre_a_definir_regroupe(self):
        m = metrer(charger("a2-reseaux-diametres.json"))
        totaux = {k: v["total_m"] for k, v in m.par_diametre.items()}
        self.assertEqual(totaux, {("aspiration", "22 mm"): 24.80, ("liquide", "12 mm"): 12.40,
                                  ("liquide", A_DEFINIR): 12.40, ("condensats", A_DEFINIR): 3.20,
                                  ("cable", "3G1,5"): 7.80})
        self.assertEqual(list(m.par_diametre), [("aspiration", "22 mm"), ("liquide", "12 mm"), ("liquide", A_DEFINIR),
                                                ("condensats", A_DEFINIR), ("cable", "3G1,5")])
        self.assertEqual(m.par_diametre[("aspiration", "22 mm")]["lignes"], ["L1", "L3"])

    def test_par_reseau_diametres(self):
        r = metrer(charger("a2-reseaux-diametres.json")).par_reseau["froid_cuivres"]
        self.assertEqual((r["plan_m"], r["vertical_m"], r["total_m"]), (41.00, 11.80, 52.80))

    def test_les_tableaux_s_additionnent_exactement(self):
        m = metrer(charger("a2-defauts-par-type.json"))
        for r in m.par_reseau.values():
            somme = arrondi(sum(m.lignes[i]["total_m"] for i in r["lignes"]))
            self.assertEqual(somme, r["total_m"])
            self.assertEqual(arrondi(r["plan_m"] + r["vertical_m"] + r["reserve_m"]), r["total_m"])

    def test_normaliser_diametre(self):
        for brut in (None, "", "  ", "à définir", "A définir par le fournisseur", "a definir"):
            self.assertEqual(normaliser_diametre(brut), A_DEFINIR)
        self.assertEqual(normaliser_diametre(" 7/8\" "), "7/8\"")


class TestFormatFrancais(unittest.TestCase):
    def test_nombre_fr(self):
        self.assertEqual(nombre_fr(8.8), "8,80")
        self.assertEqual(nombre_fr(1234.5), f"1{NB}234,50")
        self.assertEqual(nombre_fr(0.005), "0,01")                 # au plus proche, pas d'arrondi bancaire
        self.assertEqual(nombre_fr(2.675), "2,68")
        self.assertEqual(nombre_fr(-0.001), "0,00")                # pas de « -0,00 »
        self.assertEqual(longueur_fr(6.4), f"6,40{NB}m")

    def test_markdown_tableaux_et_nombres(self):
        md = metrer(charger("a2-defauts-par-type.json")).markdown()
        for titre in ("### Métré par réseau", "### Détail du calcul par ligne", "### Métré par diamètre",
                      "### Hauteurs utilisées"):
            self.assertIn(titre, md)
        # C2 : colonne « Dans le chemin (m) » ; F1 (2026-10-08) : plus de « (hyp.) », la phrase des estimations en tête.
        self.assertIn("| Réseau | Ligne | De → À | Type | En plan (m) | Dans le chemin (m) | Vertical (m) | Réserve (m) "
                      "| Total (m) | Diamètre |", md)
        self.assertIn("| Froid – cuivres et condensats | L1 | EV1 → GR1 | Aspiration | 7,00 | 0,00 | 2,40 "
                      "| 0,00 | 9,40 | à définir |", md)
        self.assertIn("| **Total Électricité (froid + clim)** |  |  |  | **22,20** | **0,00** | **7,30** "
                      "| **3,00** | **32,50** |  |", md)
        self.assertNotIn("(hyp.)", md)
        self.assertIn(PHRASE_LONGUEURS, md)
        self.assertIn("| Diamètre | Type | Total (m) |", md)
        self.assertIn("| Hauteur | Valeur (m) | Statut |", md)
        self.assertIn("| Tableau électrique | 1,50 | hypothèse |", md)
        self.assertIn(f"- **L1** (Aspiration, EV1 → GR1) : 7,00{NB}m en plan", md)
        self.assertIn("Les montées et descentes utilisent les hauteurs de pose ci-dessous, à valider (question 13). "
                      "Diamètres et charge de fluide : à définir par le fournisseur.", md)
        self.assertIsNone(re.search(r"\d\.\d", md), "aucun point décimal dans le markdown")

    def test_markdown_echappe_les_barres(self):
        plan = plan_minimal([{"id": "A", "type": "aspiration", "de": "EV1", "a": "GR1", "points": [[0, 0], [1, 0]],
                              "diametre": "22|25"}])
        self.assertIn("22\\|25", metrer(plan).markdown())

    def test_markdown_sans_ligne(self):
        md = metrer(plan_minimal([])).markdown()
        self.assertIn("Aucune ligne à métrer.", md)

    def test_note_absente_si_tout_valide(self):
        md = metrer(charger("a2-surcharges.json")).markdown()
        self.assertNotIn("question 13", md)
        self.assertIn("Les montées et descentes utilisent les hauteurs de pose ci-dessous, validées.", md)


class TestHtml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = metrer(charger("a2-defauts-par-type.json"))

    def test_html_bien_forme(self):
        racine = html_bien_forme(self.m.html())
        self.assertEqual(len(racine.findall(".//table")), 3)
        self.assertEqual([h.text for h in racine.iter("h3")], ["Métré par réseau", "Détail du calcul par ligne",
                                                                "Métré par diamètre", "Hauteurs utilisées"])
        self.assertEqual(len(racine.findall(".//li")), 10)

    def test_tableaux_html_pour_drawio(self):
        tableaux = self.m.tableaux_html()
        self.assertEqual([t for t, _ in tableaux], ["Métré par réseau", "Métré par diamètre", "Hauteurs utilisées"])
        for _, fragment in tableaux:
            racine = html_bien_forme(fragment)
            balises = {e.tag for e in racine.iter()} - {"racine"}
            self.assertLessEqual(balises, {"table", "tr", "td", "b"})
            self.assertNotIn("<style", fragment)
            self.assertNotIn("class=", fragment)
        reseau = tableaux[0][1]
        self.assertIn("32,50", reseau)
        self.assertIn("<b>Total Électricité (froid + clim)</b>", reseau)
        self.assertIn("text-align:right", reseau)

    def test_html_echappe_le_texte(self):
        plan = plan_minimal([{"id": "A", "type": "aspiration", "de": "EV1", "a": "GR1", "points": [[0, 0], [1, 0]],
                              "diametre": "<22 & 25>"}])
        m = metrer(plan)
        html_bien_forme(m.html())
        self.assertIn("&lt;22 &amp; 25&gt;", m.tableaux_html()[1][1])

    def test_en_dict_serialisable(self):
        texte = json.dumps(self.m.en_dict(), ensure_ascii=False)
        self.assertIn('"aspiration|à définir"', texte)


def plan_chemin(cable: dict | None = None, chemin: dict | None = None, **extra) -> dict:
    """Cas calculé à la main (C2). Chemin K1 côté tableau TD : (12 ; 1) → (12 ; 4) → (2 ; 4) = 3,00 + 10,00 = 13,00 m.
    Câble C1 de EV1 : (2,7 ; 8) → (4,9 ; 8) → (4,9 ; 4) = 2,20 + 4,00 = 6,20 m en plan ; il s'arrête sur K1 en
    (4,9 ; 4), à 3,00 + (12 − 4,9) = 10,10 m de l'extrémité TD du chemin."""
    c = {"id": "C1", "type": "cable", "de": "EV1", "a": "K1", "points": [[2.7, 8.0], [4.9, 8.0], [4.9, 4.0]]}
    k = {"id": "K1", "type": "chemin_cables", "de": "TD", "a": None, "points": [[12.0, 1.0], [12.0, 4.0], [2.0, 4.0]]}
    c.update(cable or {})
    k.update(chemin or {})
    plan = {"version": 1, "titre": "test", "equipements": [
        {"id": "EV1", "type": "evaporateur", "position": [2.7, 8.0]},
        {"id": "TD", "type": "tableau", "position": [12.0, 0.6]}], "lignes": [c, k]}
    plan.update(extra)
    return plan


class TestCableDansLeCheminDeCables(unittest.TestCase):
    """C2 (écart n° 1 de V) : un câble qui s'arrête sur le chemin compte son parcours dans le chemin jusqu'au TD."""

    def test_cas_a_la_main(self):
        m = metrer(plan_chemin())
        l = m.lignes["C1"]
        # 6,20 en plan + 10,10 dans le chemin + |2,80 − 2,30| + |2,80 − 1,50| + 1,00 de réserve = 19,10
        self.assertEqual((l["plan_m"], l["chemin_m"], l["vertical_m"], l["reserve_m"], l["total_m"]),
                         (6.20, 10.10, 1.80, 1.00, 19.10))
        self.assertEqual(l["chemin"], "K1")
        self.assertEqual(l["a"], "K1")                                 # le tableau affiche toujours EV1 → K1
        self.assertEqual(l["formule"], f"6,20{NB}m en plan + 10,10{NB}m dans le chemin de câbles K1 jusqu'à TD "
                                       f"+ |2,80 {MOINS} 2,30| + |2,80 {MOINS} 1,50| + 1,00{NB}m de réserve = 19,10{NB}m")
        self.assertEqual(l["hauteurs_utilisees"], {"depart": 2.30, "passage": 2.80, "arrivee": 1.50})

    def test_chemin_metre_une_fois_a_part(self):
        m = metrer(plan_chemin())
        k = m.lignes["K1"]
        self.assertEqual((k["plan_m"], k["chemin_m"], k["total_m"]), (13.00, 0.0, 13.00))
        e = m.par_reseau["electricite"]
        self.assertEqual((e["plan_m"], e["chemin_m"], e["vertical_m"], e["reserve_m"], e["total_m"]),
                         (19.20, 10.10, 1.80, 1.00, 32.10))
        self.assertEqual(arrondi(e["plan_m"] + e["chemin_m"] + e["vertical_m"] + e["reserve_m"]), e["total_m"])
        self.assertEqual(e["par_type"]["chemin_cables"]["total_m"], 13.00)

    def test_par_proximite_du_dernier_point_sans_a(self):
        # `a` absent (cas d'une ligne relue dans draw.io) : dernier point à 8 cm du chemin → associé, projection 4,9.
        l = metrer(plan_chemin({"a": None, "points": [[2.7, 8.0], [4.9, 8.0], [4.9, 4.08]]})).lignes["C1"]
        self.assertEqual((l["chemin"], l["chemin_m"], l["plan_m"]), ("K1", 10.10, 6.12))

    def test_trop_loin_du_chemin(self):
        l = metrer(plan_chemin({"a": None, "points": [[2.7, 8.0], [4.9, 8.0], [4.9, 4.15]]})).lignes["C1"]
        self.assertIsNone(l["chemin"])
        self.assertEqual(l["chemin_m"], 0.0)
        self.assertNotIn("dans le chemin", l["formule"])

    def test_cable_qui_arrive_a_un_equipement(self):
        # `a` = TD : le câble va au tableau par son propre tracé, même s'il finit sur le chemin.
        l = metrer(plan_chemin({"a": "TD"})).lignes["C1"]
        self.assertIsNone(l["chemin"])
        self.assertEqual(l["total_m"], 9.00)                          # 6,20 + 1,80 + 1,00

    def test_cote_tableau_par_le_a_du_chemin(self):
        k = {"de": None, "a": "TD", "points": [[2.0, 4.0], [12.0, 4.0], [12.0, 1.0]]}
        self.assertEqual(metrer(plan_chemin(chemin=k)).lignes["C1"]["chemin_m"], 10.10)

    def test_cote_tableau_par_proximite(self):
        # Chemin sans de ni a : l'extrémité la plus proche du centre de TD (12 ; 0,6) est (12 ; 1).
        self.assertEqual(metrer(plan_chemin(chemin={"de": None})).lignes["C1"]["chemin_m"], 10.10)
        k = {"de": None, "points": [[2.0, 4.0], [12.0, 4.0], [12.0, 1.0]]}
        self.assertEqual(metrer(plan_chemin(chemin=k)).lignes["C1"]["chemin_m"], 10.10)

    def test_sans_tableau_parcours_non_compte(self):
        plan = plan_chemin(chemin={"de": None})
        plan["equipements"] = [e for e in plan["equipements"] if e["id"] != "TD"]
        l = metrer(plan).lignes["C1"]
        self.assertEqual((l["chemin"], l["chemin_m"], l["total_m"]), ("K1", 0.0, 9.00))
        self.assertIn("non compté", l["formule"])

    def test_hauteur_du_tableau_au_bout_du_chemin(self):
        plan = plan_chemin()
        plan["equipements"][1]["hauteur"] = 1.20
        l = metrer(plan).lignes["C1"]
        self.assertEqual(l["hauteurs_utilisees"]["arrivee"], 1.20)
        self.assertEqual(l["origines_hauteurs"]["arrivee"], "équipement TD")
        self.assertEqual(l["total_m"], arrondi(6.20 + 10.10 + 0.50 + 1.60 + 1.00))

    def test_tableaux_colonne_chemin_sans_hyp(self):
        # F1 (2026-10-08) : plus de « (hyp.) » sur la page « Métré » ; la note (question 13, fournisseur) reste.
        m = metrer(plan_chemin())
        md = m.markdown()
        self.assertIn("| Électricité (froid + clim) | C1 | EV1 → K1 | Câble | 6,20 | 10,10 | 1,80 "
                      "| 1,00 | 19,10 | à définir |", md)
        reseau = m.tableaux_html()[0][1]
        html_bien_forme(reseau)
        self.assertIn(">Dans le chemin (m)<", reseau)
        self.assertIn(">10,10<", reseau)
        self.assertIn(">19,10<", reseau)
        self.assertIn("question 13", reseau)                          # note sous le tableau
        self.assertIn("à définir par le fournisseur", reseau)
        self.assertIn(">19,10<", m.tableaux_html()[1][1])             # métré par diamètre
        for _, fragment in m.tableaux_html():
            self.assertNotIn("(hyp.)", fragment)

    def test_sans_hyp_quand_les_hauteurs_sont_validees(self):
        m = metrer(plan_chemin(hauteurs_validees=True))
        for _, fragment in m.tableaux_html():
            self.assertNotIn("(hyp.)", fragment)
        self.assertIn(">19,10<", m.tableaux_html()[0][1])


class TestErreurs(unittest.TestCase):
    def ligne(self, **champs):
        base = {"id": "A", "type": "aspiration", "de": "EV1", "a": "GR1", "points": [[0, 0], [1, 0]]}
        base.update(champs)
        return base

    def test_un_seul_point(self):
        with self.assertRaisesRegex(ErreurMetre, "au moins 2 points"):
            metrer(plan_minimal([self.ligne(points=[[0, 0]])]))

    def test_point_invalide(self):
        with self.assertRaisesRegex(ErreurMetre, "point n° 2"):
            metrer(plan_minimal([self.ligne(points=[[0, 0], [1, "a"]])]))

    def test_hauteur_negative(self):
        with self.assertRaisesRegex(ErreurMetre, "négative"):
            metrer(plan_minimal([self.ligne(hauteur_passage=-1)]))
        with self.assertRaisesRegex(ErreurMetre, "hauteurs.tableau"):
            metrer(plan_minimal([], hauteurs={"tableau": "haut"}))

    def test_type_inconnu(self):
        with self.assertRaisesRegex(ErreurMetre, "inconnu"):
            metrer(plan_minimal([self.ligne(type="aspirtion")]))

    def test_identifiant_en_double(self):
        with self.assertRaisesRegex(ErreurMetre, "double"):
            metrer(plan_minimal([self.ligne(), self.ligne()]))

    def test_plan_non_modifie(self):
        plan = charger("a2-surcharges.json")
        avant = copy.deepcopy(plan)
        metrer(plan)
        self.assertEqual(plan, avant)


def plan_mesure(longueur=None, par="Loïc", date="2026-10-08", note="test", liquide=None) -> dict:
    """Ligne en L (L1 : 6,40 en plan + 2,40 = 8,80 m estimés) ; `liquide` : longueur mesurée d'une 2e ligne L2
    (liquide, même tracé, 8,80 m estimés), None = non mesurée, « estimee » = ligne présente mais estimée."""
    plan = charger("a2-ligne-en-l.json")
    if longueur is not None:
        plan["lignes"][0].update(longueur_mesuree=longueur, mesure={"par": par, "date": date, "note": note})
    if liquide is not None:
        l2 = copy.deepcopy(plan["lignes"][0])
        l2.update(id="L2", type="liquide")
        l2.pop("longueur_mesuree", None)
        l2.pop("mesure", None)
        if liquide != "estimee":
            l2.update(longueur_mesuree=liquide, mesure={"par": par, "date": date, "note": note})
        plan["lignes"].append(l2)
    return plan


class TestLongueurMesuree(unittest.TestCase):
    """F1 (décision du 2026-10-08) : toute longueur est estimée d'après le plan, sauf celle mesurée sur chantier par
    le frigoriste (`longueur_mesuree` + `mesure`), qui devient le total ; l'estimation du plan reste à côté."""

    def test_estimee_par_defaut(self):
        l = metrer(plan_mesure()).lignes["L1"]
        self.assertEqual((l["origine"], l["total_m"], l["estimation_plan_m"]), (mtr.ESTIMEE, 8.80, 8.80))
        self.assertIsNone(l["longueur_mesuree_m"])
        self.assertIsNone(l["mesure"])
        self.assertIsNone(l["ecart_m"])
        self.assertFalse(l["ecart_fort"])

    def test_mesure_retenue_comme_total(self):
        l = metrer(plan_mesure(9.10)).lignes["L1"]
        self.assertEqual((l["origine"], l["total_m"], l["estimation_plan_m"], l["longueur_mesuree_m"]),
                         (mtr.MESUREE, 9.10, 8.80, 9.10))
        # les composantes gardent l'estimation du plan
        self.assertEqual((l["plan_m"], l["vertical_m"], l["reserve_m"]), (6.40, 2.40, 0.0))
        self.assertEqual(l["mesure"], {"par": "Loïc", "date": "2026-10-08", "note": "test"})
        self.assertEqual(l["ecart_m"], 0.30)
        self.assertAlmostEqual(l["ecart_rel"], 0.30 / 8.80, places=9)
        self.assertFalse(l["ecart_fort"])
        self.assertTrue(l["formule"].endswith(f"= 8,80{NB}m ; mesurée sur chantier par Loïc : 9,10{NB}m, retenue"))
        self.assertEqual(mtr.ecart_fr(l), f"+0,30{NB}m (+3,4{NB}%)")

    def test_seuil_de_20_pct(self):
        # 8,80 × 1,20 = 10,56 : à la limite, pas d'alerte ; au delà (ou en dessous de 7,04), alerte
        for longueur, fort in ((10.56, False), (10.57, True), (7.04, False), (7.03, True), (12.0, True)):
            m = metrer(plan_mesure(longueur))
            self.assertEqual(m.lignes["L1"]["ecart_fort"], fort, longueur)
            self.assertEqual(m.lignes_ecart_fort(), ["L1"] if fort else [])
        self.assertEqual(mtr.ecart_fr(metrer(plan_mesure(7.03)).lignes["L1"]), f"−1,77{NB}m (−20,1{NB}%)")

    def test_mesure_invalide(self):
        for v in (0, -1.0, "12", True, float("nan")):
            with self.assertRaises(ErreurMetre, msg=repr(v)):
                metrer(plan_mesure(v))

    def test_totaux_par_reseau_et_par_type(self):
        r = metrer(plan_mesure(liquide="estimee")).par_reseau["froid_cuivres"]
        self.assertEqual((r["origine"], r["total_m"], r["total_estime_m"], r["total_mesure_m"]),
                         (mtr.ESTIMEE, 17.60, 17.60, 0.0))
        m = metrer(plan_mesure(9.10, liquide="estimee"))
        r = m.par_reseau["froid_cuivres"]
        self.assertEqual((r["origine"], r["total_m"], r["total_estime_m"], r["total_mesure_m"], r["estimation_plan_m"]),
                         (mtr.MIXTE, 17.90, 8.80, 9.10, 17.60))
        self.assertEqual(r["par_type"]["aspiration"]["origine"], mtr.MESUREE)
        self.assertEqual(r["par_type"]["liquide"]["origine"], mtr.ESTIMEE)
        r = metrer(plan_mesure(9.10, liquide=9.00)).par_reseau["froid_cuivres"]
        self.assertEqual((r["origine"], r["total_m"], r["total_estime_m"], r["total_mesure_m"]),
                         (mtr.MESUREE, 18.10, 0.0, 18.10))

    def test_marques_de_la_page_metre(self):
        m = metrer(plan_mesure(9.10, liquide="estimee"))
        reseau, diametres = m.tableaux_html()[0][1], m.tableaux_html()[1][1]
        html_bien_forme(reseau)
        self.assertIn(">9,10 (mesurée)<", reseau)                    # L1 : mesurée
        self.assertIn(">8,80<", reseau)                              # L2 : estimée, sans marque
        self.assertIn("<b>17,90</b>", reseau)                        # total mixte : sans marque
        self.assertIn(">9,10 (mesurée)<", diametres)                 # groupe « aspiration » entièrement mesuré
        self.assertIn(">8,80<", diametres)
        self.assertEqual(reseau.count("(mesurée)"), 1)
        m = metrer(plan_mesure(9.10, liquide=9.00))
        self.assertIn("<b>18,10 (mesurée)</b>", m.tableaux_html()[0][1])   # toutes mesurées : le total aussi
        for _, fragment in m.tableaux_html():
            self.assertNotIn("(hyp.)", fragment)

    def test_contrat_metre_json(self):
        m = metrer(plan_mesure(9.10, liquide="estimee"))
        c = m.contrat_json({"L1": "Évaporateur de test → Groupe de test"}, dossier="test-a2", plan_version=3,
                           echelle="1:50", genere_le="2026-10-08T10:12:00")
        self.assertEqual(list(c), ["version", "genere_le", "plan_version", "dossier", "echelle", "phrase",
                                   "hauteurs_validees", "reseaux", "par_type", "recapitulatif"])
        self.assertEqual((c["version"], c["plan_version"], c["dossier"], c["echelle"], c["hauteurs_validees"]),
                         (1, 3, "test-a2", "1:50", False))
        self.assertEqual(c["phrase"], "Toutes les longueurs sont des estimations d'après le plan (tracé et hauteurs "
                                      "de pose), sauf celles marquées « (mesurée) », relevées sur chantier.")
        r = c["reseaux"][0]
        self.assertEqual({k: r[k] for k in ("cle", "nom", "famille", "total_m", "total_estime_m", "total_mesure_m",
                                            "origine")},
                         {"cle": "froid_cuivres", "nom": "Froid : cuivres et condensats", "famille": "cuivre_froid",
                          "total_m": 17.90, "total_estime_m": 8.80, "total_mesure_m": 9.10, "origine": mtr.MIXTE})
        l1, l2 = r["lignes"]
        self.assertEqual(list(l1), ["id", "troncon", "de", "a", "type", "type_nom", "en_plan_m", "chemin_m",
                                    "vertical_m", "reserve_m", "total_m", "origine", "estimation_plan_m",
                                    "longueur_mesuree_m", "mesure", "diametre"])
        self.assertEqual(l1, {"id": "L1", "troncon": "Évaporateur de test → Groupe de test", "de": "EV1", "a": "GR1",
                              "type": "aspiration", "type_nom": "Aspiration", "en_plan_m": 6.40, "chemin_m": 0.0,
                              "vertical_m": 2.40, "reserve_m": 0.0, "total_m": 9.10, "origine": "mesuree",
                              "estimation_plan_m": 8.80, "longueur_mesuree_m": 9.10,
                              "mesure": {"par": "Loïc", "date": "2026-10-08", "note": "test"},
                              "diametre": "à définir par le fournisseur"})
        self.assertEqual((l2["troncon"], l2["origine"], l2["total_m"], l2["longueur_mesuree_m"], l2["mesure"]),
                         ("", "estimee", 8.80, None, None))
        self.assertEqual(c["par_type"], [
            {"reseau": "froid_cuivres", "type": "aspiration", "type_nom": "Aspiration", "total_m": 9.10,
             "origine": "mesuree"},
            {"reseau": "froid_cuivres", "type": "liquide", "type_nom": "Liquide", "total_m": 8.80,
             "origine": "estimee"}])
        self.assertEqual(c["recapitulatif"], [{"cle": "froid_cuivres", "nom": "Froid : cuivres et condensats",
                                               "total_m": 17.90, "origine": "mixte"}])
        # nombres JSON à 2 décimales au plus, point décimal
        texte = json.dumps(c, ensure_ascii=False)
        self.assertIsNone(re.search(r"\d\.\d{3,}", texte), texte)

    def test_contrat_familles_et_diametres(self):
        c = metrer(charger("a2-defauts-par-type.json")).contrat_json({}, dossier=None, plan_version=None,
                                                                      echelle=None, genere_le=None)
        self.assertEqual([(r["cle"], r["famille"]) for r in c["reseaux"]],
                         [("froid_cuivres", "cuivre_froid"), ("electricite", "electricite"),
                          ("clim_cuivres", "cuivre_clim"), ("eau_chaude", "libre")])
        lignes = {l["id"]: l for r in c["reseaux"] for l in r["lignes"]}
        self.assertIsNone(lignes["L7"]["diametre"])                   # chemin de câbles : pas un tuyau
        self.assertEqual(lignes["L4"]["diametre"], "à définir par le fournisseur")
        self.assertEqual(lignes["L8"]["type_nom"], "Eau chaude")
        self.assertTrue(all(l["origine"] == "estimee" for l in lignes.values()))
        self.assertTrue(c["reseaux"][0]["total_m"] == c["reseaux"][0]["total_estime_m"])

    def test_hauteurs_validees_dans_le_contrat(self):
        plan = plan_mesure()
        plan["hauteurs_validees"] = True
        self.assertTrue(metrer(plan).contrat_json({}, dossier=None, plan_version=None, echelle=None,
                                                  genere_le=None)["hauteurs_validees"])


if __name__ == "__main__":
    unittest.main()
