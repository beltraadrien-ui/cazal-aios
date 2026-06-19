# Convention de build — AIOS Loïc Cazal (vocal + mobile-first)

> 📌 **Statut & rôle de ce fichier.** Doc de **scope projet + réflexion technique de départ** (brief).
> Ce n'est pas le manuel d'opération. Les **décisions d'archi** issues de ce doc sont désormais tracées
> dans [`decisions/log.md`](decisions/log.md) (source de vérité). Les **conventions de build** vivent
> dans [`.claude/build-conventions.md`](.claude/build-conventions.md). Le **reste à faire** est dans
> [`.claude/reste-a-faire.md`](.claude/reste-a-faire.md). Ici = le *quoi vendu* + le *pourquoi technique*.

## Ce qui doit être fait

> **Le périmètre ferme vendu à Loïc (800 €), tel qu'établi pendant l'appel de vente.** C'est la liste
> des composantes à livrer — le *comment* (sections suivantes) peut évoluer, mais ce *quoi* est l'engagement.
> Livraison **clé en main en 7 jours**, **tout lui appartient**, pilotage **mobile/vocal** au centre.

### A. Le socle de contexte global (la pièce maîtresse — créé une fois)
- [ ] Espace de contexte rassemblant **identité de l'entreprise, voix & ton, ICP, offres, contraintes**
      (ce qu'il ne veut PAS) — l'actif portable qui rend la production « non-IA », chargé dans le mobile ET l'engine.

### B. Système 1 — Création de contenu *(sa priorité n°1, « d'office »)*
- [ ] **Scripts de réels Instagram** (cible ~1 tous les 2 jours), pilotables **au vocal + photos de chantier**.
- [ ] **Articles de blog** (1/semaine), humanisés (fini le « ChatGPT générique »).
- [ ] **Posts Google My Business** (1/semaine, format court).
- [ ] **Posts de réalisations sur le site** (1/semaine, format avant/après).
- [ ] **Base d'idées de contenu** + génération d'**angles** par idée.
- [ ] **Veille / propositions d'idées** automatiques.
- [ ] **Analyse de performance** : scraping de comptes qui « pètent » → ce qui marche (hooks, durées,
      sujets), avec **auto-amélioration** (le système apprend des données réelles).

### C. Système 2 — Résumés vocaux / devis *(le « deuxième système »)*
- [ ] **Skill de résumé structuré** : un vocal → résumé **toujours sous la même forme figée**
      (résout son irritant : ChatGPT change la structure à chaque fois).
- [ ] Couvre **récap de visite avant-devis, réunion de chantier (archi), dépannage** (même skill, variantes gérées).
- [ ] ⛔ **On ne fait PAS ses devis** (Interfast déjà rodé) et **on ne branche PAS Interfast** — il colle le résumé à la main.

### D. Accompagnement (inclus dans le prix)
- [ ] **Formation** : plusieurs visios d'1h (faites devant lui, il manipule).
- [ ] **Support WhatsApp** perso pendant **1 an**.
- [ ] Côté Loïc : **Claude Pro 20 €/mois** (utilisation seule) — confirmé.

### Hors-scope (établi comme évolution future, PAS dans les 800 €)
- ⏳ **Prospection** LinkedIn / cold email (syndics de copro, ~500 € en plus, 3ᵉ espace de travail).
- ⏳ **Génération vidéo** (type Nano Banana / vidéos immo avant-après) — branchable plus tard.

---

> ⚠️ **Premières idées, rien n'est figé.** Ce document capture la réflexion technique de départ sur
> *comment* faire fonctionner l'environnement de Loïc (vocal, mobile). Si on trouve une meilleure
> solution en cours de route, **on l'utilisera** — ceci n'est pas un engagement gravé dans le marbre.

## Contexte

Loïc (frigoriste, Belgique) a acheté un environnement de dossiers : socle de contexte + 2 systèmes
(création de contenu + résumés vocaux). Exigence forte : **bosser majoritairement depuis son téléphone,
au vocal, sans taper**. Tension : on a vendu « tout vit dans un environnement type Claude Code » — or
Claude Code n'est pas une surface mobile/vocale. Ce doc tranche cette tension.

> 🔄 **MISE À JOUR (2026-06-19) — lire ceci avant la suite.** Le mécanisme mobile décrit plus bas
> parle de **« Projets »** : c'est **dépassé**. Architecture retenue (cf. `decisions/log.md`,
> 2026-06-19, test mobile réussi) : la surface mobile = des **Skills custom uploadées sur le compte
> claude.ai de Loïc**, déclenchées dans un **chat normal** (tél ou desktop, sans PC allumé, sans
> Dispatch). Partout ci-dessous, **lire « Projet » comme « Skill custom uploadée sur le compte »**.
> Différence majeure : une skill claude.ai **a du code execution + un filesystem (éphémère) + réseau
> variable** — contrairement à un Projet (Knowledge seul). L'idée surface/engine ci-dessous **reste vraie**.

## L'idée-clé : séparer la *surface de capture* de l'*engine*

| Couche | Où ça tourne | Ce que ça fait | Pour Loïc |
|---|---|---|---|
| **Surface capture/consommation** | **App Claude** (mobile + desktop) — **Skills uploadées sur le compte** | contexte → texte : vocal in, post/résumé out, photos jointes | C'est là qu'il vit, ~80 % de l'usage quotidien |
| **Engine** | **Le dossier (repo)** sur PC (Claude Code / Cowork) + n8n + Supabase/Markdown | scripts, scraping concurrents, base d'idées, analyse de perf, veille | Il n'y touche pas — ça tourne en coulisse, il consomme les résultats |

**Le folder de contexte vendu = l'actif portable.** Il vit dans le **repo** (atelier de build), et ses
morceaux utiles sont **bundlés dans le zip** des skills publiées sur le compte de Loïc. C'est la
promesse « indépendant d'un outil ».

## Distinction critique à ne pas survendre

- Surface mobile = **Skill custom uploadée sur le compte claude.ai** : a du code execution + un
  filesystem **éphémère** (ressources bundlées dans le zip) + un **réseau variable**. Suffisant pour
  le contexte→texte ; **pas** pour du scraping lourd ou des appels réseau garantis.
- Engine = le **dossier** sur PC (Claude Code / Cowork) : skills `SKILL.md` + scripts qui s'exécutent
  vraiment, réseau garanti. C'est là que vit l'asynchrone (scraping, distillation du digest).
- **Pas de sync entre les deux** : modifier une skill dans le repo n'update PAS celle du compte de
  Loïc → il faut **re-zipper + re-uploader** (le « process de publication »).

→ « une phrase courte déclenche un workflow » est vrai au mobile **seulement pour les tâches
contexte→texte**. Les workflows à scripts lourds/réseau se déclenchent côté engine, en asynchrone.

---

## Système 1 — Résumés vocaux (le plus simple : 100 % mobile, SANS Claude Code)

Un **Projet Claude « Cazal — Résumés »** dont les *custom instructions* contiennent LE template figé
(titre / contexte / mesures / matériel / prochaines étapes…). Résout nativement son irritant (ChatGPT
change la structure à chaque fois).

**Sur le chantier :** ouvre l'app → Projet « Résumés » → tape le micro → parle → résumé toujours dans la
même structure → copie-colle dans Interfast / Drive (atterrissage à caler avec lui).

> Toit bruyant : privilégier la **dictée** (enregistre/transcrit) plutôt que le voice mode temps réel.
> Couvre récap avant-devis, réunion archi, dépannage (même Projet, le template gère les variantes).

## Système 2 — Création de contenu (hybride : mobile + engine)

### Couche mobile (vocal, contexte→texte) — Loïc pilote lui-même
Projet « Cazal — Contenu / Reels » avec la **voix de marque** chargée en Knowledge. Joint les photos du
chantier depuis la pellicule (natif dans l'app), dicte la prestation → sort le texte/script à valider.

### Couche engine (PC/cloud, asynchrone) — en coulisse
- **Base d'idées** (Airtable) — consultable sur mobile via l'app Airtable.
- **Analyse de perf concurrents** (scraping IG → Supabase ou markdown, hooks/durées qui marchent).
- **Veille / propositions d'idées** — périodique.
- **Auto-amélioration** : les apprentissages redescendent comme contexte rafraîchi dans le Projet.

---

## Workflow détaillé — « Script de reel sur chantier »

### 1. La surface : Projet Claude mobile (pas Claude Code, pas Cowork)

- **Projet Claude mobile** → vocal natif + photos jointes natives + aller-retour 30 s. Le seul qui réunit
  les trois. ✅
- **Claude Code mobile via GitHub** → voit tout le repo (rapport de perf en live) mais joindre des photos
  = les pousser dans git, et vocal moins natif. Mauvaise UX terrain. ❌ pour la capture.
- **Claude Cowork** → agent cloud async pour tâches longues (relancer le scraping). Outil d'**engine**,
  pas de capture. ❌ ici.

### 2. Comment l'IA « voit » le rapport de perf quand elle écrit

Le rapport est **dynamique** ; un Projet mobile **ne requête pas Supabase en live**. Mécanisme :

**Le rapport de perf entre dans le Projet comme fichier de Knowledge** → chargé à chaque message →
garantie d'accès, sans appel live. Ce fichier n'est PAS la base brute : c'est un **digest opérationnel
court** (1-3 pages) : *hooks qui performent dans la niche + niches voisines, durées qui marchent,
structures gagnantes*. Ça tient largement dans un Knowledge.

### Supabase vs Obsidian/Markdown : les deux, à des étages différents

- **Supabase** = couche brute/analyse de l'engine (scraping à grand volume, sémantique — pattern déjà
  utilisé par `ask-about-content`).
- **Markdown / Obsidian** = le **digest** qui nourrit le Projet. L'engine distille un
  `rapport-perf-digest.md` (style wiki, comme `Master-content/Youtube-content`) → c'est CE fichier qu'on
  met dans le Knowledge du Projet.
- **On peut démarrer 100 % markdown** (scraping → `rapport-perf-digest.md`, pas de Supabase au début) et
  ajouter Supabase seulement quand le volume le justifie. Moins de pièces, cohérent avec le pattern wiki.

### Le workflow complet

**Loïc (sur chantier) :**
1. App Claude → Projet « Cazal — Reels ».
2. Joint 3 photos + micro : *« remplacé un compresseur sur une chambre froide de boucherie, fais-moi un
   script de reel. »*
3. Le Projet a en Knowledge : `voix-de-marque.md` + `format-reel.md` + **`rapport-perf-digest.md`**.
4. → script face-caméra (hook + corps + CTA) calé sur ce qui performe.

**L'engine (invisible, ~1×/semaine) :**
- Claude Code/n8n scrape les concurrents → (Supabase brut) → distille `rapport-perf-digest.md` → met à
  jour le Knowledge du Projet (ré-upload manuel au début, automatisable via API ensuite).
- La fréquence hebdo suffit : entre deux rafraîchissements, des dizaines de scripts sur le même digest.

---

## Le pont voix-mobile ↔ engine-scripts — 3 niveaux d'ambition

- **A. Contexte → texte = app mobile, zéro pont.** Résumés + génération posts/scripts. ~80 % de l'usage. ✅
- **B. Scripts/données = engine en fond, résultats redescendus.** Asynchrone (scraping = 1×/sem). ✅
- **C. « Vocal sur chantier → déclenche un vrai script ».** Nécessite un pont (note vocale → webhook n8n,
  ou Cowork cloud). Le plus fragile, **hors du besoin réel → à reporter**, ne pas le promettre.

## Points de friction à anticiper (avant la formation)

1. **Sync contexte mobile ↔ repo** : faire évoluer la voix de marque dans le repo n'update pas le Projet
   mobile automatiquement → prévoir un mini-process de « publication contexte → Projet ».
2. **Ré-upload du digest de perf** : automatiser plus tard ; au début, manuel (~30 s/semaine).
3. **Historique photos/réalisations** : les photos jointes dans l'app ne sont pas stockées → si on veut
   un historique pour le site, les déposer aussi dans Drive.
4. **Abonnement** : Claude Pro 20 €/mois suffit pour la surface mobile ; l'engine est côté Adrien.
5. **Ne pas survendre le « tout au vocal »** : le vocal pilote la capture et la génération de texte, pas
   l'analyse de perf en temps réel.

## Verdict (provisoire)

- Les **deux systèmes vendus sont faisables**, dont le plus important (résumés + posts/scripts au vocal
  depuis le tél) **sans même Claude Code** — juste des Projets bien instruits dans l'app mobile.
- Claude Code / n8n = salle des machines d'Adrien pour l'engine, pas l'interface de Loïc.
- L'actif portable = le folder de contexte, chargé dans les deux mondes.
- Le morceau vraiment ambitieux (script déclenché à la voix depuis le chantier) est hors besoin réel et
  reportable.

## Comment vérifier avant de figer

- Tester un **Projet « Résumés » vide** avec le template figé sur 2-3 vocaux réels de Loïc → la structure tient ?
- Tester **joindre 3 photos + vocal « fais-moi un post/script »** dans un Projet « Contenu » avec un
  brouillon de voix de marque + un faux `rapport-perf-digest.md` → vérifier le rendu mobile.
- Ces deux tests valident la faisabilité mobile **avant** de construire l'engine.

---

*Statut : brouillon de réflexion (2026-06-18). À challenger et faire évoluer librement.*
