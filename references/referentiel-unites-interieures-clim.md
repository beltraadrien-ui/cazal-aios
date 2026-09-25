# Référentiel des unités intérieures de climatisation — Cazal Réfrigération

> **Source** : document de Loïc « Referentiel_unites_interieures_clim_Cazal.pdf » (version du
> 24/09/2026), converti en tableaux le 2026-09-25. Données reprises telles quelles ; seules les
> règles d'utilisation ont été ajustées avec Adrien (voir ci-dessous).
>
> **Rôle** : un **dictionnaire** des clims que Cazal pose le plus souvent, pour (1) corriger les noms
> mal compris à la dictée et (2) retrouver la référence exacte et vérifier la couleur des clims à
> poser. **Liste non limitative : les marques restent libres.**
>
> **Utilisé par** : `resume-vocal-devis` (bundlé dans son zip via `shared/scripts/export_skills.py`).

## Règles d'utilisation (validées avec Adrien le 2026-09-25, remplacent celles du PDF)

- **Les marques sont libres** : écrire exactement la marque et le modèle que Loïc dit. Cette liste
  sert à corriger et à vérifier, pas à limiter.
- **Clim à poser dont le modèle est dans la liste** : à partir de la gamme, de la puissance et de la
  couleur dictées, retrouver la **référence exacte** (site du fabricant ou d'un distributeur), puis la
  vérifier. Si la **couleur** demandée n'existe pas dans la gamme, le signaler.
- **Modèle absent de la liste** : l'écrire tel que dicté et préciser qu'il n'est **pas dans la liste**
  (ne jamais dire qu'il n'existe pas ou qu'il est inconnu).
- **Ne jamais supposer** une marque ou une gamme non dictée : en cas de doute, le signaler plutôt que
  deviner.

## Termes souvent mal retranscrits en dictée

| Entendu à la dictée | À écrire |
|---|---|
| « Ayer », « ailleurs » | **Haier** (⚠️ « ailleurs » est aussi un mot courant : ne corriger que s'il désigne clairement la marque) |
| « Seren » | **Serene** (gamme Haier) |
| « Sansira » | **Sensira** (gamme Daikin) |
| « décoclim », « dégâts clim » | **cache Décoclim** |
| « Hyper Heating » | gamme grand froid **Mitsubishi Electric** (⚠️ préciser mural ou console, voir notes) |

## Daikin

| Type | Gamme | Référence / préfixe | Coloris |
|---|---|---|---|
| Mural | **Emura** | FTXJ | Blanc mat, argent mat, noir mat |
| Mural | **Stylish** | FTXA | Blanc mat, argent mat, noir mat, bois/blanc mat, bois/noir mat |
| Mural | **Perfera** | FTXM | Blanc mat |
| Mural | **Comfora** | FTXP | Blanc mat |
| Mural | **Sensira** | FTXF / FTXC | Blanc mat |
| Mural | **Ururu Sarara** | FTXZ | — |
| Console | **Perfera Console** | FVXM | Blanc brillant |
| Console | **Console intégrée** | — | Sans habillage (non concerné) |
| Cassette 4 voies 60×60 | — | FFA | Blanc ou noir |
| Cassette 4 voies 90×90 | **Round Flow** | FCAG | Blanc ou noir |
| Gainable | — | FDXM | Non visible |
| Gainable moyenne pression statique | — | FBA | Non visible |

## Mitsubishi Electric

| Type | Gamme | Référence / préfixe | Coloris |
|---|---|---|---|
| Mural | **MSZ-LN** | MSZ-LN | Blanc perlé, blanc classique, noir, rouge |
| Mural | **MSZ-EF** | MSZ-EF | Noir brillant, argent, blanc brillant |
| Mural | **MSZ-AY** | MSZ-AY | Blanc mat |
| Mural | **MSZ-AP** | MSZ-AP | Blanc brillant |
| Mural | **MSZ-HR** | MSZ-HR | Blanc brillant |
| Mural | **MSZ-RZ (R290)** | MSZ-RZ | Blanc mat |
| Console | **MFZ-KT** | MFZ-KT | Blanc brillant |
| Console Hyper Heating | **MFZ-KW** | MFZ-KW | Blanc brillant |
| Cassette 1 voie | — | MLZ-KP / MLZ-KY | Blanc mat |
| Cassette 4 voies 60×60 | — | SLZ-M | Blanc mat |
| Cassette 4 voies 90×90 | **Mr Slim** | PLA-M | Blanc mat |
| Gainable | — | SEZ-M / PEAD-M | Non visible |

## Haier

| Type | Gamme | Référence / préfixe | Coloris |
|---|---|---|---|
| Mural | **Pearl Premium** | AS…PBPHRA-PRE | Blanc mat |
| Mural | **Serene** | AS… | Noir mat ou blanc mat |
| Console | — | AF… | Blanc brillant |
| Cassette 1 voie | — | AB… | Blanc uniquement |
| Cassette 4 voies 60×60 | **Compacte** | AB… | Blanc ou noir |
| Cassette 4 voies 90×90 | **« 360 »** | AB… | Blanc ou noir |

**Remarque (Loïc).** Chez Haier, les cassettes (1 voie, 60×60 et 90×90) ont toutes une référence
commençant par « AB » : l'identification se fait par le type de cassette et la puissance. Le « … »
dans une référence représente la puissance et le suffixe du modèle.

## Notes ajoutées (vérifiées le 2026-09-25)

- **Hyper Heating** est une technologie Mitsubishi Electric présente sur plusieurs appareils : la
  console MFZ-KW de la liste, mais aussi le mural MSZ-RZ (R290), vendu comme « Hyper Heating
  Ultimate+ » ([Sonepar](https://climate.sonepar.fr/msz-rz25vu-e2-unit-int-rieure-mural-hyper-heating-ultimate-r290)).
  Si Loïc dit « Hyper Heating » sans préciser mural ou console, lui demander.
- **Haier Pearl Premium** : un distributeur affiche une référence du type `AS20PBAHRA`
  ([Condizionati](https://www.condizionati.fr/mural-pearl/20675-climatiseur-mural-haier-pearl-premium-as20pbahra-puissance-20kw-multi-split-inverter-wifi-de-serie.html)),
  le document de Loïc indique `AS…PBPHRA-PRE` : suffixe à confirmer lors de la recherche de
  référence.
