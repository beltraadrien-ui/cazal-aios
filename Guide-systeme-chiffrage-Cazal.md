# Système de chiffrage et de plans, Cazal Réfrigération

Guide d'utilisation, octobre 2026. Préparé par Adrien Beltra, BeltraTech.

## En deux mots

Ce système prépare le chiffrage du remplacement d'une installation frigorifique, du rapport de visite InterFast
jusqu'à la demande de prix au fournisseur. Il dessine le plan du local à l'échelle, avec le métré des lignes. Il
répond aux questions techniques à partir des livres et notices de Cazal, et met en forme les résumés de visite.

* **Sur le PC** : le chiffrage, les plans, la base de savoir, la mise à jour.
* **Sur le téléphone** (ou l'application Claude sur ordinateur) : les questions techniques et les résumés vocaux.

Le système de contenu remis en juin ne change pas. Avant la première utilisation, Adrien installe en visio ce qu'il
faut sur le PC (draw.io, outils de calcul, accès à la base de savoir).

## Les principes qui ne changent jamais

* **Rien n'est inventé.** Chaque chiffre a sa source. Ce qui manque devient une question ; ce qui est supposé est
  marqué « (hyp.) ».
* **On valide à chaque étape.** L'assistant montre son travail et attend le feu vert.
* **Rien n'est envoyé automatiquement.** L'assistant prépare ; on relit et on envoie depuis sa messagerie.
* **Toute longueur de ligne est une estimation** d'après le plan, sauf celle mesurée sur chantier, marquée
  « (mesurée) ».
* **Diamètres et charge de fluide : au fournisseur.** Le système ne les calcule pas.
* **La mémoire d'un dossier est dans son dossier.** Avec « on reprend le dossier [nom] », l'assistant repart de là,
  même dans une nouvelle conversation.

## Les outils

### Le relevé de l'existant

> Étape 1 · `froid-releve-existant` · sur le PC

**À quoi ça sert.** Tirer du rapport de visite le tableau de l'installation en place, plaque par plaque.

**Ce qu'on lui donne.** Le PDF du rapport InterFast, glissé dans la conversation ou désigné par son emplacement
sur le PC.

**Ce qu'on en sort.** Le dossier de l'installation, et une page dans le navigateur : chaque plaque lue à côté de sa
photo, la source de chaque valeur, les questions.

**On le déclenche en disant.** « nouveau dossier, voici le rapport de visite », « relevé de l'existant », « on
reprend le dossier [nom] ».

**À savoir.**

* Chaque plaque est relue une seconde fois, à l'aveugle ; un désaccord devient une question.
* Plaque illisible : l'assistant demande la photo d'origine.

### Le dimensionnement

> Étape 2 · `froid-dimensionnement` · sur le PC

**À quoi ça sert.** Calculer la puissance existante et la puissance à demander pour le remplacement.

**Ce qu'on lui donne.** Le projet : ce qu'on remplace par quoi, le fluide visé, ce qu'on garde, les fournitures
annexes.

**Ce qu'on en sort.** Une page avec la puissance de chaque compresseur, calculée de deux façons qui se contrôlent,
la puissance par poste et la puissance demandée, le fluide face au règlement européen sur les gaz fluorés, ce qu'on
garde ou remplace, les hypothèses et les questions.

**On le déclenche en disant.** « on passe au dimensionnement », « dimensionne », « je remplace … par … ».

**À savoir.**

* Les calculs se font par programme, jamais de tête : un chiffre faux se corrige à la source, puis tout est
  recalculé.
* Valeurs indicatives : le choix du matériel reste au fournisseur, et la table réglementaire doit encore être relue
  par Adrien avant de servir devant un client.

### La demande fournisseur

> Étape 3 · `froid-demande-fournisseur` · sur le PC

**À quoi ça sert.** Préparer la demande de prix aux grossistes ou à un fabricant de centrale.

**Ce qu'on lui donne.** Le destinataire (les grossistes par défaut, ou un fabricant nommé, en tutoiement ou en
vouvoiement) et le délai de réponse.

**Ce qu'on en sort.** Un PDF unique de moins de 5 Mo (tableaux de l'existant, longueurs de cuivre si le plan existe,
demande détaillée, photos des plaques légendées par poste, plan du local en dernière page s'il existe) et un mail
court, sans tableau, qui renvoie au PDF.

**On le déclenche en disant.** « prépare la demande pour les grossistes », « demande de prix », « prépare la demande
pour [fabricant] ».

**À savoir.**

* Pour les grossistes, le client reste anonyme ; un contrôle automatique le vérifie, avec chaque chiffre et chaque
  photo.
* On copie le mail depuis la page qui s'ouvre, on joint le PDF, on envoie, puis on dit « c'est envoyé à … » :
  l'assistant le note.
* Une version envoyée ne se réécrit jamais : une correction donne une version 2.

### Le plan du local

> Étape P · `froid-plan-2d` · sur le PC · modèle Opus, demandé automatiquement par l'outil

**À quoi ça sert.** Dessiner le local à l'échelle avec les chambres, les équipements et les réseaux, et en tirer le
métré, avant ou après le dimensionnement.

**Ce qu'on lui donne.** Les cotes : dictées au télémètre, écrites sur un croquis photographié, ou lues sur un plan
d'architecte. Chaque cote manquante devient une question : l'assistant n'en estime aucune.

**Ce qu'on en sort.**

* un plan A4 à une échelle normalisée (1:50, 1:100…), avec barre d'échelle et règle de contrôle de 100 mm ;
* le métré de chaque réseau (cuivres froid, condensats, cuivres clim, câbles), montées et descentes comprises, et
  les croisements entre réseaux ;
* une page de lecture, un PDF à imprimer et un fichier draw.io pour retoucher à la souris.

**On le déclenche en disant.** « dessine le local », « mets ce croquis au propre », « trace les cuivres », « métré
des lignes ».

**À savoir.**

* Imprimer en « taille réelle » (100 %), jamais « ajusté à la page » : la règle de contrôle doit mesurer 100 mm au
  réglet.
* Retouches à la voix (« décale l'évaporateur de 20 cm à droite ») ou dans draw.io : enregistrer, fermer, puis le
  dire. Ne jamais déplacer tout le dessin d'un bloc.
* Une longueur mesurée sur chantier se dicte (« l'aspiration de la chambre viande, je l'ai mesurée : 12 mètres ») et
  devient « (mesurée) ». Les hauteurs de pose par défaut sont à valider une fois.

#### La feuille à imprimer et la photo du tracé

Pour tracer un réseau à la main :

1. Dire « feuille à imprimer » et le réseau (cuivres froid, cuivres clim ou électricité) : une feuille A4 avec le
   plan en gris et quatre repères dans les coins.
2. L'imprimer en A4 ; « ajuster à la page » est permis pour cette feuille seulement.
3. Tracer au marqueur rouge, bleu ou vert, un trait continu par tronçon ; un équipement à ajouter en rectangle
   fermé ; les annotations hors du bâtiment.
4. Photographier de dessus, à plat, sans flash, les quatre repères entiers, et garder la photo d'origine.
5. La transférer du téléphone au PC (mail, WhatsApp sur l'ordinateur ou câble), la déposer dans le dossier du
   chiffrage sous `plan/photos/`, puis dire « voilà la photo du tracé ». L'assistant montre ce qu'il a lu, les
   longueurs et ses questions ; rien n'entre dans le plan avant accord.

Grâce aux repères, l'angle de la photo ne fausse pas les longueurs : dans les essais, elles sont retrouvées à moins
de 1 % près.

### La question technique

> `froid-question` · sur le téléphone ou l'application Claude sur ordinateur

**À quoi ça sert.** Retrouver une réponse dans les 46 livres, formations et notices de Cazal, depuis le chantier.

**Ce qu'on lui donne.** La question, au vocal ou à l'écrit.

**Ce qu'on en sort.** Une réponse courte tirée uniquement des documents, la source (document et page imprimée) et le
lien vers l'image de la page, pour voir le vrai schéma.

**On le déclenche en disant.** « cherche dans mes docs », « retrouve le schéma de… », « comment régler
[appareil] », « symptômes de… ».

**À savoir.**

* Rien dans les documents : la réponse est « pas trouvé, à confirmer dans la notice ». Aucun schéma n'est
  redessiné.
* La base gratuite se met en pause après sept jours sans activité : l'assistant le signale, donne quand même les
  pages à consulter, et renvoie vers le PC (« état du savoir »).

### L'entretien de la base de savoir

> `froid-savoir` · sur le PC

**À quoi ça sert.** Ajouter un document, voir l'état de la base, la réveiller, noter les leçons.

**Ce qu'on lui donne.** Un PDF : livre, formation, notice ou catalogue.

**Ce qu'on en sort.** Le document lu page par page (texte reconnu sur l'image si c'est un scan) et chargé dans la
base ; l'état de la base ; le nouveau zip de la question technique.

**On le déclenche en disant.** « ajoute ce document au savoir », « état du savoir », « la base est en pause »,
« retiens ça ».

**À savoir.**

* Pour un scan, le coût de la lecture est annoncé avant de lancer.
* Après un ajout, recharger le zip de la question technique : sinon le téléphone ignore le nouveau document.
* « retiens ça » range une correction dans le carnet des leçons, relu au début de chaque dossier.

### Le résumé vocal avant devis, version 3

> `resume-vocal-devis` · sur le téléphone

**À quoi ça sert.** Toujours un vocal transformé en résumé de forme fixe, à coller dans InterFast. Nouveau : la
visite de remplacement d'installation frigorifique.

**Ce qu'on lui donne.** Le vocal de la visite.

**Ce qu'on en sort.**

* la forme « remplacement » : motif, un bloc par poste dans l'ordre du rapport InterFast (compresseurs, chambres
  desservies, gaz et charge, plaques photographiées), chambres froides, local technique ;
* des questions de rattrapage : une information indispensable manquante devient une question sous le résumé, cinq
  au plus ; après la réponse, le résumé complet est renvoyé ;
* le référentiel des unités intérieures de clim : marques mal comprises corrigées, référence exacte complétée,
  couleur vérifiée.

**On le déclenche en disant.** « résume ce vocal », « résumé visite remplacement », « récap remplacement
centrale ».

**À savoir.**

* Seul le bloc se colle dans InterFast ; « À vérifier » et « Il te manque » restent en dessous.
* Un modèle absent de la liste est écrit tel que dicté et signalé, jamais remplacé.

### La mise à jour de l'AIOS

> `maj-aios` · sur le PC

**À quoi ça sert.** Recevoir les améliorations d'Adrien.

**Ce qu'on lui donne.** Rien : la phrase suffit.

**Ce qu'on en sort.** Les nouveautés installées et un compte rendu : ce qui a changé, quels zips recharger. Un fichier
du système modifié sur le PC est mis de côté dans `active/sauvegarde-maj/<date>/` et remplacé par l'original.

**On le déclenche en disant.** « mets à jour mon AIOS », « maj ».

**À savoir.**

* Les fichiers personnels (zone perso, dossiers de chiffrage, documents) ne sont jamais touchés.
* Les zips du téléphone sont dans `skills-mobiles/`. On les charge sur claude.ai : Personnaliser ▸ Compétences ▸
  Téléverser ▸ Remplacer (intitulé variable selon la version).

### La zone perso

> dossier `perso/` · sur le PC

**À quoi ça sert.** Garder ce qu'on demande à l'assistant de créer pour soi : notes, annuaire, modèles de mail,
brouillons.

**Ce qu'on lui donne.** La demande, simplement.

**Ce qu'on en sort.** Des fichiers qui restent sur le PC : jamais envoyés dans le dépôt en ligne d'Adrien, jamais
touchés par la mise à jour.

**On le déclenche en disant.** Par exemple : « garde ce modèle de mail », « note pour Adrien : … ».

**À savoir.**

* Le fichier `perso/demandes-a-adrien.md` liste ce qu'on voudrait changer dans le système. On l'envoie à Adrien
  quand on veut (mail ou WhatsApp) ; il est aussi relu ensemble à chaque visio.
* Un nouvel outil demandé est créé dans son propre dossier et noté dans ce même fichier ; Adrien l'intègre au
  système à la mise à jour suivante.

## Le déroulé complet d'un remplacement

Exemple : une boucherie avec deux chambres froides, dont on remplace la production de froid.

### Sans plan

1. **Le rapport de visite**
   * On dit « nouveau dossier, voici le rapport de visite » et on glisse le PDF.
   * L'assistant ouvre la page du relevé, avec ses questions.
   * On vérifie les plaques, on répond, on valide.
2. **Le dimensionnement**
   * On dit « je remplace les deux groupes par une centrale au CO2 ».
   * L'assistant ouvre la page des puissances, du fluide et des questions.
   * On vérifie la puissance de chaque poste et les hypothèses, on valide.
3. **La demande fournisseur**
   * On dit « prépare la demande pour les grossistes ».
   * L'assistant produit et contrôle le PDF et le mail. Le PDF indique « Longueurs de lignes non relevées, à estimer
     par vos soins. »
   * On relit le PDF et le mail.
4. **L'envoi**
   * On envoie depuis sa messagerie, puis on dit « c'est envoyé aux grossistes ».
   * L'assistant note l'envoi dans le dossier ; une correction ultérieure donnera une version 2.

### Avec plan

1. **Le rapport de visite** : identique.
2. **Le plan du local** (nouveau, avant ou après le dimensionnement)
   * On dit « dessine le local » et on donne les cotes.
   * L'assistant pose ses questions, puis produit le plan, le métré et la page de lecture.
   * On imprime à 100 %, on vérifie la règle de 100 mm, le tracé et les hauteurs de pose.
3. **Le dimensionnement** : identique.
4. **La demande fournisseur** (change)
   * On dit la même chose.
   * Le PDF ajoute les longueurs de cuivre estimées et le plan en dernière page (détail dans le tableau suivant).
   * On relit aussi les longueurs et la page du plan.
5. **L'envoi** : identique.

### Ce qui change, en un coup d'œil

| Point | Sans plan | Avec plan |
|---|---|---|
| Étape du plan | absente | avant ou après le dimensionnement |
| Longueurs de cuivre dans le PDF | « à estimer par vos soins » | estimées d'après le plan, ou « (mesurée) » |
| Dernière page du PDF | annexes, plan d'implantation « à suivre » | le plan du local, à imprimer à 100 % |
| Mail | aucune mention des longueurs | une phrase qui renvoie aux longueurs et au plan |

### Quand on n'est pas devant l'écran

On peut tout demander d'un coup : « chiffre ce dossier et prépare la demande pour les grossistes, je ne suis pas
là ». L'assistant enchaîne les trois étapes ; ce qu'on aurait dicté devient une hypothèse marquée « (hyp.) ». À la
fin : une seule liste de questions, et rien n'est envoyé. On relit, on répond, puis on envoie. Le plan demande des
cotes et n'entre pas dans cet enchaînement ; s'il existe déjà, ses longueurs sont reprises.

## Où sont rangées les choses

Tout se trouve dans le dossier de l'AIOS, sur le PC.

| Quoi | Où | À savoir |
|---|---|---|
| Dossiers de chiffrage | `dimensionnement/dossiers/` | un dossier par installation, mémoire dans `dossier.md` |
| Plans | `plan/`, dans chaque dossier | plan, métré, feuilles, photos |
| Demandes fournisseur | `3-demande-fournisseur/`, dans chaque dossier | une version par envoi, liste des envois |
| Base de savoir | `dimensionnement/bibliotheque/` | les originaux ; le contenu lu est dans la base en ligne privée |
| Carnet des leçons | `dimensionnement/carnet/lecons.md` | relu au début de chaque dossier |
| Zips des outils du téléphone | `skills-mobiles/` | à jour après chaque mise à jour |
| Zone perso | `perso/` | jamais touchée par la mise à jour |
| Sauvegardes de mise à jour | `active/sauvegarde-maj/<date>/` | fichiers du système modifiés sur le PC, mis de côté |

## Tableau récapitulatif

| Outil | À quoi il sert | On le déclenche en disant… | Où |
|---|---|---|---|
| Relevé de l'existant (`froid-releve-existant`) | Rapport de visite → installation en place et questions | « nouveau dossier, voici le rapport de visite » | PC |
| Dimensionnement (`froid-dimensionnement`) | Puissances existante et demandée, fluide | « on passe au dimensionnement » | PC |
| Demande fournisseur (`froid-demande-fournisseur`) | PDF et mail court pour grossistes ou fabricant | « prépare la demande pour les grossistes » | PC |
| Plan du local (`froid-plan-2d`) | Plan A4 à l'échelle, métré, feuille à imprimer | « dessine le local », « voilà la photo du tracé » | PC |
| Question technique (`froid-question`) | Réponse sourcée tirée des livres et notices | « cherche dans mes docs » | téléphone |
| Entretien de la base (`froid-savoir`) | Ajout de document, état, leçons | « ajoute ce document au savoir », « état du savoir » | PC |
| Résumé vocal (`resume-vocal-devis`) | Vocal → résumé fixe pour InterFast | « résume ce vocal » | téléphone |
| Mise à jour (`maj-aios`) | Nouveautés d'Adrien, zips à recharger | « mets à jour mon AIOS » | PC |
| Zone perso (`perso/`) | Notes, annuaire, modèles, demandes à Adrien | « garde ce modèle de mail » | PC |

## À retenir

* **Valider à chaque étape.** Un chiffre faux envoyé au fournisseur, c'est le mauvais compresseur commandé.
* **Rien ne part tout seul.** L'assistant prépare ; on relit, puis on envoie.
* **Une longueur est une estimation** tant qu'elle n'a pas été mesurée sur chantier. Diamètres et charge restent au
  fournisseur.
* **Imprimer les plans à 100 %** et vérifier la règle de contrôle au réglet.
* **Après chaque mise à jour**, recharger les zips indiqués ; ranger ses propres fichiers dans `perso/`.
