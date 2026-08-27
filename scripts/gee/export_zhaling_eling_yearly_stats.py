r"""Export hybas6_v1 overall and subbasin annual statistics.

The script starts two Earth Engine batch tasks. Both CSV files are exported
to Google Drive for validation before formal data files are replaced.
"""

from __future__ import annotations

import argparse

import ee


DEFAULT_PROJECT = "careful-form-499402-d0"
DEFAULT_ROI_ASSET = (
    "projects/careful-form-499402-d0/"
    "assets/zhaling_eling_watershed_hybas6_v1"
)
START_YEAR = 2018
END_YEAR = 2024
WATER_THRESHOLD = 0.0
STATISTICS_SCALE = 20
HIGH_COVERAGE_THRESHOLD = 0.95
MEDIUM_COVERAGE_THRESHOLD = 0.80
OVERALL_DESCRIPTION = (
    "zhaling_eling_yearly_stats_2018_2024_hybas6_v1_t000"
)
SUBBASIN_DESCRIPTION = (
    "zhaling_eling_subbasin_yearly_stats_2018_2024_hybas6_v1_t000"
)
OVERALL_FIELDS = [
    "year",
    "image_count",
    "roi_area_km2",
    "valid_area_km2",
    "valid_share",
    "coverage_flag",
    "ndvi_mean",
    "mndwi_mean",
    "water_area_km2",
    "water_threshold",
    "roi_version",
    "statistics_scale_m",
]
SUBBASIN_FIELDS = [
    "year",
    "image_count",
    "subbasin_id",
    "subbasin_name",
    "hybas_id",
    "next_down",
    "subbasin_area_km2",
    "valid_area_km2",
    "valid_share",
    "coverage_flag",
    "ndvi_mean",
    "mndwi_mean",
    "water_area_km2",
    "water_threshold",
    "roi_version",
    "statistics_scale_m",
]


def mask_sentinel2_sr(image: ee.Image) -> ee.Image:
    """Mask cloud, cloud shadow, cirrus, and snow using the SCL band."""
    scl = image.select("SCL")
    clear = (
        scl.neq(3)
        .And(scl.neq(8))
        .And(scl.neq(9))
        .And(scl.neq(10))
        .And(scl.neq(11))
    )
    return image.updateMask(clear).copyProperties(image, ["system:time_start"])


def build_year_products(year: int, roi: ee.Geometry) -> dict[str, object]:
    start = ee.Date.fromYMD(year, 6, 1)
    end = ee.Date.fromYMD(year, 10, 1)
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
        .map(mask_sentinel2_sr)
    )
    composite = collection.median().clip(roi)
    ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
    mndwi = composite.normalizedDifference(["B3", "B11"]).rename("MNDWI")
    return {
        "collection": collection,
        "ndvi": ndvi,
        "mndwi": mndwi,
        "water": mndwi.gt(WATER_THRESHOLD).rename("water"),
        "valid_mask": mndwi.mask().gt(0).unmask(0).rename("valid"),
    }


def summarize_geometry(
    geometry: ee.Geometry,
    year: int,
    image_count: ee.Number,
    products: dict[str, object],
) -> dict[str, object]:
    pixel_area_km2 = ee.Image.pixelArea().divide(1_000_000)
    roi_area_km2 = ee.Number(
        pixel_area_km2.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geometry,
            scale=STATISTICS_SCALE,
            tileScale=4,
            maxPixels=1e13,
        ).get("area")
    )
    ndvi = ee.Image(products["ndvi"])
    mndwi = ee.Image(products["mndwi"])
    means = ndvi.addBands(mndwi).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=STATISTICS_SCALE,
        tileScale=4,
        maxPixels=1e13,
    )
    areas = (
        pixel_area_km2.updateMask(ee.Image(products["valid_mask"]))
        .rename("valid_area_km2")
        .addBands(
            pixel_area_km2.updateMask(ee.Image(products["water"]))
            .rename("water_area_km2")
        )
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geometry,
            scale=STATISTICS_SCALE,
            tileScale=4,
            maxPixels=1e13,
        )
    )
    # Floating-point aggregation can exceed the same-grid ROI area by a tiny
    # amount. Clamp it before deriving the formal coverage share.
    valid_area_km2 = (
        ee.Number(areas.get("valid_area_km2"))
        .min(roi_area_km2)
        .max(0)
    )
    valid_share = valid_area_km2.divide(roi_area_km2)
    coverage_flag = ee.String(
        ee.Algorithms.If(
            valid_share.gte(HIGH_COVERAGE_THRESHOLD),
            "high",
            ee.Algorithms.If(
                valid_share.gte(MEDIUM_COVERAGE_THRESHOLD), "medium", "low"
            ),
        )
    )
    return {
        "year": year,
        "image_count": image_count,
        "roi_area_km2": roi_area_km2,
        "valid_area_km2": valid_area_km2,
        "valid_share": valid_share,
        "coverage_flag": coverage_flag,
        "ndvi_mean": means.get("NDVI"),
        "mndwi_mean": means.get("MNDWI"),
        "water_area_km2": areas.get("water_area_km2"),
        "water_threshold": WATER_THRESHOLD,
        "roi_version": "hybas6_v1",
        "statistics_scale_m": STATISTICS_SCALE,
    }


def overall_feature(
    year: int, roi: ee.Geometry, products: dict[str, object]
) -> ee.Feature:
    collection = ee.ImageCollection(products["collection"])
    return ee.Feature(
        None,
        summarize_geometry(roi, year, collection.size(), products),
    )


def subbasin_features(
    year: int,
    roi_collection: ee.FeatureCollection,
    products: dict[str, object],
) -> ee.FeatureCollection:
    collection = ee.ImageCollection(products["collection"])

    def summarize(feature: ee.Feature) -> ee.Feature:
        feature = ee.Feature(feature)
        geometry = feature.geometry()
        summary = summarize_geometry(
            geometry,
            year,
            collection.filterBounds(geometry).size(),
            products,
        )
        return ee.Feature(None, summary).set(
            {
                "subbasin_id": feature.get("subbasin_id"),
                "subbasin_name": feature.get("name_cn"),
                "hybas_id": feature.get("hybas_id"),
                "next_down": feature.get("next_down"),
                "subbasin_area_km2": summary["roi_area_km2"],
            }
        ).select(SUBBASIN_FIELDS)

    return roi_collection.map(summarize)


def start_export(
    collection: ee.FeatureCollection,
    description: str,
    fields: list[str],
    drive_folder: str,
) -> ee.batch.Task:
    task = ee.batch.Export.table.toDrive(
        collection=collection,
        description=description,
        folder=drive_folder,
        fileNamePrefix=description,
        fileFormat="CSV",
        selectors=fields,
    )
    task.start()
    return task


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--roi-asset", default=DEFAULT_ROI_ASSET)
    parser.add_argument("--drive-folder", default="SRT_GEE_exports")
    args = parser.parse_args()

    ee.Initialize(project=args.project)
    roi_collection = ee.FeatureCollection(args.roi_asset).sort("subbasin_id")
    # Keep five features for display, but remove internal boundaries for the
    # study-area aggregate so the raster statistic matches the v0 union.
    roi = roi_collection.geometry().dissolve(1)
    overall_features: list[ee.Feature] = []
    subbasin_stats = ee.FeatureCollection([])

    for year in range(START_YEAR, END_YEAR + 1):
        products = build_year_products(year, roi)
        overall_features.append(overall_feature(year, roi, products))
        subbasin_stats = subbasin_stats.merge(
            subbasin_features(year, roi_collection, products)
        )

    overall_stats = ee.FeatureCollection(overall_features)
    overall_task = start_export(
        overall_stats,
        OVERALL_DESCRIPTION,
        OVERALL_FIELDS,
        args.drive_folder,
    )
    subbasin_task = start_export(
        subbasin_stats,
        SUBBASIN_DESCRIPTION,
        SUBBASIN_FIELDS,
        args.drive_folder,
    )

    print("Started Earth Engine export tasks.")
    print(f"Overall task: {overall_task.id} | {OVERALL_DESCRIPTION}")
    print(f"Subbasin task: {subbasin_task.id} | {SUBBASIN_DESCRIPTION}")
    print(f"ROI asset: {args.roi_asset}")
    print(f"Years: {START_YEAR}-{END_YEAR}")
    print("Growing season: June 1-September 30")
    print(f"Statistics scale: {STATISTICS_SCALE} m")
    print(f"MNDWI water threshold: {WATER_THRESHOLD}")
    print(f"Google Drive folder: {args.drive_folder}")


if __name__ == "__main__":
    main()
