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

# R23 of the second review of eprbell/rp2#155: the accounting_methods section of the configuration can contain a single entry, with any year
# (e.g. "2010 = fifo"). The reports assumed that a map with one entry has the year 1970, the key RP2 uses when the section is missing or the
# method comes from -m. So a run with "2010 = fifo" computed the taxes and then stopped with "KeyError: 1970" before writing any report,
# including the opening allocation report. A single entry means one method for every year: the reports must be the same as with -m and that
# method, also in their file names (<prefix>fifo_<report>.ods) and in the legend.

import os
import re
import shutil
import unittest
from pathlib import Path
from typing import Dict, List, Optional

from abstract_test_ods_output_diff import CONFIG_PATH, AbstractTestODSOutputDiff, OutputPlugins
from ods_diff import ods_diff, read_sheet_rows

ROOT_PATH: Path = Path(os.path.dirname(__file__)).parent.absolute()

_UNIVERSAL_DATASET: str = "test_data"
_PER_WALLET_DATASET: str = "test_data_per_wallet"
_PER_WALLET_PLUGINS: List[OutputPlugins] = [
    OutputPlugins.OPEN_POSITIONS,
    OutputPlugins.OPENING_ALLOCATION,
    OutputPlugins.RP2_FULL_REPORT,
    OutputPlugins.TAX_REPORT_US,
]
# The accounting_methods section, including its fields, up to the next section.
_ACCOUNTING_METHODS_SECTION = re.compile(r"^\[accounting_methods\]\n(?:(?!\[).*\n)*", re.MULTILINE)


# The configuration text with its accounting_methods section (if any) replaced by one with the given entries (none if entries is empty).
def _with_accounting_methods(config_text: str, entries: Dict[int, str]) -> str:
    result = _ACCOUNTING_METHODS_SECTION.sub("", config_text)
    if entries:
        result += "\n[accounting_methods]\n" + "".join(f"{year} = {method}\n" for year, method in entries.items())
    return result


class TestSingleAccountingMethod(AbstractTestODSOutputDiff):
    output_dir: Path
    config_dir: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.output_dir = ROOT_PATH / Path("output") / Path(cls.__module__)
        cls.config_dir = cls.output_dir / Path("config")
        shutil.rmtree(cls.output_dir, ignore_errors=True)
        cls.config_dir.mkdir(parents=True)

        # Universal application only (test_data ends before 2025): 1970 is the year RP2 itself uses for a single method, 2010 is another one.
        universal_text = (CONFIG_PATH / Path(f"{_UNIVERSAL_DATASET}.ini")).read_text(encoding="utf-8")
        for year in (1970, 2010):
            config = f"{_UNIVERSAL_DATASET}_{year}"
            (cls.config_dir / Path(f"{config}.ini")).write_text(_with_accounting_methods(universal_text, {year: "fifo"}), encoding="utf-8")
            AbstractTestODSOutputDiff._generate(
                cls.output_dir / Path(str(year)),
                test_name=_UNIVERSAL_DATASET,
                config=config,
                method="mixed",
                allow_negative_balances=True,
                config_dir=cls.config_dir,
            )

        # Per-wallet application (the per-wallet golden dataset reaches 2026), with "2010 = fifo" and, to compare, with -m fifo.
        per_wallet_text = (CONFIG_PATH / Path(f"{_PER_WALLET_DATASET}.ini")).read_text(encoding="utf-8")
        (cls.config_dir / Path(f"{_PER_WALLET_DATASET}_2010.ini")).write_text(_with_accounting_methods(per_wallet_text, {2010: "fifo"}), encoding="utf-8")
        (cls.config_dir / Path(f"{_PER_WALLET_DATASET}_none.ini")).write_text(_with_accounting_methods(per_wallet_text, {}), encoding="utf-8")
        AbstractTestODSOutputDiff._generate(
            cls.output_dir / Path("per_wallet_2010"),
            test_name=_PER_WALLET_DATASET,
            config=f"{_PER_WALLET_DATASET}_2010",
            method="mixed",
            config_dir=cls.config_dir,
        )
        AbstractTestODSOutputDiff._generate(
            cls.output_dir / Path("per_wallet_option"),
            test_name=_PER_WALLET_DATASET,
            config=f"{_PER_WALLET_DATASET}_none",
            method="fifo",
            config_dir=cls.config_dir,
        )

    # The value next to the "Accounting Method" cell of the legend sheet.
    def _get_legend_accounting_method(self, path: Path) -> Optional[str]:
        for row in read_sheet_rows(path, "Legend") or []:
            if len(row) > 1 and row[0] == "Accounting Method":
                return row[1]
        return None

    # With one entry, whatever its year, the reports are named and computed as with that method: equal to the golden files of test_data with
    # FIFO (generated with -m fifo).
    def test_universal_reports_match_the_method_golden_files(self) -> None:
        for year in (1970, 2010):
            for plugin in (OutputPlugins.RP2_FULL_REPORT, OutputPlugins.TAX_REPORT_US):
                with self.subTest(year=year, plugin=plugin.name.lower()):
                    self._compare(self.output_dir / Path(str(year)), test_name=_UNIVERSAL_DATASET, method="fifo", output_plugin=plugin)
            path = self.output_dir / Path(str(year)) / Path(f"{_UNIVERSAL_DATASET}_fifo_{OutputPlugins.OPEN_POSITIONS.name.lower()}.ods")
            with self.subTest(year=year, plugin=OutputPlugins.OPEN_POSITIONS.name.lower()):
                self.assertEqual(self._get_legend_accounting_method(path), "FIFO")

    # Per-wallet application with "2010 = fifo": the run allocates at the switch and writes all four reports, the opening allocation report
    # included, with the same content as with -m fifo.
    def test_per_wallet_reports_are_written(self) -> None:
        for plugin in _PER_WALLET_PLUGINS:
            with self.subTest(plugin=plugin.name.lower()):
                file_name = Path(f"{_PER_WALLET_DATASET}_fifo_{plugin.name.lower()}.ods")
                path = self.output_dir / Path("per_wallet_2010") / file_name
                self.assertTrue(path.exists(), msg=str(path))
                self.assertEqual(self._get_legend_accounting_method(path), "FIFO")
                diff = ods_diff(self.output_dir / Path("per_wallet_option") / file_name, path, generate_ascii_representation=False)
                self.assertFalse(diff, msg=diff)


if __name__ == "__main__":
    unittest.main()
