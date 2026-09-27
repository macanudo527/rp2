# Copyright 2025 eprbell
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

import os
import shutil
import unittest
from pathlib import Path
from subprocess import run
from typing import List, NamedTuple

from abstract_test_ods_output_diff import (
    CONFIG_PATH,
    INPUT_PATH,
    AbstractTestODSOutputDiff,
    OutputPlugins,
)
from ods_diff import ods_diff

ROOT_PATH: Path = Path(os.path.dirname(__file__)).parent.absolute()

_PER_WALLET_SECTION: str = "\n[per_wallet]\ntimezone = America/New_York\n"


class _Dataset(NamedTuple):
    test_name: str
    config: str
    methods: List[str]
    allow_negative_balances: bool


# All these datasets end before 2025: per-wallet application (-w) must produce exactly the same output as universal application (whose output
# is checked against golden files in test_ods_output_diff.py).
_DATASETS: List[_Dataset] = [
    _Dataset("crypto_example", "crypto_example", AbstractTestODSOutputDiff.METHODS, True),
    _Dataset("test_data", "test_data", AbstractTestODSOutputDiff.METHODS, True),
    _Dataset("test_data4", "test_data4", AbstractTestODSOutputDiff.METHODS, False),
    _Dataset("test_many_year_data", "test_data", AbstractTestODSOutputDiff.METHODS, True),
    _Dataset("test_data_multi_method", "test_data_multi_method", ["mixed"], True),
]


class TestODSOutputDiffPerWallet(AbstractTestODSOutputDiff):
    output_dir: Path
    universal_output_dir: Path
    config_dir: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.output_dir = ROOT_PATH / Path("output") / Path(cls.__module__)
        cls.universal_output_dir = cls.output_dir / Path("universal")
        cls.config_dir = cls.output_dir / Path("config")
        shutil.rmtree(cls.output_dir, ignore_errors=True)
        cls.config_dir.mkdir(parents=True)

        for dataset in _DATASETS:
            config_text = (CONFIG_PATH / Path(f"{dataset.config}.ini")).read_text(encoding="utf-8")
            (cls.config_dir / Path(f"{dataset.config}.ini")).write_text(config_text + _PER_WALLET_SECTION, encoding="utf-8")
            for method in dataset.methods:
                AbstractTestODSOutputDiff._generate(
                    cls.universal_output_dir,
                    test_name=dataset.test_name,
                    config=dataset.config,
                    method=method,
                    allow_negative_balances=dataset.allow_negative_balances,
                )
                AbstractTestODSOutputDiff._generate(
                    cls.output_dir,
                    test_name=dataset.test_name,
                    config=dataset.config,
                    method=method,
                    allow_negative_balances=dataset.allow_negative_balances,
                    extra_arguments=["-w"],
                    config_dir=cls.config_dir,
                )

    def test_per_wallet_output_matches_universal_output_before_2025(self) -> None:
        for dataset in _DATASETS:
            for method in dataset.methods:
                for plugin_name in (OutputPlugins.OPEN_POSITIONS.name, OutputPlugins.RP2_FULL_REPORT.name, OutputPlugins.TAX_REPORT_US.name):
                    plugin_name = plugin_name.lower()
                    with self.subTest(dataset=dataset.test_name, method=method, plugin=plugin_name):
                        file_name = Path(f"{dataset.test_name}_{method}_{plugin_name}.ods")
                        self.assertTrue((self.output_dir / file_name).exists(), msg=str(file_name))
                        diff = ods_diff(self.universal_output_dir / file_name, self.output_dir / file_name, generate_ascii_representation=True)
                        self.assertFalse(diff, msg=diff)

    def test_per_wallet_is_rejected_for_countries_with_universal_application(self) -> None:
        # Japan (and every country that doesn't declare a per-wallet start year) must never run per-wallet code.
        result = run(
            [
                "rp2_jp",
                "-w",
                "-o",
                str(self.output_dir / Path("jp")),
                str(self.config_dir / Path("test_data4.ini")),
                str(INPUT_PATH / Path("test_data4.ods")),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Per-wallet application (-w) is not supported for country 'jp'", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
