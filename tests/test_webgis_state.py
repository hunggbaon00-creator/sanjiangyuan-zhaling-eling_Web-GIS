import unittest

from app.webgis_state import (
    ACTIVE_LAYER_KEY,
    BASEMAP_KEY,
    DEFAULT_BASEMAP,
    DEFAULT_ACTIVE_LAYER,
    DEFAULT_LAYER_OPACITY,
    LAYER_OPACITY_KEY,
    MAP_REVISION_KEY,
    OVERALL_SCOPE,
    RASTER_LAYER_KEY,
    SELECTED_METRIC_KEY,
    SELECTED_SUBBASIN_KEY,
    SELECTED_YEAR_KEY,
    SUBBASIN_SCOPE,
    SUBBASIN_SELECTOR_KEY,
    VIEW_SCOPE_KEY,
    initialize_webgis_state,
    select_overall,
    select_subbasin,
    synchronize_subbasin_selector,
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
        self.assertEqual(state.basemap, DEFAULT_BASEMAP)
        self.assertEqual(state.layer_opacity, DEFAULT_LAYER_OPACITY)
        self.assertEqual(state.map_revision, 0)
        self.assertIsNone(state.raster_layer_id)
        self.assertIsNone(session_state[SUBBASIN_SELECTOR_KEY])

    def test_preserves_valid_state(self) -> None:
        session_state = {
            SELECTED_YEAR_KEY: 2021,
            SELECTED_METRIC_KEY: "NDVI均值",
            SELECTED_SUBBASIN_KEY: "SB03",
            VIEW_SCOPE_KEY: OVERALL_SCOPE,
            ACTIVE_LAYER_KEY: DEFAULT_ACTIVE_LAYER,
            BASEMAP_KEY: "terrain",
            LAYER_OPACITY_KEY: 0.35,
            MAP_REVISION_KEY: 2,
            RASTER_LAYER_KEY: "ndvi_raster",
        }

        state = initialize_webgis_state(
            session_state, YEARS, METRICS, raster_layers={"ndvi_raster"}
        )

        self.assertEqual(state.selected_year, 2021)
        self.assertEqual(state.selected_metric, "NDVI均值")
        self.assertEqual(state.selected_subbasin_id, "SB03")
        self.assertEqual(state.view_scope, SUBBASIN_SCOPE)
        self.assertEqual(state.layer_opacity, 0.35)
        self.assertEqual(state.basemap, "terrain")
        self.assertEqual(state.map_revision, 2)
        self.assertEqual(state.raster_layer_id, "ndvi_raster")
        self.assertEqual(session_state[SUBBASIN_SELECTOR_KEY], "SB03")

    def test_repairs_stale_state(self) -> None:
        session_state = {
            SELECTED_YEAR_KEY: 2017,
            SELECTED_METRIC_KEY: "未知指标",
            SELECTED_SUBBASIN_KEY: ["SB03"],
            VIEW_SCOPE_KEY: SUBBASIN_SCOPE,
            ACTIVE_LAYER_KEY: ["boundary"],
            BASEMAP_KEY: "unknown",
            LAYER_OPACITY_KEY: 2,
            MAP_REVISION_KEY: -1,
            RASTER_LAYER_KEY: "unknown",
        }

        state = initialize_webgis_state(session_state, YEARS, METRICS)

        self.assertEqual(state.selected_year, 2024)
        self.assertEqual(state.selected_metric, "水体面积")
        self.assertIsNone(state.selected_subbasin_id)
        self.assertEqual(state.view_scope, OVERALL_SCOPE)
        self.assertEqual(state.active_layer, DEFAULT_ACTIVE_LAYER)
        self.assertEqual(state.basemap, DEFAULT_BASEMAP)
        self.assertEqual(state.layer_opacity, DEFAULT_LAYER_OPACITY)
        self.assertEqual(state.map_revision, 0)
        self.assertIsNone(state.raster_layer_id)

    def test_scope_actions_keep_selection_consistent(self) -> None:
        session_state = {}
        initialize_webgis_state(session_state, YEARS, METRICS)

        select_subbasin(session_state, "SB05")
        self.assertEqual(session_state[SELECTED_SUBBASIN_KEY], "SB05")
        self.assertEqual(session_state[VIEW_SCOPE_KEY], SUBBASIN_SCOPE)

        select_overall(session_state)
        self.assertIsNone(session_state[SELECTED_SUBBASIN_KEY])
        self.assertEqual(session_state[VIEW_SCOPE_KEY], OVERALL_SCOPE)
        self.assertEqual(session_state[MAP_REVISION_KEY], 1)

    def test_map_selection_is_reflected_by_sidebar_on_rerun(self) -> None:
        session_state = {}
        initialize_webgis_state(session_state, YEARS, METRICS)

        select_subbasin(session_state, "SB05")
        initialize_webgis_state(session_state, YEARS, METRICS)

        self.assertEqual(session_state[SELECTED_SUBBASIN_KEY], "SB05")
        self.assertEqual(session_state[SUBBASIN_SELECTOR_KEY], "SB05")
        self.assertEqual(session_state[VIEW_SCOPE_KEY], SUBBASIN_SCOPE)

    def test_rejects_unknown_subbasin(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown subbasin_id"):
            select_subbasin({}, "SB99")

    def test_sidebar_selector_updates_scope_and_resets_map_event(self) -> None:
        session_state = {}
        initialize_webgis_state(session_state, YEARS, METRICS)

        session_state[SUBBASIN_SELECTOR_KEY] = "SB03"
        synchronize_subbasin_selector(session_state)
        self.assertEqual(session_state[SELECTED_SUBBASIN_KEY], "SB03")
        self.assertEqual(session_state[VIEW_SCOPE_KEY], SUBBASIN_SCOPE)
        self.assertEqual(session_state[MAP_REVISION_KEY], 1)

        session_state[SUBBASIN_SELECTOR_KEY] = None
        synchronize_subbasin_selector(session_state)
        self.assertIsNone(session_state[SELECTED_SUBBASIN_KEY])
        self.assertEqual(session_state[VIEW_SCOPE_KEY], OVERALL_SCOPE)
        self.assertEqual(session_state[MAP_REVISION_KEY], 2)

    def test_requires_years_and_metrics(self) -> None:
        with self.assertRaisesRegex(ValueError, "statistics year"):
            initialize_webgis_state({}, [], METRICS)
        with self.assertRaisesRegex(ValueError, "metric"):
            initialize_webgis_state({}, YEARS, [])


if __name__ == "__main__":
    unittest.main()
