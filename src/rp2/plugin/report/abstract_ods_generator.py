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

import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Set

import ezodf

from rp2.abstract_country import AbstractCountry
from rp2.abstract_report_generator import AbstractReportGenerator
from rp2.abstract_transaction import AbstractTransaction
from rp2.accounting_engine import get_accounting_method_years
from rp2.computed_data import ComputedData
from rp2.configuration import MAX_DATE, MIN_DATE, Configuration
from rp2.gain_loss import GainLoss
from rp2.gain_loss_set import GainLossSet
from rp2.in_transaction import InTransaction
from rp2.localization import _
from rp2.out_transaction import OutTransaction
from rp2.rp2_decimal import RP2Decimal
from rp2.rp2_error import RP2RuntimeError, RP2TypeError


# A formula that a report generator builds, e.g. Formula("=SUM(E4:E9)"). AbstractODSGenerator._fill_cell() writes a Formula as a formula and
# any other value as it is: text from the input (an ID, a note, a holder...) stays text even if it starts with "=". Example: the note "=1+1"
# shows "=1+1", not 2, and a note like =WEBSERVICE("https://...") is never evaluated.
class Formula(NamedTuple):
    text: str


# The name that a sheet has in a report. ezodf, which writes the reports, replaces tabs, carriage returns and quotes with spaces in sheet
# names and removes the spaces at both ends: e.g. the In-Out sheet of the asset B'1"x is "B 1 x In-Out". Formulas and links that refer to a
# sheet must use this name.
def get_sheet_name(name: str) -> str:
    for character in "\t\r'\"":
        name = name.replace(character, " ")
    return name.strip()


# Text in a formula: in double quotes, with each double quote of the text doubled. Example: the ID buy"id;1 is "buy""id;1".
def get_formula_string(text: str) -> str:
    return '"' + text.replace('"', '""') + '"'


# A sheet in a formula: its name in single quotes, with each single quote of the name doubled. Example: B1_2024 is 'B1_2024'.
def get_sheet_reference(sheet_name: str) -> str:
    return "'" + sheet_name.replace("'", "''") + "'"


# The target of a link to a row of a sheet (row is 1-based): its cells from column A to Z. Example: #B1 In-Out.a4:z4 for row 4 of B1 In-Out.
# A sheet name with characters other than letters, digits, spaces, "-" and "_" is in quotes: LibreOffice doesn't find B.1 In-Out.a4:z4 but
# finds 'B.1 In-Out'.a4:z4.
def get_row_link_target(sheet_name: str, row: int) -> str:
    is_plain_name: bool = all(character.isalnum() or character in " -_" for character in sheet_name)
    return f"#{sheet_name if is_plain_name else get_sheet_reference(sheet_name)}.a{row}:z{row}"


# A link to a row of a sheet (see get_row_link_target()) that shows a value: a number, or text in quotes (see get_formula_string()).
# Example, for row 4 of B1 In-Out and the ID buy"id;1: =HYPERLINK("#B1 In-Out.a4:z4"; "buy""id;1").
def get_row_hyperlink(sheet_name: str, row: int, value: Any) -> Formula:
    shown_value: str = f"{value}" if isinstance(value, (RP2Decimal, int, float)) else get_formula_string(f"{value}")
    return Formula(f"=HYPERLINK({get_formula_string(get_row_link_target(sheet_name, row))}; {shown_value})")


class AbstractODSGenerator(AbstractReportGenerator):
    @classmethod
    def _initialize_output_file(  # pylint: disable=too-many-branches
        cls,
        country: AbstractCountry,  # pylint: disable=unused-argument
        legend_data: List[List[str]],
        years_2_accounting_method_names: Dict[int, str],
        output_dir_path: str,
        output_file_prefix: str,
        output_file_name: str,
        template_path: str,
        template_sheets_to_keep: Set[str],
        from_date: date,
        to_date: date,
    ) -> Any:
        Configuration.type_check_string("output_dir_path", output_dir_path)
        Configuration.type_check_string("output_file_prefix", output_file_prefix)
        Configuration.type_check_string("output_file_name", output_file_name)
        if not isinstance(template_sheets_to_keep, Set):
            raise RP2TypeError(f"Parameter 'template_sheets_to_keep' is not a Set: {template_sheets_to_keep}")

        output_file_path: Path = cls._get_output_file_path(years_2_accounting_method_names, output_dir_path, output_file_prefix, output_file_name)
        if Path(output_file_path).exists():
            output_file_path.unlink()

        output_file: Any = ezodf.newdoc("ods", str(output_file_path), template=template_path)
        legend_sheet_name: str = f"__Legend_{cls.get_name()}"
        template_sheets_to_keep_with_legend: Set[str] = template_sheets_to_keep.copy()
        template_sheets_to_keep_with_legend.add(legend_sheet_name)

        index: int = 0
        sheet_name: str
        sheet_indexes_to_remove: List[int] = []
        for sheet_name in output_file.sheets.names():
            if sheet_name in template_sheets_to_keep_with_legend:
                if not sheet_name.startswith("__"):
                    raise RP2RuntimeError(f"Internal error: template sheet '{sheet_name}' doesn't start with '__'")
                # Template sheets' names start with "__": remove leading "__" from name of sheet we want to keep
                output_file.sheets[index].name = sheet_name[2:]
            elif sheet_name.startswith("__"):
                # Template sheet we don't want to keep: mark it for removal
                sheet_indexes_to_remove.append(index)
            index += 1

        # Setup legend sheet
        legend_sheet: Any = output_file.sheets[legend_sheet_name[2:]]
        cls._fill_page(legend_data, legend_sheet, 0, 0)
        index = 0
        method_cell_found: bool = False
        for index in range(0, 100):
            if legend_sheet[index, 0].value == _("Accounting Method"):
                accounting_method_by_year: List[str] = []
                only_accounting_method_name: Optional[str] = cls._get_only_accounting_method_name(years_2_accounting_method_names)
                if only_accounting_method_name is not None:
                    accounting_method_by_year.append(only_accounting_method_name.upper())
                else:
                    # The years of each method, as the engine applies them (e.g. "2024-2025: FIFO, 2026+: HIFO").
                    accounting_method_by_year.extend(
                        method_years.get_description() for method_years in get_accounting_method_years(years_2_accounting_method_names)
                    )
                cls._fill_cell(legend_sheet, index, 1, ", ".join(accounting_method_by_year), visual_style="transparent")
                method_cell_found = True
                cls._fill_cell(legend_sheet, index + 1, 1, from_date if from_date != MIN_DATE else "non-specified", visual_style="transparent")
                cls._fill_cell(legend_sheet, index + 2, 1, to_date if to_date != MAX_DATE else "non-specified", visual_style="transparent")
                break
        if not method_cell_found:
            raise RP2RuntimeError(f"Internal error: ODS template has no '{_('Accounting Method')}' cell in column 0 of '{_('Legend')}'' sheet")

        legend_sheet.name = _("Legend")

        # Remove sheets that were marked for removal
        for index in reversed(sheet_indexes_to_remove):
            del output_file.sheets[index]

        return output_file

    # Path of an output file: <output_dir_path>/<output_file_prefix><accounting method>_<output_file_name>, where the accounting method is
    # "mixed" if it changes over the years (e.g. output/crypto_example_fifo_open_positions.ods).
    @classmethod
    def _get_output_file_path(
        cls, years_2_accounting_method_names: Dict[int, str], output_dir_path: str, output_file_prefix: str, output_file_name: str
    ) -> Path:
        only_accounting_method_name: Optional[str] = cls._get_only_accounting_method_name(years_2_accounting_method_names)
        accounting_method: str = only_accounting_method_name if only_accounting_method_name is not None else "mixed"
        return Path(output_dir_path) / Path(f"{output_file_prefix}{accounting_method}_{output_file_name}")

    # The accounting method of every year, if the map has only one entry, or None if the method changes over the years. The only entry
    # can have any year: without the accounting_methods section of the configuration it's 1970 (MIN_DATE.year), but the section can also
    # contain a single entry with another year. Example: with "2010 = fifo" in the accounting_methods section the method is "fifo", and
    # the output files are named <prefix>fifo_<report>.ods.
    @staticmethod
    def _get_only_accounting_method_name(years_2_accounting_method_names: Dict[int, str]) -> Optional[str]:
        if len(years_2_accounting_method_names) != 1:
            return None
        return next(iter(years_2_accounting_method_names.values()))

    def _get_template_path(self, template_name: str, country: Optional[AbstractCountry], generation_language: str) -> str:
        country_path = f"{country.country_iso_code}/" if country else ""
        language_suffix = f"_{generation_language}" if country else ""
        base_path = Path(os.path.dirname(__file__)).absolute() / Path(f"data/{country_path}template_{template_name}{language_suffix}")
        ods_path = Path(f"{base_path}.ods")
        if ods_path.exists():
            return str(ods_path)
        if not country:
            raise RP2RuntimeError(f"Internal error: template {ods_path} doesn't exist")

        # Look for a link (a .txt file containing the path to the .ods file)
        txt_path = Path(f"{base_path}.txt")
        if txt_path.exists():
            new_ods_path = Path(os.path.dirname(__file__)).absolute()
            with open(txt_path, encoding="utf-8") as template_link:
                contents = template_link.read().strip()
                if not contents or not contents.endswith(".ods"):
                    raise RP2RuntimeError(f"Internal error: template link {txt_path} doesn't contain a path ending with .ods: {contents}")
                new_ods_path = new_ods_path / Path(f"data/{contents}")
                if new_ods_path.exists():
                    return str(new_ods_path)
            raise RP2RuntimeError(f"Internal error: template link {txt_path} points to a path that doesn't exist: {new_ods_path}")

        raise RP2RuntimeError(f"Language {generation_language} not supported for country {country.country_iso_code}: template {ods_path}/.txt doesn't exist")

    def generate(
        self,
        country: AbstractCountry,
        years_2_accounting_method_names: Dict[int, str],
        asset_to_computed_data: Dict[str, ComputedData],
        output_dir_path: str,
        output_file_prefix: str,
        from_date: date,
        to_date: date,
        generation_language: str,
    ) -> None:
        raise NotImplementedError("Abstract method: it must be implemented in the plugin class")

    @staticmethod
    def _apply_style_to_cell(sheet: Any, row_index: int, column_index: int, style_name: str) -> None:
        Configuration.type_check_positive_int("row_index", row_index)
        Configuration.type_check_positive_int("column_index", column_index)
        Configuration.type_check_string("style_name", style_name)

        sheet[row_index, column_index].style_name = style_name

    @classmethod
    def _fill_cell(
        cls,
        sheet: Any,
        row_index: int,
        column_index: int,
        value: Any,
        visual_style: str = "transparent",
        data_style: str = "default",
        apply_style: bool = True,
    ) -> None:
        Configuration.type_check_string("visual_style", visual_style)
        Configuration.type_check_string("data_style", data_style)

        style_name: str = f"{visual_style}_{data_style}"
        if isinstance(value, Formula):
            # Only formulas that a report generator builds are written as formulas (see Formula).
            sheet[row_index, column_index].formula = value.text
        else:
            if isinstance(value, RP2Decimal):
                # The ezodf API doesn't accept RP2Decimal, so we are forced to cast to float before writing to the spreadsheet
                value = float(value)
            # Any other value is written as it is: text stays text, even if it starts with "=" (e.g. a note "=1+1" from the input).
            sheet[row_index, column_index].set_value(value)
        if apply_style:
            cls._apply_style_to_cell(sheet=sheet, row_index=row_index, column_index=column_index, style_name=style_name)

    def _fill_header(
        self, title: str, header_row_1: List[str], header_row_2: List[str], sheet: Any, row_index: int, column_index: int, apply_style: bool = True
    ) -> int:
        Configuration.type_check_string("title", title)
        if not isinstance(header_row_1, List):
            raise RP2TypeError("Parameter 'header_row_1' is not a List")
        if not isinstance(header_row_2, List):
            raise RP2TypeError("Parameter 'header_row_2' is not a List")

        self._fill_cell(sheet, row_index, 0, title, visual_style="title", apply_style=apply_style)
        row_index += 1

        self._fill_cell(sheet, row_index, 0, "", visual_style="transparent", apply_style=apply_style)
        self._fill_cell(sheet, row_index + 1, 0, "", visual_style="transparent", apply_style=apply_style)

        header1: str
        header2: str
        i: int = 0
        for header1, header2 in zip(header_row_1, header_row_2):
            self._fill_cell(sheet, row_index, column_index + i, header1, visual_style="header", data_style="default", apply_style=apply_style)
            self._fill_cell(sheet, row_index + 1, column_index + i, header2, visual_style="header", data_style="default", apply_style=apply_style)
            i += 1
        return row_index + 2

    @classmethod
    def _fill_page(cls, data: List[List[str]], sheet: Any, row_index: int, column_index: int) -> int:
        if not isinstance(data, List):
            raise RP2TypeError("Parameter 'data' is not a List")

        i: int = 0
        for row in data:
            j: int = 0
            for element in row:
                # Apply no style because we don't know the nature of the data
                cls._fill_cell(sheet, row_index + i, column_index + j, element, apply_style=False)
                j += 1
            i += 1

        return row_index + i

    @staticmethod
    def _get_table_type_from_transaction(transaction: AbstractTransaction) -> str:
        AbstractTransaction.type_check("transaction", transaction)
        if isinstance(transaction, InTransaction):
            return "IN"
        if isinstance(transaction, OutTransaction):
            return "OUT"
        return "INTRA"

    # The description of the coins that a gain/loss took from its lot: their fraction number, their amount and the amount of the lot. With
    # per-wallet application, coins that came to a wallet through transfers or the opening allocation are a lot of that wallet created by
    # RP2 (an artificial lot), which has no row in the input: reports identify such coins by their original lot (the input purchase they come
    # from, see InTransaction.original_lot), and the description adds the wallet and the id of the wallet's lot. The amounts stay those of the
    # wallet's lot. Example: buy 2 coins on Coinbase (lot i1), send them to Kraken (Kraken's lot t1/-1) and sell 1 of them there: the sale's
    # lot is i1, described as "1/1: 1.00000000 of 2.00000000 B1 in Kraken/Bob (lot t1/-1)".
    @staticmethod
    def _get_acquired_lot_description(gain_loss_set: GainLossSet, gain_loss: GainLoss) -> str:
        acquired_lot = gain_loss.acquired_lot
        if acquired_lot is None:
            raise RP2RuntimeError(f"Internal error: gain/loss without an acquired lot: {gain_loss}")
        fraction = gain_loss_set.get_acquired_lot_fraction(gain_loss) + 1
        number_of_fractions = gain_loss_set.get_acquired_lot_number_of_fractions(acquired_lot)
        result = f"{fraction}/{number_of_fractions}: {gain_loss.crypto_amount:.8f} of {acquired_lot.crypto_balance_change:.8f} {gain_loss.asset}"
        if acquired_lot is not acquired_lot.original_lot:
            result += f" in {acquired_lot.exchange}/{acquired_lot.holder} (lot {acquired_lot.unique_id})"
        return result
