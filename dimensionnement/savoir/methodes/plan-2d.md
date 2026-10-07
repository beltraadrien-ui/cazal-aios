# Plans 2D de frigoriste (étape P)

> v1 du 2026-10-07 (Lots 5 et 6). Ce qu'est un plan ici, comment son échelle est garantie et vérifiée, comment se
> calculent le métré et les croisements, comment se lit un réseau tracé au marqueur. Sources : décisions de
> construction du 2026-10-07, exemple de plan du 2026-09-28 (local fictif), mesures de l'export draw.io faites sur le PC de
> construction le 2026-10-07, décisions d'Adrien du 2026-10-07. Aucune donnée client ici. La mécanique (scripts,
> boucle, commandes) est dans `.claude/skills/froid-plan-2d/SKILL.md` ; le dessin (styles, portes, identifiants) dans
> `.claude/skills/froid-plan-2d/references/conventions-plan-froid.md` ; les règles datées dans `regles-loic.md` (R14 à R19).

## 1. Ce qu'est un plan de frigoriste ici

- Une **vue de dessus** du local existant (murs, pièces, portes, fenêtres) avec ce que le frigoriste installe ou
  remplace : chambres froides, évaporateurs, centrales ou groupes, tableau électrique, splits et moteur de clim, et
  les **réseaux** qui les relient : cuivres froid (aspiration isolée, liquide), condensats, électricité (câbles et
  chemin de câbles), cuivres clim (gaz, liquide), et des réseaux libres (eau chaude, eau glacée, gaine…).
- **À quoi il sert** : le **métré** (mètres de cuivre et de câble pour la remise de prix ; Loïc demande au grossiste les
  prix du cuivre K65 du moment pour ses métrés, R8 et R11), une **pièce jointe** pour le fournisseur (Lot 7), un
  support de chantier imprimé.
- Il est **construit depuis un modèle en mètres** (`plan.json`) et non dessiné à la main : le dessin, le métré et la
  vérification lisent la même géométrie. Chaque cote garde sa source (télémètre, croquis, plan d'architecte, rapport).
  Une cote absente est une question, jamais une estimation (R19).

## 2. L'échelle et sa vérification

- **La règle n° 1** (décision d'Adrien du 2026-10-07) : le plan est à l'échelle et l'échelle se vérifie ; « 15 m de
  cuivre annoncés = 15 m réels ».
- draw.io compte **100 px par pouce** : 1 mm = 3,937 px. À l'échelle 1:S, 1 m = 3 937 / S px (1:50 → 78,74 ;
  1:100 → 39,37 ; 1:200 → 19,685). Échelles permises : 1:50, 75, 100, 125, 150, 200, 250, 300, 400, 500, 750, 1000.
- **Page A4** (une seule) : marges de 10 mm, cartouche de 22 mm en bas, réserve de 14 mm autour du dessin pour les
  cotes. Reste un cadre de 249 × 140 mm en paysage (162 × 227 mm en portrait), soit au 1:100 un dessin de 24,9 ×
  14 m, au 1:50 de 12,45 × 7 m, au 1:200 de 49,8 × 28 m. L'échelle choisie est la plus petite qui tient ; à égalité,
  le paysage. Le dessin est centré.
- **Cartouche** : échelle « 1:S », barre d'échelle (1 m jusqu'au 1:100, 2 m jusqu'au 1:200, 5 m au delà), **règle de
  contrôle de 100 mm** graduée tous les 10 mm, mention d'impression à 100 %, légende des calques.
- **Vérification à trois niveaux** : (1) le fichier draw.io relu et reconverti en mètres = le modèle à 1 cm (murs,
  portes, fenêtres, chambres, équipements, chaque point de chaque ligne ; chaque cote dessinée = sa valeur) ; (2) la
  barre d'échelle et la règle de contrôle à 0,5 px ; (3) le **PDF** relu : page A4, règle de 100 mm à 0,3 pt, barre
  d'échelle à 0,5 pt, trois plus longs murs à 1 pt (1 mm = 2,8346 pt).
- **Pourquoi calibrer le PDF** : draw.io Desktop exporte en PDF un peu réduit (0,245 % en A4 paysage, mesuré le
  2026-10-07 : 15 m au 1:50 sortent à 299,27 mm au lieu de 300). Le rendu mesure la règle de 100 mm dans le PDF,
  corrige le facteur et réexporte : l'écart tombe sous 0,05 %. Cette auto-calibration tient si draw.io change de
  version. Voie de secours (draw.io absent) : Edge et le viewer draw.io en ligne, exacts sans correction, même mesure.
- **Sur papier** : « taille réelle / 100 % », jamais « ajuster à la page » ; la règle de contrôle se vérifie au réglet
  (100 mm). La barre de 1 cm au 1:100 est trop courte pour juger : c'est la règle qui tranche.

## 3. Les calques

Ordre d'affichage (le premier est dessous) : Plan de base · Cotes · Froid, évaporateurs et centrales · Froid, cuivres
et condensats · Électricité (froid et clim) · Clim, splits et moteur · Clim, cuivres · calques libres (dans l'ordre
déclaré) · Croisements · Cartouche. Un calque se masque dans draw.io pour imprimer un seul réseau. Les identifiants des
éléments du dessin sont ceux du modèle (M1, CF1, EV1, LA1, C1, X1…) : c'est ce qui permet de relire un plan retouché.

## 4. Le métré

- **Formule** (une par ligne, écrite en toutes lettres dans `plan.md`) :
  métré = longueur du tracé en plan + |passage − départ| + |passage − arrivée| + réserve (câbles seulement).
  Exemple : « 6,40 m en plan + |2,60 − 2,30| + |2,60 − 0,50| = 8,80 m ».
- **Câble qui s'arrête sur le chemin de câbles** (`a` = le chemin, ou dernier point à 0,10 m du chemin) : on ajoute
  son parcours DANS le chemin, de la projection de son dernier point jusqu'à l'extrémité du chemin côté tableau,
  puis la descente au tableau et la réserve. Exemple : « 1,60 m en plan + 10,10 m dans le chemin de câbles CC1
  jusqu'à TD + |2,80 − 0,50| + |2,80 − 1,50| + 1,00 m de réserve = 16,30 m ». Colonne « Dans le chemin » des
  tableaux ; le chemin lui-même reste métré une fois, à part.
- **Hauteurs par défaut** (en m ; **hypothèses** tant que Loïc ne les a pas validées, R14) :

| Type de ligne | Départ | Passage | Arrivée | Réserve |
|---|---|---|---|---|
| Aspiration, liquide | évaporateur 2,30 | passage froid 2,60 | raccord groupe 0,50 | |
| Condensats | évaporateur 2,30 | 2,30 | évacuation 0,10 | |
| Clim gaz, clim liquide | split 2,20 | passage clim 2,20 | raccord moteur 0,50 | |
| Câble | selon l'équipement relié (évaporateur 2,30 ; groupe, centrale, condenseur 0,50 ; split 2,20 ; moteur 0,50 ; tableau 1,50) | chemin de câbles 2,80 | idem | 1,00 |
| Chemin de câbles | | | | longueur en plan seule |
| Réseau libre | 0 | passage froid 2,60 | 0 | |

- **Priorité** des hauteurs : celle écrite sur la ligne, puis celle de l'équipement relié (`hauteur`), puis celle du
  calque libre, puis la table `hauteurs` du plan, puis les défauts ci-dessus.
- **Arrondi** : chaque composante au centimètre, les totaux sont des sommes de valeurs arrondies (les tableaux
  s'additionnent exactement). Tableaux : par réseau, par type, par diamètre (« à définir » groupé en dernier).
- Le chemin de câbles compte dans le total du réseau électricité, à part dans le détail. Une ligne part et arrive au
  **centre** de son équipement (R15) : la longueur peut dépasser le raccord réel d'une demi-longueur d'appareil.
- Le métré est **recalculé depuis le fichier draw.io** par le vérificateur et comparé aux tableaux à 1 cm.

## 5. Les croisements

- Un croisement = deux lignes de **faisceaux différents** qui se coupent en plan (sur chantier : un réseau passe
  au-dessus de l'autre, un coude ou une hauteur à prévoir). Repère orange de 0,40 m sur le calque Croisements et
  tableau (point, lignes, calques).
- Les croisements distants de 0,50 m ou moins (de proche en proche) partagent un seul cercle, repère G1, G2…,
  étiqueté « X1-X3 » à côté du cercle ; le tableau garde une ligne par croisement, avec sa colonne « Repère ».
- Lisibilité (E8) : une étiquette posée sur le trait d'un autre élément (ligne, cote, attache) donne un
  avertissement ; on la déplace avec `position_etiquette` dans `plan.json`.
- Ne comptent pas : l'aspiration et le liquide d'un même évaporateur (même faisceau ; sans faisceau écrit, deux lignes
  qui relient les mêmes équipements) ; un contact à 5 cm ou moins de l'extrémité d'une ligne (départ commun, câble qui
  s'arrête sur le chemin de câbles) ; deux lignes posées l'une sur l'autre sur plus de 5 cm (recouvrement, signalé à part).

## 6. Feuille à repères et lecture des photos (Lot 6)

- **La feuille** : le plan de base en gris, à la **même échelle** que le plan ; 4 repères ArUco (dictionnaire 4 × 4,
  numéros 0 à 3, carrés de 16 mm centrés à 14 mm des bords : haut-gauche 0, haut-droite 1, bas-droite 2, bas-gauche 3),
  barre d'échelle, cadre d'identification (dossier, réseau, échelle, date), consignes. Une feuille par réseau.
- **Pourquoi des repères** : la photo est prise de travers. Les 16 coins des repères donnent la correspondance exacte
  entre la photo et les millimètres de la feuille (homographie) : ni la perspective, ni la rotation, ni une impression
  réduite uniformément ne faussent les longueurs.
- **Lecture** : redressement à 4 px/mm, retrait du plan imprimé, isolement de la couleur du marqueur, squelette du
  trait, polylignes simplifiées à 1,5 mm, conversion en mètres par l'échelle, accrochage (extrémité à 0,15 m d'un
  équipement : sur son centre ; à 0,10 m d'un mur : sur sa face ; segment à 7° ou moins de l'horizontale ou de la
  verticale : redressé). Une image de contrôle montre le trait lu sur la photo redressée.
- **Précision mesurée sur 218 photos synthétiques** (perspective jusqu'à 35°, flou, ombre, JPEG dégradé, impression à
  90 %) : écart de longueur au plus 0,80 %, en moyenne 0,13 % ; erreur de reprojection au plus 0,10 mm sur les
  130 photos en conditions courantes. **Pas encore
  de photo réelle** : validation prévue avec Adrien sur 2 ou 3 feuilles imprimées.
- **Seuil d'écart** (R16, hypothèse) : max(5 %, 0,30 m) par réseau entre la longueur lue et une longueur de référence ;
  au delà, la fusion dans le plan attend la confirmation de Loïc.

## 7. Limites

- Ni murs ni percements conçus ; aucun diamètre ni section choisis (« à définir par le dimensionnement », R18) ;
  pas de 3D (le vertical n'est que dans la formule) ; A4 seulement.
- Lot 6 : deux réseaux de même couleur sur une feuille ne sont pas séparés ; crayon et couleurs pâles non lus ; un
  piquage en T laisse une extrémité libre (question posée) ; feuille gondolée et ombre dure non testées ; une
  extrémité libre est lue 0,1 à 0,4 mm trop court sur le papier (1 à 4 cm au 1:100), biais connu non corrigé.
- Les hauteurs, l'accrochage au centre et le seuil d'écart sont des hypothèses (R14 à R16) en attente de Loïc.
