#!/usr/bin/env python3
"""Reproducible local test entrypoint for vc-quick-screen."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

# Child processes inherit this, so no helper import can leave bytecode behind.
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

TEST_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TEST_DIR.parents[1]
SKILL_DIR = PLUGIN_ROOT / "skills" / "vc-quick-screen"
EXPECTATIONS = TEST_DIR / "fixture_expectations.json"
CURRENT_OUTPUT = (
    TEST_DIR
    / "run-009-independent-vqs-1.4"
    / "星橋邊緣運算_初篩備忘_v1.md"
)
POSITIVE_OUTPUTS = (
    CURRENT_OUTPUT,
    TEST_DIR / "run-003-vqs-1.3" / "星橋邊緣運算_初篩備忘_v1.md",
    TEST_DIR
    / "run-004-independent-vqs-1.3"
    / "星橋邊緣運算_初篩備忘_v1.md",
)
NEGATIVE_OUTPUT = TEST_DIR / "negative_empty_shell.md"
# vQS-1.5 coefficient-tier regression on the synthetic 星橋 memo, evaluated
# without --legacy-contract. This is the portable core: it runs everywhere,
# including the public mirror, which carries no real case material.
VQS15_OUTPUT = (
    TEST_DIR / "run-009-independent-vqs-1.4" / "星橋邊緣運算_初篩備忘_v1.md"
)
# Real-case regressions are extra coverage held only in the private tree. They
# are skipped when the fixtures are absent, so the same file works in both.
GUANQING_OUTPUT = (
    TEST_DIR / "run-010-guanqing-vqs-1.5" / "示範能源_初篩備忘_v1.md"
)
GUANQING_EXPECTATIONS = TEST_DIR / "fixture_guanqing_expectations.json"
ANFU_OUTPUT = (
    TEST_DIR / "run-011-independent-vqs-1.5" / "示範科技_初篩備忘_v1.md"
)


def cleanup_generated_artifacts() -> None:
    """Drop bytecode caches and variant scratch files left by an aborted run.

    Each helper already unlinks its own scratch file in a `finally`, but a
    killed run skips that; sweeping at both ends keeps the tree clean either way.
    """
    for root in (TEST_DIR, SKILL_DIR):
        for cache in root.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
    for scratch in TEST_DIR.glob(".*-variant.md"):
        scratch.unlink(missing_ok=True)


def run(label: str, command: list[str], *, expect_success: bool = True) -> bool:
    print(f"\n=== {label} ===")
    completed = subprocess.run(command, text=True)
    ok = completed.returncode == 0
    if ok != expect_success:
        print(
            f"[FAIL] exit={completed.returncode}; "
            f"expected {'success' if expect_success else 'failure'}"
        )
        return False
    print(
        f"[PASS] exit={completed.returncode}; "
        f"expected {'success' if expect_success else 'failure'}"
    )
    return True


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def supports_python_docx(executable: Path) -> bool:
    if not executable.is_file():
        return False
    completed = subprocess.run(
        [str(executable), "-c", "import docx"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def select_docx_python(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    if os.environ.get("VC_QUICK_SCREEN_DOCX_PYTHON"):
        return Path(os.environ["VC_QUICK_SCREEN_DOCX_PYTHON"]).expanduser().resolve()
    candidates = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "python"
        / "python.exe",
        Path(sys.executable),
    )
    seen = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if supports_python_docx(resolved):
            return resolved
    # Use the caller as a diagnostic fallback so render_memo_docx.py emits its
    # actionable dependency message instead of an opaque runner-side error.
    return Path(sys.executable).resolve()


def step_heading_compatibility() -> bool:
    print("\n=== Step-heading compatibility ===")
    source = CURRENT_OUTPUT.read_text(encoding="utf-8")
    variant = re.sub(
        r"(?m)^(#{2,3})\s+(\d+(?:\.\d+)?)\s*[.．｜|:：]?\s*",
        r"\1 Step \2｜",
        source,
    )
    output = TEST_DIR / ".step-heading-variant.md"
    try:
        output.write_text(variant, encoding="utf-8")
        return run(
            "Step N heading variant",
            [
                sys.executable,
                "-X",
                "utf8",
                str(TEST_DIR / "evaluate_output.py"),
                str(output),
                "--expectations",
                str(EXPECTATIONS),
            ],
        )
    finally:
        output.unlink(missing_ok=True)


def numeric_subheading_compatibility() -> bool:
    print("\n=== Numeric child-heading compatibility ===")
    source = CURRENT_OUTPUT.read_text(encoding="utf-8")
    marker = "## 1. 公司快照\n"
    if marker not in source:
        print("[FAIL] current fixture is missing the canonical section 1 heading")
        return False
    variant = source.replace(
        marker,
        marker + "\n### 2025 財務 headline\n\n### 2026E 財測橋接\n",
        1,
    )
    output = TEST_DIR / ".numeric-subheading-variant.md"
    try:
        output.write_text(variant, encoding="utf-8")
        return run(
            "Unknown numeric child headings stay inside section 1",
            [
                sys.executable,
                "-X",
                "utf8",
                str(TEST_DIR / "evaluate_output.py"),
                str(output),
                "--expectations",
                str(EXPECTATIONS),
            ],
        )
    finally:
        output.unlink(missing_ok=True)


def contract_format_variants() -> bool:
    """Accept formatting choices that the Skill contract explicitly allows."""
    print("\n=== Contract-compliant format variants ===")
    source = CURRENT_OUTPUT.read_text(encoding="utf-8")

    source = re.sub(
        r"(?ms)(^## 0\.[^\n]*\n).*?(?=^## 1\.)",
        (
            r"\1\n"
            "- 文件：`fixture_pitch_deck.md`；單一 Markdown pitch deck。\n"
            "- 已揭露：公司、產品、客戶、財務、市場與募資。\n"
            "- 明顯缺口：查核財報、合約、股權、專利與訂單。\n"
            "- **資料級別：L0 薄資料。** 單一自述 Deck，僅適用初篩。\n\n"
        ),
        source,
        count=1,
    )
    # The contract says ★/5 but does not require a redundant numeric score.
    section_25_start = source.index("## 2.5")
    section_3_start = source.index("## 3.", section_25_start)
    expert_block = re.sub(
        r"([★☆]{5})\s+[0-5](?:\.\d)?/5",
        r"\1",
        source[section_25_start:section_3_start],
    )
    source = (
        source[:section_25_start] + expert_block + source[section_3_start:]
    )
    source = re.sub(
        r"(?ms)(^## 7\.[^\n]*\n).*?(?=^## 8\.)",
        (
            r"\1\n"
            "| 優先 | 必取資料 |\n"
            "|---|---|\n"
            "| 🔴 必要 | 財報、股東名冊、Term Sheet、詳細三表 |\n"
            "| 🟡 重要 | 財測、主要合約、訂單與 CapEx |\n"
            "| 🟢 補充 | 專利、認證與競品 benchmark |\n\n"
        ),
        source,
        count=1,
    )

    output = TEST_DIR / ".contract-format-variant.md"
    try:
        output.write_text(source, encoding="utf-8")
        return run(
            "Bullet inventory, pure-star scores and table checklist",
            [
                sys.executable,
                "-X",
                "utf8",
                str(TEST_DIR / "evaluate_output.py"),
                str(output),
                "--expectations",
                str(EXPECTATIONS),
            ],
        )
    finally:
        output.unlink(missing_ok=True)


def canonical_skeleton_contract() -> bool:
    print("\n=== Current vQS-1.4 canonical skeleton ===")
    text = CURRENT_OUTPUT.read_text(encoding="utf-8")
    expected = (
        "## 0. 文件盤點",
        "## 1. 公司快照",
        "### 1.5 內部一致性驗算",
        "## 2. 賽道與同業速覽",
        "### 2.2 外部足跡速查",
        "## 2.5 六專家速評",
        "## 3. 亮點與疑慮",
        "## 4. 規模與獲利天花板",
        "## 5. 估值邊界",
        "## 6. 管理層拷問",
        "## 7. 必取資料清單",
        "## 8. 初判與升級條件",
    )
    positions = [text.find(heading) for heading in expected]
    present = all(position >= 0 for position in positions)
    ordered = present and positions == sorted(positions)
    print(f"[{'PASS' if present else 'FAIL'}] all canonical headings and levels")
    print(f"[{'PASS' if ordered else 'FAIL'}] canonical heading order")
    return present and ordered


def docx_smoke(path: Path) -> bool:
    print("\n=== DOCX structural smoke ===")
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            required = {
                "[Content_Types].xml",
                "word/document.xml",
                "word/styles.xml",
                "word/numbering.xml",
            }
            document_xml = archive.read("word/document.xml").decode("utf-8")
            numbering_xml = archive.read("word/numbering.xml").decode("utf-8")
        checks = {
            "required OOXML parts": required <= names,
            "six tables rendered": document_xml.count("<w:tbl>") >= 6,
            "fixed disclaimer present": "本初篩為初步研究觀察" in document_xml,
            "emoji converted to readable labels": "🔴" not in document_xml
            and "[紅旗]" in document_xml,
            "semantic headings are not duplicated": "[亮點] 亮點" not in document_xml
            and "[紅旗] 疑慮" not in document_xml,
            "independent numbered lists": numbering_xml.count("<w:startOverride") >= 3,
            "numbering reserves a space after markers": (
                '<w:suff w:val="space"' in numbering_xml
            ),
            "expert role column has named width override": (
                '<w:gridCol w:w="1800"' in document_xml
            ),
            "table rows do not split across pages": "<w:cantSplit" in document_xml,
        }
    except Exception as exc:
        print(f"[FAIL] cannot inspect DOCX: {exc}")
        return False

    failed = []
    for label, ok in checks.items():
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            failed.append(label)
    return not failed


def _run() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-external",
        action="store_true",
        help="Run environment-owned validators when installed.",
    )
    parser.add_argument(
        "--docx-python",
        help=(
            "Python executable containing python-docx. Defaults to "
            "VC_QUICK_SCREEN_DOCX_PYTHON, then the Codex Documents runtime."
        ),
    )
    args = parser.parse_args()
    results = []

    results.append(
        run(
            "Static Skill contract",
            [sys.executable, "-X", "utf8", str(TEST_DIR / "check_skill.py")],
        )
    )
    for output in POSITIVE_OUTPUTS:
        # run-003/004 predate the vQS-1.5 coefficient tier; they stay in the
        # suite to prove format compatibility, judged by their own era's rules.
        legacy = ["--legacy-contract"] if output is not CURRENT_OUTPUT else []
        results.append(
            run(
                f"Positive semantic output: {output.parent.name}"
                f"{' (legacy contract)' if legacy else ''}",
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    str(TEST_DIR / "evaluate_output.py"),
                    str(output),
                    "--expectations",
                    str(EXPECTATIONS),
                    *legacy,
                ],
            )
        )
    results.append(
        run(
            "Coefficient-tier regression (vQS-1.5)",
            [
                sys.executable,
                "-X",
                "utf8",
                str(TEST_DIR / "evaluate_output.py"),
                str(VQS15_OUTPUT),
            ],
        )
    )
    if GUANQING_OUTPUT.is_file() and GUANQING_EXPECTATIONS.is_file():
        results.append(
        run(
            "Real-case coefficient regression: 示範能源",
            [
                sys.executable,
                "-X",
                "utf8",
                str(TEST_DIR / "evaluate_output.py"),
                str(GUANQING_OUTPUT),
                "--expectations",
                str(GUANQING_EXPECTATIONS),
            ],
        )
    )
    if ANFU_OUTPUT.is_file():
        results.append(
        run(
            "Independent real-case coefficient regression: 示範科技",
            [
                sys.executable,
                "-X",
                "utf8",
                str(TEST_DIR / "evaluate_output.py"),
                str(ANFU_OUTPUT),
            ],
        )
    )
    results.append(
        run(
            "Negative empty-shell rejection",
            [
                sys.executable,
                "-X",
                "utf8",
                str(TEST_DIR / "evaluate_output.py"),
                str(NEGATIVE_OUTPUT),
                "--expectations",
                str(EXPECTATIONS),
            ],
            expect_success=False,
        )
    )
    results.append(step_heading_compatibility())
    results.append(numeric_subheading_compatibility())
    results.append(contract_format_variants())
    results.append(canonical_skeleton_contract())

    docx_dir = TEST_DIR / "run-latest-docx"
    docx_dir.mkdir(parents=True, exist_ok=True)
    docx_path = docx_dir / "星橋邊緣運算_初篩備忘_v1.docx"
    docx_path.unlink(missing_ok=True)
    docx_python = select_docx_python(args.docx_python)
    print(f"[INFO] DOCX renderer Python={docx_python}")
    generation_ok = run(
        "Default DOCX generation",
        [
            str(docx_python),
            "-X",
            "utf8",
            str(SKILL_DIR / "scripts" / "render_memo_docx.py"),
            str(CURRENT_OUTPUT),
            str(docx_path),
        ],
    )
    results.append(generation_ok)
    if generation_ok and docx_path.is_file():
        results.append(docx_smoke(docx_path))
    else:
        print("\n=== DOCX structural smoke ===")
        print("[FAIL] skipped: no fresh DOCX was generated in this run")
        results.append(False)

    plugin_manifest = json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    prompt_ok = all(
        "$" in prompt for prompt in plugin_manifest["interface"]["defaultPrompt"]
    )
    print("\n=== Plugin prompt routing ===")
    print(f"[{'PASS' if prompt_ok else 'FAIL'}] all default prompts name a Skill")
    results.append(prompt_ok)
    results.append(
        run(
            "Neutral style resolution",
            [
                sys.executable,
                "-X",
                "utf8",
                str(PLUGIN_ROOT / "scripts" / "resolve_style.py"),
                "neutral",
                "--compact",
            ],
        )
    )

    if args.include_external:
        external_python = shutil.which("python") or sys.executable
        print(f"[INFO] external validator Python={external_python}")
        external = (
            (
                "OpenAI Skill validator",
                Path.home()
                / ".codex"
                / "skills"
                / ".system"
                / "skill-creator"
                / "scripts"
                / "quick_validate.py",
                SKILL_DIR,
            ),
            (
                "Codex Plugin validator",
                Path.home()
                / ".codex"
                / "skills"
                / ".system"
                / "plugin-creator"
                / "scripts"
                / "validate_plugin.py",
                PLUGIN_ROOT,
            ),
        )
        for label, validator, target in external:
            if validator.is_file():
                print(f"[INFO] {validator} SHA256={sha256(validator)}")
                results.append(
                    run(
                        f"{label} (environment-owned)",
                        [
                            external_python,
                            "-X",
                            "utf8",
                            str(validator),
                            str(target),
                        ],
                    )
                )
            else:
                print(f"[SKIP] {label}: environment-owned validator not installed")

    print(f"\nOVERALL: {'PASS' if all(results) else 'FAIL'}")
    return 0 if all(results) else 1


def main() -> int:
    cleanup_generated_artifacts()
    try:
        return _run()
    finally:
        cleanup_generated_artifacts()


if __name__ == "__main__":
    raise SystemExit(main())
