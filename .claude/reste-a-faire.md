# Reste à faire — AIOS Cazal Réfrigération

> Source unique de **ce qu'il reste à construire**. Toute tâche (fonctionnalité, branchement,
> correction, rangement) vit ici. On coche au fur et à mesure. En **mode build**, Claude lit ce
> fichier pour savoir « où on en est », et le met à jour en fin de build.
>
> Le *quoi vendu* et le *pourquoi technique* sont dans
> [`../convention-build.md`](../convention-build.md). Le *pourquoi des décisions* est dans
> [`../decisions/log.md`](../decisions/log.md). Le *comment construire* est dans
> [`build-conventions.md`](build-conventions.md).

## Légende
- `[ ]` à faire · `[~]` en cours · `[x]` fait. Ordre conseillé : Bloc 0 → 2 → 1 → 3 → 4 → 5.

---

## Bloc 0 — Hygiène repo + balises du mode build
- [x] Repo Git Cazal autonome (lien vers nateherkai/AIS-OS coupé).
- [x] 5 décisions d'archi loggées dans `decisions/log.md`.
- [x] Fichiers bruts archivés (transcripts + appel de cadrage) ; `convention-build.md` annoté.
- [x] `reste-a-faire.md` créé (ce fichier).
- [x] `build-conventions.md` créé.
- [x] Section « mode utilisation vs mode build » ajoutée à `CLAUDE.md`.

## Bloc 1 — Connections (débloque le reste)
- [ ] **Apify** : brancher le token (compte créé, user `Loïc_Cazal`) + `references/apify-api.md`.
- [ ] **Supabase** : créer/connecter la base contenu (ou rester 100 % markdown au début, cf. décision).
- [ ] **Claude Pro** souscrit côté Loïc + **Wispr Flow** installé sur son PC Windows.
- [ ] Mettre à jour `connections.md` (mécanisme + auth + fraîcheur) à chaque branchement.

## Pont mobile (transverse — cf. decisions/log.md 2026-06-19)
- [x] Tester qu'une skill custom uploadée se déclenche depuis l'app mobile (skill `test-pont-mobile`). ✅
- [ ] Supprimer la skill jetable `test-pont-mobile` du compte claude.ai + l'archiver dans le repo.
- [ ] Pour chaque skill métier : la **publier** = zip + upload sur le compte claude.ai de Loïc (re-upload à chaque modif).

## Bloc 2 — Système Résumés vocaux / devis (quick win, usage mobile)
- [ ] Rédiger LE **template figé** de résumé (titre / contexte / mesures / matériel / prochaines étapes…).
- [ ] Construire le skill **`resume-vocal-devis`** (SKILL.md + template bundlé), zippable pour le compte de Loïc.
- [ ] Gérer les variantes (récap avant-devis / réunion archi / dépannage) dans le même skill.
- [ ] Tester sur 2-3 vocaux réels de Loïc → la structure tient ? (validation humaine avant de figer).

## Bloc 3 — Système Création de contenu (hybride mobile + engine)
> Design + roadmap : plan approuvé `~/.claude/plans/lit-le-fichier-build-floofy-swan.md`. Architecture
> 3 étages (moteur perf → idéation → scripting), data-driven, règle d'or nuancée (ré-angler, pas bannir).

**Socle de contexte portable (assets bundlés) :**
- [x] `references/framework-hook.md` (framework Kallaway porté, adapté grand public).
- [x] `references/angles-signature-cazal.md` (angles signature + filtre éditorial).
- [x] `references/format-reel.md`, `format-article.md`, `format-gmb.md`, `format-realisation.md`.
- [x] `references/rapport-perf-digest.md` + `base-idees.md` (état amorçage, remplis par l'engine).
- [ ] Finaliser `references/voice.md` : scraper 29 articles blog + vidéos FB → mode échantillons (bloqué : besoin scrape).

**Skills construits (double version repo + zip) :**
- [x] Moteur : `scraper-contenu-cazal`, `rapport-performance`, `rapport-concurrents`.
- [x] Idéation : `veille-niche` (réécrit 2026-06-24 = orchestrateur complet calqué `veille-quotidienne` : multi-sources + dédup veille-logs + scoring + Top 10 + `AskUserQuestion` ; sources WebSearch Google/PAA + actus aides/primes + forums Reddit FR via `shared/scripts/scrape_forums.py` ; destination Supabase `idees` avec fallback `base-idees.md`), `idee-contenu` (liste → choix idée → choix format → variations).
- [x] Scripting : `script-reel-chantier` (A/B/C), `generateur-hooks`, `scripter-reel`, `rediger-article`.
- [x] `.env` (placeholders), `shared/config.py`, `shared/scripts/{scrape_instagram_apify,export_skills}.py`.
- [x] Zips générés (slashes `/`, références bundlées) ; depuis le 2026-10-08 dans `skills-mobiles/`, versionnés.

**Reste à activer (dépend de Loïc) :**
- [ ] Remplir les clés API dans `.env` (Apify + OpenAI) → débloque le moteur.
- [ ] 1ᵉʳ run moteur : `scraper-contenu-cazal` → `rapport-performance` + `rapport-concurrents` → digest réel.
- [ ] Tester `script-reel-chantier` sur un vrai chantier (vocal + photos) depuis le mobile.
- [ ] Upload des zips sur le compte claude.ai de Loïc (Réglages ▸ Fonctionnalités).
- [ ] (Plus tard) Veille auto enrichie ; Supabase si le volume l'exige.

## Bloc 3bis — Migration Supabase (base de données contenu) — 🟢 FAIT (sur le compte d'Adrien), à recopier chez Loïc
> Décision : base contenu en **Supabase** (table unique Performance + Idées). Spec :
> [`../MIGRATION-SUPABASE.md`](../MIGRATION-SUPABASE.md). SQL : [`../shared/sql/schema.sql`](../shared/sql/schema.sql).
> Décisions : `decisions/log.md` (2026-06-22). **Construit et testé en réel sur le projet Supabase
> d'Adrien `Cazal-1` (ref `ulhdjyhckvamjwmjncwy`)** le 2026-06-24. À recopier sur le compte de Loïc
> plus tard (mêmes tables, changer URL + clés dans `.env`).

- [x] SQL exécuté sur Supabase (`schema.sql`) : 5 tables + vue `contenu_avec_scores` + trigger + RLS. Vue & trigger **testés en réel**.
- [x] `.env` : `SUPABASE_PROJECT_URL` + `SUPABASE_ANON_KEY` + `SUPABASE_ACCESS_TOKEN` remplis (compte Adrien). `pip install -r requirements.txt` fait (supabase-py + openai).
- [x] Plomberie : `shared/config.py` (loader walk-up exposant les vars), `shared/database.py` (supabase-py + wrappers CRUD), `requirements.txt`. **Connexion testée** (`python -m shared.database`).
- [x] Scripts atomiques : `shared/scripts/search/list_contenu_scores.py` (testé), `post/insert_idee.py` (testé), `post/upsert_contenu_apify.py` (attend `APIFY_API_TOKEN`), `ai/analyser_contenu.py` + `prompts/gpt_hook_analysis.txt` (attend `OPENAI_API_KEY`).
- [x] Skills moteur branchés Supabase : `scraper-contenu-cazal`, **`analyser-contenu`** (NOUVEAU), `rapport-performance`, `rapport-concurrents`. `veille-niche` (écrit `idees` via MCP, ta version). Zips régénérés.
- [x] `idee-contenu` : lit `idees` via connecteur Supabase MCP (fallback snapshot). Skills scripting inchangés.
- [x] **(2026-06-24)** `rapport-performance` réécrit sur le modèle `rapport-performance-shortform` de Master-content : **rapport riche multi-sections affiché DANS LE CHAT** + sauvegarde `.md` daté + régénération digest. Script `list_contenu_scores.py` élargi (expose `hook_framework`, `content_type`, `call_to_action`, `topic_summary`, `reach`, `avg_watch_time`…). Dimensions vides (`duration`/`visual_format`/`text_hook`/`content_structure`) = stubs « à venir ». Décision loggée.
- [x] **(2026-06-24)** Seed initial : les 17 idées de `base-idees.md` insérées dans `idees` (7 manuelle + 10 veille, toutes `statut='idée'`) → Mode Supabase de `idee-contenu` opérationnel sans attendre Apify. Décision loggée.
- [x] **(2026-06-24)** Nouveau skill **`ajout-idee`** (capture à la volée → normalise → insère via `insert_idee.py`, pas MCP). Engine PC only. SKILL.md créé.
- [x] **(2026-06-25)** `veille-niche` : Reddit (Apify) **auto dès que `APIFY_API_TOKEN` SET** (statut `off` = MISSING/plantage seulement) + nouvelle colonne `idees.source_url` (ALTER live) → source **cliquable** par idée (URL réelle ou lien recherche Google) en sortie chat + Supabase. `insert_idee.py` + `schema.sql` à jour ; snapshot `base-idees.md` inchangé (choix Loïc). Décision loggée.
- [x] **(2026-07-20)** `analyser-contenu` **v3 — analyse visuelle par Claude CLI** (clonée de
      Master-content, façon claude-video, SANS le plugin marketplace) : frames hook-dense (ffmpeg,
      2 fps sur 0-4 s + 4 frames body, 512 px, dans `active/_visual_<id>/`) lues par `claude -p`
      headless (`shared/scripts/ai/call_claude.py`, prompt `claude_visual.txt`) → `text_hook`,
      `visual_hook`, `visual_format`, `audio_hook` + `duration` (ffprobe). Échec → champs null,
      jamais de fallback (`sans_visuel`). **Gemini retiré** (config, docs — n'était branché nulle
      part). Les contenus analysés avant cette date ont les visuels à null (backfill possible).
- [ ] **(reste)** Remplir `APIFY_API_TOKEN` + `OPENAI_API_KEY` dans `.env` → débloque scraper + analyser → 1ᵉʳ run moteur réel.
- [ ] **(reste)** Plus tard : recréer le schéma sur le **compte Supabase de Loïc** + basculer URL/clés du `.env`.
- [x] **(2026-07-19)** Connecteur Supabase MCP **côté Adrien** : en place sur son compte claude.ai (Desktop/mobile, OAuth ; reco `read_only=true&project_ref=…`). SKILL.md `idee-contenu`/`ajout-idee` ajustés au mode lecture seule, zip `idee-contenu` régénéré (à ré-uploader). Décision loggée.
- [x] **(2026-07-19)** Table **`syntheses`** (digest-perf + rapports datés) créée en live + `schema.sql` §9 : les skills de surface lisent le digest **en live** via le connecteur MCP (fallback snapshot bundlé) ; les skills moteur poussent en fin de run (`upsert_synthese.py`) ; lecture engine `get_synthese.py`. Seed 2026-06-24 fait. **Le re-zip ne sert plus qu'aux changements de logique des skills, plus aux données.** 6 zips régénérés (idee-contenu, script-reel-chantier, scripter-reel, generateur-hooks, rediger-article, veille-niche) → à ré-uploader sur claude.ai. Décision loggée.
- [ ] **(phase 2, PAS à la livraison)** Connecteur Supabase sur le claude.ai de **Loïc** — reporté (cf. decisions/log.md 2026-07-19) ; à activer seulement sur frustration réelle (idées périmées mobile / capture en mobilité), après migration du schéma chez lui.

## Bloc 3ter — Poller de KPIs — 🟢 SCRIPT FAIT & TESTÉ ; reste la routine locale
> Automate qui rafraîchit périodiquement les KPIs (`contenu`), les stats (`compte_stats`) et écrit un
> snapshot quotidien (`contenu_snapshots`). Réf. Master-content `lessons/1.6-instagram-poller/`.
> **`shared/scripts/post/poller.py` construit et testé en réel le 2026-06-24** (compte own
> `cazal_refrigeration`, 5 reels → 5 contenu + 5 snapshots + `compte_stats` via trigger, 0 erreur).
> `fetch_posts_apify()` factorisé dans `upsert_contenu_apify.py` (partagé scraper ↔ poller).

- [x] `poller.py` : own only (`type='own'`), reels only, upsert idempotent + snapshot du jour, résumé JSON, try/except par post.
- [x] Compte own de Loïc inséré dans `comptes` (`cazal_refrigeration`). 5 reels chargés (test quota-friendly `--limit 5`).
- [x] **(2026-07-20)** Poller **dual-mode** : Meta Graph si `META_ACCESS_TOKEN`+`IG_USER_ID` SET
      (module `shared/scripts/post/meta_graph.py`, port du n8n `ig-daily-poller` : media paginé +
      insights/reel, KPIs riches reach/saves/shares/watch time, ms→s), sinon fallback Apify inchangé.
      Sortie JSON avec `"source"`. Setup Meta côté Loïc : MIGRATION-SUPABASE.md § JOUR J bloc C-bis
      (optionnel, activable après coup). Décision loggée.
- [ ] **(reste)** Créer la **routine locale Claude** (Claude Desktop ▸ Routines ▸ Local) : nom `cazal-poller-kpis`,
      dossier `C:\GitHub\_environnement-test\Cazal-1`, planif **Quotidien**, instruction = `python shared/scripts/post/poller.py` +
      résumé 2 lignes. Faire un « Run now » + « toujours autoriser » python pour les runs silencieux.
- [ ] **(reste)** Backfill complet quand voulu : `python shared/scripts/post/poller.py --limit 121` (ou via
      `scraper-contenu-cazal`) pour charger tout l'historique des reels de Loïc (≈121).

**Relation scraper ↔ poller (clé du découpage).**
Le vrai axe n'est pas « own vs concurrent » mais **découverte (à la demande) vs rafraîchissement (récurrent)** —
les deux **partagent le même script** `shared/scripts/post/upsert_contenu_apify.py` :
- `scraper-contenu-cazal` (skill, **à la demande**) = premier import, **ajout d'un nouveau concurrent**,
  rattrapage. Lancé manuellement par Adrien quand il ajoute/élargit des comptes.
- **Poller** (**récurrent, automatique**) = re-passe sur les comptes **déjà suivis**, met à jour leurs
  KPIs et écrit le **snapshot du jour**. C'est « le même script, mais planifié ».

**Périmètre du poller : UNIQUEMENT le compte de Loïc (`type='own'`)** — exactement comme le poller de
Master-content (own only, via Meta Graph). Les **concurrents NE sont PAS** rafraîchis par le poller : ils
sont (re)scrapés **à la demande** via `scraper-contenu-cazal`. Donc `poller.py` lit `comptes WHERE
type='own'` et ne touche qu'à ces contenus.

> **Contexte d'exécution (décidé) : l'AIOS tourne sur le PC de Loïc.** Le poller est une **routine
> LOCALE lancée depuis son Claude** (Claude Desktop sur son PC), **pas dans le cloud**. Conséquence
> majeure : la routine lit le **`.env` local** → **plus aucun problème de secrets en cloud**.

- [ ] **Lancement = routine Claude LOCALE** sur le PC de Loïc, **cron quotidien** (ex. 7h). Remplace le
      workflow n8n de MC. (Confirmer au build le mécanisme exact de planification locale : skill
      `schedule`/`CronCreate` en mode local, ou Planificateur de tâches Windows déclenchant `poller.py`.)
- [ ] **Tokens minimes** : la routine ne fait que **déclencher** `shared/scripts/poller.py` (déterministe :
      Apify → upsert + snapshot) ; le LLM ne lit pas les payloads, résume en 2 lignes.
- [ ] **`poller.py`** : `SELECT comptes WHERE type='own'` → re-fetch leurs posts (Apify) → `upsert_contenu`
      (KPIs) + `insert_snapshot` du jour ; `compte_stats` rafraîchi par le trigger. **Concurrents exclus.**
- [ ] **Clés** : ✅ résolu par le local — `poller.py` lit le `.env` local (`SUPABASE_*`, `APIFY_API_TOKEN`).
      Aucun secret à pousser en cloud.
- [ ] **PC allumé** : seul prérequis du local. Cocher « exécuter dès que possible après un démarrage
      manqué » (Task Scheduler) ou équivalent pour rattraper si le PC était éteint à l'heure prévue.
- [x] **Source** : dual-mode construit (2026-07-20) — Meta Graph si token connecté (insights riches),
      sinon Apify (métriques publiques). Reste côté Loïc : le setup Meta (app + token, § JOUR J C-bis).
- [ ] Options de lancement à confirmer : **routine Claude locale + `poller.py`** (retenu) / Task Scheduler
      Windows + `poller.py` (repli simple, zéro LLM) / pg_cron Supabase (écarté : sort de « tourne dans Claude ») / n8n (écarté).

## Bloc 3quater — Distribution & maintenance via GitHub — 🟢 EN PLACE côté Adrien
> Décision : `decisions/log.md` (2026-06-24). Repo **GitHub privé `cazal-aios`** = source unique ;
> Loïc en a un clone, mis à jour via la skill **`maj-aios`** (`git pull --ff-only`, lecture seule).
> GitHub couvre l'**engine (PC)** ; le **mobile (zips claude.ai) reste en re-upload manuel** (pas
> d'auto-sync, limite produit).

- [x] Skill `maj-aios` créé (`.claude/skills/maj-aios/SKILL.md`) : `git pull --ff-only`, réinstall deps si
      `requirements.txt` change, signale les zips mobiles à ré-uploader. Ajouté au `BUNDLE` (engine, `[]`).
- [x] Repo GitHub **privé `cazal-aios`** créé (compte `beltraadrien-ui`) + push initial. `.env`/`active/` gitignorés (aucun secret poussé).
- [x] **(2026-07-20)** Déroulé d'installation figé → **§ « JOUR J » de `MIGRATION-SUPABASE.md`**
      (décisions loggées : clés API = les siennes ; données = copie de lignes via
      `shared/scripts/post/migrer_donnees.py`, dry-run testé, placeholders `CIBLE_*` posés dans le
      `.env` d'Adrien ; zips mobiles régénérés côté Loïc — `maj-aios` mis à jour).
- [ ] **(install chez Loïc, en visio)** dérouler le § « JOUR J » de `MIGRATION-SUPABASE.md`
      (PC + GitHub → base Supabase à lui + copie des données → zips + connecteur → tests de sortie).
- [ ] **(quotidien)** Boucle : Adrien `commit`+`push` → Loïc « mets à jour mon AIOS » (`maj-aios`) →
      si un zip de `skills-mobiles/` a changé, `maj-aios` le signale et guide Loïc pour le
      recharger sur SON claude.ai.

## Bloc 4 — Process & friction (avant la formation)
- [ ] Mini-process « publication contexte repo → Projet mobile » (sync voix de marque).
- [ ] Process ré-upload hebdo du digest de perf (manuel d'abord).
- [ ] Historique photos/réalisations → dépôt Drive.

## Bloc 5 — Accompagnement (livrable inclus)
- [ ] Visios de formation 1h (devant Loïc, il manipule).
- [ ] Canal support WhatsApp 1 an.

---

## Bloc 6 — Branche « dimensionnement » (v2 : chiffrage des remplacements d'installations frigorifiques, vendu le 2026-09-28)

Architecture validée le 2026-10-03 (cf. `decisions/log.md`). Manuel de branche : `dimensionnement/CLAUDE.md`.
Dossier test : ETS Denis (rapport InterFast IN01834 du 14/09/2026, local, jamais versionné).

- [x] **Lot 0** (2026-10-03) : arborescence `dimensionnement/`, 5 skills nommés, choix techniques (CoolProp, double index, abaque de volume, ETS Denis).
- [x] **Lot 1 — relevé de l'existant** (2026-10-03) : `dimensionnement/` (CLAUDE.md, `.gitignore` local, `savoir/INDEX.md`,
      `methodes/checklist-releve.md`, `materiel/lecture-plaques.md`) ; skill `froid-releve-existant` + `scripts/extraire_rapport.py`
      (PyMuPDF ajouté à `requirements.txt`) ; test ETS Denis : 9 postes, 43 photos, 7 compresseurs et 7 évaporateurs lus,
      concordance avec la conversation Claude de Loïc du 16/09 ; double lecture par sous-agent vérificateur. **Validation d'Adrien ✋ en attente.**
- [x] **Lot 4 — base de savoir** (2026-10-05, validé par Adrien le 2026-10-06 : réponses sourcées depuis le téléphone, coût réel OpenAI 11,18 $) : skill `froid-savoir` (catalogue, pages, OCR OpenAI sous budget, sections par titres
      courants, chargement Supabase, recherche PC, carnet, index mobile), `shared/savoir.py`, `shared/sql/schema_savoir.sql`,
      skill mobile `froid-question` final (zip). **Ingestion terminée le 2026-10-06 : 46 documents, 5 517 pages, 763 Mo / 1 Go, OCR 22,4 $ au total.**
      Stockage : ≈ 240 Mo restants sur le plan gratuit → prochain livre scanné en 800 px ou plan payant. Retours de Loïc sur les réponses mobiles.
- [x] **Lot 2 — dimensionnement** (2026-10-06, commit 103d164) : skill `froid-dimensionnement` (puissance existante par cylindrée et point catalogue,
      F-gas, `Valeur` sourcée, 124 tests), socle v1 (`prp.csv`, F-gas **non relue**, méthode, règles de Loïc, transitions, Bitzer, 306 points
      catalogue), `shared/rendu_html.py`, CoolProp 8.0.0 épinglé. Pas de polynômes ni d'abaque de volume en V1 (options futures).
      Reste : Adrien juge la vue HTML du dossier test ✋, relit la table F-gas, valide la table de rendement volumétrique ; réponses de Loïc aux six questions.
- [x] **Lot 3 — demande fournisseur** (2026-10-07, commit 66f122b) : skill `froid-demande-fournisseur` (PDF unique anonymisé par Edge + mail court sans tableau, deux variantes grossiste / fabricant, `controler.py`, 74 tests), socle `demande-fournisseur.md`. Reste : Adrien relit le PDF ETS Denis ✋, tranche l'ajout de `pillow` à `requirements.txt` ; `dossiers/emetteur.json` à compléter par Loïc ; questions 7-11 à la livraison.
- [x] **Lots 5 et 6 — plans 2D** (2026-10-07, commit 493204e) : skill `froid-plan-2d` (plan A4 à échelle normalisée dans draw.io, métré, croisements, `verifier_plan.py` à 11 contrôles jusque dans le PDF, import des retouches à la souris, feuille à repères ArUco + lecture des photos de tracés, 471 tests), méthode `plan-2d.md`, règles R14-R19, étape P du manuel. Page de lecture refaite après retour d'Adrien (commit 1fcbd94) ; première photo réelle lue, stylo bille et basse résolution (commit 43a8aac), réseau d'eau glacée intégré à la boucherie v8. Reste : original de la photo en pleine résolution ; champ `model` à trancher ; questions 13-21 à la livraison.
- [x] **Lot 7 — intégration et bout en bout** (2026-10-08, commits ec57149 et 4b9ebda) : longueurs estimées / mesurées, métré du plan vers la demande fournisseur (chapitre + annexe plan), ETS Denis rejoué en session neuve sans contexte (mêmes chiffres), scripts durcis et manuels complétés. Reste : `CLAUDE.md` racine ligne 45 (« à venir ») à corriger par Adrien.
- [ ] **Lot 8 — livraison** chez Loïc (`maj-aios`, clés à lui, connecteur Supabase + accès réseau sur son claude.ai, zip `froid-question`, visio).
  - [x] **(2026-10-08) Lot 8 (1/2)** : zips des 8 skills mobiles versionnés dans `skills-mobiles/` (liste `MOBILES`
        de `export_skills.py`, zips reproductibles) ; `shared/scripts/maj_aios.py` (mise à jour autonome : fichiers
        du système modifiés mis de côté dans `active/sauvegarde-maj/`, `pull --ff-only`, zips à recharger ; 20 tests)
        branché dans `maj-aios` ; zone perso `perso/` (gitignorée sauf son README) décrite dans le routeur.
  - [ ] Première mise à jour chez Loïc : son `maj-aios` actuel est l'ancien (il s'arrête sur les fichiers modifiés).
        Lancer le nouveau script par amorce, dans Git Bash à la racine du dépôt : `git fetch origin && git show
        origin/main:shared/scripts/maj_aios.py > active/maj_aios_amorce.py && PYTHONUTF8=1 python active/maj_aios_amorce.py`.
- [x] `maj-aios` : ajouter `resume-vocal-devis` et `froid-question` à la liste des skills mobiles à ré-uploader
      (2026-10-08 : liste `MOBILES`, `maj-aios` signale les zips changés).

## Hors-scope (évolutions futures, hors du périmètre vendu)
- ⏳ Connecteur Supabase MCP sur le claude.ai de Loïc (phase 2 — cf. decisions/log.md 2026-07-19 ; activer sur frustration réelle uniquement).
- ⏳ Prospection LinkedIn / cold email (~500 € en plus, 3ᵉ espace de travail).
- ⏳ Génération vidéo (Nano Banana / avant-après immo).
- ⏳ Pont « vocal sur chantier → déclenche un vrai script » (le plus fragile, reportable).

## Bloc 6 — Mails fournisseurs et sous-traitants (outil de Loïc, 2026-10-08)
- [x] Skill `mail-fournisseurs-sous-traitants` (construit par Loïc, intégré par Adrien le 2026-10-08).
- [x] Annuaires `perso/fournisseurs.md` (6 fournisseurs) et `perso/sous-traitants.md` (4 groupes, 6 sous-traitants) :
      données de Loïc, sur son PC seulement.
- [x] Pas de version mobile (demandes de prix faites au bureau sur PC).
- [ ] Chez Loïc, après la mise à jour : déplacer les deux annuaires de `references/` vers `perso/` (le skill le
      propose à son premier lancement) ; compléter l'annuaire fournisseurs avec les coordonnées manquantes.
