---
name: script-reel-chantier
description: Transforme un vocal de chantier de Loïc (ce qu'il vient de faire) + ses photos en un script de reel face-caméra prêt à filmer, sans idéation préalable. Trois variantes - reel Instagram/Facebook (défaut), réalisation avant/après pour le site, post Google My Business. Se déclenche sur "fais-moi un script de reel", "script pour ce chantier", "j'ai fini une install fais un reel", "post pour cette réalisation", "post Google".
---

# Script de reel chantier — Cazal Réfrigération (SCRIPTING)

## Ce que fait cette skill

Le **skill phare** de Loïc, pensé pour le terrain. Il finit un chantier, filme/photographie, et dicte
un vocal rapide (« voilà ce que je viens de faire »). Cette skill en sort **directement un script de
reel face-caméra** (hook + corps + CTA), **sans phase d'idéation** : on part du chantier réel. Elle
réutilise/adapte ce qui marche (`rapport-perf-digest.md`).

> Skill de surface (mobile). Loïc joint ses photos au chat — elles aident à proposer les plans à filmer.

## Les 3 variantes

- **A — Reel Instagram/Facebook** (défaut) : script face-caméra. Format → `references/format-reel.md`.
- **B — Réalisation avant/après** (site web) : fiche portfolio. Format → `references/format-realisation.md`.
- **C — Post Google My Business** : post court local-SEO. Format → `references/format-gmb.md`.

En cas de doute, demander en une phrase : « C'est pour un reel, une réalisation sur le site, ou un post
Google ? (ou plusieurs) ».

## Étapes

1. **Identifier la variante** (A/B/C, ou plusieurs).
2. **Lire le contexte** : `references/framework-hook.md` (psycho — obligatoire AVANT d'écrire),
   `references/voice.md` (ton de Loïc), `references/angles-signature-cazal.md` (angles + filtre),
   et le **digest de perf** (ce qui marche / à ré-angler) — **mode dual** : si le **connecteur
   Supabase MCP** est disponible, lire le plus récent (`SELECT contenu FROM syntheses WHERE
   type='digest-perf' ORDER BY run_date DESC LIMIT 1` — toujours frais) ; sinon
   `references/rapport-perf-digest.md` bundlé (snapshot). Jamais d'écriture dans `syntheses` ici.
3. **Extraire les faits** du vocal : prestation faite, type de client, lieu/zone, bénéfice client,
   détails visuels (avant/après, le geste, l'unité posée). Ne garder que ce qui est dit ; ne rien inventer.
4. **Produire** selon le format figé de la variante :
   - **A** : 3 options de hook (Loïc choisit) → fiche de tournage (beats + CTA + légende + texte écran
     + plans à filmer), suivant `format-reel.md` et les beats de `framework-hook.md`.
   - **B** : fiche réalisation avant/après suivant `format-realisation.md`.
   - **C** : post GMB court suivant `format-gmb.md`.
5. Sortir le résultat dans la structure exacte du format, rien autour.

## Règles fermes

- **Lire `framework-hook.md` avant d'écrire un hook** (psycho non négociable).
- **Ne jamais inventer** : info non dictée → ne pas la mettre (ou marquer `[à préciser]`). Pas de
  fausse donnée dans un post public.
- **Voix de Loïc, grand public, zéro jargon** (cf. `voice.md` + filtre `angles-signature-cazal.md`).
- **Hooks < 15 mots**, montrer > dire, CTA orienté contact/devis.
- **Réutiliser ce qui marche** (digest) ; si un angle proche a sous-performé, le **ré-angler** (autre
  cadrage), pas le bannir.
- Tant que le digest est en amorçage (pas de data), s'appuyer sur `framework-hook.md` +
  `angles-signature-cazal.md` et le signaler discrètement.
- Sortie destinée à être **filmée/publiée par Loïc après validation** — ne jamais publier en son nom.
