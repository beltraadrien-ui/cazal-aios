---
name: froid-releve-existant
description: Étape 1 du chiffrage d'un remplacement d'installation frigorifique — ouvre un dossier d'installation à partir du rapport de visite InterFast (PDF), extrait le texte et les photos, lit les plaques signalétiques et produit le tableau de l'existant, chaque valeur sourcée, avec la liste de ce qui reste à confirmer. Skill MOTEUR (PC, Claude Code). Se déclenche sur "nouveau dossier", "voici le rapport de visite", "relevé de l'existant", "sors-moi les puissances existantes", "ouvre un dossier pour", "on reprend le dossier", "remodeling", "remplacement de centrale".
---

# Relevé de l'existant — étape 1 du chiffrage (Cazal Réfrigération)

## Ce que fait cette skill

Loïc glisse (ou nomme) le **PDF du rapport InterFast** d'une visite de remplacement. La skill crée le
dossier de l'installation, en sort le texte et les photos, **lit les plaques signalétiques** et remplit
`1-existant.md` : les postes, les compresseurs, les chambres froides, la régulation, **avec la source de
chaque valeur**, et la liste « à confirmer ». Loïc valide ✋, puis vient l'étape 2 (`froid-dimensionnement`).

Lire d'abord `dimensionnement/CLAUDE.md` (règles de fiabilité). Ce manuel prime sur toute habitude.

## Étapes

1. **Trouver le PDF.** Chemin donné par Loïc, ou fichier glissé dans la conversation (le copier dans
   `active/` s'il n'est pas sur le disque). Un rapport InterFast = « rapport complet » d'une fiche de visite.
   Si Loïc dit « on reprend le dossier X » : ouvrir `dimensionnement/dossiers/<X>/dossier.md` et sauter à l'étape 4.

2. **Créer le dossier par le script** (jamais à la main) :
   ```
   python .claude/skills/froid-releve-existant/scripts/extraire_rapport.py "<chemin du PDF>"
   ```
   Il crée `dimensionnement/dossiers/AAAA-MM-JJ-client/` avec `dossier.md`, `1-existant.md` (squelette),
   `sources/` (PDF, texte page par page, `structure.json`, `photos/<poste>/`). Lire ce qu'il affiche :
   sous-points, nombres lus, photos par poste. Si le dossier existe déjà, il refuse : demander à Loïc
   avant d'utiliser `--force`.

3. **Lire les photos, poste par poste** (outil Read sur chaque fichier de `sources/photos/`), avec
   `dimensionnement/savoir/materiel/lecture-plaques.md` sous les yeux. Pour chaque plaque :
   marque, modèle complet, numéro de série, fluides listés, tension, volume balayé si écrit. Qualifier
   chaque lecture : `sûre`, `douteuse (lecture probable + doute)`, `illisible`. Les photos qui ne sont
   pas des plaques (vue d'ensemble, évaporateur, armoire) sont décrites en une ligne dans le tableau D.

4. **Compléter `1-existant.md`** : tableau B (une ligne par compresseur ou unité de condensation,
   colonne Photo = nom du fichier, colonne Source = `photo pNN-k`), tableau C (température, usage,
   « desservi par » si le rapport ou les photos le disent, sinon « à confirmer »), tableau D, et la
   liste E « À confirmer » complétée de tout ce qui est douteux ou illisible. **Ne jamais remplir une
   case avec une supposition** : ce que le rapport ne dit pas et que la photo ne montre pas reste « à confirmer ».

5. **Puissances existantes, si Loïc les demande** (« sors-moi d'abord les puissances existantes ») :
   pour chaque modèle lu `sûr`, chercher la fiche constructeur (catalogue dans `dimensionnement/savoir/`
   s'il existe, sinon WebSearch / WebFetch) et noter dans tableau B le **volume balayé (m³/h à 50 Hz)** et,
   s'il est publié, la puissance frigorifique **au régime indiqué par la source** (ex. −10 / +45 °C, R449A),
   avec le lien. Marquer « indicatif ». Aucune conversion ni somme ici : les calculs sont à l'étape 2, par script.

6. **Double lecture (vérificateur).** Lancer un sous-agent avec, pour seule entrée, la liste des photos
   et le tableau B, et pour consigne de **relire chaque plaque et signaler tout désaccord**. Chaque
   désaccord devient une ligne « à confirmer » (jamais tranché en silence).

7. **Générer la vue lisible et l'ouvrir** (le markdown est la mémoire de Claude, pas un document pour un humain) :
   ```
   python .claude/skills/froid-releve-existant/scripts/rendu_html.py dimensionnement/dossiers/<slug> --ouvrir
   ```
   Elle produit `1-existant.html` (et `dossier.md` → `dossier.html`) avec la photo de chaque plaque à côté de sa
   lecture, et l'ouvre dans le navigateur. **À régénérer après chaque modification du markdown.**
   Puis **présenter à Loïc** dans la conversation, court : le tableau A en deux phrases, les points marquants
   du tableau B, puis la liste « À confirmer » sous forme de questions courtes, en renvoyant à la page HTML
   pour le détail. Demander la validation ✋. Pas de dimensionnement ici.

8. **Après ses réponses** : reporter les réponses dans `1-existant.md` avec la source `dicté par Loïc
   (AAAA-MM-JJ)`, noter chaque correction d'une lecture dans `dimensionnement/carnet/lecons.md` (créer le
   fichier au premier usage : date, dossier, ce qui était faux, ce qui est juste, pourquoi), mettre
   `dossier.md` à jour (étape 1 : *validée*, journal) et dire : « on peut passer au dimensionnement ».

## Règles fermes

- **Une source par valeur, ou « à confirmer ».** Jamais de valeur de mémoire, jamais de modèle complété.
- **Les photos InterFast sont petites** (450 × 600). Une plaque illisible = demander à Loïc la photo
  d'origine (InterFast ou son téléphone), à déposer dans `sources/photos-hd/`.
- **Pas de calcul dans cette étape** (sommes, conversions, puissances par le volume) : c'est l'étape 2.
- Le rapport est la vérité pour les commentaires de Loïc ; la photo est la vérité pour les plaques ;
  en cas de contradiction, poser la question.
- Réponses courtes, vocabulaire de Loïc (poste, centrale, groupe, négatif / positif). Pas de jargon ajouté.
- Rien de ce dossier ne sort du PC (pas de commit, pas d'envoi).

## Fichiers

- `scripts/extraire_rapport.py` : PDF → dossier (texte, photos, structure, squelettes). Dépendance : PyMuPDF.
- `scripts/rendu_html.py` : markdown du dossier → pages HTML lisibles avec vignettes des photos. Dépendance : markdown.
- `dimensionnement/savoir/methodes/checklist-releve.md` : les 16 points d'un relevé complet (numéros de la liste E).
- `dimensionnement/savoir/materiel/lecture-plaques.md` : comment lire une plaque, pièges, repères par marque.
