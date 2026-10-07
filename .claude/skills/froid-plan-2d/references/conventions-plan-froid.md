# Conventions des plans 2D froid et clim (`plan.json` → `plan.drawio`)

Sources : décision du 2026-10-07, exemple validé du 2026-09-28 ; code : `scripts/echelle.py`, `modele.py`, `drawio.py`.

## 1. Échelle et page (règle n° 1 : le plan est à l'échelle et l'échelle se vérifie)

- draw.io imprime à 100 px par pouce : 1 mm = 3,937 px. **A4** : 1169 × 827 px (paysage) ou 827 × 1169 px, `pageScale="1"`.
- Échelles normalisées 1:S, S ∈ {50, 75, 100, 125, 150, 200, 250, 300, 400, 500, 750, 1000} ;
  1 m = 1000 × 3,937 / S px (1:100 → 39,37 px/m). Grille draw.io = 10 cm arrondis au px.
- Marge 10 mm sur les quatre côtés (rien à moins de 20 px du bord), cartouche 22 mm en bas, réserve de
  14 mm autour du dessin. S = la plus petite échelle où la boîte englobante (cotes comprises) tient ;
  orientation = celle qui donne le plus petit S, paysage en cas d'égalité ; le dessin est **centré**.
  `page.echelle` imposée : respectée si elle tient, sinon erreur qui propose l'échelle minimale.
- Toute conversion m ↔ px passe par `Echelle.m_vers_px` / `px_vers_m` (ou `longueur_px` / `longueur_m`) ;
  géométrie écrite à 0,01 px. L'origine du modèle sur la page est gardée dans le style de la cellule
  `cartouche-echelle` (`plan2dOx`, `plan2dOy`) : c'est ce qui permet de relire en mètres.

## 2. Modèle (`plan.json`)

- Mètres ; x vers la droite (est), y vers le bas (sud) ; origine = coin haut-gauche du bâtiment.
- Équipement : `position` = centre, `dimensions` = [longueur, profondeur] avant rotation, `rotation` en
  degrés sens horaire. Défauts : évaporateur 1,2 × 0,5 ; centrale 1,5 × 0,8 ; groupe 1,0 × 0,6 ;
  condenseur 1,2 × 0,5 ; split 0,9 × 0,3 ; moteur 0,9 × 0,35 ; tableau 0,6 × 0,2 ; autre 0,5 × 0,5.
- Mur : `de` / `a`, `epaisseur` (défaut 0,20 extérieur, 0,10 cloison), `alignement` : `axe` (défaut), `droite`
  (épaisseur à droite du sens de/a : contour horaire par les faces extérieures → épaisseur vers l'intérieur), `gauche`.
- Fenêtre : `position` = centre dans l'épaisseur du mur, `largeur`, `orientation` 0/90 (180/270 équivalents),
  épaisseur = celle du mur `dans`.
- Cote : `de` / `a` = points mesurés, `valeur` = lecture du télémètre (|distance − valeur| ≤ 0,01 m, sinon
  erreur : on demande la bonne cote, on n'arrondit pas), `cote` = côté de la ligne de cote
  (haut / bas / gauche / droite, compatible avec la direction), `decalage` en m (défaut 0,60).
- Ligne : `points` du départ à l'arrivée ; le premier touche `de`, le dernier touche `a`, à 0,15 m près
  (équipement, chambre, mur ou autre ligne, ex. un câble qui part du chemin de câbles).
  Diamètres jamais inventés : « à définir » (par le dimensionnement).

## 3. Calques (cellules `parent="0"`, le premier est dessous)

`plan_de_base` Plan de base · `cotes` Cotes · `froid_equipements` Froid – évaporateurs et centrales ·
`froid_cuivres` Froid – cuivres et condensats · `electricite` Électricité (froid + clim) ·
`clim_equipements` Clim – splits et moteur · `clim_cuivres` Clim – cuivres · calques libres (ordre déclaré,
clé en minuscules) · `croisements` Croisements · `cartouche` Cartouche. Les chambres froides, portes,
fenêtres, pièces et équipements « autre » vont sur le plan de base ; le tableau sur l'électricité.

## 4. Identifiants

- Identifiant de cellule = identifiant du modèle (`M1`, `D1`, `F1`, `CF1`, `EV1`, `L1`, `CT1`, `X1`, `P1`…),
  uniques sur tout le plan. Cotes : préfixe **`CT`** (`CT1`, `CT2`…), jamais `C1…` : les repères `C1…Cn` écrits sur
  le plan sont ceux des câbles. Sous-éléments : `-txt` étiquette, `-int` paroi intérieure de chambre,
  `-porte` et `-porte-ouv` porte de chambre et son ouverture, `-ouv` ouverture du mur sous une porte,
  `-v1…` ventilateurs, `-fl` flèche de soufflage, `-a1` / `-a2` lignes d'attache d'une cote,
  `-contour` contour pointillé d'une pièce.
- Réservés : `0`, clés de calques, préfixes `cartouche`, `legende`, `barre-echelle`, `regle-controle`, `metre`.
- Chaque cellule porte des clés de style que draw.io conserve : `plan2d=<rôle>` (mur, porte, fenetre,
  chambre, equipement, ligne, cote, croisement, piece, etiquette, ouverture, ventilateur, soufflage, attache,
  cartouche, barre_echelle, regle_controle…), `plan2dGenre` (type d'équipement, de ligne, de mur, régime),
  `plan2dParent`, `plan2dDe` / `plan2dA` (lignes), `plan2dAxe` (x ou y : sens de la longueur d'un mur).

## 5. Styles

| élément | style |
|---|---|
| mur extérieur / cloison | rectangle plein `#424242` / `#757575`, sans trait |
| ouverture sous une porte | rectangle blanc sans trait, toute l'épaisseur du mur |
| porte | `shape=mxgraph.floorplan.doorLeft` (sens gauche) ou `doorRight` (sens droite), trait `#424242` |
| fenêtre | `shape=mxgraph.floorplan.window`, largeur × épaisseur du mur, `rotation` = orientation |
| chambre froide | double rectangle : panneau `#B0BEC5` / trait `#37474F` (positif, 80 mm) ou `#78909C` / `#263238` (négatif, 120 mm), intérieur blanc retrait = épaisseur réelle du panneau |
| évaporateur | `#E1F5FE` / `#0277BD` 1,5 + 1 ventilateur par 0,65 m + flèche pointillée de soufflage |
| centrale, groupe, condenseur | `#E3F2FD` / `#0D47A1` 2 + ventilateurs |
| split / moteur | arrondi `#BBDEFB` / `#1565C0` ; `#E8F5E9` / `#1B5E20` + 1 ventilateur |
| tableau / autre | `#F3E5F5` / `#6A1B9A` ; `#ECEFF1` / `#90A4AE` |
| aspiration | `shape=link;width=3;strokeColor=#1565C0` (isolée, double trait) |
| liquide | trait `#C62828` 1,5 |
| condensats | pointillé `3 3` `#00ACC1` 1,5, flèche ouverte à l'arrivée |
| clim gaz / clim liquide | `shape=link;width=2` `#2E7D32` / trait `#2E7D32` 1,5 |
| câble / chemin de câbles | `#6A1B9A` 1,5, repère `C1…Cn` / `#6A1B9A` 4, pointillé `6 3` |
| calque libre | couleur du calque, trait simple 1,5 ou double (`shape=link;width=3`) |
| cote | arête à deux flèches pleines `#546E7A`, texte « 12,50 m » (police 9, fond blanc) + attaches `#B0BEC5` |
| croisement | ellipse de 0,40 m, sans remplissage, `#FF6D00` 2,5 |

Lignes : arêtes droites (`edgeStyle=none`), `sourcePoint` / `targetPoint` / `Array` explicites, **sans**
`source=` / `target=` : la géométrie dessinée est exactement celle du modèle.
## 6. Portes : orientation, sens et géométrie

`position` = charnière, sur la face du mur côté battant. Boîte draw.io : largeur = `largeur`, hauteur =
largeur + 5 px (bandeau de 5 px du symbole), tournée de `orientation` autour de son centre.

| orientation | sens gauche (doorLeft) : ouverture → / battant ↓ | sens droite (doorRight) |
|---|---|---|
| 0 | vers l'est / vers le sud | vers l'ouest / vers le sud |
| 90 | vers le sud / vers l'ouest | vers le nord / vers l'ouest |
| 180 | vers l'ouest / vers le nord | vers l'est / vers le nord |
| 270 | vers le nord / vers l'est | vers le sud / vers l'est |

Un `flipH` ajouté dans draw.io inverse le sens ; un `flipV` inverse le sens et ajoute 180°.
## 7. Règles de placement

- Évaporateur contre la paroi opposée à la porte, soufflage vers la porte (défaut quand `soufflage` manque).
- Aucun équipement ni extrémité de ligne sur l'emprise d'une fenêtre ou d'une porte (cas réel : split
  devant une fenêtre). Une ligne finit sur son équipement (0,15 m).
- Aspiration + liquide d'un même évaporateur = un faisceau (ensemble, ne se « croisent » pas) ; sans
  `faisceau`, deux lignes qui relient les mêmes équipements sont du même faisceau.
- Étiquettes : `etiquette` (texte, « \n » = retour à la ligne, "" = aucune) et `position_etiquette`
  (centre, en m) ; par défaut au-dessus de l'équipement, au centre de la pièce ou de la chambre, au milieu
  du plus long segment d'une ligne. Aucun texte ne doit en chevaucher un autre, ni une porte, ni un
  équipement (sinon : donner `position_etiquette`).

## 8. Cartouche (bande de 22 mm en bas)

Titre (`cartouche-titre`), dossier (`cartouche-dossier`), date (`cartouche-date`), « Échelle 1:S »
(`cartouche-echelle`), barre d'échelle `barre-echelle` (1 m si S ≤ 100, 2 m si S ≤ 200, sinon 5 m ;
longueur exacte en px) + `barre-echelle-txt`, mention `cartouche-mention` « Imprimer à 100 %, sans
ajustement à la page : la barre doit mesurer X cm à la règle », **règle de contrôle** `regle-controle` de
100 mm exactement (393,70 px, graduations `regle-controle-g0…g10` tous les 10 mm, texte `regle-controle-txt`) :
elle sert à mesurer l'échelle réelle du PDF exporté et à la vérifier au réglet. Légende des calques à droite.
Page 2 « Métré » : tableaux HTML (`metre-tableau-N`, titre `metre-tableau-N-titre`).

## 9. Lecture d'un fichier retouché dans draw.io Desktop

Tout se retrouve par identifiant et clés `plan2d`, jamais par position (attributs réordonnés, styles enrichis,
cellules ajoutées, `<object>`, page compressée, groupes).
Arête raccordée à la main (`source` / `target`) : relue de bord à bord ; routée par draw.io (`edgeStyle` ≠ none) :
points approximatifs (avertissement). Ne pas déplacer tout le dessin d'un bloc (l'origine du cartouche ne suit pas).
