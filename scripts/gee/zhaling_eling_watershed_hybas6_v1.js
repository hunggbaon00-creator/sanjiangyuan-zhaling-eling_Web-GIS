// 扎陵湖—鄂陵湖五子流域边界 hybas6_v1
// 数据源：HydroBASINS v1c，Pfafstetter Level 6

var sourceAsset = 'WWF/HydroSHEDS/v1/Basins/hybas_6';
var assetId =
  'projects/careful-form-499402-d0/assets/' +
  'zhaling_eling_watershed_hybas6_v1';
var exportName = 'zhaling_eling_watershed_hybas6_v1';

var basinSpecs = [
  {
    hybasId: 4060614190,
    subbasinId: 'SB01',
    nameCn: '扎陵湖上游北部单元',
    nameEn: 'Northern upstream unit of Zhaling Lake'
  },
  {
    hybasId: 4060614330,
    subbasinId: 'SB02',
    nameCn: '扎陵湖上游南部单元',
    nameEn: 'Southern upstream unit of Zhaling Lake'
  },
  {
    hybasId: 4060620840,
    subbasinId: 'SB03',
    nameCn: '扎陵湖所在单元',
    nameEn: 'Zhaling Lake unit'
  },
  {
    hybasId: 4060621070,
    subbasinId: 'SB04',
    nameCn: '鄂陵湖上游南部单元',
    nameEn: 'Southern upstream unit of Eling Lake'
  },
  {
    hybasId: 4060628060,
    subbasinId: 'SB05',
    nameCn: '鄂陵湖所在及出口单元',
    nameEn: 'Eling Lake and outlet unit'
  }
];

var source = ee.FeatureCollection(sourceAsset);
var subbasins = ee.FeatureCollection(basinSpecs.map(function(spec) {
  var sourceFeature = ee.Feature(source.filter(
    ee.Filter.eq('HYBAS_ID', spec.hybasId)
  ).first());

  return ee.Feature(sourceFeature.geometry(), {
    roi_id: 'ZE_HYBAS6_V1_' + spec.subbasinId,
    roi_version: 'hybas6_v1',
    subbasin_id: spec.subbasinId,
    name_cn: spec.nameCn,
    name_en: spec.nameEn,
    hybas_id: sourceFeature.get('HYBAS_ID'),
    next_down: sourceFeature.get('NEXT_DOWN'),
    pfaf_id: sourceFeature.get('PFAF_ID'),
    area_km2: sourceFeature.geometry().area(1).divide(1000000),
    hybas_level: 6,
    source: 'HydroBASINS',
    source_asset: sourceAsset,
    source_version: 'v1c',
    boundary_type: 'hydrobasins_subbasin'
  });
})).sort('subbasin_id');

var roi = subbasins.geometry().dissolve(1);
var zhalingPoint = ee.Geometry.Point([97.32, 34.93]);
var elingPoint = ee.Geometry.Point([97.70, 34.86]);

Map.setOptions('SATELLITE');
Map.centerObject(subbasins, 7);
Map.addLayer(
  subbasins.style({
    color: 'D62728',
    fillColor: 'D6272820',
    width: 2
  }),
  {},
  'hybas6_v1 五子流域',
  true
);
Map.addLayer(zhalingPoint, {color: '00FF00'}, '扎陵湖参考点');
Map.addLayer(elingPoint, {color: '0000FF'}, '鄂陵湖参考点');

print('子流域数量（应为5）', subbasins.size());
print('子流域属性', subbasins);
print('合并几何面积 km²', roi.area(1).divide(1000000));
print(
  '扎陵湖参考点所在单元',
  subbasins.filterBounds(zhalingPoint).aggregate_array('subbasin_id')
);
print(
  '鄂陵湖参考点所在单元',
  subbasins.filterBounds(elingPoint).aggregate_array('subbasin_id')
);

Export.table.toDrive({
  collection: subbasins,
  description: exportName,
  folder: 'SRT_GEE_exports',
  fileNamePrefix: exportName,
  fileFormat: 'GeoJSON',
  selectors: [
    '.geo',
    'roi_id',
    'roi_version',
    'subbasin_id',
    'name_cn',
    'name_en',
    'hybas_id',
    'next_down',
    'pfaf_id',
    'area_km2',
    'hybas_level',
    'source',
    'source_asset',
    'source_version',
    'boundary_type'
  ]
});

Export.table.toAsset({
  collection: subbasins,
  description: exportName + '_to_asset',
  assetId: assetId
});
