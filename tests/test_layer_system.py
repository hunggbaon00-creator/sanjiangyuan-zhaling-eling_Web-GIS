import json
import unittest
from pathlib import Path

import pandas as pd

from app.layer_system import (
    BASEMAPS,
    BUSINESS_LAYERS,
    enrich_boundary_with_year_stats,
    resolve_layer_context,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LayerSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.subbasin_data = pd.read_csv(
            PROJECT_ROOT
            / "data"
            / "processed"
            / "zhaling_eling_subbasin_yearly_stats.csv"
        )
        with (
            PROJECT_ROOT
            / "data"
            / "boundaries"
            / "zhaling_eling_watershed_hybas6_v1.geojson"
        ).open("r", encoding="utf-8") as file:
            cls.boundary = json.load(file)

    def test_registry_contains_real_available_layers(self) -> None:
        self.assertEqual(set(BASEMAPS), {"osm", "terrain"})
        self.assertEqual(
            set(BUSINESS_LAYERS),
            {"boundary", "water_area", "ndvi", "mndwi", "coverage"},
        )

    def test_resolves_boundary_without_thematic_values(self) -> None:
        context = resolve_layer_context("boundary", self.subbasin_data, 2024)

        self.assertFalse(context.is_thematic)
        self.assertEqual(dict(context.values), {})
        self.assertIsNone(context.range_label)

    def test_resolves_stable_annual_thematic_layer(self) -> None:
        context = resolve_layer_context("water_area", self.subbasin_data, 2024)

        self.assertTrue(context.is_thematic)
        self.assertEqual(set(context.values), {"SB01", "SB02", "SB03", "SB04", "SB05"})
        self.assertAlmostEqual(context.values["SB03"], 580.2204925302922)
        self.assertEqual(context.minimum, self.subbasin_data["water_area_km2"].min())
        self.assertEqual(context.maximum, self.subbasin_data["water_area_km2"].max())
        self.assertIn("km²", context.range_label)

    def test_coverage_uses_fixed_zero_to_one_scale(self) -> None:
        context = resolve_layer_context("coverage", self.subbasin_data, 2018)

        self.assertEqual(context.minimum, 0.0)
        self.assertEqual(context.maximum, 1.0)
        self.assertAlmostEqual(context.values["SB03"], 0.8662428165514341)

    def test_enriches_all_boundary_tooltips_without_mutating_source(self) -> None:
        enriched = enrich_boundary_with_year_stats(
            self.boundary, self.subbasin_data, 2024
        )

        self.assertNotIn("stats_year", self.boundary["features"][0]["properties"])
        self.assertEqual(len(enriched["features"]), 5)
        sb03 = next(
            feature
            for feature in enriched["features"]
            if feature["properties"]["subbasin_id"] == "SB03"
        )
        self.assertEqual(sb03["properties"]["stats_year"], 2024)
        self.assertAlmostEqual(
            sb03["properties"]["stats_water_area_km2"], 580.2204925302922
        )
        self.assertEqual(sb03["properties"]["stats_coverage_label"], "高")

    def test_rejects_unknown_or_incomplete_layer_data(self) -> None:
        with self.assertRaisesRegex(ValueError, "未知业务图层"):
            resolve_layer_context("unknown", self.subbasin_data, 2024)

        incomplete = self.subbasin_data.loc[
            ~(
                (self.subbasin_data["year"] == 2024)
                & (self.subbasin_data["subbasin_id"] == "SB05")
            )
        ]
        with self.assertRaisesRegex(ValueError, "未覆盖SB01—SB05"):
            resolve_layer_context("ndvi", incomplete, 2024)


if __name__ == "__main__":
    unittest.main()
