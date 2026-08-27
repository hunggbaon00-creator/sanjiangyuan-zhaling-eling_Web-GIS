# 处理后数据说明

## 正式文件

| 文件 | 行数 | 用途 |
| --- | ---: | --- |
| `zhaling_eling_yearly_stats.csv` | 7 | 研究区总体年度统计 |
| `zhaling_eling_subbasin_yearly_stats.csv` | 35 | 5个子流域的年度统计 |

当前口径为 `hybas6_v1_t000`：2018—2024年、Sentinel-2 SR Harmonized、6月1日至9月30日、20 m、`MNDWI > 0.0`。

## 总体统计字段

`year`、`image_count`、`roi_area_km2`、`valid_area_km2`、`valid_share`、`coverage_flag`、`ndvi_mean`、`mndwi_mean`、`water_area_km2`、`water_threshold`、`roi_version`、`statistics_scale_m`。

## 分区统计字段

在覆盖率和指标字段之外增加：

- `subbasin_id`：SB01—SB05稳定分区编号。
- `subbasin_name`：项目显示名称。
- `hybas_id`、`next_down`：HydroBASINS标识及下游拓扑。
- `subbasin_area_km2`：20 m栅格口径分区面积。
- `image_count`：当年与该子流域相交且通过场景云量过滤的影像数。

覆盖等级规则：`high >= 0.95`；`0.80 <= medium < 0.95`；`low < 0.80`。

## 质量结论

- v1五区合并几何与v0外边界对称差为0。
- 总体统计使用 `FeatureCollection.geometry().dissolve(1)`，避免内部边界影响栅格聚合。
- v1总体结果与v0保持同一数值口径。
- 2018年总体覆盖等级为 `low`，水体面积可能低估约2%；其余年份为 `high`。
- `t000` 已重新执行阈值、岸线及2018跨传感器验证。

完整验证证据和阈值旧基线说明见 `docs/hybas6_v1_t000_validation.md`。

## 候选晋级

1. 原始导出保存到 `data/processed/candidates/`。
2. 检查边界5个Feature、总体7行、分区35行及唯一键。
3. 检查版本、阈值、尺度、空值、数值范围和覆盖等级。
4. 检查v1总体与v0回归，以及每年五区面积汇总与总体结果的一致性。
5. 验证通过后复制为上述正式文件并启动 Streamlit 复核。

候选文件、旧数据副本和大体量栅格不纳入 Git；正式历史通过 commit 和 tag 恢复。
