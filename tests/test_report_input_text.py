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

# R24 of the second review of eprbell/rp2#155: text from the input must stay text in the reports and must not break the formulas that
# contain it. The input of these tests has text that looks like a formula (e.g. the note "=1+1", the ID "=2+2" and the exchange "=Ex"),
# quotes and semicolons (the ID buy"id;1 and the asset B'1"x) and characters that SUMIF reads as patterns (the holders Bob*, Bobby and >0).
# Every country plugin whose report generators show such text writes its reports from it: US (with per-wallet application from 2025, so
# also the opening allocation report), JP and IE.

import os
import shutil
import unittest
from pathlib import Path
from subprocess import run
from typing import Dict, List, Set, Union

from ods_diff import ODSCell, read_cells, write_ods_input

ROOT_PATH: Path = Path(os.path.dirname(__file__)).parent.absolute()

_ASSET: str = "B'1\"x"
# The text of the input that looks like a formula. Before R24, the reports wrote it as a formula: "=1+1" showed 2.
_FORMULA_TEXTS: List[str] = ["=1+1", "=2+2", "=3+3", "=4+4", "=Ex", "=SUM(1;2)", '=HYPERLINK("https://example.com/";"click")']

_GENERAL_SECTION: str = f"""[general]
assets = {_ASSET}, B2
exchanges = =Ex, Kraken
holders = A"B, Bob*, Bobby, >0
"""
_HEADER_SECTIONS: str = """
[in_header]
timestamp = 0
asset = 6
exchange = 1
holder = 2
transaction_type = 5
spot_price = 8
crypto_in = 7
fiat_fee = 11
unique_id = 12
notes = 13

[out_header]
timestamp = 0
asset = 6
exchange = 1
holder = 2
transaction_type = 5
spot_price = 8
crypto_out_no_fee = 7
crypto_fee = 9
unique_id = 12
notes = 13

[intra_header]
timestamp = 0
asset = 6
from_exchange = 1
from_holder = 2
to_exchange = 3
to_holder = 4
spot_price = 8
crypto_sent = 7
crypto_received = 10
unique_id = 12
notes = 13
"""
_IN_HEADER: List[Union[str, float]] = [
    "Timestamp",
    "Exchange",
    "Holder",
    "",
    "",
    "Transaction Type",
    "Asset",
    "Crypto In",
    "Spot Price",
    "",
    "",
    "USD Fee",
    "Unique Id",
    "Notes",
]
_OUT_HEADER: List[Union[str, float]] = [
    "Timestamp",
    "Exchange",
    "Holder",
    "",
    "",
    "Transaction Type",
    "Asset",
    "Crypto Out",
    "Spot Price",
    "Crypto Fee",
    "",
    "",
    "Unique Id",
    "Notes",
]
_INTRA_HEADER: List[Union[str, float]] = [
    "Timestamp",
    "From Exchange",
    "From Holder",
    "To Exchange",
    "To Holder",
    "",
    "Asset",
    "Crypto Sent",
    "Spot Price",
    "",
    "Crypto Received",
    "",
    "Unique Id",
    "Notes",
]
# A"B buys 3 coins of B'1"x on =Ex in 2024 (one wallet: the opening allocation at the switch to per-wallet application is automatic), then
# moves 1 to Bob*, 0.5 to Bobby and 0.5 to >0 on Kraken, and Bob* sells 0.5. Bobby also holds 1 B2. At the end: A"B 1, Bob* 0.5, Bobby 0.5
# and >0 0.5 B'1"x.
_ASSET_2_ROWS: Dict[str, List[List[Union[str, float]]]] = {
    _ASSET: [
        ["IN"],
        _IN_HEADER,
        ["2024-01-10T15:00Z", "=Ex", 'A"B', "", "", "Buy", _ASSET, 2.0, 100.0, "", "", 0.0, "=2+2", "=1+1"],
        ["2024-02-10T15:00Z", "=Ex", 'A"B', "", "", "Buy", _ASSET, 1.0, 200.0, "", "", 0.0, 'buy"id;1', '=HYPERLINK("https://example.com/";"click")'],
        ["TABLE END"],
        ["OUT"],
        _OUT_HEADER,
        ["2025-06-01T15:00Z", "Kraken", "Bob*", "", "", "Sell", _ASSET, 0.5, 300.0, 0.0, "", "", "sell'id", "=SUM(1;2)"],
        ["TABLE END"],
        ["INTRA"],
        _INTRA_HEADER,
        ["2025-02-01T15:00Z", "=Ex", 'A"B', "Kraken", "Bob*", "", _ASSET, 1.0, 250.0, "", 1.0, "", 'move"1', "'quoted'"],
        ["2025-03-01T15:00Z", "=Ex", 'A"B', "Kraken", "Bobby", "", _ASSET, 0.5, 260.0, "", 0.5, "", "=3+3", ""],
        ["2025-03-02T15:00Z", "=Ex", 'A"B', "Kraken", ">0", "", _ASSET, 0.5, 270.0, "", 0.5, "", "=4+4", ""],
        ["TABLE END"],
    ],
    "B2": [
        ["IN"],
        _IN_HEADER,
        ["2024-01-10T15:00Z", "Kraken", "Bobby", "", "", "Buy", "B2", 1.0, 10.0, "", "", 0.0, "plain", ""],
        ["TABLE END"],
    ],
}


class TestReportInputText(unittest.TestCase):
    output_dir: Path
    report_2_cells: Dict[str, List[ODSCell]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.output_dir = ROOT_PATH / Path("output") / Path(cls.__module__)
        shutil.rmtree(cls.output_dir, ignore_errors=True)
        cls.output_dir.mkdir(parents=True)
        input_path: Path = cls.output_dir / Path("input.ods")
        write_ods_input(input_path, _ASSET_2_ROWS)
        universal_path: Path = cls.output_dir / Path("universal.ini")
        universal_path.write_text(_GENERAL_SECTION + _HEADER_SECTIONS, encoding="utf-8")
        per_wallet_path: Path = cls.output_dir / Path("per_wallet.ini")
        per_wallet_path.write_text(_GENERAL_SECTION + _HEADER_SECTIONS + "\n[country.us]\ntimezone = UTC\n", encoding="utf-8")
        for country, configuration_path, extra_arguments in (("us", per_wallet_path, []), ("jp", universal_path, ["-g", "en"]), ("ie", universal_path, [])):
            run(
                [
                    f"rp2_{country}",
                    "-m",
                    "fifo",
                    *extra_arguments,
                    "-o",
                    str(cls.output_dir / Path(country)),
                    "-p",
                    f"{country}_",
                    str(configuration_path),
                    str(input_path),
                ],
                check=True,
            )
        cls.report_2_cells = {path.name: read_cells(path) for path in sorted(cls.output_dir.glob("*/*.ods"))}

    def test_reports(self) -> None:
        want: List[str] = [
            "ie_fifo_open_positions.ods",
            "ie_fifo_rp2_full_report.ods",
            "ie_fifo_tax_report_ie.ods",
            "jp_fifo_open_positions.ods",
            "jp_fifo_rp2_full_report.ods",
            "jp_fifo_tax_report_jp.ods",
            "us_fifo_open_positions.ods",
            "us_fifo_opening_allocation.ods",
            "us_fifo_rp2_full_report.ods",
            "us_fifo_tax_report_us.ods",
        ]
        reports: List[str] = sorted(self.report_2_cells.keys())
        self.assertEqual(reports, want)

    # No formula of a report comes from the input: each text that looks like a formula is in the reports as text, in every report that shows
    # its field (e.g. the IDs of the lots in the full report, the tax reports and the opening allocation report).
    def test_input_text_is_text(self) -> None:
        for report, cells in self.report_2_cells.items():
            with self.subTest(report=report):
                input_formulas: List[str] = [f"{cell.sheet}.{cell.address}: {cell.formula}" for cell in cells if cell.formula in _FORMULA_TEXTS]
                no_formulas: List[str] = []
                self.assertEqual(input_formulas, no_formulas)
        report_2_texts: Dict[str, Set[str]] = {
            "us_fifo_rp2_full_report.ods": set(_FORMULA_TEXTS),
            "jp_fifo_rp2_full_report.ods": set(_FORMULA_TEXTS),
            "ie_fifo_rp2_full_report.ods": set(_FORMULA_TEXTS),
            "us_fifo_opening_allocation.ods": {"=2+2", "=Ex"},
            "us_fifo_open_positions.ods": {"=Ex"},
            "jp_fifo_open_positions.ods": {"=Ex"},
            "ie_fifo_open_positions.ods": {"=Ex"},
            "us_fifo_tax_report_us.ods": {"=2+2"},
            "ie_fifo_tax_report_ie.ods": {"=2+2"},
        }
        for report, want_texts in report_2_texts.items():
            with self.subTest(report=report, texts="shown"):
                texts: Set[str] = {cell.text for cell in self.report_2_cells.get(report, []) if cell.formula is None}
                no_texts: Set[str] = set()
                self.assertEqual(want_texts - texts, no_texts)

    # The holder totals of the Open Positions reports compare the holders as they are: each total sums the rows whose holder is the one in its
    # own row, so no holder name is in a formula. With SUMIF the name was a criterion: in LibreOffice 24.2 the total of Bob* also counted
    # Bobby's rows ($110 instead of $50), the one of >0 was $0 ("greater than 0") and the one of A"B was an error (Err:508).
    def test_holder_totals(self) -> None:
        holders: List[str] = sorted(['A"B', ">0", "Bob*", "Bobby"])
        for report in ("us_fifo_open_positions.ods", "jp_fifo_open_positions.ods", "ie_fifo_open_positions.ods"):
            for sheet, columns in (("Asset", "EHI"), ("Asset - Exchange", "FIJ")):
                with self.subTest(report=report, sheet=sheet):
                    address_2_cell: Dict[str, ODSCell] = {cell.address: cell for cell in self.report_2_cells[report] if cell.sheet == sheet}
                    total_rows: List[int] = sorted(int(address[1:]) for address, cell in address_2_cell.items() if address[0] == "A" and cell.text == "Total")
                    total_holders: List[str] = sorted(address_2_cell[f"B{row}"].text for row in total_rows)
                    self.assertEqual(total_holders, holders)
                    # The data rows start after the 3 header rows and end before the total rows.
                    last_data_row: int = total_rows[0] - 1
                    for row in total_rows:
                        for column in columns:
                            self.assertEqual(
                                address_2_cell[f"{column}{row}"].formula, f"=SUMPRODUCT((B$4:B${last_data_row}=B{row})*{column}$4:{column}${last_data_row})"
                            )
                    holder_formulas: List[str] = [
                        f"{address}: {cell.formula}"
                        for address, cell in address_2_cell.items()
                        if cell.formula and any(f'"{holder}' in cell.formula for holder in holders)
                    ]
                    no_formulas: List[str] = []
                    self.assertEqual(holder_formulas, no_formulas)


if __name__ == "__main__":
    unittest.main()
