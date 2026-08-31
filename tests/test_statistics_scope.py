import unittest
from pathlib import Path

import pandas as pd

from app.statistics_scope import resolve_statistics_scope


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DATA = PROJECT_ROOT / "data" / "processed"


class StatisticsScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.overall_data = pd.read_csv(
            PROCESSED_DATA / "zhaling_eling_yearly_stats.csv"
        )
        cls.subbasin_data = pd.read_csv(
            PROCESSED_DATA / "zhaling_eling_subbasin_yearly_stats.csv"
        )

    def test_resolves_overall_statistics(self) -> None:
        scope = resolve_statistics_scope(
            self.overall_data, self.subbasin_data, None
        )

        self.assertTrue(scope.is_overall)
        self.assertEqual(scope.label, "总体研究区")
        self.assertEqual(scope.area_column, "roi_area_km2")
        self.assertEqual(scope.data["year"].tolist(), list(range(2018, 2025)))

    def test_resolves_subbasin_statistics(self) -> None:
        scope = resolve_statistics_scope(
            self.overall_data, self.subbasin_data, "SB03"
        )

        self.assertFalse(scope.is_overall)
        self.assertEqual(scope.label, "SB03 · 扎陵湖所在单元")
        self.assertEqual(scope.area_column, "subbasin_area_km2")
        self.assertEqual(set(scope.data["subbasin_id"]), {"SB03"})
        row_2018 = scope.data.loc[scope.data["year"] == 2018].iloc[0]
        self.assertEqual(row_2018["image_count"], 5)
        self.assertAlmostEqual(row_2018["water_area_km2"], 577.1136468792687)

    def test_rejects_unknown_or_incomplete_scope(self) -> None:
        with self.assertRaisesRegex(ValueError, "没有找到分区统计"):
            resolve_statistics_scope(
                self.overall_data, self.subbasin_data, "SB99"
            )

        incomplete = self.overall_data.iloc[:-1]
        with self.assertRaisesRegex(ValueError, "7个唯一年份"):
            resolve_statistics_scope(incomplete, self.subbasin_data, None)


if __name__ == "__main__":
    unittest.main()
