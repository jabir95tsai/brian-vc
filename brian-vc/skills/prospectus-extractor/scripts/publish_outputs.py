#!/usr/bin/env python3
"""Publish a validated prospectus output set under a human-readable prefix.

Analysts want Chinese filenames on the deliverable, but copying the files by
hand is how a ``validation_status: failed`` manifest ends up published next to
the artefact it fails to describe. This step refuses to publish anything unless
the source manifest validated, then records the alias with its own hashes so the
published set can be checked without re-deriving it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SUFFIXES = (
    "_case_data.json",
    "_Prospectus_raw.md",
    "_Factbase.md",
    "_Prospectus_coverage.md",
    "_Prospectus_extract.xlsx",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="Validated source manifest.")
    parser.add_argument("--display-prefix", required=True, help="e.g. 示範科技")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("validation_status") != "success":
        print(
            f"ERROR: refusing to publish from a manifest with "
            f"validation_status={manifest.get('validation_status')!r}: {args.manifest}",
            file=sys.stderr,
        )
        return 2

    source_dir = args.manifest.resolve().parent
    output_dir = (args.output_dir or source_dir).resolve()
    case_id = manifest["case_id"]
    output_dir.mkdir(parents=True, exist_ok=True)

    published = []
    for suffix in SUFFIXES:
        source = source_dir / f"{case_id}{suffix}"
        if not source.is_file():
            print(f"ERROR: source output missing: {source}", file=sys.stderr)
            return 2
        target = output_dir / f"{args.display_prefix}{suffix}"
        if target.resolve() != source.resolve():
            shutil.copy2(source, target)
        digest = sha256_file(target)
        if digest != sha256_file(source):
            print(f"ERROR: published copy does not match source: {target}", file=sys.stderr)
            return 2
        published.append(
            {
                "published_path": str(target),
                "source_path": str(source),
                "sha256": digest,
                "bytes": target.stat().st_size,
            }
        )

    alias = {
        "kind": "published_alias",
        "display_prefix": args.display_prefix,
        "source_case_id": case_id,
        "source_manifest": str(args.manifest.resolve()),
        "source_validation_status": manifest["validation_status"],
        "published_at": datetime.now(timezone.utc).isoformat(),
        "files": published,
        "validation_status": "success",
    }
    alias_path = output_dir / f"{args.display_prefix}_Prospectus_manifest.json"
    alias_path.write_text(json.dumps(alias, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "success", "alias_manifest": str(alias_path), "files": len(published)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
