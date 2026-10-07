# Règles de Loïc (dimensionnement et demande fournisseur)

> v1 du 2026-10-06 (Lot 2), complétée le 2026-10-07 (Lot 3 : R9 à R13, demande fournisseur). Chaque règle est
> **datée et sourcée**. Sources : « conversation Claude de Loïc
> du 16/09/2026 » (numéro de capture d'écran) et « visio du 24/09/2026 » (minute de l'enregistrement).
> Une règle énoncée pour un seul dossier est marquée « à confirmer comme règle générale ». Les réponses de
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

## R4. Ce qu'il envoie aux grossistes et fournisseurs

- **Le but** : un mail de demande d'offre de prix, avec la capacité frigorifique actuelle, que le
  fournisseur utilise pour sélectionner le matériel. Conversation du 16/09/2026, capture 2.
- **Sans nom de client** : présenter « une centrale HFC au R449 à passer en CO2 booster », la solution
  restant adaptée à ce que propose le fournisseur. Conversation du 16/09/2026, capture 9.
- **Mail aux grossistes** (version complète) : introduction (soumission pour un marché de remodeling,
  offre de prix compétitive, installation complète de A à Z), renvoi au dossier photo, puis tableaux
  1. chambres à traiter, 2. production frigorifique existante, 3. évaporateurs en place, puis la demande
  d'offre détaillée. Conversation du 16/09/2026, captures 12 et 17 à 19.
- **Mail au fournisseur de la centrale CO2 : deux tableaux seulement**, « chambres à traiter » et
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

## R6. Règles de régulation énoncées (à confirmer comme règles générales)

Conversation du 16/09/2026, capture 9, pour un dossier de chambres négatives et positive :

- **Un régulateur par groupe d'évaporateurs d'une même chambre** (en négatif : un pour trois
  évaporateurs, un autre pour deux, pour séparer les deux congélateurs).
- **Négatif : dégivrage électrique sur chaque évaporateur.**
- **Positif : un seul régulateur pour les deux évaporateurs, dégivrage naturel** (pas de dégivrage électrique).
- Cordons chauffants de portes gérés par l'armoire ; **deux soupapes de décompression** à inclure dans l'armoire.
- Régulation du **chauffage du sol** des chambres négatives.
- **Armoire complète, pré-câblée.**

## R7. Ce qu'il demande pour une centrale CO2 booster

Conversation du 16/09/2026, message daté du 24/09, capture 21 :

- **Gas coolers dimensionnés sur les températures de l'été passé.**
- **Récupération de chaleur** conservée (chauffage du sol, aujourd'hui assuré par les centrales HFC).
- **Aimants permanents** sur les compresseurs ; **variateur** sur les premiers compresseurs.
- **Désurchauffeur sur le refoulement négatif** (dicté « surchauffeurs ») ; **module ULSH en option** ;
  demander au fournisseur les autres options pertinentes.
- Centrale en extérieur sous toit et grillagée : poser la question d'un **carénage** (rongeurs).

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
