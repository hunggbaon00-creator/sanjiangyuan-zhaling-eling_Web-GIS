# 基于 GEE 与 WebGIS 的三江源植被水体可视化原型

本项目以扎陵湖—鄂陵湖候选汇水区为研究区，使用 Google Earth Engine（GEE）计算年度 NDVI、MNDWI、水体面积和有效观测覆盖率，并通过 Streamlit 展示研究区总体及五个子流域的正式结果。

## 当前数据版本

当前正式口径为 `hybas6_v1_t000`。

| 项目 | 当前口径 |
| --- | --- |
| 研究区版本 | `hybas6_v1` |
| 边界来源 | HydroBASINS Level 6，5个独立子流域 Feature |
| 影像数据 | Sentinel-2 SR Harmonized |
| 统计时期 | 2018—2024年，每年6月1日至9月30日 |
| 水体规则 | `MNDWI > 0.0`（`t000`） |
| 统计尺度 | 20 m |
| 总体统计 | `data/processed/zhaling_eling_yearly_stats.csv` |
| 分区统计 | `data/processed/zhaling_eling_subbasin_yearly_stats.csv` |
| 正式边界 | `data/boundaries/zhaling_eling_watershed_hybas6_v1.geojson` |

五个子流域保留独立边界用于地图展示和分区统计；研究区总体统计使用消除内部边界后的合并几何。阈值 `0.0` 已完成2021年多阈值对比、2019/2024岸线检查和2018年 Sentinel-2—Landsat 8交叉验证。

2018年 Sentinel-2 有效覆盖率约为 `65.22%`，覆盖等级为 `low`。该年水体面积约 `1517.62 km²`，结合 Landsat 8结果可能存在约2%的低估，不宜与高覆盖年份等权比较；2019—2024年覆盖等级均为 `high`。

## 五子流域标识

| 分区 | HYBAS ID | 名称 |
| --- | ---: | --- |
| SB01 | 4060614190 | 扎陵湖上游北部单元 |
| SB02 | 4060614330 | 扎陵湖上游南部单元 |
| SB03 | 4060620840 | 扎陵湖所在单元 |
| SB04 | 4060621070 | 鄂陵湖上游南部单元 |
| SB05 | 4060628060 | 鄂陵湖所在及出口单元 |

中文名称为项目显示名称，权威识别字段为 `HYBAS ID`。

## 启动页面

```powershell
.\.venv\Scripts\python.exe -m streamlit run app\streamlit_app.py --server.port 8501
```

浏览器打开 `http://127.0.0.1:8501`。页面不会回退到模拟数据；正式 CSV 或边界缺失、字段不完整、版本不一致时会直接显示错误。

## WebGIS交互骨架

交互骨架当前已完成阶段5：

1. `hybas6_v1_t000` 已合并到 `main`，后续 WebGIS 开发以正式 v1 数据链为唯一基线。
2. 页面状态集中在 `app/webgis_state.py`，统一管理年份、指标、当前子流域、总体/分区范围、活动图层和透明度。
3. 地图支持点击五个子流域进行选择、高亮和连续切换，并可从侧栏返回总体。
4. 地图与侧栏范围选择器双向同步，指标卡、覆盖提示、趋势图和年度明细表同步切换总体或分区正式统计。
5. 建立底图和业务图层注册表，支持边界、水体面积、NDVI、MNDWI、有效覆盖率年度分区专题层，以及透明度、动态Tooltip和固定色带图例。

现阶段图层系统使用本地正式GeoJSON和CSV，不消耗GEE计算额度。年度分区专题层不是20 m像元级遥感栅格；正式年度瓦片仍属于后续数据源扩展。

## GEE授权与导出

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\powershell\run_gee_auth.ps1
.\.venv\Scripts\python.exe scripts\gee\gee_auth_check.py
```

生成并导出五子流域边界：

```powershell
.\.venv\Scripts\python.exe scripts\gee\export_zhaling_eling_watershed_hybas6_v1.py
```

启动总体与分区年度统计任务：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\powershell\run_gee_export_stats.ps1
```

年度入口一次启动两个任务：

```text
zhaling_eling_yearly_stats_2018_2024_hybas6_v1_t000
zhaling_eling_subbasin_yearly_stats_2018_2024_hybas6_v1_t000
```

JavaScript脚本用于 Code Editor 地图检查；Python脚本用于可重复的批任务启动。两者必须保持 Asset、年份、季节、掩膜、阈值、尺度和导出字段一致。

## 数据晋级规则

1. GEE结果先进入 `data/processed/candidates/`，不得直接覆盖正式文件。
2. 运行 `scripts/validate_hybas6_v1_outputs.py` 检查边界、7行总体、35行分区、口径、回归和分区汇总。
3. 完成阈值、岸线和跨传感器验证。
4. 全部通过后再更新正式 CSV、GeoJSON和页面版本。
5. 提交脚本、文档及正式数据；候选结果、栅格、凭据和虚拟环境不纳入 Git。

完整收口结论见 `docs/hybas6_v1_t000_validation.md`，详细字段见 `data/processed/README.md`，GEE工作流见 `scripts/gee/README.md`。
