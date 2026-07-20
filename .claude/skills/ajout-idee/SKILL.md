---
name: ajout-idee
description: Capte une idée de contenu à la volée dictée par Loïc, la normalise (sujet, archétype, format, pourquoi) et l'insère directement dans la base d'idées Supabase via un script Python. Le pendant "écriture" de idee-contenu (qui ne fait que lister). Se déclenche sur "ajoute une idée", "note cette idée", "j'ai une idée de contenu", "enregistre cette idée", "garde ça pour plus tard".
---

# Ajout d'idée — Cazal Réfrigération (CAPTURE)

Tu captes une idée de contenu **dès qu'elle passe par la tête de Loïc**. Il la dicte (vocal ou
texte), tu la transformes en une ligne propre de la base d'idées et tu l'**insères dans Supabase**.
Zéro friction : l'objectif est qu'aucune idée ne se perde.

> Pendant **écriture** de `idee-contenu` (qui, lui, **lit/liste** les idées et les développe).
> Une idée ajoutée ici réapparaît directement dans `idee-contenu`.

> ⚙️ **Skill engine** (Claude Code sur le PC) : l'insertion passe par un **script Python** qui lit
> les clés Supabase du `.env` local — **pas par le connecteur MCP** (Loïc ne l'aura pas forcément).
> Conséquence : ce skill **ne fonctionne pas sur mobile** sans MCP. Sur mobile, noter l'idée à la
> main et la rejouer ici depuis le PC.
> Si un **connecteur Supabase MCP (lecture seule)** est disponible (ex. Claude Desktop d'Adrien),
> l'utiliser pour la **vérification de doublons en direct** (`SELECT sujet FROM idees`) — mais
> l'**insertion** reste toujours par le script PC ci-dessous, jamais par le connecteur.

> 🔧 **Pattern engine** : on **invoque un script Python déterministe** qui **renvoie du JSON sur
> stdout** — on lit ce JSON, on ne fabrique rien. Secrets : dispo vérifiable via
> `python shared/config.py` (`SET`/`MISSING`), **jamais** `cat .env` / `echo $VAR`.

---

## Étapes

1. **Récupérer l'idée brute** de Loïc (texte ou transcript vocal). S'il en dicte plusieurs d'un
   coup, les traiter en **lot** (le script accepte une liste JSON).

2. **Normaliser** vers les colonnes de la table `idees` :
   - `sujet` — reformulé **court, clair, grand public, zéro jargon** (cf. `references/voice.md` et la
     liste « mots à éviter » de `references/angles-signature-cazal.md`).
   - `archetype` — mappé sur un des **angles signature** de `references/angles-signature-cazal.md`
     (ex. « Idée reçue cassée », « Ça coûte/consomme combien », « X ou Y ? », « L'erreur que tout le
     monde fait », « Le truc que personne ne vous dit », « Voilà ce que ça donne », « Question que
     vous vous posez »…).
   - `format` — proposer **reel**, **article**, ou **les deux** selon le sujet.
   - `pourquoi` — **1 phrase** : pourquoi ça peut marcher / qui ça touche.
   - `origine` = `"manuelle"` · `statut` = `"idée"` (valeurs par défaut du script, ne pas surcharger).
   - Passer le **filtre « bon pour Cazal ? »** de `angles-signature-cazal.md`. Si une case saute,
     retravailler l'angle ou le signaler à Loïc.
   - **Ne rien inventer** (prix, aides, normes, dates) → marquer `[à vérifier par Loïc]` dans le
     `sujet`/`pourquoi` au lieu d'affirmer.

3. **Montrer la (les) ligne(s) normalisée(s) à Loïc → STOP, attendre confirmation** (ou ajustement
   du sujet / format / archétype). Ne pas insérer avant validation.

4. **Insérer via le script Python** (depuis la racine du projet) :
   ```
   echo '<json>' | python shared/scripts/post/insert_idee.py
   ```
   - `<json>` = un objet (`{"sujet":"…","archetype":"…","format":"reel","pourquoi":"…"}`)
     ou une **liste** d'objets pour un lot.
   - Champs autorisés : `sujet, archetype, angle, cadrage, format, statut, pourquoi, origine,
     compte_id, notes`. `statut`/`origine` ont des défauts → inutile de les passer.
   - Le script renvoie `{"inserted": N, "ids": [...]}` sur stdout. **Lire ce JSON** pour confirmer.
   - Si le JSON contient des apostrophes, préférer `--json '<json>'` ou passer par stdin avec un
     heredoc pour éviter les soucis de quoting shell.

5. **Confirmer à Loïc** : nombre d'idées ajoutées + leur(s) sujet(s), et rappeler qu'il les
   retrouvera dans `idee-contenu` (« propose-moi des idées »).

## Règles fermes

- **Toujours montrer avant d'insérer** — pas d'écriture en base sans validation de Loïc.
- **Une idée = une ligne.** Pas de doublon évident : si le sujet ressemble fort à une idée déjà en
  base, le signaler plutôt que d'empiler.
- Grand public, zéro jargon (sauf sujet pro explicitement destiné à LinkedIn).
- Ne rien inventer ; `[à vérifier par Loïc]` pour tout chiffre/aide/norme non confirmé.
- Si les clés Supabase manquent (`python shared/config.py` → `MISSING`), le dire et **ne pas**
  prétendre avoir inséré.
