# Puissance frigorifique existante d'un compresseur (étape 2)

> v1 du 2026-10-06 (Lot 2). Méthode appliquée par `compresseurs.py` du skill `froid-dimensionnement`
> (bloc B du livrable `2-dimensionnement.md`). Règle de départ : **partir de la puissance existante**
> (`regles-loic.md`, R2). Toutes les valeurs produites sont **indicatives** : la **sélection finale du
> matériel neuf se fait chez le fournisseur**.

## 1. Le principe

1. On calcule la puissance frigorifique (Q0, en kW) que chaque compresseur existant fournit **au régime
   de Loïc**, par **deux méthodes** :
   - **M1, par la cylindrée** : le volume balayé lu sur la plaque et un rendement volumétrique (λ) pris
     dans une table sourcée ;
   - **M2, par le point catalogue** : la puissance publiée par le fabricant pour ce modèle, corrigée au
     régime et au fluide de l'installation.
2. L'**écart M1 / M2** sert de contrôle. M2 est retenue quand elle existe ; sinon M1, marquée « indicatif ».
3. La somme par poste donne la puissance existante ; la **marge de Loïc** donne la puissance demandée.
4. Pas de bilan thermique en V1 (phase 2) et pas d'abaque de volume (décision du 2026-10-06).

## 2. Régimes et conditions de calcul

| Grandeur | Valeur par défaut | Statut | Source |
|---|---|---|---|
| Évaporation, négatif | T0 = −30 °C | sourcé | `regles-loic.md` R1 (conversation du 16/09/2026) |
| Évaporation, positif | T0 = −10 °C | sourcé | idem |
| Condensation | Tc = +40 °C | sourcé | idem |
| Mélanges zéotropes (R449A, R448A, R407F…) | T0 et Tc lues au **point de rosée** (vapeur saturée) | hypothèse | convention des données Bitzer : KP-104-2 p. 10, note 3 (`materiel/bitzer.md`) |
| Condition à l'aspiration | **gaz aspiré à 20 °C** par défaut ; variante : surchauffe **10 K** comptée comme utile | hypothèse | gaz aspiré 20 °C = condition des points catalogue Bitzer (EN 12900, KP-104-2 p. 12) : M1 et M2 calculées dans les mêmes conditions que les points publiés (`parametres_par_defaut()` de `compresseurs.py`) ; surchauffe 10 K = condition des estimations du 16/09 (capture 4), disponible en variante (`compresseurs.py --surchauffe 10`) |
| Sous-refroidissement du liquide | **0 K** (liquide saturé, point de bulle à Tc) | hypothèse | données Bitzer « sans sous-refroidissement » : KP-104-2 p. 11 |
| Pertes de charge des lignes | négligées | hypothèse | — |
| Fréquence | **50 Hz** uniquement ; 60 Hz refusé (≈ +21 % de débit) | règle | `lecture-plaques.md` ; 1 450 et 1 750 min⁻¹ |
| Fluide | celui qui est **dans** l'installation, pas la liste de la plaque | règle | `lecture-plaques.md`, point 4 |

La condition de référence est la **question 1** posée à Loïc le 2026-10-06. Deux enjeux chiffrés
(CoolProp 8.0.0) :

- **Surchauffe 10 K ou gaz aspiré 20 °C** (convention des catalogues Bitzer) : à −30 / +40 °C au R449A
  (`R449A.mix`), ρ1 × Δh vaut 962,8 kJ/m³ dans le premier cas et 1 010,1 kJ/m³ dans le second : **+4,9 %**.
  Le script prend le **gaz aspiré 20 °C par défaut** (mêmes conditions que les points catalogue).
- **Point de rosée ou température moyenne** pour un mélange à glissement : à −30 / +40 °C, gaz aspiré
  20 °C, le rapport ρ1 × Δh R449A / R404A vaut **0,905 quand les deux fluides sont au point de rosée** et
  **0,996 quand les deux sont en température moyenne** (comparaison des deux fluides). M2, elle, part d'un
  point catalogue donné **au point de rosée** (convention Bitzer) : si le « −30 °C » de Loïc est une température
  moyenne, le facteur de conversion du point R404A (rosée) vers l'installation R449A (moyenne) vaut **1,008**
  sans le rapport des λ et **0,981** avec (contre 0,905 et 0,855 tout au point de rosée). Exemple `4HE-18Y-40P`
  à −30 / +40 °C : M2 = **14,60 kW au point de rosée, 16,75 kW en température moyenne, soit +14,7 %**
  (`compresseurs.py --convention moyenne`, calcul du 2026-10-06). La réponse de Loïc à la question 1 peut donc
  déplacer M2 de 10 à 15 %.

## 3. M1 : par la cylindrée

**Formule** (Préparation à la certification p. 46-47 ; EFPME Cours de bases p. 57-60) :

```
Q0 = V̇ × λ × ρ1 × (h1 − h4)
```

| Terme | Signification | D'où ça vient |
|---|---|---|
| V̇ | volume balayé à 50 Hz, en m³/s (m³/h ÷ 3 600) | plaque (photo) ou catalogue |
| λ | rendement volumétrique = débit réellement aspiré / volume balayé | table A ou B ci-dessous (hypothèse) |
| ρ1 | masse volumique du gaz à l'aspiration (P0, T0 + surchauffe), en kg/m³ | CoolProp 8.0.0 |
| h1 | enthalpie du gaz à l'aspiration, en kJ/kg | CoolProp 8.0.0 |
| h4 | enthalpie du liquide à l'entrée du détendeur (= sortie condenseur, détente isenthalpique), en kJ/kg | CoolProp 8.0.0 |
| τ | taux de compression = Pc / P0, en **pressions absolues** | Technicien du froid p. 105 ; Le Kotza p. 54 |

**Pourquoi λ < 1 et pourquoi il baisse quand τ monte** : le gaz resté dans l'espace mort (espace nuisible)
au point mort haut doit se détendre avant que le clapet d'aspiration ne s'ouvre ; plus la HP monte ou la BP
baisse, plus la course « inutile » est longue (Le Kotza p. 51-52 ; Préparation à la certification p. 31 et 46).

### Table A, par défaut (proposée) : λ implicite des catalogues Bitzer

**λ = 0,9625 − 0,0288 × τ**, ajustée le 2026-10-06 sur **226 points** publiés par Bitzer pour les six
modèles `4HE-18Y`, `4NES-14Y`, `4CES-6Y`, `4H-15.2Y`, `4NCS-12.2Y`, `4CC-6.2Y` (R404A, R407A, R407F ;
EN 12900, gaz aspiré 20 °C, sans sous-refroidissement, point de rosée ; cases ombrées exclues) :
λ = Q0 catalogue ÷ (V̇ × ρ1 × Δh), propriétés CoolProp 8.0.0. Points : `materiel/points-catalogue/bitzer-r449a.csv`
(brochures Bitzer KP-104-3-CN et KP-104-2). Écart-type des résidus 0,022 ; écart maximal 0,061.

| τ | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| λ (table A) | 0,905 | 0,876 | 0,847 | 0,819 | 0,790 | 0,761 | 0,732 | 0,703 | 0,675 | 0,646 | 0,617 | 0,588 | 0,559 | 0,530 |

- Domaine : **2 ≤ τ ≤ 15** (étendue des points). En dehors : « à confirmer ».
- λ est défini dans la convention du catalogue (gaz aspiré 20 °C) puis appliqué avec ρ1 et Δh de la
  condition cible : cela revient à la correction de conditions d'EnergyPlus (§4).
- Valable pour des compresseurs à pistons semi-hermétiques récents ; pour une autre marque ou un
  compresseur ancien, c'est une **hypothèse** (statut hypothèse dans tous les cas).
- Choix de la table A comme défaut : **proposition à valider par Adrien** (elle ne vient pas des livres de
  Loïc ; elle rend M1 moins indépendante de M2 pour les modèles Bitzer de la liste).

### Table B, livres de Loïc : formule EFPME

**λ = 1 − 0,05 × τ** (EFPME, Cours de bases (froid), p. 60 : exemple τ = 17,25 / 3,3 = 5,227 → λ = 0,739).

| τ | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| λ (table B) | 0,90 | 0,85 | 0,80 | 0,75 | 0,70 | 0,65 | 0,60 | 0,55 | 0,50 | 0,45 | 0,40 |

**Pessimiste pour les semi-hermétiques actuels** : à τ = 4,6 (positif au R449A) elle donne 0,770 contre
0,830 en table A (−7 %) ; à τ = 10,3 (négatif au R449A) 0,484 contre 0,665 (**−27 %**). Contrôle par la
règle du Kotza (p. 53 : perte de 3 à 5 % par K de baisse de T0, environ 1 % par K de hausse de Tc), au
R449A, Tc = +40 °C, surchauffe 10 K :

| Passage | Table B | Table A | Catalogue Bitzer (R404A, 3 modèles ECOLINE) |
|---|---|---|---|
| positif : T0 −10 → −5 °C | ≈ 4,9 %/K | ≈ 4,5 %/K | 3,9 à 4,2 %/K |
| négatif : T0 −35 → −30 °C | ≈ 11,7 %/K | ≈ 7,4 %/K | 5,8 à 6,2 %/K |

La table B reste la référence pédagogique (borne basse) ; elle n'est pas utilisée par défaut.

**Statut du résultat M1 : hypothèse** (« indicatif, à confirmer par le fournisseur »).

## 4. M2 : point catalogue corrigé

**Donnée** : une puissance publiée par le fabricant (brochure, fiche, BITZER Software lu à la main), rangée
dans `materiel/points-catalogue/<marque>-<fluide>.csv` avec : modèle, fluide, T0, Tc, surchauffe ou
température du gaz aspiré, sous-refroidissement, fréquence, kW frigo, kW absorbés, lien, date de lecture.
Un point sans ses conditions n'est pas utilisable (« à confirmer »).

**Correction de base** (méthode EnergyPlus, Engineering Reference, « Refrigeration Equipment », correction
des valeurs nominales : <https://bigladdersoftware.com/epx/docs/9-6/engineering-reference/refrigeration-equipment.html>) :

```
Q0_cible = Q0_nominal × (ρ1_cible × Δh_cible) / (ρ1_nominal × Δh_nominal)        avec Δh = h1 − h4
```

**Exacte** quand T0, Tc et le fluide sont ceux du point et que seules la surchauffe et le sous-refroidissement
changent : le débit volumique aspiré (V̇ × λ) ne bouge pas.

**Quand T0 ou Tc diffèrent** : multiplier aussi par **λA(τ_cible) / λA(τ_nominal)** (table A). Biais
mesuré le 2026-10-06 sur les points Bitzer R404A (moyenne, entre parenthèses les extrêmes) :

| Déplacement | Sans le rapport des λ | Avec le rapport des λ |
|---|---|---|
| T0 + 5 K | −5,3 % (−18 à −1 %) | +1,0 % (−1 à +9 %) |
| T0 + 10 K | −9,8 % (−28 à −3 %) | +1,9 % (−2 à +14 %) |
| Tc − 10 K | −7,9 % (−19 à −3 %) | −0,4 % (−3 à +8 %) |
| Tc + 10 K | +8,8 % (+4 à +24 %) | +0,4 % (−8 à +3 %) |

(Mesure faite sur les mêmes données que la table A : à confirmer sur d'autres modèles.)

- **Seuil de distance** : |T0_cible − T0_nominal| ≤ 5 K **et** |Tc_cible − Tc_nominal| ≤ 10 K. Au-delà :
  « à confirmer ». Seuil fixé par nous (hypothèse, à valider avec Loïc).
- **Fluide du point ≠ fluide de l'installation** (cas courant : catalogue au R404A, installation au R449A,
  aucun point R449A publié) : même formule, avec ρ1, Δh et τ de chaque fluide :
  Q0_cible = Q0_nominal × [λA(τ_cible) × ρ1_cible × Δh_cible] / [λA(τ_nominal) × ρ1_nominal × Δh_nominal].
  **Statut hypothèse**, jamais « calculé » (les rendements changent avec le fluide).
  Repère : le fabricant du fluide annonce pour le R449A 98 % de la puissance du R404A en négatif et 99 %
  en positif, dans ses propres conditions (Chemours, guide de retrofit XP40, p. 2) ; au point de rosée, la
  formule donne nettement moins (exemple §8) : la question 1 de Loïc tranche.
- **60 Hz** : refusé. **Conditions de référence absentes** : refusé.
- **Statut du résultat** : **calculé** (point sourcé, même fluide, correction par CoolProp) ; **hypothèse**
  dès que la table A ou un changement de fluide intervient.
- **Contrôle de vraisemblance** : variation de 3 à 7 % par K sur T0 (Kotza p. 53 ; catalogue Bitzer
  ci-dessus), autour de 1 à 2 % par K sur Tc ; sinon, signaler.

## 5. Valeur retenue, écart, marge

1. **M2 disponible et valide** : valeur retenue = M2 ; M1 sert de contrôle.
2. **Deux écarts** sont calculés : l'**écart signé rapporté à M2**, (M1 − M2) ÷ M2 × 100, affiché au tableau B
   (`ecart_sur_m2`) ; l'**écart rapporté à la moyenne des deux**, |M1 − M2| ÷ ((M1 + M2) ÷ 2) × 100
   (`controles.comparer`, clé `ecart`), **seul comparé au seuil**. **Seuil provisoire : 15 %** (précision
   attendue de M1, ± 10 à 15 %, plan du 2026-10-06 §3), en attendant la réponse de Loïc (question 3). Au-delà :
   signalé au tableau B (⚠) et en bloc G.
3. **M2 absente** : valeur retenue = M1, statut hypothèse, mention « indicatif, à confirmer par le fournisseur ».
4. **Somme par poste** : le statut de la somme est celui de la plus faible de ses entrées.
5. **Puissance demandée** = puissance existante × (1 + marge). La marge de Loïc est **à confirmer**
   (question 2) : tant qu'elle manque, `calculs.py` applique **0 %, écrit comme hypothèse** (« en attente de la
   réponse de Loïc ») : la puissance demandée égale l'existante, aucune marge n'est inventée.
6. Une plaque d'ensemble (puissance du groupe ou de la centrale) se compare à la somme, au régime de la
   plaque s'il est connu ; sinon elle est citée, pas utilisée.

## 6. Les statuts

| Statut | Veut dire | Exemples |
|---|---|---|
| **sourcé** | lu tel quel dans une source citée | volume balayé sur la photo de plaque ; point catalogue avec lien |
| **calculé** | obtenu par script à partir d'entrées sourcées uniquement | M2 même fluide, même régime ; somme de valeurs sourcées ; tCO2e d'une charge connue d'un fluide sourcé |
| **hypothèse** | dépend d'au moins une hypothèse écrite | M1 (λ) ; M2 avec changement de fluide ou de régime ; surchauffe 10 K ; **lecture douteuse d'un autre champ que le nombre utilisé** (ex. un chiffre du modèle effacé, volume balayé lisible : le doute est écrit dans la source) ; tCO2e, contrôle d'étanchéité et interdictions d'un fluide supposé ; marge de 0 % en attendant Loïc |
| **à confirmer** | donnée absente, illisible ou hors domaine : pas de nombre | nombre illisible sur la plaque ; τ hors domaine ; point à 60 Hz |

Propagation : **un résultat n'est jamais plus sûr que sa plus faible entrée** (sourcé > calculé >
hypothèse > à confirmer).

## 7. Quand écrire « à confirmer »

- Volume balayé absent de la plaque et du catalogue, ou **illisible** sur la photo (le nombre lui-même).
- **Lecture douteuse** : si le nombre utilisé (le volume balayé) est lisible et que seul un autre champ est
  douteux (ex. un chiffre du modèle effacé), la valeur n'est pas « à confirmer » : c'est une **hypothèse**, avec
  le doute écrit dans la source (« lecture douteuse : … ») ; M1, M2 et la valeur retenue restent au mieux
  « hypothèse ». Si le nombre lui-même est illisible : « à confirmer ».
- Modèle illisible (M2 impossible ; M1 reste calculée si le volume balayé est lisible), fréquence inconnue ou
  différente de 50 Hz.
- Fluide réel inconnu (seule la liste des fluides autorisés de la plaque est lisible).
- τ hors du domaine de la table ; T0 sous le point triple pour le CO2 (−56,6 °C, CoolProp 8.0.0) ;
  propriété refusée par CoolProp.
- Point catalogue sans conditions, à 60 Hz, ou plus loin du régime cible que le seuil.
- Seule une puissance moteur en CV ou HP est connue : **ce n'est pas une puissance frigorifique**
  (`lecture-plaques.md`) ; question 5 à Loïc.
- Écart M1 / M2 au-delà du seuil : la valeur reste affichée, l'écart devient une question en bloc G.

## 8. Exemple complet, vérifiable à la main

Propriétés : **CoolProp 8.0.0**, fluides **`R449A.mix`** et **`R404A.mix`** (pressions absolues ; seules
les différences d'enthalpie comptent). Exemple calculé avec la **variante surchauffe 10 K** (condition des
estimations du 16/09) ; avec les paramètres par défaut (gaz aspiré 20 °C), le même compresseur donne
**M1 13,75 kW et M2 14,60 kW (−5,8 %)** (`compresseurs.py`, 2026-10-06) : ce sont ces valeurs par défaut que
le livrable affiche. Compresseur Bitzer `4HE-18Y-40P`, 73,7 m³/h à 50 Hz
(`materiel/bitzer.md`). Installation au R449A, régime négatif −30 / +40 °C (rosée), surchauffe 10 K,
sous-refroidissement 0 K.

**États calculés**

| Grandeur | R449A cible (surchauffe 10 K) | R404A nominal (gaz aspiré 20 °C) |
|---|---|---|
| P0 (rosée à −30 °C) | 1,5997 bar | 2,0223 bar |
| Pc (rosée à +40 °C) | 16,5217 bar | 18,1465 bar |
| τ = Pc / P0 | 10,328 | 8,973 |
| λ table A (0,9625 − 0,0288 τ) | 0,6650 | 0,7041 |
| T aspiration | −20 °C | +20 °C |
| ρ1 | 6,9565 kg/m³ | 8,4008 kg/m³ |
| h1 | 394,842 kJ/kg | 390,970 kJ/kg |
| h4 (liquide saturé à Pc) | 256,440 kJ/kg | 258,120 kJ/kg |
| Δh = h1 − h4 | 138,402 kJ/kg | 132,850 kJ/kg |
| ρ1 × Δh | 962,80 kJ/m³ | 1 116,05 kJ/m³ |

**M1 (table A)** : Q0 = (73,7 / 3 600) × 0,6650 × 962,80 = 0,020472 × 0,6650 × 962,80 = **13,11 kW**
(hypothèse). Avec la table B (λ = 1 − 0,05 × 10,328 = 0,4836) on trouverait 9,53 kW : −27 %.

**M2** : point publié 17,08 kW pour le `4HE-18Y-40P` au **R404A**, −30 / +40 °C, gaz aspiré 20 °C, sans
sous-refroidissement, 50 Hz (`points-catalogue/bitzer-r449a.csv`, brochure KP-104-3-CN). Changement de
fluide, même régime :
Q0 = 17,08 × (0,6650 × 962,80) / (0,7041 × 1 116,05) = 17,08 × 640,26 / 785,81 = 17,08 × 0,8148
= **13,92 kW** (hypothèse : changement de fluide).

**Contrôle M1 / M2** : (13,11 − 13,92) / 13,92 = **−5,8 %**, sous le seuil provisoire de 15 % : valeur
retenue = M2, 13,92 kW, statut hypothèse, mention « indicatif, à confirmer par le fournisseur ».

**Même calcul en positif** (`4CES-6Y-40S`, 32,5 m³/h, −10 / +40 °C) : R449A P0 = 3,5874 bar, τ = 4,605,
λA = 0,8299, ρ1 × Δh = 14,9990 × 150,288 = 2 254,17 kJ/m³ → M1 = 0,0090278 × 0,8299 × 2 254,17
= **16,89 kW** ; M2 depuis le point R404A publié 18,35 kW (τ = 4,213, λA = 0,8412, ρ1 × Δh = 2 415,89 kJ/m³)
→ 18,35 × 0,9205 = **16,89 kW** ; écart nul.

**Cas exact de la correction EnergyPlus** (même fluide, même régime) : passer d'un point R449A publié au
gaz aspiré 20 °C (ρ1 × Δh = 1 010,06 kJ/m³) à la surchauffe 10 K (962,80 kJ/m³) multiplie la puissance par
962,80 / 1 010,06 = 0,9532 : un point de 12,0 kW deviendrait 11,44 kW (statut calculé si le point existait).
