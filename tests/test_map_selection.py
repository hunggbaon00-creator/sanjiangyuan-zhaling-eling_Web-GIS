import json
import unittest
from pathlib import Path

from app.map_selection import extract_map_click, find_subbasin_at_point


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_PATH = (
    PROJECT_ROOT
    / "data"
    / "boundaries"
    / "zhaling_eling_watershed_hybas6_v1.geojson"
)


class MapSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with BOUNDARY_PATH.open("r", encoding="utf-8") as file:
            cls.boundary = json.load(file)

    def test_reference_lake_points_select_expected_subbasins(self) -> None:
        self.assertEqual(
            find_subbasin_at_point(self.boundary, 97.32, 34.93), "SB03"
        )
        self.assertEqual(
            find_subbasin_at_point(self.boundary, 97.70, 34.86), "SB05"
        )

    def test_outside_point_does_not_change_selection(self) -> None:
        self.assertIsNone(find_subbasin_at_point(self.boundary, 0.0, 0.0))

    def test_extracts_valid_leaflet_click(self) -> None:
        result = {"last_object_clicked": {"lat": 34.93, "lng": 97.32}}
        self.assertEqual(extract_map_click(result), (97.32, 34.93))

    def test_rejects_invalid_leaflet_click(self) -> None:
        invalid_results = [
            None,
            {},
            {"last_object_clicked": None},
            {"last_object_clicked": {"lat": "34.93", "lng": 97.32}},
            {"last_object_clicked": {"lat": 91, "lng": 97.32}},
            {"last_object_clicked": {"lat": 34.93, "lng": float("nan")}},
        ]
        for result in invalid_results:
            with self.subTest(result=result):
                self.assertIsNone(extract_map_click(result))


if __name__ == "__main__":
    unittest.main()
