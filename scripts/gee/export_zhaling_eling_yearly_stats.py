r"""Export annual NDVI and MNDWI statistics for the Zhaling-Eling study area.

This script starts a Google Earth Engine batch task that exports a CSV to
Google Drive. It does not download imagery to the local computer.

Usage:
    .\.venv\Scripts\python.exe scripts\gee\export_zhaling_eling_yearly_stats.py
    .\.venv\Scripts\python.exe scripts\gee\export_zhaling_eling_yearly_stats.py --project YOUR_GCP_PROJECT_ID

After the task finishes in Earth Engine, download the CSV from Google Drive
and place it under:
    data\processed\zhaling_eling_yearly_stats.csv
"""

from __future__ import annotations

import argparse

import ee


ROI = ee.Geometry.Rectangle([96.85, 34.55, 98.25, 35.25])
YEARS = list(range(2018, 2025))


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
    return image.updateMask(clear).divide(10000).copyProperties(image, ["system:time_start"])


def yearly_feature(year: int) -> ee.Feature:
    start = ee.Date.fromYMD(year, 6, 1)
    end = ee.Date.fromYMD(year, 9, 30)
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(ROI)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
        .map(mask_sentinel2_sr)
    )
    composite = collection.median().clip(ROI)
    ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
    mndwi = composite.normalizedDifference(["B3", "B11"]).rename("MNDWI")
    water = mndwi.gt(0).rename("water")

    ndvi_mean = ndvi.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=ROI,
        scale=30,
        bestEffort=True,
        maxPixels=1e13,
    ).get("NDVI")
    mndwi_mean = mndwi.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=ROI,
        scale=30,
        bestEffort=True,
        maxPixels=1e13,
    ).get("MNDWI")
    water_area_km2 = (
        ee.Image.pixelArea()
        .divide(1_000_000)
        .updateMask(water)
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=ROI,
            scale=30,
            bestEffort=True,
            maxPixels=1e13,
        )
        .get("area")
    )
    return ee.Feature(
        None,
        {
            "year": year,
            "image_count": collection.size(),
            "ndvi_mean": ndvi_mean,
            "mndwi_mean": mndwi_mean,
            "water_area_km2": water_area_km2,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", help="Optional Google Cloud project ID registered for Earth Engine.")
    parser.add_argument("--drive-folder", default="SRT_GEE_exports", help="Google Drive folder name for export output.")
    parser.add_argument(
        "--description",
        default="zhaling_eling_yearly_stats_2018_2024",
        help="Earth Engine task description and exported CSV prefix.",
    )
    args = parser.parse_args()

    if args.project:
        ee.Initialize(project=args.project)
    else:
        ee.Initialize()

    features = ee.FeatureCollection([yearly_feature(year) for year in YEARS])
    task = ee.batch.Export.table.toDrive(
        collection=features,
        description=args.description,
        folder=args.drive_folder,
        fileNamePrefix=args.description,
        fileFormat="CSV",
    )
    task.start()
    print("Started Earth Engine export task.")
    print(f"Task ID: {task.id}")
    print(f"Description: {args.description}")
    print(f"Google Drive folder: {args.drive_folder}")
    print()
    print("Check task status with:")
    print(r"  .\.venv\Scripts\python.exe -m ee.cli.eecli task list")


if __name__ == "__main__":
    main()
