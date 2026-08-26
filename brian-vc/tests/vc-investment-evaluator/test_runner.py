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

    def _advance_to(self, case, upto) -> None:
        """Drive the manifest far enough that `upto`'s dependencies are met."""
        evidence = case / "ev.json"
        if not evidence.exists():
            evidence.write_text("{}", encoding="utf-8")
        chain = ["A1", "A2", "B1", "B3", "C1", "C2", "C3", "C4", "D1", "D2", "E1"]
        # Modules that owe a key fact at completion must supply it here too.
        key_facts = {"D1": "peer_list_source=auto"}
        for module_id in chain[: chain.index(upto)] if upto in chain else chain:
            if module_id == "B3":
                # B3 <- B1, B2?  -- the optional upstream still has to resolve.
                self.run_runner(
                    "set", str(case), "B2", "not_applicable",
                    "--reason", "no prospectus in this fixture",
                    "--evidence", "DocumentIndex 無命中",
                )
            self.run_runner(
                "set", str(case), module_id, "complete",
                "--evidence", key_facts.get(module_id, "ok"),
                "--artifact", str(evidence),
            )

    def test_d1_cannot_complete_without_declaring_the_peer_list_source(self) -> None:
        """The rule binds when D1 claims completion, not at workbook assembly.

        Enforcing it only in prepare_workbook_input let a case run all the way
        to Stage F before anyone noticed D1 never said where its comparables
        came from.
        """
        with case_workspace() as raw:
            case = raw / "case"
            self.run_runner("init", str(case), "--case-id", "20260826_TEST")
            self._advance_to(case, "D2")
            evidence = case / "ev.json"

            refused = self.run_runner(
                "set", str(case), "D1", "complete",
                "--evidence", "查驗完成", "--artifact", str(evidence), expected=2,
            )
            self.assertIn("peer_list_source", refused.stderr)

            bogus = self.run_runner(
                "set", str(case), "D1", "complete",
                "--evidence", "peer_list_source=guessed",
                "--artifact", str(evidence), expected=2,
            )
            self.assertIn("not acceptable", bogus.stderr)

            for accepted in ("user_specified", "auto"):
                self.run_runner(
                    "set", str(case), "D1", "complete",
                    "--evidence", f"peer_list_source={accepted}",
                    "--artifact", str(evidence),
                )
            status = json.loads(self.run_runner("status", str(case), "--json").stdout)
            self.assertEqual(status["modules"]["D1"]["status"], "complete")

    def test_e2_cannot_complete_without_the_handoff_sentence(self) -> None:
        with case_workspace() as raw:
            case = raw / "case"
            self.run_runner("init", str(case), "--case-id", "20260826_TEST")
            self._advance_to(case, "E1")
            evidence = case / "ev.json"
            self.run_runner(
                "set", str(case), "E1", "complete",
                "--evidence", "ok", "--artifact", str(evidence),
            )

            refused = self.run_runner(
                "set", str(case), "E2", "complete",
                "--evidence", "R1-R6 齊全", "--artifact", str(evidence), expected=2,
            )
            self.assertIn("redteam_handoff", refused.stderr)

            off_template = self.run_runner(
                "set", str(case), "E2", "complete",
                "--evidence", "redteam_handoff=RedTeam 有意見",
                "--artifact", str(evidence), expected=2,
            )
            self.assertIn("not acceptable", off_template.stderr)

            self.run_runner(
                "set", str(case), "E2", "complete",
                "--evidence",
                "redteam_handoff=RedTeam 提出 5 個反對理由，主要風險點為 A、B、C，"
                "GP 決策框架已留白供填入。",
                "--artifact", str(evidence),
            )
            status = json.loads(self.run_runner("status", str(case), "--json").stdout)
            self.assertEqual(status["modules"]["E2"]["status"], "complete")

    def test_modules_without_a_declared_key_fact_are_unaffected(self) -> None:
        with case_workspace() as raw:
            case = raw / "case"
            self.run_runner("init", str(case), "--case-id", "20260826_TEST")
            evidence = case / "ev.json"
            evidence.write_text("{}", encoding="utf-8")
            self.run_runner(
                "set", str(case), "A1", "complete",
                "--evidence", "preflight ok", "--artifact", str(evidence),
            )
            status = json.loads(self.run_runner("status", str(case), "--json").stdout)
            self.assertEqual(status["modules"]["A1"]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
