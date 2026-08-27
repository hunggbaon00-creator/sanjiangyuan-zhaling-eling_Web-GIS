# 处理后数据说明

## 正式文件

Streamlit 当前只读取：

```text
data/processed/zhaling_eling_yearly_stats.csv
```

该文件由以下已验证候选文件晋级而来，两者 SHA-256 一致：

```text
data/processed/candidates/zhaling_eling_yearly_stats_2018_2024_hybas6_v0_t000.csv
```

当前正式口径为 `hybas6_v0_t000`：2018—2024 年、Sentinel-2 SR Harmonized、每年 6 月 1 日至 9 月 30 日、20 m、`MNDWI > 0.0`。

## 字段定义

| 字段 | 含义 |
| --- | --- |
| `year` | 统计年份 |
| `image_count` | 当年进入合成的影像数量 |
| `roi_area_km2` | 研究区面积，平方千米 |
| `valid_area_km2` | 年度合成中至少有一次有效观测的面积，平方千米 |
| `valid_share` | `valid_area_km2 / roi_area_km2` |
| `coverage_flag` | 有效覆盖等级：`high`、`medium` 或 `low` |
| `ndvi_mean` | 有效区域内的年度平均 NDVI |
| `mndwi_mean` | 有效区域内的年度平均 MNDWI |
| `water_area_km2` | 满足 `MNDWI > water_threshold` 的有效像元面积 |
| `water_threshold` | 水体识别阈值，当前为 `0.0` |
| `roi_version` | 研究区版本，当前为 `hybas6_v0` |
| `statistics_scale_m` | GEE 统计尺度，当前为 20 m |

覆盖等级规则：

- `high`：`valid_share >= 0.95`
- `medium`：`0.80 <= valid_share < 0.95`
- `low`：`valid_share < 0.80`

## 当前质量结论

- 2018 年 `valid_share = 0.6522`，等级为 `low`；水体面积 `1517.62 km²` 受 Sentinel-2 覆盖限制，结合 Landsat 8 独立验证可能约低估 2%。
- 2019—2024 年覆盖等级均为 `high`。
- `t000` 已通过 2021 年多阈值对比、2019/2024 年岸线检查和 2018 年 Landsat 8 交叉验证。
- 当前 GeoJSON 是 5 个六级子流域融合后的单一外边界；5 个子流域内部边界留待 v1 重新生成。

## 候选文件晋级流程

1. 新导出文件进入 `data/processed/candidates/`，不得直接覆盖正式文件。
2. 检查年份为 2018—2024、每年仅一条记录且必需字段无缺失。
3. 检查所有记录的 `roi_version`、`water_threshold` 和 `statistics_scale_m` 一致。
4. 检查 `valid_share` 范围、覆盖等级及异常年份，并完成所需验证。
5. 将通过验证的唯一候选复制为 `zhaling_eling_yearly_stats.csv`。
6. 启动 Streamlit 完成页面复核，再提交正式文件。

## Git 跟踪规则

- 跟踪：本 README、`zhaling_eling_yearly_stats.csv`、正式边界 GeoJSON、脚本和应用代码。
- 不跟踪：`candidates/`、`archive/`、其他临时导出和大体量栅格文件。
- 历史正式版本通过 Git commit/tag 恢复；本地 `archive/` 只作为临时备份，不作为版本来源。
