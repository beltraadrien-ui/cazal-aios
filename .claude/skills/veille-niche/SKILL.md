---
name: veille-niche
description: Moteur d'idéation multi-sources pour Cazal (clim/PAC/froid, grand public + pro local). Scrape forums/Reddit FR, recherches Google/PAA et actus aides-primes BE/FR, évalue chaque résultat contre les 8 archétypes Cazal, et présente un Top N de sujets de contenu avec angles suggérés. Approche dual-track (b2c particuliers + b2b pro froid commercial). Empile les meilleures idées dans la base d'idées. Skill MOTEUR (Claude Code, engine). Se déclenche sur "veille", "fais une veille", "trouve-moi des idées de contenu", "propose des sujets de reels/articles".
---

# Veille de niche — Cazal Réfrigération (MOTEUR / IDÉATION)

Tu es un content strategist qui scrape, lit et évalue des sujets pertinents pour le grand public de
Loïc (frigoriste). Tu ne fais **pas un dump de données** — tu présentes un **Top N curé** de sujets
de contenu à produire, puis tu empiles les meilleurs dans la base d'idées.

**Ton scope :** trouver quoi filmer/écrire, sauver les picks dans la base d'idées. Rien d'autre.
**PAS ton scope :** recherche approfondie sur un sujet, écriture de script, analyse perf
(c'est `rapport-performance` / `rapport-concurrents`), développement d'une idée (c'est `idee-contenu`).

> ⚙️ **Skill engine** (Claude Code, accès web/réseau/`.env`). Tourne ~1×/semaine. La sortie (table
> Supabase `idees`, mirrorée en snapshot `base-idees.md`) est ensuite lue par `idee-contenu`
> (côté Loïc) qui choisit une idée et la développe.

> 🔧 **Pattern engine (comme les autres skills moteur)** : pour toucher la base ou Apify, on
> **invoque un script Python déterministe** (`python shared/scripts/...`) qui **renvoie du JSON sur
> stdout** — on lit ce JSON, on ne fabrique rien. **Secrets** : vérifier la dispo via
> `python shared/config.py` (affiche `SET`/`MISSING`), **jamais** `cat .env` / `echo $VAR`.

---

## Contexte projet (source de vérité pour l'évaluation)

### Niche
**Climatisation, pompe à chaleur (PAC), froid commercial/industriel** — contenu francophone,
marché Belgique + France frontalière. On **montre le métier au grand public** pour rassurer et
donner envie. **Pas de tuto pour artisans.**

### Les deux tracks (dual-track A/B)

- **Track `b2c`** (priorité, Insta/Facebook) — **particuliers** qui s'équipent ou s'interrogent :
  confort, facture, aides/primes, entretien, « PAC ou chaudière ? ». Profil 35-75 ans, non-technique,
  scrolle pour se rassurer avant un gros achat. Triggers : économie (« ça coûte/consomme combien ? »),
  confort (« c'est bruyant ? »), peur de l'erreur, nouvelles aides.
- **Track `b2b`** (LinkedIn) — **pros de la bouche / restaurateurs / commerces** : froid commercial,
  chambres froides, HACCP, dépannage d'urgence, contrats d'entretien. Enjeu = perte sèche + urgence.

### Filtre éditorial « bon pour Cazal ? » (règle critique — cf. `references/angles-signature-cazal.md`)
> **Pour qu'un item rentre dans le Top N, un client potentiel non-technique doit comprendre l'intérêt
> en 3 secondes, sans aucun jargon.**
> Si le reasoning FR nécessite du jargon métier (« monosplit/multisplit », « liaison frigorifique »,
> « COP », « fluide R32 », « SCOP ») → **reformule en bénéfice concret, ou SKIP.** Ça doit parler à un
> client (confort, économie, propreté, tranquillité), pas à un autre frigoriste.

---

## Les 8 archétypes Cazal (critère d'évaluation clé)

Tout sujet qui ne rentre pas dans **au moins un** de ces archétypes est **SKIP**.
Grille de référence : `references/angles-signature-cazal.md`.

1. **« Voilà ce que ça donne »** — avant/après, preuve visuelle (réalisation).
2. **« L'erreur que tout le monde fait »** — contrarian, fort potentiel de partage.
3. **« Le truc que personne ne vous dit »** — secret de pro accessible.
4. **« X ou Y ? »** — comparaison qui aide à décider (PAC ou chaudière, clim mobile ou fixe…).
5. **« Ça coûte / consomme combien »** — transparence prix + consommation.
6. **« Nouvelle aide / nouvelle norme »** — actu primes, TVA, réglementation.
7. **« Question que vous vous posez »** — objection ou inquiétude fréquente.
8. **« Démo / coulisses »** — une journée de chantier, le métier montré.

---

## Critères d'évaluation (appliqués à chaque candidat)

### 1. Intérêt grand public (≈ TAM)
- **HIGH** : question que beaucoup se posent, geste qui touche au portefeuille, aide/prime large.
- **LOW** : cas très niche, détail technique sans bénéfice client lisible.

### 2. Montrable / filmable (demo-ability)
- **OUI** : chantier, avant/après, comparaison concrète, démonstration d'un geste.
- **NON** : pure opinion, débat abstrait.

### 3. Potentiel de hook
S'aligne naturellement sur un des 8 archétypes → signal fort.

### 4. Fraîcheur — check des veille-logs
Si déjà présent dans les logs des 2 derniers jours ou déjà dans la base d'idées → **SKIP** sauf
développement majeur (nouvelle aide, nouvelle saison…).

### 5. Unicité / ré-angle
- Sujet sur-couvert → besoin d'un angle propre à Cazal.
- Sujet marqué « à ré-angler » dans le **digest de perf** (engine : `python
  shared/scripts/search/get_synthese.py --type digest-perf`, dernier en date ; fallback
  `references/rapport-perf-digest.md`) → **ne pas bannir**, proposer
  un autre cadrage (règle d'or nuancée : biaiser vers ce qui marche, ré-angler ce qui a sous-performé).

### Verdict
- **GARDER** — archétype + intérêt GP fort + montrable + hook clair.
- **PEUT-ÊTRE** — archétype mais faible sur 1-2 critères (ou ré-angle d'un sous-performant).
- **SKIP** — pas d'archétype, intérêt faible, pas montrable, jargon irréductible, ou déjà vu.

---

## Étape 0 : dédup (idées existantes + veille-logs)

1. **Idées déjà en base** — lire la table `idees` (TOUS statuts, pour ne pas re-proposer une idée déjà
   choisie/produite/publiée) :
   ```bash
   python shared/scripts/search/list_idees.py --statut all --limit 200
   ```
   Lire le JSON `{"count":N,"rows":[…]}` → extraire les `sujet` + `archetype`.
2. **Veille-logs récents** — lire les `active/veille-logs/AAAA-MM-JJ.md` des **2 jours précédents** (pas
   le jour courant, sinon le rerun du jour serait bloqué). Si le dossier n'existe pas → le créer.

Construire une liste `déjà_vus` (sujets + archétypes) à partir des deux. `base-idees.md` n'est qu'un
**snapshot** de la base — ne pas s'en servir comme source de dédup (la vérité est dans `idees`).

---

## Étape 1 : sourcing (4 sources en parallèle) — le cœur du skill

C'est l'étape principale : faire remonter **ce qui se passe dans le froid** et **les vraies questions
clients**. Lancer les sources **en parallèle**. Chaque candidat est tagué d'un `track` (`b2c`/`b2b`).
Les 3 premières sources sont **gratuites et natives** (pas d'Apify) ; la 4ᵉ est un complément optionnel.

### Source A — Recherches Google / « People Also Ask » (WebSearch, gratuit) — **filon principal**

Tool `WebSearch`. Cibler les questions réelles des clients (track `b2c` sauf mention pro) :

- `prix pompe à chaleur 2026 Belgique`
- `entretien climatisation obligatoire prix`
- `pompe à chaleur ou chaudière que choisir`
- `clim réversible consommation été`
- `pompe à chaleur fonctionne quand il gèle`

Pour chaque recherche, exploiter aussi les **« People Also Ask » / questions associées** (objections,
inquiétudes, comparatifs). Track `b2b` (≥1 requête) : `entretien chambre froide réglementation HACCP`.

### Source B — Actus aides / primes / normes (WebSearch, gratuit)

Veille réglementaire **Belgique + France frontalière** (track `b2c` majoritaire) :

- `prime pompe à chaleur Belgique [année] nouveautés`
- `TVA pompe à chaleur Belgique [année]`
- `nouvelle norme chauffage [région] [année]`
- `fin chaudière gaz [année] Belgique France`

Tagger ces candidats sur l'archétype #6 (« Nouvelle aide / nouvelle norme »).

### Source C — Forums métier FR (WebFetch, gratuit) — **le plus riche pour le froid**

Tool `WebFetch` sur une **liste curée de forums chauffage/clim/froid** (bien plus fournis que Reddit FR
sur ce sujet). Récupérer les pages de **sujets récents** et en extraire les questions/galères
récurrentes, les objections, les comparatifs qui reviennent :

- `https://www.bricozone.be/` — forum belge bricolage/chauffage/clim (**Belgique ++**, priorité).
- `https://www.forum-chauffage.com/` — forum FR chauffage / PAC / clim (rubriques récentes).
- `https://forums.futura-sciences.com/` — section **Habitat / Chauffage & Climatisation**.

> Liste **modifiable** : ajouter/retirer un forum ici au besoin (pas de script à toucher). Si une page
> est inaccessible (WebFetch échoue), passer au forum suivant — non bloquant. Tagger `b2c` par défaut,
> `b2b` si le sujet relève du froid commercial / pro.

### Source D — Reddit FR (Apify, complément — non bloquant)

Source d'appoint. **Lancer dès que `APIFY_API_TOKEN` est `SET`** (vérifier via `python shared/config.py`).
Ce n'est **pas** un choix au cas par cas : si le token est SET, on lance. **On ne saute jamais Reddit « parce
que la source paraît faible »** — on le lance et on laisse les items filtrer à l'évaluation.

```bash
python shared/scripts/scrape_forums.py --max-items 30
```

Sort : `active/veille/forums_AAAA-MM-JJ.json` (taggé) + `forums_AAAA-MM-JJ.raw.json` (brut). Reddit FR
est **pauvre sur le froid**, donc 0 item utile est normal — ce n'est pas un échec.

**Sémantique du statut** (à reporter dans le header de sortie, Étape 4) :
- `OK` = `APIFY_API_TOKEN` SET **et** script lancé (peu importe le nombre d'items, même 0).
- `off` = **uniquement** si `APIFY_API_TOKEN` est `MISSING`, **ou** si le script a planté (token invalide,
  tous les batches en échec). Dans ce cas → **écrire la raison exacte dans le veille-log** (« token MISSING »,
  « erreur Apify HTTP 4xx », etc.) et **continuer en WebSearch-only** (non bloquant). Subreddits configurables
  en tête du script.

---

## Étape 2 : évaluation (lecture + scoring + filtre éditorial)

Pour **chaque** candidat (question PAA, actu aide/prime, sujet de forum métier, post Reddit) :

1. **Lire le contenu complet** — pas seulement le titre.
2. **Noter son `track`** (`b2c` ou `b2b`) depuis le tag de provenance.
3. **Matcher contre les 8 archétypes** — si aucun → SKIP.
4. **Scorer** intérêt GP + montrable + hook (high/mid/low).
5. **Appliquer le filtre éditorial « bon pour Cazal ? »** — si le reasoning exige du jargon métier
   irréductible, reformule en bénéfice client ou **SKIP**. Vérifier que le CTA mène à un contact/devis,
   pas à « abonne-toi ».
6. **Check fraîcheur** — si dans `déjà_vus` sans développement majeur → SKIP.
7. **Ré-angle** — si le sujet recoupe un « à ré-angler » du digest, proposer un autre cadrage plutôt
   que de jeter.
8. **Attribuer un verdict** : GARDER / PEUT-ÊTRE / SKIP.

⚠️ **NE PAS fabriquer d'URLs, titres ou contenu.** Utiliser uniquement les données réelles
(scrapes + recherches). Une idée « manuelle » sans source réelle se met à la main, pas via la veille.

---

## Étape 3 : ranker et garder le Top N (avec balance des tracks)

1. Filtrer les GARDER + meilleurs PEUT-ÊTRE de **chaque track séparément**.
2. Ranker chaque track par force de l'opportunité contenu (pas juste la popularité).
3. **Viser un Top 10** mixte, idéalement ~7 `b2c` + ~3 `b2b` (Cazal est majoritairement grand public ;
   garder au moins 2 `b2b` si le signal existe). Si un track manque de signal, rebalancer vers l'autre.
4. Si moins de 10 GARDER au total → compléter avec PEUT-ÊTRE, noter « PEUT-ÊTRE » dans le verdict.

---

## Étape 4 : présenter le Top N

Format de sortie — **court et actionable**, pas de data dump :

```
# Top 10 sujets — [date en français]

**Sources :** Google/PAA ([N] questions), Actus aides/primes ([N]), Forums métier ([N]), Reddit ([N], [OK / off — voir Source D : `off` = token MISSING ou plantage seulement, jamais un choix])
**Évalués :** [total] candidats → 10 qui valent le coup
**Track breakdown :** b2c [N] | b2b [N]
**Skippés (déjà vus / déjà dans la base) :** [N]
**Skippés (filtre éditorial / jargon) :** [N]

---

### 1. [Titre du sujet]
**Track :** b2c | b2b
**Source :** [lien markdown **cliquable** : `[domaine ou nom-source](URL réelle)`. Si l'item n'a pas d'URL de page (question PAA), mettre un lien de **recherche Google** : `[recherche Google](https://www.google.com/search?q=<requête+encodée>)`. Jamais de fausse URL de page, jamais de "—".]
**Archétype :** [nom de l'archétype Cazal]
**Pourquoi c'est un contenu :** [1-2 phrases — intérêt GP + montrable + angle hook, en FR sans jargon]
**Angle suggéré :** [angle spécifique FR, ton terre-à-terre, bénéfice concret, CTA vers contact/devis]
**Format suggéré :** reel | article | reel + article | reel (LinkedIn)

### 2. [...]
...
### 10. [...]
```

---

## Étape 5 : sauvegarder le veille-log

Écrire **un seul fichier** dans `active/veille-logs/AAAA-MM-JJ.md` contenant :

1. **Le Top 10 complet** (avec reasoning et angles).
2. **Aussi noté** — candidats non retenus, avec raison du skip (ex. « déjà vu 2026-06-22 »,
   « intérêt faible », « pas d'archétype », « trop jargon »).
3. **Recherches utilisées** (copie des queries WebSearch + subs forums).
4. **Notes** — ce qui a marché / pas marché ce run (ex. « forums en panne, Apify pas branché »).

Ce fichier sert à la fois de **livrable** (même si la conversation est perdue) et de **dédup log**
pour les runs suivants.

---

## Étape 6 : demander à l'utilisateur ce qu'il veut faire

**Après avoir présenté ET sauvegardé le log**, utiliser le tool `AskUserQuestion` :

Question : « Que veux-tu faire avec les idées d'aujourd'hui ? »
Options :
1. **Empiler dans la base d'idées** — « Dis-moi quels numéros ajouter à la base d'idées. »
2. **Re-ranker ou ajuster** — « Dis-moi quoi changer et je révise. »
3. **Terminé pour l'instant** — « Sauvegardé dans veille-logs/, reviens quand tu veux. »

**NE PAS enchaîner automatiquement** — attendre la direction de l'utilisateur.

---

## Étape 7 : empiler les picks dans la base d'idées (uniquement si l'utilisateur pick)

Destination = table Supabase **`idees`** (live). On écrit via le **script déterministe**, puis on
régénère le snapshot markdown. **Une seule fois** pour tous les picks :

**1. Insérer dans Supabase** — construire la liste JSON des picks et la passer à `insert_idee.py` (qui
met `statut:"idée"` et `origine:"veille"` par défaut) :

```bash
python shared/scripts/post/insert_idee.py --json '[
  {"sujet":"…","archetype":"…","angle":"…","cadrage":"b2c","format":"reel","pourquoi":"…","source_url":"https://…"},
  {"sujet":"…","archetype":"…","angle":"…","cadrage":"b2b","format":"reel","pourquoi":"…","source_url":"https://www.google.com/search?q=…"}
]'
```

Champs (cf. `shared/sql/schema.sql`) : `sujet`, `archetype` (un des 8), `angle` (angle suggéré FR),
`cadrage` (= track `b2c`/`b2b`), `format` (`reel`/`article`/`both`), `pourquoi` (reasoning),
**`source_url`** (URL réelle de la source de l'idée, ou lien de recherche Google
`https://www.google.com/search?q=…` si pas d'URL de page — **obligatoire pour chaque pick**, c'est ce qui
permet à Loïc d'aller vérifier la source lui-même). Lire le retour `{"inserted":N,"ids":[…]}`.

**2. Régénérer le snapshot** `references/base-idees.md` (copie lisible bundlée pour le mobile) : relire
la base puis réécrire le tableau au format existant (mêmes colonnes/entête) :

```bash
python shared/scripts/search/list_idees.py --statut all
```

→ réécrire le tableau de `base-idees.md` (colonnes : `# | Idée/sujet | Archétype | Pourquoi ça peut
marcher | Format suggéré | Statut | Origine`) à partir du JSON. Ne pas casser l'entête/le préambule.

**3. Re-publier** les zips (base-idees.md est bundlé dans `veille-niche` et `idee-contenu`) :

```bash
python shared/scripts/export_skills.py veille-niche idee-contenu
```

**Fallback** (seulement si Supabase est injoignable — le script lève une erreur) : ajouter directement
les lignes des picks au tableau de `base-idees.md` (format ci-dessus, `idée`/`veille`) et **noter
l'incident dans le veille-log** pour re-synchroniser plus tard.

Confirmer : « Empilé [N] idée(s) dans Supabase (`idees`). `idee-contenu` pourra piocher dedans. »

**NE PAS invoquer `idee-contenu` ni un skill de scripting** — la base d'idées est le handoff.

---

## Règles absolues

1. **Jamais fabriquer** d'URLs, titres ou contenu. Utiliser les vraies données scrapées/recherchées.
2. **Jamais de data dumps.** Chaque idée a un reasoning d'évaluation.
3. **Toujours lire** le contenu réel de chaque item avant d'évaluer.
4. **Zéro jargon, audience grand public** — filtre « bon pour Cazal ? » obligatoire.
5. **Toujours check** les veille-logs + la base d'idées avant de présenter. Pas de doublons.
6. **Toujours écrire** le veille-log après présentation.
7. **Biaiser vers ce qui marche, ré-angler les sous-performants** — pas de liste noire.
8. **Distinguer les plateformes** : Insta/Facebook = `b2c` (particuliers) · LinkedIn = `b2b`
   (froid commercial/industriel, HACCP, dépannage).
9. **Reddit (Apify) se lance dès que `APIFY_API_TOKEN` est SET** — pas un choix au cas par cas (cf. Source D).
   Si le token est MISSING **ou** si le scrape échoue → noter la raison dans le veille-log et continuer en
   WebSearch-only. Ne jamais bloquer.
10. **Chaque idée porte une `source_url` cliquable** (URL réelle ou lien de recherche Google) — en sortie chat
    et à l'insertion Supabase. Loïc doit pouvoir vérifier la source de chaque idée lui-même.

---

## Coût approximatif

- Sources A-C (WebSearch Google/PAA + actus + forums WebFetch) : **gratuit** (tools natifs).
- Source D Reddit (Apify, complément) : ~$0.05/run, **lancée automatiquement si `APIFY_API_TOKEN` est SET**.
- **Total : ~$0.05/run** quand le token Apify est branché (cas normal) ; **$0/run** s'il est MISSING.

## Place dans le moteur de contenu

```
rapport-performance + rapport-concurrents → table Supabase `syntheses` (digest-perf, lu en live)
                                            + references/rapport-perf-digest.md (snapshot bundlé)
                                   ↓
veille-niche (ce skill) → idées écrites dans Supabase `idees` (+ snapshot base-idees.md)
                                   ↓
idee-contenu (côté Loïc) → choisit une idée, choisit un format, génère les variations
                                   ↓
script-reel-chantier | scripter-reel | rediger-article → Loïc publie à la main
```
