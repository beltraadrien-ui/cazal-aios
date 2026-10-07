# Branche « dimensionnement » — chiffrer le remplacement d'une installation frigorifique

> Manuel de la branche. Le `CLAUDE.md` racine reste le routeur canonique ; ce fichier dit comment
> se déroule **un dossier d'installation** et quelles règles s'appliquent. Lu par les skills
> `froid-releve-existant`, `froid-dimensionnement`, `froid-demande-fournisseur`, `froid-savoir`,
> `froid-plan-2d`.
> Travail de bureau, sur PC (onglet Code). Loïc parle normalement ; le routeur fait le lien.

## Le parcours d'un dossier (une installation = un dossier)

```
① Rapport InterFast (PDF, un sous-point par poste + photos des plaques)
② ÉTAPE 1 · Relevé de l'existant ............ froid-releve-existant → 1-existant.md    ✋ Loïc valide
③ ÉTAPE 2 · Dimensionnement du remplacement . froid-dimensionnement → 2-dimensionnement.md ✋ Loïc valide
④ ÉTAPE 3 · Demande fournisseur ............. froid-demande-fournisseur → 3-demande-fournisseur/ ✋ Loïc relit et envoie lui-même
Ⓟ ÉTAPE P · Plan 2D et métré ................ froid-plan-2d → plan/ (plan.drawio, plan.pdf, plan.html) ✋ Loïc relit
   indépendante : avant ou après l'étape 2 ; nourrira l'étape 2 (longueurs de lignes) et l'étape 3 (pièce jointe) au Lot 7
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

**Étape 3 (demande fournisseur).** Loïc dit à qui il écrit (grossistes, ou un fabricant de centrale nommé).
`assembler.py` du skill `froid-demande-fournisseur` écrit `demande.json` depuis les étapes 1 et 2 (textes par défaut,
tableaux rendus depuis `2-resultats.json`, un chapitre par poste avec les photos des plaques, client anonymisé pour
les grossistes) ; Claude n'y ajuste que les textes dictés, jamais un chiffre ; `generer_livrable.py` produit **un
PDF unique** (contexte, chambres, production existante, évaporateurs, demande, détail par poste avec les photos
légendées, annexes ; moins de 5 Mo) et **un mail court sans tableau** ; `controler.py` vérifie anonymisation,
chiffres, plaques, PDF, mail et annexes (0 échec exigé), un vérificateur relit, puis Loïc relit ✋ et **envoie
lui-même** ; `envois.md` garde la trace de chaque envoi. Une version envoyée ne se réécrit jamais : `v2`, `v3`…
(grossistes) et `v1-fabricant`… (fabricant).

**Étape P (plan).** Loïc décrit le local avec ses cotes au télémètre (ou donne un croquis photographié, un plan
d'architecte en PDF ; le relevé InterFast fournit l'inventaire des chambres et des équipements). Claude écrit
`plan/plan.json`, un modèle en mètres où **chaque cote garde sa source** ; une cote manquante est une question, jamais
une estimation. `generer.py` du skill `froid-plan-2d` dessine `plan.drawio` en **A4 à une échelle normalisée** (1:50,
1:100, 1:200…, choisie automatiquement, avec barre d'échelle et règle de contrôle de 100 mm), calcule le **métré** de
chaque réseau (longueur en plan + parcours dans le chemin de câbles pour un câble qui s'y arrête + montées et
descentes aux hauteurs de pose, hypothèses tant que Loïc ne les a pas validées) et les **croisements**, rend `plan.pdf` (draw.io en ligne de commande, calibré sur la règle de 100 mm) et la
vue HTML du métré ; `verifier_plan.py` relit tout depuis le fichier draw.io et mesure le PDF (0 erreur exigée, 5 tours
au plus), Claude relit l'image du plan, puis Loïc relit ✋. Il retouche à la voix (Claude modifie `plan.json`) ou à la
souris dans draw.io Desktop (`importer_drawio.py` ramène les positions). Lot 6 : une feuille A4 à repères par réseau,
tracée au marqueur et photographiée, devient un calque (`feuille.py`, `lire_photo.py`). Les diamètres restent « à
définir par le dimensionnement ». **Pour les plans, Opus recommandé** : Loïc passe sur Opus avec `/model` avant de
commencer (meilleure lecture des croquis et des rendus).

## Où vivent les choses

```
dimensionnement/
├── CLAUDE.md            ← ce manuel
├── savoir/              ← SOCLE versionné, maintenu par Adrien (INDEX.md = routeur « pour trouver X → fichier Y, page Z »)
├── bibliotheque/        ← LOCAL (gitignoré) : documents originaux de Loïc, cache des pages et de l'OCR
├── carnet/              ← LOCAL (gitignoré) : lecons.md, les corrections de Loïc et le pourquoi
└── dossiers/            ← LOCAL (gitignoré) : un dossier par installation
    ├── emetteur.json                  ← coordonnées de Loïc pour les demandes de prix (à compléter par lui)
    └── AAAA-MM-JJ-client/
        ├── dossier.md                 ← état, précision, décisions, hypothèses, questions, journal
        ├── sources/                   ← rapport.pdf, rapport-texte.md, structure.json, photos/<poste>/
        ├── 1-existant.md
        ├── 2-dimensionnement.md
        ├── plan/                      ← étape P (froid-plan-2d), indépendante des étapes 1 à 3
        │   ├── plan.json              ← le modèle en mètres, cotes sourcées (seul fichier que Claude écrit)
        │   ├── plan.drawio            ← pages « Plan » et « Métré », s'ouvre dans draw.io Desktop
        │   ├── plan.pdf, plan.png     ← le plan sur une page A4 à l'échelle (à imprimer à 100 %), le métré
        │   │                            sur une ou deux pages A4 selon sa longueur ; image de relecture
        │   ├── plan.md, plan.html     ← métré, croisements, hauteurs, journal des versions (Loïc lit le .html)
        │   ├── plan-base.json, rendu.json        ← échelle et origine pour les feuilles ; calibration du PDF
        │   ├── verification.md, .json, journal.md ← dernier contrôle ; une ligne par génération
        │   ├── versions/              ← plan-vN.drawio + plan-vN.json à chaque génération, sauvegardes
        │   └── feuilles/, photos/, calques/      ← Lot 6 : feuilles à repères, photos des tracés, réseaux lus
        └── 3-demande-fournisseur/
            ├── envois.md              ← à qui, quand, quelle version (une ligne par envoi de Loïc)
            ├── v1/                    ← variante grossiste ; v2, v3… à chaque nouvelle version
            │   ├── demande.json       ← données de la demande (+ identifiants-client.json, valeurs-derivees.json)
            │   ├── demande-v1.html    ← page A4 (img/ : photos réduites)
            │   ├── demande-v1.pdf     ← le PDF à joindre
            │   └── mail-grossiste.txt, mail-grossiste.html  ← le mail court, sans tableau
            └── v1-fabricant/          ← variante fabricant : demande-v1-fabricant.pdf, mail-fabricant.txt…
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
