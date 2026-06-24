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

## 2026-06-24 — `veille-niche` aligné sur `veille-quotidienne` (orchestrateur complet)

**Decision:** Réécrire `veille-niche` (jusqu'ici un `SKILL.md` minimal) sur le **modèle complet de
`veille-quotidienne`** de Master-content : dédup via veille-logs sur 2 jours → scraping multi-sources
en parallèle → évaluation par les 8 archétypes + scoring + filtre éditorial → Top 10 équilibré par
track → présentation structurée → sauvegarde du veille-log → `AskUserQuestion` → écriture en base.
**Sources retenues** (adaptées à la niche clim/PAC, pas IA) : (1) WebSearch Google/PAA, (2) WebSearch
actus aides/primes BE+FR, (3) forums/Reddit FR via Apify (nouveau `shared/scripts/scrape_forums.py`,
calqué sur `scrape_reddit.py` de MC). **Tracks** : `b2c` (particuliers, Insta/FB) / `b2b` (pro froid
commercial, LinkedIn) — équivalent du dual-track business/geek de MC. **Destination** : table Supabase
`idees` quand elle sera branchée, avec **fallback markdown `base-idees.md`** d'ici là (le skill détecte
le mode).

**Why:** Le skill standard ne câblait aucune source ni mécanique réelle ; `veille-quotidienne` est
éprouvé et data-driven. Réutiliser son architecture (dédup, archétypes, balance des tracks, research-log,
checkpoint humain `AskUserQuestion`) donne de meilleurs résultats qu'une idéation ad hoc. Le fallback
markdown respecte l'amorçage (Supabase/Apify bloqués tant que Loïc n'a pas créé ses comptes — Blocs 1
& 3bis). *Changerait d'avis si* la niche imposait des sources spécifiques (ex. forums métier dédiés)
au-delà de Reddit FR.

**Alternatives considered:** garder le skill minimal (rejeté : aucune source réelle, idéation pauvre) ;
porter aussi Twitter/GitHub/concurrents Instagram comme sources (rejeté : non pertinents pour clim/PAC) ;
écrire direct en Supabase sans fallback (rejeté : Supabase bloqué, casserait le skill aujourd'hui).

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
