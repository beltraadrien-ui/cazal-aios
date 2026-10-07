"""Génère le plan 2D d'un dossier : `plan.json` → `plan.drawio`, `plan.md` + `plan.html`, `plan.pdf` + `plan.png`,
`plan-base.json`, copie `versions/plan-vN.*`, ligne datée dans `journal.md`.

Chaîne : charger → valider (erreurs → code 1, rien n'est écrit) → métré (A2) → croisements + recouvrements (A2),
regroupés (≤ 0,50 m, repères G) et injectés dans le modèle (un cercle par groupe) → échelle normalisée (A1, boîte englobante croisements compris) → `drawio.ecrire` (page
« Plan » + page « Métré » : tableaux de métré et des croisements) → rendu PDF/PNG mesuré (`rendu.py`) → `plan.md`
(identité, comment vérifier l'échelle, cotes, hauteurs, métré, croisements, calques, questions ouvertes, journal)
→ `plan.html` (`shared/rendu_html.py`) → `plan-base.json` (contrat du Lot 6 : un point (x, y) du modèle en m
tombe sur la page en `origine_mm + (x, y) × 1000 / S` mm) → versions → journal.

Usage (depuis la racine du dépôt) :
    python .claude/skills/froid-plan-2d/scripts/generer.py <dossier_plan> [--sans-rendu] [--ouvrir]
Code de retour : 0 (plan généré), 1 (modèle invalide, échelle impossible ou rendu en échec).
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import croisements as crx  # noqa: E402
import drawio  # noqa: E402
import geometrie as geo  # noqa: E402
import metre as mtr  # noqa: E402
import modele as mod  # noqa: E402
import rendu  # noqa: E402
from echelle import ErreurEchelle, PT_PAR_MM, choisir_echelle, nombre_fr  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]          # racine du dépôt (…/.claude/skills/<skill>/scripts/)
HYP = " (hyp.)"
TITRE_TABLEAU_CROISEMENTS = "Croisements entre réseaux"
ENTETES_RESEAUX = ["Réseau", "Ligne", f"De {mtr.FLECHE} À", "Type", "En plan (m)", "Dans le chemin (m)", "Vertical (m)",
                   "Réserve (m)", "Total (m)", "Diamètre"]
ALIGN_RESEAUX = ["g", "g", "g", "g", "d", "d", "d", "d", "d", "g"]
TITRES_SECTIONS = {
    "reseaux": "Métré par réseau", "diametres": "Métré par diamètre", "croisements": "Croisements et recouvrements",
}


class ErreurGeneration(RuntimeError):
    """Plan non généré : message en français."""


# ======================================================================
# Outils
# ======================================================================
def _pt(p) -> str:
    return f"({nombre_fr(p[0])} ; {nombre_fr(p[1])})"


def _table_md(entetes: list[str], rangs: list[list[str]], aligne: list[str] | None = None,
              gras: set[int] | None = None) -> str:
    aligne = aligne or ["g"] * len(entetes)
    gras = gras or set()

    def rang(cellules, en_gras=False):
        cs = [str(c).replace("|", "\\|").replace("\n", " ") for c in cellules]
        if en_gras:
            cs = [f"**{c}**" if c else c for c in cs]
        return "| " + " | ".join(cs) + " |"
    lignes = [rang(entetes), "|" + "|".join("---:" if a == "d" else "---" for a in aligne) + "|"]
    lignes += [rang(r, i in gras) for i, r in enumerate(rangs)]
    return "\n".join(lignes)


def statuts_hauteurs(m: mtr.Metre) -> dict[str, str]:
    return {h["cle"]: h["statut"] for h in m.hypotheses}


def ligne_en_hypothese(l: dict, statuts: dict[str, str]) -> tuple[bool, bool]:
    """(vertical en hypothèse, réserve en hypothèse) d'une ligne métrée : une hauteur prise dans la table
    `hauteurs` non validée par le frigoriste (question 13) rend le métré vertical « hypothèse »."""
    vertical = any(o.startswith("hauteurs.") and statuts.get(o.split(".", 1)[1]) == mtr.HYPOTHESE
                   for o in (l.get("origines_hauteurs") or {}).values())
    reserve = l["type"] == "cable" and statuts.get("reserve_cable") == mtr.HYPOTHESE
    return vertical, reserve


def tableau_reseaux_md(m: mtr.Metre) -> str:
    """« Métré par réseau » (mêmes colonnes que la page Métré du draw.io) ; « (hyp.) » après chaque valeur qui
    dépend d'une hauteur non validée."""
    statuts = statuts_hauteurs(m)
    rangs, gras = [], set()
    for r in m.par_reseau.values():
        hv_res = hr_res = False
        for lid in r["lignes"]:
            l = m.lignes[lid]
            hv, hr = ligne_en_hypothese(l, statuts)
            hv_res, hr_res = hv_res or hv, hr_res or hr
            rangs.append([r["nom"], lid, f"{l['de'] or mtr.TIRET_VIDE} {mtr.FLECHE} {l['a'] or mtr.TIRET_VIDE}",
                          l["libelle_type"], mtr.nombre_fr(l["plan_m"]), mtr.nombre_fr(l["chemin_m"]),
                          mtr.nombre_fr(l["vertical_m"]) + (HYP if hv else ""),
                          mtr.nombre_fr(l["reserve_m"]) + (HYP if hr else ""),
                          mtr.nombre_fr(l["total_m"]) + (HYP if hv or hr else ""), l["diametre"]])
        gras.add(len(rangs))
        rangs.append([f"Total {r['nom']}", "", "", "", mtr.nombre_fr(r["plan_m"]), mtr.nombre_fr(r["chemin_m"]),
                      mtr.nombre_fr(r["vertical_m"]) + (HYP if hv_res else ""),
                      mtr.nombre_fr(r["reserve_m"]) + (HYP if hr_res else ""),
                      mtr.nombre_fr(r["total_m"]) + (HYP if hv_res or hr_res else ""), ""])
    return _table_md(ENTETES_RESEAUX, rangs, ALIGN_RESEAUX, gras)


def tableau_diametres_md(m: mtr.Metre) -> str:
    statuts = statuts_hauteurs(m)
    rangs = []
    for d in m.par_diametre.values():
        hyp = any(any(ligne_en_hypothese(m.lignes[lid], statuts)) for lid in d["lignes"])
        rangs.append([d["diametre"], d["libelle_type"], mtr.nombre_fr(d["total_m"]) + (HYP if hyp else ""),
                      ", ".join(d["lignes"])])
    return _table_md(["Diamètre", "Type", "Total (m)", "Lignes"], rangs, ["g", "g", "d", "g"])


def prochaine_version(dossier: Path) -> int:
    n = 0
    for f in (dossier / "versions").glob("plan-v*.*"):
        mm = re.fullmatch(r"plan-v(\d+)\.(drawio|json)", f.name)
        if mm:
            n = max(n, int(mm.group(1)))
    return n + 1


def lire_journal(dossier: Path) -> list[str]:
    chemin = dossier / "journal.md"
    if not chemin.is_file():
        return []
    return [l for l in chemin.read_text(encoding="utf-8").splitlines() if l.startswith("- ")]


def questions_ouvertes(plan: mod.Plan, m: mtr.Metre) -> list[str]:
    q = []
    for l in plan.lignes:
        if l["type"] == "chemin_cables":
            continue                              # un chemin de câbles a naturellement une extrémité libre
        libelle = mtr.libelle_type(l["type"], plan.donnees)
        for cle, bout, point in (("de", "départ", l["points"][0]), ("a", "arrivée", l["points"][-1])):
            if not l.get(cle):
                if l["type"] == "condensats" and cle == "a":
                    q.append(f"{l['id']} ({libelle}) : évacuation libre en {_pt(point)} m : où se raccordent les "
                             "condensats (siphon, descente, regard) ?")
                else:
                    q.append(f"{l['id']} ({libelle}) : {bout} libre en {_pt(point)} m : à quel équipement la "
                             "relier ?")
    a_definir = [l["id"] for l in plan.lignes if mtr.normaliser_diametre(l.get("diametre")) == mtr.A_DEFINIR
                 and l["type"] not in ("chemin_cables",)]
    if a_definir:
        q.append(f"Diamètres et sections à définir par le dimensionnement ({len(a_definir)} lignes : "
                 f"{', '.join(a_definir)}).")
    hyp = [h for h in m.hypotheses if h["statut"] == mtr.HYPOTHESE]
    if hyp:
        q.append("Hauteurs de pose à faire valider par le frigoriste (question 13) : "
                 + " ; ".join(f"{h['libelle']} {mtr.longueur_fr(h['valeur'])}" for h in hyp) + ".")
    for cle, v in plan.exigences.items():
        if isinstance(v, dict):
            details = ", ".join(f"{k} : {w}" for k, w in v.items() if k != "motif")
            q.append(f"Exception admise pour {cle} ({details}) : {v.get('motif') or 'motif à écrire'}.")
    return q


# ======================================================================
# plan.md
# ======================================================================
def ecrire_plan_md(chemin: Path, plan: mod.Plan, ech, m: mtr.Metre, liste_x: list[dict], recouv: list[dict],
                   version: int, maintenant: datetime, rendu_info: dict | None, journal: list[str],
                   groupes: list[dict] | None = None) -> Path:
    titre = plan.titre or "Plan 2D"
    w_mm, h_mm = ech.page_mm
    morceaux = [f"<!-- titre: Plan 2D : {titre} -->", "", f"# {titre}", ""]

    morceaux += ["## Identité", "", _table_md(["Champ", "Valeur"], [
        ["Titre", titre], ["Dossier", plan.dossier or mtr.TIRET_VIDE], ["Date du relevé", plan.date or mtr.TIRET_VIDE],
        ["Version", f"v{version}, générée le {maintenant:%Y-%m-%d à %H:%M}"],
        ["Échelle", f"1:{ech.S} (1 m du bâtiment = {nombre_fr(1000.0 / ech.S, 1)} mm sur le papier)"],
        ["Orientation", ech.orientation], ["Page", f"{ech.format} ({nombre_fr(w_mm, 0)} × {nombre_fr(h_mm, 0)} mm)"],
        ["Fichiers", "`plan.drawio` (à ouvrir dans draw.io), `plan.pdf` (à imprimer), `plan.png` (aperçu)"],
    ]), ""]

    # comment vérifier l'échelle
    murs = sorted(plan.murs, key=lambda mu: -geo.distance(*mod.axe_mur(mu)))
    barre_cm = ech.barre_echelle_mm / 10.0
    morceaux += ["## Comment vérifier l'échelle", "",
                 "- Imprimer `plan.pdf` **à 100 %** (« Taille réelle »), jamais « Ajuster à la page ».",
                 "- **Règle de contrôle** (cartouche, en bas à gauche) : elle doit mesurer **100 mm** au réglet.",
                 f"- **Barre d'échelle** : {nombre_fr(ech.barre_echelle_m, 0)} m du bâtiment = "
                 f"**{nombre_fr(barre_cm, 1)} cm** sur le papier (échelle 1:{ech.S})."]
    if murs:
        lm = geo.distance(*mod.axe_mur(murs[0]))
        morceaux.append(f"- Exemple : le mur {murs[0]['id']} ({mtr.longueur_fr(lm)}) mesure "
                        f"**{nombre_fr(lm * 1000.0 / ech.S, 1)} mm** sur le papier.")
    if rendu_info and rendu_info.get("regle_pt"):
        voie = "draw.io Desktop" if rendu_info["voie"] == "drawio" else "Edge + viewer diagrams.net (secours)"
        s_txt = f"{rendu_info['facteur_s']:.6f}".replace(".", ",")
        regle_txt = f"{rendu_info['regle_pt'] / PT_PAR_MM:.3f}".replace(".", ",")
        ecart_txt = f"{rendu_info['ecart_pct']:+.3f}".replace(".", ",").replace("-", mtr.MOINS)
        morceaux.append(f"- Rendu du PDF : {voie}, facteur de correction s = {s_txt}, règle de 100 mm mesurée "
                        f"dans le PDF : {regle_txt} mm (écart {ecart_txt} %).")
    else:
        morceaux.append("- PDF non rendu à cette génération (`--sans-rendu` ou rendu en échec).")
    morceaux += ["- Contrôle automatique : `verifier_plan.py` relit `plan.drawio` et mesure `plan.pdf` "
                 "(contrôles E1 à E11, rapport `verification.md`).", ""]

    # cotes
    morceaux += ["## Cotes relevées", ""]
    if plan.cotes:
        morceaux.append(_table_md(["Cote", "De", "À", "Valeur", "Source"],
                                  [[c["id"], _pt(c["de"]), _pt(c["a"]), mtr.longueur_fr(c["valeur"]),
                                    c.get("source") or "non précisée"] for c in plan.cotes],
                                  ["g", "g", "g", "d", "g"]))
    else:
        morceaux.append("Aucune cote dans le modèle : demander les cotes au frigoriste (télémètre).")
    morceaux.append("")

    # hauteurs
    morceaux += ["## Hypothèses de hauteur", "",
                 f"Métré d'une ligne = longueur du tracé en plan + |passage {mtr.MOINS} départ| + |passage {mtr.MOINS} "
                 "arrivée| + réserve (câbles seulement) ; un câble qui s'arrête sur le chemin de câbles compte aussi son "
                 "parcours dans le chemin jusqu'au tableau (colonne « Dans le chemin ») ; le chemin de câbles lui-même "
                 "est métré une fois, à part, sans métré vertical.", ""]
    if m.hypotheses:
        morceaux.append(_table_md(["Hauteur", "Valeur (m)", "Statut"],
                                  [[h["libelle"], mtr.nombre_fr(h["valeur"]), h["statut"]] for h in m.hypotheses],
                                  ["g", "d", "g"]))
        if any(h["statut"] == mtr.HYPOTHESE for h in m.hypotheses):
            morceaux += ["", "Les hauteurs « hypothèse » sont des valeurs par défaut, à faire valider avant de commander "
                         "le matériel : les valeurs marquées (hyp.) changeront avec elles."]
    else:
        morceaux.append("Aucune hauteur utilisée (aucune ligne à métrer).")
    morceaux.append("")

    # métré
    morceaux += ["## Métré", "", f"### {TITRES_SECTIONS['reseaux']}", ""]
    if m.lignes:
        morceaux += [tableau_reseaux_md(m), "", "### Détail du calcul par ligne", ""]
        for lid, l in m.lignes.items():
            morceaux.append(f"- **{lid}** ({l['libelle_type']}, {l['de'] or mtr.TIRET_VIDE} {mtr.FLECHE} "
                            f"{l['a'] or mtr.TIRET_VIDE}) : {l['formule']}")
        morceaux += ["", f"### {TITRES_SECTIONS['diametres']}", "", tableau_diametres_md(m), ""]
    else:
        morceaux += ["Aucune ligne à métrer.", ""]

    # croisements
    morceaux += [f"## {TITRES_SECTIONS['croisements']}", "",
                 "Croisements en plan entre lignes de faisceaux différents. Sur le dessin (calque « Croisements »), "
                 "un cercle orange par repère G : les croisements distants de 0,50 m au plus partagent le même cercle, "
                 "étiqueté à côté (« X1-X3 ») :",
                 "", crx.tableau_markdown(liste_x, groupes), ""]
    if recouv:
        morceaux += ["Recouvrements (deux lignes superposées en plan, non comptés comme croisements) :", ""]
        morceaux += [f"- {r['id']} : {r['lignes'][0]} et {r['lignes'][1]} superposées sur "
                     f"{mtr.longueur_fr(r['longueur_m'])}, de {_pt(r['de'])} à {_pt(r['a'])} m." for r in recouv]
        morceaux.append("")

    # calques
    rangs = []
    for cle, nom in plan.calques():
        lignes = [l["id"] for l in plan.lignes if l.get("calque") == cle]
        equip = [q["id"] for q in plan.equipements if q.get("calque") == cle]
        contenu = []
        if equip:
            contenu.append(f"équipements {', '.join(equip)}")
        if lignes:
            contenu.append(f"lignes {', '.join(lignes)}")
        if cle == "croisements":
            contenu.append(f"{len(liste_x)} croisement(s)")
        rangs.append([cle, nom, " ; ".join(contenu) or mtr.TIRET_VIDE])
    morceaux += ["## Calques", "", "Dans draw.io : menu Affichage > Calques (Ctrl+Maj+L) pour masquer ou afficher "
                 "un réseau.", "", _table_md(["Calque", "Nom", "Contenu"], rangs), ""]

    # questions
    q = questions_ouvertes(plan, m)
    morceaux += ["## Questions ouvertes", ""]
    morceaux += [f"- {x}" for x in q] if q else ["Aucune."]
    morceaux.append("")
    if plan.notes:
        morceaux += ["## Notes du relevé", ""] + [f"- {n}" for n in plan.notes] + [""]

    morceaux += ["## Journal des versions", ""] + (journal or ["Aucune génération enregistrée."]) + [""]
    chemin.write_text("\n".join(morceaux), encoding="utf-8", newline="\n")
    return chemin


# ======================================================================
# Génération
# ======================================================================
def preparer(dossier: Path) -> dict:
    """Charge et valide le modèle, calcule métré, croisements et échelle (rien n'est écrit).
    `ErreurGeneration` (message multi-lignes) si le plan n'est pas générable."""
    chemin = dossier / "plan.json"
    try:
        plan = mod.charger(chemin)
    except mod.ErreurModele as exc:
        raise ErreurGeneration(str(exc)) from exc
    erreurs = plan.valider()
    if erreurs:
        raise ErreurGeneration("plan.json incohérent, rien n'a été généré :\n- " + "\n- ".join(erreurs))
    try:
        m = mtr.metrer(plan.donnees)
        liste_x = crx.croisements(plan.donnees)
        recouv = crx.recouvrements(plan.donnees)
    except (mtr.ErreurMetre, crx.ErreurCroisements) as exc:
        raise ErreurGeneration(f"Métré ou croisements impossibles : {exc}") from exc
    groupes = crx.regrouper(liste_x)
    donnees = copy.deepcopy(plan.donnees)
    donnees["croisements"] = crx.groupes_pour_dessin(groupes)      # un cercle par groupe (repères G)
    plan_x = mod.depuis_dict(donnees, chemin)
    try:
        ech = choisir_echelle(plan_x.bbox(), plan_x.page)
    except ErreurEchelle as exc:
        raise ErreurGeneration(str(exc)) from exc
    return {"plan": plan, "plan_x": plan_x, "metre": m, "croisements": liste_x, "groupes": groupes,
            "recouvrements": recouv, "echelle": ech}


def tableaux_page_metre(m: mtr.Metre, liste_x: list[dict], groupes: list[dict] | None = None) -> list[tuple[str, str]]:
    return m.tableaux_html() + [(TITRE_TABLEAU_CROISEMENTS, crx.tableau_html(liste_x, groupes))]


def generer(dossier_plan, rendu_pdf: bool = True, ouvrir: bool = False, maintenant: datetime | None = None,
            voie: str = "auto") -> dict:
    """Génère tous les fichiers du plan. Renvoie {code, erreurs, avertissements, fichiers, version, echelle,
    rendu, croisements}. Code 1 sans rien écrire si le modèle est invalide ; code 1 (fichiers écrits) si le
    rendu PDF échoue."""
    dossier = Path(dossier_plan)
    res = {"code": 0, "erreurs": [], "avertissements": [], "fichiers": {}, "version": None, "echelle": None,
           "rendu": None, "croisements": []}
    if not (dossier / "plan.json").is_file():
        res.update(code=1, erreurs=[f"plan.json introuvable dans {dossier}."])
        return res
    try:
        p = preparer(dossier)
    except ErreurGeneration as exc:
        res.update(code=1, erreurs=[str(exc)])
        return res
    maintenant = maintenant or datetime.now()
    plan, ech, m, liste_x = p["plan"], p["echelle"], p["metre"], p["croisements"]
    res.update(echelle=ech, croisements=liste_x)
    version = prochaine_version(dossier)
    res["version"] = version

    f = res["fichiers"]
    f["drawio"] = drawio.ecrire(p["plan_x"], ech, dossier / "plan.drawio",
                                tableaux_page_metre(m, liste_x, p["groupes"]))

    rendu_info = None
    if rendu_pdf:
        try:
            rendu_info = rendu.rendre(dossier, voie=voie)
            res["rendu"] = rendu_info
            f["pdf"], f["png"] = rendu_info["pdf"], rendu_info["png"]
            res["avertissements"] += rendu_info["avertissements"]
        except (rendu.ErreurRendu, drawio.ErreurLecture) as exc:
            res["code"] = 1
            res["erreurs"].append(f"Rendu PDF/PNG impossible : {exc}")

    rendu_txt = ("sans rendu" if not rendu_pdf else
                 (f"rendu {rendu_info['voie']} (s = {rendu_info['facteur_s']:.6f}, règle "
                  f"{rendu_info['regle_pt'] / PT_PAR_MM:.3f} mm)").replace(".", ",") if rendu_info else "rendu en échec")
    ligne_journal = (f"- {maintenant:%Y-%m-%d %H:%M} · v{version} · 1:{ech.S} {ech.orientation} · "
                     f"{len(plan.lignes)} lignes, {len(liste_x)} croisement(s) · {rendu_txt}")
    journal = lire_journal(dossier) + [ligne_journal]

    f["md"] = ecrire_plan_md(dossier / "plan.md", plan, ech, m, liste_x, p["recouvrements"], version, maintenant,
                             rendu_info, journal, p["groupes"])
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from shared.rendu_html import convertir
        f["html"] = convertir(f["md"], racine=dossier, navigation=[])
    except Exception as exc:  # noqa: BLE001 - la vue HTML est un confort : son échec ne bloque pas le plan
        res["avertissements"].append(f"plan.html non produit ({type(exc).__name__} : {exc}).")

    base = {"S": ech.S, "orientation": ech.orientation,
            "origine_mm": [round(ech.origine_mm[0], 4), round(ech.origine_mm[1], 4)]}
    f["plan_base"] = dossier / "plan-base.json"
    f["plan_base"].write_text(json.dumps(base, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    versions = dossier / "versions"
    versions.mkdir(exist_ok=True)
    f["version_drawio"] = versions / f"plan-v{version}.drawio"
    f["version_json"] = versions / f"plan-v{version}.json"
    shutil.copyfile(f["drawio"], f["version_drawio"])
    shutil.copyfile(dossier / "plan.json", f["version_json"])

    chemin_journal = dossier / "journal.md"
    entete = "" if chemin_journal.is_file() else "# Journal des générations du plan\n\n"
    with chemin_journal.open("a", encoding="utf-8", newline="\n") as j:
        j.write(entete + ligne_journal + "\n")
    f["journal"] = chemin_journal

    if ouvrir and f.get("html"):
        from shared.rendu_html import ouvrir_page
        ouvrir_page(f["html"])
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Génère plan.drawio, plan.md/html, plan.pdf/png depuis plan.json.")
    ap.add_argument("dossier_plan", help="dossier plan/ du dossier d'installation (contient plan.json)")
    ap.add_argument("--sans-rendu", action="store_true", help="ne pas produire plan.pdf et plan.png")
    ap.add_argument("--ouvrir", action="store_true", help="ouvrir plan.html dans le navigateur")
    a = ap.parse_args(argv)
    r = generer(a.dossier_plan, rendu_pdf=not a.sans_rendu, ouvrir=a.ouvrir)
    if r["version"] is not None:
        e = r["echelle"]
        print(f"Plan v{r['version']} : échelle 1:{e.S}, {e.orientation}, {len(r['croisements'])} croisement(s).")
        for nom, chemin in r["fichiers"].items():
            if chemin:
                print(f"  {nom} : {chemin}")
        if r["rendu"]:
            ri = r["rendu"]
            print(f"  rendu : {ri['voie']}, s = {ri['facteur_s']:.6f}, règle de 100 mm mesurée "
                  f"{ri['regle_pt'] / PT_PAR_MM:.3f} mm (écart {ri['ecart_pct']:+.3f} %)")
    for m in r["avertissements"]:
        print(f"Avertissement : {m}")
    for m in r["erreurs"]:
        print(f"Erreur : {m}", file=sys.stderr)
    return r["code"]


if __name__ == "__main__":
    sys.exit(main())
