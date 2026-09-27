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

# Property-based tests of per-wallet application: random, valid transaction histories across several wallets are generated and the
# following invariants are checked:
# - the lots of each wallet always add up to the wallet balance (checked after every transaction);
# - cost basis is conserved: basis acquired = basis disposed of + basis still held (with either transfer fee treatment);
# - no lot fraction is consumed twice: for every input lot, amount disposed of + amount still held (+ transfer fees, if carried over) equals
#   the lot amount;
# - with a single wallet, per-wallet and universal application produce the same gain/losses;
# - universal (e.g. JP) results are not affected by running the per-wallet code on the same input.

import unittest
from datetime import datetime, timedelta, timezone
from typing import Dict, List, NamedTuple, Set, Tuple

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from prezzemolo.avl_tree import AVLTree

from rp2.abstract_accounting_method import AbstractAccountingMethod
from rp2.account import Account
from rp2.accounting_engine import AccountingEngine
from rp2.configuration import Configuration
from rp2.gain_loss import GainLoss
from rp2.in_transaction import InTransaction
from rp2.input_data import InputData
from rp2.intra_transaction import IntraTransaction
from rp2.out_transaction import OutTransaction
from rp2.per_wallet_configuration import PerWalletConfiguration
from rp2.plugin.accounting_method.fifo import AccountingMethod as AccountingMethodFIFO
from rp2.plugin.accounting_method.hifo import AccountingMethod as AccountingMethodHIFO
from rp2.plugin.accounting_method.lifo import AccountingMethod as AccountingMethodLIFO
from rp2.plugin.accounting_method.lofo import AccountingMethod as AccountingMethodLOFO
from rp2.plugin.country.jp import JP
from rp2.plugin.country.us import US
from rp2.rp2_decimal import ZERO, RP2Decimal
from rp2.rp2_error import RP2ValueError
from rp2.tax_engine import compute_tax, compute_tax_per_wallet
from rp2.transaction_set import TransactionSet
from rp2.transfer_analyzer import TransferAnalyzer
from rp2.transfer_fee_treatment import TransferFeeTreatment

_ASSET = "B1"
_CONFIGURATION_PATH = "./config/test_data.ini"
_START = datetime(2025, 1, 1, tzinfo=timezone.utc)
_ACCOUNTS = [Account("Coinbase", "Bob"), Account("Kraken", "Bob"), Account("BlockFi", "Bob")]
_METHODS: Dict[str, AbstractAccountingMethod] = {
    "fifo": AccountingMethodFIFO(),
    "lifo": AccountingMethodLIFO(),
    "hifo": AccountingMethodHIFO(),
    "lofo": AccountingMethodLOFO(),
}
# Amounts are multiples of 0.001, to exercise lot splitting with non-integer amounts.
_QUANTUM = RP2Decimal("0.001")
_TOLERANCE = RP2Decimal("1e-12")


class _Step(NamedTuple):
    kind: str
    account: Account
    to_account: Account
    amount: RP2Decimal
    fee: RP2Decimal
    price: RP2Decimal
    transaction_type: str


def _amount(draw: st.DrawFn, maximum: RP2Decimal) -> RP2Decimal:
    return RP2Decimal(draw(st.integers(min_value=1, max_value=int(maximum / _QUANTUM)))) * _QUANTUM


@st.composite
def _histories(draw: st.DrawFn, accounts: List[Account]) -> List[_Step]:
    balances: Dict[Account, RP2Decimal] = {account: ZERO for account in accounts}
    steps: List[_Step] = []
    for _ in range(draw(st.integers(min_value=1, max_value=18))):
        funded = [account for account in accounts if balances[account] >= _QUANTUM * RP2Decimal("2")]
        kind = draw(st.sampled_from(["in", "out", "intra"])) if funded else "in"
        price = RP2Decimal(draw(st.integers(min_value=1, max_value=500)))
        if kind == "in":
            account = draw(st.sampled_from(accounts))
            amount = _amount(draw, RP2Decimal("10"))
            steps.append(_Step("in", account, account, amount, ZERO, price, draw(st.sampled_from(["Buy", "Buy", "Income", "Staking"]))))
            balances[account] += amount
        elif kind == "out":
            account = draw(st.sampled_from(funded))
            total = _amount(draw, balances[account])
            fee = _amount(draw, total) - _QUANTUM if total > _QUANTUM and draw(st.booleans()) else ZERO
            if fee >= total:
                fee = ZERO
            steps.append(_Step("out", account, account, total - fee, fee, price, "Sell"))
            balances[account] -= total
        else:
            account = draw(st.sampled_from(funded))
            to_account = draw(st.sampled_from(accounts))
            sent = _amount(draw, balances[account])
            fee = ZERO
            if draw(st.booleans()) and sent > _QUANTUM:
                fee = _amount(draw, sent - _QUANTUM)
            steps.append(_Step("intra", account, to_account, sent, fee, price, "Move"))
            balances[account] -= sent
            balances[to_account] += sent - fee
    return steps


def _create_input_data(configuration: Configuration, steps: List[_Step]) -> InputData:
    sets = {name: TransactionSet(configuration, name, _ASSET) for name in ("IN", "OUT", "INTRA")}
    for row, step in enumerate(steps, start=1):
        timestamp = (_START + timedelta(hours=row)).isoformat()
        if step.kind == "in":
            sets["IN"].add_entry(
                InTransaction(
                    configuration, timestamp, _ASSET, step.account.exchange, step.account.holder, step.transaction_type, step.price, step.amount, row=row
                )
            )
        elif step.kind == "out":
            sets["OUT"].add_entry(
                OutTransaction(configuration, timestamp, _ASSET, step.account.exchange, step.account.holder, "Sell", step.price, step.amount, step.fee, row=row)
            )
        else:
            sets["INTRA"].add_entry(
                IntraTransaction(
                    configuration,
                    timestamp,
                    _ASSET,
                    step.account.exchange,
                    step.account.holder,
                    step.to_account.exchange,
                    step.to_account.holder,
                    step.price,
                    step.amount,
                    step.amount - step.fee,
                    row=row,
                )
            )
    return InputData(_ASSET, sets["IN"], sets["OUT"], sets["INTRA"])


def _accounting_engine(method: AbstractAccountingMethod) -> AccountingEngine:
    tree: AVLTree[int, AbstractAccountingMethod] = AVLTree()
    tree.insert_node(1970, method)
    return AccountingEngine(tree)


def _balances(steps: List[_Step]) -> Dict[Account, RP2Decimal]:
    result: Dict[Account, RP2Decimal] = {}
    for step in steps:
        if step.kind == "in":
            result[step.account] = result.get(step.account, ZERO) + step.amount
        elif step.kind == "out":
            result[step.account] = result.get(step.account, ZERO) - step.amount - step.fee
        else:
            result[step.account] = result.get(step.account, ZERO) - step.amount
            result[step.to_account] = result.get(step.to_account, ZERO) + step.amount - step.fee
    return result


def _get_actual_amount(input_data: InputData, lot: object) -> RP2Decimal:
    assert isinstance(lot, InTransaction)
    return input_data.in_transaction_2_actual_amount.get(lot, lot.crypto_in)


def _universal_gain_losses(configuration: Configuration, input_data: InputData) -> List[Tuple[str, str, RP2Decimal, RP2Decimal]]:
    computed_data = compute_tax(configuration, _accounting_engine(AccountingMethodFIFO()), input_data)
    return sorted(_gain_loss_key(gain_loss) for gain_loss in computed_data.gain_loss_set if isinstance(gain_loss, GainLoss))


def _gain_loss_key(gain_loss: GainLoss) -> Tuple[str, str, RP2Decimal, RP2Decimal]:
    return (
        gain_loss.taxable_event.internal_id,
        gain_loss.acquired_lot.original_lot.internal_id if gain_loss.acquired_lot else "",
        gain_loss.crypto_amount,
        gain_loss.fiat_cost_basis,
    )


def _merge_gain_losses(gain_losses: List[GainLoss]) -> Dict[Tuple[str, str], Tuple[RP2Decimal, RP2Decimal]]:
    # Per-wallet may split a pairing in several pieces (one per artificial lot): merge them by (taxable event, original lot).
    result: Dict[Tuple[str, str], Tuple[RP2Decimal, RP2Decimal]] = {}
    for gain_loss in gain_losses:
        key = (gain_loss.taxable_event.internal_id, gain_loss.acquired_lot.original_lot.internal_id if gain_loss.acquired_lot else "")
        amount, basis = result.get(key, (ZERO, ZERO))
        result[key] = (amount + gain_loss.crypto_amount, basis + gain_loss.fiat_cost_basis)
    return result


_SETTINGS = settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])


class TestPerWalletProperties(unittest.TestCase):
    @_SETTINGS
    @given(steps=_histories(_ACCOUNTS), method_name=st.sampled_from(sorted(_METHODS)))
    def test_wallet_lots_add_up_to_wallet_balance_after_every_transaction(self, steps: List[_Step], method_name: str) -> None:
        configuration = Configuration(_CONFIGURATION_PATH, US())
        for length in range(1, len(steps) + 1):
            prefix = steps[:length]
            if all(step.kind != "in" for step in prefix):
                continue
            result = TransferAnalyzer(configuration, _METHODS[method_name], _create_input_data(configuration, prefix)).analyze_and_pair()
            balances = _balances(prefix)
            for account, input_data in result.wallet_2_input_data.items():
                held = RP2Decimal(sum((_get_actual_amount(input_data, lot) for lot in input_data.unfiltered_in_transaction_set), ZERO))
                self.assertEqual(held, balances.get(account, ZERO), msg=f"{account} after {length} transactions")

    @_SETTINGS
    @given(
        steps=_histories(_ACCOUNTS),
        method_name=st.sampled_from(sorted(_METHODS)),
        treatment=st.sampled_from(list(TransferFeeTreatment)),
    )
    def test_basis_and_lot_amounts_are_conserved(self, steps: List[_Step], method_name: str, treatment: TransferFeeTreatment) -> None:
        configuration = Configuration(_CONFIGURATION_PATH, US())
        input_data = _create_input_data(configuration, steps)
        try:
            result = TransferAnalyzer(configuration, _METHODS[method_name], input_data, transfer_fee_treatment=treatment).analyze_and_pair()
        except RP2ValueError as error:
            # The only legitimate failure: basis carryover on a self-transfer with a fee (no destination lot to carry the basis to).
            self.assertEqual(treatment, TransferFeeTreatment.BASIS_CARRYOVER)
            self.assertIn("cannot be applied to a self-transfer with a fee", str(error))
            return

        # Amounts and basis still held, per original lot.
        held_amount: Dict[InTransaction, RP2Decimal] = {}
        held_basis = ZERO
        for per_wallet_input_data in result.wallet_2_input_data.values():
            for entry in per_wallet_input_data.unfiltered_in_transaction_set:
                lot = entry
                assert isinstance(lot, InTransaction)
                amount = per_wallet_input_data.in_transaction_2_actual_amount.get(lot, lot.crypto_in)
                held_amount[lot.original_lot] = held_amount.get(lot.original_lot, ZERO) + amount
                held_basis += lot.fiat_in_with_fee * amount / lot.crypto_in

        disposed_amount: Dict[InTransaction, RP2Decimal] = {}
        disposed_basis = ZERO
        seen: Set[Tuple[str, str]] = set()
        for gain_loss in result.gain_loss_list:
            # A taxable event is paired with a given lot at most once.
            key = (gain_loss.internal_id, "")
            self.assertNotIn(key, seen)
            seen.add(key)
            if gain_loss.acquired_lot is None:
                continue
            original_lot = gain_loss.acquired_lot.original_lot
            disposed_amount[original_lot] = disposed_amount.get(original_lot, ZERO) + gain_loss.crypto_amount
            disposed_basis += gain_loss.fiat_cost_basis

        acquired_basis = RP2Decimal(sum((lot.fiat_in_with_fee for lot in input_data.unfiltered_in_transaction_set), ZERO))  # type: ignore
        self.assertLess(abs(acquired_basis - disposed_basis - held_basis), _TOLERANCE * max(acquired_basis, RP2Decimal("1")))

        total_fees = RP2Decimal(sum((step.fee for step in steps if step.kind == "intra"), ZERO))
        for entry in input_data.unfiltered_in_transaction_set:
            lot = entry
            assert isinstance(lot, InTransaction)
            accounted = disposed_amount.get(lot, ZERO) + held_amount.get(lot, ZERO)
            if treatment == TransferFeeTreatment.DISPOSAL:
                self.assertEqual(accounted, lot.crypto_in, msg=f"lot {lot.internal_id}")
            else:
                # Carried-over fee units leave the lot without a gain/loss.
                self.assertLessEqual(accounted, lot.crypto_in)
        if treatment == TransferFeeTreatment.BASIS_CARRYOVER:
            total_accounted = RP2Decimal(sum(disposed_amount.values(), ZERO)) + RP2Decimal(sum(held_amount.values(), ZERO))
            total_in = RP2Decimal(sum((lot.crypto_in for lot in input_data.unfiltered_in_transaction_set), ZERO))  # type: ignore
            self.assertEqual(total_accounted + total_fees, total_in)

    @_SETTINGS
    @given(steps=_histories([_ACCOUNTS[0]]), method_name=st.sampled_from(sorted(_METHODS)))
    def test_single_wallet_per_wallet_equals_universal(self, steps: List[_Step], method_name: str) -> None:
        configuration = Configuration(_CONFIGURATION_PATH, US())
        input_data = _create_input_data(configuration, steps)
        per_wallet_configuration = PerWalletConfiguration(timezone_name="UTC", transfer_fee_treatment=TransferFeeTreatment.DISPOSAL)
        per_wallet = compute_tax_per_wallet(configuration, _accounting_engine(_METHODS[method_name]), input_data, per_wallet_configuration)
        universal = compute_tax(configuration, _accounting_engine(_METHODS[method_name]), input_data)
        per_wallet_gain_losses = [gain_loss for gain_loss in per_wallet.gain_loss_set if isinstance(gain_loss, GainLoss)]
        universal_gain_losses = [gain_loss for gain_loss in universal.gain_loss_set if isinstance(gain_loss, GainLoss)]
        self.assertEqual(_merge_gain_losses(per_wallet_gain_losses), _merge_gain_losses(universal_gain_losses))
        self.assertEqual(
            [(y.year, y.transaction_type, y.is_long_term_capital_gains, y.crypto_amount, y.fiat_gain_loss) for y in per_wallet.yearly_gain_loss_list],
            [(y.year, y.transaction_type, y.is_long_term_capital_gains, y.crypto_amount, y.fiat_gain_loss) for y in universal.yearly_gain_loss_list],
        )

    @_SETTINGS
    @given(steps=_histories(_ACCOUNTS))
    def test_universal_jp_results_are_not_affected_by_per_wallet_code(self, steps: List[_Step]) -> None:
        jp_configuration = Configuration(_CONFIGURATION_PATH, JP())
        input_data = _create_input_data(jp_configuration, steps)
        before = _universal_gain_losses(jp_configuration, input_data)
        # Per-wallet code must refuse to run for JP...
        with self.assertRaisesRegex(RP2ValueError, "not supported for country 'jp'"):
            compute_tax_per_wallet(jp_configuration, _accounting_engine(AccountingMethodFIFO()), input_data, PerWalletConfiguration(timezone_name="Asia/Tokyo"))
        # ... and running it anyway on the same objects (it mutates to_lots of the input lots) must not change universal results.
        TransferAnalyzer(jp_configuration, AccountingMethodFIFO(), input_data, transfer_fee_treatment=TransferFeeTreatment.DISPOSAL).analyze_and_pair()
        self.assertEqual(before, _universal_gain_losses(jp_configuration, input_data))


if __name__ == "__main__":
    unittest.main()
