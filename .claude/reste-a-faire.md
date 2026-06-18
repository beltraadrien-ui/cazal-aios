# Reste à faire — AIOS Cazal Réfrigération

> Source unique de **ce qu'il reste à construire**. Toute tâche (fonctionnalité, branchement,
> correction, rangement) vit ici. On coche au fur et à mesure. En **mode build**, Claude lit ce
> fichier pour savoir « où on en est », et le met à jour en fin de build.
>
> Le *quoi vendu* (engagement 800 €) et le *pourquoi technique* sont dans
> [`../convention-build.md`](../convention-build.md). Le *pourquoi des décisions* est dans
> [`../decisions/log.md`](../decisions/log.md). Le *comment construire* est dans
> [`build-conventions.md`](build-conventions.md).

## Légende
- `[ ]` à faire · `[~]` en cours · `[x]` fait. Ordre conseillé : Bloc 0 → 2 → 1 → 3 → 4 → 5.

---

## Bloc 0 — Hygiène repo + balises du mode build
- [x] Repo Git Cazal autonome (lien vers nateherkai/AIS-OS coupé).
- [x] 5 décisions d'archi loggées dans `decisions/log.md`.
- [x] Fichiers bruts archivés (transcripts + appel de cadrage) ; `convention-build.md` annoté.
- [x] `reste-a-faire.md` créé (ce fichier).
- [x] `build-conventions.md` créé.
- [x] Section « mode utilisation vs mode build » ajoutée à `CLAUDE.md`.

## Bloc 1 — Connections (débloque le reste)
- [ ] **Apify** : brancher le token (compte créé, user `Loïc_Cazal`) + `references/apify-api.md`.
- [ ] **Supabase** : créer/connecter la base contenu (ou rester 100 % markdown au début, cf. décision).
- [ ] **Claude Pro** souscrit côté Loïc + **Wispr Flow** installé sur son PC Windows.
- [ ] Mettre à jour `connections.md` (mécanisme + auth + fraîcheur) à chaque branchement.

## Bloc 2 — Système Résumés vocaux / devis (quick win, 100 % mobile)
- [ ] Rédiger LE **template figé** de résumé (titre / contexte / mesures / matériel / prochaines étapes…).
- [ ] Créer le **Projet Claude mobile « Cazal — Résumés »** (custom instructions = template).
- [ ] Gérer les variantes (récap avant-devis / réunion archi / dépannage) dans le même Projet.
- [ ] Tester sur 2-3 vocaux réels de Loïc → la structure tient ?

## Bloc 3 — Système Création de contenu (hybride mobile + engine)
**Socle de contexte portable :**
- [ ] Finaliser `references/voice.md` : scraper 29 articles blog + vidéos FB → mode échantillons.
- [ ] Écrire `format-reel.md`, ICP, offres, contraintes (actif portable chargé mobile ET engine).

**Couche mobile :**
- [ ] Projet « Cazal — Reels/Contenu » avec voix + format + `rapport-perf-digest.md` en Knowledge.
- [ ] Tester : 3 photos + vocal « fais-moi un script » → rendu mobile OK ?

**Couche engine (asynchrone) :**
- [ ] Scraping concurrents IG (Apify) → distillation `rapport-perf-digest.md` (style wiki).
- [ ] Base d'idées (Airtable) + génération d'angles.
- [ ] Veille / propositions d'idées automatiques.
- [ ] Auto-amélioration (apprentissages redescendent dans le digest).
- [ ] Skills engine : scripts reels, articles blog, posts GMB, posts réalisations.

## Bloc 4 — Process & friction (avant la formation)
- [ ] Mini-process « publication contexte repo → Projet mobile » (sync voix de marque).
- [ ] Process ré-upload hebdo du digest de perf (manuel d'abord).
- [ ] Historique photos/réalisations → dépôt Drive.

## Bloc 5 — Accompagnement (livrable inclus)
- [ ] Visios de formation 1h (devant Loïc, il manipule).
- [ ] Canal support WhatsApp 1 an.

---

## Hors-scope (évolutions futures, PAS dans les 800 €)
- ⏳ Prospection LinkedIn / cold email (~500 € en plus, 3ᵉ espace de travail).
- ⏳ Génération vidéo (Nano Banana / avant-après immo).
- ⏳ Pont « vocal sur chantier → déclenche un vrai script » (le plus fragile, reportable).
