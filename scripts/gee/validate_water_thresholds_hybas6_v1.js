// hybas6_v1 水体阈值验证
// 验证年份：2021
// 阈值：-0.1、0、0.1、0.2

var roiCollection = ee.FeatureCollection(
  'projects/careful-form-499402-d0/assets/' +
  'zhaling_eling_watershed_hybas6_v1'
);

var roi = roiCollection.geometry().dissolve(1);

var validationYear = 2021;
var statisticsScale = 20;

var thresholdSpecs = [
  {key: 'tm010', value: -0.1, color: 'FFA500'},
  {key: 't000', value: 0.0, color: 'FFFF00'},
  {key: 't010', value: 0.1, color: '0000FF'},
  {key: 't020', value: 0.2, color: 'FF00FF'}
];


// 1. Sentinel-2 云雪掩膜：必须与正式统计脚本一致

function maskS2(image) {
  var scl = image.select('SCL');

  var clear = scl.neq(3)
    .and(scl.neq(8))
    .and(scl.neq(9))
    .and(scl.neq(10))
    .and(scl.neq(11));

  return image
    .updateMask(clear)
    .copyProperties(image, ['system:time_start']);
}


// 2. 构建2021年6—9月中位数合成影像

var start = ee.Date.fromYMD(validationYear, 6, 1);
var end = ee.Date.fromYMD(validationYear, 10, 1);

var collection = ee.ImageCollection(
  'COPERNICUS/S2_SR_HARMONIZED'
)
  .filterBounds(roi)
  .filterDate(start, end)
  .filter(
    ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40)
  )
  .map(maskS2);

var composite = collection
  .median()
  .clip(roi);

var mndwi = composite
  .normalizedDifference(['B3', 'B11'])
  .rename('MNDWI');

var validObservationCount = collection
  .select('B4')
  .count()
  .clip(roi);


// 3. 基础显示图层

Map.setOptions('SATELLITE');
Map.centerObject(roiCollection, 7);

Map.addLayer(
  composite,
  {
    bands: ['B4', 'B3', 'B2'],
    min: 0,
    max: 3000
  },
  '2021 真彩色',
  true
);

Map.addLayer(
  mndwi,
  {
    min: -0.5,
    max: 0.5,
    palette: ['brown', 'white', 'blue']
  },
  '2021 MNDWI',
  false
);

Map.addLayer(
  validObservationCount,
  {
    min: 1,
    max: 30,
    palette: ['red', 'yellow', 'green']
  },
  '2021 有效观测次数',
  false
);


// 4. 添加四个候选水体图层

thresholdSpecs.forEach(function(spec) {
  var water = mndwi
    .gt(spec.value)
    .selfMask();

  Map.addLayer(
    water,
    {palette: [spec.color]},
    '2021 水体 MNDWI > ' + spec.value,
    false
  );
});


// 5. ESA WorldCover 2021永久水体参考

var worldCover = ee.ImageCollection(
  'ESA/WorldCover/v200'
).first().select('Map');

var worldCoverWater = worldCover
  .eq(80)
  .clip(roi);

Map.addLayer(
  worldCoverWater.selfMask(),
  {palette: ['00FF00']},
  'ESA WorldCover 2021 永久水体',
  false
);


// 6. JRC长期稳定水体参考

var jrcOccurrence = ee.Image(
  'JRC/GSW1_4/GlobalSurfaceWater'
).select('occurrence');

var jrcStableWater = jrcOccurrence
  .gte(90)
  .selfMask()
  .clip(roi);

Map.addLayer(
  jrcStableWater,
  {palette: ['FFFFFF']},
  'JRC 长期稳定水体 >= 90%',
  false
);


// 7. 研究区外边界

Map.addLayer(
  roiCollection.style({
    color: 'FF0000',
    fillColor: '00000000',
    width: 2
  }),
  {},
  'hybas6_v1 五子流域边界',
  true
);


// 8. 一次计算四个阈值的面积及WorldCover重叠情况

var pixelAreaKm2 = ee.Image
  .pixelArea()
  .divide(1000000);

var metricBands = [
  pixelAreaKm2
    .updateMask(worldCoverWater)
    .rename('wc_water_area_km2')
];

thresholdSpecs.forEach(function(spec) {
  var predictedWater = mndwi.gt(spec.value);

  metricBands.push(
    pixelAreaKm2
      .updateMask(predictedWater)
      .rename('water_' + spec.key)
  );

  metricBands.push(
    pixelAreaKm2
      .updateMask(
        predictedWater.and(worldCoverWater)
      )
      .rename('overlap_' + spec.key)
  );
});

var metricStack = metricBands[0];

for (var i = 1; i < metricBands.length; i++) {
  metricStack = metricStack.addBands(
    metricBands[i]
  );
}

var metricAreas = metricStack.reduceRegion({
  reducer: ee.Reducer.sum(),
  geometry: roi,
  scale: statisticsScale,
  tileScale: 4,
  maxPixels: 1e13
});

var wcWaterArea = ee.Number(
  metricAreas.get('wc_water_area_km2')
);

var t010Area = ee.Number(
  metricAreas.get('water_t010')
);

var resultRows = thresholdSpecs.map(
  function(spec) {
    var waterArea = ee.Number(
      metricAreas.get('water_' + spec.key)
    );

    var overlapArea = ee.Number(
      metricAreas.get('overlap_' + spec.key)
    );

    return ee.Feature(null, {
      year: validationYear,
      threshold: spec.value,
      image_count: collection.size(),
      water_area_km2: waterArea,

      area_difference_from_t010_km2:
        waterArea.subtract(t010Area),

      worldcover_water_coverage:
        overlapArea.divide(wcWaterArea),

      worldcover_overlap_share:
        overlapArea.divide(waterArea),

      roi_version: 'hybas6_v1',
      scale_m: statisticsScale
    });
  }
);

var validationResults = ee.FeatureCollection(
  resultRows
);


// 9. 只输出轻量Console信息

print('验证年份', validationYear);
print('2021影像数量', collection.size());
print('研究区元数据', roiCollection.first());


// 10. 通过批处理导出阈值验证表

Export.table.toDrive({
  collection: validationResults,
  description:
    'water_threshold_validation_2021_hybas6_v1',
  folder: 'SRT_GEE_exports',
  fileNamePrefix:
    'water_threshold_validation_2021_hybas6_v1',
  fileFormat: 'CSV',
  selectors: [
    'year',
    'threshold',
    'image_count',
    'water_area_km2',
    'area_difference_from_t010_km2',
    'worldcover_water_coverage',
    'worldcover_overlap_share',
    'roi_version',
    'scale_m'
  ]
});
