r"""Check whether the local environment can access Google Earth Engine.

Usage:
    .\.venv\Scripts\python.exe scripts\gee\gee_auth_check.py
    .\.venv\Scripts\python.exe scripts\gee\gee_auth_check.py --project YOUR_GCP_PROJECT_ID
"""

from __future__ import annotations

import argparse

import ee


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        help="Optional Google Cloud project ID registered for Earth Engine.",
    )
    args = parser.parse_args()

    try:
        if args.project:
            ee.Initialize(project=args.project)
        else:
            ee.Initialize()

        value = ee.Number(1).getInfo()
        print("Earth Engine authentication: OK")
        print(f"Test value: {value}")
    except Exception as exc:  # noqa: BLE001 - show the exact auth/setup message.
        print("Earth Engine authentication: FAILED")
        print(type(exc).__name__)
        print(exc)
        print()
        print("Next step:")
        print(r"  .\.venv\Scripts\python.exe -m ee.cli.eecli authenticate --auth_mode=localhost:0")
        print("If Earth Engine asks for a Cloud project later, rerun with:")
        print(r"  .\.venv\Scripts\python.exe scripts\gee\gee_auth_check.py --project YOUR_GCP_PROJECT_ID")


if __name__ == "__main__":
    main()
