---
name: scraper-contenu-cazal
description: Scrape les posts Instagram de Loïc + de 3-5 concurrents (frigoristes/HVAC et artisans grand public qui performent) via Apify et les enregistre dans Supabase (comptes + contenu + snapshots). Skill MOTEUR, tourne dans Claude Code (engine, côté Adrien), PAS sur mobile. Se déclenche sur "scrape le contenu", "récupère les posts concurrents", "mets à jour les données de perf".
---

# Scraper de contenu — Cazal Réfrigération (MOTEUR)

## Ce que fait cette skill

Collecte les posts (vues, likes, commentaires, légende, URL, date) de Loïc **et** d'une poignée de
concurrents via **Apify**, et les **enregistre dans Supabase** (`comptes`, `contenu`,
`contenu_snapshots`). C'est la première brique du moteur data-driven : sans données, ni
`rapport-performance` ni `rapport-concurrents` ne peuvent tourner.

> ⚙️ **Skill engine** : s'exécute dans Claude Code (accès `.env`, réseau, Supabase). Pas sur mobile.

## Prérequis

- `.env` : `APIFY_API_TOKEN` (+ `SUPABASE_PROJECT_URL`, `SUPABASE_ANON_KEY` déjà branchés).
  Vérifier via `python shared/config.py` (SET/MISSING) — **jamais** `cat .env`.
- Liste des comptes à scraper : le handle de Loïc (`--type own`) + 3-5 concurrents (`--type concurrent`).

## Étapes

1. **Vérifier les clés** : `python shared/config.py` → `APIFY_API_TOKEN` doit être SET. Sinon, demander
   à Loïc/Adrien de remplir le `.env` et s'arrêter (ne pas tâtonner).
2. **Scraper + enregistrer** via le script engine, un appel par groupe :
   ```bash
   python shared/scripts/post/upsert_contenu_apify.py <handle_loic> --type own --limit 30
   python shared/scripts/post/upsert_contenu_apify.py <conc1> <conc2> <conc3> --type concurrent --limit 30
   ```
   Le script : `upsert_compte` → `upsert_contenu` (on conflict `id`, **n'écrase jamais** l'analyse IA)
   → `insert_snapshot` du jour. JSON brut archivé dans `active/contenu/`.
3. **Lire le récap JSON** (comptes / contenu insérés) et pointer la suite : lancer `analyser-contenu`
   (analyse IA) puis `rapport-performance` / `rapport-concurrents`.

## Règles fermes

- **Lecture seule côté plateformes** (draft-only) : on ne scrape que du public, aucune publication.
- **Idempotent** : re-scraper met à jour les KPIs sans dupliquer ni écraser l'analyse (`upsert on_conflict=id`).
- Ne jamais inventer de chiffres : si Apify ne renvoie pas une métrique, elle reste à 0/null.
- Les comptes de Loïc = `--type own` ; les concurrents = `--type concurrent` (sert aux rapports).
