"""Centralized UI state for the WebGIS interaction shell."""

from __future__ import annotations

from collections.abc import Collection, MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.layer_system import (
    BASEMAP_IDS,
    DEFAULT_BASEMAP_ID,
    DEFAULT_LAYER_ID,
    LAYER_IDS,
)


SELECTED_YEAR_KEY = "selected_year"
SELECTED_METRIC_KEY = "selected_metric"
SELECTED_SUBBASIN_KEY = "selected_subbasin_id"
SUBBASIN_SELECTOR_KEY = "subbasin_selector"
VIEW_SCOPE_KEY = "view_scope"
ACTIVE_LAYER_KEY = "active_layer"
BASEMAP_KEY = "basemap"
LAYER_OPACITY_KEY = "layer_opacity"
RASTER_LAYER_KEY = "raster_layer_id"
MAP_REVISION_KEY = "map_revision"

OVERALL_SCOPE = "overall"
SUBBASIN_SCOPE = "subbasin"
DEFAULT_ACTIVE_LAYER = DEFAULT_LAYER_ID
DEFAULT_BASEMAP = DEFAULT_BASEMAP_ID
DEFAULT_LAYER_OPACITY = 0.7
DEFAULT_METRIC = "水体面积"

SUBBASIN_IDS = frozenset({"SB01", "SB02", "SB03", "SB04", "SB05"})
AVAILABLE_LAYERS = LAYER_IDS
AVAILABLE_BASEMAPS = BASEMAP_IDS


@dataclass(frozen=True)
class WebGISState:
    """Validated snapshot of the page-level interaction state."""

    selected_year: int
    selected_metric: str
    selected_subbasin_id: str | None
    view_scope: str
    active_layer: str
    basemap: str
    layer_opacity: float
    raster_layer_id: str | None
    map_revision: int


def _default_metric(metrics: Collection[str]) -> str:
    if DEFAULT_METRIC in metrics:
        return DEFAULT_METRIC
    return next(iter(metrics))


def initialize_webgis_state(
    session_state: MutableMapping[str, Any],
    years: Sequence[int],
    metrics: Collection[str],
    raster_layers: Collection[str] = (),
) -> WebGISState:
    """Initialize state defaults and repair stale or invalid selections."""
    normalized_years = sorted({int(year) for year in years})
    normalized_metrics = tuple(metrics)
    if not normalized_years:
        raise ValueError("At least one statistics year is required.")
    if not normalized_metrics:
        raise ValueError("At least one metric is required.")

    selected_year = session_state.get(SELECTED_YEAR_KEY)
    if selected_year not in normalized_years:
        selected_year = normalized_years[-1]
    session_state[SELECTED_YEAR_KEY] = int(selected_year)

    selected_metric = session_state.get(SELECTED_METRIC_KEY)
    if selected_metric not in normalized_metrics:
        selected_metric = _default_metric(normalized_metrics)
    session_state[SELECTED_METRIC_KEY] = str(selected_metric)

    selected_subbasin = session_state.get(SELECTED_SUBBASIN_KEY)
    if (
        not isinstance(selected_subbasin, str)
        or selected_subbasin not in SUBBASIN_IDS
    ):
        selected_subbasin = None
    session_state[SELECTED_SUBBASIN_KEY] = selected_subbasin
    session_state[SUBBASIN_SELECTOR_KEY] = selected_subbasin
    session_state[VIEW_SCOPE_KEY] = (
        SUBBASIN_SCOPE if selected_subbasin else OVERALL_SCOPE
    )

    active_layer = session_state.get(ACTIVE_LAYER_KEY)
    if not isinstance(active_layer, str) or active_layer not in AVAILABLE_LAYERS:
        active_layer = DEFAULT_ACTIVE_LAYER
    session_state[ACTIVE_LAYER_KEY] = active_layer

    basemap = session_state.get(BASEMAP_KEY)
    if not isinstance(basemap, str) or basemap not in AVAILABLE_BASEMAPS:
        basemap = DEFAULT_BASEMAP
    session_state[BASEMAP_KEY] = basemap

    try:
        layer_opacity = float(session_state.get(LAYER_OPACITY_KEY))
    except (TypeError, ValueError):
        layer_opacity = DEFAULT_LAYER_OPACITY
    if not 0 <= layer_opacity <= 1:
        layer_opacity = DEFAULT_LAYER_OPACITY
    session_state[LAYER_OPACITY_KEY] = layer_opacity

    available_raster_layers = frozenset(raster_layers)
    raster_layer_id = session_state.get(RASTER_LAYER_KEY)
    if (
        not isinstance(raster_layer_id, str)
        or raster_layer_id not in available_raster_layers
    ):
        raster_layer_id = None
    session_state[RASTER_LAYER_KEY] = raster_layer_id

    map_revision = session_state.get(MAP_REVISION_KEY)
    if (
        isinstance(map_revision, bool)
        or not isinstance(map_revision, int)
        or map_revision < 0
    ):
        map_revision = 0
    session_state[MAP_REVISION_KEY] = map_revision

    return read_webgis_state(session_state)


def read_webgis_state(
    session_state: MutableMapping[str, Any],
) -> WebGISState:
    """Return the current validated state after initialization."""
    return WebGISState(
        selected_year=int(session_state[SELECTED_YEAR_KEY]),
        selected_metric=str(session_state[SELECTED_METRIC_KEY]),
        selected_subbasin_id=session_state[SELECTED_SUBBASIN_KEY],
        view_scope=str(session_state[VIEW_SCOPE_KEY]),
        active_layer=str(session_state[ACTIVE_LAYER_KEY]),
        basemap=str(session_state[BASEMAP_KEY]),
        layer_opacity=float(session_state[LAYER_OPACITY_KEY]),
        raster_layer_id=session_state[RASTER_LAYER_KEY],
        map_revision=int(session_state[MAP_REVISION_KEY]),
    )


def select_overall(session_state: MutableMapping[str, Any]) -> None:
    """Switch to the overall study-area view."""
    session_state[SELECTED_SUBBASIN_KEY] = None
    session_state[VIEW_SCOPE_KEY] = OVERALL_SCOPE
    _advance_map_revision(session_state)


def select_subbasin(
    session_state: MutableMapping[str, Any], subbasin_id: str
) -> None:
    """Switch to a validated subbasin selection."""
    if subbasin_id not in SUBBASIN_IDS:
        raise ValueError(f"Unknown subbasin_id: {subbasin_id}")
    session_state[SELECTED_SUBBASIN_KEY] = subbasin_id
    session_state[VIEW_SCOPE_KEY] = SUBBASIN_SCOPE


def synchronize_subbasin_selector(
    session_state: MutableMapping[str, Any],
) -> None:
    """Apply a sidebar scope change and discard any stale map click."""
    selected_subbasin = session_state.get(SUBBASIN_SELECTOR_KEY)
    if selected_subbasin is None:
        select_overall(session_state)
        return
    if not isinstance(selected_subbasin, str):
        raise ValueError("Subbasin selector value must be a string or None.")
    select_subbasin(session_state, selected_subbasin)
    _advance_map_revision(session_state)


def _advance_map_revision(session_state: MutableMapping[str, Any]) -> None:
    current_revision = session_state.get(MAP_REVISION_KEY, 0)
    if (
        isinstance(current_revision, bool)
        or not isinstance(current_revision, int)
        or current_revision < 0
    ):
        current_revision = 0
    session_state[MAP_REVISION_KEY] = current_revision + 1
