"""Structured test reporting uses invented failures and temporary outputs only."""
from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from plc_workbench import work_check_tests as driver


def case(methods: dict, name: str = "ExampleCases") -> type[unittest.TestCase]:
    return type(name, (unittest.TestCase,), {"__module__": __name__, **methods})


def execute(methods: dict, name: str = "ExampleCases") -> tuple[dict, str]:
    suite = unittest.TestLoader().loadTestsFromTestCase(case(methods, name))
    stream = io.StringIO()
    return driver.run_suite(suite, stream=stream), stream.getvalue()


def fail(test: unittest.TestCase) -> None:
    test.fail("PRIVATE_SENTINEL assertion and /private/path")


class WorkCheckTestsTests(unittest.TestCase):
    def selected_module(self, root: Path, source: str) -> dict[str, tuple[str, ...]]:
        name = "work_machine_selected_fixture"
        directory = root / "python-parser/tests"
        directory.mkdir(parents=True)
        (directory / f"{name}.py").write_text(source, encoding="utf-8")
        self.addCleanup(driver.sys.modules.pop, name, None)
        return {"application": (name,)}

    def test_counts_include_all_unittest_outcomes(self) -> None:
        def error(test: unittest.TestCase) -> None:
            raise RuntimeError("PRIVATE_SENTINEL error")

        def skip(test: unittest.TestCase) -> None:
            test.skipTest("PRIVATE_SENTINEL skip")

        payload, stream = execute({
            "test_success": lambda test: None,
            "test_failure": fail,
            "test_error": error,
            "test_skip": skip,
            "test_expected_failure": unittest.expectedFailure(lambda test: fail(test)),
            "test_unexpected_success": unittest.expectedFailure(lambda test: None),
        })
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["counts"], {
            "tests_run": 6, "failures": 1, "errors": 1, "skipped": 1,
            "expected_failures": 1, "unexpected_successes": 1,
        })
        self.assertEqual(len(payload["failed_test_ids"]), 3)
        self.assertNotIn("PRIVATE_SENTINEL", driver.render_test_result(payload))
        self.assertIn("PRIVATE_SENTINEL", stream)

    def test_skips_and_expected_failures_do_not_fail_suite(self) -> None:
        payload, _ = execute({
            "test_skip": unittest.skip("PRIVATE_SENTINEL")(lambda test: None),
            "test_expected": unittest.expectedFailure(lambda test: fail(test)),
        })
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["counts"]["skipped"], 1)
        self.assertEqual(payload["counts"]["expected_failures"], 1)
        self.assertEqual(payload["failed_test_ids"], [])

    def test_subtest_values_never_enter_shared_result(self) -> None:
        def subtests(test: unittest.TestCase) -> None:
            for index in range(3):
                with test.subTest(value=f"PRIVATE_SENTINEL_{index}"):
                    test.fail("PRIVATE_SENTINEL failure")
            with test.subTest(value="PRIVATE_SENTINEL_error"):
                raise RuntimeError("PRIVATE_SENTINEL exception")
            for index in range(2):
                with test.subTest(value=f"PRIVATE_SENTINEL_skip_{index}"):
                    test.skipTest("PRIVATE_SENTINEL skip reason")

        payload, stream = execute({"test_subtests": subtests})
        self.assertEqual(payload["counts"]["tests_run"], 1)
        self.assertEqual(payload["counts"]["failures"], 3)
        self.assertEqual(payload["counts"]["errors"], 1)
        self.assertEqual(payload["counts"]["skipped"], 2)
        self.assertEqual(payload["failed_test_ids"], [f"{__name__}.ExampleCases.test_subtests"])
        self.assertEqual(payload["failure_ids_omitted"], 0)
        self.assertNotIn("PRIVATE_SENTINEL", driver.render_test_result(payload))
        self.assertIn("PRIVATE_SENTINEL_error", stream)

    def test_custom_id_and_case_description_are_private_only(self) -> None:
        payload, stream = execute({
            "test_failure": fail,
            "id": lambda self: "PRIVATE_SENTINEL",
            "__str__": lambda self: "PRIVATE_SENTINEL",
        })
        self.assertEqual(payload["failed_test_ids"], [f"{__name__}.ExampleCases.test_failure"])
        self.assertNotIn("PRIVATE_SENTINEL", driver.render_test_result(payload))
        self.assertIn("PRIVATE_SENTINEL", stream)

    def test_unrepresentable_case_identity_uses_fixed_fallback(self) -> None:
        for name in ("Case with private spaces", "A" * 170, "Case\N{SNOWMAN}"):
            with self.subTest(name=name):
                payload, _ = execute({"test_failure": fail}, name=name)
                self.assertEqual(payload["failed_test_ids"], ["unittest.loader._FailedTest"])

    def test_import_failure_uses_fixed_fallback_without_filename(self) -> None:
        suite = unittest.TestLoader().loadTestsFromName("PRIVATE_SENTINEL_missing_module")
        payload = driver.run_suite(suite, stream=io.StringIO())
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["counts"]["errors"], 1)
        self.assertEqual(payload["failed_test_ids"], ["unittest.loader._FailedTest"])
        self.assertNotIn("PRIVATE_SENTINEL", driver.render_test_result(payload))

    def test_failure_ids_are_unique_and_bounded(self) -> None:
        payload, _ = execute({f"test_failure_{index:02d}": fail for index in range(24)})
        self.assertEqual(payload["counts"]["failures"], 24)
        self.assertEqual(len(payload["failed_test_ids"]), 20)
        self.assertEqual(payload["failure_ids_omitted"], 4)
        self.assertLess(len(driver.render_test_result(payload).encode()), driver.MAX_RESULT_BYTES)

    def test_unexpected_success_is_a_failure_with_case_id(self) -> None:
        payload, _ = execute({"test_succeeds": unittest.expectedFailure(lambda test: None)})
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["counts"]["unexpected_successes"], 1)
        self.assertEqual(len(payload["failed_test_ids"]), 1)

    def test_validator_rejects_extra_fields_counts_and_malformed_ids(self) -> None:
        original, _ = execute({"test_failure": fail})
        mutations = [
            lambda p: p.update(private_traceback="PRIVATE_SENTINEL"),
            lambda p: p.update(schema_version=True),
            lambda p: p.update(status="PRIVATE_SENTINEL"),
            lambda p: p.update(counts=None),
            lambda p: p["counts"].update(private_count=1),
            lambda p: p.update(failed_test_ids=["case.test(value='PRIVATE_SENTINEL')"]),
            lambda p: p.update(failed_test_ids=["/PRIVATE_SENTINEL/file"]),
            lambda p: p.update(failed_test_ids=["case.\N{SNOWMAN}"]),
            lambda p: p.update(failed_test_ids=["case." + "A" * 160]),
            lambda p: p.update(failed_test_ids=[1]),
            lambda p: p.update(failed_test_ids=p["failed_test_ids"] * 2),
            lambda p: p.update(failed_test_ids=[]),
            lambda p: p.update(failure_ids_omitted=True),
            lambda p: p.update(failure_ids_omitted=1),
            lambda p: p.update(status="passed"),
            lambda p: p["counts"].update(failures=0),
        ]
        for value in (True, -1, 1.2, 1_000_000_001, "PRIVATE_SENTINEL"):
            mutations.append(lambda p, v=value: p["counts"].update(tests_run=v))
        for mutation in mutations:
            payload = deepcopy(original)
            mutation(payload)
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError) as caught:
                    driver.validate_test_result(payload)
                self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))

    def test_passed_results_cannot_hide_failure_ids_or_events(self) -> None:
        original, _ = execute({"test_success": lambda test: None})
        for mutation in (
            lambda p: p["counts"].update(errors=1),
            lambda p: p["counts"].update(unexpected_successes=1),
            lambda p: p.update(failed_test_ids=["module.Case.test_something"]),
        ):
            payload = deepcopy(original)
            mutation(payload)
            with self.assertRaises(ValueError):
                driver.validate_test_result(payload)

    def test_unavailable_states_require_explicit_permission(self) -> None:
        for status in ("not_run", "runner_error"):
            payload = driver.unavailable_result(status)
            with self.assertRaises(ValueError):
                driver.validate_test_result(payload)
            driver.validate_test_result(payload, allow_unavailable=True)
            self.assertEqual(json.loads(driver.render_test_result(payload, allow_unavailable=True)), payload)
            payload["counts"] = {key: 0 for key in driver._COUNT_KEYS}
            with self.assertRaises(ValueError):
                driver.validate_test_result(payload, allow_unavailable=True)
        with self.assertRaises(ValueError):
            driver.unavailable_result("passed")

    def test_publication_is_exclusive_and_leaves_no_pending_file(self) -> None:
        payload, _ = execute({"test_success": lambda test: None})
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            driver._publish_result(output, payload)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), payload)
            with self.assertRaises(ValueError):
                driver._publish_result(output, payload)
            self.assertEqual(list(output.parent.iterdir()), [output])

    def test_publication_race_cannot_overwrite_an_existing_output(self) -> None:
        payload, _ = execute({"test_success": lambda test: None})
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"

            def concurrent_creation(source: Path, destination: Path) -> None:
                destination.write_text("earlier result", encoding="utf-8")
                raise FileExistsError("PRIVATE_SENTINEL")

            with patch.object(driver.os, "link", side_effect=concurrent_creation), self.assertRaises(FileExistsError):
                driver._publish_result(output, payload)
            self.assertEqual(output.read_text(encoding="utf-8"), "earlier result")
            self.assertEqual(list(output.parent.iterdir()), [output])

    def test_work_machine_selection_excludes_process_and_workflow_modules(self) -> None:
        excluded = {
            "test_feedback_listener", "test_revision", "test_work_check", "test_work_check_bootstrap",
            "test_work_check_tests", "test_summary_cli", "test_reference_cli",
        }
        selected = set(driver.WORK_MACHINE_MODULES["application"])
        self.assertFalse(selected & excluded)
        self.assertIn("test_source", selected)
        self.assertIn("test_references", selected)
        self.assertTrue({'test_access', 'test_access_summary', 'test_access_workflow'} <= selected)
        self.assertTrue({'test_tag_data', 'test_tag_data_summary', 'test_tag_evidence_workflow'} <= selected)
        self.assertTrue({'test_pid', 'test_pid_summary', 'test_pid_workflow'} <= selected)
        self.assertTrue({'test_pid_members', 'test_pid_member_summary', 'test_pid_member_workflow'} <= selected)
        self.assertTrue({'test_calculations', 'test_calculation_summary', 'test_calculation_workflow'} <= selected)
        self.assertIn("test_rung_syntax", driver.WORK_MACHINE_MODULES["helpers"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            modules = self.selected_module(root, "import unittest\n"
                "class Selected(unittest.TestCase):\n    def test_parser(self):\n        pass\n")
            directory = root / "python-parser/tests"
            marker = root / "unexpected-import.txt"
            for name in excluded | {"test_future_unreviewed"}:
                (directory / f"{name}.py").write_text(
                    f"from pathlib import Path\nPath({str(marker)!r}).write_text('imported')\n"
                    "raise AssertionError('Excluded module imported')\n", encoding="utf-8")
            package = directory / "test_unreviewed_package"
            package.mkdir()
            (package / "__init__.py").write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('imported package')\n",
                encoding="utf-8")
            with patch.object(driver, "WORK_MACHINE_MODULES", modules), \
                    patch.object(driver.unittest.TestLoader, "discover", side_effect=AssertionError("No discovery")):
                payload = driver.run_suite(driver._load_work_machine_suite(root, "application"), stream=io.StringIO())
            self.assertEqual(payload["status"], "passed")
            self.assertEqual(payload["counts"]["tests_run"], 1)
            self.assertFalse(marker.exists())

    def test_selected_suites_do_not_spawn_processes_or_open_sockets(self) -> None:
        # Developer-only boundary test: catch new process/network fixtures added
        # inside an already allowlisted module as well as new module selection.
        root = driver._checkout_root()
        for name in ("application", "helpers"):
            with self.subTest(suite=name), \
                    patch("subprocess.Popen", side_effect=AssertionError("Parser tests must not launch processes")) as process, \
                    patch("socket.socket", side_effect=AssertionError("Parser tests must not open sockets")) as connection:
                stream = io.StringIO()
                suite = driver._load_work_machine_suite(root, name)
                payload = driver.run_suite(suite, stream=stream)
                self.assertEqual(payload["status"], "passed", stream.getvalue())
                process.assert_not_called()
                connection.assert_not_called()

    def test_selected_module_test_failure_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            modules = self.selected_module(root, "import unittest\n"
                "class Selected(unittest.TestCase):\n    def test_parser(self):\n"
                "        self.fail('PRIVATE_SENTINEL')\n")
            output = root / "result.json"
            with patch.object(driver, "WORK_MACHINE_MODULES", modules), \
                    patch.object(driver, "_checkout_root", return_value=root), \
                    patch.object(driver.sys, "stderr", io.StringIO()):
                self.assertEqual(driver.main(["--suite", "application", "--output", str(output)]), 1)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["counts"]["failures"], 1)
            self.assertNotIn("PRIVATE_SENTINEL", driver.render_test_result(payload))

    def test_selected_module_import_failure_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            modules = self.selected_module(root, "raise ImportError('PRIVATE_SENTINEL')\n")
            with patch.object(driver, "WORK_MACHINE_MODULES", modules):
                suite = driver._load_work_machine_suite(root, "application")
                payload = driver.run_suite(suite, stream=io.StringIO())
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["counts"]["errors"], 1)
            self.assertEqual(payload["failed_test_ids"], ["unittest.loader._FailedTest"])

    def test_empty_selected_module_or_missing_module_cannot_report_success(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            modules = self.selected_module(root, "# No tests in this module.\n")
            output = root / "result.json"
            for selection in (modules, {"application": ("work_machine_missing_fixture",)}, {"application": ()}):
                with self.subTest(selection=selection), patch.object(driver, "WORK_MACHINE_MODULES", selection), \
                        patch.object(driver, "_checkout_root", return_value=root), \
                        patch.object(driver.sys, "stderr", io.StringIO()):
                    self.assertEqual(driver.main(["--suite", "application", "--output", str(output)]), 2)
                self.assertFalse(output.exists())

    def test_main_runs_requested_suite_at_checkout_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            suite = unittest.TestSuite([case({"test_success": lambda test: None})("test_success")])
            with patch.object(driver, "_load_work_machine_suite", return_value=suite) as load:
                with patch.object(driver.sys, "stderr", io.StringIO()):
                    self.assertEqual(driver.main(["--suite", "helpers", "--output", str(output)]), 0)
            load.assert_called_once_with(driver._checkout_root(), "helpers")
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "passed")

    def test_main_records_failed_suite_and_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            suite = unittest.TestSuite([case({"test_failure": fail})("test_failure")])
            with patch.object(driver, "_load_work_machine_suite", return_value=suite):
                with patch.object(driver.sys, "stderr", io.StringIO()):
                    self.assertEqual(driver.main(["--suite", "application", "--output", str(output)]), 1)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "failed")

    def test_main_empty_or_failed_discovery_does_not_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            for discovery in (unittest.TestSuite(), RuntimeError("PRIVATE_SENTINEL")):
                kwargs = {"side_effect": discovery} if isinstance(discovery, Exception) else {"return_value": discovery}
                stream = io.StringIO()
                with patch.object(driver, "_load_work_machine_suite", **kwargs), patch.object(driver.sys, "stderr", stream):
                    self.assertEqual(driver.main(["--suite", "application", "--output", str(output)]), 2)
                self.assertFalse(output.exists())
                self.assertNotIn("PRIVATE_SENTINEL", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
