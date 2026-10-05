---
name: froid-question
description: Répond à une question technique de froid, climatisation, CO2 ou régulation en cherchant dans la base de savoir de Loïc (livres, formations Advansor, notices Danfoss, guides CO2) et en citant le document, la page et l'image de la page. Se déclenche sur "question froid", "cherche dans mes docs", "retrouve le schéma de", "qu'est-ce que dit le Kotza sur", "symptômes de", "comment câbler", "comment régler", "où est-ce que je trouve", "dans la notice Danfoss", "dans la formation Advansor".
---

# Question à la base de savoir — Cazal Réfrigération

## Ce que fait cette skill

Loïc pose une question, souvent depuis son téléphone sur chantier. La skill cherche la réponse **dans ses propres
documents** et répond **avec la source** : document, page imprimée, et l'image de la page pour voir le schéma
ou le tableau. Elle n'invente rien : ce qui n'est pas dans les documents est dit « pas trouvé ».

## Fichiers bundlés

- `references/INDEX.md` : la liste des documents (avec leur `id`) et leurs sections avec les pages. À lire d'abord :
  il dit dans quel document chercher, donne souvent la bonne page, et sert de secours si la base ne répond pas.

## Étapes

1. **Lire `references/INDEX.md`** et repérer le ou les documents concernés (une notice Danfoss pour un réglage de
   régulateur, le Kotza pour un dépannage, Advansor ou les guides CO2 pour une centrale CO2…).

2. **Interroger la base** avec le connecteur Supabase (outil `execute_sql`), en lecture seule :
   ```sql
   select document_id, titre_document, page_imprimee, titre_section, extrait, mode, figures, image_url, renvois
   from rechercher_savoir('<mots-clés de la question>', 5);
   ```
   - Mots-clés en français, 2 à 6 mots importants (ex. `détendeur trop petit symptômes`, `dégivrage AK-CC 55 réglage`,
     `V4V hiver refoulement`). Accents et terminaisons sont ignorés. Pour un document en anglais (EN dans l'INDEX),
     mettre aussi les mots-clés en anglais.
   - Limiter à un document : troisième argument avec son `id` de l'INDEX, ex. `rechercher_savoir('…', 5, 'kotza')`.
   - `mode` dit si tous les mots ont été trouvés ou seulement certains : au second cas, reformuler (2 essais max).
   - Pour lire une page citée en renvoi ou une page voisine :
     `select page_imprimee, titre_section, left(texte, 2000) as texte, image_url from savoir_pages where document_id = 'kotza' and page_imprimee = 389;`

3. **Répondre**, en français simple, tutoiement, dans cet ordre :
   1. La réponse en 3 à 8 lignes, tirée **uniquement** des extraits trouvés (lire le texte complet de la page si l'extrait ne suffit pas).
   2. La source : « D'après le Kotza, p. 879, section Pannes frigorifiques des refroidisseurs de liquide ». Toujours la page **imprimée**.
   3. S'il y a une figure utile : sa description courte (colonne `figures`), puis le lien de l'image de la page sous la forme `[Voir la page 879](url)`.
   4. **Essayer d'afficher l'image** : avec l'exécution de code, télécharger `image_url` et l'enregistrer en fichier de sortie
      (`page-879.jpg`) pour qu'elle apparaisse dans la conversation. Si le téléchargement échoue parce que le domaine n'est
      pas autorisé, le dire en une ligne : « pour voir la page ici, autorise le domaine `<ref>.supabase.co`
      dans Réglages ▸ Capacités ▸ accès réseau », et garder le lien.
   5. **Ne jamais redessiner un schéma** à partir du texte (ni dessin, ni diagramme, ni SVG) : sur chantier, seule la vraie
      page fait foi. Décrire la figure en 2 lignes et donner le lien, c'est tout.
   6. Les renvois : « Voir aussi p. 105 à 121 du Kotza ».

4. **Si le connecteur Supabase ne répond pas** (absent, erreur, base en pause) : le dire clairement en une phrase, répondre
   avec `references/INDEX.md` seulement (« le sujet est traité p. 166 à 173 du Kotza »), et conseiller « demande à ton PC :
   état du savoir » pour réveiller la base.

## Règles fermes

- **Ne jamais inventer.** Une valeur, un câblage, un réglage qui ne sont pas dans les extraits → « je ne l'ai pas trouvé
  dans tes documents, à confirmer dans la notice ».
- **Toujours citer le document et la page.** Sans source, pas de réponse.
- Les extraits des scans viennent d'un OCR : un chiffre bizarre → le signaler plutôt que le corriger soi-même.
- Réponses courtes, vocabulaire de Loïc, pas de jargon ajouté. Loïc reste le seul juge sur l'installation.
- Ne rien écrire dans la base (lecture seule).
