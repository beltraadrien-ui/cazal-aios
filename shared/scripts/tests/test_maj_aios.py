"""Tests de maj_aios.py (mise à jour autonome de l'AIOS avec sauvegarde) sur des dépôts git jetables.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python -m unittest discover -s shared/scripts/tests -p "test_*.py" -v

Chaque test fabrique dans un dossier temporaire un dépôt nu « github.git », un clone « adrien » qui pousse
les mises à jour et un clone « loic » sur lequel tourne le script (--racine). La configuration git de la
machine est ignorée (GIT_CONFIG_NOSYSTEM, GIT_CONFIG_GLOBAL vers un fichier vide) pour que les tests
donnent le même résultat partout.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "maj_aios.py"
GITIGNORE = "active/\nperso/*\n!perso/README.md\n"


def _supprimer(fonction, chemin, _exc):
    os.chmod(chemin, stat.S_IWRITE)  # les objets git sont en lecture seule sous Windows
    fonction(chemin)


class BaseMaj(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._cfg = Path(tempfile.mkdtemp(prefix="maj-aios-cfg-"))
        vide = cls._cfg / "gitconfig-vide"
        vide.write_text("", encoding="utf-8")
        cls.env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(vide), PYTHONUTF8="1",
                       GIT_TERMINAL_PROMPT="0")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._cfg, onexc=_supprimer)

    # ---------- outils ----------
    def git(self, depot: Path, *args: str) -> str:
        r = subprocess.run(["git", "-C", str(depot), *args], capture_output=True, env=self.env)
        if r.returncode:
            self.fail(f"git {' '.join(args)} : {r.stderr.decode('utf-8', 'replace')}")
        return r.stdout.decode("utf-8")

    def ecrire(self, depot: Path, chemin: str, contenu: str | bytes) -> Path:
        p = depot / chemin
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(contenu if isinstance(contenu, bytes) else contenu.encode("utf-8"))
        return p

    def lire(self, depot: Path, chemin: str) -> bytes:
        return (depot / chemin).read_bytes()

    def configurer(self, depot: Path, nom: str) -> None:
        self.git(depot, "config", "user.name", nom)
        self.git(depot, "config", "user.email", f"{nom.lower()}@exemple.test")
        self.git(depot, "config", "core.autocrlf", "false")

    def pousser(self, message: str) -> None:
        self.git(self.adrien, "add", "-A")
        self.git(self.adrien, "commit", "-q", "-m", message)
        self.git(self.adrien, "push", "-q", "origin", "main")

    def lancer(self, *args: str, racine: Path | None = None, json_: bool = True) -> tuple[int, dict | str]:
        cmd = [sys.executable, str(SCRIPT), "--racine", str(racine or self.loic), *args]
        if json_:
            cmd.append("--json")
        r = subprocess.run(cmd, capture_output=True, env=self.env)
        sortie = r.stdout.decode("utf-8")
        if not json_:
            return r.returncode, sortie
        try:
            return r.returncode, json.loads(sortie)
        except json.JSONDecodeError:
            self.fail(f"Sortie non JSON :\n{sortie}\n{r.stderr.decode('utf-8', 'replace')}")

    def sauvegardes(self) -> list[Path]:
        base = self.loic / "active" / "sauvegarde-maj"
        return sorted(base.iterdir()) if base.exists() else []

    def head(self, depot: Path) -> str:
        return self.git(depot, "rev-parse", "HEAD").strip()

    # ---------- dépôts de test ----------
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="maj-aios-"))
        self.github = self.tmp / "github.git"
        self.adrien = self.tmp / "adrien"
        self.loic = self.tmp / "loic"
        self.git(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.github))
        self.git(self.tmp, "init", "-q", "-b", "main", str(self.adrien))
        self.configurer(self.adrien, "Adrien")
        self.git(self.adrien, "remote", "add", "origin", str(self.github))
        self.ecrire(self.adrien, ".gitignore", GITIGNORE)
        self.ecrire(self.adrien, "CLAUDE.md", "routeur v1\n")
        self.ecrire(self.adrien, "references/voice.md", "voix v1\n")
        self.ecrire(self.adrien, "requirements.txt", "supabase\n")
        self.ecrire(self.adrien, "skills-mobiles/idee-contenu.zip", b"PK\x03\x04\x00zip v1")
        self.pousser("version initiale")
        self.git(self.tmp, "clone", "-q", str(self.github), str(self.loic))
        self.configurer(self.loic, "Loic")

    def tearDown(self):
        shutil.rmtree(self.tmp, onexc=_supprimer)


class TestMajAios(BaseMaj):
    def test_deja_a_jour_sans_rien(self):
        code, r = self.lancer()
        self.assertEqual(code, 0)
        self.assertEqual(r["statut"], "a_jour")
        self.assertEqual((r["fichiers_mis_a_jour"], r["mis_de_cote"], r["deplaces"]), ([], [], []))
        self.assertIsNone(r["dossier_sauvegarde"])
        self.assertEqual(self.sauvegardes(), [])
        self.assertEqual(r["actions"], [])

    def test_mise_a_jour_simple(self):
        self.ecrire(self.adrien, "CLAUDE.md", "routeur v2\n")
        self.ecrire(self.adrien, "references/nouveau.md", "nouveau\n")
        self.pousser("v2")
        code, r = self.lancer()
        self.assertEqual(code, 0, r["erreurs"])
        self.assertEqual(r["statut"], "mis_a_jour")
        self.assertEqual(self.head(self.loic), self.head(self.adrien))
        self.assertEqual(self.lire(self.loic, "CLAUDE.md"), b"routeur v2\n")
        self.assertEqual(self.lire(self.loic, "references/nouveau.md"), b"nouveau\n")
        self.assertEqual(sorted((e["chemin"], e["etat"]) for e in r["fichiers_mis_a_jour"]),
                         [("CLAUDE.md", "modifié"), ("references/nouveau.md", "ajouté")])
        self.assertFalse(r["requirements_change"])
        self.assertEqual(r["zips_a_recharger"], [])
        self.assertEqual(self.sauvegardes(), [])

    def test_fichier_suivi_modifie_mis_de_cote(self):
        version_loic = "routeur v1\r\nnote ajoutée par l'assistant de Loïc : annuaire\r\n".encode("utf-8")
        self.ecrire(self.loic, "CLAUDE.md", version_loic)
        self.ecrire(self.adrien, "CLAUDE.md", "routeur v2\n")
        self.pousser("v2")
        code, r = self.lancer()
        self.assertEqual(code, 0, r["erreurs"])
        self.assertEqual(self.lire(self.loic, "CLAUDE.md"), b"routeur v2\n")
        self.assertEqual(self.head(self.loic), self.head(self.adrien))
        [dossier] = self.sauvegardes()
        self.assertEqual((dossier / "CLAUDE.md").read_bytes(), version_loic)
        self.assertEqual(r["mis_de_cote"], [{"chemin": "CLAUDE.md", "etat": "modifié",
                                             "copie": f"active/sauvegarde-maj/{dossier.name}/CLAUDE.md"}])
        self.assertEqual(r["dossier_sauvegarde"], f"active/sauvegarde-maj/{dossier.name}/")
        lisezmoi = (dossier / "LISEZMOI.md").read_text(encoding="utf-8")
        self.assertIn("`CLAUDE.md`", lisezmoi)
        self.assertIn("Rien n'est perdu", lisezmoi)
        self.assertEqual(self.git(self.loic, "status", "--porcelain"), "")

    def test_fichier_modifie_meme_si_deja_a_jour(self):
        self.ecrire(self.loic, "references/voice.md", "voix réécrite\n")
        code, r = self.lancer()
        self.assertEqual(code, 0)
        self.assertEqual(r["statut"], "a_jour")
        self.assertEqual(self.lire(self.loic, "references/voice.md"), b"voix v1\n")
        [dossier] = self.sauvegardes()
        self.assertEqual((dossier / "references" / "voice.md").read_bytes(), "voix réécrite\n".encode("utf-8"))

    def test_fichier_suivi_supprime_restaure(self):
        (self.loic / "references" / "voice.md").unlink()
        self.ecrire(self.adrien, "references/voice.md", "voix v2\n")
        self.pousser("v2")
        code, r = self.lancer()
        self.assertEqual(code, 0, r["erreurs"])
        self.assertEqual(self.lire(self.loic, "references/voice.md"), b"voix v2\n")
        self.assertEqual(r["mis_de_cote"], [{"chemin": "references/voice.md", "etat": "supprimé", "copie": None}])
        [dossier] = self.sauvegardes()
        self.assertIn("supprimé sur ce PC", (dossier / "LISEZMOI.md").read_text(encoding="utf-8"))

    def test_suppression_dans_l_index_restauree(self):
        self.git(self.loic, "rm", "-q", "references/voice.md")
        code, r = self.lancer()
        self.assertEqual(code, 0, r["erreurs"])
        self.assertEqual(self.lire(self.loic, "references/voice.md"), b"voix v1\n")
        self.assertEqual(self.git(self.loic, "status", "--porcelain"), "")

    def test_fichiers_non_suivis_conserves(self):
        perso = {
            "annuaire-sous-traitants.md": "Plombier : à compléter\n",
            "mails/demande de prix é.md": "Bonjour,\n",
            "perso/notes.md": "mes notes\n",
        }
        for chemin, contenu in perso.items():
            self.ecrire(self.loic, chemin, contenu)
        self.ecrire(self.adrien, "references/nouveau.md", "nouveau\n")
        self.pousser("v2")
        code, r = self.lancer()
        self.assertEqual(code, 0, r["erreurs"])
        for chemin, contenu in perso.items():
            self.assertEqual(self.lire(self.loic, chemin), contenu.encode("utf-8"), chemin)
        self.assertEqual(r["fichiers_perso"], sorted(perso))
        self.assertEqual(r["mis_de_cote"], [])
        self.assertEqual(self.sauvegardes(), [])

    def test_non_suivi_en_conflit_deplace(self):
        self.ecrire(self.loic, "perso/README.md", "à moi\n")
        self.ecrire(self.loic, "annuaire.md", "garde-moi\n")
        self.ecrire(self.adrien, "perso/README.md", "officiel\n")
        self.pousser("zone perso")
        code, r = self.lancer()
        self.assertEqual(code, 0, r["erreurs"])
        self.assertEqual(self.lire(self.loic, "perso/README.md"), b"officiel\n")
        self.assertEqual(self.head(self.loic), self.head(self.adrien))
        [dossier] = self.sauvegardes()
        self.assertEqual((dossier / "perso" / "README.md").read_bytes(), "à moi\n".encode("utf-8"))
        self.assertEqual(r["deplaces"], [{"chemin": "perso/README.md",
                                          "copie": f"active/sauvegarde-maj/{dossier.name}/perso/README.md"}])
        self.assertEqual(self.lire(self.loic, "annuaire.md"), b"garde-moi\n")
        self.assertEqual(r["fichiers_perso"], ["annuaire.md"])
        self.assertIn("Fichiers perso déplacés", (dossier / "LISEZMOI.md").read_text(encoding="utf-8"))

    def test_fichier_ajoute_a_l_index_retire_mais_garde(self):
        self.ecrire(self.loic, "brouillon.md", "brouillon\n")
        self.git(self.loic, "add", "brouillon.md")
        self.ecrire(self.adrien, "references/nouveau.md", "nouveau\n")
        self.pousser("v2")
        code, r = self.lancer()
        self.assertEqual(code, 0, r["erreurs"])
        self.assertEqual(self.git(self.loic, "ls-files", "brouillon.md"), "")
        self.assertEqual(self.lire(self.loic, "brouillon.md"), b"brouillon\n")
        self.assertEqual(r["retires_de_l_index"], ["brouillon.md"])
        self.assertIn("brouillon.md", r["fichiers_perso"])
        self.assertEqual(self.git(self.loic, "status", "--porcelain"), "?? brouillon.md\n")

    def test_renommage_dans_l_index(self):
        self.git(self.loic, "mv", "references/voice.md", "references/voix.md")
        code, r = self.lancer()
        self.assertEqual(code, 0, r["erreurs"])
        self.assertEqual(self.lire(self.loic, "references/voice.md"), b"voix v1\n")
        self.assertEqual(self.lire(self.loic, "references/voix.md"), b"voix v1\n")
        self.assertEqual(r["retires_de_l_index"], ["references/voix.md"])
        self.assertEqual(r["mis_de_cote"], [{"chemin": "references/voice.md", "etat": "supprimé", "copie": None}])
        self.assertEqual(self.git(self.loic, "status", "--porcelain"), "?? references/voix.md\n")

    def test_commit_local_code_3_rien_modifie(self):
        self.ecrire(self.adrien, "CLAUDE.md", "routeur v2\n")
        self.pousser("v2")
        self.ecrire(self.loic, "references/voice.md", "voix commitée chez Loïc\n")
        self.git(self.loic, "commit", "-q", "-am", "commit local")
        self.ecrire(self.loic, "CLAUDE.md", "modif en cours\n")
        avant = self.head(self.loic)
        code, r = self.lancer()
        self.assertEqual(code, 3)
        self.assertEqual(r["statut"], "arret")
        self.assertIn("Adrien", r["message"])
        self.assertEqual(self.head(self.loic), avant)
        self.assertEqual(self.lire(self.loic, "CLAUDE.md"), b"modif en cours\n")
        self.assertEqual(self.sauvegardes(), [])

    def test_commit_local_sans_rien_a_tirer_code_3(self):
        self.ecrire(self.loic, "references/voice.md", "voix commitée chez Loïc\n")
        self.git(self.loic, "commit", "-q", "-am", "commit local")
        code, r = self.lancer()
        self.assertEqual(code, 3)

    def test_pas_d_origin_code_2(self):
        self.git(self.loic, "remote", "remove", "origin")
        self.ecrire(self.loic, "CLAUDE.md", "modif\n")
        code, r = self.lancer()
        self.assertEqual(code, 2)
        self.assertEqual(r["statut"], "arret")
        self.assertIn("origin", r["message"])
        self.assertEqual(self.lire(self.loic, "CLAUDE.md"), b"modif\n")

    def test_pas_un_depot_git_code_2(self):
        vide = self.tmp / "pas-un-depot"
        vide.mkdir()
        code, r = self.lancer(racine=vide)
        self.assertEqual(code, 2)

    def test_requirements_et_zips_detectes(self):
        self.ecrire(self.adrien, "requirements.txt", "supabase\nopenai\n")
        self.ecrire(self.adrien, "skills-mobiles/idee-contenu.zip", b"PK\x03\x04\x00zip v2")
        self.ecrire(self.adrien, "skills-mobiles/froid-question.zip", b"PK\x03\x04\x00zip neuf")
        self.ecrire(self.adrien, "skills-mobiles/README.md", "mode d'emploi\n")
        self.pousser("zips")
        code, r = self.lancer()
        self.assertEqual(code, 0, r["erreurs"])
        self.assertTrue(r["requirements_change"])
        self.assertEqual(sorted(r["zips_a_recharger"]),
                         ["skills-mobiles/froid-question.zip", "skills-mobiles/idee-contenu.zip"])
        self.assertTrue(any("pip install -r requirements.txt" in a for a in r["actions"]))
        self.assertEqual(sum("skills-mobiles/" in a and ".zip" in a for a in r["actions"]), 2)

    def test_zip_supprime_pas_a_recharger(self):
        (self.adrien / "skills-mobiles" / "idee-contenu.zip").unlink()
        self.pousser("zip retiré")
        code, r = self.lancer()
        self.assertEqual(code, 0, r["erreurs"])
        self.assertEqual(r["zips_a_recharger"], [])

    def test_simuler_ne_change_rien(self):
        self.ecrire(self.loic, "CLAUDE.md", "modif de Loïc\n")
        self.ecrire(self.loic, "perso/README.md", "à moi\n")
        self.ecrire(self.loic, "brouillon.md", "brouillon\n")
        self.git(self.loic, "add", "brouillon.md")
        self.ecrire(self.adrien, "CLAUDE.md", "routeur v2\n")
        self.ecrire(self.adrien, "perso/README.md", "officiel\n")
        self.ecrire(self.adrien, "requirements.txt", "supabase\nopenai\n")
        self.pousser("v2")

        def etat():
            return (self.head(self.loic), self.git(self.loic, "ls-files", "-s"),
                    self.git(self.loic, "status", "--porcelain", "--untracked-files=all"),
                    self.lire(self.loic, "CLAUDE.md"), self.lire(self.loic, "perso/README.md"),
                    self.lire(self.loic, "brouillon.md"))

        avant = etat()
        code, r = self.lancer("--simuler")
        self.assertEqual(code, 0, r["erreurs"])
        self.assertEqual(etat(), avant)
        self.assertEqual(self.sauvegardes(), [])
        self.assertTrue(r["simulation"])
        self.assertEqual([e["chemin"] for e in r["mis_de_cote"]], ["CLAUDE.md"])
        self.assertEqual([e["chemin"] for e in r["deplaces"]], ["perso/README.md"])
        self.assertEqual(r["retires_de_l_index"], ["brouillon.md"])
        self.assertTrue(r["requirements_change"])
        prevus = sorted(e["chemin"] for e in r["fichiers_mis_a_jour"])

        code, reel = self.lancer()
        self.assertEqual(code, 0, reel["erreurs"])
        self.assertFalse(reel["simulation"])
        self.assertEqual(sorted(e["chemin"] for e in reel["fichiers_mis_a_jour"]), prevus)
        self.assertEqual([e["chemin"] for e in reel["deplaces"]], ["perso/README.md"])
        self.assertEqual(self.lire(self.loic, "CLAUDE.md"), b"routeur v2\n")

    def test_rapport_texte_lisible(self):
        self.ecrire(self.loic, "CLAUDE.md", "modif de Loïc\n")
        self.ecrire(self.loic, "annuaire.md", "à moi\n")
        self.ecrire(self.adrien, "requirements.txt", "supabase\nopenai\n")
        self.ecrire(self.adrien, "skills-mobiles/idee-contenu.zip", b"PK\x03\x04\x00zip v2")
        self.pousser("v2")
        code, texte = self.lancer(json_=False)
        self.assertEqual(code, 0, texte)
        for attendu in ("Mise à jour de l'AIOS", "Mise à jour faite : 2 fichiers mis à jour.",
                        "Fichiers du système mis de côté (1)", "active/sauvegarde-maj/",
                        "Fichiers perso, jamais touchés : 1", "annuaire.md",
                        "pip install -r requirements.txt", "skills-mobiles/idee-contenu.zip"):
            self.assertIn(attendu, texte)

    def test_rapport_texte_arret(self):
        self.git(self.loic, "remote", "remove", "origin")
        code, texte = self.lancer(json_=False)
        self.assertEqual(code, 2)
        self.assertIn("NON faite", texte)
        self.assertIn("Préviens Adrien", texte)

    def test_json_complet(self):
        code, r = self.lancer()
        self.assertEqual(code, 0)
        for cle in ("simulation", "code", "statut", "message", "racine", "branche", "version_avant",
                    "version_apres", "fichiers_mis_a_jour", "dossier_sauvegarde", "mis_de_cote", "deplaces",
                    "retires_de_l_index", "fichiers_perso", "requirements_change", "zips_a_recharger",
                    "actions", "erreurs"):
            self.assertIn(cle, r)
        self.assertEqual(r["branche"], "main")


if __name__ == "__main__":
    unittest.main()
