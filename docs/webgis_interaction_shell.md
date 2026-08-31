# WebGIS交互骨架开发记录

## 已完成：阶段0版本入口确认

- `hybas6_v1_t000` 已快进合并到 `main`。
- WebGIS交互开发基线为提交 `7b53897`。
- 当前开发分支为 `feature/webgis-interaction-shell`。
- 正式数据继续由 v1总体CSV、分区CSV和五 Feature GeoJSON提供。

## 已完成：阶段1统一状态模型

页面状态集中在 `app/webgis_state.py`，包含：

| 状态 | 含义 | 当前默认值 |
| --- | --- | --- |
| `selected_year` | 当前统计年份 | 最新正式年份 |
| `selected_metric` | 当前趋势指标 | 水体面积 |
| `selected_subbasin_id` | 当前子流域 | `None` |
| `view_scope` | 总体或分区范围 | `overall` |
| `active_layer` | 当前业务图层 | `boundary` |
| `layer_opacity` | 业务图层透明度 | `0.7` |

状态初始化会修复失效年份、未知指标、非法分区、不可用图层和越界透明度。`view_scope` 由子流域选择统一派生，避免两个状态相互矛盾。

`select_subbasin` 和 `select_overall` 是后续地图点击及侧栏选择共用的状态入口。当前页面尚未接入地图点击事件，因此默认继续展示总体统计。

## 验收范围

- v1合并后的 `main` 与远程一致。
- 新分支从 v1基线创建。
- 年份和指标控件直接绑定统一状态键。
- 默认状态、有效状态保留、陈旧状态修复、范围切换和非法分区均有自动测试。
- 本阶段不包含地图点击、双向联动、分区趋势切换或遥感瓦片。
