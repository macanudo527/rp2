# Copyright 2021 eprbell
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

from datetime import datetime
from typing import Dict, Iterable, Iterator, List, Optional, cast

from rp2.abstract_accounting_method import AbstractAccountingMethod
from rp2.abstract_transaction import AbstractTransaction
from rp2.account import Account
from rp2.accounting_engine import (
    AccountingEngine,
    AcquiredLotsExhaustedException,
    TaxableEventAndAcquiredLot,
    TaxableEventsExhaustedException,
)
from rp2.balance import CRYPTO_BALANCE_DECIMAL_MASK
from rp2.computed_data import ComputedData
from rp2.configuration import MAX_DATE, MIN_DATE, Configuration
from rp2.gain_loss import GainLoss
from rp2.gain_loss_set import GainLossSet
from rp2.in_transaction import InTransaction
from rp2.input_data import InputData
from rp2.intra_transaction import IntraTransaction
from rp2.logger import LOGGER
from rp2.out_transaction import OutTransaction
from rp2.per_wallet_configuration import PerWalletConfiguration
from rp2.rp2_decimal import ZERO, RP2Decimal
from rp2.rp2_error import RP2RuntimeError, RP2ValueError
from rp2.transaction_set import TransactionSet
from rp2.transfer_analyzer import TransferAnalyzer
from rp2.transfer_fee_treatment import TransferFeeTreatment
from rp2.unused_basis_allocator import UnusedBasisAllocator, UnusedLot


def compute_tax(configuration: Configuration, accounting_engine: AccountingEngine, input_data: InputData) -> ComputedData:
    Configuration.type_check("configuration", configuration)
    AccountingEngine.type_check("accounting_engine", accounting_engine)
    InputData.type_check("input_data", input_data)

    unfiltered_taxable_event_set: TransactionSet = input_data.create_unfiltered_taxable_event_set(configuration)
    LOGGER.debug("%s: Created taxable event set", input_data.asset)
    unfiltered_gain_loss_set: GainLossSet = _create_unfiltered_gain_and_loss_set(configuration, accounting_engine, input_data, unfiltered_taxable_event_set)
    LOGGER.debug("%s: Created gain-loss set", input_data.asset)

    return ComputedData(
        input_data.asset,
        unfiltered_taxable_event_set,
        unfiltered_gain_loss_set,
        input_data,
        configuration.from_date,
        configuration.to_date,
    )


def _get_next_taxable_event_and_acquired_lot(
    accounting_engine: AccountingEngine,
    taxable_event: Optional[AbstractTransaction],
    acquired_lot: Optional[InTransaction],
    taxable_event_amount: RP2Decimal,
    acquired_lot_amount: RP2Decimal,
) -> TaxableEventAndAcquiredLot:
    new_taxable_event: AbstractTransaction
    new_acquired_lot: Optional[InTransaction]
    new_taxable_event_amount: RP2Decimal
    new_acquired_lot_amount: RP2Decimal
    new_taxable_event, new_acquired_lot, new_taxable_event_amount, new_acquired_lot_amount = accounting_engine.get_next_taxable_event_and_amount(
        taxable_event, acquired_lot, taxable_event_amount, acquired_lot_amount
    )
    if acquired_lot == new_acquired_lot:
        _, new_acquired_lot, _, new_acquired_lot_amount = accounting_engine.get_acquired_lot_for_taxable_event(
            new_taxable_event, new_acquired_lot, new_taxable_event_amount, new_acquired_lot_amount
        )
    return TaxableEventAndAcquiredLot(new_taxable_event, new_acquired_lot, new_taxable_event_amount, new_acquired_lot_amount)


def _create_unfiltered_gain_and_loss_set(
    configuration: Configuration, accounting_engine: AccountingEngine, input_data: InputData, unfiltered_taxable_event_set: TransactionSet
) -> GainLossSet:
    gain_loss_set: GainLossSet = GainLossSet(configuration, input_data.asset, MIN_DATE, MAX_DATE)
    # Create a fresh instance of accounting engine
    new_accounting_engine: AccountingEngine = accounting_engine.__class__(accounting_engine.years_2_methods)
    taxable_event_iterator: Iterator[AbstractTransaction] = iter(cast(Iterable[AbstractTransaction], unfiltered_taxable_event_set))
    acquired_lot_iterator: Iterator[InTransaction] = iter(cast(Iterable[InTransaction], input_data.unfiltered_in_transaction_set))

    partial_amounts = input_data.in_transaction_2_actual_amount
    new_accounting_engine.initialize(taxable_event_iterator, acquired_lot_iterator, partial_amounts if partial_amounts else None)

    try:
        gain_loss: GainLoss
        taxable_event: AbstractTransaction
        acquired_lot: Optional[InTransaction]
        taxable_event_amount: RP2Decimal
        acquired_lot_amount: RP2Decimal
        total_amount: RP2Decimal = ZERO

        # Retrieve first taxable event and acquired lot
        taxable_event, acquired_lot, taxable_event_amount, acquired_lot_amount = _get_next_taxable_event_and_acquired_lot(
            new_accounting_engine, None, None, ZERO, ZERO
        )

        while taxable_event:
            # Type check values returned by accounting method plugin
            AbstractTransaction.type_check("taxable_event", taxable_event)
            if acquired_lot is None:
                # There must always be at least one acquired_lot
                raise RP2RuntimeError("Parameter 'acquired_lot' is None")
            InTransaction.type_check("acquired_lot", acquired_lot)
            Configuration.type_check_positive_decimal("taxable_event_amount", taxable_event_amount)
            Configuration.type_check_positive_decimal("acquired_lot_amount", acquired_lot_amount)

            if taxable_event.is_earning():
                # Handle earnings first: they have no acquired-lot
                gain_loss = GainLoss(configuration, taxable_event_amount, taxable_event, None)
                LOGGER.debug(
                    "tax_engine: taxable is earn: %s / %s + %s = %s: %s",
                    taxable_event_amount,
                    total_amount,
                    taxable_event_amount,
                    total_amount + taxable_event_amount,
                    gain_loss,
                )
                total_amount += taxable_event_amount
                gain_loss_set.add_entry(gain_loss)
                taxable_event, acquired_lot, taxable_event_amount, acquired_lot_amount = new_accounting_engine.get_next_taxable_event_and_amount(
                    taxable_event, acquired_lot, ZERO, acquired_lot_amount
                )
                continue
            if taxable_event_amount == acquired_lot_amount:
                gain_loss = GainLoss(configuration, taxable_event_amount, taxable_event, acquired_lot)
                LOGGER.debug(
                    "tax_engine: taxable == acquired: %s == %s / %s + %s = %s: %s",
                    taxable_event_amount,
                    acquired_lot_amount,
                    total_amount,
                    taxable_event_amount,
                    total_amount + taxable_event_amount,
                    gain_loss,
                )
                total_amount += taxable_event_amount
                gain_loss_set.add_entry(gain_loss)
                taxable_event, acquired_lot, taxable_event_amount, acquired_lot_amount = _get_next_taxable_event_and_acquired_lot(
                    new_accounting_engine, taxable_event, acquired_lot, taxable_event_amount, acquired_lot_amount
                )
            elif taxable_event_amount < acquired_lot_amount:
                gain_loss = GainLoss(configuration, taxable_event_amount, taxable_event, acquired_lot)
                LOGGER.debug(
                    "tax_engine: taxable < acquired: %s < %s / %s + %s = %s: %s",
                    taxable_event_amount,
                    acquired_lot_amount,
                    total_amount,
                    taxable_event_amount,
                    total_amount + taxable_event_amount,
                    gain_loss,
                )
                total_amount += taxable_event_amount
                gain_loss_set.add_entry(gain_loss)
                taxable_event, acquired_lot, taxable_event_amount, acquired_lot_amount = new_accounting_engine.get_next_taxable_event_and_amount(
                    taxable_event, acquired_lot, taxable_event_amount, acquired_lot_amount
                )
            else:  # taxable_amount > acquired_lot_amount
                gain_loss = GainLoss(configuration, acquired_lot_amount, taxable_event, acquired_lot)
                LOGGER.debug(
                    "tax_engine: taxable > acquired: %s > %s / %s + %s = %s: %s",
                    taxable_event_amount,
                    acquired_lot_amount,
                    total_amount,
                    acquired_lot_amount,
                    total_amount + acquired_lot_amount,
                    gain_loss,
                )
                total_amount += acquired_lot_amount
                gain_loss_set.add_entry(gain_loss)
                taxable_event, acquired_lot, taxable_event_amount, acquired_lot_amount = new_accounting_engine.get_acquired_lot_for_taxable_event(
                    taxable_event, acquired_lot, taxable_event_amount, acquired_lot_amount
                )

    except AcquiredLotsExhaustedException:
        raise RP2ValueError("Total in-transaction crypto value < total taxable crypto value") from None
    except TaxableEventsExhaustedException:
        pass

    return gain_loss_set


# Per-wallet application (e.g. US from 2025, Treas. Reg. §1.1012-1(j)). Tax years before the country's per-wallet start year use universal
# application, exactly as compute_tax() does. At the switch (January 1 of the start year, in the configured timezone):
# - the lots that are still unused under universal application are allocated to the wallets that hold funds (Rev. Proc. 2024-28 global
#   allocation, see UnusedBasisAllocator);
# - from then on TransferAnalyzer tracks lots per wallet and pairs every taxable event with lots of its own wallet.
# allocation_method is the unused basis allocation method of this asset (see PerWalletConfiguration.get_unused_basis_allocation_method()).
def compute_tax_per_wallet(
    configuration: Configuration,
    accounting_engine: AccountingEngine,
    input_data: InputData,
    per_wallet_configuration: PerWalletConfiguration,
    allocation_method: Optional[AbstractAccountingMethod] = None,
) -> ComputedData:
    Configuration.type_check("configuration", configuration)
    AccountingEngine.type_check("accounting_engine", accounting_engine)
    InputData.type_check("input_data", input_data)
    PerWalletConfiguration.type_check("per_wallet_configuration", per_wallet_configuration)

    start_year = configuration.country.get_per_wallet_application_start_year()
    if start_year is None:
        raise RP2ValueError(f"Per-wallet application is not supported for country '{configuration.country.country_iso_code}'")
    switch_timestamp = datetime(start_year, 1, 1, tzinfo=per_wallet_configuration.timezone)

    all_transactions = list(cast(Iterable[AbstractTransaction], input_data.create_all_transaction_set(configuration)))
    _check_tax_year_boundary(all_transactions, switch_timestamp, start_year, per_wallet_configuration.timezone_name)
    universal_transactions = [transaction for transaction in all_transactions if transaction.timestamp < switch_timestamp]
    per_wallet_transactions = [transaction for transaction in all_transactions if transaction.timestamp >= switch_timestamp]

    # Universal application before the switch.
    taxable_events: List[AbstractTransaction] = []
    gain_loss_list: List[GainLoss] = []
    universal_input_data: Optional[InputData] = None
    if universal_transactions:
        universal_input_data = _create_input_data(configuration, input_data.asset, universal_transactions)
        universal_taxable_event_set = universal_input_data.create_unfiltered_taxable_event_set(configuration)
        taxable_events.extend(cast(Iterable[AbstractTransaction], universal_taxable_event_set))
        gain_loss_list.extend(
            cast(Iterable[GainLoss], _create_unfiltered_gain_and_loss_set(configuration, accounting_engine, universal_input_data, universal_taxable_event_set))
        )

    # Per-wallet application from the switch on.
    if per_wallet_transactions:
        LOGGER.info("%s: per-wallet application from %s (%d transactions)", input_data.asset, switch_timestamp, len(per_wallet_transactions))
        allocated_lots: List[InTransaction] = []
        if universal_input_data is not None:
            unused_lots = _get_unused_lots(universal_input_data, gain_loss_list)
            allocated_lots = UnusedBasisAllocator(
                configuration,
                switch_timestamp,
                unused_lots,
                _get_account_balances(universal_transactions, unused_lots),
                allocation_method,
                list(per_wallet_configuration.get_unused_basis_allocation_wallet_order(input_data.asset)),
            ).allocate()
        transfer_fee_treatment = _get_transfer_fee_treatment(per_wallet_transactions, per_wallet_configuration)
        per_wallet_input_data = _create_input_data(configuration, input_data.asset, per_wallet_transactions + cast(List[AbstractTransaction], allocated_lots))
        start_year_accounting_method = accounting_engine.years_2_methods.find_max_value_less_than(start_year)
        if start_year_accounting_method is None:
            raise RP2RuntimeError(f"Internal error: no accounting method assigned for year {start_year}")
        transfer_analysis_result = TransferAnalyzer(
            configuration,
            start_year_accounting_method,
            per_wallet_input_data,
            years_2_accounting_methods=accounting_engine.years_2_methods,
            transfer_fee_treatment=transfer_fee_treatment,
        ).analyze_and_pair()
        LOGGER.info("%s: per-wallet application: found %d wallets", input_data.asset, len(transfer_analysis_result.wallet_2_input_data))
        gain_loss_list.extend(transfer_analysis_result.gain_loss_list)
        taxable_events.extend(
            transaction
            for transaction in per_wallet_transactions
            if transaction.is_taxable() and not (isinstance(transaction, IntraTransaction) and transfer_fee_treatment == TransferFeeTreatment.BASIS_CARRYOVER)
        )

    taxable_event_set = TransactionSet(configuration, "MIXED", input_data.asset, MIN_DATE, MAX_DATE)
    for transaction in taxable_events:
        taxable_event_set.add_entry(transaction)
    gain_loss_set = GainLossSet(configuration, input_data.asset, MIN_DATE, MAX_DATE)
    for gain_loss in gain_loss_list:
        gain_loss_set.add_entry(gain_loss)

    return ComputedData(
        input_data.asset,
        taxable_event_set,
        gain_loss_set,
        input_data,
        configuration.from_date,
        configuration.to_date,
    )


# The tax year of a transaction is the year of its timestamp (in the timezone of the timestamp itself). A transaction whose tax year is on
# one side of the switch while its instant is on the other side is ambiguous: rather than silently picking one, raise an error.
def _check_tax_year_boundary(transactions: List[AbstractTransaction], switch_timestamp: datetime, start_year: int, timezone_name: str) -> None:
    ambiguous_transactions = [
        transaction for transaction in transactions if (transaction.timestamp < switch_timestamp) != (transaction.timestamp.year < start_year)
    ]
    if ambiguous_transactions:
        raise RP2ValueError(
            f"{len(ambiguous_transactions)} transaction(s) fall in tax year {start_year} (or later) by their own timestamp but before the switch to "
            f"per-wallet application ({switch_timestamp}, timezone '{timezone_name}'), or vice versa: express their timestamps in timezone "
            f"'{timezone_name}' or change the timezone in the per_wallet section of the configuration file. "
            f"First one: {ambiguous_transactions[0]}"
        )


def _create_input_data(configuration: Configuration, asset: str, transactions: List[AbstractTransaction]) -> InputData:
    in_transaction_set = TransactionSet(configuration, "IN", asset, MIN_DATE, MAX_DATE)
    out_transaction_set = TransactionSet(configuration, "OUT", asset, MIN_DATE, MAX_DATE)
    intra_transaction_set = TransactionSet(configuration, "INTRA", asset, MIN_DATE, MAX_DATE)
    for transaction in transactions:
        if isinstance(transaction, InTransaction):
            in_transaction_set.add_entry(transaction)
        elif isinstance(transaction, OutTransaction):
            out_transaction_set.add_entry(transaction)
        elif isinstance(transaction, IntraTransaction):
            intra_transaction_set.add_entry(transaction)
        else:
            raise RP2RuntimeError(f"Internal error: invalid transaction class: {transaction}")
    if in_transaction_set.is_empty():
        raise RP2ValueError(f"{asset}: insufficient balance: there are disposals or transfers, but no acquisitions, before them: {transactions[0]}")
    return InputData(asset, in_transaction_set, out_transaction_set, intra_transaction_set)


# Lots (and amounts) not disposed of under universal application.
def _get_unused_lots(universal_input_data: InputData, gain_loss_list: List[GainLoss]) -> List[UnusedLot]:
    lot_2_used_amount: Dict[InTransaction, RP2Decimal] = {}
    for gain_loss in gain_loss_list:
        if gain_loss.acquired_lot is not None:
            lot_2_used_amount[gain_loss.acquired_lot] = lot_2_used_amount.get(gain_loss.acquired_lot, ZERO) + gain_loss.crypto_amount
    result: List[UnusedLot] = []
    for entry in universal_input_data.unfiltered_in_transaction_set:
        lot = cast(InTransaction, entry)
        amount = lot.crypto_in - lot_2_used_amount.get(lot, ZERO)
        if amount > ZERO:
            result.append(UnusedLot(lot, amount))
    return result


# Balance of each wallet at the switch. It must match the unused lots: if it doesn't, the input is inconsistent (e.g. negative balances).
def _get_account_balances(transactions: List[AbstractTransaction], unused_lots: List[UnusedLot]) -> Dict[Account, RP2Decimal]:
    result: Dict[Account, RP2Decimal] = {}
    for transaction in transactions:
        if isinstance(transaction, InTransaction):
            account = Account(transaction.exchange, transaction.holder)
            result[account] = result.get(account, ZERO) + transaction.crypto_in
        elif isinstance(transaction, OutTransaction):
            account = Account(transaction.exchange, transaction.holder)
            result[account] = result.get(account, ZERO) - transaction.crypto_out_with_fee
        elif isinstance(transaction, IntraTransaction):
            from_account = Account(transaction.from_exchange, transaction.from_holder)
            to_account = Account(transaction.to_exchange, transaction.to_holder)
            result[from_account] = result.get(from_account, ZERO) - transaction.crypto_sent
            result[to_account] = result.get(to_account, ZERO) + transaction.crypto_received
    for account, balance in result.items():
        if balance < ZERO and not RP2Decimal.is_equal_within_precision(balance, ZERO, CRYPTO_BALANCE_DECIMAL_MASK):
            raise RP2ValueError(f"Balance of {account.exchange}/{account.holder} is negative ({balance}) at the switch to per-wallet application")
    total_balance = RP2Decimal(sum((balance for balance in result.values() if balance > ZERO), ZERO))
    total_unused = RP2Decimal(sum((unused_lot.amount for unused_lot in unused_lots), ZERO))
    if not RP2Decimal.is_equal_within_precision(total_balance, total_unused, CRYPTO_BALANCE_DECIMAL_MASK):
        raise RP2ValueError(f"Total wallet balance ({total_balance}) doesn't match unused lot amount ({total_unused}) at the switch to per-wallet application")
    return result


def _get_transfer_fee_treatment(transactions: List[AbstractTransaction], per_wallet_configuration: PerWalletConfiguration) -> TransferFeeTreatment:
    if per_wallet_configuration.transfer_fee_treatment is not None:
        return per_wallet_configuration.transfer_fee_treatment
    transfers_with_fee = [transaction for transaction in transactions if isinstance(transaction, IntraTransaction) and transaction.crypto_fee > ZERO]
    if transfers_with_fee:
        raise RP2ValueError(
            f"{len(transfers_with_fee)} transfer(s) between wallets have a crypto fee, but 'transfer_fee_treatment' is not defined in the per_wallet "
            f"section of the configuration file (valid values: {', '.join(treatment.value for treatment in TransferFeeTreatment)}). "
            f"First one: {transfers_with_fee[0]}"
        )
    # No transfer has a fee: the treatment is irrelevant.
    return TransferFeeTreatment.DISPOSAL
