# Règles de Loïc (dimensionnement et demande fournisseur)

> v1 du 2026-10-06 (Lot 2), complétée le 2026-10-07 (Lot 3 : R9 à R13, demande fournisseur ; Lots 5 et 6 : R14 à
> R20, plans 2D, en hypothèse tant que Loïc ne les a pas validées, sauf R18 et R20 qui sont des décisions d'Adrien). Chaque règle est
> **datée et sourcée**. Sources : « conversation Claude de Loïc
> du 16/09/2026 » (numéro de capture d'écran) et « visio du 24/09/2026 » (minute de l'enregistrement).
> Une règle énoncée pour un seul dossier est marquée « observé sur le dossier test, à généraliser avec Loïc »
> (statut hypothèse) ; le **dossier test** est le chantier réel qui a servi à construire le système (septembre
> 2026) : ses particularités (nombres, implantation, fluide) ne valent pas pour une autre affaire. Les réponses de
> Loïc aux six questions du 2026-10-06 s'ajoutent en fin de fichier, avec leur date. Toute correction de
> Loïc à l'usage modifie la règle ici (et le pourquoi va dans `carnet/lecons.md`).

## R1. Régimes de calcul

- **Évaporation −30 °C en négatif, −10 °C en positif.** Conversation du 16/09/2026, capture 2.
- **Condensation +40 °C.** Conversation du 16/09/2026, capture 4 : « Condensation +40 °C, sors-moi
  l'estimation kW ». Donnée quand Claude l'a demandée.
- Non précisé par Loïc : la surchauffe ou la température du gaz aspiré, et, pour les mélanges, point de
  rosée ou température moyenne. En attendant : hypothèses de `puissance-existante.md` §2 (question 1).
- Remarque du 16/09 (capture 4) : avec une récupération de chaleur, la condensation peut tourner plus haut
  que +40 °C. Non tranché.

## R2. Partir de la puissance existante

- **On part de la puissance existante**, puis on fait « du similaire avec le matériel d'aujourd'hui ».
  Visio du 24/09/2026, 37:08 à 37:50 : « on va remplacer par une centrale CO2, donc d'abord […] les
  puissances existantes » ; « le plus simple, c'est soit de partir des volumes de chambres froides, soit
  […] sur la puissance existante » ; « des fois ils mettent des trucs un peu trop gros, mais tu es quand
  même toujours plus ou moins dans le bon ».
- **Pourquoi** : un calcul théorique peut être juste si l'isolation est mal faite, alors que l'existant
  « tourne comme ça, ça fait déjà du froid comme ça » (visio du 24/09/2026, 37:39).
- Note : la transcription automatique attribue certaines de ces phrases au mauvais interlocuteur ; la règle
  est celle de Loïc (plan validé du 2026-10-06, §1).

## R3. Précision attendue

- **Remise de prix : « on n'est pas à la virgule près »** ; après signature, il faut être plus pointu
  (mode « exécution », tout confirmé par le fournisseur). Visio du 24/09/2026, 34:29 à 36:07.
- **Mais un chiffre faux coûte cher** : « s'il y a une erreur sur un chiffre, tu vas l'envoyer au
  fournisseur et ensuite tu commandes le mauvais compresseur ». Visio du 24/09/2026, 14:00.
- Conséquence pour le système : chaque chiffre porte sa source et son statut ; la sélection finale du
  matériel reste chez le fournisseur.

## R4. Ce qu'il envoie aux grossistes et fournisseurs (observé sur le dossier test, à généraliser avec Loïc)

> **Statut : hypothèse** pour tout ce qui décrit l'installation ou le partage des tableaux : c'est ce que Loïc a fait
> sur le dossier test. Le but et l'anonymat valent pour toute demande.

- **Le but** : un mail de demande d'offre de prix, avec la capacité frigorifique actuelle, que le
  fournisseur utilise pour sélectionner le matériel. Conversation du 16/09/2026, capture 2.
- **Sans nom de client** : présenter l'installation sans la nommer (sur le dossier test : « une centrale HFC au R449
  à passer en CO2 booster »), la solution restant adaptée à ce que propose le fournisseur. Conversation du
  16/09/2026, capture 9.
- **Mail aux grossistes** (version complète) : introduction (soumission pour un marché de remodeling,
  offre de prix compétitive, installation complète de A à Z), renvoi au dossier photo, puis tableaux
  1. chambres à traiter, 2. production frigorifique existante, 3. évaporateurs en place, puis la demande
  d'offre détaillée. Conversation du 16/09/2026, captures 12 et 17 à 19.
- **Mail au fournisseur de la centrale CO2 (dossier test) : deux tableaux seulement**, « chambres à traiter » et
  « puissance frigorifique existante » (pas d'évaporateurs ni d'armoire). Conversation du 16/09/2026,
  message daté du 24/09, capture 21.
- **Format** : tableaux qui passent au copier-coller dans Outlook (version HTML) ; dossier photo des
  plaques classé par poste, envoyé en PDF. Conversation du 16/09/2026, captures 13, 14, 19 et 20.
  **Remplacé le 2026-10-07 par R13** (un seul PDF, mail court sans tableau).

## R5. Marques et matériel préférés

- **Évaporateurs CO2 : Alfa Laval de préférence** (dicté « Alpha Luv »). Conversation du 16/09/2026, capture 9.
- **Régulation Danfoss** : armoire de régulation neuve, régulateurs de poste **AK-CC 55**, supervision
  **AK-SM 800A** (après « AKSM 800 » puis « KSM 950 », Loïc tranche « AKSM800A »). Conversation du
  16/09/2026, captures 6, 9 et 11.
- **Danfoss aussi pour** détendeurs, sondes, transducteurs de pression et détection de fuite.
  Conversation du 16/09/2026, capture 17.
- **Tuyauterie et raccords en cuivre K65** (confirmé). Conversation du 16/09/2026, captures 6 et 11.

## R6. Règles de régulation (observé sur le dossier test, à généraliser avec Loïc)

> **Statut : hypothèse.** Énoncées le 16/09/2026 (capture 9) pour le dossier test (chambres négatives et une
> positive). Pour une autre affaire : pistes à confirmer avec Loïc, jamais recopiées telles quelles ; les **nombres**
> (évaporateurs par régulateur, soupapes, portes) sont ceux du dossier test et deviennent des questions.

- **Un régulateur par groupe d'évaporateurs d'une même chambre** (sur le dossier test, en négatif : un pour trois
  évaporateurs, un autre pour deux, pour séparer les deux congélateurs).
- **Négatif : dégivrage électrique sur chaque évaporateur.**
- **Positif : un seul régulateur pour les évaporateurs de la chambre, dégivrage naturel** (pas de dégivrage
  électrique ; deux évaporateurs sur le dossier test).
- Cordons chauffants de portes gérés par l'armoire ; **soupapes de décompression** à inclure dans l'armoire (deux sur
  le dossier test ; ailleurs, le nombre est une question).
- Régulation du **chauffage du sol** des chambres négatives (quand il existe, comme sur le dossier test).
- **Armoire complète, pré-câblée.**

## R7. Ce qu'il demande pour une centrale CO2 booster (observé sur le dossier test, à généraliser avec Loïc)

> **Statut : hypothèse.** Conversation du 16/09/2026, message daté du 24/09, capture 21, pour le dossier test. Les
> options (gas coolers, aimants, variateur, désurchauffeur, ULSH) sont des pistes pour une autre centrale CO2 ; la
> récupération de chaleur et l'implantation sont celles du dossier test : à confirmer à chaque affaire. Le projet
> lui-même (ce qu'on remplace par une centrale CO2) n'est jamais déduit de cette règle : il se dicte, ou reste une
> hypothèse écrite avec sa question.

- **Gas coolers dimensionnés sur les températures de l'été passé.**
- **Récupération de chaleur** conservée (sur le dossier test : chauffage du sol, aujourd'hui assuré par les
  centrales HFC).
- **Aimants permanents** sur les compresseurs ; **variateur** sur les premiers compresseurs.
- **Désurchauffeur sur le refoulement négatif** (dicté « surchauffeurs ») ; **module ULSH en option** ;
  demander au fournisseur les autres options pertinentes.
- Sur le dossier test, centrale en extérieur sous toit et grillagée : poser la question d'un **carénage**
  (rongeurs). Pour une autre affaire, l'implantation est une question.

## R8. Fournitures et prix indicatifs demandés

- Prix indicatifs du **cuivre K65 du moment**, des **isolants** et des **petites fournitures** (colliers
  isolés, coudes…), pour faire ses métrés d'après son plan d'implantation. Conversation du 16/09/2026, capture 9.

## R9. Ton selon le destinataire (demande de prix)

- **Grossistes : vouvoiement, ton formel**, plusieurs grossistes non nommés, **client anonymisé** (ni nom, ni
  adresse, ni localité, ni référence de fiche). Conversation du 16/09/2026, captures 9 et 17 à 19.
- **Fabricant de centrale : tutoiement, ton cordial**, une personne nommée, **chantier nommé** avec sa référence.
  Conversation du 16/09/2026, captures 20 à 22 (demande dictée le 24/09).
- À confirmer comme règle générale : qui sont ses fournisseurs habituels et lesquels il tutoie (question 9).

## R10. « Phase de prix, plusieurs sociétés en lice »

- Dire au fournisseur que le marché est **mis en concurrence** et qu'on est **en phase de prix** (« rien n'est
  encore signé »), avec le nombre d'entreprises en lice quand on le connaît, pour obtenir une offre « assez
  concurrentielle ». Conversation du 16/09/2026, captures 20 à 22 ; mail aux grossistes, captures 17 à 19
  (« marché de remodeling », « offre de prix compétitive »).
- Le nombre d'entreprises vient du dossier (`dossier.md`, bloc A de l'étape 2) ou de la dictée, jamais d'une
  supposition.

## R11. Cuivre K65 et métrés

- La tuyauterie est en **cuivre K65** (R5) ; Loïc fait **ses métrés lui-même d'après son plan d'implantation** et
  demande au grossiste seulement les **prix indicatifs du moment** : cuivre K65, isolants, petites fournitures
  (colliers isolés, coudes, raccords). Point f) de la demande. Conversation du 16/09/2026, captures 6, 9 et 11.
- En V1, le plan d'implantation est « à suivre » dans les annexes ; il sera joint avec le métré au Lot 7.

## R12. Marques dans les documents envoyés

- **Évaporateurs : Alfa Laval de préférence** ; **régulation, détendeurs, sondes, transducteurs et détection de
  fuite : Danfoss** (supervision AK-SM 800A, régulateurs AK-CC 55). Écrits correctement dans tout document envoyé
  (dictés « Alpha Luv » et « dents fausses »). Conversation du 16/09/2026, captures 6, 9, 11 et 17.
- Ce sont des **préférences** : la solution reste adaptée à ce que propose le fournisseur (capture 9).

## R13. Un seul PDF et un mail court (décision d'Adrien du 2026-10-07)

- La demande part en **un seul PDF** (contexte, tableaux, demande détaillée, un chapitre par poste avec les photos
  des plaques légendées, annexes ; moins de 5 Mo) et **un mail court sans tableau** qui résume, cite les chiffres
  clés et renvoie au PDF. Décision d'Adrien du 2026-10-07, dans la ligne de ce qu'il avait décrit à Loïc en visio
  le 28/09/2026 (un PDF avec les tableaux, les explications et les photos, plus le texte du mail).
- **Pourquoi** : les tableaux collés dans Outlook se perdaient (capture 20 ; visio du 24/09/2026, 16:01) et le PDF
  de photos de 11,9 Mo n'est pas passé (capture 14 ; visio du 24/09/2026, 16:41).
- Remplace la pratique du 16/09 (R4, « Format ») ; la page de tableaux pour Outlook devient une option future.
  À valider par Loïc à la livraison (ordre des chapitres, taille maximale : questions 7 et 8).

## R14. Hauteurs de pose pour le métré des plans (hypothèse du 2026-10-07)

- **Statut : hypothèse**, jamais confirmée par Loïc. Valeurs reprises de l'exemple de plan du 2026-09-28 et de la
  décision du 2026-10-07 : évaporateur **2,30 m** ; passage des cuivres froid **2,60 m** ; raccord du groupe ou de
  la centrale **0,50 m** ; tableau électrique **1,50 m** ; chemin de câbles **2,80 m** ; réserve par câble **1,00 m** ;
  split **2,20 m** ; passage des cuivres clim **2,20 m** ; raccord du moteur **0,50 m** ; condensats : passage
  **2,30 m**, évacuation **0,10 m**.
- Elles entrent dans la formule du métré (`methodes/plan-2d.md` § 4) et `plan.md` les écrit « hypothèse » tant que
  `hauteurs_validees` ne les contient pas. Une hauteur dictée pour une ligne ou un équipement prime sur la table.
- À valider par Loïc à la livraison (question 13 : lesquelles il change).

## R15. Une ligne part et arrive au centre de l'équipement (hypothèse du 2026-10-07)

- **Statut : hypothèse.** Le départ d'un cuivre ou d'un câble se compte depuis le centre de l'équipement, et
  l'accrochage d'un trait lu sur photo se fait sur ce centre (`--accrochage bord` en variante). Choix de construction
  du 2026-10-07 : le métré peut dépasser le raccord réel d'une demi-longueur d'appareil.
- À valider par Loïc à la livraison (question 15 : centre ou bord).

## R16. Écart accepté entre un tracé photographié et sa longueur de référence (hypothèse du 2026-10-07)

- **Statut : hypothèse.** Écart accepté par réseau : **max(5 %, 0,30 m)**. Au delà, `lire_photo.py` le signale et la
  fusion dans le plan attend la confirmation de Loïc. Seuil provisoire (décision du 2026-10-07).
- À valider par Loïc à la livraison (question 14).

## R17. Impression à 100 % et marqueur de couleur (décision d'Adrien du 2026-10-07 et hypothèse)

- **Plans en A4, une page, à une échelle normalisée** choisie automatiquement, avec barre d'échelle et règle de
  contrôle de 100 mm : décision d'Adrien du 2026-10-07 (« les plans sont à l'échelle et l'échelle se vérifie »).
- **Le plan s'imprime à 100 %** (« taille réelle »), jamais « ajusté à la page » ; la règle de contrôle se vérifie au
  réglet. Seule exception : la feuille à repères du Lot 6 peut être ajustée à la page (mesures relatives aux repères).
- **Tracés au marqueur rouge, bleu ou vert**, un trait continu par tronçon, une feuille par réseau, photo de dessus
  sans flash ; le noir est lu mais moins sûr (le plan imprimé est gris).
- **Statut : hypothèse** sur la pratique de Loïc : à valider à la livraison (question 16 : marqueurs et imprimante A4 ;
  question 17 : A4 seulement ou parfois A3 ; question 18 : métré sur la page 2 et dans la vue HTML).

## R18. Diamètres et charge de fluide : au fournisseur (décision du 2026-10-08)

- Chaque ligne porte **« à définir par le fournisseur »** comme diamètre ; aucune section de câble non plus. Le
  système ne calcule ni les diamètres ni la charge de fluide : la demande de prix le dit en toutes lettres
  (« Diamètres et charge de fluide à définir par vos soins »). Application des règles de fiabilité 1 et 2 de
  `dimensionnement/CLAUDE.md` (une source sur chaque chiffre ; ne jamais inventer). Le métré par diamètre regroupe
  ces lignes sous « à définir par le fournisseur ». Diamètres calculés (puissance + longueur) : option future.
- **Statut : décision d'Adrien du 2026-10-08** ; la pratique de Loïc (qui fixe les diamètres chez ses fournisseurs)
  reste à confirmer.

## R19. Cote manquante = question (règle du système du 2026-10-07)

- **Aucune cote estimée** sur un plan : une cote (dimension d'un mur, d'une pièce, d'une chambre) que Loïc n'a pas
  donnée (ni écrite sur un croquis ou un plan d'architecte) est une question, jamais une valeur « environ » ni une
  mesure prise sur un croquis. Les **longueurs de lignes** (cuivres, câbles) sont une autre chose : elles sont
  calculées depuis le tracé et annoncées comme estimations (R20). Chaque cote garde
  sa source (télémètre, croquis, plan d'architecte, rapport) ; une description incohérente de plus de 1 cm est
  signalée, jamais arrondie en silence. Seuls défauts permis, écrits comme tels : dimensions d'équipement par type,
  épaisseurs de mur, hauteurs de pose (R14).
- **Statut : hypothèse** quant à la tolérance de Loïc (1 cm entre ses cotes et le dessin) : à lui confirmer.

## R20. Toute longueur de ligne est une estimation, sauf mesurée sur chantier (décision d'Adrien du 2026-10-08)

- Deux états, partout (page du plan, page Métré du fichier draw.io, PDF de demande fournisseur) : **estimée d'après
  le plan** (tracé + hauteurs de pose supposées) et **mesurée sur chantier** (relevée par Loïc). L'estimation est la
  règle, annoncée une fois en tête du métré ; la mesure est l'exception, marquée « (mesurée) » sur la ligne.
- Une mesure de Loïc s'écrit sur la ligne du modèle (`longueur_mesuree`, qui l'a mesurée, quand) ; elle remplace
  l'estimation dans les totaux ; un écart de plus de 20 % entre les deux déclenche une question (le tracé
  correspond-il à la réalité ?).
- Le dimensionnement (étape 2) n'utilise pas les longueurs ; la demande fournisseur (étape 3) reprend les longueurs
  de cuivre du plan, avec la phrase d'estimation, via `plan/metre.json`.
- **Statut : décision d'Adrien** ; la pratique de Loïc (mesure-t-il ses lignes sur chantier, et comment) reste à
  confirmer.

## Réponses attendues (six questions posées le 2026-10-06)

Questions envoyées par Adrien (texte : plan du Lot 2 v1, §9). Tant qu'une réponse manque, l'hypothèse
indiquée s'applique et le livrable l'écrit comme hypothèse.

| # | Question | Réponse de Loïc | Date | Hypothèse en attendant |
|---|---|---|---|---|
| 1 | Régime et condition de référence (positif, négatif, clim ; surchauffe ou gaz aspiré) | | | −30 / −10 / +40 °C (R1) ; gaz aspiré 20 °C (condition des catalogues Bitzer ; surchauffe 10 K en variante) ; point de rosée |
| 2 | Marge ajoutée à la puissance existante | | | 0 %, écrit comme hypothèse : aucune marge ajoutée, aucune inventée |
| 3 | Seuil d'écart entre deux méthodes qui doit alerter | | | 15 % |
| 4 | Ratio de puissance par m³ pour les grandes chambres, ou toujours l'existant | | | toujours l'existant (R2) |
| 5 | Usage d'une plaque qui n'indique que des CV ou HP | | | refus de convertir : question à Loïc |
| 6 | Le système propose un fluide cible conforme, ou vérifie seulement celui de Loïc | | | vérifie seulement |
