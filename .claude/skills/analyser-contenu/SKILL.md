---
name: analyser-contenu
description: Analyse IA des contenus scrapés non encore analysés (extraction du hook, de la structure, du sujet, du type) et enregistre l'analyse dans Supabase. Skill MOTEUR (Claude Code, engine). Se déclenche sur "analyse les contenus", "analyse IA des posts", "extrais les hooks".
---

# Analyser le contenu — Cazal Réfrigération (MOTEUR)

## Ce que fait cette skill

Pour chaque `contenu` Supabase `is_analyzed=false`, extrait via GPT (prompt
`shared/scripts/prompts/gpt_hook_analysis.txt`) : `spoken_hook`, `hook_structure`, `hook_framework`,
`topic`, `topic_summary`, `content_type`, `call_to_action` — puis **PATCH** la ligne
(`is_analyzed=true`). C'est l'étape entre le scraping et les rapports : elle enrichit les KPIs bruts
d'une couche d'analyse réutilisable (la pyramide de hooks).

> ⚙️ Skill engine (Claude Code). Calqué sur l'analyse de Master-content, simplifié.

## Prérequis
- `.env` : `OPENAI_API_KEY` (Whisper + GPT) + `APIFY_API_TOKEN` (re-fetch des videoUrl frais) + Supabase.
- **`ffmpeg` et `curl` installés** sur le PC (pour extraire l'audio et télécharger la vidéo).
- Vérifier via `python shared/config.py`.

## Comment ça marche (v2 — transcript, calqué Master-content)
Pour chaque `contenu` `is_analyzed=false` : **re-fetch Apify** du compte (videoUrl frais, car les liens
CDN expirent vite) → **télécharge** le mp4 (`curl`) → **ffmpeg** extrait l'audio (WAV 16 kHz) →
**Whisper** transcrit → **GPT** extrait `spoken_hook`/`hook_structure`/`hook_framework`/`topic`/
`content_type`/`call_to_action` (prompt `shared/scripts/prompts/gpt_hook_analysis.txt`) → **PATCH**
`contenu` (`transcript` + champs d'analyse + `is_analyzed=true`).

## Étapes
1. Vérifier `OPENAI_API_KEY` SET (+ `APIFY_API_TOKEN`, ffmpeg/curl). Sinon s'arrêter.
2. Lancer **juste après un scrape/poller** (URLs fraîches) :
   ```bash
   python shared/scripts/ai/analyser_contenu.py --limit 30
   ```
3. Lire le récap JSON (`ok` / `fail` / `sans_transcript` / `ffmpeg` / `errors`).

## Règles fermes
- **Idempotent** : ne retraite pas `is_analyzed=true`. Re-lançable sans risque.
- **Ne rien inventer** : le prompt impose `null` si l'info n'est pas déduisible.
- **Dégradé gracieux** : pas de videoUrl frais / `ffmpeg` absent → analyse la **légende seule**
  (transcript vide) et marque quand même `is_analyzed=true` (pas de boucle). `sans_transcript` le compte.
- **Expiration des videoUrl** : toujours analyser peu après le scrape ; le script re-fetch les URLs au
  moment de l'analyse pour limiter le risque.
- Vocabulaire grand public, zéro jargon ajouté (`references/angles-signature-cazal.md`).
