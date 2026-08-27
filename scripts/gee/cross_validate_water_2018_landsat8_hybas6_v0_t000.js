// hybas6_v0 / t000：2018 年 Landsat 8 独立交叉验证
//
// Sentinel-2 与 Landsat 8 分别构建 2018 年 6—9 月中位数合成影像，
// 使用相同的 MNDWI > 0 判定开阔水体，并在 Landsat 8 的 30 m 网格上
// 统计两者共同有效区域内的重叠程度。另对 Sentinel-2 缺失区进行
// Landsat 8、JRC 长期稳定水体和 WorldCover 永久水体风险检查。

var roiCollection = ee.FeatureCollection(
  'projects/careful-form-499402-d0/assets/' +
  'zhaling_eling_watershed_hybas6_v0'
);
var roi = roiCollection.geometry();

var validationYear = 2018;
var waterThreshold = 0.0;
var comparisonScale = 30;
var exportName =
  'water_cross_validation_2018_s2_l8_hybas6_v0_t000_metrics_v1';

var start = ee.Date.fromYMD(validationYear, 6, 1);
var end = ee.Date.fromYMD(validationYear, 10, 1);


// 1. Sentinel-2：保持与正式年度统计脚本相同的掩膜和合成方法。

function maskS2(image) {
  var scl = image.select('SCL');
  var clear = scl.neq(3)
    .and(scl.neq(8))
    .and(scl.neq(9))
    .and(scl.neq(10))
    .and(scl.neq(11));

  return image.updateMask(clear)
    .copyProperties(image, ['system:time_start']);
}

var s2Collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(roi)
  .filterDate(start, end)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
  .map(maskS2);

var s2Composite = s2Collection.median().clip(roi);
var s2Mndwi = s2Composite
  .normalizedDifference(['B3', 'B11'])
  .rename('S2_MNDWI');
var s2Water = s2Mndwi.gt(waterThreshold).rename('S2_water');


// 2. Landsat 8 Collection 2 Level 2：QA_PIXEL 去除云、阴影和雪，
//    QA_RADSAT 去除饱和像元，并应用官方地表反射率缩放系数。

function prepareLandsat8(image) {
  var qa = image.select('QA_PIXEL');

  var clear = qa.bitwiseAnd(1 << 0).eq(0)
    .and(qa.bitwiseAnd(1 << 1).eq(0))
    .and(qa.bitwiseAnd(1 << 2).eq(0))
    .and(qa.bitwiseAnd(1 << 3).eq(0))
    .and(qa.bitwiseAnd(1 << 4).eq(0))
    .and(qa.bitwiseAnd(1 << 5).eq(0));

  var notSaturated = image.select('QA_RADSAT').eq(0);
  var optical = image.select('SR_B.')
    .multiply(0.0000275)
    .add(-0.2);

  return image
    .addBands(optical, null, true)
    .updateMask(clear)
    .updateMask(notSaturated)
    .copyProperties(image, ['system:time_start']);
}

var l8Collection = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
  .filterBounds(roi)
  .filterDate(start, end)
  .filter(ee.Filter.lt('CLOUD_COVER', 40))
  .map(prepareLandsat8);

var l8Composite = l8Collection.median().clip(roi);

// expression 不会因缩放后出现负反射率而自动屏蔽像元。
var l8Mndwi = l8Composite.expression(
  '(green - swir1) / (green + swir1)',
  {
    green: l8Composite.select('SR_B3'),
    swir1: l8Composite.select('SR_B6')
  }
).rename('L8_MNDWI');

var l8Water = l8Mndwi.gt(waterThreshold).rename('L8_water');


// 3. 只在两种传感器都存在有效合成值的位置进行一致性比较。

// 以 MNDWI 本身的掩膜定义有效区，确保 Green 和 SWIR1 都有值。
// unmask(0) 使缺失区成为显式的 0，便于计算补集。
var s2Valid = s2Mndwi.mask()
  .gt(0)
  .unmask(0)
  .clip(roi)
  .rename('S2_valid');
var l8Valid = l8Mndwi.mask()
  .gt(0)
  .unmask(0)
  .clip(roi)
  .rename('L8_valid');
var commonValid = s2Valid.and(l8Valid).rename('common_valid');
var s2Missing = s2Valid.not().rename('S2_missing');
var l8Missing = l8Valid.not().rename('L8_missing');
var l8ValidOutsideS2 = l8Valid
  .and(s2Missing)
  .rename('L8_valid_outside_S2');

var s2WaterFull = s2Water.updateMask(s2Valid);
var l8WaterFull = l8Water.updateMask(l8Valid);
var s2WaterCommon = s2Water.updateMask(commonValid);
var l8WaterCommon = l8Water.updateMask(commonValid);
var l8WaterOutsideS2 = l8Water
  .and(l8ValidOutsideS2)
  .rename('L8_water_outside_S2');
var intersection = s2WaterCommon
  .and(l8WaterCommon)
  .rename('intersection');
var union = s2WaterCommon
  .or(l8WaterCommon)
  .rename('union');
var s2Only = s2WaterCommon
  .and(l8WaterCommon.not())
  .rename('S2_only');
var l8Only = l8WaterCommon
  .and(s2WaterCommon.not())
  .rename('L8_only');

// 1 = 仅 Sentinel-2，2 = 仅 Landsat 8，3 = 两者一致为水体。
var comparison = s2WaterCommon.multiply(0)
  .where(s2Only, 1)
  .where(l8Only, 2)
  .where(intersection, 3)
  .updateMask(union)
  .rename('comparison');


// 4. 辅助参考数据只用于判断 Sentinel-2 缺失区是否可能漏掉水体。
//    WorldCover 为 2021 年产品，不能直接替代 2018 年观测。

var jrcStableWater = ee.Image(
  'JRC/GSW1_4/GlobalSurfaceWater'
).select('occurrence')
  .gte(90)
  .unmask(0)
  .clip(roi)
  .rename('JRC_stable_water');

var worldCoverWater = ee.ImageCollection('ESA/WorldCover/v200')
  .first()
  .select('Map')
  .eq(80)
  .unmask(0)
  .clip(roi)
  .rename('WorldCover_water');

var jrcWaterOutsideS2 = jrcStableWater
  .and(s2Missing)
  .rename('JRC_water_outside_S2');
var worldCoverWaterOutsideS2 = worldCoverWater
  .and(s2Missing)
  .rename('WorldCover_water_outside_S2');
var l8JrcOverlapOutsideS2 = l8WaterOutsideS2
  .and(jrcWaterOutsideS2)
  .rename('L8_JRC_overlap_outside_S2');
var l8WorldCoverOverlapOutsideS2 = l8WaterOutsideS2
  .and(worldCoverWaterOutsideS2)
  .rename('L8_WorldCover_overlap_outside_S2');


// 5. 在 Landsat 8 的 30 m 网格上计算一致性、覆盖率和缺失区风险指标。

var pixelAreaKm2 = ee.Image.pixelArea().divide(1000000);

function areaBand(mask, name) {
  return pixelAreaKm2.updateMask(mask).rename(name);
}

var metricBands = [
  pixelAreaKm2.rename('roi_area_km2'),
  areaBand(s2Valid, 's2_valid_area_km2'),
  areaBand(l8Valid, 'l8_valid_area_km2'),
  areaBand(commonValid, 'common_valid_area_km2'),
  areaBand(s2Missing, 's2_missing_area_km2'),
  areaBand(l8Missing, 'l8_missing_area_km2'),
  areaBand(l8ValidOutsideS2, 'l8_valid_outside_s2_area_km2'),
  areaBand(s2WaterFull, 's2_water_full_valid_area_km2'),
  areaBand(l8WaterFull, 'l8_water_full_valid_area_km2'),
  areaBand(s2WaterCommon, 's2_water_area_km2'),
  areaBand(l8WaterCommon, 'l8_water_area_km2'),
  areaBand(l8WaterOutsideS2, 'l8_water_outside_s2_valid_area_km2'),
  areaBand(jrcWaterOutsideS2, 'jrc_water_outside_s2_area_km2'),
  areaBand(
    worldCoverWaterOutsideS2,
    'worldcover_water_outside_s2_area_km2'
  ),
  areaBand(
    l8JrcOverlapOutsideS2,
    'l8_jrc_overlap_outside_s2_area_km2'
  ),
  areaBand(
    l8WorldCoverOverlapOutsideS2,
    'l8_worldcover_overlap_outside_s2_area_km2'
  ),
  areaBand(intersection, 'intersection_area_km2'),
  areaBand(union, 'union_area_km2')
];

var metricStack = metricBands[0];
for (var i = 1; i < metricBands.length; i++) {
  metricStack = metricStack.addBands(metricBands[i]);
}

// 合成影像可能带有默认投影；取实际 Landsat 场景的 30 m 投影作为共同网格。
var l8Projection = ee.Image(l8Collection.first())
  .select('SR_B3')
  .projection();

var areas = metricStack.reduceRegion({
  reducer: ee.Reducer.sum(),
  geometry: roi,
  scale: comparisonScale,
  crs: l8Projection,
  tileScale: 4,
  maxPixels: 1e13
});

var roiArea = ee.Number(areas.get('roi_area_km2'));
var s2ValidArea = ee.Number(areas.get('s2_valid_area_km2'));
var l8ValidArea = ee.Number(areas.get('l8_valid_area_km2'));
var commonValidArea = ee.Number(areas.get('common_valid_area_km2'));
var s2MissingArea = ee.Number(areas.get('s2_missing_area_km2'));
var l8MissingArea = ee.Number(areas.get('l8_missing_area_km2'));
var l8ValidOutsideS2Area = ee.Number(
  areas.get('l8_valid_outside_s2_area_km2')
);
var s2WaterFullArea = ee.Number(
  areas.get('s2_water_full_valid_area_km2')
);
var l8WaterFullArea = ee.Number(
  areas.get('l8_water_full_valid_area_km2')
);
var s2WaterArea = ee.Number(areas.get('s2_water_area_km2'));
var l8WaterArea = ee.Number(areas.get('l8_water_area_km2'));
var l8WaterOutsideS2Area = ee.Number(
  areas.get('l8_water_outside_s2_valid_area_km2')
);
var jrcWaterOutsideS2Area = ee.Number(
  areas.get('jrc_water_outside_s2_area_km2')
);
var worldCoverWaterOutsideS2Area = ee.Number(
  areas.get('worldcover_water_outside_s2_area_km2')
);
var l8JrcOverlapOutsideS2Area = ee.Number(
  areas.get('l8_jrc_overlap_outside_s2_area_km2')
);
var l8WorldCoverOverlapOutsideS2Area = ee.Number(
  areas.get('l8_worldcover_overlap_outside_s2_area_km2')
);
var intersectionArea = ee.Number(areas.get('intersection_area_km2'));
var unionArea = ee.Number(areas.get('union_area_km2'));

function safeDivide(numerator, denominator) {
  return numerator.divide(denominator.max(1e-12));
}

var validationResult = ee.Feature(null, {
  year: validationYear,
  s2_image_count: s2Collection.size(),
  l8_image_count: l8Collection.size(),
  s2_threshold: waterThreshold,
  l8_threshold: waterThreshold,
  roi_area_km2: roiArea,
  s2_valid_area_km2: s2ValidArea,
  s2_valid_share: safeDivide(s2ValidArea, roiArea),
  l8_valid_area_km2: l8ValidArea,
  l8_valid_share: safeDivide(l8ValidArea, roiArea),
  common_valid_area_km2: commonValidArea,
  common_valid_share: safeDivide(commonValidArea, roiArea),
  s2_missing_area_km2: s2MissingArea,
  s2_missing_share: safeDivide(s2MissingArea, roiArea),
  l8_missing_area_km2: l8MissingArea,
  l8_missing_share: safeDivide(l8MissingArea, roiArea),
  l8_valid_outside_s2_area_km2: l8ValidOutsideS2Area,
  s2_water_full_valid_area_km2: s2WaterFullArea,
  l8_water_full_valid_area_km2: l8WaterFullArea,
  s2_water_common_capture_share:
    safeDivide(s2WaterArea, s2WaterFullArea),
  l8_water_common_capture_share:
    safeDivide(l8WaterArea, l8WaterFullArea),
  // 以下两个旧字段继续表示“共同有效区内水体面积”，保留以兼容基线 CSV。
  s2_water_area_km2: s2WaterArea,
  l8_water_area_km2: l8WaterArea,
  l8_water_outside_s2_valid_area_km2: l8WaterOutsideS2Area,
  l8_water_outside_s2_share:
    safeDivide(l8WaterOutsideS2Area, l8WaterFullArea),
  s2_l8_gapfill_water_area_km2:
    s2WaterFullArea.add(l8WaterOutsideS2Area),
  l8_gapfill_addition_vs_s2_share:
    safeDivide(l8WaterOutsideS2Area, s2WaterFullArea),
  area_difference_l8_full_minus_s2_full_km2:
    l8WaterFullArea.subtract(s2WaterFullArea),
  jrc_water_outside_s2_area_km2: jrcWaterOutsideS2Area,
  worldcover_water_outside_s2_area_km2:
    worldCoverWaterOutsideS2Area,
  l8_jrc_overlap_outside_s2_area_km2:
    l8JrcOverlapOutsideS2Area,
  l8_jrc_coverage_outside_s2:
    safeDivide(l8JrcOverlapOutsideS2Area, jrcWaterOutsideS2Area),
  l8_gap_water_jrc_overlap_share:
    safeDivide(l8JrcOverlapOutsideS2Area, l8WaterOutsideS2Area),
  l8_worldcover_overlap_outside_s2_area_km2:
    l8WorldCoverOverlapOutsideS2Area,
  l8_worldcover_coverage_outside_s2:
    safeDivide(
      l8WorldCoverOverlapOutsideS2Area,
      worldCoverWaterOutsideS2Area
    ),
  l8_gap_water_worldcover_overlap_share:
    safeDivide(l8WorldCoverOverlapOutsideS2Area, l8WaterOutsideS2Area),
  intersection_area_km2: intersectionArea,
  union_area_km2: unionArea,
  iou: safeDivide(intersectionArea, unionArea),
  dice: safeDivide(
    intersectionArea.multiply(2),
    s2WaterArea.add(l8WaterArea)
  ),
  s2_covered_by_l8: safeDivide(intersectionArea, s2WaterArea),
  l8_covered_by_s2: safeDivide(intersectionArea, l8WaterArea),
  area_difference_l8_minus_s2_km2:
    l8WaterArea.subtract(s2WaterArea),
  roi_version: 'hybas6_v0',
  comparison_scale_m: comparisonScale
});

var validationResults = ee.FeatureCollection([validationResult]);


// 6. 可视化：绿色为两者一致，蓝色仅 Sentinel-2，洋红仅 Landsat 8。

Map.setOptions('SATELLITE');
Map.centerObject(roiCollection, 7);

Map.addLayer(
  l8Composite,
  {bands: ['SR_B4', 'SR_B3', 'SR_B2'], min: 0, max: 0.3},
  '2018 Landsat 8 真彩色',
  true
);

Map.addLayer(
  s2Composite,
  {bands: ['B4', 'B3', 'B2'], min: 0, max: 3000},
  '2018 Sentinel-2 真彩色',
  false
);

Map.addLayer(
  comparison,
  {
    min: 1,
    max: 3,
    palette: ['0000FF', 'FF00FF', '00FF00']
  },
  '2018 S2-L8 水体一致性（蓝/S2，洋红/L8，绿/共同）',
  true,
  0.7
);

Map.addLayer(
  s2WaterCommon.selfMask(),
  {palette: ['0000FF']},
  '2018 Sentinel-2 t000 水体（共同有效区）',
  false,
  0.6
);

Map.addLayer(
  l8WaterCommon.selfMask(),
  {palette: ['FF00FF']},
  '2018 Landsat 8 t000 水体（共同有效区）',
  false,
  0.6
);

Map.addLayer(
  s2Mndwi,
  {min: -0.5, max: 0.5, palette: ['8B4513', 'FFFFFF', '0000FF']},
  '2018 Sentinel-2 MNDWI',
  false
);

Map.addLayer(
  l8Mndwi,
  {min: -0.5, max: 0.5, palette: ['8B4513', 'FFFFFF', 'FF00FF']},
  '2018 Landsat 8 MNDWI',
  false
);

Map.addLayer(
  s2Collection.select('B4').count().clip(roi),
  {min: 1, max: 10, palette: ['FF0000', 'FFFF00', '008000']},
  '2018 Sentinel-2 有效观测次数',
  false
);

Map.addLayer(
  l8Collection.select('SR_B4').count().clip(roi),
  {min: 1, max: 10, palette: ['FF0000', 'FFFF00', '008000']},
  '2018 Landsat 8 有效观测次数',
  false
);

Map.addLayer(
  commonValid.selfMask(),
  {palette: ['FFFFFF']},
  '2018 两传感器共同有效区域',
  false,
  0.4
);

Map.addLayer(
  l8ValidOutsideS2.selfMask(),
  {palette: ['FFFF00']},
  '2018 Landsat 8 有效但 Sentinel-2 缺失区',
  false,
  0.35
);

Map.addLayer(
  l8WaterOutsideS2.selfMask(),
  {palette: ['FF00FF']},
  '2018 Sentinel-2 缺失区内 Landsat 8 t000 水体',
  false,
  0.8
);

Map.addLayer(
  jrcWaterOutsideS2.selfMask(),
  {palette: ['FFFFFF']},
  'Sentinel-2 缺失区内 JRC 长期稳定水体 >= 90%',
  false,
  0.8
);

Map.addLayer(
  worldCoverWaterOutsideS2.selfMask(),
  {palette: ['00FFFF']},
  'Sentinel-2 缺失区内 WorldCover 2021 永久水体（辅助）',
  false,
  0.7
);

Map.addLayer(
  roiCollection.style({
    color: 'FF0000',
    fillColor: '00000000',
    width: 2
  }),
  {},
  'hybas6_v0 研究区边界',
  true
);

print('2018 Sentinel-2 影像数量', s2Collection.size());
print('2018 Landsat 8 影像数量', l8Collection.size());
print(
  '结果说明',
  '请通过 Tasks 导出 metrics_v1 CSV；重点检查覆盖率、Landsat 8 在 ' +
    'Sentinel-2 缺失区的水体面积，以及 JRC/WorldCover 辅助覆盖指标。' +
    '不要在 Console 展开面积字典，以减少同步计算压力。'
);


// 7. 导出独立交叉验证指标。

Export.table.toDrive({
  collection: validationResults,
  description: exportName,
  folder: 'SRT_GEE_exports',
  fileNamePrefix: exportName,
  fileFormat: 'CSV',
  selectors: [
    'year',
    's2_image_count',
    'l8_image_count',
    's2_threshold',
    'l8_threshold',
    'roi_area_km2',
    's2_valid_area_km2',
    's2_valid_share',
    'l8_valid_area_km2',
    'l8_valid_share',
    'common_valid_area_km2',
    'common_valid_share',
    's2_missing_area_km2',
    's2_missing_share',
    'l8_missing_area_km2',
    'l8_missing_share',
    'l8_valid_outside_s2_area_km2',
    's2_water_full_valid_area_km2',
    'l8_water_full_valid_area_km2',
    's2_water_common_capture_share',
    'l8_water_common_capture_share',
    's2_water_area_km2',
    'l8_water_area_km2',
    'l8_water_outside_s2_valid_area_km2',
    'l8_water_outside_s2_share',
    's2_l8_gapfill_water_area_km2',
    'l8_gapfill_addition_vs_s2_share',
    'area_difference_l8_full_minus_s2_full_km2',
    'jrc_water_outside_s2_area_km2',
    'worldcover_water_outside_s2_area_km2',
    'l8_jrc_overlap_outside_s2_area_km2',
    'l8_jrc_coverage_outside_s2',
    'l8_gap_water_jrc_overlap_share',
    'l8_worldcover_overlap_outside_s2_area_km2',
    'l8_worldcover_coverage_outside_s2',
    'l8_gap_water_worldcover_overlap_share',
    'intersection_area_km2',
    'union_area_km2',
    'iou',
    'dice',
    's2_covered_by_l8',
    'l8_covered_by_s2',
    'area_difference_l8_minus_s2_km2',
    'roi_version',
    'comparison_scale_m'
  ]
});
