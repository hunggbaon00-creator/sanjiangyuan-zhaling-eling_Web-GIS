"""Export the five-feature hybas6_v1 boundary to Assets and Drive."""

from __future__ import annotations

import argparse

import ee


DEFAULT_PROJECT = "careful-form-499402-d0"
SOURCE_ASSET = "WWF/HydroSHEDS/v1/Basins/hybas_6"
TARGET_ASSET = (
    "projects/careful-form-499402-d0/"
    "assets/zhaling_eling_watershed_hybas6_v1"
)
EXPORT_NAME = "zhaling_eling_watershed_hybas6_v1"
BOUNDARY_FIELDS = [
    ".geo",
    "roi_id",
    "roi_version",
    "subbasin_id",
    "name_cn",
    "name_en",
    "hybas_id",
    "next_down",
    "pfaf_id",
    "area_km2",
    "hybas_level",
    "source",
    "source_asset",
    "source_version",
    "boundary_type",
]
BASIN_SPECS = [
    (4060614190, "SB01", "扎陵湖上游北部单元", "Northern upstream unit of Zhaling Lake"),
    (4060614330, "SB02", "扎陵湖上游南部单元", "Southern upstream unit of Zhaling Lake"),
    (4060620840, "SB03", "扎陵湖所在单元", "Zhaling Lake unit"),
    (4060621070, "SB04", "鄂陵湖上游南部单元", "Southern upstream unit of Eling Lake"),
    (4060628060, "SB05", "鄂陵湖所在及出口单元", "Eling Lake and outlet unit"),
]


def build_subbasins() -> ee.FeatureCollection:
    source = ee.FeatureCollection(SOURCE_ASSET)
    features = []
    for hybas_id, subbasin_id, name_cn, name_en in BASIN_SPECS:
        source_feature = ee.Feature(
            source.filter(ee.Filter.eq("HYBAS_ID", hybas_id)).first()
        )
        features.append(
            ee.Feature(
                source_feature.geometry(),
                {
                    "roi_id": f"ZE_HYBAS6_V1_{subbasin_id}",
                    "roi_version": "hybas6_v1",
                    "subbasin_id": subbasin_id,
                    "name_cn": name_cn,
                    "name_en": name_en,
                    "hybas_id": source_feature.get("HYBAS_ID"),
                    "next_down": source_feature.get("NEXT_DOWN"),
                    "pfaf_id": source_feature.get("PFAF_ID"),
                    "area_km2": source_feature.geometry().area(1).divide(1_000_000),
                    "hybas_level": 6,
                    "source": "HydroBASINS",
                    "source_asset": SOURCE_ASSET,
                    "source_version": "v1c",
                    "boundary_type": "hydrobasins_subbasin",
                },
            )
        )
    return ee.FeatureCollection(features).sort("subbasin_id")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--drive-folder", default="SRT_GEE_exports")
    parser.add_argument("--asset-id", default=TARGET_ASSET)
    args = parser.parse_args()

    ee.Initialize(project=args.project)
    subbasins = build_subbasins()
    try:
        ee.data.getAsset(args.asset_id)
    except ee.EEException:
        pass
    else:
        raise RuntimeError(
            f"Target asset already exists and will not be overwritten: {args.asset_id}"
        )

    asset_task = ee.batch.Export.table.toAsset(
        collection=subbasins,
        description=f"{EXPORT_NAME}_to_asset",
        assetId=args.asset_id,
    )
    drive_task = ee.batch.Export.table.toDrive(
        collection=subbasins,
        description=EXPORT_NAME,
        folder=args.drive_folder,
        fileNamePrefix=EXPORT_NAME,
        fileFormat="GeoJSON",
        selectors=BOUNDARY_FIELDS,
    )
    asset_task.start()
    drive_task.start()
    print("Started Earth Engine boundary export tasks.")
    print(f"Asset task: {asset_task.id}")
    print(f"Drive task: {drive_task.id}")
    print(f"Target asset: {args.asset_id}")


if __name__ == "__main__":
    main()
