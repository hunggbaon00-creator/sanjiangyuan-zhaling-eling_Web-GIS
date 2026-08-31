"""Run deterministic deployment checks without GEE or tile requests."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = PROJECT_ROOT / "environment" / "requirements-web.lock.txt"
DIRECT_REQUIREMENTS_PATH = (
    PROJECT_ROOT / "environment" / "requirements-web.txt"
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    from app.deployment import (
        validate_installed_requirements,
        validate_requirement_subset,
        validate_runtime_bundle,
    )

    try:
        direct_dependency_count = validate_requirement_subset(
            DIRECT_REQUIREMENTS_PATH, LOCK_PATH
        )
        dependency_count = validate_installed_requirements(LOCK_PATH)
        summary = validate_runtime_bundle(PROJECT_ROOT)
    except (OSError, ValueError) as error:
        raise SystemExit(f"deployment preflight: FAILED\n{error}") from error

    print("deployment preflight: OK")
    print(f"direct Web packages: {direct_dependency_count}")
    print(f"locked packages: {dependency_count}")
    print(f"dataset version: {summary['dataset_version']}")
    print(f"overall rows: {summary['overall_rows']}")
    print(f"subbasin rows: {summary['subbasin_rows']}")
    print(f"boundary features: {summary['boundary_features']}")
    print(f"raster layer-year assets: {summary['raster_assets']}")


if __name__ == "__main__":
    main()
