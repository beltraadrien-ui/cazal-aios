# Appel de cadrage — Loïc Cazal (Cazal Réfrigération)

> **But de l'appel (1h)** : récolter TOUT ce qu'il faut pour construire son AIOS clé en main en 7 jours.
> Scope vendu = **socle de contexte global** + **système Création de contenu** + **système Résumés vocaux / devis**. (800 €)
> Prospection LinkedIn/cold email = hors-scope (évolution future).
>
> Méthode : croisement du skill `/onboard` du repo AIS-OS (7 questions → Four Cs) avec la structure de la couche Context `00-Contexte/`.
> **Règle d'or** : pour la voix/le ton, on ne devine RIEN — on récupère des **échantillons bruts** (jamais retapés en live). C'est le nerf de la guerre pour que ça « ne sonne pas IA ».

---

## 🎯 Avant de raccrocher, j'ai besoin de cocher tout ça

- [ ] **C1 — Context** : qui il est, sa boîte, sa voix, ses clients, ses contraintes
- [ ] **C2 — Connections** : tous les outils/comptes auxquels donner accès
- [ ] **C3 — Capabilities** : le détail des 2 systèmes à construire (contenu + résumés)
- [ ] **C4 — Cadence** : priorités 90 jours + le pain n°1
- [ ] **Logistique** : facturation belge + calage formation

---

## 1. CONTEXT — Identité & entreprise (le socle global)

> Sert à remplir l'équivalent de ses `entreprise.md`, `fondateur.md`, `icp.md`, `offres.md`.

### Entreprise
- [ ] Nom légal exact + nom commercial (Cazal Réfrigération ?)
- [ ] **Métier en une phrase** (frigoriste : froid commercial & industriel, clim, PAC — privé + pro)
- [ ] Zone géographique servie (Belgique frontière FR, près de Charleville — rayon ?)
- [ ] Composition équipe (3 techs plein temps + 1 admin tiers-temps + lui) — qui fait quoi
- [ ] Ancienneté de la boîte / depuis quand il est à son compte
- [ ] Site internet (URL exacte du site + du blog)

### Lui (le fondateur, la « voix »)
- [ ] Son rôle / ce qu'il fait au quotidien (100 % opérationnel : chantiers, devis, dépannage, prospection)
- [ ] Son parcours rapide (pourquoi frigoriste, depuis combien de temps dans le métier)
- [ ] Ce qui le différencie de ses concurrents (son angle, sa fierté métier)

### Clients (ICP) — pour qui il crée du contenu / à qui il parle
- [ ] **Qui sont ses clients** : particuliers ? pros ? restaurateurs ? supermarchés ? syndics ? archis ?
- [ ] Répartition / lesquels il veut développer
- [ ] Quels sont leurs problèmes / ce qu'ils cherchent quand ils l'appellent
- [ ] Quelles prestations rapportent le plus / lesquelles il veut vendre plus (clim, PAC, chambres froides, maintenance, dépannage)

### Offres / prestations (pour que le contenu pousse les bons sujets)
- [ ] Liste de ses prestations principales + lesquelles mettre en avant en contenu
- [ ] Saisonnalité (clim l'été, PAC l'hiver…)

---

## 2. CONTEXT — Voix & ton (PRIORITÉ ABSOLUE)

> Sans ça, le contenu sonnera générique. À récupérer en **brut**, pas reformulé.

- [ ] **Échantillons écrits bruts** — lui demander de m'envoyer par WhatsApp/mail :
  - [ ] 2-3 de ses **meilleurs posts** déjà publiés (Insta / site / Google) qu'il aime
  - [ ] 2-3 articles de blog déjà publiés (même s'il les trouve « bof » → me montre ce qu'il NE veut PLUS)
  - [ ] 1-2 exemples de **vocaux** qu'il s'envoie après chantier (pour caler le format de résumé)
- [ ] **Comment il parle** : tutoiement/vouvoiement avec ses clients ? niveau de langage (cash, technique, accessible) ?
- [ ] Vocabulaire métier à garder vs jargon à éviter (parler au client final)
- [ ] Niveau d'humour / personnalité qu'il veut transmettre à l'écran (face cam)
- [ ] **Anti-exemples** : ce qu'il déteste / ce qu'il ne veut JAMAIS voir (ton corpo, emojis à gogo, « bonjour à tous »…) → équivalent de `contraintes.md`

---

## 3. CONNECTIONS — Accès & comptes à mettre en jeu

> **Décisions cadrantes** :
> - **Draft-only** : le système RÉDIGE, Loïc poste à la main → on ne branche que de la **LECTURE** (analytics). Aucun accès écriture de publication (pas de Meta publishing, pas de GMB API, pas de WordPress REST).
> - **Tout au nom de Loïc** : il crée chaque compte, génère ses clés, paie sa conso. Handoff 100 % propre. Je l'accompagne en visio écran partagé pendant la formation.

### 3.1 — Comment ça marche : les 3 mécanismes d'accès

Toute connexion passe par **l'un de ces 3 mécanismes**. C'est ça qu'il faut comprendre.

**Mécanisme A — OAuth via connecteurs Claude (le plus simple, ZÉRO secret)**
→ Airtable, Supabase, Google (Drive/Gmail/Calendar), Canva.
Dans SON Claude, Loïc clique « Connecter [service] », une fenêtre navigateur s'ouvre, il se logge dans SON compte, il autorise. Fini. Aucune clé à manipuler. **Prérequis** : avoir un compte (offre gratuite suffit) → c'est ce qu'on crée ensemble.

**Mécanisme B — Clé API dans `.env` (création de compte + clé + facturation conso)**
→ OpenAI, Apify, (Gemini optionnel).
Loïc crée un compte → génère une clé API → **la colle LUI-MÊME dans `.env`** dans son IDE. **Règle sécurité absolue** : jamais de clé dans le chat. Je mets un placeholder (`OPENAI_API_KEY=REPLACE_WITH_YOUR_KEY`), il remplace, il me dit « c'est bon », je vérifie via `${VAR:+SET}` (jamais `cat .env`). **Implique une facturation à la conso** (micro-coûts mensuels qu'il paie) → à annoncer.

**Mécanisme C — App native / login (abonnement)**
→ Claude Code (desktop) + Claude mobile (Dispatch, pilotage vocal).
Loïc se logge avec son abonnement **Claude Pro (20 €/mois)** sur desktop ET mobile. Le pilotage vocal = app Claude mobile connectée à son AIOS via **Dispatch**.

**Qui crée quoi, et QUAND :**
- **Pendant l'appel (maintenant)** : je ne crée RIEN. Je **récolte** (comptes existants, handles, plateforme du site) et je **préviens** des comptes à créer + micro-coûts.
- **Pendant la formation (visio écran partagé)** : je le guide pour créer chaque compte / générer chaque clé. Lui tape/colle, moi je regarde et explique.
- **Moi, en coulisses** : je construis la structure de dossiers, les bases Supabase/Airtable, les skills.

### 3.2 — Liste EXHAUSTIVE des accès dont j'ai besoin

> Statut : 🟢 indispensable · 🟡 selon scope final · ⚪ optionnel / plus tard.

**Bloc 1 — Le socle (obligatoire pour tout)**

| # | Accès / compte | Sert à | Mécanisme | À faire | Statut |
|---|---|---|---|---|---|
| 1 | **Claude Pro 20 €/mois** (son compte) | Faire tourner Claude Code (desktop) | C — login | Il souscrit | 🟢 |
| 2 | **Claude Code installé** sur son PC | L'AIOS vit dans son ordi | C — install | Visio formation | 🟢 |
| 3 | **App Claude mobile + Dispatch** | Pilotage par vocal (son besoin n°1) | C — login | Visio formation | 🟢 |
| 4 | **Son ordinateur** (Windows / Mac ?) | Héberge la structure de dossiers | local | Confirmer OS | 🟢 |

**Bloc 2 — Système CRÉATION DE CONTENU**

| # | Accès / compte | Sert à | Mécanisme | À récolter / faire | Statut |
|---|---|---|---|---|---|
| 5 | **Airtable** (compte gratuit Loïc) | Pipeline d'idées & de contenu (statut Idée→Posté, scripts, hooks) | A — OAuth | Créer compte ensemble | 🟢 |
| 6 | **Supabase** (compte gratuit Loïc) | Base de perf : ses posts + posts concurrents, transcripts, embeddings, analyse IA | A — OAuth | Créer compte + projet ensemble | 🟢 |
| 7 | **Compte Instagram pro** (le sien) | Lire SES stats & posts pour l'analyse de perf | B (Apify) / Meta Graph | Récolter le **@handle** + type de compte | 🟢 |
| 8 | **Apify** (compte Loïc + token) | Scraper Instagram : ses posts + concurrents | B — clé `.env` | Créer compte + token ; récolter **3-5 @ concurrents** | 🟢 |
| 9 | **OpenAI API** (compte Loïc + clé) | Whisper (transcription reels/vocaux) + embeddings (recherche) | B — clé `.env` | Créer compte + billing + clé | 🟢 |
| 10 | **Plateforme du site/blog** (WordPress ? autre ?) | CONTEXTE seulement (draft-only → pas d'accès écriture) | — | Récolter URL + plateforme | 🟡 |
| 11 | **Google My Business** | Draft-only → AUCUN accès requis (il copie/colle le texte) | — | Rien à brancher | ⚪ |
| 12 | **Gemini API** (compte Loïc) | Vision (analyse slides carrousels) — si carrousels dans le scope | B — clé `.env` | À confirmer si carrousels | 🟡 |
| 13 | **nano-banana / KIE.ai** | Génération d'images (covers, visuels) — probablement hors MVP | local / clé `.env` | Plus tard | ⚪ |

**Bloc 3 — Système RÉSUMÉS VOCAUX / DEVIS**

| # | Accès / compte | Sert à | Mécanisme | À récolter / faire | Statut |
|---|---|---|---|---|---|
| 14 | **OpenAI API** (déjà n°9) | Whisper : transcription des vocaux post-chantier | B — clé `.env` | Mutualisé avec n°9 | 🟢 |
| 15 | **Interfast** (son CRM devis) | Draft-only → AUCUN accès (il colle le résumé à la main) | — | Confirmer : pas de branchement | 🟢 |
| 16 | **Google Drive** (son compte) | OPTIONNEL : si les résumés doivent atterrir dans Drive | A — OAuth | À confirmer destination | 🟡 |

**Bloc 4 — Transverse / outillage**

| # | Accès / compte | Sert à | Mécanisme | Note | Statut |
|---|---|---|---|---|---|
| 17 | **Google Workspace** (Gmail/Drive/Calendar) | Optionnel : si rappels / organisation | A — OAuth | Hors scope initial | ⚪ |
| 18 | **n8n** | Optionnel : automatiser le scraping quotidien des stats | clé `.env` | Phase 2 (Bike Method) | ⚪ |
| 19 | **GitHub / git** | MON outillage de build, pas le sien | — | Côté moi uniquement | ⚪ |

### 3.3 — À récolter pendant l'appel (je ne crée rien, je collecte)

- [ ] **OS de son ordinateur** (Windows / Mac) → conditionne l'install Claude Code
- [ ] **@handle Instagram** + type de compte (perso / pro / créateur) → conditionne le scraping
- [ ] **3-5 comptes Instagram concurrents/inspirants** qui « pètent » (HVAC, froid, OU bouchers, fleuristes, mécanos…) → à m'envoyer (Apify)
- [ ] **URL exacte du site + blog** + **plateforme** (WordPress / Wix / autre)
- [ ] **Compte Google** utilisé (pour GMB / Drive si besoin) — lequel
- [ ] Où vivent ses **photos/vidéos de chantier** (téléphone, Drive…) → comment il les transfère
- [ ] Téléphone pour les **vocaux** (app Claude mobile / Dispatch) — iOS / Android
- [ ] **Interfast** : confirmer qu'on N'Y touche PAS (il colle le résumé à la main) ✅
- [ ] **Destination des résumés de devis** : fichier local ? Drive ? (pour décider Drive ou non)
- [ ] Comptes qu'il a **déjà** : Google ? un OpenAI/ChatGPT payant existant ?

### 3.4 — À ANNONCER (transparence)

- [ ] Il devra créer **quelques comptes gratuits** (Airtable, Supabase) → on le fait ensemble en visio
- [ ] Il devra créer **2 comptes avec facturation à la conso** : **OpenAI** (transcription) + **Apify** (scraping) → **micro-coûts mensuels** (quelques € à dizaines d'€ selon volume) qu'il paie directement. Rassurer : c'est faible.
- [ ] **Claude Pro 20 €/mois** confirmé de son côté
- [ ] **Règle de sécurité** : il collera ses clés lui-même dans son IDE, jamais dans le chat avec moi

---

## 4. CAPABILITIES — Système CRÉATION DE CONTENU (sa priorité n°1)

> Objectif explicite de Loïc : **tout piloter au vocal**, juste valider 2-3 trucs, ne jamais taper.

### Cadence & formats qu'il veut produire
- [ ] **Réels Instagram** : cible ~1 tous les 2 jours — confirmer le rythme réaliste
- [ ] **Articles de blog** : 1/semaine
- [ ] **Posts Google My Business** : 1/semaine (format court)
- [ ] **Réalisations sur le site** : 1/semaine (format avant/après)
- [ ] D'autres canaux ? (LinkedIn perso ? Facebook ? TikTok ?)

### Comment il veut bosser
- [ ] Workflow rêvé : il filme/photographie le chantier → vocal → script prêt à lire. Valider chaque étape
- [ ] Veut-il que l'IA lui **propose des idées** (veille) ou qu'il les donne lui-même ? (les deux idéalement)
- [ ] Types de vidéos qu'il imagine : face cam pédagogique (« pourquoi entretenir sa chambre froide »), chantier en cours, avant/après, conseils
- [ ] Ses **sujets piliers** (clim, PAC, chambres froides, entretien, dépannage, conseils saisonniers…)
- [ ] Tendances / hooks : il veut que le système suive ce qui marche → confirmer (oui, via l'analyse de perf)

### Matière première
- [ ] A-t-il déjà un stock de vidéos/photos de chantiers à exploiter au démarrage ?
- [ ] Liste de sujets/idées qu'il a déjà en tête (pour amorcer sa base d'idées)

---

## 5. CAPABILITIES — Système RÉSUMÉS VOCAUX / DEVIS (2e système)

> Il NE veut PAS qu'on fasse ses devis (Interfast OK, 5-10 min). Il veut un **résumé structuré toujours identique**.

- [ ] **Format de résumé cible** : quelle structure exacte il veut en sortie ? (titre, points clés, mesures, matériel, prochaines étapes…) → définir LE template figé
- [ ] Les **types de vocaux** à couvrir : récap visite avant-devis, réunion de chantier (archi), dépannage, autre ?
- [ ] Quelles **infos il dicte** typiquement (nb de pièces, m², nb de clims, type de machine, contraintes du lieu…)
- [ ] Où doit atterrir le résumé une fois fait ? (il le recolle dans Interfast à la main ? Drive ? note ?)
- [ ] Récupérer **2-3 vocaux réels + le résumé qu'il aurait voulu** → pour caler le skill au plus juste
- [ ] Son irritant actuel : ChatGPT sort une structure différente à chaque fois / parfois dans le désordre → confirmer qu'on fige ça

---

## 6. CADENCE — Priorités & pain

- [ ] **2-3 objectifs concrets à 90 jours** (avec chiffres/délais : ex. « publier 3 réels/sem », « +X devis », « tenir le blog »)
- [ ] **Le pain n°1** qui lui bouffe le plus de temps chaque semaine (= la création de contenu d'après l'appel de vente — confirmer)
- [ ] Combien de temps il passe AUJOURD'HUI sur la création de contenu (pour mesurer le gain)
- [ ] Évolutions futures envisagées (prospection LinkedIn syndics, génération vidéo type immo) → noter pour plus tard, hors scope

---

## 7. LOGISTIQUE & CHECKPOINTS

- [ ] **Coordonnées de facturation belges** : nom légal, adresse, **numéro d'entreprise (BCE)** + n° TVA → via WhatsApp
- [ ] Format de facture attendu (facturation électronique belge — quel format / logiciel côté lui ?)
- [ ] Confirmer modalités : **400 € acompte** (probable jeudi via sa compta) + 400 € à la livraison
- [ ] **Caler l'appel de formation** d'1h (la semaine prochaine) — date/heure, même sans paiement reçu
- [ ] Confirmer canal de support : WhatsApp perso (déjà échangés les numéros)
- [ ] Lui rappeler d'**aller voir ma vidéo YouTube** (20 min) pour comprendre le système avant la formation

---

## ⚠️ Checkpoints humains (ne pas inventer)
- Tout `[À COMPLÉTER]` non répondu pendant l'appel → on le note et on lui redemande, on n'invente pas.
- Les échantillons de voix doivent arriver **bruts** ; sans eux, la construction attend.
- Le template de résumé de devis = à **valider avec lui** avant de figer le skill.
