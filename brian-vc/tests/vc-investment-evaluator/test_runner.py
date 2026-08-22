from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


PLUGIN = Path(__file__).resolve().parents[2]
RUNNER = PLUGIN / "skills" / "vc-investment-evaluator" / "scripts" / "evaluator_runner.py"
TEST_ROOT = Path(__file__).resolve().parent
RUNTIME_ROOT = TEST_ROOT / ".runner-test-runtime"


@contextmanager
def case_workspace() -> Iterator[Path]:
    root = RUNTIME_ROOT / uuid.uuid4().hex
    root.mkdir(parents=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


class EvaluatorRunnerTests(unittest.TestCase):
    def run_runner(self, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(RUNNER), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, expected, result.stderr or result.stdout)
        return result

    def test_init_uses_canonical_19_module_contract(self) -> None:
        with case_workspace() as raw:
            case = raw / "case"
            result = self.run_runner(
                "init", str(case), "--case-id", "20260815_TEST", "--json"
            )
            report = json.loads(result.stdout)
            self.assertEqual(len(report["modules"]), 19)
            self.assertTrue(
                all(item["status"] == "pending" for item in report["modules"].values())
            )
            manifest = json.loads(
                (case / ".vc-evaluator" / "artifact-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["modules"]["C4"]["dependencies"], ["C3"])
            self.assertEqual(
                manifest["modules"]["F1"]["dependencies"],
                ["B_GATE", "C_GATE", "D_GATE", "E_GATE"],
            )

    def test_dependency_gate_and_artifact_hash(self) -> None:
        with case_workspace() as raw:
            case = raw / "case"
            self.run_runner("init", str(case), "--case-id", "20260815_TEST")
            evidence = case / "A1_capability-log.json"
            evidence.write_text('{"mode":"full"}\n', encoding="utf-8")
            self.run_runner(
                "set",
                str(case),
                "A2",
                "complete",
                "--evidence",
                "data gate",
                "--artifact",
                str(evidence),
                expected=2,
            )
            self.run_runner(
                "set",
                str(case),
                "A1",
                "complete",
                "--evidence",
                "preflight passed",
                "--artifact",
                str(evidence),
            )
            data_gate = case / "A2_data-gate.json"
            data_gate.write_text('{"level":"L2"}\n', encoding="utf-8")
            result = self.run_runner(
                "set",
                str(case),
                "A2",
                "complete",
                "--evidence",
                "L2 inputs present",
                "--artifact",
                str(data_gate),
                "--json",
            )
            report = json.loads(result.stdout)
            self.assertEqual(report["gates"]["A_GATE"], "complete")
            evidence.write_text('{"mode":"changed"}\n', encoding="utf-8")
            verify = self.run_runner("verify", str(case), "--json", expected=1)
            issues = json.loads(verify.stdout)["issues"]
            self.assertTrue(any(item["scope"] == "A1" for item in issues))

    def test_invalidate_stale_resets_downstream(self) -> None:
        with case_workspace() as raw:
            case = raw / "case"
            self.run_runner("init", str(case), "--case-id", "20260815_TEST")
            a1 = case / "a1.json"
            a2 = case / "a2.json"
            a1.write_text("{}\n", encoding="utf-8")
            a2.write_text("{}\n", encoding="utf-8")
            self.run_runner(
                "set", str(case), "A1", "complete", "--evidence", "ok", "--artifact", str(a1)
            )
            self.run_runner(
                "set", str(case), "A2", "complete", "--evidence", "ok", "--artifact", str(a2)
            )
            a1.write_text('{"stale":true}\n', encoding="utf-8")
            self.run_runner("verify", str(case), "--invalidate-stale", expected=1)
            status = json.loads(
                self.run_runner("status", str(case), "--json").stdout
            )
            self.assertEqual(status["modules"]["A1"]["status"], "partial")
            self.assertEqual(status["modules"]["A2"]["status"], "pending")

    def test_two_failures_stop_further_retries(self) -> None:
        with case_workspace() as raw:
            case = raw / "case"
            self.run_runner("init", str(case), "--case-id", "20260822_TEST")
            status = json.loads(self.run_runner("status", str(case), "--json").stdout)
            self.assertEqual(status["modules"]["A1"]["failed_attempts"], 0)
            self.assertFalse(status["modules"]["A1"]["retry_exhausted"])

            self.run_runner(
                "set", str(case), "A1", "partial", "--reason", "tool unavailable"
            )
            status = json.loads(self.run_runner("status", str(case), "--json").stdout)
            self.assertEqual(status["modules"]["A1"]["failed_attempts"], 1)
            self.assertFalse(status["modules"]["A1"]["retry_exhausted"])

            self.run_runner(
                "set", str(case), "A1", "blocked", "--reason", "tool still unavailable"
            )
            status = json.loads(self.run_runner("status", str(case), "--json").stdout)
            self.assertEqual(status["modules"]["A1"]["failed_attempts"], 2)
            self.assertTrue(status["modules"]["A1"]["retry_exhausted"])

            third = self.run_runner(
                "set", str(case), "A1", "partial", "--reason", "third try", expected=2
            )
            self.assertIn("retry limit reached", third.stderr)

            verify = self.run_runner("verify", str(case), "--json", expected=1)
            issues = json.loads(verify.stdout)["issues"]
            self.assertTrue(
                any(
                    item["scope"] == "A1" and "retry limit reached" in item["detail"]
                    for item in issues
                )
            )

    def test_retry_counter_resets_on_success_and_manual_reset(self) -> None:
        with case_workspace() as raw:
            case = raw / "case"
            self.run_runner("init", str(case), "--case-id", "20260822_TEST")
            self.run_runner(
                "set", str(case), "A1", "partial", "--reason", "first failure"
            )
            evidence = case / "a1.json"
            evidence.write_text("{}\n", encoding="utf-8")
            self.run_runner(
                "set", str(case), "A1", "complete", "--evidence", "ok", "--artifact", str(evidence)
            )
            status = json.loads(self.run_runner("status", str(case), "--json").stdout)
            self.assertEqual(status["modules"]["A1"]["failed_attempts"], 0)

            self.run_runner("set", str(case), "A2", "partial", "--reason", "fail 1")
            self.run_runner("set", str(case), "A2", "partial", "--reason", "fail 2")
            self.run_runner(
                "set", str(case), "A2", "partial", "--reason", "fail 3", expected=2
            )
            self.run_runner("set", str(case), "A2", "pending")
            status = json.loads(self.run_runner("status", str(case), "--json").stdout)
            self.assertEqual(status["modules"]["A2"]["failed_attempts"], 0)
            self.assertFalse(status["modules"]["A2"]["retry_exhausted"])
            self.run_runner("set", str(case), "A2", "partial", "--reason", "fresh run")

    def test_stale_invalidation_does_not_consume_retry_budget(self) -> None:
        with case_workspace() as raw:
            case = raw / "case"
            self.run_runner("init", str(case), "--case-id", "20260822_TEST")
            a1 = case / "a1.json"
            a1.write_text("{}\n", encoding="utf-8")
            self.run_runner(
                "set", str(case), "A1", "complete", "--evidence", "ok", "--artifact", str(a1)
            )
            a1.write_text('{"stale":true}\n', encoding="utf-8")
            self.run_runner("verify", str(case), "--invalidate-stale", expected=1)
            status = json.loads(self.run_runner("status", str(case), "--json").stdout)
            self.assertEqual(status["modules"]["A1"]["status"], "partial")
            self.assertEqual(status["modules"]["A1"]["failed_attempts"], 0)
            self.assertFalse(status["modules"]["A1"]["retry_exhausted"])

    def test_output_is_utf8_regardless_of_caller_locale(self) -> None:
        """Runner output must not depend on the caller's locale codec.

        Reasons are written in Chinese and print_status joins them with an em
        dash. Encoded in a legacy codec these are either unencodable or decode
        as garbage for a UTF-8 caller, and the subprocess reader thread turns
        that into an empty capture beside a zero exit code. Force UTF-8 mode
        off so this stays covered even though CI runs with PYTHONUTF8=1.
        """
        reason = "工具環境不可用，無法確認 agent 能力"
        env = dict(os.environ)
        env["PYTHONUTF8"] = "0"
        env.pop("PYTHONIOENCODING", None)

        def run_legacy(*args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
            result = subprocess.run(
                [sys.executable, str(RUNNER), *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                check=False,
            )
            self.assertEqual(result.returncode, expected, result.stderr or "<undecodable>")
            return result

        with case_workspace() as raw:
            case = raw / "case"
            run_legacy("init", str(case), "--case-id", "20260822_ENC")
            run_legacy("set", str(case), "A1", "partial", "--reason", reason)

            plain = run_legacy("status", str(case))
            self.assertIsNotNone(plain.stdout, "stdout was dropped by a decode error")
            self.assertIn(reason, plain.stdout)

            report = json.loads(run_legacy("status", str(case), "--json").stdout)
            self.assertEqual(report["modules"]["A1"]["reason"], reason)

            run_legacy("set", str(case), "A1", "blocked", "--reason", reason)
            refused = run_legacy(
                "set", str(case), "A1", "partial", "--reason", reason, expected=2
            )
            self.assertIsNotNone(refused.stderr, "stderr was dropped by a decode error")
            self.assertIn("retry limit reached", refused.stderr)


if __name__ == "__main__":
    unittest.main()
