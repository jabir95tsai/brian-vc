# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import shutil
import unittest
from pathlib import Path


def cleanup_generated_artifacts() -> None:
    test_dir = Path(__file__).parent
    skill_scripts = test_dir.parents[1] / "skills" / "prospectus-extractor" / "scripts"
    for root in (test_dir, skill_scripts):
        for cache in root.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
    for name in (
        "_legacy_fixture.xlsx",
        "_manifest_fixture.xlsx",
        "_runtime_pdf",
        "_runtime_manifest",
    ):
        target = test_dir / name
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)


def main() -> int:
    cleanup_generated_artifacts()
    try:
        suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    finally:
        cleanup_generated_artifacts()


if __name__ == "__main__":
    sys.exit(main())
