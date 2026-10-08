---
name: froid-demande-fournisseur
description: Étape 3 du chiffrage d'un remplacement d'installation frigorifique, après le relevé et le dimensionnement validés — prépare la demande de prix aux fournisseurs, un PDF unique (contexte, tableaux, longueurs de cuivre estimées d'après le plan s'il existe, demande, un chapitre par poste avec les photos des plaques légendées, annexes, plan du local en dernière page) et un mail court, en variante grossiste anonymisée ou fabricant nommé, chaque chiffre repris de l'étape 2 et contrôlé par script, que Loïc relit et envoie lui-même ; se déclenche sur « prépare la demande », « demande de prix », « mail aux grossistes », « pour Advansor », « étape 3 ».
---

# Demande de prix aux fournisseurs — étape 3 du chiffrage (Cazal Réfrigération)

## Ce que fait cette skill

Loïc a validé le relevé (`1-existant.md`, étape 1) et le dimensionnement (`2-dimensionnement.md`, étape 2). Il dit
à qui il écrit (« prépare la demande pour les grossistes », « pour Advansor, demande-lui les options »). La skill
produit, dans `3-demande-fournisseur/<vN>/`, **un PDF unique « Demande de prix »** (page de garde, 1. Contexte,
2. Chambres, 3. Production existante, 4. Évaporateurs, 5. Longueurs de cuivre estimées d'après le plan (si l'étape P
a produit `plan/metre.json`), puis Notre demande, un chapitre par poste avec les photos des plaques légendées à côté,
Annexes, et en dernière page le plan du local (si `plan/plan.pdf` existe)) et **un mail court sans tableau** qui
résume et renvoie au PDF.
**Chaque chiffre vient de `2-resultats.json`**, rendu tel quel ; rien n'est recalculé ni retapé.
**Aucun envoi automatique, jamais** : Loïc relit, corrige, joint le PDF et envoie lui-même depuis sa messagerie.

Lire d'abord `dimensionnement/CLAUDE.md` (règles de fiabilité). Ce manuel prime sur toute habitude.

## À relire à chaque dossier

- `dimensionnement/dossiers/<slug>/dossier.md` (état, décisions, hypothèses, questions), `1-existant.md`,
  `2-dimensionnement.md` (blocs A, E, F), `2-resultats.json`, `2-tableaux.md`, `2-entrees.json`, `sources/structure.json`.
- `dimensionnement/carnet/lecons.md` s'il existe (corrections passées de Loïc).
- `dimensionnement/savoir/methodes/demande-fournisseur.md` (ce qu'un fournisseur attend, structure, variantes,
  a) à f), anonymisation, poids) et `methodes/regles-loic.md` (R4, R5, R7, R8, R9 à R13).
- `3-demande-fournisseur/envois.md` : ce qui est déjà parti, à qui (une version envoyée ne se réécrit jamais).
- `plan/metre.json` et `plan/plan.pdf` s'ils existent (étape P, skill `froid-plan-2d`) : longueurs de cuivre et plan
  du local repris automatiquement (section « Longueurs de cuivre et plan du local » ci-dessous).

## Les 8 étapes

1. **Relire `dossier.md`.** Si l'étape 1 ou l'étape 2 n'est pas *validée* par Loïc, **refuser** : « On valide
   d'abord le relevé et le dimensionnement : un chiffre faux envoyé au fournisseur, c'est le mauvais compresseur
   commandé », et lister ce qui reste à valider. Seule exception : Loïc demande explicitement d'avancer quand même,
   ou demande les trois étapes sans être là (`dimensionnement/CLAUDE.md`, « Loïc absent : tout d'un coup ») ;
   le journal de `dossier.md` l'écrit (« étapes 1-2 non validées ») et on le lui redit à l'étape 8. Puis relire les
   fichiers de la liste ci-dessus.

2. **Loïc dit ce qu'il veut** : la variante (grossistes, ou fabricant de centrale), le destinataire (prénom,
   société, tutoiement ou non), ce qu'il veut en plus ou en moins (« demande-lui les options qu'il recommande »),
   le délai de réponse. Sans précision : variante grossiste, délai « dans les meilleurs délais ». Une seule question
   courte si le destinataire d'une variante fabricant manque.

3. **Assembler `demande.json`** (jamais à la main) :
   ```
   PYTHONUTF8=1 python .claude/skills/froid-demande-fournisseur/scripts/assembler.py dimensionnement/dossiers/<slug> --variante grossiste
   PYTHONUTF8=1 python .claude/skills/froid-demande-fournisseur/scripts/assembler.py dimensionnement/dossiers/<slug> --variante fabricant --destinataire "Prénom, Société" --tutoiement
   ```
   Options : `--delai "d'ici le 20 octobre"`, `--date AAAA-MM-JJ`, `--nommer` (grossiste nommé), `--anonymiser`
   (fabricant anonyme), `--version vN`, `--force` (remplacer une version **jamais envoyée**), `--emetteur <json>`.
   Il écrit `3-demande-fournisseur/vN/` (grossiste) ou `vN-fabricant/` : `demande.json` (textes par défaut des
   gabarits `templates/textes-*.md`, tableaux rendus par `Valeur.texte()`, chapitres par poste, photos classées et
   légendées, longueurs de cuivre de `plan/metre.json` et annexe `plan/plan.pdf` s'ils existent, anonymisation,
   pièces jointes), `identifiants-client.json` (ce qui a été cherché et remplacé) et
   `valeurs-derivees.json` (surfaces L × l et volumes balayés totaux, seuls calculs de l'étape 3, par script).
   Lire chaque « attention » affichée : elles sont aussi recopiées dans `demande.json` (`avertissements`, jamais
   rendues dans le PDF ni le mail) et se relisent à l'étape 4 (ex. modèle entre guillemets lu malgré tout, légendes
   de vues rapprochées par position). Code 1 ou 2 : rien n'est écrit, lire le motif. Code 1 « format inattendu » :
   un chiffre écrit dans `1-existant.md` serait devenu « à confirmer » ou « non relevé » (volume sans `formule` alors
   que le tableau C a les cotes, n° de série que la mise en forme rend illisible, photo d'un compresseur introuvable) :
   corriger la source (format dans le SKILL de l'étape 1 ou 2), relancer l'étape 2 si `2-entrees.json` change, puis
   ce point ; jamais `demande.json` à la main.
   **La demande dépend de la forme des blocs A, E, F** de `2-dimensionnement.md` : A = tableau
   `| Élément | Contenu | Source |` (lignes « Ce qu'on remplace », « Par quoi », « Marché », « Qui dessert quoi ») ;
   E = tableau dont l'en-tête Existant porte la légende des codes (« A = Centrale négative A, … ») et dont les cellules
   s'écrivent « A : … · B : … » ; F = puces dont les mots décident des points a) à f) (Danfoss, AK-SM 800A, AK-CC 55,
   soupape, cordon, détection de fuite, cuivre, K65…) et dont un nombre écrit juste avant « soupapes » ou « portes »
   est repris tel quel. Table complète : SKILL de l'étape 2, étape 5. Un point attendu absent de la demande se corrige
   dans le bloc F, puis on réassemble.

4. **Relire `demande.json` et n'ajuster que les textes dictés** : `contexte.texte`, `demande` (intro, points,
   sous-points, résumé), `postes[].remplacement`, `mail` (objet, corps, formule), selon ce que Loïc a dit à l'étape 2.
   Retirer ce qui n'a rien à faire chez un fournisseur (question interne, « à voir avec… », nom d'un autre chantier).
   Lire **`exclus_internes`** : les propositions du bloc E qu'`assembler.py` a retirées du livrable parce que ce sont
   des questions pour Loïc (« ? », « à confirmer », « à vérifier », « lesquels garder », points de « vigilance ») ; les
   lui poser à l'étape 8 (en construction :
   les consigner), jamais les remettre telles quelles dans le PDF. Le « remplacement » de chaque poste ne garde que les
   propositions du bloc E qui le concernent.
   **Jamais un chiffre** : aucun nombre ajouté, modifié ou arrondi ; les tableaux, les puissances, les longueurs de
   cuivre, les légendes des photos, les identifiants et l'émetteur ne se touchent pas (une longueur fausse se
   corrige dans `plan/plan.json`, étape P, puis on reprend l'étape 3). Un chiffre faux se corrige à l'étape 2
   (`2-entrees.json`, `calculs.py`), puis on reprend à l'étape 3 ci-dessus (`--force` si la version n'est pas envoyée).
   Variante grossiste : ne réintroduire aucun nom, lieu ou référence du client.
   **Le mail affirme ce que Loïc relira** : aucune formulation de doute (« nous supposons », « que nous pensons »,
   « d'après le relevé ») ; les hypothèses restent marquées « (hyp.) » dans le PDF et listées dans `dossier.md` pour
   sa relecture.
   **Ligne « Dessert »** d'un poste : le rattachement chambre ↔ production vient de l'étape 2 ; en hypothèse, il
   porte « (hyp.) » dans le PDF. Si Loïc le conteste : le corriger dans `2-entrees.json` (`postes[].dessert`, texte,
   source « dicté par Loïc le … », statut « sourcé »), relancer `calculs.py` et remettre à jour le bloc A
   (« Qui dessert quoi ») et la vue HTML de l'étape 2, puis réassembler (nouvelle version, ou `--force` si elle n'est
   pas envoyée) ; jamais à la main dans `demande.json`.

5. **Rendre le PDF et le mail** :
   ```
   PYTHONUTF8=1 python .claude/skills/froid-demande-fournisseur/scripts/generer_livrable.py dimensionnement/dossiers/<slug> vN
   ```
   (`vN-fabricant` pour la variante fabricant.) Il écrit `demande-vN.html`, `img/` (photos à 800 px, qualité 80),
   `demande-vN.pdf` (Edge en mode sans tête, Chrome en repli, puis la page 1 de `plan/plan.pdf` ajoutée à la fin
   telle quelle par PyMuPDF), `mail-<variante>.txt` et `mail-<variante>.html`.
   Sans navigateur : `--sans-pdf`, puis impression de la page HTML en PDF à la main (Ctrl+P) ; le plan n'est alors
   pas fusionné (le contrôle 6 échoue) : le joindre à part.

6. **Contrôler** (obligatoire, après chaque génération) :
   ```
   PYTHONUTF8=1 python .claude/skills/froid-demande-fournisseur/scripts/controler.py dimensionnement/dossiers/<slug> vN
   ```
   Sept contrôles : (1) anonymisation (aucun identifiant du client, ni ses variantes de casse, d'accents ou
   d'espaces, dans `demande.json`, la page, le mail ni le texte du PDF, page du plan comprise) ; (2) chaque nombre
   des tableaux et des puissances par poste existe au même rendu dans `2-resultats.json` ou `valeurs-derivees.json` ;
   (3) chaque photo des tableaux B, B2, C de l'étape 1 figure une fois, légendée, et chaque légende de plaque reprend
   les valeurs du relevé pour cette photo (marque, modèle, n° de série, volume balayé ; n° de la plaque d'ensemble) :
   une valeur absente, vide ou remplacée par « non relevé » échoue, comme tout caractère invisible (U+0001…) dans
   `demande.json` ou `1-existant.md` ; (4) PDF lisible, plus d'une page,
   moins de 5 Mo, pas plus ancien que `demande.json`, aucune image manquante ; (5) mail sans tableau, objet non vide,
   chiffres clés présents et retrouvés dans `2-resultats.json`, renvoi au PDF ; (6) pièces jointes et plan
   d'implantation présents ; plan du local en annexe si `plan/plan.pdf` existe : PDF = pages d'Edge + 1, page A4 à
   la taille et au texte de la page 1 du plan, titre listé dans les annexes, plan cité dans le mail ; (7) longueurs
   de cuivre : chiffres du chapitre et de `demande.json` = `plan/metre.json` (chaque ligne et chaque total, à
   0,01 m), phrase d'estimation et ligne des diamètres dans le PDF, « (mesurée) » exactement sur les longueurs
   mesurées ; sans `metre.json`, aucun tableau et la ligne « non relevées » présente.
   **Sortie 1 = on ne montre rien à Loïc.** On corrige la cause (étape 2, textes de `demande.json`, photo), on
   relance les étapes 5 et 6. On ne modifie jamais le contrôle, la page HTML ni le PDF à la main.

7. **Vérificateur** (sous-agent, contexte séparé, lecture seule). Lui donner ce brief, en remplaçant `<slug>` et `<vN>` :
   > Tu es le vérificateur de l'étape 3 du dossier `dimensionnement/dossiers/<slug>/`, version
   > `3-demande-fournisseur/<vN>/`. Tu n'as pas écrit ces fichiers ; tu ne modifies rien. (1) **Ouvre le PDF**
   > `demande-<vN>.pdf` avec PyMuPDF : texte de chaque page, et chaque page rendue en image (`get_pixmap`, PNG dans
   > ton répertoire temporaire) que tu **regardes** : texte coupé, photo coupée, légende manquante, page vide ou
   > presque, doublon. (2) **Tableaux et puissances** : compare chaque ligne des chapitres Chambres, Production et
   > Évaporateurs et la puissance de chaque poste à `2-dimensionnement.md`, `2-tableaux.md` et `2-resultats.json`
   > (même nombre, même unité, même statut « (hyp.) ») ; les espaces insécables (U+00A0) séparent les milliers.
   > (3) **Légendes contre photos** : pour au moins une plaque par poste, et pour toute légende qui te paraît
   > douteuse, ouvre la photo d'origine (`sources/photos/<poste>/pNN-k.jpeg`) **avant** de lire la légende ; note
   > modèle, n° de série, volume balayé ou année et fluide ; compare. (4) **Anonymisation** (variante grossiste) :
   > lis `identifiants-client.json`, puis cherche dans le PDF, le mail et les photos du PDF tout ce qui désigne le
   > client (nom, enseigne visible sur une photo, adresse, localité, téléphone, mail, n° de fiche). (5) **Structure
   > et ton** contre `dimensionnement/savoir/methodes/demande-fournisseur.md` et les gabarits `templates/textes-*.md` :
   > chapitres présents dans l'ordre, demande a) à f) complète (grossiste) ou options, implantation, planning et
   > « phase de prix » (fabricant), vouvoiement ou tutoiement selon la variante. (6) **Mail** : court, aucun tableau,
   > chiffres clés identiques au PDF et à `2-resultats.json`, renvoi au PDF, délai, signature de l'émetteur. Rends
   > une liste : **ACCORD** ou **DÉSACCORD** · élément · ce que tu lis · ce qui est attendu · source ; puis le total.
   Chaque désaccord se corrige à la cause (étapes 4 à 6 à nouveau) ou devient une question pour Loïc (jamais tranché
   en silence). Noter le résultat dans le journal de `dossier.md`.

8. **Ouvrir et faire relire ✋** :
   ```
   PYTHONUTF8=1 python .claude/skills/froid-demande-fournisseur/scripts/controler.py dimensionnement/dossiers/<slug> vN --ouvrir
   ```
   (ouvre le PDF et le mail HTML seulement si aucun contrôle n'échoue). Présenter à Loïc, court : la variante, le
   destinataire, les chiffres clés du mail, le nombre de pages et le poids, ce qui est « à confirmer », puis lui
   demander de relire le PDF et le mail. Il copie l'objet et le texte du mail depuis la page HTML, joint le PDF et
   **envoie lui-même**. Ses corrections : un texte → `demande.json` (étape 4) puis étapes 5 et 6 ; un chiffre →
   étape 2. **Chaque correction** va dans `dimensionnement/carnet/lecons.md` (créer au premier usage : date,
   dossier, ce qui était faux, ce qui est juste, pourquoi). Mettre à jour `dossier.md` : étape
   « 3 · Demande fournisseur — vN à relire ✋ » puis « vN envoyée le … à … », ligne de journal ; et, quand Loïc dit
   qu'il a envoyé, une ligne dans `3-demande-fournisseur/envois.md` (date, version, variante, destinataires, envoyé
   par, remarque).

## Longueurs de cuivre et plan du local (Lot 7, décision d'Adrien du 2026-10-08)

- **Source** : `plan/metre.json`, écrit par `generer.py` du skill `froid-plan-2d` (contrat dans le plan des Lots 5-6,
  § 11). Seuls les réseaux de famille `cuivre_froid` (aspiration, liquide, condensats) et `cuivre_clim` sont repris,
  jamais l'électricité ni les réseaux libres (eau glacée…). Les nombres sont recopiés tels quels (mètres, 2 décimales),
  rendus « 4,21 » sous l'en-tête « Longueur (m) » (pas d'unité dans les cases).
- **Toute longueur est une estimation** d'après le plan (tracé et hauteurs de pose), **sauf celle mesurée sur
  chantier par Loïc** (origine `mesuree`), seule fiable : marquée « (mesurée) » dans sa case. La phrase du métré le
  dit en tête du chapitre.
- **Diamètres et charge de fluide : au fournisseur.** Le chapitre finit par « Diamètres et charge de fluide à définir
  par vos soins. » (les diamètres calculés sont une option future).
- **Place** : chapitre 5 (4 en variante fabricant) « Longueurs de cuivre (estimées d'après le plan) », après les
  tableaux de l'existant et avant
  « Notre demande » (les suivants se renumérotent ; le renvoi « Régulation : voir § N c) » suit). Un tableau par
  réseau : Tronçon · Type · Longueur (m), puis le total.
- **Sans `metre.json`** (ou sans réseau de cuivre) : pas de chapitre ; une ligne « Longueurs de lignes non relevées,
  à estimer par vos soins. » dans « Notre demande », après les points ; rien dans le mail.
- **Plan du local** : si `plan/plan.pdf` existe, sa **page 1** (le plan à l'échelle, A4) est ajoutée en dernière
  page du PDF, sans mise à l'échelle (`annexes.documents`, listée dans les annexes : « à imprimer à 100 % »). Elle ne
  porte pas les numéros de page d'Edge (« Page k / N » ne compte que les pages d'avant). Variante anonymisée : les
  lignes du cartouche qui portent un identifiant du client sont effacées et réécrites (« Le client : plan froid et
  clim ») ; un nom écrit en dessin et non en texte ne serait vu que par le vérificateur.
- **Mail** : une phrase, « Les longueurs de cuivre estimées d'après le plan figurent dans le PDF, avec le plan du
  local en annexe. » (variantes sans plan ou sans métré) ; jamais de tableau ni de longueur dans le mail.
- Un nom de tronçon vient du plan (équipements, pièces) : en variante grossiste il passe par la même anonymisation
  que le reste (un nom d'équipement qui contiendrait le nom du client est masqué).

## Les deux variantes et le versionnement

| | Grossiste (défaut) | Fabricant de centrale |
|---|---|---|
| Destinataire | plusieurs grossistes, non nommés (« Grossistes (consultation) ») | une personne nommée, ex. chez Advansor |
| Ton | vouvoiement, formel | tutoiement (`--tutoiement`) ou vouvoiement, cordial |
| Client | **anonymisé** : ni nom, ni adresse, ni localité, ni téléphone, ni mail, ni n° de fiche | chantier nommé, avec sa référence |
| PDF | chapitres 1 à 7 (8 avec les longueurs de cuivre), demande a) à f) | sans le chapitre des évaporateurs (renumérotation) ; options techniques, implantation, planning |
| Plan du local | page 1 du plan en dernière page, cartouche anonymisé | page 1 du plan en dernière page, telle quelle |
| Mail | résumé, chiffres clés, renvoi au PDF | résumé cordial, options et questions, « phase de prix », renvoi au PDF |
| Dossier | `v1/`, `v2/`… | `v1-fabricant/`, `v2-fabricant/`… |

- Une **nouvelle version** (`v2`, `v2-fabricant`) à chaque régénération après un envoi ; `assembler.py` prend le
  numéro suivant de la variante. `--force` ne remplace qu'une version **qui n'est pas dans `envois.md`**.
- Les fichiers d'une version portent son nom : `demande-v1-fabricant.pdf`, `mail-fabricant.txt`.
- `envois.md` (un par dossier, à côté des versions) est la trace de ce qui est parti : jamais réécrit, on ajoute.

## L'émetteur : `dimensionnement/dossiers/emetteur.json`

Coordonnées de Cazal Réfrigération sur la page de garde et dans la signature : `societe`, `contact`, `telephone`,
`mail`, `adresse` (+ `source`). Fichier **local** (dossier gitignoré), **à compléter par Loïc** (adresse postale,
mail de contact voulu). Un `emetteur.json` dans le dossier d'une installation, ou `--emetteur`, le remplace pour ce
dossier. Champ vide : la ligne disparaît du PDF, rien n'est inventé. L'adresse postale de Cazal est vide tant que
Loïc ne l'a pas donnée : ne jamais la recopier d'un rapport ni d'ailleurs, c'est la question 11 de sa liste
(rappelée à l'étape 8 tant qu'elle manque).

## Règles fermes

- **Aucun envoi automatique, jamais** (ni Outlook, ni API mail) : le système prépare, Loïc envoie.
- **Jamais un chiffre réécrit** : les nombres viennent de `2-resultats.json` (ou de `valeurs-derivees.json`, calculés
  par script) ; « (hyp.) » et « à confirmer » restent visibles ; les évaporateurs sans puissance sourcée disent
  « à confirmer par vos calculs ». La mention « Valeurs indicatives, sélection finale chez le fournisseur » est sur
  chaque page.
- **`controler.py` à 0 échec** avant de montrer quoi que ce soit à Loïc ; vérificateur avant l'étape 8.
- **Variante grossiste anonymisée par défaut** ; nommer le client chez un grossiste se fait seulement si Loïc le dit
  (`--nommer`), et s'écrit dans le journal.
- **PDF sous 5 Mo** ; au-delà, retirer des vues d'ensemble (pas des plaques) et le dire à Loïc.
- Rien du dossier ne sort du PC par le système (pas de commit, pas d'envoi) ; tout ce qui est à Loïc reste local.

## Construction et essais (Adrien)

Pendant la construction et les essais du système, **aucune question n'est posée à Loïc** : chaque question est
consignée dans le fichier privé de questions tenu par la session principale (hors de ce dépôt) et lui est remise à
la livraison ; on avance sur des hypothèses écrites (`regles-loic.md`, gabarits). En usage réel avec Loïc (ou si
la session ne connaît pas ce fichier privé), les questions se posent courtes, dans la conversation, et ses réponses
vont dans `dossier.md` et `regles-loic.md` ; Loïc absent : une seule liste à la fin (`dimensionnement/CLAUDE.md`).

## Limites de la V1 (à dire à Loïc, simplement)

- **Pas de tableaux dans le mail** (décision du 2026-10-07) : tout est dans le PDF. Une page de tableaux à coller
  dans Outlook reste une **option future**, si un fournisseur la réclame.
- **Plan d'implantation « à suivre »** tant que l'étape P n'a pas produit `plan/plan.pdf` ; ensuite « plan du local
  en annexe ». Le métré complet (électricité, croisements, hauteurs) n'est pas joint : seules les longueurs de
  cuivre le sont. La page du plan ajoutée ne porte pas de numéro de page.
- **Puissance des évaporateurs non calculée** : « à confirmer par vos calculs » ; températures de chambre inconnues
  → régime « négatif / positif ».
- **Les photos ne sont pas lues par le contrôle** : un nom visible sur une photo (enseigne, étiquette) n'est vu
  que par le vérificateur et par Loïc. Sans Pillow, les photos ne sont pas redressées selon leur orientation EXIF.
- Pas de traduction (fournisseurs néerlandophones ou anglophones), pas de suivi des réponses ni des devis.

## Fichiers

- `scripts/assembler.py` : dossier (étapes 1 et 2) → `demande.json`, `identifiants-client.json`, `valeurs-derivees.json`.
- `scripts/generer_livrable.py` : `demande.json` → page A4, PDF (Edge sans tête), mail `.txt` et `.html`.
- `scripts/controler.py` : les sept contrôles, rapport en français, sortie 0 / 1, `--ouvrir`.
- `templates/textes-grossiste.md`, `templates/textes-fabricant.md` : textes par défaut (champs `{…}`, conditions) ;
  `templates/demande.html` : gabarit du PDF.
- Dépendances : `valeur.py` et `controles.py` du skill `froid-dimensionnement`, PyMuPDF, Edge ou Chrome déjà installé.
- Tests (racine du dépôt) : `PYTHONUTF8=1 python -m unittest discover -s .claude/skills/froid-demande-fournisseur/scripts/tests -v`
