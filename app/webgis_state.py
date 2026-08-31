"""Centralized UI state for the WebGIS interaction shell."""

from __future__ import annotations

from collections.abc import Collection, MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any


SELECTED_YEAR_KEY = "selected_year"
SELECTED_METRIC_KEY = "selected_metric"
SELECTED_SUBBASIN_KEY = "selected_subbasin_id"
VIEW_SCOPE_KEY = "view_scope"
ACTIVE_LAYER_KEY = "active_layer"
LAYER_OPACITY_KEY = "layer_opacity"

OVERALL_SCOPE = "overall"
SUBBASIN_SCOPE = "subbasin"
DEFAULT_ACTIVE_LAYER = "boundary"
DEFAULT_LAYER_OPACITY = 0.7
DEFAULT_METRIC = "水体面积"

SUBBASIN_IDS = frozenset({"SB01", "SB02", "SB03", "SB04", "SB05"})
AVAILABLE_LAYERS = frozenset({DEFAULT_ACTIVE_LAYER})


@dataclass(frozen=True)
class WebGISState:
    """Validated snapshot of the page-level interaction state."""

    selected_year: int
    selected_metric: str
    selected_subbasin_id: str | None
    view_scope: str
    active_layer: str
    layer_opacity: float


def _default_metric(metrics: Collection[str]) -> str:
    if DEFAULT_METRIC in metrics:
        return DEFAULT_METRIC
    return next(iter(metrics))


def initialize_webgis_state(
    session_state: MutableMapping[str, Any],
    years: Sequence[int],
    metrics: Collection[str],
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
    session_state[VIEW_SCOPE_KEY] = (
        SUBBASIN_SCOPE if selected_subbasin else OVERALL_SCOPE
    )

    active_layer = session_state.get(ACTIVE_LAYER_KEY)
    if not isinstance(active_layer, str) or active_layer not in AVAILABLE_LAYERS:
        active_layer = DEFAULT_ACTIVE_LAYER
    session_state[ACTIVE_LAYER_KEY] = active_layer

    try:
        layer_opacity = float(session_state.get(LAYER_OPACITY_KEY))
    except (TypeError, ValueError):
        layer_opacity = DEFAULT_LAYER_OPACITY
    if not 0 <= layer_opacity <= 1:
        layer_opacity = DEFAULT_LAYER_OPACITY
    session_state[LAYER_OPACITY_KEY] = layer_opacity

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
        layer_opacity=float(session_state[LAYER_OPACITY_KEY]),
    )


def select_overall(session_state: MutableMapping[str, Any]) -> None:
    """Switch to the overall study-area view."""
    session_state[SELECTED_SUBBASIN_KEY] = None
    session_state[VIEW_SCOPE_KEY] = OVERALL_SCOPE


def select_subbasin(
    session_state: MutableMapping[str, Any], subbasin_id: str
) -> None:
    """Switch to a validated subbasin selection."""
    if subbasin_id not in SUBBASIN_IDS:
        raise ValueError(f"Unknown subbasin_id: {subbasin_id}")
    session_state[SELECTED_SUBBASIN_KEY] = subbasin_id
    session_state[VIEW_SCOPE_KEY] = SUBBASIN_SCOPE
