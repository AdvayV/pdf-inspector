"""Check pdf2md table output against independently specified cell values."""

import argparse
import json
import re
import subprocess
import sys
from itertools import zip_longest
from pathlib import Path
from tempfile import TemporaryDirectory

FENCE = re.compile(r"\s*(\x60{3,}|~{3,})(.*)")
SEPARATOR = re.compile(r":?-{3,}:?")


def markdown_tables(text):
    """Read compact pipe tables, including empty cells and rows of wrong width."""
    rows = []
    fence = None
    for line in text.splitlines():
        marker = FENCE.fullmatch(line)
        if fence is not None:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = None
            rows.append(None)
            continue
        if marker:
            fence = marker[1]
            rows.append(None)
            continue
        line = line.strip()
        if len(line) < 2 or not (line.startswith("|") and line.endswith("|")):
            rows.append(None)
            continue
        rows.append([cell.strip() for cell in line[1:-1].split("|")])

    def header_at(index):
        header = rows[index]
        separator = rows[index + 1] if index + 1 < len(rows) else None
        return (
            header is not None
            and separator is not None
            and len(header) == len(separator)
            and all(SEPARATOR.fullmatch(cell) for cell in separator)
        )

    tables = []
    index = 0
    while index < len(rows):
        if not header_at(index):
            index += 1
            continue
        table = [rows[index]]
        index += 2
        while index < len(rows) and rows[index] is not None and not header_at(index):
            table.append(rows[index])
            index += 1
        tables.append(table)
    return tables


def load_expected(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"tables"}:
        raise ValueError("The expected JSON must contain a single 'tables' property.")
    tables = data["tables"]
    if not isinstance(tables, list):
        raise ValueError("'tables' must be a list of table matrices.")
    for number, table in enumerate(tables, start=1):
        if (
            not isinstance(table, list)
            or not table
            or not isinstance(table[0], list)
            or not table[0]
        ):
            raise ValueError(f"Expected table {number} needs a nonempty header row.")
        width = len(table[0])
        for row in table:
            if (
                not isinstance(row, list)
                or len(row) != width
                or any(not isinstance(cell, str) for cell in row)
            ):
                raise ValueError(f"Expected table {number} must be rectangular with string cells.")
    return tables


def compare_tables(expected, actual):
    """Compare tables, then rows, then cells in document order."""
    matched = 0
    differences = []
    for table_number, (want_table, got_table) in enumerate(
        zip_longest(expected, actual, fillvalue=()), start=1
    ):
        for row_number, (want_row, got_row) in enumerate(
            zip_longest(want_table, got_table, fillvalue=()), start=1
        ):
            for column_number, (want, got) in enumerate(
                zip_longest(want_row, got_row), start=1
            ):
                if want == got:
                    matched += 1
                    continue
                kind = "changed"
                if want is None:
                    kind = "extra"
                elif got is None:
                    kind = "missing"
                differences.append(
                    {
                        "table": table_number,
                        "row": row_number,
                        "column": column_number,
                        "kind": kind,
                        "expected": want,
                        "actual": got,
                    }
                )
    return {
        "passed": not differences,
        "expected_tables": len(expected),
        "actual_tables": len(actual),
        "expected_cells": sum(len(row) for table in expected for row in table),
        "matched_cells": matched,
        "differences": differences,
    }


def extract_markdown(binary, pdf):
    with TemporaryDirectory(prefix="pdf-table-check-") as directory:
        output = Path(directory) / "extracted.md"
        result = subprocess.run(
            [binary, str(pdf.resolve()), str(output)],
            capture_output=True,
            check=False,
        )
        if result.returncode:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise ValueError(f"pdf2md exited with status {result.returncode}: {detail}")
        return output.read_text(encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expected", type=Path, help="JSON with the expected table matrices")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--markdown", type=Path, help="Compare previously extracted Markdown")
    source.add_argument("--pdf", type=Path, help="Extract a local PDF with pdf2md before comparing")
    parser.add_argument("--pdf2md", help="Path to a pdf2md executable (default: pdf2md on PATH)")
    parser.add_argument("--json", action="store_true", help="Write a JSON report to standard output")
    args = parser.parse_args(argv)
    if args.pdf2md and args.pdf is None:
        parser.error("--pdf2md requires --pdf")

    try:
        expected = load_expected(args.expected)
        markdown = (
            args.markdown.read_text(encoding="utf-8")
            if args.markdown
            else extract_markdown(args.pdf2md or "pdf2md", args.pdf)
        )
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    report = compare_tables(expected, markdown_tables(markdown))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(
            f"Match: {report['matched_cells']}/{report['expected_cells']} expected cells. "
            f"Tables: {report['actual_tables']} found, {report['expected_tables']} expected. "
            f"Result: {status}."
        )
        for difference in report["differences"]:
            print(
                f"Table {difference['table']}, row {difference['row']}, "
                f"column {difference['column']} ({difference['kind']}): "
                f"expected {difference['expected']!r}, got {difference['actual']!r}"
            )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
