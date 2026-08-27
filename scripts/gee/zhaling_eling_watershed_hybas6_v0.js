// 扎陵湖—鄂陵湖汇水区候选测试边界 v0
// 数据源：HydroBASINS v1，Pfafstetter Level 6

// 当前项目中使用的两个湖泊参考位置
var zhalingPoint = ee.Geometry.Point([97.32, 34.93]);
var elingPoint = ee.Geometry.Point([97.70, 34.86]);

// HydroBASINS 第6级子流域
var hybas6 = ee.FeatureCollection(
  'WWF/HydroSHEDS/v1/Basins/hybas_6'
);

// 根据 NEXT_DOWN 拓扑查询得到的鄂陵湖单元及全部上游单元
var selectedIds = [
  4060614190,
  4060614330,
  4060620840,
  4060621070,
  4060628060
];

// 筛选子流域
var selectedBasins = hybas6.filter(
  ee.Filter.inList('HYBAS_ID', selectedIds)
);

// 融合为单一研究区几何
var roiGeometry = selectedBasins
  .geometry()
  .dissolve(1);

// 构建带有完整元数据的正式研究区要素
var roiFeature = ee.Feature(roiGeometry, {
  roi_id: 'ZE_WATERSHED_HYBAS6_V0',
  name_cn: '扎陵湖—鄂陵湖候选研究区',
  name_en: 'Zhaling-Eling Candidate Study Area',
  boundary_type: 'upstream_hydrobasins_union',
  source: 'HydroBASINS',
  source_asset: 'WWF/HydroSHEDS/v1/Basins/hybas_6',
  source_version: 'v1c',
  hybas_level: 6,
  outlet_hybas_id: 4060628060,
  source_ids: selectedIds.join(','),
  generated_date: '2026-07-15',
  crs: 'EPSG:4326',
  area_km2: roiGeometry.area(1).divide(1000000)
});

var roi = ee.FeatureCollection([roiFeature]);


// 地图检查

Map.centerObject(roi, 7);

// 将5个子流域边线栅格化，并扣除融合ROI的外轮廓。
// 该处理只影响地图显示，不改变或栅格化导出的ROI矢量几何。
var allBasinBoundaryImage = ee.Image()
  .byte()
  .paint({
    featureCollection: selectedBasins,
    color: 1,
    width: 2
  });

var outerBoundaryMask = ee.Image()
  .byte()
  .paint({
    featureCollection: roi,
    color: 1,
    width: 3
  });

var internalBasinBoundaryImage = allBasinBoundaryImage
  .updateMask(outerBoundaryMask.unmask(0).eq(0))
  .selfMask();

// 总边界默认打开：红色、半透明填充、3像素宽。
Map.addLayer(
  roi.style({
    color: 'FF0000',
    fillColor: 'FF000020',
    width: 3
  }),
  {},
  '融合后的候选研究区总边界',
  true
);

// 5个子流域图层只显示内部公共边界，默认打开。
Map.addLayer(
  internalBasinBoundaryImage,
  {palette: ['1E90FF']},
  '5个子流域内部边界',
  true
);

Map.addLayer(zhalingPoint, {color: '00FF00'}, '扎陵湖参考点');
Map.addLayer(elingPoint, {color: '0000FF'}, '鄂陵湖参考点');


// 属性与质量检查

print('选中子流域数量', selectedBasins.size());
print('选中子流域属性', selectedBasins);
print('正式ROI', roi);
print('ROI面积 km²', roiGeometry.area(1).divide(1000000));
print('ROI经纬度范围', roiGeometry.bounds());
print('是否包含扎陵湖参考点', roiGeometry.contains(zhalingPoint, 1));
print('是否包含鄂陵湖参考点', roiGeometry.contains(elingPoint, 1));

// 检查扎陵湖单元与鄂陵湖单元的上下游关系
print(
  '扎陵湖所在单元',
  hybas6.filter(ee.Filter.eq('HYBAS_ID', 4060620840))
);

print(
  '鄂陵湖所在单元',
  hybas6.filter(ee.Filter.eq('HYBAS_ID', 4060628060))
);


Map.setOptions('SATELLITE');


// 导出为GeoJSON

Export.table.toDrive({
  collection: roi,
  description: 'zhaling_eling_watershed_hybas6_v0',
  folder: 'SRT_GEE_exports',
  fileNamePrefix: 'zhaling_eling_watershed_hybas6_v0',
  fileFormat: 'GeoJSON'
});


//保存到 GEE Assets

Export.table.toAsset({
  collection: roi,
  description: 'zhaling_eling_watershed_hybas6_v0_to_asset',
  assetId: 'projects/careful-form-499402-d0/assets/zhaling_eling_watershed_hybas6_v0'
});
