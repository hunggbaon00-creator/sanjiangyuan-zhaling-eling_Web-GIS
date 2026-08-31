# 年度栅格瓦片接入契约

## 目标

页面通过版本化清单读取年度XYZ瓦片，不在访问过程中请求在线计算，也不依赖短期Map ID或临时令牌。正式瓦片尚未生产时，页面必须显示真实状态并继续使用已验证的本地矢量与统计图层，不得加载替代影像。

契约文件：

- `config/raster_layers.json`：项目实际使用的图层、年份、渲染和资产状态。
- `config/raster_layers.schema.json`：JSON Schema结构约束。
- `app/raster_tiles.py`：运行时严格校验、图层年份解析和Folium瓦片参数适配。

## 固定空间与计算口径

| 项目 | 契约值 |
| --- | --- |
| 数据版本 | `hybas6_v1_t000` |
| 年份 | 2018—2024 |
| 瓦片方案 | XYZ |
| 瓦片坐标系 | EPSG:3857 |
| 缩放级别 | 5—13 |
| 边界范围 | `[95.90833420357303, 33.94583428316831, 98.82083175391062, 35.47535499778]` |
| 数据源 | `COPERNICUS/S2_SR_HARMONIZED` |
| 生长季 | 6月1日至10月1日，结束日不含 |
| 云掩膜 | SCL排除3、8、9、10、11 |
| 年度合成 | 中位数 |
| 尺度 | 20 m |
| 水体规则 | `MNDWI > 0.0` |

清单声明五类产品：年度真彩色、NDVI、MNDWI、水体掩膜和有效观测掩膜。每类产品必须完整声明2018—2024七个年份，不能因某一年缺失而回退到其他年份。

## 资产状态

| 状态 | 含义 | 是否允许瓦片地址 |
| --- | --- | --- |
| `not_generated` | 尚未启动正式生产 | 否 |
| `processing` | 正在生产或发布 | 否 |
| `ready` | 已完成验证并可供页面读取 | 是，且必须完整 |
| `failed` | 生产或验证失败 | 否 |
| `unavailable` | 已确认当前不提供 | 否 |

正常晋级路径为：

```text
not_generated → processing → ready
                         ↘ failed → processing
```

`ready`资产必须同时声明：

- 公开的HTTPS XYZ模板，且包含`{z}`、`{x}`、`{y}`。
- 不含查询参数或URL片段，防止提交短期令牌或签名信息。
- ISO 8601生成时间。
- 来源栅格或发布包的64位小写SHA-256。
- 唯一资产版本。
- 数据来源署名。

示例：

```json
{
  "status": "ready",
  "url_template": "https://tiles.example.org/ndvi/2024/{z}/{x}/{y}.png",
  "generated_at": "2026-09-01T08:30:00Z",
  "source_checksum_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "asset_version": "hybas6_v1_t000_2024_ndvi_v1",
  "notes": "已完成范围、NoData、岸线和加载性能验证。"
}
```

## 晋级操作

1. 将对应图层年份改为`processing`，发布元数据保持为空。
2. 生产候选栅格或瓦片并完成范围、分辨率、NoData、色带、岸线和加载速度检查。
3. 将瓦片发布到稳定的HTTPS静态地址或瓦片服务；网页端不得携带私密访问凭据。
4. 计算来源文件或发布包SHA-256，填写生成时间与资产版本。
5. 将状态改为`ready`。
6. 执行：

```powershell
.\.venv\Scripts\python.exe scripts\validate_raster_tile_manifest.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

7. 启动页面，验证年份切换、图层透明度、选区边界、图例和瓦片加载。

当前清单的35个图层年份资产全部为`not_generated`。因此页面只展示状态，不产生任何栅格瓦片请求，也不消耗GEE计算额度。
