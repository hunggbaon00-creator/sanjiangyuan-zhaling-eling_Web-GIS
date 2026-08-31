"""Validate the annual raster tile manifest without requesting remote tiles."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "config" / "raster_layers.json"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the raster XYZ tile manifest contract."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to raster_layers.json.",
    )
    return parser.parse_args()


def main() -> None:
    from app.raster_tiles import load_raster_manifest

    args = parse_args()
    manifest = load_raster_manifest(args.manifest)
    statuses = Counter(
        asset.status for layer in manifest.layers for asset in layer.assets
    )
    print("raster tile manifest validation: OK")
    print(f"contract version: {manifest.contract_version}")
    print(f"dataset version: {manifest.dataset_version}")
    print(f"layers: {len(manifest.layers)}")
    print(f"layer-year assets: {sum(statuses.values())}")
    for status in sorted(statuses):
        print(f"{status}: {statuses[status]}")


if __name__ == "__main__":
    main()
