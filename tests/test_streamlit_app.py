import unittest

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = AppTest.from_file(
            "app/streamlit_app.py", default_timeout=30
        )
        self.app.run()
        self.assertFalse(self.app.exception)

    def test_default_scope_uses_overall_statistics(self) -> None:
        self.assertIsNone(self.app.sidebar.selectbox[1].value)
        self.assertEqual(self.app.metric[0].value, "1,589.09 km²")
        self.assertEqual(
            self.app.subheader[1].value,
            "总体研究区 2018—2024年水体面积趋势",
        )
        self.assertEqual(len(self.app.dataframe[0].value), 7)

    def test_sidebar_scope_switches_components_and_returns_overall(self) -> None:
        self.app.sidebar.selectbox[1].select("SB03").run()

        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.sidebar.selectbox[1].value, "SB03")
        self.assertEqual(self.app.metric[0].value, "580.22 km²")
        self.assertEqual(
            self.app.subheader[1].value,
            "SB03 · 扎陵湖所在单元 2018—2024年水体面积趋势",
        )
        detail = self.app.dataframe[0].value
        self.assertEqual(detail["年份"].tolist(), list(range(2018, 2025)))
        self.assertEqual(detail.iloc[0]["影像数量"], 5)
        self.assertAlmostEqual(
            detail.iloc[0]["水体面积（km²）"], 577.1136468792687
        )
        comparison = self.app.dataframe[1].value
        selected_marker = comparison.loc[
            comparison["分区编号"] == "SB03", "当前选区"
        ].iloc[0]
        self.assertEqual(selected_marker, "●")

        self.app.sidebar.button[0].click().run()

        self.assertFalse(self.app.exception)
        self.assertIsNone(self.app.sidebar.selectbox[1].value)
        self.assertEqual(self.app.metric[0].value, "1,589.09 km²")

    def test_layer_controls_switch_basemap_thematic_layer_and_opacity(self) -> None:
        self.app.sidebar.selectbox[2].select("terrain")
        self.app.sidebar.selectbox[3].select("water_area")
        self.app.sidebar.slider[0].set_value(0.45)
        self.app.run()

        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.sidebar.selectbox[2].value, "terrain")
        self.assertEqual(self.app.sidebar.selectbox[3].value, "water_area")
        self.assertEqual(self.app.sidebar.slider[0].value, 0.45)
        captions = [item.value for item in self.app.caption]
        self.assertTrue(
            any(
                "当前底图：地形图｜业务图层：子流域水体面积｜透明度：45%"
                in caption
                for caption in captions
            )
        )
        self.assertTrue(
            any("不是20 m像元级遥感栅格" in caption for caption in captions)
        )


if __name__ == "__main__":
    unittest.main()
