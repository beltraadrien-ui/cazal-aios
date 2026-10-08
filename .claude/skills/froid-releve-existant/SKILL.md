---
name: froid-releve-existant
description: Étape 1 du chiffrage d'un remplacement d'installation frigorifique — ouvre un dossier d'installation à partir du rapport de visite InterFast (PDF), extrait le texte et les photos, lit les plaques signalétiques et produit le tableau de l'existant, chaque valeur sourcée, avec la liste de ce qui reste à confirmer. Skill MOTEUR (PC, Claude Code). Se déclenche sur "nouveau dossier", "voici le rapport de visite", "relevé de l'existant", "sors-moi les puissances existantes", "ouvre un dossier pour", "on reprend le dossier", "remodeling", "remplacement de centrale".
---

# Relevé de l'existant — étape 1 du chiffrage (Cazal Réfrigération)

## Ce que fait cette skill

Loïc glisse (ou nomme) le **PDF du rapport InterFast** d'une visite de remplacement. La skill crée le
dossier de l'installation, en sort le texte et les photos, **lit les plaques signalétiques** et remplit
`1-existant.md` : les sous-points du rapport, les compresseurs, les plaques d'ensemble, les chambres froides, la
régulation, **avec la source de chaque valeur**, et la liste « à confirmer ». Loïc valide ✋, puis vient l'étape 2
(`froid-dimensionnement`).

Lire d'abord `dimensionnement/CLAUDE.md` (règles de fiabilité, vocabulaire : sous-point et poste). Ce manuel prime
sur toute habitude. Loïc demande les trois étapes sans être là : paragraphe « Loïc absent : tout d'un coup » du
même manuel (on enchaîne sur hypothèses écrites, une seule liste de questions à la fin, rien n'est envoyé).

## Étapes

1. **Trouver le PDF.** Chemin donné par Loïc, ou fichier glissé dans la conversation (le copier dans
   `active/` s'il n'est pas sur le disque). Un rapport InterFast = « rapport complet » d'une fiche de visite.
   Si Loïc dit « on reprend le dossier X » : ouvrir `dimensionnement/dossiers/<X>/dossier.md` et sauter à l'étape 4.

2. **Créer le dossier par le script** (jamais à la main) :
   ```
   python .claude/skills/froid-releve-existant/scripts/extraire_rapport.py "<chemin du PDF>" [--slug AAAA-MM-JJ-client] [--force]
   ```
   Il crée `dimensionnement/dossiers/AAAA-MM-JJ-client/` (ou le nom donné par `--slug`, utile pour un second dossier
   du même rapport) avec `dossier.md`, `1-existant.md` (squelette au format ci-dessous), `sources/` (PDF, texte page
   par page, `structure.json`, `photos/<poste>/`). Lire ce qu'il affiche : sous-points, nombres lus, photos par
   sous-point. Si le dossier existe déjà, il refuse : demander à Loïc avant d'utiliser `--force`.

3. **Lire les photos, sous-point par sous-point** (outil Read sur chaque fichier de `sources/photos/`), avec
   `dimensionnement/savoir/materiel/lecture-plaques.md` sous les yeux. Pour chaque plaque (compresseur, plaque
   d'ensemble, condenseur, échangeur, **évaporateur**) : marque, modèle complet, numéro de série, fluides listés,
   tension, volume balayé si écrit. Un chiffre trop petit pour être tranché : agrandir la zone (petit script PIL
   écrit dans le scratchpad) avant de conclure. Qualifier chaque lecture : `sûre`, `douteuse (lecture probable +
   doute)`, `illisible`. Les photos qui ne sont pas des plaques (vue d'ensemble, armoire, local) sont décrites en
   un segment, au tableau B2 (production) ou D (le reste).

4. **Compléter `1-existant.md` au format exact ci-dessous** (l'étape 3 le lit par script : une forme inattendue lui
   fait perdre un n° de série ou décaler une légende ; `assembler.py` le signale ou refuse, mais autant l'écrire
   juste) : tableau B (une ligne par compresseur), **B2** (plaques d'ensemble et vues des productions), C (chambres,
   évaporateurs, « desservi par » si le rapport ou les photos le disent, sinon « à confirmer »), D (le reste), et la
   liste E « À confirmer » complétée de tout ce qui est douteux ou illisible, et de chaque **plaque attendue mais non
   photographiée** (condenseur ou régulateur d'une centrale, plaque d'ensemble absente) : une question chacune.
   **Ne jamais remplir une case avec une supposition** : ce que le rapport ne dit pas et que la photo ne montre pas
   reste « à confirmer ».

5. **Puissances existantes, si Loïc les demande** (« sors-moi d'abord les puissances existantes ») :
   pour chaque modèle lu `sûr`, chercher la fiche constructeur (catalogue dans `dimensionnement/savoir/`
   s'il existe, sinon WebSearch / WebFetch) et noter dans tableau B le **volume balayé (m³/h à 50 Hz)** et,
   s'il est publié, la puissance frigorifique **au régime indiqué par la source** (ex. −10 / +45 °C, R449A),
   avec le lien. Marquer « indicatif ». Aucune conversion ni somme ici : les calculs sont à l'étape 2, par script.

6. **Double lecture (vérificateur).** Lancer un sous-agent avec, pour seule entrée, la liste des photos et les
   tableaux B, B2 et C, et pour consigne de **relire chaque plaque, évaporateurs compris** (modèle caractère par
   caractère, n° de série, année, fluide), **avant** de regarder la lecture saisie, et de signaler tout désaccord.
   Chaque désaccord devient une ligne « à confirmer » (jamais tranché en silence) ; une lecture qu'il juge serrée
   passe en `douteuse`.

7. **Générer la vue lisible et l'ouvrir** (le markdown est la mémoire de Claude, pas un document pour un humain) :
   ```
   python .claude/skills/froid-releve-existant/scripts/rendu_html.py dimensionnement/dossiers/<slug> --ouvrir
   ```
   Elle produit `1-existant.html` (et `dossier.md` → `dossier.html`) avec la photo de chaque plaque à côté de sa
   lecture (**vignette seulement si le nom de la photo est entre accents graves**, ex. `` `p05-2.jpeg` `` ; un
   `p05-2` nu devient un simple lien), et l'ouvre dans le navigateur. **À régénérer après chaque modification du
   markdown.** Loïc absent : générer sans `--ouvrir`.
   Puis **présenter à Loïc** dans la conversation, court : le tableau A en deux phrases, les points marquants
   du tableau B, puis la liste « À confirmer » sous forme de questions courtes, en renvoyant à la page HTML
   pour le détail. Demander la validation ✋. Pas de dimensionnement ici.

8. **Après ses réponses** : reporter les réponses dans `1-existant.md` avec la source `dicté par Loïc
   (AAAA-MM-JJ)`, noter chaque correction d'une lecture dans `dimensionnement/carnet/lecons.md` (créer le
   dossier et le fichier au premier usage : date, dossier, ce qui était faux, ce qui est juste, pourquoi), mettre
   `dossier.md` à jour (étape 1 : *validée*, journal) et dire : « on peut passer au dimensionnement ».

## Format de `1-existant.md` (lu par les étapes 2 et 3)

Titres de section **exactement** ceux du squelette : `## A. Postes relevés…`, `## B. Compresseurs…`,
`### B2. Plaques d'ensemble et vues des centrales et groupes`, `## C. Chambres froides et postes desservis`,
`## D. Régulation, récupération de chaleur, autres éléments`, `## E. À confirmer par Loïc`, `## F. Photos extraites`.
Le tableau A garde les titres InterFast tels quels ; ailleurs, la colonne « Poste » ou « Élément » s'écrit sans
capitales forcées et « À » final = « A » (« Centrale négative A »), comme le squelette.

- **B. Compresseurs** : une ligne par compresseur ou unité de condensation. Colonnes du squelette ; `Photo` = le nom
  du fichier entre accents graves (`` `p05-2.jpeg` ``), une photo par ligne ; `Modèle` et `N° de série` tels que lus,
  **sans guillemets ni gras** (un doute s'écrit après, entre parenthèses : « 1234?56789 (un chiffre masqué) ») ;
  volume balayé « 56,2 m³/h à 50 Hz » ; `Source` = `photo pNN-k`.
- **B2. Plaques d'ensemble et vues** (ce qui, dans un sous-point de production, n'est pas une plaque de compresseur) :
  `| Poste | Équipement | Plaque (ce qui est lu) | Lecture | Photo | Source |`, une ligne par photo. Plaque lue :
  segments séparés par « ; » : désignation « … » ou type « … » ; `n° …` ; année ; fluide ; charge ; puissance ;
  Lecture `sûre` / `douteuse` / `illisible`. Vue sans plaque : « vue d'ensemble (pas de plaque) », Lecture « — ».
  Plaque attendue mais absente : « plaque non photographiée » (et une question en E). L'étape 2 en tire
  `plaques_ensemble` ; l'étape 3 met une plaque lue dans le chapitre du poste, une vue dans les annexes.
- **C. Chambres** : `Évaporateurs` = le nombre puis **un segment par plaque**, séparés par « ; » :
  « 2 : Profroid CAB5367 n° 123456/120/12345, 2006, R404A (`` `p09-1.jpeg` ``) ; Kelvion SPBE 45-F33 MARKET n° 2020/
  12345678/1/5, 2020 (`` `p09-4.jpeg` ``) » ; deux plaques identiques : « 2 × Güntner GACC RX 050.2 n° A et B, 2025
  (`` `p07-2.jpeg` ``, `` `p07-3.jpeg` ``) ». Le modèle s'écrit comme dans `2-entrees.json`, sans guillemets ni gras ;
  une lecture serrée : « (lecture douteuse : U ou J) » dans le segment. `Usage` : l'usage et la photo de la chambre
  « (photo pNN-k) ». `Desservi par` : la production, avec sa source ; déduite des lettres des titres = hypothèse.
  `Source` cite les photos des plaques (`photo pNN-k`).
- **D. Le reste** (chauffage, récupération de chaleur, régulation, électricité, locaux) :
  `| Élément | Ce que dit le rapport | Lu sur les photos | Photo | Source |`. `Lu sur les photos` = **un segment par
  photo, chacun terminé par sa photo** : « armoire Danfoss avec variateur (`` `p14-1.jpeg` ``) ; régulateurs
  d'évaporateurs Danfoss (`` `p14-2.jpeg` ``) » ; `Photo` = toutes les photos de la ligne. L'étape 3 associe chaque
  légende à la photo qu'elle cite ; sans référence, elle rapproche par position et le signale.
- **Nombres** : espace insécable (U+00A0) entre un nombre et son unité (« −30,7 °C », « 56,2 m³/h ») et dans les
  milliers (« 1 450 min⁻¹ »), pour qu'aucune coupure de ligne ne les sépare. Pour en poser beaucoup d'un coup :
  un script Python **écrit dans un fichier** du scratchpad, jamais un heredoc Bash (une référence `\1` y devient le
  caractère invisible U+0001, que `controler.py` refuse désormais).

## Règles fermes

- **Une source par valeur, ou « à confirmer ».** Jamais de valeur de mémoire, jamais de modèle complété.
- **Les photos InterFast sont petites** (450 × 600). Une plaque illisible = demander à Loïc la photo
  d'origine (InterFast ou son téléphone), à déposer dans `sources/photos-hd/`.
- **Pas de calcul dans cette étape** (sommes, conversions, puissances par le volume) : c'est l'étape 2.
- Le rapport est la vérité pour les commentaires de Loïc ; la photo est la vérité pour les plaques ;
  en cas de contradiction, poser la question.
- **Fluide** : la plaque fait foi pour l'existant tel que lu (fluide d'origine, recopié comme il est écrit) ; le
  rapport ou Loïc font foi pour le fluide actuel réel (celui qui est dans l'installation aujourd'hui). Quand les deux
  divergent, le calcul prend le fluide du rapport en hypothèse et la divergence devient une question pour Loïc.
- Réponses courtes, vocabulaire de Loïc (poste, centrale, groupe, négatif / positif). Pas de jargon ajouté.
- Rien de ce dossier ne sort du PC (pas de commit, pas d'envoi).

## Fichiers

- `scripts/extraire_rapport.py` : PDF → dossier (texte, photos, structure, squelettes au format ci-dessus), option
  `--slug`. Dépendance : PyMuPDF.
- `scripts/rendu_html.py` : markdown du dossier → pages HTML lisibles avec vignettes des photos. Dépendance : markdown.
- `dimensionnement/savoir/methodes/checklist-releve.md` : les 16 points d'un relevé complet (numéros de la liste E).
- `dimensionnement/savoir/materiel/lecture-plaques.md` : comment lire une plaque, pièges, repères par marque.
