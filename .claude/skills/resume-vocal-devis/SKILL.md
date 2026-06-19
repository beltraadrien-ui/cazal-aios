---
name: resume-vocal-devis
description: Transforme un vocal de chantier de Loïc en un résumé structuré TOUJOURS au même format, à coller dans Interfast. Se déclenche sur "résume ce vocal", "fais le résumé pour le devis", "récap de visite", "récap avant-devis", "résumé réunion de chantier", "résumé dépannage". Trois variantes gérées : avant-devis, réunion de chantier (archi), dépannage.
---

# Résumé vocal → devis — Cazal Réfrigération

## Ce que fait cette skill

Loïc dicte (ou colle un transcript de) ce qu'il a vu/fait sur un chantier. Cette skill en produit un
**résumé structuré, toujours dans la même forme**, prêt à **copier-coller dans Interfast**. Elle résout
son irritant n°1 : un assistant générique change la structure à chaque fois.

**Elle NE fait PAS le devis** (Interfast s'en charge) et ne se connecte à rien — c'est du contexte→texte.

## Étapes

1. **Choisir la variante** (dans `templates/format-resume.md`) :
   - **A — Avant-devis** (par défaut) : récap d'une visite pour chiffrer.
   - **B — Réunion de chantier** : si Loïc mentionne un architecte / d'autres corps de métier / une réunion.
   - **C — Dépannage** : si c'est une panne / intervention de réparation.
   - En cas de doute, demander en une phrase : « C'est un avant-devis, une réunion de chantier ou un dépannage ? »

2. **Remplir le template** de la variante, section par section, **uniquement avec ce qui a été dicté**.

3. **Sortir le résumé** dans la structure exacte du template, rien autour (pas de blabla d'intro/conclusion).

## Règles fermes

- **Structure invariable** : toujours les mêmes sections, dans le même ordre. C'est tout l'intérêt.
- **Ne jamais inventer.** Info non dictée → écrire `— (non précisé)`. Mieux vaut un trou visible
  qu'une donnée fausse qui se retrouve dans un devis.
- **Vocabulaire de Loïc**, pas de jargon ajouté. Rester factuel et terre-à-terre.
- Repérer et bien capturer les éléments qui **impactent le prix** : passage des tuyaux, carottage/
  perçage (préciser le matériau, ex. mur en pierre), location de nacelle, contraintes d'accès.
- Si le vocal est long ou part dans tous les sens : réorganiser dans les bonnes sections sans rien perdre.
- À la fin, si des infos manquent pour chiffrer, les lister dans **Prochaines étapes / À clarifier**.

## Le format figé

Les trois variantes sont dans **`templates/format-resume.md`** (bundlé avec cette skill). Toujours s'y
référer — ne pas réécrire le format de mémoire.

> Statut : template **v1, à valider avec Loïc** sur de vrais vocaux avant d'être figé.
