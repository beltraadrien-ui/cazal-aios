"""Puissance frigorifique d'un compresseur existant : M1 (cylindrée) et M2 (point catalogue corrigé).

Méthode : dimensionnement/savoir/methodes/puissance-existante.md (§ 3 M1, § 4 M2, § 5 valeur retenue).
Propriétés des fluides : fluides.py (CoolProp). Chaque résultat est une Valeur avec sa source, sa formule et
son statut ; hors domaine ou donnée absente → « à confirmer » avec la raison, jamais un faux nombre.

Usage (bibliothèque) :
    from compresseurs import charger_points, parametres_par_defaut, puissance_compresseur
    from valeur import Valeur
    points = charger_points()        # dimensionnement/savoir/materiel/points-catalogue/bitzer-r449a.csv
    r = puissance_compresseur({"id": "c1", "modele": "4HE-18Y-40P", "fluide": "R449A",
                               "t0": Valeur(-30, "°C", "regles-loic.md R1", "sourcé", id="t0-negatif"),
                               "tc": Valeur(40, "°C", "regles-loic.md R1", "sourcé", id="tc"),
                               "volume_balaye": Valeur(73.7, "m³/h", "plaque, photo p05-2", "sourcé", id="c1-vb")},
                              points, parametres_par_defaut())
    r["m1"]["q0"].texte(), r["m2"]["q0"].texte(), r["ecart"]["ecart"].texte(), r["retenue"].texte()

Usage (ligne de commande, essai) :
    python compresseurs.py --modele 4HE-18Y-40P --fluide R449A --t0 -30 --tc 40 --volume 73.6
    options : --surchauffe 10 (au lieu du gaz aspiré à 20 °C) · --gaz-aspire 20 · --sous-refroidissement 0
              --convention rosee|moyenne · --lambda table_a|efpme · --points <csv> · --json
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
import unicodedata
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fluides  # noqa: E402
from controles import comparer  # noqa: E402
from unites import S_PAR_H  # noqa: E402  (1 h = 3 600 s, définition)
from valeur import (HYPOTHESE, SOURCE, Valeur, a_confirmer, calculer, combiner, en_json, nombre_fr,  # noqa: E402
                    normaliser_statut)

# ---------- constantes sourcées ----------
# Points catalogue par défaut (vague 1 · C du Lot 2, lus le 2026-10-06) : <dépôt>/dimensionnement/savoir/…
CHEMIN_POINTS_DEFAUT = (Path(__file__).resolve().parents[4]
                        / "dimensionnement" / "savoir" / "materiel" / "points-catalogue" / "bitzer-r449a.csv")
# Seule fréquence acceptée : les volumes balayés et les points Bitzer sont donnés à 50 Hz (KP-104-2 p. 11) ;
# à 60 Hz le débit est plus haut d'environ 21 % (1 750 / 1 450 min⁻¹, materiel/bitzer.md § 6) : refusé.
FREQUENCE_ACCEPTEE_HZ = 50.0
# Pourcentage : 1 = 100 % (définition).
POURCENT = 100.0

# Table A (défaut) : λ = 0,9625 − 0,0288 × τ, ajustée le 2026-10-06 sur 226 points Bitzer, domaine τ de 2 à 15.
SOURCE_TABLE_A = ("table A de λ : λ = 0,9625 − 0,0288 × τ, ajustement du 2026-10-06 sur 226 points Bitzer "
                  "(R404A, R407A, R407F ; EN 12900, gaz aspiré 20 °C ; écart-type 0,022), domaine τ de 2 à 15 "
                  "(methodes/puissance-existante.md § 3) ; proposée par défaut, à valider par Adrien")
LAMBDA_A_ORDONNEE = Valeur(0.9625, "", SOURCE_TABLE_A, HYPOTHESE, id="lambda-a-ordonnee")
LAMBDA_A_PENTE = Valeur(0.0288, "", SOURCE_TABLE_A, HYPOTHESE, id="lambda-a-pente")
TAU_A_MIN, TAU_A_MAX = 2.0, 15.0           # étendue des 226 points (puissance-existante.md § 3)
# Variante des livres de Loïc : λ = 1 − 0,05 × τ (EFPME, Cours de bases (froid), p. 60) ; domaine = étendue de
# la table B de puissance-existante.md § 3 (τ de 2 à 12).
SOURCE_EFPME = ("formule EFPME : λ = 1 − 0,05 × τ (EFPME, Cours de bases (froid), p. 60 ; table B de "
                "methodes/puissance-existante.md § 3, τ de 2 à 12) ; pessimiste pour les semi-hermétiques actuels")
LAMBDA_B_ORDONNEE = Valeur(1.0, "", SOURCE_EFPME, HYPOTHESE, id="lambda-efpme-ordonnee")
LAMBDA_B_PENTE = Valeur(0.05, "", SOURCE_EFPME, HYPOTHESE, id="lambda-efpme-pente")
TAU_B_MIN, TAU_B_MAX = 2.0, 12.0
METHODES_LAMBDA = {
    "table_a": (LAMBDA_A_ORDONNEE, LAMBDA_A_PENTE, TAU_A_MIN, TAU_A_MAX, "table A"),
    "efpme": (LAMBDA_B_ORDONNEE, LAMBDA_B_PENTE, TAU_B_MIN, TAU_B_MAX, "formule EFPME"),
}

# Conditions de référence des points Bitzer (EN 12900) : gaz aspiré 20 °C, sans sous-refroidissement
# (KP-104-2 p. 11 et 12 ; colonnes gaz_aspire_c et sous_refroidissement_k de points-catalogue/bitzer-r449a.csv).
GAZ_ASPIRE_CATALOGUE_C = 20.0
SOUS_REFROIDISSEMENT_CATALOGUE_K = 0.0
# Seuil d'écart M1 / M2 : 15 %, précision attendue de M1 (± 10 à 15 %, puissance-existante.md § 5).
SEUIL_ECART_PCT = 15.0
# Distance maximale au point catalogue pour la correction de régime (puissance-existante.md § 4, décision du
# 2026-10-06 : avec le rapport des λ, biais ≈ 1 % à 5 K sur T0 et ≈ 0,4 % à 10 K sur Tc).
SEUIL_T0_K = 5.0
SEUIL_TC_K = 10.0
# Fluide de base : seul fluide publié pour les six modèles Bitzer (points-catalogue/bitzer-r449a.md).
FLUIDE_BASE = "R404A"
# Fluides vers lesquels un point catalogue d'un autre fluide n'est jamais converti : passage au CO2 = compresseurs
# CO2 dédiés (methodes/transitions.md § 1 et tableau final) ; propane = version spécifique R290 du compresseur
# (transitions.md, Bitzer Refrigerant Report 21 p. 31). Noms CoolProp.
FLUIDES_SANS_CONVERSION = {"CO2": "compresseurs CO2 dédiés (methodes/transitions.md § 1)",
                           "R290": "version spécifique R290 du compresseur (methodes/transitions.md, propane)"}
# Correction de conditions d'EnergyPlus (rapport ρ1 × Δh) : Engineering Reference, « Refrigeration Equipment ».
SOURCE_ENERGYPLUS = ("correction EnergyPlus (Engineering Reference, Refrigeration Equipment : "
                     "https://bigladdersoftware.com/epx/docs/9-6/engineering-reference/refrigeration-equipment.html)")

COLONNES_OBLIGATOIRES = ("marque", "modele", "fluide", "frequence_hz", "t_evaporation_c", "t_condensation_c",
                         "condition_reference", "surchauffe_k", "gaz_aspire_c", "sous_refroidissement_k",
                         "puissance_frigo_kw", "source_url", "document", "page", "date_lecture")
COLONNES_NUMERIQUES = ("frequence_hz", "t_evaporation_c", "t_condensation_c", "surchauffe_k", "gaz_aspire_c",
                       "sous_refroidissement_k", "puissance_frigo_kw", "puissance_absorbee_kw", "volume_balaye_m3h",
                       "t0_min_c", "t0_max_c", "tc_min_c", "tc_max_c")
CLES_PARAMETRES = ("convention", "gaz_aspire", "surchauffe", "sous_refroidissement", "seuil_ecart", "seuil_t0",
                   "seuil_tc", "lambda_methode", "fluide_base")
CLES_ENTREE = ("id", "modele", "fluide", "t0", "tc", "volume_balaye", "frequence")


# ---------- paramètres ----------
def choix(valeur: str, source: str, statut: str, id: str) -> dict:
    """Un paramètre textuel sourcé (convention, méthode de λ, fluide de base) : dict JSON, statut propagé."""
    if not isinstance(source, str) or not source.strip():
        raise ValueError(f"paramètre « {id} » : source vide")
    return {"valeur": valeur, "source": source, "statut": normaliser_statut(statut), "id": id}


def parametres_par_defaut() -> dict:
    """Paramètres de calcul par défaut, chacun avec sa source ; toutes des hypothèses tant que Loïc n'a pas répondu."""
    return {
        "convention": choix("rosee", "hypothèse en attente de la réponse de Loïc (question 1 du 2026-10-06) : T0 et Tc "
                            "au point de rosée, convention des données Bitzer et d'EN 12900 (KP-104-2 p. 10, note 3 ; "
                            "methodes/puissance-existante.md § 2)", HYPOTHESE, "param-convention"),
        "gaz_aspire": Valeur(GAZ_ASPIRE_CATALOGUE_C, "°C", "hypothèse en attente de la réponse de Loïc (question 1) : "
                             "même condition que les points catalogue Bitzer, gaz aspiré 20 °C (EN 12900 ; KP-104-2 "
                             "p. 12)", HYPOTHESE, id="param-gaz-aspire"),
        "surchauffe": None,
        "sous_refroidissement": Valeur(SOUS_REFROIDISSEMENT_CATALOGUE_K, "K", "hypothèse : liquide saturé, comme les "
                                       "données Bitzer « sans sous-refroidissement » (KP-104-2 p. 11 ; "
                                       "methodes/puissance-existante.md § 2)", HYPOTHESE, id="param-sous-refroidissement"),
        "seuil_ecart": Valeur(SEUIL_ECART_PCT, "%", "hypothèse en attente de la réponse de Loïc (question 3) : "
                              "précision attendue de M1, ± 10 à 15 % (methodes/puissance-existante.md § 5)", HYPOTHESE,
                              id="param-seuil-ecart"),
        "seuil_t0": Valeur(SEUIL_T0_K, "K", "hypothèse à valider avec Loïc : distance maximale en évaporation entre le "
                           "régime demandé et le point catalogue corrigé (methodes/puissance-existante.md § 4)",
                           HYPOTHESE, id="param-seuil-t0"),
        "seuil_tc": Valeur(SEUIL_TC_K, "K", "hypothèse à valider avec Loïc : distance maximale en condensation entre le "
                           "régime demandé et le point catalogue corrigé (methodes/puissance-existante.md § 4)",
                           HYPOTHESE, id="param-seuil-tc"),
        "lambda_methode": choix("table_a", SOURCE_TABLE_A + " ; variante possible : « efpme » (" + SOURCE_EFPME + ")",
                                HYPOTHESE, "param-lambda"),
        "fluide_base": choix(FLUIDE_BASE, "seul fluide publié pour les six modèles Bitzer, mêmes conditions EN 12900 "
                             "(points-catalogue/bitzer-r449a.md)", SOURCE, "param-fluide-base"),
    }


def _parametres(parametres: dict | None) -> dict:
    """Défauts complétés par les paramètres donnés, puis vérifiés. Donner « surchauffe » seule annule le gaz aspiré."""
    p = parametres_par_defaut()
    if parametres:
        # « aspiration » est dérivée (gaz aspiré ou surchauffe) : recalculée ici, jamais lue
        parametres = {k: v for k, v in parametres.items() if k != "aspiration"}
        inconnues = [k for k in parametres if k not in CLES_PARAMETRES]
        if inconnues:
            raise ValueError(f"paramètre(s) inconnu(s) : {', '.join(inconnues)} ; attendus : {', '.join(CLES_PARAMETRES)}")
        p.update(parametres)
        if parametres.get("surchauffe") is not None and "gaz_aspire" not in parametres:
            p["gaz_aspire"] = None
    if (p["gaz_aspire"] is None) == (p["surchauffe"] is None):
        raise ValueError("paramètres : donner soit « gaz_aspire » (°C), soit « surchauffe » (K), une seule des deux")
    for cle, unite in (("gaz_aspire", "°C"), ("surchauffe", "K"), ("sous_refroidissement", "K"), ("seuil_ecart", "%"),
                       ("seuil_t0", "K"), ("seuil_tc", "K")):
        if p[cle] is not None:
            _exiger(p[cle], (unite,), f"le paramètre « {cle} »")
    for cle in ("seuil_t0", "seuil_tc"):
        if p[cle].nombre is not None and not p[cle].nombre > 0:
            raise ValueError(f"paramètre « {cle} » : seuil strictement positif attendu (reçu {p[cle].texte()})")
    for cle in ("convention", "lambda_methode", "fluide_base"):
        c = p[cle]
        if not isinstance(c, dict) or set(c) != {"valeur", "source", "statut", "id"}:
            raise ValueError(f"paramètre « {cle} » : attendu choix(valeur, source, statut, id), reçu {c!r}")
    p["convention"] = {**p["convention"], "valeur": fluides.convention_normalisee(p["convention"]["valeur"])}
    if p["lambda_methode"]["valeur"] not in METHODES_LAMBDA:
        raise ValueError(f"méthode de λ inconnue : « {p['lambda_methode']['valeur']} » ; possibles : "
                         + ", ".join(METHODES_LAMBDA))
    fluides.nom_coolprop(p["fluide_base"]["valeur"])
    p["aspiration"] = p["gaz_aspire"] if p["gaz_aspire"] is not None else p["surchauffe"]
    return p


# ---------- outils ----------
def _exiger(v, unites: tuple[str, ...], quoi: str) -> None:
    if not isinstance(v, Valeur):
        raise TypeError(f"{quoi} : Valeur attendue (nombre, unité, source, statut), reçu {v!r}")
    if v.unite not in unites:
        raise ValueError(f"{quoi} « {v.reference()} » doit être en {' ou '.join(unites)} (reçu : « {v.unite} »)")


def _degrader(v: Valeur, choix_liste: list[dict]) -> Valeur:
    """Applique le statut des choix (convention…) : un résultat n'est jamais plus sûr que ses hypothèses."""
    choix_liste = [c for c in choix_liste if c]
    if not choix_liste:
        return v
    statut = combiner([v.statut] + [c["statut"] for c in choix_liste])
    entrees = v.entrees + tuple(c["id"] for c in choix_liste if c["id"] not in v.entrees)
    return replace(v, statut=statut, entrees=entrees)


def _cause(valeurs) -> str:
    """La première raison d'un « à confirmer » (la cause, pas la propagation « bloqué par »)."""
    valeurs = [v for v in valeurs if isinstance(v, Valeur) and v.nombre is None]
    for v in valeurs:
        if "bloqué par" not in v.source:
            _, sep, motif = v.source.partition("calcul impossible : ")
            return f"{v.reference()} : {motif if sep else v.source}"
    return valeurs[0].source if valeurs else ""


def _fr(x: float) -> str:
    return nombre_fr(x, 1)


def _sans_accents(texte: str) -> str:
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()


def _meme_modele(a: str, b: str) -> bool:
    return (a or "").strip().upper().replace(" ", "") == (b or "").strip().upper().replace(" ", "")


def _nom_cp_ou_rien(fluide: str) -> str | None:
    try:
        return fluides.nom_coolprop(fluide)
    except ValueError:
        return None


# ---------- états thermodynamiques en Valeur ----------
def _etat(fluide: str, t0: Valeur, tc: Valeur, aspiration: Valeur, sous_ref: Valeur, convention: str,
          choix_convention: dict | None, pre: str) -> dict:
    """p0, pc (bar), τ, densité du gaz aspiré (kg/m³), h1, h4 et Δh (kJ/kg), en Valeur sourcées CoolProp."""
    nom = fluides.nom_coolprop(fluide)
    gaz = aspiration.nombre if aspiration.unite == "°C" else None
    sh = aspiration.nombre if aspiration.unite == "K" else None
    source = fluides.source_coolprop(nom, convention)
    cond = f"gaz aspiré {aspiration.reference()}" if aspiration.unite == "°C" else f"surchauffe {aspiration.reference()}"
    conv = fluides.LIBELLES[convention]

    def v(calcul, unite, formule, suffixe, entrees):
        return _degrader(calculer(calcul, unite, formule, entrees, source=source, id=f"{pre}-{suffixe}"),
                         [choix_convention])

    p0 = v(lambda: fluides.pression_pa(fluide, t0.nombre, convention) / fluides.PA_PAR_BAR, "bar",
           f"Psat {conv}({t0.reference()})", "p0", [t0])
    pc = v(lambda: fluides.pression_pa(fluide, tc.nombre, convention) / fluides.PA_PAR_BAR, "bar",
           f"Psat {conv}({tc.reference()})", "pc", [tc])
    tau = v(lambda: pc.nombre / p0.nombre, "", f"{pc.reference()} ÷ {p0.reference()}", "tau", [pc, p0])
    asp = lambda: fluides.aspiration(fluide, t0.nombre, gaz, sh, convention)  # noqa: E731
    rho = v(lambda: asp()["densite"], "kg/m³", f"ρ1({t0.reference()}, {cond})", "densite", [t0, aspiration])
    h1 = v(lambda: asp()["h_aspiration"] / fluides.J_PAR_KJ, "kJ/kg", f"h1({t0.reference()}, {cond})", "h1",
           [t0, aspiration])
    h4 = v(lambda: fluides.liquide(fluide, tc.nombre, sous_ref.nombre, convention)["h_liquide"] / fluides.J_PAR_KJ,
           "kJ/kg", f"h4({tc.reference()}, sous-refroidissement {sous_ref.reference()})", "h4", [tc, sous_ref])
    dh = v(lambda: fluides.cycle(fluide, t0.nombre, tc.nombre, gaz, sh, sous_ref.nombre, convention)["delta_h"]
           / fluides.J_PAR_KJ, "kJ/kg", f"{h1.reference()} − {h4.reference()}", "delta-h", [h1, h4])
    return {"p0": p0, "pc": pc, "tau": tau, "densite": rho, "h1": h1, "h4": h4, "delta_h": dh}


def _lambda(tau: Valeur, methode: str, id: str) -> Valeur:
    """Rendement volumétrique λ par la table A (défaut) ou la formule EFPME ; τ hors domaine → « à confirmer »."""
    a, b, tau_min, tau_max, libelle = METHODES_LAMBDA[methode]

    def calcul():
        if not tau_min <= tau.nombre <= tau_max:
            raise ValueError(f"τ = {nombre_fr(tau.nombre, 2)} hors du domaine de la {libelle} "
                             f"({nombre_fr(tau_min, 0)} à {nombre_fr(tau_max, 0)})")
        return a.nombre - b.nombre * tau.nombre
    return calculer(calcul, "", f"{a.reference()} − {b.reference()} × {tau.reference()}", [tau, a, b],
                    source=a.source, id=id)


# ---------- M1 : cylindrée ----------
def m1_cylindree(volume_balaye: Valeur, fluide: str, t0_c: Valeur, tc_c: Valeur, parametres: dict | None = None,
                 id: str = "") -> dict:
    """M1 : Q0 = V̇ × λ × ρ1 × Δh (kW), λ par la table A (ou EFPME), propriétés CoolProp au régime demandé.

    Rend {"methode", "q0", "lambda", "p0", "pc", "tau", "densite", "h1", "h4", "delta_h", "raison"} ;
    statut au mieux « hypothèse » (λ est une hypothèse) ; τ hors domaine → q0 « à confirmer », raison écrite.
    """
    p = _parametres(parametres)
    _exiger(volume_balaye, ("m³/h", "m3/h"), "le volume balayé")
    _exiger(t0_c, ("°C",), "T0")
    _exiger(tc_c, ("°C",), "Tc")
    pre = f"{id}-m1" if id else "m1"
    convention = p["convention"]["valeur"]
    etat = _etat(fluide, t0_c, tc_c, p["aspiration"], p["sous_refroidissement"], convention, p["convention"], pre)
    methode = p["lambda_methode"]["valeur"]
    lam = _degrader(_lambda(etat["tau"], methode, f"{pre}-lambda"), [p["lambda_methode"]])
    nom = fluides.nom_coolprop(fluide)
    source = ("M1 cylindrée : Q0 = V̇ × λ × ρ1 × (h1 − h4) (Préparation à la certification p. 46-47 ; EFPME, Cours "
              "de bases p. 57-60 ; methodes/puissance-existante.md § 3) ; λ par la "
              f"{METHODES_LAMBDA[methode][4]} ; propriétés {fluides.source_coolprop(nom, convention)} ; "
              "indicatif, à confirmer par le fournisseur")
    q0 = calculer(lambda: volume_balaye.nombre / S_PAR_H * lam.nombre * etat["densite"].nombre * etat["delta_h"].nombre,
                  "kW", f"{volume_balaye.reference()} ÷ {S_PAR_H:.0f} × {lam.reference()} × {etat['densite'].reference()} × "
                  f"{etat['delta_h'].reference()}", [volume_balaye, lam, etat["densite"], etat["delta_h"]],
                  source=source, id=pre)
    raison = "" if q0.nombre is not None else _cause([volume_balaye, t0_c, tc_c, *etat.values(), lam, q0])
    return {"methode": "M1 cylindrée", "q0": q0, "lambda": lam, **etat, "raison": raison}


# ---------- points catalogue ----------
def _nombre_csv(texte: str, colonne: str, ligne: int, fichier: str) -> float | None:
    texte = (texte or "").strip()
    if not texte:
        return None
    try:
        x = float(texte.replace(",", "."))
    except ValueError:
        raise ValueError(f"{fichier}, ligne {ligne}, colonne « {colonne} » : nombre illisible « {texte} »") from None
    if not math.isfinite(x):
        raise ValueError(f"{fichier}, ligne {ligne}, colonne « {colonne} » : nombre non fini « {texte} »")
    return x


def charger_points(chemin_csv: str | Path = CHEMIN_POINTS_DEFAUT, marque: str | None = None, modele: str | None = None,
                   fluide: str | None = None, frequence_hz: float | None = None) -> list[dict]:
    """Points catalogue du CSV (colonnes de points-catalogue/bitzer-r449a.md), nombres convertis (vide → None),
    plus « fichier » et « ligne » pour la traçabilité. Filtres facultatifs : marque, modèle, fluide, fréquence."""
    chemin = Path(chemin_csv)
    if not chemin.is_file():
        raise FileNotFoundError(f"fichier de points catalogue introuvable : {chemin}")
    with chemin.open(encoding="utf-8", newline="") as f:
        lecteur = csv.DictReader(f)
        manquantes = [c for c in COLONNES_OBLIGATOIRES if c not in (lecteur.fieldnames or [])]
        if manquantes:
            raise ValueError(f"{chemin.name} : colonne(s) manquante(s) {', '.join(manquantes)}")
        points = []
        for n, ligne in enumerate(lecteur, start=2):
            pt = {k: (v or "").strip() for k, v in ligne.items() if k is not None}
            for c in COLONNES_NUMERIQUES:
                if c in pt:
                    pt[c] = _nombre_csv(pt[c], c, n, chemin.name)
            pt["fichier"], pt["ligne"] = chemin.name, n
            points.append(pt)
    if marque is not None:
        points = [pt for pt in points if pt["marque"].casefold() == marque.strip().casefold()]
    if modele is not None:
        points = [pt for pt in points if _meme_modele(pt["modele"], modele)]
    if fluide is not None:
        cible = fluides.nom_coolprop(fluide)
        points = [pt for pt in points if _nom_cp_ou_rien(pt["fluide"]) == cible]
    if frequence_hz is not None:
        points = [pt for pt in points if pt["frequence_hz"] == float(frequence_hz)]
    return points


def _convention_point(pt: dict) -> str | None:
    texte = _sans_accents(pt.get("condition_reference") or "")
    if "rosee" in texte:
        return "rosee"
    if "moyenne" in texte:
        return "moyenne"
    return None


def _manque_conditions(pt: dict) -> str:
    """Ce qui manque à un point pour être utilisable (vide si complet)."""
    manque = [c for c in ("t_evaporation_c", "t_condensation_c", "puissance_frigo_kw", "sous_refroidissement_k")
              if pt.get(c) is None]
    if (pt.get("gaz_aspire_c") is None) == (pt.get("surchauffe_k") is None):
        manque.append("gaz aspiré ou surchauffe (un seul des deux)")
    if _convention_point(pt) is None:
        manque.append("convention de température (rosée ou moyenne) dans condition_reference")
    manque += [c for c in ("document", "source_url", "date_lecture") if not pt.get(c)]
    return ", ".join(manque)


def _source_point(pt: dict) -> str:
    return (f"{pt['document']}, p. {pt['page']}, {pt['source_url']}, lu le {pt['date_lecture']} ; {pt['marque']} "
            f"{pt['modele']} au {pt['fluide']}, t0 {_fr(pt['t_evaporation_c'])} °C, tc {_fr(pt['t_condensation_c'])} °C, "
            f"{nombre_fr(pt['frequence_hz'], 0)} Hz ; conditions : {pt['condition_reference']} "
            f"({pt.get('fichier', '?')}, ligne {pt.get('ligne', '?')})")


def _limites_application(donnees: list[dict]) -> tuple[float, float, float, float] | None:
    """Limites (t0_min, t0_max, tc_min, tc_max) des points ; les plus restrictives si elles diffèrent ; None si absentes."""
    cles = ("t0_min_c", "t0_max_c", "tc_min_c", "tc_max_c")
    if any(pt.get(c) is None for pt in donnees for c in cles):
        return None
    return (max(pt["t0_min_c"] for pt in donnees), min(pt["t0_max_c"] for pt in donnees),
            max(pt["tc_min_c"] for pt in donnees), min(pt["tc_max_c"] for pt in donnees))


def _poids(bas: float, haut: float, x: float) -> list[tuple[float, float]]:
    if bas == haut:
        return [(bas, 1.0)]
    f = (x - bas) / (haut - bas)
    return [(bas, 1.0 - f), (haut, f)]


def _interpolation(grille: dict, t0: float, tc: float) -> list[tuple[dict, float]] | None:
    """Coins et poids de l'interpolation linéaire sur t0 (dans chaque rangée de tc) puis sur tc ; None si impossible.
    Seules les rangées de tc qui ont au moins deux points servent (un point isolé ne fait pas une rangée)."""
    rangees: dict[float, dict[float, dict]] = {}
    for (a, b), pt in grille.items():
        rangees.setdefault(b, {})[a] = pt
    niveaux = [b for b, r in rangees.items() if len(r) >= 2]
    tc_bas = max((b for b in niveaux if b <= tc), default=None)
    tc_haut = min((b for b in niveaux if b >= tc), default=None)
    if tc_bas is None or tc_haut is None:
        return None
    coins = []
    for b, poids_tc in _poids(tc_bas, tc_haut, tc):
        rangee = rangees[b]
        a_bas = max((a for a in rangee if a <= t0), default=None)
        a_haut = min((a for a in rangee if a >= t0), default=None)
        if a_bas is None or a_haut is None:
            return None
        coins += [(rangee[a], poids_tc * poids_t0) for a, poids_t0 in _poids(a_bas, a_haut, t0)]
    return coins


def _resume_point(pt: dict) -> dict:
    cles = ("marque", "modele", "fluide", "frequence_hz", "t_evaporation_c", "t_condensation_c", "puissance_frigo_kw",
            "document", "page", "source_url", "date_lecture", "note", "fichier", "ligne")
    return {c: pt.get(c) for c in cles}


# ---------- M2 : point catalogue ----------
def m2_point_catalogue(modele: str, fluide_installation: str, t0_c: Valeur, tc_c: Valeur, points: list[dict],
                       parametres: dict | None = None, id: str = "") -> dict:
    """M2 : puissance publiée par le fabricant, ramenée au fluide et au régime de l'installation.

    Ordre : (a) point de la grille au fluide de l'installation ; (b) sinon au fluide de base (R404A) puis
    conversion Q0 × (λ ρ1 Δh)cible ÷ (λ ρ1 Δh)base, « hypothèse » ; (c) régime hors grille : interpolation
    linéaire sur t0 puis tc dans les limites d'application ; (d) sinon correction de régime depuis le point le
    plus proche, refusée au-delà des seuils (5 K en évaporation, 10 K en condensation). Points à 60 Hz, sans
    conditions de référence ou d'un autre fluide que la base annoncée : refusés ; conversion vers le CO2 ou le
    propane : refusée (compresseurs dédiés).
    Rend {"methode", "q0", "cas", "conversion", "fluide_donnees", "points", "q0_base", "facteur", "etat_cible",
    "etat_base", "alertes", "raison"}.
    """
    p = _parametres(parametres)
    _exiger(t0_c, ("°C",), "T0")
    _exiger(tc_c, ("°C",), "Tc")
    pre = f"{id}-m2" if id else "m2"
    res = {"methode": "M2 point catalogue", "q0": None, "cas": "refus", "conversion": False, "fluide_donnees": None,
           "points": [], "q0_base": None, "facteur": None, "etat_cible": None, "etat_base": None, "alertes": [],
           "raison": ""}

    def refus(raison: str) -> dict:
        res.update(q0=a_confirmer("kW", f"M2 point catalogue : {raison}", id=pre), raison=raison, cas="refus")
        return res

    if t0_c.nombre is None or tc_c.nombre is None:
        q0 = calculer(lambda: None, "kW", "", [t0_c, tc_c], source="M2 point catalogue", id=pre)
        res.update(q0=q0, raison=_cause([t0_c, tc_c]) or q0.source)
        return res
    t0, tc = t0_c.nombre, tc_c.nombre
    nom_cible = fluides.nom_coolprop(fluide_installation)
    du_modele = [pt for pt in points if _meme_modele(pt.get("modele"), modele)]
    if not du_modele:
        return refus(f"aucun point catalogue pour le modèle « {modele} »")
    a_50 = [pt for pt in du_modele if pt.get("frequence_hz") == FREQUENCE_ACCEPTEE_HZ]
    if not a_50:
        freqs = ", ".join(sorted({nombre_fr(pt["frequence_hz"], 0) if pt.get("frequence_hz") is not None
                                  else "fréquence absente" for pt in du_modele}))
        return refus(f"points du {modele} à {freqs} Hz refusés : seuls les points à 50 Hz sont utilisables "
                     "(à 60 Hz, ≈ +21 % de débit ; materiel/bitzer.md § 6)")
    if len(a_50) < len(du_modele):
        res["alertes"].append(f"{len(du_modele) - len(a_50)} point(s) du {modele} hors 50 Hz écarté(s)")
    complets = [pt for pt in a_50 if not _manque_conditions(pt)]
    if not complets:
        return refus(f"points du {modele} sans conditions de référence complètes ({_manque_conditions(a_50[0])}) : "
                     "inutilisables (methodes/puissance-existante.md § 4)")
    au_fluide = [pt for pt in complets if _nom_cp_ou_rien(pt["fluide"]) == nom_cible]
    if au_fluide:
        donnees, conversion = au_fluide, False
    else:
        if nom_cible in FLUIDES_SANS_CONVERSION:
            return refus(f"aucun point du {modele} au {fluide_installation} ; conversion d'un point d'un autre fluide "
                         f"vers le {fluide_installation} refusée : {FLUIDES_SANS_CONVERSION[nom_cible]}")
        base = p["fluide_base"]["valeur"]
        donnees = [pt for pt in complets if _nom_cp_ou_rien(pt["fluide"]) == fluides.nom_coolprop(base)]
        conversion = True
        if not donnees:
            dispo = ", ".join(sorted({pt["fluide"] for pt in complets}))
            return refus(f"aucun point du {modele} au {fluide_installation} (fluide de l'installation) ni au {base} "
                         f"(fluide de base annoncé) ; fluide(s) du catalogue : {dispo} ≠ fluide de base annoncé : "
                         "conversion refusée")
    fluide_donnees = donnees[0]["fluide"]
    res.update(conversion=conversion, fluide_donnees=fluide_donnees)
    limites = _limites_application(donnees)
    if limites is not None:
        t0_min, t0_max, tc_min, tc_max = limites
        if not (t0_min <= t0 <= t0_max and tc_min <= tc <= tc_max):
            return refus(f"régime t0 {_fr(t0)} °C / tc {_fr(tc)} °C hors des limites d'application du {modele} au "
                         f"{fluide_donnees} (t0 de {_fr(t0_min)} à {_fr(t0_max)} °C, tc de {_fr(tc_min)} à "
                         f"{_fr(tc_max)} °C ; {donnees[0]['document']})")
    grille: dict[tuple[float, float], dict] = {}
    for pt in donnees:
        grille.setdefault((pt["t_evaporation_c"], pt["t_condensation_c"]), pt)

    # (a) / (b) point exact, (c) interpolation, (d) correction de régime depuis le point le plus proche
    if (t0, tc) in grille:
        cas, coins, regime_base = "point exact", [(grille[(t0, tc)], 1.0)], None
    else:
        coins = _interpolation(grille, t0, tc)
        cas, regime_base = "interpolation", None
        if coins is None:
            s0, sc = p["seuil_t0"], p["seuil_tc"]
            if s0.nombre is None or sc.nombre is None:
                return refus("interpolation impossible et seuil de correction de régime à confirmer")
            if limites is None:
                return refus("interpolation impossible et limites d'application absentes : correction de régime refusée")

            def distance(pt):
                d0, dc = abs(pt["t_evaporation_c"] - t0), abs(pt["t_condensation_c"] - tc)
                return (max(d0 / s0.nombre, dc / sc.nombre), math.hypot(d0, dc), d0)
            proche = min(donnees, key=distance)
            d0, dc = abs(proche["t_evaporation_c"] - t0), abs(proche["t_condensation_c"] - tc)
            if d0 > s0.nombre or dc > sc.nombre:
                return refus(f"interpolation impossible ; point le plus proche (t0 {_fr(proche['t_evaporation_c'])} °C, "
                             f"tc {_fr(proche['t_condensation_c'])} °C) à {_fr(d0)} K en évaporation et {_fr(dc)} K "
                             f"en condensation : au-delà des seuils de correction de régime ({s0.texte(marque=False)}, "
                             f"{sc.texte(marque=False)})")
            cas, coins = "correction de régime", [(proche, 1.0)]
            regime_base = (proche["t_evaporation_c"], proche["t_condensation_c"])
    res["cas"], res["points"] = cas, [_resume_point(pt) for pt, _ in coins]
    ombrees = [pt for pt, _ in coins if "ombr" in _sans_accents(pt.get("note") or "")]
    if ombrees:
        res["alertes"].append("point(s) catalogue en case ombrée : refroidissement additionnel ou gaz aspiré limité "
                              f"requis au catalogue ({', '.join(_fr(pt['t_evaporation_c']) + ' / ' + _fr(pt['t_condensation_c']) + ' °C' for pt in ombrees)})")

    # puissance de base : point sourcé, ou interpolation (calcul) entre points sourcés
    vals = [Valeur(pt["puissance_frigo_kw"], "kW", _source_point(pt), SOURCE,
                   id=f"{pre}-point" if len(coins) == 1 else f"{pre}-point-{i}") for i, (pt, _) in enumerate(coins, 1)]
    if cas == "interpolation":
        poids = [w for _, w in coins]
        q0_base = calculer(lambda: sum(w * v.nombre for w, v in zip(poids, vals)), "kW",
                           " + ".join(f"{nombre_fr(w, 4)} × {v.reference()}" for w, v in zip(poids, vals)), vals,
                           source=f"interpolation linéaire sur t0 puis tc entre points catalogue ({fluide_donnees}, "
                                  f"t0 {_fr(t0)} °C, tc {_fr(tc)} °C)", id=f"{pre}-base")
    else:
        q0_base = vals[0]

    # conditions du point (lues dans le CSV) et état thermodynamique de la base
    pt0 = coins[0][0]
    src_pt = _source_point(pt0)
    if regime_base is None:
        t0_b, tc_b = t0_c, tc_c          # même régime numérique que la cible (lu sur la grille du catalogue)
    else:
        t0_b = Valeur(regime_base[0], "°C", src_pt, SOURCE, id=f"{pre}-point-t0")
        tc_b = Valeur(regime_base[1], "°C", src_pt, SOURCE, id=f"{pre}-point-tc")
    if pt0["gaz_aspire_c"] is not None:
        asp_b = Valeur(pt0["gaz_aspire_c"], "°C", src_pt, SOURCE, id=f"{pre}-point-gaz-aspire")
    else:
        asp_b = Valeur(pt0["surchauffe_k"], "K", src_pt, SOURCE, id=f"{pre}-point-surchauffe")
    sc_b = Valeur(pt0["sous_refroidissement_k"], "K", src_pt, SOURCE, id=f"{pre}-point-sous-refroidissement")
    conv_b, conv_c = _convention_point(pt0), p["convention"]["valeur"]
    etat_b = _etat(fluide_donnees, t0_b, tc_b, asp_b, sc_b, conv_b, None, f"{pre}-point")
    etat_c = _etat(fluide_installation, t0_c, tc_c, p["aspiration"], p["sous_refroidissement"], conv_c,
                   p["convention"], f"{pre}-cible")
    nom_b = fluides.nom_coolprop(fluide_donnees)
    rc, dc_, rb, db = etat_c["densite"], etat_c["delta_h"], etat_b["densite"], etat_b["delta_h"]
    # Le rapport des λ (table A) n'intervient que si τ change : autre fluide, autre convention ou autre régime.
    avec_lambda = not (nom_b == nom_cible and conv_b == conv_c and regime_base is None)
    if avec_lambda:
        lc = _lambda(etat_c["tau"], "table_a", f"{pre}-cible-lambda")
        lb = _lambda(etat_b["tau"], "table_a", f"{pre}-point-lambda")
        etat_c["lambda"], etat_b["lambda"] = lc, lb
        facteur = calculer(lambda: (lc.nombre * rc.nombre * dc_.nombre) / (lb.nombre * rb.nombre * db.nombre), "",
                           f"({lc.reference()} × {rc.reference()} × {dc_.reference()}) ÷ "
                           f"({lb.reference()} × {rb.reference()} × {db.reference()})", [lc, rc, dc_, lb, rb, db],
                           source=f"{SOURCE_ENERGYPLUS} × rapport des λ ({SOURCE_TABLE_A})", id=f"{pre}-facteur")
    else:
        facteur = calculer(lambda: (rc.nombre * dc_.nombre) / (rb.nombre * db.nombre), "",
                           f"({rc.reference()} × {dc_.reference()}) ÷ ({rb.reference()} × {db.reference()})",
                           [rc, dc_, rb, db], source=f"{SOURCE_ENERGYPLUS} : même fluide, même régime, seules les "
                           "conditions d'aspiration et de sous-refroidissement changent (exact)", id=f"{pre}-facteur")

    docs = []
    for pt, _ in coins:
        d = f"{pt['document']}, p. {pt['page']}, {pt['source_url']}, lu le {pt['date_lecture']}"
        if d not in docs:
            docs.append(d)
    parties = [f"M2 point catalogue ({cas}) : {' ; '.join(docs)}",
               f"conditions du point : {pt0['condition_reference']}, {nombre_fr(pt0['frequence_hz'], 0)} Hz"]
    if cas == "correction de régime":
        parties.append(f"correction de régime depuis t0 {_fr(regime_base[0])} °C / tc {_fr(regime_base[1])} °C : "
                       "rapport λ × ρ1 × Δh (methodes/puissance-existante.md § 4)")
    if conversion:
        parties.append(f"estimé, conversion {fluide_donnees} → {fluide_installation} par CoolProp {fluides.VERSION} "
                       f"({nom_b} → {nom_cible}), λ table A")
    parties.append(f"propriétés de l'installation : {fluides.source_coolprop(nom_cible, conv_c)}")
    q0 = calculer(lambda: q0_base.nombre * facteur.nombre, "kW", f"{q0_base.reference()} × {facteur.reference()}",
                  [q0_base, facteur], source=" ; ".join(parties), id=pre)
    res.update(q0=q0, q0_base=q0_base, facteur=facteur, etat_cible=etat_c, etat_base=etat_b)
    if q0.nombre is None:
        res["raison"] = _cause([*etat_c.values(), *etat_b.values(), facteur, q0])
    return res


# ---------- les deux méthodes, l'écart et la valeur retenue ----------
def puissance_compresseur(entree: dict, points: list[dict], parametres: dict | None = None) -> dict:
    """M1, M2 (ou « à confirmer » avec la raison), écart (controles.comparer) et valeur retenue d'un compresseur.

    entree : {"id": "c1", "modele": "4HE-18Y-40P", "fluide": "R449A", "t0": Valeur °C, "tc": Valeur °C,
              "volume_balaye": Valeur m³/h (ou absent), "frequence": Valeur Hz (facultatif)}
    Rend {"id", "modele", "fluide", "m1", "m2", "ecart", "ecart_sur_m2", "retenue", "regle", "alertes"}.
    Règle : M2 si disponible, sinon M1 (methodes/puissance-existante.md § 5), écrite dans la source de « retenue ».
    """
    p = _parametres(parametres)
    inconnues = [k for k in entree if k not in CLES_ENTREE]
    if inconnues:
        raise ValueError(f"entrée : clé(s) inconnue(s) {', '.join(inconnues)} ; attendues : {', '.join(CLES_ENTREE)}")
    for cle in ("fluide", "t0", "tc"):
        if entree.get(cle) is None:
            raise ValueError(f"entrée : « {cle} » manquant")
    ident, modele, fluide = entree.get("id", ""), entree.get("modele") or "", entree["fluide"]
    t0, tc, vb, freq = entree["t0"], entree["tc"], entree.get("volume_balaye"), entree.get("frequence")
    pre = f"{ident}-" if ident else ""
    refus_freq = ""
    if freq is not None:
        _exiger(freq, ("Hz",), "la fréquence")
        if freq.nombre is not None and freq.nombre != FREQUENCE_ACCEPTEE_HZ:
            refus_freq = (f"fréquence {freq.texte(marque=False)} refusée : volumes balayés et points catalogue à "
                          "50 Hz uniquement (materiel/bitzer.md § 6)")
    if refus_freq or vb is None:
        raison = refus_freq or "volume balayé absent (ni plaque ni catalogue)"
        m1 = {"methode": "M1 cylindrée", "q0": a_confirmer("kW", f"M1 cylindrée : {raison}", id=f"{pre}m1"),
              "raison": raison}
    else:
        m1 = m1_cylindree(vb, fluide, t0, tc, p, id=ident)
    if refus_freq or not modele:
        raison = refus_freq or "modèle du compresseur absent"
        m2 = {"methode": "M2 point catalogue", "q0": a_confirmer("kW", f"M2 point catalogue : {raison}", id=f"{pre}m2"),
              "cas": "refus", "alertes": [], "raison": raison}
    else:
        m2 = m2_point_catalogue(modele, fluide, t0, tc, points, p, id=ident)
    q1, q2 = m1["q0"], m2["q0"]
    ecart = comparer(q1, q2, p["seuil_ecart"], id=f"{pre}ecart")
    ecart_sur_m2 = calculer(lambda: (q1.nombre - q2.nombre) / q2.nombre * POURCENT, "%",
                            f"({q1.reference()} − {q2.reference()}) ÷ {q2.reference()} × {POURCENT:.0f}", [q1, q2],
                            source="écart signé rapporté à M2 (methodes/puissance-existante.md § 5)",
                            id=f"{pre}ecart-sur-m2")
    regle_txt = "règle : M2 si disponible, sinon M1 (methodes/puissance-existante.md § 5)"
    if q2.nombre is not None:
        regle = "M2"
        retenue = calculer(lambda: q2.nombre, "kW", q2.reference(), [q2],
                           source=f"valeur retenue = M2 (point catalogue), M1 sert de contrôle ; {regle_txt}",
                           id=f"{pre}retenue")
    elif q1.nombre is not None:
        regle = "M1"
        retenue = calculer(lambda: q1.nombre, "kW", q1.reference(), [q1],
                           source=f"valeur retenue = M1 (cylindrée) car M2 indisponible ({m2['raison']}) ; indicatif, "
                                  f"à confirmer par le fournisseur ; {regle_txt}", id=f"{pre}retenue")
    else:
        regle = "aucune"
        retenue = a_confirmer("kW", f"ni M2 ({m2['raison']}) ni M1 ({m1['raison']}) ; {regle_txt}", id=f"{pre}retenue")
    alertes = list(m2.get("alertes", []))
    if regle == "M1":
        alertes.append(f"M2 indisponible ({m2['raison']}) : M1 seule, indicatif, à confirmer par le fournisseur")
    if ecart["alerte"] and regle != "M1":
        alertes.append(ecart["alerte"])
    return {"id": ident, "modele": modele, "fluide": fluide, "m1": m1, "m2": m2, "ecart": ecart,
            "ecart_sur_m2": ecart_sur_m2, "retenue": retenue, "regle": regle, "alertes": alertes}


# ---------- ligne de commande (essai) ----------
def main(argv: list[str] | None = None) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Puissance frigorifique d'un compresseur : M1 (cylindrée) et M2 (point "
                                             "catalogue), écart et valeur retenue.")
    ap.add_argument("--modele", default="", help="référence du compresseur, ex. 4HE-18Y-40P")
    ap.add_argument("--fluide", required=True, help="fluide de l'installation, ex. R449A")
    ap.add_argument("--t0", type=float, required=True, help="température d'évaporation (°C)")
    ap.add_argument("--tc", type=float, required=True, help="température de condensation (°C)")
    ap.add_argument("--volume", type=float, help="volume balayé à 50 Hz (m³/h)")
    ap.add_argument("--surchauffe", type=float, help="surchauffe (K), à la place du gaz aspiré")
    ap.add_argument("--gaz-aspire", type=float, help="température du gaz aspiré (°C)")
    ap.add_argument("--sous-refroidissement", type=float, help="sous-refroidissement (K)")
    ap.add_argument("--convention", choices=("rosee", "moyenne"), help="convention de T0 / Tc (défaut : rosée)")
    ap.add_argument("--lambda", dest="lambda_methode", choices=tuple(METHODES_LAMBDA), help="méthode de λ pour M1")
    ap.add_argument("--points", default=str(CHEMIN_POINTS_DEFAUT), help="CSV des points catalogue")
    ap.add_argument("--json", action="store_true", help="sortie JSON complète")
    a = ap.parse_args(argv)
    src = "argument de la ligne de commande (essai)"
    param: dict = {}
    if a.surchauffe is not None:
        param["surchauffe"] = Valeur(a.surchauffe, "K", src, HYPOTHESE, id="param-surchauffe")
    if a.gaz_aspire is not None:
        param["gaz_aspire"] = Valeur(a.gaz_aspire, "°C", src, HYPOTHESE, id="param-gaz-aspire")
    if a.sous_refroidissement is not None:
        param["sous_refroidissement"] = Valeur(a.sous_refroidissement, "K", src, HYPOTHESE,
                                               id="param-sous-refroidissement")
    if a.convention:
        param["convention"] = choix(a.convention, src, HYPOTHESE, "param-convention")
    if a.lambda_methode:
        param["lambda_methode"] = choix(a.lambda_methode, src + " ; " + (SOURCE_TABLE_A if a.lambda_methode == "table_a"
                                        else SOURCE_EFPME), HYPOTHESE, "param-lambda")
    entree = {"id": "essai", "modele": a.modele, "fluide": a.fluide,
              "t0": Valeur(a.t0, "°C", src, SOURCE, id="t0"), "tc": Valeur(a.tc, "°C", src, SOURCE, id="tc")}
    if a.volume is not None:
        entree["volume_balaye"] = Valeur(a.volume, "m³/h", src, SOURCE, id="volume-balaye")
    try:
        points = charger_points(a.points)
        r = puissance_compresseur(entree, points, param)
    except (ValueError, TypeError, OSError) as exc:
        sys.exit(f"refusé : {exc}")
    if a.json:
        print(en_json(r))
        return
    m1, m2 = r["m1"], r["m2"]
    print(f"Compresseur {a.modele or '?'} · {a.fluide} · T0 {_fr(a.t0)} °C / Tc {_fr(a.tc)} °C")
    if "lambda" in m1:
        print(f"M1 cylindrée       : {m1['q0'].texte()}   (λ {m1['lambda'].texte(3)}, τ {m1['tau'].texte(3)}, "
              f"ρ1 {m1['densite'].texte()}, Δh {m1['delta_h'].texte()})")
    else:
        print(f"M1 cylindrée       : {m1['q0'].texte()}")
    print(f"    source : {m1['q0'].source_texte()}")
    if m1.get("raison"):
        print(f"    raison : {m1['raison']}")
    conv = f", conversion {m2['fluide_donnees']} → {a.fluide}" if m2.get("conversion") else ""
    extra = f"   ({m2['cas']}{conv}, facteur {m2['facteur'].texte(4)})" if m2.get("facteur") is not None else ""
    print(f"M2 point catalogue : {m2['q0'].texte()}{extra}")
    print(f"    source : {m2['q0'].source_texte()}")
    if m2.get("raison"):
        print(f"    raison : {m2['raison']}")
    print(f"Écart M1 / M2      : {r['ecart']['ecart'].texte()} rapporté à la moyenne ; {r['ecart_sur_m2'].texte()} "
          f"rapporté à M2 ; seuil {r['ecart']['seuil'].texte()}")
    print(f"Valeur retenue     : {r['retenue'].texte()}   ({r['regle']})")
    print(f"    source : {r['retenue'].source_texte()}")
    for al in r["alertes"]:
        print(f"Alerte : {al}")


if __name__ == "__main__":
    main()
