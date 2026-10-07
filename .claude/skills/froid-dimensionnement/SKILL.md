---
name: froid-dimensionnement
description: Étape 2 du chiffrage d'un remplacement d'installation frigorifique, après le relevé validé — calcule par script, chiffre par chiffre sourcé, la puissance existante de chaque compresseur (cylindrée et point catalogue croisés), la puissance à demander au fournisseur, la conformité F-gas du fluide et ce qu'on garde ou remplace, puis produit 2-dimensionnement.md et sa vue HTML ; se déclenche sur « dimensionne », « je remplace … par … », « sors-moi les puissances », « étape 2 », « on passe au dimensionnement ».
---

# Dimensionnement du remplacement — étape 2 du chiffrage (Cazal Réfrigération)

## Ce que fait cette skill

Loïc a validé le relevé de l'existant (`1-existant.md`, étape 1). Il dit ce qu'il remplace par quoi
(« je remplace les deux centrales par une centrale CO2 booster »). La skill remplit `2-entrees.json` avec
les données du relevé, lance `calculs.py`, et livre **`2-dimensionnement.md`** (sept blocs, A à G) et sa
**vue HTML** : la puissance frigorifique existante par compresseur et par poste, la puissance à demander,
le fluide actuel et cible face au règlement F-gas, ce qu'on garde ou remplace, les fournitures annexes, les
hypothèses et les questions. Loïc valide ✋, puis vient l'étape 3 (`froid-demande-fournisseur`).
**La sélection du matériel neuf reste chez le fournisseur** : tout est indicatif.

Lire d'abord `dimensionnement/CLAUDE.md` (règles de fiabilité, vocabulaire). Ce manuel prime sur toute habitude.
Si `1-existant.md` n'existe pas encore (« sors-moi les puissances » sur un rapport neuf), c'est l'étape 1 :
`froid-releve-existant`.

## À relire à chaque dossier

- `dimensionnement/dossiers/<slug>/dossier.md` (état, décisions, hypothèses, questions) et `1-existant.md`.
- `dimensionnement/carnet/lecons.md` s'il existe (corrections passées de Loïc).
- `dimensionnement/savoir/methodes/regles-loic.md` (régimes, marges, préférences, réponses aux six questions),
  `methodes/puissance-existante.md` (M1, M2, statuts), `methodes/transitions.md` (bloc E).

## Les 8 étapes

1. **Relire `dossier.md` et `1-existant.md`.** Si l'étape 1 n'est pas *validée* par Loïc dans `dossier.md`,
   **refuser** : « On valide d'abord le relevé de l'existant », et lister ses points « à confirmer ». Seule
   exception : Loïc demande explicitement d'avancer quand même ; le bloc A l'écrit alors (« relevé non validé »).

2. **Loïc dicte le projet** : ce qu'il remplace par quoi, le fluide cible, ce qu'il garde, les fournitures
   annexes. Questions courtes s'il manque une de ces quatre choses. S'il répond à l'une des six questions
   (régime et condition, marge, seuil d'écart, ratio par m³, CV / HP, proposer ou vérifier le fluide), sa
   réponse entre dans `2-entrees.json` avec la source `dicté par Loïc le AAAA-MM-JJ`, dans `dossier.md`
   (Décisions), et est signalée à Adrien pour `regles-loic.md` (le socle est maintenu par Adrien).

3. **Remplir `<dossier>/2-entrees.json`** (format ci-dessous, détail dans le docstring de `calculs.py`).
   **Jamais un nombre inventé** : chaque `Valeur` cite sa source, sous l'une de ces formes :
   `photo p11-3` · `rapport p. 10` · `dicté par Loïc le 2026-10-06` · `hypothèse : …` ·
   `savoir/methodes/regles-loic.md R1` · `web : <lien>` ; une donnée absente est une `Valeur` « à confirmer »
   (nombre `null`) dont la source dit pourquoi (« non écrite dans le rapport »). Depuis `1-existant.md` :
   tableau B → `compresseurs` (volume balayé, photo, lecture), B2 → `plaques_ensemble`, C → postes (volume,
   dessert, évaporateurs), rapport → charges. Les lectures : **douteuse** → volume balayé en statut
   « hypothèse » avec « lecture douteuse : … » dans la source ; **illisible** → volume « à confirmer ».
   Paramètres : ne rien écrire garde les défauts du script (écrits comme hypothèses) ; une réponse de Loïc
   remplace le défaut. Puis contrôler :
   ```
   PYTHONUTF8=1 python .claude/skills/froid-dimensionnement/scripts/calculs.py dimensionnement/dossiers/<slug> --verifier
   ```
   Corriger chaque ERREUR ; lire chaque ATTENTION (une source non reconnue se reformule).

4. **Lancer le calcul** (jamais de calcul de tête) :
   ```
   PYTHONUTF8=1 python .claude/skills/froid-dimensionnement/scripts/calculs.py dimensionnement/dossiers/<slug>
   ```
   Il écrit `2-resultats.json` (tout, avec formules et sources) et `2-tableaux.md` (tableaux B, C, D et une
   aide au bloc G). Hors plage ou donnée absente → « à confirmer », jamais un faux nombre. Code 1 : rien
   n'est écrit, corriger les entrées. On ne modifie **jamais** `2-tableaux.md` à la main : on corrige
   l'entrée et on relance.

5. **Assembler `<dossier>/2-dimensionnement.md`**, qui commence par ces deux lignes :
   ```
   <!-- titre: Dimensionnement du remplacement — <CLIENT> -->
   <!-- mention: Valeurs indicatives, sélection finale chez le fournisseur. -->
   ```
   puis un titre `# …`, un encadré d'état (« à valider par Loïc ✋ », niveau de précision), et les blocs :
   - **A. Projet** : ce qui est remplacé par quoi, fluide actuel et cible, ce qu'on garde, régimes, niveau
     de précision, état du relevé ; chaque ligne sourcée.
   - **B. Puissance existante par compresseur**, **C. Besoins par poste**, **D. Fluide et conformité** :
     tableaux **recopiés tels quels** depuis `2-tableaux.md`, avec leurs notes. Le bloc D ne contient **que**
     le texte produit par le script : aucune phrase réglementaire ajoutée à la main.
   - **E. Ce qu'on garde, ce qu'on remplace** : par poste (compresseurs, condenseurs, évaporateurs,
     détendeurs, régulation, tuyauterie, récupération de chaleur), avec la raison prise dans
     `methodes/transitions.md` et ce que Loïc a dicté ; points de vigilance.
   - **F. Fournitures annexes** : ce que Loïc liste pour le fournisseur (régulation, supervision, cordons
     chauffants, soupapes, récupération de chaleur, cuivre…), sourcé (`regles-loic.md`, dictée).
   - **G. Hypothèses et questions** : **G1** la comparaison **chiffrée et expliquée** aux contrôles du
     tableau C (estimations antérieures, plaques d'ensemble, ratio de Loïc), avec le tableau
     « G-estimations » de `2-tableaux.md` recopié tel quel s'il existe ; **G2** les hypothèses datées et
     sourcées, avec le tableau « G-variantes » (fluide supposé : mêmes calculs F-gas au fluide d'origine
     qu'indique une plaque) recopié tel quel s'il existe ; **G3** les questions pour Loïc ; **G4** les
     alertes (écart M1 / M2 au-delà du seuil) et ce qui reste à faire. Partir de l'« aide au bloc G » de
     `2-tableaux.md`, sans en oublier une ligne.
   - **G3 = trois listes, chaque ligne une question explicite** : (a) **toutes** les lignes « À confirmer »
     du § E de `1-existant.md` (étape 1), (b) **toutes** les hypothèses de `dossier.md`, (c) les nouvelles
     questions de l'étape 2 (régime et condition, marge, seuil, ratio, proposer ou vérifier le fluide, unité
     des dimensions, écarts de lecture, etc.). **Jamais un renvoi en bloc** (« voir § E ») : chaque point est
     reformulé en question courte.
   Dans la prose, **un nombre n'apparaît que s'il est dans `2-resultats.json`, dans `2-tableaux.md` ou dans
   une source citée** (avec sa référence) ; une explication qui demanderait un nouveau calcul se fait par
   script ou se formule sans chiffre. **Une ligne vide avant chaque liste** (puces ou numéros) : sans elle,
   la vue HTML colle la liste au paragraphe qui la précède. Une citation entre guillemets est **mot pour mot**
   (transcription, rapport) ; une lecture de plaque ou un résumé s'écrit sans guillemets.

6. **Vérificateur** (sous-agent, contexte séparé, lecture seule). Lui donner ce brief, en remplaçant `<slug>` :
   > Tu es le vérificateur de l'étape 2 du dossier `dimensionnement/dossiers/<slug>/`. Tu n'as pas écrit ces
   > fichiers ; tu ne modifies rien. (1) **Relis les plaques à l'aveugle** : pour chaque compresseur et chaque
   > plaque d'ensemble de `2-entrees.json`, ouvre la photo citée dans la source (`sources/photos/<poste>/pNN-k.jpeg`)
   > **avant** de regarder la valeur saisie ; note modèle, volume balayé, fréquence, puissance, fluide ; puis
   > compare à `2-entrees.json` (nombre, statut, lecture). Vérifie aussi les charges et volumes dans
   > `sources/rapport-texte.md` à la page citée. (2) **Recalcule deux lignes du tableau B** à partir des états
   > de `2-resultats.json` : M1 = volume balayé ÷ 3 600 × λ × ρ1 × Δh ; M2 = puissance du point catalogue (ligne
   > du CSV citée) × facteur ; puis l'écart (M1 − M2) ÷ M2 et une somme du tableau C (calculatrice Python
   > autorisée, `python -c`). (3) **Compare aux estimations antérieures et aux plaques d'ensemble** : l'écart
   > du tableau C et l'explication du bloc G tiennent-ils ? (4) Vérifie que les tableaux B, C, D de
   > `2-dimensionnement.md` sont identiques à `2-tableaux.md`, que chaque nombre de la prose se retrouve dans
   > `2-resultats.json`, `2-tableaux.md` ou la source citée, et que chaque ligne « À confirmer » de l'aide au
   > bloc G figure en bloc G. Les nombres utilisent des espaces insécables (U+00A0) comme séparateur de
   > milliers. Rends une liste : **ACCORD** ou **DÉSACCORD** · élément · ce que tu lis · ce qui est saisi ·
   > source ; puis le total.
   Chaque désaccord devient une question à Loïc en bloc G (jamais tranché en silence) ; un désaccord sur
   une saisie se corrige dans `2-entrees.json`, puis étapes 4 et 5 à nouveau. Noter le résultat dans le journal.

7. **Vue HTML, puis validation** (le markdown est la mémoire de Claude, pas un document pour Loïc) :
   ```
   PYTHONUTF8=1 python shared/rendu_html.py dimensionnement/dossiers/<slug>/2-dimensionnement.md --ouvrir
   ```
   (la mention et le titre viennent des deux commentaires de tête ; régénérer après chaque modification ;
   `dossier.html` aussi quand `dossier.md` change). Présenter à Loïc, court : la puissance par poste (existante
   et demandée), le fluide, ce qui change, puis les questions du bloc G, en renvoyant à la page. Demander ✋.

8. **Après ses réponses** : chaque correction entre dans `2-entrees.json` (source `dicté par Loïc le …`),
   puis étapes 4 à 7 à nouveau ; chaque correction d'un chiffre ou d'une lecture va dans
   `dimensionnement/carnet/lecons.md` (créer au premier usage : date, dossier, ce qui était faux, ce qui
   est juste, pourquoi). Mettre `dossier.md` à jour : étape « 2 · Dimensionnement — *validée* », décisions
   (ce qui est remplacé par quoi, avec la date), hypothèses, questions restantes, ligne de journal. Dire :
   « on peut passer à la demande fournisseur ».

## Format de `2-entrees.json` (en bref)

- Trois briques : **Valeur** `{id, nombre, unite, source, statut}` (nombre `null` ⇔ « à confirmer ») ;
  **choix** `{valeur, source, statut, id}` (fluide, convention…) ; **texte sourcé** `{texte, source, statut}`.
- `parametres` (facultatif) : `convention`, `gaz_aspire` / `surchauffe`, `sous_refroidissement`, `seuil_ecart`,
  `seuil_t0`, `seuil_tc`, `lambda_methode`, `fluide_base`, `marge_pct` (défaut 0 %, hypothèse), `ratio_kw_m3`.
- `projet` : `texte`, `fluide_actuel`, `fluide_cible`, `type_equipement` `{id du poste: "centrale" | "groupe
  de condensation" | …}`, `type_equipement_cible`, `precision`, `date_analyse` (AAAA-MM-JJ, règles F-gas).
- `postes[]` : `id`, `nom`, `dessert`, `fluide` (facultatif), `temperature_chambre`, `volume`, `regime {t0, tc}`,
  `charge`, `compresseurs[] {id, marque, modele, volume_balaye, lecture, note, frequence, estimation}`
  (`estimation` : chiffre antérieur pour ce compresseur, facultatif, décomposé au tableau « G-estimations »),
  `evaporateurs[] {id, modele, annee, fluide_origine, source}`, `plaques_ensemble[] {id, texte, puissance,
  fluide, regime}`, `estimations[] {id, texte, puissance}` (chiffres antérieurs à comparer).
- **id uniques dans tout le fichier** (ils apparaissent dans les formules) ; convention : poste `a`, compresseur
  `a-c1`, volume balayé `a-c1-vb`, régime `a-t0` / `a-tc`, charge `a-charge`.
- Champ facultatif **`photo`** sur `compresseurs[]`, `evaporateurs[]` et `plaques_ensemble[]` : liste des photos de la
  plaque, chemins relatifs au dossier (ex. `["sources/photos/07-centrale-negative-a/p11-3.jpeg"]`, d'après la colonne
  Photo de `1-existant.md`). Aucun calcul ne s'en sert : `calculs.py` le recopie tel quel dans `2-resultats.json`
  pour l'étape 3 (`froid-demande-fournisseur`, photo à côté de sa légende). À remplir dès que la photo est connue.

## Règles de fiabilité (en plus de `dimensionnement/CLAUDE.md`)

- **Les nombres des tableaux viennent du script**, recopiés tels quels ; aucun chiffre de tête, aucune
  retouche. Une valeur fausse se corrige à la source (`2-entrees.json`), jamais dans le tableau.
- **Statuts** : *sourcé* > *calculé* > *hypothèse* > *à confirmer*. Un résultat n'est jamais plus sûr que sa
  plus faible entrée ; M1 est toujours au mieux « hypothèse » (λ) ; un compresseur « à confirmer » rend son
  poste « à confirmer » (la somme des compresseurs lus est donnée à part, en remarque).
- **Lecture douteuse** : si le nombre utilisé (volume balayé) est lisible et que seul un autre champ est douteux
  (ex. un chiffre du modèle effacé), la valeur est une « hypothèse » avec le doute écrit dans la source ; si le
  nombre lui-même est illisible, « à confirmer » (`methodes/puissance-existante.md` § 7).
- **Fluide supposé** (choix en « hypothèse ») : le script plafonne aussi tous les résultats F-gas qui en
  dépendent (PRP du poste, tCO2e, contrôle d'étanchéité, interdictions : « (hyp.) » au tableau D) et calcule
  une variante pour chaque autre fluide qu'indique une plaque du poste (tableau « G-variantes »).
- **Aucun raisonnement réglementaire hors du texte rendu par `fgas.py`** (tableaux D et G-variantes), dans
  aucun bloc : pas de conclusion rédigée à la main sur une interdiction, un seuil de capacité ou une
  exception. Une question réglementaire non couverte par la table devient une question pour Adrien.
- **Une plaque d'ensemble sans régime** se compare à titre indicatif seulement ; une puissance en **CV ou HP
  n'est jamais une puissance frigorifique** (refus du script, question 5 à Loïc).
- **Fluide** : celui qui est **dans** l'installation, pas la liste de la plaque ; un doute (plaque d'origine
  à un autre fluide) se saisit en « hypothèse » et devient une question.
- **Table F-gas non relue** tant que la colonne `relu_par` est vide : le bloc D le dit, toujours.
- Rien du dossier ne sort du PC (pas de commit, pas d'envoi). Aucun envoi au fournisseur à cette étape.

## Vocabulaire

- **Poste** : un ensemble de production (une centrale, ou les groupes d'une chambre) ; **centrale** :
  compresseurs en parallèle ; **groupe (unité) de condensation** : un compresseur et son condenseur.
- **Régime** : T0 (évaporation) / Tc (condensation), au **point de rosée** pour un mélange (convention
  Bitzer, hypothèse tant que Loïc n'a pas dit autre chose) ; **gaz aspiré** : température du gaz à l'entrée
  du compresseur (20 °C dans les catalogues).
- **M1** : puissance par la cylindrée (volume balayé de la plaque × λ × ρ1 × Δh) ; **M2** : puissance publiée
  par le fabricant, ramenée au fluide et au régime ; **retenue** : M2 si elle existe, sinon M1.
- **Puissance existante** : somme des retenues d'un poste ; **puissance demandée** : existante × (1 + marge).

## Limites de la V1 (à dire à Loïc, simplement)

- **M2 passe par le R404A** : aucun point R449A n'est publié pour ces compresseurs ; le point R404A est
  converti au R449A par calcul (hypothèse écrite). Au point de rosée ou en température moyenne, l'écart peut
  atteindre 10 à 15 % : c'est sa question 1.
- **Pas de contrôle par le volume** des chambres (pas d'abaque) ni de bilan thermique : le contrôle repose sur
  l'écart M1 / M2, les plaques d'ensemble, ses estimations passées et son ratio s'il en donne un.
- **Table F-gas non relue** par Adrien tant que c'est le cas : à vérifier avant de s'en servir devant un client.
- **Six questions en attente** (régime et condition, marge, seuil d'écart, ratio par m³, CV / HP, proposer
  ou vérifier le fluide) : tant qu'elles manquent, les hypothèses par défaut s'appliquent et sont écrites.
- λ (rendement volumétrique) vient des catalogues Bitzer (table A, à valider par Adrien) : pour ces modèles,
  M1 n'est donc pas totalement indépendante de M2. Les évaporateurs n'ont pas de puissance calculée.

## Fichiers

- `scripts/calculs.py` : point d'entrée (`2-entrees.json` → `2-resultats.json` + `2-tableaux.md`, `--verifier`).
- `scripts/compresseurs.py` (M1, M2, valeur retenue), `scripts/fluides.py` (CoolProp 8.0.0, seul import),
  `scripts/fgas.py` (PRP, tCO2e, règles), `scripts/controles.py` (écart, somme, marge), `scripts/valeur.py`
  (Valeur, statuts, rendu), `scripts/unites.py` (conversions ; `python …/unites.py 30000 fg/h kW`).
- `shared/rendu_html.py` : vue HTML commune aux étapes. Socle : `dimensionnement/savoir/INDEX.md`.
- Tests (racine du dépôt) : `PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-dimensionnement/scripts/tests -v`
