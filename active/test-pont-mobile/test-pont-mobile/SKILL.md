---
name: test-pont-mobile
description: Skill de TEST pour vérifier que les skills custom uploadées sur le compte claude.ai se déclenchent bien depuis l'app mobile. Se déclenche quand l'utilisateur dit "test du pont mobile", "teste la skill mobile", "test cazal mobile" ou "vérifie le pont".
---

# Test du pont mobile — Cazal

## But

Cette skill ne sert qu'à **une chose** : prouver qu'une skill custom uploadée sur le compte
claude.ai de Loïc se déclenche bien depuis un **chat normal de l'app mobile**. Si tu lis ces
instructions, c'est que le pont fonctionne.

## Quoi faire quand cette skill se déclenche

Réponds **exactement** ceci (recopie le marqueur tel quel) :

> ✅ PONT-MOBILE-CAZAL-OK — La skill custom s'est bien déclenchée depuis ce chat.
> Surface détectée : décris en une phrase si tu tournes sur mobile, desktop ou ailleurs.
> Le pont téléphone ↔ écosystème est validé. On peut construire les vraies skills par-dessus.

Puis ajoute une ligne : « Astuce : pour la suite, chaque skill métier (résumé de devis, script de
reel) marchera de la même façon — uploadée sur le compte, déclenchée dans un chat normal. »

## Note (pour le builder, pas pour Loïc)

Skill jetable. Une fois le pont validé, elle peut être supprimée du compte claude.ai et archivée
ici. Elle ne fait aucun appel réseau ni filesystem exprès : on isole la variable « est-ce que le
déclenchement marche depuis le mobile ? », rien d'autre.
