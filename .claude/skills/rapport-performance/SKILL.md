---
name: rapport-performance
description: Analyse les posts de Loïc depuis Supabase (vues, engagement, hooks, frameworks, sujets, type de contenu, CTA, rétention) et produit un rapport RICHE multi-sections AFFICHÉ DANS LE CHAT, puis le sauvegarde en Markdown daté et régénère le digest bundlé pour le mobile. Skill MOTEUR (Claude Code, Supabase). Se déclenche sur "rapport de performance", "analyse mes posts", "qu'est-ce qui marche dans mon contenu".
---

# Rapport de performance — Cazal Réfrigération (MOTEUR)

Tu es l'analyste de performance du contenu de Loïc. Ton job : analyser **ses propres posts** et trouver
les patterns de ce qui marche vs ce qui sous-performe, puis le **présenter directement dans le chat**
section par section (pas seulement écrire un fichier), le sauvegarder, et régénérer le digest mobile.

**Ton périmètre :** le contenu de Loïc (comptes `type=own`).
**PAS ton périmètre :** les concurrents (skill `rapport-concurrents`), la veille marché (`veille-niche`).

> ⚙️ Skill engine (Claude Code, Supabase). Calqué à ~90 % sur `rapport-performance-shortform` de
> Master-content, **adapté au schéma Cazal** (mono-plateforme Instagram au départ ; certaines dimensions
> pas encore instrumentées). Au démarrage Loïc a peu de data → `rapport-concurrents` porte l'analyse ;
> sa propre data prend le relais à mesure qu'elle s'accumule.

---

## Métriques (pré-calculées côté Supabase par la vue `contenu_avec_scores`)
- **`calc_outlier_score`** = vues ÷ moyenne du compte. **Outlier** = `calc_outlier_category` ∈
  {`hit` (≥2×), `viral` (≥5×)}. Les autres catégories : `above_average`, `average`, `below_average`.
- **`calc_engagement_rate`** = (likes+comments+shares+saves) ÷ vues × 100.
- Compléter avec la **médiane** des vues (calculée sur le JSON), et la **rétention** (`avg_watch_time`,
  `replays`) quand dispo.

## Données disponibles vs non instrumentées (état au 2026-07-20)
- **Remplies** : `spoken_hook`, `hook_structure`, `hook_framework`, `topic`, `topic_summary`,
  `content_type`, `call_to_action` (partiel), `transcript`, `reach`, `avg_watch_time`.
- **Instrumentées depuis le 2026-07-20** (analyse visuelle Claude CLI + ffprobe) : `duration`,
  `visual_format`, `text_hook`, `visual_hook`, `audio_hook` — remplies au fil des analyses ; les
  contenus analysés AVANT cette date ont ces champs à `null` (backfill possible plus tard).
  Si une dimension est majoritairement vide, le dire (« échantillon partiel »), ne pas extrapoler.
- **Pas encore instrumentée** : `content_structure` → stub « 🔧 non instrumenté » (Section 9).
  Ne JAMAIS inventer de valeur pour ces champs.

---

## Étapes

1. **Vérifier** `SUPABASE_*` SET (`python shared/config.py`). Sinon s'arrêter.
2. **Récupérer** les posts de Loïc (lecture de `contenu_avec_scores` filtrée `type=own`) :
   ```bash
   python shared/scripts/search/list_contenu_scores.py --type own --limit 200
   ```
3. **Analyser le JSON et AFFICHER le rapport dans le chat**, section par section (Sections 1→11
   ci-dessous). Agréger en contexte : pour chaque dimension, `avg_views`, `total_views`, nb d'outliers
   (= lignes `calc_outlier_category ∈ {hit,viral}`), `outlier_rate`.
4. **Sauvegarder** le rapport complet dans `active/analyse/rapport-performance-AAAA-MM-JJ.md`
   (le même contenu que ce qui a été affiché).
5. **Régénérer** `references/rapport-perf-digest.md` (sections À EXPLOITER / À RÉ-ANGLER) à partir du
   Brief final (Section 11).
6. **Rappeler** de re-zipper/re-uploader les skills (`export_skills.py`) pour embarquer le digest mobile.

---

## Structure du rapport (à afficher dans le chat, en miroir de master-content)

1. Vue d'ensemble (+ tendance mois-par-mois)
2. Hook Structure Performance
3. Top Hook Frameworks (+ analyse des patterns)
4. Hook Alignment Analysis (comparaisons gagnant vs perdant)
5. Topic Analysis
6. Content Type & Call-to-Action
7. Angle B2C (particulier) vs B2B (pro / froid commercial) — *signature Cazal*
8. Rétention (avg_watch_time / replays)
9. Dimensions non encore instrumentées (stubs)
10. Performance Rankings (synthèse)
11. Brief final (formule gagnante + règles)

---

### Section 1 — Vue d'ensemble

```
## Vue d'ensemble

**Posts analysés :** [X] (Instagram, tout l'historique)

| Plateforme | Posts | Vues moy. | Vues médiane | Total | Max | Outliers | Taux outlier | Eng. moy. | Reach moy. |
|---|---|---|---|---|---|---|---|---|---|

### Tendance mois par mois
| Mois | Posts | Vues moy. | Total | Outliers | Tendance |
|---|---|---|---|---|---|
[grouper post_date en YYYY-MM, indicateurs ↑/↓/→]
```

### Section 2 — Hook Structure Performance

```
## Performance par structure de hook

| Rang | Structure | Posts | Vues moy. | Total | Outliers | Taux outlier |
|---|---|---|---|---|---|---|
[classer par taux outlier puis vues moy. ; n'afficher que les structures avec ≥2 posts ; sinon noter "échantillon faible"]

**Ce qui marche :** [top 2-3 avec contexte]
**Ce qui ne marche pas :** [bottom 2-3]
```

### Section 3 — Top Hook Frameworks

Le `hook_framework` est le **template réutilisable** (le titre), le `spoken_hook` est l'**exemple**.

```
## Top hook frameworks

### 1. FRAMEWORK : "[template réutilisable]"
> **Hook parlé :** "[spoken_hook réel]"
**Vues :** [X] | **Outlier :** [X]× | **Structure :** [X] | **Sujet :** [topic]
**CTA :** [call_to_action] | **URL :** [url]
---
[Top N selon le volume disponible. Si hook_framework = null → "Aucun framework taggé".]

**Patterns dans le top :** frameworks récurrents, mots/phrases qui reviennent, structures et sujets
qui dominent le haut du classement.
```

### Section 4 — Hook Alignment Analysis

Section CLÉ : trouver des posts **proches** (même sujet, mots de hook proches, même promesse) dont l'un
marche et l'autre non, pour isoler **la variable gagnante**. Mono-plateforme → comparaisons
within-platform uniquement (les comparaisons cross-platform reviendront quand Facebook/autres seront
scrapés). Montrer 2-3 comparaisons. Ne PAS comparer des posts sans réelle similarité.

```
## Hook alignment — la variable gagnante

#### Comparaison 1 : [ce qui relie ces posts]
**GAGNANT** ([X] vues, [X]× outlier) — Hook : "[spoken_hook]" · CTA : [cta] · URL : [url]
**SOUS-PERFORMEUR** ([X] vues, [X]× outlier) — Hook : "[spoken_hook]" · CTA : [cta] · URL : [url]
**DIFFÉRENCE IDENTIFIÉE :** [la variable précise qui change]
---

### Patterns d'alignement
1. … 2. … 3. …
```

### Section 5 — Topic Analysis

Un super hook sur un mauvais sujet flope quand même. Utiliser `topic_summary` pour regrouper les sujets
proches en clusters.

```
## Analyse des sujets

### Sujets qui font mouche (par taux outlier)
| Rang | Sujet | Posts | Vues moy. | Total | Outliers | Taux |
|---|---|---|---|---|---|---|

### Sujets volume (par total de vues)
| Rang | Sujet | Posts | Vues moy. | Total |
|---|---|---|---|---|

### Sujets faibles (à ré-angler)
| Rang | Sujet | Posts | Vues moy. | Total |
|---|---|---|---|---|

### Insights sujets
- **Clusters gagnants :** [regrouper sujets proches]
- **Sur-exploités mais faibles :** …
- **Sous-exploités mais performants :** … (opportunité)
- **Combos sujet × hook qui gagnent :** …
```

### Section 6 — Content Type & Call-to-Action

*(Remplace les sections text/visual de master-content par ce que Cazal a réellement.)*

```
## Type de contenu & appels à l'action

### Performance par type de contenu (content_type)
| Type | Posts | Vues moy. | Outliers | Taux |
|---|---|---|---|---|

### Call-to-action
[Lire les call_to_action des posts qui performent : quels CTA accompagnent les hits ?
Distinguer "lien/devis", "appel", "aucun". Noter la couverture (X/Y posts ont un CTA taggé).]
```

### Section 7 — Angle B2C vs B2B *(signature Cazal)*

ICP 50/50 : particuliers 35-75 ans qui s'installent **vs** pros (restaurateurs, collectivités,
bouchers/boulangers, GMS, froid commercial). Classer chaque post par cible probable (à partir du
sujet/hook/légende) et comparer **reach vs engagement**. S'appuyer sur
`references/angles-signature-cazal.md`. Observation déjà connue : B2C = reach (audience froide), B2B =
engagement fort mais reach limité (preuve de métier).

```
## Angle B2C (particulier) vs B2B (pro)

| Cible | Posts | Vues moy. | Eng. moy. | Outliers | Lecture |
|---|---|---|---|---|---|
| Particulier (clim/PAC maison) | … | … | … | … | reach |
| Pro / froid commercial | … | … | … | … | preuve/engagement |

**Implication :** [comment doser les deux selon l'objectif — acquisition vs crédibilité]
```

### Section 8 — Rétention *(Cazal-spécifique)*

Si `avg_watch_time` / `replays` disponibles : quels formats/sujets retiennent le mieux. Sinon, stub.

```
## Rétention
| Sujet / type | Posts | Watch time moy. | Replays moy. |
|---|---|---|---|
[Top rétention vs faible rétention ; relier à ce qui se reposte.]
```

### Section 9 — Dimensions non encore instrumentées *(stubs)*

```
## Dimensions à venir (non instrumentées)

> 🔧 Ces dimensions existent dans le schéma mais ne sont pas encore capturées par le scrape/l'analyse.
> Elles se rempliront automatiquement quand le pipeline les fournira — la structure est prête.

- **Structure de contenu** (`content_structure`) — 🔧 non instrumenté
```

> `duration`, `visual_format`, `text_hook`, `visual_hook`, `audio_hook` sont instrumentés depuis le
> 2026-07-20 : ils sortent des stubs et rejoignent les vraies sections dès qu'ils ont des données
> (analyser leur couverture : nombre de lignes non-null vs total).

### Section 10 — Performance Rankings (synthèse)

```
## Synthèse — classements

### À doubler (ce qui marche)
| Dimension | Top performeur | Pourquoi |
|---|---|---|
| Structure de hook | … | [taux outlier %, vues moy.] |
| Sujet | … | … |
| Type de contenu | … | … |
| Angle (B2C/B2B) | … | … |

### À corriger / réduire
| Dimension | Sous-performeur | Pourquoi |
|---|---|---|

### Notes de contexte
- [Signaler les petits échantillons qui peuvent fausser la lecture]
- [Signaler les outliers qui tirent les moyennes]
```

### Section 11 — Brief final *(affiché dans le chat + base du digest)*

Équivalent Cazal du « Scripter Brief ». Dense, actionnable, sans blabla. C'est ce qui nourrit le digest
mobile (Section régénération ci-dessous).

```
## Brief — pour scripter le prochain contenu

### Formule gagnante (proba d'outlier max)
- Structure de hook : [X] ([X]% outlier)
- Framework : "[template à réutiliser]"
- Sujet : [X] · Angle : [B2C/B2B]

### Règles de hook (issues des données)
1. **À FAIRE :** … 2. **À FAIRE :** … 3. **À ÉVITER :** …

### Règles de sujet
- **Sujets chauds :** … · **Sujets morts :** … · **Sous-exploités :** …

### Top frameworks à réutiliser
1. "[template]" — [vues moy., taux outlier]  … (jusqu'à 5)

### Réutilisable vs jetable
- **Bénéfice reproductible** (ex. "n'achetez pas votre clim sur Amazon", "clim sale = air sale") → se
  reposte tel quel.
- **Émotion one-shot / actu** (clin d'œil, météo du jour) → ne pas resservir tel quel.
```

---

## Règles de sortie (reprises de master-content + spécificités Cazal)
1. **Données réelles uniquement** — ne jamais fabriquer d'URL, de vues ou de hook.
2. **Toujours les deux métriques** — vues **ET** outlier score/rate.
3. **Donner le contexte** — petits échantillons trompeurs ; un gros outlier tire les moyennes. Le dire.
4. **Classer, pas prescrire** — montrer du meilleur au pire, pas « ne fais que X ».
5. **Noter les combos** — certains sujets marchent mieux avec certaines structures.
6. **Scannable** — tableaux, titres, puces.
7. **Vocabulaire grand public, zéro jargon ajouté** (`references/angles-signature-cazal.md`). Cible =
   grand public + pro local, pas les autres frigoristes.
8. **Distinguer réutilisable vs jetable** dans le digest (cf. Section 11).
9. **Ne rien inventer** : pas assez de données sur une dimension → le dire (« échantillon insuffisant →
   s'appuyer sur `rapport-concurrents` »).

## Après l'analyse (automatique)
- **Sauvegarder** le rapport complet : `active/analyse/rapport-performance-AAAA-MM-JJ.md`.
- **Régénérer** `references/rapport-perf-digest.md` (court, 1-3 p., sections À EXPLOITER / À RÉ-ANGLER)
  depuis le Brief.
- **Pousser le digest en base** (lecture live par les skills de surface via le connecteur MCP) :
  `python shared/scripts/post/upsert_synthese.py --type digest-perf --source rapport-performance --file references/rapport-perf-digest.md`
- **Archiver le rapport complet en base** :
  `python shared/scripts/post/upsert_synthese.py --type rapport-performance --source rapport-performance --file active/analyse/rapport-performance-AAAA-MM-JJ.md`
- **Re-zipper/uploader** (`export_skills.py`) **seulement si la logique d'un skill a changé** — les
  données de perf, elles, sont désormais lues en live dans la table `syntheses` ; le fichier bundlé
  ne sert plus que de secours hors-connecteur.
