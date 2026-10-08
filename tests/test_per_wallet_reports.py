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

# End-to-end tests of the reports generated with per-wallet application (compute_tax_per_wallet): they check actual report cells. Expected
# values are computed by hand: each test explains the rule it checks.

import shutil
import unittest
from pathlib import Path
from typing import List, NamedTuple

from ods_diff import read_sheet_rows
from per_wallet_common import _ASSET, _CONFIGURATION_PATH, _COINBASE, _KRAKEN, _UTC, AbstractPerWalletTest, _GainLoss, _In, _Intra, _Out, _sorted

from rp2.configuration import MAX_DATE, MIN_DATE, Configuration
from rp2.gain_loss import GainLoss
from rp2.in_transaction import InTransaction
from rp2.localization import set_generation_language
from rp2.per_wallet_configuration import PerWalletConfiguration
from rp2.plugin.accounting_method.fifo import AccountingMethod as AccountingMethodFIFO
from rp2.plugin.country.us import US
from rp2.plugin.report.open_positions import Generator as OpenPositionsGenerator
from rp2.plugin.report.rp2_full_report import Generator as FullReportGenerator
from rp2.plugin.report.us.tax_report_us import Generator as TaxReportUSGenerator
from rp2.rp2_decimal import RP2Decimal
from rp2.tax_engine import compute_tax_per_wallet


class TestPerWalletReports(AbstractPerWalletTest):
    def test_reports_with_artificial_lots(self) -> None:
        # Gain/losses on artificial lots (transfer destinations, unused basis allocation) must not break report generation, and Form 8949
        # "date acquired" must be the original acquisition date, not the transfer date.
        set_generation_language("en")
        configuration = Configuration(_CONFIGURATION_PATH, US())
        input_data = self._create_input_data(
            configuration,
            [
                _In("i1", "2024-06-01T00:00:00+00:00", "Coinbase", "Buy", "100", "2", fiat_fee="1"),
                _In("i2", "2024-07-01T00:00:00+00:00", "Kraken", "Buy", "150", "1"),
                _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "150", "2", "1.9"),
                _Out("o1", "2025-08-01T00:00:00+00:00", "Kraken", "300", "2.5"),
            ],
        )
        per_wallet_configuration = PerWalletConfiguration(
            timezone_name="UTC",
            unused_basis_allocation_method="fifo",
            unused_basis_allocation_wallet_order=(_COINBASE, _KRAKEN),
        )
        computed_data = compute_tax_per_wallet(
            configuration, self._create_accounting_engine(None), input_data, per_wallet_configuration, AccountingMethodFIFO()
        )
        gain_losses = [gain_loss for gain_loss in computed_data.gain_loss_set if isinstance(gain_loss, GainLoss)]
        self.assertTrue(any(gain_loss.acquired_lot is not None and gain_loss.acquired_lot.from_lot is not None for gain_loss in gain_losses))
        for gain_loss in gain_losses:
            if gain_loss.acquired_lot is not None:
                self.assertEqual(gain_loss.acquired_lot.cost_basis_timestamp, gain_loss.acquired_lot.original_lot.timestamp)
        # The sold percentage of an input lot includes sales of its artificial descendants: i1 (2 units) had 0.1 disposed of as a transfer fee
        # and 1.9 sold on Kraken.
        original_lot = next(lot for lot in input_data.unfiltered_in_transaction_set if isinstance(lot, InTransaction) and lot.unique_id == "i1")
        self.assertEqual(computed_data.get_in_lot_sold_percentage(original_lot), RP2Decimal("1"))

        output_dir = Path("output") / Path("test_per_wallet_tax_engine")
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True)
        for generator in (OpenPositionsGenerator(), FullReportGenerator(), TaxReportUSGenerator()):
            generator.generate(US(), {1970: "fifo"}, {_ASSET: computed_data}, str(output_dir), "per_wallet_", MIN_DATE, MAX_DATE, "en")
        self.assertEqual(len(list(output_dir.glob("per_wallet_*.ods"))), 3)

    # IRS FAQ A81 and A97: the crypto paid as a fee on a transfer between the taxpayer's own wallets is disposed of and gain or loss is
    # recognized on it; A53: that fee is not a digital asset transaction cost, so it is not added to the basis of the received units.
    # Reproduction from the review of eprbell/rp2#155 (R02), checked in the actual report cells: buy 1 unit for $100, transfer it when it is
    # worth $200 paying a 0.1 unit fee, sell the 0.9 received units for $270.
    def test_transfer_fee_is_a_disposal_in_reports(self) -> None:
        set_generation_language("en")
        configuration = Configuration(_CONFIGURATION_PATH, US())
        input_data = self._create_input_data(
            configuration,
            [
                _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "1"),
                _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "200", "1", "0.9"),
                _Out("o1", "2025-03-01T00:00:00+00:00", "Kraken", "300", "0.9"),
            ],
        )
        computed_data = compute_tax_per_wallet(configuration, self._create_accounting_engine(None), input_data, _UTC)
        output_dir = Path("output") / Path("test_per_wallet_tax_engine_fee")
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True)
        TaxReportUSGenerator().generate(US(), {1970: "fifo"}, {_ASSET: computed_data}, str(output_dir), "fee_", MIN_DATE, MAX_DATE, "en")
        report_path = output_dir / Path("fee_fifo_tax_report_us.ods")

        # Columns: amount, asset, date acquired, date sold or transacted, proceeds, cost basis, (f), (g), gain or loss, then the additional
        # transaction information (type, acquired lot fraction and id, taxable event fraction and id, capital gains type, full timestamp).
        def data_rows(sheet_name: str) -> List[List[str]]:
            rows = read_sheet_rows(report_path, sheet_name)
            self.assertIsNotNone(rows, msg=f"missing sheet {sheet_name}")
            return [row for row in rows or [] if row[1:2] == [_ASSET]]

        # The fee (MOVE): 0.1 unit of lot i1 disposed of at $200/unit: proceeds $20, basis $10, gain $10, with its source lot and transfer.
        want_fee_rows: List[List[str]] = [
            ["0.1", "B1", "01/02/2025", "02/01/2025", "20.0", "10.0", "", "", "10.0", "INTRA / MOVE"]
            + ["1/1: 0.10000000 of 1.00000000 B1", "i1", "1/1: 0.10000000 of 0.10000000 B1", "t1", "SHORT", "2025-02-01 00:00:00+00:00"]
        ]
        self.assertEqual(data_rows("Investment Expenses"), want_fee_rows)
        # The sale: the 0.9 received units keep their basis ($90) and acquisition date. (Its acquired lot id column is fixed by R17.)
        want_sale_rows: List[List[str]] = [["0.9", "B1", "01/02/2025", "03/01/2025", "270.0", "90.0", "", "", "180.0", "OUT / SELL"]]
        got_sale_rows: List[List[str]] = [row[:10] for row in data_rows("Capital Gains")]
        self.assertEqual(got_sale_rows, want_sale_rows)

    # R05 from the review of eprbell/rp2#155: after a transfer fee, the basis left in the reports must match the coins actually left.
    #
    # The rule in plain English: the coins paid as a transfer fee are treated as sold (IRS FAQ A81, A97), so they use up their own share of
    # the purchase cost. The fee is not added to the cost of the coins that arrive (FAQ A53), and the coins that arrive keep their purchase
    # cost and date (Treas. Reg. §1.1012-1(j)(1): the date units were transferred into a wallet is disregarded).
    #
    # Example: buy 10 coins for $1,000 ($100 each), move them to another wallet paying 1 coin as the fee, so 9 coins arrive. The fee coin
    # uses up $100 of cost, and the 9 coins that arrive carry the other $900. Sell 1 of them: 8 coins are left, with $800 of cost.
    #
    # The removed "basis carryover" option (R02) got this wrong: it spread the fee coin's $100 over the 9 coins that arrived ($111.11 each),
    # but the Open Positions report still subtracted only the coins sold, so 8 coins showed $900 instead of $888.89. Selling all 9 left
    # $100 of cost with no coins to hold it, and the Open Positions report crashed with KeyError: 'B1'.
    def test_transfer_fee_leaves_no_phantom_basis(self) -> None:
        class _Case(NamedTuple):
            description: str
            transactions: List[object]
            want: List[_GainLoss]
            # Fraction of lot i1 that is used up (fee plus sales), as shown in the "Sent/Sold" column of the full report.
            want_sold_fraction: str
            # Open Positions "Asset" sheet: asset, holder, balance, cost per unit, total cost of the coins still held.
            want_by_asset: List[List[str]]
            # Open Positions "Asset - Exchange" sheet: the same, per wallet.
            want_by_exchange: List[List[str]]

        buy_10 = _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10")
        # Move all 10 coins when they are worth $150 each, paying 1 coin as the fee. The fee is a sale of 1 coin for $150 with $100 of cost.
        move_all = _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "150", "10", "9")
        fee_of_1_coin = _GainLoss("t1", "i1", "1", "100", "50", False)
        cases = [
            _Case(
                description="sell 1 of the 9 coins received: 8 coins left with $800 of cost",
                transactions=[buy_10, move_all, _Out("o1", "2025-03-01T00:00:00+00:00", "Kraken", "200", "1")],
                want=[fee_of_1_coin, _GainLoss("o1", "i1", "1", "100", "100", False)],
                want_sold_fraction="0.2",
                want_by_asset=[["B1", "Bob", "8.0", "100.0", "800.0"]],
                want_by_exchange=[["B1", "Bob", "Kraken", "8.0", "100.0", "800.0"]],
            ),
            _Case(
                description="sell all 9 coins received: no coins and no cost left, and every report is generated",
                transactions=[buy_10, move_all, _Out("o1", "2025-03-01T00:00:00+00:00", "Kraken", "200", "9")],
                want=[fee_of_1_coin, _GainLoss("o1", "i1", "9", "900", "900", False)],
                want_sold_fraction="1.0",
                want_by_asset=[],
                want_by_exchange=[],
            ),
            _Case(
                # Part of the lot stays behind and part travels: move 6 of the 10 coins paying 1 coin as the fee (5 arrive), then sell 3 of
                # the 5. Used up: 1 (fee) + 3 (sale) = 4 of 10 coins. Left: 4 coins on Coinbase and 2 on Kraken, $100 each.
                description="lot partly used up across wallets: 6 coins left with $600 of cost",
                transactions=[
                    buy_10,
                    _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "150", "6", "5"),
                    _Out("o1", "2025-03-01T00:00:00+00:00", "Kraken", "200", "3"),
                ],
                want=[fee_of_1_coin, _GainLoss("o1", "i1", "3", "300", "300", False)],
                want_sold_fraction="0.4",
                want_by_asset=[["B1", "Bob", "6.0", "100.0", "600.0"]],
                want_by_exchange=[["B1", "Bob", "Coinbase", "4.0", "100.0", "400.0"], ["B1", "Bob", "Kraken", "2.0", "100.0", "200.0"]],
            ),
            _Case(
                # Amounts that don't divide evenly must not leave a tiny rounding remainder of cost behind: buy 3 coins for $21 ($7 each),
                # move them paying 0.1 coin as the fee, sell the 2.9 that arrive. Fee: 0.1 × $7 = $0.70 of cost; sale: 2.9 × $7 = $20.30.
                description="uneven amounts: no rounding remainder of cost is left",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "7", "3"),
                    _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "9", "3", "2.9"),
                    _Out("o1", "2025-03-01T00:00:00+00:00", "Kraken", "11", "2.9"),
                ],
                want=[_GainLoss("t1", "i1", "0.1", "0.7", "0.2", False), _GainLoss("o1", "i1", "2.9", "20.3", "11.6", False)],
                want_sold_fraction="1.0",
                want_by_asset=[],
                want_by_exchange=[],
            ),
        ]

        set_generation_language("en")
        configuration = Configuration(_CONFIGURATION_PATH, US())
        for case in cases:
            with self.subTest(name=case.description):
                input_data = self._create_input_data(configuration, case.transactions)
                computed_data = compute_tax_per_wallet(configuration, self._create_accounting_engine(None), input_data, _UTC)
                gain_losses = [gain_loss for gain_loss in computed_data.gain_loss_set if isinstance(gain_loss, GainLoss)]
                self.assertEqual(_sorted(self._to_tuples(gain_losses)), _sorted(self._want_tuples(case.want)))

                # Generating the reports must not fail (selling everything used to crash Open Positions with KeyError: 'B1').
                output_dir = Path("output") / Path("test_per_wallet_tax_engine_r05")
                shutil.rmtree(output_dir, ignore_errors=True)
                output_dir.mkdir(parents=True)
                for generator in (OpenPositionsGenerator(), FullReportGenerator(), TaxReportUSGenerator()):
                    generator.generate(US(), {1970: "fifo"}, {_ASSET: computed_data}, str(output_dir), "r05_", MIN_DATE, MAX_DATE, "en")

                # Full report, In-Flow Detail: the first column of lot i1 is the fraction of the lot used up, counting the fee and the sales
                # made from the wallet the coins were moved to.
                in_out_rows = read_sheet_rows(output_dir / Path("r05_fifo_rp2_full_report.ods"), f"{_ASSET} In-Out") or []
                got_sold_fraction: List[str] = [row[0] for row in in_out_rows if row[14:15] == ["i1"]]
                want_sold_fraction: List[str] = [case.want_sold_fraction]
                self.assertEqual(got_sold_fraction, want_sold_fraction)

                # Open Positions: the coins still held and their remaining cost (purchase cost minus the cost used up by the fee and sales).
                open_positions_path = output_dir / Path("r05_fifo_open_positions.ods")
                got_by_asset: List[List[str]] = [row[:5] for row in read_sheet_rows(open_positions_path, "Asset") or [] if row[:1] == [_ASSET]]
                self.assertEqual(got_by_asset, case.want_by_asset)
                got_by_exchange: List[List[str]] = [row[:6] for row in read_sheet_rows(open_positions_path, "Asset - Exchange") or [] if row[:1] == [_ASSET]]
                self.assertEqual(got_by_exchange, case.want_by_exchange)


if __name__ == "__main__":
    unittest.main()
