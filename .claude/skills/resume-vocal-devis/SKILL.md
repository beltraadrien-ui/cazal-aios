---
name: resume-vocal-devis
description: Transforme un vocal de chantier de Loïc en un résumé structuré TOUJOURS au même format, à coller dans Interfast. Corrige les noms de clim mal compris à la dictée, complète la référence des clims à poser et repose la question quand une info importante manque. Se déclenche sur "résume ce vocal", "fais le résumé pour le devis", "récap de visite", "récap avant-devis", "résumé réunion de chantier", "résumé dépannage", "résumé entretien", "résumé visite remplacement", "compte rendu modification installation frigo", "récap remplacement centrale". Cinq variantes gérées : avant-devis installation, réunion de chantier (archi), dépannage, entretien/maintenance, visite de remplacement d'installation frigorifique.
---

# Résumé vocal → devis — Cazal Réfrigération

## Ce que fait cette skill

Loïc dicte (ou colle un transcript de) ce qu'il a vu/fait sur un chantier. Cette skill en produit un
**résumé structuré, toujours dans la même forme**, prêt à **copier-coller dans Interfast**. Elle résout
son irritant n°1 : un assistant générique change la structure à chaque fois.

En plus du résumé, elle :
- **corrige les noms de clim mal compris à la dictée** (« Ayer » → Haier…) ;
- **complète la référence exacte** des clims à poser qui sont dans la liste de Loïc, et vérifie la couleur ;
- **repose la question** quand Loïc a oublié une info indispensable.

**Elle NE fait PAS le devis** (Interfast s'en charge).

## Fichiers à utiliser (bundlés avec cette skill)

- **`templates/format-resume.md`** : les 5 formats figés + les **infos indispensables** de chaque
  variante. Toujours s'y référer — ne pas réécrire le format de mémoire.
- **`references/referentiel-unites-interieures-clim.md`** : la liste des clims de Loïc (marques,
  gammes, références, couleurs) + les termes souvent mal retranscrits.

## Étapes

1. **Choisir la variante** (dans `templates/format-resume.md`) :
   - **A — Avant-devis INSTALLATION** (par défaut) : visite pour chiffrer une pose (mono/multisplit, PAC, hybride…).
   - **B — Réunion de chantier** : si Loïc mentionne un architecte / d'autres corps de métier / une réunion.
   - **C — Dépannage** : si c'est une panne / intervention de réparation.
   - **D — Entretien / maintenance** : si c'est un chiffrage d'entretien d'un parc existant (nb d'unités, forfait, pas de travaux de pose).
   - **E — Remplacement d'installation frigorifique** : visite pour chiffrer le remplacement ou la modification d'une installation de froid existante (centrales, groupes de condensation, chambres froides, changement de gaz, « remodeling »).
   - En cas de doute, demander en une phrase : « C'est un avant-devis installation, un entretien, une réunion de chantier, un dépannage ou une visite de remplacement frigo ? »

2. **Corriger les erreurs de dictée** sur les noms de marques et de modèles (section ci-dessous).

3. **Remplir le template** de la variante, section par section, **uniquement avec ce qui a été dicté**.

4. **Clims à poser : compléter la référence et vérifier la couleur** (section ci-dessous).

5. **Rendre la réponse, dans cet ordre :**
   1. **Le résumé, seul dans un bloc de code** (Loïc le copie avec le bouton « copier » du bloc),
      dans la structure exacte du template. Pas de blabla d'intro.
   2. **Sous le bloc, « À vérifier »** — seulement s'il y a quelque chose à signaler : mots douteux,
      modèles absents de la liste, couleurs qui n'existent pas dans la gamme, références à confirmer,
      liens des références trouvées.
   3. **En dernier, « Il te manque »** — seulement s'il manque des infos indispensables : les questions.

   Rien de ce qui est sous le bloc ne doit se retrouver dans le bloc : Loïc ne colle que le bloc dans
   Interfast.

6. **Quand Loïc répond aux questions** : renvoyer **le résumé complet mis à jour** (un nouveau bloc
   entier, pas seulement les ajouts), pour qu'il n'ait qu'une seule version à copier.

## Noms de marques et de modèles (dictée)

- **Les marques sont libres.** Écrire exactement la marque et le modèle que Loïc dit. La liste de
  Loïc n'est **pas limitative** : ne jamais remplacer une marque par une autre parce qu'elle n'y
  figure pas.
- **Corriger automatiquement** les erreurs de dictée listées dans le référentiel (« Termes souvent
  mal retranscrits ») et les noms de gammes du référentiel mal écrits — **seulement quand le contexte
  parle clairement de matériel**. Quand la correction est sûre, la faire sans la signaler.
  - **« ailleurs »** est aussi un mot courant (« on met l'unité extérieure ailleurs ») : ne le
    remplacer par Haier que s'il désigne clairement une marque (« une ailleurs de 3,5 kW »).
  - **« Hyper Heating »** est une technologie Mitsubishi présente sur plusieurs appareils (la console
    MFZ-KW de la liste, mais aussi le mural MSZ-RZ) : si Loïc ne précise pas mural ou console, le lui
    demander dans « Il te manque ».
- **Mot douteux** (ressemble à une marque ou un modèle, mais pas reconnu avec certitude) : écrire la
  forme la plus probable dans le résumé et la lister dans « À vérifier ». Ne jamais deviner en silence.

## Clims à poser : référence exacte et couleur

Concerne les clims **à poser ou à chiffrer** (surtout la variante A, et toute clim à fournir dans une
autre variante).

- **Modèle présent dans la liste de Loïc :**
  1. À partir de la marque, de la gamme, de la puissance et de la couleur dictées, **chercher la
     référence exacte** sur le site du fabricant ou d'un distributeur (recherche web), puis la vérifier.
  2. Référence trouvée et vérifiée → l'écrire dans le résumé (« réf. … ») et mettre le lien de la
     source dans « À vérifier ».
  3. Référence pas trouvée avec certitude, ou recherche web indisponible → écrire « réf. à confirmer »
     dans le résumé.
  4. **Couleur** : si la couleur dictée n'existe pas pour cette gamme dans la liste, garder la couleur
     telle que dictée et le signaler dans « À vérifier » (ex. « Daikin Perfera en noir : dans ta liste,
     la Perfera existe seulement en blanc mat. »).
- **Modèle absent de la liste :** l'écrire exactement comme Loïc l'a dit, sans chercher de référence,
  et ajouter dans « À vérifier » : « [modèle] : ce modèle n'est pas dans ta liste. Je l'ai écrit tel
  que tu l'as dit, sans vérifier la référence ni la couleur. » **Ne jamais écrire qu'un modèle
  « n'existe pas » ou est « inconnu »** : il est seulement absent de la liste.
- **Appareil déjà en place** (dépannage, entretien, remplacement) : écrire ce qui est dicté (erreurs
  de dictée corrigées), **sans chercher de référence ni ajouter de remarque « pas dans ta liste »** —
  un appareil posé il y a des années n'a pas forcément la référence du catalogue actuel.

## Infos oubliées : reposer la question

- Chaque variante a sa liste d'**infos indispensables** (dans `templates/format-resume.md`).
- Si l'une d'elles n'a pas été dictée : laisser `— (non précisé)` dans le résumé et la demander dans
  « Il te manque », sous forme de question simple (« Tu ne m'as pas dit le gaz de la centrale B,
  c'est lequel ? »).
- **5 questions maximum à la fois**, dans l'ordre de la liste. S'il en reste, les poser au tour suivant.
- Au premier passage, une info indispensable manquante va **seulement dans « Il te manque »**, pas
  dans la section « À obtenir du client / À clarifier » du résumé (pas de doublon).
- Si Loïc répond qu'il n'a pas l'info ou qu'il faut la demander au client : garder `— (non précisé)`
  et l'ajouter dans la section « À obtenir du client / À clarifier » du résumé.
- Ne pas poser de question sur les infos non indispensables : elles restent `— (non précisé)` sans
  commentaire.

## Règles fermes

- **Structure invariable** : toujours les mêmes sections, dans le même ordre. C'est tout l'intérêt.
- **Ne jamais inventer.** Info non dictée → écrire `— (non précisé)`. Mieux vaut un trou visible
  qu'une donnée fausse qui se retrouve dans un devis.
- **Déduction évidente** (ex. 2 unités intérieures + 1 extérieure → multisplit ; un gaz annoncé pour
  toute l'installation → reporté sur chaque poste) : on peut l'écrire, mais toujours la signaler dans
  « À vérifier ».
- **Vocabulaire de Loïc**, pas de jargon ajouté. Rester factuel et terre-à-terre.
- Repérer et bien capturer les éléments qui **impactent le prix** : passage des tuyaux, carottage/
  perçage (préciser le matériau, ex. mur en pierre), location de nacelle, contraintes d'accès.
- Si le vocal est long ou part dans tous les sens : réorganiser dans les bonnes sections sans rien perdre.

> Statut : **v3 (2026-09-25)** — variante E, questions de rattrapage, référentiel clim. Les listes
> d'infos indispensables sont **à valider avec Loïc** sur de vrais vocaux.
