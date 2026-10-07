"""Rendu de `plan.drawio` en `plan.pdf` (A4, à l'échelle exacte, mesurée) et `plan.png` (2 px par px draw.io).

Règle n° 1 : le plan imprimé à 100 % est à l'échelle. Le rendu ne la suppose pas, il la MESURE : la règle de
contrôle de 100 mm du cartouche (`regle-controle`, 393,70 px) est relue dans le PDF avec PyMuPDF et doit valoir
283,46 pt à 0,05 % près.

Voie principale (recherche R1) : draw.io Desktop en ligne de commande, `-x -f pdf -a -s <s>` (les 2 pages,
« Plan » et « Métré »). draw.io sort son PDF 0,245 % trop petit : le facteur `s` corrige. Il est CALIBRÉ (export
à s = 1, mesure de la règle, s = attendu / mesuré, réexport, remesure), mémorisé dans `plan/rendu.json` et
revérifié à chaque rendu (recalibré si l'écart dépasse 0,05 %). Jamais `--crop`, `-b`, ni `pageScale ≠ 1`.
Voie de secours (draw.io absent) : Edge sans tête + viewer statique diagrams.net (en ligne), page HTML A4 exacte
(`@page 297mm 210mm`, `scale(0.96)` : 1 px CSS = 1/96 in, 1 px draw.io = 1/100 in), rectangle invisible de la
taille de la page pour ancrer l'origine ; une seule page (le plan). Même mesure de la règle.
PNG : la page 1 du PDF rastérisée par PyMuPDF à 200 dpi (2 px par px draw.io), jamais l'export PNG de draw.io
(cassé au-delà de ~2 500 px de large sur ce PC, R1 §4).

Usage :
    from rendu import rendre
    r = rendre("…/plan")    # {pdf, png, voie, facteur_s, ecart_pct, regle_pt, commande, avertissements}
    python rendu.py <dossier_plan> [--voie auto|drawio|edge] [--sans-png]

Mesure (aussi utilisée par verifier_plan.py, contrôle E10) : `rectangles_pleins(page)`, `mesurer_regle(page,
boite_px)`, `transformation(regle, boite_px)`, `chercher_rectangle(...)`.
"""
from __future__ import annotations

import argparse
import glob
import html as _html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drawio  # noqa: E402
from echelle import PT_PAR_MM, REGLE_CONTROLE_MM  # noqa: E402

PT_PAR_PX = 72.0 / 100.0                     # nominal : 1 px draw.io = 1/100 in, 1 pt = 1/72 in
REGLE_PT = REGLE_CONTROLE_MM * PT_PAR_MM     # 283,4646 pt : longueur exacte de la règle de 100 mm
TOLERANCE_CALIBRATION = 0.0005               # 0,05 % : écart admis entre règle mesurée et règle exacte
ESSAIS_CALIBRATION = 4
DPI_PNG = 200                                # 200 dpi = 2 px par px draw.io (100 px par pouce)
VIEWER_EN_LIGNE = "https://viewer.diagrams.net/js/viewer-static.min.js"
DELAI_DRAWIO_S = 120
DELAI_EDGE_S = 180
CREATION_DISCRETE = getattr(subprocess, "CREATE_NO_WINDOW", 0)

EMPLACEMENTS_DRAWIO = (
    r"C:\Program Files\WindowsApps\draw.io.draw.ioDiagrams_*\app\draw.io.exe",   # version Store (R1)
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "draw.io", "draw.io.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "draw.io", "draw.io.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "draw.io", "draw.io.exe"),
)
EMPLACEMENTS_EDGE = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)


class ErreurRendu(RuntimeError):
    """Rendu impossible (fichier absent, aucun outil de rendu, PDF illisible…) : message en français."""


# ======================================================================
# Outils de rendu
# ======================================================================
def trouver_drawio() -> Path | None:
    """Exécutable de draw.io Desktop (Store ou installation classique), ou None.

    Variable d'environnement `FROID_PLAN_DRAWIO` : chemin imposé, ou « aucun » pour faire comme s'il était
    absent (tests de la voie de secours)."""
    impose = os.environ.get("FROID_PLAN_DRAWIO")
    if impose:
        return None if impose.lower() == "aucun" else (Path(impose) if Path(impose).is_file() else None)
    for motif in EMPLACEMENTS_DRAWIO:
        if not motif:
            continue
        trouves = sorted(glob.glob(motif)) if "*" in motif else ([motif] if Path(motif).is_file() else [])
        if trouves:
            return Path(trouves[-1])
    try:   # dernier recours : le dossier d'installation du paquet Store, demandé à Windows
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            '(Get-AppxPackage -Name "draw.io.draw.ioDiagrams").InstallLocation'],
                           capture_output=True, text=True, timeout=30, creationflags=CREATION_DISCRETE)
        dossier = (r.stdout or "").strip()
        if dossier and (Path(dossier) / "app" / "draw.io.exe").is_file():
            return Path(dossier) / "app" / "draw.io.exe"
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def trouver_edge() -> Path | None:
    for c in EMPLACEMENTS_EDGE:
        if Path(c).is_file():
            return Path(c)
    trouve = shutil.which("msedge.exe") or shutil.which("msedge")
    return Path(trouve) if trouve else None


def _supprimer(chemin: Path) -> None:
    try:
        chemin.unlink(missing_ok=True)
    except PermissionError:
        raise ErreurRendu(f"{chemin.name} est ouvert dans un autre programme (lecteur PDF ?) : le fermer puis "
                          "relancer.") from None


def _texte(octets: bytes | str | None) -> str:
    if octets is None:
        return ""
    if isinstance(octets, str):
        return octets
    return octets.decode("utf-8", errors="replace")


def exporter_drawio(exe: Path, src: Path, pdf: Path, s: float) -> list[str]:
    """Export PDF des 2 pages par draw.io Desktop, facteur d'échelle `s` ; attend la fin du processus."""
    _supprimer(pdf)
    commande = [str(exe), "-x", "-f", "pdf", "-a", "-s", f"{s:.6f}", "-o", str(pdf), str(src)]
    try:
        subprocess.run(commande, check=True, capture_output=True, timeout=DELAI_DRAWIO_S,
                       creationflags=CREATION_DISCRETE)
    except subprocess.CalledProcessError as exc:
        raise ErreurRendu(f"draw.io a échoué (code {exc.returncode}) : {_texte(exc.stderr).strip()[:300]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ErreurRendu(f"draw.io n'a pas fini l'export en {DELAI_DRAWIO_S} s.") from exc
    if not pdf.is_file() or pdf.stat().st_size == 0:
        raise ErreurRendu("draw.io n'a pas produit de PDF (code de retour 0 mais fichier absent).")
    return commande


def page_html_viewer(src: Path, page_html: Path, s: float = 1.0, viewer: str = VIEWER_EN_LIGNE) -> Path:
    """Page HTML A4 exacte qui affiche la page « Plan » de `src` avec le viewer statique diagrams.net.

    Corrections de R1 : `@page {size; margin: 0}`, `transform: scale(0.96 × s)`, pas de clé `toolbar` dans la
    configuration (elle décale tout de 26 px), `border: 0`, rectangle invisible de la taille de la page ajouté
    (en mémoire) sur le premier calque pour que le viewer cadre la page entière et non le contenu."""
    racine = ET.parse(src).getroot()
    diagrammes = racine.findall("diagram") if racine.tag == "mxfile" else []
    if racine.tag == "mxfile" and not diagrammes:
        raise ErreurRendu(f"{src.name} : aucune page.")
    d1 = diagrammes[0] if diagrammes else None
    modele = racine if racine.tag == "mxGraphModel" else d1.find("mxGraphModel")
    if modele is None and d1 is not None and (d1.text or "").strip():
        modele = ET.fromstring(drawio._decompresser(d1.text))
    if modele is None:
        raise ErreurRendu(f"{src.name} : page « Plan » illisible.")
    pw, ph = float(modele.get("pageWidth", 0)), float(modele.get("pageHeight", 0))
    if pw <= 0 or ph <= 0:
        raise ErreurRendu(f"{src.name} : dimensions de page absentes.")
    root = modele.find("root")
    calques = [c for c in root if c.get("parent") == "0"]
    if not calques:
        raise ErreurRendu(f"{src.name} : aucun calque.")
    cadre = ET.Element("mxCell", {"id": "__page__", "value": "", "vertex": "1", "parent": calques[0].get("id"),
                                  "style": "rounded=0;html=1;fillColor=none;strokeColor=none;"})
    ET.SubElement(cadre, "mxGeometry", {"x": "0", "y": "0", "width": f"{pw:g}", "height": f"{ph:g}", "as": "geometry"})
    root.insert(list(root).index(calques[0]) + 1, cadre)
    mxfile = ET.Element("mxfile", {"host": drawio.HOTE})
    nouveau = ET.SubElement(mxfile, "diagram", {"name": "Plan", "id": "plan"})
    nouveau.append(modele)
    xml = ET.tostring(mxfile, encoding="unicode")
    cfg = {"highlight": "#0000ff", "nav": False, "resize": False, "edit": None, "border": 0, "zoom": 1, "xml": xml}
    donnees = _html.escape(json.dumps(cfg), quote=True)
    w_mm, h_mm = pw / (100.0 / 25.4), ph / (100.0 / 25.4)
    w_mm, h_mm = round(w_mm), round(h_mm)          # 1169 × 827 px → 297 × 210 mm
    page = (f"""<!doctype html><html><head><meta charset="utf-8"><title>plan</title><style>
@page {{ size: {w_mm}mm {h_mm}mm; margin: 0 }}
html, body {{ margin: 0; padding: 0; background: #fff }}
#feuille {{ position: absolute; left: 0; top: 0; width: {w_mm}mm; height: {h_mm}mm; overflow: hidden }}
#plan {{ position: absolute; left: 0; top: 0; transform: scale({0.96 * s:.6f}); transform-origin: 0 0;
         width: {pw:g}px; height: {ph:g}px }}
</style></head><body><div id="feuille"><div id="plan"><div class="mxgraph" style="width:{pw:g}px" """
            f"""data-mxgraph="{donnees}"></div></div></div>
<script src="{_html.escape(viewer, quote=True)}"></script></body></html>""")
    page_html.write_text(page, encoding="utf-8", newline="\n")
    return page_html


def _ps(v: str) -> str:
    """Chaîne PowerShell entre apostrophes (apostrophes doublées)."""
    return "'" + str(v).replace("'", "''") + "'"


def imprimer_edge(edge: Path, page_html: Path, pdf: Path) -> list[str]:
    """Imprime `page_html` en PDF avec Edge sans tête, lancé par PowerShell `Start-Process -Wait` (un Edge lancé
    directement rend la main avant la fin), profil `--user-data-dir` neuf à chaque fois."""
    _supprimer(pdf)
    profil = Path(tempfile.mkdtemp(prefix="froid-plan-edge-"))
    args = ["--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions", f'--user-data-dir="{profil}"',
            "--virtual-time-budget=15000", f'--print-to-pdf="{pdf}"', page_html.resolve().as_uri()]
    script = (f"$p = Start-Process -FilePath {_ps(edge)} -ArgumentList @({', '.join(_ps(a) for a in args)}) "
              "-Wait -PassThru -WindowStyle Hidden; exit $p.ExitCode")
    commande = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    try:
        subprocess.run(commande, capture_output=True, timeout=DELAI_EDGE_S, creationflags=CREATION_DISCRETE)
    except subprocess.TimeoutExpired as exc:
        raise ErreurRendu(f"Edge n'a pas fini l'impression en {DELAI_EDGE_S} s.") from exc
    finally:
        for _ in range(10):
            shutil.rmtree(profil, ignore_errors=True)
            if not profil.exists():
                break
            time.sleep(0.5)
    if not pdf.is_file() or pdf.stat().st_size == 0:
        raise ErreurRendu("Edge n'a pas produit de PDF (viewer diagrams.net injoignable ? connexion internet "
                          "requise pour la voie de secours).")
    return [str(edge), *args]


# ======================================================================
# Mesure du PDF (PyMuPDF)
# ======================================================================
def rectangles_pleins(page) -> list[dict]:
    """Rectangles remplis de la page : [{x0, y0, x1, y1, l (largeur), h (hauteur), fill (r, g, b)}] en pt."""
    res = []
    for d in page.get_drawings():
        fill = d.get("fill")
        if fill is None:
            continue
        items = d.get("items") or []
        rects = []
        for it in items:
            if it[0] == "re":
                rects.append(pymupdf.Rect(it[1]))
            elif it[0] == "qu":
                rects.append(it[1].rect)
        if not rects and items and all(it[0] == "l" for it in items) and 3 <= len(items) <= 5:
            rects.append(pymupdf.Rect(d["rect"]))
        for r in rects:
            res.append({"x0": r.x0, "y0": r.y0, "x1": r.x1, "y1": r.y1, "l": r.width, "h": r.height,
                        "fill": tuple(float(c) for c in fill[:3])})
    return res


def _centre(r: dict) -> tuple[float, float]:
    return ((r["x0"] + r["x1"]) / 2.0, (r["y0"] + r["y1"]) / 2.0)


def mesurer_regle(page, boite_px: tuple[float, float, float, float] | None = None,
                  rects: list[dict] | None = None) -> dict | None:
    """La règle de contrôle dans le PDF : rectangle plein noir, fin (< 3 pt), long de 85 à 115 % de 283,46 pt.

    `boite_px` = (x, y, largeur, hauteur) de la cellule `regle-controle` : départage par la position attendue
    (0,72 pt par px). Renvoie le rectangle (pt) ou None."""
    rects = rectangles_pleins(page) if rects is None else rects
    cands = [r for r in rects if max(r["fill"]) < 0.15 and r["h"] < 3.0
             and 0.85 * REGLE_PT <= r["l"] <= 1.15 * REGLE_PT]
    if not cands:
        return None
    if boite_px:
        x, y, w, h = boite_px
        attendu = ((x + w / 2) * PT_PAR_PX, (y + h / 2) * PT_PAR_PX)
        return min(cands, key=lambda r: (_centre(r)[0] - attendu[0]) ** 2 + (_centre(r)[1] - attendu[1]) ** 2)
    return min(cands, key=lambda r: abs(r["l"] - REGLE_PT))


def transformation(regle: dict, boite_px: tuple[float, float, float, float]) -> tuple[float, float, float]:
    """(k pt par px, décalage x, décalage y) déduits de la règle mesurée : px draw.io → pt du PDF."""
    x, y, w, h = boite_px
    k = regle["l"] / w
    return k, regle["x0"] - k * x, (regle["y0"] + regle["y1"]) / 2.0 - k * (y + h / 2.0)


def px_vers_pt(p: tuple[float, float], transfo: tuple[float, float, float]) -> tuple[float, float]:
    k, ox, oy = transfo
    return (ox + k * p[0], oy + k * p[1])


def chercher_rectangle(rects: list[dict], boite_px: tuple[float, float, float, float],
                       transfo: tuple[float, float, float], couleur: tuple[float, float, float] | None = None,
                       tolerance_pt: float = 3.0) -> dict | None:
    """Rectangle plein du PDF dont le centre tombe là où la cellule (x, y, l, h en px) est attendue (à
    `tolerance_pt`), de couleur `couleur` (± 0,03) si donnée ; le plus proche."""
    x, y, w, h = boite_px
    c = px_vers_pt((x + w / 2.0, y + h / 2.0), transfo)
    k = transfo[0]
    cands = []
    for r in rects:
        if couleur is not None and any(abs(a - b) > 0.03 for a, b in zip(r["fill"], couleur)):
            continue
        rc = _centre(r)
        d = ((rc[0] - c[0]) ** 2 + (rc[1] - c[1]) ** 2) ** 0.5
        if d > tolerance_pt:
            continue
        # même allure (une longueur au moins à 20 % près) : écarte les petits rectangles centrés au même endroit
        if abs(max(r["l"], r["h"]) - k * max(w, h)) > 0.2 * k * max(w, h):
            continue
        cands.append((d, r))
    return min(cands, key=lambda t: t[0])[1] if cands else None


def couleur_rgb(hexa: str) -> tuple[float, float, float] | None:
    """« #424242 » → (0,259, 0,259, 0,259)."""
    if not hexa or not hexa.startswith("#") or len(hexa) != 7:
        return None
    return tuple(int(hexa[i:i + 2], 16) / 255.0 for i in (1, 3, 5))


# ======================================================================
# Rendu
# ======================================================================
def pages_attendues(lecture) -> int:
    """Feuilles A4 du PDF de draw.io : 1 pour la page « Plan » (tout doit y tenir) + les feuilles occupées par
    la page « Métré » (draw.io la découpe en feuilles A4 quand ses tableaux dépassent une feuille)."""
    total = 0
    for i, p in enumerate(lecture.pages):
        h = p.get("hauteur_px") or 0.0
        bas = 0.0
        for c in p.get("cellules") or []:
            g = c.get("geometrie")
            if g and not g.get("relative") and c.get("vertex"):
                bas = max(bas, g["y"] + g["height"])
        total += 1 if i == 0 or h <= 0 else max(1, int(-(-(bas - 1e-6) // h)))
    return total


def _lire_memoire(dossier: Path) -> dict:
    chemin = dossier / "rendu.json"
    try:
        d = json.loads(chemin.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _ecrire_memoire(dossier: Path, memoire: dict) -> None:
    (dossier / "rendu.json").write_text(json.dumps(memoire, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8", newline="\n")


def _boite_regle(lecture) -> tuple[float, float, float, float]:
    cell = lecture.brut.get("regle-controle")
    g = cell.get("geometrie") if cell else None
    if not g:
        raise ErreurRendu("plan.drawio sans règle de contrôle (cellule « regle-controle ») : regénérer le plan "
                          "avec generer.py.")
    return (g["x"], g["y"], g["width"], g["height"])


def _mesurer(pdf: Path, boite) -> dict:
    try:
        doc = pymupdf.open(pdf)
    except Exception as exc:  # noqa: BLE001 - PyMuPDF lève des types variés
        raise ErreurRendu(f"PDF illisible ({pdf.name}) : {exc}") from exc
    try:
        if doc.page_count == 0:
            raise ErreurRendu(f"{pdf.name} : aucune page.")
        page = doc[0]
        regle = mesurer_regle(page, boite)
        return {"regle": regle, "pages": doc.page_count, "page_pt": (page.rect.width, page.rect.height)}
    finally:
        doc.close()


def rasteriser(pdf: Path, png: Path, dpi: int = DPI_PNG) -> tuple[int, int]:
    """Page 1 du PDF → PNG à `dpi` (200 dpi = 2 px par px draw.io). Renvoie (largeur, hauteur) en px."""
    _supprimer(png)
    with pymupdf.open(pdf) as doc:
        pix = doc[0].get_pixmap(dpi=dpi)
        pix.save(png)
        return pix.width, pix.height


def rendre(dossier_plan, pdf: bool = True, png: bool = True, voie: str = "auto",
           viewer: str = VIEWER_EN_LIGNE) -> dict:
    """Rend `plan.drawio` du dossier en `plan.pdf` (A4, échelle mesurée) et `plan.png`.

    `voie` : « auto » (draw.io s'il est installé, sinon Edge), « drawio » ou « edge ». Renvoie
    {pdf, png, voie, facteur_s, ecart_pct, regle_pt, pages, png_px, commande, essais, avertissements}.
    `ErreurRendu` si aucun rendu n'est possible ou si la règle de contrôle est introuvable dans le PDF."""
    dossier = Path(dossier_plan)
    src = dossier / "plan.drawio"
    if not src.is_file():
        raise ErreurRendu(f"plan.drawio introuvable dans {dossier} : lancer d'abord generer.py.")
    res = {"pdf": None, "png": None, "voie": None, "facteur_s": None, "ecart_pct": None, "regle_pt": None,
           "pages": None, "png_px": None, "commande": None, "essais": 0, "avertissements": []}
    if not pdf and not png:
        return res
    lecture = drawio.lire(src)
    boite = _boite_regle(lecture)
    cle_page = f"{lecture.page.get('format') or 'A4'}-{lecture.page.get('orientation')}"
    if (lecture.page.get("page_scale") or 1.0) != 1.0:
        raise ErreurRendu(f"plan.drawio a pageScale = {lecture.page.get('page_scale')} : il doit valoir 1 "
                          "(sinon la page PDF n'est plus un A4).")

    exe_drawio = trouver_drawio() if voie in ("auto", "drawio") else None
    edge = trouver_edge() if voie == "edge" or (voie == "auto" and exe_drawio is None) else None
    if voie == "drawio" and exe_drawio is None:
        raise ErreurRendu("draw.io Desktop introuvable (Microsoft Store ou installation classique).")
    if exe_drawio is not None:
        res["voie"] = "drawio"
    elif edge is not None:
        res["voie"] = "edge"
        pourquoi = "voie Edge demandée" if voie == "edge" else "draw.io Desktop introuvable"
        res["avertissements"].append(
            f"Voie de secours ({pourquoi}) : rendu par Edge + viewer diagrams.net en ligne (PDF d'une seule "
            "page : le plan ; la page « Métré » n'est pas imprimée).")
    else:
        raise ErreurRendu("Ni draw.io Desktop ni Edge trouvé : aucun rendu PDF possible. Installer draw.io "
                          "(Microsoft Store) ou ouvrir plan.drawio et l'exporter à la main (PDF, 100 %).")

    memoire = _lire_memoire(dossier)
    facteurs = memoire.setdefault("facteurs", {}).setdefault(res["voie"], {})
    s = float(facteurs.get(cle_page) or 1.0)
    cible = dossier / "plan.pdf" if pdf else dossier / "plan.rendu-temporaire.pdf"
    html_viewer = dossier / "plan.rendu-viewer.html"
    mesure = None
    try:
        for essai in range(1, ESSAIS_CALIBRATION + 1):
            res["essais"] = essai
            if res["voie"] == "drawio":
                commande = exporter_drawio(exe_drawio, src, cible, s)
            else:
                page_html_viewer(src, html_viewer, s, viewer)
                commande = imprimer_edge(edge, html_viewer, cible)
            res["commande"] = subprocess.list2cmdline(commande)
            mesure = _mesurer(cible, boite)
            if mesure["regle"] is None:
                raise ErreurRendu("Règle de contrôle de 100 mm introuvable dans le PDF : le rendu a échoué ou le "
                                  "cartouche a été modifié. Ouvrir plan.pdf pour voir ce qui est sorti.")
            ecart = mesure["regle"]["l"] / REGLE_PT - 1.0
            if abs(ecart) < TOLERANCE_CALIBRATION:
                break
            s = s * REGLE_PT / mesure["regle"]["l"]
        else:
            res["avertissements"].append(
                f"Échelle du PDF non calibrée à 0,05 % après {ESSAIS_CALIBRATION} essais : règle de 100 mm mesurée "
                f"{mesure['regle']['l'] / PT_PAR_MM:.3f} mm. Ne pas utiliser ce PDF pour mesurer.")
    finally:
        html_viewer.unlink(missing_ok=True)

    ecart = mesure["regle"]["l"] / REGLE_PT - 1.0
    res.update(facteur_s=s, ecart_pct=ecart * 100.0, regle_pt=mesure["regle"]["l"], pages=mesure["pages"])
    pw, ph = mesure["page_pt"]
    if abs(pw - lecture.page["largeur_px"] * PT_PAR_PX) > 1.5 or abs(ph - lecture.page["hauteur_px"] * PT_PAR_PX) > 1.5:
        res["avertissements"].append(f"Page PDF de {pw:.2f} × {ph:.2f} pt : ce n'est pas la page A4 attendue.")
    attendues = pages_attendues(lecture) if res["voie"] == "drawio" else 1
    res["pages_attendues"] = attendues
    if mesure["pages"] != attendues:
        res["avertissements"].append(f"PDF de {mesure['pages']} page(s) au lieu de {attendues} : un élément "
                                     "dépasse peut-être de la page « Plan ».")
    if abs(ecart) < TOLERANCE_CALIBRATION:
        facteurs[cle_page] = round(s, 6)
    memoire["dernier"] = {"date": datetime.now().isoformat(timespec="seconds"), "voie": res["voie"],
                          "page": cle_page, "facteur_s": round(s, 6), "ecart_pct": round(ecart * 100.0, 4),
                          "regle_mm": round(mesure["regle"]["l"] / PT_PAR_MM, 3), "essais": res["essais"]}
    _ecrire_memoire(dossier, memoire)
    if png:
        res["png"] = dossier / "plan.png"
        res["png_px"] = rasteriser(cible, res["png"])
    if pdf:
        res["pdf"] = cible
    else:
        cible.unlink(missing_ok=True)
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Rend plan.drawio en plan.pdf (A4, échelle mesurée) et plan.png.")
    ap.add_argument("dossier_plan")
    ap.add_argument("--voie", choices=("auto", "drawio", "edge"), default="auto")
    ap.add_argument("--sans-png", action="store_true")
    a = ap.parse_args(argv)
    try:
        r = rendre(a.dossier_plan, png=not a.sans_png, voie=a.voie)
    except (ErreurRendu, drawio.ErreurLecture) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    print(f"Voie : {r['voie']} ; facteur s = {r['facteur_s']:.6f} ; règle de 100 mm mesurée "
          f"{r['regle_pt'] / PT_PAR_MM:.3f} mm (écart {r['ecart_pct']:+.3f} %) ; {r['essais']} export(s).")
    print(f"PDF : {r['pdf']}  ({r['pages']} page(s))")
    if r["png"]:
        print(f"PNG : {r['png']}  ({r['png_px'][0]} × {r['png_px'][1]} px)")
    for m in r["avertissements"]:
        print(f"Avertissement : {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
