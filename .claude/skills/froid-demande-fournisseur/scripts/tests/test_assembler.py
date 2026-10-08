"""Tests d'assembler.py (étape 3, données de la demande de prix) sur un dossier fictif, et de l'extension « photo »
de calculs.py (étape 2).

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-demande-fournisseur/scripts/tests -v
Le dossier est créé dans un répertoire temporaire du système (rien n'est écrit dans le dépôt) : noms, adresse,
téléphone, mail et n° de fiche inventés ; 2 postes (négatif, positif), 3 compresseurs (dont un en lecture douteuse sans
champ « photo », pour le repli), 2 évaporateurs (dont un sans champ « photo »), une plaque d'ensemble, 9 photos.
2-resultats.json est produit par le vrai calculs.py de l'étape 2.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
SCRIPTS_DIM = SCRIPTS.parents[1] / "froid-dimensionnement" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS_DIM))
import assembler  # noqa: E402
import calculs  # noqa: E402
from controles import somme  # noqa: E402
from valeur import Valeur, depuis_json, en_json  # noqa: E402

S, H = "sourcé", "hypothèse"
CLIENT = "BOUCHERIE FICTIVOR"
IDENTIFIANTS = ("fictivor", "testville", "rue des essais", "9999", "0499", "11 22 33", "in99999", "fictivor.test")

PHOTOS = {
    "01-centrale-negative-fictive": ["p02-1", "p02-2", "p02-3", "p02-4"],
    "02-evaporateur-negatif-fictif": ["p03-1", "p03-2"],
    "03-groupe-positif-fictif": ["p04-1"],
    "04-evaporateur-positif-fictif": ["p05-1"],
    "09-regulation": ["p06-1"],
}

DOSSIER_MD = f"""# Dossier {CLIENT} — visite du 01/01/2026 — fiche InterFast IN99999

- **Slug** : `2026-01-01-boucherie-fictivor` · **Type de fiche** : VisiteAvantDevis · **Responsable** : JEAN ESSAI
- **Client** : {CLIENT} — 12 Rue des Essais 9999 Testville · 0499 11 22 33 · info@fictivor.test
- **Adresse d'intervention** : 12 Rue des Essais 9999 Testville
- **Étape en cours** : **2 · Dimensionnement — à valider ✋**
"""

EXISTANT_MD = f"""# Relevé de l'existant — {CLIENT} — visite du 01/01/2026 (fiche InterFast IN99999)

## B. Compresseurs (une ligne par compresseur, d'après les plaques)

| Poste | Marque | Modèle (référence complète) | N° de série | Fluides sur la plaque | Tension | Volume balayé et autres données de plaque | Photo | Lecture | Source |
|---|---|---|---|---|---|---|---|---|---|
| CENTRALE NÉGATIVE FICTIVE — compresseur 1/2 | Bitzer | 4CES-6Y-40S | 1111111111 | — | 400 V | 32,5 m³/h | `01-centrale-negative-fictive/p02-1.jpeg` | sûre | photo p02-1 |
| CENTRALE NÉGATIVE FICTIVE — compresseur 2/2 | Fictif | MODELE-FICTIF-1 | 2222222222 (un chiffre masqué) | — | 400 V | 20 m³/h | `01-centrale-negative-fictive/p02-2.jpeg` | douteuse | photo p02-2 |
| GROUPE POSITIF FICTIF — compresseur 1/1 | Bitzer | 4CES-6Y-40S | 3333333333 | — | 400 V | 32,5 m³/h | `03-groupe-positif-fictif/p04-1.jpeg` | sûre | photo p04-1 |

### B2. Plaques d'ensemble (centrales, condenseurs, échangeurs)

| Poste | Équipement | Ce que dit la plaque | Photo | Lecture |
|---|---|---|---|---|
| CENTRALE NÉGATIVE FICTIVE | Plaque constructeur de la centrale | Désignation « centrale fictive » ; fluide primaire **R449A** ; n° 4444-01 ; date de mise en service 2015 | `01-centrale-negative-fictive/p02-3.jpeg` | sûre |
| CENTRALE NÉGATIVE FICTIVE | Vue de la centrale : 2 compresseurs, réservoir | — | `p02-4.jpeg` | — |

## C. Chambres froides et postes desservis

| Poste / chambre | L × l × h | Volume (m³, calcul) | Température | Usage | Évaporateurs (plaques) | Desservie par | Source |
|---|---|---|---|---|---|---|---|
| Chambre négative fictive | 5 × 8 × 2,5 m | 100 | à confirmer | congélation (photo p03-2) ; produits à confirmer | Fictair **EVA-1** (n° 5555/01, 2010, R404A) | centrale | rapport p. 3 ; photos p03-1, p03-2 |
| Chambre positive fictive | 4 × 5 × 2,5 m | 50 | à confirmer | stockage | Fictair **EVA-2** (n° 6666/02, 2012, R449A) | groupe | rapport p. 4 ; photos p05-1 |

## D. Régulation, récupération de chaleur, chauffage, électricité

| Élément | Ce que dit le rapport | Lu sur les photos | Photo | Source |
|---|---|---|---|---|
| Régulation — centrale | — | Armoire fictive, étiquette « dépannage 0499 11 22 33 » (repère 12) ; afficheur | `09-regulation/p06-1.jpeg` | rapport p. 6 |

## E. À confirmer par Loïc

- [ ] rien

## F. Photos extraites (index)

| Photo | Page | Poste | Taille |
|---|---|---|---|
""" + "".join(f"| `sources/photos/{d}/{r}.jpeg` | {r[1:3]} | {d.split('-', 1)[1].upper()} | 450 × 600 |\n"
              for d, refs in PHOTOS.items() for r in refs)

DIMENSIONNEMENT_MD = f"""# Dimensionnement du remplacement — {CLIENT}

## A. Projet

| Élément | Contenu | Source |
|---|---|---|
| Ce qu'on remplace | La centrale négative fictive et le groupe positif fictif de {CLIENT} | essai |
| Par quoi | Une **centrale CO2 booster** en extérieur sous toit grillagé, avec récupération de chaleur pour le chauffage du sol | essai |
| Qui dessert quoi | Centrale → chambre négative ; groupe → chambre positive ; les deux chambres sont accolées | essai |
| Marché | Mis en concurrence (3 entreprises), souhait du client : avril ; chantier à Testville (fiche IN99999) | essai |

## E. Ce qu'on garde, ce qu'on remplace

| Élément | Existant (N = centrale négative fictive, P = groupe positif fictif) | Avec la centrale CO2 booster | Source |
|---|---|---|---|
| Compresseurs | N : 4CES-6Y-40S, MODELE-FICTIF-1 · P : 4CES-6Y-40S | **remplacés** par les compresseurs CO2 de la centrale (G3, question 1) | essai |
| Chambres | 2 chambres | **gardées** | essai |

## F. Fournitures annexes (à lister pour le fournisseur)

- **Armoire de régulation Danfoss** neuve, pré-câblée ; supervision **AK-SM 800A** ; régulateurs **AK-CC 55**.
- **Dégivrage** électrique en négatif ; dégivrage naturel en positif.
- **Évaporateurs CO2** Alfa Laval de préférence.
- **Centrale CO2 booster** : gas coolers sur l'été passé, récupération de chaleur, aimants permanents, variateur, désurchauffeur.
- **Cuivre K65, isolants et petites fournitures** : prix indicatifs du moment.

## G. Hypothèses

- aucune
"""


def v(n, u, src, st, id):
    return Valeur(n, u, src, st, id=id)


def chemin(dossier: str, ref: str) -> str:
    return f"sources/photos/{dossier}/{ref}.jpeg"


def entrees_fictives() -> dict:
    def regime(p, t0):
        return {"t0": v(t0, "°C", "dicté par Loïc le 2026-01-01 (essai)", S, f"{p}-t0"),
                "tc": v(40, "°C", "dicté par Loïc le 2026-01-01 (essai)", S, f"{p}-tc")}
    return {
        "format": "2-entrees v1", "dossier": "2026-01-01-boucherie-fictivor",
        "projet": {
            "texte": {"texte": "Remplacer la centrale et le groupe par une centrale CO2 booster",
                      "source": "dicté par Loïc le 2026-01-01", "statut": S},
            "fluide_actuel": {"valeur": "R449A", "source": "rapport p. 2", "statut": S, "id": "fluide-actuel"},
            "fluide_cible": {"valeur": "R744", "source": "dicté par Loïc le 2026-01-01", "statut": S,
                             "id": "fluide-cible"},
            "type_equipement": {"poste-n": "centrale", "poste-p": "groupe de condensation"},
            "type_equipement_cible": "centrale", "precision": "remise de prix", "date_analyse": "2026-01-01"},
        "postes": [
            {"id": "poste-n", "nom": "Centrale négative fictive",
             "dessert": {"texte": f"chambre négative fictive, congélation chez {CLIENT} (1 évaporateur)",
                         "source": "rapport p. 3", "statut": S},
             "temperature_chambre": v(None, "°C", "non écrite dans le rapport : à confirmer", "à confirmer",
                                      "n-t-chambre"),
             "volume": Valeur(100, "m³", "rapport p. 3 : « 5 x 8 x 2,5 », hypothèse : dimensions en mètres", H,
                              "5 × 8 × 2,5", id="n-volume"),
             "regime": regime("n", -30),
             "charge": v(20, "kg", "rapport p. 3", S, "n-charge"),
             "compresseurs": [
                 {"id": "n-c1", "marque": "Bitzer", "modele": "4CES-6Y-40S", "lecture": "sûre",
                  "volume_balaye": v(32.5, "m³/h", "photo p02-1 (plaque)", S, "n-c1-vb"),
                  "frequence": v(50, "Hz", "photo p02-1", S, "n-c1-freq"),
                  "photo": [chemin("01-centrale-negative-fictive", "p02-1")]},
                 {"id": "n-c2", "marque": "Fictif", "modele": "MODELE-FICTIF-1", "lecture": "douteuse",
                  "note": "un chiffre masqué",
                  "volume_balaye": v(20.0, "m³/h", "photo p02-2 ; lecture douteuse : un chiffre masqué", H,
                                     "n-c2-vb")}],
             "evaporateurs": [{"id": "n-e1", "modele": "Fictair EVA-1", "annee": "2010", "fluide_origine": "R404A",
                               "source": "1-existant.md § C (rapport p. 3 ; photos p03-1)",
                               "photo": [chemin("02-evaporateur-negatif-fictif", "p03-1")]}],
             "plaques_ensemble": [{"id": "n-plaque", "texte": "plaque de la centrale fictive (photo p02-3)",
                                   "puissance": v(9, "kW", "photo p02-3 : plaque de la centrale", S, "n-plaque-kw"),
                                   "fluide": None, "regime": None,
                                   "photo": [chemin("01-centrale-negative-fictive", "p02-3")]}],
             "estimations": []},
            {"id": "poste-p", "nom": "Groupe positif fictif",
             "dessert": {"texte": "chambre positive fictive, stockage (1 évaporateur)", "source": "rapport p. 4",
                         "statut": S},
             "temperature_chambre": v(None, "°C", "non écrite dans le rapport : à confirmer", "à confirmer",
                                      "p-t-chambre"),
             "volume": Valeur(50, "m³", "rapport p. 4 : « 4 x 5 x 2,5 », hypothèse : dimensions en mètres", H,
                              "4 × 5 × 2,5", id="p-volume"),
             "regime": regime("p", -10),
             "charge": v(None, "kg", "absente de la plaque", "à confirmer", "p-charge"),
             "compresseurs": [
                 {"id": "p-c1", "marque": "Bitzer", "modele": "4CES-6Y-40S", "lecture": "sûre",
                  "volume_balaye": v(32.5, "m³/h", "photo p04-1 (plaque)", S, "p-c1-vb"),
                  "frequence": v(50, "Hz", "photo p04-1", S, "p-c1-freq"),
                  "photo": [chemin("03-groupe-positif-fictif", "p04-1")]}],
             "evaporateurs": [{"id": "p-e1", "modele": "Fictair EVA-2", "annee": "2012", "fluide_origine": "R449A",
                               "source": "1-existant.md § C (rapport p. 4 ; photos p05-1)"}],
             "plaques_ensemble": [], "estimations": []},
        ],
    }


def construire_dossier(racine: Path) -> Path:
    dossier = racine / "2026-01-01-boucherie-fictivor"
    for d, refs in PHOTOS.items():
        (dossier / "sources" / "photos" / d).mkdir(parents=True)
        for r in refs:
            (dossier / "sources" / "photos" / d / f"{r}.jpeg").write_bytes(b"\xff\xd8\xff\xd9")
    (dossier / "dossier.md").write_text(DOSSIER_MD, encoding="utf-8")
    (dossier / "1-existant.md").write_text(EXISTANT_MD, encoding="utf-8")
    (dossier / "2-dimensionnement.md").write_text(DIMENSIONNEMENT_MD, encoding="utf-8")
    (dossier / "2-entrees.json").write_text(en_json(entrees_fictives(), indent=2), encoding="utf-8")
    (racine / "emetteur.json").write_text(json.dumps({"societe": "Émetteur Fictif", "contact": "Paul Essai",
                                                      "telephone": "0400 00 00 01", "mail": "devis@emetteur.test",
                                                      "adresse": ""}), encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()) as sortie:
        code = calculs.main([str(dossier)])
    if code != 0:
        raise RuntimeError(f"calculs.py a échoué ({code}) : {sortie.getvalue()}")
    return dossier


def lancer(*args) -> tuple[int, str]:
    with contextlib.redirect_stdout(io.StringIO()) as sortie:
        code = assembler.main([str(a) for a in args])
    return code, sortie.getvalue()


class TestAssembler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dossier = construire_dossier(Path(cls._tmp.name))
        cls.res = depuis_json((cls.dossier / "2-resultats.json").read_text(encoding="utf-8"))
        cls.g = assembler.assembler(cls.dossier, "grossiste", date="2026-01-02")
        cls.f = assembler.assembler(cls.dossier, "fabricant", destinataire="Jean Essai, Fournisseur Fictif",
                                    tutoiement=True, date="2026-01-02")
        cls.dg, cls.df = cls.g["demande"], cls.f["demande"]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def poste(self, pid):
        return next(p for p in self.res["postes"] if p["id"] == pid)

    # ---------- schéma ----------
    def test_schema_conforme(self):
        for d in (self.dg, self.df):
            self.assertEqual(assembler.verifier_schema(d), [])
            self.assertEqual(list(d.keys()), list(assembler.CLES_DEMANDE))
            self.assertEqual(set(d["emetteur"]), {"societe", "contact", "telephone", "mail", "adresse"})
            self.assertEqual(set(d["site"]), {"nom", "localite", "reference_dossier"})
            self.assertEqual(set(d["annexes"]), {"vues_ensemble", "plan_implantation", "pieces_jointes", "documents"})
            self.assertEqual(d["annexes"]["plan_implantation"], "à suivre")
            self.assertEqual(d["annexes"]["documents"], [])               # pas de plan/plan.pdf
            self.assertEqual(d["longueurs"], {"absentes": True, "phrase": assembler.PHRASE_NON_RELEVEES})
            self.assertEqual(set(d["mail"]), {"objet", "salutation", "corps", "formule", "signature"})
            for p in d["postes"]:
                self.assertEqual(set(p), {"id", "titre", "dessert", "existant", "puissance", "statut",
                                          "remplacement", "photos"})
            relu = json.loads((self.g["chemin"] if d is self.dg else self.f["chemin"]).read_text(encoding="utf-8"))
            self.assertEqual(relu, d)
        self.assertEqual(self.dg["version"], "v1")
        self.assertEqual(self.g["dossier_sortie"].name, "v1")
        self.assertEqual(self.f["dossier_sortie"].name, "v1-fabricant")
        self.assertIsNone(self.dg["destinataire"])
        self.assertIsNotNone(self.dg["evaporateurs"])
        self.assertIsNone(self.df["evaporateurs"])
        self.assertEqual(len(self.dg["evaporateurs"]["lignes"]), 2)
        for l in self.dg["evaporateurs"]["lignes"]:
            self.assertEqual(l["puissance"], "à confirmer par vos calculs")

    def test_schema_detecte_un_ecart(self):
        d = json.loads(json.dumps(self.dg))
        del d["mail"]["formule"]
        d["postes"][0]["photos"][0]["type"] = "autre"
        erreurs = assembler.verifier_schema(d)
        self.assertTrue(any("mail" in e for e in erreurs))
        self.assertTrue(any("type" in e for e in erreurs))

    # ---------- anonymisation ----------
    def test_anonymisation_grossiste(self):
        self.assertTrue(self.dg["anonymise"])
        self.assertEqual(self.dg["site"], {"nom": "", "localite": "", "reference_dossier": ""})
        sortie = self.g["dossier_sortie"]
        for nom in ("demande.json", "valeurs-derivees.json"):
            texte = (sortie / nom).read_text(encoding="utf-8").lower()
            for ident in IDENTIFIANTS:
                self.assertNotIn(ident, texte, f"{ident} survit dans {nom}")
        self.assertIn("installation frigorifique", self.dg["titre"])
        # les identifiants ont bien été remplacés (pas seulement absents) : bloc A et tableau D
        self.assertIn("le client", self.dg["contexte"]["texte"])
        self.assertTrue(any("(téléphone retiré)" in v["legende"] for v in self.dg["annexes"]["vues_ensemble"]))
        ids = json.loads((sortie / "identifiants-client.json").read_text(encoding="utf-8"))
        self.assertTrue(ids["anonymise"])
        recherches = " ".join(ids["recherches"]).lower()
        for ident in ("boucherie fictivor", "fictivor", "testville", "12 rue des essais", "9999", "0499 11 22 33",
                      "info@fictivor.test", "in99999"):
            self.assertIn(ident, recherches)

    def test_fabricant_nomme(self):
        d = self.df
        self.assertFalse(d["anonymise"])
        self.assertEqual(d["site"], {"nom": CLIENT, "localite": "Testville", "reference_dossier": "IN99999"})
        self.assertEqual(d["destinataire"], {"prenom": "Jean", "nom": "Essai", "societe": "Fournisseur Fictif",
                                             "tutoiement": True})
        self.assertIn(CLIENT, d["titre"])
        self.assertIn(f"réf. {CLIENT} – Testville", d["mail"]["objet"])
        self.assertEqual(d["mail"]["salutation"], "Salut Jean,")
        self.assertIn("Je te sollicite", d["contexte"]["texte"])
        self.assertNotIn("Nous vous sollicitons", d["contexte"]["texte"])

    def test_fabricant_vouvoiement_et_anonymisation_forcee(self):
        r = assembler.assembler(self.dossier, "fabricant", destinataire="Marie Essai, Fournisseur Fictif",
                                date="2026-01-02", anonymiser_force=True, ecrire=False)
        d = r["demande"]
        self.assertTrue(d["anonymise"])
        self.assertEqual(d["mail"]["salutation"], "Bonjour Marie Essai,")
        self.assertIn("Nous vous sollicitons", d["contexte"]["texte"])
        texte = json.dumps(d, ensure_ascii=False).lower()
        for ident in IDENTIFIANTS:
            self.assertNotIn(ident, texte)

    # ---------- textes des gabarits ----------
    def test_textes_grossiste(self):
        d = self.dg
        self.assertIn("Nous soumissionnons actuellement pour un marché de remodeling", d["contexte"]["texte"])
        self.assertIn("installation complète de A à Z", d["contexte"]["texte"])
        self.assertIn("Marché : mis en concurrence (3 entreprises), souhait du client : avril", d["contexte"]["texte"])
        self.assertEqual(d["mention"], "Valeurs indicatives, sélection finale chez le fournisseur.")
        self.assertTrue(d["demande"]["resume"].startswith("En résumé, nous recherchons le chiffrage"))
        self.assertEqual(d["mail"]["formule"], "Bien cordialement,")
        self.assertEqual(d["mail"]["salutation"], "Bonjour,")
        self.assertEqual(d["mail"]["signature"], "Paul Essai\nÉmetteur Fictif — 0400 00 00 01\ndevis@emetteur.test")
        self.assertIn("Les deux chambres sont accolées.", d["chambres"]["note"])
        titres = [p["titre"] for p in d["demande"]["points"]]
        self.assertEqual(titres[0], "Centrale CO₂ booster")
        self.assertIn("Évaporateurs CO₂ neufs", titres)
        self.assertIn("Tarifs indicatifs", titres)
        # bloc F sans détection de fuite ni détendeurs : ces points ne sortent pas, lettres renumérotées
        self.assertFalse(any("détection de fuite" in t for t in titres))
        self.assertFalse(any("Matériel frigorifique" in t for t in titres))
        self.assertEqual([p["lettre"] for p in d["demande"]["points"]], list("abcd"[:len(titres)]))
        armoire = next(p for p in d["demande"]["points"] if p["titre"].startswith("Armoire"))
        self.assertIn("Partie négative : 1 régulateur gérant l'évaporateur de la chambre négative fictive ; "
                      "dégivrage électrique sur chaque évaporateur.", armoire["sous_points"])
        self.assertIn("Supervision AK-SM 800A.", armoire["sous_points"])
        self.assertFalse(any("soupape" in s for s in armoire["sous_points"]))       # absent du bloc F

    def test_textes_fabricant(self):
        d = self.df
        titres = [p["titre"] for p in d["demande"]["points"]]
        for t in ("Gas coolers", "Récupération de chaleur", "Désurchauffeur", "Compresseurs", "Options",
                  "Implantation", "Planning"):
            self.assertIn(t, titres)
        planning = next(p for p in d["demande"]["points"] if p["titre"] == "Planning")
        self.assertIn("en avril", planning["texte"])
        self.assertIn("3 entreprises à remettre prix", d["contexte"]["texte"])
        self.assertIn("phase de prix", d["mail"]["corps"])
        self.assertEqual(d["mail"]["formule"], "À bientôt,")

    def test_mail_sans_tableau(self):
        for d in (self.dg, self.df):
            for k, texte in d["mail"].items():
                self.assertNotIn("|", texte, k)
                self.assertFalse(any(l.lstrip().startswith("|") for l in texte.split("\n")))
            self.assertIn("PDF joint", d["mail"]["corps"])
            paragraphes = d["mail"]["corps"].split("\n\n")
            self.assertTrue(4 <= len(paragraphes) <= 8, len(paragraphes))

    # ---------- chiffres : ceux de 2-resultats.json, rendus par Valeur.texte() ----------
    def test_chiffres_identiques_aux_resultats(self):
        d = self.dg
        for ligne, p in zip(d["production"]["lignes"], self.res["postes"]):
            self.assertEqual(ligne["poste"], p["nom"])
            self.assertEqual(ligne["puissance"], p["existante"].texte(marque=False))
            self.assertEqual(ligne["statut"], p["existante"].statut)
            vt = somme([c["volume_balaye"] for c in p["compresseurs"]], "m³/h")
            self.assertEqual(ligne["volume_balaye"], vt.texte())
        sous = {s["libelle"].split(" (")[0]: s["puissance"] for s in d["production"]["sous_totaux"]}
        self.assertEqual(sous["Sous-total négatif"], self.poste("poste-n")["existante"].texte(marque=False))
        self.assertEqual(sous["Sous-total positif"], self.poste("poste-p")["existante"].texte(marque=False))
        for p in self.res["postes"]:
            self.assertIn(p["existante"].texte(marque=False), d["mail"]["corps"])
            self.assertIn(p["existante"].texte(marque=False), d["contexte"]["texte"])
        for ligne, p in zip(d["chambres"]["lignes"], self.res["postes"]):
            self.assertEqual(ligne["volume"], p["volume"].texte())
        self.assertEqual(d["chambres"]["lignes"][0]["surface"], "40,0\u00a0m² (hyp.)")    # 5 × 8, hypothèse
        derivees = {x["id"]: x for x in self.g["derivees"]}
        self.assertIn("poste-n-surface", derivees)
        self.assertIn("poste-n-volume-balaye-total", derivees)
        jp = {pj["id"]: pj for pj in d["postes"]}
        for p in self.res["postes"]:
            self.assertEqual(jp[p["id"]]["puissance"], p["existante"].texte())
            for c in p["compresseurs"]:
                self.assertTrue(any(f"puissance retenue {c['retenue'].texte()}" in ph["legende"]
                                    for ph in jp[p["id"]]["photos"]), c["id"])

    # ---------- photos ----------
    def test_photos_placees_une_fois(self):
        d = self.dg
        par_poste = {pj["id"]: {ph["fichier"]: ph for ph in pj["photos"]} for pj in d["postes"]}
        n = par_poste["poste-n"]
        self.assertEqual(n[chemin("01-centrale-negative-fictive", "p02-1")]["type"], "plaque")
        self.assertIn("n° 1111111111", n[chemin("01-centrale-negative-fictive", "p02-1")]["legende"])
        # repli : compresseur sans champ « photo », photo lue dans la source du volume balayé
        self.assertIn("MODELE-FICTIF-1 (lecture douteuse)", n[chemin("01-centrale-negative-fictive", "p02-2")]["legende"])
        self.assertIn("n° 5555/01", n[chemin("02-evaporateur-negatif-fictif", "p03-1")]["legende"])
        ens = n[chemin("01-centrale-negative-fictive", "p02-3")]
        self.assertEqual(ens["type"], "ensemble")
        self.assertIn("puissance lue sur la plaque 9,0\u00a0kW", ens["legende"])
        p = par_poste["poste-p"]
        # repli : évaporateur sans champ « photo », une photo citée par sa source
        self.assertIn("n° 6666/02", p[chemin("04-evaporateur-positif-fictif", "p05-1")]["legende"])
        self.assertTrue(any("p-e1" in a for a in self.g["avertissements"]))
        vues = {v["fichier"]: v["legende"] for v in d["annexes"]["vues_ensemble"]}
        self.assertEqual(set(vues), {chemin("01-centrale-negative-fictive", "p02-4"),
                                     chemin("02-evaporateur-negatif-fictif", "p03-2"), chemin("09-regulation", "p06-1")})
        self.assertIn("vue de la chambre (congélation)", vues[chemin("02-evaporateur-negatif-fictif", "p03-2")])
        self.assertTrue(vues[chemin("01-centrale-negative-fictive", "p02-4")].startswith("Centrale négative fictive · "))
        tous = assembler._chemins_photos(d)
        self.assertEqual(len(tous), len(set(tous)))
        self.assertEqual(len(tous), sum(len(r) for r in PHOTOS.values()))
        for ch in tous:
            self.assertTrue((self.dossier / ch).is_file(), ch)

    def test_remplacement_depuis_bloc_e(self):
        jp = {pj["id"]: pj for pj in self.dg["postes"]}
        armoire = next(pt["lettre"] for pt in self.dg["demande"]["points"] if "armoire" in pt["titre"].lower())
        self.assertEqual(jp["poste-n"]["remplacement"],                                # (G3…) retiré ; renvoi
                         f"Compresseurs : remplacés par les compresseurs CO2 de la centrale. Régulation : voir § 5 {armoire}).")
        self.assertEqual(jp["poste-p"]["remplacement"], jp["poste-n"]["remplacement"])
        for pj in self.df["postes"]:                                                   # fabricant : pas d'armoire
            self.assertEqual(pj["remplacement"], "Compresseurs : remplacés par les compresseurs CO2 de la centrale.")

    def test_aucun_exclu_interne_dans_le_dossier_fictif(self):
        for d in (self.dg, self.df):
            self.assertEqual(d["exclus_internes"], [])
        d = json.loads(json.dumps(self.dg))
        d["exclus_internes"] = [{"element": "Régulation", "postes": ["poste-n"], "texte": "x ?"}]   # raison absente
        self.assertTrue(any("exclus_internes[0]" in e for e in assembler.verifier_schema(d)))

    # ---------- versions et ligne de commande ----------
    def test_versions_et_codes_de_sortie(self):
        code, sortie = lancer(self.dossier, "--variante", "grossiste", "--version", "v1", "--date", "2026-01-02")
        self.assertEqual(code, 1, sortie)                                   # version existante sans --force
        code, sortie = lancer(self.dossier, "--variante", "grossiste", "--date", "2026-01-02")
        self.assertEqual(code, 0, sortie)
        self.assertTrue((self.dossier / "3-demande-fournisseur" / "v2" / "demande.json").is_file())
        code, sortie = lancer(self.dossier / "absent", "--variante", "grossiste")
        self.assertEqual(code, 2, sortie)
        code, sortie = lancer(self.dossier, "--variante", "grossiste", "--version", "deux")
        self.assertEqual(code, 1, sortie)


class TestExtensionPhoto(unittest.TestCase):
    """Champ facultatif « photo » de 2-entrees.json : recopié tel quel dans 2-resultats.json, sans effet sur les
    chiffres ; absent : sortie inchangée."""

    def test_photo_recopiee_et_chiffres_inchanges(self):
        with tempfile.TemporaryDirectory() as tmp:
            dossier = construire_dossier(Path(tmp))
            res = depuis_json((dossier / "2-resultats.json").read_text(encoding="utf-8"))
            n = next(p for p in res["postes"] if p["id"] == "poste-n")
            c1, c2 = n["compresseurs"]
            self.assertEqual(c1["photo"], [chemin("01-centrale-negative-fictive", "p02-1")])
            self.assertNotIn("photo", c2)                                        # absent → rien d'ajouté
            self.assertEqual(n["evaporateurs"][0]["photo"], [chemin("02-evaporateur-negatif-fictif", "p03-1")])
            self.assertEqual(n["plaques"][0]["photo"], [chemin("01-centrale-negative-fictive", "p02-3")])
            # mêmes entrées sans aucun champ « photo » : mêmes chiffres, mêmes tableaux
            e = entrees_fictives()
            for p in e["postes"]:
                for grp in ("compresseurs", "evaporateurs", "plaques_ensemble"):
                    for o in p[grp]:
                        o.pop("photo", None)
            sans = calculs.calculer_dossier(depuis_json(en_json(e)), calculs.charger_points(
                str(calculs.CHEMIN_POINTS_DEFAUT)))

            def sans_photo(o):
                if isinstance(o, dict):
                    return {k: sans_photo(x) for k, x in o.items() if k != "photo"}
                if isinstance(o, list):
                    return [sans_photo(x) for x in o]
                return o
            self.assertEqual(sans_photo(json.loads(en_json(res))), json.loads(en_json(sans)))
            self.assertEqual(calculs.tableaux_markdown(res), calculs.tableaux_markdown(sans))

    def test_photo_invalide_refusee(self):
        for mauvais in ("sources/photos/x.jpeg", ["C:/photos/x.jpeg"], [""], ["/abs/x.jpeg"]):
            e = entrees_fictives()
            e["postes"][0]["compresseurs"][0]["photo"] = mauvais
            erreurs, _ = calculs.verifier(depuis_json(en_json(e)))
            self.assertTrue(any(".photo" in x for x in erreurs), (mauvais, erreurs))
        e = entrees_fictives()
        erreurs, _ = calculs.verifier(depuis_json(en_json(e)))
        self.assertEqual(erreurs, [])


BLOC_E_FICTIF = """# Dimensionnement — essai

## E. Ce qu'on garde, ce qu'on remplace

| Élément | Existant (N = centrale négative fictive, CP = chambre positive fictive) | Avec la centrale CO2 booster | Source |
|---|---|---|---|
| Évaporateurs | N : Fictair EVA-1 (2010) · CP : Fictair EVA-2 (2024) | **remplacés** par des évaporateurs CO2 ; le Fictair de 2024 est déposé avec soin (G3, question 4) ; **vigilance** : le Fictair de 2010 est ancien | essai |
| Régulation | N : afficheur · CP : régulateur | armoire neuve ; garder l'ancien régulateur ? ; câblage à vérifier sur place | essai |
| Condenseurs | N : condenseur à air | remplacés par un gas cooler. Le condenseur du groupe positif fictif reste en secours | essai |
| Chambres | 2 chambres | **gardées** (à confirmer avec Loïc) | essai |
| Tuyauterie | non relevée | remplacée, cuivre K65 | essai |

- la chambre négative fictive est accolée à la positive ; lesquels garder parmi les régulateurs ?
- point général sans poste

## F. Fournitures annexes
"""
POSTES_BLOC_E = [
    {"id": "poste-n", "nom": "Centrale négative fictive",
     "dessert": {"texte": "chambre négative fictive, congélation", "source": "essai", "statut": S}},
    {"id": "poste-p", "nom": "Groupe positif fictif",
     "dessert": {"texte": "chambre positive fictive, stockage", "source": "essai", "statut": S}},
]


class TestBlocE(unittest.TestCase):
    """Bloc E découpé par poste ; questions internes exclues du livrable et listées pour Claude."""

    @classmethod
    def setUpClass(cls):
        cls.par, cls.exclus = assembler._bloc_e(BLOC_E_FICTIF, POSTES_BLOC_E)

    def test_propositions_rattachees_au_bon_poste(self):
        self.assertEqual(self.par["poste-n"], [
            "Évaporateurs : remplacés par des évaporateurs CO2",
            "Régulation : armoire neuve",
            "Condenseurs : remplacés par un gas cooler.",
            "Vigilance : la chambre négative fictive est accolée à la positive"])          # citée par sa chambre
        self.assertEqual(self.par["poste-p"], [
            "Évaporateurs : remplacés par des évaporateurs CO2 ; le Fictair de 2024 est déposé avec soin",
            # « 2024 » n'est que dans l'existant du poste P ; (G3…) retiré
            "Régulation : armoire neuve",                      # code CP rattaché au poste par le nom de sa chambre
            "Condenseurs : Le condenseur du groupe positif fictif reste en secours"])      # cité par son nom

    def test_ligne_sans_poste_omise(self):
        tout = " ".join(self.par["poste-n"] + self.par["poste-p"] + [x["texte"] for x in self.exclus])
        self.assertNotIn("K65", tout)
        self.assertNotIn("point général", tout)

    def test_questions_internes_exclues_et_listees(self):
        self.assertEqual([(x["element"], x["postes"], x["texte"], x["raison"]) for x in self.exclus], [
            ("Évaporateurs", ["poste-n"], "vigilance : le Fictair de 2010 est ancien", "« vigilance »"),
            ("Régulation", ["poste-n", "poste-p"], "garder l'ancien régulateur ?", "« ? »"),
            ("Régulation", ["poste-n", "poste-p"], "câblage à vérifier sur place", "« à vérifier »"),
            ("Chambres", [], "gardées (à confirmer avec Loïc)", "« à confirmer »"),
            ("Vigilance", [], "lesquels garder parmi les régulateurs ?", "« lesquels garder »")])
        livrable = " ".join(self.par["poste-n"] + self.par["poste-p"])
        for marque in ("?", "à confirmer", "à vérifier", "lesquels", "vigilance"):
            self.assertNotIn(marque, livrable)


class TestQuantitesEtPhotos(unittest.TestCase):
    """Quantités du bloc F reprises telles quelles ; légendes des vues du tableau D, une par photo."""

    @staticmethod
    def contexte(bloc_f: str) -> "assembler.Contexte":
        return assembler.Contexte(champs={"regulateurs_negatif": "1 régulateur pour la chambre négative",
                                          "regulateurs_positif": ""},
                                  corpus=assembler._norm(bloc_f), corpus_present=True, tutoiement=False,
                                  categories={"negatif"}, bloc_f=assembler._norm(bloc_f))

    def test_quantites_du_bloc_f(self):
        gab = assembler.Gabarit(assembler.TEMPLATES / "textes-grossiste.md")
        avec = self.contexte("- **Armoire de régulation Danfoss** ; **cordons chauffants** sur les 3 portes ; "
                             "**deux soupapes de décompression** dans l'armoire ; dégivrage électrique")
        self.assertEqual(avec.quantite("porte"), "3")
        self.assertEqual(avec.quantite("soupape"), "deux")
        negatif = next(s for s in gab.point("demande.c", avec)["sous_points"] if s.startswith("Partie négative"))
        self.assertIn("gestion des 3 portes avec cordon chauffant", negatif)
        self.assertIn("deux soupapes de décompression à intégrer dans l'armoire", negatif)
        sans = self.contexte("- **Armoire de régulation Danfoss** ; cordons chauffants de portes ; soupapes de "
                             "décompression dans l'armoire")
        self.assertEqual(sans.quantite("porte"), "")
        negatif = next(s for s in gab.point("demande.c", sans)["sous_points"] if s.startswith("Partie négative"))
        self.assertIn("gestion des portes avec cordon chauffant", negatif)                 # rien d'inventé
        self.assertIn("; soupapes de décompression à intégrer dans l'armoire", negatif)

    def test_segments_par_photo(self):
        lu = ("Armoire 4 portes ; étiquette « 400 V » ; disjoncteur général ; « Rés. porte »")
        self.assertEqual(assembler.segments_par_photo(lu, ["p01-1", "p01-2"]),
                         [("p01-1", "Armoire 4 portes"), ("p01-2", "disjoncteur général")])
        self.assertEqual(assembler.segments_par_photo("Armoire avec afficheur ; à l'intérieur : régulateur",
                                                      ["p02-1", "p02-2", "p02-3"]),
                         [("p02-1", "Armoire avec afficheur"), ("p02-2", "Armoire avec afficheur"),
                          ("p02-3", "à l'intérieur : régulateur")])
        self.assertEqual(assembler.segments_par_photo("Régulateurs ; départs « V1, V2 » ; « pompe »", ["a", "b", "c"]),
                         [("a", "Régulateurs"), ("b", "Régulateurs"), ("c", "Régulateurs")])



if __name__ == "__main__":
    unittest.main()
