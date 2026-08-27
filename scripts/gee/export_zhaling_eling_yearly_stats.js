// 扎陵湖—鄂陵湖候选汇水区 hybas6_v0
var roiCollection = ee.FeatureCollection(
  'projects/careful-form-499402-d0/assets/zhaling_eling_watershed_hybas6_v0'
);
var roi = roiCollection.geometry();

var startYear = 2018;
var endYear = 2024;
var waterThreshold = 0.0;
var statisticsScale = 20;
var highCoverageThreshold = 0.95;
var mediumCoverageThreshold = 0.80;
var exportName =
  'zhaling_eling_yearly_stats_2018_2024_hybas6_v0_t000';

// 有效覆盖面积和 ROI 面积必须使用同一像元面积影像、比例尺和区域，
// 才能保证 valid_share 的分子与分母口径一致。
var pixelAreaKm2 = ee.Image.pixelArea().divide(1000000);
var roiAreaKm2 = ee.Number(pixelAreaKm2.reduceRegion({
  reducer: ee.Reducer.sum(),
  geometry: roi,
  scale: statisticsScale,
  tileScale: 4,
  maxPixels: 1e13
}).get('area'));

Map.centerObject(roiCollection, 7);
Map.addLayer(
  roiCollection.style({
    color: 'FF0000',
    fillColor: 'FF000020',
    width: 2
  }),
  {},
  'hybas6_v0 研究区边界'
);

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

function yearlyFeature(year) {
  year = ee.Number(year);

  var start = ee.Date.fromYMD(year, 6, 1);
  // filterDate 的结束日期不包含当天，因此用 10 月 1 日覆盖完整的 6—9 月。
  var end = ee.Date.fromYMD(year, 10, 1);

  var collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(roi)
    .filterDate(start, end)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
    .map(maskS2);

  var composite = collection.median().clip(roi);

  var ndvi = composite.normalizedDifference(['B8', 'B4']).rename('NDVI');
  var mndwi = composite.normalizedDifference(['B3', 'B11']).rename('MNDWI');
  var water = mndwi.gt(waterThreshold).rename('water');
  var validMask = mndwi.mask().gt(0).unmask(0).rename('valid');

  var means = ndvi.addBands(mndwi).reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: roi,
    scale: statisticsScale,
    tileScale: 4,
    maxPixels: 1e13
  });

  var areas = pixelAreaKm2.updateMask(validMask)
    .rename('valid_area_km2')
    .addBands(
      pixelAreaKm2.updateMask(water).rename('water_area_km2')
    )
    .reduceRegion({
      reducer: ee.Reducer.sum(),
      geometry: roi,
      scale: statisticsScale,
      tileScale: 4,
      maxPixels: 1e13
    });

  var validAreaKm2 = ee.Number(areas.get('valid_area_km2'));
  var validShare = validAreaKm2.divide(roiAreaKm2);
  var coverageFlag = ee.String(ee.Algorithms.If(
    validShare.gte(highCoverageThreshold),
    'high',
    ee.Algorithms.If(
      validShare.gte(mediumCoverageThreshold),
      'medium',
      'low'
    )
  ));

  return ee.Feature(null, {
    year: year,
    image_count: collection.size(),
    roi_area_km2: roiAreaKm2,
    valid_area_km2: validAreaKm2,
    valid_share: validShare,
    coverage_flag: coverageFlag,
    ndvi_mean: means.get('NDVI'),
    mndwi_mean: means.get('MNDWI'),
    water_area_km2: areas.get('water_area_km2'),
    water_threshold: waterThreshold,
    roi_version: 'hybas6_v0',
    statistics_scale_m: statisticsScale
  });
}

var years = ee.List.sequence(startYear, endYear);
var stats = ee.FeatureCollection(years.map(yearlyFeature));

print('研究区元数据', roiCollection.first());
print('栅格口径 ROI 面积 km²', roiAreaKm2);
print('覆盖等级规则', 'high >= 0.95；medium >= 0.80 且 < 0.95；low < 0.80');
print('年度统计结果', stats);

Export.table.toDrive({
  collection: stats,
  description: exportName,
  folder: 'SRT_GEE_exports',
  fileNamePrefix: exportName,
  fileFormat: 'CSV',
  selectors: [
    'year',
    'image_count',
    'roi_area_km2',
    'valid_area_km2',
    'valid_share',
    'coverage_flag',
    'ndvi_mean',
    'mndwi_mean',
    'water_area_km2',
    'water_threshold',
    'roi_version',
    'statistics_scale_m'
  ]
});



var visYear = 2024;

var visCollection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(roi)
  .filterDate(visYear + '-06-01', visYear + '-10-01')
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
  .map(maskS2);

var visComposite = visCollection.median().clip(roi);

var visNdvi = visComposite.normalizedDifference(['B8', 'B4']).rename('NDVI');
var visMndwi = visComposite.normalizedDifference(['B3', 'B11']).rename('MNDWI');
var visWater = visMndwi.gt(waterThreshold).selfMask();

Map.addLayer(
  visComposite,
  {bands: ['B4', 'B3', 'B2'], min: 0, max: 3000},
  '2024 真彩色'
);

Map.addLayer(
  visNdvi,
  {min: -0.2, max: 0.8, palette: ['brown', 'yellow', 'green']},
  '2024 NDVI'
);

Map.addLayer(
  visMndwi,
  {min: -0.5, max: 0.5, palette: ['brown', 'white', 'blue']},
  '2024 MNDWI'
);

Map.addLayer(
  visWater,
  {palette: ['blue']},
  '2024 水体识别'
);

print('2024 影像数量', visCollection.size());
