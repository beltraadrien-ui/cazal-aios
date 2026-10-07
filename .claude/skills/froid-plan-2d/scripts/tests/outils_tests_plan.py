"""Outils communs aux tests de rendu.py, generer.py, verifier_plan.py et importer_drawio.py (B1).

- `dossier_boucherie(racine, rendu_pdf=False)` : copie de la fixture boucherie dans un dossier temporaire, générée.
- Mutations du XML de `plan.drawio` par identifiant de cellule (`modifier_xml`, `geometrie`, `deplacer_sommet`,
  `deplacer_arete`, `supprimer_cellule`, `decaler_tout`, `ajouter_arete`).
- `fabriquer_pdf(dossier, k=0.72)` : PDF A4 dessiné avec PyMuPDF à partir de la lecture de plan.drawio (règle de
  contrôle, barre d'échelle, murs), à l'échelle k pt par px (0,72 = exact) : sert à tester E10 sans draw.io, et
  à fabriquer exprès un PDF à l'échelle fausse.
Données génériques (boucherie test fictive), aucune donnée client.
"""
from __future__ import annotations

import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # dossier scripts/
import drawio  # noqa: E402
import generer  # noqa: E402
import rendu  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BOUCHERIE = FIXTURES / "a1-boucherie-plan.json"
PAGE_PT = (841.92, 594.96)          # page A4 paysage telle que draw.io et Edge la sortent (R1)


def charger_boucherie() -> dict:
    return json.loads(BOUCHERIE.read_text(encoding="utf-8"))


def ecrire_plan(dossier: Path, donnees: dict) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / "plan.json"
    chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")
    return chemin


def dossier_boucherie(racine: Path, nom: str = "plan", donnees: dict | None = None, rendu_pdf: bool = False,
                      pdf_fabrique: bool = True) -> Path:
    """Dossier plan/ prêt : plan.json (boucherie ou `donnees`), généré ; PDF + PNG fabriqués exacts si demandé."""
    dossier = Path(racine) / nom
    ecrire_plan(dossier, donnees if donnees is not None else charger_boucherie())
    r = generer.generer(dossier, rendu_pdf=rendu_pdf)
    if r["code"] != 0:
        raise AssertionError(f"generer a échoué : {r['erreurs']}")
    if not rendu_pdf and pdf_fabrique:
        fabriquer_pdf(dossier)
    return dossier


def copier(dossier: Path, racine: Path, nom: str) -> Path:
    cible = Path(racine) / nom
    shutil.copytree(dossier, cible)
    return cible


# ----------------------------------------------------------------------------------------------------------
# Mutations du XML
# ----------------------------------------------------------------------------------------------------------
def _arbre(chemin: Path) -> ET.ElementTree:
    return ET.parse(chemin)


def _ecrire(arbre: ET.ElementTree, chemin: Path) -> None:
    arbre.write(chemin, encoding="utf-8", xml_declaration=False)


def cellule(arbre: ET.ElementTree, ident: str, page: str = "plan") -> ET.Element:
    for d in arbre.getroot().findall("diagram"):
        if d.get("id") == page:
            for c in d.iter("mxCell"):
                if c.get("id") == ident:
                    return c
    raise KeyError(ident)


def modifier_xml(dossier: Path, fonction, page: str = "plan") -> None:
    """Applique `fonction(arbre)` au XML de plan.drawio et le réécrit."""
    chemin = Path(dossier) / "plan.drawio"
    arbre = _arbre(chemin)
    fonction(arbre)
    _ecrire(arbre, chemin)


def geometrie(dossier: Path, ident: str, page: str = "plan", **valeurs) -> None:
    """Change des attributs de <mxGeometry> (x, y, width, height) d'une cellule."""
    def f(arbre):
        g = cellule(arbre, ident, page).find("mxGeometry")
        for k, v in valeurs.items():
            g.set(k, f"{float(v):.2f}")
    modifier_xml(dossier, f, page)


def lire_geometrie(dossier: Path, ident: str, page: str = "plan") -> dict:
    g = cellule(_arbre(Path(dossier) / "plan.drawio"), ident, page).find("mxGeometry")
    return {k: float(g.get(k)) for k in ("x", "y", "width", "height") if g.get(k) is not None}


def deplacer_sommet(dossier: Path, ident: str, dx: float = 0.0, dy: float = 0.0) -> None:
    g = lire_geometrie(dossier, ident)
    geometrie(dossier, ident, x=g["x"] + dx, y=g["y"] + dy)


def deplacer_arete(dossier: Path, ident: str, quoi: str = "sourcePoint", dx: float = 0.0, dy: float = 0.0,
                   indice: int | None = None) -> None:
    """Déplace sourcePoint / targetPoint (quoi), ou le point intermédiaire n° `indice` (quoi = "points")."""
    def f(arbre):
        g = cellule(arbre, ident).find("mxGeometry")
        if quoi == "points":
            p = g.find("Array").findall("mxPoint")[indice]
        else:
            p = next(p for p in g.findall("mxPoint") if p.get("as") == quoi)
        p.set("x", f"{float(p.get('x')) + dx:.2f}")
        p.set("y", f"{float(p.get('y')) + dy:.2f}")
    modifier_xml(dossier, f)


def supprimer_cellule(dossier: Path, ident: str, page: str = "plan") -> None:
    def f(arbre):
        for d in arbre.getroot().findall("diagram"):
            if d.get("id") != page:
                continue
            for parent in d.iter():
                for c in list(parent):
                    if c.tag == "mxCell" and c.get("id") == ident:
                        parent.remove(c)
    modifier_xml(dossier, f, page)


def changer_attribut(dossier: Path, ident: str, attribut: str, remplacer: tuple[str, str], page: str = "plan") -> None:
    def f(arbre):
        c = cellule(arbre, ident, page)
        avant = c.get(attribut) or ""
        if remplacer[0] not in avant:
            raise AssertionError(f"« {remplacer[0]} » absent de {ident}.{attribut}")
        c.set(attribut, avant.replace(remplacer[0], remplacer[1], 1))
    modifier_xml(dossier, f, page)


def decaler_tout(dossier: Path, dx: float, dy: float, sauf_calques: tuple[str, ...] = ("cartouche",)) -> None:
    """Déplace d'un bloc toutes les cellules de la page « Plan » (hors calques exclus), comme une sélection
    complète déplacée à la souris dans draw.io."""
    def f(arbre):
        d = next(d for d in arbre.getroot().findall("diagram") if d.get("id") == "plan")
        for c in d.iter("mxCell"):
            if c.get("parent") in (None, "0") or c.get("parent") in sauf_calques:
                continue
            g = c.find("mxGeometry")
            if g is None:
                continue
            if c.get("vertex") == "1":
                g.set("x", f"{float(g.get('x', 0)) + dx:.2f}")
                g.set("y", f"{float(g.get('y', 0)) + dy:.2f}")
            for p in g.iter("mxPoint"):
                p.set("x", f"{float(p.get('x', 0)) + dx:.2f}")
                p.set("y", f"{float(p.get('y', 0)) + dy:.2f}")
    modifier_xml(dossier, f)


def ajouter_arete(dossier: Path, ident: str, calque: str, points_px: list[tuple[float, float]], style: str) -> None:
    """Ajoute une arête comme si le frigoriste l'avait dessinée dans draw.io (identifiant quelconque)."""
    def f(arbre):
        d = next(d for d in arbre.getroot().findall("diagram") if d.get("id") == "plan")
        root = d.find("mxGraphModel").find("root")
        c = ET.SubElement(root, "mxCell", {"id": ident, "value": "", "style": style, "edge": "1", "parent": calque})
        g = ET.SubElement(c, "mxGeometry", {"relative": "1", "as": "geometry"})
        ET.SubElement(g, "mxPoint", {"x": f"{points_px[0][0]:.2f}", "y": f"{points_px[0][1]:.2f}", "as": "sourcePoint"})
        ET.SubElement(g, "mxPoint", {"x": f"{points_px[-1][0]:.2f}", "y": f"{points_px[-1][1]:.2f}", "as": "targetPoint"})
        if len(points_px) > 2:
            arr = ET.SubElement(g, "Array", {"as": "points"})
            for x, y in points_px[1:-1]:
                ET.SubElement(arr, "mxPoint", {"x": f"{x:.2f}", "y": f"{y:.2f}"})
    modifier_xml(dossier, f)


# ----------------------------------------------------------------------------------------------------------
# PDF et PNG fabriqués (PyMuPDF)
# ----------------------------------------------------------------------------------------------------------
def fabriquer_pdf(dossier: Path, k: float = rendu.PT_PAR_PX, page_pt: tuple[float, float] = PAGE_PT,
                  k_barre: float | None = None, k_murs: float | None = None, png: bool = True) -> Path:
    """PDF d'une page dessiné depuis la lecture de plan.drawio : règle de contrôle, barre d'échelle et murs en
    rectangles pleins à `k` pt par px (0,72 = échelle exacte) ; `k_barre` / `k_murs` faussent une seule mesure."""
    import pymupdf
    dossier = Path(dossier)
    L = drawio.lire(dossier / "plan.drawio")
    doc = pymupdf.open()
    page = doc.new_page(width=page_pt[0], height=page_pt[1])

    def rect(ident, kk_longueur=None):
        c = L.brut[ident]
        g = c["geometrie"]
        fill = rendu.couleur_rgb(c["style"].get("fillColor", "#000000")) or (0, 0, 0)
        kl = kk_longueur or k
        cx, cy = (g["x"] + g["width"] / 2) * k, (g["y"] + g["height"] / 2) * k
        w, h = g["width"] * kl, g["height"] * kl
        page.draw_rect(pymupdf.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), color=None, fill=fill)

    x0 = L.brut["regle-controle"]["geometrie"]["x"]
    g = L.brut["regle-controle"]["geometrie"]
    page.draw_rect(pymupdf.Rect(x0 * k, g["y"] * k, (x0 + g["width"]) * k, (g["y"] + g["height"]) * k),
                   color=None, fill=(0, 0, 0))
    rect("barre-echelle", k_barre)
    for e in L.elements.values():
        if e.get("type") == "mur":
            rect(e["id"], k_murs)
    pdf = dossier / "plan.pdf"
    pdf.unlink(missing_ok=True)
    doc.save(pdf)
    doc.close()
    if png:
        rendu.rasteriser(pdf, dossier / "plan.png")
    return pdf
