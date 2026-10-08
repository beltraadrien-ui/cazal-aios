---
name: maj-aios
description: Met à jour l'AIOS de Loïc avec les dernières modifications d'Adrien depuis le repo GitHub, toute seule et sans rien perdre (script shared/scripts/maj_aios.py : met de côté les fichiers du système modifiés sur ce PC, tire la mise à jour, dit quels zips recharger sur claude.ai). Skill MOTEUR, tourne dans Claude Code sur le PC (engine), PAS sur mobile. Se déclenche sur "mets à jour mon AIOS", "maj", "récupère les dernières modifs", "mets à jour le système".
---

# Mettre à jour l'AIOS — Cazal Réfrigération (MOTEUR)

## Ce que fait cette skill

Récupère les améliorations d'Adrien depuis le **repo GitHub** privé (`cazal-aios`) et les applique au PC
de Loïc. Tout le travail est fait par un script, `shared/scripts/maj_aios.py` ; ton rôle : le lancer,
relayer son rapport en mots simples, puis faire les deux actions de suivi (dépendances, zips).

Le script :
- met de côté les **fichiers du système** (tout ce que git suit) modifiés ou supprimés sur ce PC : copie
  dans `active/sauvegarde-maj/<date-heure>/` (avec un `LISEZMOI.md` qui explique), puis fichier remis
  d'origine. Il le fait à chaque lancement : après la mise à jour, le système est exactement celui d'Adrien ;
- ne touche **jamais** aux fichiers perso de Loïc (`perso/`, ses notes, annuaires, mails, tout fichier non
  suivi). Seule exception : un fichier perso qui porte exactement le nom d'un fichier qui arrive est
  **déplacé** dans la sauvegarde, jamais effacé ;
- tire la mise à jour en avance rapide stricte (`git pull --ff-only`) ;
- dit si `requirements.txt` a changé et quels zips de `skills-mobiles/` sont à recharger sur claude.ai.

> ⚙️ **Skill engine** : s'exécute dans Claude Code sur le PC de Loïc (accès au repo git local).
> **Pas sur mobile** : claude.ai ne synchronise pas les skills depuis GitHub, d'où les zips à recharger.

## Étapes

1. **Lancer le script** depuis la racine du projet (un seul appel, aucune commande git à la main avant) :
   ```bash
   PYTHONUTF8=1 python shared/scripts/maj_aios.py
   ```
   `--simuler` montre ce qui serait fait sans rien toucher ; `--json` donne le même rapport en JSON.

2. **Relayer le rapport à Loïc en quelques lignes simples**, sans jargon git :
   - ce qui a été mis à jour (« déjà à jour » ou « N fichiers mis à jour ») ;
   - ce qui a été mis de côté et où (`active/sauvegarde-maj/<date-heure>/`), en rassurant : rien n'est
     perdu. Si une copie contient une information qu'il veut garder, proposer de la recopier dans `perso/`
     (jamais dans le fichier du système) ;
   - ses fichiers perso : intacts (donner le nombre).

3. **Si `requirements.txt` a changé** (le rapport le dit dans « À faire maintenant ») : lancer
   `pip install -r requirements.txt` et dire à Loïc que c'est fait (ou relayer l'erreur telle quelle).

4. **Si des zips ont changé** (`skills-mobiles/<skill>.zip` dans « À faire maintenant ») : guider Loïc pas
   à pas, un zip à la fois, de préférence depuis son ordinateur :
   1. ouvrir claude.ai (ou l'application Claude) ▸ **Personnaliser ▸ Compétences** ;
   2. **Téléverser** le fichier `skills-mobiles/<skill>.zip` (dans le dossier de l'AIOS sur son PC) ;
   3. **Remplacer** l'ancienne version du même nom.

   Les intitulés exacts peuvent varier selon la version de l'application : chercher l'équivalent. Attendre
   que Loïc confirme avant de passer au zip suivant. Mode d'emploi complet : `skills-mobiles/README.md`.

5. **En cas d'arrêt**, relayer le message du script **tel quel**, sans tâtonner :
   - code **2** (pas relié à GitHub) ou **3** (commit local, historique divergent) : dire à Loïc de
     prévenir Adrien. Rien n'a été modifié ;
   - code **1** (réseau, erreur git) : si c'est la connexion, relancer plus tard ; sinon prévenir Adrien.

   Jamais de commande git à la main pour « réparer ».

## Règles fermes

- **Lecture seule côté Loïc** : jamais `commit`, `push`, `merge`, `reset --hard`, `clean`, `stash`, ni
  `pull` sans `--ff-only`. Le clone de Loïc est un **consommateur** ; la source de vérité est le repo
  d'Adrien. Le script ne fait que des copies de sauvegarde, `checkout HEAD -- <fichier>`,
  `reset -q -- <fichier>` (retirer de l'index) et `pull --ff-only`.
- **Secrets et sorties intouchés** : `.env` et `active/` sont ignorés par git, un pull ne les touche
  jamais. Les sauvegardes s'ajoutent dans `active/sauvegarde-maj/` et ne sont jamais effacées.
- **Zone perso** : `perso/` n'est jamais touché (ni envoyé sur GitHub, ni modifié par la mise à jour).
- **Rapporter fidèlement** : ne jamais inventer un résultat, ne jamais dire « à jour » si le script a
  échoué.
