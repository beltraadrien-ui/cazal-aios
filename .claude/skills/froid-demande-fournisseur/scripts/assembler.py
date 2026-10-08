"""froid-demande-fournisseur — étape 3 : assembler demande.json (données de la demande de prix) depuis les étapes 1 et 2.

Lit le dossier d'une installation et écrit <dossier>/3-demande-fournisseur/<vN>/demande.json, que generer_livrable.py
transforme en PDF unique + mail court. Rien n'est envoyé, jamais : Loïc relit et envoie lui-même.

Usage, depuis la racine du dépôt :
    PYTHONUTF8=1 python .claude/skills/froid-demande-fournisseur/scripts/assembler.py <dossier>
        --variante grossiste|fabricant [--destinataire "Prénom Nom, Société"] [--tutoiement] [--version vN]
        [--nommer | --anonymiser] [--date AAAA-MM-JJ] [--delai "d'ici le 20 octobre"] [--emetteur <fichier.json>]
        [--force]
    <dossier> : chemin du dossier, ou son nom dans dimensionnement/dossiers/.
    Variante grossiste : anonymisée par défaut (--nommer pour nommer le client) ; dossier vN/.
    Variante fabricant : nommée par défaut (--anonymiser pour la rendre anonyme) ; dossier vN-fabricant/.
    --version absent : dernier numéro de la variante + 1. Une version existante n'est remplacée qu'avec --force
    (Claude a pu y ajuster des textes).
Codes de sortie : 0 écrit ; 1 refusé (version existante, gabarit invalide, anonymisation incomplète) ;
2 dossier, dossier.md ou 2-resultats.json absent.

Python : from assembler import assembler ; resultat = assembler(dossier, "grossiste", ...) → {"demande", "chemin",
"identifiants", "avertissements", ...}. verifier_schema(demande) rend la liste des écarts au schéma (vide = conforme).

Sources lues (rien n'est écrit en dehors de 3-demande-fournisseur/<vN>/) :
    dossier.md                identité du client (titre, ligne « Client », adresse d'intervention, fiche InterFast)
    sources/structure.json    mêmes identifiants (complément), si présent
    1-existant.md             tableau B (n° de série et photo de chaque compresseur), B2 (plaques d'ensemble et vues),
                              C (chambres, n° de série des évaporateurs, usage), D (régulation, chauffage, locaux),
                              F (index des photos)
    2-resultats.json          TOUS les chiffres : puissances retenues, sous-totaux, volumes, régimes, volumes balayés,
                              rendus par Valeur.texte() (jamais un nombre tapé à la main)
    2-dimensionnement.md      bloc A (ce qu'on remplace, par quoi, marché, qui dessert quoi), bloc E (ce qu'on
                              remplace par poste), bloc F (fournitures : décide quels points de la demande sortent)
    emetteur.json             coordonnées de l'émetteur (Cazal Réfrigération), local, non versionné : <dossier>/
                              emetteur.json, sinon dimensionnement/dossiers/emetteur.json, sinon --emetteur
    sources/photos/           photos (chemins relatifs à la racine du dossier, ex. sources/photos/<nn-poste>/pNN-k.jpeg)
    plan/metre.json           s'il existe (étape P, skill froid-plan-2d, contrat du plan des Lots 5-6 § 11) : longueurs
                              de cuivre par réseau ; seules les familles cuivre_froid et cuivre_clim sont reprises
                              (jamais l'électricité ni les réseaux libres), nombres recopiés tels quels
    plan/plan.pdf             s'il existe : sa page 1 (le plan à l'échelle, A4) est fusionnée à la fin du PDF de la
                              demande par generer_livrable.py (annexes.documents)

Sorties dans 3-demande-fournisseur/<vN>/ :
    demande.json              schéma commun avec generer_livrable.py (ci-dessous)
    identifiants-client.json  identifiants du client recherchés et remplacés (contrôle de l'anonymisation ; local)
    valeurs-derivees.json     les seules valeurs calculées ici (surface = L × l, volume balayé total d'un poste,
                              somme d'une catégorie sans sous-total à l'étape 2), avec formule et entrées, par
                              valeur.calculer / controles.somme : à accepter par le contrôle « chaque nombre du PDF
                              existe dans 2-resultats.json »

Schéma de demande.json (cellules de tableau = textes déjà rendus par Valeur.texte() ; chemins de photos relatifs à la
racine du dossier) :
    {"version", "date", "variante": "grossiste" | "fabricant",
     "destinataire": {"prenom", "nom", "societe", "tutoiement"} | null, "anonymise",
     "emetteur": {"societe", "contact", "telephone", "mail", "adresse"},
     "site": {"nom", "localite", "reference_dossier"} (vides si anonymisé), "titre", "mention",
     "contexte": {"texte"},
     "chambres": {"lignes": [{"chambre", "regime", "surface", "volume", "nb_evaporateurs"}], "note"},
     "production": {"lignes": [{"poste", "compresseurs", "volume_balaye", "puissance", "statut"}],
                    "sous_totaux": [{"libelle", "puissance", "statut"}], "note"},
     "evaporateurs": {"lignes": [{"chambre", "modele", "annee", "puissance"}], "note"} | null (fabricant),
     "longueurs": {"phrase", "reseaux": [{"cle", "nom", "famille", "lignes": [{"troncon", "type_nom", "total_m",
                   "origine"}], "total_m", "origine"}], "diametres", "source": "plan/metre.json", "plan_version"}
                  | {"absentes": true, "phrase": "Longueurs de lignes non relevées, à estimer par vos soins."},
     "demande": {"titre", "intro", "points": [{"lettre", "titre", "texte", "sous_points": [...]}], "resume"},
     "postes": [{"id", "titre", "dessert", "existant": [...], "puissance", "statut", "remplacement",
                 "photos": [{"fichier", "legende", "type": "plaque" | "ensemble"}]}],
     "annexes": {"vues_ensemble": [{"fichier", "legende"}], "plan_implantation": "à suivre" | "plan du local en annexe",
                 "pieces_jointes": [],
                 "documents": [{"type": "plan", "fichier": "../../plan/plan.pdf", "titre", "pages": 1}]},
     "mail": {"objet", "salutation", "corps", "formule", "signature"},
     "exclus_internes": [{"element", "postes": [id du poste…], "texte", "raison"}]}
« longueurs » : familles cuivre_froid et cuivre_clim de plan/metre.json, réseau par réseau (total_m en mètres, nombre
JSON à 2 décimales ; origine « estimee » ou « mesuree » par ligne, « estimee », « mesuree » ou « mixte » par réseau) ;
toute longueur est une estimation d'après le plan, sauf celle mesurée sur chantier par Loïc ; diamètres et charge de
fluide laissés au fournisseur. Sans metre.json (ou sans réseau de cuivre) : {"absentes": true, "phrase": …}.
« annexes.documents » : PDF dont les pages sont ajoutées à la fin de la demande ; « fichier » est relatif au dossier
de la version (3-demande-fournisseur/<vN>/), contrairement aux photos.
« remplacement » d'un poste : les propositions du bloc E qui le concernent (découpage décrit dans _bloc_e : poste,
chambre, marque / modèle / année cités, sinon code de la colonne Existant). « exclus_internes » : les propositions du
bloc E interrogatives ou qui contiennent « à confirmer », « lesquels garder », « ? » : questions pour Loïc, jamais
dans le livrable fournisseur ; Claude les relit à l'étape 4 (elles ne sont ni rendues ni envoyées).
Photos d'un poste : « plaque » = plaque d'un compresseur ou d'un évaporateur ; « ensemble » = plaque d'ensemble
(centrale, condenseur, échangeur : tableau B2 avec une plaque lue). Les vues sans plaque (régulation, condenseurs en
cage, échangeurs, locaux, chambres) vont dans annexes.vues_ensemble. Chaque photo n'apparaît qu'une fois.
Photo d'une plaque : champ « photo » de 2-resultats.json (recopié depuis 2-entrees.json) ; repli : la « photo pNN-k »
citée dans la source du volume balayé (compresseur), de la puissance (plaque d'ensemble) ou de l'évaporateur
(plusieurs photos pour autant d'évaporateurs : rattachées dans l'ordre, avec un avertissement).

Anonymisation (grossiste par défaut) : identifiants lus dans dossier.md et structure.json (nom du client et ses mots
distinctifs, adresse, rue, code postal, localité, téléphone, mail et domaine, n° de fiche InterFast, slug) ; chaque
occurrence est remplacée dans tous les textes et légendes (« le client », « le site », « (localité retirée) »…), jamais
dans les chemins de fichiers ; puis un contrôle relit tout le JSON (hors chemins) et refuse d'écrire si un
identifiant survit.

Mécanisme des textes (templates/textes-grossiste.md, templates/textes-fabricant.md) :
    - « ## clé » ouvre une section (titre, mention, contexte, chambres.note, production.note, evaporateurs.note,
      evaporateurs.puissance, demande.titre, demande.intro, demande.<lettre>, demande.resume, liste.<nom>,
      motif.regulateur.negatif / .positif, mail.objet, mail.salutation, mail.salutation.destinataire, mail.corps,
      mail.formule, mail.signature). Ce qui précède la première section et les commentaires <!-- --> sont ignorés.
    - Lignes : des lignes qui se suivent forment un paragraphe (jointes par une espace) ; une ligne vide sépare deux
      paragraphes. Contexte et corps du mail : paragraphes séparés par une ligne vide ; notes : un seul paragraphe ;
      signature : une ligne par ligne gardée.
    - {champ} : remplacé par une valeur du dossier ; une ligne dont un champ est vide disparaît (ex. pas de marché
      au bloc A → pas de ligne « Marché »). Un champ inconnu est une erreur de gabarit (code 1).
    - [si mot1 / mot2] en début de ligne : ligne gardée si l'un des mots figure (sans accents ni casse) au bloc F,
      au bloc A ou dans le texte du projet de l'étape 2 ; bloc F absent : toutes les conditions sont vraies (avec un
      avertissement). [si poste négatif] / [si poste positif] : s'il existe un tel poste (nom ou « dessert »).
      [tu] / [vous] : selon --tutoiement. Plusieurs conditions se cumulent.
    - {si mot1 / mot2 : texte} dans une ligne : texte inséré si l'un des mots est trouvé ; il commence après « : » et
      une espace.
    - {qte mot1 / mot2} dans une ligne : le nombre écrit juste avant l'un des mots dans le bloc F (« deux soupapes »,
      « 3 portes »), suivi d'une espace ; rien s'il n'y en a pas (la ligne reste, sans quantité inventée).
    - demande.<lettre> : « titre: », « si: » (le point disparaît si aucun mot n'est trouvé), « texte: » (plusieurs
      lignes possibles, jointes), sous-points « - … », éléments « - … » en retrait joints au sous-point qui les
      précède par « ; » (sous-point retiré si aucun élément ne reste). Les lettres sont renumérotées a), b)…
    - liste.<nom> → champ {liste_<nom>} (« a, b et c ») ; motif.regulateur.negatif / .positif : une phrase par
      poste de cette catégorie (champs {chambre}, {les_evaporateurs}), jointes par « ; » → {regulateurs_negatif},
      {regulateurs_positif}.
Champs disponibles : date, version, site_titre, reference_chantier, fluide_actuel, fluide_actuel_note (« R449A (d'après le
rapport ; à confirmer) » si le fluide est une hypothèse), famille_actuelle, fluide_cible,
installation_actuelle, remplace, par_quoi, marche, planning_client, nb_entreprises, planning_cazal (vide : à dicter),
disposition, chiffres_cles, regimes, condensation, note_hypotheses, chambres_resume, regulateurs_negatif,
regulateurs_positif, liste_<nom>, destinataire_prenom, destinataire_nom, delai_reponse, contact,
societe_et_telephone, mail_emetteur, phrase_longueurs (phrase du mail sur les longueurs et le plan joint ; vide sans
plan ni métré : la ligne disparaît).

Dépendances : aucune hors du dépôt (valeur.py et controles.py du skill froid-dimensionnement).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

ICI = Path(__file__).resolve().parent
SKILL = ICI.parent
TEMPLATES = SKILL / "templates"
ROOT = Path(__file__).resolve().parents[4]          # racine du dépôt (…/.claude/skills/<skill>/scripts/)
DOSSIERS = ROOT / "dimensionnement" / "dossiers"
sys.path.insert(0, str(SKILL.parent / "froid-dimensionnement" / "scripts"))
from controles import somme  # noqa: E402
from valeur import HYPOTHESE, SOURCE, Valeur, a_confirmer, calculer, depuis_json  # noqa: E402

GROSSISTE, FABRICANT = "grossiste", "fabricant"
VARIANTES = (GROSSISTE, FABRICANT)
SORTIE = "3-demande-fournisseur"
PLAN_IMPLANTATION = "à suivre"
DELAI_DEFAUT = "dans les meilleurs délais"
EMETTEUR_DEFAUT = {"societe": "Cazal Réfrigération", "contact": "", "telephone": "", "mail": "", "adresse": ""}
CLES_EMETTEUR = ("societe", "contact", "telephone", "mail", "adresse")
NOMS_FLUIDES = {"R744": "CO₂", "CO2": "CO₂"}
NOMBRES_FEMININS = {1: "une", 2: "deux", 3: "trois", 4: "quatre", 5: "cinq", 6: "six", 7: "sept", 8: "huit",
                    9: "neuf", 10: "dix"}
MOIS = ("janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre", "novembre",
        "decembre")
# Mots génériques d'une raison sociale : jamais pris seuls comme identifiant du client.
MOTS_GENERIQUES = {"ets", "etablissements", "etablissement", "sa", "sprl", "srl", "sas", "sarl", "nv", "bv", "scrl",
                   "sc", "asbl", "snc", "eurl", "cie", "compagnie", "societe", "groupe", "group", "the", "de", "des",
                   "du", "la", "le", "les", "et", "and", "fils", "freres"}
DOMAINES_GENERIQUES = {"gmail", "hotmail", "outlook", "yahoo", "live", "icloud", "skynet", "telenet", "proximus",
                       "orange", "free", "voo", "scarlet", "msn", "aol", "protonmail", "wanadoo", "laposte"}
REMPLACEMENTS = {"client": "le client", "adresse": "le site", "rue": "le site", "localite": "(localité retirée)",
                 "code_postal": "(code postal retiré)", "telephone": "(téléphone retiré)",
                 "mail": "(adresse mail retirée)", "fiche": "(référence retirée)"}
CLES_DEMANDE = ("version", "date", "variante", "destinataire", "anonymise", "emetteur", "site", "titre", "mention",
                "contexte", "chambres", "production", "evaporateurs", "longueurs", "demande", "postes", "annexes",
                "mail", "exclus_internes")
CLES_ANNEXES = ("vues_ensemble", "plan_implantation", "pieces_jointes", "documents")

# Lot 7 : longueurs de cuivre et plan du local (étape P, skill froid-plan-2d ; contrat plan/metre.json)
PLAN = "plan"
FAMILLES_CUIVRE = ("cuivre_froid", "cuivre_clim")
FAMILLES_METRE = FAMILLES_CUIVRE + ("electricite", "libre")
ORIGINES_LIGNE = ("estimee", "mesuree")
ORIGINES_TOTAL = ("estimee", "mesuree", "mixte")
PHRASE_ESTIMATION = ("Toutes les longueurs sont des estimations d'après le plan (tracé et hauteurs de pose), sauf "
                     "celles marquées « (mesurée) », relevées sur chantier.")
PHRASE_NON_RELEVEES = "Longueurs de lignes non relevées, à estimer par vos soins."
PHRASE_DIAMETRES = "Diamètres et charge de fluide à définir par vos soins."
SOURCE_METRE = "plan/metre.json"
TITRE_ANNEXE_PLAN = "Plan du local (A4, échelle écrite sur le plan)"
PLAN_EN_ANNEXE = "plan du local en annexe"
A4_PT = (595.28, 841.89)
TOLERANCE_A4_PT = 3.0
# Phrase du mail selon (longueurs présentes, plan joint) ; vide : la ligne du gabarit disparaît.
PHRASES_MAIL = {(True, True): "Les longueurs de cuivre estimées d'après le plan figurent dans le PDF, avec le plan du "
                              "local en annexe.",
                (True, False): "Les longueurs de cuivre estimées d'après le plan figurent dans le PDF.",
                (False, True): "Le plan du local figure en annexe du PDF.",
                (False, False): ""}


class Refus(Exception):
    """Demande impossible (code de sortie 1)."""


class SourceAbsente(Exception):
    """Dossier ou fichier indispensable absent (code de sortie 2)."""


# =====================================================================================================
# Outils de texte
# =====================================================================================================
def _norm(texte: Any) -> str:
    """Sans accents, minuscules, espaces simples (comparaisons et recherches)."""
    t = unicodedata.normalize("NFKD", "" if texte is None else str(texte))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.replace(" ", " ").replace(" ", " ")).strip().lower()


def _propre(texte: Any) -> str:
    """Texte d'une cellule ou d'une puce markdown : gras, code et <br> retirés, espaces simples."""
    t = str(texte or "").replace("**", "").replace("`", "")
    t = re.sub(r"\s*<br\s*/?>\s*", " ; ", t)
    t = t.replace("\\|", "|")
    return re.sub(r"[ \t]+", " ", t).strip()


_REFS_INTERNES = re.compile(r"G\d|question|bloc |\.md|§|lo[iï]c|regles-|methodes/|transitions", re.I)


def _sans_refs_internes(texte: str) -> str:
    """Retire les parenthèses qui renvoient au fonctionnement interne (« (G3, question 11) », « (à confirmer avec
    Loïc) », fichiers .md) : sans objet pour un fournisseur."""
    t = texte
    while True:
        nouveau = re.sub(r"\s*\(([^()]*)\)", lambda m: "" if _REFS_INTERNES.search(m.group(1)) else m.group(0), t)
        if nouveau == t:
            break
        t = nouveau
    return re.sub(r"\s+([,.])", r"\1", re.sub(r"[ \t]+", " ", t)).strip()


def _sans_parentheses_chiffrees(texte: str) -> str:
    """Retire les parenthèses qui contiennent des chiffres (lectures d'afficheur, repères) : légendes courtes."""
    t = texte
    while True:
        nouveau = re.sub(r"\s*\([^()]*\d[^()]*\)", "", t)
        if nouveau == t:
            break
        t = nouveau
    return re.sub(r"[ \t]+", " ", t).strip()


def _segments(texte: str, sep: str = ";") -> list[str]:
    """Découpe sur le séparateur hors parenthèses et guillemets."""
    morceaux, courant, prof = [], [], 0
    for ch in texte:
        if ch in "(«":
            prof += 1
        elif ch in ")»":
            prof = max(0, prof - 1)
        if ch == sep and prof == 0:
            morceaux.append("".join(courant).strip())
            courant = []
        else:
            courant.append(ch)
    morceaux.append("".join(courant).strip())
    return [m for m in morceaux if m]


def _couper(texte: str, n: int = 160) -> str:
    """Coupe un texte trop long à une limite de mot, avec « … »."""
    if len(texte) <= n:
        return texte
    coupe = texte[:n].rsplit(" ", 1)[0].rstrip(",;: ")
    return coupe + " …"


def _couper_elements(texte: str, n: int = 160) -> str:
    """Texte trop long coupé après le dernier élément entier (« , » hors parenthèses et guillemets) qui tient dans n
    caractères ; un premier élément trop long est coupé à une limite de mot (_couper)."""
    if len(texte) <= n:
        return texte
    garde = ""
    for el in _segments(texte, ","):
        essai = f"{garde}, {el}" if garde else el
        if len(essai) > n:
            break
        garde = essai
    return garde or _couper(texte, n)


def _majuscule(texte: str) -> str:
    for i, c in enumerate(texte):
        if c.isalpha():
            return texte[:i] + c.upper() + texte[i + 1:]
    return texte


def _minuscule_initiale(texte: str) -> str:
    """« Les deux centrales… » → « les deux centrales… » (sauf sigle : « HFC… » reste tel quel)."""
    if len(texte) > 1 and texte[0].isupper() and not texte[1].isupper():
        return texte[0].lower() + texte[1:]
    return texte


def _liste_fr(elements: list[str]) -> str:
    el = [e for e in elements if e]
    if len(el) <= 1:
        return "".join(el)
    return ", ".join(el[:-1]) + " et " + el[-1]


def _refs(texte: Any) -> list[str]:
    """Références de photos citées (« p11-3 »), dans l'ordre, sans doublon."""
    vues = []
    for r in re.findall(r"(?<![A-Za-z0-9])(p\d{2}-\d+)", str(texte or "")):
        if r not in vues:
            vues.append(r)
    return vues


def _titre_poste(texte: str) -> str:
    """« CENTRALE NÉGATIVE B » (titre InterFast) → « Centrale négative B »."""
    t = str(texte or "").strip()
    if t.isupper():
        mots = t.lower().split()
        mots = [m.upper() if len(m) == 1 and m.isalpha() and i == len(mots) - 1 else m for i, m in enumerate(mots)]
        t = " ".join(mots)
    return _majuscule(t)


# =====================================================================================================
# Markdown : sections, tableaux, puces
# =====================================================================================================
def section_md(texte: str, prefixe: str) -> str:
    """Contenu d'une section (de son titre au titre suivant de même niveau ou plus haut) ; « » si absente."""
    lignes = texte.split("\n")
    for i, l in enumerate(lignes):
        if l.startswith(prefixe):
            niveau = len(l) - len(l.lstrip("#"))
            fin = len(lignes)
            for j in range(i + 1, len(lignes)):
                m = re.match(r"^(#+)\s", lignes[j])
                if m and len(m.group(1)) <= niveau:
                    fin = j
                    break
            return "\n".join(lignes[i + 1:fin])
    return ""


def _cellules(ligne: str) -> list[str]:
    s = ligne.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def tableau_md(texte: str) -> list[dict]:
    """Premier tableau markdown du texte : une liste de lignes {en-tête: cellule}."""
    entete, lignes = None, []
    for l in texte.split("\n"):
        if not l.strip().startswith("|"):
            if entete is not None:
                break
            continue
        cells = _cellules(l)
        if entete is None:
            entete = cells
            continue
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        cells += [""] * (len(entete) - len(cells))
        lignes.append(dict(zip(entete, cells)))
    return lignes


def _col(ligne: dict | None, *mots: str) -> str:
    """Cellule de la colonne dont l'en-tête vaut l'un des mots, sinon de la première qui le contient (sans accents
    ni casse)."""
    if not ligne:
        return ""
    for k, v in ligne.items():
        if _norm(k) in mots:
            return v
    for k, v in ligne.items():
        if any(m in _norm(k) for m in mots):
            return v
    return ""


def puces_md(texte: str) -> list[str]:
    return [_propre(l[2:]) for l in texte.split("\n") if l.startswith("- ")]


# =====================================================================================================
# Lecture du dossier
# =====================================================================================================
@dataclass
class Sources:
    dossier: Path
    resultats: dict
    dossier_md: str = ""
    existant_md: str = ""
    dim_md: str = ""
    structure: dict = field(default_factory=dict)
    photos: dict = field(default_factory=dict)          # réf « p11-3 » → « sources/photos/…/p11-3.jpeg »
    avertissements: list = field(default_factory=list)


def _lire(chemin: Path) -> str:
    return chemin.read_text(encoding="utf-8") if chemin.is_file() else ""


def _cle_photo(chemin: str) -> tuple:
    m = re.search(r"/(\d+)-[^/]*/p(\d+)-(\d+)\.", chemin)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (999, 999, 999)


def lire_sources(dossier: Path) -> Sources:
    if not dossier.is_dir():
        raise SourceAbsente(f"dossier introuvable : {dossier}")
    chemin_res = dossier / "2-resultats.json"
    if not chemin_res.is_file():
        raise SourceAbsente(f"{chemin_res} absent : lancer d'abord l'étape 2 (calculs.py du skill froid-dimensionnement)")
    if not (dossier / "dossier.md").is_file():
        raise SourceAbsente(f"{dossier / 'dossier.md'} absent : identité du client inconnue, anonymisation impossible")
    s = Sources(dossier=dossier, resultats=depuis_json(chemin_res.read_text(encoding="utf-8")))
    s.dossier_md = _lire(dossier / "dossier.md")
    s.existant_md = _lire(dossier / "1-existant.md")
    s.dim_md = _lire(dossier / "2-dimensionnement.md")
    if not s.existant_md:
        s.avertissements.append("1-existant.md absent : n° de série, plaques d'ensemble et légendes des vues "
                                "« à confirmer »")
    if not s.dim_md:
        s.avertissements.append("2-dimensionnement.md absent : blocs A, E, F indisponibles (textes par défaut)")
    try:
        s.structure = json.loads(_lire(dossier / "sources" / "structure.json") or "{}")
    except json.JSONDecodeError:
        s.avertissements.append("sources/structure.json illisible : ignoré")
    racine = dossier / "sources" / "photos"
    if racine.is_dir():
        for f in sorted(racine.glob("*/*")):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                s.photos.setdefault(f.stem, f.relative_to(dossier).as_posix())
    s.photos = dict(sorted(s.photos.items(), key=lambda kv: _cle_photo(kv[1])))
    return s


# =====================================================================================================
# Identifiants du client et anonymisation
# =====================================================================================================
_RE_TEL = re.compile(r"^\+?[\d][\d\s./-]{6,}\d$")


def lire_identifiants(dossier_md: str, structure: dict, slug: str) -> dict:
    """Nom, adresse, rue, code postal, localité, téléphone, mail, fiche InterFast, lus dans dossier.md (titre, ligne
    « Client », « Adresse d'intervention ») et sources/structure.json."""
    noms, adresses, tels, mails, fiches = [], [], [], [], []
    m = re.search(r"^#\s+Dossier\s+(.+?)\s+—", dossier_md, re.M)
    if m:
        noms.append(m.group(1).strip())
    fiches += re.findall(r"fiche InterFast\s+([A-Z]{1,4}\d{3,})", dossier_md)
    m = re.search(r"\*\*Client\*\*\s*:\s*(.+)$", dossier_md, re.M)
    if m:
        parties = [p.strip() for p in m.group(1).split(" · ")]
        tete = [p.strip() for p in parties[0].split(" — ")]
        noms.append(tete[0])
        adresses += tete[1:]
        for p in parties[1:]:
            (mails if "@" in p else tels if _RE_TEL.match(p) else adresses).append(p)
    m = re.search(r"\*\*Adresse d'intervention\*\*\s*:\s*(.+)$", dossier_md, re.M)
    if m:
        adresses.append(m.group(1).strip())
    client = (structure or {}).get("client") or {}
    if client.get("nom"):
        noms.append(client["nom"])
    for l in client.get("lignes") or []:
        l = str(l).strip()
        if not l or l in noms:
            continue
        (mails if "@" in l else tels if _RE_TEL.match(l) else adresses).append(l)
    if ((structure or {}).get("intervention") or {}).get("adresse"):
        adresses.append(structure["intervention"]["adresse"])
    if (structure or {}).get("fiche"):
        fiches.append(str(structure["fiche"]))

    def uniques(liste):
        vus = []
        for x in liste:
            x = re.sub(r"\s+", " ", str(x)).strip()
            if x and x not in vus:
                vus.append(x)
        return vus

    noms, adresses, tels, mails, fiches = map(uniques, (noms, adresses, tels, mails, fiches))
    rues, codes, localites = [], [], []
    for a in adresses:
        m = re.search(r"^(.*?)[\s,]*\b(\d{4,5})\s+([^\d,]+?)\s*$", a)
        if m:
            if m.group(1).strip():
                rues.append(m.group(1).strip(" ,"))
            codes.append(m.group(2))
            localites.append(m.group(3).strip())
    mots = []
    for n in noms:
        for mot in re.findall(r"[\w'’-]+", n):
            if len(mot) >= 3 and _norm(mot) not in MOTS_GENERIQUES and not mot.isdigit() and mot not in mots:
                mots.append(mot)
    domaines = []
    for ml in mails:
        dom = ml.split("@", 1)[1].strip().lower()
        if dom.split(".")[0] not in DOMAINES_GENERIQUES:
            domaines.append(dom)
            if len(dom.split(".")[0]) >= 4:
                domaines.append(dom.split(".")[0])
    nom_slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", slug or "")
    return {"client": noms[0] if noms else "", "noms": noms, "mots_distinctifs": mots, "adresses": adresses,
            "rues": uniques(rues), "codes_postaux": uniques(codes), "localites": uniques(localites),
            "telephones": tels, "mails": mails, "domaines_mail": uniques(domaines), "fiches": fiches,
            "slug": nom_slug}


_VARIANTES_LETTRES = {"a": "aàâäáAÀÂÄÁ", "e": "eéèêëEÉÈÊË", "i": "iîïíIÎÏÍ", "o": "oôöóOÔÖÓ", "u": "uùûüúUÙÛÜÚ",
                      "c": "cçCÇ", "y": "yÿYŸ", "n": "nñNÑ"}


def _motif_regex(texte: str, telephone: bool = False) -> re.Pattern:
    """Motif tolérant : casse, accents, espaces et tirets variables ; bornes de mot aux deux extrémités."""
    if telephone:
        chiffres = re.sub(r"\D", "", texte)
        corps = r"[\s./-]*".join(re.escape(c) for c in chiffres)
        return re.compile(rf"(?<!\d){corps}(?!\d)")
    morceaux = []
    for ch in texte:
        base = _norm(ch)
        if ch.isspace() or ch in "-–—":
            morceaux.append(r"[\s  \-–—]+")
        elif base in _VARIANTES_LETTRES:
            morceaux.append("[" + _VARIANTES_LETTRES[base] + "]")
        elif ch.isalpha():
            morceaux.append("[" + re.escape(ch.lower()) + re.escape(ch.upper()) + "]")
        else:
            morceaux.append(re.escape(ch))
    corps = "".join(morceaux)
    return re.compile(rf"(?<![\w]){corps}(?![\w])")


def motifs_anonymisation(ids: dict) -> list[tuple[str, str, re.Pattern]]:
    """(identifiant, remplacement, motif), du plus long au plus court."""
    paires = []
    for a in ids["adresses"]:
        paires.append((a, REMPLACEMENTS["adresse"], False))
    for r in ids["rues"]:
        paires.append((r, REMPLACEMENTS["rue"], False))
    for ml in ids["mails"]:
        paires.append((ml, REMPLACEMENTS["mail"], False))
    for d in ids["domaines_mail"]:
        paires.append((d, REMPLACEMENTS["mail"], False))
    for t in ids["telephones"]:
        paires.append((t, REMPLACEMENTS["telephone"], True))
    for n in ids["noms"]:
        paires.append((n, REMPLACEMENTS["client"], False))
    if ids.get("slug"):
        paires.append((ids["slug"], REMPLACEMENTS["client"], False))
    for m in ids["mots_distinctifs"]:
        paires.append((m, REMPLACEMENTS["client"], False))
    for loc in ids["localites"]:
        paires.append((loc, REMPLACEMENTS["localite"], False))
    for c in ids["codes_postaux"]:
        paires.append((c, REMPLACEMENTS["code_postal"], False))
    for f in ids["fiches"]:
        paires.append((f, REMPLACEMENTS["fiche"], False))
    vus, res = set(), []
    for texte, rempl, tel in sorted(paires, key=lambda p: -len(p[0])):
        if texte and texte not in vus:
            vus.add(texte)
            res.append((texte, rempl, _motif_regex(texte, tel)))
    return res


def _remplacer(texte: str, motifs: list) -> str:
    for _, rempl, motif in motifs:
        texte = motif.sub(rempl, texte)
    texte = re.sub(r"(^|[.!?]\s+)(le client|le site)", lambda m: m.group(1) + _majuscule(m.group(2)), texte)
    return texte


def anonymiser(obj: Any, motifs: list, cle: str = "") -> Any:
    """Remplace les identifiants dans toutes les chaînes, sauf les chemins de fichiers (clé « fichier »)."""
    if isinstance(obj, dict):
        return {k: anonymiser(v, motifs, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [anonymiser(v, motifs, cle) for v in obj]
    if isinstance(obj, str) and cle != "fichier":
        return _remplacer(obj, motifs)
    return obj


def identifiants_restants(obj: Any, motifs: list, cle: str = "") -> list[str]:
    """Identifiants encore présents (hors chemins de fichiers)."""
    trouves = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            trouves += identifiants_restants(v, motifs, k)
    elif isinstance(obj, list):
        for v in obj:
            trouves += identifiants_restants(v, motifs, cle)
    elif isinstance(obj, str) and cle != "fichier":
        trouves += [texte for texte, _, motif in motifs if motif.search(obj)]
    return trouves


# =====================================================================================================
# Gabarits de textes
# =====================================================================================================
RE_CONDITION = re.compile(r"^\[([^\]]+)\]\s*")
RE_SI = re.compile(r"\{si ([^{}:]+?) : ([^{}]*)\}")
RE_CHAMP = re.compile(r"\{([a-z_]+)\}")
RE_CLE_POINT = re.compile(r"^(titre|si|texte)\s*:\s?(.*)$")
RE_QTE = re.compile(r"\{qte ([^{}]+?)\}")
_NOMBRES_ECRITS = r"\d+|une?|deux|trois|quatre|cinq|six|sept|huit|neuf|dix"


def RE_QUANTITE(mot: str) -> re.Pattern:
    return re.compile(rf"(?<![\w,.])({_NOMBRES_ECRITS})\s+{re.escape(mot)}")


@dataclass
class Contexte:
    champs: dict
    corpus: str                  # bloc F + bloc A + projet, normalisé
    corpus_present: bool
    tutoiement: bool
    categories: set
    bloc_f: str = ""             # bloc F seul, normalisé (quantités dictées par Loïc)

    def trouve(self, mots: str) -> bool:
        if not self.corpus_present:
            return True
        return any(_norm(m) and _norm(m) in self.corpus for m in mots.split("/"))

    def quantite(self, mots: str) -> str:
        """Nombre écrit juste avant l'un des mots dans le bloc F (« deux soupapes », « 3 portes »), tel qu'écrit ;
        « » s'il n'y en a pas (on n'invente jamais une quantité)."""
        for mot in mots.split("/"):
            m = RE_QUANTITE(_norm(mot)).search(self.bloc_f) if _norm(mot) else None
            if m:
                return m.group(1)
        return ""

    def avec(self, **champs) -> "Contexte":
        return replace(self, champs={**self.champs, **champs})


class Gabarit:
    """Textes par défaut d'une variante (templates/textes-<variante>.md)."""

    def __init__(self, chemin: Path):
        if not chemin.is_file():
            raise Refus(f"gabarit introuvable : {chemin}")
        texte = re.sub(r"<!--.*?-->", "", chemin.read_text(encoding="utf-8"), flags=re.S)
        self.chemin = chemin
        self.sections: dict[str, list[str]] = {}
        cle = None
        for ligne in texte.split("\n"):
            m = re.match(r"^## (\S+)\s*$", ligne)
            if m:
                cle = m.group(1)
                self.sections[cle] = []
            elif cle is not None:
                self.sections[cle].append(ligne.rstrip())
        for k, v in self.sections.items():
            while v and not v[0].strip():
                v.pop(0)
            while v and not v[-1].strip():
                v.pop()

    def a(self, cle: str) -> bool:
        return cle in self.sections

    def _lignes(self, cle: str) -> list[str]:
        if cle not in self.sections:
            raise Refus(f"{self.chemin.name} : section « ## {cle} » absente")
        return self.sections[cle]

    # --- une ligne : conditions, conditions en ligne, champs -------------------------------------------
    def _conditions(self, ligne: str, ctx: Contexte) -> tuple[bool, str]:
        ok = True
        while True:
            m = RE_CONDITION.match(ligne)
            if not m:
                return ok, ligne
            ligne = ligne[m.end():]
            c = _norm(m.group(1))
            if c == "tu":
                ok = ok and ctx.tutoiement
            elif c == "vous":
                ok = ok and not ctx.tutoiement
            elif c.startswith("si poste "):
                ok = ok and c[len("si poste "):] in ctx.categories
            elif c.startswith("si "):
                ok = ok and ctx.trouve(m.group(1).strip()[3:])
            else:
                raise Refus(f"{self.chemin.name} : condition inconnue « [{m.group(1)}] »")

    def _remplir(self, ligne: str, ctx: Contexte) -> str | None:
        ligne = RE_SI.sub(lambda m: m.group(2) if ctx.trouve(m.group(1)) else "", ligne)
        ligne = RE_QTE.sub(lambda m: (q + " ") if (q := ctx.quantite(m.group(1))) else "", ligne)
        vide = False

        def champ(m):
            nonlocal vide
            k = m.group(1)
            if k not in ctx.champs:
                raise Refus(f"{self.chemin.name} : champ inconnu « {{{k}}} »")
            v = ctx.champs[k]
            if not v:
                vide = True
            return str(v)

        ligne = RE_CHAMP.sub(champ, ligne)
        if vide:
            return None
        ligne = re.sub(r"[ \t]+", " ", ligne).strip()
        return ligne or None

    def ligne(self, brute: str, ctx: Contexte) -> str | None:
        ok, reste = self._conditions(brute.strip(), ctx)
        return self._remplir(reste, ctx) if ok else None

    # --- sections de texte ---------------------------------------------------------------------------------
    def texte(self, cle: str, ctx: Contexte, mode: str = "paragraphes") -> str:
        """mode « paragraphes » (séparés par une ligne vide), « phrases » (un seul paragraphe) ou « lignes »."""
        paragraphes, courant, gardees = [], [], []
        for l in self._lignes(cle) + [""]:
            if not l.strip():
                if courant:
                    paragraphes.append(" ".join(courant))
                    courant = []
                continue
            r = self.ligne(l, ctx)
            if r:
                courant.append(r)
                gardees.append(r)
        if mode == "lignes":
            return "\n".join(gardees)
        return (" " if mode == "phrases" else "\n\n").join(paragraphes)

    def liste(self, cle: str, ctx: Contexte) -> list[str]:
        res = []
        for l in self._lignes(cle):
            if l.startswith("- "):
                r = self.ligne(l[2:], ctx)
                if r:
                    res.append(r)
        return res

    def point(self, cle: str, ctx: Contexte) -> dict | None:
        """Un point de la demande : {"titre", "texte", "sous_points"} ou None s'il ne s'applique pas au dossier."""
        titre, si, textes, sous = None, None, [], []
        parent = None                    # [texte rendu | None, enfants définis ?, enfants rendus]
        for l in self._lignes(cle):
            if not l.strip():
                continue
            if re.match(r"^\s+- ", l):
                if parent is not None:
                    parent[1] = True
                    if parent[0] is not None:
                        r = self.ligne(l.strip()[2:], ctx)
                        if r:
                            parent[2].append(r)
                continue
            if l.startswith("- "):
                parent = [self.ligne(l[2:], ctx), False, []]
                sous.append(parent)
                continue
            m = RE_CLE_POINT.match(l.strip())
            if m and m.group(1) == "titre":
                titre = self.ligne(m.group(2), ctx)
                if titre is None:
                    return None
            elif m and m.group(1) == "si":
                si = m.group(2)
            else:
                r = self.ligne(m.group(2) if m else l, ctx)
                if r:
                    textes.append(r)
        if si is not None and not ctx.trouve(si):
            return None
        sous_points = []
        for texte, a_enfants, enfants in sous:
            if texte is None:
                continue
            if a_enfants:
                if not enfants:
                    continue
                texte = f"{texte} {' ; '.join(enfants)}"
                if not texte.endswith((".", "!", "?")):
                    texte += "."
            sous_points.append(texte)
        return {"titre": titre or "", "texte": _majuscule(" ".join(textes)), "sous_points": sous_points}


# =====================================================================================================
# Données de l'étape 2
# =====================================================================================================
def categorie(poste: dict) -> str | None:
    """« négatif » / « positif » d'après le nom et la chambre desservie ; None si on ne sait pas."""
    t = _norm(f"{poste.get('nom', '')} {((poste.get('dessert') or {}).get('texte') or '')}")
    if "negati" in t or "congel" in t:
        return "négatif"
    if "positi" in t:
        return "positif"
    return None


def nom_chambre(poste: dict) -> str:
    d = ((poste.get("dessert") or {}).get("texte") or "").strip()
    return d.split(",")[0].strip() if d else poste.get("nom", "")


def _fluide_aff(nom: str) -> str:
    return NOMS_FLUIDES.get(str(nom).upper().replace(" ", ""), nom)


def _v(x: Any) -> Valeur | None:
    return x if isinstance(x, Valeur) else None


def totaux_categories(res: dict, derivees: list) -> list[dict]:
    """Puissance existante par catégorie (négatif, positif), depuis les sous-totaux de l'étape 2 ou le poste seul."""
    postes = res.get("postes") or []
    ordre = []
    for p in postes:
        c = categorie(p)
        if c not in ordre:
            ordre.append(c)
    ordre.sort(key=lambda c: {"négatif": 0, "positif": 1}.get(c, 2))
    groupes = []
    for c in ordre:
        prs = [p for p in postes if categorie(p) == c]
        if c is None:
            groupes += [{"categorie": None, "libelle": p["nom"], "postes": [p]} for p in prs]
        else:
            groupes.append({"categorie": c, "libelle": c, "postes": prs})
    for g in groupes:
        prs, ids = g["postes"], {p["id"] for p in g["postes"]}
        if len(prs) == 1:
            g["valeur"] = prs[0]["existante"]
        else:
            st = next((s for s in res.get("sous_totaux") or [] if set(s.get("postes") or []) == ids), None)
            if st is not None:
                g["valeur"] = st["existante"]
            else:
                g["valeur"] = somme([p["existante"] for p in prs], "kW", id=f"total-{_norm(g['libelle'])}",
                                    source=f"somme des puissances existantes des postes {', '.join(sorted(ids))} "
                                           "(assembler.py, pas de sous-total commun à l'étape 2)")
                derivees.append(g["valeur"])
        t0s = {p["regime"]["t0"].nombre for p in prs}
        tcs = {p["regime"]["tc"].nombre for p in prs}
        g["t0"] = prs[0]["regime"]["t0"] if len(t0s) == 1 else None
        g["tc"] = prs[0]["regime"]["tc"] if len(tcs) == 1 else None
    return groupes


def _temp(v: Valeur | None) -> str:
    return v.texte(0, marque=False) if v is not None else "à confirmer"


# =====================================================================================================
# Tableaux de 1-existant.md
# =====================================================================================================
@dataclass
class Releve:
    b: list
    b2: list
    c: list
    d: list
    f: list


def lire_releve(existant_md: str) -> Releve:
    if not existant_md:
        return Releve([], [], [], [], [])
    sec_b = section_md(existant_md, "## B.")
    return Releve(b=tableau_md(sec_b), b2=tableau_md(section_md(existant_md, "### B2.")),
                  c=tableau_md(section_md(existant_md, "## C.")), d=tableau_md(section_md(existant_md, "## D.")),
                  f=tableau_md(section_md(existant_md, "## F.")))


def _b2_est_plaque(ligne: dict) -> bool:
    """Ligne B2 avec une plaque lue (sinon : vue d'ensemble)."""
    lecture = _norm(_propre(_col(ligne, "lecture")))
    plaque = _norm(_propre(_col(ligne, "plaque")))
    if lecture in ("", "—", "-", "a confirmer") or plaque in ("", "—", "-"):
        return False
    return not plaque.startswith(("vue d'ensemble", "plaque non photographiee", "plaques d'ensemble non lisibles"))


def _serie_evaporateur(releve: Releve, ev: dict, refs: list[str], rang: int) -> str:
    """N° de série d'un évaporateur, lu au tableau C (segment qui cite son modèle)."""
    cle_modele = re.sub(r"\s+", "", _norm(ev.get("modele")))
    if not cle_modele:
        return ""
    lignes = [l for l in releve.c if any(r in _col(l, "source") for r in refs)] or releve.c
    for l in lignes:
        for seg in _segments(_propre(_col(l, "evaporateur")), ";"):
            if cle_modele in re.sub(r"\s+", "", _norm(seg)):
                series = []
                m = re.search(r"n°\s*([^\s,;()]+)((?:\s+et\s+[^\s,;()]+)*)", seg)
                if m:
                    series = [m.group(1)] + re.findall(r"\s+et\s+([^\s,;()]+)", m.group(2))
                else:
                    m = re.search(r"fabr\.\s*([^\s,;()]+)", seg)
                    if m:
                        series = [m.group(1)]
                if series:
                    return series[min(rang, len(series) - 1)]
    return ""


# =====================================================================================================
# Plan du local et longueurs de cuivre (plan/metre.json, plan/plan.pdf)
# =====================================================================================================
def _longueur_ok(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x >= 0


def ecarts_metre(m: Any) -> list[str]:
    """Écarts de plan/metre.json au contrat (vide = conforme). Les lignes ne sont vérifiées que pour les réseaux de
    cuivre, les seuls repris : un réseau d'électricité mal formé ne bloque pas la demande."""
    if not isinstance(m, dict):
        return ["objet JSON attendu"]
    err = []
    if m.get("version") != 1:
        err.append(f"version {m.get('version')!r} (attendue : 1)")
    if not isinstance(m.get("reseaux"), list):
        return err + ["« reseaux » : liste attendue"]
    for i, r in enumerate(m["reseaux"], 1):
        if not isinstance(r, dict):
            err.append(f"réseau {i} : objet attendu")
            continue
        if r.get("famille") not in FAMILLES_CUIVRE:
            continue
        ou = f"réseau {i} ({r.get('cle') or '?'})"
        for k in ("cle", "nom"):
            if not isinstance(r.get(k), str) or not r[k].strip():
                err.append(f"{ou} : « {k} » texte non vide attendu")
        if not _longueur_ok(r.get("total_m")):
            err.append(f"{ou} : « total_m » nombre positif attendu, reçu {r.get('total_m')!r}")
        if not isinstance(r.get("lignes"), list):
            err.append(f"{ou} : « lignes » liste attendue")
            continue
        for j, l in enumerate(r["lignes"], 1):
            if not isinstance(l, dict):
                err.append(f"{ou}, ligne {j} : objet attendu")
                continue
            for k in ("troncon", "type_nom"):
                if not isinstance(l.get(k), str) or not l[k].strip():
                    err.append(f"{ou}, ligne {j} : « {k} » texte non vide attendu")
            if not _longueur_ok(l.get("total_m")):
                err.append(f"{ou}, ligne {j} : « total_m » nombre positif attendu, reçu {l.get('total_m')!r}")
            if l.get("origine") not in ORIGINES_LIGNE:
                err.append(f"{ou}, ligne {j} : origine {l.get('origine')!r} (attendue : estimee ou mesuree)")
    return err


def lire_metre(dossier: Path) -> dict | None:
    """plan/metre.json relu et vérifié (Refus s'il est illisible ou hors contrat) ; None s'il n'existe pas."""
    chemin = Path(dossier) / PLAN / "metre.json"
    if not chemin.is_file():
        return None
    try:
        m = json.loads(chemin.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise Refus(f"{chemin} illisible ({e}) : relancer generer.py du skill froid-plan-2d") from None
    err = ecarts_metre(m)
    if err:
        raise Refus(f"{chemin} hors contrat : " + " ; ".join(err))
    return m


def origine_totale(lignes: list[dict]) -> str:
    """« mesuree » si toutes les lignes sont mesurées, « estimee » si aucune, « mixte » sinon."""
    mesurees = sum(1 for l in lignes if l["origine"] == "mesuree")
    return "mesuree" if mesurees == len(lignes) else "estimee" if mesurees == 0 else "mixte"


def longueurs_depuis_metre(metre: dict | None, avert: list) -> dict:
    """Champ « longueurs » de demande.json : réseaux de cuivre (froid, clim) de metre.json, chiffres recopiés ;
    {"absentes": true, …} sans metre.json ou sans réseau de cuivre."""
    if metre is None:
        return {"absentes": True, "phrase": PHRASE_NON_RELEVEES}
    reseaux = []
    for r in metre["reseaux"]:
        famille = r.get("famille") if isinstance(r, dict) else None
        if famille not in FAMILLES_CUIVRE:
            if famille not in FAMILLES_METRE:
                avert.append(f"plan/metre.json : réseau « {(r or {}).get('cle')} » de famille inconnue "
                             f"« {famille} », non repris")
            continue
        lignes = [{"troncon": l["troncon"].strip(), "type_nom": l["type_nom"].strip(),
                   "total_m": round(float(l["total_m"]), 2), "origine": l["origine"]} for l in r["lignes"]]
        if not lignes:
            continue
        total = round(float(r["total_m"]), 2)
        somme_lignes = sum(l["total_m"] for l in lignes)
        if abs(somme_lignes - total) > 0.005 * len(lignes) + 0.005:
            avert.append(f"plan/metre.json, réseau « {r['cle']} » : total {total:.2f} m, somme des lignes "
                         f"{somme_lignes:.2f} m (repris tels quels ; à vérifier côté plan)")
        reseaux.append({"cle": r["cle"], "nom": r["nom"].strip(), "famille": famille, "lignes": lignes,
                        "total_m": total, "origine": origine_totale(lignes)})
    if not reseaux:
        avert.append("plan/metre.json ne contient aucun réseau de cuivre (froid ou clim) : longueurs « non relevées »")
        return {"absentes": True, "phrase": PHRASE_NON_RELEVEES}
    if metre.get("hauteurs_validees") is False:
        avert.append("plan/metre.json : hauteurs de pose pas encore validées par Loïc (longueurs estimées sous "
                     "hypothèses de hauteur)")
    pv = metre.get("plan_version")
    return {"phrase": str(metre.get("phrase") or PHRASE_ESTIMATION).strip(), "reseaux": reseaux,
            "diametres": PHRASE_DIAMETRES, "source": SOURCE_METRE,
            "plan_version": pv if isinstance(pv, int) and not isinstance(pv, bool) else None}


def est_a4(largeur: float, hauteur: float) -> bool:
    """Page A4 (portrait ou paysage), à TOLERANCE_A4_PT près."""
    petit, grand = sorted((largeur, hauteur))
    return abs(petit - A4_PT[0]) <= TOLERANCE_A4_PT and abs(grand - A4_PT[1]) <= TOLERANCE_A4_PT


def annexe_plan(dossier: Path, sortie: Path, avert: list) -> dict | None:
    """Annexe « plan du local » (page 1 de plan/plan.pdf) si le fichier existe et s'ouvre ; chemin relatif au dossier
    de la version."""
    plan = Path(dossier) / PLAN / "plan.pdf"
    if not plan.is_file():
        return None
    try:
        import pymupdf
        with pymupdf.open(plan) as doc:
            if doc.page_count < 1:
                raise ValueError("aucune page")
            rect = doc[0].rect
    except Exception as e:                                  # PDF tronqué, pas un PDF
        avert.append(f"plan/plan.pdf illisible ({e}) : pas d'annexe plan")
        return None
    if not est_a4(rect.width, rect.height):
        avert.append(f"page 1 de plan/plan.pdf hors format A4 ({rect.width:.0f} × {rect.height:.0f} pt) : le contrôle "
                     "la refusera")
    return {"type": "plan", "fichier": os.path.relpath(plan, sortie).replace("\\", "/"),
            "titre": TITRE_ANNEXE_PLAN, "pages": 1}


# =====================================================================================================
# Assemblage
# =====================================================================================================
def _lire_emetteur(dossier: Path, chemin: str | None, dossier_md: str, avert: list) -> dict:
    candidats = [Path(chemin)] if chemin else [dossier / "emetteur.json", dossier.parent / "emetteur.json"]
    for c in candidats:
        if c.is_file():
            try:
                brut = json.loads(c.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise Refus(f"{c} : JSON invalide ({exc})") from None
            return {k: str(brut.get(k) or EMETTEUR_DEFAUT[k]) for k in CLES_EMETTEUR}
    em = dict(EMETTEUR_DEFAUT)
    m = re.search(r"\*\*Responsable\*\*\s*:\s*([^·\n]+)", dossier_md)
    if m:
        em["contact"] = " ".join(w.capitalize() for w in m.group(1).split())
    avert.append("emetteur.json absent (dimensionnement/dossiers/emetteur.json) : téléphone, mail et adresse de "
                 "l'émetteur vides dans la signature")
    return em


def _destinataire(texte: str | None, tutoiement: bool) -> dict | None:
    if not texte:
        return None
    personne, _, societe = texte.partition(",")
    mots = personne.split()
    return {"prenom": mots[0] if mots else "", "nom": " ".join(mots[1:]), "societe": societe.strip(),
            "tutoiement": bool(tutoiement)}


def _bloc_a(dim_md: str) -> dict:
    lignes = tableau_md(section_md(dim_md, "## A.")) if dim_md else []
    return {_norm(_propre(_col(l, "element"))): _sans_refs_internes(_propre(_col(l, "contenu"))) for l in lignes}


def _bloc_a_champ(bloc_a: dict, *mots: str) -> str:
    for k, v in bloc_a.items():
        if any(m in k for m in mots):
            return v
    return ""


_RE_INTERNE = re.compile(r"\?|\b[àa] (?:confirmer|vérifier|verifier)\b|\blesquel(?:le)?s(?: \w+)?|\best-ce que\b|"
                         r"\b(?:faut-il|peut-on|doit-on)\b|^\s*vigilance\b", re.I)


def question_interne(texte: str) -> str:
    """« » si la proposition peut aller chez un fournisseur ; sinon la marque qui en fait une question pour Loïc
    (« ? », « à confirmer », « à vérifier », « lesquels garder », tournure interrogative, point de « vigilance »)."""
    m = _RE_INTERNE.search(str(texte or "").replace("\u00a0", " "))
    return f"« {m.group(0)} »" if m else ""


def _propositions(texte: str) -> list[str]:
    """Propositions d'une cellule ou d'une puce : séparées par « ; » (hors parenthèses et guillemets) ou par une fin de
    phrase."""
    res = []
    for seg in _segments(texte, ";"):
        res += [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý«])", seg) if x.strip()]
    return res


def _jetons_identifiants(texte: str) -> set[str]:
    """Marques, modèles et années d'un texte d'existant : mots à chiffre (3 caractères ou plus) ou à majuscule
    initiale (4 lettres ou plus), sans accents ni casse."""
    jetons = set()
    for mot in re.findall(r"[^\W_]+", texte):
        n = _norm(mot)
        if (any(c.isdigit() for c in n) and len(n) >= 3) or (mot[0].isupper() and len(n) >= 4):
            jetons.add(n)
    return jetons


def _bloc_e(dim_md: str, postes: list[dict]) -> tuple[dict[str, list[str]], list[dict]]:
    """Bloc E découpé par poste : ({id du poste: ["Élément : ce qui le remplace", …]}, exclus internes).

    Chaque cellule de la colonne « Avec … » du tableau, et chaque puce sous le tableau, est découpée en propositions
    (« ; » hors parenthèses, fins de phrase). Une proposition va au(x) poste(s) qu'elle cite : nom du poste ou de sa
    chambre, ou marque / modèle / année propre à ce poste dans la colonne Existant de la même ligne (« les Güntner de
    2025 » → le poste dont l'existant les cite) ; sinon aux postes cités par leur code dans la colonne Existant
    (« A : … · B : … » ; codes de la légende de l'en-tête rattachés à un poste par son nom ou par le nom de sa chambre :
    les évaporateurs cités par chambre vont au poste de cette chambre). Une ligne ou une puce qui ne se rattache à
    aucun poste est omise (sa matière est dans la demande, tirée du bloc F).
    Une proposition interrogative, ou qui contient « à confirmer », « à vérifier », « lesquels garder », « ? », ou qui
    commence par « vigilance » (point à trancher avec Loïc, bloc G de l'étape 2) n'est jamais gardée :
    c'est une question pour Loïc, pas pour le fournisseur ; elle est rendue dans les exclus internes
    ({"element", "postes", "texte", "raison"}), que Claude relit à l'étape 4."""
    par_poste: dict[str, list[str]] = {p["id"]: [] for p in postes}
    exclus: list[dict] = []
    sec = section_md(dim_md, "## E.") if dim_md else ""
    if not sec:
        return par_poste, exclus
    noms = {p["id"]: [n for n in {_norm(p.get("nom")), _norm(nom_chambre(p))} if len(n) >= 4] for p in postes}

    def cites(prop: str, propres: dict[str, set]) -> list[str]:
        pn = _norm(prop)
        jetons = set(re.findall(r"[a-z0-9]+", pn))
        return [pid for pid in par_poste if any(n in pn for n in noms[pid]) or (propres.get(pid, set()) & jetons)]

    def traiter(element: str, cellule: str, defaut: list[str], propres: dict[str, set]) -> None:
        gardees: dict[str, list[str]] = {}
        for prop in _propositions(_propre(cellule)):
            cibles = cites(prop, propres) or defaut
            raison = question_interne(prop)
            if raison:
                exclus.append({"element": element, "postes": cibles, "texte": prop, "raison": raison})
                continue
            prop = _sans_refs_internes(prop)
            for pid in cibles if prop else []:
                gardees.setdefault(pid, []).append(prop)
        for pid, props in gardees.items():
            par_poste[pid].append(f"{element} : {' ; '.join(props)}")

    lignes = tableau_md(sec)
    if lignes:
        entetes = list(lignes[0].keys())
        legende = dict(re.findall(r"\b([A-Z]{1,3})\s*=\s*([^,)]+)", entetes[1] if len(entetes) > 1 else ""))
        codes = {}
        for code, libelle in legende.items():
            lib = _norm(libelle)
            for p in postes:
                if any(n and (lib in n or n in lib) for n in (_norm(p.get("nom")), _norm(nom_chambre(p)))):
                    codes[code] = p["id"]
                    break
        for l in lignes:
            element = _propre(l.get(entetes[0], ""))
            existant = _propre(l.get(entetes[1], "")) if len(entetes) > 1 else ""
            segments: dict[str, list[str]] = {}
            for seg in existant.split("·"):
                m = re.match(r"\s*([A-Z]{1,3})\s*:\s*(.*)", seg)
                if m and m.group(1) in codes:
                    segments.setdefault(codes[m.group(1)], []).append(m.group(2))
            jetons = {pid: _jetons_identifiants(" ".join(x)) for pid, x in segments.items()}
            propres = {pid: j - set().union(*(o for q, o in jetons.items() if q != pid)) for pid, j in jetons.items()}
            traiter(element, l.get(entetes[2], "") if len(entetes) > 2 else "", list(segments), propres)
    for puce in puces_md(sec):                                     # points de vigilance sous le tableau
        traiter("Vigilance", puce, [], {})
    return par_poste, exclus


def segments_par_photo(lu: str, refs: list[str]) -> list[tuple[str, str]]:
    """Ce qu'on voit sur chaque photo d'une ligne du tableau D : le texte « Lu sur les photos » est découpé en segments
    (« ; » hors parenthèses et guillemets) ; un segment qui n'est qu'une étiquette citée (« « Rés. porte » », « départs
    « … » ») est un détail du précédent, pas une vue à part : il n'entre pas dans les légendes. Photos et segments sont
    rapprochés dans l'ordre : autant de segments que de photos → un chacun ; moins de segments → les premières photos
    partagent le premier, les dernières prennent les suivants ; plus de segments → les derniers sont laissés."""
    segs = [s for i, s in enumerate(_segments(lu or "", ";")) if i == 0 or not re.match(r"^(?:«|[^\s«]+\s+«)", s)]
    if not refs:
        return []
    if not segs:
        return [(r, "") for r in refs]
    n, m = len(refs), len(segs)
    if m >= n:
        return list(zip(refs, segs))
    partage = n - m + 1
    return [(r, segs[0] if k < partage else segs[k - partage + 1]) for k, r in enumerate(refs)]


def _photo_chemin(s: Sources, ref: str) -> str:
    return s.photos.get(ref, "")


def _dossier_photo(chemin: str) -> str:
    parties = chemin.split("/")
    return parties[-2] if len(parties) >= 2 else ""


def _photos_plaque(s: Sources, objet: dict, source: str) -> tuple[list[str], bool]:
    """Chemins des photos d'une plaque : champ « photo », sinon les « photo pNN-k » de la source (repli)."""
    if objet.get("photo"):
        return [str(x) for x in objet["photo"]], False
    return [c for c in (_photo_chemin(s, r) for r in _refs(source)) if c], True


def _legende_b2(ligne: dict, plaque: dict | None) -> tuple[str, str]:
    """(légende, ligne « existant ») d'une plaque d'ensemble du tableau B2."""
    equipement = _propre(_col(ligne, "equipement"))
    segs = _segments(_propre(_col(ligne, "plaque")), ";")
    modele = next((x for x in segs if "«" in x or _norm(x).startswith("type")), "")
    serie = next((x for x in segs if _norm(x).startswith("n°") or _norm(x).startswith("n ")), "")
    fluide = next((x for x in segs if re.search(r"\bR\d{2,4}[A-Z]?\b", x)), "")
    annee = next((x for x in segs if re.search(r"\b(19|20)\d\d\b", x) and x not in (serie, modele)), "")
    lecture = _segments(_propre(_col(ligne, "lecture")), ";")
    morceaux = [modele, serie, ", ".join(x for x in (annee, fluide) if x)]
    if plaque is not None and _v(plaque.get("puissance")) is not None:
        reg = " (régime non indiqué)" if "non indiqu" in _norm(plaque.get("portee")) else ""
        morceaux.append(f"puissance lue sur la plaque {plaque['puissance'].texte()}{reg}")
    if lecture and re.search(r"douteu|illisible", _norm(lecture[0])):
        morceaux.append(f"lecture : {lecture[0]}")
    elif not modele and not serie:
        morceaux.append(_couper(segs[0], 80) if segs else "")
    morceaux = [m for m in morceaux if m]
    return " · ".join([equipement] + morceaux), f"{equipement} : {', '.join(morceaux)}" if morceaux else equipement


def assembler(dossier: Path, variante: str, destinataire: str | None = None, tutoiement: bool = False,
              version: str | None = None, nommer: bool = False, anonymiser_force: bool = False,
              date: str | None = None, delai: str | None = None, emetteur: str | None = None,
              force: bool = False, ecrire: bool = True) -> dict:
    """Construit (et écrit) demande.json. Rend {"demande", "chemin", "identifiants", "derivees", "avertissements"}."""
    if variante not in VARIANTES:
        raise Refus(f"variante « {variante} » ; possibles : {', '.join(VARIANTES)}")
    if nommer and anonymiser_force:
        raise Refus("--nommer et --anonymiser sont incompatibles")
    dossier = Path(dossier)
    if not dossier.is_dir() and (DOSSIERS / str(dossier)).is_dir():
        dossier = DOSSIERS / str(dossier)
    s = lire_sources(dossier)
    avert = s.avertissements
    res = s.resultats
    postes = res.get("postes") or []
    if not postes:
        raise Refus("2-resultats.json ne contient aucun poste")
    anonyme = anonymiser_force or (variante == GROSSISTE and not nommer)
    date = date or dt.date.today().isoformat()
    try:
        dt.date.fromisoformat(date)
    except ValueError:
        raise Refus(f"date « {date} » : format attendu AAAA-MM-JJ") from None

    # --- version et dossier de sortie ---
    base = dossier / SORTIE
    suffixe = "" if variante == GROSSISTE else f"-{FABRICANT}"
    if version:
        if not re.fullmatch(r"v\d+", version):
            raise Refus(f"version « {version} » : format attendu v1, v2…")
    else:
        nums = [int(m.group(1)) for d in (base.iterdir() if base.is_dir() else [])
                if d.is_dir() and (m := re.fullmatch(rf"v(\d+){re.escape(suffixe)}", d.name))]
        version = f"v{max(nums, default=0) + 1}"
    sortie = base / f"{version}{suffixe}"
    if ecrire and (sortie / "demande.json").exists() and not force:
        raise Refus(f"{sortie / 'demande.json'} existe déjà (textes peut-être ajustés par Claude) : --force pour le "
                    "remplacer, ou une nouvelle version")

    # --- plan du local et longueurs de cuivre (étape P) ---
    longueurs = longueurs_depuis_metre(lire_metre(dossier), avert)
    avec_longueurs = not longueurs.get("absentes")
    doc_plan = annexe_plan(dossier, sortie, avert)

    etape = re.search(r"\*\*Étape en cours\*\*\s*:\s*(.+)", s.dossier_md)
    if etape is None or "a valider" in _norm(etape.group(1)):
        avert.append("étapes 1 et 2 pas encore validées par Loïc (dossier.md, « Étape en cours ») : le SKILL demande "
                     "cette validation avant l'envoi")

    # --- identité du client, émetteur, destinataire ---
    ids = lire_identifiants(s.dossier_md, s.structure, dossier.name)
    if anonyme and not (ids["noms"] or ids["adresses"]):
        raise Refus("identité du client introuvable dans dossier.md : anonymisation impossible")
    em = _lire_emetteur(dossier, emetteur, s.dossier_md, avert)
    dest = _destinataire(destinataire, tutoiement)
    client = ids["client"]
    localite = ids["localites"][0] if ids["localites"] else ""

    # --- étape 2 : blocs A, E, F ---
    bloc_a = _bloc_a(s.dim_md)
    sec_f = section_md(s.dim_md, "## F.") if s.dim_md else ""
    puces_f = puces_md(sec_f)
    projet = res.get("projet") or {}
    texte_projet = ((projet.get("texte") or {}).get("texte") or "")
    corpus = _norm(" ".join(puces_f) + " " + " ".join(bloc_a.values()) + " " + texte_projet)
    if not puces_f:
        avert.append("bloc F de 2-dimensionnement.md absent ou vide : tous les points de la demande sont gardés, "
                     "à trier par Claude")
    remplacements, exclus_internes = _bloc_e(s.dim_md, postes)

    releve = lire_releve(s.existant_md)
    derivees: list[Valeur] = []

    # --- champs des gabarits ---
    fluide_actuel = ((projet.get("fluide_actuel") or {}).get("valeur") or "")
    fluide_cible = _fluide_aff((projet.get("fluide_cible") or {}).get("valeur") or "") or "(fluide cible à confirmer)"
    famille = next((p["verdict"].get("famille") for p in postes if p.get("verdict") and p["verdict"].get("famille")), "")
    types = (projet.get("type_equipement") or {})
    eqs = []
    for t in ("centrale", "groupe de condensation"):
        ps = [p for p in postes if _norm(types.get(p["id"], "")) == _norm(t)]
        n = len(ps) if t == "centrale" else sum(len(p.get("compresseurs") or []) for p in ps)
        if n:
            eqs.append(t if n == 1 else re.sub(r"^(\w+)", r"\1s", t))
    equipements = " et ".join(eqs) or "installation"
    installation_actuelle = (f"{equipements} {famille} ({fluide_actuel})" if famille and fluide_actuel
                             else f"{equipements} ({fluide_actuel})" if fluide_actuel else equipements)
    remplace = _minuscule_initiale(_bloc_a_champ(bloc_a, "remplace"))
    par_quoi = _minuscule_initiale(_bloc_a_champ(bloc_a, "par quoi"))
    m = re.match(r"^\s*remplacer\s+(.+?)\s+par\s+(.+)$", texte_projet, re.I)
    if m:
        remplace = remplace or _sans_refs_internes(m.group(1))
        par_quoi = par_quoi or _sans_refs_internes(m.group(2))
    marche = _minuscule_initiale(_bloc_a_champ(bloc_a, "marche"))
    planning_client = ""
    m = re.search(r"souhait du client\s*:\s*([^;,.)]+)", marche)
    if m:
        quand = m.group(1).strip()
        planning_client = f"en {quand}" if _norm(quand) in MOIS else quand
    m = re.search(r"(\d+)\s+(?:entreprises|societes|sociétés)", marche)
    nb_entreprises = m.group(1) if m else ""
    qui = _bloc_a_champ(bloc_a, "dessert")
    disposition = " ".join(_majuscule(x).rstrip(".") + "." for x in _segments(qui, ";") if "→" not in x)

    groupes = totaux_categories(res, derivees)
    morceaux = []
    for g in groupes:
        temp = f" (évaporation {_temp(g['t0'])})" if g["t0"] is not None else ""
        morceaux.append(f"{g['valeur'].texte(marque=False)} en {g['libelle']}{temp}")
    tcs = {p["regime"]["tc"].nombre for p in postes}
    condensation = _temp(postes[0]["regime"]["tc"]) if len(tcs) == 1 else \
        " / ".join(_temp(p["regime"]["tc"]) for p in postes)
    fl_actuel = projet.get("fluide_actuel") or {}
    sous_hyp = _norm(fl_actuel.get("statut")) == _norm(HYPOTHESE) or any(
        g["valeur"].statut == HYPOTHESE or any(v is not None and v.statut == HYPOTHESE for v in (g["t0"], g["tc"]))
        for g in groupes)
    chiffres_cles = _liste_fr(morceaux) + (f", condensation {condensation}" if len(tcs) == 1 else "") + \
        " ; valeurs indicatives" + (", calculées sous hypothèses (régimes, fluide)" if sous_hyp else "")
    fluide_actuel_note = fluide_actuel
    if fluide_actuel and _norm(fl_actuel.get("statut")) == _norm(HYPOTHESE):
        fluide_actuel_note += " (d'après le rapport ; à confirmer)" if "rapport" in _norm(fl_actuel.get("source")) \
            else " (à confirmer)"
    t0s = []
    for p in postes:
        t = _temp(p["regime"]["t0"])
        if t not in t0s:
            t0s.append(t)
    regimes = f"{' / '.join(t0s)} évap., {condensation} cond."
    comptes = {}
    for p in postes:
        comptes[categorie(p)] = comptes.get(categorie(p), 0) + 1
    morceaux = []
    for cat, (sing, plur) in (("négatif", ("négative", "négatives")), ("positif", ("positive", "positives"))):
        n = comptes.get(cat, 0)
        if n:
            morceaux.append(f"{NOMBRES_FEMININS.get(n, str(n))} chambre{'s' if n > 1 else ''} "
                            f"{plur if n > 1 else sing}")
    if comptes.get(None):
        n = comptes[None]
        morceaux.append(f"{NOMBRES_FEMININS.get(n, str(n))} autre{'s' if n > 1 else ''} poste{'s' if n > 1 else ''}")
    chambres_resume = _liste_fr(morceaux)

    if dest:
        destinataire_nom = " ".join(x for x in (dest["prenom"], dest["nom"]) if x)
    else:
        destinataire_nom = ""
    societe_tel = " — ".join(x for x in (em["societe"], em["telephone"]) if x)
    champs = {
        "date": date, "version": version,
        "site_titre": "installation frigorifique" if anonyme or not client else
        ", ".join(x for x in (client, localite) if x),
        "reference_chantier": "remodeling frigorifique" if anonyme or not client else
        " – ".join(x for x in (client, localite) if x),
        "fluide_actuel": fluide_actuel, "fluide_actuel_note": fluide_actuel_note,
        "famille_actuelle": famille or "installation", "fluide_cible": fluide_cible,
        "installation_actuelle": installation_actuelle, "remplace": remplace, "par_quoi": par_quoi, "marche": marche,
        "planning_client": planning_client, "nb_entreprises": nb_entreprises, "planning_cazal": "",
        "disposition": disposition, "chiffres_cles": chiffres_cles, "regimes": regimes, "condensation": condensation,
        "note_hypotheses": "", "chambres_resume": chambres_resume, "regulateurs_negatif": "",
        "regulateurs_positif": "", "destinataire_prenom": (dest or {}).get("prenom", ""),
        "destinataire_nom": destinataire_nom, "delai_reponse": DELAI_DEFAUT if delai is None else delai,
        "contact": em["contact"], "societe_et_telephone": societe_tel, "mail_emetteur": em["mail"],
        "phrase_longueurs": PHRASES_MAIL[(avec_longueurs, doc_plan is not None)],
        "chambre": "", "les_evaporateurs": ""}
    cats = {_norm(categorie(p)) for p in postes if categorie(p)}
    gab = Gabarit(TEMPLATES / f"textes-{variante}.md")
    ctx = Contexte(champs=champs, corpus=corpus, corpus_present=bool(puces_f),
                   tutoiement=bool(dest and dest["tutoiement"]), categories=cats, bloc_f=_norm(" ".join(puces_f)))
    if tutoiement and not dest:
        avert.append("--tutoiement sans --destinataire : vouvoiement gardé")
    for cle in list(gab.sections):
        if cle.startswith("liste."):
            champs[f"liste_{cle[len('liste.'):]}"] = _liste_fr(gab.liste(cle, ctx))
    for cat in ("negatif", "positif"):
        cle = f"motif.regulateur.{cat}"
        if gab.a(cle):
            phrases = []
            for p in postes:
                if _norm(categorie(p)) != cat:
                    continue
                n = len(p.get("evaporateurs") or [])
                les = "l'évaporateur" if n == 1 else f"les {n} évaporateurs" if n else \
                    "les évaporateurs (nombre à confirmer)"
                r = gab.texte(cle, ctx.avec(chambre=_minuscule_initiale(nom_chambre(p)), les_evaporateurs=les),
                              "phrases")
                if r:
                    phrases.append(r)
            champs[f"regulateurs_{cat}"] = " ; ".join(phrases)

    # --- tableaux : chambres, production, évaporateurs ---
    hyp = False
    lignes_ch = []
    for p in postes:
        vol = _v(p.get("volume"))
        tch = _v(p.get("temperature_chambre"))
        if tch is not None and tch.nombre is not None:
            regime = tch.texte(0)
        else:
            regime = categorie(p) or "à confirmer"
        surface = "à confirmer"
        if vol is not None and vol.nombre is not None:
            dims = re.findall(r"\d+(?:,\d+)?", vol.formule or "")
            if len(dims) >= 2:
                L = Valeur(float(dims[0].replace(",", ".")), "m", vol.source, vol.statut, id=f"{p['id']}-longueur")
                la = Valeur(float(dims[1].replace(",", ".")), "m", vol.source, vol.statut, id=f"{p['id']}-largeur")
                sv = calculer(lambda L=L, la=la: L.nombre * la.nombre, "m²", f"{L.id} × {la.id}", [L, la],
                              source=f"surface au sol = longueur × largeur, d'après la formule du volume "
                                     f"« {vol.formule} » (assembler.py)", id=f"{p['id']}-surface")
                derivees.append(sv)
                surface = sv.texte()
                hyp = hyp or sv.statut == HYPOTHESE
        if vol is not None:
            hyp = hyp or vol.statut == HYPOTHESE
        lignes_ch.append({"chambre": _majuscule(nom_chambre(p)), "regime": regime, "surface": surface,
                          "volume": vol.texte() if vol is not None else "à confirmer",
                          "nb_evaporateurs": str(len(p.get("evaporateurs") or [])) if p.get("evaporateurs")
                          else "à confirmer"})

    lignes_prod = []
    for p in postes:
        comps = p.get("compresseurs") or []
        groupes_c: dict[tuple, int] = {}
        for c in comps:
            k = (c.get("marque") or "", c.get("modele") or "modèle à confirmer")
            groupes_c[k] = groupes_c.get(k, 0) + 1
        marques = {k[0] for k in groupes_c}
        parts = [f"{n} × {mo}" if n > 1 else mo for (_, mo), n in groupes_c.items()]
        if len(marques) == 1:
            txt = f"{next(iter(marques))} {' + '.join(parts)}".strip()
        else:
            txt = " + ".join(f"{ma} {f'{n} × {mo}' if n > 1 else mo}".strip() for (ma, mo), n in groupes_c.items())
        nd = sum(1 for c in comps if c.get("lecture") == "douteuse")
        ni = sum(1 for c in comps if c.get("lecture") == "illisible")
        extra = [f"{nd} en lecture douteuse" if nd else "", f"{ni} plaque{'s' if ni > 1 else ''} illisible"
                 f"{'s' if ni > 1 else ''}" if ni else ""]
        if any(extra):
            txt += f" (dont {', '.join(x for x in extra if x)})"
        vbs = [_v(c.get("volume_balaye")) for c in comps]
        if comps and all(v is not None for v in vbs):
            vt = somme(vbs, "m³/h", id=f"{p['id']}-volume-balaye-total",
                       source="somme des volumes balayés des plaques du poste (assembler.py)")
            derivees.append(vt)
            vol_txt = vt.texte()
        else:
            vol_txt = "à confirmer"
        ex = p["existante"]
        hyp = hyp or ex.statut == HYPOTHESE
        lignes_prod.append({"poste": p["nom"], "compresseurs": txt or "à confirmer", "volume_balaye": vol_txt,
                            "puissance": ex.texte(marque=False), "statut": ex.statut})
    sous_totaux = []
    for g in groupes:
        if g["categorie"] is None:
            continue
        reg = f" (évap. {_temp(g['t0'])}, cond. {_temp(g['tc'])})" if g["t0"] is not None and g["tc"] is not None \
            else ""
        sous_totaux.append({"libelle": f"Sous-total {g['libelle']}{reg}", "puissance": g["valeur"].texte(marque=False),
                            "statut": g["valeur"].statut})
    champs["note_hypotheses"] = ("« (hyp.) » ou « hypothèse » : valeur qui dépend d'une hypothèse de l'étude, à "
                                 "confirmer.") if hyp else ""

    evaporateurs = None
    if variante == GROSSISTE:
        puiss_ev = gab.texte("evaporateurs.puissance", ctx, "phrases")
        evaporateurs = {"lignes": [{"chambre": _majuscule(nom_chambre(p)), "modele": ev.get("modele") or "à confirmer",
                                    "annee": str(ev.get("annee") or "à confirmer"), "puissance": puiss_ev}
                                   for p in postes for ev in p.get("evaporateurs") or []],
                        "note": gab.texte("evaporateurs.note", ctx, "phrases")}

    # --- demande ---
    points, lettre = [], ord("a")
    for cle in sorted(k for k in gab.sections if re.fullmatch(r"demande\.[a-z]", k)):
        pt = gab.point(cle, ctx)
        if pt is None:
            continue
        points.append({"lettre": chr(lettre), **pt})
        lettre += 1
    demande_bloc = {"titre": gab.texte("demande.titre", ctx, "phrases"),
                    "intro": gab.texte("demande.intro", ctx, "phrases") if gab.a("demande.intro") else "",
                    "points": points,
                    "resume": gab.texte("demande.resume", ctx, "phrases") if gab.a("demande.resume") else ""}

    # renvoi vers le point de la demande sur l'armoire de régulation : chapitre 4, + 1 avec les évaporateurs,
    # + 1 avec les longueurs de cuivre (chapitres placés avant la demande)
    pt_reg = next((x for x in points if "armoire" in _norm(x["titre"])), None) or \
        next((x for x in points if "regulation" in _norm(x["titre"])), None)
    chapitre_demande = 4 + (evaporateurs is not None) + avec_longueurs
    renvoi_regulation = f"Régulation : voir § {chapitre_demande} {pt_reg['lettre']})" if pt_reg else ""

    # --- postes : existant, puissance, remplacement, photos ---
    utilisees: set[str] = set()
    dossiers_poste: dict[str, str] = {}             # dossier de photos → id du poste
    postes_json = []
    puiss_ev_leg = gab.texte("evaporateurs.puissance", ctx, "phrases")
    for p in postes:
        comps = p.get("compresseurs") or []
        evs = p.get("evaporateurs") or []
        existant, photos = [], []
        fl = p.get("fluide") or projet.get("fluide_actuel") or {}
        fl_txt = fl.get("valeur") or "à confirmer"
        if fl.get("statut") and fl.get("statut") != SOURCE and fl.get("valeur"):
            fl_txt += f" ({fl['statut']})"
        charge = _v(p.get("charge"))
        existant.append(f"Fluide actuel : {fl_txt} ; charge : {charge.texte() if charge else 'à confirmer'}")
        for i, c in enumerate(comps, 1):
            chemins, repli = _photos_plaque(s, c, (_v(c.get("volume_balaye")) or a_confirmer("", "—")).source)
            if repli and chemins:
                avert.append(f"{c['id']} : photo retrouvée dans la source (« photo pNN-k ») ; champ « photo » absent "
                             "de 2-entrees.json")
            refs = [Path(x).stem for x in chemins]
            ligne_b = next((l for l in releve.b if any(r in _refs(_col(l, "photo")) for r in refs)), None)
            serie = _propre(_col(ligne_b, "serie")) if ligne_b else ""
            modele = c.get("modele") or "modèle à confirmer"
            if c.get("lecture") in ("douteuse", "illisible"):
                modele += f" (lecture {c['lecture']})"
            vb = _v(c.get("volume_balaye"))
            ret = _v(c.get("retenue"))
            morceaux = [f"{c.get('marque') or ''} {modele}".strip(), f"n° {serie}" if serie else "n° de série non relevé",
                        vb.texte() if vb else "volume balayé à confirmer",
                        f"puissance retenue {ret.texte() if ret else 'à confirmer'}"]
            existant.append(f"Compresseur {i}/{len(comps)} : " + ", ".join(morceaux))
            for ch in chemins:
                if ch not in utilisees:
                    photos.append({"fichier": ch, "legende": " · ".join(morceaux), "type": "plaque"})
                    utilisees.add(ch)
                    dossiers_poste.setdefault(_dossier_photo(ch), p["id"])
        for pl in p.get("plaques") or []:
            chemins, repli = _photos_plaque(s, pl, (_v(pl.get("puissance")) or a_confirmer("", "—")).source)
            for ch in chemins:
                dossiers_poste.setdefault(_dossier_photo(ch), p["id"])
        # évaporateurs : photo de chaque plaque ; repli dans l'ordre des photos citées par la source
        par_source: dict[str, list[dict]] = {}
        for ev in evs:
            par_source.setdefault(ev.get("source") or "", []).append(ev)
        for i, ev in enumerate(evs, 1):
            if ev.get("photo"):
                chemins = [str(x) for x in ev["photo"]]
            else:
                freres = par_source.get(ev.get("source") or "", [])
                cites = [c for c in (_photo_chemin(s, r) for r in _refs(ev.get("source"))) if c]
                if len(cites) == len(freres) and cites:
                    chemins = [cites[freres.index(ev)]]
                    avert.append(f"{ev.get('id')} : photo rattachée dans l'ordre des photos citées par sa source, "
                                 "à vérifier (champ « photo » absent de 2-entrees.json)")
                else:
                    chemins = []
                    if cites:
                        avert.append(f"{ev.get('id')} : {len(cites)} photo(s) citée(s) pour {len(freres)} "
                                     "évaporateur(s), rattachement impossible : photo « à confirmer »")
            refs = [Path(x).stem for x in chemins] + _refs(ev.get("source"))
            refs += re.findall(r"rapport p\. ?\d+", ev.get("source") or "")
            freres_modele = [e for e in evs if _norm(e.get("modele")) == _norm(ev.get("modele"))]
            serie = _serie_evaporateur(releve, ev, refs, freres_modele.index(ev))
            fl_o = ev.get("fluide_origine") or ""
            fl_o = f"fluide {fl_o}" if fl_o and not fl_o.upper().startswith("R") else fl_o
            morceaux = [ev.get("modele") or "modèle à confirmer", f"n° {serie}" if serie else "n° de série non relevé",
                        ", ".join(x for x in (str(ev.get("annee") or ""), fl_o) if x) or "année à confirmer",
                        f"puissance {puiss_ev_leg}"]
            existant.append(f"Évaporateur {i}/{len(evs)} : " + ", ".join(morceaux[:3]))
            for ch in chemins:
                if ch not in utilisees:
                    photos.append({"fichier": ch, "legende": " · ".join(morceaux), "type": "plaque"})
                    utilisees.add(ch)
                    dossiers_poste.setdefault(_dossier_photo(ch), p["id"])
        ex = p["existante"]
        puissance = ex.texte()
        dem = _v(p.get("demandee"))
        if dem is not None and dem.nombre != ex.nombre:
            marge = _v(p.get("marge"))
            puissance = f"{ex.texte()} existante ; {dem.texte()} demandée" + \
                (f" (marge {marge.texte()})" if marge else "")
        rempl = list(remplacements.get(p["id"]) or [])
        if renvoi_regulation and not any(_norm(x).startswith("regulation") for x in rempl):
            rempl.append(renvoi_regulation)
        postes_json.append({"id": p["id"], "titre": p["nom"],
                            "dessert": ((p.get("dessert") or {}).get("texte") or "à confirmer"),
                            "existant": existant, "puissance": puissance, "statut": ex.statut,
                            "remplacement": " ".join(x.rstrip(".") + "." for x in rempl) if rempl else "à confirmer",
                            "photos": photos, "_plaques": p.get("plaques") or []})

    # plaques d'ensemble du tableau B2 (photo avec une plaque lue) → poste ; le reste → vues d'ensemble
    noms_postes = {_norm(p["nom"]): p["id"] for p in postes}
    par_id = {pj["id"]: pj for pj in postes_json}
    for l in releve.b2:
        if not _b2_est_plaque(l):
            continue
        refs = _refs(_col(l, "photo"))
        for r in refs[:1]:
            ch = _photo_chemin(s, r)
            if not ch or ch in utilisees:
                continue
            pid = dossiers_poste.get(_dossier_photo(ch)) or noms_postes.get(_norm(_col(l, "poste")))
            if pid is None:
                continue
            pj = par_id[pid]
            plaque = next((pl for pl in pj["_plaques"]
                           if ch in [str(x) for x in pl.get("photo") or []]
                           or r in _refs((_v(pl.get("puissance")) or a_confirmer("", "—")).source)), None)
            legende, ligne_ex = _legende_b2(l, plaque)
            pj["photos"].append({"fichier": ch, "legende": legende, "type": "ensemble"})
            pj["existant"].append(ligne_ex)
            utilisees.add(ch)
    for pj in postes_json:
        pj.pop("_plaques")
    # plaques d'ensemble de l'étape 2 dont la photo n'est pas au tableau B2
    for p in postes:
        pj = par_id[p["id"]]
        for pl in p.get("plaques") or []:
            chemins, _ = _photos_plaque(s, pl, (_v(pl.get("puissance")) or a_confirmer("", "—")).source)
            for ch in chemins:
                if ch in utilisees:
                    continue
                leg = f"{_sans_parentheses_chiffrees(_propre(pl.get('texte') or 'plaque d’ensemble'))} · puissance lue " \
                      f"sur la plaque {pl['puissance'].texte()}"
                pj["photos"].append({"fichier": ch, "legende": leg, "type": "ensemble"})
                utilisees.add(ch)

    # --- annexes : vues d'ensemble ---
    candidats: dict[str, list[tuple]] = {}

    def candidat(ref: str, cle: tuple, legende: str):
        candidats.setdefault(ref, []).append((cle, legende))

    def nom_poste_photo(ref: str, defaut: str) -> str:
        pid = dossiers_poste.get(_dossier_photo(_photo_chemin(s, ref)))
        if pid:
            return next(p["nom"] for p in postes if p["id"] == pid)
        return _titre_poste(defaut)

    for i, l in enumerate(releve.d):
        element = _sans_parentheses_chiffrees(_propre(_col(l, "element")))
        lu = _propre(_col(l, "lu sur"))
        if lu in ("", "—", "-"):
            lu = _propre(_col(l, "rapport"))
        refs = _refs(_col(l, "photo"))
        for pos, (r, seg) in enumerate(segments_par_photo(lu if lu not in ("—", "-") else "", refs)):
            extrait = _majuscule(_couper_elements(_sans_parentheses_chiffrees(seg)))
            candidat(r, (pos > 0, 0, i), " · ".join(x for x in (element, extrait) if x))
    for i, l in enumerate(releve.b2):
        if _b2_est_plaque(l):
            continue
        for pos, r in enumerate(_refs(_col(l, "photo"))):
            equip = _couper(_propre(_col(l, "equipement")))
            candidat(r, (pos > 0, 1, i), f"{nom_poste_photo(r, _col(l, 'poste'))} · {equip}")
    for i, l in enumerate(releve.c):
        usage = _propre(_col(l, "usage"))
        for pos, r in enumerate(_refs(usage)):
            seg = re.sub(r"\s*\(photos? [^)]*\)", "", _segments(usage, ";")[0]).strip()
            pid = dossiers_poste.get(_dossier_photo(_photo_chemin(s, r)))
            chambre = _majuscule(nom_chambre(next(p for p in postes if p["id"] == pid))) if pid else \
                _titre_poste(_col(l, "poste").split("(")[0])
            candidat(r, (pos > 0, 2, i), f"{chambre} · vue de la chambre ({seg})" if seg else f"{chambre} · vue")
    titres_f = {}
    for l in releve.f:
        for r in _refs(_col(l, "photo")):
            titres_f[r] = _col(l, "poste")
    vues = []
    for ref, chemin in s.photos.items():
        if chemin in utilisees:
            continue
        if candidats.get(ref):
            legende = min(candidats[ref])[1]
        else:
            legende = f"{nom_poste_photo(ref, titres_f.get(ref, _dossier_photo(chemin)))} · vue d'ensemble"
        vues.append({"fichier": chemin, "legende": legende})

    # --- textes ---
    contexte = gab.texte("contexte", ctx)
    sal = gab.texte("mail.salutation.destinataire", ctx, "phrases") if dest and gab.a("mail.salutation.destinataire") \
        else ""
    mail = {"objet": gab.texte("mail.objet", ctx, "phrases"),
            "salutation": sal or gab.texte("mail.salutation", ctx, "phrases"),
            "corps": gab.texte("mail.corps", ctx),
            "formule": gab.texte("mail.formule", ctx, "phrases"),
            "signature": gab.texte("mail.signature", ctx, "lignes")}

    demande = {
        "version": version, "date": date, "variante": variante, "destinataire": dest, "anonymise": anonyme,
        "emetteur": em,
        "site": {"nom": "", "localite": "", "reference_dossier": ""} if anonyme else
        {"nom": client, "localite": localite, "reference_dossier": ids["fiches"][0] if ids["fiches"] else ""},
        "titre": gab.texte("titre", ctx, "phrases"),
        "mention": gab.texte("mention", ctx, "phrases"),
        "contexte": {"texte": contexte},
        "chambres": {"lignes": lignes_ch, "note": gab.texte("chambres.note", ctx, "phrases")},
        "production": {"lignes": lignes_prod, "sous_totaux": sous_totaux,
                       "note": gab.texte("production.note", ctx, "phrases")},
        "evaporateurs": evaporateurs,
        "longueurs": longueurs,
        "demande": demande_bloc,
        "postes": postes_json,
        "annexes": {"vues_ensemble": vues,
                    "plan_implantation": PLAN_EN_ANNEXE if doc_plan else PLAN_IMPLANTATION,
                    "pieces_jointes": [], "documents": [doc_plan] if doc_plan else []},
        "mail": mail,
        "exclus_internes": exclus_internes,
    }

    # --- anonymisation et contrôles ---
    motifs = motifs_anonymisation(ids)
    derivees_json = [v.vers_dict() for v in derivees]
    if anonyme:
        demande = anonymiser(demande, motifs)
        derivees_json = anonymiser(derivees_json, motifs)
        restants = identifiants_restants(demande, motifs) + identifiants_restants(derivees_json, motifs)
        if restants:
            raise Refus(f"anonymisation incomplète, identifiants restants : {sorted(set(restants))}")
        dans_chemins = sorted({t for t, _, mo in motifs for ph in _chemins_photos(demande) if mo.search(ph)})
        if dans_chemins:
            avert.append(f"identifiant du client dans un chemin de photo (non modifié) : {dans_chemins}")
    erreurs = verifier_schema(demande)
    if erreurs:
        raise Refus("demande.json non conforme au schéma : " + " ; ".join(erreurs))
    mail_txt = "\n".join(str(v) for v in demande["mail"].values())
    if "|" in mail_txt:
        raise Refus("le mail contient « | » (tableau interdit dans le mail)")
    nb_photos = sum(len(pj["photos"]) for pj in demande["postes"]) + len(demande["annexes"]["vues_ensemble"])
    if nb_photos != len(s.photos):
        avert.append(f"{len(s.photos) - nb_photos} photo(s) de sources/photos non placée(s)")

    identifiants = {"anonymise": anonyme, "source": "dossier.md (titre, ligne Client, Adresse d'intervention) et "
                    "sources/structure.json", **{k: v for k, v in ids.items()},
                    "recherches": [t for t, _, _ in motifs],
                    "remplacements": {t: r for t, r, _ in motifs}}
    if ecrire:
        sortie.mkdir(parents=True, exist_ok=True)
        _ecrire_json(sortie / "demande.json", demande)
        _ecrire_json(sortie / "identifiants-client.json", identifiants)
        _ecrire_json(sortie / "valeurs-derivees.json",
                     {"note": "valeurs calculées par assembler.py (valeur.calculer, controles.somme) à partir de "
                              "2-resultats.json ; toutes les autres viennent telles quelles de l'étape 2",
                      "valeurs": derivees_json})
    return {"demande": demande, "chemin": sortie / "demande.json", "dossier_sortie": sortie,
            "identifiants": identifiants, "derivees": derivees_json, "avertissements": avert,
            "nb_photos": nb_photos}


def _chemins_photos(demande: dict) -> list[str]:
    ch = [ph["fichier"] for pj in demande.get("postes") or [] for ph in pj.get("photos") or []]
    return ch + [v["fichier"] for v in (demande.get("annexes") or {}).get("vues_ensemble") or []]


def _ecrire_json(chemin: Path, obj: Any) -> None:
    chemin.write_bytes((json.dumps(obj, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


# =====================================================================================================
# Schéma
# =====================================================================================================
def verifier_schema(d: Any) -> list[str]:
    """Écarts au schéma commun de demande.json (liste vide = conforme)."""
    err = []

    def cles(obj, attendues, chemin):
        if not isinstance(obj, dict):
            err.append(f"{chemin} : objet attendu")
            return False
        manquantes = [k for k in attendues if k not in obj]
        en_trop = [k for k in obj if k not in attendues]
        if manquantes:
            err.append(f"{chemin} : clés manquantes {manquantes}")
        if en_trop:
            err.append(f"{chemin} : clés inattendues {en_trop}")
        return not manquantes

    def textes(obj, attendues, chemin):
        if cles(obj, attendues, chemin):
            for k in attendues:
                if not isinstance(obj[k], str):
                    err.append(f"{chemin}.{k} : texte attendu, reçu {type(obj[k]).__name__}")

    def liste(obj, chemin):
        if not isinstance(obj, list):
            err.append(f"{chemin} : liste attendue")
            return []
        return obj

    if not cles(d, CLES_DEMANDE, "demande"):
        return err
    for k in ("version", "date", "titre", "mention"):
        if not isinstance(d[k], str) or not d[k]:
            err.append(f"{k} : texte non vide attendu")
    if d["variante"] not in VARIANTES:
        err.append(f"variante « {d['variante']} »")
    if not isinstance(d["anonymise"], bool):
        err.append("anonymise : booléen attendu")
    if d["destinataire"] is not None:
        if cles(d["destinataire"], ("prenom", "nom", "societe", "tutoiement"), "destinataire"):
            if not isinstance(d["destinataire"]["tutoiement"], bool):
                err.append("destinataire.tutoiement : booléen attendu")
    textes(d["emetteur"], CLES_EMETTEUR, "emetteur")
    textes(d["site"], ("nom", "localite", "reference_dossier"), "site")
    textes(d["contexte"], ("texte",), "contexte")
    if cles(d["chambres"], ("lignes", "note"), "chambres"):
        for i, l in enumerate(liste(d["chambres"]["lignes"], "chambres.lignes")):
            textes(l, ("chambre", "regime", "surface", "volume", "nb_evaporateurs"), f"chambres.lignes[{i}]")
    if cles(d["production"], ("lignes", "sous_totaux", "note"), "production"):
        for i, l in enumerate(liste(d["production"]["lignes"], "production.lignes")):
            textes(l, ("poste", "compresseurs", "volume_balaye", "puissance", "statut"), f"production.lignes[{i}]")
        for i, l in enumerate(liste(d["production"]["sous_totaux"], "production.sous_totaux")):
            textes(l, ("libelle", "puissance", "statut"), f"production.sous_totaux[{i}]")
    if d["evaporateurs"] is not None and cles(d["evaporateurs"], ("lignes", "note"), "evaporateurs"):
        for i, l in enumerate(liste(d["evaporateurs"]["lignes"], "evaporateurs.lignes")):
            textes(l, ("chambre", "modele", "annee", "puissance"), f"evaporateurs.lignes[{i}]")
    lg = d["longueurs"]
    if isinstance(lg, dict) and "absentes" in lg:
        if cles(lg, ("absentes", "phrase"), "longueurs"):
            if lg["absentes"] is not True or not isinstance(lg["phrase"], str) or not lg["phrase"]:
                err.append("longueurs : « absentes » vrai et phrase non vide attendus")
    elif cles(lg, ("phrase", "reseaux", "diametres", "source", "plan_version"), "longueurs"):
        for k in ("phrase", "diametres", "source"):
            if not isinstance(lg[k], str) or not lg[k]:
                err.append(f"longueurs.{k} : texte non vide attendu")
        if lg["plan_version"] is not None and (not isinstance(lg["plan_version"], int)
                                               or isinstance(lg["plan_version"], bool)):
            err.append("longueurs.plan_version : entier ou null attendu")
        reseaux = liste(lg["reseaux"], "longueurs.reseaux")
        if not reseaux:
            err.append("longueurs.reseaux : au moins un réseau (sinon « absentes »)")
        for i, r in enumerate(reseaux):
            ou = f"longueurs.reseaux[{i}]"
            if not cles(r, ("cle", "nom", "famille", "lignes", "total_m", "origine"), ou):
                continue
            if r["famille"] not in FAMILLES_CUIVRE:
                err.append(f"{ou}.famille « {r['famille']} » (seuls {', '.join(FAMILLES_CUIVRE)})")
            if r["origine"] not in ORIGINES_TOTAL or not _longueur_ok(r["total_m"]):
                err.append(f"{ou} : origine ou total_m invalide")
            lignes = liste(r["lignes"], f"{ou}.lignes")
            if not lignes:
                err.append(f"{ou}.lignes : au moins une ligne")
            for j, l in enumerate(lignes):
                if cles(l, ("troncon", "type_nom", "total_m", "origine"), f"{ou}.lignes[{j}]"):
                    if not isinstance(l["troncon"], str) or not isinstance(l["type_nom"], str) or \
                            not _longueur_ok(l["total_m"]) or l["origine"] not in ORIGINES_LIGNE:
                        err.append(f"{ou}.lignes[{j}] : troncon, type_nom (textes), total_m (nombre), origine "
                                   "(estimee ou mesuree) attendus")
    if cles(d["demande"], ("titre", "intro", "points", "resume"), "demande"):
        for i, p in enumerate(liste(d["demande"]["points"], "demande.points")):
            if cles(p, ("lettre", "titre", "texte", "sous_points"), f"demande.points[{i}]"):
                if not all(isinstance(x, str) for x in liste(p["sous_points"], f"demande.points[{i}].sous_points")):
                    err.append(f"demande.points[{i}].sous_points : textes attendus")
    for i, p in enumerate(liste(d["postes"], "postes")):
        if cles(p, ("id", "titre", "dessert", "existant", "puissance", "statut", "remplacement", "photos"),
                f"postes[{i}]"):
            if not all(isinstance(x, str) for x in liste(p["existant"], f"postes[{i}].existant")):
                err.append(f"postes[{i}].existant : textes attendus")
            for j, ph in enumerate(liste(p["photos"], f"postes[{i}].photos")):
                textes(ph, ("fichier", "legende", "type"), f"postes[{i}].photos[{j}]")
                if isinstance(ph, dict) and ph.get("type") not in ("plaque", "ensemble"):
                    err.append(f"postes[{i}].photos[{j}].type « {ph.get('type')} »")
    if cles(d["annexes"], CLES_ANNEXES, "annexes"):
        for j, v in enumerate(liste(d["annexes"]["vues_ensemble"], "annexes.vues_ensemble")):
            textes(v, ("fichier", "legende"), f"annexes.vues_ensemble[{j}]")
        liste(d["annexes"]["pieces_jointes"], "annexes.pieces_jointes")
        for j, doc in enumerate(liste(d["annexes"]["documents"], "annexes.documents")):
            if cles(doc, ("type", "fichier", "titre", "pages"), f"annexes.documents[{j}]"):
                if doc["type"] != "plan" or not isinstance(doc["fichier"], str) or not doc["fichier"] or \
                        not isinstance(doc["titre"], str) or not isinstance(doc["pages"], int) or doc["pages"] < 1:
                    err.append(f"annexes.documents[{j}] : type « plan », fichier et titre (textes), pages (≥ 1) "
                               "attendus")
    textes(d["mail"], ("objet", "salutation", "corps", "formule", "signature"), "mail")
    for i, x in enumerate(liste(d["exclus_internes"], "exclus_internes")):
        if cles(x, ("element", "postes", "texte", "raison"), f"exclus_internes[{i}]"):
            if not all(isinstance(x[k], str) for k in ("element", "texte", "raison")) or \
                    not all(isinstance(pid, str) for pid in liste(x["postes"], f"exclus_internes[{i}].postes")):
                err.append(f"exclus_internes[{i}] : textes et liste d'identifiants de postes attendus")
    return err


# =====================================================================================================
# Ligne de commande
# =====================================================================================================
def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(prog="assembler.py", description="Étape 3 : assembler demande.json depuis les étapes "
                                 "1 et 2 (variante grossiste anonymisée ou fabricant nommée).")
    ap.add_argument("dossier", help="dossier de l'installation (chemin ou nom dans dimensionnement/dossiers/)")
    ap.add_argument("--variante", required=True, choices=VARIANTES)
    ap.add_argument("--destinataire", help="« Prénom Nom, Société » (ex. « Prénom Nom, Société »)")
    ap.add_argument("--tutoiement", action="store_true", help="tutoyer le destinataire")
    ap.add_argument("--version", help="vN (défaut : dernier + 1 pour cette variante)")
    ap.add_argument("--nommer", action="store_true", help="grossiste : ne pas anonymiser le client")
    ap.add_argument("--anonymiser", action="store_true", help="fabricant : anonymiser le client")
    ap.add_argument("--date", help="date de la demande, AAAA-MM-JJ (défaut : aujourd'hui)")
    ap.add_argument("--delai", help=f"délai de réponse souhaité (défaut : « {DELAI_DEFAUT} »)")
    ap.add_argument("--emetteur", help="fichier JSON des coordonnées de l'émetteur")
    ap.add_argument("--force", action="store_true", help="remplacer une version existante")
    a = ap.parse_args(argv)
    try:
        r = assembler(Path(a.dossier), a.variante, a.destinataire, a.tutoiement, a.version, a.nommer, a.anonymiser,
                      a.date, a.delai, a.emetteur, a.force)
    except SourceAbsente as exc:
        print(f"refusé : {exc}")
        return 2
    except Refus as exc:
        print(f"refusé : {exc}")
        return 1
    d = r["demande"]
    print(f"Écrit : {r['chemin']}")
    print(f"  variante {d['variante']}, {'anonymisée' if d['anonymise'] else 'nommée'}, version {d['version']}")
    print(f"  {len(d['postes'])} poste(s), {sum(len(p['photos']) for p in d['postes'])} photo(s) de plaques, "
          f"{len(d['annexes']['vues_ensemble'])} vue(s) d'ensemble, {len(d['demande']['points'])} point(s) de demande")
    for l in d["production"]["sous_totaux"]:
        print(f"  {l['libelle']} : {l['puissance']} ({l['statut']})")
    lg = d["longueurs"]
    if lg.get("absentes"):
        print(f"  longueurs : {lg['phrase']}")
    else:
        print(f"  longueurs de cuivre (plan v{lg['plan_version']}) : "
              + " ; ".join(f"{r['nom']} " + f"{r['total_m']:.2f}".replace(".", ",") + " m" for r in lg["reseaux"]))
    for doc in d["annexes"]["documents"]:
        print(f"  annexe fusionnée en fin de PDF : {doc['titre']} ({doc['fichier']})")
    for m in r["avertissements"]:
        print(f"  attention : {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
