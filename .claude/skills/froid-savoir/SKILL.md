---
name: froid-savoir
description: Entretient la base de savoir « froid » de Loïc (livres, formations, notices) dans sa base Supabase — ajoute un document (OCR si scan, images de pages, sections, figures, vecteurs), met à jour le zip du skill mobile froid-question, note une leçon dans le carnet, cherche dans le savoir depuis le PC, réveille la base. Skill MOTEUR (PC, Claude Code). Se déclenche sur "ajoute ce document au savoir", "ajoute ce catalogue", "mets à jour le savoir", "ingère ce PDF", "retiens ça", "note cette leçon", "cherche dans mes docs" (sur PC), "la base est en pause", "état du savoir".
---

# Base de savoir froid — ingestion, carnet, recherche (PC)

## Ce que fait cette skill

Loïc dépose un PDF (livre, formation, notice, catalogue) : la skill le range dans sa bibliothèque locale, le
transforme page par page (OCR par OpenAI si c'est un scan, texte direct sinon), le charge dans **sa base
Supabase** (tables `savoir_*`, images de pages dans le bucket privé `savoir-pages`) et régénère l'index du
skill mobile `froid-question`. Elle note aussi ses corrections dans le carnet de leçons, et cherche dans le savoir
depuis le PC. Lire `dimensionnement/CLAUDE.md` d'abord.

Tout vit dans `dimensionnement/bibliotheque/` (local, jamais sur GitHub) : les PDF originaux, `catalogue.json`,
et le cache `_cache/` (pages, OCR payé, sections). **Une page transcrite n'est jamais repayée.**

## Commandes

| Besoin | Commande (depuis la racine du dépôt) |
|---|---|
| Voir le catalogue et l'état de chaque document | `python .claude/skills/froid-savoir/scripts/catalogue.py --lister` |
| Ajouter un document au catalogue | `python …/catalogue.py --ajouter "<dossier>/<fichier>.pdf" --id <slug> --titre "…" --type notice --marque Danfoss [--sommaire 3-12] [--decalage 1] [--priorite 2]` |
| Ingérer un document (pages → OCR si scan → sections → base) | `python …/ingerer.py --doc <slug> [--budget-usd 2]` |
| Ingérer tout ce qui manque, par priorité | `python …/ingerer.py --tout [--priorite-max 3] [--budget-usd 10]` |
| État de la base, dépenses OpenAI estimées | `python …/ingerer.py --etat` · détail Supabase (stockage) : `python shared/scripts/sql/appliquer_sql.py --check` |
| Régénérer l'index mobile puis le zip | `python …/index_mobile.py` puis `python shared/scripts/export_skills.py froid-question` → ré-upload du zip sur claude.ai |
| Noter une leçon | `python …/lecon.py "…" [--dossier <slug du dossier>] [--theme dimensionnement]` |
| Chercher depuis le PC | `python …/rechercher.py "question" [--doc <slug>] [--les-deux]` |
| Rejouer le schéma SQL (nouvelle base, mise à jour) | `python shared/scripts/sql/appliquer_sql.py shared/sql/schema_savoir.sql` |

## Étapes : « ajoute ce document au savoir »

1. **Ranger le fichier** dans `dimensionnement/bibliotheque/<dossier>/` (copier, ne pas déplacer l'original de Loïc).
   Un `.doc`/`.docx` doit d'abord être enregistré en PDF (Word).
2. **L'ajouter au catalogue** avec un `--id` court et stable, un titre lisible, le type et la marque. Le script détecte
   scan / natif et le nombre de pages. Pour un livre scanné avec un sommaire, indiquer ses pages PDF (`--sommaire`)
   et le décalage page imprimée / page PDF (`--decalage`).
3. **Annoncer le coût avant d'ingérer un scan** : environ 0,004 à 0,008 $ par page avec `gpt-5.4-mini` (un natif ne
   coûte rien). Au-delà de 2 $, demander l'accord de Loïc et passer `--budget-usd`.
4. **Ingérer** (`ingerer.py --doc`). Lire le bilan : pages chargées, figures, dollars. Un arrêt « budget » ou
   « plafond OpenAI » est normal : relancer plus tard, la reprise est automatique.
5. **Régénérer l'index mobile et le zip**, puis dire à Loïc de remplacer le zip `froid-question` sur son claude.ai
   (Réglages ▸ Fonctionnalités ▸ Skills). Sans ça, le téléphone ne connaît pas le nouveau document.

## Étapes : « retiens ça » / « note cette leçon »

Reformuler la leçon en une phrase factuelle (ce qui était faux, ce qui est juste, pourquoi), puis `lecon.py`
avec le dossier concerné. Le carnet `dimensionnement/carnet/lecons.md` est relu au début de chaque dossier.

## Étapes : « la base ne répond pas » (plan gratuit : pause après 7 jours sans activité)

`python …/ingerer.py --etat` suffit à la réveiller (première requête lente, jusqu'à une minute). Si l'erreur
persiste, ouvrir le tableau de bord Supabase et cliquer « Restore project ».

## Règles fermes

- **Jamais d'OCR sans annoncer le coût** ; jamais au-delà du budget donné. Le registre local
  `_cache/ocr/_depenses.json` est une estimation : la console OpenAI fait foi.
- **Rien de la bibliothèque sur GitHub** : droits d'auteur. Seuls le code et l'index (titres, sections) sont versionnés.
- Une page dont l'OCR est douteux reste dans la base avec sa confiance ; on ne corrige jamais un chiffre à la main
  dans la base, on note une leçon et on garde l'image de la page comme référence.
- Le markdown est la mémoire des skills ; une réponse pour Loïc cite toujours **document + page imprimée + lien image**.
