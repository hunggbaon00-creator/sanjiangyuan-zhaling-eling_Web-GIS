import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path
from folium import Map, Marker, TileLayer
from streamlit_folium import st_folium


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "zhaling_eling_yearly_stats.csv"

st.set_page_config(
    page_title="SRT WebGIS 原型",
    layout="wide",
)

st.title("三江源扎陵湖-鄂陵湖 WebGIS 原型")
st.caption("环境测试页：后续可替换为 GEE 导出的 NDVI、NDWI/MNDWI 图层和统计结果。")

years = [2018, 2019, 2020, 2021, 2022, 2023, 2024]
layer = st.sidebar.radio("展示图层", ["研究区概览", "NDVI 示例", "水体指数示例"], index=0)

if DATA_PATH.exists():
    data = pd.read_csv(DATA_PATH)
    data = data.rename(
        columns={
            "year": "年份",
            "ndvi_mean": "NDVI均值",
            "mndwi_mean": "MNDWI均值",
            "water_area_km2": "水体面积(km²)",
            "image_count": "影像数量",
        }
    )
    st.sidebar.success("已读取 GEE 导出的真实统计数据")
else:
    data = pd.DataFrame(
        {
            "年份": years,
            "NDVI均值": [0.42, 0.44, 0.43, 0.46, 0.45, 0.47, 0.48],
            "MNDWI均值": [0.10, 0.11, 0.12, 0.13, 0.12, 0.13, 0.14],
            "水体面积(km²)": [1.00, 0.98, 1.03, 1.05, 1.02, 1.04, 1.06],
            "影像数量": [0, 0, 0, 0, 0, 0, 0],
        }
    )
    st.sidebar.info("当前使用示例数据")

years = sorted(data["年份"].dropna().astype(int).unique().tolist())
selected_year = st.sidebar.selectbox("年份", years, index=len(years) - 1)

map_col, chart_col = st.columns([1.25, 1])

with map_col:
    st.subheader("研究区地图")
    m = Map(location=[34.92, 97.55], zoom_start=8, control_scale=True)
    TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    Marker([34.93, 97.32], popup="扎陵湖区域").add_to(m)
    Marker([34.86, 97.70], popup="鄂陵湖区域").add_to(m)
    st_folium(m, height=520, width=820)

with chart_col:
    st.subheader(f"{selected_year} 年指标展示")
    if layer == "水体指数示例":
        y_col = "水体面积(km²)" if "水体面积(km²)" in data.columns else "MNDWI均值"
    else:
        y_col = "NDVI均值"
    fig = px.line(data, x="年份", y=y_col, markers=True)
    st.plotly_chart(fig)

    current = data[data["年份"].astype(int) == int(selected_year)]
    if not current.empty:
        st.dataframe(current, hide_index=True)

    st.info(
        "当前页面用于验证 Streamlit、Folium、Plotly 和 pandas 是否安装成功。"
        "正式开发时，可将这里的示例数据替换为 GEE 导出的 CSV、GeoJSON 或栅格图层。"
    )
