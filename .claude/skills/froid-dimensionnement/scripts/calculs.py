"""Étape 2 du dimensionnement : 2-entrees.json → 2-resultats.json + 2-tableaux.md (tableaux B, C, D).

Point d'entrée du skill froid-dimensionnement. Claude remplit 2-entrees.json (une Valeur sourcée par donnée, jamais
un nombre inventé) ; ce script calcule tout le reste : M1 et M2 par compresseur (compresseurs.py), sommes, contrôles
et puissance demandée (controles.py), conformité du fluide (fgas.py). Il écrit les tableaux B, C, D à recopier tels
quels dans 2-dimensionnement.md. Les nombres des tableaux viennent uniquement de Valeur.texte() (PRP : fgas.texte_prp ;
phrases réglementaires : fgas.py). Même entrée, même résultat (aucune date de génération dans les sorties).

Usage (depuis la racine du dépôt) :
    PYTHONUTF8=1 python .claude/skills/froid-dimensionnement/scripts/calculs.py dimensionnement/dossiers/<slug>
    PYTHONUTF8=1 python .claude/skills/froid-dimensionnement/scripts/calculs.py dimensionnement/dossiers/<slug> --verifier
    option : --points <csv> (points catalogue ; défaut : dimensionnement/savoir/materiel/points-catalogue/bitzer-r449a.csv)
--verifier relit seulement les entrées et signale les incohérences (id en double, unités, statuts, lectures, sources
non reconnues), sans rien écrire. Sans --verifier, la même vérification passe d'abord : une erreur bloque l'écriture.
Codes de sortie : 0 fait (ou entrées cohérentes) ; 1 entrées incohérentes, rien n'est écrit ; 2 dossier ou
2-entrees.json absent, JSON illisible.

Format de 2-entrees.json (« 2-entrees v1 »). Trois briques :
    Valeur        {"id", "nombre", "unite", "source", "statut"}   (valeur.py ; nombre null ⇔ statut « à confirmer »)
    choix         {"valeur", "source", "statut", "id"}            (paramètre texte sourcé : fluide, convention…)
    texte sourcé  {"texte", "source", "statut"}
Chaque source dit d'où vient la donnée : « photo p11-3 », « rapport p. 10 », « dicté par Loïc le AAAA-MM-JJ »,
« hypothèse : … », « savoir/methodes/… § N », « web : <lien> » ; une Valeur « à confirmer » dit pourquoi.
{
  "format": "2-entrees v1", "dossier": "<slug>",
  "parametres": {                         facultatif ; clé absente = défaut du script, écrit comme hypothèse
      "convention": choix (rosee | moyenne), "gaz_aspire": Valeur °C | null, "surchauffe": Valeur K | null,
      "sous_refroidissement": Valeur K, "seuil_ecart": Valeur %, "seuil_t0": Valeur K, "seuil_tc": Valeur K,
      "lambda_methode": choix (table_a | efpme), "fluide_base": choix, "marge_pct": Valeur % (défaut : 0 %,
      hypothèse en attente de Loïc), "ratio_kw_m3": Valeur kW/m³ (règle de pouce de Loïc, seulement s'il l'a donnée)},
  "projet": {
      "texte": texte sourcé (ce qui est remplacé par quoi), "fluide_actuel": choix, "fluide_cible": choix,
      "type_equipement": {"<id du poste>": "centrale" | "groupe de condensation" | … (synonymes de fgas.py)},
      "type_equipement_cible": "centrale", "precision": "remise de prix" | "exécution", "date_analyse": "AAAA-MM-JJ"},
  "postes": [{
      "id", "nom", "dessert": texte sourcé, "fluide": choix (facultatif ; sinon le fluide actuel du projet),
      "temperature_chambre": Valeur °C, "volume": Valeur m³, "regime": {"t0": Valeur °C, "tc": Valeur °C},
      "charge": Valeur kg,
      "compresseurs": [{"id", "marque", "modele", "volume_balaye": Valeur m³/h (photo en source),
                        "lecture": "sûre" | "douteuse" | "illisible", "note": texte, "frequence": Valeur Hz,
                        "estimation": Valeur kW (facultatif : chiffre antérieur pour ce compresseur)}],
      "evaporateurs": [{"id", "modele", "annee", "fluide_origine", "source"}],
      "plaques_ensemble": [{"id", "texte", "puissance": Valeur kW, "fluide": choix | null,
                            "regime": {"t0", "tc"} | null}],
      "estimations": [{"id", "texte", "puissance": Valeur kW}]}]       (chiffres antérieurs à comparer)
}
Règles : lecture « douteuse » → volume balayé en statut « hypothèse » avec « lecture douteuse : … » dans la source
(M1, M2 et la valeur retenue restent au mieux « hypothèse ») ; lecture « illisible » → volume balayé « à confirmer »,
M1 et M2 « à confirmer ». Un compresseur « à confirmer » rend la puissance du poste « à confirmer » : le tableau C
donne à part « somme des n compresseurs lus : X kW », valeur calculée distincte. Une plaque d'ensemble est comparée
aux compresseurs du poste recalculés à son fluide (et à son régime s'il est écrit ; sinon l'écart est indicatif).
La capacité passée à fgas.py est la somme des puissances retenues du poste (indicative). Un fluide en « hypothèse »
plafonne aussi les résultats F-gas (PRP du poste, tCO2e, étanchéité, interdictions : « (hyp.) » au tableau D) ; une
plaque du poste qui indique un autre fluide (plaque d'ensemble, fluide d'origine d'un évaporateur) donne une variante
calculée (tableau « G-variantes »). Les id sont uniques dans tout le fichier : ils apparaissent dans les formules.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
from dataclasses import replace
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fgas  # noqa: E402
import fluides  # noqa: E402
from compresseurs import CHEMIN_POINTS_DEFAUT, CLES_PARAMETRES, charger_points, puissance_compresseur  # noqa: E402
from compresseurs import _parametres as parametres_effectifs  # noqa: E402  (défauts + vérification, même skill)
from controles import comparer, puissance_demandee, somme  # noqa: E402
from valeur import (A_CONFIRMER, HYPOTHESE, RANG, SOURCE, Valeur, a_confirmer, calculer,  # noqa: E402
                    combiner, depuis_json, en_json, normaliser_statut)

# ---------- constantes ----------
FORMAT_ENTREES = "2-entrees v1"
FORMAT_RESULTATS = "2-resultats v1"
ENTREES, RESULTATS, TABLEAUX = "2-entrees.json", "2-resultats.json", "2-tableaux.md"
POURCENT = 100.0                                   # 1 = 100 % (définition)
SURE, DOUTEUSE, ILLISIBLE = "sûre", "douteuse", "illisible"
LECTURES = {"sure": SURE, "douteuse": DOUTEUSE, "illisible": ILLISIBLE}
MOTIF_DOUTE = "lecture douteuse"
PRECISIONS = ("remise de prix", "exécution")
# Écart entre le volume balayé de la plaque et celui du catalogue au-delà duquel le tableau C le signale : 1 %.
# Choix de présentation (les arrondis des plaques des six modèles du CSV restent sous 0,2 %), pas une donnée physique.
SEUIL_VOLUME_PCT = 1.0
FREQUENCE_ATTENDUE_HZ = 50.0                       # volumes balayés et points catalogue à 50 Hz (materiel/bitzer.md § 6)

CLES_RACINE = ("format", "dossier", "parametres", "projet", "postes")
CLES_PARAMETRES_ENTREES = CLES_PARAMETRES + ("marge_pct", "ratio_kw_m3")
CLES_PROJET = ("texte", "fluide_actuel", "fluide_cible", "type_equipement", "type_equipement_cible", "precision",
               "date_analyse")
CLES_POSTE = ("id", "nom", "dessert", "fluide", "temperature_chambre", "volume", "regime", "charge", "compresseurs",
              "evaporateurs", "plaques_ensemble", "estimations")
CLES_COMPRESSEUR = ("id", "marque", "modele", "volume_balaye", "lecture", "note", "frequence", "estimation")
CLES_EVAPORATEUR = ("id", "modele", "annee", "fluide_origine", "source")
CLES_PLAQUE = ("id", "texte", "puissance", "fluide", "regime")
CLES_ESTIMATION = ("id", "texte", "puissance")
CLES_REGIME = ("t0", "tc")
CLES_CHOIX = ("valeur", "source", "statut", "id")
CLES_TEXTE = ("texte", "source", "statut")
UNITES_PARAMETRES = {"gaz_aspire": ("°C",), "surchauffe": ("K",), "sous_refroidissement": ("K",),
                     "seuil_ecart": ("%",), "seuil_t0": ("K",), "seuil_tc": ("K",), "marge_pct": ("%",),
                     "ratio_kw_m3": ("kW/m³", "kW/m3")}
CHOIX_PARAMETRES = {"convention": ("rosee", "moyenne"), "lambda_methode": ("table_a", "efpme"), "fluide_base": None}

# Sources reconnues (texte sans accents, minuscules). Une source hors de ces formes donne un avertissement.
MOTIFS_SOURCE = re.compile(
    r"photo p\d|rapport p\.? ?\d|dicte par loic|hypothese|lecture douteuse|suppose|savoir/|methodes/|materiel/"
    r"|fluides/|regles-loic|web ?:|https?://|calcul|conversation|1-existant|dossier\.md|estimation|plaque|catalogue"
    r"|a confirmer|absent|illisible|inconnu|(non|pas) (ecrit|releve|lu|indique|photographie|donne|precise)")


def marge_par_defaut() -> Valeur:
    """Marge par défaut : 0 %, hypothèse écrite (aucune marge n'est inventée ; décision du 2026-10-06)."""
    return Valeur(0.0, "%", "hypothèse en attente de la réponse de Loïc (question 2 du 2026-10-06) : 0 %, aucune marge "
                  "ajoutée à la puissance existante (methodes/puissance-existante.md § 5)", HYPOTHESE, id="param-marge")


# ---------- outils ----------
def _sa(texte: Any) -> str:
    """Sans accents, minuscules, espaces simples."""
    t = unicodedata.normalize("NFKD", "" if texte is None else str(texte))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.replace(" ", " ")).strip().lower()


def _lecture(texte: Any) -> str:
    return LECTURES.get(_sa(texte), "")


def _meme_modele(a: Any, b: Any) -> bool:
    return str(a or "").strip().upper().replace(" ", "") == str(b or "").strip().upper().replace(" ", "")


def _esc(texte: Any) -> str:
    """Contenu d'une cellule markdown : « | » échappé, retours à la ligne aplatis."""
    return re.sub(r"\s*\n\s*", " ", str(texte if texte is not None else "")).replace("|", "\\|").strip()


def _cellule(morceaux: list[str]) -> str:
    """Plusieurs éléments dans une cellule, chacun échappé, séparés par un saut de ligne HTML."""
    return "<br>".join(_esc(m) for m in morceaux if m) or "—"


def _ligne(cellules: list[str]) -> str:
    return "| " + " | ".join(cellules) + " |"


def _signe(v: Valeur, marque: bool = False) -> str:
    """Écart signé : « +23,4 % », « -5,9 % » ou « à confirmer » (le nombre vient de Valeur.texte())."""
    t = v.texte(marque=marque)
    nul = re.fullmatch(r"0(,0+)?", t.split(" ")[0]) is not None     # « 0,0 % » : pas de signe
    return ("+" + t) if v.nombre is not None and v.nombre > 0 and not nul and not t.startswith("+") else t


def _regime_txt(regime: dict) -> str:
    return f"{regime['t0'].texte(0, marque=False)} / {regime['tc'].texte(0, marque=False)}"


def _au_plus(v: Valeur, statut: str, ref: str) -> Valeur:
    """Plafonne le statut de v (un résultat n'est jamais plus sûr qu'une lecture douteuse ou qu'un fluide supposé)."""
    if v is None or v.nombre is None:
        return v
    nouveau = combiner([v.statut, statut])
    entrees = v.entrees + ((ref,) if ref and ref not in v.entrees else ())
    return replace(v, statut=nouveau, entrees=entrees)


def _ecart_signe(calcule: Valeur, reference: Valeur, id: str, source: str) -> Valeur:
    """(calcule − reference) ÷ reference × 100, en %, signé."""
    rc, rr = calcule.reference(), reference.reference()
    return calculer(lambda: (calcule.nombre - reference.nombre) / reference.nombre * POURCENT, "%",
                    f"({rc} − {rr}) ÷ {rr} × 100", [calcule, reference], source=source, id=id)


def _verdict_plafonne(v: dict | None, statut: str, ref: str) -> dict | None:
    """Verdict de fgas.py plafonné par le statut du fluide : PRP, tCO2e et mesure deviennent au mieux `statut`, et
    chaque section (étanchéité, interdictions) le porte dans « fiabilite » (sa clé « statut » est l'état réglementaire,
    ex. « à venir ») : « (hyp.) » au tableau D. Un résultat qui dépend
    d'un fluide supposé n'est jamais plus sûr que ce fluide."""
    if v is None:
        return None
    v = dict(v)
    for cle in ("prp", "tco2e"):
        if isinstance(v.get(cle), Valeur):
            v[cle] = _au_plus(v[cle], statut, ref)
    for cle in ("etancheite", "interdiction_entretien", "interdiction_mise_sur_le_marche"):
        d = dict(v[cle])
        if isinstance(d.get("mesure"), Valeur):
            d["mesure"] = _au_plus(d["mesure"], statut, ref)
        d["fiabilite"] = combiner([d.get("fiabilite", SOURCE), statut])
        d["fiabilite_depuis"] = ref
        v[cle] = d
    v["fiabilite"] = combiner([v.get("fiabilite", SOURCE), statut])
    return v


def _statut_choix(c: dict | None) -> str:
    try:
        return normaliser_statut((c or {}).get("statut", A_CONFIRMER))
    except ValueError:
        return A_CONFIRMER


# =====================================================================================================
# Lecture et vérification des entrées
# =====================================================================================================
class EntreesIllisibles(ValueError):
    """2-entrees.json absent ou JSON invalide (code de sortie 2)."""


def _erreurs_valeurs(obj: Any, chemin: str = "") -> list[str]:
    """Toutes les Valeur invalides du JSON brut, avec leur chemin (quand depuis_json s'arrête à la première)."""
    erreurs = []
    if isinstance(obj, dict):
        if "nombre" in obj and any(k in obj for k in ("unite", "source", "statut")):
            try:
                Valeur.depuis_dict(obj)
            except ValueError as exc:
                erreurs.append(f"ERREUR · {chemin or 'racine'} : {exc}")
            return erreurs
        for k, v in obj.items():
            erreurs += _erreurs_valeurs(v, f"{chemin}.{k}" if chemin else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            erreurs += _erreurs_valeurs(v, f"{chemin}[{i}]")
    return erreurs


def charger_entrees(dossier: Path) -> tuple[dict | None, list[str]]:
    """Lit <dossier>/2-entrees.json. Rend (entrées avec des Valeur, []) ou (None, erreurs). JSON illisible ou fichier
    absent : EntreesIllisibles."""
    chemin = Path(dossier) / ENTREES
    if not chemin.is_file():
        raise EntreesIllisibles(f"{chemin} introuvable (Claude le remplit à l'étape 3 du skill)")
    texte = chemin.read_text(encoding="utf-8")
    try:
        brut = json.loads(texte)
    except json.JSONDecodeError as exc:
        raise EntreesIllisibles(f"{ENTREES} : JSON invalide ({exc})") from None
    if not isinstance(brut, dict):
        raise EntreesIllisibles(f"{ENTREES} : objet JSON attendu à la racine")
    erreurs = _erreurs_valeurs(brut)
    if erreurs:
        return None, erreurs
    return depuis_json(texte), []


class _Rapport:
    def __init__(self) -> None:
        self.erreurs: list[str] = []
        self.attentions: list[str] = []
        self.ids: dict[str, str] = {}

    def erreur(self, chemin: str, msg: str) -> None:
        self.erreurs.append(f"ERREUR · {chemin} : {msg}")

    def attention(self, chemin: str, msg: str) -> None:
        self.attentions.append(f"ATTENTION · {chemin} : {msg}")

    def id(self, chemin: str, ident: Any, obligatoire: bool = True) -> None:
        if not isinstance(ident, str) or not ident.strip():
            if obligatoire:
                self.erreur(chemin, "id manquant (chaque objet et chaque Valeur porte un id unique)")
            return
        if ident in self.ids:
            self.erreur(chemin, f"id « {ident} » en double (déjà utilisé en {self.ids[ident]})")
        else:
            self.ids[ident] = chemin

    def cles(self, chemin: str, obj: Any, attendues: tuple, obligatoires: tuple = ()) -> bool:
        if not isinstance(obj, dict):
            self.erreur(chemin, "objet JSON attendu")
            return False
        for k in obj:
            if k not in attendues:
                self.erreur(chemin, f"clé inconnue « {k} » ; clés attendues : {', '.join(attendues)}")
        for k in obligatoires:
            if obj.get(k) in (None, ""):
                self.erreur(chemin, f"clé « {k} » manquante")
        return True

    def source(self, chemin: str, texte: Any) -> None:
        if not MOTIFS_SOURCE.search(_sa(texte)):
            self.attention(chemin, f"source non reconnue « {texte} » (attendu : photo pNN-k, rapport p. N, dicté par "
                                   "Loïc le …, hypothèse : …, savoir/… , web : <lien>, ou la raison d'un « à confirmer »)")

    def valeur(self, chemin: str, v: Any, unites: tuple, obligatoire: bool = True) -> Valeur | None:
        if v is None:
            if obligatoire:
                self.erreur(chemin, "Valeur manquante (écrire une Valeur « à confirmer » avec la raison en source)")
            return None
        if not isinstance(v, Valeur):
            self.erreur(chemin, "Valeur attendue : {\"id\", \"nombre\", \"unite\", \"source\", \"statut\"}")
            return None
        self.id(chemin, v.id)
        if v.unite not in unites:
            self.erreur(chemin, f"unité « {v.unite} » ; attendue : {' ou '.join(unites)}")
        self.source(chemin, v.source)
        s = _sa(v.source)
        if v.statut == SOURCE and s.startswith("hypothese"):
            self.erreur(chemin, "statut « sourcé » mais la source commence par « hypothèse »")
        if v.statut == HYPOTHESE and not re.search(r"hypothese|lecture douteuse|suppose|estimation", s):
            self.attention(chemin, "statut « hypothèse » : dire pourquoi dans la source (« hypothèse : … »)")
        return v

    def choix(self, chemin: str, c: Any, obligatoire: bool = True, permis: tuple | None = None,
              fluide: str = "") -> dict | None:
        """fluide : « coolprop » (doit être calculable) ou « fgas » (doit être connu de prp.csv)."""
        if c is None:
            if obligatoire:
                self.erreur(chemin, "choix manquant : {\"valeur\", \"source\", \"statut\", \"id\"}")
            return None
        if not self.cles(chemin, c, CLES_CHOIX, ("source", "statut", "id")):
            return None
        self.id(chemin, c.get("id"))
        try:
            statut = normaliser_statut(c.get("statut"))
        except ValueError as exc:
            self.erreur(chemin, str(exc))
            return None
        valeur = c.get("valeur")
        if (valeur in (None, "")) != (statut == A_CONFIRMER):
            self.erreur(chemin, f"valeur {valeur!r} incompatible avec le statut « {statut} » (vide ⇔ « à confirmer »)")
        self.source(chemin, c.get("source"))
        if valeur not in (None, ""):
            if permis and valeur not in permis:
                self.erreur(chemin, f"valeur « {valeur} » ; possibles : {', '.join(permis)}")
            if fluide == "coolprop":
                try:
                    fluides.nom_coolprop(valeur)
                except ValueError as exc:
                    self.erreur(chemin, f"fluide inconnu de CoolProp : {exc}")
            elif fluide == "fgas" and fgas.nom_canonique(valeur) is None:
                self.attention(chemin, f"fluide « {valeur} » absent de fluides/prp.csv : bloc D « à confirmer »")
        return c

    def texte(self, chemin: str, t: Any, obligatoire: bool = True) -> None:
        if t is None:
            if obligatoire:
                self.erreur(chemin, "texte sourcé manquant : {\"texte\", \"source\", \"statut\"}")
            return
        if not self.cles(chemin, t, CLES_TEXTE, CLES_TEXTE):
            return
        try:
            normaliser_statut(t.get("statut"))
        except ValueError as exc:
            self.erreur(chemin, str(exc))
        self.source(chemin, t.get("source"))

    def regime(self, chemin: str, reg: Any, obligatoire: bool = True) -> None:
        if reg is None:
            if obligatoire:
                self.erreur(chemin, "régime manquant : {\"t0\": Valeur °C, \"tc\": Valeur °C}")
            return
        if not self.cles(chemin, reg, CLES_REGIME, CLES_REGIME):
            return
        t0 = self.valeur(f"{chemin}.t0", reg.get("t0"), ("°C",))
        tc = self.valeur(f"{chemin}.tc", reg.get("tc"), ("°C",))
        if t0 is not None and tc is not None and t0.nombre is not None and tc.nombre is not None \
                and t0.nombre >= tc.nombre:
            self.erreur(chemin, f"évaporation {t0.texte()} ≥ condensation {tc.texte()}")


def verifier(e: dict) -> tuple[list[str], list[str]]:
    """Cohérence de 2-entrees.json (déjà converti par depuis_json). Rend (erreurs, avertissements)."""
    r = _Rapport()
    if not r.cles("racine", e, CLES_RACINE, ("projet", "postes")):
        return r.erreurs, r.attentions
    if e.get("format") != FORMAT_ENTREES:
        r.attention("format", f"« {e.get('format')} » ; attendu « {FORMAT_ENTREES} »")

    # paramètres
    params = e.get("parametres") or {}
    if r.cles("parametres", params, CLES_PARAMETRES_ENTREES):
        for k, v in params.items():
            if k in UNITES_PARAMETRES:
                r.valeur(f"parametres.{k}", v, UNITES_PARAMETRES[k], obligatoire=False)
            elif k in CHOIX_PARAMETRES:
                r.choix(f"parametres.{k}", v, permis=CHOIX_PARAMETRES[k],
                        fluide="coolprop" if k == "fluide_base" else "")
        try:
            parametres_effectifs({k: v for k, v in params.items() if k in CLES_PARAMETRES})
        except (ValueError, TypeError) as exc:
            r.erreur("parametres", str(exc))

    # projet
    projet = e.get("projet") or {}
    postes = e.get("postes") or []
    ids_postes = [p.get("id") for p in postes if isinstance(p, dict)]
    if r.cles("projet", projet, CLES_PROJET, ("fluide_actuel",)):
        r.texte("projet.texte", projet.get("texte"))
        r.choix("projet.fluide_actuel", projet.get("fluide_actuel"), fluide="coolprop")
        cible = r.choix("projet.fluide_cible", projet.get("fluide_cible"), obligatoire=False, fluide="fgas")
        if cible and cible.get("valeur") and not projet.get("type_equipement_cible"):
            r.erreur("projet.type_equipement_cible", "manquant (type du futur équipement, ex. « centrale »)")
        if projet.get("type_equipement_cible") and not fgas.decrire_equipement(projet["type_equipement_cible"]).reconnu:
            r.attention("projet.type_equipement_cible", f"type « {projet['type_equipement_cible']} » non reconnu par fgas.py")
        types = projet.get("type_equipement") or {}
        if not isinstance(types, dict):
            r.erreur("projet.type_equipement", "objet {\"<id du poste>\": \"<type>\"} attendu")
            types = {}
        for pid, t in types.items():
            if pid not in ids_postes:
                r.erreur(f"projet.type_equipement.{pid}", "id de poste inconnu")
            elif not fgas.decrire_equipement(t).reconnu:
                r.attention(f"projet.type_equipement.{pid}", f"type « {t} » non reconnu par fgas.py (règles sous conditions)")
        for pid in ids_postes:
            if pid not in types:
                r.attention(f"projet.type_equipement.{pid}", "type d'équipement absent : règles F-gas sous conditions")
        if projet.get("precision") and projet["precision"] not in PRECISIONS:
            r.attention("projet.precision", f"« {projet['precision']} » ; attendu : {' ou '.join(PRECISIONS)}")
        if not projet.get("date_analyse"):
            r.attention("projet.date_analyse", "absente : date du jour utilisée pour les règles F-gas (non reproductible)")
        else:
            try:
                dt.date.fromisoformat(str(projet["date_analyse"]))
            except ValueError:
                r.erreur("projet.date_analyse", f"« {projet['date_analyse']} » : format attendu AAAA-MM-JJ")

    # postes
    if not isinstance(postes, list) or not postes:
        r.erreur("postes", "liste d'au moins un poste attendue")
        return r.erreurs, r.attentions
    for i, poste in enumerate(postes):
        ch = f"postes[{i}]"
        if not r.cles(ch, poste, CLES_POSTE, ("id", "nom", "regime")):
            continue
        ch = f"postes[{i}] ({poste.get('id')})"
        r.id(ch, poste.get("id"))
        r.texte(f"{ch}.dessert", poste.get("dessert"))
        fl = r.choix(f"{ch}.fluide", poste.get("fluide"), obligatoire=False, fluide="coolprop")
        r.valeur(f"{ch}.temperature_chambre", poste.get("temperature_chambre"), ("°C",))
        r.valeur(f"{ch}.volume", poste.get("volume"), ("m³", "m3"))
        r.regime(f"{ch}.regime", poste.get("regime"))
        r.valeur(f"{ch}.charge", poste.get("charge"), ("kg",))
        if fl is None and not (projet.get("fluide_actuel") or {}).get("valeur"):
            r.attention(ch, "fluide à confirmer : M1, M2 et bloc D « à confirmer »")
        comps = poste.get("compresseurs") or []
        if not comps:
            r.attention(f"{ch}.compresseurs", "aucun compresseur : puissance existante « à confirmer »")
        for j, c in enumerate(comps):
            cc = f"{ch}.compresseurs[{j}]"
            if not r.cles(cc, c, CLES_COMPRESSEUR, ("id", "lecture")):
                continue
            cc = f"{ch}.compresseurs[{j}] ({c.get('id')})"
            r.id(cc, c.get("id"))
            lecture = _lecture(c.get("lecture"))
            if not lecture:
                r.erreur(cc, f"lecture « {c.get('lecture')} » ; attendue : sûre, douteuse ou illisible")
            vb = r.valeur(f"{cc}.volume_balaye", c.get("volume_balaye"), ("m³/h", "m3/h"))
            freq = r.valeur(f"{cc}.frequence", c.get("frequence"), ("Hz",), obligatoire=False)
            r.valeur(f"{cc}.estimation", c.get("estimation"), ("kW",), obligatoire=False)
            if freq is not None and freq.nombre is not None and freq.nombre != FREQUENCE_ATTENDUE_HZ:
                r.attention(f"{cc}.frequence", f"{freq.texte()} : M1 et M2 refusés (50 Hz uniquement)")
            if vb is not None and lecture == DOUTEUSE:
                if vb.nombre is not None and vb.statut != HYPOTHESE:
                    r.erreur(f"{cc}.volume_balaye", f"lecture douteuse : statut « hypothèse » attendu (reçu « {vb.statut} »)")
                if vb.nombre is not None and MOTIF_DOUTE not in _sa(vb.source):
                    r.erreur(f"{cc}.volume_balaye", "lecture douteuse : écrire « lecture douteuse : … » dans la source")
                if vb.nombre is None:
                    r.attention(f"{cc}.volume_balaye", "lecture douteuse sans volume : plutôt « illisible »")
            if vb is not None and lecture == ILLISIBLE and vb.nombre is not None:
                r.erreur(f"{cc}.volume_balaye", "plaque illisible : le volume balayé doit être « à confirmer » (nombre null)")
            if lecture == ILLISIBLE and c.get("modele"):
                r.attention(cc, "plaque illisible : le modèle est ignoré (si seul le volume manque, lecture « sûre »)")
            if lecture in (SURE, DOUTEUSE) and not c.get("modele"):
                r.attention(cc, "modèle absent : M2 impossible")
        for j, ev in enumerate(poste.get("evaporateurs") or []):
            ce = f"{ch}.evaporateurs[{j}]"
            if r.cles(ce, ev, CLES_EVAPORATEUR, ("modele", "source")):
                r.id(ce, ev.get("id"), obligatoire=False)
                r.source(ce, ev.get("source"))
        for j, pl in enumerate(poste.get("plaques_ensemble") or []):
            cp = f"{ch}.plaques_ensemble[{j}]"
            if not r.cles(cp, pl, CLES_PLAQUE, ("id", "texte")):
                continue
            r.id(cp, pl.get("id"))
            r.valeur(f"{cp}.puissance", pl.get("puissance"), ("kW",))
            r.choix(f"{cp}.fluide", pl.get("fluide"), obligatoire=False, fluide="coolprop")
            r.regime(f"{cp}.regime", pl.get("regime"), obligatoire=False)
        for j, es in enumerate(poste.get("estimations") or []):
            cs = f"{ch}.estimations[{j}]"
            if r.cles(cs, es, CLES_ESTIMATION, ("id", "texte")):
                r.id(cs, es.get("id"))
                r.valeur(f"{cs}.puissance", es.get("puissance"), ("kW",))
    return r.erreurs, r.attentions


# =====================================================================================================
# Calculs
# =====================================================================================================
def _parametres_entrees(e: dict) -> tuple[dict, Valeur, Valeur | None, list[str]]:
    """Paramètres effectifs (défauts de compresseurs.py complétés), marge, ratio, liste des clés prises par défaut."""
    donnes = dict(e.get("parametres") or {})
    marge = donnes.pop("marge_pct", None) or marge_par_defaut()
    ratio = donnes.pop("ratio_kw_m3", None)
    p = parametres_effectifs(donnes)
    defauts = [k for k in CLES_PARAMETRES if k not in donnes and p.get(k) is not None]
    if "marge_pct" not in (e.get("parametres") or {}):
        defauts.append("marge_pct")
    return p, marge, ratio, defauts


def _resultat_a_confirmer(cid: str, modele: str, fluide: str, raison: str, p: dict) -> dict:
    q1 = a_confirmer("kW", f"M1 cylindrée : {raison}", id=f"{cid}-m1")
    q2 = a_confirmer("kW", f"M2 point catalogue : {raison}", id=f"{cid}-m2")
    return {"id": cid, "modele": modele, "fluide": fluide,
            "m1": {"methode": "M1 cylindrée", "q0": q1, "raison": raison},
            "m2": {"methode": "M2 point catalogue", "q0": q2, "cas": "refus", "alertes": [], "raison": raison},
            "ecart": comparer(q1, q2, p["seuil_ecart"], id=f"{cid}-ecart"),
            "ecart_sur_m2": a_confirmer("%", f"écart : {raison}", id=f"{cid}-ecart-sur-m2"),
            "retenue": a_confirmer("kW", f"ni M2 ni M1 : {raison}", id=f"{cid}-retenue"), "regle": "aucune",
            "alertes": []}


def _volume_catalogue(c: dict, points: list[dict]) -> dict | None:
    """Volume balayé du catalogue pour ce modèle (50 Hz) comparé à celui de la plaque."""
    vb = c.get("volume_balaye")
    if not c.get("modele") or vb is None or vb.nombre is None:
        return None
    pts = [pt for pt in points if _meme_modele(pt.get("modele"), c["modele"])
           and pt.get("volume_balaye_m3h") is not None and pt.get("frequence_hz") == FREQUENCE_ATTENDUE_HZ]
    if not pts:
        return None
    pt = pts[0]
    cat = Valeur(pt["volume_balaye_m3h"], "m³/h", f"{pt['document']}, p. {pt['page']} ({pt['fichier']}, ligne "
                 f"{pt['ligne']})", SOURCE, id=f"{c['id']}-volume-catalogue")
    ecart = _ecart_signe(vb, cat, f"{c['id']}-volume-ecart", "écart signé du volume balayé de la plaque sur celui du "
                         "catalogue")
    return {"catalogue": cat, "ecart": ecart,
            "signale": ecart.nombre is not None and abs(ecart.nombre) > SEUIL_VOLUME_PCT}


def _calculer_compresseur(c: dict, fl: dict | None, regime: dict, points: list[dict], p: dict) -> dict:
    """M1, M2, écarts et valeur retenue d'un compresseur, statuts plafonnés par la lecture et le fluide."""
    cid = c["id"]
    lecture = _lecture(c.get("lecture"))
    modele = c.get("modele") or ""
    fluide = (fl or {}).get("valeur") or ""
    if not fluide:
        r = _resultat_a_confirmer(cid, modele, "", f"fluide du poste à confirmer ({(fl or {}).get('source', 'non renseigné')})", p)
    elif lecture == ILLISIBLE:
        vb = c.get("volume_balaye")
        r = _resultat_a_confirmer(cid, "", fluide, f"plaque illisible ({vb.source if vb else 'source non donnée'}) : "
                                  "demander la photo d'origine à Loïc", p)
    else:
        entree = {"id": cid, "modele": modele, "fluide": fluide, "t0": regime["t0"], "tc": regime["tc"]}
        if c.get("volume_balaye") is not None:
            entree["volume_balaye"] = c["volume_balaye"]
        if c.get("frequence") is not None:
            entree["frequence"] = c["frequence"]
        r = puissance_compresseur(entree, points, p)
    plafonds = []
    if lecture == DOUTEUSE:
        plafonds.append((HYPOTHESE, f"{cid}-lecture-douteuse"))
    statut_fl = _statut_choix(fl)
    if fl and fluide and RANG[statut_fl] > RANG[SOURCE]:
        plafonds.append((statut_fl, fl.get("id", "")))
    for statut, ref in plafonds:
        r["m1"]["q0"] = _au_plus(r["m1"]["q0"], statut, ref)
        r["m2"]["q0"] = _au_plus(r["m2"]["q0"], statut, ref)
        r["retenue"] = _au_plus(r["retenue"], statut, ref)
    r["marque"] = c.get("marque") or ""
    r["lecture"] = lecture
    r["note"] = c.get("note") or ""
    r["volume_balaye"] = c.get("volume_balaye")
    r["volume_catalogue"] = _volume_catalogue(c, points) if lecture != ILLISIBLE else None
    return r


def _controle_plaque(pl: dict, comps: list[dict], fl: dict | None, regime: dict, existante: Valeur, p: dict,
                     points: list[dict]) -> dict:
    """Plaque d'ensemble : comparée aux mêmes compresseurs recalculés au fluide (et au régime) de la plaque."""
    plid = pl["id"]
    puissance = pl["puissance"]
    fl_pl, reg_pl = pl.get("fluide"), pl.get("regime")
    fluide_poste = (fl or {}).get("valeur") or ""
    fluide_calc = (fl_pl or {}).get("valeur") or fluide_poste
    regime_calc = reg_pl or regime
    autre_fluide = bool(fluide_calc and fluide_poste
                        and fluides.nom_coolprop(fluide_calc) != fluides.nom_coolprop(fluide_poste))
    autre_regime = reg_pl is not None and (reg_pl["t0"].nombre, reg_pl["tc"].nombre) != (regime["t0"].nombre,
                                                                                          regime["tc"].nombre)
    recalcul = []
    if autre_fluide or autre_regime:
        for c in comps:
            sous = _calculer_compresseur({**c, "id": f"{plid}-{c['id']}"}, fl_pl or fl, regime_calc, points, p)
            m2 = sous["m2"]
            recalcul.append({"id": sous["id"], "compresseur": c["id"], "retenue": sous["retenue"], "regle": sous["regle"],
                             "conversion": bool(m2.get("conversion")), "fluide_donnees": m2.get("fluide_donnees"),
                             "q0_base": m2.get("q0_base"), "points": m2.get("points") or []})
        reference = somme([s["retenue"] for s in recalcul], "kW", id=f"{plid}-recalcul",
                          source=f"mêmes compresseurs recalculés au {fluide_calc}, {_regime_txt(regime_calc)} "
                                 "(M2 si disponible, sinon M1)") if recalcul else existante
        libelle = f"compresseurs du poste au {fluide_calc}, {_regime_txt(regime_calc)}"
    else:
        reference = existante
        libelle = "puissance existante du poste"
    ecart = _ecart_signe(reference, puissance, f"{plid}-ecart", "écart signé du calcul sur la plaque d'ensemble")
    # Seconde lecture : points catalogue tels quels, sans conversion de fluide (cas d'un catalogue qui publie un
    # tableau commun aux deux fluides, ex. « R404A/R507A »).
    sans_conversion = ecart_sans = None
    communs = []
    if recalcul and all(s["conversion"] and s["q0_base"] is not None for s in recalcul):
        fl_donnees = recalcul[0]["fluide_donnees"]
        communs = [s["compresseur"] for s in recalcul
                   if any(fluide_calc.upper() in str(pt.get("note") or "").upper() for pt in s["points"])]
        sans_conversion = somme([s["q0_base"] for s in recalcul], "kW", id=f"{plid}-sans-conversion",
                                source=f"points catalogue au {fl_donnees} tels quels, sans conversion au {fluide_calc}")
        ecart_sans = _ecart_signe(sans_conversion, puissance, f"{plid}-ecart-sans-conversion",
                                  "écart signé des points catalogue sans conversion sur la plaque d'ensemble")
    if reg_pl is not None:
        cmp = comparer(reference, puissance, p["seuil_ecart"], id=f"{plid}-ecart-moyenne")
        depassement, portee = cmp["depassement"], f"au régime de la plaque, seuil {p['seuil_ecart'].texte()}"
    else:
        depassement, portee = None, "indicatif : régime de la plaque non indiqué, calcul au régime du poste"
    return {"id": plid, "texte": pl.get("texte", ""), "puissance": puissance, "fluide": fluide_calc,
            "regime": regime_calc, "reference": reference, "libelle": libelle, "recalcul": recalcul, "ecart": ecart,
            "sans_conversion": sans_conversion, "ecart_sans_conversion": ecart_sans, "tableau_commun": communs,
            "depassement": depassement, "portee": portee}


def _variantes_fluide(poste: dict, fluide_nom: str, type_eq: str, charge: Valeur | None, date: Any,
                      capacite: Valeur | None) -> list[dict]:
    """Fluide actuel supposé : mêmes calculs F-gas pour chaque autre fluide qu'indique une plaque du poste (plaque
    d'ensemble, fluide d'origine d'un évaporateur). Chaque variante est une hypothèse."""
    pid = poste["id"]
    actuel = fgas.nom_canonique(fluide_nom) or fluide_nom
    origines: dict[str, list[str]] = {}
    for pl in poste.get("plaques_ensemble") or []:
        c = pl.get("fluide") or {}
        nom = fgas.nom_canonique(c.get("valeur")) if c.get("valeur") else None
        if nom and nom != actuel:
            origines.setdefault(nom, []).append(f"plaque d'ensemble {pl['id']}")
    for ev in poste.get("evaporateurs") or []:
        nom = fgas.nom_canonique(ev.get("fluide_origine")) if ev.get("fluide_origine") else None
        if nom and nom != actuel:
            origines.setdefault(nom, []).append(" ".join(x for x in ("évaporateur", ev.get("id"), ev.get("modele"),
                                                                     f"de {ev['annee']}" if ev.get("annee") else "")
                                                         if x))
    res = []
    for nom, orig in origines.items():
        cle = re.sub(r"[^a-z0-9]+", "-", _sa(nom)).strip("-")
        ref = f"{pid}-variante-{cle}"
        verdict = _verdict_plafonne(fgas.verdict_fluide(nom, type_eq, charge, date, capacite), HYPOTHESE, ref)
        tco2 = _au_plus(fgas.tco2e(charge, nom, id=f"{pid}-tco2e-{cle}"), HYPOTHESE, ref)
        res.append({"fluide": nom, "origines": orig, "tco2e": tco2, "verdict": verdict})
    return res


def _calculer_poste(poste: dict, projet: dict, p: dict, marge: Valeur, ratio: Valeur | None, points: list[dict],
                    date: Any) -> dict:
    pid = poste["id"]
    fl = poste.get("fluide") or projet.get("fluide_actuel")
    regime = poste["regime"]
    comps_entrees = poste.get("compresseurs") or []
    comps = [_calculer_compresseur(c, fl, regime, points, p) for c in comps_entrees]
    for c, ce in zip(comps, comps_entrees):
        est = ce.get("estimation")
        c["estimation"] = None if est is None else {
            "puissance": est,
            "m1_sur_estimation": _ecart_signe(c["m1"]["q0"], est, f"{c['id']}-m1-sur-estimation",
                                              "écart signé de M1 sur l'estimation antérieure (rendement volumétrique "
                                              "et conditions de calcul ; mêmes volumes balayés)"),
            "retenue_sur_m1": _ecart_signe(c["retenue"], c["m1"]["q0"], f"{c['id']}-retenue-sur-m1",
                                           "écart signé de la valeur retenue sur M1 (effet du choix de M2)"),
            "retenue_sur_estimation": _ecart_signe(c["retenue"], est, f"{c['id']}-retenue-sur-estimation",
                                                   "écart signé de la valeur retenue sur l'estimation antérieure")}
    retenues = [c["retenue"] for c in comps]
    if retenues:
        existante = somme(retenues, "kW", id=f"{pid}-existante",
                          source="somme des puissances retenues des compresseurs du poste")
    else:
        existante = a_confirmer("kW", "aucun compresseur relevé pour ce poste", id=f"{pid}-existante")
    lues = [v for v in retenues if v.nombre is not None]
    partielle = None
    if existante.nombre is None and lues:
        partielle = somme(lues, "kW", id=f"{pid}-somme-partielle",
                          source=f"somme partielle des {len(lues)} compresseur(s) lu(s) sur {len(retenues)} : ne "
                                 "remplace pas la puissance du poste (à confirmer)")
    demandee = puissance_demandee(existante, marge, id=f"{pid}-demandee")

    plaques = [_controle_plaque(pl, comps_entrees, fl, regime, existante, p, points)
               for pl in poste.get("plaques_ensemble") or []]
    estimations = [{"id": es["id"], "texte": es.get("texte", ""), "puissance": es["puissance"],
                    "ecart": _ecart_signe(existante, es["puissance"], f"{es['id']}-ecart",
                                          "écart signé du calcul du jour sur l'estimation antérieure")}
                   for es in poste.get("estimations") or []]
    volume = poste.get("volume")
    controle_ratio = None
    if ratio is not None and volume is not None:
        pr = calculer(lambda: volume.nombre * ratio.nombre, "kW", f"{volume.reference()} × {ratio.reference()}",
                      [volume, ratio], source="ratio de Loïc × volume de la chambre", id=f"{pid}-ratio")
        controle_ratio = {"puissance": pr, "ratio": ratio,
                          "ecart": _ecart_signe(existante, pr, f"{pid}-ratio-ecart",
                                                "écart signé de la puissance existante sur le ratio de Loïc")}

    # fluide et conformité (bloc D)
    fluide_nom = (fl or {}).get("valeur") or ""
    type_eq = (projet.get("type_equipement") or {}).get(pid, "")
    charge = poste.get("charge")
    capacite = existante if existante.nombre is not None else None
    statut_fl = _statut_choix(fl)
    suppose = bool(fluide_nom) and RANG[statut_fl] > RANG[SOURCE]
    variantes = []
    if fluide_nom:
        verdict = fgas.verdict_fluide(fluide_nom, type_eq, charge, date, capacite)
        tco2 = fgas.tco2e(charge, fluide_nom, id=f"{pid}-tco2e")
        if suppose:
            verdict = _verdict_plafonne(verdict, statut_fl, fl.get("id", ""))
            tco2 = _au_plus(tco2, statut_fl, fl.get("id", ""))
            variantes = _variantes_fluide(poste, fluide_nom, type_eq, charge, date, capacite)
    else:
        verdict = None
        tco2 = a_confirmer("tCO2e", "fluide à confirmer", id=f"{pid}-tco2e")

    # remarques (tableau C) et relevés pour le bloc G
    remarques, alertes = [], []
    if partielle is not None:
        n, n_conf = len(lues), len(retenues) - len(lues)
        remarques.append(f"somme des {n} compresseur{'s' if n > 1 else ''} lu{'s' if n > 1 else ''} : "
                         f"{partielle.texte()} ({n_conf} à confirmer)")
    for c in comps:
        nom_c = f"{c['id']} ({c['modele'] or 'modèle à confirmer'})"
        if c["lecture"] == DOUTEUSE:
            remarques.append(f"{nom_c} : lecture douteuse, {c['note'] or c['volume_balaye'].source}")
        if c["lecture"] == ILLISIBLE:
            remarques.append(f"{nom_c} : plaque illisible, à confirmer ({c['note'] or 'photo d’origine à demander'})")
        if c["regle"] == "M1":
            remarques.append(f"{nom_c} : M2 indisponible, M1 seule (indicatif)")
        vc = c.get("volume_catalogue")
        if vc and vc["signale"]:
            remarques.append(f"{nom_c} : volume balayé plaque {c['volume_balaye'].texte(marque=False)}, catalogue "
                             f"{vc['catalogue'].texte()} ({_signe(vc['ecart'])}) : lecture ou variante à revérifier "
                             "(M1 suit la plaque)")
        for al in c["alertes"]:
            alertes.append(f"{nom_c} : {al}")
    if fl and fluide_nom and _statut_choix(fl) != SOURCE:
        remarques.append(f"fluide {fluide_nom} : {_statut_choix(fl)} (source en bloc G)")
    for pl in plaques:
        if pl["depassement"]:
            alertes.append(f"plaque d'ensemble {pl['id']} : écart {_signe(pl['ecart'])} au-delà du seuil")
    return {"id": pid, "nom": poste.get("nom", pid), "dessert": poste.get("dessert"), "fluide": fl,
            "type_equipement": type_eq, "regime": regime, "temperature_chambre": poste.get("temperature_chambre"),
            "volume": volume, "charge": charge, "compresseurs": comps, "existante": existante,
            "somme_partielle": partielle, "marge": marge, "demandee": demandee, "plaques": plaques,
            "estimations": estimations, "ratio": controle_ratio, "verdict": verdict, "tco2e": tco2,
            "variantes_fluide": variantes,
            "evaporateurs": poste.get("evaporateurs") or [], "remarques": remarques, "alertes": alertes}


def _sous_totaux(postes: list[dict]) -> list[dict]:
    """Sous-total par régime (T0, Tc) dès que deux postes au moins le partagent (ex. tout le négatif)."""
    groupes: dict[tuple, list[dict]] = {}
    for pr in postes:
        t0, tc = pr["regime"]["t0"], pr["regime"]["tc"]
        if t0.nombre is not None and tc.nombre is not None:
            groupes.setdefault((t0.nombre, tc.nombre), []).append(pr)
    res = []
    for prs in groupes.values():
        if len(prs) < 2:
            continue
        ident = "-".join(pr["id"] for pr in prs)
        noms = ", ".join(pr["nom"] for pr in prs)
        ex = somme([pr["existante"] for pr in prs], "kW", id=f"sous-total-{ident}",
                   source=f"somme des puissances existantes des postes au même régime ({noms})")
        de = somme([pr["demandee"] for pr in prs], "kW", id=f"sous-total-demande-{ident}",
                   source=f"somme des puissances demandées des postes au même régime ({noms})")
        connues = [pr["existante"] if pr["existante"].nombre is not None else pr["somme_partielle"] for pr in prs]
        connues = [v for v in connues if v is not None and v.nombre is not None]
        partielle = None
        if ex.nombre is None and connues:
            partielle = somme(connues, "kW", id=f"sous-total-partiel-{ident}",
                              source="somme partielle des puissances connues (postes ou compresseurs lus)")
        res.append({"regime": prs[0]["regime"], "postes": [pr["id"] for pr in prs], "noms": noms, "existante": ex,
                    "demandee": de, "somme_partielle": partielle})
    return res


def _charges(postes: list[dict]) -> list[dict]:
    """Charges totales par fluide (somme des postes), tCO2e ; somme partielle si une charge manque."""
    groupes: dict[str, list[dict]] = {}
    for pr in postes:
        nom = ((pr["fluide"] or {}).get("valeur") or "")
        if nom:
            groupes.setdefault(fgas.nom_canonique(nom) or nom, []).append(pr)
    res = []
    for nom, prs in groupes.items():
        cle = re.sub(r"[^a-z0-9]+", "-", _sa(nom))
        charges = [pr["charge"] for pr in prs if pr["charge"] is not None]
        if not charges:
            continue
        total = somme(charges, "kg", id=f"charge-totale-{cle}", source=f"somme des charges des postes au {nom}")
        connues = [c for c in charges if c.nombre is not None]
        partielle = None
        if total.nombre is None and connues:
            partielle = somme(connues, "kg", id=f"charge-partielle-{cle}",
                              source=f"somme des {len(connues)} charge(s) connue(s) sur {len(charges)}")
        base = total if total.nombre is not None else partielle
        tco2 = fgas.tco2e(base, nom, id=f"tco2e-{'totale' if base is total else 'partielle'}-{cle}") if base else None
        statuts = [_statut_choix(pr["fluide"]) for pr in prs]
        pire = combiner(statuts)
        if tco2 is not None and RANG[pire] > RANG[SOURCE]:
            tco2 = _au_plus(tco2, pire, next(pr["fluide"].get("id", "") for pr in prs
                                             if _statut_choix(pr["fluide"]) == pire))
        res.append({"fluide": nom, "postes": [pr["id"] for pr in prs], "total": total, "somme_partielle": partielle,
                    "tco2e": tco2, "n_connues": len(connues), "n": len(charges)})
    return res


def _fluide_cible(projet: dict, postes: list[dict], date: Any) -> dict | None:
    c = projet.get("fluide_cible")
    if not c or not c.get("valeur"):
        return None
    type_c = projet.get("type_equipement_cible") or ""
    existantes = [pr["existante"] for pr in postes]
    total = somme(existantes, "kW", id="total-existant", source="somme des puissances existantes de tous les postes, "
                  "tous régimes confondus (capacité indicative pour fgas.py seulement)") if existantes else None
    capacite = total if total is not None and total.nombre is not None else None
    verdict = fgas.verdict_fluide(c["valeur"], type_c, None, date, capacite)
    actuel = (projet.get("fluide_actuel") or {}).get("valeur")
    comparaison = fgas.comparer_fluides(actuel, c["valeur"], type_c, None, None, date, capacite) if actuel else None
    fa = projet.get("fluide_actuel") or {}
    if comparaison and RANG[_statut_choix(fa)] > RANG[SOURCE]:
        comparaison = dict(comparaison)
        for cle in ("rapport_prp", "variation_prp"):
            comparaison[cle] = _au_plus(comparaison[cle], _statut_choix(fa), fa.get("id", ""))
        comparaison["statut_actuel"] = _statut_choix(fa)
    return {"choix": c, "type_equipement": type_c, "total_existant": total, "verdict": verdict,
            "comparaison": comparaison}


def _releves(e: dict, p: dict, marge: Valeur, ratio: Valeur | None, defauts: list[str], postes: list[dict]) -> dict:
    """Hypothèses, « à confirmer » et alertes, pour l'aide au bloc G."""
    hyp, conf, alertes = [], [], []
    for k in CLES_PARAMETRES:
        v = p.get(k)
        if v is None:
            continue
        txt = v.texte() if isinstance(v, Valeur) else v["valeur"]
        statut = v.statut if isinstance(v, Valeur) else v["statut"]
        if statut == HYPOTHESE:
            hyp.append(f"paramètre {k} = {txt}{' (défaut du script)' if k in defauts else ''} : "
                       f"{v.source if isinstance(v, Valeur) else v['source']}")
    hyp.append(f"marge = {marge.texte()}{' (défaut du script)' if 'marge_pct' in defauts else ''} : {marge.source}")
    if ratio is None:
        conf.append("ratio de puissance par m³ de Loïc : non fourni (question 4) ; contrôle par le ratio non fait")
    projet = e.get("projet") or {}
    for cle in ("fluide_actuel", "fluide_cible"):
        c = projet.get(cle)
        if c and _statut_choix(c) == HYPOTHESE:
            hyp.append(f"{cle} = {c.get('valeur')} : {c.get('source')}")
        elif c and _statut_choix(c) == A_CONFIRMER:
            conf.append(f"{cle} : {c.get('source')}")
    for pr in postes:
        n = pr["nom"]
        if pr["fluide"] and pr["fluide"] is not projet.get("fluide_actuel") and _statut_choix(pr["fluide"]) == HYPOTHESE:
            hyp.append(f"{n} · fluide {pr['fluide'].get('valeur')} : {pr['fluide'].get('source')}")
        d = pr["dessert"] or {}
        if d and _statut_choix(d) != SOURCE:
            (conf if _statut_choix(d) == A_CONFIRMER else hyp).append(f"{n} · dessert « {d.get('texte')} » : {d.get('source')}")
        for cle, v in (("température de chambre", pr["temperature_chambre"]), ("volume", pr["volume"]),
                       ("évaporation", pr["regime"]["t0"]), ("condensation", pr["regime"]["tc"]),
                       ("charge", pr["charge"])):
            if v is None:
                continue
            if v.nombre is None:
                conf.append(f"{n} · {cle} : {v.source}")
            elif v.statut == HYPOTHESE:
                hyp.append(f"{n} · {cle} = {v.texte()} : {v.source}")
        for c in pr["compresseurs"]:
            nom_c = f"{n} · {c['id']} ({c['modele'] or 'modèle à confirmer'})"
            if c["lecture"] == DOUTEUSE:
                hyp.append(f"{nom_c} : {c['volume_balaye'].source}")
            if c["retenue"].nombre is None:
                conf.append(f"{nom_c} : puissance à confirmer ({c['retenue'].source})")
        if pr["existante"].nombre is None:
            conf.append(f"{n} · puissance existante à confirmer ({pr['existante'].source})")
        for pl in pr["plaques"]:
            if pl["depassement"] is None:
                hyp.append(f"{n} · plaque d'ensemble {pl['id']} : {pl['portee']}")
        alertes += [f"{n} · {a}" for a in pr["alertes"]]
    return {"hypotheses": hyp, "a_confirmer": conf, "alertes": alertes}


def calculer_dossier(e: dict, points: list[dict]) -> dict:
    """Toutes les sorties de l'étape 2 à partir des entrées (déjà vérifiées)."""
    p, marge, ratio, defauts = _parametres_entrees(e)
    projet = e.get("projet") or {}
    date = projet.get("date_analyse") or None
    postes = [_calculer_poste(poste, projet, p, marge, ratio, points, date) for poste in e["postes"]]
    relecture = next((pr["verdict"]["relecture"] for pr in postes if pr["verdict"]), "")
    return {"format": FORMAT_RESULTATS, "dossier": e.get("dossier", ""), "date_analyse": date,
            "versions": {"CoolProp": fluides.VERSION}, "parametres": p, "marge": marge, "ratio_kw_m3": ratio,
            "parametres_par_defaut": defauts, "projet": projet, "postes": postes, "sous_totaux": _sous_totaux(postes),
            "charges": _charges(postes), "fluide_cible": _fluide_cible(projet, postes, date),
            "relecture_fgas": relecture, "releves": _releves(e, p, marge, ratio, defauts, postes)}


# =====================================================================================================
# Tableaux markdown
# =====================================================================================================
def _source_m1(m1: dict) -> str:
    if m1["q0"].nombre is None:
        return f"M1 : {m1.get('raison') or m1['q0'].source}"
    lam, tau = m1.get("lambda"), m1.get("tau")
    if lam is None or tau is None:
        return "M1 : cylindrée"
    return f"M1 : λ {lam.texte(3, marque=False)} (τ {tau.texte(2, marque=False)})"


def _source_m2(m2: dict, fluide: str) -> str:
    if m2["q0"].nombre is None or not m2.get("points"):
        return f"M2 : {m2.get('raison') or m2['q0'].source}"
    pt = m2["points"][0]
    detail = (f"{m2['cas']} au {m2['fluide_donnees']}, converti au {fluide} par CoolProp, λ table A"
              if m2.get("conversion") else m2["cas"])
    return f"M2 : {pt['document']} p. {pt['page']} ({detail})"


def _tableau_b(res: dict) -> list[str]:
    seuil = res["parametres"]["seuil_ecart"]
    lignes = ["## B. Puissance existante par compresseur", "",
              _ligne(["Poste", "Compresseur", "Régime T0 / Tc", "M1 cylindrée", "M2 point catalogue",
                      "Écart (M1 − M2) ÷ M2", "Retenue", "Source", "Statut"]),
              _ligne(["---"] * 9)]
    for pr in res["postes"]:
        for c in pr["compresseurs"]:
            nom = " ".join(x for x in (c["marque"], c["modele"]) if x) or "modèle à confirmer"
            if c["lecture"] == DOUTEUSE:
                nom += " (lecture douteuse)"
            elif c["lecture"] == ILLISIBLE:
                nom += " (plaque illisible)"
            ecart = _signe(c["ecart_sur_m2"])
            if c["ecart"]["depassement"]:
                ecart = f"⚠ {ecart} (au-delà de {seuil.texte(marque=False)})"
            retenue = c["retenue"].texte() + (f" · {c['regle']}" if c["regle"] in ("M1", "M2") else "")
            vb = c.get("volume_balaye")
            sources = [f"volume balayé {vb.texte(marque=False)} : {vb.source}" if vb is not None and vb.nombre is not None
                       else f"volume balayé à confirmer : {vb.source if vb is not None else 'non donné'}",
                       _source_m1(c["m1"]), _source_m2(c["m2"], c["fluide"])]
            statut = [c["retenue"].statut] + (["lecture douteuse"] if c["lecture"] == DOUTEUSE else [])
            lignes.append(_ligne([_esc(f"{pr['nom']} · {c['id']}"), _esc(nom), _esc(_regime_txt(pr["regime"])),
                                  _esc(c["m1"]["q0"].texte()), _esc(c["m2"]["q0"].texte()), _esc(ecart),
                                  _esc(retenue), _cellule(sources), _cellule(statut)]))
    lignes += ["", "> M1 = cylindrée (volume balayé × λ × ρ1 × Δh, propriétés CoolProp) ; M2 = point catalogue du "
               "fabricant ramené au fluide et au régime ; retenue = M2 si disponible, sinon M1 ; « (hyp.) » = dépend "
               f"d'une hypothèse écrite en bloc G ; seuil d'écart M1 / M2 : {seuil.texte()} (sur la moyenne des deux).", ""]
    return lignes


def _controles_poste(pr: dict, res: dict) -> list[str]:
    seuil = res["parametres"]["seuil_ecart"]
    items = []
    hors = [c for c in pr["compresseurs"] if c["ecart"]["depassement"]]
    if hors:
        items.append("⚠ écart M1 / M2 au-delà du seuil : " + ", ".join(f"{c['id']} ({_signe(c['ecart_sur_m2'])})"
                                                                       for c in hors))
    elif any(c["ecart"]["depassement"] is False for c in pr["compresseurs"]):
        items.append(f"écarts M1 / M2 sous le seuil de {seuil.texte()}")
    for pl in pr["plaques"]:
        t = f"{pl['texte']} : {pl['puissance'].texte()}"
        if pl["libelle"] != "puissance existante du poste":
            t += f" ; {pl['libelle']} : {pl['reference'].texte()}"
        t += f" ; écart du calcul sur la plaque : {_signe(pl['ecart'])}"
        if pl.get("sans_conversion") is not None:
            commun = (f" ; le catalogue de {', '.join(pl['tableau_commun'])} publie un tableau commun "
                      f"{pl['recalcul'][0]['fluide_donnees']}/{pl['fluide']}" if pl["tableau_commun"] else "")
            t += (f" ; sans conversion (points {pl['recalcul'][0]['fluide_donnees']} tels quels{commun}) : "
                  f"{pl['sans_conversion'].texte()}, écart {_signe(pl['ecart_sans_conversion'])}")
        t += f" ({pl['portee']})"
        items.append(("⚠ " if pl["depassement"] else "") + t)
    for es in pr["estimations"]:
        items.append(f"{es['texte']} : {es['puissance'].texte()} ; écart du calcul sur l'estimation : "
                     f"{_signe(es['ecart'])}")
    if pr["ratio"]:
        r = pr["ratio"]
        items.append(f"ratio de Loïc {r['ratio'].texte()} × volume : {r['puissance'].texte()} ; écart : {_signe(r['ecart'])}")
    else:
        items.append("ratio de Loïc : non fourni (question 4)")
    return items


def _tableau_c(res: dict) -> list[str]:
    lignes = ["## C. Besoins par poste", "",
              _ligne(["Poste", "Dessert", "T chambre", "Volume", "Puissance existante", "Contrôles",
                      "Puissance demandée", "Remarques"]),
              _ligne(["---"] * 8)]
    for pr in res["postes"]:
        d = pr["dessert"] or {}
        dessert = d.get("texte", "à confirmer") + ("" if _statut_choix(d) == SOURCE else
                                                    (" (hyp.)" if _statut_choix(d) == HYPOTHESE else " (à confirmer)"))
        tc = pr["temperature_chambre"]
        vol = pr["volume"]
        demandee = [pr["demandee"].texte(), f"marge {pr['marge'].texte()}"]
        lignes.append(_ligne([_esc(pr["nom"]), _esc(dessert), _esc(tc.texte() if tc else "à confirmer"),
                              _esc(vol.texte() if vol else "à confirmer"), _esc(pr["existante"].texte()),
                              _cellule(_controles_poste(pr, res)), _cellule(demandee),
                              _cellule(pr["remarques"])]))
    for st in res["sous_totaux"]:
        rem = [f"somme des puissances connues : {st['somme_partielle'].texte()}"] if st["somme_partielle"] else []
        lignes.append(_ligne([_esc(f"Sous-total {_regime_txt(st['regime'])}"), _esc(st["noms"]), "—", "—",
                              _esc(st["existante"].texte()), "—", _esc(st["demandee"].texte()), _cellule(rem)]))
    lignes += ["", "> Puissance existante = somme des puissances retenues du tableau B (une seule « à confirmer » "
               "la rend « à confirmer » : la somme des compresseurs lus est alors donnée à part en remarque). "
               "Puissance demandée = existante × (1 + marge ÷ 100).", ""]
    return lignes


def _sans_prefixe(texte: str, prefixe: str) -> str:
    return texte[len(prefixe):] if texte.startswith(prefixe) else texte


def _cellules_verdict(v: dict) -> list[str]:
    et = _sans_prefixe(_sans_prefixe(v["etancheite"]["texte"], "Contrôle d'étanchéité F-gas : "),
                       "Contrôle d'étanchéité : ")
    if v["famille"] == fgas.NON_FLUORE:
        entretien = "hors règlement F-gas (fluide non fluoré) ; sécurité EN 378 non couverte par la table"
    else:
        entretien = _sans_prefixe(v["interdiction_entretien"]["texte"], "Entretien et recharge : ")
    neuf = _sans_prefixe(v["interdiction_mise_sur_le_marche"]["texte"], "Équipement neuf de ce type avec ce fluide : ")
    marques = [" (hyp.)" if v.get(cle, {}).get("fiabilite") == HYPOTHESE else ""
               for cle in ("etancheite", "interdiction_entretien", "interdiction_mise_sur_le_marche")]
    return [et + marques[0], entretien + marques[1], neuf + marques[2]]


def _fluide_txt(v: dict) -> str:
    """« R449A (mélange HFC/HFO, classe A1) » : libellé de famille de fgas.py (même skill)."""
    famille = fgas._libelle_famille(v["fluide"], v["famille"]) if v["fluide_connu"] else v["famille"]
    return f"{v['fluide']} ({famille}, classe {v['classe_securite']})"


def _tableau_d(res: dict) -> list[str]:
    lignes = ["## D. Fluide et conformité", "",
              _ligne(["Poste", "Fluide", "PRP", "Charge", "tCO2e", "Contrôle d'étanchéité", "Entretien et recharge",
                      "Équipement neuf de ce type", "Statut"]),
              _ligne(["---"] * 9)]
    for pr in res["postes"]:
        v = pr["verdict"]
        fl = pr["fluide"] or {}
        statut = [f"fluide : {_statut_choix(fl)}"] + (["table F-gas non relue"] if v and fgas.MENTION_NON_RELUE in
                                                       v["relecture"] else [])
        poste = [pr["nom"], f"type : {pr['type_equipement'] or 'à confirmer'}"]
        if v is None:
            lignes.append(_ligne([_cellule(poste), "à confirmer", "à confirmer", _esc(pr["charge"].texte()),
                                  "à confirmer", "à confirmer", "à confirmer", "à confirmer", _cellule(statut)]))
            continue
        lignes.append(_ligne([_cellule(poste), _esc(_fluide_txt(v)), _esc(fgas.texte_prp(v["prp"])),
                              _esc(pr["charge"].texte() if pr["charge"] else "à confirmer"), _esc(pr["tco2e"].texte()),
                              *[_esc(x) for x in _cellules_verdict(v)], _cellule(statut)]))
    for ch in res["charges"]:
        if ch["n"] < 2:
            continue
        charge = [ch["total"].texte()]
        tco2 = [ch["tco2e"].texte() if ch["tco2e"] and ch["total"].nombre is not None else "à confirmer"]
        if ch["somme_partielle"] is not None:
            charge.append(f"charges connues ({ch['n_connues']} sur {ch['n']}) : {ch['somme_partielle'].texte()}")
            tco2.append(f"charges connues : {ch['tco2e'].texte()}")
        lignes.append(_ligne([_esc(f"Total des charges au {ch['fluide']}"), _esc(ch["fluide"]), "—", _cellule(charge),
                              _cellule(tco2), _esc("par circuit (ligne de chaque poste)"), "—", "—",
                              _esc("indicatif")]))
    cible = res["fluide_cible"]
    if cible:
        v = cible["verdict"]
        c = cible["choix"]
        lignes.append(_ligne([_cellule(["Projet : fluide cible", f"type : {cible['type_equipement']}"]),
                              _esc(_fluide_txt(v)), _esc(fgas.texte_prp(v["prp"])), _esc("à confirmer (fournisseur)"),
                              "à confirmer", *[_esc(x) for x in _cellules_verdict(v)],
                              _cellule([f"fluide cible : {_statut_choix(c)}"])]))
    lignes.append("")
    notes = []
    if cible and cible["comparaison"]:
        statut_actuel = cible["comparaison"].get("statut_actuel")
        notes.append(f"> {_esc(cible['comparaison']['texte'].splitlines()[0])}"
                     + (f" (fluide actuel : {statut_actuel})" if statut_actuel else ""))
    relecture = res["relecture_fgas"] or ""
    if fgas.MENTION_NON_RELUE in relecture:
        detail = relecture.replace(fgas.MENTION_NON_RELUE, "", 1).strip()
        notes.append(f"> **Table F-gas non relue**{' ' + detail if detail else ''} : à vérifier sur EUR-Lex avant de "
                     "s'en servir devant un client.")
    notes.append(f"> Règles évaluées au {res['date_analyse'] or 'jour du calcul'} ; type d'équipement lu par les "
                 "synonymes de fgas.py ; capacité passée au règlement = puissance existante du poste (indicative).")
    for note in notes:                                   # une note par paragraphe (lisible dans la vue HTML)
        lignes += [note, ""]
    return lignes


def _tableau_g_estimations(res: dict) -> list[str]:
    comps = [(pr, c) for pr in res["postes"] for c in pr["compresseurs"] if c.get("estimation")]
    if not comps:
        return []
    lignes = ["## G-estimations. Écarts aux estimations antérieures, par compresseur", "",
              _ligne(["Poste · compresseur", "Estimation antérieure", "M1 cylindrée", "M1 sur l'estimation",
                      "Retenue", "Retenue sur M1", "Retenue sur l'estimation"]),
              _ligne(["---"] * 7)]
    for pr, c in comps:
        e = c["estimation"]
        lignes.append(_ligne([_esc(f"{pr['nom']} · {c['id']} ({c['modele'] or 'modèle à confirmer'})"),
                              _esc(e["puissance"].texte()), _esc(c["m1"]["q0"].texte()), _esc(_signe(e["m1_sur_estimation"])),
                              _esc(c["retenue"].texte() + (f" · {c['regle']}" if c["regle"] in ("M1", "M2") else "")),
                              _esc(_signe(e["retenue_sur_m1"])), _esc(_signe(e["retenue_sur_estimation"]))]))
    lignes += ["", "> M1 sur l'estimation : effet du rendement volumétrique et des conditions de calcul (mêmes volumes "
               "balayés). Retenue sur M1 : effet du choix de M2 (point catalogue) quand il existe.", ""]
    return lignes


def _tableau_g_variantes(res: dict) -> list[str]:
    lignes_v = [(pr, va) for pr in res["postes"] for va in pr.get("variantes_fluide") or []]
    if not lignes_v:
        return []
    lignes = ["## G-variantes. Variantes de fluide (fluide actuel supposé)", "",
              _ligne(["Poste", "Fluide retenu", "Variante", "Indiquée par", "Charge", "tCO2e", "Contrôle d'étanchéité",
                      "Entretien et recharge"]),
              _ligne(["---"] * 8)]
    phrases = []
    for pr, va in lignes_v:
        v = va["verdict"]
        et, entretien, _ = _cellules_verdict(v)
        fl = pr["fluide"] or {}
        charge = pr["charge"].texte() if pr["charge"] is not None else "à confirmer"
        lignes.append(_ligne([_esc(pr["nom"]), _esc(f"{fl.get('valeur')} ({_statut_choix(fl)})"), _esc(va["fluide"]),
                              _cellule(va["origines"]), _esc(charge), _esc(va["tco2e"].texte()), _esc(et),
                              _esc(entretien)]))
        frequence = v["etancheite"].get("frequence") or "à confirmer"
        detection = " ; système de détection des fuites obligatoire" if v["etancheite"].get(
            "detection_fuites_obligatoire") else ""
        phrases.append(f"> Si le fluide de « {pr['nom']} » était resté au {va['fluide']} (selon : {', '.join(va['origines'])}) : "
                       f"{va['tco2e'].texte()}, contrôle d'étanchéité {frequence}{detection}.")
    lignes.append("")
    for ph in phrases:
        lignes += [_esc(ph), ""]
    return lignes


def _aide_g(res: dict) -> list[str]:
    r = res["releves"]
    lignes = ["## Aide au bloc G (relevé automatique : à reformuler, pas à recopier tel quel)", ""]
    for titre, cle in (("Hypothèses utilisées", "hypotheses"), ("À confirmer", "a_confirmer"), ("Alertes", "alertes")):
        lignes += [f"### {titre}", ""]                   # ligne vide avant chaque liste (vue HTML)
        lignes += [f"- {x}" for x in r[cle]] or ["- aucune"]
        lignes.append("")
    return lignes


def tableaux_markdown(res: dict) -> str:
    lignes = ["<!-- Généré par calculs.py depuis 2-entrees.json : ne pas modifier à la main. Recopier les tableaux "
              "B, C, D (et G-estimations, G-variantes s'ils existent) tels quels dans 2-dimensionnement.md. -->", "",
              f"# Tableaux de l'étape 2 · {res['dossier']}", ""]
    lignes += (_tableau_b(res) + _tableau_c(res) + _tableau_d(res) + _tableau_g_estimations(res)
               + _tableau_g_variantes(res) + _aide_g(res))
    return "\n".join(lignes).rstrip("\n") + "\n"


# =====================================================================================================
# Ligne de commande
# =====================================================================================================
def _resume(res: dict) -> list[str]:
    sortie = []
    for pr in res["postes"]:
        t = f"  {pr['nom']} : existante {pr['existante'].texte()}, demandée {pr['demandee'].texte()}"
        if pr["somme_partielle"] is not None:
            t += f" (compresseurs lus : {pr['somme_partielle'].texte()})"
        sortie.append(t)
    r = res["releves"]
    sortie.append(f"  {len(r['hypotheses'])} hypothèse(s), {len(r['a_confirmer'])} « à confirmer », "
                  f"{len(r['alertes'])} alerte(s)")
    return sortie


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(prog="calculs.py", description="Étape 2 : 2-entrees.json → 2-resultats.json et "
                                 "2-tableaux.md (tableaux B, C, D).")
    ap.add_argument("dossier", help="dossier de l'installation, ex. dimensionnement/dossiers/<slug>")
    ap.add_argument("--verifier", action="store_true", help="relire seulement les entrées et signaler les incohérences")
    ap.add_argument("--points", default=str(CHEMIN_POINTS_DEFAUT), help="CSV des points catalogue")
    a = ap.parse_args(argv)
    dossier = Path(a.dossier)
    try:
        entrees, erreurs = charger_entrees(dossier)
    except EntreesIllisibles as exc:
        print(f"refusé : {exc}")
        return 2
    attentions: list[str] = []
    if entrees is not None:
        erreurs, attentions = verifier(entrees)
    for m in erreurs + attentions:
        print(m)
    if erreurs:
        print(f"{len(erreurs)} erreur(s) dans {ENTREES} : rien n'est écrit. Corriger les entrées, puis relancer.")
        return 1
    if a.verifier:
        print(f"{ENTREES} cohérent ({len(attentions)} avertissement(s)).")
        return 0
    try:
        points = charger_points(a.points)
        res = calculer_dossier(entrees, points)
    except (ValueError, TypeError, OSError) as exc:
        print(f"refusé : {exc}")
        return 1
    (dossier / RESULTATS).write_text(en_json(res) + "\n", encoding="utf-8", newline="\n")
    (dossier / TABLEAUX).write_text(tableaux_markdown(res), encoding="utf-8", newline="\n")
    print(f"Écrits : {dossier / RESULTATS}, {dossier / TABLEAUX}")
    print("\n".join(_resume(res)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
