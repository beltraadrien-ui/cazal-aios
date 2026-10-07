"""Tests de modele.py : chargement, défauts, validation (fichier valide + 20 incohérences + 6 fichiers
illisibles), géométrie dérivée (axe des murs, portes, cotes, boîte englobante).

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -p "test_modele.py" -v
Données génériques (« boucherie test » fictive), aucune donnée client.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # dossier scripts/
import modele as mod  # noqa: E402
from modele import ErreurModele, charger, depuis_dict  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BOUCHERIE = FIXTURES / "a1-boucherie-plan.json"
DOSSIER_BOUCHERIE = (Path(__file__).resolve().parents[5] / "dimensionnement" / "dossiers"
                     / "2026-09-28-boucherie-test" / "plan" / "plan.json")


def plan_minimal() -> dict:
    """Une chambre froide de 3 × 4 m dans un local de 5 × 6 m, un évaporateur, un groupe, deux lignes."""
    return {
        "version": 1, "titre": "Local minimal", "dossier": "test-minimal", "date": "2026-10-07",
        "page": {"format": "A4", "orientation": "auto", "echelle": None},
        "murs": [
            {"id": "M1", "de": [0, 0], "a": [5, 0], "epaisseur": 0.2, "alignement": "droite"},
            {"id": "M2", "de": [5, 0], "a": [5, 6], "epaisseur": 0.2, "alignement": "droite"},
            {"id": "M3", "de": [5, 6], "a": [0, 6], "epaisseur": 0.2, "alignement": "droite"},
            {"id": "M4", "de": [0, 6], "a": [0, 0], "epaisseur": 0.2, "alignement": "droite"},
        ],
        "chambres_froides": [{"id": "CF1", "regime": "positif", "polygone": [[1, 1], [4, 1], [4, 5], [1, 5]],
                              "porte": {"position": [2, 5], "largeur": 0.9, "orientation": 0}}],
        "portes": [{"id": "D1", "position": [3, 5.8], "largeur": 0.9, "orientation": 180, "dans": "M3"}],
        "equipements": [
            {"id": "EV1", "type": "evaporateur", "position": [2.5, 1.4], "chambre": "CF1"},
            {"id": "GR1", "type": "groupe", "position": [2.5, -1.0]},
        ],
        "cotes": [{"id": "C1", "de": [0, 0], "a": [5, 0], "valeur": 5.0, "source": "telemetre", "cote": "haut",
                   "decalage": 0.6}],
        "lignes": [
            {"id": "L1", "type": "aspiration", "de": "EV1", "a": "GR1", "points": [[2.4, 1.15], [2.4, -0.7]]},
            {"id": "L2", "type": "liquide", "de": "EV1", "a": "GR1", "points": [[2.6, 1.15], [2.6, -0.7]]},
        ],
    }


def messages(d: dict) -> list[str]:
    return depuis_dict(d).valider()


class TestChargement(unittest.TestCase):
    def test_boucherie_valide(self):
        plan = charger(BOUCHERIE)
        self.assertEqual(plan.valider(), [])
        self.assertEqual(len(plan.murs), 10)
        self.assertEqual(len(plan.lignes), 21)
        self.assertEqual(len(plan.cotes), 10)

    def test_copie_de_la_fixture_du_dossier(self):
        """Le dossier local peut avoir été enrichi par l'usage (réseaux ajoutés depuis une photo, étiquettes
        déplacées) : tout ce que contient la fixture commitée doit s'y retrouver à l'identique, élément par
        élément (par identifiant pour les listes), les ajouts étant permis."""
        if not DOSSIER_BOUCHERIE.is_file():
            self.skipTest("dossier de test absent (gitignoré)")
        dossier = json.loads(DOSSIER_BOUCHERIE.read_text(encoding="utf-8"))
        fixture = json.loads(BOUCHERIE.read_text(encoding="utf-8"))
        for cle, valeur in fixture.items():
            self.assertIn(cle, dossier, cle)
            if isinstance(valeur, list) and valeur and isinstance(valeur[0], dict) and "id" in valeur[0]:
                par_id = {e["id"]: e for e in dossier[cle]}
                for element in valeur:
                    self.assertIn(element["id"], par_id, f"{cle}/{element['id']} absent du dossier")
                    for champ, attendu in element.items():
                        if champ in ("position_etiquette", "etiquette"):
                            continue
                        self.assertEqual(par_id[element["id"]].get(champ), attendu,
                                         f"{cle}/{element['id']}/{champ}")
            elif cle in ("notes", "calques_libres"):
                for element in valeur:
                    self.assertIn(element, dossier[cle], f"{cle} : {element!r} absent du dossier")
            else:
                self.assertEqual(dossier[cle], valeur, cle)

    def test_plan_minimal_valide(self):
        self.assertEqual(messages(plan_minimal()), [])

    def test_donnees_brutes_conservees(self):
        d = plan_minimal()
        plan = depuis_dict(d)
        self.assertEqual(plan.donnees, d)
        self.assertNotIn("dimensions", plan.donnees["equipements"][0])   # le brut ne reçoit pas les défauts

    def test_defauts(self):
        d = plan_minimal()
        d["murs"].append({"id": "M5", "de": [2.5, 0.2], "a": [2.5, 1], "type": "cloison"})
        d["lignes"].append({"id": "L3", "type": "condensats", "de": "EV1", "points": [[2.8, 1.15], [2.8, -0.2]]})
        plan = depuis_dict(d)
        self.assertEqual(plan.equipement("EV1")["dimensions"], (1.2, 0.5))
        self.assertEqual(plan.equipement("GR1")["dimensions"], (1.0, 0.6))
        self.assertEqual(plan.equipement("EV1")["calque"], "froid_equipements")
        self.assertEqual(plan.mur("M5")["epaisseur"], 0.10)
        self.assertEqual(plan.ligne("L3")["calque"], "froid_cuivres")
        self.assertEqual(plan.ligne("L1")["diametre"], "à définir")
        self.assertEqual(plan.hauteurs["passage_froid"], 2.60)
        self.assertEqual(plan.hauteurs["evacuation_condensats"], 0.10)
        self.assertEqual(plan.chambre("CF1")["panneau_mm"], 80)
        self.assertEqual(plan.soufflage(plan.equipement("EV1")), "bas")   # vers la porte de la chambre
        self.assertEqual(plan.valider(), [])

    def test_champs_optionnels_du_metre(self):
        d = plan_minimal()
        d["equipements"][0]["hauteur"] = 2.4
        d["calques_libres"] = [{"cle": "eau_chaude", "nom": "Eau chaude", "couleur": "#EF6C00", "trait": "simple",
                                "hauteur_depart": 0.5, "hauteur_passage": 2.7, "hauteur_arrivee": 0.5}]
        d["lignes"].append({"id": "L3", "type": "eau_chaude", "points": [[0.5, 0.5], [0.5, 3]]})
        d["hauteurs"] = {"passage_condensats": 2.4, "evacuation_condensats": 0.2}
        d["hauteurs_validees"] = ["passage_froid", "evaporateur"]
        plan = depuis_dict(d)
        self.assertEqual(plan.valider(), [])
        self.assertEqual(plan.ligne("L3")["calque"], "eau_chaude")
        self.assertEqual(plan.equipement("EV1")["hauteur"], 2.4)
        d["hauteurs_validees"] = True
        self.assertEqual(messages(d), [])

    def test_calques_dans_l_ordre(self):
        d = plan_minimal()
        d["calques_libres"] = [{"cle": "eau_glacee", "nom": "Eau glacée"}, {"cle": "gaine", "nom": "Gaines"}]
        cles = [c for c, _ in depuis_dict(d).calques()]
        self.assertEqual(cles, ["plan_de_base", "cotes", "froid_equipements", "froid_cuivres", "electricite",
                                "clim_equipements", "clim_cuivres", "eau_glacee", "gaine", "croisements", "cartouche"])

    def test_acces_par_identifiant(self):
        plan = depuis_dict(plan_minimal())
        self.assertEqual(plan.equipement("GR1")["type"], "groupe")
        self.assertEqual(plan.element("C1")[0], "cotes")
        with self.assertRaises(KeyError):
            plan.equipement("EV9")

    def test_bbox_avec_cotes_et_equipements(self):
        plan = depuis_dict(plan_minimal())
        xmin, ymin, xmax, ymax = plan.bbox()
        self.assertAlmostEqual(ymin, -1.3)   # groupe (centre −1,0 ; profondeur 0,6)
        self.assertAlmostEqual(xmin, 0.0)
        self.assertAlmostEqual(xmax, 5.0)
        self.assertAlmostEqual(ymax, 6.0)
        d = plan_minimal()
        d["cotes"][0]["decalage"] = 2.0
        self.assertAlmostEqual(depuis_dict(d).bbox()[1], -2.0)   # la ligne de cote décalée compte


class TestGeometrieDuModele(unittest.TestCase):
    def test_axe_mur_alignement(self):
        m = {"de": (0, 0), "a": (16, 0), "epaisseur": 0.2, "alignement": "droite"}
        self.assertEqual(mod.axe_mur(m), ((0.0, 0.1), (16.0, 0.1)))
        m["alignement"] = "gauche"
        self.assertEqual(mod.axe_mur(m), ((0.0, -0.1), (16.0, -0.1)))
        m["alignement"] = "axe"
        self.assertEqual(mod.axe_mur(m), ((0, 0), (16, 0)))

    def test_vecteurs_porte(self):
        attendu = {(0, "gauche"): ((1, 0), (0, 1)), (90, "gauche"): ((0, 1), (-1, 0)),
                   (180, "gauche"): ((-1, 0), (0, -1)), (270, "gauche"): ((0, -1), (1, 0)),
                   (0, "droite"): ((-1, 0), (0, 1)), (90, "droite"): ((0, -1), (-1, 0)),
                   (180, "droite"): ((1, 0), (0, -1)), (270, "droite"): ((0, 1), (1, 0))}
        for (o, sens), (ouv, bat) in attendu.items():
            with self.subTest(orientation=o, sens=sens):
                self.assertEqual(mod.vecteurs_porte(o, sens), (ouv, bat))

    def test_ligne_de_cote(self):
        c = {"de": (0, 0), "a": (12.5, 0), "cote": "haut", "decalage": 0.6}
        self.assertEqual(mod.ligne_de_cote(c), ((0.0, -0.6), (12.5, -0.6)))
        c = {"de": (0, 0), "a": (0, 8), "cote": "droite", "decalage": 1.0}
        self.assertEqual(mod.ligne_de_cote(c), ((1.0, 0.0), (1.0, 8.0)))
        self.assertIsNone(mod.normale_cote({"de": (0, 0), "a": (5, 0), "cote": "gauche"}))
        self.assertEqual(mod.texte_cote(12.5), "12,50 m")


def _mute(fonction):
    d = plan_minimal()
    fonction(d)
    return d


# (nom, mutation du plan minimal, extrait attendu dans un des messages de valider())
INCOHERENCES = [
    ("cote_incoherente", lambda d: d["cotes"][0].update(valeur=5.02), "incohérente"),
    ("ligne_ne_touche_pas", lambda d: d["lignes"][0]["points"].__setitem__(0, [2.4, 2.0]), "ne touche pas"),
    ("chambre_sans_porte", lambda d: d["chambres_froides"][0].pop("porte"), "aucune porte"),
    ("identifiant_double", lambda d: d["equipements"][1].update(id="EV1"), "en double"),
    ("calque_inconnu", lambda d: d["lignes"][0].update(calque="plomberie"), "calque « plomberie »"),
    ("type_ligne_inconnu", lambda d: d["lignes"][0].update(type="gaz_naturel"), "type « gaz_naturel »"),
    ("orientation_porte", lambda d: d["portes"][0].update(orientation=45), "orientation 45"),
    ("reference_inconnue", lambda d: d["lignes"][1].update(a="GR9"), "« GR9 »"),
    ("type_equipement", lambda d: d["equipements"][1].update(type="pompe"), "type « pompe »"),
    ("cote_cote_incompatible", lambda d: d["cotes"][0].update(cote="gauche"), "incompatible"),
    ("porte_loin_du_mur", lambda d: d["portes"][0].update(position=[3, 5.0]), "du mur M3"),
    ("chambre_non_rectangle", lambda d: d["chambres_froides"][0].update(
        polygone=[[1, 1], [4, 1], [4, 3], [2, 3], [2, 5], [1, 5]]), "rectangles"),
    ("couleur_calque_libre", lambda d: d.update(calques_libres=[{"cle": "gaine", "nom": "Gaine", "couleur": "bleu"}]),
     "couleur"),
    ("echelle_non_normalisee", lambda d: d["page"].update(echelle=130), "non normalisée"),
    ("exigence_sans_motif", lambda d: d.update(exigences={"CF1": {"cable": "non_requis"}}), "motif"),
    ("identifiant_reserve", lambda d: d["cotes"][0].update(id="cartouche-titre"), "réservé"),
    ("mur_longueur_nulle", lambda d: d["murs"].append({"id": "M5", "de": [1, 1], "a": [1, 1]}), "longueur nulle"),
    ("points_confondus", lambda d: d["lignes"][0]["points"].insert(1, [2.4, 1.15]), "confondus"),
    ("porte_non_parallele", lambda d: d["portes"][0].update(orientation=90), "parallèle"),
    ("hauteur_validee_inconnue", lambda d: d.update(hauteurs_validees=["plafond"]), "hauteurs_validees"),
    ("regime_inconnu", lambda d: d["chambres_froides"][0].update(regime="tiede"), "régime"),
    ("suffixe_reserve", lambda d: d["equipements"].append({"id": "EV1-txt", "type": "autre", "position": [0, 0]}),
     "sous-élément"),
]

ILLISIBLES = [
    ("mur_sans_extremite", lambda d: d["murs"][0].pop("a"), "« a »"),
    ("coordonnee_texte", lambda d: d["equipements"][0].update(position=["deux", 1]), "position"),
    ("equipement_sans_type", lambda d: d["equipements"][0].pop("type"), "« type »"),
    ("ligne_sans_points", lambda d: d["lignes"][0].pop("points"), "« points »"),
    ("murs_pas_une_liste", lambda d: d.update(murs={"M1": {}}), "liste"),
    ("cote_sans_valeur", lambda d: d["cotes"][0].pop("valeur"), "« valeur »"),
]


class TestIncoherences(unittest.TestCase):
    def test_au_moins_quinze_cas(self):
        self.assertGreaterEqual(len(INCOHERENCES), 15)


def _fabrique_incoherence(mutation, extrait):
    def test(self):
        msgs = messages(_mute(mutation))
        self.assertTrue(any(extrait in m for m in msgs), f"« {extrait} » absent de : {msgs}")
    return test


for _nom, _mutation, _extrait in INCOHERENCES:
    setattr(TestIncoherences, f"test_{_nom}", _fabrique_incoherence(_mutation, _extrait))


class TestFichiersIllisibles(unittest.TestCase):
    def test_json_mal_forme(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "plan.json"
            p.write_text('{"version": 1, "murs": [}', encoding="utf-8")
            with self.assertRaises(ErreurModele) as ctx:
                charger(p)
            self.assertIn("ligne 1", str(ctx.exception))

    def test_fichier_absent(self):
        with self.assertRaises(ErreurModele):
            charger(Path(tempfile.gettempdir()) / "plan-inexistant-a1.json")

    def test_racine_pas_un_objet(self):
        with self.assertRaises(ErreurModele):
            depuis_dict([1, 2, 3])

    def test_toutes_les_fautes_listees(self):
        d = plan_minimal()
        d["murs"][0].pop("a")
        d["cotes"][0].pop("valeur")
        with self.assertRaises(ErreurModele) as ctx:
            depuis_dict(d)
        self.assertIn("« a »", str(ctx.exception))
        self.assertIn("« valeur »", str(ctx.exception))


def _fabrique_illisible(mutation, extrait):
    def test(self):
        with self.assertRaises(ErreurModele) as ctx:
            depuis_dict(_mute(mutation))
        self.assertIn(extrait, str(ctx.exception))
    return test


for _nom, _mutation, _extrait in ILLISIBLES:
    setattr(TestFichiersIllisibles, f"test_{_nom}", _fabrique_illisible(_mutation, _extrait))


if __name__ == "__main__":
    unittest.main()
