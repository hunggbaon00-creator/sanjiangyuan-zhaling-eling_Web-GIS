// 扎陵湖—鄂陵湖 hybas6_v1 总体与五子流域年度统计

var roiCollection = ee.FeatureCollection(
  'projects/careful-form-499402-d0/assets/' +
  'zhaling_eling_watershed_hybas6_v1'
).sort('subbasin_id');
// 展示保留5个Feature；总体统计使用消除内部边界后的合并几何。
var roi = roiCollection.geometry().dissolve(1);

var startYear = 2018;
var endYear = 2024;
var waterThreshold = 0.0;
var statisticsScale = 20;
var highCoverageThreshold = 0.95;
var mediumCoverageThreshold = 0.80;
var overallExportName =
  'zhaling_eling_yearly_stats_2018_2024_hybas6_v1_t000';
var subbasinExportName =
  'zhaling_eling_subbasin_yearly_stats_2018_2024_' +
  'hybas6_v1_t000';

var pixelAreaKm2 = ee.Image.pixelArea().divide(1000000);

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

function buildYearProducts(year) {
  year = ee.Number(year);
  var start = ee.Date.fromYMD(year, 6, 1);
  var end = ee.Date.fromYMD(year, 10, 1);
  var collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(roi)
    .filterDate(start, end)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
    .map(maskS2);
  var composite = collection.median().clip(roi);
  var ndvi = composite.normalizedDifference(['B8', 'B4']).rename('NDVI');
  var mndwi = composite.normalizedDifference(['B3', 'B11']).rename('MNDWI');

  return {
    collection: collection,
    composite: composite,
    ndvi: ndvi,
    mndwi: mndwi,
    water: mndwi.gt(waterThreshold).rename('water'),
    validMask: mndwi.mask().gt(0).unmask(0).rename('valid')
  };
}

function summarizeGeometry(
  geometry,
  year,
  imageCount,
  ndvi,
  mndwi,
  water,
  validMask
) {
  var roiAreaKm2 = ee.Number(pixelAreaKm2.reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: geometry,
    scale: statisticsScale,
    tileScale: 4,
    maxPixels: 1e13
  }).get('area'));

  var means = ndvi.addBands(mndwi).reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: geometry,
    scale: statisticsScale,
    tileScale: 4,
    maxPixels: 1e13
  });

  var areas = pixelAreaKm2.updateMask(validMask)
    .rename('valid_area_km2')
    .addBands(pixelAreaKm2.updateMask(water).rename('water_area_km2'))
    .reduceRegion({
      reducer: ee.Reducer.sum(),
      geometry: geometry,
      scale: statisticsScale,
      tileScale: 4,
      maxPixels: 1e13
    });

  // 浮点聚合可能产生约 1e-10 km² 的上溢，限制到同口径 ROI 面积。
  var validAreaKm2 = ee.Number(areas.get('valid_area_km2'))
    .min(roiAreaKm2)
    .max(0);
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

  return {
    year: year,
    image_count: imageCount,
    roi_area_km2: roiAreaKm2,
    valid_area_km2: validAreaKm2,
    valid_share: validShare,
    coverage_flag: coverageFlag,
    ndvi_mean: means.get('NDVI'),
    mndwi_mean: means.get('MNDWI'),
    water_area_km2: areas.get('water_area_km2'),
    water_threshold: waterThreshold,
    roi_version: 'hybas6_v1',
    statistics_scale_m: statisticsScale
  };
}

function overallFeature(year) {
  year = ee.Number(year);
  var products = buildYearProducts(year);
  return ee.Feature(null, summarizeGeometry(
    roi,
    year,
    products.collection.size(),
    products.ndvi,
    products.mndwi,
    products.water,
    products.validMask
  ));
}

function subbasinFeatures(year) {
  year = ee.Number(year);
  var products = buildYearProducts(year);

  return roiCollection.map(function(feature) {
    feature = ee.Feature(feature);
    var geometry = feature.geometry();
    var summary = summarizeGeometry(
      geometry,
      year,
      products.collection.filterBounds(geometry).size(),
      products.ndvi,
      products.mndwi,
      products.water,
      products.validMask
    );

    return ee.Feature(null, summary).set({
      subbasin_id: feature.get('subbasin_id'),
      subbasin_name: feature.get('name_cn'),
      hybas_id: feature.get('hybas_id'),
      next_down: feature.get('next_down'),
      subbasin_area_km2: summary.roi_area_km2
    }).select([
      'year',
      'image_count',
      'subbasin_id',
      'subbasin_name',
      'hybas_id',
      'next_down',
      'subbasin_area_km2',
      'valid_area_km2',
      'valid_share',
      'coverage_flag',
      'ndvi_mean',
      'mndwi_mean',
      'water_area_km2',
      'water_threshold',
      'roi_version',
      'statistics_scale_m'
    ]);
  });
}

var years = ee.List.sequence(startYear, endYear);
var overallStats = ee.FeatureCollection(years.map(overallFeature));
var subbasinStats = ee.FeatureCollection(
  years.map(subbasinFeatures)
).flatten();

print('研究区子流域数量', roiCollection.size());
print('总体年度统计', overallStats);
print('分区年度统计（应为35行）', subbasinStats);
print(
  '覆盖等级规则',
  'high >= 0.95；medium >= 0.80 且 < 0.95；low < 0.80'
);

Export.table.toDrive({
  collection: overallStats,
  description: overallExportName,
  folder: 'SRT_GEE_exports',
  fileNamePrefix: overallExportName,
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

Export.table.toDrive({
  collection: subbasinStats,
  description: subbasinExportName,
  folder: 'SRT_GEE_exports',
  fileNamePrefix: subbasinExportName,
  fileFormat: 'CSV',
  selectors: [
    'year',
    'image_count',
    'subbasin_id',
    'subbasin_name',
    'hybas_id',
    'next_down',
    'subbasin_area_km2',
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
var visProducts = buildYearProducts(visYear);
Map.setOptions('SATELLITE');
Map.centerObject(roiCollection, 7);
Map.addLayer(
  visProducts.composite,
  {bands: ['B4', 'B3', 'B2'], min: 0, max: 3000},
  '2024 真彩色'
);
Map.addLayer(
  visProducts.ndvi,
  {min: -0.2, max: 0.8, palette: ['brown', 'yellow', 'green']},
  '2024 NDVI',
  false
);
Map.addLayer(
  visProducts.mndwi,
  {min: -0.5, max: 0.5, palette: ['brown', 'white', 'blue']},
  '2024 MNDWI',
  false
);
Map.addLayer(
  visProducts.water.selfMask(),
  {palette: ['0000FF']},
  '2024 水体识别',
  true
);
Map.addLayer(
  roiCollection.style({
    color: 'D62728',
    fillColor: '00000000',
    width: 2
  }),
  {},
  'hybas6_v1 五子流域边界',
  true
);
