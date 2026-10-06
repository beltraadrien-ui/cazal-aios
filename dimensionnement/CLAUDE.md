# Branche « dimensionnement » — chiffrer le remplacement d'une installation frigorifique

> Manuel de la branche. Le `CLAUDE.md` racine reste le routeur canonique ; ce fichier dit comment
> se déroule **un dossier d'installation** et quelles règles s'appliquent. Lu par les skills
> `froid-releve-existant`, `froid-dimensionnement`, `froid-demande-fournisseur`, `froid-savoir`.
> Travail de bureau, sur PC (onglet Code). Loïc parle normalement ; le routeur fait le lien.

## Le parcours d'un dossier (une installation = un dossier)

```
① Rapport InterFast (PDF, un sous-point par poste + photos des plaques)
② ÉTAPE 1 · Relevé de l'existant ............ froid-releve-existant → 1-existant.md    ✋ Loïc valide
③ ÉTAPE 2 · Dimensionnement du remplacement . froid-dimensionnement → 2-dimensionnement.md ✋ Loïc valide
④ ÉTAPE 3 · Demande fournisseur ............. froid-demande-fournisseur → 3-demande-fournisseur/ ✋ Loïc relit et envoie lui-même
```

Chaque étape relit `dossier.md` en premier (état, décisions, hypothèses, questions, corrections) et
l'écrit en dernier. Si la conversation est perdue, « on reprend le dossier X » repart du fichier.

**Deux formes pour chaque document du dossier.** Le markdown (`dossier.md`, `1-existant.md`…) est la
**mémoire de Claude** : complet, sourcé, relu par les skills. Pour **Loïc**, on génère toujours la **vue
HTML** (`shared/rendu_html.py`, convertisseur commun à toutes les étapes ; `rendu_html.py` du skill
`froid-releve-existant` n'en est qu'un adaptateur) : même contenu, lisible, avec la photo de chaque
plaque à côté de sa lecture, ouverte dans le navigateur. On ne demande jamais à Loïc de lire du markdown.

**Étape 2 (dimensionnement).** Claude remplit `2-entrees.json` (une valeur sourcée par donnée, rien
d'inventé) ; `calculs.py` du skill `froid-dimensionnement` calcule la **puissance existante** de chaque
compresseur par **deux méthodes** (M1 par la cylindrée de la plaque, M2 par le point catalogue du fabricant
ramené au fluide et au régime ; M2 retenue si elle existe, l'écart sert de contrôle), la somme par poste, la
**puissance demandée** (marge de Loïc) et la **conformité F-gas** du fluide, puis écrit les tableaux B, C, D.
Claude assemble `2-dimensionnement.md` (blocs A à G : projet, compresseurs, besoins, fluide, ce qu'on garde,
fournitures, hypothèses et questions), un vérificateur le relit, Loïc valide ✋. Chaque chiffre porte un
**statut** : *sourcé* (lu tel quel), *calculé* (script, entrées sourcées), *hypothèse* (dépend d'une hypothèse
écrite, marqué « (hyp.) ») ou *à confirmer* (pas de nombre) ; un résultat n'est jamais plus sûr que sa plus
faible entrée.

## Où vivent les choses

```
dimensionnement/
├── CLAUDE.md            ← ce manuel
├── savoir/              ← SOCLE versionné, maintenu par Adrien (INDEX.md = routeur « pour trouver X → fichier Y, page Z »)
├── bibliotheque/        ← LOCAL (gitignoré) : documents originaux de Loïc, cache des pages et de l'OCR
├── carnet/              ← LOCAL (gitignoré) : lecons.md, les corrections de Loïc et le pourquoi
└── dossiers/            ← LOCAL (gitignoré) : un dossier par installation
    └── AAAA-MM-JJ-client/
        ├── dossier.md                 ← état, précision, décisions, hypothèses, questions, journal
        ├── sources/                   ← rapport.pdf, rapport-texte.md, structure.json, photos/<poste>/
        ├── 1-existant.md
        ├── 2-dimensionnement.md
        └── 3-demande-fournisseur/     ← demande-v1.pdf, tableaux-outlook.html, mail.txt
```

Ce qui est à Loïc (documents, dossiers clients, corrections) ne va **jamais** sur GitHub.

## La base de savoir (livres, formations, notices)

Les documents de Loïc sont **dans sa base Supabase** (tables `savoir_documents`, `savoir_sections`, `savoir_pages`,
`savoir_chunks`, `savoir_figures`, `savoir_renvois` ; images de pages dans le bucket privé `savoir-pages` ; schéma
`shared/sql/schema_savoir.sql`). Une ligne par page, recherche **par mots** (`rechercher_savoir`, français sans
accents) et **par sens** (`rechercher_savoir_vec`, vecteurs OpenAI). Ingestion et entretien : skill `froid-savoir`
(catalogue `bibliotheque/catalogue.json`, cache `bibliotheque/_cache/`, OCR des scans par OpenAI). Accès depuis le
téléphone : skill `froid-question` (zip + connecteur Supabase en lecture seule) avec `references/INDEX.md` en secours.
Code commun : `shared/savoir.py`.

## Règles de fiabilité (non négociables)

1. **Une source sur chaque chiffre** : `rapport p. 4`, `photo p05-2`, `catalogue Bitzer p. 34`, `web : <lien>`,
   `calcul : 14,6 × 11,6 × 2,4`, `dicté par Loïc`, `hypothèse`. Sans source, la case dit « à confirmer ».
2. **Ne jamais inventer** : une valeur absente ou illisible devient « à confirmer », jamais une estimation silencieuse.
3. **Les calculs se font par script** (`scripts/` des skills), jamais de tête. Même entrée, même résultat.
4. **Les plaques se lisent sur la photo**, et une lecture douteuse est marquée « douteuse ». Une photo
   InterFast est petite (450 × 600) : si c'est illisible, demander à Loïc la photo d'origine.
5. **Validation humaine à chaque étape** ✋ et **aucun envoi automatique**, jamais. Loïc valide et signe.
6. **Niveau de précision** noté dans `dossier.md` : « remise de prix » (par défaut, l'ordre de grandeur
   suffit) ou « exécution » (après signature : tout est à faire confirmer par le fournisseur).
7. **Chaque correction de Loïc** va dans `carnet/lecons.md` avec le pourquoi, et est relue au dossier suivant.
8. Recherche web autorisée pour une donnée constructeur, **avec le lien en source**, et marquée « indicatif ».

## Vocabulaire de Loïc

- **Poste** = un sous-point du rapport InterFast (ex. « Centrale négative B », « Chambre froide »).
- **Centrale** = plusieurs compresseurs en parallèle ; **groupe / unité de condensation** = un compresseur
  avec son condenseur ; **négatif** = congélation (≈ −18 à −25 °C) ; **positif** = réfrigération (≈ 0 à +4 °C).
- **Remodeling** = remplacement d'une installation existante (gaz, compresseurs, régulation).
- **Remise de prix** = chiffrage avant signature ; « on n'est pas à la virgule près ».
