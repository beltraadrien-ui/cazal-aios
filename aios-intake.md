# AIS-OS Intake

This is the source-of-truth file for your AIOS. Fill it in by typing, voice-pasting (Wispr Flow / OS dictation), or running `/onboard` for a guided conversation. Whichever mode, this file is what `/onboard` reads to scaffold your Day-1 setup.

**Hard cap: 7 questions.** Each answerable in under 60 seconds. Don't overthink — you can edit and re-run `/onboard` any time.

> Rempli depuis le transcript de l'appel de mise en place (Adrien × Loïc, 16 juin 2026). AIOS construit par Adrien Beltra (BeltraTech) pour le compte de Loïc Cazal.

---

## Q1 — Who are you, what do you sell, who do you sell it to?

Identity, offer, ICP. One paragraph each is fine.

```
IDENTITÉ — Loïc Cazal, fondateur de Cazal Réfrigération, frigoriste basé en
Belgique (près de la frontière française, côté Charleville). 27 ans. Indépendant
depuis 5 ans, société à 100 % depuis 3 ans. Équipe : 3 techniciens + 1 aide
administrative à tiers-temps (vérif paiements/factures, fiches de paye). Loïc fait
encore 100 % de l'opérationnel + tous les devis. Diplômé frigoriste (formation en
alternance) après des études de prof de gym (STAPS). Élément différenciant : fait
le métier par passion, pas pour l'argent ; obsédé par la satisfaction client.
Zone : ~80 km autour de chez lui (≈1h de route), Belgique ET France frontalière.

OFFRE — Installation et maintenance : climatisation, pompes à chaleur
(remplacement de chaudières → radiateurs ou plancher chauffant), ventilation
(VMC, CTA), boilers thermodynamiques. Côté pro : froid commercial (GMS type
Carrefour, Delhaize, Super U) et froid industriel (chambres froides, grossistes
en viande), tout l'équipement métiers de bouche (frigos, tables réfrigérées).
Contrats de maintenance annuels pour générer du revenu récurrent.

ICP — 50/50 particuliers / professionnels.
• Particuliers : couples 35-75 ans qui s'installent et commencent à avoir les
  moyens.
• Pros : restaurateurs, collectivités (homes/EHPAD), bouchers, boulangers, snacks,
  grossistes en viande / distributeurs, GMS. Du petit snack solo au grossiste de
  18 chambres froides sur 2000 m².
```

---

## Q2 — Paste 1-2 things you've written recently. Don't edit them.

An email, a LinkedIn post, a DM, a doc — anything that sounds like you when you're not trying. **Paste verbatim.** Do not type these mid-conversation with Claude — chat-shaped samples are worse than no samples (voice contamination).

```
[À COMPLÉTER — échantillons écrits bruts en attente]
Adrien doit scraper : les 29 articles de blog du site (cazalrefrigeration.be) +
les vidéos Facebook de Loïc, pour servir d'échantillons de voix authentiques.
Tant qu'ils ne sont pas récupérés, references/voice.md reste en mode "guidance"
(ci-dessous) plutôt qu'en mode "échantillons".
```

```
GUIDANCE DE VOIX (extraite du transcript, en attendant les vrais échantillons) :
Cible = grand public / clients potentiels, PAS d'autres artisans. Loïc ne veut PAS
faire de tuto technique pour frigoristes. Il parle bénéfices et résultats concrets
(« ça consomme moins d'électricité », « pas de poussière quand on est parti »,
« le temps que ça prend »), pas jargon métier. Ton accessible, terre-à-terre,
honnête. Un peu de technique vite fait OK, mais jamais le cœur du propos.
```

---

## Q3 — What are your 2-3 biggest priorities for the next 90 days?

Quarterly priorities. Not yearly aspirations. Things that, if not done by July, would make you say "I wasted Q2."

```
1. Diviser par ~5 le temps passé sur la création de contenu (reels Instagram/
   Facebook, articles de blog, posts Google My Business, réalisations sur le site)
   — aujourd'hui tout est fait main, c'est le plus chronophage. Objectif : piloter
   au vocal, valider, publier. Viser ~1 reel/2 jours, 1 article/semaine,
   1 post Google/semaine, 1 réalisation/semaine.
2. Standardiser les résumés de devis : à partir d'un vocal terrain, obtenir un
   résumé TOUJOURS au même format (machines, passage des tuyaux, carottage,
   location nacelle, spécificités type perçage mur en pierre) à coller dans le
   canevas Interfast.
3. (Plus tard, évolutif) Étendre à la prospection — LinkedIn / cold email.
```

---

## Q4 — Where does revenue actually land, and where is it tracked?

Multiple answers OK. Stripe? Skool? GoHighLevel? QuickBooks? A spreadsheet?

```
Logiciel métier Interfast : CRM complet + gestion des interventions, devis,
factures, gammes de maintenance (a remplacé Odoo). Relances devis/paiement déjà
automatisées dedans ; l'aide admin vérifie manuellement l'arrivée des paiements.
~10 devis/semaine. Revenu récurrent via contrats de maintenance annuels.
Sources de leads : appels téléphoniques directs, messages Facebook, formulaire de
contact du site (~7 leads sur 15 jours), plateforme de leads tierce (pompes à
chaleur, ~1 signature sur 3).
```

---

## Q5 — Where do you talk to customers, your team, and the outside world day-to-day?

Email (which one — Gmail / Outlook)? Slack? Teams? DMs (Skool / Discord / iMessage)? Phone?

```
Clients : téléphone (canal principal — les gens appellent directement), messages
Facebook, formulaire de contact du site. Réseaux : Instagram + Facebook (cible
particuliers, vidéos clim/PAC « mainstream »), LinkedIn (irrégulier, cible pro :
entretiens chambres froides, dépannages). Email pro : loic@cazal-refrigeration.be
(+ contact@cazalrefrigeration.be). Avec le prestataire (Adrien) : WhatsApp.
Équipe interne : 3 techniciens + 1 admin.
```

---

## Q6 — Where do meeting recordings, notes, and important docs live?

Granola? Otter? Fireflies? Google Drive? Notion? Dropbox? A folder on your desktop you keep meaning to organize?

```
Pas d'outil de notes dédié. Sur le terrain : application Interfast sur tablette
(iPad) avec un canevas pré-rempli « visite avant-devis pack RR » (photo du tableau
électrique, mètres cubes des pièces, checklist) + une zone de texte libre.
Notes de chantier : vocaux faits dans ChatGPT (sur tablette pendant la visite, ou
au téléphone dans la voiture après) → résumé point par point recollé dans Interfast.
Whisper Flow (Wispr Flow) à installer pour dicter partout sur le PC.
Articles de blog rédigés via le portail client de l'hébergeur du site.
```

---

## Q7 — What's the one task that eats your week, and where do you currently track work?

The single biggest time-suck or recurring drudgery. Plus where tasks/projects live (ClickUp / Asana / Linear / Notion / a notebook).

```
TOP TIME-SUCK : la création de contenu (faite à 100 % à la main, part de la feuille
blanche). Juste derrière : la recherche de pièces détachées pour les dépannages
(appeler les fournisseurs, références obsolètes) — très chronophage mais dur à
automatiser. Les devis prennent du temps aussi (clim ~10 min, PAC ~30 min, grosse
chambre froide 5-6 h).
Suivi du travail : tout vit dans Interfast (interventions, devis, factures,
maintenance). Idées de contenu : aucun système pour l'instant.
```

---

When this file is filled, run `/onboard` (or re-run it) and the wizard will scaffold your Day-1 file set: `context/`, `references/voice.md`, populated `connections.md`, and a filled `CLAUDE.md`.
