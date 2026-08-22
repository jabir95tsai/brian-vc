from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = PLUGIN_ROOT / "scripts" / "preflight.py"


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


if __name__ == "__main__":
    unittest.main()
