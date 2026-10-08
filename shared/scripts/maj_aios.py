"""Met à jour l'AIOS de Loïc depuis GitHub, toute seule, sans rien perdre.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python shared/scripts/maj_aios.py             # mise à jour réelle
    PYTHONUTF8=1 python shared/scripts/maj_aios.py --simuler   # dit ce qui serait fait, ne touche à rien
    PYTHONUTF8=1 python shared/scripts/maj_aios.py --json      # le même rapport, en JSON
    --racine <chemin> : le dépôt à mettre à jour (par défaut, celui qui contient ce script)

Déroulé :
 1. Vérifie que le dossier est une copie git reliée à GitHub (remote origin), sinon code 2.
 2. Télécharge l'état de GitHub (git fetch : ne change ni les fichiers ni la branche de Loïc).
    Commit local ou historique divergent : arrêt, code 3, rien n'est modifié.
 3. Fichiers du système (suivis par git) modifiés, supprimés ou renommés sur ce PC : copie de leur
    contenu dans active/sauvegarde-maj/<AAAA-MM-JJ-HHMM>/<même chemin>, puis remis dans l'état du
    dépôt (git checkout HEAD -- <chemin>). Fichier seulement ajouté à l'index : retiré de l'index
    (git reset -q -- <chemin>), gardé sur le disque. Un LISEZMOI.md dans la sauvegarde explique tout.
    Fait à chaque lancement, même quand GitHub n'a rien de neuf : après maj-aios, le système est
    exactement celui d'Adrien.
 4. git pull --ff-only origin <branche>. Si git refuse parce que des fichiers non suivis seraient
    écrasés par des fichiers qui arrivent, ces fichiers-là (et eux seuls) sont déplacés dans la
    sauvegarde (copie puis suppression de l'original), puis une seconde et dernière tentative.
 5. Rapport : fichiers mis à jour, fichiers mis de côté, fichiers perso intacts, dépendances Python
    à réinstaller (requirements.txt), zips de skills-mobiles/ à recharger sur claude.ai.

Les fichiers non suivis (les affaires de Loïc, dont perso/) ne sont jamais touchés, sauf le cas du
point 4 (déplacés, jamais effacés). .env et active/ sont ignorés par git : jamais touchés.
Jamais de reset --hard, merge, push, clean ni commit.

--simuler fait le fetch du point 2 (pour savoir ce qui arriverait) et n'écrit rien d'autre :
ni fichier, ni index, ni branche, ni sauvegarde.

Codes de sortie : 0 = fait (ou déjà à jour) · 1 = erreur (réseau, git) · 2 = pas une copie git
reliée à GitHub · 3 = situation à faire régler par Adrien (commit local, historique divergent…).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

SAUVEGARDE = Path("active") / "sauvegarde-maj"
DOSSIER_ZIPS = "skills-mobiles/"
DOSSIER_PERSO = "perso"
OK, ERREUR, PAS_DE_DEPOT, ADRIEN = 0, 1, 2, 3
PREVENIR = "Préviens Adrien : il réglera ça à distance. Rien n'a été forcé."
CONFLITS = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
ETATS = {"A": "ajouté", "M": "modifié", "D": "supprimé"}
MAX_LISTE = 40


class Arret(Exception):
    """Arrêt propre : un code de sortie et un message lisible par Loïc."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Rapport:
    simulation: bool = False
    code: int = OK
    statut: str = ""  # a_jour | mis_a_jour | arret (codes 2 et 3) | erreur (code 1)
    message: str = ""
    racine: str = ""
    branche: str = ""
    version_avant: str = ""
    version_apres: str = ""
    fichiers_mis_a_jour: list = field(default_factory=list)  # {"etat", "chemin"}
    dossier_sauvegarde: str | None = None
    mis_de_cote: list = field(default_factory=list)  # {"chemin", "etat", "copie"}
    deplaces: list = field(default_factory=list)  # {"chemin", "copie"}
    retires_de_l_index: list = field(default_factory=list)
    fichiers_perso: list = field(default_factory=list)
    requirements_change: bool = False
    zips_a_recharger: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    erreurs: list = field(default_factory=list)


def _env_git() -> dict:
    env = dict(os.environ)
    # Messages git en anglais (on les analyse), jamais de question posée dans le terminal.
    env.update({"LC_ALL": "C", "LANG": "C", "GIT_TERMINAL_PROMPT": "0"})
    env.pop("LANGUAGE", None)
    return env


def git(racine: Path, *args: str) -> tuple[int, str, str]:
    cmd = ["git", "-C", str(racine), "-c", "core.quotepath=false", "--literal-pathspecs", *args]
    r = subprocess.run(cmd, capture_output=True, env=_env_git())
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def _derniere_ligne(texte: str) -> str:
    lignes = [l.strip() for l in texte.splitlines() if l.strip()]
    return lignes[-1] if lignes else "(pas de message)"


def _paquets(chemins: list[str], taille: int = 50):
    for i in range(0, len(chemins), taille):
        yield chemins[i:i + taille]


def _s(n: int, mot: str) -> str:
    return f"{n} {mot if n <= 1 else mot + 's'}"


def fichiers_non_suivis_bloquants(sortie: str) -> list[str]:
    """Fichiers nommés par git sous « untracked working tree files would be overwritten (ou removed) »."""
    fichiers, dedans = [], False
    for ligne in sortie.splitlines():
        if "untracked working tree files would be" in ligne:
            dedans = True
        elif dedans and ligne.startswith("\t"):
            fichiers.append(ligne[1:].rstrip("\r"))
        else:
            dedans = False
    return fichiers


class MiseAJour:
    def __init__(self, racine_demandee: str | None, simuler: bool):
        self.racine_demandee = racine_demandee
        self.simuler = simuler
        self.racine: Path | None = None
        self.r = Rapport(simulation=simuler)
        self.horodatage = dt.datetime.now()
        self._dossier: Path | None = None

    # ---------- outils ----------
    def g(self, *args: str) -> str:
        code, out, err = git(self.racine, *args)
        if code:
            commande = next((a for a in args if not a.startswith("-")), args[0])
            raise Arret(ERREUR, f"La commande git « {commande} » a échoué : {_derniere_ligne(err or out)}. "
                                f"{PREVENIR}")
        return out

    def rel(self, p: Path) -> str:
        return p.relative_to(self.racine).as_posix()

    def dossier(self) -> Path:
        """Dossier de sauvegarde de ce lancement (créé à la première utilisation, jamais en simulation)."""
        if self._dossier is None:
            base = self.racine / SAUVEGARDE
            nom = self.horodatage.strftime("%Y-%m-%d-%H%M")
            d, n = base / nom, 2
            while d.exists():
                d, n = base / f"{nom}-{n}", n + 1
            if not self.simuler:
                d.mkdir(parents=True)
            self._dossier = d
            self.r.dossier_sauvegarde = self.rel(d) + "/"
        return self._dossier

    # ---------- déroulé ----------
    def lancer(self) -> Rapport:
        try:
            self._lancer()
        except Arret as a:
            self.r.code, self.r.message = a.code, a.message
            self.r.statut = "erreur" if a.code == ERREUR else "arret"
            self.r.erreurs.append(a.message)
        except Exception as e:  # imprévu : on le dit tel quel, sans rien tenter de plus
            self.r.code, self.r.statut = ERREUR, "erreur"
            self.r.message = f"Erreur imprévue pendant la mise à jour : {e!r}. {PREVENIR}"
            self.r.erreurs.append(self.r.message)
        finally:
            if self._dossier is not None and not self.simuler:
                try:
                    self._ecrire_lisezmoi()
                except Exception as e:
                    self.r.erreurs.append(f"LISEZMOI.md non écrit dans la sauvegarde : {e!r}")
        self._actions()
        return self.r

    def _lancer(self) -> None:
        r = self.r
        branche, avant = self._verifier()
        code, _, err = git(self.racine, "fetch", "--quiet", "origin")
        if code:
            raise Arret(ERREUR, "Impossible de récupérer la mise à jour sur GitHub (connexion internet ou accès "
                                f"au dépôt) : {_derniere_ligne(err)}. Rien n'a été modifié : vérifie la connexion "
                                "puis relance. Si ça recommence, préviens Adrien.")
        code, out, _ = git(self.racine, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{branche}")
        if code:
            raise Arret(ADRIEN, f"La branche « {branche} » n'existe pas sur GitHub : la mise à jour ne peut pas "
                                f"se faire toute seule. Rien n'a été modifié. {PREVENIR}")
        distant = out.strip()
        locaux = int(self.g("rev-list", "--count", f"{distant}..{avant}").strip())
        if locaux:
            raise Arret(ADRIEN, f"Cette copie contient {_s(locaux, 'enregistrement')} git (commit) fait sur ce PC "
                                "et absent de GitHub : l'historique a divergé, la mise à jour ne peut pas se faire "
                                f"toute seule. Rien n'a été modifié. {PREVENIR}")
        a_tirer = int(self.g("rev-list", "--count", f"{avant}..{distant}").strip())

        suivis, ajoutes, non_suivis, conflits = self._lire_statut()
        if conflits:
            raise Arret(ADRIEN, "Des fichiers sont restés en conflit git (" + ", ".join(sorted(conflits)[:5])
                                + f") : la mise à jour ne peut pas se faire toute seule. Rien n'a été modifié. "
                                  f"{PREVENIR}")

        # 3. Mettre de côté les fichiers du système changés sur ce PC, puis les remettre d'origine.
        self._mettre_de_cote(suivis)
        self._retirer_de_l_index(ajoutes)
        non_suivis = set(non_suivis) | {c for c in ajoutes if (self.racine / c).is_file()}

        # 4. Tirer.
        r.version_avant = avant[:7]
        if a_tirer == 0:
            r.statut, r.version_apres = "a_jour", avant[:7]
            r.message = "Déjà à jour : rien de nouveau sur GitHub."
        elif self.simuler:
            r.fichiers_mis_a_jour = self._diff(avant, distant)
            arrivent = {e["chemin"] for e in r.fichiers_mis_a_jour if e["etat"] == "ajouté"}
            for chemin in sorted(arrivent & non_suivis):
                r.deplaces.append({"chemin": chemin, "copie": self.rel(self.dossier() / chemin)})
            n = len(r.fichiers_mis_a_jour)
            r.statut, r.version_apres = "mis_a_jour", distant[:7]
            r.message = f"{_s(n, 'fichier')} {'serait mis' if n <= 1 else 'seraient mis'} à jour."
        else:
            self._tirer(branche)
            apres = self.g("rev-parse", "HEAD").strip()
            r.fichiers_mis_a_jour = self._diff(avant, apres)
            r.statut, r.version_apres = "mis_a_jour", apres[:7]
            r.message = f"Mise à jour faite : {_s(len(r.fichiers_mis_a_jour), 'fichier')} mis à jour."

        # 5. Ce qui reste à faire, et les affaires de Loïc (jamais touchées).
        for e in r.fichiers_mis_a_jour:
            if e["chemin"] == "requirements.txt":
                r.requirements_change = True
            if e["chemin"].startswith(DOSSIER_ZIPS) and e["chemin"].endswith(".zip") and e["etat"] != "supprimé":
                r.zips_a_recharger.append(e["chemin"])
        perso = non_suivis - {d["chemin"] for d in r.deplaces}
        code, out, _ = git(self.racine, "ls-files", "-z", "--others", "--ignored", "--exclude-standard",
                           "--", DOSSIER_PERSO)
        if code == 0:
            perso |= {c for c in out.split("\0") if c}
        r.fichiers_perso = sorted(perso)

    def _verifier(self) -> tuple[str, str]:
        depart = Path(self.racine_demandee) if self.racine_demandee else Path(__file__).resolve().parent
        if not depart.is_dir():
            raise Arret(PAS_DE_DEPOT, f"Dossier introuvable : {depart}. Rien n'a été modifié. {PREVENIR}")
        code, out, err = git(depart, "rev-parse", "--show-toplevel")
        if code:
            raise Arret(PAS_DE_DEPOT, f"Ce dossier n'est pas une copie git de l'AIOS ({_derniere_ligne(err)}). "
                                      f"Rien n'a été modifié. {PREVENIR}")
        self.racine = Path(out.strip())
        self.r.racine = str(self.racine)
        code, _, _ = git(self.racine, "remote", "get-url", "origin")
        if code:
            raise Arret(PAS_DE_DEPOT, "Cette copie de l'AIOS n'est pas reliée à GitHub (aucun remote « origin ») : "
                                      f"impossible de récupérer la mise à jour. Rien n'a été modifié. {PREVENIR}")
        code, out, _ = git(self.racine, "symbolic-ref", "-q", "--short", "HEAD")
        if code:
            raise Arret(ADRIEN, "La copie de l'AIOS n'est sur aucune branche (état git inhabituel) : la mise à jour "
                                f"ne peut pas se faire toute seule. Rien n'a été modifié. {PREVENIR}")
        branche = out.strip()
        self.r.branche = branche
        for nom in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
            if (self.racine / self.g("rev-parse", "--git-path", nom).strip()).exists():
                raise Arret(ADRIEN, "Une opération git est restée en cours (fusion ou rebase) : la mise à jour ne "
                                    f"peut pas se faire toute seule. Rien n'a été modifié. {PREVENIR}")
        code, out, _ = git(self.racine, "rev-parse", "--verify", "-q", "HEAD")
        if code:
            raise Arret(ADRIEN, f"La copie de l'AIOS n'a aucune version enregistrée. Rien n'a été modifié. {PREVENIR}")
        return branche, out.strip()

    def _lire_statut(self) -> tuple[list[str], list[str], list[str], list[str]]:
        """Classe `git status` : suivis modifiés, ajoutés à l'index, non suivis, conflits."""
        out = self.g("--no-optional-locks", "status", "--porcelain=v1", "-z", "--untracked-files=all")
        champs = out.split("\0")
        suivis, ajoutes, non_suivis, conflits = [], [], [], []
        i = 0
        while i < len(champs):
            entree = champs[i]
            i += 1
            if len(entree) < 4:
                continue
            xy, chemin = entree[:2], entree[3:]
            origine = None
            if xy[0] in "RC":  # avec -z : « XY nouveau\0ancien\0 »
                origine = champs[i]
                i += 1
            if xy == "??":
                non_suivis.append(chemin)
            elif xy == "!!":
                continue
            elif xy in CONFLITS:
                conflits.append(chemin)
            elif xy[0] in "RC":
                ajoutes.append(chemin)  # le nouveau nom n'existe que dans l'index
                if xy[0] == "R":
                    suivis.append(origine)  # l'ancien nom est un fichier du système à remettre
            elif "A" in xy:
                ajoutes.append(chemin)
            else:
                suivis.append(chemin)
        return suivis, ajoutes, non_suivis, conflits

    def _mettre_de_cote(self, suivis: list[str]) -> None:
        chemins = sorted(set(suivis))
        for chemin in chemins:
            src = self.racine / chemin
            dest = self.dossier() / chemin
            if src.is_file():
                self.r.mis_de_cote.append({"chemin": chemin, "etat": "modifié", "copie": self.rel(dest)})
                if not self.simuler:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
            else:
                self.r.mis_de_cote.append({"chemin": chemin, "etat": "supprimé", "copie": None})
        if chemins and not self.simuler:
            for lot in _paquets(chemins):  # toutes les copies sont faites avant de remettre quoi que ce soit
                self.g("checkout", "HEAD", "--", *lot)

    def _retirer_de_l_index(self, ajoutes: list[str]) -> None:
        chemins = sorted(set(ajoutes))
        self.r.retires_de_l_index = chemins
        if chemins and not self.simuler:
            for lot in _paquets(chemins):
                self.g("reset", "-q", "--", *lot)

    def _tirer(self, branche: str) -> None:
        commande = ("pull", "--ff-only", "--no-rebase", "origin", branche)
        code, out, err = git(self.racine, *commande)
        if code:
            bloquants = fichiers_non_suivis_bloquants(out + "\n" + err)
            if bloquants:
                self._deplacer(bloquants)
                code, out, err = git(self.racine, *commande)
        if code:
            texte = out + "\n" + err
            if "fast-forward" in texte or "diverg" in texte:
                raise Arret(ADRIEN, "La mise à jour n'est pas une simple avance (l'historique a divergé) : elle ne "
                                    f"peut pas se faire toute seule. {PREVENIR}")
            raise Arret(ERREUR, f"La mise à jour a échoué : {_derniere_ligne(texte)}. {PREVENIR}")

    def _deplacer(self, chemins: list[str]) -> None:
        for chemin in chemins:
            src = self.racine / chemin
            if not src.is_file():
                self.r.erreurs.append(f"Fichier signalé par git mais introuvable : {chemin}")
                continue
            dest = self.dossier() / chemin
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            src.unlink()
            self.r.deplaces.append({"chemin": chemin, "copie": self.rel(dest)})

    def _diff(self, a: str, b: str) -> list[dict]:
        champs = self.g("diff-tree", "-r", "--name-status", "--no-renames", "-z", a, b).split("\0")
        res = []
        for i in range(0, len(champs) - 1, 2):
            if champs[i]:
                res.append({"etat": ETATS.get(champs[i][0], "modifié"), "chemin": champs[i + 1]})
        return res

    def _ecrire_lisezmoi(self) -> None:
        r, d = self.r, self._dossier
        quand = self.horodatage.strftime("%Y-%m-%d à %H:%M")
        lignes = [
            f"# Mis de côté par la mise à jour de l'AIOS du {quand}", "",
            "La mise à jour (maj-aios) remet les fichiers du système exactement comme Adrien les a livrés.",
            "Les fichiers listés ici avaient été changés sur ce PC (souvent par l'assistant, à ta demande) :",
            "leur version d'avant est copiée dans ce dossier, au même chemin. Rien n'est perdu.",
            "Ce dossier reste sur ce PC : il n'est jamais envoyé sur GitHub et la mise à jour n'y touche plus.", "",
            "Une information à garder dans une de ces copies ? Demande à l'assistant de la recopier dans `perso/`",
            "(jamais dans un fichier du système). Un changement à faire dans le système ? Note-le dans",
            "`perso/demandes-a-adrien.md`, Adrien l'intègre.", "",
        ]
        if r.mis_de_cote:
            lignes += ["## Fichiers du système remis d'origine", ""]
            for e in r.mis_de_cote:
                if e["copie"]:
                    lignes.append(f"- `{e['chemin']}` : modifié sur ce PC. Ta version est copiée ici : `{e['copie']}`")
                else:
                    lignes.append(f"- `{e['chemin']}` : supprimé sur ce PC, remis en place (rien à copier).")
            lignes.append("")
        if r.deplaces:
            lignes += ["## Fichiers perso déplacés", "",
                       "La mise à jour apportait un fichier du système au même endroit : ton fichier a été déplacé "
                       "ici, pas effacé.", ""]
            lignes += [f"- `{e['chemin']}` déplacé vers `{e['copie']}`" for e in r.deplaces]
            lignes.append("")
        occupes = {e["chemin"] for e in r.mis_de_cote + r.deplaces}
        nom = "LISEZMOI.md" if "LISEZMOI.md" not in occupes else "LISEZMOI-sauvegarde.md"
        (d / nom).write_text("\n".join(lignes), encoding="utf-8")

    def _actions(self) -> None:
        r = self.r
        if r.requirements_change:
            r.actions.append("Réinstaller les dépendances Python : pip install -r requirements.txt")
        for z in r.zips_a_recharger:
            r.actions.append(f"Recharger {z} sur claude.ai (mode d'emploi : skills-mobiles/README.md)")
        if r.mis_de_cote or r.deplaces:
            r.actions.append(f"Regarder avec Loïc si une copie mise de côté ({r.dossier_sauvegarde}) contient une "
                             "information à garder : la recopier dans perso/, jamais dans un fichier du système.")


def _liste(lignes: list[str], elements: list[str]) -> None:
    for e in elements[:MAX_LISTE]:
        lignes.append(f"  - {e}")
    if len(elements) > MAX_LISTE:
        lignes.append(f"  - … et {len(elements) - MAX_LISTE} autres (liste complète avec --json)")


def en_texte(r: Rapport) -> str:
    sim = r.simulation
    titre = "Mise à jour de l'AIOS" + (" : SIMULATION, rien n'a été modifié" if sim else "")
    l = [titre, "=" * len(titre)]
    l.append(r.message if r.code == OK else f"Mise à jour NON faite (code {r.code}).")
    if r.version_avant and r.version_apres and r.version_avant != r.version_apres:
        l.append(f"Version : {r.version_avant} -> {r.version_apres} (branche {r.branche})")
    if r.fichiers_mis_a_jour:
        l += ["", f"Fichiers {'qui seraient mis' if sim else 'mis'} à jour ({len(r.fichiers_mis_a_jour)}) :"]
        _liste(l, [f"{e['chemin']} ({e['etat']})" for e in r.fichiers_mis_a_jour])
    if r.mis_de_cote:
        l += ["", f"Fichiers du système {'qui seraient mis' if sim else 'mis'} de côté ({len(r.mis_de_cote)}), "
                  f"copies dans {r.dossier_sauvegarde} :"]
        _liste(l, [f"{e['chemin']} (modifié sur ce PC : copie gardée, fichier remis d'origine)" if e["copie"]
                   else f"{e['chemin']} (supprimé sur ce PC : remis en place)" for e in r.mis_de_cote])
    if r.deplaces:
        l += ["", f"Fichiers perso {'qui seraient déplacés' if sim else 'déplacés'} parce que la mise à jour "
                  f"apporte un fichier au même endroit ({len(r.deplaces)}) :"]
        _liste(l, [f"{e['chemin']} -> {e['copie']}" for e in r.deplaces])
    if r.retires_de_l_index:
        l += ["", f"Fichiers {'qui seraient retirés' if sim else 'retirés'} de l'index git, gardés sur le disque "
                  f"({len(r.retires_de_l_index)}) :"]
        _liste(l, r.retires_de_l_index)
    if r.code == OK:
        l += ["", f"Fichiers perso, jamais touchés : {len(r.fichiers_perso)}"]
        _liste(l, r.fichiers_perso)
        l += ["", "Ce qu'il y aurait à faire ensuite :" if sim else "À faire maintenant :"]
        if r.actions:
            _liste(l, r.actions)
        else:
            l.append("  rien d'autre.")
    if r.erreurs:
        l += ["", "Erreurs :"]
        _liste(l, r.erreurs)
    return "\n".join(l)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Met à jour l'AIOS depuis GitHub en mettant de côté les fichiers "
                                            "du système modifiés sur ce PC (rien n'est perdu).")
    p.add_argument("--racine", help="dépôt à mettre à jour (défaut : celui qui contient ce script)")
    p.add_argument("--simuler", action="store_true", help="dire ce qui serait fait, sans rien modifier")
    p.add_argument("--json", action="store_true", help="rapport en JSON")
    a = p.parse_args(argv)
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except Exception:
            pass
    rapport = MiseAJour(a.racine, a.simuler).lancer()
    print(json.dumps(asdict(rapport), ensure_ascii=False, indent=2) if a.json else en_texte(rapport))
    return rapport.code


if __name__ == "__main__":
    sys.exit(main())
