"""Build local water and valid-observation candidate tiles from an MNDWI COG."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_VERSION = "hybas6_v1_t000"
YEAR = 2024
EXPECTED_SOURCE_SHA256 = (
    "60bbab4f520443df43931ba1ac3589fe116e497fa1db622cf893cc85b8711e47"
)
EXPECTED_VALID_PIXEL_COUNT = 86_113_134
MIN_ZOOM = 5
MAX_ZOOM = 13
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_png_header(path: Path) -> dict[str, int]:
    with path.open("rb") as file:
        signature = file.read(8)
        length_raw = file.read(4)
        chunk_type = file.read(4)
        if signature != PNG_SIGNATURE or len(length_raw) != 4 or chunk_type != b"IHDR":
            raise ValueError(f"无效PNG文件：{path}")
        length = struct.unpack(">I", length_raw)[0]
        payload = file.read(length)
    if length != 13 or len(payload) != 13:
        raise ValueError(f"无效PNG IHDR：{path}")
    width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", payload)
    return {
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": color_type,
    }


def inventory_tiles(tile_root: Path) -> dict[str, Any]:
    files = sorted(tile_root.glob("*/*/*.png"), key=lambda item: item.as_posix())
    if not files:
        raise ValueError(f"未生成PNG瓦片：{tile_root}")

    aggregate = hashlib.sha256()
    counts_by_zoom: dict[str, int] = {}
    total_bytes = 0
    for path in files:
        relative = path.relative_to(tile_root).as_posix()
        parts = relative.split("/")
        if len(parts) != 3 or not all(part.isdigit() for part in parts[:2]):
            raise ValueError(f"瓦片路径不符合z/x/y.png：{relative}")
        header = read_png_header(path)
        if header != {
            "width": 256,
            "height": 256,
            "bit_depth": 8,
            "color_type": 6,
        }:
            raise ValueError(f"瓦片不是256像素8位RGBA PNG：{relative}，{header}")
        zoom = parts[0]
        counts_by_zoom[zoom] = counts_by_zoom.get(zoom, 0) + 1
        tile_hash = sha256_file(path)
        aggregate.update(relative.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(bytes.fromhex(tile_hash))
        total_bytes += path.stat().st_size

    expected_zooms = {str(zoom) for zoom in range(MIN_ZOOM, MAX_ZOOM + 1)}
    if set(counts_by_zoom) != expected_zooms:
        raise ValueError(
            f"瓦片缩放级别不完整：实际{sorted(counts_by_zoom)}，预期{sorted(expected_zooms)}"
        )
    return {
        "tile_count": len(files),
        "counts_by_zoom": dict(sorted(counts_by_zoom.items(), key=lambda item: int(item[0]))),
        "total_bytes": total_bytes,
        "package_sha256": aggregate.hexdigest(),
        "png": {"width": 256, "height": 256, "bit_depth": 8, "color_type": "RGBA"},
    }


def qgis_environment(qgis_root: Path) -> tuple[dict[str, str], Path, Path]:
    python = qgis_root / "apps" / "Python312" / "python.exe"
    gdaldem = qgis_root / "bin" / "gdaldem.exe"
    required = [
        python,
        gdaldem,
        qgis_root / "apps" / "Python312" / "Lib" / "site-packages" / "osgeo",
        qgis_root / "apps" / "gdal" / "share" / "gdal",
        qgis_root / "share" / "proj",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("缺少本地GDAL运行组件：" + "；".join(missing))

    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(
        [
            str(qgis_root / "bin"),
            str(qgis_root / "apps" / "qgis" / "bin"),
            str(qgis_root / "apps" / "Python312"),
            env.get("PATH", ""),
        ]
    )
    env["PYTHONHOME"] = str(qgis_root / "apps" / "Python312")
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(qgis_root / "apps" / "Python312" / "Lib"),
            str(qgis_root / "apps" / "Python312" / "Lib" / "site-packages"),
        ]
    )
    env["GDAL_DATA"] = str(qgis_root / "apps" / "gdal" / "share" / "gdal")
    env["PROJ_LIB"] = str(qgis_root / "share" / "proj")
    return env, python, gdaldem


def run(command: list[str], env: dict[str, str]) -> None:
    print("运行：" + " ".join(command), flush=True)
    subprocess.run(command, check=True, env=env)


def inspect_binary_mask(path: Path, python: Path, env: dict[str, str]) -> dict[str, Any]:
    code = """
import json
import sys
import numpy as np
from osgeo import gdal

dataset = gdal.Open(sys.argv[1])
if dataset is None:
    raise SystemExit("无法打开掩膜")
band = dataset.GetRasterBand(1)
block_x, block_y = band.GetBlockSize()
ones = 0
others = 0
for y in range(0, dataset.RasterYSize, block_y):
    height = min(block_y, dataset.RasterYSize - y)
    for x in range(0, dataset.RasterXSize, block_x):
        width = min(block_x, dataset.RasterXSize - x)
        values = band.ReadAsArray(x, y, width, height)
        ones += int(np.count_nonzero(values == 1))
        others += int(np.count_nonzero((values != 0) & (values != 1)))
print(json.dumps({
    "width": dataset.RasterXSize,
    "height": dataset.RasterYSize,
    "bands": dataset.RasterCount,
    "data_type": gdal.GetDataTypeName(band.DataType),
    "nodata": band.GetNoDataValue(),
    "one_pixel_count": ones,
    "unexpected_pixel_count": others,
    "projection_contains_3857": "3857" in dataset.GetProjection(),
}))
"""
    result = subprocess.run(
        [str(python), "-c", code, str(path)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    stats = json.loads(result.stdout.strip().splitlines()[-1])
    expected = {
        "width": 16212,
        "height": 10358,
        "bands": 1,
        "data_type": "Byte",
        "nodata": 0.0,
        "unexpected_pixel_count": 0,
        "projection_contains_3857": True,
    }
    for key, value in expected.items():
        if stats.get(key) != value:
            raise ValueError(f"掩膜校验失败：{path.name} 的 {key}={stats.get(key)!r}，预期{value!r}")
    return stats


def build_binary_cog(
    source: Path,
    output: Path,
    expression: str,
    python: Path,
    env: dict[str, str],
) -> None:
    command = [
        str(python),
        "-m",
        "osgeo_utils.gdal_calc",
        "-A",
        str(source),
        f"--calc={expression}",
        "--hideNoData",
        "--type=Byte",
        "--NoDataValue=0",
        "--format=COG",
        "--co=COMPRESS=DEFLATE",
        "--co=LEVEL=9",
        "--co=BLOCKSIZE=512",
        "--co=OVERVIEW_RESAMPLING=NEAREST",
        "--co=NUM_THREADS=ALL_CPUS",
        f"--outfile={output}",
    ]
    run(command, env)


def colorize_mask(
    source: Path,
    output: Path,
    color_file: Path,
    gdaldem: Path,
    env: dict[str, str],
) -> None:
    run(
        [
            str(gdaldem),
            "color-relief",
            str(source),
            str(color_file),
            str(output),
            "-alpha",
            "-nearest_color_entry",
            "-of",
            "COG",
            "-co",
            "COMPRESS=DEFLATE",
            "-co",
            "LEVEL=9",
            "-co",
            "BLOCKSIZE=512",
            "-co",
            "OVERVIEW_RESAMPLING=NEAREST",
            "-co",
            "NUM_THREADS=ALL_CPUS",
        ],
        env,
    )


def tile_rgba_cog(
    source: Path,
    output: Path,
    python: Path,
    processes: int,
    env: dict[str, str],
) -> None:
    run(
        [
            str(python),
            "-m",
            "osgeo_utils.gdal2tiles",
            "--legacy",
            "--xyz",
            "--zoom=5-13",
            "--resampling=near",
            "--exclude",
            "--processes",
            str(processes),
            "--tiledriver=PNG",
            "--no-kml",
            "--webviewer=none",
            str(source),
            str(output),
        ],
        env,
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build(args: argparse.Namespace) -> Path:
    source = args.input.resolve()
    output_root = args.output_root.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"找不到输入COG：{source}")
    source_sha256 = sha256_file(source)
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise ValueError(
            f"输入COG校验和不匹配：{source_sha256}，预期{EXPECTED_SOURCE_SHA256}"
        )
    if output_root.exists():
        raise FileExistsError(f"候选输出已存在，未覆盖：{output_root}")

    env, qgis_python, gdaldem = qgis_environment(args.qgis_root.resolve())
    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{YEAR}-tiles-", dir=output_root.parent))
    sources = staging / "sources"
    work = staging / "_work"
    sources.mkdir()
    work.mkdir()

    layer_specs = {
        "water_mask": {
            "expression": "logical_and(A!=-9999,A>0)",
            "color": "#0000FF",
            "palette": "nv 0 0 0 0\n0 0 0 0 0\n1 0 0 255 255\n",
            "rule": "source_mndwi != -9999 and source_mndwi > 0.0",
        },
        "valid_observation": {
            "expression": "A!=-9999",
            "color": "#00C853",
            "palette": "nv 0 0 0 0\n0 0 0 0 0\n1 0 200 83 255\n",
            "rule": "source_mndwi != -9999",
        },
    }

    try:
        results: dict[str, Any] = {}
        for layer_id, spec in layer_specs.items():
            print(f"\n生成 {layer_id} 候选资产", flush=True)
            binary_cog = sources / f"{layer_id}_{YEAR}_{DATASET_VERSION}_candidate.tif"
            rgba_cog = work / f"{layer_id}_{YEAR}_{DATASET_VERSION}_rgba.tif"
            color_file = work / f"{layer_id}.txt"
            tile_root = staging / layer_id
            color_file.write_text(str(spec["palette"]), encoding="ascii")

            build_binary_cog(
                source,
                binary_cog,
                str(spec["expression"]),
                qgis_python,
                env,
            )
            stats = inspect_binary_mask(binary_cog, qgis_python, env)
            colorize_mask(binary_cog, rgba_cog, color_file, gdaldem, env)
            tile_rgba_cog(rgba_cog, tile_root, qgis_python, args.processes, env)
            inventory = inventory_tiles(tile_root)
            results[layer_id] = {
                "status": "candidate",
                "derivation_rule": spec["rule"],
                "display_color": spec["color"],
                "source_cog": f"sources/{binary_cog.name}",
                "source_cog_sha256": sha256_file(binary_cog),
                "source_cog_bytes": binary_cog.stat().st_size,
                "binary_raster": stats,
                "tiles": layer_id + "/{z}/{x}/{y}.png",
                **inventory,
            }

        valid_count = results["valid_observation"]["binary_raster"]["one_pixel_count"]
        water_count = results["water_mask"]["binary_raster"]["one_pixel_count"]
        if valid_count != EXPECTED_VALID_PIXEL_COUNT:
            raise ValueError(
                f"有效观测像元数{valid_count}与输入COG复验值{EXPECTED_VALID_PIXEL_COUNT}不一致"
            )
        if not 0 < water_count <= valid_count:
            raise ValueError(f"水体像元数不合法：{water_count}，有效像元数：{valid_count}")

        manifest = {
            "status": "candidate",
            "dataset_version": DATASET_VERSION,
            "year": YEAR,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": {
                "file_name": source.name,
                "sha256": source_sha256,
                "crs": "EPSG:3857",
                "pixel_size_m": 20,
                "nodata": -9999,
                "band": "MNDWI",
            },
            "tile_contract": {
                "scheme": "XYZ",
                "crs": "EPSG:3857",
                "min_zoom": MIN_ZOOM,
                "max_zoom": MAX_ZOOM,
                "format": "PNG",
                "tile_size": 256,
                "resampling": "nearest",
                "public_url": None,
            },
            "layers": results,
            "promotion": {
                "eligible": False,
                "reason": "本地候选资产尚未发布到稳定HTTPS地址，也未完成浏览器性能验收。",
            },
        }
        write_json(staging / "candidate_manifest.json", manifest)
        shutil.rmtree(work)
        staging.rename(output_root)
    except Exception:
        print(f"构建未完成，诊断文件保留在：{staging}", file=sys.stderr)
        raise

    return output_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从已验证的2024 MNDWI COG生成本地水体和有效观测候选XYZ瓦片。"
    )
    parser.add_argument("--input", type=Path, required=True, help="MNDWI COG路径。")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=(
            PROJECT_ROOT
            / "data"
            / "processed"
            / "candidates"
            / "raster_tiles"
            / DATASET_VERSION
            / str(YEAR)
        ),
        help="候选输出目录；已存在时拒绝覆盖。",
    )
    parser.add_argument(
        "--qgis-root",
        type=Path,
        default=Path(r"C:\Program Files\QGIS 3.44.11"),
        help="包含GDAL和Python运行时的QGIS安装目录。",
    )
    parser.add_argument(
        "--processes",
        type=int,
        default=max(1, min(4, os.cpu_count() or 1)),
        help="瓦片生成进程数。",
    )
    args = parser.parse_args()
    if args.processes < 1:
        parser.error("--processes必须大于0")
    return args


def main() -> int:
    try:
        output = build(parse_args())
    except (FileNotFoundError, FileExistsError, ValueError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"\n候选瓦片生成完成：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
