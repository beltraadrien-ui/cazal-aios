"""Une donnée sourcée : la classe Valeur, la propagation des statuts et le rendu français des tableaux.

Principe (recherche du 2026-10-02, §4.1) : Claude écrit des entrées sourcées, les scripts rendent des
valeurs sourcées. Chaque nombre circule avec son unité, sa source et son statut ; un résultat de calcul
n'est jamais plus sûr que sa plus faible entrée.

Usage (bibliothèque, importée par les autres scripts du skill) :
    from valeur import Valeur, calculer, combiner, en_json, depuis_json, a_confirmer

    vb = Valeur(73.6, "m³/h", "plaque, photo p05-2", "sourcé", id="c1-volume-balaye")
    lam = Valeur(0.75, "", "table de λ, methodes/puissance-existante.md", "hypothèse", id="c1-lambda")
    utile = calculer(lambda: vb.nombre * lam.nombre, "m³/h", "c1-volume-balaye × c1-lambda", [vb, lam])
    utile.texte()         → « 55,20 m³/h (hyp.) »
    utile.source_texte()  → « calcul · formule : c1-volume-balaye × c1-lambda · entrées : c1-volume-balaye, c1-lambda »

Statuts, du plus sûr au moins sûr : « sourcé » > « calculé » > « hypothèse » > « à confirmer ».
« à confirmer » ⇔ nombre absent (None) : on n'écrit jamais un faux nombre.
"""
from __future__ import annotations

import json
import math
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Iterable

SOURCE = "sourcé"
CALCULE = "calculé"
HYPOTHESE = "hypothèse"
A_CONFIRMER = "à confirmer"
STATUTS = (SOURCE, CALCULE, HYPOTHESE, A_CONFIRMER)          # du plus sûr au moins sûr
RANG = {s: i for i, s in enumerate(STATUTS)}                  # 0 = le plus sûr

# Marque affichée après le nombre dans les tableaux (« sourcé » et « calculé » : rien, la colonne Source suffit).
MARQUES = {SOURCE: "", CALCULE: "", HYPOTHESE: " (hyp.)"}

# Espace insécable (U+00A0) : séparateur de milliers et espace avant l'unité (typographie française).
# Choisie plutôt que l'espace fine (U+202F) car présente dans toutes les polices, y compris celles des PDF.
ESPACE = " "

# Décimales affichées par unité : convention de lisibilité (pas une donnée physique). Défaut : 2.
DECIMALES = {
    "W": 0, "kW": 1, "MW": 2,
    "kcal/h": 0, "fg/h": 0, "BTU/h": 0, "TR": 2,
    "%": 1, "°C": 1, "K": 1,
    "bar": 2, "kPa": 0, "MPa": 2,
    "m³/h": 2, "m3/h": 2, "m³": 1, "m3": 1, "m²": 1, "m2": 1, "m": 2,
    "kg": 1, "t": 2, "tCO2e": 2, "PRP": 0, "kgCO2e/kg": 0,
    "kJ/kg": 1, "kg/m³": 2, "kg/m3": 2,
    "Hz": 0, "tr/min": 0, "A": 1, "V": 0,
}
DECIMALES_DEFAUT = 2

CLES_OBLIGATOIRES = ("nombre", "unite", "source", "statut")
CLES_VALEUR = ("id",) + CLES_OBLIGATOIRES + ("formule", "entrees")


def _sans_accents(texte: str) -> str:
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().strip().lower()


_ALIAS_STATUTS = {_sans_accents(s): s for s in STATUTS}


def normaliser_statut(statut: str) -> str:
    """« Hypothese », « sourcé », « a confirmer » → forme canonique ; statut inconnu → ValueError."""
    if not isinstance(statut, str) or _sans_accents(statut) not in _ALIAS_STATUTS:
        raise ValueError(f"statut inconnu : {statut!r} ; statuts possibles : {', '.join(STATUTS)}")
    return _ALIAS_STATUTS[_sans_accents(statut)]


@dataclass(frozen=True)
class Valeur:
    """Un nombre avec son unité, sa source et son statut. Immuable.

    nombre  : float, ou None si inconnu (le statut est alors obligatoirement « à confirmer »)
    unite   : « kW », « °C », « m³/h », « % », « » pour un nombre sans dimension
    source  : obligatoire, ex. « plaque, photo p11-3 », « rapport p. 10 », « dicté par Loïc le … »,
              « hypothèse en attente de la réponse de Loïc », « web : <lien> », « calcul »
    statut  : « sourcé » | « calculé » | « hypothèse » | « à confirmer »
    formule : pour un calcul, la formule avec les identifiants des entrées
    entrees : identifiants des valeurs utilisées par le calcul
    id      : identifiant facultatif, repris dans les formules et les colonnes Source
    """
    nombre: float | None
    unite: str
    source: str
    statut: str
    formule: str = ""
    entrees: tuple[str, ...] = ()
    id: str = ""

    def __post_init__(self) -> None:
        nom = f"Valeur « {self.id} »" if isinstance(self.id, str) and self.id else "Valeur"
        n = self.nombre
        if n is not None:
            if isinstance(n, bool) or not isinstance(n, (int, float)):
                raise ValueError(f"{nom} : nombre invalide {n!r} (attendu : un nombre ou None)")
            if not math.isfinite(n):
                raise ValueError(f"{nom} : nombre non fini ({n!r}) ; un calcul raté s'écrit « à confirmer », nombre None")
            object.__setattr__(self, "nombre", float(n))
        if not isinstance(self.unite, str):
            raise ValueError(f"{nom} : unité invalide {self.unite!r} (attendu : texte, « » si sans dimension)")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError(f"{nom} : source vide ; chaque chiffre porte sa source (règle de fiabilité n° 1)")
        try:
            statut = normaliser_statut(self.statut)
        except ValueError as exc:
            raise ValueError(f"{nom} : {exc}") from None
        object.__setattr__(self, "statut", statut)
        if (n is None) != (statut == A_CONFIRMER):
            raise ValueError(f"{nom} : nombre {n!r} incompatible avec le statut « {statut} » "
                             "(nombre absent ⇔ « à confirmer » ; une lecture douteuse s'écrit « hypothèse »)")
        entrees = self.entrees
        if isinstance(entrees, str) or not all(isinstance(e, str) for e in entrees):
            raise ValueError(f"{nom} : entrées invalides {entrees!r} (attendu : liste d'identifiants)")
        object.__setattr__(self, "entrees", tuple(entrees))
        if not isinstance(self.formule, str) or not isinstance(self.id, str):
            raise ValueError(f"{nom} : formule et id doivent être du texte")

    # ---------- rendu pour les tableaux ----------
    def texte(self, decimales: int | None = None, marque: bool = True) -> str:
        """« 35,2 kW », « 35,2 kW (hyp.) » ou « à confirmer »."""
        if self.nombre is None:
            return A_CONFIRMER
        d = DECIMALES.get(self.unite, DECIMALES_DEFAUT) if decimales is None else decimales
        t = nombre_fr(self.nombre, d) + (ESPACE + self.unite if self.unite else "")
        return t + (MARQUES[self.statut] if marque else "")

    def source_texte(self) -> str:
        """Colonne « Source » : la source, puis pour un calcul la formule et les identifiants des entrées."""
        parties = [self.source]
        if self.formule:
            parties.append(f"formule : {self.formule}")
        if self.entrees:
            parties.append("entrées : " + ", ".join(self.entrees))
        return " · ".join(parties)

    def reference(self) -> str:
        """Ce qui désigne cette valeur dans la formule d'un calcul : son id, sinon son rendu."""
        return self.id or self.texte()

    # ---------- JSON (2-entrees.json, 2-resultats.json) ----------
    def vers_dict(self) -> dict:
        return {"id": self.id, "nombre": self.nombre, "unite": self.unite, "source": self.source,
                "statut": self.statut, "formule": self.formule, "entrees": list(self.entrees)}

    @classmethod
    def depuis_dict(cls, d: dict) -> "Valeur":
        if not isinstance(d, dict):
            raise ValueError(f"Valeur attendue sous forme d'objet JSON, reçu : {d!r}")
        nom = f"Valeur « {d.get('id')} »" if d.get("id") else "Valeur"
        manquantes = [k for k in CLES_OBLIGATOIRES if k not in d]
        if manquantes:
            raise ValueError(f"{nom} : clé(s) manquante(s) {', '.join(manquantes)} ; clés attendues : {', '.join(CLES_VALEUR)}")
        inconnues = [k for k in d if k not in CLES_VALEUR]
        if inconnues:
            raise ValueError(f"{nom} : clé(s) inconnue(s) {', '.join(inconnues)} ; clés attendues : {', '.join(CLES_VALEUR)}")
        entrees = d.get("entrees", ())
        if isinstance(entrees, list):
            entrees = tuple(entrees)
        return cls(nombre=d["nombre"], unite=d["unite"], source=d["source"], statut=d["statut"],
                   formule=d.get("formule", ""), entrees=entrees, id=d.get("id", ""))


def nombre_fr(x: float, decimales: int = DECIMALES_DEFAUT) -> str:
    """1234.5 → « 1 234,5 » (espace insécable entre les milliers, virgule décimale, arrondi au plus proche)."""
    q = Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
    if q == 0:
        q = abs(q)                                   # pas de « -0,0 »
    signe = "-" if q < 0 else ""
    entier, _, frac = f"{abs(q):f}".partition(".")
    groupes = []
    while len(entier) > 3:
        groupes.insert(0, entier[-3:])
        entier = entier[:-3]
    groupes.insert(0, entier)
    return signe + ESPACE.join(groupes) + ("," + frac if frac else "")


def a_confirmer(unite: str, source: str, id: str = "") -> Valeur:
    """Une donnée absente ou illisible : pas de nombre, la source dit pourquoi (ex. « absent de la plaque »)."""
    return Valeur(None, unite, source, A_CONFIRMER, id=id)


def combiner(statuts: Iterable[str]) -> str:
    """Le statut le plus faible de la liste (sourcé > calculé > hypothèse > à confirmer)."""
    liste = [normaliser_statut(s) for s in statuts]
    if not liste:
        raise ValueError("combiner : aucun statut fourni")
    return max(liste, key=RANG.__getitem__)


def calculer(nombre: float | None | Callable[[], float], unite: str, formule: str, entrees: list[Valeur],
             source: str = "calcul", id: str = "") -> Valeur:
    """Résultat d'un calcul, avec propagation des statuts.

    statut = le plus faible de (« calculé », statuts des entrées). Si une entrée n'a pas de nombre, le
    résultat est « à confirmer », nombre None, et la source dit quelle entrée bloque.
    `nombre` peut être une fonction sans argument (lambda) : elle n'est appelée que si toutes les entrées
    ont un nombre, ce qui évite de calculer avec None. Une division par zéro, une erreur de domaine
    (ValueError, ex. hors plage) ou un résultat non fini donnent « à confirmer » avec la raison en source.
    """
    entrees = list(entrees)
    for e in entrees:
        if not isinstance(e, Valeur):
            raise TypeError(f"calculer : entrée {e!r} n'est pas une Valeur")
    refs = tuple(e.reference() for e in entrees)
    statut = combiner([e.statut for e in entrees] + [CALCULE])
    bloquantes = [r for e, r in zip(entrees, refs) if e.nombre is None]
    if bloquantes:
        return Valeur(None, unite, f"{source} ; bloqué par : {', '.join(bloquantes)} (à confirmer)",
                      A_CONFIRMER, formule, refs, id)
    try:
        n = nombre() if callable(nombre) else nombre
    except (ArithmeticError, ValueError) as exc:     # division par zéro, dépassement, domaine, hors plage
        return Valeur(None, unite, f"{source} ; calcul impossible : {exc}", A_CONFIRMER, formule, refs, id)
    if n is None or isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n):
        return Valeur(None, unite, f"{source} ; résultat non numérique ou non fini : {n!r}",
                      A_CONFIRMER, formule, refs, id)
    return Valeur(float(n), unite, source, statut, formule, refs, id)


# ---------- fichiers JSON contenant des Valeur n'importe où ----------
def _par_defaut(obj: Any) -> Any:
    if isinstance(obj, Valeur):
        return obj.vers_dict()
    raise TypeError(f"non sérialisable en JSON : {obj!r}")


def _crochet(d: dict) -> Any:
    """Un objet JSON qui ressemble à une Valeur (« nombre » plus « unite », « source » ou « statut ») redevient
    une Valeur ; s'il lui manque une clé ou s'il en porte une inconnue (faute de frappe), c'est une erreur."""
    if "nombre" in d and any(k in d for k in ("unite", "source", "statut")):
        return Valeur.depuis_dict(d)
    return d


def en_json(obj: Any, indent: int = 1) -> str:
    """Sérialise une structure (dict, list…) contenant des Valeur."""
    return json.dumps(obj, default=_par_defaut, ensure_ascii=False, indent=indent)


def depuis_json(texte: str) -> Any:
    """Relit une structure écrite par en_json (ou par Claude) : chaque objet-Valeur redevient une Valeur."""
    return json.loads(texte, object_hook=_crochet)
