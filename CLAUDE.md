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

#### Universal (single global lot pool — existing path)

```
Config file (INI) + Input ODS spreadsheet
  ↓
configuration.py → rp2_configuration_translator (optional migration)
  ↓
ods_parser.py → InputData (all transactions by asset, single pool)
  ↓
tax_engine.compute_tax(): for each asset:
  - InputData.create_unfiltered_taxable_event_set() builds taxable event set
  - AccountingEngine pairs in/out lots via selected accounting method
  - produces GainLoss objects
  ↓
ComputedData (asset → GainLossSet)
  ↓
plugin/report/ generators → ODS output files + logs
```

#### Per-Wallet (new path, in development)

```
Config file (INI) + Input ODS spreadsheet
  ↓
ods_parser.py → InputData (universal: all transactions by asset)
  ↓
TransferAnalyzer(universal_input_data, transfer_semantics).analyze()
  - iterates all transactions chronologically across all wallets
  - InTransactions: adds lots to the source wallet's PerWalletTransactions
  - OutTransactions: marks lots as spent in the appropriate wallet
  - IntraTransactions: creates artificial InTransactions at the destination
    wallet, linking back via from_lot / originates_from / cost_basis_timestamp;
    handles self-transfers and cycle detection
  → Dict[Account, InputData]  (one InputData per wallet)
  ↓
[Optional] GlobalAllocator(wallet_2_input_data, allocation_method, year, account_order).allocate()
  - builds a single global acquired_lots pool across all wallets
  - for each account in account_order, uses AccountingEngine to pick which lots
    should fill that account's balance using the chosen allocation method
  - generates artificial IntraTransactions representing the reallocation
  → List[IntraTransaction]
  (feed back into TransferAnalyzer with the new intra transactions to get
   final per-wallet InputData)
  ↓
tax_engine.compute_tax(): for each asset/wallet:
  - same as universal path, but InputData is per-wallet
  - LTCG uses cost_basis_timestamp (original acquisition date, preserved
    through the transfer chain) rather than the transfer timestamp
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
| `Account` | `in_transaction.py` | Frozen `(exchange, holder)` wallet identity; key in per-wallet dicts |
| `PerWalletTransactions` | `transfer_analyzer.py` | Accumulates in/out/intra sets plus partial-amount map for one wallet during transfer analysis |
| `TransferAnalyzer` | `transfer_analyzer.py` | Decomposes universal `InputData` into per-wallet `InputData` objects; creates artificial `InTransaction`s for transfer destinations |
| `GlobalAllocator` | `global_allocation.py` | Generates artificial `IntraTransaction`s that reallocate lots across wallets using a chosen accounting method |

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

#### Per-Wallet and Global Allocation Tests (new)

- `tests/test_transfer_analysis_semantics_independent.py` — transfer analysis tests whose expected results do not depend on which accounting method is used for transfer semantics (e.g., single-lot transfers).
- `tests/test_transfer_analysis_semantics_dependent.py` — transfer analysis tests whose results differ based on FIFO vs. LIFO vs. HIFO transfer semantics.
- `tests/test_global_allocation.py` — end-to-end tests for `GlobalAllocator`, verifying that the generated artificial IntraTransactions correctly reallocate lots across wallets.
- `tests/transfer_analysis_common.py` — shared helpers for building `TransferAnalyzer` test fixtures.
- `tests/global_allocation_common.py` — shared helpers for building `GlobalAllocator` test fixtures.
- `tests/transaction_processing_common.py` — low-level helpers for constructing transactions and per-wallet InputData from descriptor dicts.

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

### Universal Lot Pool (default path)
All accounting methods (FIFO, LIFO, HIFO, LOFO) operate on a single global pool of lots per asset, regardless of which exchange or wallet the lots are held in. Per-wallet lot tracking is available via `TransferAnalyzer` but is not yet exposed in the CLI. Balance enforcement IS per-account (via `BalanceSet`), but lot selection is global in the universal path.

### Artificial InTransactions (per-wallet path only)
`TransferAnalyzer` creates artificial `InTransaction` objects to model the "to" side of each `IntraTransaction`. These artificial transactions exist only in per-wallet `InputData` objects — they are never present in the original universal `InputData` returned by `ods_parser.py`. Identifying fields: `from_lot is not None`. The fields `from_lot`, `to_lots`, and `originates_from` are only meaningful on artificial InTransactions.

### cost_basis_timestamp and LTCG (per-wallet path)
`InTransaction.cost_basis_timestamp` walks the `from_lot` chain back to the original acquisition to find the true purchase date. `GainLoss.is_long_term_capital_gains()` uses `cost_basis_timestamp` (not `timestamp`) so that the holding period survives wallet-to-wallet transfers. In the universal path all InTransactions are real (no `from_lot`), so `cost_basis_timestamp` falls back to `timestamp` and behavior is unchanged.

### TransferAnalyzer Requires InTransactions Before OutTransactions Per Account
`TransferAnalyzer.analyze()` raises `RP2ValueError` if an `OutTransaction` or `IntraTransaction` references an account that has not yet been seen in an `InTransaction`. The universal `InputData` must include all acquisition events; the analyzer processes everything chronologically in a single pass.

### GlobalAllocator Is Incomplete
`global_allocation.py` contains several `TODO` comments (fee splitting, spot price for artificial intra transactions). The core allocation loop works for the happy path, but edge cases (e.g., very small dust amounts, accounts with zero balance) may not be fully handled. The CLI does not yet expose global allocation.
