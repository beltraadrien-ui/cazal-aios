---
name: mail-fournisseurs-sous-traitants
description: Rédige, à partir d'un vocal ou d'un texte dicté par Loïc, des mails personnalisés pour les fournisseurs de matériel (centrales, évaporateurs, clim/PAC…) et les sous-traitants de Cazal (isolation, manutention, bureaux d'études, dessin…), en allant chercher les bonnes coordonnées dans les annuaires de la zone perso. Demandes de prix, commandes, relances, questions, réponses. Un mail par destinataire, jamais groupé. Se déclenche sur "demande de prix", "fais un mail au fournisseur", "écris au sous-traitant", "consulte les fournisseurs / les sous-traitants", "demande un prix pour une centrale / des évaporateurs", "fais les mails pour l'isolation / la manutention / le bureau d'études", "réponds à", "relance", "qui je peux contacter pour".
---

# Mails fournisseurs & sous-traitants — Cazal Réfrigération

> Outil construit par Loïc avec son assistant le 2026-10-08, intégré au système par Adrien. Usage PC
> uniquement (Claude Code) : pas de version mobile.

## Ce que fait cette skill

Loïc dicte un besoin (vocal ou texte), par ex. « demande de prix pour une centrale CO2 et 4
évaporateurs pour une GMS à Bohan » ou « il me faut un prix de calorifugeage chez un boucher à
Givet ». La skill :
1. identifie **à qui écrire** : fournisseurs (matériel) et/ou sous-traitants (main-d'œuvre, études) ;
2. va chercher les bons contacts dans les annuaires ;
3. rédige **un mail personnalisé par destinataire** (bon nom, bonne adresse, bon ton, besoin adapté).

**Elle n'envoie rien.** Elle produit des brouillons prêts à copier-coller. Loïc relit et envoie.

## Les deux annuaires (seules sources de coordonnées)

Les annuaires sont des **données de Loïc** : ils vivent dans sa zone perso, jamais sur GitHub, jamais
touchés par la mise à jour de l'AIOS.

- `perso/fournisseurs.md` — **matériel sur commande** (centrales, évaporateurs, groupes…), demandé
  par mail. **Une seule liste, sans groupes** : les fournisseurs font un peu de tout, on choisit
  grâce à la ligne « Points forts » de chaque fiche.
- `perso/sous-traitants.md` — **prestations**, rangées par groupe de domaine : isolation /
  calorifugeage, manutention / levage, bureaux d'études, dessin technique et plans…

Avant tout : si un annuaire est absent de `perso/` mais existe encore dans `references/` (son
ancienne place, avant la zone perso), le **déplacer** dans `perso/` et le dire à Loïc. S'il n'existe
nulle part, le créer depuis les modèles en bas de ce fichier et demander les premières fiches.

Ne **jamais inventer** un nom, une adresse mail ou un numéro.

## Étapes

1. **Comprendre la demande** : type de mail (demande de prix, commande, relance, question, réponse
   à un mail reçu) et ce qu'il faut (matériel et/ou prestation).
2. **Choisir les destinataires**. Un même projet peut toucher les deux annuaires
   (ex. chambre froide = fournisseurs + isolation + manutention) → les proposer tous.
   - **Fournisseurs** : par défaut, consulter **tous** ceux de la liste (mise en concurrence), en
     signalant ceux dont les « Points forts » collent le mieux ; Loïc retire qui il veut.
   - **Sous-traitants** : le ou les groupes du domaine concerné.
   - **Destinataires et copies** : si la fiche a une ligne « Demandes de prix : À … · Cc … », la
     respecter à la lettre (ex. chez un fabricant : À le commercial, Cc l'ingénieur commercial ;
     chez un grossiste : À le technicien du domaine concerné, Cc le commercial attitré). Si la fiche
     prévoit une adresse pour les livraisons / demandes non spécifiques, l'utiliser pour ces
     sujets-là. Sinon, À le contact principal, sans copie.
   - Si Loïc nomme un destinataire précis → seulement celui-là.
   - Si c'est ambigu ou si l'annuaire/le groupe est vide → le dire simplement et demander.
3. **Rassembler les infos** depuis la dictée : matériel ou travaux, quantités / puissances /
   dimensions / références, lieu (commune), type de client (particulier, boucher, GMS… — **pas son
   nom** sauf si Loïc le demande), délai, date limite de retour, pièces jointes prévues (plans,
   photos, cahier des charges). Info essentielle manquante → `[à compléter par Loïc]` dans le mail.
4. **Rédiger un mail par destinataire**, en adaptant :
   - la salutation au contact (prénom/nom, tutoiement ou vouvoiement selon la fiche — vouvoiement
     par défaut) ;
   - le contenu à sa **spécialité** et à ce qu'il **ne fait pas** (cf. fiche) ;
   - une touche personnelle si la fiche a des notes (« comme sur le chantier de septembre »).
5. **Présenter** tous les mails à la suite, puis un récap : à qui on a écrit, et qui n'a pas pu
   être consulté (groupe vide, fiche sans e-mail…).

## Règles de rédaction

- **Statut du projet** : en phase de prix, écrire que Cazal **remet prix / chiffre** le projet.
  Ne **jamais** écrire que le chantier nous est attribué ou que nous en sommes chargés, sauf si Loïc
  dit explicitement que c'est signé.
- Français (sauf si la fiche indique une autre langue), ton pro mais simple et direct, comme Loïc
  parle à des partenaires. Pas de jargon commercial.
- Court : objet clair + 5 à 12 lignes. Infos techniques en liste à puces si plus de 3 éléments.
- Demande de prix **fournisseur** : demander prix, **délai de livraison**, validité de l'offre ;
  rappeler le n° client Cazal s'il est dans la fiche.
- Demande de prix **sous-traitant** : demander prix, **délai d'intervention**, validité de l'offre.
- Mentionner la date limite de retour si Loïc l'a donnée.
- Ne rien inventer (prix, normes, références, dimensions) → `[à vérifier par Loïc]`.
- Si le chiffrage du projet existe dans `dimensionnement/dossiers/<slug>/` (étape 3 faite), la
  demande fournisseur officielle est le PDF de `froid-demande-fournisseur` : ce skill sert alors aux
  mails complémentaires (relance, question, commande), jamais à réécrire la demande.

## Format de sortie (pour chaque destinataire)

```
---
**À :** <e-mail>  ·  <Nom de l'entreprise> — <Contact>
**Cc :** <e-mail(s) en copie, si la fiche en prévoit>
**Objet :** <Demande de prix / Commande / Relance…> – <matériel ou travaux> – <commune>

Bonjour <Prénom / Madame, Monsieur>,

<1 phrase de contexte : Cazal remet prix pour … chez un(e) … à …>

<Le besoin précis pour CE destinataire, en puces si besoin>

<Pièces jointes prévues / visite possible>

<La demande : prix + délais (+ validité)<, idéalement pour le JJ/MM>>

Merci d'avance,

Loïc Cazal
Cazal Réfrigération
```

## Quand une coordonnée manque

Si une fiche n'a pas d'e-mail (ou d'adresse, de site…) mais qu'on connaît le **nom de la société**,
**chercher soi-même sur Internet avant de demander à Loïc**, dans cet ordre :
1. **Essayer directement l'adresse du site** devinée depuis le nom (ex. « Dupont Manutention » →
   `dupont-manutention.be`, `dupontmanutention.be`, en `.be`, `.fr`, `.com`) — si l'e-mail connu a
   un domaine (`@societe.be`), le site est souvent ce domaine.
2. Recherche web avec le nom de la société + la ville ; si les résultats sont vides, refaire la
   recherche dans le navigateur (Google), plus complet que l'outil de recherche.
3. Annuaires d'entreprises (Companyweb, BCE/KBO, Pages d'Or, Societe.com pour la France) — ils
   donnent souvent l'adresse, rarement l'e-mail.
Sur le site trouvé : page Contact, pied de page, mentions légales. Règles :
- Ne retenir qu'une info trouvée sur une source fiable, et dire d'où elle vient.
- Une adresse générique (info@, contact@) est acceptable : le signaler à Loïc.
- Ne **jamais** fabriquer une adresse « probable » (ex. prenom.nom@domaine) sans l'avoir vue écrite.
- Rien trouvé → le dire, et seulement alors demander à Loïc.
- Reporter l'info trouvée dans la fiche de l'annuaire concerné.

## Quand un annuaire évolue

Si Loïc donne un nouveau fournisseur, sous-traitant ou groupe (signature de mail, site, vocal…),
l'ajouter directement dans le bon annuaire de `perso/` avec la fiche modèle, en complétant d'abord
en ligne ce qui manque. La modif est prise en compte immédiatement (pas de zip, pas de mise à jour).

## Modèles des annuaires (pour créer un annuaire absent)

### `perso/fournisseurs.md`

```
# Annuaire des fournisseurs — Cazal Réfrigération

> Fournisseurs à qui Cazal écrit par mail : le matériel sur commande, absent des e-shops.
> Une seule liste, par ordre alphabétique ; la ligne « Points forts » aide à choisir qui consulter.

## Fournisseurs

### Nom de l'entreprise
- **Contacts :** Prénom Nom (fonction — ex. commercial frigo, technico-commercial) · e-mail · téléphone
- **E-mail général :** adresse@exemple.be
- **Téléphone :** +32 …
- **Site :** https://…
- **Agence / zone :** ville de l'agence ou du dépôt
- **Points forts :** ce pour quoi on les consulte en priorité (ex. centrales CO2, évaporateurs, marque X)
- **N° client Cazal :** …
- **Demandes de prix :** **À** <contact commercial> · **Cc** <ingénieur commercial / agence>
- **Langue / ton :** français / néerlandais / anglais, tutoiement ou vouvoiement
- **Notes :** délais habituels, conditions, historique…
```

### `perso/sous-traitants.md`

```
# Annuaire des sous-traitants — Cazal Réfrigération

> Sous-traitants avec qui Cazal travaille, rangés par domaine d'activité.
> Ajouter un groupe : nouveau titre `## Nom du groupe` + une ligne « Pour quoi ».

## Isolation
**Pour quoi :** panneaux sandwich, chambres froides (montage d'enceintes isothermes), isolation de
tuyauteries, portes isothermes, calorifugeage.

## Manutention
**Pour quoi :** levage et grutage (groupes de condensation, CTA, unités en toiture), camion-grue,
nacelle, transport et mise en place de matériel lourd.

## Bureaux d'études
**Pour quoi :** études techniques (dimensionnement, calcul de charges, PEB/EPB, stabilité des
supports en toiture), plans, dossiers pour architectes et marchés publics.

## Dessin technique & plans
**Pour quoi :** plans d'implantation, dessins techniques, vues 3D et rendus, plans de coordination
entre corps de métier. ≠ bureau d'études : pas de calculs ni de dimensionnement frigorifique.

### Nom de l'entreprise (dans son groupe)
- **Contact :** Prénom Nom (fonction)
- **E-mail :** adresse@exemple.be
- **Téléphone :** +32 …
- **Zone :** Belgique / France / les deux
- **Spécialités :** ce qu'ils font précisément (et ce qu'ils ne font pas)
- **Langue / ton :** français, tutoiement ou vouvoiement
- **Notes :** délais habituels, tarif, assurance, historique avec Cazal…
```
