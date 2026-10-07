---
name: froid-plan-2d
description: Plan 2D de frigoriste à l'échelle (étape P d'un dossier, Cazal Réfrigération) ; à partir d'une description dictée avec les cotes au télémètre, d'un croquis photographié, d'un plan d'architecte en PDF ou du relevé InterFast, écrit le modèle plan.json, dessine plan.drawio en A4 à une échelle normalisée (barre d'échelle, règle de contrôle de 100 mm), calcule le métré de chaque réseau et les croisements, vérifie l'échelle jusque dans le PDF, reprend les retouches faites à la souris dans draw.io et lit la photo d'un réseau tracé au marqueur sur une feuille imprimée ; se déclenche sur « plan », « plan 2D », « dessine le local », « trace les réseaux », « métré », « feuille à imprimer », « photo du tracé », « draw.io ».
---

# Plans 2D du frigoriste : étape P d'un dossier (Cazal Réfrigération)

> **Pour Loïc** : pour les plans, passe sur Opus avec /model avant de commencer : c'est le modèle qui lit le mieux
> les croquis et les rendus.

## Ce que fait cette skill

Loïc décrit un local (ou donne un croquis, un plan d'architecte, un relevé) **avec ses cotes**. Claude écrit le modèle
`plan.json` (en mètres) ; les scripts dessinent, mesurent et vérifient. Dans `dimensionnement/dossiers/<slug>/plan/` :

- `plan.drawio` : page « Plan » (A4, échelle 1:S écrite dans le cartouche, un calque par réseau) et page « Métré » ;
- `plan.pdf` (à imprimer) et `plan.png` (relecture) ; `plan.md` + `plan.html` (ce que Loïc lit, sans aucun code de
  ligne) : le plan en image, les chambres et les équipements avec leur emplacement en mots, le métré en un tableau par
  réseau (tronçon en noms, en plan, montées et descentes, total) et son récapitulatif, les croisements en mots (un par
  repère G), les cotes et ce qu'elles mesurent, les hauteurs de pose, les questions ouvertes, des détails techniques
  courts ; `metre-detail.md` (mémoire de Claude, non rendue en HTML) : métré par ligne avec codes, formules, hauteurs
  et diamètres, métré par diamètre, croisements un par un, calques, notes du relevé ; `verification.md` : dernier contrôle ;
- Lot 6 : une feuille A4 à repères par réseau, que Loïc trace au marqueur et photographie ; la photo devient un calque.

L'étape P est **indépendante** des étapes 1 à 3 : avant ou après l'étape 2. Le métré nourrira l'étape 2 (longueurs de
lignes) et le PDF l'étape 3 (pièce jointe, point f) ; ce branchement est prévu au Lot 7, il n'existe pas encore.
Lire d'abord `dimensionnement/CLAUDE.md` (règles de fiabilité). **Claude n'écrit que `plan.json`** (et `dossier.md`) :
le dessin, les tableaux, les PDF et les rapports sortent des scripts, jamais d'une retouche à la main.

## La règle n° 1 : le plan est à l'échelle, et l'échelle se vérifie

« 15 m de cuivre annoncés = 15 m réels. »

- **A4, une page, échelle normalisée choisie automatiquement** : S ∈ {50, 75, 100, 125, 150, 200, 250, 300, 400, 500,
  750, 1000}, la plus petite où le bâtiment, ses cotes et ses étiquettes tiennent (paysage ou portrait, paysage à
  égalité). Repère : au 1:100 en paysage, le dessin peut faire 24,9 × 14 m (un local de 16 × 11 m y tient).
  `page.echelle` imposée dans `plan.json` est respectée si elle tient, sinon erreur qui donne l'échelle minimale.
- **Cartouche** : « Échelle 1:S », barre d'échelle (1 m jusqu'au 1:100, 2 m jusqu'au 1:200, 5 m au delà), **règle de
  contrôle de 100 mm** graduée, mention « Imprimer à 100 %, sans ajustement à la page… ».
- **Sur papier** : imprimer en « taille réelle / 100 % », jamais « ajuster à la page » ; poser un réglet sur la règle
  de contrôle : elle doit faire 100 mm. Sinon l'impression est réduite et le plan ne se mesure pas.
- **Ce que `verifier_plan.py` mesure** : (1) le fichier : chaque mur, porte, fenêtre, chambre, équipement et chaque
  point de ligne relu dans le XML et reconverti en mètres = `plan.json` à 1 cm ; chaque cote dessinée = sa valeur à
  1 cm ; (2) la barre d'échelle et la règle de contrôle à 0,5 px ; (3) **le papier** : `plan.pdf` relu avec PyMuPDF,
  page A4, règle de 100 mm à 0,3 pt, barre d'échelle à 0,5 pt, trois plus longs murs à 1 pt (1 pt = 0,35 mm).
- **Le PDF** (pages « Plan » et « Métré ») sort de draw.io Desktop en ligne de commande, **calibré sur la règle de
  100 mm** : `rendu.py` exporte, mesure la règle dans le PDF, corrige le facteur (`-s`), réexporte et remesure (écart
  admis 0,05 % ; sans correction, draw.io réduit de 0,245 %, mesuré sur ce PC le 2026-10-07). Le facteur est gardé
  dans `plan/rendu.json` et revérifié à chaque rendu. Secours si draw.io manque : Edge et le viewer draw.io en ligne
  (Internet nécessaire, page « Plan » seule), même mesure. `plan.png` = la page 1 du PDF rasterisée par PyMuPDF.

## À relire à chaque dossier

- `<dossier>/dossier.md`, `1-existant.md` s'il existe, `sources/` ; et s'il y a déjà un plan : `plan/plan.json`,
  `plan/plan.md` (journal des versions), `plan/verification.md`.
- `dimensionnement/carnet/lecons.md` s'il existe ; `savoir/methodes/plan-2d.md` (métré, hauteurs, seuils) ;
  `savoir/methodes/regles-loic.md` R14 à R19 ; `references/conventions-plan-froid.md` (styles, portes, identifiants).

## Les entrées acceptées

| Entrée | Ce que Claude en tire | Source écrite sur chaque cote |
|---|---|---|
| Description dictée + cotes au télémètre | murs, pièces, portes, chambres, équipements, tracés | `télémètre, dicté par Loïc le AAAA-MM-JJ` |
| Croquis photographié + cotes (`sources/`) | la disposition et les cotes écrites ; **jamais une mesure prise sur le croquis** | `croquis sources/<photo>, cote écrite` |
| Plan d'architecte PDF (`sources/`) | chaque page rendue en image et regardée ; les cotes écrites sur le plan | `plan architecte p. N, cote écrite` |
| Relevé InterFast (`1-existant.md`, `sources/rapport-texte.md`) | l'inventaire : chambres, régimes, évaporateurs par chambre, centrales et groupes | `rapport p. N` ; positions et cotes : à demander |

Une longueur mesurée sur un dessin (et non écrite) sert à poser la question, jamais à remplir `plan.json`. Rendre un
PDF page par page pour le regarder (dans le répertoire temporaire de la session) :

```
python -c "import pymupdf,sys; [p.get_pixmap(dpi=150).save(f'{sys.argv[2]}/page-{i+1}.png') for i,p in enumerate(pymupdf.open(sys.argv[1]))]" <plan.pdf> <dossier temporaire>
```

## Écrire `plan.json`

**D'abord la liste des cotes.** Avant d'écrire, Claude donne à Loïc, court, chaque cote avec sa valeur et sa source, puis
**ce qui manque, en questions** (« Il me manque la largeur de la chambre négative et la position de la porte du labo
depuis le coin nord-ouest »). **Cote manquante = question ; jamais une longueur estimée**, ni « environ », ni valeur
« habituelle ». Seuls défauts permis, écrits dans `notes` : dimensions d'équipement par type, épaisseurs de mur (0,20
extérieur, 0,10 cloison), hauteurs de pose (hypothèses R14). Un emplacement que Loïc ne précise pas (« le groupe est
dans la cour ») se place en principe, est écrit dans `notes` et devient une question : il change le métré.

Schéma complet : `references/conventions-plan-froid.md` (décision du 2026-10-07). Exemple : la fixture
`dimensionnement/dossiers/2026-09-28-boucherie-test/plan/` (`description.md` = ce qu'on dicterait, `plan.json` = le
modèle ; copie suivie dans le dépôt : `scripts/tests/fixtures/a1-boucherie-plan.json`). L'essentiel :

- **Repère** : mètres ; origine (0 ; 0) = coin haut-gauche extérieur du bâtiment (nord-ouest si le nord est en haut) ;
  **x vers la droite (est), y vers le bas (sud)**. Dire à Loïc quel coin est l'origine : ses positions en partent.
- **Murs** `de`, `a`, `epaisseur`, `type` (`exterieur` | `cloison`), `alignement` (`droite` pour un contour décrit dans
  le sens horaire par les faces extérieures). **Pièces** : `polygone`, `etiquette`.
- **Chambres froides** : rectangle extérieur, `regime` (`positif` | `negatif`), `panneau_mm` (80 | 120), `porte`.
- **Portes** : `position` = la charnière, sur la face du mur côté battant ; `largeur` ; `dans` (le mur) ; `orientation`
  (0, 90, 180, 270) et `sens` (`gauche` par défaut). En sens gauche : ouverture vers l'est et battant vers le sud = 0 ;
  vers le sud et l'ouest = 90 ; vers l'ouest et le nord = 180 ; vers le nord et l'est = 270 (table : conventions §6).
- **Fenêtres** : centre dans l'épaisseur du mur, `largeur`, `orientation` 0 (mur horizontal) ou 90.
- **Équipements** : `type` (`evaporateur`, `centrale`, `groupe`, `condenseur`, `split`, `moteur`, `tableau`, `autre`),
  `position` = centre, `dimensions` [longueur, profondeur] avant `rotation` (défauts : évaporateur 1,2 × 0,5 ;
  centrale 1,5 × 0,8 ; groupe 1,0 × 0,6 ; condenseur 1,2 × 0,5 ; split 0,9 × 0,3 ; moteur 0,9 × 0,35 ; tableau
  0,6 × 0,2 ; autre 0,5 × 0,5), `chambre`, `soufflage`. Évaporateur contre la paroi opposée à la porte, soufflage
  vers la porte. Jamais devant une porte ou une fenêtre.
- **Cotes** : `id` **`CT1`, `CT2`…** (préfixe CT : `C1…Cn` sont les repères des câbles sur le plan), `de`, `a` (les
  deux points mesurés), `valeur` (le télémètre), `source`, `cote` (côté : haut, bas, gauche, droite), `decalage` (m). **|distance(de, a) − valeur| ≤ 0,01 m**, sinon erreur : une description incohérente se
  dit à Loïc, on n'arrondit pas en silence.
- **Lignes** : `id`, `type` (`aspiration`, `liquide`, `condensats`, `clim_gaz`, `clim_liquide`, `cable`,
  `chemin_cables`, ou la clé d'un calque libre), `de`, `a` (équipement, chambre, mur ou autre ligne ; `null` pour des
  condensats qui sortent du bâtiment), `points` du départ à l'arrivée (premier et dernier point à 0,15 m de leur
  équipement), `faisceau` (aspiration + liquide d'un même évaporateur), `diametre: "à définir"`, `hauteur_depart`,
  `hauteur_passage`, `hauteur_arrivee` (vides = défauts), `repere` (câbles C1…), `etiquette`, `position_etiquette`.
- **Calques libres** (`eau_chaude`, `eau_glacee`, `gaine`…) : `cle`, `nom`, `couleur`, `trait` (simple | double).
- **`exigences`** : une exception à la complétude (`{"CF1": {"cable": "non_requis", "motif": "câble existant
  conservé"}}`, motif obligatoire) transforme l'erreur en avertissement.
- **`hauteurs`** (table R14) et **`hauteurs_validees`** (`false`, ou la liste des hauteurs que Loïc a validées).

## La boucle : dessiner, vérifier, corriger (5 tours au plus)

1. **Générer** (code 1 : `plan.json` invalide, toutes les fautes listées d'un coup ; corriger et relancer) :
   ```
   PYTHONUTF8=1 python .claude/skills/froid-plan-2d/scripts/generer.py dimensionnement/dossiers/<slug>/plan
   ```
   `--sans-rendu` : sans PDF ni PNG (tours rapides) ; `--ouvrir` : ouvre `plan.html` dans le navigateur. Chaque
   génération est une version `vN` (copie `versions/plan-vN.drawio` et `.json`, ligne dans `journal.md`).
2. **Vérifier** (code 0 = 0 erreur, 1 = erreurs, 2 = fichier manquant ; rapport dans `verification.md` : code,
   gravité, élément, attendu, trouvé, conseil de correction ; même contenu dans `verification.json`) :
   ```
   PYTHONUTF8=1 python .claude/skills/froid-plan-2d/scripts/verifier_plan.py dimensionnement/dossiers/<slug>/plan
   ```
   `--sans-pdf` seulement pendant les tours rapides ; **le dernier tour se fait toujours avec le PDF**. Contrôles :
   E1 échelle du fichier, E2 cotes, E3 barre d'échelle, E4 tout dans la page, E5 complétude (porte, évaporateur,
   aspiration, liquide, condensats et câble par chambre ; gaz, liquide et câble par split), E6 tableaux = recalcul
   depuis le XML (page « Métré », `metre-detail.md` ligne par ligne, `plan.md` par réseau et récapitulatif), E7
   croisements, E8 textes qui se chevauchent, E9 cohérence (calques, rien sur une porte ou une fenêtre, extrémités
   de lignes), E10 PDF, E11 PNG. Croisements : ceux à 0,50 m ou moins l'un de l'autre partagent
   un seul cercle (repère G, étiquette « X1-X3 » posée à côté) ; les tableaux gardent une ligne par croisement avec
   la colonne « Repère ». E8 avertit aussi quand une étiquette est posée sur le trait d'un autre élément (ligne,
   cote, attache) : la déplacer avec `position_etiquette` dans `plan.json` (équipements, pièces, chambres, lignes).
3. **Corriger `plan.json`** d'après le conseil (jamais `plan.drawio`, `plan.md` ni le PDF à la main), puis 1 et 2.
4. **Arrêt à 0 erreur.** Après 5 tours avec des erreurs : s'arrêter et dire ce qui reste (code, élément, pourquoi) et
   la question qui le débloque (souvent une cote incohérente). Chaque avertissement est lu : une étiquette se déplace
   (`position_etiquette`), le reste se dit à Loïc.
5. **Relire le PNG** (Claude ouvre `plan.png`) : ce qu'un script ne voit pas. Vraisemblance (évaporateur dans sa
   chambre, face à la porte ; groupe dehors ou en local technique ; une ligne qui traverse une chambre froide ou une
   pièce sans raison) ; oublis (un équipement dicté absent, un réseau dicté non tracé) ; placements absurdes ; texte
   illisible ou trop petit ; cartouche et légende lisibles. Un défaut : corriger `plan.json`, reprendre en 1.
6. **Montrer à Loïc ✋** : ouvrir `plan.pdf` (`Start-Process`) et `plan.html` (`--ouvrir`). Présenter court : échelle
   et orientation, ce qui est dessiné, le métré par réseau **recopié de `plan.md`** (aucun nombre de tête), les
   croisements, puis les « Questions ouvertes » de `plan.md` (extrémités libres, hauteurs en hypothèse, diamètres à
   définir, exceptions). Lui demander de vérifier la règle de 100 mm au réglet après impression. Puis `dossier.md`.

## Modifier à la voix

Claude édite `plan.json`, puis générer, vérifier, relire le PNG. Le sens des mots, sur la feuille (nord en haut) :

| Loïc dit | Dans `plan.json` |
|---|---|
| « remonte l'évaporateur de 10 cm » | `position` : y − 0,10 (vers le haut de la feuille, donc y diminue) |
| « descends-le de 10 cm » / « décale à droite de 20 cm » / « à gauche » | y + 0,10 / x + 0,20 / x diminue |
| « tourne le split » / « souffle vers la porte » | `rotation` (90, 180, 270) / `soufflage` (haut, bas, gauche, droite) |
| « pose-le à 2,40 », « plus haut au mur » | c'est une **hauteur** : `hauteur` de l'équipement ou `hauteur_*` de la ligne (métré) |
| « la chambre fait 4,10, pas 4,00 » | la `valeur` de la cote **et** la géométrie (chambre, murs, porte) ensemble |

- « Remonter » est ambigu (sur le plan ou au mur) : une question courte en cas de doute.
- Un équipement déplacé emmène ses lignes : déplacer aussi le premier ou le dernier point (et le point voisin, pour
  garder les angles droits) ; sinon E9.

## Modifier à la souris (draw.io Desktop)

1. Loïc ouvre `plan.drawio` (double clic : draw.io Desktop est installé), déplace ou retrace, **enregistre (Ctrl+S) et
   ferme draw.io** : sinon un enregistrement plus tard écraserait le plan regénéré.
2. Claude relit les retouches, d'abord en aperçu (rien n'est écrit), puis pour de bon (`plan.json` est d'abord copié
   en `versions/plan.json.avant-import-…` ; code 0 = fait ou rien à importer, 1 = illisible, 2 = manquant) :
   ```
   PYTHONUTF8=1 python .claude/skills/froid-plan-2d/scripts/importer_drawio.py dimensionnement/dossiers/<slug>/plan --apercu
   PYTHONUTF8=1 python .claude/skills/froid-plan-2d/scripts/importer_drawio.py dimensionnement/dossiers/<slug>/plan
   ```
   Reviennent : position et rotation des équipements, tracé des lignes (coudes ajoutés ou retirés), portes et
   fenêtres, lignes nouvelles tracées dans un calque réseau (`L-nouveau-N`, type déduit du calque, `de` / `a` si une
   extrémité est à 0,15 m d'un équipement, sinon question ; Claude les renomme et complète `faisceau` avec Loïc).
   **Ne reviennent pas** : murs, chambres, pièces, cotes, étiquettes (le relevé fait foi : avertissement s'ils
   diffèrent ; ils se changent en le disant à Claude) ; un élément supprimé est signalé, pas supprimé.
3. Générer, vérifier, relire le PNG, comme dans la boucle.

À dire à Loïc, simplement : **ne pas déplacer tout le dessin d'un bloc** (l'import détecte un décalage commun de
tous les murs et le recale, mais c'est une source d'erreur) ; **ne changer ni la page, ni le format, ni l'échelle** ;
tracer une nouvelle ligne dans le bon calque (Affichage, Calques), en trait droit, pas en connecteur automatique.

## Lot 6 : tracer un réseau au marqueur sur une feuille imprimée

1. **La feuille** (après `generer.py`, qui écrit `plan-base.json` : échelle, orientation, origine en mm) :
   ```
   PYTHONUTF8=1 python .claude/skills/froid-plan-2d/scripts/feuille.py dimensionnement/dossiers/<slug>/plan --reseau froid_cuivres --type aspiration
   ```
   `--reseau` : `froid_cuivres`, `clim_cuivres`, `electricite` ou la clé d'un calque libre ; sans `--type` :
   `aspiration`, `clim_gaz`, `cable` ou la clé du calque libre ; `--sans-pdf` : PNG et JSON seulement. Une feuille par
   réseau, et chaque ligne lue prendra ce type. Elle porte le plan de base en gris **à la même échelle que le plan**,
   4 repères aux coins (carrés noirs et blancs de 16 mm), la barre d'échelle, le cadre d'identification et les
   consignes ; elle est contrôlée (PDF A4, repères relus à 0,5 mm) : code 1 = ne pas l'imprimer. Sorties :
   `feuilles/feuille-<reseau>.pdf`, `.png`, `.json`. Ne pas la regénérer entre l'impression et la lecture de la photo.
2. **Consignes à Loïc** : imprimer en A4 à 100 % (si l'imprimante coupe un repère, « ajuster à la page » est permis
   pour cette feuille : les mesures se font par rapport aux repères) ; **marqueur rouge, bleu ou vert** (le noir est
   lu, moins sûr) ; un trait continu par tronçon ; rien dans les repères, le cadre, ni au bord ; photo de dessus,
   feuille à plat, les 4 repères entiers, sans flash ; déposer la photo dans `plan/photos/`.
3. **Lire la photo** (calque seul, rien n'entre encore dans le plan) :
   ```
   PYTHONUTF8=1 python .claude/skills/froid-plan-2d/scripts/lire_photo.py dimensionnement/dossiers/<slug>/plan dimensionnement/dossiers/<slug>/plan/photos/<photo>.jpg --reseau froid_cuivres
   ```
   Options : `--marqueur auto|rouge|bleu|vert|noir` ; `--longueur-attendue M` (longueur de référence du réseau, si Loïc
   l'a mesurée : déclenche le contrôle d'écart) ; `--accrochage centre|bord` (centre par défaut, hypothèse R15) ;
   `--fusionner` ; `--confirmer`. Sorties : `calques/<reseau>.json` (tronçons en mètres, longueur, `de`, `a`,
   confiance, erreur de reprojection, questions) et `calques/<reseau>-controle.png` (photo redressée, tracé lu en
   couleur, équipements accrochés). Code 1 : repère manquant (il est nommé) ou aucun trait : reprendre la photo.
4. **Regarder le PNG de contrôle et le montrer à Loïc**, avec la longueur de chaque tronçon et les questions
   (« extrémité libre à (x ; y) : relier à quel équipement ? »).
5. **Fusionner** quand il est d'accord : relancer avec `--fusionner`. `plan.json` est sauvegardé
   (`versions/plan.json.avant-fusion-…`), les lignes d'une photo précédente du même réseau sont remplacées, les
   nouvelles portent `source: "photo"` et `diametre: "à définir"`. Écart avec `--longueur-attendue` au delà de
   **max(5 %, 0,30 m)** : avertissement et fusion refusée ; `--confirmer` seulement si Loïc accepte l'écart.
6. **Compléter `plan.json`** (extrémités `null`, `faisceau`, hauteurs ; une ligne liquide sur le même tracé seulement si
   Loïc le confirme), puis générer, vérifier, relire le PNG.

## Ce que le plan ne fait pas

- **Ni murs ni percements** : il dessine les murs relevés ; il ne conçoit ni cloison ni carottage, et une traversée de
  mur n'est ni cotée ni décrite.
- **Aucun diamètre choisi** : « à définir par le dimensionnement », toujours ; aucune section de câble non plus.
- **Pas de 3D** : le vertical n'existe que dans le métré (formule avec les hauteurs de pose). Un câble qui
  s'arrête sur le chemin de câbles (`a` = le chemin, ou dernier point à 0,10 m du chemin) compte en plus son
  parcours dans le chemin jusqu'à l'extrémité côté tableau (colonne « Dans le chemin »), puis la descente au
  tableau et la réserve ; le chemin lui-même est métré une fois, à part.
- Pas de lecture automatique d'un plan d'architecte ou d'un croquis (Claude les regarde, les cotes écrites font foi) ;
  pas d'A3 ; pas de branchement vers les étapes 2 et 3 avant le Lot 7. Lot 6 : deux réseaux de même couleur sur une
  feuille ne sont pas séparés, le crayon et les couleurs pâles ne sont pas lus ; pas encore validé sur photo réelle.
  Une extrémité **libre** (non accrochée à un équipement ou à un mur) est lue 0,1 à 0,4 mm trop court sur le
  papier (1 à 4 cm au 1:100) : biais connu, non corrigé (voir le journal du Lot 6) ; les extrémités accrochées
  n'ont pas ce biais.

## Où vivent les fichiers

```
dimensionnement/dossiers/<slug>/plan/
├── plan.json              ← le modèle en mètres : le seul fichier que Claude écrit
├── plan.drawio            ← pages « Plan » et « Métré » (s'ouvre dans draw.io Desktop)
├── plan.pdf, plan.png     ← le plan sur une page A4 à l'échelle, le métré sur une ou deux pages A4 selon
│                            sa longueur ; plan.png = image du plan pour la relecture
├── plan.md, plan.html     ← vue lisible : plan, contenu, métré par réseau, croisements, cotes, hauteurs, questions
│                            (Loïc lit le .html ; aucun code de ligne)
├── metre-detail.md        ← mémoire : métré par ligne (codes, formules, diamètres), croisements un par un, notes
├── plan-base.json         ← échelle, orientation, origine en mm (repris par les feuilles du Lot 6)
├── rendu.json             ← facteur de calibration du PDF (règle de 100 mm), revérifié à chaque rendu
├── verification.md, .json ← dernier rapport de verifier_plan.py
├── journal.md             ← une ligne par génération (version, échelle, lignes, croisements, rendu)
├── versions/              ← plan-vN.drawio + plan-vN.json à chaque génération ; sauvegardes avant import, fusion
├── feuilles/              ← feuille-<reseau>.pdf, .png, .json (Lot 6)
├── photos/                ← photos des feuilles tracées (croquis et plans d'architecte : <dossier>/sources/)
└── calques/               ← <reseau>.json + <reseau>-controle.png
```

## Mettre à jour `dossier.md`

- Une ligne **« Plan »** sous « Étape en cours » (elle ne la remplace pas) : `**P · Plan — vN à relire ✋**` (`plan/`,
  date), puis « P · Plan — vN validé le … » quand Loïc le dit.
- **Hypothèses** : les hauteurs encore non validées, les emplacements de principe. **Questions** : cotes manquantes,
  extrémités libres. **Journal** : date, version, « 0 erreur, N avertissements ». Puis
  `PYTHONUTF8=1 python shared/rendu_html.py dimensionnement/dossiers/<slug>/dossier.md`.
- Chaque correction de Loïc (cote, placement, hauteur) va dans `dimensionnement/carnet/lecons.md` ; une hauteur qu'il
  valide entre dans `hauteurs_validees` et est signalée à Adrien pour `regles-loic.md`.

## Hypothèses en attente de Loïc (écrites « hypothèse » dans `plan.md` tant qu'il ne les a pas validées)

| Sujet | Hypothèse | Règle |
|---|---|---|
| Hauteurs de pose (m) | évaporateur 2,30 ; passage froid 2,60 ; raccord groupe 0,50 ; tableau 1,50 ; chemin de câbles 2,80 ; réserve de câble 1,00 ; split 2,20 ; passage clim 2,20 ; raccord moteur 0,50 ; condensats : passage 2,30, évacuation 0,10 | R14 |
| Départ et arrivée d'une ligne | au centre de l'équipement | R15 |
| Écart accepté photo / référence | max(5 %, 0,30 m) par réseau | R16 |
| Format | A4 seulement ; le plan sur une page A4, le métré sur une ou deux pages A4 selon sa longueur, et dans la vue HTML | R17 |

## Règles fermes

- **Cote manquante = question** ; aucune longueur estimée, aucun diamètre inventé.
- **`verifier_plan.py` à 0 erreur** (avec le PDF) et PNG relu avant de montrer le plan à Loïc ; sinon, le rapport de
  ce qui reste après 5 tours.
- Les nombres montrés à Loïc viennent de `plan.md` (script), jamais d'un calcul de tête.
- **Confidentialité** : tout `dimensionnement/dossiers/` est local (gitignoré) ; plans, photos, adresses et noms de
  clients ne vont jamais sur GitHub ; les fixtures des tests sont fictives ; rien n'est envoyé par le système.
- Construction et essais (Adrien) : aucune question à Loïc ; elles vont dans la liste privée remise à la livraison.

## Fichiers et tests

- `scripts/echelle.py` (seule conversion mètres ↔ px), `modele.py` (lecture et validation de `plan.json`),
  `geometrie.py`, `drawio.py` (écriture et lecture du `.drawio`), `metre.py`, `croisements.py` (contrôles rapides :
  `python <script> <plan.json>`), `rendu.py` (PDF calibré, PNG), `generer.py`, `verifier_plan.py`,
  `importer_drawio.py` ; Lot 6 : `feuille.py`, `lire_photo.py`, `photo_synthetique.py` (photos de test).
- Dépendances : PyMuPDF, numpy, opencv-python (repères ArUco), Pillow ; draw.io Desktop (Microsoft Store) ; Edge en
  secours. `shared/rendu_html.py` pour les vues HTML.
- Tests (racine du dépôt ; unittest, pytest n'est pas installé ; la lecture des photos prend une demi-minute) :
  `PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-plan-2d/scripts/tests -v`
