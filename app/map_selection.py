"""Pure helpers for translating map clicks into subbasin selections."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any


OUTSIDE = 0
INSIDE = 1
BOUNDARY = 2
COORDINATE_EPSILON = 1e-10


def extract_map_click(
    map_result: Mapping[str, Any] | None,
) -> tuple[float, float] | None:
    """Return a validated ``(longitude, latitude)`` map click."""
    if not isinstance(map_result, Mapping):
        return None
    clicked = map_result.get("last_object_clicked")
    if not isinstance(clicked, Mapping):
        return None

    longitude = clicked.get("lng")
    latitude = clicked.get("lat")
    if (
        isinstance(longitude, bool)
        or isinstance(latitude, bool)
        or not isinstance(longitude, Real)
        or not isinstance(latitude, Real)
    ):
        return None

    longitude = float(longitude)
    latitude = float(latitude)
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        return None
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        return None
    return longitude, latitude


def _point_on_segment(
    x: float,
    y: float,
    start: Sequence[float],
    end: Sequence[float],
) -> bool:
    x1, y1 = float(start[0]), float(start[1])
    x2, y2 = float(end[0]), float(end[1])
    cross_product = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
    scale = max(abs(x2 - x1), abs(y2 - y1), 1.0)
    if abs(cross_product) > COORDINATE_EPSILON * scale:
        return False
    return (
        min(x1, x2) - COORDINATE_EPSILON
        <= x
        <= max(x1, x2) + COORDINATE_EPSILON
        and min(y1, y2) - COORDINATE_EPSILON
        <= y
        <= max(y1, y2) + COORDINATE_EPSILON
    )


def _point_in_ring(x: float, y: float, ring: Sequence[Sequence[float]]) -> int:
    if len(ring) < 4:
        return OUTSIDE

    inside = False
    previous = ring[-1]
    for current in ring:
        if _point_on_segment(x, y, previous, current):
            return BOUNDARY

        x1, y1 = float(previous[0]), float(previous[1])
        x2, y2 = float(current[0]), float(current[1])
        if (y1 > y) != (y2 > y):
            intersection_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < intersection_x:
                inside = not inside
        previous = current
    return INSIDE if inside else OUTSIDE


def _point_in_polygon(
    x: float,
    y: float,
    rings: Sequence[Sequence[Sequence[float]]],
) -> int:
    if not rings:
        return OUTSIDE
    exterior_result = _point_in_ring(x, y, rings[0])
    if exterior_result != INSIDE:
        return exterior_result

    for hole in rings[1:]:
        hole_result = _point_in_ring(x, y, hole)
        if hole_result == BOUNDARY:
            return BOUNDARY
        if hole_result == INSIDE:
            return OUTSIDE
    return INSIDE


def _point_in_geometry(x: float, y: float, geometry: Mapping[str, Any]) -> int:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, Sequence):
        return OUTSIDE
    if geometry_type == "Polygon":
        return _point_in_polygon(x, y, coordinates)
    if geometry_type == "MultiPolygon":
        result = OUTSIDE
        for polygon in coordinates:
            polygon_result = _point_in_polygon(x, y, polygon)
            if polygon_result == BOUNDARY:
                return BOUNDARY
            if polygon_result == INSIDE:
                result = INSIDE
        return result
    return OUTSIDE


def find_subbasin_at_point(
    boundary: Mapping[str, Any],
    longitude: float,
    latitude: float,
) -> str | None:
    """Return the unique subbasin containing a longitude/latitude point."""
    matches: list[str] = []
    features = boundary.get("features", [])
    if not isinstance(features, Sequence):
        return None

    for feature in features:
        if not isinstance(feature, Mapping):
            continue
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        if not isinstance(properties, Mapping) or not isinstance(geometry, Mapping):
            continue
        subbasin_id = properties.get("subbasin_id")
        if not isinstance(subbasin_id, str):
            continue
        if _point_in_geometry(longitude, latitude, geometry) != OUTSIDE:
            matches.append(subbasin_id)

    return matches[0] if len(matches) == 1 else None
