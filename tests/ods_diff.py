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
from typing import Any, Dict, List, NamedTuple, Optional
from xml.etree import ElementTree

import ezodf

from rp2.rp2_decimal import CRYPTO_DECIMALS

_PURGE_HYPERLIKS = True
# Marks the formula cells in the text that ods_diff() compares (see _row_as_string()).
_FORMULA_MARKER = "ƒ"
# A hyperlink to a row of a sheet, as the reports write it (see get_row_hyperlink() in abstract_ods_generator.py): =HYPERLINK("#B1 In-Out.a4:z4";
# "1"), =HYPERLINK("#B1 In-Out.a4:z4"; 0.5) or, with a quoted sheet name and a quote in the text, =HYPERLINK("#'B.1 In-Out'.a4:z4"; "a""b").
_ROW_HYPERLINK = re.compile(r'^=HYPERLINK\("(?P<target>(?:[^"]|"")*)"; *(?P<text>"(?:[^"]|"")*"|[^";]*)\)$')
_ROW_LINK_TARGET = re.compile(r"^#(?P<sheet>'(?:[^']|'')*'|[^']*?)\.a(?P<row>\d+):z(?P=row)$")


# A cell of a report: its text and, if it's a hyperlink to a row of a sheet, that sheet and row (1-based, as in the formula).
class ReportCell(NamedTuple):
    text: str
    link_sheet: Optional[str] = None
    link_row: Optional[int] = None


# A hyperlink to a row of a sheet: the sheet, the row (1-based, as in the formula) and the text that it shows (without the quotes of the formula).
class RowHyperlink(NamedTuple):
    sheet: str
    row: int
    text: str


# A hyperlink to a row of a sheet (see _ROW_HYPERLINK), or None if the formula isn't one. Example: =HYPERLINK("#'B.1 In-Out'.a4:z4";
# "buy""id;1") is RowHyperlink("B.1 In-Out", 4, 'buy"id;1').
def parse_row_hyperlink(formula: str) -> Optional[RowHyperlink]:
    match: Optional[re.Match[str]] = _ROW_HYPERLINK.match(formula)
    if match is None:
        return None
    target: Optional[re.Match[str]] = _ROW_LINK_TARGET.match(match.group("target").replace('""', '"'))
    if target is None:
        return None
    sheet: str = target.group("sheet")
    if sheet.startswith("'"):
        sheet = sheet[1:-1].replace("''", "'")
    text: str = match.group("text")
    if text.startswith('"'):
        text = text[1:-1].replace('""', '"')
    return RowHyperlink(sheet, int(target.group("row")), text)


# The sheets that a formula refers to by quoted names (see get_sheet_reference() in abstract_ods_generator.py), without the quotes. Example:
# ='B1_2024'.G33+'B''2_2024'.G33 refers to B1_2024 and B'2_2024.
def get_quoted_sheet_references(formula: str) -> List[str]:
    return [reference.replace("''", "'") for reference in re.findall(r"'((?:[^']|'')*)'\.", formula)]


# The name that ezodf gives a sheet (the tests compare it with get_sheet_name() in abstract_ods_generator.py).
def get_ezodf_sheet_name(name: str) -> str:
    sheet: Any = ezodf.Table(name)
    return str(sheet.name)


def _row_as_string(row: Any) -> str:
    values: List[str] = []
    cell: Any
    for cell in row:
        # A formula cell starts with the marker, so a formula that becomes text, or text that becomes a formula (e.g. a note "=1+1" from the
        # input), is a difference even when the text is the same.
        value: Any = f"{_FORMULA_MARKER if cell.formula else ''}{_parse_cell_value(cell)}"
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
            link: Optional[RowHyperlink] = parse_row_hyperlink(value)
            value = link.text if link else value.split(";")[1].lstrip(' "').rstrip('")')
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
            link: Optional[RowHyperlink] = parse_row_hyperlink(cell.formula) if cell.formula else None
            if link:
                cells.append(ReportCell(link.text, link.sheet, link.row))
            else:
                cells.append(ReportCell(str(_parse_cell_value(cell))))
        result.append(cells)
    return result


_TABLE_NAMESPACE: str = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_TEXT_NAMESPACE: str = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"


# A cell of an ODS file, as its XML (content.xml) has it: sheet, address (e.g. G4), formula (None if the cell isn't a formula) and text.
class ODSCell(NamedTuple):
    sheet: str
    address: str
    formula: Optional[str]
    text: str


# The text of an element of a cell: text:s is one or more spaces (text:c of them), text:tab a tab, text:line-break a new line.
def _get_xml_text(element: ElementTree.Element) -> str:
    parts: List[str] = [element.text or ""]
    for child in element:
        if child.tag == f"{{{_TEXT_NAMESPACE}}}s":
            parts.append(" " * int(child.get(f"{{{_TEXT_NAMESPACE}}}c", "1")))
        elif child.tag == f"{{{_TEXT_NAMESPACE}}}tab":
            parts.append("\t")
        elif child.tag == f"{{{_TEXT_NAMESPACE}}}line-break":
            parts.append("\n")
        else:
            parts.append(_get_xml_text(child))
        parts.append(child.tail or "")
    return "".join(parts)


# Every cell of an ODS file that has a formula or text, read from the XML of the file (not with ezodf, which writes the reports). The text of
# a cell is its paragraphs, one per line. Example: a note "=1+1" written as text is ODSCell("B1 In-Out", "P4", None, "=1+1"), the same note
# written as a formula is ODSCell("B1 In-Out", "P4", "=1+1", "").
def read_cells(file_path: Path) -> List[ODSCell]:
    with zipfile.ZipFile(file_path) as ods_file:
        content: ElementTree.Element = ElementTree.fromstring(ods_file.read("content.xml"))
    result: List[ODSCell] = []
    for table in content.iter(f"{{{_TABLE_NAMESPACE}}}table"):
        sheet: str = table.get(f"{{{_TABLE_NAMESPACE}}}name", "")
        row_number: int = 1
        for row in table.iter(f"{{{_TABLE_NAMESPACE}}}table-row"):
            column_index: int = 0
            for cell in row:
                formula: Optional[str] = cell.get(f"{{{_TABLE_NAMESPACE}}}formula")
                text: str = "\n".join(_get_xml_text(paragraph) for paragraph in cell.iter(f"{{{_TEXT_NAMESPACE}}}p"))
                if formula is not None or text:
                    result.append(ODSCell(sheet, f"{_get_column_name(column_index)}{row_number}", formula, text))
                column_index += int(cell.get(f"{{{_TABLE_NAMESPACE}}}number-columns-repeated", "1"))
            row_number += int(row.get(f"{{{_TABLE_NAMESPACE}}}number-rows-repeated", "1"))
    return result


# Writes an RP2 input file: one sheet for each asset, with the given rows (an empty string leaves the cell empty). A sheet keeps its name
# as it is, also with quotes (e.g. B'1"x): ezodf would replace them with spaces, but LibreOffice, where users write their input, allows them.
def write_ods_input(file_path: Path, asset_2_rows: Dict[str, List[List[Any]]]) -> None:
    document: Any = ezodf.newdoc("ods", str(file_path), template=None)
    for asset, rows in asset_2_rows.items():
        sheet: Any = ezodf.Table("asset")
        document.sheets += sheet
        sheet.reset(size=(len(rows), max(len(row) for row in rows)))
        # After reset(), which sets the name again through ezodf's setter.
        sheet.set_attr(f"{{{_TABLE_NAMESPACE}}}name", asset)
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                if value != "":
                    sheet[row_index, column_index].set_value(value)
    document.save()


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
