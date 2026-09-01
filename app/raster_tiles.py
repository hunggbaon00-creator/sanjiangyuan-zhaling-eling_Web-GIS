"""Strict manifest contract and adapter for annual raster XYZ tiles."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError


EXPECTED_YEARS = tuple(range(2018, 2025))
EXPECTED_BOUNDS = (
    95.90833420357303,
    33.94583428316831,
    98.82083175391062,
    35.47535499778,
)
EXPECTED_LAYER_IDS = (
    "true_color_raster",
    "ndvi_raster",
    "mndwi_raster",
    "water_mask_raster",
    "valid_observation_raster",
)
ALLOWED_STATUSES = frozenset(
    {"not_generated", "processing", "ready", "failed", "unavailable"}
)
STATUS_LABELS = {
    "not_generated": "未生成",
    "processing": "处理中",
    "ready": "已就绪",
    "failed": "生成失败",
    "unavailable": "不可用",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
LAYER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class RasterRendering:
    mode: str
    minimum: float
    maximum: float
    palette: tuple[str, ...]
    bands: tuple[str, ...]
    nodata_transparent: bool


@dataclass(frozen=True)
class RasterTileAsset:
    year: int
    status: str
    url_template: str | None
    generated_at: str | None
    source_checksum_sha256: str | None
    asset_version: str | None
    notes: str | None

    @property
    def is_ready(self) -> bool:
        return self.status == "ready"

    @property
    def status_label(self) -> str:
        return STATUS_LABELS[self.status]


@dataclass(frozen=True)
class RasterLayer:
    id: str
    label: str
    description: str
    data_type: str
    attribution: str
    rendering: RasterRendering
    assets: tuple[RasterTileAsset, ...]

    def asset_for_year(self, year: int) -> RasterTileAsset:
        for asset in self.assets:
            if asset.year == year:
                return asset
        raise ValueError(f"图层{self.id}缺少{year}年状态。")


@dataclass(frozen=True)
class RasterManifest:
    contract_version: str
    dataset_version: str
    tile_scheme: str
    crs: str
    bounds: tuple[float, float, float, float]
    min_zoom: int
    max_zoom: int
    years: tuple[int, ...]
    layers: tuple[RasterLayer, ...]

    @property
    def layer_ids(self) -> tuple[str, ...]:
        return tuple(layer.id for layer in self.layers)

    def get_layer(self, layer_id: str) -> RasterLayer:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        raise ValueError(f"未知栅格图层：{layer_id}")


@dataclass(frozen=True)
class RasterSelection:
    layer: RasterLayer
    asset: RasterTileAsset


def load_raster_manifest(path: str | Path) -> RasterManifest:
    """Load and validate the tracked raster tile manifest."""
    manifest_path = Path(path)
    try:
        with manifest_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(f"栅格瓦片清单不是有效JSON：{error}") from error
    manifest = parse_raster_manifest(payload)
    schema_path = manifest_path.with_name("raster_layers.schema.json")
    try:
        with schema_path.open("r", encoding="utf-8") as file:
            schema = json.load(file)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(payload)
    except json.JSONDecodeError as error:
        raise ValueError(f"栅格瓦片Schema不是有效JSON：{error}") from error
    except SchemaError as error:
        raise ValueError(f"栅格瓦片Schema无效：{error.message}") from error
    except ValidationError as error:
        raise ValueError(f"栅格瓦片清单不符合Schema：{error.message}") from error
    return manifest


def parse_raster_manifest(payload: Any) -> RasterManifest:
    """Parse a manifest and reject ambiguous or unsafe tile definitions."""
    root = _require_dict(payload, "清单根对象")
    _require_exact_keys(
        root,
        {
            "schema_file",
            "contract_version",
            "dataset_version",
            "tile_scheme",
            "crs",
            "bounds",
            "min_zoom",
            "max_zoom",
            "years",
            "processing",
            "layers",
        },
        "清单根对象",
    )
    if root["schema_file"] != "raster_layers.schema.json":
        raise ValueError("schema_file必须指向raster_layers.schema.json。")
    if root["contract_version"] != "1.0.0":
        raise ValueError("不支持的栅格瓦片契约版本。")
    if root["dataset_version"] != "hybas6_v1_t000":
        raise ValueError("栅格瓦片清单数据版本必须为hybas6_v1_t000。")
    if root["tile_scheme"] != "xyz" or root["crs"] != "EPSG:3857":
        raise ValueError("瓦片必须使用EPSG:3857的XYZ方案。")

    years = tuple(_require_int(year, "years") for year in _require_list(root["years"], "years"))
    if years != EXPECTED_YEARS:
        raise ValueError("栅格瓦片年份必须严格为2018—2024。")
    bounds = _parse_bounds(root["bounds"])
    if bounds != EXPECTED_BOUNDS:
        raise ValueError("bounds必须与hybas6_v1正式边界范围一致。")
    min_zoom = _require_int(root["min_zoom"], "min_zoom")
    max_zoom = _require_int(root["max_zoom"], "max_zoom")
    if (min_zoom, max_zoom) != (5, 13):
        raise ValueError("瓦片缩放级别必须固定为5—13。")
    _parse_processing(root["processing"])

    layer_payloads = _require_list(root["layers"], "layers")
    if not layer_payloads:
        raise ValueError("栅格瓦片清单至少需要一个图层。")
    layers = tuple(_parse_layer(item, years) for item in layer_payloads)
    layer_ids = [layer.id for layer in layers]
    if len(layer_ids) != len(set(layer_ids)):
        raise ValueError("栅格图层ID必须唯一。")
    if tuple(layer_ids) != EXPECTED_LAYER_IDS:
        raise ValueError("栅格图层必须严格声明五类正式年度产品。")
    ready_versions = [
        asset.asset_version
        for layer in layers
        for asset in layer.assets
        if asset.is_ready
    ]
    if len(ready_versions) != len(set(ready_versions)):
        raise ValueError("就绪栅格资产版本必须唯一。")
    return RasterManifest(
        contract_version=str(root["contract_version"]),
        dataset_version=str(root["dataset_version"]),
        tile_scheme=str(root["tile_scheme"]),
        crs=str(root["crs"]),
        bounds=bounds,
        min_zoom=min_zoom,
        max_zoom=max_zoom,
        years=years,
        layers=layers,
    )


def resolve_raster_selection(
    manifest: RasterManifest,
    layer_id: str | None,
    year: int,
) -> RasterSelection | None:
    """Resolve the selected layer-year without falling back to another asset."""
    if layer_id is None:
        return None
    if year not in manifest.years:
        raise ValueError(f"栅格瓦片清单不包含{year}年。")
    layer = manifest.get_layer(layer_id)
    return RasterSelection(layer=layer, asset=layer.asset_for_year(year))


def build_raster_tile_options(
    manifest: RasterManifest,
    selection: RasterSelection | None,
    opacity: float,
) -> dict[str, Any] | None:
    """Build Folium XYZ options only for a validated ready asset."""
    if selection is None or not selection.asset.is_ready:
        return None
    if not 0 <= opacity <= 1:
        raise ValueError("栅格瓦片透明度必须位于0—1之间。")
    return {
        "tiles": selection.asset.url_template,
        "attr": selection.layer.attribution,
        "name": f"{selection.asset.year}年{selection.layer.label}",
        "overlay": True,
        "show": True,
        "opacity": opacity,
        "min_zoom": manifest.min_zoom,
        "max_zoom": manifest.max_zoom,
        "bounds": [
            [manifest.bounds[1], manifest.bounds[0]],
            [manifest.bounds[3], manifest.bounds[2]],
        ],
        "no_wrap": True,
        "keep_buffer": 0,
        "update_when_idle": True,
    }


def _parse_processing(payload: Any) -> None:
    processing = _require_dict(payload, "processing")
    _require_exact_keys(
        processing,
        {
            "collection_id",
            "season_start",
            "season_end_exclusive",
            "composite",
            "cloud_mask",
            "scale_m",
            "roi_version",
            "water_threshold",
        },
        "processing",
    )
    expected = {
        "collection_id": "COPERNICUS/S2_SR_HARMONIZED",
        "season_start": "06-01",
        "season_end_exclusive": "10-01",
        "composite": "median",
        "cloud_mask": "SCL_exclude_3_8_9_10_11",
        "scale_m": 20,
        "roi_version": "hybas6_v1",
        "water_threshold": 0.0,
    }
    if processing != expected:
        raise ValueError("processing与hybas6_v1_t000正式统计口径不一致。")


def _parse_layer(payload: Any, years: tuple[int, ...]) -> RasterLayer:
    layer = _require_dict(payload, "layer")
    _require_exact_keys(
        layer,
        {
            "id",
            "label",
            "description",
            "data_type",
            "attribution",
            "rendering",
            "assets",
        },
        "layer",
    )
    layer_id = _require_string(layer["id"], "layer.id")
    if not LAYER_ID_PATTERN.fullmatch(layer_id):
        raise ValueError(f"非法栅格图层ID：{layer_id}")
    data_type = _require_string(layer["data_type"], f"{layer_id}.data_type")
    if data_type not in {"rgb", "continuous", "binary"}:
        raise ValueError(f"{layer_id}的数据类型无效。")
    rendering = _parse_rendering(layer_id, data_type, layer["rendering"])
    assets_payload = _require_dict(layer["assets"], f"{layer_id}.assets")
    if set(assets_payload) != {str(year) for year in years}:
        raise ValueError(f"{layer_id}必须完整声明2018—2024年状态。")
    assets = tuple(
        _parse_asset(layer_id, year, assets_payload[str(year)]) for year in years
    )
    return RasterLayer(
        id=layer_id,
        label=_require_string(layer["label"], f"{layer_id}.label"),
        description=_require_string(
            layer["description"], f"{layer_id}.description"
        ),
        data_type=data_type,
        attribution=_require_string(
            layer["attribution"], f"{layer_id}.attribution"
        ),
        rendering=rendering,
        assets=assets,
    )


def _parse_rendering(
    layer_id: str, data_type: str, payload: Any
) -> RasterRendering:
    rendering = _require_dict(payload, f"{layer_id}.rendering")
    _require_exact_keys(
        rendering,
        {"mode", "min", "max", "palette", "bands", "nodata_transparent"},
        f"{layer_id}.rendering",
    )
    mode = _require_string(rendering["mode"], f"{layer_id}.rendering.mode")
    if mode != data_type:
        raise ValueError(f"{layer_id}的rendering.mode必须与data_type一致。")
    minimum = _require_number(rendering["min"], f"{layer_id}.rendering.min")
    maximum = _require_number(rendering["max"], f"{layer_id}.rendering.max")
    if minimum >= maximum:
        raise ValueError(f"{layer_id}的渲染范围必须满足min < max。")
    palette = tuple(
        _require_string(color, f"{layer_id}.rendering.palette")
        for color in _require_list(
            rendering["palette"], f"{layer_id}.rendering.palette"
        )
    )
    bands = tuple(
        _require_string(band, f"{layer_id}.rendering.bands")
        for band in _require_list(rendering["bands"], f"{layer_id}.rendering.bands")
    )
    if data_type == "rgb" and (len(bands) != 3 or palette):
        raise ValueError(f"{layer_id}的RGB图层必须声明3个波段且不使用palette。")
    if data_type != "rgb" and (len(bands) != 1 or not palette):
        raise ValueError(f"{layer_id}的单波段图层必须声明1个波段和palette。")
    if not isinstance(rendering["nodata_transparent"], bool):
        raise ValueError(f"{layer_id}.nodata_transparent必须为布尔值。")
    return RasterRendering(
        mode=mode,
        minimum=minimum,
        maximum=maximum,
        palette=palette,
        bands=bands,
        nodata_transparent=rendering["nodata_transparent"],
    )


def _parse_asset(layer_id: str, year: int, payload: Any) -> RasterTileAsset:
    asset = _require_dict(payload, f"{layer_id}.{year}")
    _require_exact_keys(
        asset,
        {
            "status",
            "url_template",
            "generated_at",
            "source_checksum_sha256",
            "asset_version",
            "notes",
        },
        f"{layer_id}.{year}",
    )
    status = _require_string(asset["status"], f"{layer_id}.{year}.status")
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"{layer_id}.{year}状态无效：{status}")
    url_template = _optional_string(asset["url_template"], "url_template")
    generated_at = _optional_string(asset["generated_at"], "generated_at")
    checksum = _optional_string(
        asset["source_checksum_sha256"], "source_checksum_sha256"
    )
    asset_version = _optional_string(asset["asset_version"], "asset_version")
    notes = _optional_string(asset["notes"], "notes")
    if status == "ready":
        _validate_ready_asset(
            layer_id,
            year,
            url_template,
            generated_at,
            checksum,
            asset_version,
        )
    elif any((url_template, generated_at, checksum, asset_version)):
        raise ValueError(f"{layer_id}.{year}非就绪状态不得声明发布元数据。")
    return RasterTileAsset(
        year=year,
        status=status,
        url_template=url_template,
        generated_at=generated_at,
        source_checksum_sha256=checksum,
        asset_version=asset_version,
        notes=notes,
    )


def _validate_ready_asset(
    layer_id: str,
    year: int,
    url_template: str | None,
    generated_at: str | None,
    checksum: str | None,
    asset_version: str | None,
) -> None:
    prefix = f"{layer_id}.{year}"
    if not all((url_template, generated_at, checksum, asset_version)):
        raise ValueError(f"{prefix}就绪状态缺少发布元数据。")
    parsed_url = urlsplit(url_template)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ValueError(f"{prefix}必须使用公开HTTPS瓦片地址。")
    if parsed_url.query or parsed_url.fragment:
        raise ValueError(f"{prefix}瓦片地址不得包含查询参数或片段。")
    if not all(token in url_template for token in ("{z}", "{x}", "{y}")):
        raise ValueError(f"{prefix}瓦片地址必须包含{{z}}/{{x}}/{{y}}。")
    try:
        parsed_time = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{prefix}.generated_at不是ISO 8601时间。") from error
    if parsed_time.tzinfo is None:
        raise ValueError(f"{prefix}.generated_at必须包含时区。")
    if not SHA256_PATTERN.fullmatch(checksum):
        raise ValueError(f"{prefix}必须声明64位小写SHA-256。")


def _parse_bounds(payload: Any) -> tuple[float, float, float, float]:
    values = _require_list(payload, "bounds")
    if len(values) != 4:
        raise ValueError("bounds必须为[min_lon,min_lat,max_lon,max_lat]。")
    min_lon, min_lat, max_lon, max_lat = (
        _require_number(value, "bounds") for value in values
    )
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise ValueError("bounds经纬度范围无效。")
    return min_lon, min_lat, max_lon, max_lat


def _require_exact_keys(
    payload: dict[str, Any], expected: set[str], label: str
) -> None:
    actual = set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{label}字段不符合契约；缺少{missing}，多出{extra}。")


def _require_dict(payload: Any, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label}必须为对象。")
    return payload


def _require_list(payload: Any, label: str) -> list[Any]:
    if not isinstance(payload, list):
        raise ValueError(f"{label}必须为数组。")
    return payload


def _require_string(payload: Any, label: str) -> str:
    if not isinstance(payload, str) or not payload.strip():
        raise ValueError(f"{label}必须为非空字符串。")
    return payload


def _optional_string(payload: Any, label: str) -> str | None:
    if payload is None:
        return None
    return _require_string(payload, label)


def _require_int(payload: Any, label: str) -> int:
    if isinstance(payload, bool) or not isinstance(payload, int):
        raise ValueError(f"{label}必须为整数。")
    return payload


def _require_number(payload: Any, label: str) -> float:
    if isinstance(payload, bool) or not isinstance(payload, (int, float)):
        raise ValueError(f"{label}必须为数值。")
    value = float(payload)
    if not math.isfinite(value):
        raise ValueError(f"{label}必须为有限数值。")
    return value
