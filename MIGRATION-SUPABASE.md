# Migration vers Supabase — spec exécutable (DIFFÉRÉE)

> **Statut : 🟠 PRÊT À DÉROULER — décisions prises le 2026-07-20, en attente du jour de livraison.**
> Le déroulé complet de l'installation chez Loïc est en bas de ce fichier (§ « JOUR J »).
> Tant que ce n'est pas fait, le système tourne en **amorçage markdown** (les skills actuels lisent
> `references/rapport-perf-digest.md` et `references/base-idees.md`). **Ne rien migrer avant d'avoir les
> accès** — sinon les skills pointeraient vers une base inexistante.
>
> Ce fichier est la **checklist d'exécution** à dérouler dès que les accès existent. Plan détaillé
> complet : `~/.claude/plans/lit-le-fichier-build-floofy-swan.md` (section ADDENDUM). Décision :
> `decisions/log.md` (2026-06-22). SQL prêt : `shared/sql/schema.sql`.

## Pourquoi Supabase (rappel)
Base unique pour Performance + Idées. Airtable écarté (plafond 1 000 lignes + API 5 req/s),
Google Sheets écarté (Loïc ne consulte pas la base lui-même — interface = les skills). Supabase :
aucun plafond utile, clés permanentes (pas de ré-auth hebdo), pgvector dispo (différé), maîtrisé par
Adrien (Master-content). Caveat : projet gratuit en pause après 7 j d'inactivité → run hebdo le garde
chaud.

## Principe d'architecture (validé)
- **ENGINE = Python + Supabase** (Claude Code, PC) : tout le travail data.
- **MOBILE = pas de Python réseau** : les skills mobiles lisent un **snapshot bundlé** ou la base via le
  **connecteur Supabase MCP** de claude.ai (pas de clé embarquée).
- Chaque skill engine, après écriture Supabase, **régénère le snapshot** mobile puis on **re-zip + re-upload**.

---

## ÉTAPE 1 — Créer la base (quand le projet Supabase existe)
1. Créer le projet Supabase sur le compte de Loïc. Récupérer **Project URL** + **anon key**
   (+ **access token** pour le MCP).
2. Exécuter **`shared/sql/schema.sql`** dans le SQL Editor (ou via MCP `apply_migration`).
   → crée `comptes`, `contenu`, `compte_stats`, `contenu_snapshots`, `idees`, la vue
   `contenu_avec_scores`, le trigger `update_compte_stats`, la RLS.
3. (Optionnel, plus tard) pgvector : `CREATE EXTENSION IF NOT EXISTS vector;` puis décommenter la
   colonne `embedding` dans le schéma.

## ÉTAPE 2 — Secrets (.env), placeholders style Master-content
Remplacer le `.env` racine actuel par ce jeu de placeholders (Loïc/Adrien collent les vraies valeurs ;
vérif `python shared/config.py` → SET/MISSING ; jamais de secret dans le chat) :
```
SUPABASE_PROJECT_URL=REPLACE_WITH_YOUR_SUPABASE_PROJECT_URL
SUPABASE_ANON_KEY=REPLACE_WITH_YOUR_SUPABASE_ANON_KEY
SUPABASE_ACCESS_TOKEN=REPLACE_WITH_YOUR_SUPABASE_ACCESS_TOKEN
APIFY_API_TOKEN=REPLACE_WITH_YOUR_APIFY_API_TOKEN
OPENAI_API_KEY=REPLACE_WITH_YOUR_OPENAI_API_KEY
# Poller (optionnel — own-account via Meta Graph)
META_ACCESS_TOKEN=REPLACE_WITH_YOUR_META_ACCESS_TOKEN
IG_USER_ID=REPLACE_WITH_YOUR_IG_USER_ID
IG_HANDLE=REPLACE_WITH_YOUR_IG_HANDLE
```
> Renommages vs version actuelle : `SUPABASE_URL`→`SUPABASE_PROJECT_URL`, `APIFY_TOKEN`→`APIFY_API_TOKEN`.

## ÉTAPE 3 — Plomberie (calquée Master-content à ~90 %)
- **`shared/config.py`** → loader `.env` walk-up qui **expose les variables en module** (copie conforme
  de `Master-content/shared/config.py`). *(remplace la version actuelle à base de `require/status`.)*
- **`shared/database.py`** (NOUVEAU) → client **`supabase-py`** singleton `get_client()` + wrappers :
  `upsert_compte`, `upsert_contenu` (on_conflict=`id`, n'écrase pas l'analyse), `insert_snapshot`,
  `get_contenu_scores` (lit la vue), `update_contenu_fields`, `list_idees`, `insert_idee`,
  `update_idee_statut`. Calqué sur `Master-content/shared/database.py`.
- **`requirements.txt`** (NOUVEAU) → `supabase>=2.9.0`, `openai`. Install : `pip install -r requirements.txt`
  (**demander confirmation avant d'installer**).
- **`shared/scripts/`** → sous-dossiers MC-style : `post/`, `search/`, `ai/`, `prompts/`. Scripts
  atomiques : imports `from shared.config import …` / `from shared.database import get_client`,
  `argparse`/`sys.argv`, **JSON stdout / progression stderr**, idempotents.

## ÉTAPE 4 — Modifs skill par skill

### Engine (Python + Supabase, tournent dans Claude Code)
- **`scraper-contenu-cazal`** *(modifié)* — script `shared/scripts/post/upsert_contenu_apify.py` :
  Apify (Loïc + 3-5 concurrents) → `upsert_compte` → `upsert_contenu` (on_conflict=`id`) →
  `insert_snapshot`. Lit `APIFY_API_TOKEN`. JSON brut archivé dans `active/contenu/`.
- **`analyser-contenu`** *(NOUVEAU)* — `shared/scripts/ai/analyser_contenu.py` : pour `contenu`
  `is_analyzed=false` → Whisper (transcript) + GPT (`spoken_hook`/`hook_structure`/`hook_framework`/
  `topic`, prompt `shared/scripts/prompts/gpt_hook_analysis.txt`) + **visuels par Claude CLI
  headless** (frames ffmpeg lues par Claude, zéro coût API — pas de Gemini) →
  PATCH `contenu`, `is_analyzed=true`. Calqué `_analysis.py` de MC.
- **`rapport-performance`** *(modifié)* — lit la vue `contenu_avec_scores` (posts de Loïc) via
  `shared/scripts/search/list_contenu_scores.py` → rapport `active/analyse/` → **régénère**
  `references/rapport-perf-digest.md`.
- **`rapport-concurrents`** *(modifié)* — lit `contenu_avec_scores` (concurrents vs Loïc, même sujet) →
  variable gagnante + fix → MAJ `references/rapport-perf-digest.md` ; verse les gaps dans `idees`.
- **`veille-niche`** *(modifié)* — `shared/scripts/post/insert_idee.py` → écrit `idees` + **régénère**
  `references/base-idees.md`.

### Mobile (pas de Python réseau)
- **`idee-contenu`** *(modifié)* — lit `idees` via **connecteur Supabase MCP** (si Loïc l'a connecté),
  sinon snapshot bundlé `references/base-idees.md`. Flux inchangé (liste → choix idée → choix format →
  variations). MAJ `statut` via MCP si dispo, sinon réconciliation engine.
- **`script-reel-chantier`, `generateur-hooks`, `scripter-reel`, `rediger-article`** *(quasi inchangés)*
  — lisent les snapshots bundlés (`rapport-perf-digest.md`, `voice.md`, `framework-hook.md`, formats).

### Pont engine → mobile
Après chaque run engine : `rapport-*` régénèrent `rapport-perf-digest.md`, `veille-niche` régénère
`base-idees.md` → `python shared/scripts/export_skills.py` → re-upload sur claude.ai.

## ÉTAPE 5 — Vérification
- `python shared/config.py` → `SUPABASE_PROJECT_URL` / `SUPABASE_ANON_KEY` = SET.
- Insert de test via `shared/database.py` puis `get_contenu_scores` → la ligne revient.
- `scraper-contenu-cazal` → lignes dans `comptes`/`contenu`/`contenu_snapshots` ; `compte_stats` rempli
  par le trigger.
- `rapport-performance` régénère `rapport-perf-digest.md` ; `idee-contenu` liste les idées de `idees`.
- `python shared/scripts/export_skills.py` → zips OK (slashes `/`, snapshots bundlés).

---

## ANNEXE — Poller de KPIs (construit — cf. reste-a-faire.md Bloc 3ter)
Automate périodique qui rafraîchit les KPIs (`contenu`), les stats (`compte_stats`, via trigger) et
écrit un snapshot quotidien (`contenu_snapshots`). Réf. Master-content :
`lessons/1.6-instagram-poller/` (n8n). Implémentation Cazal : **routine Claude LOCALE** sur le PC de
Loïc (décision Bloc 3ter — pas de cloud, le `.env` local fournit les secrets), qui déclenche le
script déterministe **`shared/scripts/post/poller.py`** (le LLM ne lit pas les payloads).
**Dual-mode (2026-07-20)** : Meta Graph si `META_ACCESS_TOKEN` + `IG_USER_ID` SET (own-account,
insights riches : reach/saves/shares/watch time — module `shared/scripts/post/meta_graph.py`),
sinon Apify (views/likes/comments). Setup Meta : § JOUR J, bloc C-bis.

---

## MISE À JOUR 2026-07-19 — Table 9 `syntheses`

Le schéma compte désormais une **table 9 `syntheses`** (digests & rapports de perf datés, lus en
live par les skills via le connecteur MCP — cf. `decisions/log.md` 2026-07-19). Elle est incluse
dans `shared/sql/schema.sql` (SQL idempotent) : la migration chez Loïc la créera automatiquement
en rejouant le schéma. *(Le re-seed du digest est couvert par la copie de lignes du Jour J ci-dessous —
`syntheses` fait partie des tables copiées.)*

---

## JOUR J — installation chez Loïc (déroulé complet, décisions du 2026-07-20)

> Décisions actées (`decisions/log.md` 2026-07-20) : **clés API tierces = les siennes** (comptes
> Apify/OpenAI créés ensemble — Gemini abandonné, visuels par Claude CLI) · **données = copie de
> lignes** depuis la base d'Adrien
> (`shared/scripts/post/migrer_donnees.py`) · **zips mobiles = régénérés par Loïc** après un pull
> (`maj-aios` mis à jour). Ordre pensé pour tout tester au fur et à mesure.

### A. Le PC (engine)
1. Installer : **Git**, **Python**, **VS Code + Claude Code** (compte Claude payant de Loïc).
2. GitHub : Loïc crée un **compte GitHub gratuit** → Adrien l'invite **collaborateur en lecture**
   sur le repo privé `cazal-aios` → `git clone` dans `C:\AIOS-Cazal` (login navigateur une fois,
   mémorisé par Git Credential Manager).
3. `pip install -r requirements.txt` (confirmer avant d'installer).

### B. La base Supabase (la sienne)
4. Loïc crée son **compte Supabase** → nouveau projet (région EU). Récupérer Project URL + anon key
   (+ access token si besoin du connecteur).
5. SQL Editor → coller **`shared/sql/schema.sql`** (idempotent, crée les 9 objets d'un coup).
6. `.env` local chez lui (jamais dans le chat) : ÉTAPE 2 ci-dessus + ses clés **Apify / OpenAI
   créées sur SES comptes** (pas de Gemini — les visuels passent par le Claude CLI, déjà installé
   en A.1). Vérif : `python shared/config.py` → tout SET.
7. **Copie des données** depuis la base d'Adrien — sur le PC d'**Adrien** (qui a les deux jeux de
   clés dans son `.env` : source + `CIBLE_SUPABASE_URL`/`CIBLE_SUPABASE_ANON_KEY`) :
   ```bash
   python shared/scripts/post/migrer_donnees.py        # dry-run : comptages
   python shared/scripts/post/migrer_donnees.py --go   # copie réelle (idempotent, rejouable)
   ```
   Copie `comptes`, `contenu`, `contenu_snapshots`, `compte_stats`, `idees`, `syntheses` en
   préservant ids/dates/analyses. Vérif côté Loïc : `PYTHONUTF8=1 python -m shared.database`.

### C. La surface (claude.ai de Loïc)
8. Uploader les zips de `active/skills-zip/` (régénérés au besoin : `python
   shared/scripts/export_skills.py`) sur **son** compte : Réglages ▸ Fonctionnalités.
9. **Connecteur Supabase MCP** sur son compte claude.ai :
   `https://mcp.supabase.com/mcp?project_ref=<SON_ref>&read_only=true&features=database,docs`.
   Sans lui, les skills retombent sur les snapshots bundlés (dégradé propre).

### C-bis. Meta Graph — KPIs riches (OPTIONNEL, activable après coup)
Le poller est **dual-mode** : tant que le token Meta manque, il tourne via Apify (views/likes/
comments). Avec Meta : reach, saves, shares, watch time en plus. Setup (~30 min, faisable un autre
jour) :
1. Compte Instagram de Cazal en **professionnel**, relié à une **Page Facebook**.
2. developers.facebook.com → créer une app → produit **Instagram Graph API** → permissions
   `instagram_basic`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`.
3. Générer un **token longue durée** (⚠️ expire ~60 jours, renouvellement manuel — le poller
   affichera « token Meta expiré » le moment venu) + récupérer l'`IG_USER_ID` via la Page liée.
4. Coller `META_ACCESS_TOKEN` + `IG_USER_ID` (+ `IG_HANDLE`) dans le `.env` → au prochain run,
   le poller bascule tout seul en mode Meta (`"source": "meta"` dans sa sortie).

### D. Tests de sortie + rappels
10. Engine : « qu'est-ce qui marche dans mon contenu ? » → `rapport-performance` lit SA base.
11. Surface (Desktop/mobile) : un skill de rédaction cite le digest et sa `run_date` → il lit la
    table `syntheses` de SA base via le connecteur.
12. Boucle de maj : Adrien push un changement témoin → Loïc « mets à jour mon AIOS » (`maj-aios`).
13. Rappels : projet Supabase gratuit **en pause après 7 j d'inactivité** (le run hebdo le garde
    chaud) · le `.env` et `active/` ne sont jamais touchés par un pull · Adrien retire ensuite les
    clés `CIBLE_*` de son `.env` (la copie est terminée).
