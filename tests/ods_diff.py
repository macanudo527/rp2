# Copyright 2021 eprbell
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import zipfile
from argparse import ArgumentParser, Namespace
from difflib import unified_diff
from itertools import zip_longest
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, List, NamedTuple, Optional
from xml.etree import ElementTree

import ezodf

from rp2.rp2_decimal import CRYPTO_DECIMALS

_PURGE_HYPERLIKS = True
# A hyperlink to a row of a sheet, as the reports write it: =HYPERLINK("#B1 In-Out.a4:z4"; "1") or =HYPERLINK("#B1 In-Out.a4:z4"; 0.5).
_ROW_HYPERLINK = re.compile(r'^=HYPERLINK\("#(?P<sheet>[^"]+)\.a(?P<row>\d+):z(?P=row)"; *(?P<text>.*)\)$')


# A cell of a report: its text and, if it's a hyperlink to a row of a sheet, that sheet and row (1-based, as in the formula).
class ReportCell(NamedTuple):
    text: str
    link_sheet: Optional[str] = None
    link_row: Optional[int] = None


def _row_as_string(row: Any) -> str:
    values: List[str] = []
    cell: Any
    for cell in row:
        value: Any = str(_parse_cell_value(cell))
        values.append(value)

    # Remove trailing whitespace from row
    i: int
    for i in range(len(values) - 1, -1, -1):
        if not values[i]:
            del values[i]
        else:
            break

    return ",".join(values)


def _parse_cell_value(cell: Any) -> Any:
    value: Any
    if cell.formula:
        value = cell.formula
        if _PURGE_HYPERLIKS and value.startswith("=HYPERLINK"):
            value = value.split(";")[1].lstrip(' "').rstrip('")')
    elif cell.value or cell.value == 0:
        value = cell.value
    else:
        value = ""
    try:
        value = round(float(value), CRYPTO_DECIMALS)
        if value == -0.0:
            value = 0
    except ValueError:
        pass

    if value is None:
        value = ""

    return value


# The non-empty rows of a sheet, as lists of cell values converted to strings (numbers rounded like ods_diff() does, hyperlinks replaced by
# their text). Returns None if the file has no sheet with that name. Used by tests that check specific report cells.
def read_sheet_rows(file_path: Path, sheet_name: str) -> Optional[List[List[str]]]:
    document: Any = ezodf.opendoc(str(file_path))
    if sheet_name not in document.sheets.names():
        return None
    result: List[List[str]] = []
    for row in document.sheets[sheet_name].rows():
        values = [str(_parse_cell_value(cell)) for cell in row]
        while values and not values[-1]:
            values.pop()
        if values:
            result.append(values)
    return result


# All the rows of a sheet (row i of the list is row i + 1 of the sheet, as in the reports' hyperlinks), as ReportCells: unlike
# read_sheet_rows(), it keeps the target of each hyperlink. Returns None if the file has no sheet with that name. Example: the cell
# =HYPERLINK("#B1 In-Out.a4:z4"; "1") is ReportCell("1", "B1 In-Out", 4).
def read_sheet_cells(file_path: Path, sheet_name: str) -> Optional[List[List[ReportCell]]]:
    document: Any = ezodf.opendoc(str(file_path))
    if sheet_name not in document.sheets.names():
        return None
    result: List[List[ReportCell]] = []
    for row in document.sheets[sheet_name].rows():
        cells: List[ReportCell] = []
        for cell in row:
            match = _ROW_HYPERLINK.match(cell.formula) if cell.formula else None
            if match:
                cells.append(ReportCell(match.group("text").strip('"'), match.group("sheet"), int(match.group("row"))))
            else:
                cells.append(ReportCell(str(_parse_cell_value(cell))))
        result.append(cells)
    return result


_TABLE_NAMESPACE: str = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"


# Why a formula isn't well formed, or None if it is: every parenthesis must be opened before it is closed and closed before the formula ends,
# and every quote must be closed. Text in double quotes (a string, where "" is a quote in the string) and in single quotes (a sheet name,
# where '' is a quote in the name) is skipped, because its parentheses are only text. Only the structure is checked: a well-formed formula
# can still compute a wrong value. Examples: =IF(A1="(";1;2) is well formed; =IF(A1="(";1;2 has "1 unclosed parenthesis";
# =SUM(A1:A2)) has "a ) without its (".
def get_formula_problem(formula: str) -> Optional[str]:
    depth: int = 0
    index: int = 0
    while index < len(formula):
        character: str = formula[index]
        if character in "\"'":
            end: int = formula.find(character, index + 1)
            # A doubled quote is a quote in the text: the text continues after it.
            while end != -1 and formula[end + 1 : end + 2] == character:
                end = formula.find(character, end + 2)
            if end == -1:
                return f"unclosed {character}"
            index = end + 1
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return "a ) without its ("
        index += 1
    if depth > 0:
        return f"{depth} unclosed parenthes{'is' if depth == 1 else 'es'}"
    return None


# The name of a column from its index (0-based): 0 is A, 25 is Z, 26 is AA.
def _get_column_name(column_index: int) -> str:
    name: str = ""
    column_number: int = column_index + 1
    while column_number > 0:
        column_number, remainder = divmod(column_number - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


# The formulas of an ODS file that aren't well formed (see get_formula_problem()), as "<sheet>.<cell>: <problem>: <formula>". Example:
# "Asset.G4: 1 unclosed parenthesis: =IF(...". The formulas are read from the XML of the file (content.xml), not with ezodf, so that the
# check doesn't depend on the library that writes the reports and that ods_diff() uses to compare them with golden files.
def get_malformed_formulas(file_path: Path) -> List[str]:
    with zipfile.ZipFile(file_path) as ods_file:
        content: ElementTree.Element = ElementTree.fromstring(ods_file.read("content.xml"))
    result: List[str] = []
    for table in content.iter(f"{{{_TABLE_NAMESPACE}}}table"):
        row_number: int = 1
        for row in table.iter(f"{{{_TABLE_NAMESPACE}}}table-row"):
            column_index: int = 0
            # Merged cells (covered-table-cell) are columns too.
            for cell in row:
                formula: Optional[str] = cell.get(f"{{{_TABLE_NAMESPACE}}}formula")
                problem: Optional[str] = get_formula_problem(formula) if formula is not None else None
                if problem is not None:
                    result.append(f"{table.get(f'{{{_TABLE_NAMESPACE}}}name')}.{_get_column_name(column_index)}{row_number}: {problem}: {formula}")
                column_index += int(cell.get(f"{{{_TABLE_NAMESPACE}}}number-columns-repeated", "1"))
            row_number += int(row.get(f"{{{_TABLE_NAMESPACE}}}number-rows-repeated", "1"))
    return result


def ods_diff(file1_path: Path, file2_path: Path, generate_ascii_representation: bool) -> str:  # pylint: disable=too-many-branches
    if not file1_path.exists():
        return f"Error: {file1_path} does not exist"
    if not file2_path.exists():
        return f"Error: {file2_path} does not exist"

    file1: Any = ezodf.opendoc(str(file1_path))
    file2: Any = ezodf.opendoc(str(file2_path))
    sheet1: Any
    sheet2: Any

    contents1: List[str] = []
    contents2: List[str] = []
    row_count1: int = 0
    row_count2: int = 0
    for sheet1 in file1.sheets:
        if sheet1.name not in file2.sheets.names():
            contents2.append(f"{sheet1.name}: sheet not found in '{file2_path}'")
            continue
        sheet2 = file2.sheets[sheet1.name]
        contents1.append(sheet1.name)
        contents2.append(sheet1.name)

        row1: Any = None
        row2: Any = None
        for _, (row1, row2) in enumerate(zip_longest(sheet1.rows(), sheet2.rows())):
            string_row: str
            if row1:
                string_row = _row_as_string(row1)
                if string_row:
                    contents1.append(string_row)
                    row_count1 += 1
            if row2:
                string_row = _row_as_string(row2)
                if string_row:
                    contents2.append(string_row)
                    row_count2 += 1

    if row_count1 <= 0 or row_count2 <= 0:
        return f"Error: {file1_path} has no data in common with {file2_path}"

    for sheet2 in file2.sheets:
        if sheet2.name not in file1.sheets.names():
            contents1.append(f"{sheet2.name}: sheet not found in '{file1_path}'")

    if generate_ascii_representation:
        for file_path, contents in zip([file1_path, file2_path], [contents1, contents2]):
            with NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as temp_file:
                temp_file.write("\n".join(contents))
                temp_file.flush()
                print(f"ASCII representation of {file_path}: {temp_file.name}")

    return "\n".join(unified_diff(contents1, contents2, lineterm=""))


def main() -> None:
    parser: ArgumentParser = ArgumentParser(description="Generate yearly capital gain/loss report and account balances for crypto holdings.")
    parser.add_argument(
        "-a",
        "--ascii-representation",
        action="store_true",
        help="Save ASCII representation of ODS files in temporary directory",
    )
    parser.add_argument(
        "ods_file1",
        action="store",
        help="First ODS file",
        metavar="ODS_FILE1",
        type=str,
    )
    parser.add_argument(
        "ods_file2",
        action="store",
        help="Second ODS file",
        metavar="ODS_FILE2",
        type=str,
    )

    args: Namespace = parser.parse_args()
    print(ods_diff(Path(args.ods_file1), Path(args.ods_file2), generate_ascii_representation=args.ascii_representation))


if __name__ == "__main__":
    main()
