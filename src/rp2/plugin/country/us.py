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
from typing import Optional, Set

from dateutil.relativedelta import relativedelta

from rp2.abstract_country import AbstractCountry
from rp2.rp2_main import rp2_main


# US-specific class
class US(AbstractCountry):
    def __init__(self) -> None:
        super().__init__("us", "usd")

    # Measured in days
    def get_long_term_capital_gain_period(self) -> int:
        return 365

    # IRC §1222: long-term means held "more than 1 year". IRS Publication 544 ("Holding period"): "start counting on the day following
    # the day you acquired the property. The day you disposed of the property is part of your holding period". So the holding period
    # is measured in calendar dates, not in days: it's long-term if the disposal date is after the first anniversary of the acquisition
    # date (e.g. bought 2023-03-01: long-term from 2024-03-02, even though 2024-03-01 is already 366 days later because of February 29th).
    # Each date is the one of its own timestamp (the same convention used for tax years).
    def is_long_term_capital_gain(self, acquisition_timestamp: datetime, disposal_timestamp: datetime) -> bool:
        return disposal_timestamp.date() > acquisition_timestamp.date() + relativedelta(years=1)

    # Default accounting method to use if the user doesn't specify one on the command line
    def get_default_accounting_method(self) -> str:
        return "fifo"

    # Set of accounting methods accepted in the country
    def get_accounting_methods(self) -> Set[str]:
        return {"fifo", "hifo", "lifo", "lofo"}

    # Default set of generators to use if the user doesn't specify them on the command line
    def get_report_generators(self) -> Set[str]:
        return {
            "open_positions",
            "rp2_full_report",
            "us.tax_report_us",
        }

    # Default language to use at report generation if the user doesn't specify it on the command line (in ISO 639-1 format)
    def get_default_generation_language(self) -> str:
        return "en"

    # Treas. Reg. §1.1012-1(j) (T.D. 10000) requires basis identification per wallet or account for dispositions on or after
    # January 1, 2025: earlier years keep universal application (see also Rev. Proc. 2024-28).
    def get_per_wallet_application_start_year(self) -> Optional[int]:
        return 2025


# US-specific entry point
def rp2_entry() -> None:
    rp2_main(US())
