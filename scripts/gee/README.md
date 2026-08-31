# GEE工作流

## 授权检查

```powershell
.\.venv\Scripts\python.exe -m ee.cli.eecli authenticate --auth_mode=localhost:0
.\.venv\Scripts\python.exe scripts\gee\gee_auth_check.py
```

默认 Cloud Project 为 `careful-form-499402-d0`。

## 五子流域边界

Code Editor入口：`zhaling_eling_watershed_hybas6_v1.js`。

Python批任务入口：

```powershell
.\.venv\Scripts\python.exe scripts\gee\export_zhaling_eling_watershed_hybas6_v1.py
```

该脚本同时导出GeoJSON到 Drive，并创建：

```text
projects/careful-form-499402-d0/assets/zhaling_eling_watershed_hybas6_v1
```

目标 Asset 已存在时脚本会停止，不执行覆盖。

## 年度统计

```powershell
.\.venv\Scripts\python.exe scripts\gee\export_zhaling_eling_yearly_stats.py
```

一次启动总体和五子流域两个CSV任务。总体使用五区消除内部边界后的合并几何；分区逐 Feature 计算，并分别统计相交影像数。

## 2024年MNDWI栅格试导出

先检查配置而不启动任务：

```powershell
.\.venv\Scripts\python.exe scripts\gee\export_mndwi_2024_pilot.py
```

确认项目、Asset、尺度、投影和Drive目录后，只启动一个批任务：

```powershell
.\.venv\Scripts\python.exe scripts\gee\export_mndwi_2024_pilot.py --start
```

任务输出为2024年全研究区、20 m、EPSG:3857的单波段MNDWI Cloud Optimized GeoTIFF，NoData为`-9999`。工作负载标签为`hybas6-v1-2024-mndwi-pilot`，用于在Cloud Monitoring中单独核对EECU消耗。脚本会拒绝启动同名的活动任务。

## 验证

- `validate_water_thresholds_hybas6_v1.js`：2021年四阈值对比。
- `validate_water_shorelines_2019_2024_hybas6_v1_t000.js`：2019/2024岸线目视检查。
- `cross_validate_water_2018_landsat8_hybas6_v1_t000.js`：2018年跨传感器地图与指标。
- `export_water_cross_validation_2018_hybas6_v1.py`：2018年跨传感器指标批量导出。

所有导出先作为候选结果保存。不得将v0边界、v1统计或不同阈值结果混合晋级。

## 本地完整复验

从项目根目录运行：

```powershell
.\.venv\Scripts\python.exe scripts\validate_hybas6_v1_outputs.py `
  --boundary data\boundaries\zhaling_eling_watershed_hybas6_v1.geojson `
  --baseline-boundary data\boundaries\zhaling_eling_watershed_hybas6_v0.geojson `
  --overall data\processed\zhaling_eling_yearly_stats.csv `
  --subbasins data\processed\zhaling_eling_subbasin_yearly_stats.csv `
  --baseline-overall data\processed\candidates\zhaling_eling_yearly_stats_2018_2024_hybas6_v0_t000.csv `
  --threshold-validation data\processed\candidates\water_threshold_validation_2021_hybas6_v1.csv `
  --cross-validation data\processed\candidates\water_cross_validation_2018_s2_l8_hybas6_v1_t000_metrics_v1.csv `
  --baseline-cross-validation data\processed\candidates\water_cross_validation_2018_s2_l8_hybas6_v0_t000_metrics_v1.csv
```

验证脚本同时检查参考点归属、v0/v1外边界等价、总体回归、分区汇总、阈值年度自洽和跨传感器回归。候选目录不纳入 Git，复验前需确保上述原始导出仍在本地。
