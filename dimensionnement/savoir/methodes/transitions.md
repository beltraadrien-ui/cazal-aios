# Transitions de fluide : ce qu'on garde, ce qu'on remplace

> v1 du 2026-10-06 (Lot 2). Sert au bloc E du livrable `2-dimensionnement.md` (« ce qu'on garde, ce qu'on
> remplace »). Brouillon **sourcé mais à compléter avec Loïc** : il ne remplace ni son expérience, ni
> l'avis du fabricant du matériel, ni la sélection du fournisseur. Les références « base de savoir »
> renvoient aux documents de Loïc (skill `froid-savoir`), avec la page donnée par la base.

## 0. Le cadre réglementaire en bref

Détail, articles et dates : `fluides/reglementation-fgas.csv` (table **non relue** à ce jour) ; PRP : `fluides/prp.csv`.

- **R404A (3 922) et R507A (3 985)** : entretien interdit depuis le 1/1/2025 (PRP ≥ 2 500), fluide
  régénéré ou recyclé toléré jusqu'au 1/1/2030 (règlement (UE) 2024/573, art. 13(3)).
- **R449A (1 396), R448A (1 386), R407F (1 825), R452A (2 139)** : entretien de la réfrigération fixe
  interdit au 1/1/2032 (PRP ≥ 750), sauf fluide régénéré ou recyclé (art. 13(5)).
- **Neuf** : une centrale commerciale multipostes ≥ 40 kW ne peut plus être mise sur le marché avec un gaz
  de l'annexe I de PRP ≥ 150 depuis le 1/1/2022 (annexe IV point 6) ; les autres équipements de
  réfrigération (hors autonomes et refroidisseurs) suivent au 1/1/2030 (annexe IV point 5 c)).
- Conséquence : remplacer une centrale HFC par une centrale neuve impose un fluide de PRP < 150 (CO2 en
  pratique) ; un retrofit vers un HFC/HFO de PRP entre 750 et 2 500 ne donne qu'un horizon jusqu'en 2032.

## 1. HFC à haut PRP (R404A, R507A, R449A…) → centrale CO2 booster

**Tout le circuit frigorifique change.** Le CO2 travaille à des pressions bien plus élevées et a une
production frigorifique volumique beaucoup plus forte : cylindrées, tuyauteries, évaporateurs et
condenseurs se dimensionnent autrement (Emerson, guide des systèmes commerciaux au CO2, p. 28, section 7,
base de savoir).

| Élément | Verdict | Pourquoi | Source |
|---|---|---|---|
| Compresseurs | **remplacés** | compresseurs CO2 dédiés ; pressions de refoulement MT jusqu'à 120 ou 130 bar selon la gamme | Advansor module 2 p. 10-14 ; Emerson p. 28 |
| Condenseur | **remplacé par un refroidisseur de gaz (gas cooler)** | au-dessus de 31 °C (point critique), plus de condensation : le gas cooler refroidit le gaz, une vanne haute pression crée la détente | Advansor module 2 p. 19-23 |
| Évaporateurs | **remplacés** (évaporateurs CO2) | pressions de service et dimensionnement différents ; Loïc demande des évaporateurs CO2 neufs, Alfa Laval de préférence | Emerson p. 28 ; `regles-loic.md` R5 |
| Détendeurs | **remplacés** (détendeurs électroniques) | les installations CO2 utilisent des détendeurs électroniques plutôt que thermostatiques | EVAPCO, manuel CO2 transcritique p. 25 ; `regles-loic.md` R5 (Danfoss) |
| Tuyauterie | **remplacée** (cuivre K65 ou équivalent) | le K65 (cuivre-fer) tient 120 bar ; le cuivre standard ne convient pas au-delà de petits diamètres, même côté basse pression | Emerson p. 30 ; EVAPCO p. 30-31 ; `regles-loic.md` R5 |
| Régulation | **remplacée** (armoire neuve) | régulateur de centrale booster dédié (ex. Danfoss AK-PC 782), régulateurs d'évaporateurs, supervision | Danfoss AK-PC 782 p. 3 ; `regles-loic.md` R5 et R6 |
| Soupapes et sécurités | **ajoutées ou remplacées** | pression d'arrêt du CO2 supérieure à la pression de service : soupapes, maintien en pression (unité de secours) ou pression de service calculée sur l'arrêt | Emerson p. 28 ; Advansor module 3 p. 11 et 36 ; module 2 p. 14 |
| Huile | celle de la centrale neuve | gestion d'huile propre à la centrale | Advansor module 6 p. 12-23 |
| Récupération de chaleur | **à reprévoir** sur la centrale CO2 | le CO2 s'y prête bien (refoulement plus chaud qu'en HFC) ; Loïc la garde pour le chauffage du sol | Advansor module 4 p. 12-13, module 9 p. 10 ; `regles-loic.md` R7 |
| Détection de fuite | **à prévoir** | EN 378 impose une détection si la concentration peut dépasser la limite pratique de 0,1 kg/m³ | Emerson p. 28 ; `regles-loic.md` R5 |
| Chambres, isolation, portes | gardées a priori | hors circuit frigorifique | à confirmer avec Loïc |

### Vigilance

- **Gas cooler dimensionné sur la température extérieure d'été** : au-delà d'environ 25 °C d'air, la
  centrale passe en transcritique (Advansor module 2 p. 23) ; Loïc le demande explicitement (`regles-loic.md` R7).
- **Pressions** : chaîne de sécurité côté HP échelonnée d'environ 100 à 148 bar, avec soupape commune à
  120 ou 130 bar selon la gamme (Advansor module 2 p. 14) ;
  côté BT, évaporateurs à MOP −15 °C recommandés pour éviter la surpression à l'aspiration BT (Advansor
  module 5 p. 8).
- **Liquide piégé** entre deux vannes fermées : forte dilatation du CO2, prévoir une protection
  (Emerson p. 11 et 28).
- **Ligne liquide sans sous-refroidissement** : la moindre perte de charge ou remontée crée du gaz de
  détente (Advansor module 3 p. 30).
- **Désurchauffeur sur le refoulement BT** : abaisse la température de refoulement MT (Advansor module 5
  p. 16) ; demandé par Loïc (`regles-loic.md` R7).
- **Certification** : le CO2 relève d'un certificat dédié (catégorie B selon le guide AREA p. 14, à vérifier).

## 2. HFC à haut PRP → HFC/HFO à PRP plus bas (retrofit, ex. R404A → R449A, R448A ou R452A)

**Le circuit est conservé**, le fluide change. Possible seulement si les fabricants des composants
l'autorisent. Rappel : un retrofit est de l'entretien, pas une mise sur le marché ; les pièces de rechange
sont permises si elles n'augmentent ni la capacité, ni la charge, ni le PRP (art. 11(1)).

| Élément | Verdict | Pourquoi | Source |
|---|---|---|---|
| Compresseurs | **souvent gardés**, si le fabricant homologue le fluide | les ECOLINE Bitzer sont prévus pour ces mélanges, plusieurs sont homologués (données dans BITZER Software) | Bitzer Refrigerant Report 21 p. 26 (base de savoir) |
| Température de refoulement | **vigilance** | plus élevée que le R404A (+10 à 20 K pour le R449A) : limites d'application à vérifier, surtout en négatif mono-étagé | Bitzer RR21 p. 25 ; Chemours, guide de retrofit XP40, p. 2 |
| Capacité | proche (R449A : 98 % en négatif, 99 % en positif, calcul du fabricant de fluide) | débit massique plus faible (−20 à −25 %) | Chemours p. 2-3 |
| Huile | **gardée** si c'est déjà une POE ; huile minérale ou AB : passage en POE | | Chemours p. 2-3 ; EFPME Cours de bases p. 158-159 |
| Détendeurs | **gardés en général, à régler** (surchauffe) | dans la plage d'un détendeur R404A bien dimensionné ; régler la surchauffe sur le point de rosée | Chemours p. 3 |
| Joints, élastomères, plastiques | **à vérifier** | compatibilité à confirmer auprès des fabricants des composants | Chemours p. 10 ; EFPME Cours de bases p. 158 |
| Filtre déshydrateur | **remplacé** | pratique courante à chaque retrofit | Chemours p. 3 ; EFPME Cours de bases p. 159 |
| Pressostats, régulateurs de pression, HP flottante | **à régler** | pressions d'aspiration et de refoulement différentes | Chemours p. 3 |
| Tuyauteries | **gardées, à vérifier** | vitesses, pertes de charge et retour d'huile avec le nouveau fluide | Chemours p. 3 |
| Charge | refaite | départ à environ 85 % de la charge R404A, puis ajustement | Chemours p. 4 et 10 |
| Étiquetage | **refait** | nouveau fluide et nouvelle huile | Chemours p. 4 ; règlement 2024/573 art. 12 |

### Vigilance

- **Glissement** des mélanges (R449A : environ 4 à 6 K) : surchauffe mesurée sur le point de rosée,
  sous-refroidissement sur le point de bulle (Chemours p. 3 ; Bitzer RR21 p. 27).
- **PRP < 150 = inflammable** : les remplaçants du R404A sous un PRP d'environ 1 300 sont inflammables
  (A2L : R454C, R455A…), avec limites de charge et exigences de sécurité (Bitzer RR21 p. 24-25) :
  « à confirmer », hors périmètre v1.
- **R452A** (PRP 2 139) : température de refoulement modérée, proche du R404A (Bitzer RR21 p. 25), mais
  il tombe aussi sous l'interdiction d'entretien PRP ≥ 750 au 1/1/2032.
- **Horizon** : un retrofit vers un fluide de PRP ≥ 750 n'a de sens que pour une installation qui ne dépassera
  pas 2032 (ou qui sera ensuite entretenue au fluide régénéré).

## 3. HFC → propane (R290, A3)

**Hors périmètre v1. Tout est « à confirmer ».**

- Les **limites de charge EN 378** (norme payante) ne sont pas codées : à confirmer au cas par cas.
- **Conversion d'une installation existante au R290 : seulement dans des cas exceptionnels**, quand
  l'installation peut être mise en conformité de sécurité avec un effort acceptable (Bitzer RR21 p. 31).
- Compresseurs : **version spécifique R290** (huile particulière, commande explicite) (Bitzer RR21 p. 31).
- Sécurité : analyse de risque, zones de type ATEX, ventilation, dispositifs contre les surpressions,
  équipement électrique adapté (Bitzer RR21 p. 30-31).
- Cuivre compatible (Bitzer RR21 p. 30) ; débit massique d'environ 55 à 60 % de celui du R22 (p. 31).
- Réglementation F-gas : non fluoré (PRP 0,02), hors des interdictions ; certification A1 couvrant les
  hydrocarbures (guide AREA p. 14, à vérifier).

## 4. Récapitulatif

| Élément | HFC → CO2 booster | HFC → HFC/HFO (retrofit A1) | HFC → propane |
|---|---|---|---|
| Compresseurs | remplacés | gardés si homologués | à confirmer (version R290) |
| Condenseur | remplacé (gas cooler) | gardé, régler la HP | à confirmer |
| Évaporateurs | remplacés | gardés | à confirmer |
| Détendeurs | remplacés (électroniques) | gardés, réglés | à confirmer |
| Tuyauterie | remplacée (K65) | gardée, vérifiée | à confirmer |
| Régulation | remplacée | gardée, réglée | à confirmer |
| Huile | celle de la centrale neuve | POE gardée | huile spécifique |
| Sécurités | soupapes, maintien en pression, détection | pressostats réglés | ATEX, ventilation |

## À compléter avec Loïc

- Ce qu'il garde réellement lors d'un passage au CO2 (chambres, portes, circuits du chauffage du sol,
  câblage, supports, régulation récupérable).
- Son expérience des retrofits R404A → R449A ou R448A (détendeurs changés ou non, huile, températures de
  refoulement constatées).
- CO2 transcritique booster ou cascade : dans quels cas il propose l'un ou l'autre.
- S'il veut que le système **propose** un fluide cible ou **vérifie** seulement le sien (question 6).
