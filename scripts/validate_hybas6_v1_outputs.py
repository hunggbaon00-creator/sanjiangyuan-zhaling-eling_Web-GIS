"""Validate the complete hybas6_v1_t000 promotion bundle."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

import pandas as pd


EXPECTED_SUBBASINS = {
    "SB01": (4060614190, 4060620840),
    "SB02": (4060614330, 4060620840),
    "SB03": (4060620840, 4060628060),
    "SB04": (4060621070, 4060628060),
    "SB05": (4060628060, 4060660740),
}
OVERALL_FIELDS = {
    "year",
    "image_count",
    "roi_area_km2",
    "valid_area_km2",
    "valid_share",
    "coverage_flag",
    "ndvi_mean",
    "mndwi_mean",
    "water_area_km2",
    "water_threshold",
    "roi_version",
    "statistics_scale_m",
}
SUBBASIN_FIELDS = {
    "year",
    "image_count",
    "subbasin_id",
    "subbasin_name",
    "hybas_id",
    "next_down",
    "subbasin_area_km2",
    "valid_area_km2",
    "valid_share",
    "coverage_flag",
    "ndvi_mean",
    "mndwi_mean",
    "water_area_km2",
    "water_threshold",
    "roi_version",
    "statistics_scale_m",
}
YEARS = list(range(2018, 2025))
BOUNDARY_FIELDS = {
    "roi_id",
    "roi_version",
    "subbasin_id",
    "name_cn",
    "name_en",
    "hybas_id",
    "next_down",
    "pfaf_id",
    "area_km2",
    "hybas_level",
    "source",
    "source_asset",
    "source_version",
    "boundary_type",
}
REFERENCE_POINTS = {
    "Zhaling Lake": ((97.32, 34.93), "SB03"),
    "Eling Lake": ((97.70, 34.86), "SB05"),
}
THRESHOLDS = [-0.1, 0.0, 0.1, 0.2]


def expected_coverage(valid_share: float) -> str:
    if valid_share >= 0.95:
        return "high"
    if valid_share >= 0.80:
        return "medium"
    return "low"


def geometry_polygons(geometry: dict) -> Iterable[list]:
    if geometry["type"] == "Polygon":
        yield geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        yield from geometry["coordinates"]
    else:
        raise AssertionError(f"Unsupported geometry type: {geometry['type']}")


def ring_contains(ring: list, point: tuple[float, float]) -> bool:
    x, y = point
    inside = False
    for first, second in zip(ring, ring[1:]):
        x1, y1 = first
        x2, y2 = second
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
    return inside


def geometry_contains(geometry: dict, point: tuple[float, float]) -> bool:
    for polygon in geometry_polygons(geometry):
        if ring_contains(polygon[0], point) and not any(
            ring_contains(hole, point) for hole in polygon[1:]
        ):
            return True
    return False


def normalized_edge(first: list, second: list) -> tuple:
    # GEE's GeoJSON writer can differ at the 12th decimal place between a
    # dissolved geometry and the original features. Nine decimals is still
    # well below the 0.001 km² equivalence tolerance at this latitude.
    endpoints = (
        (round(float(first[0]), 9), round(float(first[1]), 9)),
        (round(float(second[0]), 9), round(float(second[1]), 9)),
    )
    return tuple(sorted(endpoints))


def geometry_edges(features: list[dict]) -> Counter:
    edges: Counter = Counter()
    for feature in features:
        for polygon in geometry_polygons(feature["geometry"]):
            for ring in polygon:
                for first, second in zip(ring, ring[1:]):
                    edges[normalized_edge(first, second)] += 1
    return edges


def validate_boundary(path: Path, baseline_path: Path) -> None:
    boundary = json.loads(path.read_text(encoding="utf-8"))
    assert boundary.get("type") == "FeatureCollection"
    features = boundary.get("features", [])
    assert len(features) == 5, f"Expected 5 boundary features, got {len(features)}"
    assert all(feature.get("geometry") for feature in features)
    assert all(
        BOUNDARY_FIELDS <= set(feature.get("properties", {}))
        for feature in features
    )
    properties = {
        feature["properties"]["subbasin_id"]: feature["properties"]
        for feature in features
    }
    assert set(properties) == set(EXPECTED_SUBBASINS)
    for subbasin_id, (hybas_id, next_down) in EXPECTED_SUBBASINS.items():
        item = properties[subbasin_id]
        assert int(item["hybas_id"]) == hybas_id
        assert int(item["next_down"]) == next_down
        assert item["roi_version"] == "hybas6_v1"
        assert int(item["hybas_level"]) == 6
        assert item["source"] == "HydroBASINS"
        assert item["source_version"] == "v1c"
        assert item["boundary_type"] == "hydrobasins_subbasin"
        assert float(item["area_km2"]) > 0

    for label, (point, expected_subbasin) in REFERENCE_POINTS.items():
        matches = [
            feature["properties"]["subbasin_id"]
            for feature in features
            if geometry_contains(feature["geometry"], point)
        ]
        assert matches == [expected_subbasin], f"{label}: {matches}"

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_features = baseline.get("features", [])
    assert len(baseline_features) == 1
    candidate_edges = geometry_edges(features)
    candidate_exterior = Counter(
        {edge: count for edge, count in candidate_edges.items() if count % 2}
    )
    baseline_edges = geometry_edges(baseline_features)
    assert candidate_exterior == baseline_edges, (
        "The five-feature exterior does not match the v0 dissolved boundary"
    )
    candidate_area = sum(
        float(feature["properties"]["area_km2"]) for feature in features
    )
    baseline_area = float(baseline_features[0]["properties"]["area_km2"])
    assert abs(candidate_area - baseline_area) <= 0.001


def validate_common(data: pd.DataFrame, area_column: str) -> None:
    assert not data.isna().any().any(), "Candidate data contains null values"
    assert set(data["roi_version"]) == {"hybas6_v1"}
    assert set(data["water_threshold"].astype(float)) == {0.0}
    assert set(data["statistics_scale_m"].astype(int)) == {20}
    assert data["valid_share"].between(0, 1).all()
    assert data["ndvi_mean"].between(-1, 1).all()
    assert data["mndwi_mean"].between(-1, 1).all()
    assert (data["water_area_km2"] >= 0).all()
    assert (data["water_area_km2"] <= data["valid_area_km2"]).all()
    assert (data["valid_area_km2"] <= data[area_column] + 1e-6).all()
    share_error = (
        data["valid_share"]
        - data["valid_area_km2"] / data[area_column]
    ).abs()
    assert (share_error <= 1e-9).all()
    expected_flags = data["valid_share"].map(expected_coverage)
    assert (data["coverage_flag"] == expected_flags).all()


def validate_overall(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    assert OVERALL_FIELDS <= set(data.columns)
    assert len(data) == 7
    assert data["year"].astype(int).tolist() == YEARS
    assert data["year"].is_unique
    validate_common(data, "roi_area_km2")
    return data.sort_values("year").reset_index(drop=True)


def validate_subbasins(path: Path) -> pd.DataFrame:
    data = pd.read_csv(path)
    assert SUBBASIN_FIELDS <= set(data.columns)
    assert len(data) == 35
    assert not data.duplicated(["year", "subbasin_id"]).any()
    assert set(data["year"].astype(int)) == set(YEARS)
    assert set(data["subbasin_id"]) == set(EXPECTED_SUBBASINS)
    for subbasin_id, (hybas_id, next_down) in EXPECTED_SUBBASINS.items():
        subset = data[data["subbasin_id"] == subbasin_id]
        assert set(subset["hybas_id"].astype(int)) == {hybas_id}
        assert set(subset["next_down"].astype(int)) == {next_down}
    validate_common(data, "subbasin_area_km2")
    return data.sort_values(["year", "subbasin_id"]).reset_index(drop=True)


def validate_regression(candidate: pd.DataFrame, baseline_path: Path) -> None:
    baseline = pd.read_csv(baseline_path).sort_values("year").reset_index(drop=True)
    assert baseline["year"].astype(int).tolist() == YEARS
    assert (candidate["image_count"].astype(int) == baseline["image_count"].astype(int)).all()
    assert (candidate["coverage_flag"] == baseline["coverage_flag"]).all()
    for column in ["roi_area_km2", "valid_area_km2", "water_area_km2"]:
        assert ((candidate[column] - baseline[column]).abs() <= 0.01).all(), column
    for column in ["ndvi_mean", "mndwi_mean"]:
        assert ((candidate[column] - baseline[column]).abs() <= 1e-6).all(), column


def validate_partition_sums(
    overall: pd.DataFrame, subbasins: pd.DataFrame
) -> None:
    grouped = subbasins.groupby("year", as_index=False).agg(
        roi_area_km2=("subbasin_area_km2", "sum"),
        valid_area_km2=("valid_area_km2", "sum"),
        water_area_km2=("water_area_km2", "sum"),
    )
    merged = overall.merge(grouped, on="year", suffixes=("_overall", "_parts"))
    for column in ["roi_area_km2", "valid_area_km2", "water_area_km2"]:
        relative_error = (
            merged[f"{column}_parts"] - merged[f"{column}_overall"]
        ).abs() / merged[f"{column}_overall"]
        assert (relative_error <= 0.001).all(), column


def validate_thresholds(path: Path, overall: pd.DataFrame) -> dict[str, float]:
    data = pd.read_csv(path).sort_values("threshold").reset_index(drop=True)
    required = {
        "year",
        "threshold",
        "image_count",
        "water_area_km2",
        "area_difference_from_t010_km2",
        "worldcover_water_coverage",
        "worldcover_overlap_share",
        "roi_version",
        "scale_m",
    }
    assert required <= set(data.columns)
    assert len(data) == 4
    assert not data[sorted(required)].isna().any().any()
    assert data["threshold"].astype(float).tolist() == THRESHOLDS
    assert set(data["year"].astype(int)) == {2021}
    assert set(data["roi_version"]) == {"hybas6_v1"}
    assert set(data["scale_m"].astype(int)) == {20}
    assert data["water_area_km2"].is_monotonic_decreasing
    assert data["worldcover_water_coverage"].is_monotonic_decreasing
    assert data["worldcover_overlap_share"].is_monotonic_increasing
    assert data["worldcover_water_coverage"].between(0, 1).all()
    assert data["worldcover_overlap_share"].between(0, 1).all()

    t010_area = data.loc[data["threshold"] == 0.1, "water_area_km2"].iloc[0]
    difference_error = (
        data["area_difference_from_t010_km2"]
        - (data["water_area_km2"] - t010_area)
    ).abs()
    assert (difference_error <= 1e-9).all()

    threshold_t000 = data.loc[data["threshold"] == 0.0].iloc[0]
    annual_2021 = overall.loc[overall["year"] == 2021].iloc[0]
    assert int(threshold_t000["image_count"]) == int(annual_2021["image_count"])
    t000_area_error = abs(
        float(threshold_t000["water_area_km2"])
        - float(annual_2021["water_area_km2"])
    )
    assert t000_area_error <= 0.01
    return {
        "t000_area_error_km2": t000_area_error,
        "t000_worldcover_coverage": float(
            threshold_t000["worldcover_water_coverage"]
        ),
        "t000_worldcover_overlap_share": float(
            threshold_t000["worldcover_overlap_share"]
        ),
    }


def validate_cross_sensor(
    path: Path, baseline_path: Path
) -> dict[str, float]:
    candidate = pd.read_csv(path)
    baseline = pd.read_csv(baseline_path)
    assert len(candidate) == len(baseline) == 1
    assert not candidate.isna().any().any()
    row = candidate.iloc[0]
    assert int(row["year"]) == 2018
    assert float(row["s2_threshold"]) == 0.0
    assert float(row["l8_threshold"]) == 0.0
    assert row["roi_version"] == "hybas6_v1"
    assert int(row["comparison_scale_m"]) == 30
    for column in [
        "s2_valid_share",
        "l8_valid_share",
        "common_valid_share",
        "iou",
        "dice",
        "l8_gapfill_addition_vs_s2_share",
    ]:
        assert 0 <= float(row[column]) <= 1

    common_columns = sorted(
        (set(candidate.columns) & set(baseline.columns)) - {"roi_version"}
    )
    numeric_columns = [
        column
        for column in common_columns
        if pd.api.types.is_numeric_dtype(candidate[column])
        and pd.api.types.is_numeric_dtype(baseline[column])
    ]
    max_regression_error = max(
        abs(float(candidate.iloc[0][column]) - float(baseline.iloc[0][column]))
        for column in numeric_columns
    )
    assert max_regression_error <= 1e-8
    return {
        "max_regression_error": max_regression_error,
        "s2_valid_share": float(row["s2_valid_share"]),
        "l8_valid_share": float(row["l8_valid_share"]),
        "iou": float(row["iou"]),
        "dice": float(row["dice"]),
        "gapfill_addition_share": float(
            row["l8_gapfill_addition_vs_s2_share"]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boundary", type=Path, required=True)
    parser.add_argument("--baseline-boundary", type=Path, required=True)
    parser.add_argument("--overall", type=Path, required=True)
    parser.add_argument("--subbasins", type=Path, required=True)
    parser.add_argument("--baseline-overall", type=Path, required=True)
    parser.add_argument("--threshold-validation", type=Path, required=True)
    parser.add_argument("--cross-validation", type=Path, required=True)
    parser.add_argument("--baseline-cross-validation", type=Path, required=True)
    args = parser.parse_args()

    validate_boundary(args.boundary, args.baseline_boundary)
    overall = validate_overall(args.overall)
    subbasins = validate_subbasins(args.subbasins)
    validate_regression(overall, args.baseline_overall)
    validate_partition_sums(overall, subbasins)
    threshold_metrics = validate_thresholds(args.threshold_validation, overall)
    cross_metrics = validate_cross_sensor(
        args.cross_validation, args.baseline_cross_validation
    )
    print("hybas6_v1_t000 promotion validation: OK")
    print(
        "threshold t000 annual area error (km2): "
        f"{threshold_metrics['t000_area_error_km2']:.12g}"
    )
    print(
        "cross-sensor maximum v0/v1 regression error: "
        f"{cross_metrics['max_regression_error']:.12g}"
    )


if __name__ == "__main__":
    main()
