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

# R17 of the second review of eprbell/rp2#155: the cells of the full report that refer to lots and years, with date filters (-f) and with
# per-wallet application. Each test writes a small input and runs rp2_us on it.

import os
import shutil
import unittest
from pathlib import Path
from subprocess import CompletedProcess, run
from typing import Dict, List, NamedTuple, Union

from ods_diff import ReportCell, read_sheet_cells, write_ods_input
from test_report_input_text import _HEADER_SECTIONS, _IN_HEADER, _INTRA_HEADER, _OUT_HEADER

ROOT_PATH: Path = Path(os.path.dirname(__file__)).parent.absolute()

_GENERAL_SECTION: str = "[general]\nassets = B1\nexchanges = Coinbase, Kraken\nholders = Bob\n"


# The result of a run of rp2_us: its exit code and output, and the path of its full report.
class _Run(NamedTuple):
    returncode: int
    output: str
    report_path: Path


class TestFullReportCells(unittest.TestCase):
    # Writes the input and the configuration of a test, runs rp2_us with the given arguments and returns the result of the run and the
    # path of the full report.
    def _run(self, name: str, rows: List[List[Union[str, float]]], arguments: List[str], country_section: str = "") -> _Run:
        output_dir: Path = ROOT_PATH / Path("output") / Path(self.__module__) / Path(name)
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True)
        input_path: Path = output_dir / Path("input.ods")
        asset_2_rows: Dict[str, List[List[Union[str, float]]]] = {"B1": rows}
        write_ods_input(input_path, asset_2_rows)
        configuration_path: Path = output_dir / Path("config.ini")
        configuration_path.write_text(_GENERAL_SECTION + _HEADER_SECTIONS + country_section, encoding="utf-8")
        report_dir: Path = output_dir / Path("reports")
        result: CompletedProcess[str] = run(
            ["rp2_us", "-m", "fifo", *arguments, "-o", str(report_dir), "-p", f"{name}_", str(configuration_path), str(input_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        return _Run(result.returncode, result.stdout + result.stderr, report_dir / Path(f"{name}_fifo_rp2_full_report.ods"))

    # The Summary has whole years, from the year of the -f date, while the Tax sheet starts at the -f date: a year can have a Summary row
    # but no row in the Gain / Loss Detail table, which the Summary row links to. Then its cells have no link. Example (the review's): buy on
    # 2024-01-10, sell on 2024-03-01 and run with -f 2024-06-01. Before, the report stopped with KeyError: _AssetAndYear(asset='B1', year=2024)
    # (RP2 1.7.2 too).
    def test_summary_year_without_detail_rows(self) -> None:
        rows: List[List[Union[str, float]]] = [
            ["IN"],
            _IN_HEADER,
            ["2024-01-10T15:00Z", "Kraken", "Bob", "", "", "Buy", "B1", 1.0, 100.0, "", "", 0.0, "i1", ""],
            ["TABLE END"],
            ["OUT"],
            _OUT_HEADER,
            ["2024-03-01T15:00Z", "Kraken", "Bob", "", "", "Sell", "B1", 0.5, 200.0, 0.0, "", "", "o1", ""],
            ["TABLE END"],
        ]
        run_result = self._run("summary_without_detail", rows, ["-f", "2024-06-01"])
        self.assertEqual(run_result.returncode, 0, msg=run_result.output)
        summary_rows: List[List[ReportCell]] = [cells for cells in read_sheet_cells(run_result.report_path, "Summary") or [] if cells[0].text == "2024.0"]
        want_texts: List[List[str]] = [["2024.0", "B1", "50.0", "SHORT", "SELL"]]
        got_texts: List[List[str]] = [[cell.text for cell in cells[:5]] for cells in summary_rows]
        self.assertEqual(got_texts, want_texts)
        links: Dict[str, int] = {cell.text: cell.link_row for cells in summary_rows for cell in cells if cell.link_row is not None}
        no_links: Dict[str, int] = {}
        self.assertEqual(links, no_links)

    # With per-wallet application, Acquired Lot Fraction % is the fraction of the original lot, the in-transaction that the lot's cells link
    # to, as the legend says ("Percentage of the in-transaction"); the description names the wallet's lot. Example: buy 5 coins on Coinbase
    # (i1), move 2 to Kraken (t1) and sell 1 there: the sale takes 1 coin of Kraken's lot t1/-n, 20% of i1. Before, the fraction was of the
    # wallet's lot (1 of its 2 coins: 50%), next to a link to i1's row.
    def test_acquired_lot_fraction_of_the_original_lot(self) -> None:
        rows: List[List[Union[str, float]]] = [
            ["IN"],
            _IN_HEADER,
            ["2025-01-10T15:00Z", "Coinbase", "Bob", "", "", "Buy", "B1", 5.0, 100.0, "", "", 0.0, "i1", ""],
            ["TABLE END"],
            ["OUT"],
            _OUT_HEADER,
            ["2025-03-01T15:00Z", "Kraken", "Bob", "", "", "Sell", "B1", 1.0, 200.0, 0.0, "", "", "o1", ""],
            ["TABLE END"],
            ["INTRA"],
            _INTRA_HEADER,
            ["2025-02-01T15:00Z", "Coinbase", "Bob", "Kraken", "Bob", "", "B1", 2.0, 150.0, "", 2.0, "", "t1", ""],
            ["TABLE END"],
        ]
        run_result = self._run("fraction_of_the_original_lot", rows, [], "\n[country.us]\ntimezone = UTC\n")
        self.assertEqual(run_result.returncode, 0, msg=run_result.output)
        in_out_rows: List[List[ReportCell]] = read_sheet_cells(run_result.report_path, "B1 In-Out") or []
        lot_rows: List[List[ReportCell]] = [
            cells for cells in read_sheet_cells(run_result.report_path, "B1 Tax") or [] if len(cells) > 19 and cells[18].text == "i1"
        ]
        self.assertEqual(len(lot_rows), 1)
        cells: List[ReportCell] = lot_rows[0]
        # The fraction, the unique id and the description of the lot; all link to i1's row of the In-Out sheet.
        self.assertEqual(cells[13].text, "0.2")
        self.assertRegex(cells[19].text, r"^1/1: 1\.00000000 of 2\.00000000 B1 in Kraken/Bob \(lot t1/-\d+\)$")
        for cell in (cells[13], cells[18], cells[19]):
            self.assertEqual(cell.link_sheet, "B1 In-Out")
            link_row: int = cell.link_row or 0
            self.assertEqual(in_out_rows[link_row - 1][14].text, "i1")


if __name__ == "__main__":
    unittest.main()
