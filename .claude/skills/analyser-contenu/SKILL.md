---
name: analyser-contenu
description: Analyse IA des contenus scrapés non encore analysés (hook, structure, sujet, type + analyse visuelle des frames par Claude) et enregistre l'analyse dans Supabase. Skill MOTEUR (Claude Code, engine). Se déclenche sur "analyse les contenus", "analyse IA des posts", "extrais les hooks".
---

# Analyser le contenu — Cazal Réfrigération (MOTEUR)

## Ce que fait cette skill

Pour chaque `contenu` Supabase `is_analyzed=false`, extrait deux couches d'analyse puis **PATCH**
la ligne (`is_analyzed=true`) :
- **Audio/texte (GPT)** : `spoken_hook`, `hook_structure`, `hook_framework`, `topic`,
  `topic_summary`, `content_type`, `call_to_action` (prompt `shared/scripts/prompts/gpt_hook_analysis.txt`).
- **Visuel (Claude CLI)** : `text_hook`, `visual_hook`, `visual_format` (taxonomie 6 valeurs),
  `audio_hook` + `duration` — des frames sont extraites par ffmpeg (2 img/s sur les 4 premières
  secondes = le hook, + 4 frames réparties dans le corps, 512 px) et **Claude les regarde** via le
  CLI headless (`claude -p`, abonnement → zéro coût API). Mécanisme cloné de Master-content
  (façon claude-video), prompt `shared/scripts/prompts/claude_visual.txt`.

C'est l'étape entre le scraping et les rapports : elle enrichit les KPIs bruts d'une couche
d'analyse réutilisable (pyramide de hooks + dimension visuelle).

> ⚙️ Skill engine (Claude Code). Calqué sur l'analyse de Master-content (`_analysis.py`).

## Prérequis
- `.env` : `OPENAI_API_KEY` (Whisper + GPT) + `APIFY_API_TOKEN` (re-fetch des videoUrl frais) + Supabase.
- **`ffmpeg`, `ffprobe` et `curl` installés** (audio, durée, frames, download).
- **Claude CLI installé et loggé** (`claude`) — déjà le cas sur un PC qui fait tourner Claude Code.
- Vérifier via `python shared/config.py`.

## Comment ça marche (v3 — transcript + visuels Claude)
Pour chaque `contenu` `is_analyzed=false` : **re-fetch Apify** du compte (videoUrl frais, car les liens
CDN expirent vite) → **télécharge** le mp4 (`curl`) → **ffprobe** (durée) → **ffmpeg** extrait
l'audio (WAV 16 kHz) → **Whisper** transcrit → **GPT** extrait les champs hooks/topic → **ffmpeg**
extrait les frames dans `active/_visual_<id>/` → **Claude CLI** lit les frames (tool Read) et rend le
JSON visuel → **PATCH** `contenu` (transcript + analyse + visuels + duration + `is_analyzed=true`)
→ cleanup des frames.

## Étapes
1. Vérifier `OPENAI_API_KEY` SET (+ `APIFY_API_TOKEN`, ffmpeg/ffprobe/curl, CLI `claude`). Sinon s'arrêter.
2. Lancer **juste après un scrape/poller** (URLs fraîches) :
   ```bash
   python shared/scripts/ai/analyser_contenu.py --limit 30
   ```
3. Lire le récap JSON (`ok` / `fail` / `sans_transcript` / `sans_visuel` / `errors`).
   Compter ~30-60 s de plus par vidéo pour le step visuel (appel Claude CLI).

## Règles fermes
- **Idempotent** : ne retraite pas `is_analyzed=true`. Re-lançable sans risque.
- **Ne rien inventer** : les prompts imposent `null` si l'info n'est pas déduisible ;
  `visual_format` hors taxonomie → `null`.
- **Dégradé gracieux, jamais de fallback** : pas de videoUrl / `ffmpeg` absent → **légende seule**
  (`sans_transcript`) ; échec du step visuel (CLI absent, timeout) → champs visuels `null`
  (`sans_visuel`) — dans les deux cas `is_analyzed=true` (pas de boucle), données cohérentes.
- **Expiration des videoUrl** : toujours analyser peu après le scrape ; le script re-fetch les URLs au
  moment de l'analyse pour limiter le risque.
- Vocabulaire grand public, zéro jargon ajouté (`references/angles-signature-cazal.md`).
