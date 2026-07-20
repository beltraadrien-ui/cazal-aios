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
| 7 | Knowledge / files | Apify (scrape Instagram/contenu) | key+ref (`.env` → `APIFY_TOKEN`) | API token (placeholder posé) | 2026-06-22 ⏳ clé à remplir |
| 7b | Knowledge / files | OpenAI (Whisper transcription vidéos + embeddings) | key+ref (`.env` → `OPENAI_API_KEY`) | API key (placeholder posé) | 2026-06-22 ⏳ clé à remplir |
| 7c | Knowledge / files | **Supabase** (base contenu — projet `Cazal-1`, ref `ulhdjyhckvamjwmjncwy`, eu-west-1, compte Adrien pour l'instant) | key+ref (`.env` → `SUPABASE_PROJECT_URL` + `SUPABASE_ANON_KEY`) · **connecteur MCP hébergé sur le compte claude.ai d'Adrien** (Desktop/mobile, OAuth — reco : `read_only=true&project_ref=…`) | anon key remplie (`.env`) · OAuth (connecteur) | 2026-07-19 ✅ engine testé en réel (30 contenus, poller quotidien) + connecteur compte Adrien en place |
| 7d | Knowledge / files | portail blog du site | not yet connected | — | — |
| 7e | Knowledge / files | **Meta Graph API** (KPIs riches du compte IG de Cazal : reach, saves, shares, watch time — mode Meta du poller) | `script` (`shared/scripts/post/meta_graph.py`, activé si `.env` → `META_ACCESS_TOKEN`+`IG_USER_ID`) | token longue durée (~60 j, renouvellement manuel — placeholders posés) | 2026-07-20 ⏳ code prêt, setup app Meta + token = jour J bloc C-bis (optionnel) |
| 8 | Surface d'usage (mobile + desktop) | **claude.ai (compte Loïc)** — Skills custom uploadées (zip) | upload manuel (Réglages ▸ Fonctionnalités) | Pro + code execution | 2026-06-19 ✅ pont mobile testé |
| 9 | Distribution / maintenance | **GitHub `cazal-aios` (privé, compte Adrien `beltraadrien-ui`)** — source unique du code, livré chez Loïc par clone + `git pull` | `script` (skill `maj-aios` = `git pull --ff-only`) · `gh`/git | gh CLI (scope `repo`) | 2026-06-24 ✅ repo créé + push |

**Mechanism options:** `mcp` (MCP server), `script` (Python/Bash hitting an API, in `scripts/`), `export` (CSV/JSON dump pipeline), `key+ref` (`.env` key + `references/{tool}-api.md` guide), `not yet connected`.

When you wire a new tool, also save `references/{tool}-api.md` capturing endpoints, auth flow, and common queries — researched-once-saved-forever.

> Notes Day-2 (depuis l'appel de mise en place) :
> - **Apify** : compte créé (user `Loïc_Cazal`), token API récupéré → à brancher (scrape Instagram : transcriptions, vues, likes…).
> - **Supabase** : à créer/connecter pour héberger la base de données contenu.
> - **Claude Pro** : abonnement à prendre côté Loïc avant la démo (mercredi 18h).
> - **Wispr Flow** : à installer sur le PC Windows de Loïc pour la dictée partout.
