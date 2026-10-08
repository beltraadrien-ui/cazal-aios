"""Tests du Lot 7, première moitié : longueurs de cuivre estimées d'après le plan (plan/metre.json) et plan du local
(plan/plan.pdf) joint en fin du PDF de la demande, sur un jeu entièrement fictif.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-demande-fournisseur/scripts/tests -v
Fixtures (répertoire temporaire, rien n'est écrit dans le dépôt) : le dossier fictif de test_assembler.py (calculs.py
réel), un plan/metre.json conforme au contrat du plan des Lots 5-6 § 11 (un réseau cuivre froid avec une ligne mesurée
sur chantier, un réseau clim, un réseau d'électricité et un réseau libre qui doivent être exclus), un plan/plan.pdf
A4 paysage de 2 pages fabriqué avec PyMuPDF (plan avec cartouche au nom du client fictif, puis une page « Métré » qui
ne doit pas être jointe). La chaîne réelle (Edge ou Chrome) est essayée si un navigateur est présent ; les contrôles
mis en échec par mutation travaillent sur un PDF factice « comme Edge » (texte de la page HTML, pagination
« Page k / N ») auquel la page du plan est ajoutée par generer_livrable.fusionner_annexes.
"""
from __future__ import annotations

import contextlib
import html as html_mod
import io
import json
import re
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import pymupdf

TESTS = Path(__file__).resolve().parent
SCRIPTS = TESTS.parent
for _chemin in (SCRIPTS, SCRIPTS.parents[1] / "froid-dimensionnement" / "scripts", TESTS):
    if str(_chemin) not in sys.path:
        sys.path.insert(0, str(_chemin))
import assembler  # noqa: E402
import controler as ctl  # noqa: E402
import generer_livrable as gl  # noqa: E402
import test_assembler as ta  # noqa: E402
import test_controler as tc  # noqa: E402

NBSP = " "
DATE = "2026-01-02"
PHRASE = ("Toutes les longueurs sont des estimations d'après le plan (tracé et hauteurs de pose), sauf celles "
          "marquées « (mesurée) », relevées sur chantier.")
A4_PAYSAGE = (841.92, 594.96)


# ── Fixtures ────────────────────────────────────────────────────────────────────────────────────────

def ligne(id_, troncon, de, a, type_, type_nom, en_plan, vertical, total, origine="estimee"):
    mesuree = origine == "mesuree"
    return {"id": id_, "troncon": troncon, "de": de, "a": a, "type": type_, "type_nom": type_nom,
            "en_plan_m": en_plan, "chemin_m": 0.0, "vertical_m": vertical, "reserve_m": 0.0, "total_m": total,
            "origine": origine, "estimation_plan_m": round(en_plan + vertical, 2),
            "longueur_mesuree_m": total if mesuree else None,
            "mesure": {"par": "frigoriste (essai)", "date": "2026-10-08", "note": "télémètre"} if mesuree else None,
            "diametre": "à définir par le fournisseur"}


def metre_fictif(plan_version: int = 9) -> dict:
    """plan/metre.json conforme au contrat : froid (dont LA2 mesurée sur chantier), électricité, clim, libre."""
    froid = [ligne("LA1", "Évaporateur CF1 (EV1) → Centrale positive", "EV1", "CP1", "aspiration", "Aspiration",
                   1.81, 2.40, 4.21),
             ligne("LL1", "Évaporateur CF1 (EV1) → Centrale positive", "EV1", "CP1", "liquide", "Liquide",
                   1.81, 2.40, 4.21),
             ligne("LA2", "Évaporateur CF2 (EV2) → Centrale positive", "EV2", "CP1", "aspiration", "Aspiration",
                   8.03, 2.40, 12.00, "mesuree"),
             ligne("LCO1", "Évaporateur CF1 (EV1) → évacuation", "EV1", None, "condensats", "Condensats",
                   0.79, 2.20, 2.99)]
    clim = [ligne("LG1", "Split salle (SP1) → Moteur de clim (MC1)", "SP1", "MC1", "clim_gaz", "Clim gaz",
                  4.32, 2.20, 6.52),
            ligne("LLC1", "Split salle (SP1) → Moteur de clim (MC1)", "SP1", "MC1", "clim_liquide", "Clim liquide",
                  4.40, 2.20, 6.60)]
    elec = [ligne("LE1", "Centrale positive (CP1) → Tableau froid (TD)", "CP1", "TD", "cable", "Câble",
                  1.60, 3.60, 16.37)]
    libre = [ligne("EG1", "Ventilo vente (VC1) → Groupe eau glacée (GEG1)", "VC1", "GEG1", "eau_glacee", "Eau glacée",
                   28.21, 2.40, 30.61)]
    return {
        "version": 1, "genere_le": "2026-10-08T10:12:00", "plan_version": plan_version,
        "dossier": "2026-01-01-boucherie-fictivor", "echelle": "1:100", "phrase": PHRASE, "hauteurs_validees": False,
        "reseaux": [
            {"cle": "froid_cuivres", "nom": "Froid : cuivres et condensats", "famille": "cuivre_froid",
             "lignes": froid, "total_m": 23.41, "total_estime_m": 11.41, "total_mesure_m": 12.0},
            {"cle": "electricite", "nom": "Électricité (froid + clim)", "famille": "electricite",
             "lignes": elec, "total_m": 16.37, "total_estime_m": 16.37, "total_mesure_m": 0.0},
            {"cle": "clim_cuivres", "nom": "Clim : cuivres", "famille": "cuivre_clim",
             "lignes": clim, "total_m": 13.12, "total_estime_m": 13.12, "total_mesure_m": 0.0},
            {"cle": "eau_glacee", "nom": "Eau glacée", "famille": "libre",
             "lignes": libre, "total_m": 30.61, "total_estime_m": 30.61, "total_mesure_m": 0.0}],
        "par_type": [{"reseau": "froid_cuivres", "type": "aspiration", "type_nom": "Aspiration", "total_m": 16.21,
                      "origine": "mixte"}],
        "recapitulatif": [{"cle": "froid_cuivres", "nom": "Froid : cuivres et condensats", "total_m": 23.41}]}


def ecrire_plan_pdf(chemin: Path, taille=A4_PAYSAGE, titre: str = "Boucherie Fictivor") -> None:
    """plan.pdf fictif : page 1 = plan (murs, chambre, cuivre, étiquettes, cartouche au nom du client fictif),
    page 2 = métré (ne doit jamais être jointe)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    p = doc.new_page(width=taille[0], height=taille[1])
    p.draw_rect(pymupdf.Rect(60, 60, 560, 400), color=(0, 0, 0), width=2)
    p.draw_rect(pymupdf.Rect(80, 80, 200, 180), color=(0.2, 0.3, 0.8), width=1)
    p.draw_line((300, 120), (500, 120), color=(0.8, 0.1, 0.1), width=1.5)
    for (x, y), t in (((90, 100), "CF1 +2 °C"), ((90, 112), "Viande"), ((300, 300), "Salle de vente"),
                      ((320, 115), "Centrale positive C1"), ((420, 250), "Laboratoire de découpe")):
        p.insert_text((x, y), t, fontsize=8)
    p.draw_rect(pymupdf.Rect(30, 470, 420, 570), color=(0.5, 0.55, 0.6), width=0.8)
    p.insert_text((35, 490), f"{titre} : plan froid et clim", fontsize=8, fontname="hebo")
    p.insert_text((35, 502), "Dossier : 2026-01-01-boucherie-fictivor", fontsize=6)
    p.insert_text((35, 516), "Échelle 1:100", fontsize=8, fontname="hebo")
    p.insert_text((35, 530), "Imprimer à 100 %, sans ajustement à la page : la barre doit mesurer 1 cm à la règle.",
                  fontsize=6)
    p2 = doc.new_page(width=taille[0], height=taille[1])
    p2.insert_text((40, 60), "Métré par réseau (page à ne pas joindre)", fontsize=10)
    doc.save(str(chemin))
    doc.close()


def dossier_fictif(racine: Path, metre: dict | None = None, plan: bool = True) -> Path:
    """Dossier de test_assembler.py avec de vraies images, plan/metre.json (si `metre`) et plan/plan.pdf (si `plan`)."""
    racine.mkdir(parents=True, exist_ok=True)
    dossier = ta.construire_dossier(racine)
    for i, photo in enumerate(sorted((dossier / "sources" / "photos").glob("*/*.jpeg"))):
        tc.fabriquer_photo(photo, (40 + 20 * i % 200, 90, 120))
    if metre is not None:
        (dossier / "plan").mkdir(exist_ok=True)
        (dossier / "plan" / "metre.json").write_text(json.dumps(metre, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")
    if plan:
        ecrire_plan_pdf(dossier / "plan" / "plan.pdf")
    return dossier


def pdf_factice(page_html: str, chemin: Path) -> None:
    """PDF « comme Edge » : texte de la page HTML sur des pages A4, pagination « Page k / N » dès la page 2."""
    texte = html_mod.unescape(re.sub(r"<style>.*?</style>|<[^>]+>", " ", page_html, flags=re.S))
    lignes = textwrap.wrap(" ".join(texte.split()), 110)
    par_page = 60
    n = max(2, -(-len(lignes) // par_page))
    doc = pymupdf.open()
    for k in range(n):
        page = doc.new_page()
        for j, l in enumerate(lignes[k * par_page:(k + 1) * par_page]):
            page.insert_text((40, 60 + 11.5 * j), l, fontsize=8)
        if k:
            page.insert_text((470, 820), f"Page {k + 1} / {n}", fontsize=7)
    doc.save(str(chemin))
    doc.close()


def refaire_pdf(dossier: Path, version: str = "v1", remplacer=(), fusion: bool = True, anonymiser: bool = True,
                documents=None) -> Path:
    """PDF factice de la version depuis sa page HTML (remplacements (avant, après) appliqués au texte), puis annexes
    fusionnées comme generer_livrable.py le fait après Edge."""
    dv = dossier / gl.SOUS_DOSSIER / version
    page = (dv / f"demande-{version}.html").read_text(encoding="utf-8")
    for avant, apres in remplacer:
        if avant not in page:
            raise AssertionError(f"{avant!r} absent de la page")
        page = page.replace(avant, apres, 1)
    pdf = dv / f"demande-{version}.pdf"
    pdf_factice(page, pdf)
    if fusion:
        demande = json.loads((dv / "demande.json").read_text(encoding="utf-8"))
        docs = gl.documents_annexes(demande, dv) if documents is None else documents
        if docs:
            anon = gl.motifs_client(dv) if anonymiser and demande.get("anonymise") else None
            gl.fusionner_annexes(pdf, docs, anon)
    return pdf


def lancer_assembler(*args) -> tuple[int, str]:
    with contextlib.redirect_stdout(io.StringIO()) as sortie:
        code = assembler.main([str(a) for a in args])
    return code, sortie.getvalue()


def par_numero(dossier: Path, version: str = "v1") -> dict[int, ctl.Controle]:
    return {c.numero: c for c in ctl.controler(dossier, version)}


# ── assembler.py ─────────────────────────────────────────────────────────────────────────────────────

class TestAssemblerLongueurs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.dossier = dossier_fictif(Path(cls.tmp.name), metre_fictif())
        cls.g = assembler.assembler(cls.dossier, "grossiste", date=DATE)
        cls.f = assembler.assembler(cls.dossier, "fabricant", destinataire="Jean Essai, Fournisseur Fictif",
                                    tutoiement=True, date=DATE)
        cls.dg, cls.df = cls.g["demande"], cls.f["demande"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_contrat_longueurs_et_schema(self):
        for d in (self.dg, self.df):
            self.assertEqual(assembler.verifier_schema(d), [])
            lg = d["longueurs"]
            self.assertEqual(set(lg), {"phrase", "reseaux", "diametres", "source", "plan_version"})
            self.assertEqual(lg["phrase"], PHRASE)
            self.assertEqual(lg["diametres"], "Diamètres et charge de fluide à définir par vos soins.")
            self.assertEqual(lg["source"], "plan/metre.json")
            self.assertEqual(lg["plan_version"], 9)
            for r in lg["reseaux"]:
                self.assertEqual(set(r), {"cle", "nom", "famille", "lignes", "total_m", "origine"})
                for l in r["lignes"]:
                    self.assertEqual(set(l), {"troncon", "type_nom", "total_m", "origine"})

    def test_seuls_les_reseaux_de_cuivre(self):
        lg = self.dg["longueurs"]
        self.assertEqual([r["cle"] for r in lg["reseaux"]], ["froid_cuivres", "clim_cuivres"])
        self.assertEqual({r["famille"] for r in lg["reseaux"]}, {"cuivre_froid", "cuivre_clim"})
        texte = json.dumps(self.dg, ensure_ascii=False)
        for intrus in ("16.37", "30.61", "Électricité", "Eau glacée", "Câble"):
            self.assertNotIn(intrus, texte)

    def test_nombres_et_origines_recopies(self):
        froid, clim = self.dg["longueurs"]["reseaux"]
        self.assertEqual([l["total_m"] for l in froid["lignes"]], [4.21, 4.21, 12.0, 2.99])
        self.assertEqual([l["origine"] for l in froid["lignes"]], ["estimee", "estimee", "mesuree", "estimee"])
        self.assertEqual((froid["total_m"], froid["origine"]), (23.41, "mixte"))
        self.assertEqual((clim["total_m"], clim["origine"]), (13.12, "estimee"))
        self.assertEqual(froid["lignes"][0]["troncon"], "Évaporateur CF1 (EV1) → Centrale positive")
        self.assertEqual(clim["lignes"][1]["type_nom"], "Clim liquide")

    def test_annexe_plan_chemin_relatif(self):
        for r in (self.g, self.f):
            docs = r["demande"]["annexes"]["documents"]
            self.assertEqual(docs, [{"type": "plan", "fichier": "../../plan/plan.pdf",
                                     "titre": "Plan du local (A4, échelle écrite sur le plan)", "pages": 1}])
            self.assertTrue((r["dossier_sortie"] / docs[0]["fichier"]).resolve().is_file())
            self.assertEqual(r["demande"]["annexes"]["plan_implantation"], "plan du local en annexe")

    def test_mail_une_phrase_sans_tableau_ni_longueur(self):
        phrase = ("Les longueurs de cuivre estimées d'après le plan figurent dans le PDF, avec le plan du local en "
                  "annexe.")
        for d in (self.dg, self.df):
            corps = d["mail"]["corps"]
            self.assertEqual(corps.count(phrase), 1)
            self.assertNotIn("|", corps)
            for n in ("4,21", "23,41", "13,12", "12,00"):
                self.assertNotIn(n, corps)

    def test_renvoi_regulation_renumerote(self):
        armoire = next(pt["lettre"] for pt in self.dg["demande"]["points"] if "armoire" in pt["titre"].lower())
        for pj in self.dg["postes"]:                     # contexte, chambres, production, évaporateurs, longueurs
            self.assertIn(f"Régulation : voir § 6 {armoire})", pj["remplacement"])

    def test_avertissements(self):
        self.assertTrue(any("hauteurs de pose" in a for a in self.g["avertissements"]))
        code, sortie = lancer_assembler(self.dossier, "--variante", "grossiste", "--date", DATE)
        self.assertEqual(code, 0, sortie)
        self.assertIn("longueurs de cuivre (plan v9)", sortie)
        self.assertIn("23,41 m", sortie)
        self.assertIn("annexe fusionnée en fin de PDF", sortie)


class TestAssemblerCas(unittest.TestCase):
    """Cas particuliers : chacun son dossier."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.racine = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sans_plan_ni_metre(self):
        d = assembler.assembler(dossier_fictif(self.racine, None, plan=False), "grossiste", date=DATE)["demande"]
        self.assertEqual(d["longueurs"], {"absentes": True,
                                          "phrase": "Longueurs de lignes non relevées, à estimer par vos soins."})
        self.assertEqual(d["annexes"]["documents"], [])
        self.assertNotIn("longueurs", d["mail"]["corps"].lower())
        self.assertNotIn("plan du local", d["mail"]["corps"].lower())
        self.assertIn("voir § 5", d["postes"][0]["remplacement"])

    def test_metre_sans_plan_pdf_et_plan_sans_metre(self):
        d = assembler.assembler(dossier_fictif(self.racine / "a", metre_fictif(), plan=False), "grossiste",
                                date=DATE)["demande"]
        self.assertIn("Les longueurs de cuivre estimées d'après le plan figurent dans le PDF.", d["mail"]["corps"])
        self.assertNotIn("plan du local", d["mail"]["corps"])
        self.assertEqual(d["annexes"]["documents"], [])
        d = assembler.assembler(dossier_fictif(self.racine / "b", None, plan=True), "grossiste", date=DATE)["demande"]
        self.assertTrue(d["longueurs"]["absentes"])
        self.assertIn("Le plan du local figure en annexe du PDF.", d["mail"]["corps"])
        self.assertEqual(len(d["annexes"]["documents"]), 1)

    def test_nom_du_client_dans_un_troncon(self):
        metre = metre_fictif()
        metre["reseaux"][0]["lignes"][0]["troncon"] = "Vitrine Fictivor (VT1) → Centrale positive"
        dossier = dossier_fictif(self.racine, metre)
        g = assembler.assembler(dossier, "grossiste", date=DATE)["demande"]
        troncon = g["longueurs"]["reseaux"][0]["lignes"][0]["troncon"]     # masqué par le mécanisme commun
        self.assertRegex(troncon, r"^Vitrine (le client|\(adresse mail retirée\)) \(VT1\) → Centrale positive$")
        self.assertNotIn("fictivor", json.dumps(g["longueurs"], ensure_ascii=False).lower())
        self.assertEqual(g["longueurs"]["reseaux"][0]["lignes"][0]["total_m"], 4.21)          # chiffre intact
        f = assembler.assembler(dossier, "fabricant", destinataire="Jean Essai, Fournisseur Fictif", date=DATE)
        self.assertEqual(f["demande"]["longueurs"]["reseaux"][0]["lignes"][0]["troncon"],
                         "Vitrine Fictivor (VT1) → Centrale positive")

    def test_metre_hors_contrat_refuse(self):
        mutations = {
            "version": lambda m: m.update(version=2),
            "origine": lambda m: m["reseaux"][0]["lignes"][1].update(origine="supposee"),
            "total": lambda m: m["reseaux"][2]["lignes"][0].pop("total_m"),
            "négatif": lambda m: m["reseaux"][0].update(total_m=-1),
        }
        for nom, muter in mutations.items():
            with self.subTest(nom=nom):
                metre = metre_fictif()
                muter(metre)
                dossier = dossier_fictif(self.racine / nom, metre)
                code, sortie = lancer_assembler(dossier, "--variante", "grossiste", "--date", DATE)
                self.assertEqual(code, 1, sortie)
                self.assertIn("hors contrat", sortie)
                self.assertFalse((dossier / "3-demande-fournisseur" / "v1").exists())
        dossier = dossier_fictif(self.racine / "illisible", None)
        (dossier / "plan" / "metre.json").write_text("{pas du json", encoding="utf-8")
        code, sortie = lancer_assembler(dossier, "--variante", "grossiste")
        self.assertEqual(code, 1, sortie)
        self.assertIn("illisible", sortie)

    def test_reseaux_exclus_jamais_bloquants(self):
        metre = metre_fictif()
        metre["reseaux"][1]["lignes"][0].pop("total_m")           # électricité mal formée : ignorée
        metre["reseaux"][3]["famille"] = "inconnue"
        r = assembler.assembler(dossier_fictif(self.racine, metre), "grossiste", date=DATE)
        self.assertEqual([x["cle"] for x in r["demande"]["longueurs"]["reseaux"]], ["froid_cuivres", "clim_cuivres"])
        self.assertTrue(any("famille inconnue" in a for a in r["avertissements"]))

    def test_metre_sans_cuivre(self):
        metre = metre_fictif()
        metre["reseaux"] = [x for x in metre["reseaux"] if x["famille"] in ("electricite", "libre")]
        r = assembler.assembler(dossier_fictif(self.racine, metre), "grossiste", date=DATE)
        self.assertTrue(r["demande"]["longueurs"]["absentes"])
        self.assertTrue(any("aucun réseau de cuivre" in a for a in r["avertissements"]))

    def test_schema_detecte_les_ecarts_de_longueurs(self):
        d = assembler.assembler(dossier_fictif(self.racine, metre_fictif()), "grossiste", date=DATE,
                                ecrire=False)["demande"]
        mauvais = json.loads(json.dumps(d))
        mauvais["longueurs"]["reseaux"][0]["famille"] = "electricite"
        mauvais["longueurs"]["reseaux"][1]["lignes"][0]["origine"] = "supposee"
        mauvais["annexes"]["documents"][0]["pages"] = 0
        erreurs = assembler.verifier_schema(mauvais)
        self.assertTrue(any("famille" in e for e in erreurs), erreurs)
        self.assertTrue(any("lignes[0]" in e for e in erreurs), erreurs)
        self.assertTrue(any("documents[0]" in e for e in erreurs), erreurs)


# ── generer_livrable.py ──────────────────────────────────────────────────────────────────────────────

class TestRendu(unittest.TestCase):
    """Page HTML (sans navigateur) : place du chapitre, tableaux, ligne « non relevées », annexe listée."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        racine = Path(cls.tmp.name)
        cls.avec = dossier_fictif(racine / "avec", metre_fictif())
        assembler.assembler(cls.avec, "grossiste", date=DATE)
        cls.r = gl.generer(cls.avec, "v1", pdf=False)
        cls.html = cls.r["html"].read_text(encoding="utf-8")
        cls.sans = dossier_fictif(racine / "sans", None, plan=False)
        assembler.assembler(cls.sans, "grossiste", date=DATE)
        cls.html_sans = gl.generer(cls.sans, "v1", pdf=False)["html"].read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def chapitre(self) -> str:
        return re.search(r'<section class="chapitre" id="longueurs">(.*?)</section>', self.html, re.S).group(1)

    def test_longueur_fr(self):
        self.assertEqual(gl.longueur_fr(4.21), "4,21")
        self.assertEqual(gl.longueur_fr(12), "12,00")
        self.assertEqual(gl.longueur_fr(1234.5), f"1{NBSP}234,50")
        self.assertEqual(gl.longueur_fr("à confirmer"), "à confirmer")

    def test_chapitre_entre_l_existant_et_la_demande(self):
        titres = [(n, html_mod.unescape(t)) for n, t in
                  re.findall(r'<h1 class="chapitre-titre"><span class="num">(\d+)\.</span>(.*?)</h1>', self.html)]
        attendus = ["Contexte", "Les chambres à traiter", "La production frigorifique existante",
                    "Les évaporateurs en place", "Longueurs de cuivre (estimées d'après le plan)"]
        self.assertEqual(titres[:5], [(str(i), t) for i, t in enumerate(attendus, 1)])
        self.assertEqual([n for n, _ in titres], [str(i) for i in range(1, 9)])
        self.assertTrue(titres[5][1].startswith("Notre demande"))
        sommaire = html_mod.unescape(re.search(r'<nav class="sommaire">(.*?)</nav>', self.html, re.S).group(1))
        self.assertIn("5.</span>Longueurs de cuivre (estimées d'après le plan)", sommaire)

    def test_tableau_par_reseau(self):
        ch = self.chapitre()
        self.assertEqual(re.findall(r'data-reseau="([^"]+)"', ch), ["froid-cuivres", "clim-cuivres"])
        self.assertLess(ch.index("Toutes les longueurs sont des estimations"), ch.index("<table"))
        self.assertGreater(ch.index("Diamètres et charge de fluide à définir par vos soins."), ch.rindex("</table>"))
        self.assertIn("<th>Tronçon</th><th>Type</th><th class=\"num\">Longueur (m)</th>", ch)
        self.assertEqual(ch.count("<tr>"), 4 + 2 + 2)            # en-têtes et lignes ; totaux en tr.sous-total
        self.assertEqual(ch.count('class="sous-total"'), 2)
        self.assertIn(f"<td>Évaporateur CF1 (EV1) → Centrale positive</td><td>Aspiration</td>"
                      "<td class=\"num\">4,21</td>", ch)
        self.assertIn('<td class="num">23,41</td>', ch)
        self.assertIn('<td class="num">13,12</td>', ch)
        self.assertNotIn(f"{NBSP}m<", ch)                         # l'unité est dans l'en-tête seulement
        for intrus in ("16,37", "30,61", "Électricité", "Eau glacée"):
            self.assertNotIn(intrus, self.html)

    def test_marque_mesuree_seulement_sur_la_ligne_mesuree(self):
        ch = self.chapitre()
        self.assertEqual(ch.count('<span class="mesuree">(mesurée)</span>'), 1)
        self.assertEqual(ch.count("(mesurée)"), 2)               # la phrase d'estimation cite la marque
        self.assertIn('<td class="num">12,00 <span class="mesuree">(mesurée)</span></td>', ch)

    def test_annexe_listee(self):
        annexes = re.search(r'id="annexes">(.*?)</section>', self.html, re.S).group(1)
        self.assertIn("plan du local en annexe", annexes)
        self.assertIn("Plan du local (A4, échelle écrite sur le plan) :", annexes)
        self.assertIn("dernière page de ce document", annexes)

    def test_sans_metre_une_ligne_dans_la_demande(self):
        self.assertNotIn('id="longueurs"', self.html_sans)
        self.assertNotIn("donnees longueurs", self.html_sans)
        demande = re.search(r'id="demande">(.*?)</section>', self.html_sans, re.S).group(1)
        self.assertIn('<p class="longueurs-absentes">Longueurs de lignes non relevées, à estimer par vos soins.</p>',
                      demande)
        self.assertEqual(self.html_sans.count("Longueurs de lignes non relevées"), 1)
        self.assertEqual(len(re.findall(r'<section class="chapitre[ "]', self.html_sans)), 7)
        self.assertNotIn("Plan du local (A4", self.html_sans)

    def test_sans_pdf_l_annexe_est_signalee(self):
        self.assertTrue(any("joindre à la main" in a for a in self.r["avertissements"]), self.r["avertissements"])
        self.assertEqual(self.r["annexes_fusionnees"], 0)

    def test_annexe_introuvable(self):
        dv = self.avec / gl.SOUS_DOSSIER / "v1"
        demande = json.loads((dv / "demande.json").read_text(encoding="utf-8"))
        demande["annexes"]["documents"][0]["fichier"] = "../../plan/absent.pdf"
        with self.assertRaises(gl.ErreurLivrable):
            gl.documents_annexes(demande, dv)


class TestFusion(unittest.TestCase):
    """fusionner_annexes sur un PDF factice : page 1 du plan seulement, à l'échelle, cartouche anonymisé."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.dossier = dossier_fictif(Path(self.tmp.name), metre_fictif())

    def tearDown(self):
        self.tmp.cleanup()

    def fusion(self, variante: str, **options) -> pymupdf.Document:
        r = assembler.assembler(self.dossier, variante, date=DATE, **options)
        version = r["dossier_sortie"].name
        gl.generer(self.dossier, version, pdf=False)
        return pymupdf.open(refaire_pdf(self.dossier, version))

    def test_page_1_seulement_a_l_echelle_et_anonymisee(self):
        source = pymupdf.open(self.dossier / "plan" / "plan.pdf")
        with self.fusion("grossiste") as doc:
            derniere = doc[-1]
            self.assertEqual((round(derniere.rect.width, 2), round(derniere.rect.height, 2)),
                             (round(source[0].rect.width, 2), round(source[0].rect.height, 2)))
            texte = derniere.get_text()
            self.assertIn("Échelle 1:100", texte)
            self.assertNotIn("Métré par réseau", "".join(p.get_text() for p in doc))
            self.assertNotIn("fictivor", texte.lower())
            self.assertIn("Le client : plan froid et clim", texte)
            self.assertIn("Dossier : le client", texte)
            self.assertIn("Salle de vente", texte)               # le reste du texte du plan est intact
            self.assertEqual(len(derniere.get_drawings()), len(source[0].get_drawings()))   # traits intacts
        source.close()

    def test_fabricant_nomme_cartouche_intact(self):
        with self.fusion("fabricant", destinataire="Jean Essai, Fournisseur Fictif") as doc:
            self.assertIn("Boucherie Fictivor : plan froid et clim", doc[-1].get_text())


class TestChaineReelle(unittest.TestCase):
    """assembler.py → generer_livrable.py (Edge ou Chrome) → controler.py, avec métré et plan : 0 échec."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.dossier = dossier_fictif(Path(cls.tmp.name), metre_fictif())
        cls.navigateur = gl.trouver_navigateur()
        cls.res = {}
        for variante, options in (("grossiste", {}), ("fabricant", {"destinataire": "Jean Essai, Fournisseur Fictif",
                                                                    "tutoiement": True})):
            version = assembler.assembler(cls.dossier, variante, date=DATE, **options)["dossier_sortie"].name
            if cls.navigateur is not None:
                cls.res[variante] = (version, gl.generer(cls.dossier, version, pdf=True))
            else:
                gl.generer(cls.dossier, version, pdf=False)
                refaire_pdf(cls.dossier, version)
                cls.res[variante] = (version, None)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_controles_sans_echec(self):
        for variante, (version, _) in self.res.items():
            with self.subTest(variante=variante):
                r = par_numero(self.dossier, version)
                self.assertFalse(ctl.en_echec(list(r.values())), {i: r[i].details for i in r if r[i].details})
                self.assertEqual(r[7].statut, ctl.OK)
                self.assertIn("1 marquée(s) « (mesurée) »", r[7].resume)
                self.assertIn("après", r[6].resume)

    def test_pdf_edge_plus_une_page(self):
        if self.navigateur is None:
            self.skipTest("ni Edge ni Chrome sur ce PC")
        version, g = self.res["grossiste"]
        self.assertEqual(g["pages"], g["pages_edge"] + 1)
        self.assertEqual(g["annexes_fusionnees"], 1)
        self.assertLess(g["mo"], gl.SEUIL_MO)
        with pymupdf.open(g["pdf"]) as doc:
            self.assertEqual(ctl.pages_edge([p.get_text() for p in doc][:-1]), g["pages_edge"])
            self.assertGreater(doc[-1].rect.width, doc[-1].rect.height)         # plan A4 paysage
            self.assertNotIn("Page ", doc[-1].get_text())                       # pas de pagination sur le plan
            texte = ctl.compacter("".join(p.get_text() for p in doc))
        self.assertTrue(ctl.motif_phrase(PHRASE).search(texte))
        self.assertIn("12,00 (mesurée)", texte)


# ── controler.py : chaque nouveau contrôle mis en échec ──────────────────────────────────────────────

class BaseMutation(unittest.TestCase):
    """Un modèle (grossiste, métré et plan, PDF factice) construit une fois ; chaque test travaille sur une copie."""

    METRE: dict | None = metre_fictif()
    PLAN = True

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.modele = dossier_fictif(Path(cls.tmp.name) / "modele", cls.METRE, plan=cls.PLAN)
        assembler.assembler(cls.modele, "grossiste", date=DATE)
        gl.generer(cls.modele, "v1", pdf=False)
        refaire_pdf(cls.modele)
        cls.n = 0

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def copie(self) -> Path:
        type(self).n += 1
        cible = Path(self.tmp.name) / f"copie-{self.n}" / self.modele.name
        shutil.copytree(self.modele, cible)
        return cible

    def assertEchec(self, c: ctl.Controle, *fragments: str):
        self.assertEqual(c.statut, ctl.ECHEC, c.details)
        texte = "\n".join(c.details)
        for f in fragments:
            self.assertIn(f, texte)


class TestControlesAvecPlan(BaseMutation):
    def test_modele_sans_echec(self):
        r = par_numero(self.modele)
        self.assertFalse(ctl.en_echec(list(r.values())), {i: r[i].details for i in r if r[i].details})
        self.assertEqual(r[1].statut, ctl.OK)                    # cartouche du plan anonymisé

    def test_a_metre_modifie_apres_la_demande(self):
        d = self.copie()
        metre = metre_fictif()
        metre["reseaux"][0]["lignes"][0]["total_m"] = 4.50
        (d / "plan" / "metre.json").write_text(json.dumps(metre, ensure_ascii=False), encoding="utf-8")
        self.assertEchec(par_numero(d)[7], "froid_cuivres, ligne 1", "4,50 m dans plan/metre.json",
                         "4,21 m au lieu de 4,50 m")

    def test_a_longueur_fausse_dans_le_pdf(self):
        d = self.copie()
        refaire_pdf(d, remplacer=[(">23,41<", ">23,47<")])
        self.assertEchec(par_numero(d)[7], "réseau froid_cuivres, total : 23,47 m au lieu de 23,41 m")

    def test_a_version_du_plan_et_reseau_exclu(self):
        d = self.copie()
        metre = metre_fictif(plan_version=10)
        (d / "plan" / "metre.json").write_text(json.dumps(metre, ensure_ascii=False), encoding="utf-8")
        self.assertEchec(par_numero(d)[7], "plan v9", "à la v10")
        d = self.copie()
        dv = d / gl.SOUS_DOSSIER / "v1"
        demande = json.loads((dv / "demande.json").read_text(encoding="utf-8"))
        demande["longueurs"]["reseaux"].append({"cle": "electricite", "nom": "Électricité", "famille": "electricite",
                                               "lignes": [], "total_m": 16.37, "origine": "estimee"})
        (dv / "demande.json").write_text(json.dumps(demande, ensure_ascii=False), encoding="utf-8")
        self.assertEchec(par_numero(d)[7], "sans électricité ni réseaux libres")

    def test_b_phrases_absentes_du_pdf(self):
        d = self.copie()
        refaire_pdf(d, remplacer=[("Toutes les longueurs sont des estimations", "Longueurs")])
        self.assertEchec(par_numero(d)[7], "phrase d'estimation des longueurs absente")
        d = self.copie()
        refaire_pdf(d, remplacer=[("Diamètres et charge de fluide à définir par vos soins.", "")])
        self.assertEchec(par_numero(d)[7], "Diamètres et charge de fluide")

    def test_c_metre_retire_apres_la_demande(self):
        d = self.copie()
        (d / "plan" / "metre.json").unlink()
        self.assertEchec(par_numero(d)[7], "alors que plan/metre.json n'existe pas", "chapitre ou tableau de longueurs",
                         "Longueurs de lignes non relevées")

    def test_d_annexe_absente_ou_en_double(self):
        d = self.copie()
        refaire_pdf(d, fusion=False)
        self.assertEchec(par_numero(d)[6], "pages d'Edge + 1 page(s) d'annexe")
        d = self.copie()
        dv = d / gl.SOUS_DOSSIER / "v1"
        demande = json.loads((dv / "demande.json").read_text(encoding="utf-8"))
        docs = gl.documents_annexes(demande, dv)
        refaire_pdf(d, documents=docs + docs)
        self.assertEchec(par_numero(d)[6], "pages d'Edge + 1 page(s) d'annexe")

    def test_d_annexe_hors_a4_ou_mauvaise_page(self):
        d = self.copie()
        a3 = d / "plan" / "plan-a3.pdf"
        ecrire_plan_pdf(a3, taille=(1190.55, 841.89))
        refaire_pdf(d, documents=[({"titre": "Plan du local", "pages": 1}, a3)])
        self.assertEchec(par_numero(d)[6], "hors format A4", "pt, la page 1 de plan.pdf fait")
        d = self.copie()
        metre_page = d / "plan" / "page-metre.pdf"
        with pymupdf.open(d / "plan" / "plan.pdf") as src:
            autre = pymupdf.open()
            autre.insert_pdf(src, from_page=1, to_page=1)
            autre.save(str(metre_page))
            autre.close()
        refaire_pdf(d, documents=[({"titre": "Plan du local", "pages": 1}, metre_page)])
        self.assertEchec(par_numero(d)[6], "ne reprend pas le texte de la page 1 de plan.pdf")

    def test_d_plan_present_mais_pas_en_annexe(self):
        d = self.copie()
        dv = d / gl.SOUS_DOSSIER / "v1"
        demande = json.loads((dv / "demande.json").read_text(encoding="utf-8"))
        demande["annexes"]["documents"] = []
        (dv / "demande.json").write_text(json.dumps(demande, ensure_ascii=False), encoding="utf-8")
        self.assertEchec(par_numero(d)[6], "n'est pas en annexe de la demande")

    def test_d_cartouche_non_anonymise(self):
        d = self.copie()
        refaire_pdf(d, anonymiser=False)
        self.assertEchec(par_numero(d)[1], "fictivor")

    def test_e_marque_mesuree_manquante_ou_en_trop(self):
        d = self.copie()
        refaire_pdf(d, remplacer=[('<span class="mesuree">(mesurée)</span>', "")])
        self.assertEchec(par_numero(d)[7], "ligne 3 : « (mesurée) » manquante")
        d = self.copie()
        refaire_pdf(d, remplacer=[(">4,21</td>", ">4,21 (mesurée)</td>")])
        self.assertEchec(par_numero(d)[7], "ligne 1 : « (mesurée) » en trop")

    def test_mail_sans_la_phrase(self):
        d = self.copie()
        mail = d / gl.SOUS_DOSSIER / "v1" / "mail-grossiste.txt"
        texte = mail.read_text(encoding="utf-8")
        phrase = ("Les longueurs de cuivre estimées d'après le plan figurent dans le PDF, avec le plan du local en "
                  "annexe.")
        self.assertIn(phrase, texte)
        mail.write_text(texte.replace(phrase, ""), encoding="utf-8")
        r = par_numero(d)
        self.assertEchec(r[7], "ne dit pas que les longueurs de cuivre estimées sont dans le PDF")
        self.assertEchec(r[6], "ne cite pas le plan du local")

    def test_demande_anterieure_au_lot_7(self):
        d = self.copie()
        dv = d / gl.SOUS_DOSSIER / "v1"
        demande = json.loads((dv / "demande.json").read_text(encoding="utf-8"))
        del demande["longueurs"]
        del demande["annexes"]["documents"]
        (dv / "demande.json").write_text(json.dumps(demande, ensure_ascii=False), encoding="utf-8")
        r = par_numero(d)
        self.assertEchec(r[7], "antérieur au Lot 7")
        self.assertEchec(r[6], "antérieur au Lot 7")


class TestControlesSansMetre(BaseMutation):
    """Dossier sans plan/metre.json ni plan.pdf : ligne « non relevées », aucun tableau."""

    METRE = None
    PLAN = False

    def test_modele_sans_echec(self):
        r = par_numero(self.modele)
        self.assertFalse(ctl.en_echec(list(r.values())), {i: r[i].details for i in r if r[i].details})
        self.assertEqual(r[7].statut, ctl.OK)
        self.assertIn("ligne « non relevées »", r[7].resume)

    def test_c_ligne_non_relevees_absente(self):
        d = self.copie()
        refaire_pdf(d, remplacer=[("Longueurs de lignes non relevées, à estimer par vos soins.", "")])
        self.assertEchec(par_numero(d)[7], "Longueurs de lignes non relevées")

    def test_c_tableau_sans_metre(self):
        d = self.copie()
        refaire_pdf(d, remplacer=[('<section class="chapitre" id="demande">',
                                   '<section class="chapitre" id="longueurs"><h1>Longueurs de cuivre (estimées '
                                   "d'après le plan)</h1><p>4,21 (mesurée)</p></section>"
                                   '<section class="chapitre" id="demande">')])
        self.assertEchec(par_numero(d)[7], "chapitre ou tableau de longueurs", "« (mesurée) » dans le PDF")


if __name__ == "__main__":
    unittest.main()
