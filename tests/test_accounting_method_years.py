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

# R36 of the second review of eprbell/rp2#155: the years of each annual accounting method, as the reports' legend and the log show them, must
# be the years in which the engine uses it. The engine uses, in each tax year, the method of the latest entry of the accounting_methods
# section at or before that year. Example: with 2024 = fifo and 2026 = hifo, FIFO in 2024 and 2025 and HIFO from 2026 on. Before the fix the
# legend said "1970->2024:FIFO, 2024->2026:HIFO" (each range got the method of its end year, and it started in 1970, a year with no method),
# and reversing the two entries in the configuration file gave "1970->2026:HIFO, 2024:FIFO".

import os
import re
import shutil
import unittest
from pathlib import Path
from subprocess import run
from typing import Dict, List, Optional, Tuple

from abstract_test_ods_output_diff import CONFIG_PATH, GOLDEN_PATH, INPUT_PATH, OutputPlugins
from ods_diff import ods_diff
from prezzemolo.avl_tree import AVLTree

from rp2.accounting_engine import AccountingMethodYears, get_accounting_method_years
from rp2.rp2_error import RP2TypeError

ROOT_PATH: Path = Path(os.path.dirname(__file__)).parent.absolute()

_PER_WALLET_DATASET: str = "test_data_per_wallet"
_PER_WALLET_PLUGINS: List[OutputPlugins] = [
    OutputPlugins.OPEN_POSITIONS,
    OutputPlugins.OPENING_ALLOCATION,
    OutputPlugins.RP2_FULL_REPORT,
    OutputPlugins.TAX_REPORT_US,
]


class TestAccountingMethodYears(unittest.TestCase):
    # Each case: the configured entries, in configuration-file order, and the description of each range.
    _CASES: List[Tuple[Dict[int, str], List[str]]] = [
        ({2024: "fifo", 2026: "hifo"}, ["2024-2025: FIFO", "2026+: HIFO"]),
        ({2026: "hifo", 2024: "fifo"}, ["2024-2025: FIFO", "2026+: HIFO"]),
        ({2020: "fifo", 2021: "lifo", 2022: "hifo", 2023: "fifo"}, ["2020: FIFO", "2021: LIFO", "2022: HIFO", "2023+: FIFO"]),
        ({2016: "hifo", 2010: "fifo", 2015: "lifo"}, ["2010-2014: FIFO", "2015: LIFO", "2016+: HIFO"]),
        ({1970: "fifo"}, ["1970+: FIFO"]),
    ]

    def test_descriptions(self) -> None:
        for entries, want in self._CASES:
            with self.subTest(entries=entries):
                got: List[str] = [method_years.get_description() for method_years in get_accounting_method_years(entries)]
                self.assertEqual(got, want)

    def test_ranges(self) -> None:
        want: List[AccountingMethodYears] = [AccountingMethodYears(2010, 2014, "fifo"), AccountingMethodYears(2015, None, "lifo")]
        self.assertEqual(get_accounting_method_years({2015: "lifo", 2010: "fifo"}), want)

    # Every year, from before the first entry to after the last one, is in the range of the method that the engine's lookup (the AVLTree that
    # AccountingEngine and TransferAnalyzer use) selects for it, and years before the first entry are in no range.
    def test_ranges_match_the_engine_lookup(self) -> None:
        for entries, _ in self._CASES:
            tree: AVLTree[int, str] = AVLTree()
            for year, method in entries.items():
                tree.insert_node(year, method)
            ranges = get_accounting_method_years(entries)
            for year in range(min(entries) - 2, max(entries) + 3):
                with self.subTest(entries=entries, year=year):
                    in_range: List[str] = [
                        method_years.accounting_method_name
                        for method_years in ranges
                        if method_years.start_year <= year and (method_years.end_year is None or year <= method_years.end_year)
                    ]
                    engine_method: Optional[str] = tree.find_max_value_less_than(year)
                    want: List[str] = [engine_method] if engine_method is not None else []
                    self.assertEqual(in_range, want)

    def test_type_check(self) -> None:
        with self.assertRaisesRegex(RP2TypeError, "Parameter 'years_2_accounting_method_names' is not a Mapping"):
            get_accounting_method_years([2024, "fifo"])  # type: ignore


# The per-wallet golden dataset (2024 = fifo, 2026 = hifo) with the two entries in reverse order in the configuration file: the reports equal
# the golden files, legend included, and the log shows the years of each method.
class TestReversedAccountingMethods(unittest.TestCase):
    def test_reversed_entries(self) -> None:
        output_dir = ROOT_PATH / Path("output") / Path(self.__module__)
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True)
        config_text = (CONFIG_PATH / Path(f"{_PER_WALLET_DATASET}.ini")).read_text(encoding="utf-8")
        reversed_text = re.sub(r"^2024 = fifo\n2026 = hifo\n", "2026 = hifo\n2024 = fifo\n", config_text, flags=re.MULTILINE)
        self.assertNotEqual(reversed_text, config_text)
        config_path = output_dir / Path(f"{_PER_WALLET_DATASET}_reversed.ini")
        config_path.write_text(reversed_text, encoding="utf-8")
        result = run(
            ["rp2_us", "-o", str(output_dir), "-p", f"{_PER_WALLET_DATASET}_", str(config_path), str(INPUT_PATH / Path(f"{_PER_WALLET_DATASET}.ods"))],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Accounting methods: 2024-2025: FIFO, 2026+: HIFO", result.stdout + result.stderr)
        for plugin in _PER_WALLET_PLUGINS:
            with self.subTest(plugin=plugin.name.lower()):
                file_name = Path(f"{_PER_WALLET_DATASET}_mixed_{plugin.name.lower()}.ods")
                diff = ods_diff(GOLDEN_PATH / Path("us") / file_name, output_dir / file_name, generate_ascii_representation=False)
                self.assertFalse(diff, msg=diff)


# R22 of the second review of eprbell/rp2#155 (follow-up): every sale, fee and transfer needs the accounting method of its tax year, so one in a
# year before the first entry of the accounting_methods section is reported before any computation, with the asset, the transaction and the
# first year. Before, the computation stopped with "Internal error: no accounting method assigned for year 2020". Purchases don't take coins
# from lots, so they can be in earlier years. In test_data all transactions are in 2020 and 2021: B1 has only purchases (2020), B2 also has
# sales in 2020.
class TestTransactionsBeforeTheFirstMethod(unittest.TestCase):
    def _run(self, first_year: int, extra_arguments: List[str]) -> Tuple[int, str, List[str]]:
        output_dir = ROOT_PATH / Path("output") / Path(self.__module__) / Path(f"before_first_{first_year}_{'_'.join(extra_arguments)}")
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True)
        config_text = (CONFIG_PATH / Path("test_data.ini")).read_text(encoding="utf-8")
        config_path = output_dir / Path("config.ini")
        config_path.write_text(f"{config_text}\n[accounting_methods]\n{first_year} = fifo\n", encoding="utf-8")
        report_dir = output_dir / Path("reports")
        arguments = ["rp2_us", "-n", *extra_arguments, "-o", str(report_dir), "-p", "t_", str(config_path), str(INPUT_PATH / Path("test_data.ods"))]
        result = run(arguments, check=False, capture_output=True, text=True)
        reports: List[str] = sorted(os.listdir(report_dir)) if report_dir.exists() else []
        return result.returncode, result.stdout + result.stderr, reports

    def test_sale_before_the_first_method(self) -> None:
        returncode, output, reports = self._run(2021, ["-a", "B2"])
        self.assertNotEqual(returncode, 0)
        self.assertIn(
            "B2: the OutTransaction of 2020-01-11 11:15:00+00:00 (row 16) is in tax year 2020, which has no accounting method: the "
            "accounting_methods section of the configuration file starts in 2021 (add an entry for 2020 or earlier)",
            output,
        )
        self.assertNotIn("Internal error", output)
        no_reports: List[str] = []
        self.assertEqual(reports, no_reports)

    def test_purchases_before_the_first_method(self) -> None:
        returncode, output, reports = self._run(2021, ["-a", "B1"])
        self.assertEqual(returncode, 0, msg=output)
        self.assertEqual(len(reports), 3, msg=str(reports))

    def test_first_method_in_the_year_of_the_first_sale(self) -> None:
        returncode, output, reports = self._run(2020, [])
        self.assertEqual(returncode, 0, msg=output)
        self.assertEqual(len(reports), 3, msg=str(reports))


if __name__ == "__main__":
    unittest.main()
