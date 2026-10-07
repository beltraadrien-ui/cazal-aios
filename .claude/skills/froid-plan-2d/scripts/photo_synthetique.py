"""Photos synthétiques de feuilles tracées au marqueur (Lot 6 du skill froid-plan-2d) : tests et démonstration.

Part de la feuille rendue (`feuille-<reseau>.png`, 8 px/mm) et de traits connus en mm sur la feuille,
dessine les traits comme un marqueur (épaisseur 1,5 à 3 mm, léger tremblement ± 0,3 mm, encre
translucide), puis simule la prise de vue : homographie aléatoire (inclinaison 5-15°, rotation ± 10°,
échelle), table autour de la feuille, dégradé de lumière, dominante de couleur, flou gaussien, bruit,
JPEG qualité 85. La vérité (traits en mm et en m, longueurs, homographie) est renvoyée avec la photo.

    from photo_synthetique import fabriquer
    jpeg, verite = fabriquer(feuille_png, feuille_json, [[(x, y), (x, y), ...]], graine=3, couleur="rouge")
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np

import feuille as fe

# Transmittance de l'encre (B, G, R) : multipliée au papier là où passe le marqueur.
ENCRES = {
    "rouge": (0.22, 0.16, 0.86),
    "bleu": (0.80, 0.38, 0.12),
    "vert": (0.35, 0.62, 0.12),
    "noir": (0.13, 0.12, 0.12),
}


def _longueur(points) -> float:
    p = np.asarray(points, dtype=float)
    return float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()) if len(p) > 1 else 0.0


def _trembler(points_mm: np.ndarray, rng: np.random.Generator, amplitude_mm: float = 0.3) -> np.ndarray:
    """Densifie la polyligne (pas de 0,5 mm) et la décale perpendiculairement d'un tremblement lisse ≤ amplitude."""
    morceaux, abscisses = [], []
    s0 = 0.0
    for a, b in zip(points_mm[:-1], points_mm[1:]):
        l = float(np.linalg.norm(b - a))
        n = max(2, int(math.ceil(l / 0.5)) + 1)
        t = np.linspace(0, 1, n)
        seg = a + (b - a) * t[:, None]
        nrm = np.array([-(b - a)[1], (b - a)[0]]) / max(l, 1e-9)
        morceaux.append((seg, nrm))
        abscisses.append(s0 + l * t)
        s0 += l
    phases = rng.uniform(0, 2 * math.pi, 3)
    longueurs_onde = rng.uniform(12, 60, 3)
    poids = rng.uniform(0.3, 1.0, 3)
    poids = poids / poids.sum() * amplitude_mm
    sortie = []
    for (seg, nrm), s in zip(morceaux, abscisses):
        bruit = sum(w * np.sin(2 * math.pi * s / lo + ph) for w, lo, ph in zip(poids, longueurs_onde, phases))
        sortie.append(seg + np.outer(np.clip(bruit, -amplitude_mm, amplitude_mm), nrm))
    return np.vstack(sortie)


def _matrice_rotation(axe: np.ndarray, angle: float) -> np.ndarray:
    axe = axe / np.linalg.norm(axe)
    k = np.array([[0, -axe[2], axe[1]], [axe[2], 0, -axe[0]], [-axe[1], axe[0], 0]])
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * k @ k


def fabriquer(feuille_png, feuille_json, traits_mm, graine: int, couleur: str = "rouge", largeur_photo: int = 2000,
              sortie=None, epaisseur_mm: float | None = None, inclinaison_deg: float | None = None,
              rotation_deg: float | None = None, masquer_reperes=(), echelle_impression: float = 1.0,
              qualite_jpeg: int = 85):
    """Fabrique une photo synthétique. Renvoie (chemin_jpeg, verite).

    - traits_mm : liste de polylignes, chacune une liste de (x, y) en mm sur la feuille nominale.
    - masquer_reperes : ids de repères à effacer (tests « repère manquant »).
    - echelle_impression : impression réduite uniformément autour du centre de la page (ex. 0,94 pour
      « ajuster à la page ») ; l'utilisateur trace sur le plan imprimé, donc ses traits sont réduits pareil.
    - verite : traits en mm (feuille nominale) et en m (modèle), longueurs, homographie, coins des repères
      dans la photo (px), paramètres tirés.
    """
    rng = np.random.default_rng(graine)
    infos = json.loads(Path(feuille_json).read_text(encoding="utf-8"))
    ppm = float(infos["px_par_mm"])
    page = tuple(infos["page_mm"])
    base = {"S": infos["S"], "origine_mm": infos["origine_mm"]}
    gris = fe.lire_image(feuille_png)
    if gris is None:
        raise FileNotFoundError(f"feuille introuvable : {feuille_png}")
    if gris.ndim == 3:
        gris = cv2.cvtColor(gris, cv2.COLOR_BGR2GRAY)
    h_px, l_px = gris.shape
    papier = gris.astype(np.float32) / 255.0

    centre_mm = np.array(page, dtype=float) / 2
    k = float(echelle_impression)

    def imprime(p_mm):
        return centre_mm + k * (np.asarray(p_mm, dtype=float) - centre_mm)

    if k != 1.0:
        c_px = fe.mm_vers_px(centre_mm, ppm)
        a = np.array([[k, 0, c_px[0] * (1 - k)], [0, k, c_px[1] * (1 - k)]], dtype=np.float64)
        papier = cv2.warpAffine(papier, a, (l_px, h_px), flags=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=1.0)
    for i in masquer_reperes:
        x0, y0, x1, y1 = infos["reperes"][str(i)]["zone_blanche_mm"]
        p0 = fe.mm_vers_px(imprime([x0, y0]), ppm)
        p1 = fe.mm_vers_px(imprime([x1, y1]), ppm)
        papier[int(p0[1]):int(math.ceil(p1[1])) + 1, int(p0[0]):int(math.ceil(p1[0])) + 1] = 1.0

    # 1. Traits au marqueur (encre translucide, densité légèrement irrégulière)
    ep = float(epaisseur_mm) if epaisseur_mm else float(rng.uniform(1.5, 3.0))
    masque = np.zeros((h_px, l_px), np.uint8)
    for trait in traits_mm:
        pts = _trembler(imprime(trait), rng)
        pts_px = np.round(fe.mm_vers_px(pts, ppm) * 16).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(masque, [pts_px], False, 255, max(1, int(round(ep * k * ppm))), cv2.LINE_AA, shift=4)
    densite = cv2.GaussianBlur(rng.uniform(0.82, 1.0, (h_px // 16 + 1, l_px // 16 + 1)).astype(np.float32), (0, 0), 1.5)
    densite = cv2.resize(densite, (l_px, h_px), interpolation=cv2.INTER_LINEAR)
    alpha = (masque.astype(np.float32) / 255.0) * densite
    encre = np.array(ENCRES[couleur], dtype=np.float32)
    feuille_bgr = np.repeat(papier[:, :, None], 3, axis=2) * (1 - alpha[:, :, None] * (1 - encre))

    # 2. Prise de vue : feuille dans l'espace, caméra à 45 cm, inclinaison + rotation
    l_ph, h_ph = int(largeur_photo), int(round(largeur_photo * 3 / 4))
    incl = math.radians(inclinaison_deg if inclinaison_deg is not None else rng.uniform(5, 15))
    rot = math.radians(rotation_deg if rotation_deg is not None else rng.uniform(-10, 10))
    phi = rng.uniform(0, 2 * math.pi)
    r = _matrice_rotation(np.array([0, 0, 1.0]), rot) @ _matrice_rotation(np.array([math.cos(phi), math.sin(phi), 0.0]), incl)
    coins_mm = np.array([[0, 0], [page[0], 0], [page[0], page[1]], [0, page[1]]], dtype=float)
    p3 = np.hstack([coins_mm - centre_mm, np.zeros((4, 1))]) @ r.T + np.array([0, 0, 450.0])
    proj = p3[:, :2] / p3[:, 2:3]
    occupation = rng.uniform(0.72, 0.86)
    etendue = proj.max(axis=0) - proj.min(axis=0)
    f = occupation * min(l_ph / etendue[0], h_ph / etendue[1])
    decalage = rng.uniform(-0.03, 0.03, 2) * np.array([l_ph, h_ph])
    cible = (proj - (proj.max(axis=0) + proj.min(axis=0)) / 2) * f + np.array([l_ph, h_ph]) / 2 + decalage
    source = fe.mm_vers_px(coins_mm, ppm)
    hom = cv2.getPerspectiveTransform(source.astype(np.float32), cible.astype(np.float32)).astype(np.float64)

    # anti-repliement avant réduction
    echelle_moy = math.sqrt(abs(np.linalg.det(hom[:2, :2]))) / max(1e-9, float(hom[2] @ np.array([l_px / 2, h_px / 2, 1])))
    if echelle_moy < 1:
        feuille_bgr = cv2.GaussianBlur(feuille_bgr, (0, 0), 0.45 / echelle_moy)
    photo = cv2.warpPerspective(feuille_bgr, hom, (l_ph, h_ph), flags=cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    couverture = cv2.warpPerspective(np.ones((h_px, l_px), np.float32), hom, (l_ph, h_ph), flags=cv2.INTER_LINEAR)
    teinte_table = np.array(rng.uniform([0.25, 0.32, 0.42], [0.35, 0.42, 0.55]), dtype=np.float32)
    grain = cv2.GaussianBlur(rng.normal(0, 0.04, (h_ph, l_ph)).astype(np.float32), (0, 0), 3)
    table = teinte_table[None, None, :] * (1 + grain[:, :, None])
    photo = photo * couverture[:, :, None] + table * (1 - couverture[:, :, None])

    # 3. Lumière : dégradé + dominante, flou, bruit
    yy, xx = np.mgrid[0:h_ph, 0:l_ph].astype(np.float32)
    theta = rng.uniform(0, 2 * math.pi)
    u = (xx - l_ph / 2) * math.cos(theta) + (yy - h_ph / 2) * math.sin(theta)
    u /= float(np.abs(u).max())
    gain = rng.uniform(0.82, 0.98) * (1 + rng.uniform(0.08, 0.18) * u)
    dominante = np.array(rng.uniform(0.92, 1.04, 3), dtype=np.float32)
    photo = photo * gain[:, :, None] * dominante[None, None, :]
    photo = cv2.GaussianBlur(photo, (0, 0), float(rng.uniform(0.6, 1.1)))
    photo = photo + rng.normal(0, rng.uniform(2.0, 5.0) / 255.0, photo.shape).astype(np.float32)
    photo8 = np.clip(photo * 255 + 0.5, 0, 255).astype(np.uint8)

    if sortie is None:
        sortie = Path(feuille_png).resolve().parent.parent / "photos" / f"synthetique-{graine}-{couleur}.jpg"
    sortie = Path(sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    ok, tampon = cv2.imencode(".jpg", photo8, [cv2.IMWRITE_JPEG_QUALITY, int(qualite_jpeg)])
    if not ok:
        raise RuntimeError("échec d'encodage JPEG")
    tampon.tofile(str(sortie))

    traits_m = [fe.mm_vers_m(np.asarray(t, dtype=float), base) for t in traits_mm]
    reperes_photo = {}
    for i, rep in infos["reperes"].items():
        pts = fe.mm_vers_px(imprime(rep["coins_mm"]), ppm).reshape(-1, 1, 2)
        reperes_photo[i] = cv2.perspectiveTransform(pts, hom).reshape(4, 2).tolist()
    verite = {
        "graine": graine, "couleur": couleur, "epaisseur_mm": round(ep, 3),
        "inclinaison_deg": round(math.degrees(incl), 3), "rotation_deg": round(math.degrees(rot), 3),
        "echelle_impression": k,
        "traits_mm": [np.asarray(t, dtype=float).tolist() for t in traits_mm],
        "traits_m": [t.round(6).tolist() for t in traits_m],
        "longueurs_mm": [round(_longueur(t), 4) for t in traits_mm],
        "longueurs_m": [round(_longueur(t), 4) for t in traits_m],
        "longueur_totale_m": round(sum(_longueur(t) for t in traits_m), 4),
        "homographie_feuille_px_vers_photo": hom.tolist(),
        "reperes_photo_px": reperes_photo,
        "photo_px": [l_ph, h_ph],
    }
    return str(sortie), verite
