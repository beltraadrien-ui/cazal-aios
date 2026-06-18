# Decisions Log

Append-only record of meaningful decisions and why they were made. `/level-up` Phase 2 (Method interview) writes scoped automation specs here. You can also append manually whenever you decide something worth remembering.

**Format per entry:**

```
## YYYY-MM-DD — Short title

**Decision:** what was decided.

**Why:** the reasoning, constraints, and what would change your mind.

**Alternatives considered:** what else was on the table.

**Owner:** who's accountable.
```

Keep it terse. Future-you will thank present-you for capturing the *why*, not just the *what*.

---

## 2026-06-18 — Séparer la surface de capture de l'engine

**Decision:** L'AIOS de Loïc est en deux couches : une **surface de capture/consommation** (app Claude mobile, Projets) où Loïc vit ~80 % du temps (vocal in, texte out, photos jointes), et un **engine** (Claude Code + n8n + Supabase/markdown) qui tourne en coulisse (scraping, analyse de perf, veille) et qu'il ne touche pas.

**Why:** Tension de vente : « tout vit dans Claude Code » alors que Claude Code n'est pas une surface mobile/vocale. Besoin n°1 de Loïc = piloter au téléphone, au vocal, sans taper. La séparation résout la tension. L'actif portable = le folder de contexte, chargé dans les DEUX mondes. *Changerait d'avis si* une surface unique mobile+engine devenait viable.

**Alternatives considered:** Tout en Claude Code mobile via GitHub (mauvaise UX terrain pour photos+vocal) ; tout dans l'app mobile (impossible pour scripts/scraping).

**Owner:** Adrien.

## 2026-06-18 — Markdown-first pour le digest de perf

**Decision:** Démarrer le rapport de perf en **100 % markdown** (`rapport-perf-digest.md`, style wiki) chargé en Knowledge du Projet mobile. N'ajouter **Supabase** que quand le volume de scraping le justifie.

**Why:** Moins de pièces mobiles au départ, cohérent avec le pattern wiki déjà éprouvé. Un Projet mobile ne requête pas Supabase en live de toute façon — il lui faut un digest court (1-3 pages). *Changerait d'avis si* le volume/la sémantique de recherche dépasse ce que le markdown gère.

**Alternatives considered:** Supabase dès le début (sur-ingénierie au Day 1).

**Owner:** Adrien.

## 2026-06-18 — Pont « vocal sur chantier → script » reporté

**Decision:** Ne PAS construire le déclenchement d'un vrai script engine à la voix depuis le chantier (note vocale → webhook n8n / Cowork). Reporté, non promis.

**Why:** Hors du besoin réel ; c'est le morceau le plus fragile. Le vocal pilote la capture et la génération de texte (contexte→texte), pas l'analyse de perf en temps réel. Les workflows à scripts tournent en asynchrone côté engine (~1×/semaine suffit). *Changerait d'avis si* un vrai besoin terrain émerge après rodage des 2 systèmes.

**Alternatives considered:** Construire le pont dès le MVP (risque/complexité injustifiés).

**Owner:** Adrien.

## 2026-06-18 — Draft-only, tout au nom de Loïc

**Decision:** Le système RÉDIGE, Loïc poste à la main → **aucun accès en écriture de publication** (pas de Meta publishing, pas de GMB API, pas de WordPress REST ; on ne branche PAS Interfast). Tous les comptes et clés sont **créés et payés par Loïc**, collés par lui dans son IDE.

**Why:** Handoff 100 % propre (tout lui appartient), sécurité (jamais de secret dans le chat), et Interfast déjà rodé pour les devis. *Changerait d'avis si* Loïc demande explicitement la publication automatique plus tard.

**Alternatives considered:** Accès écriture pour auto-publier (risque, dépendance, hors besoin).

**Owner:** Adrien.

## 2026-06-18 — Repo Cazal autonome (lien vers le template de Nate coupé)

**Decision:** Le dossier `Cazal-1/` était un clone du starter kit `nateherkai/AIS-OS`. Le `.git` hérité a été supprimé et un nouveau repo Git Cazal a été initialisé (sans remote pour l'instant).

**Why:** C'est le projet de Loïc, plus celui de Nate. Évite la confusion d'un historique/remote pointant vers le template d'origine. *Changerait d'avis si* on veut tirer les futures mises à jour du template (peu probable, on a divergé).

**Alternatives considered:** Garder le remote vers Nate (confusion) ; pas de Git du tout (perte de traçabilité).

**Owner:** Adrien.
