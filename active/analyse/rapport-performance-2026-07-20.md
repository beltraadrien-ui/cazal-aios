# Rapport de performance — Cazal Réfrigération

**Date :** 2026-07-20 · **Source :** Supabase `contenu_avec_scores` (`type=own`) · **Posts :** 30

---

## 1. Vue d'ensemble

**Posts analysés :** 30 (Instagram, tout l'historique — mars 2024 à juillet 2026)

| Plateforme | Posts | Vues moy. | Médiane | Total | Max | Outliers | Taux | Eng. moy. |
|---|---|---|---|---|---|---|---|---|
| Instagram | 30 | 579 | 490 | 17 372 | 1 433 | 3 | 10 % | 4,78 % |

### Tendance mois par mois

| Mois | Posts | Vues moy. | Total | Outliers | Tendance |
|---|---|---|---|---|---|
| 2024-03 | 1 | 1 363 | 1 363 | 1 | — (post isolé) |
| 2026-02 | 1 | 1 099 | 1 099 | 0 | — |
| 2026-04 | 2 | 280 | 561 | 0 | ↓ |
| 2026-05 | 10 | 345 | 3 452 | 0 | → |
| 2026-06 | 12 | 556 | 6 669 | 1 | ↑ |
| 2026-07 | 4 | 1 057 | 4 228 | 1 | ↑↑ |

Progression nette : vues moyennes triplées entre mai et juillet (345 → 1 057).

⚠️ Réserves : juillet ne compte que 4 posts (mois en cours) ; l'`outlier_score` compare chaque post à
la moyenne de **tout l'historique**, ce qui avantage juillet du fait de la faiblesse de mai.

---

## 2. Performance par structure de hook

| Rang | Structure | Posts | Vues moy. | Total | Outliers | Taux | Eng. |
|---|---|---|---|---|---|---|---|
| 1 | Éducatif | 12 | 580 | 6 958 | 1 | 8 % | 4,79 % |
| 2 | Question | 8 | 562 | 4 496 | 1 | 12 % | 4,68 % |
| 3 | FOMO | 2 | 816 | 1 632 | 0 | 0 % | 5,15 % |
| 4 | Choc | 3 | 606 | 1 818 | 0 | 0 % | 5,25 % |
| 5 | Annonce | 2 | 278 | 556 | 0 | 0 % | 4,60 % |
| 6 | Comment-faire | 2 | 274 | 549 | 0 | 0 % | 4,27 % |

**Ce qui marche :** Éducatif et Question portent 20 des 30 posts et concentrent les deux outliers
récents. FOMO a la meilleure moyenne (816) mais sur 2 posts — échantillon insuffisant.

**Ce qui ne marche pas :** Annonce et Comment-faire (278 et 274 vues moy.), 2 posts chacun. À
surveiller, pas à condamner.

---

## 3. Top hook frameworks

### 1. « Vous pensez que [X] est bruyant ? En vrai [Y] est silencieux grâce à [Z]. »
> **Hook parlé :** « Aujourd'hui je t'embarque avec nous sur un chantier de climatisation. »

**Vues :** 1 433 | **Outlier :** 2,47× (hit) | **Type :** Démo | **Sujet :** climatisation silencieuse
**CTA :** Un devis ? 👇 | **URL :** https://www.instagram.com/p/DalMYN5N2OB/

### 2. « [X] pour avoir [Y] installée ? On vous explique [Z] ! »
> **Hook parlé :** « Combien de temps pour avoir sa climatisation installée ? »

**Vues :** 1 383 | **Outlier :** 2,39× (hit) | **Type :** Avis | **Sujet :** délai installation
**CTA :** Un devis ? 👇 | **URL :** https://www.instagram.com/p/DaLdCPMtuhx/

### 3. « Vous vous dites que [X] ? En fait, [Y] ! »
> **Hook parlé :** « Vous souffrez de la chaleur en été ? C'est maintenant qu'il faut prévoir… »

**Vues :** 1 099 | **Outlier :** 1,90× | **Type :** Conseil | **CTA :** aucun
**URL :** https://www.instagram.com/p/DVMMGcZChd9/

### 4. « [X] se passe pour [Y] ? On t'explique [Z] »
> **Hook parlé :** « Comment ça se passe pour avoir une climatisation ? »

**Vues :** 903 | **Outlier :** 1,56× | **Type :** Conseil | **CTA :** Un devis ? 👇
**URL :** https://www.instagram.com/p/DavbrWvtc8-/

### 5. « Vous vous demandez [X] ? En vrai [Y] »
> **Hook parlé :** « Il y a-t-il une pénurie chez les fournisseurs de climatiseurs ? Non ! »

**Vues :** 895 | **Outlier :** 1,55× | **Type :** Avis | **CTA :** Un devis ? 👇

**Patterns dans le top :** le motif « fausse croyance → correction » (*Vous pensez que… ? En vrai…*)
revient sur 4 des 5 meilleurs. Le sujet est systématiquement la **climatisation résidentielle**. Le
CTA « Un devis ? 👇 » accompagne 3 des 4 premiers.

---

## 4. Hook alignment — la variable gagnante

#### Comparaison 1 : même sujet exact, « climatisation silencieuse »
- **GAGNANT** (1 433 vues, 2,47×) — « Aujourd'hui je t'embarque avec nous sur un chantier de
  climatisation. » · CTA : Un devis ? 👇 · https://www.instagram.com/p/DalMYN5N2OB/
- **SOUS-PERFORMEUR** (225 vues, 0,39×) — « À la recherche d'une climatisation silencieuse et
  élégante ? » · CTA : Contacte-nous pour un devis.

**DIFFÉRENCE IDENTIFIÉE :** le gagnant montre un **chantier réel filmé** ; le perdant est une
formulation publicitaire fermée. Même promesse — l'un prouve, l'autre vend.

#### Comparaison 2 : même sujet, « installation climatisation »
- **GAGNANT** (1 099 vues, 1,90×) — « Vous souffrez de la chaleur en été ? C'est maintenant qu'il
  faut prévoir… »
- **SOUS-PERFORMEUR** (223 vues, 0,39×) — « Nous aimons les jolies installations ! »

**DIFFÉRENCE IDENTIFIÉE :** le gagnant part d'un **problème vécu par le spectateur** ; le perdant
part de l'entreprise. Dès que la phrase commence par « nous », les vues s'effondrent.

#### Comparaison 3 : accroche identique, sujets différents
- **1 433 vues** — « je t'embarque… » sur un chantier climatisation (B2C)
- **227 vues** — « je t'embarque… » sur un dépannage de congélateur de boulangerie (B2B)

**DIFFÉRENCE IDENTIFIÉE :** ce n'est pas le hook, c'est **le sujet**. Accroche identique mot pour
mot, écart de 6×.

### Patterns d'alignement
1. Parler du problème du spectateur, jamais de soi ni de son savoir-faire.
2. Montrer un chantier réel bat une formulation d'annonce, à sujet égal.
3. Le sujet plafonne la portée, quel que soit le hook.

---

## 5. Analyse des sujets

### Sujets qui font mouche

| Rang | Sujet | Posts | Vues moy. | Outliers |
|---|---|---|---|---|
| 1 | délai installation climatisation | 1 | 1 383 | 1 |
| 2 | climatisation silencieuse | 2 | 829 | 1 |
| 3 | climatisation budget | 1 | 997 | 0 |
| 4 | pénurie climatiseurs | 1 | 895 | 0 |
| 5 | entretien climatisation | 1 | 843 | 0 |
| 6 | climatisation Amazon | 1 | 837 | 0 |

### Sujets volume

| Rang | Sujet | Posts | Vues moy. | Total |
|---|---|---|---|---|
| 1 | installation climatisation | 4 | 632 | 2 529 |
| 2 | climatisation silencieuse | 2 | 829 | 1 658 |
| 3 | dépannage climatisation | 2 | 348 | 697 |

### Sujets faibles (à ré-angler)

| Sujet | Posts | Vues moy. |
|---|---|---|
| préparation climatisation | 1 | 176 |
| installation hotte de cuisine | 1 | 219 |
| dépannage congélateur boulangerie | 1 | 227 |
| dépannage chambre froide | 1 | 232 |
| installation pompe à chaleur | 1 | 262 |
| climatisation abordable | 1 | 276 |

### Insights sujets
- **Cluster gagnant :** les questions d'avant-achat en clim résidentielle — délai, prix, bruit,
  disponibilité. Tous entre 837 et 1 383 vues.
- **Cluster faible :** le froid commercial (chambre froide, congélateur, hotte, frigo magasin) —
  176 à 299 vues, sans exception.
- **Sous-exploité mais performant :** les sujets d'opinion — « climatisation Amazon » (837) et
  « pénurie » (895), 1 post chacun. Veine à creuser.
- **Combo gagnant :** question d'avant-achat × chantier filmé × CTA devis.

⚠️ 21 des 25 sujets n'ont qu'un seul post. Ce classement indique des pistes, pas des certitudes.

---

## 6. Type de contenu & appels à l'action

### Par type de contenu

| Type | Posts | Vues moy. | Outliers | Taux | Eng. |
|---|---|---|---|---|---|
| Avis | 7 | 680 | 1 | 14 % | 4,89 % |
| Conseil | 9 | 564 | 0 | 0 % | 4,47 % |
| Démo | 13 | 475 | 1 | 8 % | 4,94 % |

La **Démo** est le format le plus produit (13 posts) mais le moins performant en vues. L'**Avis** —
prise de position — est le moins produit et le plus performant.

### Call-to-action

CTA taggés : **21/30**.

| CTA | Posts | Vues moy. | Eng. |
|---|---|---|---|
| Devis / lien | 15 | 697 | 3,67 % |
| Aucun | 9 | 527 | 5,74 % |
| Contact / appel | 4 | 345 | 6,18 % |

Les posts avec CTA devis font plus de vues mais un taux d'engagement plus bas — artefact
arithmétique, cf. section 8.

---

## 7. Angle B2C vs B2B

| Cible | Posts | Vues moy. | Eng. moy. | Outliers | Lecture |
|---|---|---|---|---|---|
| Particulier (clim/PAC maison) | 22 | 654 | 4,42 % | 3 | **portée** |
| Pro / froid commercial | 8 | 373 | 5,76 % | 0 | **preuve de métier** |

L'hypothèse de départ est confirmée : le B2C va chercher l'audience froide (+75 % de vues), le B2B
parle à une audience déjà acquise (engagement supérieur, zéro outlier).

**Implication :** deux outils différents, pas deux options concurrentes. Le B2C alimente
l'acquisition, le B2B installe la crédibilité auprès des abonnés existants. Le ratio actuel
(~3 B2C pour 1 B2B) paraît juste.

---

## 8. Rétention

> 🔧 **Non instrumenté.** `avg_watch_time` et `replays` sont à 0 sur les 30 posts — le scrape Apify
> ne les remonte pas. Il faudrait le token Meta Graph (`META_ACCESS_TOKEN` actuellement `MISSING`).

**Observation de substitution :** corrélation vues ↔ taux d'engagement = **−0,60** (fortement
négative). Corrélation vues ↔ **nombre absolu d'interactions** = **+0,59** (positive).

Traduction : quand un post fait beaucoup de vues, son *pourcentage* d'engagement baisse
mécaniquement (audience plus froide), mais le *nombre réel* de personnes qui réagissent augmente.
Ne jamais juger un post sur son seul taux d'engagement.

---

## 9. Dimensions à venir (non instrumentées)

> 🔧 Prêtes dans le schéma, pas encore alimentées par le pipeline.

- **Durée** (`duration`) — 🔧 non instrumenté
- **Format visuel** (`visual_format`) — 🔧 non instrumenté
- **Text hook** (texte à l'écran, `text_hook`) — 🔧 non instrumenté
- **Hook visuel** (`visual_hook`) — 🔧 non instrumenté
- **Structure de contenu** (`content_structure`) — 🔧 non instrumenté
- **Reach** (`reach`) — 🔧 à 0 sur les 30 posts

---

## 10. Synthèse — classements

### À doubler

| Dimension | Top performeur | Pourquoi |
|---|---|---|
| Structure de hook | Éducatif / Question | 20 posts, les 2 outliers récents |
| Framework | « Vous pensez que [X] ? En vrai [Y] » | Présent sur 4 des 5 meilleurs |
| Sujet | Questions d'avant-achat clim | 837 à 1 383 vues, cluster le plus régulier |
| Type | Avis | 680 vues moy., 14 % d'outliers |
| Angle | B2C | 654 vues moy., les 3 outliers |

### À corriger / réduire

| Dimension | Sous-performeur | Pourquoi |
|---|---|---|
| Ouverture | Toute phrase commençant par « Nous… » | 219 et 223 vues |
| Sujet | Froid commercial en accroche | 176-299 vues, plafond net |
| Type | Démo sans question d'accroche | 13 posts pour 475 vues moy. |

### Notes de contexte
- **21 des 25 sujets n'ont qu'un seul post.** Beaucoup de lignes ci-dessus sont des indices, pas des lois.
- **3 outliers seulement**, dont un post de mars 2024 sans analyse (légende générique). Base
  statistique mince.
- **Le post à 1 433 vues tire les moyennes** de juillet et du cluster « clim silencieuse ».
- **Correction d'une lecture antérieure (même session) :** l'accroche « je t'embarque » avait été
  jugée pénalisante pour l'engagement sur la base de 6 posts. Sur les 30, cette famille fait 570 vues
  de moyenne contre 600 pour les questions directes — écart négligeable. Le vrai discriminant est le
  **sujet** (B2C vs froid commercial), pas cette formule.

---

## 11. Brief — pour scripter le prochain contenu

### Formule gagnante
- **Structure :** Question ou Éducatif
- **Framework :** « Vous pensez que [X] ? En vrai [Y] » ou « Combien de temps / combien ça coûte
  pour [X] ? »
- **Sujet :** question d'avant-achat en clim résidentielle · **Angle :** B2C
- **Format :** chantier réel filmé · **CTA :** Un devis ? 👇

### Règles de hook
1. **À FAIRE :** ouvrir sur le problème ou la question du spectateur (« Combien de temps… »,
   « Vous souffrez de… »).
2. **À FAIRE :** corriger une fausse croyance — motif le plus présent dans le haut du classement.
3. **À ÉVITER :** commencer par « Nous… » — les deux posts concernés sont dans le bas du classement.

### Règles de sujet
- **Sujets chauds :** délai d'installation, prix, bruit, disponibilité, entretien.
- **Sous-exploités :** les sujets d'opinion (« n'achetez pas votre clim sur Amazon », pénurie) —
  2 posts, 866 vues de moyenne.
- **À réserver :** le froid commercial — excellent en preuve de métier, plafonné en portée.

### Top frameworks à réutiliser
1. « Vous pensez que [X] ? En vrai [Y] » — 1 433 vues, 2,47×
2. « Combien de temps pour avoir [X] ? On vous explique » — 1 383 vues, 2,39×
3. « Vous souffrez de [X] ? C'est maintenant qu'il faut [Y] » — 1 099 vues, 1,90×
4. « Comment ça se passe pour [X] ? On t'explique » — 903 vues, 1,56×
5. « Y a-t-il [X] ? Non ! » — 895 vues, 1,55×

### Réutilisable vs jetable
- **Bénéfice reproductible** (se repostent tels quels chaque saison) : délai d'installation, clim sur
  Amazon, prix, entretien, bruit.
- **Émotion one-shot / actu** (ne pas resservir tel quel) : canicule du jour, clin d'œil « Cazal dans
  un film », actualité prix matériaux.
