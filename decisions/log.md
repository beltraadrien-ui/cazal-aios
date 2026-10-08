# Decisions Log

Append-only record of meaningful decisions and why they were made. `/level-up` Phase 2 (Method interview) writes scoped automation specs here. You can also append manually whenever you decide something worth remembering.

**Format per entry:**

```
## YYYY-MM-DD — Short title

**Decision:** what was decided.

**Why:** the reasoning, constraints, and what would change your mind.

**Alternatives considered:** what else was on the table.

**Owner:** who's accountable.
```

Keep it terse. Future-you will thank present-you for capturing the *why*, not just the *what*.

---

## 2026-06-18 — Séparer la surface de capture de l'engine

**Decision:** L'AIOS de Loïc est en deux couches : une **surface de capture/consommation** (app Claude mobile, Projets) où Loïc vit ~80 % du temps (vocal in, texte out, photos jointes), et un **engine** (Claude Code + n8n + Supabase/markdown) qui tourne en coulisse (scraping, analyse de perf, veille) et qu'il ne touche pas.

**Why:** Tension de vente : « tout vit dans Claude Code » alors que Claude Code n'est pas une surface mobile/vocale. Besoin n°1 de Loïc = piloter au téléphone, au vocal, sans taper. La séparation résout la tension. L'actif portable = le folder de contexte, chargé dans les DEUX mondes. *Changerait d'avis si* une surface unique mobile+engine devenait viable.

**Alternatives considered:** Tout en Claude Code mobile via GitHub (mauvaise UX terrain pour photos+vocal) ; tout dans l'app mobile (impossible pour scripts/scraping).

**Owner:** Adrien.

## 2026-06-18 — Markdown-first pour le digest de perf

**Decision:** Démarrer le rapport de perf en **100 % markdown** (`rapport-perf-digest.md`, style wiki) chargé en Knowledge du Projet mobile. N'ajouter **Supabase** que quand le volume de scraping le justifie.

**Why:** Moins de pièces mobiles au départ, cohérent avec le pattern wiki déjà éprouvé. Un Projet mobile ne requête pas Supabase en live de toute façon — il lui faut un digest court (1-3 pages). *Changerait d'avis si* le volume/la sémantique de recherche dépasse ce que le markdown gère.

**Alternatives considered:** Supabase dès le début (sur-ingénierie au Day 1).

**Owner:** Adrien.

## 2026-06-18 — Pont « vocal sur chantier → script » reporté

**Decision:** Ne PAS construire le déclenchement d'un vrai script engine à la voix depuis le chantier (note vocale → webhook n8n / Cowork). Reporté, non promis.

**Why:** Hors du besoin réel ; c'est le morceau le plus fragile. Le vocal pilote la capture et la génération de texte (contexte→texte), pas l'analyse de perf en temps réel. Les workflows à scripts tournent en asynchrone côté engine (~1×/semaine suffit). *Changerait d'avis si* un vrai besoin terrain émerge après rodage des 2 systèmes.

**Alternatives considered:** Construire le pont dès le MVP (risque/complexité injustifiés).

**Owner:** Adrien.

## 2026-06-18 — Draft-only, tout au nom de Loïc

**Decision:** Le système RÉDIGE, Loïc poste à la main → **aucun accès en écriture de publication** (pas de Meta publishing, pas de GMB API, pas de WordPress REST ; on ne branche PAS Interfast). Tous les comptes et clés sont **créés et payés par Loïc**, collés par lui dans son IDE.

**Why:** Handoff 100 % propre (tout lui appartient), sécurité (jamais de secret dans le chat), et Interfast déjà rodé pour les devis. *Changerait d'avis si* Loïc demande explicitement la publication automatique plus tard.

**Alternatives considered:** Accès écriture pour auto-publier (risque, dépendance, hors besoin).

**Owner:** Adrien.

## 2026-06-18 — Repo Cazal autonome (lien vers le template de Nate coupé)

**Decision:** Le dossier `Cazal-1/` était un clone du starter kit `nateherkai/AIS-OS`. Le `.git` hérité a été supprimé et un nouveau repo Git Cazal a été initialisé (sans remote pour l'instant).

**Why:** C'est le projet de Loïc, plus celui de Nate. Évite la confusion d'un historique/remote pointant vers le template d'origine. *Changerait d'avis si* on veut tirer les futures mises à jour du template (peu probable, on a divergé).

**Alternatives considered:** Garder le remote vers Nate (confusion) ; pas de Git du tout (perte de traçabilité).

**Owner:** Adrien.

## 2026-06-19 — Pont mobile = Skills uploadées sur le compte claude.ai de Loïc

**Decision:** Loïc utilise l'AIOS via des **Skills custom uploadées sur son compte claude.ai**
(Réglages ▸ Fonctionnalités, en zip ; Pro avec code execution), déclenchées **dans un chat normal**
de l'app Claude — **téléphone ou desktop, sans Dispatch et sans que son PC soit allumé**. Séparation
nette : le **dossier (repo) = atelier de build** d'Adrien (skills + engine) ; le **compte claude.ai
de Loïc = surface d'usage** où l'on **publie** (upload zip) les skills contexte→texte. Loïc ne touche
jamais Claude Code, Cowork ni Dispatch.

**Why:** C'est le seul modèle où Loïc, non-technique, retrouve ses capacités dans l'app qu'il a déjà,
partout, sans dépendre d'un PC allumé. La doc Anthropic confirme que les skills du compte claude.ai
sont rattachées au compte (donc dispo sur mobile). *Changerait d'avis si* le test de Phase A montrait
qu'une skill custom ne se déclenche pas depuis l'app mobile.

**Contraintes acceptées (doc officielle) :** (1) **pas de sync entre surfaces** → re-zipper +
re-uploader à chaque modif (process de « publication ») ; (2) **VM claude.ai éphémère et séparée du
repo** → bundler template/voix/digest dans le zip ; (3) **réseau variable** sur claude.ai → pas de
scraping lourd côté mobile, l'engine reste dans le dossier sur PC.

**Alternatives considered:** **Dispatch** (tél pilote le PC — rejeté : exige le PC allumé/joignable) ;
**Projets Claude** Knowledge-only (rejeté : pas de code execution ni ressources bundlées comme une
vraie skill) ; tout en Claude Code (rejeté : outil de dev, pas pour Loïc).

**Owner:** Adrien.

---

## 2026-06-22 — Système de création de contenu : architecture à 3 étages, data-driven

**Decision:** Construire le système de contenu sur le modèle de Master-content, en 3 étages : un
**MOTEUR** d'analyse de perf (`scraper-contenu-cazal` → `rapport-performance` + `rapport-concurrents`
→ digest « À EXPLOITER / À RÉ-ANGLER »), une **PARTIE IDÉATION** (`veille-niche` + un unique
`idee-contenu` qui liste, fait choisir une idée puis un format reel/article/les deux), et une **PARTIE
SCRIPTING** (`script-reel-chantier` dédié au terrain + variantes réalisation/GMB, `generateur-hooks`,
`scripter-reel`, `rediger-article`). Skills granulaires (1 skill = 1 étape). Framework Kallaway porté
dans `references/framework-hook.md`.

**Why:** Le pain n°1 de Loïc = la création de contenu (idéation + rédaction), qu'il n'a pas le temps de
faire. Le moteur de perf garantit qu'on propose et rédige en s'appuyant sur ce qui marche réellement,
pas du générique. Granularité façon Master-content = meilleurs résultats qu'un méga-skill.

**Règle d'or NUANCÉE :** on biaise vers les patterns gagnants mais on **ne bannit pas** ce qui a
sous-performé — on le **ré-angle** (même structure/autre angle, même sujet/autre cadrage). Distinction
ré-utilisable (hook « bénéfice reproductible ») vs jetable (hook « émotion one-shot/actu »).

**Alternatives considered:** méga-skill « contenu » multi-variantes (rejeté : trop fourre-tout, déclenche
mal) ; bannir strictement les sous-performers (rejeté : on perd des sujets recyclables sous un autre angle).

**Owner:** Adrien.

---

## 2026-06-22 — Double version obligatoire de chaque skill (repo + zip)

**Decision:** Tout skill existe en deux versions : la **version repo** (`.claude/skills/<nom>/`, source
de vérité, utilisée dans Claude Code et Cowork) et la **version zip** (`active/skills-zip/<nom>.zip`,
pour upload dans Claude Desktop / claude.ai). Un script `shared/scripts/export_skills.py` génère les
zips (slashes `/`, jamais `Compress-Archive`) et bundle les références nécessaires dans chaque zip.

**Why:** La surface mobile de Loïc (claude.ai) et l'atelier de build (repo) ne sont pas synchronisés.
Il faut donc un export reproductible, et chaque zip doit être autonome (ressources bundlées). Le bug
`Compress-Archive` (antislashs → "invalid characters" à l'upload) impose la voie Python.

**Alternatives considered:** zip manuel à chaque fois (rejeté : source d'erreurs, bug antislash) ;
une seule version (impossible : claude.ai exige un zip, Claude Code lit le dossier).

**Owner:** Adrien.

---

## 2026-06-22 — Base de données contenu : Supabase (unique), schéma calqué Master-content

**Decision:** La base de données du système de contenu sera **Supabase** (une seule base pour
Performance + Idées), schéma calqué sur Master-content avec en plus une table `comptes` normalisée :
`comptes`, `contenu` (FK `compte_id`), `compte_stats`, `contenu_snapshots`, `idees`, + vue
`contenu_avec_scores` + trigger `update_compte_stats`. **Engine en Python** (Claude Code, via
`supabase-py` + `.env` style MC) ; **mobile sans Python réseau** (connecteur Supabase MCP ou snapshot
bundlé). Construction **différée** : Loïc n'a pas encore de compte Supabase → SQL + spec persistés
(`shared/sql/schema.sql`, `MIGRATION-SUPABASE.md`), exécution dès l'obtention des accès.

**Why:** Outil unique demandé. Airtable écarté (plafond 1 000 lignes/base + API 5 req/s) ; Google
Sheets écarté (Loïc ne consulte pas la base lui-même, interface = les skills) ; Supabase = aucun
plafond utile, clés permanentes (pas de ré-auth hebdo), pgvector dispo (différé), maîtrisé par Adrien.
Calquer Master-content à ~90 % accélère le build et réutilise les patterns connus. *Supersède* le
« markdown-first » du 2026-06-18 (le markdown reste comme snapshot exporté pour le mobile).

**Alternatives considered:** Airtable (plafond + limite API), Google Sheets + compte de service
(viable mais UI inutile pour Loïc), rester markdown (pas scalable), hybride Supabase+Airtable (2 outils).

**Owner:** Adrien.

---

## 2026-06-22 — Engine en Python, pas de Python réseau côté mobile

**Decision:** Tout le travail data (Supabase, Apify, OpenAI) se fait **côté engine en Python** dans
Claude Code (PC). Les **skills mobiles** (claude.ai) ne font **jamais de Python réseau** : elles lisent
un **snapshot bundlé** ou la base via le **connecteur Supabase MCP** de claude.ai (pas de clé embarquée
dans le zip).

**Why:** Le bac à sable « code execution » de claude.ai exécute du Python mais a un **réseau
restreint/incertain** et embarquer une clé dans un zip uploadé est un risque de sécurité. Le canal
réseau fiable sur claude.ai = les connecteurs MCP. *Changerait d'avis si* un test mobile prouvait un
réseau sortant fiable depuis le bac à sable (test non retenu pour l'instant : on conçoit sans).

**Alternatives considered:** Python réseau côté mobile (rejeté : non fiable + secret embarqué) ;
construire un skill de test pour vérifier (reporté).

**Owner:** Adrien.

---

## 2026-06-24 — `veille-niche` aligné sur `veille-quotidienne` (orchestrateur complet, branché Supabase)

**Decision:** Réécrire `veille-niche` (jusqu'ici un `SKILL.md` minimal) sur le **modèle complet de
`veille-quotidienne`** de Master-content : dédup (table `idees` + veille-logs sur 2 jours) → sourcing
multi-sources en parallèle → évaluation par les 8 archétypes + scoring + filtre éditorial → Top 10
équilibré par track → présentation structurée → sauvegarde du veille-log → `AskUserQuestion` → écriture
en base. **Le cœur du skill = le sourcing**, avec **4 sources** (niche clim/PAC/froid, pas IA) :
(A) WebSearch Google/PAA — vraies questions clients (filon principal) ; (B) WebSearch actus
aides/primes/normes BE+FR ; (C) **forums métier FR via WebFetch** — liste curée `bricozone.be`,
`forum-chauffage.com`, `forums.futura-sciences.com` (gratuit, le plus riche pour le froid) ; (D) Reddit
FR via Apify (`shared/scripts/scrape_forums.py`) en **complément optionnel non-bloquant** (Reddit FR
pauvre sur le froid). **Tracks** : `b2c` (particuliers, Insta/FB) / `b2b` (pro froid commercial,
LinkedIn). **Destination** : table Supabase `idees` (live) via `shared/scripts/post/insert_idee.py`
(pattern engine = script déterministe → JSON), + régénération du **snapshot** `references/base-idees.md`
(lu par `idee-contenu` en fallback mobile). Dédup via nouveau `shared/scripts/search/list_idees.py`.

**Why:** Le skill standard ne câblait aucune source ni mécanique réelle ; `veille-quotidienne` est
éprouvé et data-driven. Réutiliser son architecture (dédup, archétypes, balance des tracks, veille-log,
checkpoint humain `AskUserQuestion`) donne de meilleurs résultats qu'une idéation ad hoc. Sourcing
privilégié **gratuit/natif** (WebSearch + WebFetch) car Reddit FR est trop pauvre sur le froid : Apify
reste un simple complément. Écriture via script déterministe = même pattern que les autres skills moteur
déjà migrés sur Supabase. *Changerait d'avis si* un forum métier précis s'avérait bien plus productif
(ajuster la liste WebFetch, qui vit dans le SKILL.md).

**Alternatives considered:** garder le skill minimal (rejeté : aucune source réelle) ; Twitter/GitHub/
concurrents IG comme sources (rejeté : non pertinents clim/PAC) ; Reddit/Apify comme source forum
principale (rejeté : trop pauvre — relégué en complément, forums WebFetch en source forum primaire) ;
écrire en base via MCP `execute_sql` (rejeté : le pattern engine du repo = script Python déterministe).

**Owner:** Adrien.

## 2026-06-24 — Rapport de perf : affichage chat + structure master-content

**Decision:** Le skill `rapport-performance` est passé de moteur silencieux (écrit un fichier) à un skill qui **affiche un rapport riche multi-sections DANS LE CHAT** (calqué ~90 % sur `rapport-performance-shortform` de Master-content), puis sauvegarde le `.md` daté ET régénère le digest mobile. Source de données inchangée : le script Python `list_contenu_scores.py` (élargi pour exposer les colonnes riches déjà présentes dans la vue) ; agrégation faite par Claude en contexte. Pas de migration vers du SQL MCP.

**Why:** L'ancien rapport était trop pauvre et invisible (Loïc ne le voyait pas se construire). Master-content prouve qu'un rapport sectionné affiché dans le chat est plus utile. Garder le script Python respecte le pattern engine/`.env` de Cazal et évite une dépendance MCP au runtime. *Changerait d'avis si* Facebook/autres plateformes arrivaient (réactiver les comparaisons cross-platform) ou si le volume dépassait l'agrégation en contexte (≤200 lignes aujourd'hui).

**Alternatives considered:** Migrer vers du SQL MCP pur comme master-content (diverge du pattern Cazal, dépendance runtime) ; omettre les dimensions vides (choisi : stubs « à venir » pour future-proofer la structure).

**Owner:** Adrien.

---

## 2026-06-24 — Distribution & maintenance de l'AIOS : repo GitHub privé + skill `maj-aios`

**Decision:** Livrer l'AIOS à Loïc via un **repo GitHub privé `cazal-aios`** (compte d'Adrien,
source unique). Loïc en a un **clone local** sur son PC, avec **son propre `.env`** (gitignoré, jamais
poussé ni écrasé). Les mises à jour d'Adrien arrivent chez Loïc via une **skill engine `maj-aios`**
(`git pull --ff-only`, lecture seule — jamais `commit`/`push`/`merge`/`reset`), déclenchée dans Claude
Code sur le PC (« mets à jour mon AIOS »). La skill réinstalle les deps si `requirements.txt` a changé
et **signale** si un `SKILL.md` mobile a changé (re-upload de zip à faire à la main).

**Why:** Objectif d'Adrien : ne plus ré-envoyer le dossier par mail/Drive à chaque modif. GitHub couvre
parfaitement la surface **engine (PC)** : `git clone` une fois, `git pull` ensuite. Le `--ff-only` +
le « zéro commit côté Loïc » garantissent des pulls sans conflit (Loïc ne modifie aucun fichier suivi ;
ses données vivent dans Supabase + `.env`). *Changerait d'avis si* Anthropic ajoutait une vraie sync
GitHub→skills sur claude.ai grand public (alors le canal mobile deviendrait automatique aussi).

**Limite assumée (vérifiée) :** la surface **mobile (skills uploadées en zip sur claude.ai grand
public)** n'a **pas d'auto-sync GitHub** → re-upload manuel des zips quand une skill stabilisée change
(rare). GitHub ne couvre donc que l'engine, pas le mobile.

**Alternatives considered:** plugin marketplace Claude Code (`/plugin marketplace update`) — rejeté :
demande une action manuelle de Loïc à chaque fois (préférence pour une skill « dans l'AIOS ») ;
Task Scheduler `git pull` 100 % auto — écarté pour l'instant (Loïc veut déclencher via une skill) ;
ré-envoi du dossier par Drive (rejeté : c'est exactement le problème à supprimer).

**Owner:** Adrien.

---

## 2026-06-24 — Base d'idées Supabase : seed initial + skill `ajout-idee` (capture)

**Decision:** (1) **Seeder** les 17 idées d'amorçage de `references/base-idees.md` dans la table
Supabase `idees` (toutes `statut='idée'` ; 7 `origine='manuelle'`, 10 `origine='veille'`) pour rendre
le « Mode Supabase » de `idee-contenu` opérationnel tout de suite — jusqu'ici la table était vide
(les idées ne vivaient que dans le snapshot, jamais réconciliées en base). (2) Ajouter un skill engine
**`ajout-idee`** : Loïc dicte une idée n'importe quand, Claude la normalise (sujet/archétype/format/
pourquoi) et l'insère via le script Python **existant** `shared/scripts/post/insert_idee.py` — pendant
« écriture » de `idee-contenu` (lecture).

**Why:** Le skill `idee-contenu` était déjà branché Supabase (lecture MCP + fallback snapshot) mais
ne renvoyait rien en base car rien n'avait jamais peuplé `idees`. Le seed corrige ce trou,
indépendamment d'Apify (pas encore branché). `ajout-idee` couvre le besoin « capter une idée à la
volée sans la perdre ». **Insertion via script Python (pas MCP)** : Loïc n'aura peut-être pas le
connecteur Supabase MCP → le script + `.env` local est le canal fiable. Aucun nouveau code Python
(insert_idee.py + database.py existaient et étaient testés) — le skill n'ajoute qu'un SKILL.md.

**Limite assumée :** `ajout-idee` insère via Python/`.env` local → **engine PC uniquement**, pas
mobile sans MCP (noté dans le SKILL.md).

**Point ouvert (futur) :** sens de vérité idées = Supabase ; régénérer `base-idees.md` **depuis** la
base (pas l'inverse) pour éviter les doublons au prochain run de veille. À figer si besoin.

**Alternatives considered:** seed via Python `insert_idee.py` (équivalent ; on a pris MCP `execute_sql`
pour le one-shot car plus direct, sans dépendre du `.env`) ; ne rien seeder et attendre la veille auto
(rejeté : bloque `idee-contenu` en Mode Supabase tant qu'Apify n'est pas branché).

**Owner:** Adrien.

---

## 2026-06-25 — `veille-niche` : Reddit auto-si-SET + source cliquable par idée

**Decision:** Deux modifs au skill `veille-niche`. (1) **Reddit (Apify) se lance automatiquement
dès que `APIFY_API_TOKEN` est SET** — plus de saut discrétionnaire « source faible ». Le statut
`off` dans le header de sortie est désormais réservé aux cas `token MISSING` ou `scrape planté`
(raison écrite dans le veille-log). (2) **Nouvelle colonne `idees.source_url`** (`ALTER TABLE`
appliqué en live) : chaque idée porte une source **cliquable** (URL réelle, ou lien de recherche
Google `https://www.google.com/search?q=…` si pas d'URL de page), affichée en sortie chat et
persistée à l'insertion. `insert_idee.py` (`ALLOWED`) et `schema.sql` mis à jour ; `list_idees.py`
inchangé (`select("*")` remonte la colonne).

**Why:** (1) Loïc lisait « Reddit off » comme une panne alors que c'était un choix du modèle — le
comportement implicite était ambigu, on le rend déterministe. (2) Les idées venaient d'URLs réelles
jamais persistées : impossible pour Loïc d'aller vérifier la source d'une idée a posteriori. La
`source_url` ferme ce trou (traçabilité + confiance).

**Scope explicitement exclu:** le snapshot `references/base-idees.md` **n'a pas** de colonne Source
(choix de Loïc) — la source vit en Supabase + sortie chat uniquement. Les 17 idées existantes ont
`source_url = NULL` (rétro-remplissage non requis).

**Alternatives considered:** garder Reddit optionnel mais forcer la raison du skip dans le log
(rejeté : Loïc préfère le lancement systématique) ; tiret « — » pour les idées sans URL (rejeté au
profit d'un lien de recherche Google actionnable).

**Owner:** Adrien.

---

## 2026-07-19 — Connecteur Supabase MCP : compte Adrien oui, Loïc reporté phase 2

**Decision:** Le « Mode Supabase » des skills de surface s'appuie sur le **connecteur Supabase MCP
hébergé** (`https://mcp.supabase.com/mcp`), déjà en place sur le **compte claude.ai d'Adrien**
(Desktop/mobile, OAuth). Configuration recommandée : `?project_ref=ulhdjyhckvamjwmjncwy&read_only=true`.
**Côté Loïc : rien en V1** — le déploiement du connecteur sur son compte est **reporté en phase 2**.
Les **écritures** restent par les scripts Python déterministes (`insert_idee.py`, poller) : le
connecteur ne sert qu'à la lecture → l'écriture est limitée à `idees` *par construction*.

**Why:** Techniquement trivial, mais peu pertinent pour Loïc en V1 : ses deux systèmes vendus
(résumés vocaux, scripts chantier) n'utilisent pas la base ; l'intelligence vient du digest distillé
(circuit engine → re-zip hebdo déjà prévu) ; seuls `idee-contenu`/`ajout-idee` y gagneraient, à
moitié en lecture seule. En face : créer un compte Supabase à Loïc, migrer la base avant OAuth,
reconnexions — friction disproportionnée pour un non-tech, contraire à la doctrine surface
simple / engine data (Bike Method : livrer le vélo qui roule d'abord).

**Conditions d'activation phase 2 :** frustration réelle constatée sur des idées périmées en mobile,
ou besoin avéré de capture d'idées en mobilité. Prérequis : schéma migré sur SON compte Supabase,
connecteur avec SON `project_ref` + `read_only=true`, OAuth avec SON compte (jamais les identifiants
d'Adrien chez Loïc).

**Limite produit documentée :** le MCP Supabase n'offre **aucune écriture limitée par table**
(`read_only` global ou rien) — d'où le choix lecture seule + écritures par scripts. SKILL.md ajustés
en conséquence (`idee-contenu` : ne jamais prétendre avoir écrit si l'UPDATE est refusé ;
`ajout-idee` : connecteur = vérif doublons seulement) ; zip `idee-contenu` régénéré.

**Alternatives considered:** connecteur en écriture complète (rejeté : une conversation mobile peut
modifier la prod) ; MCP local dans `claude_desktop_config.json` avec token personnel (rejeté :
token dans un fichier + desktop-only, inférieur à l'OAuth hébergé) ; déploiement chez Loïc à la
livraison (rejeté : cf. Why).

**Owner:** Adrien.

---

## 2026-07-19 — Table `syntheses` : digests & rapports de perf lus en live (fin du re-zip data)

**Decision:** Nouvelle table Supabase **`syntheses`** (id, type, titre, contenu markdown, run_date,
source ; unique (type, run_date)) qui stocke, datés : le **digest de perf** (`type='digest-perf'` —
LE contenu que les skills de rédaction lisent) et les **rapports complets**
(`type='rapport-performance'` / `'rapport-concurrents'`, archives consultables). Les skills moteur
la remplissent en fin de run via le script déterministe `shared/scripts/post/upsert_synthese.py`
(--file sur le markdown généré) ; les skills de surface (`idee-contenu`, `script-reel-chantier`,
`scripter-reel`, `generateur-hooks`, `rediger-article`) lisent **le plus récent en live** via le
connecteur Supabase MCP (`SELECT … ORDER BY run_date DESC LIMIT 1`), avec fallback sur le snapshot
bundlé `references/rapport-perf-digest.md`. `veille-niche` (engine) lit via
`shared/scripts/search/get_synthese.py`. Wrappers `upsert_synthese`/`get_derniere_synthese` ajoutés
à `shared/database.py`. Table créée en live (API management, SQL idempotent) + ajoutée à
`schema.sql` (§9) pour la migration Loïc. Seed : digest + rapport du 2026-06-24.

**Why:** Chaque rafraîchissement du digest imposait re-zip + ré-upload de tous les skills de surface
(friction relevée à l'usage par Adrien) et le mobile raisonnait sur des chiffres figés (digest du
24/06 vs base au 15/07). Le pattern dual Supabase/snapshot existait déjà pour les idées
(`idee-contenu`) — on le généralise au digest : le **re-zip ne sert plus qu'aux changements de
logique**, plus jamais aux données. Le fichier digest reste la source rédigée et le fallback →
zéro régression si le connecteur manque.

**Alternatives considered:** Supabase Storage/bucket (rejeté : un fichier dans un bucket n'est pas
requêtable en SQL par le connecteur MCP) ; digest granulaire en `jsonb` une ligne par insight
(différé en V2 : plus requêtable mais plus de build, le markdown suffit) ; laisser la surface
recalculer depuis les tables brutes (rejeté : cher en tokens, conclusions incohérentes d'une
conversation à l'autre).

**Owner:** Adrien.

## 2026-07-20 — Livraison chez Loïc : clés à lui, copie de lignes, zips régénérés par Loïc

**Decision:** Trois choix qui figent le déroulé d'installation (§ « JOUR J » de
`MIGRATION-SUPABASE.md`). (1) **Clés API tierces = les siennes** : comptes Apify, OpenAI et Gemini
créés par/avec Loïc le jour de l'installation — aucune clé d'Adrien ne part chez lui. (2) **Données
= copie de lignes** de la base d'Adrien vers la nouvelle base Supabase de Loïc via le script
one-shot `shared/scripts/post/migrer_donnees.py` (dry-run par défaut, `--go` pour copier ;
idempotent ; préserve ids/dates/analyses ; cible lue dans `CIBLE_SUPABASE_URL`/
`CIBLE_SUPABASE_ANON_KEY` du `.env` d'Adrien, placeholders posés). (3) **Zips mobiles régénérés
côté Loïc** : après un `git pull`, `maj-aios` lance `export_skills.py` localement et guide Loïc
pour l'upload sur SON claude.ai — la boucle de maj est 100 % autonome chez lui.

**Why:** (1) Facturation et responsabilité chez le client, pas de conso de Loïc sur les comptes
d'Adrien. (2) Trois semaines d'analyses déjà payées (Whisper/GPT) et l'historique de snapshots sont
préservés ; repartir de zéro aurait vidé le digest et re-coûté chaque analyse. (3) `export_skills.py`
est déjà dans le repo → aucun aller-retour avec Adrien pour une simple maj de skill mobile.

**Alternatives considered:** Prêter les clés d'Adrien (rejeté : facture et quotas mélangés) ;
re-scraper sur la base vierge (rejeté : perte d'historique + re-coût d'analyse) ; pg_dump/restore
(rejeté : demande le mot de passe DB et un tooling Postgres local — la copie via supabase-py suffit
pour ~350 lignes) ; Adrien continue d'uploader les zips (rejeté : dépendance inutile, Loïc a tout
sur son PC).

**Owner:** Adrien.

## 2026-07-20 — Analyse visuelle par Claude CLI (exit Gemini) + poller KPIs dual-mode Meta/Apify

**Decision:** Deux évolutions du moteur data. (1) **Analyse visuelle des reels par Claude CLI
headless**, clonée du pipeline de Master-content (décision 2026-07-06 du repo racine, « façon
claude-video ») directement dans `analyser_contenu.py` (v3) : ffmpeg extrait des frames hook-dense
(2 fps sur les 4 premières secondes + 4 frames à 25/45/65/85 %, 512 px) dans `active/_visual_<id>/`,
`claude -p` (abonnement, zéro coût API — wrapper `shared/scripts/ai/call_claude.py`, prompt
`shared/scripts/prompts/claude_visual.txt`) les lit et remplit `text_hook`, `visual_hook`,
`visual_format` (taxonomie 6 valeurs), `audio_hook` ; `duration` via ffprobe. Échec → champs null,
jamais de fallback. **Gemini retiré partout** (config.py, placeholders, docs) — il n'était en
réalité branché nulle part (variable morte + une ligne de doc erronée). (2) **Poller dual-mode** :
`poller.py` bascule sur **Meta Graph** (own-account) si `META_ACCESS_TOKEN`+`IG_USER_ID` sont SET —
port Python du workflow n8n `ig-daily-poller` de Master-content (module
`shared/scripts/post/meta_graph.py` : /media paginé + /insights par reel, v21.0, KPIs riches
reach/saves/shares/total_interactions/watch times convertis ms→s) — sinon fallback **Apify**
inchangé (views/likes/comments). Setup Meta côté Loïc documenté au § JOUR J bloc C-bis de
`MIGRATION-SUPABASE.md` (optionnel, activable après coup ; token longue durée ~60 j, renouvellement
manuel, erreur OAuthException 190 explicite).

**Why:** (1) Alignement sur l'AIOS d'Adrien (un seul mécanisme d'analyse visuelle à maintenir),
zéro clé API en plus pour Loïc (le CLI Claude est déjà installé et loggé sur son PC), et les
colonnes visuelles du schéma cessent d'être des stubs « non instrumenté » dans les rapports.
(2) Mêmes raisons : parité avec Master-content (Meta = métriques que Apify ne voit pas : reach,
saves, watch time) sans casser le jour J si le setup Meta (app développeur + token) n'est pas fait.

**Alternatives considered:** Gemini API (rejeté : clé et facturation en plus, mécanisme divergent
de l'AIOS d'Adrien) ; installer le plugin /watch depuis la marketplace (rejeté : Loïc n'a pas à
gérer un plugin — on clone le fonctionnement, pas la dépendance ; le skill /watch interactif n'est
pas répliqué non plus, choix utilisateur) ; bascule totale Meta sans fallback (rejeté : token ~60 j
à renouvellement manuel = poller mort en silence ; Apify reste nécessaire pour les concurrents de
toute façon).

**Owner:** Adrien.

## 2026-09-25 — `resume-vocal-devis` v3 : variante remplacement frigo, questions de rattrapage, référentiel clim

**Decision:** Retouche gratuite du skill (demandée par Loïc en visio le 2026-09-24, hors devis).
(1) **Variante E « remplacement d'installation frigorifique »** : motif et projet, un bloc par poste
(compresseurs, desserte + température, fluide + charge, plaques photographiées), chambres froides,
local technique et contraintes. (2) **Infos indispensables** listées pour chaque variante
(`templates/format-resume.md`) : si l'une manque, Claude la redemande sous le résumé (5 questions
max), puis renvoie le résumé complet mis à jour. (3) **Référentiel clim de Loïc**
(`references/referentiel-unites-interieures-clim.md`, bundlé dans le zip) : marques libres (liste
non limitative), correction automatique des erreurs de dictée (« Ayer » → Haier…) seulement dans un
contexte matériel ; pour une clim à poser présente dans la liste, référence exacte cherchée en ligne
et couleur vérifiée ; modèle hors liste écrit tel que dicté avec la mention « pas dans ta liste »
(jamais « n'existe pas ») ; aucune recherche de référence pour un appareil déjà en place. (4) Le
résumé sort **seul dans un bloc de code** (bouton copier) ; « À vérifier » et « Il te manque » vont
sous le bloc.

**Why:** Loïc n'utilisait pas le skill pour ses visites de remplacement (aucun format adapté, il
demandait « résume un peu ») ; il veut qu'on lui repose la question quand il oublie une info
importante ; son référentiel sert à corriger ses erreurs de prononciation et à fiabiliser les
références. Marques libres : décision d'Adrien (Loïc pose d'autres marques, la liste = les plus
fréquentes). Pas de référence pour l'existant : le catalogue actuel ne correspond pas forcément à un
appareil posé il y a des années. Bloc de code : Loïc copie le résumé sans les remarques. Test à blanc
sur 2 faux vocaux (variantes A et E) le 2026-09-25 : pièges évités, deux ambiguïtés corrigées
(pas de doublon « Il te manque » / « À clarifier » ; déduction évidente écrite mais signalée).

**Alternatives considered:** Limiter aux 3 marques du référentiel, comme le proposait le PDF
(rejeté : les marques doivent rester libres) ; signaler chaque correction de dictée (rejeté : Loïc
veut une correction automatique, seuls les doutes sont signalés) ; poser les questions avant le
résumé (rejeté : Loïc les veut « à la fin »).

**Owner:** Adrien. Listes d'infos indispensables à valider avec Loïc sur de vrais vocaux (Bike
Method phase 1). ⚠️ `maj-aios` ne liste pas `resume-vocal-devis` parmi les skills mobiles à
ré-uploader : prévenir Loïc à la main pour cette mise à jour.

---

## 2026-10-03 — Lancement de la branche « dimensionnement » (v2) : arborescence, skills, choix techniques

**Decision:** Ajout d'une branche `dimensionnement/` à l'AIOS (sous-dossier avec son propre
`CLAUDE.md`, pattern « Sub-OS folder » d'`EXPANSIONS.md`) pour le **chiffrage des remplacements
d'installations frigorifiques**. Cinq skills, noms validés :
- `froid-releve-existant` (PC) : PDF InterFast → dossier créé, photos extraites, tableau de l'existant
  où chaque valeur porte sa source ; validation de Loïc.
- `froid-dimensionnement` (PC) : besoins par poste (puissance existante croisée avec l'abaque par
  volume), pièces à remplacer, conformité du fluide, contrôle de l'écart ; validation de Loïc.
- `froid-demande-fournisseur` (PC) : PDF léger + page de tableaux pour Outlook + texte du mail +
  photos triées ; Loïc relit et envoie lui-même.
- `froid-savoir` (PC) : ingestion d'un document (OCR si scan, images de pages, figures décrites,
  index, base), carnet de leçons.
- `froid-question` (mobile, zip + connecteur Supabase lecture seule) : question à la base de savoir
  depuis le téléphone, réponse sourcée (document + page imprimée + image de la page).

Arborescence : `dimensionnement/savoir/` **versionné** (INDEX.md « par question », `methodes/`,
`fluides/`, `materiel/`, `abaques/` en CSV vérifiés, `formations/`) ; `bibliotheque/`, `carnet/`,
`dossiers/` **locaux et gitignorés** (originaux, OCR, images de pages, leçons, un dossier par
installation). Code partagé par plusieurs skills (recherche dans le savoir, wrappers Supabase,
`shared/sql/schema_savoir.sql`) dans `shared/` ; scripts propres à un skill dans son dossier.

Base de savoir : un schéma « savoir » dans le **projet Supabase de Loïc** (une ligne par page avec
recherche plein texte en français **et** vecteurs, descriptions des figures incluses, images de pages
dans un bucket privé, fonction SQL de recherche en lecture seule). Lue par scripts Python sur PC et
par le connecteur Supabase MCP (lecture seule) sur mobile. Le socle distillé reste en markdown
versionné, lu directement (jamais vectorisé) et bundlé dans le zip mobile comme secours.

Quatre choix tranchés par Adrien : (1) **CoolProp installé chez Loïc** (dépendance épinglée dans
`requirements.txt`, avec son accord) ; (2) **double index, par mots et par sens, pour tout document
ingéré, dès la V1** côté PC ; le mobile cherche par mots en V1 ; (3) contrôle par **abaque de volume**
en V1, le bilan thermique détaillé de chambre est reporté en phase 2 ; (4) **le dossier test (client réel, nom retiré)**
(rapport InterFast IN01834 + conversation Claude de Loïc du 16/09) est le dossier test des étapes 1
et 2. InterFast : démarrage **sans** MCP (réservé au plan supérieur), le PDF reste la porte
d'entrée. Ordre de construction : module chiffrage d'abord, module plans 2D ensuite, séparément.

**Why:** Les documents de Loïc sont pour l'essentiel des **scans sans texte** (environ 3 400 pages),
avec plus d'une page sur deux porteuse d'un schéma ou d'un tableau : un index markdown seul ne tient
pas, il faut OCR, images et recherche. Supabase est déjà en place chez Loïc et branché à l'engine ;
le connecteur MCP lecture seule est le seul canal mobile éprouvé dans cet AIOS (décision 2026-06-19
et 2026-07-19). Vectoriser à l'ingestion coûte quelques centimes et évite de retraiter le corpus plus
tard. Aucun projet open source ne fait le chiffrage de bout en bout ; seules des briques sont
reprises (CoolProp, deux fonctions EN 12900 de TESPy, formule et jeu de compresseurs d'EnergyPlus,
PRP de CoolProp), toutes sous licence MIT ou BSD. Règle inchangée : **tout nombre vient d'un
script, chaque valeur porte sa source, rien n'est inventé**, validation humaine à chaque étape.
Deux recherches documentées (base de savoir le 2026-10-01, dépôts open source le 2026-10-02) sont
conservées par Adrien.

**Alternatives considered:** Projet claude.ai, Cowork ou Claude Code mobile comme accès téléphone
(rejetés : pas d'accès par script, PC à garder allumé, ou interface de session de code) ; index
markdown seul (rejeté : pas joignable du téléphone, et les livres sous droits ne vont pas sur
GitHub) ; tables de fluides précalculées à la place de CoolProp (gardé comme repli si l'installation
échoue chez Loïc) ; bilan thermique détaillé en V1 (rejeté : données de terrain non relevées, hors
besoin au stade remise de prix) ; TESPy et python-hvac comme dépendances (rejetés : trop lourds).

**Owner:** Adrien. Aucun envoi automatique, jamais ; Loïc valide et signe (EN 378).

## 2026-10-03 — Base de savoir : OCR par OpenAI, images 1 000 px, Supabase gratuit, figures sans découpe, vectoriel mobile en phase 2

**Decision:** Après le POC de la base de savoir (39 pages chargées dans le Supabase du projet, recherche
par mots et par sens, skill mobile `froid-question` validé depuis claude.ai), cinq choix sont arrêtés pour
l'ingestion complète (Lot 4). (1) **L'OCR des scans se fait avec l'API OpenAI** (modèle de vision, Responses
API, sortie JSON stricte : markdown de la page, numéro de page imprimé, chapitre, pied de page, figures
signalées par un marqueur `[FIGURE : …]`), clé `OPENAI_API_KEY` du `.env`, modèle par défaut `gpt-5.4-mini`,
repli `gpt-4.1-mini`. Mistral OCR est abandonné. (2) Les images de pages stockées dans le bucket `savoir-pages`
sont ramenées à **1 000 px** de large. (3) Le projet Supabase reste sur le **plan gratuit** : le skill mobile
signale une base en pause et renvoie vers le PC, qui la réveille à la prochaine mise à jour du savoir.
(4) Les figures ne sont **pas découpées** en V1 : la page entière est l'image de référence. (5) La recherche
par sens (embeddings) reste côté PC en V1 ; le mobile cherche par mots ; vectoriel mobile en phase 2.
Le coût d'OCR est mesuré sur un premier lot d'une centaine de pages (tokens comptés par page) avant de
lancer le corpus entier ; une page déjà transcrite est mise en cache et n'est jamais repayée.

**Why:** L'AIOS attend déjà la clé OpenAI pour Whisper, GPT et les embeddings : un seul fournisseur IA pour
l'engine, une seule clé à poser chez le client, une seule facture. Un modèle de vision fait en une passe ce
que Mistral OCR aurait demandé en deux (texte, puis numéro de page, chapitre et figures par un second
modèle). Le pilote montre une lecture juste (tableau de 45 valeurs exact, page tournée de 90° gérée) pour
moins d'un demi-centime par page. 1 000 px tiennent dans le Go du plan gratuit pour tout le corpus et
restent lisibles sur téléphone. La découpe des figures et le vectoriel mobile n'ont pas prouvé leur besoin
au POC : on attend l'usage réel.

**Alternatives considered:** Mistral OCR (rejeté : second compte et seconde clé, OCR non inclus dans le plan
gratuit, et seconde passe nécessaire) ; Claude CLI comme au POC (gardé seulement pour les petits ajouts
de quelques pages : trop lent et consomme le forfait pour un corpus entier) ; OCR local type Tesseract
(rejeté : tableaux et schémas mal lus, et modèle nécessaire derrière de toute façon) ; Gemini (rejeté : pas
plus simple, compte et facturation à ouvrir) ; plan Supabase Pro (reporté : seulement si la pause gêne).

**Owner:** Adrien. Les documents sources restent locaux (droits d'auteur) ; seul le code d'ingestion est versionné.

## 2026-10-03 — Lot 1 livré : `froid-releve-existant`, PyMuPDF en dépendance, dossier d'installation comme mémoire

**Decision:** Première brique de la branche « dimensionnement » : le skill moteur `froid-releve-existant` ouvre
un dossier d'installation (`dimensionnement/dossiers/AAAA-MM-JJ-client/`) à partir du PDF InterFast via
`scripts/extraire_rapport.py` (texte page par page, sous-points et valeurs lues par motif avec leur page,
photos extraites et rangées par poste, `structure.json`, squelettes `dossier.md` et `1-existant.md`), puis
Claude lit les plaques photo par photo, qualifie chaque lecture (sûre / douteuse / illisible), remplit le
relevé avec une source par valeur et une liste « à confirmer », et lance une **double lecture par un
sous-agent vérificateur** avant la validation de Loïc. **PyMuPDF** entre dans `requirements.txt` (rendu et
extraction PDF ; servira aussi au Lot 4). Le socle de savoir démarre avec `savoir/INDEX.md`,
`methodes/checklist-releve.md` (source unique des infos indispensables, miroir de la variante E du résumé
vocal) et `materiel/lecture-plaques.md`. `dimensionnement/.gitignore` exclut `bibliotheque/`, `carnet/`,
`dossiers/`. Le `CLAUDE.md` racine gagne deux lignes de routage ; le manuel de branche est
`dimensionnement/CLAUDE.md`.

**Why:** Le rapport InterFast est la seule porte d'entrée universelle (API et MCP réservés au plan
Business). Les images de gabarit du PDF (fond de page, logo) sont ré-embarquées sur chaque page avec un
identifiant différent : le filtre se fait par empreinte de contenu, pas par identifiant. Les photos sortent
en 450 × 600 ou 800 × 600 : lisibles pour les plaques Bitzer et Profroid du dossier test, pas pour tout
(échangeur Alfa Laval illisible), d'où la règle « illisible = demander l'original ». Le volume des chambres
est le seul calcul de l'étape 1 (L × l × h), signalé comme tel ; tout le reste est une lecture sourcée.
Sur le dossier test, les 7 compresseurs, les 7 évaporateurs et les 3 volumes concordent avec ce que Loïc
avait obtenu à la main le 16/09 ; le relevé ajoute ce que la conversation n'avait pas relevé (plaque
d'ensemble de la centrale B avec R507 d'origine et 21,6 kW, condenseur, régulation détaillée, chauffage).

**Alternatives considered:** `pypdf` seul (rejeté : pas de rendu de page, nécessaire au Lot 4) ; lecture
des plaques par un modèle de vision via API (rejeté en V1 : Claude Code lit les photos directement, et la
double lecture par sous-agent remplit le rôle de vérification) ; calcul des puissances dès l'étape 1
(rejeté : les calculs sont l'étape 2, par script).

**Owner:** Adrien. Validation du relevé du dossier test (client réel, nom retiré) par Adrien (comparaison avec la conversation du 16/09) avant commit.

## 2026-10-05 — Le markdown est la mémoire de Claude ; l'humain lit une vue HTML générée

**Decision:** Chaque document d'un dossier d'installation existe en deux formes : le markdown (`dossier.md`,
`1-existant.md`…), complet et sourcé, relu et écrit par les skills ; et une **vue HTML générée**
(`froid-releve-existant/scripts/rendu_html.py`, bibliothèque `markdown` ajoutée à `requirements.txt`) avec la
photo de chaque plaque en vignette cliquable à côté de sa lecture, ouverte dans le navigateur. Les skills
régénèrent la vue après chaque modification et ne demandent jamais à Loïc de lire du markdown.

**Why:** Au test du Lot 1, Adrien a validé le fond du relevé (tableau des compresseurs identique à celui que
Loïc avait obtenu le 16/09) mais a jugé le markdown « très pénible à lire » pour un humain, surtout les
tableaux : impossible de juger la longueur ou la clarté. Un rendu HTML règle le problème sans changer la
source de vérité, et prépare le modèle HTML unique prévu pour le livrable fournisseur (PDF via Edge).

**Alternatives considered:** Tableaux directement dans la conversation (insuffisant : pas de photos à côté,
perdu à la session suivante) ; DOCX/PDF générés (plus lourd, pas de clic sur les photos ; le PDF viendra du
même HTML au Lot 3) ; convertisseur markdown maison sans dépendance (rejeté : fragile, `markdown` est pur Python).

**Owner:** Adrien.

## 2026-10-05 — Lot 4 livré : base de savoir complète (`froid-savoir` + `froid-question`), OCR OpenAI sous plafond, sections par titres courants

**Decision:** Les scripts du POC sont réécrits dans le dépôt : skill moteur `froid-savoir` (`catalogue.py`,
`extraire_pages.py`, `ocr_openai.py`, `sections.py`, `charger_supabase.py`, `ingerer.py`, `rechercher.py`, `lecon.py`,
`index_mobile.py`), code commun `shared/savoir.py`, schéma `shared/sql/schema_savoir.sql`, outil
`shared/scripts/sql/appliquer_sql.py`. La bibliothèque vit dans `dimensionnement/bibliotheque/` (local) avec un
`catalogue.json` (id, titre, fichier, nature, priorité, décalage, pages de sommaire) et un cache `_cache/` (pages,
OCR, sections, empreintes de chargement) : **une page transcrite n'est jamais repayée**, une page inchangée n'est
jamais rechargée. L'ingestion se fait par priorité (natifs gratuits d'abord, scans par utilité) sous un **budget
par exécution** (`--budget-usd`) et s'arrête proprement au plafond mensuel OpenAI (quota) ; les dépenses sont
estimées dans `_cache/ocr/_depenses.json`. L'OCR (`gpt-5.4-mini`, Responses API, JSON strict) rend en une passe le
markdown, le numéro de page lu, le chapitre, le type de page et la **description de chaque figure** (sans découpe :
l'image de référence est la page, stockée à 1 000 px). Les **sections d'un scan viennent des titres courants lus
sur chaque page** (niveau 1 = `#`, niveau 2 = `##`), exacts page par page ; le sommaire structuré par le modèle et
les signets PDF ne servent qu'en repli. Le skill mobile `froid-question` est finalisé (INDEX généré depuis la base,
zip par `export_skills.py`, ajouté à la liste des zips de `maj-aios`). Les PDF natifs n'ont pas de description de
figures en V1 (texte seul).

**Why:** Première ingestion le 2026-10-05 : 41 documents, 3 431 pages (1 646 natives gratuites, 1 785 scannées
par OCR), 463 Mo de stockage, toutes vectorisées, pour ≈ 10,7 $ estimés, sous le plafond de 12 $ fixé par Adrien
pour mesurer le coût réel. Le Kotza complet (1 301 pages) a coûté 8,75 $ ; une notice 0,0037 $/page, une page de
livre dense 0,0067 $/page. Le sommaire structuré par le modèle (130 puis 538 sections) décalait des chapitres de
plusieurs pages : les titres courants donnent 1 506 sections justes pour le Kotza, gratuitement. Jeu de contrôle sur
le livre complet : 6/7 par mots, 7/7 par sens (bonne page dans le top 3). Un arrêt budget en cours d'exécution a
révélé un blocage de fin de pool de threads (corrigé : drapeau d'arrêt, `shutdown` hors boucle) et une erreur
d'embedding sur une page trop dense (corrigé : repli à 9 000 caractères). PostgREST tronque à 1 000 lignes :
toutes les lectures de pages sont paginées ou comptées par document.

**Alternatives considered:** Mistral OCR (abandonné, cf. 2026-10-03) ; Claude CLI pour les sommaires comme au POC
(écarté : les titres courants suffisent et ne coûtent rien) ; description des figures des natifs par vision
(reporté : doublerait le coût, à décider à l'usage) ; chunking plus fin qu'une page (reporté : la page est l'unité
citée et affichée).

**Owner:** Adrien. Reste à ingérer quand le plafond OpenAI le permet : Manuel Frigobase (406 p.), Électrotechnique
(1 238 p.), Moteurs mono (18 p.), fin de Certif prépa (49 p.) ≈ 11 à 12 $ ; les deux cours EFPME en Word à convertir.

## 2026-10-06 — Bibliothèque entièrement ingérée (46 documents, 5 517 pages) ; quatre correctifs d'ingestion

**Decision:** L'ingestion est terminée : 46 documents, 5 517 pages, toutes vectorisées, 763 Mo de pages images sur le Go
gratuit de Supabase. Quatre correctifs sont intégrés aux scripts : (1) `shared/savoir.texte_propre` neutralise les
caractères nuls et les espaces de largeur nulle (conversion Word → PDF) que Postgres refuse ; appliqué à l'extraction du
texte natif, à la lecture du cache au chargement et aux titres de sections. (2) `ingerer.py` conserve la dépense OCR d'un
document dont le chargement échoue ensuite (bilan et budget de l'exécution justes). (3) `sections.py` : les numéros de
page lus par l'OCR sont validés contre la médiane locale des écarts PDF − imprimé (un numéro de figure ne peut plus
étirer une section sur mille pages), le titre courant du livre lui-même et les rubriques récurrentes (« Solution »,
« Notes personnelles », « Sommaire ») ne font pas de section, un titre numéroté « 40.14 … » lu en `#` est un sous-titre.
(4) Index sur les clés étrangères `savoir_pages.section_id` et `savoir_sections.parent_id` (schéma + appliqué) et
suppression des sections par lots de 300 : sans cela, remplacer les 1 733 sections d'un livre dépasse le délai PostgREST.

**Why:** Coût réel mesuré : 1 711 pages scannées pour 11,22 $ (0,0066 $/page ; estimation 11,2 à 12,7 $), total OCR de
la bibliothèque ≈ 22,4 $. Les deux cours EFPME convertis depuis Word portaient des puces en caractère nul sur toutes
leurs pages (erreur 22P05). Électrotechnique : 1 733 sections dont des sections de 1 100 pages (97 numéros de page lus
faux sur 1 238, « ÉLECTROTECHNIQUE » en titre courant sur 159 pages) → 1 252 sections, la plus longue 42 pages ; Kotza
régénéré avec les nouvelles règles et identique sur ses 9 pages de contrôle.

**Alternatives considered:** sommaire structuré par le modèle pour Électrotechnique (écarté : les titres courants
corrigés suffisent et ne coûtent rien) ; réduire la résolution des pages déjà chargées pour gagner du stockage (reporté :
≈ 240 Mo restent ; le prochain livre scanné se chargera en 800 px ou le projet passera au plan payant).

**Owner:** Adrien. Reste : remplacer le zip `froid-question` sur son claude.ai ; retours de Loïc à l'usage.

## 2026-10-06 — Lot 2 livré : `froid-dimensionnement`, deux méthodes croisées depuis les plaques, sans polynômes ni abaque de volume

**Decision:** L'étape 2 du parcours (dimensionnement du remplacement) est construite : skill `froid-dimensionnement`
(`calculs.py` lit `2-entrees.json`, écrit `2-resultats.json` et `2-tableaux.md` ; modules `valeur.py`, `unites.py`,
`controles.py`, `fluides.py` (seul import CoolProp), `compresseurs.py`, `fgas.py` ; 124 tests unittest), socle
`dimensionnement/savoir/` (PRP, compositions des mélanges, table F-gas, méthode de la puissance existante, règles de
Loïc, matrice des transitions, fiche Bitzer, 306 points catalogue Bitzer publics) et convertisseur HTML commun
`shared/rendu_html.py` (le script du Lot 1 devient un adaptateur). **La puissance existante d'un compresseur vient
de deux méthodes croisées** : M1 par la cylindrée (volume balayé de la plaque, propriétés CoolProp, rendement
volumétrique par une table ajustée sur les catalogues Bitzer) et M2 par le point catalogue publié, converti au fluide
de l'installation et corrigé de régime ; l'écart entre les deux est le contrôle de vraisemblance. **Aucun nombre ne
sort du modèle** : chaque valeur est une `Valeur` qui porte sa source et son statut (sourcé, calculé, hypothèse, à
confirmer), et un résultat n'est jamais plus sûr que sa plus faible entrée. Le bloc réglementaire ne contient que le
texte rendu par `fgas.py`. **Pas de polynômes fabricants ni d'abaque de volume en V1** (décisions d'Adrien du
2026-10-06) : ils sont notés comme options futures avec le bilan thermique. CoolProp 8.0.0 est épinglé dans
`requirements.txt`. La table F-gas (48 règles) est marquée « non relue » tant que la colonne de relecture est vide.

**Why:** La méthode de Loïc part de la puissance existante, que les plaques ne donnent pas ; au stade de la remise de
prix, il faut un chiffre traçable avec une marge connue, pas l'exactitude d'un polynôme que seul un export humain par
modèle fournirait. Sur le dossier test, les deux méthodes se recoupent à moins de 8 % sur sept compresseurs, un
vérificateur indépendant a retrouvé les plaques à l'aveugle et recalculé deux compresseurs à moins de 0,01 %, et les
écarts avec les estimations antérieures (+23 %, +13 %, +2 %) sont décomposés et expliqués. Aucune table publique de
puissance par volume ne couvre les grandes chambres ; la seule table sourcée (Énergie+) a été jugée insuffisante. Le
rendement volumétrique des livres de Loïc (λ = 1 − 0,05 τ) sous-estime de 27 % en négatif face aux catalogues : la
table ajustée est le défaut, la formule des livres reste disponible, les deux sourcées. Construction menée par
sous-agents en trois vagues (cœur, socle, recherche ; calculs ; assemblage, vérificateur) pour préserver le contexte.

**Alternatives considered:** polynômes EN 12900 exportés des logiciels fabricants (option future : précision du mode
« exécution ») ; abaque de volume Énergie+ (refusé) ; bilan thermique détaillé (phase 2) ; lecture douteuse traitée en
« à confirmer » (rejeté : si le nombre utilisé est lisible, c'est une hypothèse écrite, sinon le calcul disparaît).

**Owner:** Adrien. Reste : relire la table F-gas, valider la table de rendement volumétrique, obtenir les réponses de
Loïc aux six questions (la convention de température du mélange pèse jusqu'à 15 % sur M2), retours de Loïc à l'usage.

## 2026-10-07 — Lot 3 livré : `froid-demande-fournisseur`, un PDF unique et un mail court, anonymisation contrôlée

**Decision:** L'étape 3 du parcours (demande de prix au fournisseur) est construite : skill `froid-demande-fournisseur`
(`assembler.py` lit les étapes 1 et 2 et écrit `demande.json` ; `generer_livrable.py` produit `demande-vN.html`,
`demande-vN.pdf` par Edge en mode sans tête et les mails `.txt` / `.html` ; `controler.py` vérifie anonymisation,
chiffres, plaques, poids, mail ; 74 tests), gabarits de textes repris mot pour mot des mails que Loïc envoyait à la
main, fiche `savoir/methodes/demande-fournisseur.md`, règles R9 à R13. **Le livrable est un PDF unique** (page de
garde, contexte, chambres à traiter, production frigorifique existante, évaporateurs, demande détaillée, un chapitre
par poste avec les photos des plaques légendées, annexes avec l'emplacement du plan d'implantation) **et un mail court
sans tableau** qui résume et renvoie au PDF. Deux variantes : grossiste (vouvoiement, client anonymisé par un
contrôle bloquant) et fabricant de centrale (tutoiement, chantier nommé, options techniques). Chaque chiffre vient de
l'étape 2 (`Valeur.texte()`), les questions internes (« à confirmer », « lesquels garder ») sont exclues du livrable et
listées pour Claude. Versions `vN` et `envois.md` ; **aucun envoi automatique, jamais** : Loïc relit et envoie.

**Why:** Choix d'Adrien du 2026-10-07 : « un mail avec un résumé, toutes les informations dans le PDF, plus aucun
tableau dans le mail », à la place de la pratique de Loïc (tableaux dans le corps du mail, PDF de photos seules de
11,9 Mo dont l'envoi avait échoué) ; c'est aussi ce qui avait été présenté à Loïc en visio le 28/09. Un vérificateur
indépendant a confirmé sur le dossier test : anonymisation étanche (identifiants cherchés jusque dans les métadonnées et
l'EXIF des 43 photos), chiffres identiques à l'étape 2, six légendes relues sur six justes, structures des mails du
16/09 et du 24/09 respectées ; PDF de 16 pages pour 2,5 Mo. Les corrections demandées (quantités dictées, note interne
partie chez le fournisseur, annotations de lecture dans les légendes) ont été appliquées. Edge imprime le PDF sans
logiciel supplémentaire. Pillow est utilisé pour redimensionner les photos avec un repli PyMuPDF : son ajout à
`requirements.txt` est en attente de la décision d'Adrien (il est déjà requis par `froid-savoir`).

**Alternatives considered:** page de tableaux HTML à coller dans Outlook (pratique de Loïc, écartée : option future
si un fournisseur la réclame) ; Word (rejeté : Loïc n'arrivait pas à l'ouvrir) ; envoi par Outlook ou par API (jamais) ;
`wkhtmltopdf` (nouvelle dépendance, inutile avec Edge).

**Owner:** Adrien. Reste : décision Pillow ; coordonnées de l'émetteur (`dossiers/emetteur.json`, local) à compléter
par Loïc ; questions 7 à 11 remises à Loïc à la livraison ; retours de Loïc à l'usage (ton, ordre des chapitres).

## 2026-10-07 — Lots 5 et 6 : plans 2D à l'échelle vérifiée (`froid-plan-2d`) et lecture des tracés photographiés

**Decision:** L'étape P du parcours (plan 2D, indépendante des étapes 1 à 3) est construite dans le skill
`froid-plan-2d`. Claude écrit un modèle en mètres (`plan/plan.json`, chaque cote avec sa source ; une cote manquante est
une question, jamais une estimation) ; les scripts dessinent `plan.drawio` (pages « Plan » et « Métré », un calque par
réseau), calculent le métré (longueur en plan + montées et descentes aux hauteurs de pose) et les croisements, rendent
`plan.pdf` et `plan.png`, et vérifient. **A4, une page, échelle normalisée choisie automatiquement** (1:50 à 1:1000,
la plus petite qui tient), barre d'échelle et règle de contrôle de 100 mm dans le cartouche, impression à 100 % :
**décision d'Adrien du 2026-10-07** (« les plans sont à l'échelle et l'échelle se vérifie »). **Vérification à trois
niveaux** (`verifier_plan.py`, 11 contrôles, 0 erreur exigée, 5 tours au plus) : le fichier draw.io relu et reconverti
en mètres = le modèle à 1 cm, la barre d'échelle à 0,5 px, **le PDF mesuré** (page A4, règle de 100 mm, barre et trois
plus longs murs, à 1 pt près au plus). **PDF par draw.io Desktop en ligne de commande, calibré sur la règle de 100 mm** (mesurée dans le PDF, facteur
corrigé puis revérifié à chaque rendu) ; secours Edge et viewer draw.io ; PNG = PDF rasterisé par PyMuPDF. Retouches à
la voix (Claude modifie `plan.json`) ou à la souris dans draw.io Desktop (`importer_drawio.py`). **Lot 6** : une
feuille A4 par réseau avec 4 **repères ArUco de 16 mm** aux coins ; Loïc trace au marqueur, photographie ;
`lire_photo.py` redresse par homographie, lit le trait, le convertit en mètres, l'accroche aux équipements et l'ajoute
au plan après son accord. **opencv-python ajouté** à `requirements.txt` (autorisé par Adrien le 2026-10-07), avec
numpy et Pillow. Tests en **unittest** (pytest absent). **Opus recommandé, pas forcé** : une phrase au début du skill
demande à Loïc de passer sur Opus avec `/model` ; pas de champ `model` tant qu'Adrien ne l'a pas tranché.

**Why:** Un métré faux, c'est du cuivre commandé en trop ou en moins ; un plan « à peu près à l'échelle » ne se mesure
pas au réglet sur chantier. L'export PDF de draw.io Desktop sort réduit de 0,245 % (mesuré sur ce PC) : seule une
mesure dans le PDF lui-même garantit l'échelle, et elle tient si draw.io change de version. L'A4 est le format de
l'imprimante de bureau ; l'échelle normalisée rend la barre et la règle lisibles. Les repères ArUco rendent la photo
indépendante de l'angle de prise de vue et d'une impression réduite : sur 218 photos synthétiques (perspective
jusqu'à 35°, flou, JPEG dégradé), écart de longueur au plus 0,80 %. Le modèle en mètres, unique source du dessin, du
métré et de la vérification, empêche qu'un chiffre retouché à la main diverge du dessin.

**Alternatives considered:** A3 ou échelle libre (1 m = 50 px de l'exemple du 28/09, soit un 1:78,74 non normalisé :
rejeté) ; export PNG de draw.io (cassé au-delà d'environ 2 500 px sur ce PC : rejeté) ; Edge + viewer en voie
principale (gardé en secours) ; lecture de photo sans repères (perspective non maîtrisée : rejetée) ; scikit-image pour
le squelette (nouvelle dépendance : remplacée par du numpy) ; champ `model: opus` forcé (repli silencieux si
indisponible : en attente d'Adrien).

**Owner:** Adrien. Reste : validation du Lot 6 sur 2 ou 3 feuilles imprimées et photographiées (à la fin, avec Adrien) ;
hypothèses en attente de Loïc (hauteurs de pose, seuil d'écart max(5 %, 0,30 m), accrochage au centre, marqueurs et
imprimante, A4 seulement, métré en page 2 : questions 13 à 18, règles R14 à R19) ; champ `model` ; branchement du métré
vers les étapes 2 et 3 (Lot 7).

## 2026-10-08 — Lot 7 livré : longueurs estimées ou mesurées, métré du plan dans la demande fournisseur, bout en bout validé en session neuve ; Opus forcé pour les plans

**Decision:** (1) Toute longueur de ligne est une **estimation d'après le plan**, sauf celle **mesurée sur chantier** par Loïc : la phrase d'estimation ouvre chaque métré, la marque « (mesurée) » n'apparaît que sur l'exception ; les diamètres et la charge de fluide sont **laissés au fournisseur**. Le plan écrit `plan/metre.json`, que la demande fournisseur reprend dans un chapitre « Longueurs de cuivre (estimées d'après le plan) » avec le plan du local en annexe ; sans plan, une ligne « longueurs non relevées ». (2) Le pipeline de chiffrage est validé **de bout en bout par un sous-agent sans contexte** (rapport de visite seul, Loïc absent, sans plan) : mêmes puissances que le dossier validé ; les frictions trouvées sont corrigées (scripts qui n'échouent plus en silence, contrôle des légendes, formats inter-étapes écrits, cas « Loïc absent », règle fluide unique). (3) Le skill `froid-plan-2d` **force Opus** (`model: opus`) et garde la phrase de recommandation pour Loïc. (4) Avant livraison : prix et prénoms retirés des textes, transcriptions d'appels supprimées du dépôt, clé Supabase anonyme remplacée par un placeholder dans `.env.example`, routeur racine à jour (étapes 1, 2, 3 et P).

**Why:** (1) décision d'Adrien du 2026-10-08 : un fournisseur doit savoir ce qui est mesuré et ce qui est estimé, et c'est son métier de fixer diamètres et charge. (2) Chaque étape avait été construite avec tout le contexte ; seule une session vierge montre ce que Loïc vivra. (3) La doc Claude Code confirme qu'Opus est le défaut du forfait Pro et que le repli est silencieux si le modèle manque : forcer ne coûte rien et ne bloque pas. (4) Rien de privé ni de secret dans un dépôt synchronisé chez le client.

**Alternatives considered:** longueurs dans le dimensionnement (l'étape 2 ne les utilise pas en V1: rejeté) ; diamètres calculés par le système (option future, tables de la base de savoir) ; bout en bout avec un plan ETS Denis (pas de cotes, jamais inventées : rejeté, chemin avec plan prouvé sur la boucherie) ; recommander Opus sans forcer (choisi le 2026-10-07, remplacé) ; garder la clé anonyme dans l'exemple pour simplifier l'installation (rejeté : règle des placeholders).

**Owner:** Adrien. Reste : Lot 8 (push des commits, `maj-aios`, zips des skills mobiles, installation chez Loïc avec draw.io et la vraie clé dans son `.env`, visio de prise en main, liste des 21 questions, facture du solde).

## 2026-10-08 — Lot 8 (1/2) — zips mobiles versionnés, mise à jour autonome avec sauvegarde, zone perso

**Decision:** (1) Les zips des 8 skills mobiles sont **versionnés** dans `skills-mobiles/` (et non plus dans `active/skills-zip/`, gitignoré) : `export_skills.py` n'exporte plus que la liste `MOBILES`, refuse un skill moteur et écrit des zips reproductibles (date fixe, ordre trié : un zip ne change dans git que si son contenu change) ; `skills-mobiles/README.md` dit à Loïc comment les recharger. (2) `maj-aios` devient autonome : `shared/scripts/maj_aios.py` copie chaque fichier du système modifié, supprimé ou renommé sur le PC de Loïc dans `active/sauvegarde-maj/<AAAA-MM-JJ-HHMM>/` (avec un `LISEZMOI.md`), le remet d'origine, retire de l'index un fichier seulement ajouté, tire en `--ff-only`, déplace (sans l'effacer) un fichier non suivi qui bloquerait un fichier entrant, puis dit si `requirements.txt` a changé et quels zips recharger. Commit local ou historique divergent : arrêt (code 3) sans rien toucher ; pas de remote : code 2. Jamais de `reset --hard`, `merge`, `push`, `clean` ni `commit`. 20 tests sur des dépôts git jetables. (3) **Zone perso** `perso/` (gitignorée sauf son README) pour tout ce que Loïc fait créer ou garder, `perso/demandes-a-adrien.md` pour les changements voulus dans le système, nouveau skill de Loïc dans un nouveau dossier `.claude/skills/<nom>/` : nouvelle section du routeur.

**Why:** Loïc a modifié des fichiers du système sans le savoir (son assistant a édité le guide et un journal) et sa mise à jour se bloquait depuis juin ; ses propres fichiers (annuaire, mails de demande de prix) n'avaient pas de place prévue. Adrien veut trouver les zips directement dans l'AIOS au moment de la mise à jour, sans envoi par mail.

**Alternatives considered:** régénérer les zips chez Loïc (dépendait de l'export local, rejeté) ; bloquer la mise à jour et faire nettoyer à la main en visio (rejeté : une seule fois, et il recommencera) ; `git stash` (invisible pour Loïc, rejeté).

**Owner:** Adrien. Reste : première mise à jour chez Loïc par amorce (son `maj-aios` actuel est l'ancien, cf. `reste-a-faire.md`), puis Lot 8 (2/2) : installation, clés, visio.

