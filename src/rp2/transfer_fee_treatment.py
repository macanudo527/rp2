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

from enum import Enum

from rp2.rp2_error import RP2TypeError, RP2ValueError


# How a crypto fee paid on a transfer between the taxpayer's own wallets (IntraTransaction with crypto_sent > crypto_received) is
# treated in per-wallet application. US law does not settle this, so the user must choose explicitly:
# - DISPOSAL: the fee units are disposed of and generate a gain/loss (this is also what universal application does);
# - BASIS_CARRYOVER: the fee units are not a taxable event: their cost basis is added to the units received at the destination.
class TransferFeeTreatment(Enum):
    DISPOSAL = "disposal"
    BASIS_CARRYOVER = "basis_carryover"

    @classmethod
    def type_check(cls, name: str, value: "TransferFeeTreatment") -> "TransferFeeTreatment":
        if not isinstance(value, cls):
            raise RP2TypeError(f"Parameter '{name}' is not of type {cls.__name__}: {value}")
        return value

    @classmethod
    def from_string(cls, value: str) -> "TransferFeeTreatment":
        try:
            return cls(value.strip().lower())
        except ValueError:
            raise RP2ValueError(f"Invalid transfer fee treatment '{value}': valid values are {', '.join(treatment.value for treatment in cls)}") from None
