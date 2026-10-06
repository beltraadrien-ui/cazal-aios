# Bitzer : compresseurs à pistons semi-hermétiques

> v1 du 2026-10-06 (Lot 2). Complète `lecture-plaques.md` pour la marque Bitzer. Sources publiques Bitzer
> (liens ci-dessous, lus le 2026-10-06) ; ce qui n'y figure pas est marqué « à confirmer ». Les puissances
> publiées par modèle vont dans `points-catalogue/bitzer-<fluide>.csv`, pas ici.

## Sources

- [KP-104-2] Brochure Bitzer « ECOLINE, compresseurs hermétiques accessibles à piston », 50 Hz, 09.2012,
  trilingue avec le français :
  <https://www.actrol.com.au/resources/themes/actrol/assets/services/brouchures/250-Bitzer-Ecoline-SemiHermetic-Compressor-Brochure-kp-104-2.pdf>
  (copie hébergée par un distributeur).
- [BA-101-2] Bitzer, « Compressor Reciprocating Retrofit Guide » BA-101-2 AUS :
  <https://www.bitzer.de/shared_media/documentation/ba-101-2-au.pdf>
- [KT-410] Bitzer, « Explanation of the motor codes », KT-410-7 :
  <https://www.bitzer.de/shared_media/html/kt-410/en-GB/235410571235455883.html>
- [ECOLINE] Présentation ECOLINE reprise dans une liste de prix distributeur (2014), p. 1 :
  <https://cdn.rcpsrl.com/refrigeration-compressors/pdf/bitzer/bitzer-technical-information.pdf>

## 1. Décoder une référence

Exemple officiel `4NES-20Y-40P` ([KP-104-2] p. 5, « Explication de la désignation des types ») :

| Position | Dans l'exemple | Signification |
|---|---|---|
| 1er chiffre | `4` | nombre de cylindres (doublé pour un compresseur tandem) |
| 1re lettre | `N` | codification alésage × course |
| `E` | `E` | série BITZER ECOLINE |
| `S` | `S` | lubrification centrifuge |
| nombre | `20` | code de taille du moteur (**pas** une puissance frigorifique) |
| `Y` | `Y` | charge d'huile ester (HFC, HFO) |
| suffixe | `40P` | code moteur (tension, fréquence, démarrage) |

Les modèles d'avant ECOLINE portent un suffixe `.2` (ex. `4H-15.2`, `4NCS-12.2`, `4CC-6.2`) : [BA-101-2]
les range en « Former Models » face à leurs remplaçants ECOLINE (p. 15, 19, 22). La signification exacte
du `.2` et de la lettre `C` des anciennes références est **à confirmer** (lecture probable : génération
précédente, la lettre `C` de série étant remplacée par `E` en ECOLINE : `4NCS` → `4NES`, `4CC` → `4CES`).

## 2. Les six références rencontrées

| Référence | Cylindres | Série | Lubrif. centrifuge (`S`) | Version moteur | Huile | Code moteur | Volume balayé à 50 Hz (1 450 min⁻¹) | Correspondance |
|---|---|---|---|---|---|---|---|---|
| `4HE-18Y-40P` | 4 | ECOLINE | non (à confirmer : pompe à huile) | 2 [KP-104-2 p. 28] | ester | 40P | 73,7 m³/h [BA-101-2 p. 22 et 25] | même famille que l'ancien `4H-15.2` [BA-101-2 p. 22] |
| `4H-15.2Y-40P` | 4 | ancienne génération | non | 2 [KP-100-5] | ester | 40P | 73,7 m³/h [KP-100-5] | remplacé par la famille `4HE` (73,70 m³/h) [BA-101-2 p. 22] |
| `4NES-14Y-40P` | 4 | ECOLINE | oui | 2 [KP-104-2 p. 28] | ester | 40P | 56,2 m³/h [BA-101-2 p. 19-20] | remplace `4NCS-12.2` [BA-101-2 p. 19] |
| `4NCS-12.2Y-40P` | 4 | ancienne génération | oui | 2 [KP-100-5] | ester | 40P | 56,2 m³/h [KP-100-5] | remplacé par `4NES-14Y` [BA-101-2 p. 19] |
| `4CC-6.2Y` | 4 | ancienne génération | à confirmer | 2 [KP-100-5] | ester | non lu | 32,5 m³/h [KP-100-5] ; 33,07 m³/h lu sur une plaque : écart à confirmer | remplacé par `4CES-6Y` [BA-101-2 p. 15] |
| `4CES-6Y-40S` | 4 | ECOLINE | oui | 2 [KP-104-2 p. 28] | ester | 40S | 32,5 m³/h [BA-101-2 p. 15-16] | remplace `4CC-6.2` [BA-101-2 p. 15] |

- [KP-100-5] : brochure Bitzer des semi-hermétiques de l'ancienne génération (2005) ;
  références et pages dans `points-catalogue/bitzer-r449a.md`.
- La plaque fait foi pour M1 ; le catalogue sert de contrôle. Un écart entre les deux est une question à Loïc.
- **Version moteur 2** : en R404A/R507A (R407A, R407F), « optimisée pour champ d'application élargi à la
  réfrigération à moyenne température et à basse température jusqu'à tc = 62 °C » ; la version 1 vise la
  moyenne température et la climatisation ; la version 3 n'existe que pour le R134a ([KP-104-2] p. 11 ;
  [ECOLINE] p. 1). Les tableaux de puissance diffèrent selon la version : la noter avec le point catalogue.
- Un ECOLINE remplace son prédécesseur sans modifier l'installation (mêmes dimensions et raccords)
  [ECOLINE] p. 1. Cela ne dit rien de sa puissance au nouveau fluide.

## 3. Codes moteur

| Code | Ce qu'il dit | Source |
|---|---|---|
| `40P` | moteur à démarrage **en bobinage partiel** (part winding) Y/YY, 380-420 V YY 3~ 50 Hz et 440-480 V YY 3~ 60 Hz ; enroulements 50 % / 50 % (4VES à 6FE) ; contacteurs choisis pour environ 60 % du courant de service maximal | [BA-101-2] p. 37-38 ; [KP-104-2] p. 28 |
| `40S` | moteur Δ/Y : 220-240 V Δ 50 Hz, 380-420 V Y 50 Hz, 440-480 V Y 60 Hz ; mode de démarrage (direct ou étoile-triangle) : à confirmer | [KT-410] ; [KP-104-2] p. 28 |

## 4. Conditions de référence des données Bitzer

- Données de puissance **selon EN 12900, à 50 Hz** ; 60 Hz et conditions particulières : BITZER Software
  [KP-104-2] p. 11.
- **Sans sous-refroidissement du liquide** : la puissance est donc plus basse que dans des données qui
  comptent 5 ou 8,3 K de sous-refroidissement [KP-104-2] p. 11.
- Tableaux « se référant à une température du **gaz d'aspiration de 20 °C**, sans sous-refroidissement »
  [KP-104-2] p. 12 et suivantes.
- Températures d'évaporation et de condensation au **point de rosée** (vapeur saturée) [KP-104-2] p. 10, note 3.
- La brochure ne donne que R134a, R404A, R407A et R407F ; les autres fluides (dont le **R449A**) sont
  « sur demande », donc dans BITZER Software [KP-104-2] p. 11.
- Toujours recopier ces conditions avec un point catalogue (`methodes/puissance-existante.md` §4).

## 5. Où trouver les données publiques

- **BITZER Software** (gratuit, en ligne) : <https://www.bitzer.de/websoftware/> — modèle, fluide, T0, Tc,
  surchauffe ou gaz aspiré, sous-refroidissement, fréquence → puissance frigorifique, puissance absorbée,
  débit massique. Les polynômes de puissance s'exportent en CSV depuis le 13/12/2023 :
  <https://www.bitzer.de/mt/en/press/new-bitzer-software-even-clearer-and-more-comprehensive.jsp>
  (option future du plan, pas en V1).
- **[KP-104-2]** : tableaux de puissance, limites d'application, caractéristiques techniques (p. 28 :
  volume balayé à 1 450 min⁻¹, nombre de cylindres, version moteur, courants).
- **[BA-101-2]** : volumes balayés, anciens modèles et équivalents des autres marques (Dorin, Bock,
  Frascold, Copeland).
- Base de savoir de Loïc : « Bitzer — Refrigerant Report 21 » (fluides homologués, classes de sécurité, p. 26-27 et 42).

## 6. Lire une plaque Bitzer (compléments à `lecture-plaques.md`)

- **Type complet** avec code moteur (`4NES-14Y-40P`) et **numéro de série** (S.Nr.).
- **Volume balayé à 50 Hz et à 60 Hz** (m³/h), avec les vitesses (1 450 et 1 750 min⁻¹) : ne retenir que
  la valeur à 50 Hz ; celle à 60 Hz est plus haute d'environ 21 % (1 750 / 1 450).
- **Tension et fréquence**, **courant de service maximal**, **courant de démarrage** : contrôle électrique,
  pas dimensionnement.
- **Pressions maximales admissibles** côté BP et côté HP (en bar) : utiles pour vérifier un fluide de retrofit.
- Disposition exacte des champs sur la plaque : à confirmer sur la notice de service Bitzer du modèle.

## 7. Pièges

- Le nombre de la référence (`18` dans `4HE-18Y`) est un **code de taille du moteur**, pas une puissance
  frigorifique ([KP-104-2] p. 5).
- Deux modèles de même volume balayé (`4H-15.2` et `4HE-18Y`, 73,7 m³/h) n'ont pas forcément la même
  puissance au même régime (clapets et moteur optimisés en ECOLINE) : M2 se lit **modèle par modèle**.
- `4CC-6.2Y` : écart entre une plaque lue (33,07 m³/h) et le catalogue (32,5 m³/h) à confirmer avant de
  choisir la valeur pour M1.
