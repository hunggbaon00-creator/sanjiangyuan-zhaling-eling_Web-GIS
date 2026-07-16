var roi = ee.Geometry.Rectangle([96.85, 34.55, 98.25, 35.25]);

Map.centerObject(roi, 8);
Map.addLayer(
  ee.Image().paint(roi, 1, 2),
  {palette: ['red']},
  '研究区边界'
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
  var end = ee.Date.fromYMD(year, 9, 30);

  var collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(roi)
    .filterDate(start, end)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
    .map(maskS2);

  var composite = collection.median().clip(roi);

  var ndvi = composite.normalizedDifference(['B8', 'B4']).rename('NDVI');
  var mndwi = composite.normalizedDifference(['B3', 'B11']).rename('MNDWI');
  var water = mndwi.gt(0.1).rename('water');

  var ndviMean = ndvi.reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: roi,
    scale: 30,
    bestEffort: true,
    maxPixels: 1e13
  }).get('NDVI');

  var mndwiMean = mndwi.reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: roi,
    scale: 30,
    bestEffort: true,
    maxPixels: 1e13
  }).get('MNDWI');

  var waterArea = ee.Image.pixelArea().divide(1000000)
    .updateMask(water)
    .reduceRegion({
      reducer: ee.Reducer.sum(),
      geometry: roi,
      scale: 30,
      bestEffort: true,
      maxPixels: 1e13
    }).get('area');

  return ee.Feature(null, {
    year: year,
    image_count: collection.size(),
    ndvi_mean: ndviMean,
    mndwi_mean: mndwiMean,
    water_area_km2: waterArea
  });
}

var years = ee.List.sequence(2018, 2024);
var stats = ee.FeatureCollection(years.map(yearlyFeature));

print('年度统计结果', stats);

Export.table.toDrive({
  collection: stats,
  description: 'zhaling_eling_yearly_stats_2018_2024',
  folder: 'SRT_GEE_exports',
  fileNamePrefix: 'zhaling_eling_yearly_stats_2018_2024',
  fileFormat: 'CSV'
});



var visYear = 2024;

var visCollection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(roi)
  .filterDate(visYear + '-06-01', visYear + '-09-30')
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
  .map(maskS2);

var visComposite = visCollection.median().clip(roi);

var visNdvi = visComposite.normalizedDifference(['B8', 'B4']).rename('NDVI');
var visMndwi = visComposite.normalizedDifference(['B3', 'B11']).rename('MNDWI');
var visWater = visMndwi.gt(0.1).selfMask();

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