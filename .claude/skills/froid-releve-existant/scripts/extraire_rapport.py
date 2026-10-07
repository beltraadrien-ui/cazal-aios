"""froid-releve-existant — étape 1 : extraire un rapport InterFast (PDF) dans un nouveau dossier d'installation.

Entrée : le PDF « rapport complet » exporté d'InterFast (visite avant devis : un sous-point par poste,
commentaires de Loïc, photos des plaques).

Sortie : dimensionnement/dossiers/<AAAA-MM-JJ-client>/
    dossier.md                 fiche de suivi (état, précision, décisions, questions, journal)
    1-existant.md              squelette du relevé : ce que dit le rapport, tableaux à compléter par la
                               lecture des photos, liste « à confirmer » ; validé ensuite par Loïc
    sources/rapport.pdf        copie du PDF
    sources/rapport-texte.md   texte du PDF page par page (traçabilité)
    sources/structure.json     fiche, client, sous-points, valeurs lues par le script, photos
    sources/photos/<nn-poste>/pNN-k.jpg   photos extraites, rangées par sous-point, dans l'ordre de la page

Rien n'est inventé : chaque valeur écrite vient d'une ligne du PDF (page citée) ou d'un calcul simple
(volume = L × l × h) signalé comme tel.

Usage : python .claude/skills/froid-releve-existant/scripts/extraire_rapport.py "<rapport.pdf>"
            [--slug 2026-09-14-boucherie-test] [--force]
Dépendance : PyMuPDF (pymupdf, dans requirements.txt).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[4]          # racine du dépôt (…/.claude/skills/<skill>/scripts/)
DOSSIERS = ROOT / "dimensionnement" / "dossiers"

RE_PAGINATION = re.compile(r"^(\d+) / (\d+)$")
RE_DIMS = re.compile(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)", re.I)
RE_COMPRESSEURS = re.compile(r"(\d+)\s*compresseurs?", re.I)
RE_EVAPORATEURS = re.compile(r"(\d+)\s*[ée]vaporateurs?", re.I)
RE_UNITES_COND = re.compile(r"(\d+)\s*unit[ée]s?\s+de\s+condensation", re.I)
RE_FLUIDE = re.compile(r"\br\s?-?(\d{2,4}\s?[a-dA-D]?)\b", re.I)
RE_CHARGE = re.compile(r"(\d+(?:[.,]\d+)?)\s*kg", re.I)
RE_TEMP = re.compile(r"(-?\s?\d+(?:[.,]\d+)?)\s*°\s*c", re.I)


def slugifier(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t or "sans-titre"


def nombre(s: str) -> float:
    return float(s.replace(",", "."))


def fr(x: float) -> str:
    """Nombre en écriture française (virgule décimale)."""
    return f"{x:g}".replace(".", ",")


def lignes(page) -> list[str]:
    return [l.strip() for l in page.get_text().split("\n") if l.strip()]


def lire_entete(ls: list[str]) -> dict:
    """Page 1 : type de fiche, numéro, client, intervention, commentaire général."""
    e = {"type": ls[0] if ls else "", "fiche": "", "client": {}, "intervention": {}, "prevoir_devis": "", "commentaire": []}
    for l in ls:
        m = re.match(r"Fiche\s+(\S+)", l)
        if m:
            e["fiche"] = m.group(1)
    if "Client" in ls and "Intervention" in ls:
        bloc = ls[ls.index("Client") + 1: ls.index("Intervention")]
        e["client"] = {"nom": bloc[0] if bloc else "", "lignes": bloc}
    for l in ls:
        for cle, motif in (("adresse", r"Adresse\s*:\s*(.+)"), ("date", r"Date\s*:\s*(.+)"),
                           ("responsable", r"Responsable\s*:\s*(.+)"), ("techniciens", r"Nombre de techniciens\s*:\s*(.+)")):
            m = re.match(motif, l)
            if m:
                e["intervention"][cle] = m.group(1).strip()
    if "Prévoir un devis" in ls:
        i = ls.index("Prévoir un devis")
        e["prevoir_devis"] = ls[i + 1] if i + 1 < len(ls) else ""
    if "Commentaire" in ls:
        i = ls.index("Commentaire") + 1
        fin = len(ls)
        for j in range(i, len(ls)):
            if ls[j] == "Signature technicien" or RE_PAGINATION.match(ls[j]):
                fin = j
                break
        e["commentaire"] = ls[i:fin]
    return e


def lire_sous_point(ls: list[str]) -> dict | None:
    """Page « Element pour le devis » : titre, commentaire, pagination. None si ce n'est pas une page de titre."""
    if not ls or ls[0] != "Element pour le devis" or "Titre" not in ls:
        return None
    i = ls.index("Titre")
    titre = ls[i + 1] if i + 1 < len(ls) else ""
    commentaire: list[str] = []
    if "Commentaire" in ls:
        j = ls.index("Commentaire") + 1
        while j < len(ls) and ls[j] != "Photos" and not RE_PAGINATION.match(ls[j]):
            commentaire.append(ls[j])
            j += 1
    pag = next((RE_PAGINATION.match(l) for l in ls if RE_PAGINATION.match(l)), None)
    return {"titre": titre, "commentaire": commentaire,
            "pages_annoncees": int(pag.group(2)) if pag else 1}


def est_continuation(ls: list[str]) -> bool:
    return bool(ls) and (ls[0] == "Photos" or RE_PAGINATION.match(ls[0]) is not None) and len(ls) <= 2


def analyser_commentaire(lignes_c: list[str], page: int) -> dict:
    """Valeurs lues par motif dans le commentaire de Loïc, chacune avec sa ligne source."""
    lu: dict = {}
    for l in lignes_c:
        src = f"rapport p. {page} : « {l} »"
        m = RE_DIMS.search(l)
        if m and "dimensions" not in lu:
            L, la, h = (nombre(x) for x in m.groups())
            lu["dimensions"] = {"L": L, "l": la, "h": h, "unite": "m (supposé)", "source": src}
            lu["volume_m3"] = {"valeur": round(L * la * h, 1), "source": f"calcul : {m.group(1)} × {m.group(2)} × {m.group(3)} ({src})"}
        m = RE_COMPRESSEURS.search(l)
        if m:
            lu["compresseurs"] = {"valeur": int(m.group(1)), "source": src}
        m = RE_EVAPORATEURS.search(l)
        if m:
            lu["evaporateurs"] = {"valeur": int(m.group(1)), "source": src}
        m = RE_UNITES_COND.search(l)
        if m:
            lu["unites_condensation"] = {"valeur": int(m.group(1)), "source": src}
        m = RE_FLUIDE.search(l)
        if m:
            lu["fluide"] = {"valeur": "R" + m.group(1).replace(" ", "").upper(), "source": src}
        m = RE_CHARGE.search(l)
        if m:
            lu["charge_kg"] = {"valeur": nombre(m.group(1)), "source": src}
        m = RE_TEMP.search(l)
        if m:
            lu["temperature_c"] = {"valeur": nombre(m.group(1).replace(" ", "")), "source": src}
        if re.search(r"r[ée]cup[ée]ration", l, re.I):
            lu["recuperation_chaleur"] = {"valeur": True, "source": src}
    return lu


def extraire(pdf: Path, slug: str | None, force: bool) -> Path:
    doc = pymupdf.open(pdf)
    entete = lire_entete(lignes(doc[0]))

    # --- sous-points et pages -------------------------------------------------------------------
    sous_points: list[dict] = []
    page_vers_sp: dict[int, int] = {}
    for num in range(2, len(doc) + 1):
        ls = lignes(doc[num - 1])
        sp = lire_sous_point(ls)
        if sp:
            sp.update({"numero": len(sous_points) + 1, "slug": slugifier(sp["titre"]), "pages": [num], "photos": []})
            sp["lu"] = analyser_commentaire(sp["commentaire"], num)
            sous_points.append(sp)
            page_vers_sp[num] = len(sous_points) - 1
        elif est_continuation(ls) and sous_points:
            sous_points[-1]["pages"].append(num)
            page_vers_sp[num] = len(sous_points) - 1
        else:
            page_vers_sp[num] = len(sous_points) - 1 if sous_points else -1

    # --- dossier ------------------------------------------------------------------------------
    date_visite = entete["intervention"].get("date", "")
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", date_visite)
    date_iso = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else dt.date.today().isoformat()
    client = entete["client"].get("nom", "") or pdf.stem
    slug = slug or f"{date_iso}-{slugifier(client)}"
    dossier = DOSSIERS / slug
    if dossier.exists() and not force:
        raise SystemExit(f"Le dossier existe déjà : {dossier}\nRelancer avec --force pour le régénérer "
                         f"(les fichiers 1-existant.md et dossier.md existants seraient écrasés).")
    if force and (dossier / "sources" / "photos").exists():
        shutil.rmtree(dossier / "sources" / "photos")      # on repart propre : aucune photo d'un ancien passage
    (dossier / "sources" / "photos").mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf, dossier / "sources" / "rapport.pdf")

    # --- photos : on écarte les images de gabarit (même contenu sur ≥ 3 pages : fond, logo) et les icônes
    empreintes: dict[int, str] = {}
    pages_par_empreinte: dict[str, set] = {}
    for num in range(1, len(doc) + 1):
        for img in doc[num - 1].get_images(full=True):
            xref = img[0]
            h = hashlib.md5(doc.extract_image(xref)["image"]).hexdigest()
            empreintes[xref] = h
            pages_par_empreinte.setdefault(h, set()).add(num)
    gabarit = {h for h, pages in pages_par_empreinte.items() if len(pages) >= 3}
    photos: list[dict] = []
    for num in range(1, len(doc) + 1):
        page = doc[num - 1]
        candidats = []
        for img in page.get_images(full=True):
            xref = img[0]
            if empreintes[xref] in gabarit:
                continue
            info = doc.extract_image(xref)
            if info["width"] < 200 or info["height"] < 200:
                continue
            rects = page.get_image_rects(xref)
            y, x = (rects[0].y0, rects[0].x0) if rects else (0.0, 0.0)
            candidats.append((round(y), x, xref, info))
        candidats.sort()
        isp = page_vers_sp.get(num, -1)
        for k, (_, _, xref, info) in enumerate(candidats, start=1):
            if isp >= 0:
                sp = sous_points[isp]
                sous_dossier = f"{sp['numero']:02d}-{sp['slug']}"
            else:
                sous_dossier = "00-fiche"
            nom = f"p{num:02d}-{k}.{info['ext']}"
            rel = f"sources/photos/{sous_dossier}/{nom}"
            (dossier / "sources" / "photos" / sous_dossier).mkdir(parents=True, exist_ok=True)
            (dossier / rel).write_bytes(info["image"])
            ph = {"fichier": rel, "page": num, "poste": sous_points[isp]["titre"] if isp >= 0 else "fiche",
                  "largeur": info["width"], "hauteur": info["height"], "ko": len(info["image"]) // 1024}
            photos.append(ph)
            if isp >= 0:
                sous_points[isp]["photos"].append(rel)

    # --- texte page par page --------------------------------------------------------------------
    with open(dossier / "sources" / "rapport-texte.md", "w", encoding="utf-8") as f:
        f.write(f"# Texte du rapport InterFast {entete['fiche']} — page par page\n\n")
        f.write(f"Source : `sources/rapport.pdf` ({len(doc)} pages). Extraction automatique, lignes brutes.\n")
        for num in range(1, len(doc) + 1):
            f.write(f"\n## Page {num}\n\n")
            for l in lignes(doc[num - 1]):
                f.write(f"{l}  \n")

    structure = {"fiche": entete["fiche"], "type": entete["type"], "client": entete["client"],
                 "intervention": entete["intervention"], "prevoir_devis": entete["prevoir_devis"],
                 "commentaire_general": entete["commentaire"], "pages": len(doc), "sous_points": sous_points,
                 "photos": photos, "extrait_le": dt.datetime.now().isoformat(timespec="seconds"),
                 "script": "froid-releve-existant/scripts/extraire_rapport.py"}
    (dossier / "sources" / "structure.json").write_text(json.dumps(structure, ensure_ascii=False, indent=1), encoding="utf-8")

    ecrire_dossier_md(dossier, structure, slug)
    ecrire_existant_md(dossier, structure)
    return dossier


def ecrire_dossier_md(dossier: Path, s: dict, slug: str) -> None:
    it, cl = s["intervention"], s["client"]
    adresse_client = " · ".join(cl.get("lignes", [])[1:]) if cl.get("lignes") else ""
    texte = f"""# Dossier {cl.get('nom', '')} — visite du {it.get('date', '?')} — fiche InterFast {s['fiche']}

- **Slug** : `{slug}` · **Type de fiche** : {s['type']} · **Responsable** : {it.get('responsable', '?')}
- **Client** : {cl.get('nom', '')} — {adresse_client}
- **Adresse d'intervention** : {it.get('adresse', '?')}
- **Commentaire général du rapport** : {' / '.join(s['commentaire_general']) or '—'}
- **Créé le** : {s['extrait_le'][:10]} par `froid-releve-existant` (script `extraire_rapport.py`)
- **Étape en cours** : **1 · Relevé de l'existant** — état : *à compléter* (lecture des photos), puis *à valider par Loïc* ✋
- **Niveau de précision** : remise de prix *(passer à « exécution » après signature)*

## Motif et projet
- Pourquoi on remplace : *à dicter par Loïc*
- Ce qu'on envisage : *à dicter par Loïc*

## Décisions
*(ce qui est remplacé par quoi, validé par Loïc, avec la date)*

## Hypothèses
*(chaque hypothèse est datée et sourcée ; une hypothèse non confirmée reste une hypothèse)*

## Questions ouvertes
*(reprises de la liste « À confirmer » de `1-existant.md`, puis des étapes suivantes)*

## Journal
| Date | Qui | Quoi |
|---|---|---|
| {s['extrait_le'][:10]} | script | Dossier créé depuis `sources/rapport.pdf` : {len(s['sous_points'])} sous-points, {len(s['photos'])} photos extraites |
"""
    (dossier / "dossier.md").write_text(texte, encoding="utf-8")


def ecrire_existant_md(dossier: Path, s: dict) -> None:
    it, cl = s["intervention"], s["client"]
    L: list[str] = []
    L.append(f"# Relevé de l'existant — {cl.get('nom', '')} — visite du {it.get('date', '?')} (fiche InterFast {s['fiche']})")
    L.append("")
    L.append("> **État : à compléter** (lecture des photos par Claude, tableaux B et D) → puis **à valider par Loïc** ✋.")
    L.append("> Règle : chaque valeur porte sa source (`rapport p. N`, `photo pNN-k`, `calcul`, `dicté par Loïc`, `web : lien`).")
    L.append("> Ce qui manque est écrit « à confirmer », jamais deviné. Photos InterFast en 450 × 600 : une plaque illisible = demander l'original.")
    L.append("")
    L.append("## A. Postes relevés (ce que dit le rapport, tel quel)")
    L.append("")
    L.append("| # | Poste (sous-point InterFast) | Commentaire de Loïc (texte du rapport) | Lu par le script | Pages | Photos |")
    L.append("|---|---|---|---|---|---|")
    for sp in s["sous_points"]:
        lu = sp["lu"]
        morceaux = []
        if "compresseurs" in lu:
            morceaux.append(f"{lu['compresseurs']['valeur']} compresseurs")
        if "unites_condensation" in lu:
            morceaux.append(f"{lu['unites_condensation']['valeur']} unités de condensation")
        if "evaporateurs" in lu:
            morceaux.append(f"{lu['evaporateurs']['valeur']} évaporateurs")
        if "fluide" in lu:
            morceaux.append(f"fluide {lu['fluide']['valeur']}")
        if "charge_kg" in lu:
            morceaux.append(f"charge {fr(lu['charge_kg']['valeur'])} kg")
        if "dimensions" in lu:
            d = lu["dimensions"]
            morceaux.append(f"{fr(d['L'])} × {fr(d['l'])} × {fr(d['h'])} m → {fr(lu['volume_m3']['valeur'])} m³ (calcul)")
        if "temperature_c" in lu:
            morceaux.append(f"{fr(lu['temperature_c']['valeur'])} °C")
        if "recuperation_chaleur" in lu:
            morceaux.append("récupération de chaleur")
        L.append(f"| {sp['numero']} | {sp['titre']} | {' / '.join(sp['commentaire']) or '—'} | {' ; '.join(morceaux) or '—'} "
                 f"| {', '.join(str(p) for p in sp['pages'])} | {len(sp['photos'])} |")
    L.append("")
    L.append("## B. Compresseurs (une ligne par compresseur, d'après les plaques)")
    L.append("")
    L.append("| Poste | Marque | Modèle (référence complète) | N° de série | Fluides sur la plaque | Tension / fréquence | Volume balayé ou autres données de plaque | Photo | Lecture | Source |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for sp in s["sous_points"]:
        n = sp["lu"].get("compresseurs", {}).get("valeur")
        if n:
            for i in range(1, n + 1):
                L.append(f"| {sp['titre']} — compresseur {i}/{n} | à lire | à lire | à lire | à lire | à lire | à lire | ? | — | nombre : {sp['lu']['compresseurs']['source']} |")
        n2 = sp["lu"].get("unites_condensation", {}).get("valeur")
        if n2:
            for i in range(1, n2 + 1):
                L.append(f"| {sp['titre']} — unité de condensation {i}/{n2} | à lire | à lire | à lire | à lire | à lire | à lire | ? | — | nombre : {sp['lu']['unites_condensation']['source']} |")
    L.append("")
    L.append("*Lecture* : `sûre`, `douteuse (lecture la plus probable + doute)` ou `illisible`. Voir `dimensionnement/savoir/materiel/lecture-plaques.md`.")
    L.append("")
    L.append("## C. Chambres froides et postes desservis")
    L.append("")
    L.append("| Poste / chambre | L × l × h | Volume (m³, calcul) | Température | Usage | Évaporateurs | Desservi par | Source |")
    L.append("|---|---|---|---|---|---|---|---|")
    for sp in s["sous_points"]:
        lu = sp["lu"]
        if "dimensions" in lu or "evaporateurs" in lu:
            d = lu.get("dimensions")
            dims = f"{fr(d['L'])} × {fr(d['l'])} × {fr(d['h'])} {d['unite']}" if d else "à confirmer"
            vol = fr(lu["volume_m3"]["valeur"]) if "volume_m3" in lu else "à confirmer"
            temp = f"{fr(lu['temperature_c']['valeur'])} °C" if "temperature_c" in lu else "à confirmer"
            ev = f"{lu['evaporateurs']['valeur']}" if "evaporateurs" in lu else "à confirmer"
            src = (d or lu.get("evaporateurs"))["source"]
            L.append(f"| {sp['titre']} | {dims} | {vol} | {temp} | à confirmer | {ev} | à confirmer | {src} |")
    L.append("")
    L.append("## D. Régulation, récupération de chaleur, autres éléments")
    L.append("")
    L.append("| Élément | Ce que dit le rapport | Lu sur les photos | Source |")
    L.append("|---|---|---|---|")
    for sp in s["sous_points"]:
        lu = sp["lu"]
        if "recuperation_chaleur" in lu:
            L.append(f"| Récupération de chaleur — {sp['titre']} | {' / '.join(sp['commentaire'])} | à lire | {lu['recuperation_chaleur']['source']} |")
        if not any(k in lu for k in ("compresseurs", "dimensions", "evaporateurs", "unites_condensation")):
            L.append(f"| {sp['titre']} | {' / '.join(sp['commentaire']) or '—'} | à lire | rapport p. {sp['pages'][0]} |")
    L.append("")
    L.append("## E. À confirmer par Loïc")
    L.append("")
    L.append("*(numéros de la checklist `dimensionnement/savoir/methodes/checklist-releve.md`)*")
    L.append("")
    L.append("- [ ] 1-2. Motif du remplacement et ce qu'on envisage : *non écrits dans le rapport*")
    for sp in s["sous_points"]:
        lu = sp["lu"]
        if "compresseurs" in lu or "unites_condensation" in lu:
            if "fluide" not in lu:
                L.append(f"- [ ] 7. {sp['titre']} : fluide et charge non indiqués")
            L.append(f"- [ ] 6. {sp['titre']} : ce qu'il dessert et à quelle température")
        if "dimensions" in lu and "temperature_c" not in lu:
            L.append(f"- [ ] 10. {sp['titre']} : température de consigne et usage ; état de l'isolation")
    L.append("- [ ] 13-15. Local technique, électricité disponible, contraintes d'exploitation et délais : *non écrits dans le rapport*")
    L.append("")
    L.append("## F. Photos extraites (index)")
    L.append("")
    L.append("| Photo | Page | Poste | Taille |")
    L.append("|---|---|---|---|")
    for ph in s["photos"]:
        L.append(f"| `{ph['fichier']}` | {ph['page']} | {ph['poste']} | {ph['largeur']} × {ph['hauteur']} |")
    L.append("")
    (dossier / "1-existant.md").write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", help="rapport complet InterFast (PDF)")
    ap.add_argument("--slug", help="nom du dossier (défaut : AAAA-MM-JJ-client d'après le rapport)")
    ap.add_argument("--force", action="store_true", help="régénérer un dossier existant")
    a = ap.parse_args()
    pdf = Path(a.pdf)
    if not pdf.exists():
        raise SystemExit(f"PDF introuvable : {pdf}")
    dossier = extraire(pdf, a.slug, a.force)
    s = json.loads((dossier / "sources" / "structure.json").read_text(encoding="utf-8"))
    print(f"Dossier créé : {dossier}")
    print(f"Fiche {s['fiche']} · {s['type']} · client {s['client'].get('nom', '')} · visite du {s['intervention'].get('date', '?')} · {s['pages']} pages")
    print(f"{len(s['sous_points'])} sous-points, {len(s['photos'])} photos extraites :")
    for sp in s["sous_points"]:
        lu = sp["lu"]
        resume = ", ".join(f"{k}={v['valeur']}" for k, v in lu.items() if k != "dimensions" and "valeur" in v)
        print(f"  {sp['numero']:2d}. {sp['titre']} — pages {sp['pages']} — {len(sp['photos'])} photo(s) — {resume or 'rien de chiffré'}")
    print("À faire ensuite : lire les photos (tableaux B et D de 1-existant.md), puis validation de Loïc.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
