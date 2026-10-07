"""Ramène dans `plan.json` ce que le frigoriste a modifié à la souris dans `plan.drawio` (draw.io Desktop).

Ce qui est repris (tout relu par `drawio.lire`, reconverti en mètres) :
- positions et rotations des équipements ;
- tracés des lignes (points, y compris les coudes ajoutés ou retirés) ;
- portes (charnière, orientation, sens) et fenêtres (centre, orientation), portes de chambres comprises ;
- nouvelles arêtes dessinées dans un calque réseau (Froid – cuivres, Électricité, Clim – cuivres, calques libres) :
  nouvelles lignes `L-nouveau-N`, type déduit du calque et du style, `de` / `a` = équipement ou chambre à 0,15 m
  au plus de l'extrémité, sinon `null` + question.
Ce qui n'est PAS repris : murs, chambres, pièces, cotes (le relevé fait foi : avertissement s'ils diffèrent),
étiquettes, éléments supprimés (avertissement : à supprimer dans plan.json si c'est voulu).

Recalage : si TOUS les murs relus sont décalés du même vecteur (plus de 1 cm), c'est que tout le dessin a été
déplacé d'un bloc (l'origine du cartouche ne suit pas) : le vecteur inverse est appliqué à tout ce qui est relu.

Avant d'écrire : copie `versions/plan.json.avant-import-AAAAMMJJ-HHMMSS`. Ensuite : generer.py puis verifier_plan.py.

Usage (depuis la racine du dépôt) :
    python .claude/skills/froid-plan-2d/scripts/importer_drawio.py <dossier_plan> [--apercu]
Code de retour : 0 (import fait ou rien à importer), 1 (fichier illisible), 2 (fichier manquant).
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drawio  # noqa: E402
import geometrie as geo  # noqa: E402
import modele as mod  # noqa: E402
from echelle import nombre_fr  # noqa: E402

SEUIL_DEPLACEMENT_M = 0.005       # en dessous : bruit d'arrondi du XML (0,01 px), rien à importer
SEUIL_RECALAGE_M = 0.01           # décalage d'ensemble des murs au-delà duquel on recale
ACCORD_RECALAGE_M = 0.01          # les murs doivent tous être décalés du même vecteur à 1 cm près
SEUIL_ANGLE_DEG = 0.5
DECIMALES = 3                     # positions écrites au mm


class ErreurImport(RuntimeError):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


def _pt(p) -> str:
    return f"({nombre_fr(p[0])} ; {nombre_fr(p[1])})"


def _r(v: float) -> float:
    v = round(float(v), DECIMALES)
    return int(v) if v == int(v) else v


def _rp(p) -> list:
    return [_r(p[0]), _r(p[1])]


def _angle(a: float) -> float:
    a = geo.normaliser_angle(a)
    return int(round(a)) if abs(a - round(a)) < 1e-6 else round(a, 2)


def _ecart_angle(a: float, b: float, modulo: float = 360.0) -> float:
    d = abs(geo.normaliser_angle(a) - geo.normaliser_angle(b)) % modulo
    return min(d, modulo - d)


def vecteur_recalage(plan: mod.Plan, lecture) -> tuple[tuple[float, float], list[str]]:
    """Décalage commun de tous les murs relus (m), ou (0, 0) ; + avertissements sur les murs."""
    decalages, avert = [], []
    for m in plan.murs:
        e = lecture.elements.get(m["id"])
        if not e or e.get("type") != "mur" or not e.get("points_m"):
            avert.append(f"Mur {m['id']} absent du dessin (non réimporté : le relevé fait foi).")
            continue
        a1, a2 = mod.axe_mur(m)
        p1, p2 = e["points_m"]
        if geo.distance(a1, p1) + geo.distance(a2, p2) > geo.distance(a1, p2) + geo.distance(a2, p1):
            p1, p2 = p2, p1
        decalages.append((m["id"], ((p1[0] - a1[0] + p2[0] - a2[0]) / 2.0, (p1[1] - a1[1] + p2[1] - a2[1]) / 2.0),
                          abs(geo.distance(p1, p2) - geo.distance(a1, a2))))
    if not decalages:
        return (0.0, 0.0), avert
    vx = sum(d[1][0] for d in decalages) / len(decalages)
    vy = sum(d[1][1] for d in decalages) / len(decalages)
    accord = all(geo.distance(d[1], (vx, vy)) <= ACCORD_RECALAGE_M and d[2] <= ACCORD_RECALAGE_M for d in decalages)
    if accord and math.hypot(vx, vy) > SEUIL_RECALAGE_M:
        return (vx, vy), avert
    for mid, d, dl in decalages:
        if math.hypot(*d) > mod.TOLERANCE_COTE or dl > mod.TOLERANCE_COTE:
            avert.append(f"Mur {mid} modifié dans le dessin (décalé de {nombre_fr(math.hypot(*d))} m) : NON réimporté, "
                         "le relevé fait foi ; corriger plan.json (cotes du télémètre) si le mur est vraiment faux.")
    return (0.0, 0.0), avert


def deduire_type(e: dict, plan: mod.Plan) -> tuple[str | None, str | None]:
    """(type, question) d'une arête nouvelle selon son calque et son style."""
    if e.get("genre"):
        return e["genre"], None
    st, calque = e.get("style") or {}, e.get("calque")
    couleur = (st.get("strokeColor") or "").upper()
    lien = st.get("shape") == "link"
    pointille = st.get("dashed") == "1"
    epais = float(st.get("strokeWidth") or 1) >= 3
    if calque == "froid_cuivres":
        if couleur == "#C62828":
            return "liquide", None
        if couleur == "#00ACC1" or pointille:
            return "condensats", None
        if lien or couleur == "#1565C0":
            return "aspiration", None
        return "aspiration", "type déduit par défaut (aspiration) : aspiration, liquide ou condensats ?"
    if calque == "electricite":
        return ("chemin_cables", None) if (epais or pointille) else ("cable", None)
    if calque == "clim_cuivres":
        return ("clim_gaz", None) if lien else ("clim_liquide", None)
    if calque and plan.calque_libre(calque):
        return calque, None
    return None, None


def objet_proche(point, plan: mod.Plan, prefere: str | None = None) -> tuple[str | None, float | None]:
    """Équipement ou chambre à 0,15 m au plus du point (le préféré d'abord s'il convient)."""
    if prefere:
        d = plan.distance_a_objet(point, prefere)
        if d is not None and d <= mod.TOLERANCE_EXTREMITE:
            return prefere, d
    meilleur = (None, None)
    for col in ("equipements", "chambres_froides"):
        for o in getattr(plan, col):
            d = plan.distance_a_objet(point, o["id"])
            if d is not None and d <= mod.TOLERANCE_EXTREMITE and (meilleur[1] is None or d < meilleur[1]):
                meilleur = (o["id"], d)
    return meilleur


def calculer_import(dossier: Path) -> dict:
    """Calcule le nouveau plan.json (sans rien écrire) : {nouveau, changements, avertissements, questions,
    recalage}."""
    chemin_json, chemin_drawio = dossier / "plan.json", dossier / "plan.drawio"
    for c in (chemin_json, chemin_drawio):
        if not c.is_file():
            raise ErreurImport(f"{c.name} introuvable dans {dossier}.", code=2)
    try:
        brut = json.loads(chemin_json.read_text(encoding="utf-8-sig"))
        plan = mod.depuis_dict(brut, chemin_json)
        lecture = drawio.lire(chemin_drawio)
    except (json.JSONDecodeError, mod.ErreurModele, drawio.ErreurLecture) as exc:
        raise ErreurImport(f"Lecture impossible : {exc}") from exc
    if lecture.echelle is None:
        raise ErreurImport("Échelle illisible dans le cartouche de plan.drawio : import impossible ("
                           + " ; ".join(lecture.avertissements) + ").")
    nouveau = copy.deepcopy(brut)
    changements, avert, questions = [], [], []
    v, av_murs = vecteur_recalage(plan, lecture)
    avert += av_murs
    if v != (0.0, 0.0):
        avert.append(f"Tout le dessin a été déplacé d'un bloc de {_pt(v)} m : recalé (vecteur inverse appliqué à "
                     "tout ce qui est relu).")

    def corr(p):
        return (p[0] - v[0], p[1] - v[1])

    def relu(ident, type_):
        e = lecture.elements.get(ident)
        return e if e and e.get("type") == type_ else None

    # équipements
    for q in nouveau.get("equipements") or []:
        e = relu(q.get("id"), "equipement")
        if e is None:
            avert.append(f"Équipement {q.get('id')} absent du dessin : non supprimé de plan.json (le supprimer à la "
                         "main si c'est voulu).")
            continue
        norm = plan.equipement(q["id"])
        pos = corr(e["centre_m"])
        if geo.distance(pos, norm["position"]) > SEUIL_DEPLACEMENT_M:
            changements.append(f"{q['id']} déplacé de {_pt(norm['position'])} à {_pt(pos)} m")
            q["position"] = _rp(pos)
        if _ecart_angle(e["rotation"], norm.get("rotation", 0.0)) > SEUIL_ANGLE_DEG:
            changements.append(f"{q['id']} tourné de {nombre_fr(norm.get('rotation', 0.0), 0)}° à "
                               f"{nombre_fr(e['rotation'], 0)}°")
            q["rotation"] = _angle(e["rotation"])
        dims = e.get("dimensions_m")
        if dims and (abs(dims[0] - norm["dimensions"][0]) > mod.TOLERANCE_COTE
                     or abs(dims[1] - norm["dimensions"][1]) > mod.TOLERANCE_COTE):
            avert.append(f"{q['id']} redimensionné dans le dessin ({nombre_fr(dims[0])} × {nombre_fr(dims[1])} m) : "
                         "dimensions NON réimportées (les écrire dans plan.json si elles sont mesurées).")

    # lignes existantes
    ids_lignes = set()
    for l in nouveau.get("lignes") or []:
        ids_lignes.add(l.get("id"))
        e = relu(l.get("id"), "ligne")
        if e is None:
            avert.append(f"Ligne {l.get('id')} absente du dessin : non supprimée de plan.json (la supprimer à la main "
                         "si c'est voulu).")
            continue
        anciens = [tuple(p) for p in l.get("points") or []]
        relus = [corr(p) for p in e["points_m"]]
        if len(relus) != len(anciens) or any(geo.distance(a, b) > SEUIL_DEPLACEMENT_M for a, b in zip(anciens, relus)):
            if len(relus) == len(anciens):      # points inchangés gardés tels quels (pas de bruit d'arrondi)
                garde = [list(a) if geo.distance(a, b) <= SEUIL_DEPLACEMENT_M else _rp(b) for a, b in zip(anciens, relus)]
            else:
                garde = [_rp(b) for b in relus]
            changements.append(f"{l['id']} : tracé modifié ({len(anciens)} → {len(relus)} points)")
            l["points"] = garde
        if e.get("avertissement"):
            avert.append(f"{l['id']} : {e['avertissement']}.")

    # portes et fenêtres
    def maj_porte(p: dict, e: dict, nom: str):
        pos = corr(e["position_m"])
        if geo.distance(pos, p["position"]) > SEUIL_DEPLACEMENT_M:
            changements.append(f"{nom} : charnière déplacée de {_pt(p['position'])} à {_pt(pos)} m")
            p["position"] = _rp(pos)
        if _ecart_angle(e["orientation"], p.get("orientation", 0)) > SEUIL_ANGLE_DEG:
            changements.append(f"{nom} : orientation {nombre_fr(p.get('orientation', 0), 0)}° → "
                               f"{nombre_fr(e['orientation'], 0)}°")
            p["orientation"] = _angle(e["orientation"])
        if e.get("sens") and e["sens"] != p.get("sens", "gauche"):
            changements.append(f"{nom} : sens {p.get('sens', 'gauche')} → {e['sens']}")
            p["sens"] = e["sens"]

    for p in nouveau.get("portes") or []:
        e = relu(p.get("id"), "porte")
        if e is None:
            avert.append(f"Porte {p.get('id')} absente du dessin : non supprimée de plan.json.")
            continue
        maj_porte(p, e, f"Porte {p['id']}")
    for c in nouveau.get("chambres_froides") or []:
        if isinstance(c.get("porte"), dict):
            e = relu(f"{c['id']}-porte", "porte")
            if e is not None:
                maj_porte(c["porte"], e, f"Porte de {c['id']}")
        e = relu(c.get("id"), "chambre")
        if e is not None:
            attendu = mod.rectangle_chambre(plan.chambre(c["id"]))
            trouve = geo.boite_englobante([corr(p) for p in e["points_m"]])
            if any(abs(a - b) > mod.TOLERANCE_COTE for a, b in zip(attendu, trouve)):
                avert.append(f"Chambre {c['id']} modifiée dans le dessin : NON réimportée (le relevé fait foi).")
    for f in nouveau.get("fenetres") or []:
        e = relu(f.get("id"), "fenetre")
        if e is None:
            avert.append(f"Fenêtre {f.get('id')} absente du dessin : non supprimée de plan.json.")
            continue
        pos = corr(e["centre_m"])
        if geo.distance(pos, f["position"]) > SEUIL_DEPLACEMENT_M:
            changements.append(f"Fenêtre {f['id']} : centre déplacé de {_pt(f['position'])} à {_pt(pos)} m")
            f["position"] = _rp(pos)
        if _ecart_angle(e["orientation"], f.get("orientation", 0), 180.0) > SEUIL_ANGLE_DEG:
            changements.append(f"Fenêtre {f['id']} : orientation → {nombre_fr(e['orientation'], 0)}°")
            f["orientation"] = _angle(e["orientation"])

    # nouvelles lignes
    reseaux = set(mod.CALQUES_RESEAUX) | {q["cle"] for q in plan.calques_libres}
    pris = {x["id"] for col in mod.COLLECTIONS for x in getattr(plan, col)}
    n = 0
    plan_pour_proximite = mod.depuis_dict(nouveau)       # équipements à leur position importée
    for e in lecture.elements.values():
        if e.get("type") != "ligne" or e["id"] in ids_lignes or e.get("calque") not in reseaux:
            continue
        if not e.get("points_m") or len(e["points_m"]) < 2:
            continue
        type_, question = deduire_type(e, plan)
        if type_ is None:
            avert.append(f"Arête {e['id']} du calque {e.get('calque')} : type indéterminé, non importée.")
            continue
        n += 1
        while f"L-nouveau-{n}" in pris:
            n += 1
        lid = f"L-nouveau-{n}"
        pris.add(lid)
        pts = [corr(p) for p in e["points_m"]]
        de, _ = objet_proche(pts[0], plan_pour_proximite, e.get("de"))
        a, _ = objet_proche(pts[-1], plan_pour_proximite, e.get("a"))
        ligne = {"id": lid, "type": type_, "calque": e["calque"], "de": de, "a": a, "points": [_rp(p) for p in pts],
                 "diametre": "à définir", "source": "drawio"}
        nouveau.setdefault("lignes", []).append(ligne)
        changements.append(f"{lid} : nouvelle ligne {type_} ({len(pts)} points, {de or '?'} → {a or '?'}) "
                           f"dessinée dans draw.io (cellule {e['id']})")
        if question:
            questions.append(f"{lid} : {question}")
        for cle, bout, p in (("de", "départ", pts[0]), ("a", "arrivée", pts[-1])):
            if ligne[cle] is None and type_ != "chemin_cables":
                questions.append(f"{lid} : {bout} libre en {_pt(p)} m : à quel équipement la relier ?")

    # cotes et étiquettes : pas de réimport, mais on signale une cote retouchée
    for c in plan.cotes:
        e = relu(c["id"], "cote")
        if e and e.get("valeur_m") is not None and abs(e["valeur_m"] - c["valeur"]) > 1e-6:
            avert.append(f"Cote {c['id']} modifiée dans le dessin (« {e.get('texte')} ») : NON réimportée ; une cote "
                         "vient du télémètre, la corriger dans plan.json.")
    try:
        problemes = mod.depuis_dict(nouveau).valider()
    except mod.ErreurModele as exc:
        problemes = [str(exc)]
    return {"nouveau": nouveau, "changements": changements, "avertissements": avert, "questions": questions,
            "recalage": v, "problemes": problemes}


def importer(dossier_plan, apercu: bool = False, maintenant: datetime | None = None) -> dict:
    """Importe les modifications de plan.drawio dans plan.json (sauf `apercu`). Renvoie le résultat de
    `calculer_import` + {ecrit, sauvegarde}."""
    dossier = Path(dossier_plan)
    res = calculer_import(dossier)
    res.update(ecrit=False, sauvegarde=None)
    if apercu or not res["changements"]:
        return res
    maintenant = maintenant or datetime.now()
    versions = dossier / "versions"
    versions.mkdir(exist_ok=True)
    sauvegarde = versions / f"plan.json.avant-import-{maintenant:%Y%m%d-%H%M%S}"
    k = 1
    while sauvegarde.exists():
        k += 1
        sauvegarde = versions / f"plan.json.avant-import-{maintenant:%Y%m%d-%H%M%S}-{k}"
    shutil.copyfile(dossier / "plan.json", sauvegarde)
    (dossier / "plan.json").write_text(json.dumps(res["nouveau"], ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8", newline="\n")
    res.update(ecrit=True, sauvegarde=sauvegarde)
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ramène dans plan.json les modifications faites dans plan.drawio.")
    ap.add_argument("dossier_plan")
    ap.add_argument("--apercu", action="store_true", help="afficher les changements sans écrire plan.json")
    a = ap.parse_args(argv)
    try:
        r = importer(a.dossier_plan, apercu=a.apercu)
    except ErreurImport as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return exc.code
    if r["changements"]:
        print(("Aperçu (rien n'est écrit) : " if a.apercu else "Changements importés : ") + f"{len(r['changements'])}")
        for c in r["changements"]:
            print(f"  - {c}")
    else:
        print("Aucun changement à importer : plan.json est déjà à jour avec plan.drawio.")
    for m in r["avertissements"]:
        print(f"Avertissement : {m}")
    for q in r["questions"]:
        print(f"Question : {q}")
    if r["changements"] and r["problemes"]:
        print("À corriger avant de regénérer (plan.json après import) :")
        for p in r["problemes"]:
            print(f"  - {p}")
    if r["ecrit"]:
        print(f"plan.json mis à jour ; ancienne version : {r['sauvegarde']}")
        print("Suite : generer.py puis verifier_plan.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
