# Demande de prix aux fournisseurs (étape 3)

> v1 du 2026-10-07 (Lot 3). Ce que Loïc attend d'une demande de prix et comment le système la construit. Sources :
> « conversation Claude de Loïc du 16/09/2026 » (numéro de capture d'écran), « visio du 24/09/2026 » (minute de
> l'enregistrement), décision d'Adrien du 2026-10-07. Aucune donnée client ici. La mécanique (scripts, étapes,
> contrôles) est dans `.claude/skills/froid-demande-fournisseur/SKILL.md` ; les règles datées dans `regles-loic.md`
> (R4, R5, R7, R8, R9 à R13).

## 1. Ce qu'un fournisseur attend (d'après Loïc)

- **La capacité frigorifique actuelle**, pour qu'il sélectionne le matériel : c'est le but de la demande
  (conversation du 16/09, capture 2). D'où la puissance existante par poste, avec ses régimes (évaporation et
  condensation), et la mention « Valeurs indicatives, sélection finale chez le fournisseur ».
- **Des chiffres justes et sourcés** : « s'il y a une erreur sur un chiffre, tu vas l'envoyer au fournisseur et
  ensuite tu commandes le mauvais compresseur » (visio du 24/09, 14:00). Chaque chiffre vient de l'étape 2 avec son
  statut ; une hypothèse reste marquée « (hyp.) » ; ce qu'on ne sait pas s'écrit « à confirmer par vos calculs »
  (puissance des évaporateurs) plutôt qu'une estimation.
- **L'ordre de grandeur suffit en remise de prix** : « on n'est pas à la virgule près » ; après signature, tout est
  à faire confirmer par le fournisseur (visio du 24/09, 34:29 à 36:07).
- **Le sous-détail à côté de chaque photo** : « tu lui fais le dossier photo, tu as déjà le sous-détail à chaque
  fois de ce que tu lui demandes, c'est carré […] tu as l'air beaucoup plus sérieux » (visio du 24/09, 17:08). Chaque
  plaque a sa légende juste à côté : modèle, n° de série, volume balayé ou année et fluide, puissance avec statut.
- **Trois tableaux** : les chambres à traiter, la production frigorifique existante, les évaporateurs en place, puis
  la demande d'offre détaillée (16/09, captures 12 et 17 à 19). Pour le fabricant de la centrale : chambres et
  production seulement (16/09, captures 20 à 22, demande dictée le 24/09).
- **Une pièce jointe qui passe** : le PDF de photos de 11,9 Mo n'est pas parti (16/09, capture 14 ; visio du 24/09,
  16:41 : « le mail ne passe pas parce qu'il est trop volumineux »).
- **Des tableaux qui ne se cassent pas** : coller des tableaux dans Outlook les perdait ; seule une page HTML copiée a
  marché (16/09, capture 20 ; visio du 24/09, 16:01). D'où la décision du 2026-10-07 (§ 2).

## 2. Le livrable : un seul PDF et un mail court

**Décision d'Adrien du 2026-10-07** (R13) : un **PDF unique** qui contient tout (tableaux, demande, photos) et un
**mail court sans aucun tableau** qui renvoie au PDF. Elle remplace la pratique du 16/09 (trois tableaux collés dans
le corps du mail, PDF de photos seules) ; une page de tableaux à coller dans Outlook reste une option future.

### Le PDF, en sept chapitres

| Chapitre | Contenu |
|---|---|
| Page de garde | Cazal Réfrigération (coordonnées de `emetteur.json`), « Demande de prix », date, version, destinataire (« Grossistes (consultation) » ou la personne), sommaire, mention « Valeurs indicatives, sélection finale chez le fournisseur » |
| 1. Contexte | 5 à 8 lignes : l'existant en une phrase, ce qu'on remplace par quoi, l'objectif (offre compétitive, installation complète de A à Z ou centrale seule), la puissance existante, les contraintes (implantation, récupération de chaleur, planning, phase de prix et nombre d'entreprises en lice) |
| 2. Les chambres à traiter | Chambre · Régime · Surface · Volume · Évaporateurs ; chambres accolées ou communicantes, condensation de référence |
| 3. La production frigorifique existante | Poste · Compresseurs · Volume balayé · Puissance · Statut ; sous-total par régime ; note : calculée à partir des plaques, deux méthodes croisées, régimes, fluide actuel |
| 4. Les évaporateurs en place | Chambre · Fabricant / modèle · Année · Puissance « à confirmer par vos calculs » (variante grossiste) |
| (5.) Longueurs de cuivre | Seulement si l'étape P a produit `plan/metre.json` (§ 6 bis) ; les chapitres suivants prennent un numéro de plus |
| 5. Notre demande | Grossiste : a) à f) puis « En résumé » (§ 4). Fabricant : options techniques, implantation, planning |
| 6. Le détail par poste | Pour chaque centrale ou groupe : ce qu'il dessert, l'existant (une ligne par équipement), la puissance retenue, ce qu'on remplace (seulement ce qui concerne ce poste dans le bloc E ; les questions pour Loïc en sont retirées ; « Régulation : voir § 5 c) » si la régulation est demandée à part), les photos des plaques légendées, deux par rangée. Une légende ne garde que ce qui est lu avec certitude : les annotations de lecture (« ? », « douteux », « lecture : … ») sont retirées et la légende dit « plaque partiellement lisible » |
| 7. Annexes | Plan d'implantation (« à suivre » sans plan, sinon « plan du local en annexe »), pièces jointes, vues d'ensemble légendées (régulation, condenseurs, échangeurs, locaux, chambres) ; la page 1 du plan du local en dernière page du PDF si `plan/plan.pdf` existe (§ 6 bis) |

A4, numéros de page, titre en en-tête, mention en pied de page ; chapitres 1 à 5 à la suite, nouvelle page pour le
contexte, le détail par poste et les annexes. Sans chapitre 4 (variante fabricant), les suivants se renumérotent.

### Le mail

Objet ; « Bonjour, » ou « Salut <prénom>, » ; **6 à 8 lignes** : ce qu'on chiffre, l'installation en une phrase,
**les chiffres clés en une ligne** (puissance par régime, régimes, condensation, « valeurs indicatives »), ce qu'on
demande, « tout le détail, plaques et photos, est dans le PDF joint », le délai de réponse ; formule ; signature.
**Aucun tableau.** Livré en `.txt` et en page `.html` (objet et texte prêts à copier ; Loïc joint le PDF).

## 3. Les deux variantes

| | Grossiste | Fabricant de centrale |
|---|---|---|
| Destinataire | plusieurs grossistes, non nommés | une personne nommée chez le fabricant |
| Ton | vouvoiement, formel (16/09, captures 17 à 19) | tutoiement, cordial (16/09, captures 20 à 22) |
| Client | anonymisé (16/09, capture 9 : « sans nom de client ») | chantier nommé, avec sa référence |
| PDF | chapitres 1 à 7 | sans le chapitre des évaporateurs ni l'armoire ; options, implantation, planning |
| Mail | résumé, chiffres clés, renvoi au PDF | résumé cordial, options et questions techniques, « phase de prix », renvoi au PDF |

## 4. La demande a) à f) (variante grossiste)

D'après le mail aux grossistes du 16/09 (captures 6, 9, 11, 17 à 19), termes corrigés :

- **a) Centrale CO2 booster** basse + moyenne température, dimensionnée pour les charges des tableaux, avec
  récupération de chaleur si le projet en prévoit une.
- **b) Évaporateurs CO2 neufs**, Alfa Laval de préférence, en remplacement des existants.
- **c) Armoire de régulation complète, pré-câblée, Danfoss** : supervision AK-SM 800A, régulateurs de poste
  AK-CC 55 ; détail par régime (régulateurs par chambre, dégivrage, cordons chauffants de portes, soupapes de
  décompression) ; régulation du chauffage du sol s'il y en a un.
- **d) Matériel frigorifique de régulation Danfoss** : détendeurs électroniques, transducteurs de pression, sondes de
  température.
- **e) Détection de fuite CO2 Danfoss**, complète.
- **f) Tarifs indicatifs** pour les métrés d'après le plan d'implantation : cuivre K65 du moment, isolants, petites
  fournitures (colliers isolés, coudes, raccords).

Puis « En résumé… » en une phrase. Un point ne sort que si l'étape 2 en parle (bloc F, bloc A ou projet) ; une
quantité (portes, soupapes) n'est reprise que si le bloc F l'écrit, telle quelle (« deux soupapes »), jamais devinée.
Variante fabricant (16/09, captures 20 à 22, R7) : gas coolers dimensionnés sur les températures de l'été passé,
récupération de chaleur, désurchauffeur sur le refoulement négatif, aimants permanents, variateur sur les premiers
compresseurs, module ULSH en option, autres options recommandées, implantation (extérieur sous toit grillagé,
carénage contre les rongeurs ?), planning.

## 5. Anonymisation (variante grossiste)

- Sont retirés : le nom du client et ses mots distinctifs, l'adresse, la rue, le code postal, la localité, le
  téléphone, le mail et son domaine, le n° de fiche InterFast, le nom du dossier. Ils deviennent « le client »,
  « le site », « (localité retirée) »… ; les chemins des photos, jamais montrés, ne sont pas touchés.
- Le contrôle les cherche ensuite dans `demande.json`, la page, le mail et le texte du PDF, en majuscules, sans
  accents et sans espaces. **Une photo n'est pas lue par le contrôle** : une enseigne ou une étiquette au nom du
  client sur une photo se voit à la relecture (vérificateur, puis Loïc).
- Le titre devient « installation frigorifique » ; le fabricant, lui, reçoit le chantier nommé.

## 6. Le poids

- **Moins de 5 Mo** (hypothèse en attendant la réponse de Loïc sur ce qui passe chez ses fournisseurs) ; au-delà, le
  contrôle échoue. 11,9 Mo n'est pas passé (16/09, capture 14).
- Photos réduites à 800 px de large, JPEG qualité 80 : un dossier de 43 photos tient en 2,5 Mo environ (essai du
  2026-10-07). Trop lourd : retirer des vues d'ensemble, jamais une plaque.

## 6 bis. Longueurs de cuivre et plan du local (Lot 7, décision d'Adrien du 2026-10-08)

- Le fournisseur chiffre les cuivres : on lui donne **les longueurs de cuivre estimées d'après le plan** (étape P,
  `plan/metre.json`), réseau par réseau (froid : aspiration, liquide, condensats ; clim : gaz, liquide), jamais
  l'électricité ni les autres réseaux (eau glacée). Chapitre « Longueurs de cuivre (estimées d'après le plan) »,
  entre les évaporateurs et la demande : la phrase « Toutes les longueurs sont des estimations d'après le plan (tracé
  et hauteurs de pose), sauf celles marquées « (mesurée) », relevées sur chantier. », un tableau par réseau (Tronçon · Type ·
  Longueur (m), total), puis « Diamètres et charge de fluide à définir par vos soins. ».
- **Toute longueur est une estimation**, sauf celle **mesurée sur chantier par Loïc**, seule fiable, marquée
  « (mesurée) ». Les **diamètres et la charge de fluide restent au fournisseur** (diamètres calculés : option future).
- Sans métré : pas de chapitre, une ligne « Longueurs de lignes non relevées, à estimer par vos soins. » dans la
  demande, rien dans le mail.
- Le **plan du local** (page 1 de `plan/plan.pdf`, A4 à l'échelle) est ajouté en dernière page du PDF, sans mise à
  l'échelle (à imprimer à 100 %) ; il ne porte pas les numéros de page du document. Variante grossiste : le cartouche
  est anonymisé comme le reste.
- Mail : une seule phrase, « Les longueurs de cuivre estimées d'après le plan figurent dans le PDF, avec le plan du
  local en annexe. » ; aucun tableau.

## 7. Hors V1

Page de tableaux pour Outlook (option future) · métré complet joint (électricité, croisements ; seules les longueurs
de cuivre et le plan le sont depuis le Lot 7) · diamètres calculés · traduction ·
suivi des réponses des fournisseurs · **envoi automatique : jamais** (Loïc envoie lui-même).
