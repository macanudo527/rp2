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

from datetime import datetime
from typing import Dict, List, NamedTuple, Optional

from rp2.abstract_accounting_method import AbstractAccountingMethod, AcquiredLotSortKey
from rp2.account import Account
from rp2.configuration import Configuration
from rp2.in_transaction import InTransaction
from rp2.logger import LOGGER
from rp2.plugin.accounting_method.fifo import AccountingMethod as AccountingMethodFIFO
from rp2.rp2_decimal import ZERO, RP2Decimal
from rp2.rp2_error import RP2TypeError, RP2ValueError
from rp2.transfer_analyzer import TransferAnalyzer


class UnusedLot(NamedTuple):
    acquired_lot: InTransaction
    # Amount of the lot not yet disposed of under universal application at the time of the switch.
    amount: RP2Decimal


# UnusedBasisAllocator implements the transition from universal to per-wallet application: it assigns the lots that are still unused (under
# universal application) at the switch instant to the wallets that actually hold the funds at that instant. This is the "global allocation"
# of Rev. Proc. 2024-28: a rule-based allocation that the taxpayer must have chosen (and documented) before the switch. The rule is:
# 1) sort the unused lots with the given accounting method (e.g. FIFO: oldest first);
# 2) fill the wallets in the given order, each one up to its balance at the switch.
# Each allocated lot piece becomes an artificial InTransaction at the switch instant, in the wallet it was allocated to: it points to the
# original lot (from_lot) and keeps its per-unit cost basis and acquisition date. The specific-unit allocation of Rev. Proc. 2024-28 is
# not supported.
class UnusedBasisAllocator:
    def __init__(
        self,
        configuration: Configuration,
        switch_timestamp: datetime,
        unused_lots: List[UnusedLot],
        account_2_balance: Dict[Account, RP2Decimal],
        allocation_method: Optional[AbstractAccountingMethod],
        wallet_order: List[Account],
    ) -> None:
        self.__configuration = Configuration.type_check("configuration", configuration)
        if not isinstance(switch_timestamp, datetime) or switch_timestamp.tzinfo is None:
            raise RP2TypeError(f"Parameter 'switch_timestamp' is not a timezone-aware datetime: {switch_timestamp}")
        self.__switch_timestamp = switch_timestamp
        self.__unused_lots = unused_lots
        self.__account_2_balance = {account: balance for account, balance in account_2_balance.items() if balance > ZERO}
        if allocation_method is not None and not isinstance(allocation_method, AbstractAccountingMethod):
            raise RP2TypeError(f"Parameter 'allocation_method' is not of type AbstractAccountingMethod: {allocation_method}")
        self.__allocation_method = allocation_method
        self.__wallet_order = wallet_order

    def allocate(self) -> List[InTransaction]:
        funded_accounts = sorted(self.__account_2_balance, key=_account_sort_key)
        if not funded_accounts:
            return []
        wallet_order: List[Account]
        allocation_method: AbstractAccountingMethod
        if len(funded_accounts) == 1:
            # Only one wallet holds funds: there's nothing to choose, all unused lots go to it.
            wallet_order = funded_accounts
            allocation_method = self.__allocation_method or AccountingMethodFIFO()
        else:
            if self.__allocation_method is None or not self.__wallet_order:
                raise RP2ValueError(
                    f"Unused basis allocation is needed at {self.__switch_timestamp} ({len(funded_accounts)} wallets hold "
                    f"{self.__unused_lots[0].acquired_lot.asset if self.__unused_lots else ''} funds: "
                    f"{', '.join(f'{account.exchange}/{account.holder}' for account in funded_accounts)}), but the 'unused_basis_allocation_method' "
                    "and 'unused_basis_allocation_wallet_order' fields are not defined in the per_wallet section of the configuration file "
                    "(see Rev. Proc. 2024-28)"
                )
            missing_accounts = [account for account in funded_accounts if account not in self.__wallet_order]
            if missing_accounts:
                raise RP2ValueError(
                    "Wallets holding funds at the per-wallet switch are missing from 'unused_basis_allocation_wallet_order': "
                    f"{', '.join(f'{account.exchange}/{account.holder}' for account in missing_accounts)}"
                )
            wallet_order = [account for account in self.__wallet_order if account in self.__account_2_balance]
            allocation_method = self.__allocation_method

        per_wallet_method = TransferAnalyzer.get_per_wallet_accounting_method(allocation_method)

        def unused_lot_sort_key(unused_lot: UnusedLot) -> AcquiredLotSortKey:
            return per_wallet_method.sort_key(unused_lot.acquired_lot)

        sorted_unused_lots = sorted(self.__unused_lots, key=unused_lot_sort_key)
        result: List[InTransaction] = []
        lot_index = 0
        lot_amount_left = sorted_unused_lots[0].amount if sorted_unused_lots else ZERO
        for account in wallet_order:
            balance_left = self.__account_2_balance[account]
            while balance_left > ZERO:
                if lot_index >= len(sorted_unused_lots):
                    raise RP2ValueError(
                        f"Unused lots are insufficient to cover the balance of {account.exchange}/{account.holder} at {self.__switch_timestamp}"
                    )
                piece_amount = min(balance_left, lot_amount_left)
                result.append(self._create_allocated_lot(sorted_unused_lots[lot_index].acquired_lot, account, piece_amount))
                balance_left -= piece_amount
                lot_amount_left -= piece_amount
                if lot_amount_left == ZERO:
                    lot_index += 1
                    lot_amount_left = sorted_unused_lots[lot_index].amount if lot_index < len(sorted_unused_lots) else ZERO
        LOGGER.info("Unused basis allocation at %s: allocated %d lot pieces to %d wallets", self.__switch_timestamp, len(result), len(wallet_order))
        return result

    def _create_allocated_lot(self, acquired_lot: InTransaction, account: Account, amount: RP2Decimal) -> InTransaction:
        artificial_id = self.__configuration.get_new_artificial_id()
        fraction = amount / acquired_lot.crypto_in
        fiat_fee = acquired_lot.fiat_fee * fraction
        return InTransaction(
            configuration=self.__configuration,
            timestamp=self.__switch_timestamp.isoformat(),
            asset=acquired_lot.asset,
            exchange=account.exchange,
            holder=account.holder,
            transaction_type=acquired_lot.transaction_type.value,
            spot_price=acquired_lot.spot_price,
            crypto_in=amount,
            fiat_in_no_fee=acquired_lot.fiat_in_no_fee * fraction,
            fiat_fee=fiat_fee if fiat_fee > ZERO else None,
            row=artificial_id,
            unique_id=f"{acquired_lot.unique_id}/{artificial_id}",
            notes=(
                f"Artificial transaction modeling the allocation of {amount} {acquired_lot.asset} of unused basis to "
                f"{account.exchange}/{account.holder} at the switch to per-wallet application ({self.__switch_timestamp})."
            ),
            from_lot=acquired_lot,
            cost_basis_timestamp=acquired_lot.cost_basis_timestamp.isoformat(),
        )


def _account_sort_key(account: Account) -> str:
    return f"{account.exchange}/{account.holder}"
