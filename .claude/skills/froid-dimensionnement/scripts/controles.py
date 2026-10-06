"""Contrôles de vraisemblance et marge : écart entre deux valeurs, seuil, somme par poste, puissance demandée.

Les paramètres (seuil d'écart, marge) sont eux-mêmes des Valeur dont la source est écrite :
« règle de Loïc du 24/09 (visio, 37:24) » si elle est sourcée, « hypothèse en attente de la réponse de
Loïc » sinon. Aucun seuil ni aucune marge n'est codé en dur ici : ils viennent de 2-entrees.json.

Usage (bibliothèque) :
    from controles import ecart_relatif, comparer, somme, puissance_demandee
    seuil = Valeur(15, "%", "hypothèse en attente de la réponse de Loïc", "hypothèse", id="seuil-ecart")
    r = comparer(m1, m2, seuil)          → {"ecart": Valeur %, "seuil": Valeur, "depassement": bool | None, "alerte": str}
    total = somme([c1, c2, c3], "kW", id="poste-a")
    demande = puissance_demandee(total, marge, id="poste-a-demande")
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from unites import convertir  # noqa: E402
from valeur import HYPOTHESE, Valeur, calculer  # noqa: E402

POURCENT = 100.0   # définition du pourcentage (1 = 100 %)


def _meme_unite(v: Valeur, unite: str) -> Valeur:
    """Ramène v dans l'unité voulue (conversion sourcée par unites.py), ou lève UniteRefusee."""
    return v if v.unite == unite else convertir(v, unite, id=v.id)


def _exiger_pourcent(v: Valeur, role: str) -> None:
    if v.unite != "%":
        raise ValueError(f"{role} « {v.reference()} » doit être en % (reçu : « {v.unite} »)")


def ecart_relatif(a: Valeur, b: Valeur, id: str = "") -> Valeur:
    """Écart relatif en %, rapporté à la moyenne des deux : abs(a − b) ÷ ((a + b) ÷ 2) × 100. Toujours ≥ 0.

    b est d'abord converti dans l'unité de a si besoin. Moyenne nulle : « à confirmer ».
    La formule écrite n'utilise pas « | » (il casserait les tableaux markdown).
    """
    b2 = _meme_unite(b, a.unite)
    ra, rb = a.reference(), b.reference()
    formule = f"abs({ra} − {rb}) ÷ moyenne({ra}, {rb}) × 100"
    # moyenne des deux valeurs : (a + b) ÷ 2 (définition de la moyenne arithmétique)
    return calculer(lambda: abs(a.nombre - b2.nombre) / abs((a.nombre + b2.nombre) / 2) * POURCENT,
                    "%", formule, [a, b2], id=id)


def comparer(a: Valeur, b: Valeur, seuil_pct: Valeur, id: str = "") -> dict:
    """Compare deux valeurs à un seuil d'écart (en %).

    Renvoie {"ecart": Valeur, "seuil": Valeur, "depassement": True | False | None, "alerte": str}.
    depassement = écart strictement supérieur au seuil ; None si l'écart ou le seuil est « à confirmer ».
    alerte : texte français à reporter en bloc G ; vide quand tout va bien.
    """
    _exiger_pourcent(seuil_pct, "le seuil")
    ecart = ecart_relatif(a, b, id=id)
    ra, rb = a.reference(), b.reference()
    valeurs = f"{ra} = {a.texte()} et {rb} = {b.texte()}"
    seuil_txt = f"{seuil_pct.texte(marque=False)} ({'hypothèse, ' if seuil_pct.statut == HYPOTHESE else ''}source : {seuil_pct.source})"
    if ecart.nombre is None or seuil_pct.nombre is None:
        manque = [r for v, r in ((a, ra), (b, rb)) if v.nombre is None]
        raison = (", ".join(manque) + " à confirmer") if manque else (
            "seuil à confirmer" if seuil_pct.nombre is None else f"écart incalculable ({ecart.source})")
        alerte = f"Écart non vérifiable entre {valeurs} : {raison}."
        return {"ecart": ecart, "seuil": seuil_pct, "depassement": None, "alerte": alerte}
    depassement = ecart.nombre > seuil_pct.nombre
    alerte = ""
    if depassement:
        b_conv = _meme_unite(b, a.unite)
        plus_haut = ra if a.nombre > b_conv.nombre else rb
        alerte = (f"Écart de {ecart.texte(marque=False)} entre {valeurs} ({plus_haut} plus élevé), au-dessus du "
                  f"seuil de {seuil_txt}. À expliquer ou à faire confirmer par le fournisseur.")
    return {"ecart": ecart, "seuil": seuil_pct, "depassement": depassement, "alerte": alerte}


def somme(valeurs: list[Valeur], unite: str, id: str = "", source: str = "calcul") -> Valeur:
    """Somme de plusieurs valeurs, ramenées dans `unite` ; une seule entrée « à confirmer » rend la somme
    « à confirmer » (nombre None), une hypothèse la rend hypothèse."""
    valeurs = list(valeurs)
    if not valeurs:
        raise ValueError("somme : liste vide (aucune valeur à additionner)")
    converties = [_meme_unite(v, unite) for v in valeurs]
    formule = "somme(" + ", ".join(v.reference() for v in valeurs) + ")"
    resultat = calculer(lambda: sum(v.nombre for v in converties), unite, formule, converties, source=source, id=id)
    # les identifiants listés sont ceux des valeurs d'origine, pas des conversions intermédiaires
    return Valeur(resultat.nombre, resultat.unite, resultat.source, resultat.statut, resultat.formule,
                  tuple(v.reference() for v in valeurs), resultat.id)


def puissance_demandee(existante: Valeur, marge_pct: Valeur, id: str = "") -> Valeur:
    """Puissance à demander au fournisseur : existante × (1 + marge ÷ 100), dans l'unité de l'existante."""
    _exiger_pourcent(marge_pct, "la marge")
    re_, rm = existante.reference(), marge_pct.reference()
    return calculer(lambda: existante.nombre * (1 + marge_pct.nombre / POURCENT), existante.unite,
                    f"{re_} × (1 + {rm} ÷ 100)", [existante, marge_pct], id=id)

