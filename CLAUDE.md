<!--- Copyright 2026 Neal Chambers --->

<!--- Licensed under the Apache License, Version 2.0 (the "License"); --->
<!--- you may not use this file except in compliance with the License. --->
<!--- You may obtain a copy of the License at --->

<!---     http://www.apache.org/licenses/LICENSE-2.0 --->

<!--- Unless required by applicable law or agreed to in writing, software --->
<!--- distributed under the License is distributed on an "AS IS" BASIS, --->
<!--- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. --->
<!--- See the License for the specific language governing permissions and --->
<!--- limitations under the License. --->

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RP2 is a privacy-focused, open-source cryptocurrency tax calculator written in Python 3.8+. It computes capital gains/losses from crypto transactions using pluggable accounting methods (FIFO, LIFO, HIFO, LOFO) and generates country-specific tax reports. All computation runs locally — no network calls.

## Development Setup

```bash
virtualenv -p python3 .venv
. .venv/bin/activate
.venv/bin/pip3 install -e '.[dev]'
```

## Common Commands

```bash
# Tests
pytest --tb=native --verbose              # all tests
pytest tests/test_accounting_method.py -v # single file
pytest tests/ -k "test_fifo" -v           # by pattern

# Static analysis
mypy src/ tests/
pylint -r y src tests/*.py
bandit -r src/

# Formatting
black src/ tests/
isort .

# Make targets
make all               # build virtualenv
make check             # run all tests
make static_analysis   # mypy + pylint + bandit
make run               # run example files
```

## Architecture

### Data Flow

```
Config file (INI) + Input ODS spreadsheet
  ↓
configuration.py → rp2_configuration_translator (optional migration)
  ↓
ods_parser.py → InputData (all transactions by asset)
  ↓
tax_engine.py: for each asset:
  - build taxable event set (SELL, GIFT, DONATE, etc.)
  - AccountingEngine pairs in/out lots via selected accounting method
  - produces GainLoss objects
  ↓
ComputedData (asset → GainLossSet)
  ↓
plugin/report/ generators → ODS output files + logs
```

### Plugin Architecture

Plugins are auto-discovered via `pkgutil.iter_modules()`:

- `src/rp2/plugin/accounting_method/` — one file per method (fifo.py, lifo.py, etc.)
- `src/rp2/plugin/country/` — country entry points and country-specific report configs
- `src/rp2/plugin/report/` — report generators (abstract_report_generator.py + concrete implementations)

Country-specific CLI entry points (e.g., `rp2_us`, `rp2_jp`) each call `rp2_main()` with a country object that specifies which report generators and accounting methods apply.

### Key Classes

| Class | File | Role |
|---|---|---|
| `AbstractEntry` | `abstract_entry.py` | Base for all entries; immutable |
| `InTransaction` | `in_transaction.py` | Acquisitions (BUY, MINING, STAKING, etc.) |
| `OutTransaction` | `out_transaction.py` | Sales/disposals |
| `IntraTransaction` | `intra_transaction.py` | Internal transfers |
| `GainLoss` | `gain_loss.py` | A computed gain/loss for one lot fraction |
| `AccountingEngine` | `accounting_engine.py` | Pairs lots using accounting method |
| `TaxEngine` | `tax_engine.py` | Orchestrates per-asset computation |
| `RP2Decimal` | `rp2_decimal.py` | High-precision Decimal subclass; use for all math |

### Design Conventions

- **Immutability**: dataclasses use `frozen=True`; fields are private (`__field`) with read-only `@property` accessors.
- **Runtime type checking**: every public method calls `type_check_*()` helpers at entry; don't skip these.
- **Precision**: all monetary/quantity values use `RP2Decimal`, never plain `float`.
- **14 transaction types** are defined in `entry_types.py` as `TransactionType` enum — understand these before adding logic.

### Testing

- `tests/golden/` holds expected ODS outputs for regression tests.
- `tests/rp2_test_output.py` provides helpers for comparing actual vs. expected output.
- Output-diff tests (`test_ods_output_diff_*.py`) are per-country and catch report formatting regressions.
- `tests/test_gain_loss.py` contains unit tests that verify IRS-rule-level correctness. Each test cites the governing IRS authority:
  - `test_ltcg_boundary` — IRS FAQ Q50 / IRC §1222 (holding period >365 days for LTCG)
  - `test_earn_type_income_recognition` — earn types (HARDFORK, AIRDROP, MINING, STAKING, WAGES, INCOME) produce ordinary income at FMV with no cost basis (Rev. Rul. 2019-24, Notice 2014-21, Rev. Rul. 2023-14, FAQ Q57-61, IRC §61)
  - `test_donate_gift_disposal_gain_loss` — DONATE/GIFT disposals compute gain/loss identically to SELL (IRS FAQ Q75-78, Notice 2014-21)
  - `test_holding_period_resets_after_exchange` — received asset's holding period starts fresh on exchange date (IRS FAQ Q74)
  - `test_fee_out_transaction_gain_loss` — FEE-typed disposal recognises gain/loss on crypto used to pay fees (IRS FAQ Q97, Notice 2014-21)
  - `test_good_non_interest_gain_loss` — intra-transaction crypto fee is a taxable disposal (IRS FAQ Q81/Q97, Notice 2014-21)

## Known Limitations and Tax Law Notes

These are intentional design decisions or known constraints to keep in mind when modifying the engine.

### LTCG Holding Period (fixed)
`gain_loss.py:is_long_term_capital_gains()` uses `>` (strictly greater than) against `country.get_long_term_capital_gain_period()`. For the US, the threshold is 365, so a lot must be held for **at least 366 days** to qualify as long-term. This correctly implements the IRS "more than one year" rule — exactly 365 days is short-term. Previously the code used `>=` which was incorrect.

### DONATE and GIFT Tax Treatment
RP2 computes gain/loss for `DONATE` and `GIFT` out-transactions using the same formula as `SELL`. This is intentional — the output tabs give tax professionals the data they need. However, the actual tax treatment differs from a sale:
- **DONATE to 501(c)(3):** No capital gains tax; the donor may instead deduct the FMV as a charitable contribution.
- **GIFT:** No capital gains tax for the giver; recipient inherits the giver's cost basis.

Do not change `OutTransaction.is_taxable()` to return `False` for these types without also updating all downstream report generators to handle them differently.

### IntraTransaction Fees Are Taxable Events
When `crypto_sent > crypto_received`, `IntraTransaction.is_taxable()` returns `True` and the fee generates a gain/loss entry. This is correct under IRS Notice 2014-21 but surprises users who expect wallet-to-wallet transfers to be tax-free. See `user_faq.md` for the user-facing explanation.

### Slashing / Negative Staking Income
RP2 has no dedicated slash transaction type. Involuntary stake losses (slashing) must be entered as an `OutTransaction` with `transaction_type = STAKING`. In-transaction amounts must be positive — do not enter negative `crypto_in` values.

### Crypto Precision
`RP2Decimal` uses 13 decimal places for crypto amounts (`CRYPTO_DECIMALS = 13`). Ethereum and other EVM chains use 18 decimal places (wei). Transaction amounts with more than 13 significant decimal digits will be truncated. For dust amounts this may cause minor discrepancies against on-chain records.

### Same-Timestamp Ordering
When two transactions share the same timestamp, their relative order is determined by their row number in the input spreadsheet. For LIFO and HIFO methods, swapping same-timestamp rows changes which lot is selected, potentially altering the tax outcome with no warning.

### Universal Lot Pool
All accounting methods (FIFO, LIFO, HIFO, LOFO) operate on a single global pool of lots per asset, regardless of which exchange or wallet the lots are held in. Per-wallet lot tracking is not implemented. Balance enforcement IS per-account (via `BalanceSet`), but lot selection is global.
