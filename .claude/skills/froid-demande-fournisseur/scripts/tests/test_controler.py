"""Tests de controler.py (étape 3, contrôle du livrable) sur un jeu entièrement fictif.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-demande-fournisseur/scripts/tests -v
Chaque test fabrique, dans un répertoire temporaire, un dossier d'installation inventé (client, localité, téléphone,
fiche) : 1-existant.md (tableaux B, B2, C, D), 2-resultats.json et valeurs-derivees.json (des Valeur), photos
(rectangles colorés), demande.json, page et mail par generer_livrable.py (sans navigateur), PDF écrit par PyMuPDF.
Cas qui doivent échouer : identifiant qui fuite (variantes de casse, d'accents, d'espaces ; mail, PDF), nombre inventé
ou mal rendu, plaque absente ou en double, légende vide, PDF absent / d'une page / trop lourd / périmé, image
manquante, mail avec tableau ou sans chiffre, annexes incomplètes. Dernier test : la chaîne réelle assembler.py →
generer_livrable.py → controler.py sur le dossier fictif de test_assembler.py (PDF imprimé si Edge ou Chrome est là).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
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
import controler as ctl  # noqa: E402
import generer_livrable as gl  # noqa: E402
from valeur import Valeur, en_json  # noqa: E402

NBSP = " "
S, H = "sourcé", "hypothèse"
VERSION = "v1"
IDENTIFIANTS = ["BOUCHERIE FICTIVOR", "FICTIVOR", "12 Rue des Essais", "Lèvremont-Essai", "9999", "0499 11 22 33",
                "info@fictivor.test", "IN99999", "boucherie-fictivor"]

PHOTOS = {"sources/photos/01-centrale-fictive/p02-1.jpeg": (31, 78, 121),
          "sources/photos/01-centrale-fictive/p02-2.jpeg": (90, 110, 60),
          "sources/photos/01-centrale-fictive/p02-3.jpeg": (120, 60, 60),
          "sources/photos/02-chambre-fictive/p03-1.jpeg": (70, 70, 120),
          "sources/photos/02-chambre-fictive/p03-2.jpeg": (130, 90, 30)}

EXISTANT_MD = """# Relevé de l'existant — BOUCHERIE FICTIVOR — essai

## A. Postes relevés

| Poste | Photo |
|---|---|
| Centrale | p02-3 |

## B. Compresseurs (une ligne par compresseur, d'après les plaques)

| Poste | Marque | Modèle | N° de série | Photo | Lecture | Source |
|---|---|---|---|---|---|---|
| CENTRALE NÉGATIVE — compresseur 1/1 | Fictif | X-100 | 1111111111 | `01-centrale-fictive/p02-1.jpeg` | sûre | photo p02-1 ; rapport p. 2 |

### B2. Plaques d'ensemble (centrales, condenseurs, échangeurs)

| Poste | Équipement | Ce que dit la plaque | Photo | Lecture |
|---|---|---|---|---|
| CENTRALE NÉGATIVE | Plaque de la centrale | fluide R449A ; n° 4444-01 | `01-centrale-fictive/p02-2.jpeg` | sûre |
| CENTRALE NÉGATIVE | Vue de la centrale | — | `p02-3.jpeg` | — |

## C. Chambres froides et postes desservis

| Poste / chambre | Volume | Usage | Évaporateurs (plaques) | Source |
|---|---|---|---|---|
| Chambre négative | 100 | congélation (photo p03-2) | Fictair EVA-1 (n° 5555/01, 2010) | rapport p. 3 ; photos p03-1 |

## D. Régulation, récupération de chaleur, chauffage, électricité

| Élément | Photo |
|---|---|
| Armoire de régulation | `09-regulation/p09-9.jpeg` |
"""


def v(n, u, src, st, id):
    return Valeur(n, u, src, st, id=id)


def resultats_fictifs() -> dict:
    return {"format": "2-resultats essai", "postes": [{
        "id": "n", "nom": "Centrale négative",
        "regime": {"t0": v(-30, "°C", "dicté (essai)", S, "n-t0"), "tc": v(40, "°C", "dicté (essai)", S, "n-tc")},
        "volume": v(100, "m³", "rapport p. 3", H, "n-volume"),
        "compresseurs": [{"id": "n-c1", "volume_balaye": v(32.5, "m³/h", "photo p02-1", S, "n-c1-vb"),
                          "retenue": v(12.4, "kW", "calcul", H, "n-c1-q0")}],
        "existante": v(12.4, "kW", "calcul", H, "n-existante"),
        "evaporateurs": [{"id": "n-e1", "modele": "Fictair EVA-1", "annee": "2010"}]}],
        "sous_totaux": []}


def demande_fictive() -> dict:
    kw = f"12,4{NBSP}kW"
    return {
        "version": VERSION, "date": "2026-01-02", "variante": "grossiste", "destinataire": None, "anonymise": True,
        "emetteur": {"societe": "Émetteur Fictif", "contact": "Paul Essai", "telephone": "0400 00 00 01",
                     "mail": "devis@emetteur.test", "adresse": ""},
        "site": {"nom": "", "localite": "", "reference_dossier": ""},
        "titre": "Demande de prix — installation frigorifique — 2026-01-02 — v1",
        "mention": "Valeurs indicatives, sélection finale chez le fournisseur.",
        "contexte": {"texte": "Nous chiffrons le remplacement d'une centrale négative par une centrale CO₂ booster."},
        "chambres": {"lignes": [{"chambre": "Chambre négative", "regime": "négatif", "surface": f"40,0{NBSP}m² (hyp.)",
                                 "volume": f"100,0{NBSP}m³ (hyp.)", "nb_evaporateurs": "1"}],
                     "note": "Condensation de référence : 40 °C."},
        "production": {"lignes": [{"poste": "Centrale négative", "compresseurs": "Fictif X-100 + 2 × Fictif Y-50",
                                   "volume_balaye": f"32,50{NBSP}m³/h", "puissance": kw, "statut": H}],
                       "sous_totaux": [{"libelle": f"Sous-total négatif (évap. -30{NBSP}°C, cond. 40{NBSP}°C)",
                                        "puissance": kw, "statut": H}],
                       "note": "Puissances calculées à partir des plaques."},
        "evaporateurs": {"lignes": [{"chambre": "Chambre négative", "modele": "Fictair EVA-1", "annee": "2010",
                                     "puissance": "à confirmer par vos calculs"}], "note": ""},
        "demande": {"titre": "Notre demande", "intro": "Merci de nous chiffrer :",
                    "points": [{"lettre": "a", "titre": "Centrale CO₂ booster", "texte": "Pour la charge ci-dessus.",
                                "sous_points": []}], "resume": ""},
        "postes": [{"id": "n", "titre": "Centrale négative", "dessert": "chambre négative (1 évaporateur)",
                    "existant": [f"Compresseur 1/1 : Fictif X-100, n° 1111111111, 32,50{NBSP}m³/h"],
                    "puissance": f"{kw} (hyp.)", "statut": H, "remplacement": "Remplacée par la centrale CO₂.",
                    "photos": [
                        {"fichier": "sources/photos/01-centrale-fictive/p02-1.jpeg", "type": "plaque",
                         "legende": f"Fictif X-100 · n° 1111111111 · 32,50{NBSP}m³/h"},
                        {"fichier": "sources/photos/01-centrale-fictive/p02-2.jpeg", "type": "ensemble",
                         "legende": "Plaque de la centrale · n° 4444-01"},
                        {"fichier": "sources/photos/02-chambre-fictive/p03-1.jpeg", "type": "plaque",
                         "legende": "Fictair EVA-1 · n° 5555/01 · 2010 · puissance à confirmer par vos calculs"}]}],
        "annexes": {"vues_ensemble": [
            {"fichier": "sources/photos/01-centrale-fictive/p02-3.jpeg", "legende": "Centrale négative · vue"},
            {"fichier": "sources/photos/02-chambre-fictive/p03-2.jpeg", "legende": "Chambre négative · vue"}],
            "plan_implantation": "à suivre", "pieces_jointes": []},
        "mail": {"objet": "Demande de prix — centrale CO₂ booster", "salutation": "Bonjour,",
                 "corps": (f"Nous chiffrons le remplacement d'une centrale négative.\n\nPuissance existante : {kw} en "
                           f"négatif (évaporation -30{NBSP}°C), condensation 40{NBSP}°C ; valeurs indicatives.\n\n"
                           "Tout le détail, plaques et photos, est dans le PDF joint."),
                 "formule": "Bien cordialement,", "signature": "Paul Essai\nÉmetteur Fictif — 0400 00 00 01"},
    }


def fabriquer_photo(chemin: Path, couleur: tuple[int, int, int], taille=(160, 120)) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, *taille), False)
    pix.set_rect(pix.irect, couleur)
    pix.save(str(chemin), output="jpg")


def ecrire_pdf(chemin: Path, lignes: list[str], pages: int = 2) -> None:
    """PDF de `pages` pages portant les lignes (police de base, texte extractible par PyMuPDF)."""
    doc = pymupdf.open()
    par_page = max(1, -(-len(lignes) // pages))
    for i in range(pages):
        page, y = doc.new_page(), 60
        for ligne in lignes[i * par_page:(i + 1) * par_page]:
            for morceau in textwrap.wrap(ligne, 95) or [""]:
                if y > 800:
                    page, y = doc.new_page(), 60
                page.insert_text((40, y), morceau, fontsize=8)
                y += 11
    doc.save(str(chemin))
    doc.close()


def construire(racine: Path, modifier=None, lignes_pdf: list[str] | None = None, pages_pdf: int = 2) -> Path:
    """Dossier fictif complet ; `modifier(demande)` ajuste demande.json avant la génération de la page et du mail."""
    dossier = Path(racine) / "2026-01-01-essai-controle"
    for rel, couleur in PHOTOS.items():
        fabriquer_photo(dossier / rel, couleur)
    (dossier / "1-existant.md").write_text(EXISTANT_MD, encoding="utf-8")
    (dossier / "2-resultats.json").write_text(en_json(resultats_fictifs(), indent=1), encoding="utf-8")
    dv = dossier / gl.SOUS_DOSSIER / VERSION
    dv.mkdir(parents=True)
    surface = v(40.0, "m²", "surface = longueur × largeur (essai)", H, "n-surface")
    (dv / "valeurs-derivees.json").write_text(json.dumps({"valeurs": [surface.vers_dict()]}, ensure_ascii=False),
                                              encoding="utf-8")
    (dv / "identifiants-client.json").write_text(json.dumps({"anonymise": True, "recherches": IDENTIFIANTS},
                                                            ensure_ascii=False), encoding="utf-8")
    demande = demande_fictive()
    if modifier:
        modifier(demande)
    (dv / "demande.json").write_text(json.dumps(demande, ensure_ascii=False, indent=1), encoding="utf-8")
    gl.generer(dossier, VERSION, pdf=False)
    if lignes_pdf is None:
        lignes_pdf = ["Demande de prix - installation frigorifique - v1", "Contexte",
                      demande["contexte"]["texte"], "Notre demande", "Annexes", "Plan d'implantation : a suivre"]
    ecrire_pdf(dv / f"demande-{VERSION}.pdf", lignes_pdf, pages_pdf)
    return dossier


def par_numero(controles: list[ctl.Controle]) -> dict[int, ctl.Controle]:
    return {c.numero: c for c in controles}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.racine = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def controler(self, **options) -> dict[int, ctl.Controle]:
        self.dossier = construire(self.racine, **options)
        self.dv = self.dossier / gl.SOUS_DOSSIER / VERSION
        return par_numero(ctl.controler(self.dossier, VERSION))

    def assertEchec(self, c: ctl.Controle, *fragments: str):
        self.assertEqual(c.statut, ctl.ECHEC, c.details)
        texte = "\n".join(c.details)
        for f in fragments:
            self.assertIn(f, texte)


class TestOutils(unittest.TestCase):
    def test_nombres_et_unites(self):
        self.assertEqual([(n, u) for n, u, _ in ctl.nombres(f"1{NBSP}971,0{NBSP}m³ (hyp.)")], [(f"1{NBSP}971,0", "m³")])
        self.assertEqual([(n, u) for n, u, _ in ctl.nombres(f"(évap. -30{NBSP}°C, cond. 40{NBSP}°C)")],
                         [("-30", "°C"), ("40", "°C")])
        self.assertEqual([(n, u) for n, u, _ in ctl.nombres("63,5kW à −30 °C")], [("63,5", "kW"), ("−30", "°C")])
        # « 800A » d'une référence n'est pas un courant, « R449A » n'est pas un nombre
        self.assertEqual([(n, u) for n, u, _ in ctl.nombres("AK-SM 800A, R449A")], [("800", "")])

    def test_rendus_admis(self):
        admis = ctl.rendus([v(-30, "°C", "x", S, "a"), v(169.36, "m²", "x", H, "b"), v(63.5, "kW", "x", H, "c")])
        self.assertIn(("-30", "°C"), admis)                     # entier : décimales nulles omises
        self.assertIn(("-30,0", "°C"), admis)
        self.assertIn(("169,4", "m²"), admis)
        self.assertNotIn(("169", "m²"), admis)                  # arrondi qui perd de l'information : refusé
        self.assertNotIn(("64", "kW"), admis)
        self.assertNotIn(("63,50", "kW"), admis)                # pas le rendu de Valeur.texte()

    def test_variantes_d_un_identifiant(self):
        m = ctl.motif_identifiant("Lèvremont-Essai")
        for texte in ("à Lèvremont-Essai", "LEVREMONT ESSAI", "levremontessai", "Levremont_Essai"):
            self.assertTrue(m.search(ctl.normaliser(texte)), texte)
        self.assertFalse(m.search(ctl.normaliser("Lèvremont-Essaim")))
        tel = ctl.motif_identifiant("0499 11 22 33")
        for texte in ("0499112233", "0499.11.22.33", "04 99 11 22 33"):
            self.assertTrue(tel.search(ctl.normaliser(texte)), texte)
        self.assertFalse(ctl.motif_identifiant("9999").search("99999"))

    def test_photos_citees_tableaux_b_b2_c_seulement(self):
        self.assertEqual(ctl.photos_citees(EXISTANT_MD),
                         {"p02-1": "B", "p02-2": "B2", "p02-3": "B2", "p03-2": "C", "p03-1": "C"})


class TestLivrableConforme(Base):
    def test_six_controles_ok(self):
        r = self.controler()
        self.assertEqual([r[i].statut for i in range(1, 7)], [ctl.OK] * 6, {i: r[i].details for i in r})
        self.assertIn("aucun trouvé", r[1].resume)
        self.assertIn("tous retrouvés", r[2].resume)
        self.assertIn("5 photos citées", r[3].resume)
        self.assertIn("12,4", r[5].resume)
        with contextlib.redirect_stdout(io.StringIO()) as sortie:
            code = ctl.main([str(self.dossier), VERSION])
        self.assertEqual(code, 0)
        self.assertIn("Bilan : 6 OK, 0 en échec", sortie.getvalue())

    def test_variante_nommee_sans_objet(self):
        def nommer(d):
            d["anonymise"] = False
            d["site"] = {"nom": "BOUCHERIE FICTIVOR", "localite": "Lèvremont-Essai", "reference_dossier": "IN99999"}
            d["mail"]["objet"] += " — réf. BOUCHERIE FICTIVOR"
        r = self.controler(modifier=nommer)
        self.assertEqual(r[1].statut, ctl.SANS_OBJET)
        self.assertFalse(ctl.en_echec(list(r.values())), {i: r[i].details for i in r})


class TestAnonymisation(Base):
    def test_identifiant_qui_fuite_dans_le_mail(self):
        def fuite(d):
            d["mail"]["corps"] += "\n\nChantier : LEVREMONT ESSAI, chez boucheriefictivor, tél. 0499112233."
        r = self.controler(modifier=fuite)
        self.assertEchec(r[1], "Lèvremont-Essai", "BOUCHERIE FICTIVOR", "0499 11 22 33", "mail-grossiste.txt",
                         "mail-grossiste.html", "demande.json › mail.corps")
        self.assertEqual(r[2].statut, ctl.OK)

    def test_identifiant_qui_fuite_dans_le_pdf_seulement(self):
        r = self.controler(lignes_pdf=["Demande de prix", "Installation de la Boucherie Fictivor", "Annexes"])
        self.assertEchec(r[1], "demande-v1.pdf (texte)")
        self.assertNotIn("demande.json", "\n".join(r[1].details))

    def test_chemins_de_photos_ignores(self):
        def chemin(d):
            d["annexes"]["vues_ensemble"][0]["fichier"] = "sources/photos/01-centrale-fictive/p02-3.jpeg"
        self.assertEqual(self.controler(modifier=chemin)[1].statut, ctl.OK)

    def test_identifiants_absents(self):
        self.controler()
        (self.dv / "identifiants-client.json").unlink()
        self.assertEchec(par_numero(ctl.controler(self.dossier, VERSION))[1], "identifiants-client.json absent")


class TestChiffres(Base):
    def test_nombre_invente(self):
        def inventer(d):
            d["production"]["lignes"][0]["puissance"] = f"15,0{NBSP}kW"
            d["postes"][0]["puissance"] = f"99,9{NBSP}kW (hyp.)"
        r = self.controler(modifier=inventer)
        self.assertEchec(r[2], f"15,0 kW", "99,9 kW", "production › lignes 1 › puissance")
        self.assertEqual(len(r[2].details), 2)

    def test_meme_valeur_mal_rendue(self):
        def rendre(d):
            d["production"]["lignes"][0]["puissance"] = f"12,40{NBSP}kW"     # décimales différentes
            d["chambres"]["lignes"][0]["volume"] = f"100,00{NBSP}m3"         # décimales et unité différentes
            d["chambres"]["lignes"][0]["surface"] = "40,0 m²"                 # espace ordinaire : toléré
        r = self.controler(modifier=rendre)
        self.assertEchec(r[2], "12,40 kW", "100,00 m3")
        self.assertEqual(len(r[2].details), 2)

    def test_nombre_d_evaporateurs(self):
        r = self.controler(modifier=lambda d: d["chambres"]["lignes"][0].update(nb_evaporateurs="4"))
        self.assertEchec(r[2], "4 évaporateur(s)")

    def test_designations_series_annees_ignorees(self):
        def designer(d):
            d["production"]["lignes"][0]["compresseurs"] = "Fictif 4H-15.2Y-40P n° 1670106407"
            d["evaporateurs"]["lignes"][0].update(modele="Fictair 5267 R449A", annee="2011")
        self.assertEqual(self.controler(modifier=designer)[2].statut, ctl.OK)


class TestPlaques(Base):
    def test_plaque_absente(self):
        r = self.controler(modifier=lambda d: d["postes"][0]["photos"].pop(0))
        self.assertEchec(r[3], "p02-1 (tableau B de 1-existant.md) absente du PDF")

    def test_photo_en_double_et_legende_vide(self):
        def doubler(d):
            d["annexes"]["vues_ensemble"].append({"fichier": "sources/photos/02-chambre-fictive/p03-1.jpeg",
                                                  "legende": "doublon"})
            d["postes"][0]["photos"][1]["legende"] = "  "
        r = self.controler(modifier=doubler)
        self.assertEchec(r[3], "p03-1 (tableau C) présente 2 fois", "p02-2 (poste « Centrale négative ») : légende vide")


class TestPdf(Base):
    def test_pdf_absent(self):
        self.controler()
        (self.dv / "demande-v1.pdf").unlink()
        r = par_numero(ctl.controler(self.dossier, VERSION))
        self.assertEchec(r[4], "demande-v1.pdf absent")
        self.assertEchec(r[1], "texte du PDF non vérifié")

    def test_pdf_d_une_page(self):
        self.assertEchec(self.controler(pages_pdf=1)[4], "n'a que 1 page")

    def test_pdf_trop_lourd(self):
        self.controler()
        liv = ctl.charger(self.dossier, VERSION)
        self.assertEchec(ctl.controle_pdf(liv, seuil_mo=0.000001), "au-delà de")

    def test_pdf_perime_et_image_manquante(self):
        self.controler()
        recent = (self.dv / "demande-v1.pdf").stat().st_mtime + 60
        os.utime(self.dv / "demande.json", (recent, recent))
        next((self.dv / "img").glob("*.jpg")).unlink()
        r = par_numero(ctl.controler(self.dossier, VERSION))
        self.assertEchec(r[4], "demande.json modifié après demande-v1.pdf", "image manquante")


class TestMail(Base):
    def test_tableau_dans_le_mail(self):
        r = self.controler(modifier=lambda d: d["mail"].update(corps=d["mail"]["corps"] + "\n\n| Poste | kW |"))
        self.assertEchec(r[5], "contient « | »")

    def test_objet_vide_chiffre_invente_sans_renvoi(self):
        def abimer(d):
            d["mail"].update(objet="", corps=f"Environ 70{NBSP}kW en négatif.")
        r = self.controler(modifier=abimer)
        self.assertEchec(r[5], "objet vide", "« 70 kW » du mail introuvable", "ne renvoie pas au PDF")

    def test_mail_sans_chiffre(self):
        r = self.controler(modifier=lambda d: d["mail"].update(corps="Tout est dans le PDF joint."))
        self.assertEchec(r[5], "aucun chiffre clé")


class TestAnnexesEtErreurs(Base):
    def test_annexes_incompletes(self):
        def amputer(d):
            del d["annexes"]["pieces_jointes"]
            d["annexes"]["plan_implantation"] = ""
        r = self.controler(modifier=amputer)
        self.assertEchec(r[6], "pieces_jointes absent", "plan_implantation absent ou vide")

    def test_code_de_sortie_1_et_erreurs(self):
        self.controler(modifier=lambda d: d["postes"][0].update(puissance=f"77,7{NBSP}kW"))
        with contextlib.redirect_stdout(io.StringIO()) as sortie:
            self.assertEqual(ctl.main([str(self.dossier), VERSION]), 1)
        self.assertIn("ÉCHEC", sortie.getvalue())
        with self.assertRaises(ctl.ErreurControle):
            ctl.controler(self.dossier, "version-1")
        with self.assertRaises(ctl.ErreurControle):
            ctl.controler(self.dossier, "v2")                        # dossier de version absent
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ctl.main([str(self.racine / "inexistant"), VERSION]), 1)


class TestChaineComplete(unittest.TestCase):
    """assembler.py → generer_livrable.py → controler.py sur le dossier fictif de test_assembler.py : 0 échec."""

    @classmethod
    def setUpClass(cls):
        import test_assembler as ta                                   # dossier fictif partagé (calculs.py réel)
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.dossier = ta.construire_dossier(Path(cls.tmp.name))
        for i, photo in enumerate(sorted((cls.dossier / "sources" / "photos").glob("*/*.jpeg"))):
            fabriquer_photo(photo, (40 + 20 * i % 200, 90, 120))      # vraies images à la place des octets factices
        cls.navigateur = gl.trouver_navigateur()
        cls.versions = {}
        for variante, options in (("grossiste", {}), ("fabricant", {"destinataire": "Jean Essai, Fournisseur Fictif",
                                                                    "tutoiement": True})):
            r = ta.assembler.assembler(cls.dossier, variante, date="2026-01-02", **options)
            version = r["dossier_sortie"].name
            g = gl.generer(cls.dossier, version, pdf=cls.navigateur is not None)
            if g["pdf"] is None:                                     # sans navigateur : PDF du texte de la page
                texte = re.sub(r"<style>.*?</style>|<[^>]+>", " ", g["html"].read_text(encoding="utf-8"), flags=re.S)
                ecrire_pdf(g["html"].with_suffix(".pdf"), [" ".join(texte.split())], pages=3)
            cls.versions[variante] = version

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_grossiste_et_fabricant_sans_echec(self):
        for variante, version in self.versions.items():
            with self.subTest(variante=variante):
                r = par_numero(ctl.controler(self.dossier, version))
                self.assertFalse(ctl.en_echec(list(r.values())), {i: r[i].details for i in r if r[i].details})
                self.assertEqual(r[1].statut, ctl.OK if variante == "grossiste" else ctl.SANS_OBJET)


if __name__ == "__main__":
    unittest.main()
