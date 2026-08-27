"""Export 2018 Sentinel-2 and Landsat 8 water cross-validation metrics."""

from __future__ import annotations

import argparse

import ee


DEFAULT_PROJECT = "careful-form-499402-d0"
ROI_ASSET = (
    "projects/careful-form-499402-d0/"
    "assets/zhaling_eling_watershed_hybas6_v1"
)
EXPORT_NAME = "water_cross_validation_2018_s2_l8_hybas6_v1_t000_metrics_v1"
YEAR = 2018
THRESHOLD = 0.0
SCALE = 30


def mask_sentinel2(image: ee.Image) -> ee.Image:
    scl = image.select("SCL")
    clear = (
        scl.neq(3)
        .And(scl.neq(8))
        .And(scl.neq(9))
        .And(scl.neq(10))
        .And(scl.neq(11))
    )
    return image.updateMask(clear).copyProperties(image, ["system:time_start"])


def prepare_landsat8(image: ee.Image) -> ee.Image:
    qa = image.select("QA_PIXEL")
    clear = (
        qa.bitwiseAnd(1 << 0).eq(0)
        .And(qa.bitwiseAnd(1 << 1).eq(0))
        .And(qa.bitwiseAnd(1 << 2).eq(0))
        .And(qa.bitwiseAnd(1 << 3).eq(0))
        .And(qa.bitwiseAnd(1 << 4).eq(0))
        .And(qa.bitwiseAnd(1 << 5).eq(0))
    )
    optical = image.select("SR_B.").multiply(0.0000275).add(-0.2)
    return (
        image.addBands(optical, None, True)
        .updateMask(clear)
        .updateMask(image.select("QA_RADSAT").eq(0))
        .copyProperties(image, ["system:time_start"])
    )


def safe_divide(numerator: ee.Number, denominator: ee.Number) -> ee.Number:
    return numerator.divide(denominator.max(1e-12))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--drive-folder", default="SRT_GEE_exports")
    args = parser.parse_args()
    ee.Initialize(project=args.project)

    roi = ee.FeatureCollection(ROI_ASSET).geometry().dissolve(1)
    start = ee.Date.fromYMD(YEAR, 6, 1)
    end = ee.Date.fromYMD(YEAR, 10, 1)
    s2_collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40))
        .map(mask_sentinel2)
    )
    l8_collection = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterBounds(roi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUD_COVER", 40))
        .map(prepare_landsat8)
    )
    s2_mndwi = (
        s2_collection.median().clip(roi)
        .normalizedDifference(["B3", "B11"])
        .rename("S2_MNDWI")
    )
    l8_composite = l8_collection.median().clip(roi)
    l8_mndwi = l8_composite.expression(
        "(green - swir1) / (green + swir1)",
        {
            "green": l8_composite.select("SR_B3"),
            "swir1": l8_composite.select("SR_B6"),
        },
    ).rename("L8_MNDWI")
    s2_water = s2_mndwi.gt(THRESHOLD).rename("S2_water")
    l8_water = l8_mndwi.gt(THRESHOLD).rename("L8_water")
    s2_valid = s2_mndwi.mask().gt(0).unmask(0).clip(roi).rename("S2_valid")
    l8_valid = l8_mndwi.mask().gt(0).unmask(0).clip(roi).rename("L8_valid")
    common_valid = s2_valid.And(l8_valid).rename("common_valid")
    s2_missing = s2_valid.Not().rename("S2_missing")
    l8_missing = l8_valid.Not().rename("L8_missing")
    l8_valid_outside_s2 = l8_valid.And(s2_missing).rename("L8_valid_outside_S2")
    s2_water_full = s2_water.updateMask(s2_valid)
    l8_water_full = l8_water.updateMask(l8_valid)
    s2_water_common = s2_water.updateMask(common_valid)
    l8_water_common = l8_water.updateMask(common_valid)
    l8_water_outside_s2 = l8_water.And(l8_valid_outside_s2)
    intersection = s2_water_common.And(l8_water_common)
    union = s2_water_common.Or(l8_water_common)
    jrc_outside = (
        ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
        .select("occurrence").gte(90).unmask(0).clip(roi).And(s2_missing)
    )
    worldcover_outside = (
        ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
        .eq(80).unmask(0).clip(roi).And(s2_missing)
    )
    l8_jrc_overlap = l8_water_outside_s2.And(jrc_outside)
    l8_worldcover_overlap = l8_water_outside_s2.And(worldcover_outside)
    pixel_area = ee.Image.pixelArea().divide(1_000_000)

    def area_band(mask: ee.Image, name: str) -> ee.Image:
        return pixel_area.updateMask(mask).rename(name)

    bands = [
        pixel_area.rename("roi_area_km2"),
        area_band(s2_valid, "s2_valid_area_km2"),
        area_band(l8_valid, "l8_valid_area_km2"),
        area_band(common_valid, "common_valid_area_km2"),
        area_band(s2_missing, "s2_missing_area_km2"),
        area_band(l8_missing, "l8_missing_area_km2"),
        area_band(l8_valid_outside_s2, "l8_valid_outside_s2_area_km2"),
        area_band(s2_water_full, "s2_water_full_valid_area_km2"),
        area_band(l8_water_full, "l8_water_full_valid_area_km2"),
        area_band(s2_water_common, "s2_water_area_km2"),
        area_band(l8_water_common, "l8_water_area_km2"),
        area_band(l8_water_outside_s2, "l8_water_outside_s2_valid_area_km2"),
        area_band(jrc_outside, "jrc_water_outside_s2_area_km2"),
        area_band(worldcover_outside, "worldcover_water_outside_s2_area_km2"),
        area_band(l8_jrc_overlap, "l8_jrc_overlap_outside_s2_area_km2"),
        area_band(
            l8_worldcover_overlap,
            "l8_worldcover_overlap_outside_s2_area_km2",
        ),
        area_band(intersection, "intersection_area_km2"),
        area_band(union, "union_area_km2"),
    ]
    stack = bands[0]
    for band in bands[1:]:
        stack = stack.addBands(band)
    l8_projection = ee.Image(l8_collection.first()).select("SR_B3").projection()
    areas = stack.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=roi,
        scale=SCALE,
        crs=l8_projection,
        tileScale=4,
        maxPixels=1e13,
    )
    values = {name: ee.Number(areas.get(name)) for name in [
        "roi_area_km2", "s2_valid_area_km2", "l8_valid_area_km2",
        "common_valid_area_km2", "s2_missing_area_km2", "l8_missing_area_km2",
        "l8_valid_outside_s2_area_km2", "s2_water_full_valid_area_km2",
        "l8_water_full_valid_area_km2", "s2_water_area_km2",
        "l8_water_area_km2", "l8_water_outside_s2_valid_area_km2",
        "jrc_water_outside_s2_area_km2", "worldcover_water_outside_s2_area_km2",
        "l8_jrc_overlap_outside_s2_area_km2",
        "l8_worldcover_overlap_outside_s2_area_km2", "intersection_area_km2",
        "union_area_km2",
    ]}
    v = values
    props = {
        "year": YEAR,
        "s2_image_count": s2_collection.size(),
        "l8_image_count": l8_collection.size(),
        "s2_threshold": THRESHOLD,
        "l8_threshold": THRESHOLD,
        **v,
        "s2_valid_share": safe_divide(v["s2_valid_area_km2"], v["roi_area_km2"]),
        "l8_valid_share": safe_divide(v["l8_valid_area_km2"], v["roi_area_km2"]),
        "common_valid_share": safe_divide(v["common_valid_area_km2"], v["roi_area_km2"]),
        "s2_missing_share": safe_divide(v["s2_missing_area_km2"], v["roi_area_km2"]),
        "l8_missing_share": safe_divide(v["l8_missing_area_km2"], v["roi_area_km2"]),
        "s2_water_common_capture_share": safe_divide(v["s2_water_area_km2"], v["s2_water_full_valid_area_km2"]),
        "l8_water_common_capture_share": safe_divide(v["l8_water_area_km2"], v["l8_water_full_valid_area_km2"]),
        "l8_water_outside_s2_share": safe_divide(v["l8_water_outside_s2_valid_area_km2"], v["l8_water_full_valid_area_km2"]),
        "s2_l8_gapfill_water_area_km2": v["s2_water_full_valid_area_km2"].add(v["l8_water_outside_s2_valid_area_km2"]),
        "l8_gapfill_addition_vs_s2_share": safe_divide(v["l8_water_outside_s2_valid_area_km2"], v["s2_water_full_valid_area_km2"]),
        "area_difference_l8_full_minus_s2_full_km2": v["l8_water_full_valid_area_km2"].subtract(v["s2_water_full_valid_area_km2"]),
        "l8_jrc_coverage_outside_s2": safe_divide(v["l8_jrc_overlap_outside_s2_area_km2"], v["jrc_water_outside_s2_area_km2"]),
        "l8_gap_water_jrc_overlap_share": safe_divide(v["l8_jrc_overlap_outside_s2_area_km2"], v["l8_water_outside_s2_valid_area_km2"]),
        "l8_worldcover_coverage_outside_s2": safe_divide(v["l8_worldcover_overlap_outside_s2_area_km2"], v["worldcover_water_outside_s2_area_km2"]),
        "l8_gap_water_worldcover_overlap_share": safe_divide(v["l8_worldcover_overlap_outside_s2_area_km2"], v["l8_water_outside_s2_valid_area_km2"]),
        "iou": safe_divide(v["intersection_area_km2"], v["union_area_km2"]),
        "dice": safe_divide(v["intersection_area_km2"].multiply(2), v["s2_water_area_km2"].add(v["l8_water_area_km2"])),
        "s2_covered_by_l8": safe_divide(v["intersection_area_km2"], v["s2_water_area_km2"]),
        "l8_covered_by_s2": safe_divide(v["intersection_area_km2"], v["l8_water_area_km2"]),
        "area_difference_l8_minus_s2_km2": v["l8_water_area_km2"].subtract(v["s2_water_area_km2"]),
        "roi_version": "hybas6_v1",
        "comparison_scale_m": SCALE,
    }
    fields = list(props)
    task = ee.batch.Export.table.toDrive(
        collection=ee.FeatureCollection([ee.Feature(None, props)]),
        description=EXPORT_NAME,
        folder=args.drive_folder,
        fileNamePrefix=EXPORT_NAME,
        fileFormat="CSV",
        selectors=fields,
    )
    task.start()
    print(f"Started task: {task.id} | {EXPORT_NAME}")


if __name__ == "__main__":
    main()
