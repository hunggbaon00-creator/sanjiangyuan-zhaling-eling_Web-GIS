// hybas6_v0 / t000 跨年岸线核查
// 检查 MNDWI > 0.0 在 2019、2024 年的湖岸、浅水区和陆地误提。


var roiCollection = ee.FeatureCollection(
  'projects/careful-form-499402-d0/assets/' +
  'zhaling_eling_watershed_hybas6_v0'
);
var roi = roiCollection.geometry();

var candidateThreshold = 0.0;
var previousThreshold = 0.1;

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

function addValidationLayers(year, showByDefault) {
  var start = ee.Date.fromYMD(year, 6, 1);
  var end = ee.Date.fromYMD(year, 10, 1);

  var collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(roi)
    .filterDate(start, end)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
    .map(maskS2);

  var composite = collection.median().clip(roi);
  var mndwi = composite
    .normalizedDifference(['B3', 'B11'])
    .rename('MNDWI');

  var waterT000 = mndwi.gt(candidateThreshold);
  var waterT010 = mndwi.gt(previousThreshold);

  // 该图层只显示阈值从 0.1 调整至 0.0 后新增的像元：0 < MNDWI <= 0.1。
  var t000AddedPixels = waterT000
    .and(waterT010.not())
    .selfMask();

  var validObservationCount = collection
    .select('B4')
    .count()
    .clip(roi);

  Map.addLayer(
    composite,
    {bands: ['B4', 'B3', 'B2'], min: 0, max: 3000},
    year + ' 真彩色',
    showByDefault
  );

  Map.addLayer(
    waterT000.selfMask(),
    {palette: ['0000FF']},
    year + ' t000 水体（MNDWI > 0）',
    showByDefault,
    0.55
  );

  Map.addLayer(
    waterT010.selfMask(),
    {palette: ['00FFFF']},
    year + ' t010 水体（MNDWI > 0.1）',
    false,
    0.55
  );

  Map.addLayer(
    t000AddedPixels,
    {palette: ['FFFF00']},
    year + ' t000 相对 t010 新增像元',
    false,
    0.8
  );

  Map.addLayer(
    mndwi,
    {
      min: -0.5,
      max: 0.5,
      palette: ['8B4513', 'FFFFFF', '0000FF']
    },
    year + ' MNDWI',
    false
  );

  Map.addLayer(
    validObservationCount,
    {
      min: 1,
      max: 30,
      palette: ['FF0000', 'FFFF00', '008000']
    },
    year + ' 有效观测次数',
    false
  );

  print(year + ' 影像数量', collection.size());
}

Map.setOptions('SATELLITE');
Map.centerObject(roiCollection, 7);

// 默认显示 2024；核查 2019 时关闭 2024 两个默认图层，再开启 2019 对应图层。
addValidationLayers(2019, false);
addValidationLayers(2024, true);

var worldCoverWater = ee.ImageCollection('ESA/WorldCover/v200')
  .first()
  .select('Map')
  .eq(80)
  .clip(roi)
  .selfMask();

var jrcStableWater = ee.Image('JRC/GSW1_4/GlobalSurfaceWater')
  .select('occurrence')
  .gte(90)
  .clip(roi)
  .selfMask();

Map.addLayer(
  worldCoverWater,
  {palette: ['00FF00']},
  'ESA WorldCover 2021 永久水体（辅助参考）',
  false,
  0.6
);

Map.addLayer(
  jrcStableWater,
  {palette: ['FFFFFF']},
  'JRC 长期稳定水体 >= 90%（辅助参考）',
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

print(
  '核查顺序',
  '同一缩放级别依次检查主湖岸线、东部小湖群、河道/湿地及山地阴影；' +
  '黄色新增像元应主要位于真实水体边缘，而不应大量散布于陆地。'
);
