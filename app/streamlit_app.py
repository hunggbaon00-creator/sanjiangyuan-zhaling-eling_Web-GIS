import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from folium import GeoJson, Map, TileLayer
from folium.features import GeoJsonTooltip
from streamlit_folium import st_folium

from app.map_selection import extract_map_click, find_subbasin_at_point
from app.webgis_state import (
    SELECTED_METRIC_KEY,
    SELECTED_YEAR_KEY,
    initialize_webgis_state,
    read_webgis_state,
    select_overall,
    select_subbasin,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "zhaling_eling_yearly_stats.csv"
SUBBASIN_DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "zhaling_eling_subbasin_yearly_stats.csv"
)
BOUNDARY_PATH = (
    PROJECT_ROOT
    / "data"
    / "boundaries"
    / "zhaling_eling_watershed_hybas6_v1.geojson"
)

REQUIRED_COLUMNS = {
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

NUMERIC_COLUMNS = [
    "year",
    "image_count",
    "roi_area_km2",
    "valid_area_km2",
    "valid_share",
    "ndvi_mean",
    "mndwi_mean",
    "water_area_km2",
    "water_threshold",
    "statistics_scale_m",
]

SUBBASIN_REQUIRED_COLUMNS = {
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

SUBBASIN_NUMERIC_COLUMNS = [
    "year",
    "image_count",
    "hybas_id",
    "next_down",
    "subbasin_area_km2",
    "valid_area_km2",
    "valid_share",
    "ndvi_mean",
    "mndwi_mean",
    "water_area_km2",
    "water_threshold",
    "statistics_scale_m",
]

COVERAGE_LABELS = {
    "high": "高",
    "medium": "中",
    "low": "低",
}

METRICS = {
    "NDVI均值": {
        "column": "ndvi_mean",
        "axis": "研究区NDVI均值",
        "color": "#2E8B57",
        "format": ".4f",
    },
    "MNDWI均值": {
        "column": "mndwi_mean",
        "axis": "研究区MNDWI均值",
        "color": "#2878B5",
        "format": ".4f",
    },
    "水体面积": {
        "column": "water_area_km2",
        "axis": "水体面积（km²）",
        "color": "#0066CC",
        "format": ",.2f",
    },
}


@st.cache_data
def load_yearly_stats(path: str) -> pd.DataFrame:
    data = pd.read_csv(path)
    missing_columns = REQUIRED_COLUMNS.difference(data.columns)
    if missing_columns:
        missing = "、".join(sorted(missing_columns))
        raise ValueError(f"年度统计CSV缺少字段：{missing}")

    data = data.copy()
    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="raise")

    if data["year"].duplicated().any():
        duplicated = data.loc[data["year"].duplicated(), "year"].tolist()
        raise ValueError(f"年度统计CSV存在重复年份：{duplicated}")
    if data[list(REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("年度统计CSV存在关键字段缺失值。")
    if not data["valid_share"].between(0, 1).all():
        raise ValueError("valid_share 应位于0—1之间。")
    if set(data["roi_version"]) != {"hybas6_v1"}:
        raise ValueError("总体年度统计不是hybas6_v1版本。")
    if set(data["water_threshold"].astype(float)) != {0.0}:
        raise ValueError("总体年度统计水体阈值不是0.0。")
    if set(data["statistics_scale_m"].astype(int)) != {20}:
        raise ValueError("总体年度统计尺度不是20 m。")

    data["year"] = data["year"].astype(int)
    data["image_count"] = data["image_count"].astype(int)
    data["coverage_label"] = data["coverage_flag"].map(COVERAGE_LABELS)
    data["coverage_label"] = data["coverage_label"].fillna(
        data["coverage_flag"]
    )
    return data.sort_values("year").reset_index(drop=True)


@st.cache_data
def load_subbasin_stats(path: str) -> pd.DataFrame:
    data = pd.read_csv(path)
    missing_columns = SUBBASIN_REQUIRED_COLUMNS.difference(data.columns)
    if missing_columns:
        missing = "、".join(sorted(missing_columns))
        raise ValueError(f"子流域年度统计CSV缺少字段：{missing}")

    data = data.copy()
    for column in SUBBASIN_NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="raise")
    if len(data) != 35:
        raise ValueError(f"子流域年度统计应为35行，当前为{len(data)}行。")
    if data.duplicated(["year", "subbasin_id"]).any():
        raise ValueError("子流域年度统计存在重复的年份—分区组合。")
    if data[list(SUBBASIN_REQUIRED_COLUMNS)].isna().any().any():
        raise ValueError("子流域年度统计存在关键字段缺失值。")
    if set(data["subbasin_id"]) != {"SB01", "SB02", "SB03", "SB04", "SB05"}:
        raise ValueError("子流域编号应为SB01—SB05。")
    if set(data["roi_version"]) != {"hybas6_v1"}:
        raise ValueError("子流域年度统计不是hybas6_v1版本。")
    if not data["valid_share"].between(0, 1).all():
        raise ValueError("子流域valid_share应位于0—1之间。")

    data["year"] = data["year"].astype(int)
    data["image_count"] = data["image_count"].astype(int)
    data["coverage_label"] = data["coverage_flag"].map(COVERAGE_LABELS)
    return data.sort_values(["year", "subbasin_id"]).reset_index(drop=True)


@st.cache_data
def load_boundary(path: str) -> dict:
    with Path(path).open("r", encoding="utf-8") as file:
        boundary = json.load(file)
    if boundary.get("type") != "FeatureCollection" or not boundary.get("features"):
        raise ValueError("研究区GeoJSON不是有效的FeatureCollection。")
    if len(boundary["features"]) != 5:
        raise ValueError("hybas6_v1边界应包含5个子流域Feature。")
    subbasin_ids = {
        feature.get("properties", {}).get("subbasin_id")
        for feature in boundary["features"]
    }
    if subbasin_ids != {"SB01", "SB02", "SB03", "SB04", "SB05"}:
        raise ValueError("hybas6_v1边界的子流域编号不完整。")
    return boundary


def build_boundary_map(
    boundary: dict, selected_subbasin_id: str | None = None
) -> Map:
    map_object = Map(
        location=[34.9, 97.55],
        zoom_start=7,
        control_scale=True,
        tiles=None,
    )
    TileLayer("OpenStreetMap", name="OpenStreetMap", show=True).add_to(map_object)
    TileLayer(
        tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        attr="Map data © OpenStreetMap contributors, SRTM | Map style © OpenTopoMap",
        name="地形图",
        show=False,
    ).add_to(map_object)

    boundary_layer = GeoJson(
        boundary,
        name="hybas6_v1五子流域边界",
        style_function=lambda feature: (
            {
                "color": "#FF7F0E",
                "weight": 4,
                "fillColor": "#FF7F0E",
                "fillOpacity": 0.28,
            }
            if feature.get("properties", {}).get("subbasin_id")
            == selected_subbasin_id
            else {
                "color": "#D62728",
                "weight": 3,
                "fillColor": "#D62728",
                "fillOpacity": 0.08,
            }
        ),
        highlight_function=lambda feature: {
            "color": "#FFC107",
            "weight": 5,
            "fillOpacity": (
                0.32
                if feature.get("properties", {}).get("subbasin_id")
                == selected_subbasin_id
                else 0.16
            ),
        },
        tooltip=GeoJsonTooltip(
            fields=[
                "subbasin_id",
                "name_cn",
                "hybas_id",
                "next_down",
                "area_km2",
            ],
            aliases=[
                "分区编号：",
                "名称：",
                "HYBAS ID：",
                "下游 HYBAS ID：",
                "矢量面积（km²）：",
            ],
            localize=True,
            sticky=False,
        ),
    )
    boundary_layer.add_to(map_object)
    map_object.fit_bounds(boundary_layer.get_bounds())
    return map_object


def build_trend_chart(data: pd.DataFrame, metric_name: str):
    metric = METRICS[metric_name]
    column = metric["column"]
    figure = px.line(
        data,
        x="year",
        y=column,
        markers=True,
        custom_data=["valid_share", "coverage_label", "image_count"],
        labels={"year": "年份", column: metric["axis"]},
    )
    figure.update_traces(
        line={"color": metric["color"], "width": 3},
        marker={"size": 9},
        hovertemplate=(
            "年份：%{x}<br>"
            + metric["axis"]
            + "：%{y:"
            + metric["format"]
            + "}<br>有效覆盖率：%{customdata[0]:.2%}"
            "<br>覆盖等级：%{customdata[1]}"
            "<br>影像数量：%{customdata[2]:.0f}<extra></extra>"
        ),
    )

    limited_coverage = data[data["coverage_flag"] != "high"]
    if not limited_coverage.empty:
        figure.add_scatter(
            x=limited_coverage["year"],
            y=limited_coverage[column],
            mode="markers",
            name="覆盖受限年份",
            marker={"color": "#FF8C00", "size": 13, "symbol": "diamond"},
            hoverinfo="skip",
        )

    figure.update_layout(
        height=440,
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.12, "x": 0},
    )
    figure.update_xaxes(dtick=1)
    return figure


st.set_page_config(
    page_title="扎陵湖—鄂陵湖植被水体监测",
    page_icon="🏔️",
    layout="wide",
)

st.title("三江源扎陵湖—鄂陵湖植被与水体监测")
st.caption("基于Google Earth Engine与WebGIS的年度统计可视化原型")

try:
    yearly_data = load_yearly_stats(str(DATA_PATH))
    subbasin_data = load_subbasin_stats(str(SUBBASIN_DATA_PATH))
except (FileNotFoundError, ValueError, pd.errors.ParserError) as error:
    st.error(f"无法读取正式hybas6_v1数据：{error}")
    st.stop()

years = yearly_data["year"].tolist()
initialize_webgis_state(st.session_state, years, METRICS)
st.sidebar.selectbox("统计年份", years, key=SELECTED_YEAR_KEY)
st.sidebar.radio(
    "趋势指标",
    list(METRICS),
    key=SELECTED_METRIC_KEY,
)
ui_state = read_webgis_state(st.session_state)
selected_year = ui_state.selected_year
selected_metric = ui_state.selected_metric

st.sidebar.divider()
st.sidebar.markdown("**当前地图选区**")
if ui_state.selected_subbasin_id:
    selected_name_rows = subbasin_data.loc[
        subbasin_data["subbasin_id"] == ui_state.selected_subbasin_id,
        "subbasin_name",
    ]
    selected_name = selected_name_rows.iloc[0]
    st.sidebar.caption(f"{ui_state.selected_subbasin_id} · {selected_name}")
    if st.sidebar.button("返回总体", use_container_width=True):
        select_overall(st.session_state)
        st.rerun()
else:
    st.sidebar.caption("总体研究区")
st.sidebar.caption("本阶段地图选区仅用于高亮；统计仍保持总体口径。")

st.sidebar.divider()
st.sidebar.markdown("**数据口径**")
st.sidebar.caption(
    "Sentinel-2 SR Harmonized\n\n"
    "生长季：6月1日—9月30日\n\n"
    "水体：MNDWI > 0.0\n\n"
    "统计尺度：20 m\n\n"
    "ROI：hybas6_v1（5个六级子流域）"
)

current = yearly_data.loc[yearly_data["year"] == selected_year].iloc[0]

metric_columns = st.columns(4)
metric_columns[0].metric("水体面积", f"{current['water_area_km2']:,.2f} km²")
metric_columns[1].metric("NDVI均值", f"{current['ndvi_mean']:.4f}")
metric_columns[2].metric("MNDWI均值", f"{current['mndwi_mean']:.4f}")
metric_columns[3].metric(
    "有效覆盖率",
    f"{current['valid_share']:.2%}",
    help="有效MNDWI像元面积占研究区栅格口径面积的比例。",
)

st.caption(
    f"{selected_year}年共使用 {current['image_count']} 景候选影像；"
    f"覆盖等级：{current['coverage_label']}。"
)

if current["coverage_flag"] == "low":
    st.warning(
        f"{selected_year}年有效覆盖率仅为 {current['valid_share']:.2%}。"
        "该年度正式Sentinel-2水体面积可能约低估2%，应结合Landsat 8独立验证结果解释，"
        "不宜与高覆盖年份等权比较。"
    )
elif current["coverage_flag"] == "medium":
    st.warning(
        f"{selected_year}年有效覆盖率为 {current['valid_share']:.2%}，"
        "进行跨年比较时应注意覆盖差异。"
    )

map_column, chart_column = st.columns([1.1, 1])

with map_column:
    st.subheader("研究区范围")
    try:
        boundary_data = load_boundary(str(BOUNDARY_PATH))
        boundary_map = build_boundary_map(
            boundary_data, ui_state.selected_subbasin_id
        )
        map_result = st_folium(
            boundary_map,
            key=f"study_area_map_{ui_state.map_revision}",
            height=500,
            width=None,
            returned_objects=["last_object_clicked"],
            use_container_width=True,
        )
        clicked_point = extract_map_click(map_result)
        if clicked_point:
            clicked_subbasin = find_subbasin_at_point(
                boundary_data, *clicked_point
            )
            if (
                clicked_subbasin
                and clicked_subbasin != ui_state.selected_subbasin_id
            ):
                select_subbasin(st.session_state, clicked_subbasin)
                st.rerun()

        if ui_state.selected_subbasin_id:
            st.caption(
                f"已选择 {ui_state.selected_subbasin_id}；橙色区域为当前选区。"
                "可继续点击其他子流域，或在侧栏返回总体。"
            )
        else:
            st.caption(
                "点击任一子流域进行选择；悬停可查看分区属性。"
            )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        st.error(f"无法加载研究区边界：{error}")

with chart_column:
    st.subheader(f"2018—2024年{selected_metric}趋势")
    trend_chart = build_trend_chart(yearly_data, selected_metric)
    st.plotly_chart(trend_chart, width="stretch")
    st.caption("橙色菱形表示有效覆盖率低于95%的年份。")

with st.expander("查看年度统计明细"):
    detail_data = yearly_data[
        [
            "year",
            "image_count",
            "ndvi_mean",
            "mndwi_mean",
            "water_area_km2",
            "valid_share",
            "coverage_label",
        ]
    ].rename(
        columns={
            "year": "年份",
            "image_count": "影像数量",
            "ndvi_mean": "NDVI均值",
            "mndwi_mean": "MNDWI均值",
            "water_area_km2": "水体面积（km²）",
            "valid_share": "有效覆盖率",
            "coverage_label": "覆盖等级",
        }
    )
    detail_data["有效覆盖率"] = detail_data["有效覆盖率"] * 100
    st.dataframe(
        detail_data,
        hide_index=True,
        width="stretch",
        column_config={
            "NDVI均值": st.column_config.NumberColumn(format="%.4f"),
            "MNDWI均值": st.column_config.NumberColumn(format="%.4f"),
            "水体面积（km²）": st.column_config.NumberColumn(format="%.2f"),
            "有效覆盖率": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.2f%%",
            ),
        },
    )

with st.expander(f"查看{selected_year}年五子流域统计"):
    selected_subbasins = subbasin_data.loc[
        subbasin_data["year"] == selected_year,
        [
            "subbasin_id",
            "subbasin_name",
            "image_count",
            "ndvi_mean",
            "mndwi_mean",
            "water_area_km2",
            "valid_share",
            "coverage_label",
        ],
    ].rename(
        columns={
            "subbasin_id": "分区编号",
            "subbasin_name": "分区名称",
            "image_count": "影像数量",
            "ndvi_mean": "NDVI均值",
            "mndwi_mean": "MNDWI均值",
            "water_area_km2": "水体面积（km²）",
            "valid_share": "有效覆盖率",
            "coverage_label": "覆盖等级",
        }
    )
    selected_subbasins["有效覆盖率"] *= 100
    st.dataframe(
        selected_subbasins,
        hide_index=True,
        width="stretch",
        column_config={
            "NDVI均值": st.column_config.NumberColumn(format="%.4f"),
            "MNDWI均值": st.column_config.NumberColumn(format="%.4f"),
            "水体面积（km²）": st.column_config.NumberColumn(format="%.2f"),
            "有效覆盖率": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.2f%%",
            ),
        },
    )

st.caption(
    "数据版本：hybas6_v1_t000｜统计年份：2018—2024｜"
    "水体判定：MNDWI > 0.0｜总体与五子流域采用同一统计口径。"
)
