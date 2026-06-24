---
name: rapport-concurrents
description: Compare le contenu de Loïc à celui de concurrents qui surperforment (depuis Supabase), sujet par sujet, pour isoler la variable gagnante et sortir des fixes actionnables. Skill MOTEUR (Claude Code, engine). Se déclenche sur "rapport concurrents", "compare-moi aux concurrents", "qu'est-ce qui marche chez les autres".
---

# Rapport concurrents — Cazal Réfrigération (MOTEUR)

## Ce que fait cette skill

La **pépite du moteur**. Pour chaque sujet de Loïc, trouve le post **concurrent même sujet** qui
surperforme, **isole la variable gagnante** (hook ? accroche actu ? format ? durée ?) et en tire un
**fix actionnable**. Source : la vue Supabase `contenu_avec_scores`.

> ⚙️ Skill engine (Claude Code, Supabase). **Sans pgvector** (différé) : Claude lit les posts des deux
> côtés et compare sujet par sujet.

## Étapes
1. Récupérer les posts :
   ```bash
   python shared/scripts/search/list_contenu_scores.py --type concurrent --limit 200
   python shared/scripts/search/list_contenu_scores.py --type own --limit 200
   ```
2. Pour chaque sujet de Loïc, repérer le(s) post(s) concurrent(s) **du même sujet** qui surperforment
   (outlier `hit`/`viral`).
3. **Isoler la variable gagnante** (hook, accroche, format, durée, angle) → **fix actionnable**
   (« reformule le hook en question », « accroche à une aide/actu », « passe en avant/après »).
4. Écrire `active/analyse/rapport-concurrents-AAAA-MM-JJ.md` (tableau d'ensemble + comparaisons
   même-sujet + gaps de sujets non traités par Loïc).
5. **Mettre à jour** `references/rapport-perf-digest.md` (À EXPLOITER : patterns gagnants ; À RÉ-ANGLER :
   ce que Loïc a tenté + la piste tirée du concurrent). Verser les gaps prometteurs dans la veille/`idees`.

## Règles fermes
- **Toujours comparer à sujet égal** (sinon la variable n'est pas isolée).
- **Concurrents pertinents** : HVAC grand public + artisans qui « pètent ». Pas de comptes geek.
- Fixes **concrets et actionnables**. Ré-angler, pas bannir.
- Ne rien inventer : pas de comparaison fabriquée si le concurrent n'a pas de post sur le sujet.
