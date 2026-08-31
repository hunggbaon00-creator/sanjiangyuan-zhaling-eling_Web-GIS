"""Registry and data preparation for the WebGIS layer system."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class BasemapDefinition:
    id: str
    label: str
    tiles: str
    attribution: str | None = None


@dataclass(frozen=True)
class LayerDefinition:
    id: str
    label: str
    source_kind: str
    column: str | None
    unit: str
    colors: tuple[str, ...]
    decimals: int
    fixed_minimum: float | None = None
    fixed_maximum: float | None = None


@dataclass(frozen=True)
class LayerContext:
    definition: LayerDefinition
    year: int
    values: Mapping[str, float]
    minimum: float | None
    maximum: float | None

    @property
    def is_thematic(self) -> bool:
        return self.definition.source_kind == "annual_statistics"

    @property
    def range_label(self) -> str | None:
        if self.minimum is None or self.maximum is None:
            return None
        decimals = self.definition.decimals
        unit = f" {self.definition.unit}" if self.definition.unit else ""
        return (
            f"{self.minimum:.{decimals}f}—"
            f"{self.maximum:.{decimals}f}{unit}"
        )


BASEMAPS = MappingProxyType(
    {
        "osm": BasemapDefinition(
            id="osm",
            label="OpenStreetMap",
            tiles="OpenStreetMap",
        ),
        "terrain": BasemapDefinition(
            id="terrain",
            label="地形图",
            tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
            attribution=(
                "Map data © OpenStreetMap contributors, SRTM | "
                "Map style © OpenTopoMap"
            ),
        ),
    }
)

BUSINESS_LAYERS = MappingProxyType(
    {
        "boundary": LayerDefinition(
            id="boundary",
            label="五子流域边界",
            source_kind="boundary",
            column=None,
            unit="",
            colors=(),
            decimals=0,
        ),
        "water_area": LayerDefinition(
            id="water_area",
            label="子流域水体面积",
            source_kind="annual_statistics",
            column="water_area_km2",
            unit="km²",
            colors=("#F7FBFF", "#6BAED6", "#08306B"),
            decimals=2,
        ),
        "ndvi": LayerDefinition(
            id="ndvi",
            label="子流域NDVI均值",
            source_kind="annual_statistics",
            column="ndvi_mean",
            unit="",
            colors=("#8C510A", "#F6E8C3", "#66BD63", "#006837"),
            decimals=4,
        ),
        "mndwi": LayerDefinition(
            id="mndwi",
            label="子流域MNDWI均值",
            source_kind="annual_statistics",
            column="mndwi_mean",
            unit="",
            colors=("#8C510A", "#F7F7F7", "#67A9CF", "#2166AC"),
            decimals=4,
        ),
        "coverage": LayerDefinition(
            id="coverage",
            label="子流域有效覆盖率",
            source_kind="annual_statistics",
            column="valid_share",
            unit="",
            colors=("#D73027", "#FEE08B", "#1A9850"),
            decimals=2,
            fixed_minimum=0.0,
            fixed_maximum=1.0,
        ),
    }
)

DEFAULT_BASEMAP_ID = "osm"
DEFAULT_LAYER_ID = "boundary"
BASEMAP_IDS = frozenset(BASEMAPS)
LAYER_IDS = frozenset(BUSINESS_LAYERS)
EXPECTED_SUBBASIN_IDS = frozenset({"SB01", "SB02", "SB03", "SB04", "SB05"})


def resolve_layer_context(
    layer_id: str,
    subbasin_data: pd.DataFrame,
    selected_year: int,
) -> LayerContext:
    """Resolve values and a stable color domain for one business layer."""
    if layer_id not in BUSINESS_LAYERS:
        raise ValueError(f"未知业务图层：{layer_id}")
    definition = BUSINESS_LAYERS[layer_id]
    if definition.source_kind == "boundary":
        return LayerContext(
            definition=definition,
            year=int(selected_year),
            values=MappingProxyType({}),
            minimum=None,
            maximum=None,
        )

    column = definition.column
    if column is None or column not in subbasin_data.columns:
        raise ValueError(f"图层字段不可用：{column}")
    selected = subbasin_data.loc[
        subbasin_data["year"] == selected_year, ["subbasin_id", column]
    ].copy()
    if len(selected) != 5 or set(selected["subbasin_id"]) != EXPECTED_SUBBASIN_IDS:
        raise ValueError(f"{selected_year}年图层数据未覆盖SB01—SB05。")
    if selected["subbasin_id"].duplicated().any():
        raise ValueError(f"{selected_year}年图层数据存在重复分区。")
    selected[column] = pd.to_numeric(selected[column], errors="raise")
    if selected[column].isna().any():
        raise ValueError(f"{selected_year}年图层字段存在缺失值：{column}")

    all_values = pd.to_numeric(subbasin_data[column], errors="raise")
    minimum = (
        definition.fixed_minimum
        if definition.fixed_minimum is not None
        else float(all_values.min())
    )
    maximum = (
        definition.fixed_maximum
        if definition.fixed_maximum is not None
        else float(all_values.max())
    )
    if minimum == maximum:
        maximum = minimum + 1.0

    values = {
        str(row.subbasin_id): float(getattr(row, column))
        for row in selected.itertuples(index=False)
    }
    return LayerContext(
        definition=definition,
        year=int(selected_year),
        values=MappingProxyType(values),
        minimum=minimum,
        maximum=maximum,
    )


def enrich_boundary_with_year_stats(
    boundary: dict[str, Any],
    subbasin_data: pd.DataFrame,
    selected_year: int,
) -> dict[str, Any]:
    """Attach the selected year's formal statistics to boundary tooltips."""
    required_columns = {
        "subbasin_id",
        "year",
        "water_area_km2",
        "ndvi_mean",
        "mndwi_mean",
        "valid_share",
        "coverage_flag",
    }
    missing_columns = required_columns.difference(subbasin_data.columns)
    if missing_columns:
        missing = "、".join(sorted(missing_columns))
        raise ValueError(f"图层Tooltip缺少字段：{missing}")

    selected = subbasin_data.loc[subbasin_data["year"] == selected_year].copy()
    if len(selected) != 5 or set(selected["subbasin_id"]) != EXPECTED_SUBBASIN_IDS:
        raise ValueError(f"{selected_year}年Tooltip数据未覆盖SB01—SB05。")
    rows = selected.set_index("subbasin_id").to_dict("index")
    enriched = deepcopy(boundary)
    coverage_labels = {"high": "高", "medium": "中", "low": "低"}

    for feature in enriched.get("features", []):
        properties = feature.setdefault("properties", {})
        subbasin_id = properties.get("subbasin_id")
        if subbasin_id not in rows:
            raise ValueError(f"边界分区缺少年度统计：{subbasin_id}")
        row = rows[subbasin_id]
        properties.update(
            {
                "stats_year": int(selected_year),
                "stats_water_area_km2": float(row["water_area_km2"]),
                "stats_ndvi_mean": float(row["ndvi_mean"]),
                "stats_mndwi_mean": float(row["mndwi_mean"]),
                "stats_valid_share_pct": float(row["valid_share"]) * 100,
                "stats_coverage_label": coverage_labels.get(
                    str(row["coverage_flag"]), str(row["coverage_flag"])
                ),
            }
        )
    return enriched
