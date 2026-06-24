# Conventions de build — AIOS Cazal

> **Quand lire ce fichier** : AVANT toute création, modification ou suppression de skill, script ou
> secret (= **mode build**). Inutile en usage quotidien (générer un résumé, écrire un post…).
>
> Complète [`../EXPANSIONS.md`](../EXPANSIONS.md) (la doctrine *quoi ajouter / quand*) en répondant au
> *comment* : où ça vit, comment c'est fait, quels pièges éviter.

## Où vivent les skills

- **Toute skill** → `.claude/skills/<nom>/SKILL.md` (+ ses dossiers de support bundlés à côté). Un
  dossier = une skill autonome qui se déplace d'un bloc.
- **Noms spécifiques** (domaine + fonction, ex. `resume-vocal-devis`, pas `resume`) : un nom vague
  déclenche à tort. Les **variantes d'une même fonction = modes d'un même skill**, pas des skills séparés
  (ex. récap avant-devis / réunion archi / dépannage = 1 skill « résumé », 3 variantes).
- Skills natives du kit : `onboard`, `audit`, `level-up`. Ne pas les casser ; les nouvelles s'ajoutent
  à côté (souvent via `/level-up`).

## Anatomie d'une skill

- `SKILL.md` (frontmatter `name` + `description` claire qui dit QUAND la déclencher) + éventuels
  `scripts/`, `templates/`, `reference/` **bundlés dans le dossier de la skill**. Rien d'orphelin ailleurs.
- Script utilisé par **une seule** skill → dans `skills/<skill>/scripts/`.
- Code partagé par **≥ 2 skills** → dossier `scripts/` à la racine du repo (créé seulement le jour où
  le besoin existe — cf. `EXPANSIONS.md`).

## La distinction surface / engine (spécifique à Cazal)

Avant de construire une capacité, trancher **où elle vit** (cf. `convention-build.md` + `decisions/log.md`) :

- **Surface d'usage de Loïc** = des **Skills custom uploadées sur son compte claude.ai** (zip ; Pro +
  code execution), déclenchées dans un **chat normal** (mobile ou desktop, sans PC, sans Dispatch ;
  pont testé OK le 2026-06-19). Capacité **contexte→texte** : résumé, génération de post/script. La
  skill **a** du code execution + un filesystem **éphémère** (ressources bundlées dans le zip) + un
  réseau **variable** → suffisant pour le contexte→texte, pas pour le scraping lourd. C'est là que Loïc
  vit (~80 %).
- **Engine** (ce repo sur PC, via Claude Code / Cowork + n8n) = scripts qui s'exécutent vraiment :
  scraping, distillation du digest de perf, base d'idées, veille. Asynchrone, en coulisse. Loïc n'y touche pas.

**Conséquence build (cf. `decisions/log.md` 2026-06-19) :** une skill destinée à Loïc se construit ici,
**bundle ses ressources** (template, voix, digest) dans son dossier, puis se **publie** = zip + upload
sur le compte de Loïc. Pas de sync auto → **re-uploader à chaque modif**.

→ Une capacité « déclenchée par une phrase courte » est vraie **au mobile pour les tâches
contexte→texte uniquement**. Les workflows à scripts lourds/réseau vivent côté engine.

## Double version de chaque skill (repo + zip) — OBLIGATOIRE

Tout skill existe en **deux versions** (cf. `decisions/log.md` 2026-06-22) :
1. **Version repo** — `.claude/skills/<nom>/SKILL.md` (+ supports). Source de vérité, utilisée dans
   **Claude Code et Cowork**.
2. **Version zip** — `active/skills-zip/<nom>.zip`, pour upload sur **Claude Desktop / claude.ai**.

- **Générer** : `python shared/scripts/export_skills.py` (tous) ou `… <nom>` (ciblé). Le script bundle
  les références nécessaires (mapping `BUNDLE`) et écrit des chemins internes en **slashes `/`**.
- ⚠️ **Jamais `Compress-Archive`** : antislashs → erreur claude.ai « invalid characters ». Voie Python only.
- **Pas de sync auto** : modif d'un skill ou d'une référence bundlée → **re-zipper + re-uploader**.
- Les **`references/*.md`** sont la source de vérité unique ; les copies dans les zips en sont une export.

## Moteur de contenu (markdown-first)

- Moteur (`scraper-contenu-cazal`, `rapport-performance`, `rapport-concurrents`, `veille-niche`) tourne
  dans Claude Code. Scripts Python dans `shared/scripts/`, config via `shared/config.py`.
- **Markdown/JSON d'abord** : scrape → `active/contenu/`, rapports → `active/analyse/`, digests →
  `references/{rapport-perf-digest,base-idees}.md`. Supabase si volume seulement.
- **Règle d'or nuancée** : biaiser vers ce qui marche, **ré-angler** (pas bannir) ce qui a sous-performé.
  Digest en deux sections : **À EXPLOITER / À RÉ-ANGLER**.

## Secrets

- **`.env` à la racine du repo** = point unique des secrets. Mécanique : Claude pose un **placeholder**
  (`APIFY_TOKEN=REPLACE_WITH_YOUR_TOKEN`), Loïc colle la valeur dans son IDE, vérif via `${VAR:+SET}`
  uniquement — **jamais** de `cat .env`, `echo $VAR`, ni secret dans le chat. `.env` est gitignoré.
- **Draft-only** (cf. `decisions/log.md`) : on ne branche **que de la lecture** (analytics). Aucun
  accès écriture de publication. Tous les comptes/clés sont créés et payés par Loïc.

## À faire en fin de build (rituel)

1. **Logger** toute décision structurelle dans [`../decisions/log.md`](../decisions/log.md).
2. **Cocher / mettre à jour** [`reste-a-faire.md`](reste-a-faire.md).
3. **Nouvel outil branché** → ligne ajoutée dans [`../connections.md`](../connections.md) + (si API)
   un `references/<outil>-api.md` (researched-once-saved-forever).

## Pièges connus

- **Pas de manuel parallèle** : un seul `CLAUDE.md` canonique. Les décisions ne se dupliquent pas entre
  `convention-build.md` et `decisions/log.md` — `decisions/log.md` est la source de vérité.
- **Nommage** : kebab-case, sans accent ni espace (fichiers et slugs). Sorties datées : `AAAA-MM-JJ-sujet.md`.
- **Anti-patterns** (cf. `EXPANSIONS.md`) : pas de `notes/` `misc/` `tmp/` `inbox/` ; pas de dossiers
  vides « pour plus tard » ; pas de dumps bruts dans `references/` (savoir distillé uniquement — la
  matière première va dans `archives/`).
