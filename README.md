# 基于 GEE 与 WebGIS 的三江源植被水体可视化原型

本项目以扎陵湖—鄂陵湖候选汇水区为研究区，使用 Google Earth Engine（GEE）计算年度 NDVI、MNDWI、水体面积和有效观测覆盖率，并通过 Streamlit 展示正式统计结果。

## 当前阶段

当前已完成 `hybas6_v0_t000` 阶段的数据生产与验证，正式年度 CSV 已接入 Streamlit 页面。建议在完成页面复核和提交后使用阶段标签 `hybas6-v0-t000`。

| 项目 | 当前口径 |
| --- | --- |
| 研究区版本 | `hybas6_v0` |
| 边界来源 | HydroBASINS Level 6，5 个上游子流域的合并几何 |
| 当前边界展示 | 1 个融合后的外边界 Polygon，不显示 5 个子流域内部边界 |
| 影像数据 | Sentinel-2 SR Harmonized |
| 统计时期 | 2018—2024 年，每年 6 月 1 日至 9 月 30 日 |
| 水体规则 | `MNDWI > 0.0`（版本后缀 `t000`） |
| 统计尺度 | 20 m |
| 正式数据 | `data/processed/zhaling_eling_yearly_stats.csv` |

阈值 `0.0` 经过 2021 年 `-0.1 / 0.0 / 0.1 / 0.2` 对比、2019 与 2024 年岸线检查，以及 2018 年 Sentinel-2 与 Landsat 8 独立交叉验证后固定。

2018 年 Sentinel-2 有效覆盖率为 `65.22%`，覆盖等级为 `low`。该年水体面积 `1517.62 km²` 应作为受覆盖限制的正式估计值使用；结合 Landsat 8 验证，可能存在约 2% 的低估。2019—2024 年覆盖等级均为 `high`。

## 目录结构

```text
app/                         Streamlit 展示页面
data/boundaries/             正式研究区 GeoJSON
data/processed/              正式年度 CSV 与数据说明
data/processed/candidates/   阈值、岸线和交叉验证候选结果（不纳入 Git）
data/processed/archive/      本地旧数据副本（不纳入 Git）
data/raw/                    本地原始数据
scripts/gee/                 GEE JavaScript、Python 与验证脚本
scripts/powershell/          Windows 授权和运行脚本
environment/                 依赖清单
.venv/                       本地 Python 虚拟环境
```

## 启动 Streamlit 页面

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m streamlit run app\streamlit_app.py --server.port 8501
```

浏览器打开 `http://127.0.0.1:8501`。页面读取正式 CSV 和正式 GeoJSON；如果 CSV 缺失、字段不完整或年份重复，页面会显示错误，不会自动降级为模拟数据。

## GEE 授权与年度导出

首次使用或授权失效时执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\powershell\run_gee_auth.ps1
.\.venv\Scripts\python.exe scripts\gee\gee_auth_check.py
```

年度统计有两种等价入口：

- `scripts/gee/export_zhaling_eling_yearly_stats.js`：适合在 GEE Code Editor 中逐层查看、检查 Console 并手动启动导出。
- `scripts/gee/export_zhaling_eling_yearly_stats.py`：适合通过已配置的 API 重复启动批处理任务。

Python 入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\powershell\run_gee_export_stats.ps1
```

两套脚本必须保持 ROI Asset、年份、季节、水体阈值、统计尺度、覆盖等级规则和导出字段一致。当前导出任务名为：

```text
zhaling_eling_yearly_stats_2018_2024_hybas6_v0_t000
```

## 数据生产流程

1. 在 GEE 中检查 ROI、影像数量、真彩色、MNDWI、水体和有效观测次数。
2. 将新导出的 CSV 先放入 `data/processed/candidates/`，文件名保留 ROI、阈值和年份信息。
3. 检查 7 个年份、字段完整性、阈值、ROI 版本、覆盖率和异常年份。
4. 完成阈值验证、岸线检查和必要的独立传感器交叉验证。
5. 通过验证后，将唯一采用的结果复制为 `data/processed/zhaling_eling_yearly_stats.csv`。
6. 启动 Streamlit，核对指标卡、趋势图、2018 覆盖警告、地图边界和明细表。
7. 提交脚本、正式 CSV、正式 GeoJSON 和 README；候选输出不提交。

详细字段和晋级规则见 `data/processed/README.md`。

## Git 与版本管理

Git 只跟踪可复现脚本、文档、正式年度 CSV 和正式边界 GeoJSON。候选结果、旧数据副本、原始大文件、栅格输出、本地凭据和虚拟环境由 `.gitignore` 排除。

脚本历史通过 Git commit 和阶段 tag 管理，不在文件名中连续复制 `v2_final_final` 一类版本。数据文件名使用以下含义：

```text
zhaling_eling_yearly_stats_2018_2024_hybas6_v0_t000.csv
                                              └─ MNDWI > 0.0
                                     └────────── ROI 版本
```

## v1 边界事项

`hybas6_v0` 的统计几何来自 5 个 HydroBASINS Level 6 多边形，但当前 Asset 和 GeoJSON 已融合为单一外边界，因此页面不能显示 5 个子流域的内部边界。

开始 v1 前应先保留 5 个独立 Feature，重新生成并同步替换 GEE Asset、GeoJSON 和相关脚本配置，再重新执行验证与年度导出。不要将 v0 的融合边界文件与 v1 的分区统计结果混用。
