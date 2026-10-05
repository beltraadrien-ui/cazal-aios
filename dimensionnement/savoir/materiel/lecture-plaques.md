# Lire une plaque signalétique (compresseur, groupe de condensation, évaporateur)

> v1 générale du 2026-10-03, pour l'étape 1. Les fiches par marque (décodage précis des références,
> gammes, performances) arrivent au Lot 2 à partir des catalogues de Loïc. Tout décodage ci-dessous
> est **indicatif** : la référence exacte se confirme dans le catalogue de la marque.

## Méthode, dans l'ordre

1. **Regarder la photo en entier** : il y a souvent deux plaques (compresseur et groupe/centrale) ou
   une plaque et une étiquette de fluide. Lire chacune séparément.
2. **Recopier tel quel** : marque, modèle (référence complète, avec tirets et suffixes), numéro de
   série, année si présente. Un suffixe change le modèle : `4HE-18Y` ≠ `4HE-18Y-40P`.
3. **Relever les données électriques** : tension et fréquence (`400 V 3~ 50 Hz`), intensité maximale
   (`MRA`, `MCC`), courant rotor bloqué (`LRA`). Elles servent au contrôle, pas au dimensionnement.
4. **Relever le fluide** : les fluides **autorisés** listés sur la plaque (ex. `R404A / R448A / R449A`)
   ne disent pas lequel est **dans** l'installation. La charge réelle et le fluide réel viennent du
   commentaire de Loïc ou d'une étiquette de charge, et c'est cette source qu'on cite.
5. **Relever la cylindrée ou le volume balayé** s'il est écrit (`m³/h` à 50 Hz) : c'est la donnée la
   plus utile pour estimer la puissance au Lot 2. Sinon, il se retrouve dans le catalogue à partir du modèle.
6. **Qualifier la lecture** : `sûre` (tout est net), `douteuse` (un caractère incertain : écrire la
   lecture la plus probable et le doute, ex. `4HE-18Y ou 4HE-15Y ?`), `illisible` (demander la photo
   d'origine à Loïc). Une lecture douteuse ne passe jamais pour sûre.
7. **Ne jamais compléter de mémoire** un modèle à moitié lu.

## Pièges connus

- **CV / HP ≠ puissance frigorifique.** Le nombre dans une référence (ex. le `18` de `4HE-18Y`) est une
  puissance moteur nominale approximative, pas la puissance froid. La puissance froid dépend du régime
  (température d'évaporation et de condensation) et du fluide : elle vient d'un catalogue ou d'un logiciel
  constructeur, au Lot 2.
- **50 Hz / 60 Hz** : une donnée catalogue à 60 Hz est environ 20 % plus haute qu'à 50 Hz. En Europe, 50 Hz.
- **Plaque du groupe ≠ plaque du compresseur** : le groupe (unité de condensation) a sa propre référence
  et sa propre puissance ; noter les deux.
- **Photos InterFast** : 450 × 600 px. Les petits caractères sont souvent perdus. Demander l'original plutôt que deviner.

## Repères par marque (indicatifs, à confirmer au catalogue)

| Marque | Forme de la référence | Repères |
|---|---|---|
| Bitzer (pistons) | `4HE-18Y`, `4H-15.2Y`, `4NCS-12.2Y`, `6GE-34Y` | Premier chiffre = nombre de cylindres ; lettres = série ; nombre = puissance moteur nominale approximative ; `Y` = huile ester (HFC/HFO). Le volume balayé exact est dans le catalogue Bitzer |
| Copeland (scroll) | `ZB45KCE-TFD`, `ZF18K4E-TFD` | `ZB` = réfrigération moyenne/haute température, `ZF` = basse température ; le nombre ≈ puissance nominale en kBtu/h à 60 Hz ; `TFD` = 380-420 V 3~ 50 Hz |
| Copeland (semi-hermétique) | `D4DH-250X` | Série Discus ; le nombre ≈ puissance moteur en dixièmes de HP |
| Tecumseh (groupes) | `TAG4568Z`, `CAJ4519Z` | Famille, puis taille ; le suffixe de fluide (`Z` = R404A/R452A, `Y` = R134a, `T` = R407C…) à confirmer |
| Danfoss / Maneurop | `MT64HM4VE`, `NTZ108` | `MT` = moyenne/haute température, `LT`/`NTZ` = basse température |
| Frascold, Dorin, Carlyle | références propres | à documenter au Lot 2 selon ce que Loïc rencontre |

Ces repères servent à **reconnaître** une plaque et à poser la bonne question ; ils ne remplacent pas le catalogue.
