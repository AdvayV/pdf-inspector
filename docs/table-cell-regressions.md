# PDF table cell regression checks

An extractor can preserve every word and still move a value to the wrong
column. Use `scripts/check_table_cells.py` to check exact cell positions for a
small, known PDF or a captured Markdown output. Run the same expectation
against a baseline and a candidate build when reviewing a parser change.

## Run the included example

The inventory fixture is a fictional, one-page PDF with a ruled table and two
deliberately empty cells. It needs no external data or OCR. To check the PDF,
build the existing extractor and give the checker its path:

```sh
cargo build --release --bin pdf2md
python scripts/check_table_cells.py scripts/tests/fixtures/table_cells/expected.json --pdf scripts/tests/fixtures/table_cells/inventory.pdf --pdf2md target/release/pdf2md
```

On Windows, use `target/release/pdf2md.exe` as the extractor path. If
`pdf2md` is on your PATH, you can omit `--pdf2md`.

You can also run the example with only Python 3.9 or newer. The first command
checks the captured good output. The second shows what happens when the
value `24` shifts from **Remaining** to **Used**:

```sh
python scripts/check_table_cells.py scripts/tests/fixtures/table_cells/expected.json --markdown scripts/tests/fixtures/table_cells/correct.md
python scripts/check_table_cells.py scripts/tests/fixtures/table_cells/expected.json --markdown scripts/tests/fixtures/table_cells/shifted.md --json
```

The first command matches all 12 cells. The second matches 10 and reports
differences at table 1, row 2, columns 3 and 4. An exit code of `0` means all
cells match, `1` means the output differs, and `2` means the input or
extraction failed. Use `--json` to pass a report to a script or CI job.

## Write an expectation

Create a JSON object with a `tables` array, in document order. Each table is
a rectangular array of rows, each with string cells. Include its header as
row 1 and represent a blank with `""`. Enter the expected contents from the
source document so the current extractor cannot silently set the expectation.

The checker reads compact pipe tables from `pdf2md` Markdown. It ignores
padding around cells and keeps internal spacing, case and punctuation.
Each different, missing or extra cell fails the check. The JSON report uses
`null` for a missing position and `""` for a present blank. Tables and rows
are compared in order. The checker treats pipes as delimiters, so use
fixtures without literal pipe characters inside cells.

Run the tool's offline unit tests with:

```sh
python -m unittest discover -s scripts/tests -p test_check_table_cells.py
```
