"""Tests de verifier_plan.py : la boucherie passe à 0 erreur ; CHAQUE contrôle E1 à E11 a au moins un test qui le
fait échouer par mutation d'une copie (XML de plan.drawio, plan.json, plan.md, PDF fabriqué exprès à l'échelle
fausse avec PyMuPDF, PNG absent ou de mauvaise taille) ; format de verification.md / verification.json.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -p "test_verifier_plan.py" -v
Données génériques (boucherie test fictive), aucune donnée client.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import drawio  # noqa: E402
import generer  # noqa: E402
import outils_tests_plan as ot  # noqa: E402
import rendu  # noqa: E402
import verifier_plan as vp  # noqa: E402


def erreurs(r: dict) -> set[str]:
    return {c["code"] for c in r["constats"] if c["gravite"] == vp.ERREUR}


def avertissements(r: dict) -> set[str]:
    return {c["code"] for c in r["constats"] if c["gravite"] == vp.AVERTISSEMENT}


def elements(r: dict, code: str) -> list[str]:
    return [c["element"] for c in r["constats"] if c["code"] == code]


class Base(unittest.TestCase):
    """Une boucherie générée (sans rendu) + PDF/PNG fabriqués exacts ; chaque test travaille sur une copie."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.racine = Path(cls.tmp.name)
        cls.base = ot.dossier_boucherie(cls.racine, "base")
        cls.n = 0

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def copie(self) -> Path:
        type(self).n += 1
        return ot.copier(self.base, self.racine, f"copie-{self.n}")

    def verifier(self, d: Path, **kw) -> dict:
        return vp.verifier(d, **kw)


class TestBoucherie(Base):
    def test_zero_erreur_zero_avertissement(self):
        r = self.verifier(self.copie())
        self.assertEqual(r["code"], 0, r["constats"])
        self.assertEqual(r["erreurs"], 0)
        self.assertEqual(r["avertissements"], 0, r["constats"])

    def test_mesures_du_pdf(self):
        r = self.verifier(self.copie())
        self.assertAlmostEqual(r["mesures"]["regle_pt"], rendu.REGLE_PT, delta=0.01)
        self.assertEqual(set(r["mesures"]["murs_pt"]), {"M1", "M3", "M8"})      # les trois plus longs murs
        self.assertAlmostEqual(r["mesures"]["murs_pt"]["M1"], 160.0 * 72 / 25.4, delta=0.05)

    def test_rapport_ecrit(self):
        d = self.copie()
        self.verifier(d)
        md = (d / "verification.md").read_text(encoding="utf-8")
        self.assertIn("**Résultat : 0 erreur, 0 avertissement**", md)
        for code in vp.CONTROLES:
            self.assertIn(f"| {code} | ", md)
        js = json.loads((d / "verification.json").read_text(encoding="utf-8"))
        self.assertEqual(js["code"], 0)
        self.assertEqual(set(js["controles"]), set(vp.CONTROLES))

    def test_sans_pdf(self):
        d = self.copie()
        (d / "plan.pdf").unlink()
        (d / "plan.png").unlink()
        r = self.verifier(d, sans_pdf=True)
        self.assertEqual(r["code"], 0)
        self.assertEqual(r["rapport"].ignores, {"E10": "--sans-pdf", "E11": "--sans-pdf"})

    def test_fichier_manquant_code_2(self):
        d = self.copie()
        (d / "plan.drawio").unlink()
        r = self.verifier(d)
        self.assertEqual(r["code"], 2)
        self.assertIn("plan.drawio", (d / "verification.md").read_text(encoding="utf-8"))

    def test_ligne_de_commande(self):
        d = self.copie()
        with contextlib.redirect_stdout(io.StringIO()) as sortie:
            self.assertEqual(vp.main([str(d)]), 0)
        self.assertIn("0 erreur(s), 0 avertissement(s)", sortie.getvalue())


@unittest.skipIf(rendu.trouver_drawio() is None, "draw.io Desktop absent : vrai PDF non testé")
class TestBoucherieRenduReel(unittest.TestCase):
    def test_generer_puis_verifier_zero_erreur(self):
        with tempfile.TemporaryDirectory() as t:
            d = ot.dossier_boucherie(Path(t), rendu_pdf=True)
            r = vp.verifier(d)
            self.assertEqual(r["code"], 0, r["constats"])
            self.assertLessEqual(abs(r["mesures"]["regle_pt"] - rendu.REGLE_PT), 0.3)
            for m in r["mesures"]["murs_pt"].values():
                self.assertGreater(m, 400)


class TestE1(Base):
    def test_mur_deplace_de_2_px(self):
        d = self.copie()
        ot.deplacer_sommet(d, "M1", dx=2.0)
        r = self.verifier(d)
        self.assertIn("E1", erreurs(r))
        self.assertIn("M1", elements(r, "E1"))
        self.assertEqual(r["code"], 1)

    def test_page_non_a4(self):
        d = self.copie()
        ot.modifier_xml(d, lambda a: next(x for x in a.getroot().findall("diagram") if x.get("id") == "plan")
                        .find("mxGraphModel").set("pageWidth", "1654"))
        self.assertIn("page", elements(self.verifier(d), "E1"))

    def test_cartouche_a_une_autre_echelle(self):
        d = self.copie()
        ot.changer_attribut(d, "cartouche-echelle", "value", ("1:100", "1:75"))
        self.assertIn("E1", erreurs(self.verifier(d)))

    def test_equipement_ajoute_dans_le_dessin_avertit(self):
        d = self.copie()
        ot.ajouter_arete(d, "abc-1", "froid_cuivres", [(300, 300), (400, 300)],
                         "endArrow=none;html=1;strokeColor=#C62828;strokeWidth=1.5;")
        r = self.verifier(d)
        self.assertIn("abc-1", [c["element"] for c in r["constats"] if c["code"] == "E1"
                                and c["gravite"] == vp.AVERTISSEMENT])


class TestE2(Base):
    def test_texte_de_cote_modifie(self):
        d = self.copie()
        ot.changer_attribut(d, "C1", "value", ("16,00 m", "16,10 m"))
        r = self.verifier(d)
        self.assertIn("C1", elements(r, "E2"))

    def test_cote_raccourcie(self):
        d = self.copie()
        ot.deplacer_arete(d, "C1", "targetPoint", dx=-4.0)
        self.assertIn("E2", erreurs(self.verifier(d)))

    def test_cote_incoherente_dans_le_modele(self):
        d = self.copie()
        donnees = json.loads((d / "plan.json").read_text(encoding="utf-8"))
        donnees["cotes"][1]["valeur"] = 11.05
        ot.ecrire_plan(d, donnees)
        self.assertIn("C2", elements(self.verifier(d), "E2"))


class TestE3(Base):
    def test_barre_raccourcie(self):
        d = self.copie()
        ot.geometrie(d, "barre-echelle", width=38.0)
        r = self.verifier(d)
        self.assertIn("barre-echelle", elements(r, "E3"))

    def test_regle_raccourcie(self):
        d = self.copie()
        ot.geometrie(d, "regle-controle", width=390.0)
        self.assertIn("regle-controle", elements(self.verifier(d), "E3"))

    def test_texte_de_barre_faux(self):
        d = self.copie()
        ot.changer_attribut(d, "barre-echelle-txt", "value", ("1 m", "2 m"))
        self.assertIn("barre-echelle-txt", elements(self.verifier(d), "E3"))


class TestE4(Base):
    def test_etiquette_hors_zone_utile(self):
        d = self.copie()
        ot.deplacer_sommet(d, "P1", dx=-400.0)
        self.assertIn("P1", elements(self.verifier(d), "E4"))

    def test_element_du_cartouche_hors_du_cartouche(self):
        d = self.copie()
        ot.deplacer_sommet(d, "cartouche-date", dy=-300.0)
        self.assertIn("cartouche-date", elements(self.verifier(d), "E4"))


class TestE5(Base):
    def test_condensats_supprimes(self):
        d = self.copie()
        ot.supprimer_cellule(d, "LCO1")
        r = self.verifier(d)
        self.assertIn("E5", erreurs(r))
        self.assertIn("EV1", elements(r, "E5"))

    def test_aspiration_sans_groupe(self):
        d = self.copie()
        ot.changer_attribut(d, "LA3", "style", ("plan2dA=GR1", "plan2dA=TD"))
        self.assertIn("EV3", elements(self.verifier(d), "E5"))

    def test_porte_de_chambre_supprimee(self):
        d = self.copie()
        ot.supprimer_cellule(d, "CF2-porte")
        self.assertIn("CF2", elements(self.verifier(d), "E5"))

    def test_split_sans_alimentation(self):
        donnees = ot.charger_boucherie()
        donnees["lignes"] = [l for l in donnees["lignes"] if l["id"] != "LE7"]       # câble du moteur MS1
        d = ot.dossier_boucherie(self.racine, "sans-le7", donnees)
        r = self.verifier(d)
        self.assertIn("E5", erreurs(r))
        self.assertTrue({"SP1", "SP2"} <= set(elements(r, "E5")))

    def test_exigence_motivee_avertissement(self):
        donnees = ot.charger_boucherie()
        donnees["lignes"] = [l for l in donnees["lignes"] if l["id"] != "LCO1"]
        donnees["exigences"] = {"EV1": {"condensats": "non_requis", "motif": "évacuation gravitaire existante"}}
        d = ot.dossier_boucherie(self.racine, "exigence", donnees)
        r = self.verifier(d)
        self.assertNotIn("E5", erreurs(r))
        self.assertIn("E5", avertissements(r))
        self.assertEqual(r["code"], 0)


class TestE6(Base):
    def test_tableau_de_la_page_metre_falsifie(self):
        d = self.copie()
        ot.changer_attribut(d, "metre-tableau-1", "value", (">4,21 (hyp.)<", ">4,51 (hyp.)<"), page="metre")
        r = self.verifier(d)
        self.assertIn("E6", erreurs(r))
        self.assertTrue(any("page Métré" in e and "LA1" in e for e in elements(r, "E6")))

    def test_plan_md_falsifie(self):
        d = self.copie()
        md = (d / "plan.md").read_text(encoding="utf-8")
        self.assertIn("| 4,21 (hyp.) |", md)
        (d / "plan.md").write_text(md.replace("| 4,21 (hyp.) |", "| 4,51 (hyp.) |", 1), encoding="utf-8")
        r = self.verifier(d)
        self.assertTrue(any(e.startswith("plan.md") and "LA1" in e for e in elements(r, "E6")))

    def test_total_de_reseau_falsifie(self):
        d = self.copie()
        md = (d / "plan.md").read_text(encoding="utf-8")
        self.assertIn("**36,02 (hyp.)**", md)
        (d / "plan.md").write_text(md.replace("**36,02 (hyp.)**", "**37,02 (hyp.)**"), encoding="utf-8")
        self.assertTrue(any("Total" in e for e in elements(self.verifier(d), "E6")))

    def test_recalcul_depuis_le_dessin_et_non_le_modele(self):
        d = self.copie()
        ot.deplacer_arete(d, "LE7", "targetPoint", dx=20.0)       # câble raccourci de 0,51 m dans le dessin
        r = self.verifier(d)
        self.assertTrue(any("LE7" in e for e in elements(r, "E6")))

    def test_ligne_relue_par_modele_relu(self):
        d = self.copie()
        L = drawio.lire(d / "plan.drawio")
        relu = vp.modele_relu(L, json.loads((d / "plan.json").read_text(encoding="utf-8")))
        la1 = next(l for l in relu["lignes"] if l["id"] == "LA1")
        self.assertEqual(la1["type"], "aspiration")
        self.assertEqual((la1["de"], la1["a"], la1["faisceau"]), ("EV1", "CP1", "EV1-CP1"))
        self.assertAlmostEqual(la1["points"][0][0], 3.34, delta=0.001)

    def test_cable_dans_le_chemin_sur_le_modele_relu(self):
        """C2 : LE1 s'arrête sur CC1 en (3,10 ; 0,30) : 3,30 + 6,80 = 10,10 m dans le chemin jusqu'au TD. Le métré
        recalculé depuis le dessin le retrouve, même sans `a` (ligne tracée dans draw.io) ni `de` sur le chemin."""
        d = self.copie()
        L = drawio.lire(d / "plan.drawio")
        relu = vp.modele_relu(L, json.loads((d / "plan.json").read_text(encoding="utf-8")))
        le1 = next(l for l in relu["lignes"] if l["id"] == "LE1")
        self.assertEqual(le1["a"], "CC1")                              # relu dans le style draw.io
        l = vp.mtr.metrer(relu).lignes["LE1"]
        self.assertEqual((l["chemin"], l["chemin_m"], l["total_m"]), ("CC1", 10.10, 16.30))
        le1["a"] = None
        next(x for x in relu["lignes"] if x["id"] == "CC1")["de"] = None
        l = vp.mtr.metrer(relu).lignes["LE1"]
        self.assertEqual((l["chemin"], l["chemin_m"], l["total_m"]), ("CC1", 10.10, 16.30))

    def test_parcours_dans_le_chemin_recalcule_depuis_le_dessin(self):
        d = self.copie()
        ot.deplacer_arete(d, "LE1", "targetPoint", dx=20.0)       # jonction avancée de 0,51 m le long de CC1
        r = self.verifier(d)
        self.assertTrue(any("LE1" in c["element"] and "Dans le chemin" in c["attendu"]
                            for c in r["constats"] if c["code"] == "E6"), r["constats"])

    def test_colonne_dans_le_chemin_falsifiee(self):
        d = self.copie()
        md = (d / "plan.md").read_text(encoding="utf-8")
        self.assertIn("| 1,60 | 10,10 | 3,60 (hyp.) | 1,00 (hyp.) | 16,30 (hyp.) |", md)
        (d / "plan.md").write_text(md.replace("| 1,60 | 10,10 |", "| 1,60 | 0,00 |", 1), encoding="utf-8")
        r = self.verifier(d)
        self.assertTrue(any(e.startswith("plan.md") and "LE1" in e for e in elements(r, "E6")))

    def test_page_metre_imprimee_avec_hyp(self):
        """C2 (écart n° 6) : la page « Métré » porte « (hyp.) » comme plan.md, et E6 la relit sans erreur."""
        d = self.copie()
        tableaux = dict(drawio.lire(d / "plan.drawio").tableaux)
        reseau = tableaux["Métré par réseau"]
        self.assertIn(">16,30 (hyp.)<", reseau)
        self.assertIn(">86,88 (hyp.)<", reseau)                    # total électricité : 25,94 + 35,94 + 18 + 7
        self.assertIn("question 13", reseau)
        self.assertIn(">76,38 (hyp.)<", tableaux["Métré par diamètre"])   # câbles : 40,44 + 35,94
        self.assertNotIn("E6", erreurs(self.verifier(d)))


def _ajouter_cercle(racine, ident: str, cx: float, cy: float, g: dict, style: str) -> None:
    """Ajoute dans la page « Plan » un cercle de croisement `ident` centré en (cx, cy) px (taille de `g`)."""
    import xml.etree.ElementTree as ET
    root = next(d for d in racine.getroot().findall("diagram") if d.get("id") == "plan").find(".//root")
    w, h = float(g["width"]), float(g["height"])
    c = ET.SubElement(root, "mxCell", {"id": ident, "value": "", "style": style, "vertex": "1",
                                       "parent": "croisements"})
    ET.SubElement(c, "mxGeometry", {"x": f"{cx - w / 2:.2f}", "y": f"{cy - h / 2:.2f}", "width": f"{w:.2f}",
                                    "height": f"{h:.2f}", "as": "geometry"})


class TestE7(Base):
    def test_ellipse_supprimee(self):
        # C : un cercle par groupe (G1 = X1 à X3) ; le supprimer = erreur E7
        d = self.copie()
        ot.supprimer_cellule(d, "G1")
        r = self.verifier(d)
        self.assertIn("E7", erreurs(r))
        self.assertTrue(any(e.startswith("G1") and "X1-X3" in e for e in elements(r, "E7")))

    def test_ellipse_en_trop(self):
        d = self.copie()
        ot.deplacer_sommet(d, "G2", dx=60.0)
        self.assertIn("E7", erreurs(self.verifier(d)))

    def test_ellipse_par_croisement_au_lieu_du_groupe(self):
        # trois cercles X1, X2, X3 au lieu du seul cercle G1 : deux cercles en trop (le dessin d'avant le regroupement)
        d = self.copie()
        L = drawio.lire(d / "plan.drawio")
        ech = L.echelle
        style = L.brut["G1"]["style_brut"]
        g = ot.lire_geometrie(d, "G1")
        ot.supprimer_cellule(d, "G1")
        for xid, x in (("X1", 3.22), ("X2", 3.34), ("X3", 3.46)):
            cx, cy = ech.m_vers_px(x, 0.30)
            ot.modifier_xml(d, lambda racine, i=xid, cx=cx, cy=cy: _ajouter_cercle(racine, i, cx, cy, g, style))
        r = self.verifier(d)
        self.assertIn("E7", erreurs(r))
        self.assertEqual(sum(1 for c in r["constats"] if c["code"] == "E7" and "cercle en trop" in c["trouve"]), 2)

    def test_repere_du_tableau_falsifie(self):
        d = self.copie()
        html = ot.cellule(ot._arbre(d / "plan.drawio"), "metre-tableau-4", "metre").get("value")
        i = html.index(">X4<")
        j = html.index(">G2<", i)
        ot.changer_attribut(d, "metre-tableau-4", "value", (html[i:j + 4], html[i:j] + ">G1<"), page="metre")
        self.assertTrue(any("X4" in e for e in elements(self.verifier(d), "E7")))

    def test_tableau_des_croisements_falsifie(self):
        d = self.copie()
        ot.changer_attribut(d, "metre-tableau-4", "value", ("3,22 m ; 0,30 m", "3,52 m ; 0,30 m"),
                            page="metre")
        self.assertTrue(any("X1" in e for e in elements(self.verifier(d), "E7")))


class TestE8(Base):
    def test_textes_superposes(self):
        d = self.copie()
        g = ot.lire_geometrie(d, "EV1-txt")
        ot.geometrie(d, "EV2-txt", x=g["x"] + 3, y=g["y"] + 2)
        r = self.verifier(d)
        self.assertIn("E8", erreurs(r))
        self.assertTrue(any("EV1-txt" in e and "EV2-txt" in e for e in elements(r, "E8")))

    def test_texte_sur_un_equipement(self):
        d = self.copie()
        L = drawio.lire(d / "plan.drawio")
        cx, cy = L.elements["GR1"]["centre_px"]
        g = ot.lire_geometrie(d, "CF3-txt")
        ot.geometrie(d, "CF3-txt", x=cx - g["width"] / 2, y=cy - g["height"] / 2)
        self.assertTrue(any("CF3-txt / GR1" == e for e in elements(self.verifier(d), "E8")))

    def test_etiquette_sur_son_propre_equipement_ignoree(self):
        d = self.copie()
        L = drawio.lire(d / "plan.drawio")
        cx, cy = L.elements["EV1"]["centre_px"]
        g = ot.lire_geometrie(d, "EV1-txt")
        ot.geometrie(d, "EV1-txt", x=cx - g["width"] / 2, y=cy - g["height"] / 2)
        self.assertNotIn("E8", erreurs(self.verifier(d)))

    def test_etiquette_sur_une_ligne_avertissement(self):
        # C : « TD-F » posé sur le chemin de câbles CC1 = avertissement E8 (pas une erreur)
        d = self.copie()
        L = drawio.lire(d / "plan.drawio")
        cx, cy = L.echelle.m_vers_px(9.9, 2.0)                   # milieu du tronçon vertical de CC1
        g = ot.lire_geometrie(d, "TD-txt")
        ot.geometrie(d, "TD-txt", x=cx - g["width"] / 2, y=cy - g["height"] / 2)
        r = self.verifier(d)
        self.assertNotIn("E8", erreurs(r))
        self.assertIn("E8", avertissements(r))
        self.assertIn("TD-txt / CC1", elements(r, "E8"))

    def test_etiquette_sur_sa_propre_ligne_ignoree(self):
        d = self.copie()
        L = drawio.lire(d / "plan.drawio")
        cx, cy = L.echelle.m_vers_px(3.1, -0.5)                  # sur le tronçon vertical du câble LE1 (repère C1)
        g = ot.lire_geometrie(d, "LE1-txt")
        ot.geometrie(d, "LE1-txt", x=cx - g["width"] / 2, y=cy - g["height"] / 2)
        r = self.verifier(d)
        self.assertNotIn("LE1-txt / LE1", elements(r, "E8"))
        self.assertEqual([c for c in r["constats"] if c["code"] == "E8"], [])

    def test_boucherie_etiquettes_hors_des_traits(self):
        r = self.verifier(self.copie())
        self.assertEqual(elements(r, "E8"), [])


class TestE9(Base):
    def test_calque_supprime(self):
        d = self.copie()
        ot.supprimer_cellule(d, "clim_cuivres")
        r = self.verifier(d)
        self.assertIn("clim_cuivres", elements(r, "E9"))

    def test_equipement_sur_le_battant_d_une_porte(self):
        d = self.copie()
        L = drawio.lire(d / "plan.drawio")
        x, y = L.echelle.m_vers_px(1.4, 3.9)                      # dans l'emprise de la porte de CF1
        g = ot.lire_geometrie(d, "TD")
        ot.geometrie(d, "TD", x=x - g["width"] / 2, y=y - g["height"] / 2)
        self.assertIn("TD / CF1-porte", elements(self.verifier(d), "E9"))

    def test_extremite_loin_de_son_equipement(self):
        d = self.copie()
        ot.deplacer_arete(d, "LA1", "sourcePoint", dy=-12.0)       # 0,30 m au-dessus de EV1
        r = self.verifier(d)
        self.assertIn("LA1", elements(r, "E9"))

    def test_extremite_sur_une_fenetre(self):
        d = self.copie()
        L = drawio.lire(d / "plan.drawio")
        x, y = L.echelle.m_vers_px(11.5, 0.1)                      # centre de la fenêtre F3
        ot.modifier_xml(d, lambda a: [p.set("x", f"{x:.2f}") or p.set("y", f"{y:.2f}")
                                      for p in ot.cellule(a, "LCO3").find("mxGeometry").findall("mxPoint")
                                      if p.get("as") == "targetPoint"])
        self.assertTrue(any(e == "LCO3" for e in elements(self.verifier(d), "E9")))

    def test_evaporateur_dos_a_la_porte_avertissement(self):
        d = self.copie()

        def inverser(arbre):
            pts = {p.get("as"): p for p in ot.cellule(arbre, "EV1-fl").find("mxGeometry").findall("mxPoint")}
            s, t = dict(pts["sourcePoint"].attrib), dict(pts["targetPoint"].attrib)
            for k in ("x", "y"):
                pts["sourcePoint"].set(k, t[k])
                pts["targetPoint"].set(k, s[k])
        ot.modifier_xml(d, inverser)
        r = self.verifier(d)
        self.assertIn("EV1", [c["element"] for c in r["constats"] if c["code"] == "E9"
                              and c["gravite"] == vp.AVERTISSEMENT])
        self.assertNotIn("E9", erreurs(r))


class TestE10(Base):
    def test_pdf_a_l_echelle_fausse(self):
        d = self.copie()
        ot.fabriquer_pdf(d, k=0.718236)                            # PDF de draw.io non corrigé (R1 : −0,245 %)
        r = self.verifier(d)
        self.assertIn("regle-controle", elements(r, "E10"))
        self.assertIn("M1", elements(r, "E10"))

    def test_barre_fausse_dans_le_pdf(self):
        d = self.copie()
        ot.fabriquer_pdf(d, k_barre=0.70)
        r = self.verifier(d)
        self.assertEqual(elements(r, "E10"), ["barre-echelle"])

    def test_murs_faux_dans_le_pdf(self):
        d = self.copie()
        ot.fabriquer_pdf(d, k_murs=0.717)
        self.assertTrue({"M1", "M3"} <= set(elements(self.verifier(d), "E10")))

    def test_page_pdf_non_a4(self):
        d = self.copie()
        ot.fabriquer_pdf(d, page_pt=(1190.55, 841.89))
        self.assertIn("plan.pdf · page", elements(self.verifier(d), "E10"))

    def test_regle_absente_du_pdf(self):
        d = self.copie()
        import pymupdf
        doc = pymupdf.open()
        doc.new_page(width=ot.PAGE_PT[0], height=ot.PAGE_PT[1])
        (d / "plan.pdf").unlink()
        doc.save(d / "plan.pdf")
        doc.close()
        self.assertIn("regle-controle", elements(self.verifier(d), "E10"))

    def test_pdf_absent_avertissement_seulement(self):
        d = self.copie()
        (d / "plan.pdf").unlink()
        r = self.verifier(d)
        self.assertNotIn("E10", erreurs(r))
        self.assertIn("E10", avertissements(r))


class TestE11(Base):
    def test_png_absent(self):
        d = self.copie()
        (d / "plan.png").unlink()
        r = self.verifier(d)
        self.assertIn("E11", erreurs(r))
        md = (d / "verification.md").read_text(encoding="utf-8")
        self.assertIn("| Code | Gravité | Élément | Attendu | Trouvé | Conseil |", md)
        self.assertIn("| E11 | ⚠ erreur | plan.png |", md)

    def test_png_de_mauvaise_taille(self):
        d = self.copie()
        rendu.rasteriser(d / "plan.pdf", d / "plan.png", dpi=150)
        self.assertIn("E11", erreurs(self.verifier(d)))


class TestOutils(unittest.TestCase):
    def test_lire_nombre(self):
        self.assertEqual(vp.lire_nombre("1 234,50 (hyp.)"), 1234.5)
        self.assertEqual(vp.lire_nombre("**36,02**"), 36.02)
        self.assertEqual(vp.lire_nombre("−0,24"), -0.24)
        self.assertIsNone(vp.lire_nombre("à définir"))

    def test_rangs_markdown(self):
        md = "## A\n\ntexte\n\n| x | y |\n|---|---:|\n| 1 | a\\|b |\n\n## B\n"
        self.assertEqual(vp.rangs_markdown(md, "A"), [["x", "y"], ["1", "a|b"]])
        self.assertIsNone(vp.rangs_markdown(md, "C"))
        self.assertEqual(vp.rangs_markdown(md, "B"), [])

    def test_recouvrement(self):
        a = [(0, 0), (1, 0), (1, 1), (0, 1)]
        self.assertAlmostEqual(vp.recouvrement(a, [(0.5, 0.5), (2, 0.5), (2, 2), (0.5, 2)]), 0.5)
        self.assertLessEqual(vp.recouvrement(a, [(1.1, 0), (2, 0), (2, 1), (1.1, 1)]), 0)

    def test_boite_e8(self):
        b = vp.boite_e8({"boite_texte_px": (0, 0, 100, 20), "texte": "abcd\nef", "taille_police": 10})
        self.assertEqual(b, (50 - 11, 10 - 12, 50 + 11, 10 + 12))


if __name__ == "__main__":
    unittest.main()
