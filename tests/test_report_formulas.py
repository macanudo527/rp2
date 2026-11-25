# Copyright 2026 eprbell
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

# R25 of the second review of eprbell/rp2#155: the formulas of the reports must be well formed. Since the Open Positions report was added
# (RP2 1.7.2 has it too), its price formulas (Asset G and Asset - Exchange H) had no closing parenthesis for their IF, e.g.
# =IF(VLOOKUP(A4;$Input.A:B;2;0)="Enter asset value";"See Input tab";VLOOKUP(A4;$Input.A:B;2;0). LibreOffice adds the missing parenthesis
# when it opens the file, so the report showed the right values there, but the formula is invalid and other programs don't have to repair it.
# The golden files had the same formulas, so the tests that compare reports with golden files passed: these tests check the formulas.

import os
import shutil
import unittest
from pathlib import Path
from subprocess import run
from typing import Dict, List, Optional

from abstract_test_ods_output_diff import CONFIG_PATH, GOLDEN_PATH, INPUT_PATH
from ods_diff import get_formula_problem, get_malformed_formulas, read_sheet_cells

ROOT_PATH: Path = Path(os.path.dirname(__file__)).parent.absolute()


# The check that the other tests use, on formulas with parentheses and quotes in strings and in sheet names.
class TestFormulaCheck(unittest.TestCase):
    def test_formula_problem(self) -> None:
        cases: Dict[str, Optional[str]] = {
            '=IF(VLOOKUP(A4;$Input.A:B;2;0)="Enter asset value";"See Input tab";VLOOKUP(A4;$Input.A:B;2;0))': None,
            '=IF(VLOOKUP(A4;$Input.A:B;2;0)="Enter asset value";"See Input tab";VLOOKUP(A4;$Input.A:B;2;0)': "1 unclosed parenthesis",
            "=SUM((A1": "2 unclosed parentheses",
            "=SUM(A1:A2))": "a ) without its (",
            "=)(": "a ) without its (",
            '=IF(A1="(";1;2)': None,
            '=IF(A1=")";1;2)': None,
            # "" is a quote in a string and '' is a quote in a sheet name.
            '=IF(A1="a""(""b";1;2)': None,
            "=SUM($'Bob''s (wallet'.A1:A2)": None,
            '=HYPERLINK("#B1 In-Out.a4:z4"; "1")': None,
            '=SUMIF(B$4:B$9;"Bob";E$4:E$9)': None,
            '=IF(A1="abc;1;2)': 'unclosed "',
            "=SUM($'Asset.A1:A2)": "unclosed '",
            '=IF(A1="a"";1;2)': 'unclosed "',
            "=1+1": None,
        }
        for formula, want in cases.items():
            with self.subTest(formula=formula):
                self.assertEqual(get_formula_problem(formula), want)


# Every formula of every golden report is well formed. Before the fix, the 8 golden files of the Open Positions report had 92 malformed price
# formulas, and all the other formulas (about 67,700) were well formed.
class TestGoldenReportFormulas(unittest.TestCase):
    def test_golden_report_formulas_are_well_formed(self) -> None:
        golden_paths: List[Path] = sorted(GOLDEN_PATH.rglob("*.ods"))
        self.assertTrue(golden_paths)
        for golden_path in golden_paths:
            with self.subTest(golden_file=str(golden_path.relative_to(GOLDEN_PATH))):
                no_problems: List[str] = []
                self.assertEqual(get_malformed_formulas(golden_path), no_problems)


# The price formula of each row of the Asset and Asset - Exchange sheets of new Open Positions reports: a universal one (test_data, with 2
# holders, so with a total row for each holder) and a per-wallet one (test_data_per_wallet). Row n shows the price that the user enters for
# the asset of the row (An) in the Input sheet, or "See Input tab" while the Input sheet has the placeholder "Enter asset value".
class TestOpenPositionsPriceFormulas(unittest.TestCase):
    output_dir: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.output_dir = ROOT_PATH / Path("output") / Path(cls.__module__)
        shutil.rmtree(cls.output_dir, ignore_errors=True)
        cls.output_dir.mkdir(parents=True)
        for prefix, dataset, extra_arguments in (("universal_", "test_data", ["-m", "fifo", "-n"]), ("per_wallet_", "test_data_per_wallet", [])):
            run(
                [
                    "rp2_us",
                    *extra_arguments,
                    "-o",
                    str(cls.output_dir),
                    "-p",
                    prefix,
                    str(CONFIG_PATH / Path(f"{dataset}.ini")),
                    str(INPUT_PATH / Path(f"{dataset}.ods")),
                ],
                check=True,
            )

    def test_price_formulas(self) -> None:
        for report_name in ("universal_fifo_open_positions.ods", "per_wallet_mixed_open_positions.ods"):
            report_path: Path = self.output_dir / Path(report_name)
            # The Input sheet: a title, 2 header rows, then each asset with the placeholder of its price.
            input_prices: Dict[str, str] = {row[0].text: row[1].text for row in (read_sheet_cells(report_path, "Input") or [])[3:] if row[0].text}
            for sheet, price_column in (("Asset", 6), ("Asset - Exchange", 7)):
                with self.subTest(report=report_name, sheet=sheet):
                    # The data rows start after the 3 header rows and end before the total rows.
                    rows = read_sheet_cells(report_path, sheet) or []
                    data_rows = [(number, row) for number, row in enumerate(rows, 1) if number > 3 and row[0].text not in ("", "Total", "Grand Total")]
                    self.assertTrue(data_rows)
                    for row_number, row in data_rows:
                        self.assertEqual(input_prices.get(row[0].text), "Enter asset value")
                        self.assertEqual(
                            row[price_column].text,
                            f'=IF(VLOOKUP(A{row_number};$Input.A:B;2;0)="Enter asset value";"See Input tab";VLOOKUP(A{row_number};$Input.A:B;2;0))',
                        )
            with self.subTest(report=report_name, formulas="all"):
                no_problems: List[str] = []
                self.assertEqual(get_malformed_formulas(report_path), no_problems)


if __name__ == "__main__":
    unittest.main()
