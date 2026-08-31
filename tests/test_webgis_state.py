import unittest

from app.webgis_state import (
    ACTIVE_LAYER_KEY,
    DEFAULT_ACTIVE_LAYER,
    DEFAULT_LAYER_OPACITY,
    LAYER_OPACITY_KEY,
    OVERALL_SCOPE,
    SELECTED_METRIC_KEY,
    SELECTED_SUBBASIN_KEY,
    SELECTED_YEAR_KEY,
    SUBBASIN_SCOPE,
    VIEW_SCOPE_KEY,
    initialize_webgis_state,
    select_overall,
    select_subbasin,
)


YEARS = list(range(2018, 2025))
METRICS = ["NDVI均值", "MNDWI均值", "水体面积"]


class WebGISStateTests(unittest.TestCase):
    def test_initializes_useful_defaults(self) -> None:
        session_state = {}

        state = initialize_webgis_state(session_state, YEARS, METRICS)

        self.assertEqual(state.selected_year, 2024)
        self.assertEqual(state.selected_metric, "水体面积")
        self.assertIsNone(state.selected_subbasin_id)
        self.assertEqual(state.view_scope, OVERALL_SCOPE)
        self.assertEqual(state.active_layer, DEFAULT_ACTIVE_LAYER)
        self.assertEqual(state.layer_opacity, DEFAULT_LAYER_OPACITY)

    def test_preserves_valid_state(self) -> None:
        session_state = {
            SELECTED_YEAR_KEY: 2021,
            SELECTED_METRIC_KEY: "NDVI均值",
            SELECTED_SUBBASIN_KEY: "SB03",
            VIEW_SCOPE_KEY: OVERALL_SCOPE,
            ACTIVE_LAYER_KEY: DEFAULT_ACTIVE_LAYER,
            LAYER_OPACITY_KEY: 0.35,
        }

        state = initialize_webgis_state(session_state, YEARS, METRICS)

        self.assertEqual(state.selected_year, 2021)
        self.assertEqual(state.selected_metric, "NDVI均值")
        self.assertEqual(state.selected_subbasin_id, "SB03")
        self.assertEqual(state.view_scope, SUBBASIN_SCOPE)
        self.assertEqual(state.layer_opacity, 0.35)

    def test_repairs_stale_state(self) -> None:
        session_state = {
            SELECTED_YEAR_KEY: 2017,
            SELECTED_METRIC_KEY: "未知指标",
            SELECTED_SUBBASIN_KEY: ["SB03"],
            VIEW_SCOPE_KEY: SUBBASIN_SCOPE,
            ACTIVE_LAYER_KEY: ["boundary"],
            LAYER_OPACITY_KEY: 2,
        }

        state = initialize_webgis_state(session_state, YEARS, METRICS)

        self.assertEqual(state.selected_year, 2024)
        self.assertEqual(state.selected_metric, "水体面积")
        self.assertIsNone(state.selected_subbasin_id)
        self.assertEqual(state.view_scope, OVERALL_SCOPE)
        self.assertEqual(state.active_layer, DEFAULT_ACTIVE_LAYER)
        self.assertEqual(state.layer_opacity, DEFAULT_LAYER_OPACITY)

    def test_scope_actions_keep_selection_consistent(self) -> None:
        session_state = {}
        initialize_webgis_state(session_state, YEARS, METRICS)

        select_subbasin(session_state, "SB05")
        self.assertEqual(session_state[SELECTED_SUBBASIN_KEY], "SB05")
        self.assertEqual(session_state[VIEW_SCOPE_KEY], SUBBASIN_SCOPE)

        select_overall(session_state)
        self.assertIsNone(session_state[SELECTED_SUBBASIN_KEY])
        self.assertEqual(session_state[VIEW_SCOPE_KEY], OVERALL_SCOPE)

    def test_rejects_unknown_subbasin(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown subbasin_id"):
            select_subbasin({}, "SB99")

    def test_requires_years_and_metrics(self) -> None:
        with self.assertRaisesRegex(ValueError, "statistics year"):
            initialize_webgis_state({}, [], METRICS)
        with self.assertRaisesRegex(ValueError, "metric"):
            initialize_webgis_state({}, YEARS, [])


if __name__ == "__main__":
    unittest.main()
