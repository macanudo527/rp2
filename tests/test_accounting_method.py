# Copyright 2024 eprbell
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

import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from rp2.abstract_accounting_method import AbstractAccountingMethod
from rp2.configuration import Configuration
from rp2.in_transaction import InTransaction
from rp2.plugin.accounting_method.fifo import AccountingMethod as AccountingMethodFIFO
from rp2.plugin.accounting_method.hifo import AccountingMethod as AccountingMethodHIFO
from rp2.plugin.accounting_method.lifo import AccountingMethod as AccountingMethodLIFO
from rp2.plugin.accounting_method.lofo import AccountingMethod as AccountingMethodLOFO
from rp2.plugin.country.us import US
from rp2.rp2_decimal import RP2Decimal


@dataclass(frozen=True, eq=True)
class SeekLotResult:
    amount: int
    row: int


@dataclass(frozen=True, eq=True)
class InTransactionDescriptor:
    spot_price: int
    amount: int
    fiat_fee: int = 0
    transaction_type: str = "Buy"


@dataclass(frozen=True, eq=True)
class _Test:
    description: str
    lot_selection_method: AbstractAccountingMethod
    in_transactions: List[InTransactionDescriptor]
    amounts_to_match: List[int]
    want: List[SeekLotResult]


class TestAccountingMethod(unittest.TestCase):
    _configuration: Configuration

    @classmethod
    def setUpClass(cls) -> None:
        TestAccountingMethod._configuration = Configuration("./config/test_data.ini", US())

    def setUp(self) -> None:
        self.maxDiff = None  # pylint: disable=invalid-name

    def _initialize_acquired_lots(self, in_transaction_descriptors: List[InTransactionDescriptor]) -> List[InTransaction]:
        date = datetime.strptime("2021-01-01", "%Y-%m-%d")
        in_transactions: List[InTransaction] = []
        for i, desc in enumerate(in_transaction_descriptors):
            in_transactions.append(
                InTransaction(
                    self._configuration,
                    f"{date.isoformat()}Z",
                    "B1",
                    "Coinbase",
                    "Bob",
                    desc.transaction_type,
                    RP2Decimal(desc.spot_price),
                    RP2Decimal(desc.amount),
                    fiat_fee=RP2Decimal(desc.fiat_fee) if desc.fiat_fee else None,
                    row=1 + i,
                )
            )
            date += timedelta(days=1)
        return in_transactions

    # This function adds all acquired lots at first and then does amount pairings.
    def _run_test_fixed_lot_candidates(self, lot_selection_method: AbstractAccountingMethod, test: _Test) -> None:
        print(f"\nDescription: {test.description:}")
        in_transactions = self._initialize_acquired_lots(test.in_transactions)
        acquired_lot_candidates = lot_selection_method.create_lot_candidates(in_transactions, {})
        acquired_lot_candidates.set_to_index(len(in_transactions) - 1)
        i = 0
        for int_amount in test.amounts_to_match:
            amount = RP2Decimal(int_amount)
            while True:
                result = lot_selection_method.seek_non_exhausted_acquired_lot(acquired_lot_candidates, amount)
                if result is None:
                    break
                if result.amount >= amount:
                    acquired_lot_candidates.set_partial_amount(result.acquired_lot, result.amount - amount)
                    self.assertEqual(result.amount, RP2Decimal(test.want[i].amount))
                    self.assertEqual(result.acquired_lot.row, test.want[i].row)
                    i += 1
                    break
                acquired_lot_candidates.clear_partial_amount(result.acquired_lot)
                amount -= result.amount
                self.assertEqual(result.amount, RP2Decimal(test.want[i].amount))
                self.assertEqual(result.acquired_lot.row, test.want[i].row)
                i += 1

    # This function grows lot_candidates dynamically: it adds an acquired lot, does an amount pairing and repeats.
    def _run_test_dynamic_lot_candidates(self, lot_selection_method: AbstractAccountingMethod, test: _Test) -> None:
        print(f"\nDescription: {test.description:}")
        in_transactions = self._initialize_acquired_lots(test.in_transactions)
        acquired_lot_candidates = lot_selection_method.create_lot_candidates([], {})
        i = 0
        for int_amount in test.amounts_to_match:
            amount = RP2Decimal(int_amount)
            while True:
                if i < len(in_transactions):
                    acquired_lot_candidates.add_acquired_lot(in_transactions[i])
                    acquired_lot_candidates.set_to_index(i)
                result = lot_selection_method.seek_non_exhausted_acquired_lot(acquired_lot_candidates, amount)
                if result is None:
                    break
                if result.amount >= amount:
                    acquired_lot_candidates.set_partial_amount(result.acquired_lot, result.amount - amount)
                    self.assertEqual(result.amount, RP2Decimal(test.want[i].amount))
                    self.assertEqual(result.acquired_lot.row, test.want[i].row)
                    i += 1
                    break
                acquired_lot_candidates.clear_partial_amount(result.acquired_lot)
                amount -= result.amount
                self.assertEqual(result.amount, RP2Decimal(test.want[i].amount))
                self.assertEqual(result.acquired_lot.row, test.want[i].row)
                i += 1

    def test_with_fixed_lot_candidates(self) -> None:
        # Go-style, table-based tests. The want field contains the expected results.
        tests: List[_Test] = [
            _Test(
                description="Simple test (FIFO)",
                lot_selection_method=AccountingMethodFIFO(),
                in_transactions=[InTransactionDescriptor(10, 10), InTransactionDescriptor(11, 20), InTransactionDescriptor(12, 30)],
                amounts_to_match=[6, 4, 2, 18, 3],
                want=[SeekLotResult(10, 1), SeekLotResult(4, 1), SeekLotResult(20, 2), SeekLotResult(18, 2), SeekLotResult(30, 3)],
            ),
            _Test(
                description="Requested amount greater than acquired lot (FIFO)",
                lot_selection_method=AccountingMethodFIFO(),
                in_transactions=[InTransactionDescriptor(10, 10), InTransactionDescriptor(11, 20), InTransactionDescriptor(12, 30)],
                amounts_to_match=[15, 10, 5],
                want=[SeekLotResult(10, 1), SeekLotResult(20, 2), SeekLotResult(15, 2), SeekLotResult(5, 2)],
            ),
            _Test(
                description="Simple test (LIFO)",
                lot_selection_method=AccountingMethodLIFO(),
                in_transactions=[InTransactionDescriptor(10, 10), InTransactionDescriptor(11, 20), InTransactionDescriptor(12, 30)],
                amounts_to_match=[7, 23, 19, 1, 9],
                want=[SeekLotResult(30, 3), SeekLotResult(23, 3), SeekLotResult(20, 2), SeekLotResult(1, 2), SeekLotResult(10, 1)],
            ),
            _Test(
                description="Requested amount greater than acquired lot (LIFO)",
                lot_selection_method=AccountingMethodLIFO(),
                in_transactions=[InTransactionDescriptor(10, 10), InTransactionDescriptor(11, 20), InTransactionDescriptor(12, 30)],
                amounts_to_match=[55, 5],
                want=[SeekLotResult(30, 3), SeekLotResult(20, 2), SeekLotResult(10, 1), SeekLotResult(5, 1)],
            ),
            _Test(
                description="Simple test (HIFO)",
                lot_selection_method=AccountingMethodHIFO(),
                in_transactions=[InTransactionDescriptor(10, 10), InTransactionDescriptor(12, 20), InTransactionDescriptor(11, 30)],
                amounts_to_match=[15, 5, 20, 10, 7],
                want=[SeekLotResult(20, 2), SeekLotResult(5, 2), SeekLotResult(30, 3), SeekLotResult(10, 3), SeekLotResult(10, 1)],
            ),
            _Test(
                description="Requested amount greater than acquired lot (HIFO)",
                lot_selection_method=AccountingMethodHIFO(),
                in_transactions=[InTransactionDescriptor(10, 10), InTransactionDescriptor(12, 20), InTransactionDescriptor(11, 30)],
                amounts_to_match=[15, 5, 35, 5],
                want=[SeekLotResult(20, 2), SeekLotResult(5, 2), SeekLotResult(30, 3), SeekLotResult(10, 1), SeekLotResult(5, 1)],
            ),
            _Test(
                description="Simple test (LOFO)",
                lot_selection_method=AccountingMethodLOFO(),
                in_transactions=[InTransactionDescriptor(12, 10), InTransactionDescriptor(10, 20), InTransactionDescriptor(11, 30)],
                amounts_to_match=[15, 5, 20, 10, 7],
                want=[SeekLotResult(20, 2), SeekLotResult(5, 2), SeekLotResult(30, 3), SeekLotResult(10, 3), SeekLotResult(10, 1)],
            ),
            _Test(
                description="Requested amount greater than acquired lot (LOFO)",
                lot_selection_method=AccountingMethodLOFO(),
                in_transactions=[InTransactionDescriptor(12, 10), InTransactionDescriptor(10, 20), InTransactionDescriptor(11, 30)],
                amounts_to_match=[15, 5, 35, 5],
                want=[SeekLotResult(20, 2), SeekLotResult(5, 2), SeekLotResult(30, 3), SeekLotResult(10, 1), SeekLotResult(5, 1)],
            ),
            # --- Tests for Issue #150 / PR #151: lot ranking must use full cost per unit, not spot price alone ---
            #
            # The IRS says your "cost basis" (what you paid for an asset) must include the purchase
            # price AND any fees you paid to acquire it.  See IRS FAQ Q8 on virtual currency:
            # https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-virtual-currency-transactions
            #
            # HIFO (Highest In, First Out) and LOFO (Lowest In, First Out) are methods that let you
            # choose which "lot" (a batch of crypto bought in one transaction) to sell first, ranked
            # by cost.  To rank correctly, RP2 must use the full cost per unit:
            #
            #   cost_per_unit = (spot_price × quantity + all_fees) ÷ quantity
            #                 = spot_price + fees_per_unit
            #
            # Example: You buy 1 BTC at a market price (spot price) of $45,000 but also pay a
            # $10,000 broker fee.  Your real cost per unit is $55,000, not $45,000.  Under HIFO
            # this lot should be selected before another lot bought at $50,000 with no fee (real
            # cost = $50,000/unit).  Using spot price alone would rank them in the wrong order.
            _Test(
                # Lot 1 (row 1): market price $50, no fee  → real cost per unit = $50
                # Lot 2 (row 2): market price $45, $10 fee → real cost per unit = $55  ← highest total cost
                # HIFO (Highest In, First Out) must sell lot 2 first because it cost more per unit.
                # IRS authority: FAQ Q8 — basis includes fees
                # https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-virtual-currency-transactions
                description="HIFO (Highest In, First Out): a purchase fee makes the lower-priced lot cost more per unit overall, so HIFO sells it first (IRS FAQ Q8)",
                lot_selection_method=AccountingMethodHIFO(),
                in_transactions=[
                    InTransactionDescriptor(spot_price=50, amount=1, fiat_fee=0),
                    InTransactionDescriptor(spot_price=45, amount=1, fiat_fee=10),
                ],
                amounts_to_match=[2],
                want=[SeekLotResult(1, 2), SeekLotResult(1, 1)],
            ),
            _Test(
                # Lot 1 (row 1): market price $50, no fee  → real cost per unit = $50  ← lowest total cost
                # Lot 2 (row 2): market price $45, $10 fee → real cost per unit = $55
                # LOFO (Lowest In, First Out) must sell lot 1 first because it cost less per unit.
                # IRS authority: FAQ Q8 — basis includes fees
                # https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-virtual-currency-transactions
                description="LOFO (Lowest In, First Out): without a fee, the higher-priced lot costs less per unit overall, so LOFO sells it first (IRS FAQ Q8)",
                lot_selection_method=AccountingMethodLOFO(),
                in_transactions=[
                    InTransactionDescriptor(spot_price=50, amount=1, fiat_fee=0),
                    InTransactionDescriptor(spot_price=45, amount=1, fiat_fee=10),
                ],
                amounts_to_match=[2],
                want=[SeekLotResult(1, 1), SeekLotResult(1, 2)],
            ),
            _Test(
                # Lot 1 (row 1): mined at market price $60, no fee → real cost per unit = $60
                #   (mined coins have no purchase fee; their basis is the market value when received)
                # Lot 2 (row 2): purchased at market price $55, $10 fee → real cost per unit = $65
                # HIFO must sell the purchased lot first because it cost more per unit in total.
                # IRS authority:
                #   FAQ Q8 — basis includes fees
                #   https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-virtual-currency-transactions
                #   Rev. Rul. 2023-14 / FAQ Q57 — mined coins have a basis equal to fair market value at receipt
                #   https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-digital-asset-transactions
                description="HIFO: a purchase fee makes a bought lot cost more per unit than a mined lot at higher market price, so HIFO sells the purchased lot first (IRS FAQ Q8, Rev. Rul. 2023-14)",
                lot_selection_method=AccountingMethodHIFO(),
                in_transactions=[
                    InTransactionDescriptor(spot_price=60, amount=1, fiat_fee=0, transaction_type="Mining"),
                    InTransactionDescriptor(spot_price=55, amount=1, fiat_fee=10, transaction_type="Buy"),
                ],
                amounts_to_match=[2],
                want=[SeekLotResult(1, 2), SeekLotResult(1, 1)],
            ),
            _Test(
                # Lot 1 (row 1): mined at market price $60, no fee → real cost per unit = $60  ← lowest total cost
                # Lot 2 (row 2): purchased at market price $55, $10 fee → real cost per unit = $65
                # LOFO must sell the mined lot first because it cost less per unit in total.
                # IRS authority:
                #   FAQ Q8 — basis includes fees
                #   https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-virtual-currency-transactions
                #   Rev. Rul. 2023-14 / FAQ Q57 — mined coins have a basis equal to fair market value at receipt
                #   https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-digital-asset-transactions
                description="LOFO: a mined lot with no fee costs less per unit than a purchased lot with a fee, so LOFO sells the mined lot first (IRS FAQ Q8, Rev. Rul. 2023-14)",
                lot_selection_method=AccountingMethodLOFO(),
                in_transactions=[
                    InTransactionDescriptor(spot_price=60, amount=1, fiat_fee=0, transaction_type="Mining"),
                    InTransactionDescriptor(spot_price=55, amount=1, fiat_fee=10, transaction_type="Buy"),
                ],
                amounts_to_match=[2],
                want=[SeekLotResult(1, 1), SeekLotResult(1, 2)],
            ),
            _Test(
                # Lot 1 (row 1): market price $50, $5 fee → real cost per unit = $55, acquired day 1
                # Lot 2 (row 2): market price $50, $5 fee → real cost per unit = $55, acquired day 2
                # When two lots have exactly the same cost per unit, RP2 uses the older one first
                # (the one acquired earliest).  This is consistent with IRS specific-identification
                # rules which require traceable records; when cost is equal, chronological order is
                # a predictable and auditable tiebreaker.
                # IRS authority: FAQ Q39-Q40 — specific identification of lots
                # https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-virtual-currency-transactions
                description="HIFO: when two lots have exactly the same cost per unit (including fees), the older lot (earliest purchase date) is used first as a tiebreaker (IRS FAQ Q39-Q40)",
                lot_selection_method=AccountingMethodHIFO(),
                in_transactions=[
                    InTransactionDescriptor(spot_price=50, amount=1, fiat_fee=5),
                    InTransactionDescriptor(spot_price=50, amount=1, fiat_fee=5),
                ],
                amounts_to_match=[2],
                want=[SeekLotResult(1, 1), SeekLotResult(1, 2)],
            ),
            _Test(
                # Same setup as the HIFO tiebreaker test above — two lots with identical cost per
                # unit.  LOFO also falls back to oldest-first when costs are equal.
                # IRS authority: FAQ Q39-Q40 — specific identification of lots
                # https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-virtual-currency-transactions
                description="LOFO: when two lots have exactly the same cost per unit (including fees), the older lot (earliest purchase date) is used first as a tiebreaker (IRS FAQ Q39-Q40)",
                lot_selection_method=AccountingMethodLOFO(),
                in_transactions=[
                    InTransactionDescriptor(spot_price=50, amount=1, fiat_fee=5),
                    InTransactionDescriptor(spot_price=50, amount=1, fiat_fee=5),
                ],
                amounts_to_match=[2],
                want=[SeekLotResult(1, 1), SeekLotResult(1, 2)],
            ),
            _Test(
                # Lot 1 (row 1): market price $40, 3 units, $30 fee → real cost per unit = ($120+$30)/3 = $50
                # Lot 2 (row 2): market price $55, 2 units, no fee → real cost per unit = $55  ← highest total cost
                # HIFO sells lot 2 first (higher cost per unit).  Lot 2 only covers 2 of the 3
                # units needed in the first taxable event, so the engine splits across lots.
                # The remaining 2 units from lot 1 are then consumed in the second taxable event.
                # This verifies that cost-per-unit ranking is preserved correctly even when a lot
                # is only partially used.
                # IRS authority: FAQ Q8 — basis includes fees; FAQ Q39-Q40 — lot identification
                # https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-virtual-currency-transactions
                description="HIFO: when a lot is only partially used for one sale, cost-per-unit ranking (including fees) is preserved correctly for the next sale (IRS FAQ Q8, Q39-Q40)",
                lot_selection_method=AccountingMethodHIFO(),
                in_transactions=[
                    InTransactionDescriptor(spot_price=40, amount=3, fiat_fee=30),
                    InTransactionDescriptor(spot_price=55, amount=2, fiat_fee=0),
                ],
                amounts_to_match=[3, 2],
                # Sale 1 (need 3 units): lot 2 exhausted (2 units), then 1 unit taken from lot 1
                #   (seek returns the full lot-1 size of 3; the remaining 2 are tracked separately)
                # Sale 2 (need 2 units): the remaining 2 units from lot 1 are consumed
                want=[SeekLotResult(2, 2), SeekLotResult(3, 1), SeekLotResult(2, 1)],
            ),
        ]
        for test in tests:
            with self.subTest(name=f"{test.description}"):
                self._run_test_fixed_lot_candidates(lot_selection_method=test.lot_selection_method, test=test)

    def test_with_dynamic_lot_candidates(self) -> None:
        # Go-style, table-based tests. The want field contains the expected results.
        tests: List[_Test] = [
            _Test(
                description="Dynamic test (FIFO)",
                lot_selection_method=AccountingMethodFIFO(),
                in_transactions=[InTransactionDescriptor(10, 10), InTransactionDescriptor(11, 20), InTransactionDescriptor(12, 30)],
                amounts_to_match=[6, 4, 2, 18, 3],
                want=[SeekLotResult(10, 1), SeekLotResult(4, 1), SeekLotResult(20, 2), SeekLotResult(18, 2), SeekLotResult(30, 3)],
            ),
            _Test(
                description="Dynamic test (LIFO)",
                lot_selection_method=AccountingMethodLIFO(),
                in_transactions=[InTransactionDescriptor(10, 10), InTransactionDescriptor(11, 20), InTransactionDescriptor(12, 30)],
                amounts_to_match=[4, 15, 27, 14],
                want=[SeekLotResult(10, 1), SeekLotResult(20, 2), SeekLotResult(30, 3), SeekLotResult(3, 3), SeekLotResult(5, 2), SeekLotResult(6, 1)],
            ),
            _Test(
                description="Dynamic test (HIFO)",
                lot_selection_method=AccountingMethodHIFO(),
                in_transactions=[InTransactionDescriptor(10, 10), InTransactionDescriptor(12, 20), InTransactionDescriptor(11, 30)],
                amounts_to_match=[4, 16, 40],
                want=[SeekLotResult(10, 1), SeekLotResult(20, 2), SeekLotResult(4, 2), SeekLotResult(30, 3), SeekLotResult(6, 1)],
            ),
            _Test(
                description="Dynamic test (LOFO)",
                lot_selection_method=AccountingMethodLOFO(),
                in_transactions=[InTransactionDescriptor(12, 10), InTransactionDescriptor(10, 20), InTransactionDescriptor(11, 30)],
                amounts_to_match=[4, 16, 40],
                want=[SeekLotResult(10, 1), SeekLotResult(20, 2), SeekLotResult(4, 2), SeekLotResult(30, 3), SeekLotResult(6, 1)],
            ),
        ]
        for test in tests:
            with self.subTest(name=f"{test.description}"):
                self._run_test_dynamic_lot_candidates(lot_selection_method=test.lot_selection_method, test=test)


if __name__ == "__main__":
    unittest.main()
