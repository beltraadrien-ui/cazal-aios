---
name: idee-contenu
description: Liste les idées de contenu disponibles, fait choisir une idée à Loïc, puis le format (reel, article de blog, ou les deux), et développe le sujet en plusieurs variations d'angles prêtes à scripter. Se déclenche sur "idée de contenu", "propose-moi des idées", "qu'est-ce que je peux poster", "développe une idée".
---

# Idée de contenu — Cazal Réfrigération (IDÉATION)

## Ce que fait cette skill

Le point d'entrée idéation côté Loïc. Elle **liste les idées disponibles**, le laisse **en choisir
une**, lui demande **quel format** (reel / article de blog / les deux), puis **multiplie le sujet en
plusieurs variations d'angles** prêtes à passer au scripting. Biaisée vers ce qui marche
(`rapport-perf-digest.md`), elle ré-angle aussi ce qui a sous-performé (pas de liste noire).

> Skill de surface (utilisable sur mobile). Sa sortie alimente `scripter-reel` et/ou `rediger-article`.

## Étapes

1. **Lister les idées** — la source de vérité est la table Supabase **`idees`**. Détecter le mode :
   - **Mode Supabase** (préféré) : si le **connecteur Supabase MCP** est disponible, lire les idées au
     statut `idée` (`SELECT * FROM idees WHERE statut='idée' ORDER BY created_at DESC`).
   - **Mode snapshot** (fallback, hors-ligne / pas de connecteur) : lire `references/base-idees.md`.
   Présenter les idées en liste numérotée (sujet + archétype + pourquoi ça marche + format suggéré).
   **STOP — demander à Loïc d'en choisir une** (ou de dicter un sujet libre s'il a une idée à lui).

2. **Choisir le format** : demander → **reel**, **article de blog**, ou **les deux**.

3. **Contexte** : lire le **digest de perf** (à exploiter / à ré-angler) — **mode dual**, comme pour
   les idées : mode Supabase → `SELECT contenu FROM syntheses WHERE type='digest-perf' ORDER BY
   run_date DESC LIMIT 1` (toujours frais) ; mode snapshot → `references/rapport-perf-digest.md`
   bundlé. Puis `references/angles-signature-cazal.md` (angles + filtre), `references/voice.md` (ton).
   Jamais d'écriture dans `syntheses` depuis la surface.

4. **Développer en variations** : décliner le sujet via les **7 cadrages** (en choisir 3-5 pertinents) :
   - Liste · Focus unique · Contrarian · Showcase · Tutoriel · Comparaison · Émotionnel.
   - Règles : chaque variation = cadrage différent ; **≥ 1 contrarian** ; **≥ 1 tutoriel/conseil** ;
     chaque variation filmable/rédigeable seule ; **zéro jargon**.
   - Numéroter les angles `A1, A2, A3…` (ordre des variations retenues).
   - Pour chaque variation : titre, cadrage, angle/hook pressenti, pourquoi ça peut marcher (réf. digest).

5. **Présenter les variations** → **STOP, attendre que Loïc valide/choisisse**.

6. **Passer la main au scripting** selon le format choisi :
   - reel → enchaîner sur `scripter-reel` (ou le proposer).
   - article → enchaîner sur `rediger-article`.
   - les deux → les deux, à partir des mêmes faits.
   - Mettre à jour le statut de l'idée → `choisie` : en **mode Supabase** via le connecteur MCP
     (`UPDATE idees SET statut='choisie' WHERE id=…`) ; en **mode snapshot**, dans `base-idees.md`.
   - ⚠️ Le connecteur peut être en **lecture seule** : si l'UPDATE est refusé, **ne pas prétendre
     avoir écrit** — annoncer « idée notée comme choisie, la base sera mise à jour depuis le PC »
     et continuer normalement (le choix n'est pas perdu, il est dans la conversation).

## Règles fermes

- **Toujours faire choisir** (l'idée, puis le format) — ne pas auto-décider.
- **Biaiser vers ce qui marche** ; **ré-angler** ce qui a sous-performé (autre cadrage), ne pas bannir.
- Filtre « bon pour Cazal ? » sur chaque variation (`angles-signature-cazal.md`).
- Zéro jargon, grand public (sauf sujets pro explicitement destinés à LinkedIn).
- Ne rien inventer (prix, aides, normes) : marquer `[à vérifier par Loïc]`.
