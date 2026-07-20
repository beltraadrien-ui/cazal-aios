---
name: maj-aios
description: Met à jour l'AIOS de Loïc en récupérant les dernières modifications d'Adrien depuis le repo GitHub (git pull). Skill MOTEUR, tourne dans Claude Code sur le PC (engine), PAS sur mobile. Se déclenche sur "mets à jour mon AIOS", "maj", "récupère les dernières modifs", "mets à jour le système".
---

# Mettre à jour l'AIOS — Cazal Réfrigération (MOTEUR)

## Ce que fait cette skill

Récupère les dernières modifications d'Adrien depuis le **repo GitHub** (`cazal-aios`) et les applique
au clone local de Loïc, via un `git pull`. C'est le canal de **maintenance à distance** : Adrien pousse
ses améliorations sur GitHub, Loïc lance « mets à jour mon AIOS » et les reçoit, sans ré-télécharger
le dossier par mail/Drive.

> ⚙️ **Skill engine** : s'exécute dans Claude Code sur le PC de Loïc (accès au repo git local).
> **Pas sur mobile** — claude.ai grand public ne synchronise pas les skills depuis GitHub.

## Prérequis

- Le projet est un **clone git** du repo `cazal-aios` (un `git remote -v` doit montrer `origin`).
- Connexion internet. Le `.env` local de Loïc (ses clés) **n'est pas suivi par git** → jamais écrasé.

## Étapes

1. **Vérifier le contexte git** depuis la racine du projet :
   ```bash
   git -C "<racine>" remote -v
   git -C "<racine>" status --short
   ```
   - Si pas de `origin` → s'arrêter et le signaler (le clone n'est pas relié à GitHub).
   - Si des fichiers **suivis** sont modifiés localement → s'arrêter et prévenir (Loïc ne doit rien
     modifier dans les fichiers du système ; ses données vivent dans Supabase + `.env` non suivis).

2. **Tirer les mises à jour** en fast-forward strict (jamais de merge automatique) :
   ```bash
   git -C "<racine>" pull --ff-only
   ```
   - Capturer le résumé (liste des fichiers changés).
   - Si le pull **n'est pas fast-forward** (divergence) → **s'arrêter**, ne rien forcer, signaler à
     Adrien qu'il faut intervenir. Ne jamais faire `git reset --hard`, `merge` ni `push`.

3. **Réagir aux changements détectés** dans le diff :
   - Si **`requirements.txt`** a changé → relancer `pip install -r requirements.txt`.
   - Si une **skill mobile** a changé — son `SKILL.md` OU un fichier `references/` qu'elle bundle
     (`scraper-contenu-cazal` et autres skills engine n'ont PAS de zip mobile — concernées :
     `veille-niche`, `idee-contenu`, `script-reel-chantier`, `generateur-hooks`, `scripter-reel`,
     `rediger-article`) → **régénérer les zips localement** :
     ```bash
     python shared/scripts/export_skills.py <skills concernées>
     ```
     puis guider Loïc pas à pas : sur claude.ai → **Réglages ▸ Fonctionnalités**, supprimer
     l'ancienne version de chaque skill concernée et uploader le nouveau zip depuis
     `active/skills-zip/<skill>.zip` (la sync mobile n'est pas automatique).

4. **Résumé en 2 lignes** : ce qui a été mis à jour (ou « déjà à jour »), et toute action restante
   (re-upload d'un zip, dépendance réinstallée). En cas d'erreur, message clair, pas de tâtonnement.

## Règles fermes

- **Lecture seule côté Loïc** : cette skill ne fait **jamais** `commit`, `push`, `merge` ni
  `reset --hard`. Le clone de Loïc est un **consommateur** ; la source de vérité est le repo d'Adrien.
- **`--ff-only` obligatoire** : si l'historique a divergé, on s'arrête au lieu de créer un merge bancal.
- **Secrets intouchés** : `.env` et `active/` sont gitignorés → un pull ne les touche jamais.
- Ne jamais inventer un résultat : rapporter fidèlement la sortie de `git pull` (fichiers, erreurs).
