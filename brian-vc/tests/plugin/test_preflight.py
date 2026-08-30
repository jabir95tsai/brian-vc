from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = PLUGIN_ROOT / "scripts" / "preflight.py"


def load_preflight():
    spec = importlib.util.spec_from_file_location("brian_vc_preflight", PREFLIGHT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DistributionPreflightTests(unittest.TestCase):
    def test_packaging_preflight_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PREFLIGHT), "--skip-python-deps", "--json"],
            cwd=PLUGIN_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "pass")
        labels = {item["label"] for item in report["results"]}
        for skill_name in (
            "vc-quick-screen",
            "prospectus-extractor",
            "vc-investment-evaluator",
        ):
            self.assertIn(f"{skill_name}: SKILL.md", labels)
            self.assertIn(f"{skill_name}: default prompt", labels)


class IdentityLayoutTests(unittest.TestCase):
    """Both unpack layouts pass; a renamed or misplaced package still fails."""

    MANIFEST = {"name": "brian-vc", "version": "1.0.0+codex.20260815141526"}

    def identity(self, folder: str, manifest: dict | None = None) -> dict:
        module = load_preflight()
        return module.validate_identity(
            Path("C:/staging") / folder, self.MANIFEST if manifest is None else manifest
        )

    def test_source_checkout_layout_passes(self) -> None:
        self.assertEqual(self.identity("brian-vc")["status"], "pass")

    def test_codex_versioned_install_layout_passes(self) -> None:
        result = self.identity("brian-vc/1.0.0+codex.20260815141526")
        self.assertEqual(result["status"], "pass", result["detail"])

    def test_renamed_package_folder_fails(self) -> None:
        self.assertEqual(self.identity("vc-plugin")["status"], "fail")

    def test_version_folder_under_the_wrong_parent_fails(self) -> None:
        self.assertEqual(
            self.identity("some-other-plugin/1.0.0+codex.20260815141526")["status"], "fail"
        )

    def test_version_folder_not_matching_the_manifest_fails(self) -> None:
        self.assertEqual(self.identity("brian-vc/9.9.9")["status"], "fail")

    def test_foreign_manifest_name_fails(self) -> None:
        result = self.identity("brian-vc", {"name": "other", "version": "1.0.0"})
        self.assertEqual(result["status"], "fail")


if __name__ == "__main__":
    unittest.main()
