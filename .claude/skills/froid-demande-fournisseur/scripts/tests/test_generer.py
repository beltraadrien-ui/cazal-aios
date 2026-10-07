"""Tests du rendu de l'étape 3 (generer_livrable.py) : gabarit, photos, page HTML, mail, PDF.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-demande-fournisseur/scripts/tests -v
Jeu d'essai entièrement fictif, écrit dans un répertoire temporaire (images fabriquées : rectangles colorés).
Le test du PDF est sauté si ni Edge ni Chrome n'est installé.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # dossier scripts/
import generer_livrable as gl  # noqa: E402

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

NBSP = " "
VERSION = "v1"
PIEGE = '<script>alert("x")</script> & Co'


def fabriquer_image(chemin: Path, couleur: tuple[int, int, int], texte: str, taille=(1200, 900), mode="RGB") -> None:
    """Rectangle coloré avec un texte (Pillow ; repli PyMuPDF sans texte)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if Image is None:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, *taille), False)
        pix.set_rect(pix.irect, couleur)
        pix.save(str(chemin))
        return
    im = Image.new(mode, taille, couleur + ((255,) if mode == "RGBA" else ()))
    d = ImageDraw.Draw(im)
    try:
        police = ImageFont.load_default(size=64)
    except TypeError:
        police = ImageFont.load_default()
    d.rectangle([40, 40, taille[0] - 40, taille[1] - 40], outline=(255, 255, 255), width=8)
    d.text((80, taille[1] // 2 - 40), texte, fill=(255, 255, 255), font=police)
    im.save(chemin)


PHOTOS = {  # chemin relatif au dossier d'installation → (couleur, texte, taille)
    "sources/photos/01-centrale-a/p03-1.jpg": ((31, 78, 121), "Plaque compresseur 1", (1200, 900)),
    "sources/photos/01-centrale-a/p03-2.jpg": ((90, 110, 60), "Plaque compresseur 2", (1200, 900)),
    "sources/photos/01-centrale-a/p04-1.jpg": ((120, 60, 60), "Centrale vue de face", (900, 1200)),
    "sources/photos/02-centrale-b/p06-1.jpg": ((70, 70, 120), "Plaque centrale B", (1200, 900)),
    "sources/photos/03-groupe-c/p08-1.png": ((130, 90, 30), "Plaque groupe C", (1200, 900)),
    "sources/photos/04-local/p10-1.jpg": ((60, 100, 100), "Local technique", (1200, 900)),
}


def demande_fictive(evaporateurs: bool = True, piege: bool = False) -> dict:
    """demande.json fictif conforme au schéma commun (3 postes, 6 photos, noms inventés)."""
    kw = lambda x: f"{x}{NBSP}kW"  # noqa: E731
    legende_c = PIEGE if piege else "Groupe C : Fictif Z-10, n° 0003, 2014, R449A, puissance à confirmer"
    return {
        "version": VERSION, "date": "2026-10-07", "variante": "grossiste", "destinataire": None, "anonymise": True,
        "emetteur": {"societe": "Froid Exemple SRL", "contact": "Jean Exemple", "telephone": "+32 470 00 00 00",
                     "mail": "contact@froid-exemple.invalid", "adresse": "Rue de l'Exemple 1, 1000 Ville-Fictive"},
        "site": {"nom": "Installation frigorifique", "localite": "", "reference_dossier": ""},
        "titre": "Demande de prix — Installation frigorifique — 2026-10-07 — v1",
        "mention": "Valeurs indicatives, sélection finale chez le fournisseur.",
        "contexte": {"texte": (
            "Nous chiffrons le remplacement complet d'une installation frigorifique existante (trois chambres, "
            "deux centrales et un groupe de condensation au R449A) par une centrale CO₂ booster.\n\n"
            "L'objectif est une offre de prix compétitive pour une installation complète de A à Z, ou pour la "
            "centrale seule.\n\n"
            "- implantation dans le local technique existant\n- récupération de chaleur souhaitée\n"
            "- phase de prix, deux sociétés en lice")},
        "chambres": {"lignes": [
            {"chambre": "Chambre négative A", "regime": f"−22{NBSP}°C", "surface": f"45,0{NBSP}m²",
             "volume": f"110{NBSP}m³", "nb_evaporateurs": "2"},
            {"chambre": "Chambre positive B", "regime": f"+2{NBSP}°C", "surface": f"30,5{NBSP}m²",
             "volume": f"76{NBSP}m³", "nb_evaporateurs": "2"},
            {"chambre": "Chambre positive C", "regime": f"+4{NBSP}°C", "surface": f"12,0{NBSP}m²",
             "volume": f"29{NBSP}m³", "nb_evaporateurs": "1"}],
            "note": "Les chambres A et B sont accolées. Condensation de référence : +40 °C."},
        "production": {"lignes": [
            {"poste": "Centrale négative A", "compresseurs": "3 × Fictif X-100", "volume_balaye": f"3 × 40,1{NBSP}m³/h",
             "puissance": kw("48,2"), "statut": "hyp."},
            {"poste": "Centrale positive B", "compresseurs": "2 × Fictif Y-50", "volume_balaye": f"2 × 22,0{NBSP}m³/h",
             "puissance": kw("21,7"), "statut": "calculé"},
            {"poste": "Groupe C", "compresseurs": "1 × Fictif Z-10", "volume_balaye": "à confirmer",
             "puissance": "à confirmer", "statut": "à confirmer"}],
            "sous_totaux": [{"libelle": "Total négatif (−30 °C évap.)", "puissance": kw("48,2"), "statut": "hyp."},
                            {"libelle": "Total positif (−10 °C évap.)", "puissance": kw("21,7"), "statut": ""}],
            "note": "Puissances calculées à partir des plaques, deux méthodes croisées, régimes −30 / −10 °C évap., "
                    "+40 °C cond."},
        "evaporateurs": {"lignes": [
            {"chambre": "Chambre négative A", "modele": "Fictif EV-200 (× 2)", "annee": "2012",
             "puissance": "à confirmer par vos calculs"},
            {"chambre": "Chambre positive B", "modele": "Fictif EV-120 (× 2)", "annee": "2012",
             "puissance": "à confirmer par vos calculs"},
            {"chambre": "Chambre positive C", "modele": "Fictif EV-60", "annee": "2015",
             "puissance": "à confirmer par vos calculs"}],
            "note": "Modèles relevés sur les plaques ; puissances à recalculer de votre côté."} if evaporateurs else None,
        "demande": {"titre": "Notre demande", "intro": "Merci de nous transmettre une offre de prix pour :",
                    "points": [
                        {"lettre": "a", "titre": "La centrale", "texte": "Centrale CO₂ booster couvrant les deux régimes.",
                         "sous_points": [f"négatif : {kw('48,2')} à −30 °C", f"positif : {kw('21,7')} à −10 °C"]},
                        {"lettre": "b", "titre": "Les évaporateurs", "texte": "Un évaporateur CO₂ par position existante.",
                         "sous_points": []},
                        {"lettre": "c", "titre": "L'armoire de régulation", "texte": "Détail par poste.",
                         "sous_points": ["régulation de centrale", "un régulateur par chambre"]},
                        {"lettre": "d", "titre": "Le matériel de régulation", "texte": "", "sous_points": []},
                        {"lettre": "e", "titre": "La détection de fuite", "texte": "Une sonde par chambre.",
                         "sous_points": []},
                        {"lettre": "f", "titre": "Tarifs indicatifs", "texte": "",
                         "sous_points": ["cuivre K65", "isolants", "petites fournitures"]}],
                    "resume": "En résumé : une centrale, cinq évaporateurs, la régulation et la détection de fuite."},
        "postes": [
            {"id": "centrale-a", "titre": "Centrale négative A", "dessert": "Chambre négative A",
             "existant": ["3 compresseurs Fictif X-100 (2011, R449A)", "Condenseur à air Fictif C-300"],
             "puissance": kw("48,2"), "statut": "hyp.", "remplacement": "Remplacée par la centrale CO₂ (régime négatif).",
             "photos": [
                 {"fichier": "sources/photos/01-centrale-a/p03-1.jpg", "type": "plaque",
                  "legende": f"Compresseur 1 : Fictif X-100, n° 0001, 40,1{NBSP}m³/h, R449A (hyp.)"},
                 {"fichier": "sources/photos/01-centrale-a/p03-2.jpg", "type": "plaque",
                  "legende": f"Compresseur 2 : Fictif X-100, n° 0002, 40,1{NBSP}m³/h, R449A"},
                 {"fichier": "sources/photos/01-centrale-a/p04-1.jpg", "type": "ensemble",
                  "legende": "Centrale négative A, vue de face"}]},
            {"id": "centrale-b", "titre": "Centrale positive B", "dessert": "Chambres positives B et C",
             "existant": ["2 compresseurs Fictif Y-50 (2013, R449A)"], "puissance": kw("21,7"), "statut": "calculé",
             "remplacement": "Remplacée par la centrale CO₂ (régime positif).",
             "photos": [{"fichier": "sources/photos/02-centrale-b/p06-1.jpg", "type": "plaque",
                         "legende": f"Centrale B : Fictif Y-50, 22,0{NBSP}m³/h"}]},
            {"id": "groupe-c", "titre": "Groupe de condensation C", "dessert": "Chambre positive C",
             "existant": ["1 compresseur Fictif Z-10 (2014, R449A)"], "puissance": "à confirmer", "statut": "",
             "remplacement": "Raccordé à la centrale CO₂.",
             "photos": [{"fichier": "sources/photos/03-groupe-c/p08-1.png", "type": "plaque", "legende": legende_c}]}],
        "annexes": {"vues_ensemble": [{"fichier": "sources/photos/04-local/p10-1.jpg",
                                       "legende": "Local technique, vue d'ensemble"}],
                    "plan_implantation": "à suivre", "pieces_jointes": []},
        "mail": {"objet": "Demande de prix — installation frigorifique CO₂ — 3 chambres",
                 "salutation": "Bonjour,",
                 "corps": ("Nous chiffrons le remplacement d'une installation frigorifique (3 chambres, R449A vers CO₂ "
                           "booster).\n\n"
                           f"Chiffres clés : ≈ {kw('48,2')} en négatif à −30 °C, ≈ {kw('21,7')} en positif à −10 °C, "
                           "condensation +40 °C, valeurs indicatives.\n\n"
                           "Tout le détail, plaques et photos, est dans le PDF joint. Une réponse sous dix jours "
                           "nous arrangerait."),
                 "formule": "Bien à vous,", "signature": "Jean Exemple\nFroid Exemple SRL\n+32 470 00 00 00"},
    }


def construire_dossier_fictif(racine: Path, evaporateurs: bool = True, piege: bool = False) -> Path:
    """Dossier d'installation fictif : 6 photos fabriquées + 3-demande-fournisseur/v1/demande.json."""
    dossier = Path(racine) / "2026-10-07-essai-fictif"
    for rel, (couleur, texte, taille) in PHOTOS.items():
        fabriquer_image(dossier / rel, couleur, texte, taille, mode="RGBA" if rel.endswith(".png") else "RGB")
    dv = dossier / gl.SOUS_DOSSIER / VERSION
    dv.mkdir(parents=True, exist_ok=True)
    (dv / "demande.json").write_text(json.dumps(demande_fictive(evaporateurs, piege), ensure_ascii=False, indent=1),
                                     encoding="utf-8", newline="\n")
    return dossier


def empreinte(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


class TestMoteur(unittest.TestCase):
    def test_variables_echappees_et_brutes(self):
        self.assertEqual(gl.rendre("{{a}}|{{{a}}}", {"a": "<b>&"}), "&lt;b&gt;&amp;|<b>&")

    def test_blocs_listes_conditions_et_cles_imbriquees(self):
        g = "{{#l}}[{{x}}{{#y}}+{{/y}}]{{/l}}{{^vide}}rien{{/vide}}{{o.p}}{{#s}}{{.}}{{/s}}"
        ctx = {"l": [{"x": 1, "y": True}, {"x": 2, "y": ""}], "vide": [], "o": {"p": "P"}, "s": ["a", "b"]}
        self.assertEqual(gl.rendre(g, ctx), "[1+][2]rienPab")

    def test_cle_du_contexte_parent(self):
        self.assertEqual(gl.rendre("{{#l}}{{n}}{{/l}}", {"l": [{}, {}], "n": "x"}), "xx")

    def test_erreurs(self):
        with self.assertRaises(gl.ErreurGabarit):
            gl.rendre("{{inconnue}}", {})
        with self.assertRaises(gl.ErreurGabarit):
            gl.rendre("{{#a}}sans fin", {"a": 1})
        with self.assertRaises(gl.ErreurGabarit):
            gl.rendre("{{#a}}x{{/b}}", {"a": 1})

    def test_marquage_des_statuts(self):
        self.assertIn('class="hyp"', gl.marquer(f"48,2{NBSP}kW (hyp.)"))
        self.assertTrue(gl.marquer("à confirmer par vos calculs").startswith('<span class="a-confirmer">'))
        self.assertIn(NBSP, gl.marquer(f"48,2{NBSP}kW"))
        self.assertEqual(gl.statut_html("hypothèse"), '<span class="statut">(hyp.)</span>')
        self.assertEqual(gl.statut_html(""), "")

    def test_typographie(self):
        self.assertEqual(gl.typographie("centrale CO2 booster, 2,10 tCO2e, kgCO2e/kg"),
                         "centrale CO₂ booster, 2,10 tCO2e, kgCO2e/kg")
        self.assertEqual(gl.typographie("type « COND »"), f"type «{NBSP}COND{NBSP}»")
        self.assertEqual(gl.typographie(f"évap. -30{NBSP}°C, régimes -30 °C / -10 °C, (-30/-10 °C)"),
                         f"évap. −30{NBSP}°C, régimes −30 °C / −10 °C, (−30/−10 °C)")
        for inchange in ("4H-15.2Y-40P", "n° 3092-005", "2026-10-07", "Sous-total", "-5 kW", "TS −40/38 °C"):
            self.assertEqual(gl.typographie(inchange), inchange)

    def test_a_confirmer_colore_dans_les_cellules_seulement(self):
        self.assertEqual(gl.marquer("puissance à confirmer", confirmer=False), "puissance à confirmer")
        self.assertIn('<span class="hyp">', gl.marquer("14,6 kW (hyp.)", confirmer=False))
        self.assertTrue(gl.marquer("à confirmer").startswith('<span class="a-confirmer">'))
        self.assertNotIn("a-confirmer", gl.paragraphes_html("Charge à confirmer.\n\n- point à confirmer"))

    def test_annotations_de_lecture_retirees(self):
        sa = gl.sans_annotations
        self.assertEqual(sa(f"Fictif X-9 (lecture douteuse) · n° 12?45 (un chiffre masqué) · 40,10{NBSP}m³/h (hyp.)"),
                         f"40,10{NBSP}m³/h (hyp.) · plaque partiellement lisible")
        self.assertEqual(sa("Plaque de la centrale · Désignation « CF-1 » · n° 77-01 · lecture : sûre sauf la "
                            "désignation (douteuse)"), "Plaque de la centrale · n° 77-01 · plaque partiellement lisible")
        self.assertEqual(sa("Échangeur Fictif · type et données illisibles · n° 555 · lecture : illisible (type)"),
                         "Échangeur Fictif · n° 555 · plaque partiellement lisible")
        self.assertEqual(sa("Fictif C-1 · Type « ABC » · n° 9 · lecture : type douteux (caractères serrés), reste sûr"),
                         "Fictif C-1 · n° 9 · plaque partiellement lisible")
        self.assertEqual(sa("Fictif X-9 · n° 1 · lecture : sûre"), "Fictif X-9 · n° 1")
        vue = ("Local · collecteur, pompe verte (Wilo ?), type « G-1 » (douteux), deux afficheurs (illisibles), "
               "bouteille bleue (étiquette « R » ?)")
        self.assertEqual(sa(vue, plaque=False), "Local · collecteur, pompe verte, deux afficheurs, bouteille bleue")
        self.assertEqual(sa("Compresseur 2/2 : Fictif X-9 (lecture douteuse), n° 1, 40,10 m³/h", separateur=", "),
                         "Compresseur 2/2 : n° 1, 40,10 m³/h, plaque partiellement lisible")
        self.assertEqual(sa("Condenseur Fictif (Usine, Ville) : Type « A », n° 2, lecture : type douteux, reste sûr",
                            separateur=", "), "Condenseur Fictif (Usine, Ville) : n° 2, plaque partiellement lisible")
        sans = f"Fictif X-100 · n° 0001 · 40,1{NBSP}m³/h, R449A (hyp.) · puissance à confirmer par vos calculs"
        self.assertEqual(sa(sans), sans)                                          # rien à retirer : inchangé

    def test_statut_du_poste_jamais_repete(self):
        """Puissance d'un poste déjà marquée par assembler.py (« 43,2 kW (hyp.) ») : le statut n'est pas rajouté."""
        d = demande_fictive()
        carte = {f: "img/x.jpg" for f in gl.photos_referencees(d)}
        d["postes"][0].update(puissance=f"48,2{NBSP}kW (hyp.)", statut="hypothèse")
        d["postes"][2].update(puissance="à confirmer", statut="à confirmer")
        postes = gl.preparer_vue(d, carte)["postes"]
        self.assertEqual(postes[0]["puissance_html"].count("(hyp.)"), 1)
        self.assertEqual(postes[1]["puissance_html"].count("(calculé)"), 1)        # texte sans marque : statut ajouté
        self.assertEqual(postes[2]["puissance_html"].count("à confirmer"), 1)


class TestRedimensionnement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _verifier(self, moteur):
        src = self.d / "src.png"
        fabriquer_image(src, (200, 30, 30), "test", (1200, 900), mode="RGBA")
        avant = empreinte(src)
        taille = gl.redimensionner(src, self.d / "out" / f"{moteur}.jpg", moteur=moteur)
        self.assertEqual(taille, (800, 600))
        self.assertEqual(empreinte(src), avant)
        self.assertEqual(pymupdf.Pixmap(str(self.d / "out" / f"{moteur}.jpg")).width, 800)

    def test_pillow(self):
        if Image is None:
            self.skipTest("Pillow absent")
        self._verifier("pillow")

    def test_repli_pymupdf(self):
        self._verifier("pymupdf")

    def test_petite_image_jamais_agrandie(self):
        src = self.d / "petite.jpg"
        fabriquer_image(src, (10, 10, 10), "p", (450, 600))
        self.assertEqual(gl.redimensionner(src, self.d / "p.jpg"), (450, 600))

    def test_refus_d_ecraser_l_original(self):
        src = self.d / "a.jpg"
        fabriquer_image(src, (10, 10, 10), "a", (100, 100))
        with self.assertRaises(gl.ErreurLivrable):
            gl.redimensionner(src, src)


class TestLivrable(unittest.TestCase):
    """Dossier fictif complet (7 chapitres), PDF imprimé si Edge ou Chrome est présent."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.dossier = construire_dossier_fictif(Path(cls.tmp.name))
        cls.empreintes = {rel: empreinte(cls.dossier / rel) for rel in PHOTOS}
        cls.navigateur = gl.trouver_navigateur()
        cls.r = gl.generer(cls.dossier, VERSION, pdf=cls.navigateur is not None)
        cls.html = cls.r["html"].read_text(encoding="utf-8")
        cls.demande = demande_fictive()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_sept_chapitres_dans_l_ordre(self):
        self.assertEqual(len(re.findall(r'<section class="chapitre[ "]', self.html)), 7)
        # chapitres 1 à 5 en continu : nouvelle page seulement pour le contexte, les postes et les annexes
        self.assertEqual(re.findall(r'<section class="chapitre nouvelle-page" id="(\w+)"', self.html),
                         ["contexte", "postes", "annexes"])
        attendus = ["Contexte", "Les chambres à traiter", "La production frigorifique existante",
                    "Les évaporateurs en place", "Notre demande", "Le détail par poste", "Annexes"]
        titres = re.findall(r'<h1 class="chapitre-titre"><span class="num">(\d+)\.</span>(.*?)</h1>', self.html)
        self.assertEqual(titres, [(str(i), t) for i, t in enumerate(attendus, 1)])

    def test_un_bloc_par_poste_et_toutes_les_legendes(self):
        self.assertEqual(self.html.count('<article class="poste"'), 3)
        legendes = [p["legende"] for poste in self.demande["postes"] for p in poste["photos"]]
        legendes += [v["legende"] for v in self.demande["annexes"]["vues_ensemble"]]
        self.assertEqual(len(legendes), 6)
        texte = re.sub(r"<[^>]+>", "", self.html)
        for legende in legendes:
            self.assertIn(gl.echapper(legende), texte)
        self.assertEqual(self.html.count("<figcaption>"), 6)
        self.assertEqual(self.html.count('<div class="rangee">'), 5)   # 2 + 1 + 1 pour les postes, 1 en annexe

    def test_aucune_marque_de_gabarit_restante(self):
        self.assertNotIn("{{", self.html)
        self.assertNotIn("}}", re.sub(r"<style>.*?</style>", "", self.html, flags=re.S))

    def test_espaces_insecables_conserves(self):
        self.assertIn(f"48,2{NBSP}kW", self.html)
        self.assertIn(f"40,1{NBSP}m³/h", self.html)

    def test_statuts_et_plan_a_suivre(self):
        self.assertIn('<span class="statut">(hyp.)</span>', self.html)
        self.assertIn('<span class="a-confirmer">à confirmer par vos calculs</span>', self.html)
        self.assertIn("Plan d'implantation :", self.html)
        self.assertIn("à suivre", self.html)

    def test_images_redimensionnees_originaux_intacts(self):
        self.assertEqual(len(self.r["images"]), 6)
        for chemin in self.r["images"]:
            self.assertTrue(chemin.is_file(), chemin)
            self.assertEqual(chemin.parent.name, "img")
            self.assertLessEqual(pymupdf.Pixmap(str(chemin)).width, gl.LARGEUR_MAX)
            self.assertIn(f'src="img/{chemin.name}"', self.html)
        for rel, h in self.empreintes.items():
            self.assertEqual(empreinte(self.dossier / rel), h, rel)

    def test_mail_sans_tableau(self):
        txt = self.r["mail_txt"].read_text(encoding="utf-8")
        self.assertEqual(self.r["mail_txt"].name, "mail-grossiste.txt")
        lignes = txt.split("\n")
        self.assertEqual(lignes[0], self.demande["mail"]["objet"])
        self.assertEqual(lignes[1], "")
        self.assertEqual(lignes[2], "Bonjour,")
        self.assertNotIn("|", txt)
        self.assertNotIn("<table", txt)
        self.assertIn("Bien à vous,", txt)
        page = self.r["mail_html"].read_text(encoding="utf-8")
        self.assertNotIn("<table", page)
        self.assertIn("<p>Bonjour,</p>", page)

    def test_pdf(self):
        if self.navigateur is None:
            self.skipTest("ni Edge ni Chrome sur ce PC")
        pdf = self.r["pdf"]
        self.assertTrue(pdf.is_file())
        self.assertLess(pdf.stat().st_size, gl.SEUIL_MO * gl.OCTETS_PAR_MO)
        with pymupdf.open(pdf) as doc:
            self.assertGreater(doc.page_count, 1)
            self.assertEqual(doc.page_count, self.r["pages"])
            self.assertAlmostEqual(doc[0].rect.width, 595, delta=2)       # A4 portrait
            texte = "".join(p.get_text() for p in doc)
        self.assertIn("Notre demande", texte)
        self.assertIn("Page 2 /", texte)
        self.assertIn("sélection finale chez le fournisseur", texte)
        self.assertEqual(self.r["avertissements"], [])


class TestSansEvaporateurs(unittest.TestCase):
    """Chapitre des évaporateurs omis (renumérotation) et textes piégés échappés ; sans PDF."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.dossier = construire_dossier_fictif(Path(cls.tmp.name), evaporateurs=False, piege=True)
        cls.r = gl.generer(cls.dossier, VERSION, pdf=False)
        cls.html = cls.r["html"].read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_six_chapitres_renumerotes(self):
        self.assertEqual(len(re.findall(r'<section class="chapitre[ "]', self.html)), 6)
        self.assertNotIn("Les évaporateurs en place", self.html)
        self.assertIn('<span class="num">4.</span>Notre demande', self.html)
        self.assertIn('<span class="num">5.1</span>Centrale négative A', self.html)
        self.assertIsNone(self.r["pdf"])

    def test_texte_piege_echappe(self):
        self.assertNotIn("<script>", self.html)
        self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; Co", self.html)


class TestErreurs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.dossier = construire_dossier_fictif(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_version_mal_formee(self):
        with self.assertRaises(gl.ErreurLivrable):
            gl.generer(self.dossier, "1", pdf=False)

    def test_version_avec_suffixe(self):
        """vN-<suffixe> (dossier écrit par assembler.py pour la variante fabricant) : accepté, fichiers nommés d'après lui."""
        demande = demande_fictive()
        demande.update(variante="fabricant", anonymise=False)
        dv = self.dossier / gl.SOUS_DOSSIER / "v1-fabricant"
        dv.mkdir(parents=True)
        (dv / "demande.json").write_text(json.dumps(demande, ensure_ascii=False), encoding="utf-8")
        r = gl.generer(self.dossier, "v1-fabricant", pdf=False)
        self.assertEqual(r["html"], dv / "demande-v1-fabricant.html")
        self.assertEqual(r["mail_txt"].name, "mail-fabricant.txt")
        for mauvaise in ("v1-", "v1_fabricant", "v1-Fabricant", "fabricant-v1"):
            with self.assertRaises(gl.ErreurLivrable, msg=mauvaise):
                gl.generer(self.dossier, mauvaise, pdf=False)

    def test_reference_de_la_page_de_garde_et_legende_des_statuts(self):
        """Variante nommée : « Référence » = client – localité, jamais le n° de fiche ; clé « à confirmer » sous le
        tableau 3 seulement s'il y en a un, note et clé dans le même bloc que le tableau (jamais coupés)."""
        chemin = self.dossier / gl.SOUS_DOSSIER / VERSION / "demande.json"
        demande = json.loads(chemin.read_text(encoding="utf-8"))
        demande.update(anonymise=False, site={"nom": "Fictive SA", "localite": "Ville-Essai", "reference_dossier": "IN00001"})
        chemin.write_text(json.dumps(demande, ensure_ascii=False), encoding="utf-8")
        page = gl.generer(self.dossier, VERSION, pdf=False)["html"].read_text(encoding="utf-8")
        self.assertIn("<th>Référence</th><td>Fictive SA – Ville-Essai</td>", page)
        self.assertNotIn("IN00001", page)
        production = page[page.index('id="production"'):page.index('id="evaporateurs"')]
        self.assertIn('<span class="a-confirmer">à confirmer</span> : donnée encore à vérifier', production)
        self.assertNotIn("(hyp.) : valeur", production)                            # définie une fois, au chapitre 2
        self.assertRegex(production, r'(?s)<div class="entree-chapitre">(?:(?!</section>).)*class="note"(?:(?!</section>).)*'
                                     r'</div>\s*</div>\s*</section>')
        for ligne in demande["production"]["lignes"]:
            ligne.update(puissance=f"12,0{NBSP}kW", volume_balaye=f"10,00{NBSP}m³/h", statut="hyp.")
        for st in demande["production"]["sous_totaux"]:
            st["puissance"] = f"12,0{NBSP}kW"
        chemin.write_text(json.dumps(demande, ensure_ascii=False), encoding="utf-8")
        page = gl.generer(self.dossier, VERSION, pdf=False)["html"].read_text(encoding="utf-8")
        self.assertNotIn("donnée encore à vérifier", page)

    def test_typographie_au_rendu_seulement(self):
        """CO₂, guillemets et signe moins dans la page et le mail ; demande.json reste tel quel."""
        chemin = self.dossier / gl.SOUS_DOSSIER / VERSION / "demande.json"
        demande = json.loads(chemin.read_text(encoding="utf-8"))
        demande["contexte"]["texte"] = "Centrale CO2 booster, étiquette « Rosada », évaporation -30 °C ; charge à confirmer."
        demande["mail"]["corps"] = "Centrale CO2 booster, évaporation -30 °C. Détail dans le PDF joint."
        chemin.write_text(json.dumps(demande, ensure_ascii=False), encoding="utf-8")
        avant = chemin.read_bytes()
        r = gl.generer(self.dossier, VERSION, pdf=False)
        page = r["html"].read_text(encoding="utf-8")
        contexte = page[page.index('id="contexte"'):page.index('id="chambres"')]
        self.assertIn(f"Centrale CO₂ booster, étiquette «{NBSP}Rosada{NBSP}», évaporation −30 °C", contexte)
        self.assertNotIn("a-confirmer", contexte)                       # texte courant : pas de couleur
        self.assertIn('<span class="a-confirmer">à confirmer par vos calculs</span>', page)     # cellule : couleur
        self.assertIn("Centrale CO₂ booster, évaporation −30 °C.", r["mail_txt"].read_text(encoding="utf-8"))
        self.assertEqual(chemin.read_bytes(), avant)

    def test_photo_introuvable(self):
        (self.dossier / "sources/photos/04-local/p10-1.jpg").unlink()
        with self.assertRaises(gl.ErreurLivrable) as ctx:
            gl.generer(self.dossier, VERSION, pdf=False)
        self.assertIn("p10-1.jpg", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
