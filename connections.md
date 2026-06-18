# Connections

Registry of every system your AIOS can reach. Filled by `/onboard` from Q4-Q7 answers; expanded over time as you wire new tools. `/audit` checks this file for domain coverage and freshness.

| # | Domain | Tool | Mechanism | Auth | Last checked |
|---|---|---|---|---|---|
| 1 | Revenue / Financials | Interfast (CRM, devis, factures, maintenance) | not yet connected | — | — |
| 2 | Customer interactions | Téléphone · Facebook Messenger · formulaire site · plateforme de leads PAC | not yet connected | — | — |
| 3 | Calendar | Google Calendar (déduit du compte Google) | not yet connected | — | — |
| 4 | Communication | Instagram · Facebook · LinkedIn · email pro · WhatsApp (avec Adrien) | not yet connected | — | — |
| 5 | Project / task tracking | Interfast (interventions) | not yet connected | — | — |
| 6 | Meeting intelligence | Vocaux ChatGPT · canevas terrain Interfast (iPad) · Wispr Flow (à installer) | not yet connected | — | — |
| 7 | Knowledge / files | Apify (scrape Instagram/contenu) · Supabase (base de données contenu) · portail blog du site | not yet connected | — | — |

**Mechanism options:** `mcp` (MCP server), `script` (Python/Bash hitting an API, in `scripts/`), `export` (CSV/JSON dump pipeline), `key+ref` (`.env` key + `references/{tool}-api.md` guide), `not yet connected`.

When you wire a new tool, also save `references/{tool}-api.md` capturing endpoints, auth flow, and common queries — researched-once-saved-forever.

> Notes Day-2 (depuis l'appel de mise en place) :
> - **Apify** : compte créé (user `Loïc_Cazal`), token API récupéré → à brancher (scrape Instagram : transcriptions, vues, likes…).
> - **Supabase** : à créer/connecter pour héberger la base de données contenu.
> - **Claude Pro** : abonnement à prendre côté Loïc avant la démo (mercredi 18h).
> - **Wispr Flow** : à installer sur le PC Windows de Loïc pour la dictée partout.
