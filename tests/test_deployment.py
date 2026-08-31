import tempfile
import unittest
from pathlib import Path

from app.deployment import (
    read_pinned_requirements,
    validate_installed_requirements,
    validate_requirement_subset,
    validate_runtime_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = PROJECT_ROOT / "environment" / "requirements-web.lock.txt"
DIRECT_REQUIREMENTS_PATH = PROJECT_ROOT / "environment" / "requirements-web.txt"


class DeploymentTests(unittest.TestCase):
    def test_runtime_bundle_is_complete(self) -> None:
        summary = validate_runtime_bundle(PROJECT_ROOT)

        self.assertEqual(summary["dataset_version"], "hybas6_v1_t000")
        self.assertEqual(summary["overall_rows"], 7)
        self.assertEqual(summary["subbasin_rows"], 35)
        self.assertEqual(summary["boundary_features"], 5)
        self.assertEqual(summary["raster_assets"], 35)

    def test_active_runtime_matches_lock(self) -> None:
        self.assertGreater(validate_installed_requirements(LOCK_PATH), 40)

    def test_direct_requirements_match_lock(self) -> None:
        self.assertEqual(
            validate_requirement_subset(DIRECT_REQUIREMENTS_PATH, LOCK_PATH),
            7,
        )

    def test_loose_requirement_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "requirements.txt"
            path.write_text("streamlit>=1.58\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "不是精确版本"):
                read_pinned_requirements(path)


if __name__ == "__main__":
    unittest.main()
