import json
import unittest
from copy import deepcopy
from pathlib import Path

from app.raster_tiles import (
    EXPECTED_YEARS,
    build_raster_tile_options,
    load_raster_manifest,
    parse_raster_manifest,
    resolve_raster_selection,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "config" / "raster_layers.json"
SCHEMA_PATH = PROJECT_ROOT / "config" / "raster_layers.schema.json"


class RasterTileContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with MANIFEST_PATH.open("r", encoding="utf-8") as file:
            cls.payload = json.load(file)

    def test_tracked_manifest_and_schema_are_valid_json(self) -> None:
        manifest = load_raster_manifest(MANIFEST_PATH)
        with SCHEMA_PATH.open("r", encoding="utf-8") as file:
            schema = json.load(file)

        self.assertEqual(manifest.contract_version, "1.0.0")
        self.assertEqual(manifest.dataset_version, "hybas6_v1_t000")
        self.assertEqual(manifest.years, EXPECTED_YEARS)
        self.assertEqual(manifest.crs, "EPSG:3857")
        self.assertEqual(
            manifest.bounds,
            (
                95.90833420357303,
                33.94583428316831,
                98.82083175391062,
                35.47535499778,
            ),
        )
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_manifest_declares_five_products_and_all_years(self) -> None:
        manifest = load_raster_manifest(MANIFEST_PATH)

        self.assertEqual(
            manifest.layer_ids,
            (
                "true_color_raster",
                "ndvi_raster",
                "mndwi_raster",
                "water_mask_raster",
                "valid_observation_raster",
            ),
        )
        for layer in manifest.layers:
            self.assertEqual(
                tuple(asset.year for asset in layer.assets), EXPECTED_YEARS
            )
            self.assertTrue(all(asset.url_template is None for asset in layer.assets))
        status_by_asset = {
            (layer.id, asset.year): asset.status
            for layer in manifest.layers
            for asset in layer.assets
        }
        self.assertEqual(
            status_by_asset[("mndwi_raster", 2024)], "processing"
        )
        self.assertEqual(
            list(status_by_asset.values()).count("not_generated"), 34
        )

    def test_resolves_selected_layer_year_without_fallback(self) -> None:
        manifest = load_raster_manifest(MANIFEST_PATH)

        self.assertIsNone(resolve_raster_selection(manifest, None, 2024))
        selection = resolve_raster_selection(manifest, "ndvi_raster", 2024)

        self.assertEqual(selection.layer.label, "年度NDVI")
        self.assertEqual(selection.asset.status_label, "未生成")
        self.assertFalse(selection.asset.is_ready)

    def test_accepts_complete_public_ready_asset(self) -> None:
        payload = deepcopy(self.payload)
        asset = payload["layers"][1]["assets"]["2024"]
        asset.update(
            {
                "status": "ready",
                "url_template": "https://tiles.example.org/ndvi/2024/{z}/{x}/{y}.png",
                "generated_at": "2026-09-01T08:30:00Z",
                "source_checksum_sha256": "a" * 64,
                "asset_version": "hybas6_v1_t000_2024_ndvi_v1",
                "notes": "已完成目视与范围验证。",
            }
        )

        manifest = parse_raster_manifest(payload)
        selection = resolve_raster_selection(manifest, "ndvi_raster", 2024)

        self.assertTrue(selection.asset.is_ready)
        self.assertIn("{z}/{x}/{y}", selection.asset.url_template)
        options = build_raster_tile_options(manifest, selection, 0.6)
        self.assertEqual(options["opacity"], 0.6)
        self.assertEqual(options["min_zoom"], 5)
        self.assertEqual(options["max_zoom"], 13)
        self.assertTrue(options["tiles"].startswith("https://"))

    def test_nonready_asset_produces_no_tile_options(self) -> None:
        manifest = load_raster_manifest(MANIFEST_PATH)
        selection = resolve_raster_selection(manifest, "ndvi_raster", 2024)

        self.assertIsNone(build_raster_tile_options(manifest, selection, 0.7))

    def test_rejects_temporary_or_incomplete_ready_asset(self) -> None:
        payload = deepcopy(self.payload)
        asset = payload["layers"][1]["assets"]["2024"]
        asset.update(
            {
                "status": "ready",
                "url_template": "https://tiles.example.org/{z}/{x}/{y}.png?token=short",
                "generated_at": "2026-09-01T08:30:00Z",
                "source_checksum_sha256": "a" * 64,
                "asset_version": "v1",
            }
        )
        with self.assertRaisesRegex(ValueError, "不得包含查询参数"):
            parse_raster_manifest(payload)

        asset["url_template"] = None
        with self.assertRaisesRegex(ValueError, "缺少发布元数据"):
            parse_raster_manifest(payload)

    def test_rejects_missing_year_or_processing_drift(self) -> None:
        missing_year = deepcopy(self.payload)
        del missing_year["layers"][0]["assets"]["2018"]
        with self.assertRaisesRegex(ValueError, "完整声明2018—2024"):
            parse_raster_manifest(missing_year)

        drifted = deepcopy(self.payload)
        drifted["processing"]["water_threshold"] = 0.1
        with self.assertRaisesRegex(ValueError, "正式统计口径不一致"):
            parse_raster_manifest(drifted)

        wrong_bounds = deepcopy(self.payload)
        wrong_bounds["bounds"][0] = 95.0
        with self.assertRaisesRegex(ValueError, "正式边界范围一致"):
            parse_raster_manifest(wrong_bounds)


if __name__ == "__main__":
    unittest.main()
