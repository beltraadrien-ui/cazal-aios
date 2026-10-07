"""Géométrie plane de base, fonctions pures sur des tuples ou des listes (mètres ou pixels, peu importe).

Repère : x vers la droite, y vers le bas (celui du modèle `plan.json` et de draw.io). Un angle positif
tourne dans le sens des aiguilles d'une montre À L'ÉCRAN : c'est la convention de l'attribut `rotation`
de draw.io (rotation de 90 : la droite (1, 0) devient le bas (0, 1)).

Fonctions : distance, longueur_polyligne, segments, projection_point_segment, distance_point_segment,
distance_point_polyligne, intersection_segments, point_dans_polygone, distance_point_polygone,
boite_englobante, union_boites, boites_se_chevauchent, rotation_point, rotation_vecteur,
rotation_rectangle, surface_polygone, centroide_polygone, est_rectangle_aligne, angle_deg,
normaliser_angle.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

EPS = 1e-12

Point = Sequence[float]


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def segments(points: Sequence[Point]) -> list[tuple[Point, Point]]:
    """Segments consécutifs d'une polyligne : [(p0, p1), (p1, p2), …]."""
    return [(points[i], points[i + 1]) for i in range(len(points) - 1)]


def longueur_polyligne(points: Sequence[Point]) -> float:
    """Longueur totale d'une polyligne (0 pour moins de deux points)."""
    return sum(distance(a, b) for a, b in segments(points))


def projection_point_segment(p: Point, a: Point, b: Point) -> tuple[tuple[float, float], float]:
    """Projection de p sur le segment [a, b] : (point projeté, paramètre t ∈ [0, 1])."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    if l2 < EPS:
        return (float(a[0]), float(a[1])), 0.0
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2
    t = max(0.0, min(1.0, t))
    return (a[0] + t * dx, a[1] + t * dy), t


def distance_point_segment(p: Point, a: Point, b: Point) -> float:
    q, _ = projection_point_segment(p, a, b)
    return distance(p, q)


def distance_point_polyligne(p: Point, points: Sequence[Point]) -> float:
    if len(points) == 1:
        return distance(p, points[0])
    return min(distance_point_segment(p, a, b) for a, b in segments(points))


def _vectoriel(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def intersection_segments(a: Point, b: Point, c: Point, d: Point,
                          tolerance_extremite: float = 0.0) -> tuple[float, float] | None:
    """Point d'intersection PROPRE des segments [a, b] et [c, d], ou None.

    « Propre » : les segments se coupent, et le point est à plus de `tolerance_extremite` de chacune des
    quatre extrémités (avec 0, un simple contact en bout de segment ne compte pas). Segments parallèles ou
    colinéaires (même superposés) : None.
    """
    rx, ry = b[0] - a[0], b[1] - a[1]
    sx, sy = d[0] - c[0], d[1] - c[1]
    denom = _vectoriel(rx, ry, sx, sy)
    if abs(denom) < EPS:
        return None
    qx, qy = c[0] - a[0], c[1] - a[1]
    t = _vectoriel(qx, qy, sx, sy) / denom
    u = _vectoriel(qx, qy, rx, ry) / denom
    if t < -1e-12 or t > 1 + 1e-12 or u < -1e-12 or u > 1 + 1e-12:
        return None
    p = (a[0] + t * rx, a[1] + t * ry)
    if min(distance(p, e) for e in (a, b, c, d)) <= tolerance_extremite + 1e-12:
        return None
    return p


def point_dans_polygone(p: Point, polygone: Sequence[Point], bord: bool = True) -> bool:
    """Vrai si p est dans le polygone (lancer de rayon). `bord` : un point sur un côté compte comme dedans."""
    n = len(polygone)
    if n < 3:
        return False
    for i in range(n):
        if distance_point_segment(p, polygone[i], polygone[(i + 1) % n]) <= 1e-9:
            return bord
    x, y = p[0], p[1]
    dedans = False
    for i in range(n):
        x1, y1 = polygone[i]
        x2, y2 = polygone[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xi:
                dedans = not dedans
    return dedans


def distance_point_polygone(p: Point, polygone: Sequence[Point]) -> float:
    """0 si p est dans le polygone (bord compris), sinon distance au côté le plus proche."""
    if point_dans_polygone(p, polygone):
        return 0.0
    n = len(polygone)
    return min(distance_point_segment(p, polygone[i], polygone[(i + 1) % n]) for i in range(n))


def boite_englobante(points: Iterable[Point]) -> tuple[float, float, float, float]:
    """(xmin, ymin, xmax, ymax) d'un ensemble de points ; ValueError s'il est vide."""
    pts = list(points)
    if not pts:
        raise ValueError("boîte englobante d'un ensemble vide")
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def union_boites(boites: Iterable[Sequence[float]]) -> tuple[float, float, float, float]:
    bs = list(boites)
    if not bs:
        raise ValueError("union d'aucune boîte")
    return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))


def boites_se_chevauchent(b1: Sequence[float], b2: Sequence[float], marge: float = 0.0) -> bool:
    """Vrai si les boîtes (xmin, ymin, xmax, ymax) se recouvrent sur une surface non nulle (au-delà de `marge`)."""
    return (min(b1[2], b2[2]) - max(b1[0], b2[0]) > marge and min(b1[3], b2[3]) - max(b1[1], b2[1]) > marge)


def rotation_vecteur(v: Point, angle_deg_: float) -> tuple[float, float]:
    """Tourne un vecteur de `angle_deg_` (sens horaire à l'écran, convention draw.io)."""
    a = math.radians(angle_deg_)
    c, s = math.cos(a), math.sin(a)
    # Valeurs exactes pour les quarts de tour (évite 6e-17 au lieu de 0).
    if abs(round(angle_deg_) - angle_deg_) < 1e-12 and int(round(angle_deg_)) % 90 == 0:
        k = (int(round(angle_deg_)) // 90) % 4
        c, s = ((1, 0), (0, 1), (-1, 0), (0, -1))[k]
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)


def rotation_point(p: Point, centre: Point, angle_deg_: float) -> tuple[float, float]:
    """Tourne p autour de `centre` (sens horaire à l'écran pour un angle positif)."""
    vx, vy = rotation_vecteur((p[0] - centre[0], p[1] - centre[1]), angle_deg_)
    return (centre[0] + vx, centre[1] + vy)


def rotation_rectangle(centre: Point, dimensions: Sequence[float], angle_deg_: float) -> list[tuple[float, float]]:
    """Quatre coins d'un rectangle (longueur × profondeur) centré en `centre` et tourné de `angle_deg_`.

    Ordre : coins haut-gauche, haut-droit, bas-droit, bas-gauche du rectangle AVANT rotation.
    """
    l, p = dimensions[0] / 2.0, dimensions[1] / 2.0
    return [rotation_point((centre[0] + dx, centre[1] + dy), centre, angle_deg_)
            for dx, dy in ((-l, -p), (l, -p), (l, p), (-l, p))]


def surface_polygone(polygone: Sequence[Point]) -> float:
    """Aire (formule du lacet), toujours positive."""
    n = len(polygone)
    s = 0.0
    for i in range(n):
        x1, y1 = polygone[i]
        x2, y2 = polygone[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def centroide_polygone(polygone: Sequence[Point]) -> tuple[float, float]:
    """Centre de gravité d'un polygone simple (moyenne des sommets s'il est dégénéré)."""
    n = len(polygone)
    a = 0.0
    cx = cy = 0.0
    for i in range(n):
        x1, y1 = polygone[i]
        x2, y2 = polygone[(i + 1) % n]
        f = x1 * y2 - x2 * y1
        a += f
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    if abs(a) < EPS:
        return (sum(p[0] for p in polygone) / n, sum(p[1] for p in polygone) / n)
    return (cx / (3.0 * a), cy / (3.0 * a))


def est_rectangle_aligne(polygone: Sequence[Point], tolerance: float = 1e-6) -> bool:
    """Vrai si le polygone est un rectangle de surface non nulle aux côtés horizontaux et verticaux."""
    if len(polygone) != 4:
        return False
    xs = sorted({round(p[0] / tolerance) for p in polygone})
    ys = sorted({round(p[1] / tolerance) for p in polygone})
    if len(xs) != 2 or len(ys) != 2:
        return False
    for i in range(4):
        a, b = polygone[i], polygone[(i + 1) % 4]
        if abs(a[0] - b[0]) > tolerance and abs(a[1] - b[1]) > tolerance:
            return False
    return True


def angle_deg(a: Point, b: Point) -> float:
    """Direction de a vers b en degrés dans [0, 360) (0 = vers la droite, 90 = vers le bas)."""
    return normaliser_angle(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])))


def normaliser_angle(angle: float) -> float:
    """Ramène un angle dans [0, 360)."""
    a = math.fmod(float(angle), 360.0)
    if a < 0:
        a += 360.0
    if abs(a - 360.0) < 1e-9:
        a = 0.0
    return a
