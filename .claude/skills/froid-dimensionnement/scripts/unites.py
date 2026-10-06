"""Conversions d'unités de puissance (froid) : W, kW, kcal/h, fg/h, BTU/h, TR. Constantes sourcées.

Refuse de convertir une puissance moteur (CV, HP, ch) en puissance froid : ce sont deux grandeurs
différentes (la puissance froid dépend du fluide et du régime T0 / Tc). Unité inconnue : refusée aussi.

Usage (bibliothèque) :
    from unites import convertir, UniteRefusee
    kw = convertir(Valeur(30000, "fg/h", "dicté par Loïc", "sourcé", id="p-a"), "kW")
    kw.texte() → « 34,9 kW » (statut « calculé », formule et constante en source)

Usage (ligne de commande, pour ne jamais convertir de tête) :
    python …/unites.py 30000 fg/h kW
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from valeur import Valeur, calculer, nombre_fr  # noqa: E402

# ---------- constantes ----------
# 1 kW = 10³ W : préfixe SI « kilo » (Brochure SI du BIPM, 9e édition 2019, tableau 7).
W_PAR_KW = 1000.0
# 1 kcal_IT = 4 186,8 J (calorie « International Table », 1956) : NIST SP 811 (2008), annexe B.8.
# Donc 1 kcal/h = 4 186,8 J / 3 600 s = 1,163 W (valeur exacte).
J_PAR_KCAL_IT = 4186.8
S_PAR_H = 3600.0                                    # 1 h = 3 600 s (définition)
W_PAR_KCAL_H = J_PAR_KCAL_IT / S_PAR_H              # = 1,163 W
# 1 frigorie = 1 kcal soustraite (unité française hors SI, usage du métier ; Larousse, « frigorie »).
# Donc 1 fg/h = 1 kcal/h = 1,163 W de puissance froid.
W_PAR_FG_H = W_PAR_KCAL_H
# 1 Btu_IT = 1 055,055 852 62 J (définition « International Table ») ; NIST SP 811 (2008), annexe B.8 :
# 1 Btu_IT/h = 2,930 711 × 10⁻¹ W. Donc 1 BTU/h = 0,293 071 07 W.
J_PAR_BTU_IT = 1055.05585262
W_PAR_BTU_H = J_PAR_BTU_IT / S_PAR_H                # = 0,29307107 W
# 1 TR (« ton of refrigeration ») = 12 000 Btu_IT/h = 3,516 853 × 10³ W : NIST SP 811 (2008), annexe B.8.
BTU_H_PAR_TR = 12000.0
W_PAR_TR = BTU_H_PAR_TR * W_PAR_BTU_H               # = 3 516,85 W = 3,51685 kW

# Facteur vers le watt et texte de la source, par unité canonique.
UNITES = {
    "W": (1.0, "unité SI"),
    "kW": (W_PAR_KW, "1 kW = 1 000 W (préfixe SI)"),
    "kcal/h": (W_PAR_KCAL_H, "1 kcal/h = 1,163 W (kcal_IT = 4 186,8 J, NIST SP 811 B.8)"),
    "fg/h": (W_PAR_FG_H, "1 fg/h = 1 kcal/h = 1,163 W (frigorie = kcal soustraite ; NIST SP 811 B.8)"),
    "BTU/h": (W_PAR_BTU_H, "1 BTU/h = 0,29307107 W (Btu_IT, NIST SP 811 B.8)"),
    "TR": (W_PAR_TR, "1 TR = 12 000 BTU/h = 3,51685 kW (NIST SP 811 B.8)"),
}
# Écritures acceptées (minuscules, sans espaces) → unité canonique.
ALIAS = {
    "w": "W", "watt": "W", "watts": "W",
    "kw": "kW", "kilowatt": "kW", "kilowatts": "kW",
    "kcal/h": "kcal/h", "kcalh": "kcal/h",
    "fg/h": "fg/h", "frig/h": "fg/h", "frigorie/h": "fg/h", "frigories/h": "fg/h",
    "btu/h": "BTU/h", "btuh": "BTU/h", "btu/hr": "BTU/h",
    "tr": "TR", "rt": "TR", "tonref": "TR",
}
# Puissances moteur : jamais converties en puissance froid.
PUISSANCES_MOTEUR = {"cv", "hp", "ch", "ps", "bhp"}


class UniteRefusee(ValueError):
    """Unité inconnue, ou puissance moteur (CV, HP, ch) présentée comme une puissance froid."""


def canonique(unite: str) -> str:
    """« KW », « btu/h », « Frigories/h » → « kW », « BTU/h », « fg/h » ; sinon UniteRefusee."""
    cle = (unite or "").strip().lower().replace(" ", "")
    if cle in PUISSANCES_MOTEUR:
        raise UniteRefusee(
            f"« {unite} » est une puissance moteur (puissance absorbée par le compresseur), pas une puissance "
            "frigorifique : conversion refusée. La puissance froid dépend du fluide et du régime (T0, Tc) ; "
            "il faut la référence du compresseur ou le volume balayé de sa plaque. Question à poser à Loïc.")
    if cle not in ALIAS:
        raise UniteRefusee(f"unité inconnue : « {unite} » ; unités de puissance acceptées : {', '.join(UNITES)}")
    return ALIAS[cle]


def convertir(v: Valeur, vers: str, id: str = "") -> Valeur:
    """Convertit une Valeur de puissance vers l'unité `vers`. Même unité : renvoie `v` tel quel.

    Le résultat est un calcul : statut propagé (sourcé → calculé, hypothèse reste hypothèse, à confirmer
    reste à confirmer sans nombre), formule et constante écrites en source.
    """
    de, a = canonique(v.unite), canonique(vers)
    if de == a:
        return v
    facteur = UNITES[de][0] / UNITES[a][0]
    constantes = " ; ".join(UNITES[u][1] for u in (de, a) if u != "W")
    affiche = nombre_fr(facteur, 10).rstrip("0").rstrip(",")
    formule = f"{v.reference()} × {affiche} ({de} → {a})"
    return calculer(lambda: v.nombre * facteur, a, formule, [v], source=f"conversion d'unités : {constantes}", id=id)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) != 4:
        sys.exit("usage : python unites.py <nombre> <unité de départ> <unité d'arrivée>   ex. 30000 fg/h kW")
    nombre = float(sys.argv[1].replace(",", "."))
    try:
        r = convertir(Valeur(nombre, sys.argv[2], "valeur donnée en argument", "sourcé", id="entrée"), sys.argv[3])
    except UniteRefusee as exc:
        sys.exit(f"refusé : {exc}")
    print(f"{r.texte()}   ({r.source_texte()})")


if __name__ == "__main__":
    main()
