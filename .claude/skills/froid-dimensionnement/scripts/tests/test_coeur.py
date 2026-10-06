"""Tests du cœur du skill froid-dimensionnement : Valeur, propagation des statuts, unités, contrôles, rendu.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-dimensionnement/scripts/tests -v
Bibliothèque standard uniquement (unittest). Données génériques, aucune donnée client.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # dossier scripts/
from controles import comparer, ecart_relatif, puissance_demandee, somme  # noqa: E402
from unites import UniteRefusee, canonique, convertir  # noqa: E402
from valeur import (A_CONFIRMER, CALCULE, ESPACE, HYPOTHESE, SOURCE, Valeur, a_confirmer, calculer,  # noqa: E402
                    combiner, depuis_json, en_json, nombre_fr)


def sv(nombre, unite="kW", id="", source="plaque, photo test"):
    """Valeur sourcée de test."""
    return Valeur(nombre, unite, source, SOURCE, id=id)


def hyp(nombre, unite="kW", id="", source="hypothèse de test"):
    return Valeur(nombre, unite, source, HYPOTHESE, id=id)


def lisible(t: str) -> str:
    """Remplace l'espace insécable par une espace ordinaire pour comparer au texte attendu."""
    return t.replace(ESPACE, " ")


class TestConversions(unittest.TestCase):
    def test_kcal_h_vers_w(self):
        self.assertAlmostEqual(convertir(sv(1, "kcal/h"), "W").nombre, 1.163, places=12)

    def test_fg_h_egale_kcal_h(self):
        self.assertAlmostEqual(convertir(sv(1, "fg/h"), "W").nombre, 1.163, places=12)
        self.assertAlmostEqual(convertir(sv(1, "fg/h"), "kcal/h").nombre, 1.0, places=12)

    def test_btu_h_vers_w(self):
        self.assertAlmostEqual(convertir(sv(1, "BTU/h"), "W").nombre, 0.29307107, places=8)

    def test_tr_vers_kw(self):
        self.assertAlmostEqual(convertir(sv(1, "TR"), "kW").nombre, 3.51685, places=5)

    def test_kw_w_aller_retour(self):
        self.assertAlmostEqual(convertir(sv(1, "kW"), "W").nombre, 1000.0)
        self.assertAlmostEqual(convertir(sv(2500, "W"), "kW").nombre, 2.5)

    def test_frigories_vers_kw_et_statut(self):
        r = convertir(sv(30000, "fg/h", id="p-a"), "kW")
        self.assertAlmostEqual(r.nombre, 34.89, places=9)
        self.assertEqual(r.statut, CALCULE)
        self.assertEqual(r.entrees, ("p-a",))
        self.assertIn("1,163", r.source)
        self.assertIn("fg/h → kW", r.formule)

    def test_alias_et_meme_unite(self):
        self.assertEqual(canonique("KW"), "kW")
        self.assertEqual(canonique("Frigories/h"), "fg/h")
        v = sv(12, "kW")
        self.assertIs(convertir(v, "kw"), v)

    def test_propagation_dans_conversion(self):
        self.assertEqual(convertir(hyp(10, "TR"), "kW").statut, HYPOTHESE)
        r = convertir(a_confirmer("TR", "absent de la plaque", id="c9"), "kW")
        self.assertEqual(r.statut, A_CONFIRMER)
        self.assertIsNone(r.nombre)


class TestRefus(unittest.TestCase):
    def test_puissances_moteur_refusees(self):
        for u in ("CV", "HP", "ch", "cv", "hp"):
            with self.subTest(unite=u):
                with self.assertRaises(UniteRefusee) as ctx:
                    convertir(sv(5, u), "kW")
                self.assertIn("puissance moteur", str(ctx.exception))

    def test_vers_puissance_moteur_refusee(self):
        with self.assertRaises(UniteRefusee):
            convertir(sv(5, "kW"), "CV")

    def test_unite_inconnue(self):
        with self.assertRaises(UniteRefusee) as ctx:
            convertir(sv(5, "kWh"), "kW")
        self.assertIn("inconnue", str(ctx.exception))


class TestValeurEtPropagation(unittest.TestCase):
    def test_combiner(self):
        self.assertEqual(combiner([SOURCE, SOURCE]), SOURCE)
        self.assertEqual(combiner([SOURCE, CALCULE]), CALCULE)
        self.assertEqual(combiner([SOURCE, HYPOTHESE, CALCULE]), HYPOTHESE)
        self.assertEqual(combiner([SOURCE, A_CONFIRMER, HYPOTHESE]), A_CONFIRMER)
        self.assertEqual(combiner(["hypothese", "Sourcé"]), HYPOTHESE)
        with self.assertRaises(ValueError):
            combiner([])
        with self.assertRaises(ValueError):
            combiner(["peut-être"])

    def test_sources_seules_donnent_calcule(self):
        r = calculer(lambda: 2 * 3, "kW", "a × b", [sv(2, id="a"), sv(3, "", id="b")])
        self.assertEqual((r.nombre, r.statut, r.entrees), (6.0, CALCULE, ("a", "b")))

    def test_source_plus_hypothese_donne_hypothese(self):
        a, b = sv(2, id="a"), hyp(3, "", id="b")
        r = calculer(lambda: a.nombre * b.nombre, "kW", "a × b", [a, b])
        self.assertEqual((r.nombre, r.statut), (6.0, HYPOTHESE))

    def test_a_confirmer_donne_a_confirmer_sans_nombre(self):
        a, b = sv(2, id="a"), a_confirmer("", "illisible sur la photo", id="b")
        appels = []
        r = calculer(lambda: appels.append(1) or a.nombre * b.nombre, "kW", "a × b", [a, b])
        self.assertEqual(r.statut, A_CONFIRMER)
        self.assertIsNone(r.nombre)
        self.assertEqual(appels, [])                     # la fonction n'est jamais appelée avec None
        self.assertIn("bloqué par : b", r.source)

    def test_nombre_deja_calcule_ignore_si_entree_manquante(self):
        r = calculer(42.0, "kW", "a + b", [sv(2, id="a"), a_confirmer("kW", "absent", id="b")])
        self.assertIsNone(r.nombre)

    def test_division_par_zero_et_resultat_non_fini(self):
        r = calculer(lambda: 1 / 0, "kW", "a ÷ 0", [sv(1, id="a")])
        self.assertEqual((r.nombre, r.statut), (None, A_CONFIRMER))
        r = calculer(float("nan"), "kW", "x", [sv(1, id="a")])
        self.assertEqual((r.nombre, r.statut), (None, A_CONFIRMER))

    def test_validation(self):
        with self.assertRaises(ValueError):
            Valeur(None, "kW", "plaque", SOURCE)            # pas de nombre mais « sourcé »
        with self.assertRaises(ValueError):
            Valeur(3.0, "kW", "plaque", A_CONFIRMER)        # un nombre mais « à confirmer »
        with self.assertRaises(ValueError):
            Valeur(3.0, "kW", "  ", SOURCE)                 # source vide
        with self.assertRaises(ValueError):
            Valeur(3.0, "kW", "plaque", "probable")         # statut inconnu
        with self.assertRaises(ValueError):
            Valeur(float("inf"), "kW", "plaque", SOURCE)    # nombre non fini
        self.assertEqual(Valeur(3, "kW", "plaque", "hypothese").statut, HYPOTHESE)
        self.assertIsInstance(Valeur(3, "kW", "plaque", SOURCE).nombre, float)


class TestJson(unittest.TestCase):
    def test_aller_retour_dict(self):
        v = calculer(lambda: 6.5, "kW", "a + b", [sv(2, id="a"), hyp(4.5, id="b")], id="total")
        self.assertEqual(Valeur.depuis_dict(v.vers_dict()), v)

    def test_aller_retour_json_structure(self):
        donnees = {"postes": [{"nom": "poste test", "compresseurs": [sv(12.5, id="c1"), a_confirmer("kW", "absent", id="c2")]}],
                   "marge": hyp(10, "%", id="marge"), "note": "texte libre"}
        relu = depuis_json(en_json(donnees))
        self.assertEqual(relu, donnees)
        self.assertIsInstance(relu["postes"][0]["compresseurs"][1], Valeur)
        self.assertIn("à confirmer", en_json(donnees))       # UTF-8 lisible, pas d'échappement à

    def test_cles_manquantes_ou_inconnues(self):
        with self.assertRaises(ValueError):
            Valeur.depuis_dict({"nombre": 1, "unite": "kW", "source": "plaque"})
        with self.assertRaises(ValueError):
            depuis_json('{"nombre": 1, "unité": "kW", "source": "plaque", "statut": "sourcé"}')


class TestControles(unittest.TestCase):
    def test_ecart_relatif_par_rapport_a_la_moyenne(self):
        r = ecart_relatif(sv(110, id="m1"), sv(90, id="m2"))
        self.assertAlmostEqual(r.nombre, 20.0)
        self.assertEqual((r.unite, r.statut), ("%", CALCULE))
        self.assertAlmostEqual(ecart_relatif(sv(90), sv(110)).nombre, 20.0)

    def test_ecart_avec_conversion_et_hypothese(self):
        r = ecart_relatif(hyp(11.63, "kW", id="m1"), sv(10000, "kcal/h", id="m2"))
        self.assertAlmostEqual(r.nombre, 0.0, places=9)
        self.assertEqual(r.statut, HYPOTHESE)

    def test_ecart_moyenne_nulle(self):
        self.assertEqual(ecart_relatif(sv(0), sv(0)).statut, A_CONFIRMER)

    def test_comparer_depasse(self):
        seuil = hyp(15, "%", id="seuil", source="hypothèse en attente de la réponse de Loïc")
        r = comparer(sv(110, id="m1"), sv(90, id="m2"), seuil)
        self.assertTrue(r["depassement"])
        self.assertIn("seuil", r["alerte"])
        self.assertIn("m1 plus élevé", r["alerte"])
        self.assertIn("hypothèse en attente", r["alerte"])

    def test_comparer_sous_le_seuil(self):
        seuil = sv(25, "%", id="seuil", source="règle de test")
        r = comparer(sv(110, id="m1"), sv(90, id="m2"), seuil)
        self.assertFalse(r["depassement"])
        self.assertEqual(r["alerte"], "")

    def test_comparer_non_verifiable(self):
        r = comparer(sv(110, id="m1"), a_confirmer("kW", "point catalogue introuvable", id="m2"), sv(15, "%", id="s"))
        self.assertIsNone(r["depassement"])
        self.assertIn("non vérifiable", r["alerte"])

    def test_comparer_seuil_en_pourcent(self):
        with self.assertRaises(ValueError):
            comparer(sv(1), sv(1), sv(15, "kW"))

    def test_somme(self):
        r = somme([sv(10.5, id="c1"), sv(12, id="c2"), sv(7.5, id="c3")], "kW", id="poste")
        self.assertEqual((r.nombre, r.statut), (30.0, CALCULE))
        self.assertEqual(r.formule, "somme(c1, c2, c3)")
        self.assertEqual(r.entrees, ("c1", "c2", "c3"))

    def test_somme_propagation_et_unites(self):
        self.assertEqual(somme([sv(10, id="c1"), hyp(5, id="c2")], "kW").statut, HYPOTHESE)
        r = somme([sv(10, id="c1"), a_confirmer("kW", "plaque illisible", id="c2")], "kW")
        self.assertEqual((r.nombre, r.statut), (None, A_CONFIRMER))
        self.assertIn("c2", r.source)
        r = somme([sv(1, "kW", id="c1"), sv(1000, "W", id="c2")], "kW")
        self.assertAlmostEqual(r.nombre, 2.0)
        self.assertEqual(r.entrees, ("c1", "c2"))
        with self.assertRaises(ValueError):
            somme([], "kW")

    def test_puissance_demandee(self):
        marge = hyp(10, "%", id="marge", source="hypothèse en attente de la réponse de Loïc")
        r = puissance_demandee(sv(100, id="existante"), marge, id="demandee")
        self.assertAlmostEqual(r.nombre, 110.0)
        self.assertEqual((r.unite, r.statut, r.id), ("kW", HYPOTHESE, "demandee"))
        self.assertEqual(r.formule, "existante × (1 + marge ÷ 100)")
        r = puissance_demandee(sv(100, id="existante"), sv(10, "%", id="marge", source="règle de test"))
        self.assertEqual(r.statut, CALCULE)
        with self.assertRaises(ValueError):
            puissance_demandee(sv(100), sv(10, "kW"))


class TestRendu(unittest.TestCase):
    def test_milliers_et_virgule(self):
        self.assertEqual(lisible(sv(1234.5).texte()), "1 234,5 kW")
        self.assertEqual(sv(1234.5).texte(), f"1{ESPACE}234,5{ESPACE}kW")
        self.assertEqual(lisible(sv(1234567.89).texte()), "1 234 567,9 kW")

    def test_marques_de_statut(self):
        self.assertEqual(lisible(sv(35.2).texte()), "35,2 kW")
        self.assertEqual(lisible(hyp(35.2).texte()), "35,2 kW (hyp.)")
        self.assertEqual(a_confirmer("kW", "absent").texte(), "à confirmer")
        self.assertEqual(lisible(calculer(35.24, "kW", "x", [sv(1, id="a")]).texte()), "35,2 kW")

    def test_decimales_par_unite_et_arrondi(self):
        self.assertEqual(lisible(sv(1163, "W").texte()), "1 163 W")
        self.assertEqual(lisible(sv(-30, "°C").texte()), "-30,0 °C")
        self.assertEqual(lisible(sv(12.345, "%").texte()), "12,3 %")
        self.assertEqual(lisible(sv(0.75, "").texte()), "0,75")
        self.assertEqual(nombre_fr(0.125, 2), "0,13")          # arrondi au plus proche, pas « au pair »
        self.assertEqual(nombre_fr(-0.04, 1), "0,0")           # pas de « -0,0 »
        self.assertEqual(lisible(sv(35.2).texte(decimales=2)), "35,20 kW")

    def test_source_texte(self):
        self.assertEqual(sv(12, source="plaque, photo p01-1").source_texte(), "plaque, photo p01-1")
        r = somme([sv(1, id="c1"), sv(2, id="c2")], "kW")
        self.assertEqual(r.source_texte(), "calcul · formule : somme(c1, c2) · entrées : c1, c2")


if __name__ == "__main__":
    unittest.main()
