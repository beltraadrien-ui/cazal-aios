<!--
Textes par défaut de la demande de prix, variante « grossiste » (plusieurs grossistes non nommés, vouvoiement,
client anonymisé). Lu par scripts/assembler.py, qui remplit les champs {…} depuis le dossier (mécanisme complet dans
le docstring d'assembler.py). Claude peut ensuite ajuster les textes dictés dans demande.json, jamais un chiffre.

Origine : structure et phrases du mail aux grossistes du 16/09/2026 (conversation de Loïc, captures 17 à 19 :
objet, « Nous soumissionnons actuellement… », 1. Chambres à traiter, 2. Production frigorifique existante,
3. Évaporateurs en place, 4. Notre demande d'offre a) à f), « En résumé… », formule). Termes corrigés : Alfa Laval
(dicté « Alpha Luv »), Danfoss (dicté « dents fausses »), supervision AK-SM 800A, régulateurs AK-CC 55, cuivre K65.
Adaptations voulues : le mail ne porte plus aucun tableau (décision D11 du 2026-10-07) et renvoie au PDF, qui contient
tout ; la référence à un autre chantier (« même principe que notre projet … ») est retirée ; les quantités
(portes, soupapes) ne sont reprises que si le bloc F de l'étape 2 les écrit ({qte …}) ; les phrases liées au
dossier ne sortent que si l'étape 2 (bloc F, bloc A ou projet) en parle (conditions [si …]).
Aucun nom de client ni coordonnée dans ce fichier : tout vient du dossier par les champs.
Lot 7 : {phrase_longueurs} (mail) dit que les longueurs de cuivre estimées d'après le plan et le plan du local sont
dans le PDF ; vide sans plan ni métré, la ligne disparaît. Jamais de tableau de longueurs dans le mail.
-->
# Textes par défaut · demande de prix · variante « grossiste »

Syntaxe (détail dans le docstring d'assembler.py) :

- `## clé` ouvre une section ; tout ce qui précède la première section est de la documentation.
- `{champ}` est remplacé par une valeur du dossier ; une ligne dont un champ est vide disparaît.
- `[si mot1 / mot2]` en début de ligne : la ligne n'est gardée que si l'un des mots figure au bloc F, au bloc A ou
  dans le projet de l'étape 2 ; `[si poste négatif]`, `[si poste positif]` : s'il existe un tel poste ;
  `[tu]`, `[vous]` : selon le tutoiement.
- `{si mot1 / mot2 : texte}` dans une ligne : le texte n'est inséré que si l'un des mots figure dans l'étape 2 ; il
  commence juste après « : » et une espace (deux espaces pour qu'il commence par une espace).
- `{qte mot}` : le nombre écrit juste avant ce mot au bloc F (« deux soupapes » → « deux ») et une espace ; rien
  sinon (jamais de quantité inventée).
- Dans une section, les lignes qui se suivent forment un paragraphe ; une ligne vide sépare deux paragraphes.
- `demande.<lettre>` : `titre:`, `si:` (le point entier disparaît si aucun mot n'est trouvé), `texte:`, puis les
  sous-points `- …` ; des éléments `  - …` (en retrait) sont joints au sous-point qui les précède par « ; ».
- `liste.<nom>` donne le champ {liste_<nom>} (« a, b et c ») ; `motif.<nom>` est un modèle répété par poste.

## titre

Demande de prix — {site_titre} — {date} — {version}

## mention

Valeurs indicatives, sélection finale chez le fournisseur.

## contexte

Nous soumissionnons actuellement pour un marché de remodeling d'une installation frigorifique aujourd'hui en
{installation_actuelle}, appelée à être remplacée par une centrale {fluide_cible} booster (basse + moyenne
température). À ce stade nous chiffrons notre offre : nous avons donc besoin d'une offre de prix compétitive de votre
part pour une installation complète de A à Z, sur la base de l'installation existante détaillée ci-dessous. La
solution {fluide_cible} pourra être adaptée selon ce que vous proposez.

Il s'agit de remplacer {remplace} par {par_quoi}.

Puissance frigorifique existante, calculée à partir des plaques des compresseurs : {chiffres_cles}.

Marché : {marche}.

Vous trouverez dans ce document l'ensemble des plaques signalétiques (compresseurs par centrale, évaporateurs par
chambre), chacune légendée à côté de sa photo.

## chambres.note

{disposition}
Condensation de référence : {condensation}.
{note_hypotheses}

## production.note

Puissances calculées à partir des plaques des compresseurs, par deux méthodes croisées (cylindrée et point catalogue
du fabricant), régimes {regimes}, fluide actuel {fluide_actuel_note}.
Valeurs indicatives, sélection finale chez le fournisseur.

## evaporateurs.note

Les plaques des évaporateurs ne donnent pas la puissance frigorifique : puissance à confirmer par vos calculs, aux
régimes ci-dessus.

## evaporateurs.puissance

à confirmer par vos calculs

## demande.titre

Notre demande d'offre — installation complète de A à Z

## demande.intro

Sur la base des chambres, des puissances et des régimes ci-dessus, merci de nous chiffrer les éléments suivants.

## demande.a

titre: Centrale {fluide_cible} booster
texte: Basse + moyenne température, dimensionnée pour les charges ci-dessus{si récupération de chaleur : , avec récupération de chaleur pour le chauffage au sol des congélateurs}.

## demande.b

titre: Évaporateurs {fluide_cible} neufs
si: évaporateur
texte: {si Alfa Laval : de préférence marque Alfa Laval, }en remplacement des évaporateurs existants, dimensionnés pour les régimes ci-dessus.

## demande.c

titre: Armoire de régulation complète, pré-câblée{si Danfoss : , en Danfoss}
si: armoire / régulat
- [si AK-SM 800A] Supervision AK-SM 800A.
- [si AK-CC 55] Régulateurs de poste AK-CC 55.
- [si poste négatif] Partie négative :
  - {regulateurs_negatif}
  - [si dégivrage électrique] dégivrage électrique sur chaque évaporateur
  - [si cordon] gestion des {qte porte}portes avec cordon chauffant
  - [si soupape] {qte soupape}soupapes de décompression à intégrer dans l'armoire
- [si poste positif] Partie positive :
  - {regulateurs_positif}
  - [si dégivrage naturel] pas de dégivrage électrique, dégivrage naturel
- [si chauffage du sol] Prévoir également la régulation du chauffage au sol des congélateurs.

## demande.d

titre: Matériel frigorifique de régulation{si Danfoss :  — Danfoss}
si: détendeur / sonde / transducteur
- détendeurs (électroniques)
- transducteurs de pression
- sondes de température

## demande.e

titre: Système de détection de fuite {fluide_cible}{si Danfoss :  — Danfoss} (complet)
si: détection de fuite

## demande.f

titre: Tarifs indicatifs
si: cuivre / isolant / petites fournitures
texte: Pour nos métrés d'après plan d'implantation :
- [si cuivre] prix du cuivre{si K65 :  K65} du moment
- [si isolant] prix des isolants
- [si petites fournitures] prix des petites fournitures (colliers isolés, coudes, raccords, etc.)

## demande.resume

En résumé, nous recherchons le chiffrage d'une installation {fluide_cible} complète : {liste_demande}{si Danfoss :  — la partie régulation et détection en Danfoss}.

## liste.demande

- [si centrale] centrale booster
- [si évaporateur] évaporateurs
- [si armoire] armoire de régulation pré-câblée
- [si détection de fuite] détection de fuite
- [si détendeur / sonde / transducteur] l'ensemble du matériel de régulation frigorifique (détendeurs, transducteurs de pression, sondes de température)

## motif.regulateur.negatif

1 régulateur gérant {les_evaporateurs} de la {chambre}

## motif.regulateur.positif

1 seul régulateur gérant {les_evaporateurs}

## mail.objet

Demande d'offre de prix — Installation complète centrale {fluide_cible} booster (remplacement {famille_actuelle} {fluide_actuel})

## mail.salutation

Bonjour,

## mail.salutation.destinataire

Bonjour {destinataire_nom},

## mail.corps

Nous soumissionnons actuellement pour un marché de remodeling d'une installation frigorifique aujourd'hui en
{installation_actuelle}, appelée à être remplacée par une centrale {fluide_cible} booster (basse + moyenne
température) : {chambres_resume}.

Puissance frigorifique existante, calculée à partir des plaques des compresseurs : {chiffres_cles}.

Nous avons besoin d'une offre de prix compétitive de votre part pour une installation complète de A à Z :
{liste_demande}{si Danfoss :  — la partie régulation et détection en Danfoss}.

Tout le détail (chambres, production existante, évaporateurs en place, notre demande point par point, plaques
signalétiques et photos) est dans le PDF joint.
{phrase_longueurs}

Pourriez-vous nous faire parvenir votre offre {delai_reponse} ?
Merci d'avance pour votre proposition. N'hésitez pas à revenir vers nous pour tout complément.

## mail.formule

Bien cordialement,

## mail.signature

{contact}
{societe_et_telephone}
{mail_emetteur}
