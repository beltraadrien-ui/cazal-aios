"""Propriétés des fluides frigorigènes par CoolProp : le seul module du skill qui importe CoolProp.

Rôle : températures et pressions de saturation, glissement des mélanges, état du gaz aspiré (densité,
enthalpie), enthalpie du liquide avant le détendeur, Δh à l'évaporateur et taux de compression, pour
les calculs de puissance de compresseurs.py (méthode : dimensionnement/savoir/methodes/puissance-existante.md).

Usage (bibliothèque) :
    from fluides import nom_coolprop, p_saturation, etat_aspiration, delta_h_evaporateur
    nom_coolprop("R449A")                                   → « R449A.mix »
    designation("R 507") ; designation("r404a")             → « R507A » ; « R404A »  (écritures de plaque)
    p_saturation("R449A", -30).texte()                      → « 1,60 bar »  (pression absolue, point de rosée)
    e = etat_aspiration("R449A", -30, gaz_aspire_c=20)
    e["densite"].texte(), e["enthalpie"].texte()            → « 5,88 kg/m³ », « 428,2 kJ/kg »
    delta_h_evaporateur("R449A", -30, 40, surchauffe_k=10).texte()   → « 138,4 kJ/kg »

Entrées : des nombres (float) ou des Valeur (« °C », « bar », « K ») ; une entrée « à confirmer » donne un
résultat « à confirmer ». Sorties publiques : des Valeur dont la source dit « CoolProp 8.0.0, <nom CoolProp>,
convention <rosée|moyenne|bulle> ». Température ou pression hors domaine (CO2 sous le point triple, au-dessus
du point critique, sous la limite basse de CoolProp…) : ValueError avec un message en français.
Fonctions de calcul en nombres (pour compresseurs.py) : cycle(), pression_pa(), aspiration(), liquide(), en
unités SI (Pa, J/kg ; températures en °C).

Conventions :
- pressions absolues ; enthalpies : seules les différences ont un sens (état de référence propre à CoolProp) ;
- « rosee » : la température donnée est celle de la vapeur saturée (point de rosée, convention Bitzer /
  EN 12900) ; « bulle » : liquide saturé ; « moyenne » : moyenne des températures de bulle et de rosée à la
  même pression (sens à confirmer par Loïc, question 1 du 2026-10-06) ;
- surchauffe comptée depuis la température de rosée à P0 ; sous-refroidissement depuis la température de
  bulle à Pc ; détente isenthalpique (h à l'entrée de l'évaporateur = h du liquide avant le détendeur).
"""
from __future__ import annotations

import functools
import math
import re
import sys
import unicodedata
from pathlib import Path

import CoolProp
from CoolProp.CoolProp import PropsSI

sys.path.insert(0, str(Path(__file__).resolve().parent))
from valeur import Valeur, calculer, nombre_fr  # noqa: E402

# ---------- constantes ----------
# Version réellement installée, écrite dans chaque source (requirements.txt : CoolProp==8.0.0, décision du 2026-10-03).
VERSION = CoolProp.__version__
# 0 °C = 273,15 K : définition du degré Celsius (Brochure SI du BIPM, 9e édition 2019, § 2.3.1).
K_PAR_C = 273.15
# 1 bar = 100 000 Pa (Brochure SI du BIPM, 9e édition 2019, tableau 8).
PA_PAR_BAR = 1.0e5
# 1 kJ = 1 000 J : préfixe SI « kilo » (Brochure SI du BIPM, 9e édition 2019, tableau 7).
J_PAR_KJ = 1.0e3
# Résolution de la convention « moyenne » par dichotomie : tolérance et nombre d'itérations. Choix de calcul
# (pas une donnée physique) : 1e-6 K est mille fois plus fin que l'affichage au 0,01 K près.
TOLERANCE_K = 1.0e-6
ITERATIONS_MAX = 200

# Désignation (ASHRAE 34, écrite en majuscules sans tiret ni espace) → nom CoolProp 8.0.0.
# Mélanges : modèle de mélange de CoolProp (« .mix »), compositions ASHRAE 34-2022 identiques à
# dimensionnement/savoir/fluides/compositions-melanges.csv.
# R404A (et R507A, R410A) : « .mix » plutôt que le pseudo-corps pur, choix du 2026-10-06 :
#   1. même modèle que les autres mélanges, donc points de bulle et de rosée et convention « moyenne » cohérents ;
#   2. même nom que l'ajustement de la table A de λ et que l'exemple de methodes/puissance-existante.md (§ 8) ;
#   3. écart mesuré entre « R404A » et « R404A.mix » : 0,003 % sur ρ1 × Δh à −30 / +40 °C (gaz aspiré 20 °C),
#      vérifié par tests/test_calculs.py.
NOMS_COOLPROP = {
    "R404A": "R404A.mix", "R507A": "R507A.mix", "R407A": "R407A.mix", "R407C": "R407C.mix",
    "R407F": "R407F.mix", "R410A": "R410A.mix", "R448A": "R448A.mix", "R449A": "R449A.mix",
    "R452A": "R452A.mix", "R454A": "R454A.mix", "R454C": "R454C.mix", "R455A": "R455A.mix",
    "R513A": "R513A.mix",
    "R744": "CO2", "CO2": "CO2",
    "R134A": "R134a", "R32": "R32", "R125": "R125", "R22": "R22",
    "R1234YF": "R1234yf", "R1234ZE": "R1234ze(E)", "R1234ZE(E)": "R1234ze(E)",
    "R290": "R290", "PROPANE": "R290", "R600A": "R600a", "ISOBUTANE": "R600a", "R1270": "R1270",
    "R717": "R717", "NH3": "R717", "AMMONIAC": "R717",
}
# Un nom CoolProp déjà écrit (« R449A.mix », « CO2 ») est accepté tel quel.
_NOMS_DIRECTS = {nom.upper(): nom for nom in NOMS_COOLPROP.values()}
# Écritures de plaque sans la lettre de la série ASHRAE 34, acceptées seulement quand la série n'a qu'un membre
# (R404A, R507A) : « R507 » → « R507A ». Les séries à plusieurs membres (R407A/C/F, R410A/B, R449A/B/C, R452A/B/C,
# R513A/B) restent refusées sans leur lettre : la lettre change le fluide. Décision du 2026-10-08 (friction 7 du test
# « session neuve » : la plaque d'une centrale écrivait « R507 »).
ALIAS_PLAQUE = {"R404": "R404A", "R507": "R507A"}

# Conventions de température de saturation acceptées et leur libellé dans les sources.
LIBELLES = {"rosee": "rosée", "bulle": "bulle", "moyenne": "moyenne"}
QUALITE = {"rosee": 1.0, "bulle": 0.0}   # titre en vapeur : 1 = vapeur saturée (rosée), 0 = liquide saturé (bulle)


# ---------- noms et sources ----------
def _cle(texte: str) -> str:
    return texte.strip().upper().replace("-", "").replace(" ", "")


def nom_coolprop(fluide: str) -> str:
    """« R449A », « R-449A », « r449a » → « R449A.mix » ; « R744 » ou « CO2 » → « CO2 » ; inconnu : ValueError."""
    if not isinstance(fluide, str) or not fluide.strip():
        raise ValueError(f"fluide absent ou illisible : {fluide!r}")
    cle = ALIAS_PLAQUE.get(_cle(fluide), _cle(fluide))
    if cle in NOMS_COOLPROP:
        return NOMS_COOLPROP[cle]
    if fluide.strip().upper() in _NOMS_DIRECTS:
        return _NOMS_DIRECTS[fluide.strip().upper()]
    connus = ", ".join(sorted(k for k in NOMS_COOLPROP if k[0] == "R" or k == "CO2"))
    raise ValueError(f"fluide inconnu : « {fluide} » ; fluides pris en charge : {connus}")


def designation(fluide: str) -> str | None:
    """Désignation de référence (ASHRAE 34) d'une écriture de plaque ou de rapport, None si elle n'est pas reconnue :
    « R507 », « R-507A », « r507a » → « R507A » ; « R404a » → « R404A » ; « R 449 A » → « R449A » ; « R134A » →
    « R134a » ; « R744 » → « R744 ». Seules les désignations « R » + chiffres (+ une lettre) sont traitées : « CO2 »,
    « propane », « R1234yf » ou un texte (« non indiqué ») rendent None et restent tels qu'écrits."""
    if not isinstance(fluide, str) or not fluide.strip():
        return None
    cle = ALIAS_PLAQUE.get(_cle(fluide), _cle(fluide))
    if not re.fullmatch(r"R\d+[A-Z]?", cle) or cle not in NOMS_COOLPROP:
        return None
    nom = NOMS_COOLPROP[cle]
    if nom.endswith(".mix"):
        return nom[:-len(".mix")]
    return nom if nom.startswith("R") else cle


def convention_normalisee(convention: str, permises: tuple[str, ...] = ("rosee", "moyenne")) -> str:
    """« rosée », « Rosee », « moyenne » → « rosee », « moyenne » ; sinon ValueError."""
    cle = unicodedata.normalize("NFKD", str(convention)).encode("ascii", "ignore").decode().strip().lower()
    if cle not in permises:
        raise ValueError(f"convention inconnue : « {convention} » ; conventions possibles : "
                         + ", ".join(LIBELLES[p] for p in permises))
    return cle


def source_coolprop(nom_cp: str, convention: str) -> str:
    """Texte de la colonne Source pour une propriété CoolProp."""
    return f"CoolProp {VERSION}, {nom_cp}, convention {LIBELLES[convention]}"


# ---------- garde-fous de domaine ----------
@functools.lru_cache(maxsize=None)
def _limites(nom_cp: str) -> tuple[float, float, float, float | None, float | None]:
    """(T_min, T_triple en K, p_triple en Pa, T_critique en K ou None, p_critique en Pa ou None), lus dans CoolProp.

    Mélanges : CoolProp ne donne pas le point critique par Props1SI (None) ; au-delà, c'est CoolProp qui échoue.
    """
    t_min, t_triple, p_triple = PropsSI("Tmin", nom_cp), PropsSI("Ttriple", nom_cp), PropsSI("ptriple", nom_cp)
    try:
        t_crit, p_crit = PropsSI("Tcrit", nom_cp), PropsSI("pcrit", nom_cp)
    except ValueError:
        t_crit = p_crit = None
    return t_min, t_triple, p_triple, t_crit, p_crit


def _c(t_k: float) -> str:
    return nombre_fr(t_k - K_PAR_C, 1) + " °C"


def _bar(p_pa: float) -> str:
    return nombre_fr(p_pa / PA_PAR_BAR, 2) + " bar"


def _verifier_temperature(nom_cp: str, t_c: float, quoi: str = "température") -> None:
    if not math.isfinite(t_c):
        raise ValueError(f"{quoi} non finie : {t_c!r}")
    t_k = t_c + K_PAR_C
    t_min, t_triple, p_triple, t_crit, _ = _limites(nom_cp)
    if nom_cp == "CO2" and t_k < t_triple:
        raise ValueError(f"CO2 (R744) : {quoi} de {nombre_fr(t_c, 1)} °C sous le point triple ({_c(t_triple)}, "
                         f"{_bar(p_triple)}, CoolProp {VERSION}) : pas d'équilibre liquide-vapeur (le CO2 devient "
                         "solide), calcul refusé")
    if t_k < t_min:
        raise ValueError(f"{nom_cp} : {quoi} de {nombre_fr(t_c, 1)} °C sous la limite basse de CoolProp {VERSION} "
                         f"({_c(t_min)}) : hors domaine, calcul refusé")
    if t_crit is not None and t_k >= t_crit:
        raise ValueError(f"{nom_cp} : {quoi} de {nombre_fr(t_c, 1)} °C au-delà de la température critique "
                         f"({_c(t_crit)}, CoolProp {VERSION}) : pas de saturation possible"
                         + (" (cycle transcritique, hors domaine de ce calcul)" if nom_cp == "CO2" else "")
                         + ", calcul refusé")


def _verifier_pression(nom_cp: str, p_pa: float, quoi: str = "pression") -> None:
    if not math.isfinite(p_pa) or p_pa <= 0:
        raise ValueError(f"{quoi} invalide : {p_pa!r} Pa (pression absolue attendue, strictement positive)")
    _, t_triple, p_triple, _, p_crit = _limites(nom_cp)
    if p_pa < p_triple:
        raise ValueError(f"{nom_cp} : {quoi} de {_bar(p_pa)} sous la pression du point triple ({_bar(p_triple)}, "
                         f"{_c(t_triple)}, CoolProp {VERSION}) : pas d'équilibre liquide-vapeur, calcul refusé")
    if p_crit is not None and p_pa >= p_crit:
        raise ValueError(f"{nom_cp} : {quoi} de {_bar(p_pa)} au-delà de la pression critique ({_bar(p_crit)}, "
                         f"CoolProp {VERSION}) : pas de saturation possible, calcul refusé")


def _props(sortie: str, n1: str, v1: float, n2: str, v2: float, nom_cp: str, quoi: str) -> float:
    """PropsSI avec un refus en français (au lieu de l'exception anglaise de CoolProp)."""
    try:
        r = PropsSI(sortie, n1, v1, n2, v2, nom_cp)
    except ValueError as exc:
        raise ValueError(f"CoolProp {VERSION} refuse le calcul ({quoi}, {nom_cp}) : {exc}") from None
    if not math.isfinite(r):
        raise ValueError(f"CoolProp {VERSION} : résultat non fini ({quoi}, {nom_cp})")
    return r


# ---------- saturation (nombres, SI) ----------
def _p_sat(nom_cp: str, t_c: float, convention: str) -> float:
    """Pression de saturation (Pa) à la température t_c (°C) : point de rosée, de bulle ou température moyenne."""
    _verifier_temperature(nom_cp, t_c)
    if convention == "moyenne":
        return _p_moyenne(nom_cp, t_c)
    return _props("P", "T", t_c + K_PAR_C, "Q", QUALITE[convention], nom_cp,
                  f"pression de saturation ({LIBELLES[convention]}) à {nombre_fr(t_c, 2)} °C")


def _t_sat(nom_cp: str, p_pa: float, convention: str) -> float:
    """Température de saturation (°C) à la pression p_pa (Pa) : rosée, bulle ou moyenne des deux."""
    _verifier_pression(nom_cp, p_pa)
    if convention == "moyenne":
        return (_t_sat(nom_cp, p_pa, "rosee") + _t_sat(nom_cp, p_pa, "bulle")) / 2
    t = _props("T", "P", p_pa, "Q", QUALITE[convention], nom_cp,
               f"température de saturation ({LIBELLES[convention]}) à {_bar(p_pa)}") - K_PAR_C
    _verifier_temperature(nom_cp, t, "température de saturation")
    return t


def _p_moyenne(nom_cp: str, t_c: float) -> float:
    """Pression (Pa) à laquelle la moyenne des températures de bulle et de rosée vaut t_c (dichotomie)."""
    bas, haut = _p_sat(nom_cp, t_c, "rosee"), _p_sat(nom_cp, t_c, "bulle")
    if haut <= bas:                       # corps pur ou azéotrope : pas de glissement
        return bas
    milieu = (bas + haut) / 2
    for _ in range(ITERATIONS_MAX):
        milieu = (bas + haut) / 2
        t_moy = _t_sat(nom_cp, milieu, "moyenne")
        if abs(t_moy - t_c) < TOLERANCE_K:
            return milieu
        if t_moy < t_c:
            bas = milieu
        else:
            haut = milieu
    return milieu


# ---------- états du cycle (nombres, SI) ----------
def _aspiration(nom_cp: str, t0_c: float, gaz_aspire_c: float | None, surchauffe_k: float | None,
                convention: str) -> dict:
    if (gaz_aspire_c is None) == (surchauffe_k is None):
        raise ValueError("état d'aspiration : donner soit la température du gaz aspiré, soit la surchauffe (une seule des deux)")
    p0 = _p_sat(nom_cp, t0_c, convention)
    t_rosee = t0_c if convention == "rosee" else _t_sat(nom_cp, p0, "rosee")
    if surchauffe_k is not None:
        if not math.isfinite(surchauffe_k) or surchauffe_k < 0:
            raise ValueError(f"surchauffe invalide : {surchauffe_k!r} K (attendu : 0 ou plus)")
        t_asp = t_rosee + surchauffe_k
    else:
        if not math.isfinite(gaz_aspire_c):
            raise ValueError(f"température du gaz aspiré invalide : {gaz_aspire_c!r}")
        t_asp = gaz_aspire_c
        if t_asp < t_rosee:
            raise ValueError(f"gaz aspiré à {nombre_fr(t_asp, 1)} °C sous la température de rosée à P0 "
                             f"({nombre_fr(t_rosee, 1)} °C) : ce ne serait pas de la vapeur surchauffée, calcul refusé")
    quoi = f"gaz aspiré à {nombre_fr(t_asp, 2)} °C et {_bar(p0)}"
    if t_asp == t_rosee:                  # vapeur saturée : l'état (P, T) est sur la courbe, on le prend par le titre
        rho = _props("D", "P", p0, "Q", 1.0, nom_cp, quoi)
        h = _props("H", "P", p0, "Q", 1.0, nom_cp, quoi)
    else:
        rho = _props("D", "T", t_asp + K_PAR_C, "P", p0, nom_cp, quoi)
        h = _props("H", "T", t_asp + K_PAR_C, "P", p0, nom_cp, quoi)
    return {"p0_pa": p0, "t_rosee_p0_c": t_rosee, "t_aspiration_c": t_asp, "densite": rho, "h_aspiration": h}


def _liquide(nom_cp: str, tc_c: float, sous_refroidissement_k: float, convention: str) -> dict:
    if not math.isfinite(sous_refroidissement_k) or sous_refroidissement_k < 0:
        raise ValueError(f"sous-refroidissement invalide : {sous_refroidissement_k!r} K (attendu : 0 ou plus)")
    pc = _p_sat(nom_cp, tc_c, convention)
    t_bulle = _t_sat(nom_cp, pc, "bulle")
    t_liq = t_bulle - sous_refroidissement_k
    quoi = f"liquide à {nombre_fr(t_liq, 2)} °C et {_bar(pc)}"
    if sous_refroidissement_k == 0:
        h = _props("H", "P", pc, "Q", 0.0, nom_cp, quoi)
    else:
        _verifier_temperature(nom_cp, t_liq, "température du liquide sous-refroidi")
        h = _props("H", "T", t_liq + K_PAR_C, "P", pc, nom_cp, quoi)
    return {"pc_pa": pc, "t_bulle_pc_c": t_bulle, "t_liquide_c": t_liq, "h_liquide": h}


@functools.lru_cache(maxsize=1024)
def _cycle(nom_cp: str, t0_c: float, tc_c: float, gaz_aspire_c: float | None, surchauffe_k: float | None,
           sous_refroidissement_k: float, convention: str) -> dict:
    if not tc_c > t0_c:
        raise ValueError(f"condensation ({nombre_fr(tc_c, 1)} °C) pas au-dessus de l'évaporation "
                         f"({nombre_fr(t0_c, 1)} °C) : régime incohérent, calcul refusé")
    asp = _aspiration(nom_cp, t0_c, gaz_aspire_c, surchauffe_k, convention)
    liq = _liquide(nom_cp, tc_c, sous_refroidissement_k, convention)
    dh = asp["h_aspiration"] - liq["h_liquide"]
    if not dh > 0:
        raise ValueError(f"Δh à l'évaporateur nul ou négatif ({nombre_fr(dh / J_PAR_KJ, 1)} kJ/kg) : régime "
                         "incohérent, calcul refusé")
    return {**asp, **liq, "tau": liq["pc_pa"] / asp["p0_pa"], "delta_h": dh}


def cycle(fluide: str, t0_c: float, tc_c: float, gaz_aspire_c: float | None = None,
          surchauffe_k: float | None = None, sous_refroidissement_k: float = 0.0,
          convention: str = "rosee") -> dict:
    """Toutes les grandeurs d'un régime en nombres SI (mise en cache) : p0_pa, pc_pa, tau (Pc / P0),
    t_rosee_p0_c, t_aspiration_c, densite (kg/m³), h_aspiration (J/kg), t_bulle_pc_c, t_liquide_c,
    h_liquide (J/kg), delta_h (J/kg). Lève ValueError hors domaine."""
    return dict(_cycle(nom_coolprop(fluide), float(t0_c), float(tc_c),
                       None if gaz_aspire_c is None else float(gaz_aspire_c),
                       None if surchauffe_k is None else float(surchauffe_k),
                       float(sous_refroidissement_k), convention_normalisee(convention)))


def pression_pa(fluide: str, t_c: float, convention: str = "rosee") -> float:
    """Pression absolue de saturation (Pa) à t_c (°C), dans la convention donnée. Lève ValueError hors domaine."""
    return _p_sat(nom_coolprop(fluide), float(t_c), convention_normalisee(convention, ("rosee", "bulle", "moyenne")))


def aspiration(fluide: str, t0_c: float, gaz_aspire_c: float | None = None, surchauffe_k: float | None = None,
               convention: str = "rosee") -> dict:
    """État du gaz aspiré en nombres SI : p0_pa, t_rosee_p0_c, t_aspiration_c, densite (kg/m³), h_aspiration (J/kg)."""
    return _aspiration(nom_coolprop(fluide), float(t0_c), gaz_aspire_c, surchauffe_k, convention_normalisee(convention))


def liquide(fluide: str, tc_c: float, sous_refroidissement_k: float = 0.0, convention: str = "rosee") -> dict:
    """Liquide avant le détendeur en nombres SI : pc_pa, t_bulle_pc_c, t_liquide_c, h_liquide (J/kg)."""
    return _liquide(nom_coolprop(fluide), float(tc_c), float(sous_refroidissement_k), convention_normalisee(convention))


# ---------- fonctions publiques : des Valeur ----------
def _nombre(x, unite: str, quoi: str) -> float | None:
    """Nombre d'une entrée (float ou Valeur dans l'unité attendue) ; None si la Valeur est « à confirmer »."""
    if x is None:
        return None
    if isinstance(x, Valeur):
        if x.unite != unite:
            raise ValueError(f"{quoi} « {x.reference()} » doit être en {unite} (reçu : « {x.unite} »)")
        return x.nombre
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise TypeError(f"{quoi} : nombre ou Valeur attendu, reçu {x!r}")
    return float(x)


def _ref(x, unite: str) -> str:
    if isinstance(x, Valeur):
        return x.reference()
    return nombre_fr(float(x), 2) + " " + unite


def _resultat(calcul, unite: str, formule: str, entrees: list, nom_cp: str, convention: str, id: str) -> Valeur:
    """Valeur sourcée CoolProp. Entrée « à confirmer » → résultat « à confirmer » ; hors domaine → ValueError."""
    valeurs = [e for e in entrees if isinstance(e, Valeur)]
    source = source_coolprop(nom_cp, convention)
    if any(v.nombre is None for v in valeurs):
        return calculer(calcul, unite, formule, valeurs, source=source, id=id)
    return calculer(calcul(), unite, formule, valeurs, source=source, id=id)


def p_saturation(fluide: str, t_c, phase: str = "rosee", id: str = "") -> Valeur:
    """Pression absolue de saturation (bar) à la température t_c (°C) ; phase : « rosee », « bulle » ou « moyenne »."""
    nom, conv = nom_coolprop(fluide), convention_normalisee(phase, ("rosee", "bulle", "moyenne"))
    t = _nombre(t_c, "°C", "la température")
    return _resultat(lambda: _p_sat(nom, t, conv) / PA_PAR_BAR, "bar",
                     f"Psat {LIBELLES[conv]}({_ref(t_c, '°C')})", [t_c], nom, conv, id)


def t_saturation(fluide: str, p_bar, phase: str = "rosee", id: str = "") -> Valeur:
    """Température de saturation (°C) à la pression absolue p_bar ; phase : « rosee », « bulle » ou « moyenne »."""
    nom, conv = nom_coolprop(fluide), convention_normalisee(phase, ("rosee", "bulle", "moyenne"))
    p = _nombre(p_bar, "bar", "la pression")
    return _resultat(lambda: _t_sat(nom, p * PA_PAR_BAR, conv), "°C",
                     f"Tsat {LIBELLES[conv]}({_ref(p_bar, 'bar')})", [p_bar], nom, conv, id)


def glissement(fluide: str, p_bar, id: str = "") -> Valeur:
    """Glissement de température (K) d'un mélange à la pression p_bar : T rosée − T bulle (0 pour un corps pur)."""
    nom = nom_coolprop(fluide)
    p = _nombre(p_bar, "bar", "la pression")
    return _resultat(lambda: _t_sat(nom, p * PA_PAR_BAR, "rosee") - _t_sat(nom, p * PA_PAR_BAR, "bulle"), "K",
                     f"Tsat rosée({_ref(p_bar, 'bar')}) − Tsat bulle({_ref(p_bar, 'bar')})", [p_bar], nom, "rosee", id)


def etat_aspiration(fluide: str, t0_c, gaz_aspire_c=None, surchauffe_k=None, convention: str = "rosee",
                    id: str = "") -> dict:
    """État du gaz aspiré au régime T0 : {"p0" (bar), "t_aspiration" (°C), "densite" (kg/m³), "enthalpie" (kJ/kg)}.

    Donner soit gaz_aspire_c (température absolue du gaz aspiré, ex. 20 °C des catalogues Bitzer), soit
    surchauffe_k (comptée depuis la rosée à P0 ; 0 = vapeur saturée).
    """
    nom, conv = nom_coolprop(fluide), convention_normalisee(convention)
    t0 = _nombre(t0_c, "°C", "T0")
    ga = _nombre(gaz_aspire_c, "°C", "le gaz aspiré")
    sh = _nombre(surchauffe_k, "K", "la surchauffe")
    if (gaz_aspire_c is None) == (surchauffe_k is None):
        raise ValueError("état d'aspiration : donner soit gaz_aspire_c, soit surchauffe_k (une seule des deux)")
    cond = gaz_aspire_c if gaz_aspire_c is not None else surchauffe_k
    cond_txt = (f"gaz aspiré {_ref(gaz_aspire_c, '°C')}" if gaz_aspire_c is not None
                else f"surchauffe {_ref(surchauffe_k, 'K')}")
    entrees = [t0_c, cond]
    pre = f"{id}-" if id else ""

    def c():
        return _aspiration(nom, t0, ga, sh, conv)
    regime = f"T0 = {_ref(t0_c, '°C')}, {cond_txt}"
    return {
        "p0": _resultat(lambda: c()["p0_pa"] / PA_PAR_BAR, "bar", f"P0 = Psat {LIBELLES[conv]}({_ref(t0_c, '°C')})",
                        [t0_c], nom, conv, pre + "p0" if id else ""),
        "t_aspiration": _resultat(lambda: c()["t_aspiration_c"], "°C", f"T aspiration ({regime})", entrees, nom, conv,
                                  pre + "t-aspiration" if id else ""),
        "densite": _resultat(lambda: c()["densite"], "kg/m³", f"ρ1 ({regime})", entrees, nom, conv,
                             pre + "densite" if id else ""),
        "enthalpie": _resultat(lambda: c()["h_aspiration"] / J_PAR_KJ, "kJ/kg", f"h1 ({regime})", entrees, nom, conv,
                               pre + "h1" if id else ""),
    }


def enthalpie_liquide(fluide: str, tc_c, sous_refroidissement_k=0.0, convention: str = "rosee", id: str = "") -> dict:
    """Liquide avant le détendeur : {"pc" (bar), "t_liquide" (°C), "enthalpie" (kJ/kg)} ; sous-refroidissement
    compté depuis la température de bulle à Pc (0 = liquide saturé)."""
    nom, conv = nom_coolprop(fluide), convention_normalisee(convention)
    tc = _nombre(tc_c, "°C", "Tc")
    sc = _nombre(sous_refroidissement_k, "K", "le sous-refroidissement")
    entrees = [tc_c, sous_refroidissement_k]
    regime = f"Tc = {_ref(tc_c, '°C')}, sous-refroidissement {_ref(sous_refroidissement_k, 'K')}"
    pre = f"{id}-" if id else ""

    def c():
        return _liquide(nom, tc, sc, conv)
    return {
        "pc": _resultat(lambda: c()["pc_pa"] / PA_PAR_BAR, "bar", f"Pc = Psat {LIBELLES[conv]}({_ref(tc_c, '°C')})",
                        [tc_c], nom, conv, pre + "pc" if id else ""),
        "t_liquide": _resultat(lambda: c()["t_liquide_c"], "°C", f"T liquide ({regime})", entrees, nom, conv,
                               pre + "t-liquide" if id else ""),
        "enthalpie": _resultat(lambda: c()["h_liquide"] / J_PAR_KJ, "kJ/kg", f"h4 ({regime})", entrees, nom, conv,
                               pre + "h4" if id else ""),
    }


def delta_h_evaporateur(fluide: str, t0_c, tc_c, gaz_aspire_c=None, surchauffe_k=None, sous_refroidissement_k=0.0,
                        convention: str = "rosee", id: str = "") -> Valeur:
    """Δh = h1 (gaz aspiré) − h4 (liquide avant détendeur), en kJ/kg."""
    nom, conv = nom_coolprop(fluide), convention_normalisee(convention)
    if (gaz_aspire_c is None) == (surchauffe_k is None):
        raise ValueError("Δh : donner soit gaz_aspire_c, soit surchauffe_k (une seule des deux)")
    t0, tc = _nombre(t0_c, "°C", "T0"), _nombre(tc_c, "°C", "Tc")
    ga, sh = _nombre(gaz_aspire_c, "°C", "le gaz aspiré"), _nombre(surchauffe_k, "K", "la surchauffe")
    sc = _nombre(sous_refroidissement_k, "K", "le sous-refroidissement")
    cond = gaz_aspire_c if gaz_aspire_c is not None else surchauffe_k
    cond_txt = (f"gaz aspiré {_ref(gaz_aspire_c, '°C')}" if gaz_aspire_c is not None
                else f"surchauffe {_ref(surchauffe_k, 'K')}")
    formule = (f"h1 − h4 (T0 = {_ref(t0_c, '°C')}, Tc = {_ref(tc_c, '°C')}, {cond_txt}, "
               f"sous-refroidissement {_ref(sous_refroidissement_k, 'K')})")
    return _resultat(lambda: _cycle(nom, t0, tc, ga, sh, sc, conv)["delta_h"] / J_PAR_KJ, "kJ/kg", formule,
                     [t0_c, tc_c, cond, sous_refroidissement_k], nom, conv, id)


def taux_compression(fluide: str, t0_c, tc_c, convention: str = "rosee", id: str = "") -> Valeur:
    """τ = Pc / P0 (pressions absolues) au régime T0 / Tc, sans dimension."""
    nom, conv = nom_coolprop(fluide), convention_normalisee(convention)
    t0, tc = _nombre(t0_c, "°C", "T0"), _nombre(tc_c, "°C", "Tc")
    return _resultat(lambda: _p_sat(nom, tc, conv) / _p_sat(nom, t0, conv), "",
                     f"Psat {LIBELLES[conv]}({_ref(tc_c, '°C')}) ÷ Psat {LIBELLES[conv]}({_ref(t0_c, '°C')})",
                     [t0_c, tc_c], nom, conv, id)
