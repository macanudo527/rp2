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

# End-to-end tests of per-wallet application (compute_tax_per_wallet). Expected values are computed by hand: each test explains the rule it
# checks. Regulatory references:
# - Treas. Reg. §1.1012-1(j): from 2025 basis is identified per wallet/account; absent specific identification, units are disposed of
#   "in order of time from the earliest date on which units ... were acquired by the taxpayer" (FIFO by original acquisition date);
# - Rev. Proc. 2024-28: unused basis at 2025-01-01 is allocated to wallets (global allocation or specific unit allocation);
# - IRC §1223: the holding period of transferred units includes the period they were held in the source wallet;
# - IRS FAQ Q13 / Rev. Rul. 2023-14: earned crypto is income at receipt, once.

import shutil
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

from prezzemolo.avl_tree import AVLTree

from rp2.abstract_accounting_method import AbstractAccountingMethod
from rp2.abstract_transaction import AbstractTransaction
from rp2.account import Account
from rp2.accounting_engine import AccountingEngine
from rp2.configuration import MAX_DATE, MIN_DATE, Configuration
from rp2.gain_loss import GainLoss
from rp2.in_transaction import InTransaction
from rp2.input_data import InputData
from rp2.intra_transaction import IntraTransaction
from rp2.localization import set_generation_language
from rp2.out_transaction import OutTransaction
from rp2.per_wallet_configuration import PerWalletConfiguration
from rp2.plugin.accounting_method.fifo import AccountingMethod as AccountingMethodFIFO
from rp2.plugin.accounting_method.hifo import AccountingMethod as AccountingMethodHIFO
from rp2.plugin.country.jp import JP
from rp2.plugin.country.us import US
from rp2.plugin.report.open_positions import Generator as OpenPositionsGenerator
from rp2.plugin.report.rp2_full_report import Generator as FullReportGenerator
from rp2.plugin.report.us.tax_report_us import Generator as TaxReportUSGenerator
from rp2.rp2_decimal import RP2Decimal
from rp2.rp2_error import RP2ValueError
from rp2.tax_engine import compute_tax, compute_tax_per_wallet
from rp2.transaction_set import TransactionSet
from rp2.transfer_fee_treatment import TransferFeeTreatment

_ASSET = "B1"
_CONFIGURATION_PATH = "./config/test_data.ini"
_UTC = PerWalletConfiguration(timezone_name="UTC")


# Short-form transaction descriptions.
class _In(NamedTuple):
    unique_id: str
    timestamp: str
    exchange: str
    transaction_type: str
    spot_price: str
    crypto_in: str
    fiat_fee: Optional[str] = None


class _Out(NamedTuple):
    unique_id: str
    timestamp: str
    exchange: str
    spot_price: str
    crypto_out_no_fee: str
    crypto_fee: str = "0"


class _Intra(NamedTuple):
    unique_id: str
    timestamp: str
    from_exchange: str
    to_exchange: str
    spot_price: str
    crypto_sent: str
    crypto_received: str


# Expected gain/loss: acquired_lot_unique_id is the unique id of the original (input) lot, even when the gain/loss refers to an artificial
# lot created by a transfer or by the unused basis allocation.
class _GainLoss(NamedTuple):
    taxable_event_unique_id: str
    acquired_lot_unique_id: Optional[str]
    crypto_amount: str
    fiat_cost_basis: str
    fiat_gain: str
    is_long_term: bool


_GainLossTuple = Tuple[str, Optional[str], RP2Decimal, RP2Decimal, RP2Decimal, bool]


def _sorted(gain_losses: List[_GainLossTuple]) -> List[_GainLossTuple]:
    return sorted(gain_losses, key=str)


@dataclass(frozen=True)
class _Test:
    description: str
    transactions: List[object]
    want: List[_GainLoss] = field(default_factory=list)
    want_error: str = ""
    per_wallet_configuration: PerWalletConfiguration = _UTC
    allocation_method: Optional[AbstractAccountingMethod] = None
    years_2_methods: Optional[Dict[int, AbstractAccountingMethod]] = None
    # With a single wallet per-wallet and universal application must produce the same result.
    same_as_universal: bool = False


def _fee_config(treatment: TransferFeeTreatment) -> PerWalletConfiguration:
    return PerWalletConfiguration(timezone_name="UTC", transfer_fee_treatment=treatment)


def _allocation_config(order: Tuple[Account, ...]) -> PerWalletConfiguration:
    return PerWalletConfiguration(timezone_name="UTC", unused_basis_allocation_method="fifo", unused_basis_allocation_wallet_order=order)


_COINBASE = Account("Coinbase", "Bob")
_KRAKEN = Account("Kraken", "Bob")


class TestPerWalletTaxEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None  # pylint: disable=invalid-name

    @staticmethod
    def _create_input_data(configuration: Configuration, transactions: List[object]) -> InputData:
        sets = {name: TransactionSet(configuration, name, _ASSET) for name in ("IN", "OUT", "INTRA")}
        for row, transaction in enumerate(transactions, start=1):
            if isinstance(transaction, _In):
                sets["IN"].add_entry(
                    InTransaction(
                        configuration,
                        transaction.timestamp,
                        _ASSET,
                        transaction.exchange,
                        "Bob",
                        transaction.transaction_type,
                        RP2Decimal(transaction.spot_price),
                        RP2Decimal(transaction.crypto_in),
                        fiat_fee=RP2Decimal(transaction.fiat_fee) if transaction.fiat_fee else None,
                        row=row,
                        unique_id=transaction.unique_id,
                    )
                )
            elif isinstance(transaction, _Out):
                sets["OUT"].add_entry(
                    OutTransaction(
                        configuration,
                        transaction.timestamp,
                        _ASSET,
                        transaction.exchange,
                        "Bob",
                        "Sell",
                        RP2Decimal(transaction.spot_price),
                        RP2Decimal(transaction.crypto_out_no_fee),
                        RP2Decimal(transaction.crypto_fee),
                        row=row,
                        unique_id=transaction.unique_id,
                    )
                )
            elif isinstance(transaction, _Intra):
                sets["INTRA"].add_entry(
                    IntraTransaction(
                        configuration,
                        transaction.timestamp,
                        _ASSET,
                        transaction.from_exchange,
                        "Bob",
                        transaction.to_exchange,
                        "Bob",
                        RP2Decimal(transaction.spot_price),
                        RP2Decimal(transaction.crypto_sent),
                        RP2Decimal(transaction.crypto_received),
                        row=row,
                        unique_id=transaction.unique_id,
                    )
                )
        return InputData(_ASSET, sets["IN"], sets["OUT"], sets["INTRA"])

    @staticmethod
    def _create_accounting_engine(years_2_methods: Optional[Dict[int, AbstractAccountingMethod]]) -> AccountingEngine:
        tree: AVLTree[int, AbstractAccountingMethod] = AVLTree()
        for year, method in (years_2_methods or {1970: AccountingMethodFIFO()}).items():
            tree.insert_node(year, method)
        return AccountingEngine(tree)

    @staticmethod
    def _to_tuples(gain_losses: List[GainLoss]) -> List[_GainLossTuple]:
        return [
            (
                gain_loss.taxable_event.unique_id,
                gain_loss.acquired_lot.original_lot.unique_id if gain_loss.acquired_lot else None,
                gain_loss.crypto_amount,
                gain_loss.fiat_cost_basis,
                gain_loss.fiat_gain,
                gain_loss.is_long_term_capital_gains(),
            )
            for gain_loss in gain_losses
        ]

    def _run_test(self, test: _Test, country: object = None) -> None:
        configuration = Configuration(_CONFIGURATION_PATH, country or US())  # type: ignore
        input_data = self._create_input_data(configuration, test.transactions)
        engine = self._create_accounting_engine(test.years_2_methods)
        if test.want_error:
            with self.assertRaisesRegex(RP2ValueError, test.want_error):
                compute_tax_per_wallet(configuration, engine, input_data, test.per_wallet_configuration, test.allocation_method)
            return
        computed_data = compute_tax_per_wallet(configuration, engine, input_data, test.per_wallet_configuration, test.allocation_method)
        got: List[_GainLossTuple] = self._to_tuples([gain_loss for gain_loss in computed_data.gain_loss_set if isinstance(gain_loss, GainLoss)])
        want: List[_GainLossTuple] = [
            (
                w.taxable_event_unique_id,
                w.acquired_lot_unique_id,
                RP2Decimal(w.crypto_amount),
                RP2Decimal(w.fiat_cost_basis),
                RP2Decimal(w.fiat_gain),
                w.is_long_term,
            )
            for w in test.want
        ]
        self.assertEqual(_sorted(got), _sorted(want))
        if test.same_as_universal:
            universal_computed_data = compute_tax(configuration, self._create_accounting_engine(test.years_2_methods), input_data)
            universal = self._to_tuples([gain_loss for gain_loss in universal_computed_data.gain_loss_set if isinstance(gain_loss, GainLoss)])
            self.assertEqual(_sorted(got), _sorted(universal))

    def test_per_wallet(self) -> None:  # pylint: disable=too-many-statements
        tests: List[_Test] = [
            _Test(
                description="Single wallet: a sale that exhausts a lot (this failed before the fix)",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _Out("o1", "2025-02-01T00:00:00+00:00", "Coinbase", "200", "10"),
                ],
                want=[_GainLoss("o1", "i1", "10", "1000", "1000", False)],
                same_as_universal=True,
            ),
            _Test(
                description="Single wallet: two sales exhausting one lot",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _Out("o1", "2025-02-01T00:00:00+00:00", "Coinbase", "200", "4"),
                    _Out("o2", "2025-03-01T00:00:00+00:00", "Coinbase", "200", "6"),
                ],
                want=[_GainLoss("o1", "i1", "4", "400", "400", False), _GainLoss("o2", "i1", "6", "600", "600", False)],
                same_as_universal=True,
            ),
            _Test(
                description="Earned crypto is income once: moving it to another wallet doesn't create income again",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Income", "100", "10"),
                    _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "150", "4", "4"),
                    _Out("o1", "2025-03-01T00:00:00+00:00", "Kraken", "200", "4"),
                ],
                want=[_GainLoss("i1", None, "10", "0", "1000", False), _GainLoss("o1", "i1", "4", "400", "400", False)],
            ),
            _Test(
                description="Purchase fee stays in the cost basis after a transfer",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10", fiat_fee="10"),
                    _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "150", "10", "10"),
                    _Out("o1", "2025-03-01T00:00:00+00:00", "Kraken", "200", "10"),
                ],
                want=[_GainLoss("o1", "i1", "10", "1010", "990", False)],
            ),
            _Test(
                description="FIFO within a wallet uses the original acquisition date, not the arrival date (Treas. Reg. §1.1012-1(j))",
                transactions=[
                    _In("i1", "2025-01-01T12:00:00+00:00", "Coinbase", "Buy", "100", "1"),
                    _In("i2", "2025-04-10T00:00:00+00:00", "Kraken", "Buy", "500", "1"),
                    _Intra("t1", "2025-07-19T00:00:00+00:00", "Coinbase", "Kraken", "550", "1", "1"),
                    _Out("o1", "2025-10-27T00:00:00+00:00", "Kraken", "600", "1"),
                ],
                want=[_GainLoss("o1", "i1", "1", "100", "500", False)],
            ),
            # The next three cases are worked examples from the Reddit threads linked in eprbell/rp2#135, with the answers given there by
            # a CPA (JustinCPA). Kraken and BlockFi stand in for hardware wallets.
            _Test(
                description="eprbell's question (reddit.com/r/CryptoTax/comments/1gbvfic/comment/ltvfqy7): with FIFO the round trip sells the $11000 lot",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "10000", "1"),
                    _In("i2", "2025-02-01T00:00:00+00:00", "Coinbase", "Buy", "11000", "1"),
                    _Intra("t1", "2025-03-01T00:00:00+00:00", "Coinbase", "Kraken", "12000", "1", "1"),
                    _Intra("t2", "2025-04-01T00:00:00+00:00", "Coinbase", "BlockFi", "13000", "1", "1"),
                    _Intra("t3", "2025-05-01T00:00:00+00:00", "BlockFi", "Coinbase", "14000", "1", "1"),
                    _Out("o1", "2025-06-01T00:00:00+00:00", "Coinbase", "20000", "1"),
                ],
                want=[_GainLoss("o1", "i2", "1", "11000", "9000", False)],
            ),
            _Test(
                description="eprbell's question with HIFO: transfers use the method of the year, so the $10000 lot comes back and is sold",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "10000", "1"),
                    _In("i2", "2025-02-01T00:00:00+00:00", "Coinbase", "Buy", "11000", "1"),
                    _Intra("t1", "2025-03-01T00:00:00+00:00", "Coinbase", "Kraken", "12000", "1", "1"),
                    _Intra("t2", "2025-04-01T00:00:00+00:00", "Coinbase", "BlockFi", "13000", "1", "1"),
                    _Intra("t3", "2025-05-01T00:00:00+00:00", "BlockFi", "Coinbase", "14000", "1", "1"),
                    _Out("o1", "2025-06-01T00:00:00+00:00", "Coinbase", "20000", "1"),
                ],
                years_2_methods={1970: AccountingMethodHIFO()},
                want=[_GainLoss("o1", "i1", "1", "10000", "10000", False)],
            ),
            _Test(
                description="gurtz135's question (reddit.com/r/CryptoTax/comments/1gbvfic/comment/m310q4a): units moved to Kraken keep their date",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _In("i2", "2025-02-01T00:00:00+00:00", "Kraken", "Buy", "200", "5"),
                    _Intra("t1", "2025-03-01T00:00:00+00:00", "Coinbase", "Kraken", "300", "4", "4"),
                    _Out("o1", "2025-04-01T00:00:00+00:00", "Kraken", "400", "2"),
                ],
                # "They retain their original holding period. So the 2BTC sold would be from Coinbase."
                want=[_GainLoss("o1", "i1", "2", "200", "600", False)],
            ),
            _Test(
                description="Metal450's question (reddit.com/r/CryptoTax/comments/1hk31yd/comment/m4w1hll): sale order A1, B, A2 by acquisition date",
                transactions=[
                    _In("a1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "1"),
                    _In("b1", "2025-02-01T00:00:00+00:00", "Kraken", "Buy", "200", "1"),
                    _In("a2", "2025-03-01T00:00:00+00:00", "Coinbase", "Buy", "300", "1"),
                    _Intra("t1", "2025-04-01T00:00:00+00:00", "Coinbase", "Kraken", "400", "2", "2"),
                    _Out("o1", "2025-05-01T00:00:00+00:00", "Kraken", "500", "1"),
                    _Out("o2", "2025-05-02T00:00:00+00:00", "Kraken", "500", "1"),
                    _Out("o3", "2025-05-03T00:00:00+00:00", "Kraken", "500", "1"),
                ],
                want=[
                    _GainLoss("o1", "a1", "1", "100", "400", False),
                    _GainLoss("o2", "b1", "1", "200", "300", False),
                    _GainLoss("o3", "a2", "1", "300", "200", False),
                ],
            ),
            _Test(
                description="Transfer fee paid in the transferred asset, treated as a disposal",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "150", "10", "9"),
                    _Out("o1", "2025-03-01T00:00:00+00:00", "Kraken", "200", "9"),
                ],
                per_wallet_configuration=_fee_config(TransferFeeTreatment.DISPOSAL),
                want=[_GainLoss("t1", "i1", "1", "100", "50", False), _GainLoss("o1", "i1", "9", "900", "900", False)],
            ),
            _Test(
                description="Transfer fee paid in the transferred asset, basis carried over to the received units",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "150", "10", "9"),
                    _Out("o1", "2025-03-01T00:00:00+00:00", "Kraken", "200", "9"),
                ],
                per_wallet_configuration=_fee_config(TransferFeeTreatment.BASIS_CARRYOVER),
                want=[_GainLoss("o1", "i1", "9", "1000", "800", False)],
            ),
            _Test(
                description="Transfer fee without an explicit fee treatment: error (unsettled US law, never picked silently)",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "150", "10", "9"),
                ],
                want_error="have a crypto fee, but 'transfer_fee_treatment' is not defined",
            ),
            _Test(
                description="Transfer fee spanning two lots (https://github.com/eprbell/rp2/issues/149)",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "5", "100"),
                    _In("i2", "2025-01-03T00:00:00+00:00", "Coinbase", "Buy", "3", "110"),
                    _Out("o0", "2025-01-04T00:00:00+00:00", "Coinbase", "6", "95"),
                    _Intra("t1", "2025-01-05T00:00:00+00:00", "Coinbase", "Kraken", "6", "7", "4"),
                    _Out("o1", "2025-01-06T00:00:00+00:00", "Kraken", "7", "4"),
                ],
                per_wallet_configuration=_fee_config(TransferFeeTreatment.DISPOSAL),
                # FIFO: i1 has 5 left after o0: the fee (3, proceeds 3 * 6 = 18) is paid first, with i1 units; the 4 received units are the
                # remaining 2 of i1 and 2 of i2.
                want=[
                    _GainLoss("o0", "i1", "95", "475", "95", False),
                    _GainLoss("t1", "i1", "3", "15", "3", False),
                    _GainLoss("o1", "i1", "2", "10", "4", False),
                    _GainLoss("o1", "i2", "2", "6", "8", False),
                ],
            ),
            _Test(
                description="Holding period is preserved through transfers: sold the day after the first anniversary is long term",
                transactions=[
                    _In("i1", "2024-03-01T00:00:00+00:00", "Coinbase", "Buy", "100", "1"),
                    _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "150", "1", "1"),
                    _Out("o1", "2025-03-02T00:00:00+00:00", "Kraken", "200", "1"),
                ],
                want=[_GainLoss("o1", "i1", "1", "100", "100", True)],
            ),
            _Test(
                description="Holding period is preserved through transfers: sold on the first anniversary is short term",
                transactions=[
                    _In("i1", "2024-03-01T00:00:00+00:00", "Coinbase", "Buy", "100", "1"),
                    _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "150", "1", "1"),
                    _Out("o1", "2025-03-01T00:00:00+00:00", "Kraken", "200", "1"),
                ],
                want=[_GainLoss("o1", "i1", "1", "100", "100", False)],
            ),
            _Test(
                description="A sale larger than the wallet balance is an error, even if another wallet has funds",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _In("i2", "2025-01-02T00:00:00+00:00", "Kraken", "Buy", "100", "10"),
                    _Out("o1", "2025-02-01T00:00:00+00:00", "Kraken", "200", "15"),
                ],
                want_error=r"Insufficient balance on Account\(exchange='Kraken', holder='Bob'\) to cover out transaction \(missing 5 of 15 B1\)",
            ),
            _Test(
                description="A transfer from a wallet that never received funds is an error (send with no prior receive)",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _Intra("t1", "2025-02-01T00:00:00+00:00", "Kraken", "Coinbase", "150", "1", "1"),
                ],
                want_error=r"Insufficient balance on Account\(exchange='Kraken', holder='Bob'\): no funds were ever received",
            ),
            _Test(
                description="Unused basis in two wallets at the switch without an allocation rule: error (Rev. Proc. 2024-28)",
                transactions=[
                    _In("i1", "2024-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _In("i2", "2024-01-03T00:00:00+00:00", "Kraken", "Buy", "200", "10"),
                    _Out("o1", "2025-02-01T00:00:00+00:00", "Kraken", "300", "5"),
                ],
                want_error="Unused basis allocation is needed",
            ),
            _Test(
                description="Unused basis allocation: FIFO lots, Kraken filled first, so Kraken gets the oldest lot (i1)",
                transactions=[
                    _In("i1", "2024-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _In("i2", "2024-01-03T00:00:00+00:00", "Kraken", "Buy", "200", "10"),
                    _Out("o1", "2025-02-01T00:00:00+00:00", "Kraken", "300", "5"),
                ],
                per_wallet_configuration=_allocation_config((_KRAKEN, _COINBASE)),
                allocation_method=AccountingMethodFIFO(),
                want=[_GainLoss("o1", "i1", "5", "500", "1000", True)],
            ),
            _Test(
                description="Unused basis allocation: HIFO lots, Kraken filled first, so Kraken gets the most expensive lot (i2)",
                transactions=[
                    _In("i1", "2024-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _In("i2", "2024-01-03T00:00:00+00:00", "Kraken", "Buy", "200", "10"),
                    _Out("o1", "2025-02-01T00:00:00+00:00", "Kraken", "300", "5"),
                ],
                per_wallet_configuration=_allocation_config((_KRAKEN, _COINBASE)),
                allocation_method=AccountingMethodHIFO(),
                want=[_GainLoss("o1", "i2", "5", "1000", "500", True)],
            ),
            _Test(
                # Rev. Proc. 2024-28 §3.04: "The acquisition date of a unit of unused basis is the acquisition date of the digital asset unit
                # to which the unit of unused basis was originally attached." Allocation moves basis and date together: it can't attach the
                # highest basis to the earliest date (as some allocation plans suggested in the threads linked in eprbell/rp2#135).
                description="Unused basis allocation keeps each basis with its own acquisition date: HIFO gives Kraken i2, sold short term",
                transactions=[
                    _In("i1", "2024-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _In("i2", "2024-06-01T00:00:00+00:00", "Kraken", "Buy", "200", "10"),
                    _Out("o1", "2025-02-01T00:00:00+00:00", "Kraken", "300", "5"),
                ],
                per_wallet_configuration=_allocation_config((_KRAKEN, _COINBASE)),
                allocation_method=AccountingMethodHIFO(),
                want=[_GainLoss("o1", "i2", "5", "1000", "500", False)],
            ),
            _Test(
                description="Per-asset wallet order override: B1 fills Coinbase first even though the default order fills Kraken first",
                transactions=[
                    _In("i1", "2024-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _In("i2", "2024-01-03T00:00:00+00:00", "Kraken", "Buy", "200", "10"),
                    _Out("o1", "2025-02-01T00:00:00+00:00", "Kraken", "300", "5"),
                ],
                per_wallet_configuration=PerWalletConfiguration(
                    timezone_name="UTC",
                    unused_basis_allocation_method="fifo",
                    unused_basis_allocation_wallet_order=(_KRAKEN, _COINBASE),
                    asset_2_unused_basis_allocation_wallet_order={_ASSET: (_COINBASE, _KRAKEN)},
                ),
                allocation_method=AccountingMethodFIFO(),
                # Coinbase is filled first with the oldest lot (i1), so Kraken gets i2.
                want=[_GainLoss("o1", "i2", "5", "1000", "500", True)],
            ),
            _Test(
                description="A per-asset override for another asset doesn't affect this one (the default order fills Kraken first)",
                transactions=[
                    _In("i1", "2024-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "10"),
                    _In("i2", "2024-01-03T00:00:00+00:00", "Kraken", "Buy", "200", "10"),
                    _Out("o1", "2025-02-01T00:00:00+00:00", "Kraken", "300", "5"),
                ],
                per_wallet_configuration=PerWalletConfiguration(
                    timezone_name="UTC",
                    unused_basis_allocation_method="fifo",
                    unused_basis_allocation_wallet_order=(_KRAKEN, _COINBASE),
                    asset_2_unused_basis_allocation_wallet_order={"B2": (_COINBASE, _KRAKEN)},
                ),
                allocation_method=AccountingMethodFIFO(),
                want=[_GainLoss("o1", "i1", "5", "500", "1000", True)],
            ),
            _Test(
                description="Before the switch universal application is unchanged (the 2023 Kraken sale uses the Coinbase lot)",
                transactions=[
                    _In("i1", "2023-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "2"),
                    _In("i2", "2023-02-02T00:00:00+00:00", "Kraken", "Buy", "300", "2"),
                    _Out("o1", "2023-06-01T00:00:00+00:00", "Kraken", "200", "1"),
                    _Out("o2", "2025-06-01T00:00:00+00:00", "Kraken", "400", "1"),
                ],
                per_wallet_configuration=_allocation_config((_COINBASE, _KRAKEN)),
                allocation_method=AccountingMethodFIFO(),
                # At the switch: unused i1 = 1, i2 = 2; Coinbase (balance 2) gets i1 (1) + i2 (1), Kraken (balance 1) gets i2 (1).
                want=[_GainLoss("o1", "i1", "1", "100", "100", False), _GainLoss("o2", "i2", "1", "300", "100", True)],
            ),
            _Test(
                description="Transfer in flight across the year boundary: its timestamp decides the wallet that holds the funds at the switch",
                transactions=[
                    _In("i1", "2024-06-01T00:00:00+00:00", "Coinbase", "Buy", "100", "1"),
                    _Intra("t1", "2024-12-31T23:30:00+00:00", "Coinbase", "Kraken", "150", "1", "1"),
                    _Out("o1", "2025-01-01T00:30:00+00:00", "Kraken", "200", "1"),
                ],
                want=[_GainLoss("o1", "i1", "1", "100", "100", False)],
            ),
            _Test(
                description="Timezone: 2025-01-01 03:00 JST is 2024 in New York: the transaction is ambiguous and must be fixed by the user",
                transactions=[
                    _In("i1", "2025-01-01T03:00:00+09:00", "Coinbase", "Buy", "100", "1"),
                    _Out("o1", "2025-02-01T00:00:00+00:00", "Coinbase", "200", "1"),
                ],
                per_wallet_configuration=PerWalletConfiguration(timezone_name="America/New_York"),
                want_error="fall in tax year 2025 .* but before the switch to per-wallet application",
            ),
            _Test(
                description="Timezone: 2025-01-01 03:00 JST with the switch in Tokyo time is per-wallet",
                transactions=[
                    _In("i1", "2025-01-01T03:00:00+09:00", "Coinbase", "Buy", "100", "1"),
                    _Out("o1", "2025-02-01T00:00:00+00:00", "Coinbase", "200", "1"),
                ],
                per_wallet_configuration=PerWalletConfiguration(timezone_name="Asia/Tokyo"),
                want=[_GainLoss("o1", "i1", "1", "100", "100", False)],
            ),
            _Test(
                description="Same timestamp: a transfer arriving at the same instant as a sale is available to the sale (In, Intra, Out order)",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "1"),
                    _Out("o1", "2025-02-01T00:00:00+00:00", "Kraken", "200", "1"),
                    _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "150", "1", "1"),
                ],
                want=[_GainLoss("o1", "i1", "1", "100", "100", False)],
            ),
            _Test(
                description="Multi-hop (CB->Kraken->BlockFi) and round trip (CB->Kraken->CB) on the same day keep basis and acquisition date",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "2"),
                    _Intra("t1", "2025-02-01T01:00:00+00:00", "Coinbase", "Kraken", "150", "2", "2"),
                    _Intra("t2", "2025-02-01T02:00:00+00:00", "Kraken", "BlockFi", "150", "1", "1"),
                    _Intra("t3", "2025-02-01T03:00:00+00:00", "Kraken", "Coinbase", "150", "1", "1"),
                    _Out("o1", "2025-03-01T00:00:00+00:00", "BlockFi", "200", "1"),
                    _Out("o2", "2025-03-02T00:00:00+00:00", "Coinbase", "300", "1"),
                ],
                want=[_GainLoss("o1", "i1", "1", "100", "100", False), _GainLoss("o2", "i1", "1", "100", "200", False)],
            ),
            _Test(
                description="Accounting method change across years: FIFO in 2025, HIFO in 2026",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "1"),
                    _In("i2", "2025-02-01T00:00:00+00:00", "Coinbase", "Buy", "300", "1"),
                    _In("i3", "2025-03-01T00:00:00+00:00", "Coinbase", "Buy", "200", "1"),
                    _Out("o1", "2025-06-01T00:00:00+00:00", "Coinbase", "400", "1"),
                    _Out("o2", "2026-06-01T00:00:00+00:00", "Coinbase", "400", "1"),
                ],
                years_2_methods={1970: AccountingMethodFIFO(), 2026: AccountingMethodHIFO()},
                want=[_GainLoss("o1", "i1", "1", "100", "300", False), _GainLoss("o2", "i2", "1", "300", "100", True)],
                same_as_universal=True,
            ),
            _Test(
                description="Staking income after the switch, then sold",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Staking", "10", "2"),
                    _Out("o1", "2025-02-01T00:00:00+00:00", "Coinbase", "15", "2"),
                ],
                want=[_GainLoss("i1", None, "2", "0", "20", False), _GainLoss("o1", "i1", "2", "20", "10", False)],
                same_as_universal=True,
            ),
            _Test(
                description="Decimal precision: dust transfers (3 x 0.1) are tracked exactly",
                transactions=[
                    _In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "3", "1"),
                    _Intra("t1", "2025-02-01T00:00:00+00:00", "Coinbase", "Kraken", "5", "0.1", "0.1"),
                    _Intra("t2", "2025-02-02T00:00:00+00:00", "Coinbase", "Kraken", "5", "0.1", "0.1"),
                    _Intra("t3", "2025-02-03T00:00:00+00:00", "Coinbase", "Kraken", "5", "0.1", "0.1"),
                    _Out("o1", "2025-03-01T00:00:00+00:00", "Kraken", "10", "0.3"),
                    _Out("o2", "2025-03-01T00:00:00+00:00", "Coinbase", "10", "0.7"),
                ],
                want=[
                    _GainLoss("o1", "i1", "0.1", "0.3", "0.7", False),
                    _GainLoss("o1", "i1", "0.1", "0.3", "0.7", False),
                    _GainLoss("o1", "i1", "0.1", "0.3", "0.7", False),
                    _GainLoss("o2", "i1", "0.7", "2.1", "4.9", False),
                ],
            ),
        ]
        for test in tests:
            with self.subTest(name=test.description):
                self._run_test(test)

    def test_per_wallet_is_rejected_for_japan(self) -> None:
        # Japan uses universal application (total/moving average, pooled across all wallets): per-wallet code must never run.
        self._run_test(
            _Test(
                description="JP",
                transactions=[_In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "1")],
                want_error="Per-wallet application is not supported for country 'jp'",
            ),
            country=JP(),
        )

    def test_per_wallet_start_year_must_match_the_country_policy(self) -> None:
        # The US policy switches to per-wallet application at the start of 2025: no other switch year is accepted.
        configuration = Configuration(_CONFIGURATION_PATH, US())
        input_data = self._create_input_data(configuration, [_In("i1", "2025-01-02T00:00:00+00:00", "Coinbase", "Buy", "100", "1")])
        engine = self._create_accounting_engine(None)
        for year in (2024, 2026):
            with self.subTest(year=year):
                with self.assertRaisesRegex(RP2ValueError, f"Per-wallet application can't start in {year} for country 'us'"):
                    compute_tax_per_wallet(configuration, engine, input_data, _UTC, per_wallet_start_year=year)
        computed_data = compute_tax_per_wallet(configuration, engine, input_data, _UTC, per_wallet_start_year=2025)
        self.assertEqual(len(list(computed_data.gain_loss_set)), 0)

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
            transfer_fee_treatment=TransferFeeTreatment.DISPOSAL,
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

    def test_artificial_in_transaction_is_not_income(self) -> None:
        configuration = Configuration(_CONFIGURATION_PATH, US())
        income = InTransaction(configuration, "2025-01-02T00:00:00+00:00", _ASSET, "Coinbase", "Bob", "Income", RP2Decimal("1"), RP2Decimal("1"))
        artificial = InTransaction(
            configuration, "2025-01-03T00:00:00+00:00", _ASSET, "Kraken", "Bob", "Income", RP2Decimal("1"), RP2Decimal("1"), from_lot=income
        )
        self.assertTrue(income.is_taxable())
        self.assertFalse(artificial.is_taxable())
        self.assertIs(artificial.original_lot, income)
        transactions: List[AbstractTransaction] = [artificial]
        self.assertFalse(any(transaction.is_earning() for transaction in transactions))


if __name__ == "__main__":
    unittest.main()
