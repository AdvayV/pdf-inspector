import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_table_cells import compare_tables, main, markdown_tables

FIXTURES = Path(__file__).parent / "fixtures" / "table_cells"


def run_check(*arguments):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main([str(arg) for arg in arguments])
    return code, stdout.getvalue(), stderr.getvalue()


class TableCellTests(unittest.TestCase):
    def test_exact_fixture_passes(self):
        code, stdout, stderr = run_check(
            FIXTURES / "expected.json", "--markdown", FIXTURES / "correct.md"
        )
        self.assertEqual(code, 0)
        self.assertIn("12/12 expected cells", stdout)
        self.assertEqual(stderr, "")

    def test_shifted_values_report_coordinates_and_preserve_empty_cells(self):
        code, stdout, stderr = run_check(
            FIXTURES / "expected.json", "--markdown", FIXTURES / "shifted.md", "--json"
        )
        report = json.loads(stdout)
        self.assertEqual(code, 1)
        self.assertEqual(stderr, "")
        self.assertFalse(report["passed"])
        self.assertEqual(report["matched_cells"], 10)
        self.assertEqual(
            report["differences"],
            [
                {
                    "table": 1,
                    "row": 2,
                    "column": 3,
                    "kind": "changed",
                    "expected": "",
                    "actual": "24",
                },
                {
                    "table": 1,
                    "row": 2,
                    "column": 4,
                    "kind": "changed",
                    "expected": "24",
                    "actual": "",
                },
            ],
        )

    def test_missing_cell_differs_from_present_empty_cell(self):
        actual = markdown_tables("|A|B|\n|---|---|\n|one|\n")
        report = compare_tables([[["A", "B"], ["one", ""]]], actual)
        self.assertEqual(report["differences"][0]["kind"], "missing")
        self.assertEqual(report["differences"][0]["expected"], "")
        self.assertIsNone(report["differences"][0]["actual"])

    def test_extra_cells_fail_even_if_all_expected_cells_match(self):
        actual = markdown_tables("|A|\n|---|\n|one|two|\n")
        report = compare_tables([[["A"], ["one"]]], actual)
        self.assertEqual(report["matched_cells"], report["expected_cells"])
        self.assertFalse(report["passed"])
        self.assertEqual(report["differences"][0]["kind"], "extra")

    def test_ignores_fences_and_reads_multiple_tables_in_order(self):
        text = (
            "~~~md\n|ignored|\n|---|\n~~~\n"
            "Notes about the inventory.\n"
            "| A | B |\n| :--- | ---: |\n| two  spaces | |\n"
            "|C|\n|---|\n|value|\n"
        )
        self.assertEqual(
            markdown_tables(text),
            [[["A", "B"], ["two  spaces", ""]], [["C"], ["value"]]],
        )

    def test_wrong_golden_schema_is_an_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            expected = Path(directory) / "golden.json"
            expected.write_text('{"tables": [[["A", "B"], ["one"]]]}', encoding="utf-8")
            code, stdout, stderr = run_check(
                expected, "--markdown", FIXTURES / "correct.md"
            )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("must be rectangular", stderr)

    def test_pdf_mode_uses_pdf2md_and_removes_temporary_output(self):
        temporary = []

        def render(command, **kwargs):
            self.assertEqual(command[:2], ["test-pdf2md", str(Path("fixture.pdf").resolve())])
            self.assertTrue(kwargs["capture_output"])
            output = Path(command[2])
            output.write_bytes((FIXTURES / "correct.md").read_bytes())
            temporary.append(output)
            return CompletedProcess(command, 0)

        with patch("check_table_cells.subprocess.run", side_effect=render):
            code, stdout, stderr = run_check(
                FIXTURES / "expected.json", "--pdf", "fixture.pdf", "--pdf2md", "test-pdf2md"
            )
        self.assertEqual(code, 0)
        self.assertIn("12/12 expected cells", stdout)
        self.assertEqual(stderr, "")
        self.assertFalse(temporary[0].exists())

    def test_extractor_error_returns_two(self):
        result = CompletedProcess([], 7, stderr=b"PDF read error")
        with patch("check_table_cells.subprocess.run", return_value=result):
            code, stdout, stderr = run_check(
                FIXTURES / "expected.json", "--pdf", "fixture.pdf"
            )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("status 7: PDF read error", stderr)


if __name__ == "__main__":
    unittest.main()
