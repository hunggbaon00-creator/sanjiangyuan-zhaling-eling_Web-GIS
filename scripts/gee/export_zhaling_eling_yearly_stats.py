r"""Export annual NDVI and MNDWI statistics for the Zhaling-Eling watershed.

This script starts a Google Earth Engine batch task that exports a CSV to
Google Drive. It does not download imagery to the local computer.

Usage:
    .\.venv\Scripts\python.exe scripts\gee\export_zhaling_eling_yearly_stats.py
    .\.venv\Scripts\python.exe scripts\gee\export_zhaling_eling_yearly_stats.py --project YOUR_GCP_PROJECT_ID

After the task finishes in Earth Engine, download the CSV from Google Drive
and validate it before replacing the CSV currently used by Streamlit.
"""

from __future__ import annotations

import argparse

import ee


DEFAULT_PROJECT = "careful-form-499402-d0"
DEFAULT_ROI_ASSET = (
    "projects/careful-form-499402-d0/"
    "assets/zhaling_eling_watershed_hybas6_v0"
)
START_YEAR = 2018
END_YEAR = 2024
WATER_THRESHOLD = 0.0
STATISTICS_SCALE = 20
HIGH_COVERAGE_THRESHOLD = 0.95
MEDIUM_COVERAGE_THRESHOLD = 0.80
EXPORT_FIELDS = [
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


def yearly_feature(
    year: int, roi: ee.Geometry, roi_area_km2: ee.Number
) -> ee.Feature:
    start = ee.Date.fromYMD(year, 6, 1)
    # Earth Engine excludes the filterDate end date, so October 1 includes
    # the complete June-September growing season.
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
    water = mndwi.gt(WATER_THRESHOLD).rename("water")
    valid_mask = mndwi.mask().gt(0).unmask(0).rename("valid")

    means = ndvi.addBands(mndwi).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=roi,
        scale=STATISTICS_SCALE,
        tileScale=4,
        maxPixels=1e13,
    )

    pixel_area_km2 = ee.Image.pixelArea().divide(1_000_000)
    areas = (
        pixel_area_km2.updateMask(valid_mask)
        .rename("valid_area_km2")
        .addBands(pixel_area_km2.updateMask(water).rename("water_area_km2"))
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=roi,
            scale=STATISTICS_SCALE,
            tileScale=4,
            maxPixels=1e13,
        )
    )
    valid_area_km2 = ee.Number(areas.get("valid_area_km2"))
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

    return ee.Feature(
        None,
        {
            "year": year,
            "image_count": collection.size(),
            "roi_area_km2": roi_area_km2,
            "valid_area_km2": valid_area_km2,
            "valid_share": valid_share,
            "coverage_flag": coverage_flag,
            "ndvi_mean": means.get("NDVI"),
            "mndwi_mean": means.get("MNDWI"),
            "water_area_km2": areas.get("water_area_km2"),
            "water_threshold": WATER_THRESHOLD,
            "roi_version": "hybas6_v0",
            "statistics_scale_m": STATISTICS_SCALE,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        default=DEFAULT_PROJECT,
        help="Google Cloud project ID registered for Earth Engine.",
    )
    parser.add_argument(
        "--roi-asset",
        default=DEFAULT_ROI_ASSET,
        help="Earth Engine FeatureCollection asset used as the study-area boundary.",
    )
    parser.add_argument("--drive-folder", default="SRT_GEE_exports", help="Google Drive folder name for export output.")
    parser.add_argument(
        "--description",
        default="zhaling_eling_yearly_stats_2018_2024_hybas6_v0_t000",
        help="Earth Engine task description and exported CSV prefix.",
    )
    args = parser.parse_args()

    ee.Initialize(project=args.project)

    roi_collection = ee.FeatureCollection(args.roi_asset)
    roi = roi_collection.geometry()
    # Use the same pixel-area image, scale, and geometry as the yearly valid
    # area so that valid_share has a consistent numerator and denominator.
    roi_area_km2 = ee.Number(
        ee.Image.pixelArea()
        .divide(1_000_000)
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=roi,
            scale=STATISTICS_SCALE,
            tileScale=4,
            maxPixels=1e13,
        )
        .get("area")
    )
    years = range(START_YEAR, END_YEAR + 1)
    features = ee.FeatureCollection(
        [yearly_feature(year, roi, roi_area_km2) for year in years]
    )
    task = ee.batch.Export.table.toDrive(
        collection=features,
        description=args.description,
        folder=args.drive_folder,
        fileNamePrefix=args.description,
        fileFormat="CSV",
        selectors=EXPORT_FIELDS,
    )
    task.start()
    print("Started Earth Engine export task.")
    print(f"Task ID: {task.id}")
    print(f"Description: {args.description}")
    print(f"ROI asset: {args.roi_asset}")
    print(f"Years: {START_YEAR}-{END_YEAR}")
    print(f"Growing season: June 1-September 30")
    print(f"Statistics scale: {STATISTICS_SCALE} m")
    print(f"MNDWI water threshold: {WATER_THRESHOLD}")
    print(
        "Coverage flags: "
        f"high >= {HIGH_COVERAGE_THRESHOLD:.2f}; "
        f"medium >= {MEDIUM_COVERAGE_THRESHOLD:.2f} and < "
        f"{HIGH_COVERAGE_THRESHOLD:.2f}; low < {MEDIUM_COVERAGE_THRESHOLD:.2f}"
    )
    print(f"Google Drive folder: {args.drive_folder}")
    print()
    print("Check task status with:")
    print(r"  .\.venv\Scripts\python.exe -m ee.cli.eecli task list")


if __name__ == "__main__":
    main()
