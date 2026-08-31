"""Offline validation helpers for the deployable WebGIS runtime bundle."""

from __future__ import annotations

import json
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pandas as pd

from app.raster_tiles import load_raster_manifest


EXPECTED_YEARS = set(range(2018, 2025))
EXPECTED_SUBBASINS = {"SB01", "SB02", "SB03", "SB04", "SB05"}
PINNED_REQUIREMENT = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[A-Za-z0-9_.+!-]+)$"
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_pinned_requirements(path: Path) -> dict[str, str]:
    """Read an exact-version requirement file and reject loose entries."""
    _require(path.is_file(), f"依赖锁定文件不存在：{path}")
    requirements: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = PINNED_REQUIREMENT.fullmatch(line)
        _require(
            match is not None,
            f"依赖锁定文件第{line_number}行不是精确版本：{line}",
        )
        name = match.group("name").lower().replace("_", "-")
        _require(name not in requirements, f"依赖重复：{name}")
        requirements[name] = match.group("version")
    _require(bool(requirements), "依赖锁定文件为空。")
    return requirements


def validate_installed_requirements(path: Path) -> int:
    """Ensure the active interpreter matches every pinned package version."""
    requirements = read_pinned_requirements(path)
    mismatches: list[str] = []
    for name, expected in requirements.items():
        try:
            actual = version(name)
        except PackageNotFoundError:
            mismatches.append(f"{name} 未安装")
            continue
        if actual != expected:
            mismatches.append(f"{name}=={actual}，期望{expected}")
    _require(not mismatches, "运行依赖不一致：" + "；".join(mismatches))
    return len(requirements)


def validate_requirement_subset(direct_path: Path, lock_path: Path) -> int:
    """Ensure every direct Web dependency has the same version in the lock."""
    direct = read_pinned_requirements(direct_path)
    locked = read_pinned_requirements(lock_path)
    mismatches = [
        f"{name}=={expected}，锁定为{locked.get(name, '缺失')}"
        for name, expected in direct.items()
        if locked.get(name) != expected
    ]
    _require(not mismatches, "直接依赖与锁定文件不一致：" + "；".join(mismatches))
    return len(direct)


def validate_runtime_bundle(project_root: Path) -> dict[str, int | str]:
    """Validate only files required by the public read-only Web runtime."""
    overall_path = (
        project_root / "data" / "processed" / "zhaling_eling_yearly_stats.csv"
    )
    subbasin_path = (
        project_root
        / "data"
        / "processed"
        / "zhaling_eling_subbasin_yearly_stats.csv"
    )
    boundary_path = (
        project_root
        / "data"
        / "boundaries"
        / "zhaling_eling_watershed_hybas6_v1.geojson"
    )
    manifest_path = project_root / "config" / "raster_layers.json"
    required_paths = [
        overall_path,
        subbasin_path,
        boundary_path,
        manifest_path,
        manifest_path.with_name("raster_layers.schema.json"),
    ]
    missing = [str(path) for path in required_paths if not path.is_file()]
    _require(not missing, "部署文件缺失：" + "；".join(missing))

    overall = pd.read_csv(overall_path)
    _require(len(overall) == 7, "总体统计必须严格为7行。")
    _require(overall["year"].is_unique, "总体统计年份不唯一。")
    _require(
        set(overall["year"].astype(int)) == EXPECTED_YEARS,
        "总体统计年份必须为2018—2024。",
    )
    _require(
        set(overall["roi_version"]) == {"hybas6_v1"},
        "总体统计版本不是hybas6_v1。",
    )
    _require(not overall.isna().any().any(), "总体统计存在空值。")

    subbasins = pd.read_csv(subbasin_path)
    _require(len(subbasins) == 35, "子流域统计必须严格为35行。")
    _require(
        not subbasins.duplicated(["year", "subbasin_id"]).any(),
        "子流域统计年份—分区组合不唯一。",
    )
    _require(
        set(subbasins["year"].astype(int)) == EXPECTED_YEARS,
        "子流域统计年份必须为2018—2024。",
    )
    _require(
        set(subbasins["subbasin_id"]) == EXPECTED_SUBBASINS,
        "子流域统计编号不完整。",
    )
    _require(
        set(subbasins["roi_version"]) == {"hybas6_v1"},
        "子流域统计版本不是hybas6_v1。",
    )
    _require(not subbasins.isna().any().any(), "子流域统计存在空值。")

    boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
    features = boundary.get("features", [])
    _require(
        boundary.get("type") == "FeatureCollection" and len(features) == 5,
        "正式边界必须为含5个Feature的FeatureCollection。",
    )
    boundary_ids = {
        feature.get("properties", {}).get("subbasin_id")
        for feature in features
    }
    _require(boundary_ids == EXPECTED_SUBBASINS, "正式边界分区编号不完整。")

    manifest = load_raster_manifest(manifest_path)
    asset_count = sum(len(layer.assets) for layer in manifest.layers)
    _require(asset_count == 35, "栅格瓦片契约必须包含35个图层年份资产。")
    return {
        "overall_rows": len(overall),
        "subbasin_rows": len(subbasins),
        "boundary_features": len(features),
        "raster_assets": asset_count,
        "dataset_version": manifest.dataset_version,
    }
