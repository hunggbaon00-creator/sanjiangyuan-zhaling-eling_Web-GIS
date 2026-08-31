"""Start one 2024 MNDWI pilot export for the WebGIS raster pipeline."""

from __future__ import annotations

import argparse

import ee

from export_zhaling_eling_yearly_stats import (
    DEFAULT_PROJECT,
    DEFAULT_ROI_ASSET,
    STATISTICS_SCALE,
    build_year_products,
)


YEAR = 2024
DATASET_VERSION = "hybas6_v1_t000"
DESCRIPTION = "zhaling_eling_mndwi_2024_hybas6_v1_t000_pilot"
WORKLOAD_TAG = "hybas6-v1-2024-mndwi-pilot"
OUTPUT_CRS = "EPSG:3857"
NO_DATA = -9999.0
MAX_PIXELS = 200_000_000
ACTIVE_STATES = {"READY", "RUNNING", "CANCEL_REQUESTED"}


def matching_active_tasks(description: str) -> list[dict]:
    """Return active tasks with the same description."""
    matches = []
    for task in ee.batch.Task.list():
        status = task.status()
        if (
            status.get("description") == description
            and status.get("state") in ACTIVE_STATES
        ):
            matches.append(status)
    return matches


def build_export_task(
    roi_asset: str,
    drive_folder: str,
) -> ee.batch.Task:
    """Build, but do not start, the single pilot batch task."""
    roi_collection = ee.FeatureCollection(roi_asset).sort("subbasin_id")
    roi = roi_collection.geometry().dissolve(1)
    products = build_year_products(YEAR, roi)
    mndwi = (
        ee.Image(products["mndwi"])
        .toFloat()
        .unmask(NO_DATA, False)
        .set(
            {
                "dataset_version": DATASET_VERSION,
                "year": YEAR,
                "product": "MNDWI",
                "statistics_scale_m": STATISTICS_SCALE,
                "water_threshold": 0.0,
            }
        )
    )
    return ee.batch.Export.image.toDrive(
        image=mndwi,
        description=DESCRIPTION,
        folder=drive_folder,
        fileNamePrefix=DESCRIPTION,
        region=roi,
        scale=STATISTICS_SCALE,
        crs=OUTPUT_CRS,
        maxPixels=MAX_PIXELS,
        fileFormat="GeoTIFF",
        formatOptions={
            "cloudOptimized": True,
            "noData": NO_DATA,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare or start the 2024 MNDWI pilot export."
    )
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--roi-asset", default=DEFAULT_ROI_ASSET)
    parser.add_argument("--drive-folder", default="SRT_GEE_exports")
    parser.add_argument(
        "--start",
        action="store_true",
        help="Start the batch task. Without this flag, only validate setup.",
    )
    args = parser.parse_args()

    ee.Initialize(project=args.project)
    duplicates = matching_active_tasks(DESCRIPTION)
    if duplicates:
        duplicate_ids = ", ".join(item["id"] for item in duplicates)
        raise SystemExit(f"Active duplicate task exists: {duplicate_ids}")

    ee.data.setDefaultWorkloadTag(WORKLOAD_TAG)
    task = build_export_task(args.roi_asset, args.drive_folder)
    if not args.start:
        print("2024 MNDWI pilot export setup: OK (not started)")
        print(f"Description: {DESCRIPTION}")
        print(f"Workload tag: {WORKLOAD_TAG}")
        print(f"ROI asset: {args.roi_asset}")
        print(f"Scale: {STATISTICS_SCALE} m | CRS: {OUTPUT_CRS}")
        print(f"Drive folder: {args.drive_folder}")
        return

    task.start()
    status = task.status()
    print("Started one Earth Engine batch export task.")
    print(f"Task ID: {task.id}")
    print(f"State: {status.get('state')}")
    print(f"Description: {DESCRIPTION}")
    print(f"Workload tag: {WORKLOAD_TAG}")
    print(f"ROI asset: {args.roi_asset}")
    print(f"Scale: {STATISTICS_SCALE} m | CRS: {OUTPUT_CRS}")
    print(f"NoData: {NO_DATA} | maxPixels: {MAX_PIXELS}")
    print(f"Drive folder: {args.drive_folder}")


if __name__ == "__main__":
    main()
