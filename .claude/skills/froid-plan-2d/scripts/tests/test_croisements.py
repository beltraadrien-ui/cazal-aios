"""Tests des croisements (croisements.py) : cas calculés à la main, faisceaux, extrémités, recouvrements, tableaux.

Usage, depuis la racine du dépôt :
    python -m pytest .claude/skills/froid-plan-2d/scripts/tests/test_croisements.py -q
ou, sans pytest (bibliothèque standard) :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -p "test_croisements.py" -v
Données génériques (fixtures « a2-* »), aucune donnée client.
"""
from __future__ import annotations

import json
import random
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # dossier scripts/
from croisements import (AUCUN, ErreurCroisements, croisements, meme_faisceau, recouvrements,  # noqa: E402
                         tableau_html, tableau_markdown)
from croisements import RAYON_GROUPE, etiquette_groupe, groupes_pour_dessin, regrouper  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
NB = " "


def charger(nom: str) -> dict:
    return json.loads((FIXTURES / nom).read_text(encoding="utf-8"))


def ligne(id_, points, type_="cable", de=None, a=None, faisceau=None, calque=None) -> dict:
    l = {"id": id_, "type": type_, "de": de, "a": a, "points": points}
    if faisceau is not None:
        l["faisceau"] = faisceau
    if calque is not None:
        l["calque"] = calque
    return l


def plan(*lignes, **extra) -> dict:
    p = {"version": 1, "lignes": list(lignes)}
    p.update(extra)
    return p


def points(liste):
    return [c["point"] for c in liste]


class TestCasSimples(unittest.TestCase):
    def test_deux_faisceaux_un_croisement(self):
        p = plan(ligne("L1", [[0, 1], [6, 1]], "aspiration", "EV1", "GR1", "F1"),
                 ligne("L2", [[3, 0], [3, 3]], "cable", "EV2", "TD"))
        x = croisements(p)
        self.assertEqual(len(x), 1)
        self.assertEqual(x[0]["id"], "X1")
        self.assertEqual(x[0]["point"], [3.0, 1.0])
        self.assertEqual(x[0]["lignes"], ["L1", "L2"])
        self.assertEqual(x[0]["calques"], ["froid_cuivres", "electricite"])
        self.assertEqual(x[0]["types"], ["aspiration", "cable"])
        self.assertEqual(x[0]["noms_calques"], ["Froid – cuivres et condensats", "Électricité (froid + clim)"])

    def test_point_oblique_calcule_a_la_main(self):
        # (0,0)→(4,4) et (0,4)→(4,0) se coupent en (2,2)
        p = plan(ligne("A", [[0, 0], [4, 4]], de="E1"), ligne("B", [[0, 4], [4, 0]], de="E2"))
        self.assertEqual(points(croisements(p)), [[2.0, 2.0]])

    def test_paralleles_sans_croisement(self):
        p = plan(ligne("A", [[0, 0], [10, 0]], "aspiration", "EV1", "GR1", "F1"),
                 ligne("B", [[0, 1], [10, 1]], "clim_gaz", "SP1", "MO1", "F2"))
        self.assertEqual(croisements(p), [])
        self.assertEqual(recouvrements(p), [])

    def test_segments_qui_ne_se_rejoignent_pas(self):
        p = plan(ligne("A", [[0, 0], [2, 0]], de="E1"), ligne("B", [[3, -1], [3, 1]], de="E2"))
        self.assertEqual(croisements(p), [])

    def test_extremite_commune_non_comptee(self):
        p = plan(ligne("A", [[0, 0], [5, 0]], "aspiration", "EV1", "GR1", "F1"),
                 ligne("B", [[0, 0], [0, 5]], "cable", "EV1", "TD"))
        self.assertEqual(croisements(p), [])

    def test_extremite_a_moins_de_5_cm_ignoree(self):
        # B s'arrête 3 cm après avoir coupé A : contact en bout de ligne, ignoré
        p = plan(ligne("A", [[0, 0], [5, 0]], de="E1"), ligne("B", [[2.5, 3], [2.5, -0.03]], de="E2"))
        self.assertEqual(croisements(p), [])

    def test_extremite_a_plus_de_5_cm_comptee(self):
        p = plan(ligne("A", [[0, 0], [5, 0]], de="E1"), ligne("B", [[4, 3], [4, -0.08]], de="E2"))
        self.assertEqual(points(croisements(p)), [[4.0, 0.0]])

    def test_ligne_qui_s_arrete_sur_une_autre(self):
        p = plan(ligne("A", [[0, 0], [5, 0]], de="E1"), ligne("B", [[2, 3], [2, 0]], de="E2"))
        self.assertEqual(croisements(p), [])


class TestFaisceaux(unittest.TestCase):
    def croix(self, la_extra: dict, lb_extra: dict) -> list:
        la = {"id": "A", "type": "aspiration", "points": [[0, 0], [4, 4]], **la_extra}
        lb = {"id": "B", "type": "liquide", "points": [[0, 4], [4, 0]], **lb_extra}
        return croisements(plan(la, lb))

    def test_aspiration_et_liquide_du_meme_faisceau(self):
        self.assertEqual(self.croix({"faisceau": "CF1-groupe"}, {"faisceau": "CF1-groupe"}), [])

    def test_sans_faisceau_memes_equipements(self):
        self.assertEqual(self.croix({"de": "EV1", "a": "GR1"}, {"de": "EV1", "a": "GR1"}), [])
        self.assertEqual(self.croix({"de": "EV1", "a": "GR1"}, {"de": "GR1", "a": "EV1"}), [])

    def test_sans_faisceau_equipements_differents(self):
        self.assertEqual(len(self.croix({"de": "EV1", "a": "GR1"}, {"de": "EV2", "a": "GR1"})), 1)

    def test_sans_faisceau_ni_equipements(self):
        self.assertEqual(len(self.croix({}, {})), 1)

    def test_un_faisceau_contre_aucun(self):
        self.assertEqual(len(self.croix({"faisceau": "F1", "de": "EV1", "a": "GR1"}, {"de": "EV1", "a": "GR1"})), 1)

    def test_faisceaux_differents(self):
        self.assertEqual(len(self.croix({"faisceau": "F1"}, {"faisceau": "F2"})), 1)

    def test_meme_faisceau_fonction(self):
        self.assertTrue(meme_faisceau({"faisceau": "F"}, {"faisceau": "F"}))
        self.assertFalse(meme_faisceau({"faisceau": ""}, {"faisceau": ""}))   # vide = pas de faisceau
        self.assertFalse(meme_faisceau({"de": "EV1", "a": None}, {"de": "EV1", "a": None}))


class TestFixtureCroisements(unittest.TestCase):
    """Deux câbles traversent le faisceau aspiration + liquide EV1-GR1 : 4 croisements calculés à la main."""

    @classmethod
    def setUpClass(cls):
        cls.plan = charger("a2-croisements.json")
        cls.x = croisements(cls.plan)

    def test_points_et_ordre(self):
        self.assertEqual(points(self.x), [[2.0, 0.5], [2.0, 0.6], [5.0, 0.5], [5.0, 0.6]])
        self.assertEqual([c["id"] for c in self.x], ["X1", "X2", "X3", "X4"])

    def test_lignes_de_chaque_croisement(self):
        self.assertEqual([c["lignes"] for c in self.x], [["L1", "L5"], ["L2", "L5"], ["L1", "L3"], ["L2", "L3"]])

    def test_identifiants_stables(self):
        self.assertEqual(croisements(self.plan), self.x)
        melange = json.loads(json.dumps(self.plan))
        random.Random(7).shuffle(melange["lignes"])
        autre = croisements(melange)
        self.assertEqual([(c["id"], c["point"]) for c in autre], [(c["id"], c["point"]) for c in self.x])
        self.assertEqual([set(c["lignes"]) for c in autre], [set(c["lignes"]) for c in self.x])

    def test_depart_commun_split_ignore(self):
        # L4 (clim) et L5 (câble) partent tous deux de (2, 3) : aucun croisement entre eux
        self.assertFalse(any(set(c["lignes"]) == {"L4", "L5"} for c in self.x))


class TestRecouvrements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = charger("a2-recouvrement.json")

    def test_cable_dans_le_chemin_n_est_pas_un_croisement(self):
        x = croisements(self.plan)
        self.assertEqual(points(x), [[9.0, 2.0]])          # seul le liquide traverse le chemin de câbles
        self.assertEqual(x[0]["lignes"], ["K1", "L1"])

    def test_recouvrement_signale(self):
        r = recouvrements(self.plan)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["id"], "R1")
        self.assertEqual(r[0]["lignes"], ["K1", "C1"])
        self.assertEqual((r[0]["de"], r[0]["a"]), ([3.0, 2.0], [8.0, 2.0]))
        self.assertEqual(r[0]["longueur_m"], 5.0)

    def test_recouvrement_meme_faisceau_non_signale(self):
        p = plan(ligne("A", [[0, 0], [5, 0]], "aspiration", "EV1", "GR1", "F1"),
                 ligne("B", [[0, 0], [5, 0]], "liquide", "EV1", "GR1", "F1"))
        self.assertEqual(recouvrements(p), [])

    def test_bout_a_bout_n_est_ni_croisement_ni_recouvrement(self):
        p = plan(ligne("A", [[0, 0], [5, 0]], de="E1"), ligne("B", [[5, 0], [9, 0]], de="E2"))
        self.assertEqual(croisements(p), [])
        self.assertEqual(recouvrements(p), [])

    def test_cable_decale_de_3_cm_dans_le_chemin(self):
        # tracé à la souris : le câble longe le chemin 3 cm plus bas ; son entrée ne doit pas compter comme croisement
        for ordre in (1, -1):
            lignes = [ligne("K1", [[0, 2], [10, 2]], "chemin_cables"),
                      ligne("C1", [[3, 0], [3, 2.03], [8, 2.03], [8, 4]], "cable", "EV1", "TD")][::ordre]
            p = plan(*lignes)
            self.assertEqual(croisements(p), [], f"ordre {ordre}")
            r = recouvrements(p)
            self.assertEqual(len(r), 1)
            self.assertAlmostEqual(r[0]["longueur_m"], 5.0, places=2)

    def test_paralleles_a_10_cm_ni_croisement_ni_recouvrement(self):
        p = plan(ligne("A", [[0, 0], [10, 0]], "aspiration", "EV1", "GR1", "F1"),
                 ligne("B", [[0, 0.1], [10, 0.1]], "liquide", "EV2", "GR1", "F2"))
        self.assertEqual(croisements(p), [])
        self.assertEqual(recouvrements(p), [])


class TestCasParticuliers(unittest.TestCase):
    def test_passage_par_un_coude_compte_une_fois(self):
        p = plan(ligne("A", [[0, 0], [2, 2], [4, 0]], de="E1"), ligne("B", [[2, 3], [2, 1]], de="E2"))
        self.assertEqual(points(croisements(p)), [[2.0, 2.0]])

    def test_deux_croisements_entre_les_memes_lignes(self):
        p = plan(ligne("A", [[0, 1], [10, 1]], de="E1"), ligne("B", [[2, 0], [2, 2], [6, 2], [6, 0]], de="E2"))
        self.assertEqual(points(croisements(p)), [[2.0, 1.0], [6.0, 1.0]])

    def test_trois_lignes_au_meme_point(self):
        p = plan(ligne("A", [[0, 2], [4, 2]], de="E1"), ligne("B", [[2, 0], [2, 4]], de="E2"),
                 ligne("C", [[0, 0], [4, 4]], de="E3"))
        x = croisements(p)
        self.assertEqual([c["lignes"] for c in x], [["A", "B"], ["A", "C"], ["B", "C"]])
        self.assertEqual({tuple(c["point"]) for c in x}, {(2.0, 2.0)})

    def test_calque_libre_et_types(self):
        p = plan(ligne("E", [[0, 1], [4, 1]], "eau_chaude", calque="eau_chaude"), ligne("C", [[2, 0], [2, 2]], de="E2"),
                 calques_libres=[{"cle": "eau_chaude", "nom": "Eau chaude", "couleur": "#EF6C00", "trait": "simple"}])
        x = croisements(p)
        self.assertEqual(x[0]["calques"], ["eau_chaude", "electricite"])
        self.assertEqual(x[0]["noms_calques"][0], "Eau chaude")
        self.assertEqual(x[0]["libelles_types"], ["Eau chaude", "Câble"])

    def test_plan_sans_ligne(self):
        self.assertEqual(croisements({"version": 1}), [])

    def test_ligne_a_un_seul_point(self):
        with self.assertRaisesRegex(ErreurCroisements, "au moins 2 points"):
            croisements(plan(ligne("A", [[0, 0]])))


class TestTableaux(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x = croisements(charger("a2-croisements.json"))

    def test_markdown(self):
        md = tableau_markdown(self.x)
        lignes = md.splitlines()
        self.assertEqual(lignes[0], "| N° | Point (x ; y) | Lignes | Calques |")
        self.assertEqual(len(lignes), 2 + 4)
        self.assertEqual(lignes[2], f"| X1 | 2,00{NB}m ; 0,50{NB}m | L1 (Aspiration) × L5 (Câble) "
                                    "| Froid – cuivres et condensats × Électricité (froid + clim) |")

    def test_markdown_vide(self):
        self.assertEqual(tableau_markdown([]), AUCUN)

    def test_html_bien_forme(self):
        racine = ET.fromstring(f"<racine>{tableau_html(self.x)}</racine>")
        rangs = racine.findall(".//tr")
        self.assertEqual(len(rangs), 5)
        self.assertEqual({e.tag for e in racine.iter()} - {"racine"}, {"table", "tr", "td", "b"})
        self.assertEqual(rangs[1].findall("td")[0].text, "X1")

    def test_html_vide(self):
        racine = ET.fromstring(f"<racine>{tableau_html([])}</racine>")
        self.assertIn(AUCUN, "".join(racine.itertext()))


def x_(id_, x, y, lignes=("A", "B"), calques=("froid_cuivres", "electricite")) -> dict:
    return {"id": id_, "point": [x, y], "lignes": list(lignes), "calques": list(calques)}


class TestRegrouper(unittest.TestCase):
    """C : regroupement des croisements proches pour le dessin (un cercle par groupe, repères G)."""

    def test_trois_proches_un_groupe(self):
        g = regrouper([x_("X1", 3.22, 0.3, ("LCO1", "CC1")), x_("X2", 3.34, 0.3, ("LA1", "CC1")),
                       x_("X3", 3.46, 0.3, ("LL1", "CC1"))])
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0]["id"], "G1")
        self.assertEqual(g[0]["croisements"], ["X1", "X2", "X3"])
        self.assertEqual(g[0]["point"], [3.34, 0.3])                    # moyenne des points
        self.assertEqual(g[0]["lignes"], ["LCO1", "CC1", "LA1", "LL1"])  # union, ordre d'apparition
        self.assertEqual(g[0]["calques"], ["froid_cuivres", "electricite"])

    def test_deux_lointains_deux_groupes(self):
        g = regrouper([x_("X1", 0.0, 0.0), x_("X2", 0.51, 0.0)])
        self.assertEqual([e["croisements"] for e in g], [["X1"], ["X2"]])
        self.assertEqual([e["id"] for e in g], ["G1", "G2"])
        self.assertEqual(g[1]["point"], [0.51, 0.0])                    # croisement isolé : son propre point

    def test_rayon_inclus(self):
        self.assertEqual(len(regrouper([x_("X1", 0.0, 0.0), x_("X2", 0.3, 0.4)])), 1)   # 0,50 m pile
        self.assertEqual(RAYON_GROUPE, 0.5)

    def test_transitivite(self):
        # X1-X2 = 0,40 m, X2-X3 = 0,40 m, X1-X3 = 0,80 m : un seul groupe (de proche en proche)
        g = regrouper([x_("X1", 0.0, 0.0), x_("X2", 0.4, 0.0), x_("X3", 0.8, 0.0)])
        self.assertEqual(len(g), 1)
        self.assertEqual(g[0]["croisements"], ["X1", "X2", "X3"])
        self.assertEqual(g[0]["point"], [0.4, 0.0])

    def test_transitivite_dans_le_desordre(self):
        # la chaîne X1 … X3 … X2 n'est pas dans l'ordre de la liste ; X4 loin
        g = regrouper([x_("X1", 0.0, 0.0), x_("X2", 0.8, 0.0), x_("X3", 0.4, 0.1), x_("X4", 5.0, 5.0)])
        self.assertEqual([e["croisements"] for e in g], [["X1", "X2", "X3"], ["X4"]])

    def test_rayon_parametrable_et_liste_vide(self):
        self.assertEqual(regrouper([]), [])
        self.assertEqual(len(regrouper([x_("X1", 0, 0), x_("X2", 0.12, 0)], rayon=0.1)), 2)

    def test_croisements_inchanges(self):
        liste = croisements(charger("a2-croisements.json"))
        avant = json.dumps(liste, sort_keys=True)
        regrouper(liste)
        self.assertEqual(json.dumps(liste, sort_keys=True), avant)
        self.assertEqual(sum(len(g["croisements"]) for g in regrouper(liste)), len(liste))

    def test_etiquette(self):
        self.assertEqual(etiquette_groupe({"croisements": ["X1", "X2", "X3"]}), "X1-X3")
        self.assertEqual(etiquette_groupe({"croisements": ["X4"]}), "X4")
        self.assertEqual(etiquette_groupe({"croisements": ["X1", "X2", "X5"]}), "X1-X2, X5")

    def test_pour_dessin(self):
        d = groupes_pour_dessin(regrouper([x_("X1", 1.0, 1.0), x_("X2", 1.2, 1.0)]))
        self.assertEqual(d, [{"id": "G1", "point": [1.1, 1.0], "croisements": ["X1", "X2"], "lignes": ["A", "B"],
                              "etiquette": "X1-X2"}])

    def test_tableaux_avec_repere(self):
        liste = croisements(charger("a2-croisements.json"))
        groupes = regrouper(liste)
        md = tableau_markdown(liste, groupes).splitlines()
        self.assertEqual(md[0], "| N° | Repère | Point (x ; y) | Lignes | Calques |")
        self.assertEqual(md[1], "|---|---|---|---|---|")
        self.assertEqual(len(md), 2 + len(liste))                       # une ligne par croisement
        repere = {x: g["id"] for g in groupes for x in g["croisements"]}
        self.assertTrue(md[2].startswith(f"| X1 | {repere['X1']} |"))
        racine = ET.fromstring(f"<racine>{tableau_html(liste, groupes)}</racine>")
        rangs = racine.findall(".//tr")
        self.assertEqual(len(rangs), 1 + len(liste))
        self.assertEqual([td.text for td in rangs[1].findall("td")][:2], ["X1", repere["X1"]])
        vide = ET.fromstring(f"<racine>{tableau_html([], [])}</racine>")
        self.assertEqual(vide.find(".//td[@colspan]").get("colspan"), "5")


if __name__ == "__main__":
    unittest.main()
