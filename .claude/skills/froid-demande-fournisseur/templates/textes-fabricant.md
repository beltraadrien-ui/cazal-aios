<!--
Textes par défaut de la demande de prix, variante « fabricant » (une personne nommée chez le fabricant de la centrale,
ton cordial, chantier nommé ; tutoiement avec --tutoiement, vouvoiement sinon). Lu par scripts/assembler.py, qui
remplit les champs {…} depuis le dossier (mécanisme complet dans le docstring d'assembler.py). Claude peut ensuite
ajuster les textes dictés dans demande.json, jamais un chiffre.

Origine : demande de Loïc du 24/09/2026 pour le fabricant de la centrale CO2 (conversation de Loïc, captures 20 à 22 :
dictée complète de Loïc et résumé du mail produit ; le corps du mail lui-même n'apparaît pas dans les captures, ces
phrases reprennent donc la dictée au plus près). Ce qu'on y retrouve : ton cordial, référence du chantier, seulement
les chambres et la production existante (pas les évaporateurs ni l'armoire), centrale booster avec gas coolers
dimensionnés sur les températures de l'été, récupération de chaleur pour le chauffage du sol, désurchauffeur sur le
refoulement négatif, aimants permanents, variateur sur les premiers compresseurs, module ULSH en option, options
recommandées, implantation extérieure sous toit grillagé et question du carénage (rongeurs), planning, phase de prix
avec plusieurs sociétés en lice. Termes corrigés : Advansor (dicté « Advensor », nom du destinataire passé en option,
pas dans ce fichier), désurchauffeur (dicté « surchauffeur »), gas cooler (dicté « gaz couleur »).
Retiré : le nom de l'autre chantier prévu avant celui-ci dans le planning de Loïc (champ {planning_cazal}, vide par
défaut : à dicter par Loïc, la phrase n'apparaît que s'il est rempli).
Aucun nom de client ni coordonnée dans ce fichier : tout vient du dossier par les champs.
Lot 7 : {phrase_longueurs} (mail) dit que les longueurs de cuivre estimées d'après le plan et le plan du local sont
dans le PDF ; vide sans plan ni métré, la ligne disparaît. Jamais de tableau de longueurs dans le mail.
-->
# Textes par défaut · demande de prix · variante « fabricant »

Syntaxe : la même que `textes-grossiste.md` (détail dans le docstring d'assembler.py). Les lignes `[tu]` sortent
avec --tutoiement, les lignes `[vous]` sans.

## titre

Demande de prix — {site_titre} — {date} — {version}

## mention

Valeurs indicatives, sélection finale chez le fournisseur.

## contexte

[tu] Je te sollicite pour une offre de prix pour un nouveau projet, réf. {reference_chantier}.
[vous] Nous vous sollicitons pour une offre de prix pour un nouveau projet, réf. {reference_chantier}.

Il s'agit de remplacer {remplace} par {par_quoi}.

Puissance frigorifique existante, calculée à partir des plaques des compresseurs : {chiffres_cles}.

Sur ce projet, nous sommes {nb_entreprises} entreprises à remettre prix : il nous faut donc une offre de prix assez
concurrentielle. Nous sommes en phase de prix, rien n'est encore signé.

[tu] Tu trouveras ci-dessous les chambres à traiter et la production frigorifique existante, puis notre demande et,
[tu] pour chaque poste, les plaques avec leurs photos.
[vous] Vous trouverez ci-dessous les chambres à traiter et la production frigorifique existante, puis notre demande
[vous] et, pour chaque poste, les plaques avec leurs photos.

## chambres.note

{disposition}
Condensation de référence : {condensation}.
{note_hypotheses}

## production.note

Puissances calculées à partir des plaques des compresseurs, par deux méthodes croisées (cylindrée et point catalogue
du fabricant), régimes {regimes}, fluide actuel {fluide_actuel_note}.
Valeurs indicatives, sélection finale chez le fournisseur.

## evaporateurs.note

Les plaques des évaporateurs ne donnent pas la puissance frigorifique : puissance à confirmer.

## evaporateurs.puissance

à confirmer

## demande.titre

Notre demande d'offre — centrale {fluide_cible} booster

## demande.intro

[tu] Peux-tu nous faire une offre de prix pour cette centrale en booster avec les gas coolers associés, pour les
[tu] puissances ci-dessus ?
[vous] Pourriez-vous nous faire une offre de prix pour cette centrale en booster avec les gas coolers associés, pour
[vous] les puissances ci-dessus ?

## demande.a

titre: Gas coolers
si: gas cooler
texte: Dimensionnés en fonction des températures que nous avons eues cet été.

## demande.b

titre: Récupération de chaleur
si: récupération de chaleur
texte: Sur la centrale {fluide_cible}, il nous faudra une récupération de chaleur{si chauffage du sol : , pour le chauffage du sol, aujourd'hui assuré par la récupération de chaleur de l'installation existante}.

## demande.c

titre: Désurchauffeur
si: désurchauffeur
texte: Il nous faudra d'office un désurchauffeur sur le refoulement négatif.

## demande.d

titre: Compresseurs
si: aimants / variateur
texte: À prévoir :
- [si aimants] aimants permanents sur les compresseurs
- [si variateur] d'office, variateur sur les premiers compresseurs

## demande.e

titre: Options
- [si ULSH] [tu] Le module ULSH ne serait-il pas intéressant ? Peux-tu le faire apparaître en option ?
- [si ULSH] [vous] Le module ULSH ne serait-il pas intéressant ? Pourriez-vous le faire apparaître en option ?
- [tu] Quelles options te paraissent pertinentes{si aimants : , en plus des aimants permanents} ?
- [vous] Quelles options vous paraissent pertinentes{si aimants : , en plus des aimants permanents} ?

## demande.f

titre: Implantation
si: extérieur / carénage
texte: [si toit / grillag] La centrale {fluide_cible} sera en extérieur, couverte par un toit et grillagée autour.
- [si carénage] [tu] Ne serait-il pas intéressant d'avoir quand même un carénage autour, pour la protéger de tout ce qui serait rongeur, etc. ? Qu'en penses-tu ?
- [si carénage] [vous] Ne serait-il pas intéressant d'avoir quand même un carénage autour, pour la protéger de tout ce qui serait rongeur, etc. ? Qu'en pensez-vous ?

## demande.g

titre: Planning
texte: C'est un projet que le client souhaiterait voir réalisé {planning_client}, au plus tôt dans l'année.
texte: De notre côté, si les chantiers sont signés, nous ferions d'abord {planning_cazal}, puis nous enchaînerions sur ce projet si le client décide de travailler avec nous.

## demande.resume

[tu] En résumé : une offre de prix pour la centrale {fluide_cible} booster avec {liste_options}, et ton avis sur les autres options pertinentes.
[vous] En résumé : une offre de prix pour la centrale {fluide_cible} booster avec {liste_options}, et votre avis sur les autres options pertinentes.

## liste.options

- [si gas cooler] gas coolers dimensionnés sur les températures de cet été
- [si récupération de chaleur] récupération de chaleur
- [si désurchauffeur] désurchauffeur sur le refoulement négatif
- [si aimants] aimants permanents
- [si variateur] variateur sur les premiers compresseurs
- [si ULSH] module ULSH en option
- [si carénage] carénage contre les rongeurs

## mail.objet

Demande de prix — centrale {fluide_cible} booster — réf. {reference_chantier}

## mail.salutation

Bonjour,

## mail.salutation.destinataire

[tu] Salut {destinataire_prenom},
[vous] Bonjour {destinataire_nom},

## mail.corps

[tu] Je te sollicite pour une offre de prix pour un nouveau projet, réf. {reference_chantier} : remplacer
[tu] {remplace} par une centrale {fluide_cible} booster avec les gas coolers associés.
[vous] Nous vous sollicitons pour une offre de prix pour un nouveau projet, réf. {reference_chantier} : remplacer
[vous] {remplace} par une centrale {fluide_cible} booster avec les gas coolers associés.

Puissance frigorifique existante, calculée à partir des plaques des compresseurs : {chiffres_cles}.

[tu] À prévoir : {liste_options}. Quelles autres options te paraissent pertinentes ?
[vous] À prévoir : {liste_options}. Quelles autres options vous paraissent pertinentes ?

[tu] Tout le détail, plaques et photos comprises, est dans le PDF joint (chambres, production existante,
[tu] implantation, planning).
[vous] Tout le détail, plaques et photos comprises, est dans le PDF joint (chambres, production existante,
[vous] implantation, planning).
{phrase_longueurs}

Nous sommes en phase de prix, {nb_entreprises} sociétés en lice : il nous faut une offre assez concurrentielle.
[tu] Peux-tu nous faire ton offre {delai_reponse} ?
[vous] Pourriez-vous nous faire votre offre {delai_reponse} ?

[tu] Merci d'avance !
[vous] Merci d'avance pour votre proposition.

## mail.formule

[tu] À bientôt,
[vous] Bien cordialement,

## mail.signature

{contact}
{societe_et_telephone}
{mail_emetteur}
