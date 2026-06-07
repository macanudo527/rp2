<!--- Copyright 2021 eprbell --->

<!--- Licensed under the Apache License, Version 2.0 (the "License"); --->
<!--- you may not use this file except in compliance with the License. --->
<!--- You may obtain a copy of the License at --->

<!---     http://www.apache.org/licenses/LICENSE-2.0 --->

<!--- Unless required by applicable law or agreed to in writing, software --->
<!--- distributed under the License is distributed on an "AS IS" BASIS, --->
<!--- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. --->
<!--- See the License for the specific language governing permissions and --->
<!--- limitations under the License. --->

# RP2 Frequently Asked Questions (User)

## Table of Contents
* **[General Questions](#general-questions)**
  * [How to Verify that I Entered Data Correctly in the Input Spreadsheet?](#how-to-verify-that-i-entered-data-correctly-in-the-input-spreadsheet)
  * [How to Verify that Tax Computation is Correct?](#how-to-verify-that-tax-computation-is-correct)
  * [What Is the Timestamp Format?](#what-is-the-timestamp-format)
  * [What if I Don't Have the Spot Price for Some Transactions?](#what-if-i-dont-have-the-spot-price-for-some-transactions)
  * [What Tokens Does RP2 Support?](#what-tokens-does-rp2-support)
  * [What Accounting Methods Are Supported?](#what-accounting-methods-are-supported)
  * [Do Accounting Methods Use Universal or Per-Wallet Application](#do-accounting-methods-use-universal-or-per-wallet-application)
  * [Can I Change Accounting Method?](#can-i-change-accounting-method)
  * [What Countries Are Supported?](#what-countries-are-supported)
  * [How to Switch from Another Tax Software to RP2?](#how-to-switch-from-another-tax-software-to-rp2)
  * [Why Should I Use RP2 Instead of Another Software?](#why-should-i-use-rp2-instead-of-another-software)
  * [What's the Difference Between Rotki and RP2?](#whats-the-difference-between-rotki-and-rp2)
  * [Can I Avoid Writing the Input Spreadsheet Manually?](#can-i-avoid-writing-the-input-spreadsheet-manually)
  * [Can I Avoid Writing a Config File from Scratch?](#can-i-avoid-writing-a-config-file-from-scratch)
  * [Is My Tax Report Browsable?](#is-my-tax-report-browsable)
  * [How to Report a RP2 Bug Without Sharing Personal Information?](#how-to-report-a-rp2-bug-without-sharing-personal-information)
  * [What if I Don't Trust RP2 With My Crypto Data?](#what-if-i-dont-trust-rp2-with-my-crypto-data)
  * [Why Can't I Open the RP2 Output Report with Excel?](#why-cant-i-open-the-rp2-output-report-with-excel)
  * [Who is the Author of RP2?](#who-is-the-author-of-rp2)
  * [How to Pronounce RP2?](#how-to-pronounce-rp2)
  * [What Does RP2 Mean?](#what-does-rp2-mean)

* **[Tax Questions](#tax-questions)**
  * [What Events Are Taxable?](#what-events-are-taxable)
  * [How Does RP2 Determine Long-Term vs Short-Term Capital Gains?](#how-does-rp2-determine-long-term-vs-short-term-capital-gains)
  * [Can I Avoid Paying Crypto Taxes?](#can-i-avoid-paying-crypto-taxes)
  * [Which Resources Can I Use to Learn About Crypto Taxes?](#which-resources-can-i-use-to-learn-about-crypto-taxes)
  * [Which Crypto Tax Forms to File?](#which-crypto-tax-forms-to-file)

* **[Tax Scenarios](#tax-scenarios)**
  * [What if I and My Spouse File Taxes Jointly?](#what-if-i-and-my-spouse-file-taxes-jointly)
  * [How to Handle a Transfer of Funds from a Wallet or Exchange to Another?](#how-to-handle-a-transfer-of-funds-from-a-wallet-or-exchange-to-another)
  * [If I Transfer Cryptocurrency Between Two Accounts I Own, Is the Fee Taxable?](#if-i-transfer-cryptocurrency-between-two-accounts-i-own-is-the-fee-taxable)
  * [How to Represent Fiat vs Crypto Transaction Fees?](#how-to-represent-fiat-vs-crypto-transaction-fees)
  * [How to Handle Conversion of a Cryptocurrency to Another?](#how-to-handle-conversion-of-a-cryptocurrency-to-another)
  * [How to Handle Airdrops?](#how-to-handle-airdrops)
  * [How to Handle Donations?](#how-to-handle-donations)
  * [Important: Tax Treatment of Donations vs. Gifts](#important-tax-treatment-of-donations-vs-gifts)
  * [How to Handle Gifts?](#how-to-handle-gifts)
  * [How to Handle Inherited Crypto?](#how-to-handle-inherited-crypto)
  * [How to Handle Hard Forks?](#how-to-handle-hard-forks)
  * [How to Handle Miscellaneous Crypto Income?](#how-to-handle-miscellaneous-crypto-income)
  * [How to Handle Crypto Interest?](#how-to-handle-crypto-interest)
  * [How to Handle Income from Mining?](#how-to-handle-income-from-mining)
  * [How to Handle Income from Staking?](#how-to-handle-income-from-staking)
  * [How to Handle Losses from Staking?](#how-to-handle-losses-from-staking)
  * [How to Handle Income from Crypto Wages?](#how-to-handle-income-from-crypto-wages)
  * [How to Handle Crypto Rewards?](#how-to-handle-crypto-rewards)
  * [Important: Lost or Stolen Crypto May Not Be Tax-Deductible](#important-lost-or-stolen-crypto-may-not-be-tax-deductible)
  * [How to Handle Fee-only DeFi Transactions?](#how-to-handle-fee-only-defi-transactions)
  * [How to Handle DeFi Bridging?](#how-to-handle-defi-bridging)
  * [How to Handle DeFi Reflexive Tokens?](#how-to-handle-defi-reflexive-tokens)
  * [How to Handle DeFi Yield from Liquidity Pools](#how-to-handle-defi-yield-from-liquidity-pools)
  * [How to Handle DeFi Liquidity Pool Deposits and Withdrawals?](#how-to-handle-defi-liquidity-pool-deposits-and-withdrawals)
  * [How to Handle Crypto-to-Crypto Swaps on Decentralized Exchanges?](#how-to-handle-crypto-to-crypto-swaps-on-decentralized-exchanges)
  * [How to Handle NFTs?](#how-to-handle-nfts)
  * [How to Handle Margin Trading?](#how-to-handle-margin-trading)
  * [How to Handle Futures and Options?](#how-to-handle-futures-and-options)
  * [Important: Wash Sale Rules Do Not Currently Apply to Crypto](#important-wash-sale-rules-do-not-currently-apply-to-crypto)

## General Questions

### How to Verify that I Entered Data Correctly in the Input Spreadsheet?
In rp2_full_report.ods check the Account Balances table in the tax sheets, and make sure they match the actual balances of your accounts. If not, you probably have an error in the input file or missed some transactions.

### How to Verify that Tax Computation is Correct?
RP2 features [transparent computation](output_files.md#rp2-full-report-transparent-computation) and generates full computation details for every lot and lot fraction (a *lot* is a batch of crypto you purchased at a specific price and time; a *lot fraction* is the portion of a lot matched against a particular sale), so that it's possible to verify step-by-step how RP2 reaches the final result.

### What Is the Timestamp Format?
Timestamp format is [ISO8601](https://en.wikipedia.org/wiki/ISO_8601) (see [examples](https://en.wikipedia.org/wiki/ISO_8601#Combined_date_and_time_representations) of timestamps in this format). Note that RP2 requires full timestamps, including date, time and timezone.

### What if I Don't Have the Spot Price for Some Transactions?
In some cases exchange reports miss spot price information. In such situations you can retrieve historical price data from <!-- markdown-link-check-disable -->[Yahoo](https://finance.yahoo.com/quote/BTC-USD/history/)<!-- markdown-link-check-enable -->, [CoinMarketCap](https://coinmarketcap.com/currencies/bitcoin/historical-data/) and others.

### What Tokens Does RP2 Support?
The user adds the tokens to the `assets` field of the [config file](input_files.md#the-config-file): RP2 accepts as valid all the tokens present in this field. See also the question on [writing a config file from scratch](#can-i-avoid-writing-a-config-file-from-scratch).

### What Accounting Methods Are Supported?
Accounting methods vary country by country, as described in the [supported countries](supported_countries.md) document.

### Do Accounting Methods Use Universal or Per-Wallet Application?
RP2 engine currently supports [universal application](https://www.forbes.com/sites/shehanchandrasekera/2020/09/17/what-crypto-taxpayers-need-to-know-about-fifo-lifo-hifo-specific-id/) application, however per-wallet support is [being worked on](https://github.com/eprbell/rp2/issues/135).

### Can I Change Accounting Method?
Yes, for countries that support more than one accounting method, you can select which one to use via the `-m` command line option, or you can use the `accounting_methods` section of the [config file](https://github.com/eprbell/rp2/blob/main/docs/input_files.md#the-config-file).

### What Countries Are Supported?
RP2 can be used in most countries: see the [supported countries](supported_countries.md) document for details.

### How to Switch from Another Tax Software to RP2?
In other words, how does RP2 handle transactions that were managed by other software in previous years? In this case the user can just leave out from the RP2 input spreadsheet the transactions and lots (individual purchase batches) that were already sold in previous years.

E.g. suppose the user's first year of trading BTC was 2020 and these were their transactions:

<ol type="a">
<li> 2020-2-5: buy 1 BTC</li>
<li> 2020-5-5: buy 2 BTC</li>
<li> 2020-8-1: sell 1.5 BTC</li>
<li> 2021: more transactions...</li>
</ol>

Let's also assume they didn't use RP2 for their 2020 taxes and they used the FIFO accounting method. This means they sold all of lot a) and 0.5 BTC from lot b).

So if they want to start using RP2 for their 2021 taxes, they would just leave out what they already sold and enter the following in the RP2 input spreadsheet:

* 2020-5-5: buy 1.5 BTC</li>
* 2021: more transactions...</li>

This is because a), part of b) and c) are already accounted for in the pre-RP2 system. The Notes column can be useful here: it can be used to describe why lot b) is partial.

Of course the user still needs to keep all the documentation for previous years as well as for the current year. Also they will need to keep the same accounting method they were using previously: to switch accounting method it is a good idea to speak to a tax professional first.

### Why Should I Use RP2 Instead of Another Software?
RP2 has all of the following features:
* 100% privacy-focused;
* 100% open-source;
* 100% free;
* 100% non-commercial;
* powerful and robust.

This means that with RP2 there are no transaction limits, no premium versions, no payment requests, no personal data sent to a server (at risk of being hacked), no account creation, no unauditable source code.

Additionally RP2 offers [transparent computation](output_files.md#rp2-full-report-transparent-computation) and generates full computation details for every lot fraction, so that it's possible to:
* verify step-by-step how RP2 reaches the final result;
* track down every lot fraction and its cost basis, gain/loss, and other accounting details, in case of an audit.

### What's the Difference Between Rotki and RP2?
One difference is that RP2 is 100% free and non-commercial, whereas Rotki is a commercial product: their free offering has transaction limits and other constraints that can be lifted by purchasing the premium product. Another difference relates to privacy protection: to access premium features in Rotki the user needs to open an account on the Rotki web site and pay them (thus disclosing some personal information to them), whereas on RP2 no personal information ever leaves the user's computer. See also the question on [what differentiates RP2 from other crypto tax software](#why-should-i-use-rp2-instead-on-another-software).

### Can I Avoid Writing the Input Spreadsheet Manually?
You can generate it automatically using [DaLI](https://github.com/eprbell/dali-rp2), the data loader and input generator for RP2.

### Can I Avoid Writing a Config File from Scratch?
You can generate it automatically using [DaLI](https://github.com/eprbell/dali-rp2), the data loader and input generator for RP2. Alternatively you can use [crypto_example.ini](../config/crypto_example.ini) as boilerplate and the [Input Files](input_files.md) document as reference.

### Is My Tax Report Browsable?
The rp2_full_report output contains full tax computation details. Part of its contents are hyperlinked to enable browsing: in LibreOffice, CTRL-click (on Mac, Command-click) on a cell to jump to the target. The browsable elements are:
  * taxable events and acquired lots in the *cryptocurrency* Tax sheet are hyperlinked to their definition line in the *cryptocurrency* In-Out sheet;
  * summary lines in the Summary sheet are hyperlinked to the first line of the given year in the *cryptocurrency* Tax sheet.

### How to Report a RP2 Bug Without Sharing Personal Information?
See the Reporting Bugs section in the [CONTRIBUTING](../CONTRIBUTING.md#reporting-bugs) document.

### What if I Don't Trust RP2 With My Crypto Data?
In other words, how to be sure RP2 is not malware/spyware? After all, Bitcoin's motto is *"don't trust, verify"*. RP2 is open-source and written in Python, so anybody with Python skills can inspect the code anytime: if RP2 were to try anything untoward (e.g. connecting to a server), someone would likely notice. However if you don't have the time, patience or skill to verify the code and you don't trust others to do so for you, you can still use RP2 in an isolated environment:
- start a fresh virtual machine with your OS of choice;
- install RP2 in the virtual machine;
- isolate the virtual machine: kill networking, shared directories and other mechanisms of outside communication;
- copy your crypto input data to the virtual machine via USB key or other physical medium (because the machine is now isolated);
- run RP2 in the virtual machine.

### Why Can't I Open the RP2 Output Report with Excel?
Some people have reported a problem when opening the rp2_full_report.ods file in Excel. RP2 generates ODS output using the pyexcel-ezodf library, which works well with [Libre Office](https://www.libreoffice.org/) and Open Office (both of which are free). If Excel is unable to open a RP2 file, try again with one of its free alternatives.

### Who is the Author of RP2?
The author of RP2 is a Silicon Valley veteran, a software engineer and bitcoiner who also dabbles in Quantum Computing.

### How to Pronounce RP2?
It's RP Square (see [What Does RP2 Mean](#what-does-rp2-mean)).

### What Does RP2 Mean?
It's a humorous reference to Warren Buffett’s claim that Bitcoin is [“rat poison squared”](https://www.cnbc.com/2018/05/05/warren-buffett-says-bitcoin-is-probably-rat-poison-squared.html). Other smart people occasionally made [famously](https://www.snopes.com/fact-check/paul-krugman-internets-effect-economy/) [wrong](https://libquotes.com/thomas-edison/quote/lbx5e7q) [remarks](https://en.wikipedia.org/wiki/Robert_Metcalfe#Incorrect_predictions) about technology: I have a feeling Buffett’s quote might end up among those.

## Tax Questions

### What Events Are Taxable?
Selling, swapping, donating, mining, staking, earning cryptocurrency are some common taxable events. For an up-to-date list in any given year, ask your tax professional. For additional information on taxable events read the <!-- markdown-link-check-disable -->[Cryptocurrency Tax FAQ](https://www.reddit.com/r/CryptoTax/comments/re6jal/cryptocurrency_tax_faq/)<!-- markdown-link-check-enable--> on Reddit and <!-- markdown-link-check-disable -->[CoinTracker's summary on crypto taxes](https://www.cointracker.io/blog/what-tax-forms-should-crypto-holders-file).<!-- markdown-link-check-enable-->

### How Does RP2 Determine Long-Term vs Short-Term Capital Gains?
The IRS defines a long-term capital gain as one where the asset was held **more than one year** (IRS Publication 544). RP2 implements this as: the holding period (sale date minus purchase date, in days) must be **strictly greater than 365 days**. Consequently:

* A lot bought on Jan 1, 2021 and sold on Jan 1, 2022 (exactly 365 days) is **short-term**.
* A lot bought on Jan 1, 2021 and sold on Jan 2, 2022 (366 days) is **long-term**.
* In a leap year (e.g. buy Jan 1, 2020, sell Jan 1, 2021) the difference is 366 days, which is long-term.

The holding period threshold is configurable per country. For other countries the long-term threshold may differ; RP2 applies the same "strictly greater than" rule against each country's configured threshold.

### Can I Avoid Paying Crypto Taxes?
No. The IRS has made it clear that [crypto taxes must be paid](https://www.irs.gov/newsroom/irs-reminds-taxpayers-to-report-virtual-currency-transactions). Various tax agencies in other jurisdictions have made similar statements.

### Which Resources Can I Use to Learn About Crypto Taxes?
A good starting point is the <!-- markdown-link-check-disable -->[Cryptocurrency Tax FAQ](https://www.reddit.com/r/CryptoTax/comments/re6jal/cryptocurrency_tax_faq/)<!-- markdown-link-check-enable--> on Reddit. Also read the question on [which tax forms to file](#which-crypto-tax-forms-to-file) and consult with your tax professional.

### Which Crypto Tax Forms to File?
RP2 tracks which purchase lots are matched against which sales, how those lots are split when only part of a lot is sold, and it computes capital gains and losses, but it doesn't generate the final tax forms. The computed information is written to the tax_report_us output, which is intended for tax professionals: all taxable events are grouped in different tabs by type (mining, staking, selling, donating, etc.). Each tax event type has a specific tax treatment: your tax professional can transfer the information from the tax_report_us output tabs to the appropriate forms in any given year.

For additional information on which forms to file read:
<!-- markdown-link-check-disable -->
* [CoinTracker's summary on this topic](https://www.cointracker.io/blog/what-tax-forms-should-crypto-holders-file)
<!-- markdown-link-check-enable-->
* [IRS Virtual Currency FAQ](https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-virtual-currency-transactions)

Also read the question on [crypto tax resources](#which-resources-can-i-use-to-learn-about-crypto-taxes).

## Tax Scenarios

### What if I and My Spouse File Taxes Jointly?
The names of people filing taxes jointly should be added to the holders section of the config file (which is used for validation) and also in the holder column of each transaction in the input file. With this information RP2 generates a joint output. Here's an example in which the people filing jointly are called Alice and Bob:
* [config/crypto_example.ini](../config/crypto_example.ini) (see Alice and Bob in the holders section)
* [input/crypto_example.ods](../input/crypto_example.ods) (see transactions moving BTC from Bob to Alice in the INTRA table of the BTC tab).

See the [input files](input_files.md) section of the documentation for format details.

### How to Handle a Transfer of Funds from a Wallet or Exchange to Another?
If the both the source and destination accounts belong to the same owner (or to [people filing jointly](#what-if-i-and-my-spouse-file-taxes-jointly)), use an intra-transaction. Otherwise, use an out-transaction. See the [input files](input_files.md) section of the documentation for format details.

### If I Transfer Cryptocurrency Between Two Accounts I Own, Is the Fee Taxable?
Such fees affect which purchase lots are matched against which sales, so RP2 keeps track of them (in the "Investment Expenses" tab of the tax_report_us output). Ask your tax professional about how to handle this tab in any given year.

> **Note:** When an intra-transaction has a non-zero crypto fee (i.e. `crypto_sent > crypto_received`), RP2 treats the fee as a taxable event and generates a gain/loss entry for it. This follows IRS Notice 2014-21 (property disposed to pay a fee triggers a gain/loss) and IRS Digital Assets FAQ Q97 (gain/loss recognised on digital assets used to pay transaction fees — fair market value (FMV) at disposal minus your cost basis (the price you originally paid for the crypto)). If the fee was zero, no taxable event is generated. This behavior is intentional but easy to miss: moving coins between your own wallets will produce a gain/loss line in your tax report whenever a crypto fee is charged.
>
> **References:**
> * IRS Digital Assets FAQ Q81 (wallet-to-wallet transfers are non-taxable except for fees paid in crypto): https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-digital-asset-transactions
> * IRS Digital Assets FAQ Q97 (gain/loss on crypto used to pay transaction fees): https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-digital-asset-transactions
> * IRS Notice 2014-21 (crypto is property; property disposal rules apply to fees): https://www.irs.gov/pub/irs-drop/n-14-21.pdf

### How to Represent Fiat Vs Crypto Transaction Fees?
Here are the possible scenarios for in and out-transaction fees (intra-transactions fees are implicitly defined as `crypto_sent` - `crypto_received`):
* if the fee was paid in fiat: use `crypto_fee` == 0 (or empty) and `fiat_fee` >= 0: RP2 uses `fiat_fee` as passed in;
* if the fee was paid in the same crypto as the transaction: use `crypto_fee` > 0 and `fiat_fee` empty: RP2 populates `fiat_fee` internally as `spot_price` * `crypto_fee`. Note that for in-transactions, the crypto fee comes out of the crypto amount of the in-transaction: RP2 models this by creating an additional, artificial, [fee-only out-transaction](#how-to-handle-fee-only-defi-transactions) in the amount of the crypto fee;
* if the fee was paid in the same crypto as the transaction, but the exchange reports a `fiat_fee` value that doesn't match `crypto_fee` (sometimes this occurs on some exchanges, like Coinbase): use `crypto_fee` >= 0 and `fiat_fee` >= 0 (this should generate a warning, but RP2 will use the fiat_fee in the calculation of taxes);
* if the fee was paid in a different crypto than the one the transaction is denominated in: use an additional [fee-only transaction](#how-to-handle-fee-only-defi-transactions) (`transaction_type` set to FEE), denominated in the new crypto.

### How to Handle Conversion of a Cryptocurrency to Another?
Converting from one cryptocurrency to another can be captured in RP2 by splitting the original transaction into two:
* a SELL-type out-transaction that describes selling the initial cryptocurrency into fiat, and
* a BUY-type in-transaction that describes buying the final cryptocurrency using fiat.

If there was a conversion fee and it was paid in crypto, choose one (and only one) applicable option among the following:
* if the crypto fee was paid with the crypto you are giving up (the *out-currency*), assign it to the `crypto_fee` field of the out-transaction, or
* if the crypto fee was paid with the crypto you are receiving (the *in-currency*), assign it to the `crypto_fee` field of the in-transaction, or
* if the crypto fee was paid with a third cryptocurrency (neither the one you gave up nor the one you received), create a new [fee-only transaction](#how-to-handle-fee-only-defi-transactions) (`transaction_type` set to FEE) denominated in that third currency.

If there was a conversion fee and it was paid in fiat, choose one (and only one) of these options:
* assign it to the `fiat_fee` of the in-transaction, or
* assign it to the `fiat_fee` of the out-transaction.

See the [input files](input_files.md) section of the documentation for format details.

> **Important — holding period resets on every exchange (IRS Digital Assets FAQ Q74):** When you receive new crypto in a swap, the holding period for the **received** asset starts fresh on the day you receive it — regardless of how long you held the asset you gave up. For example, if you held ETH for 2 years (long-term) and swap it for BTC today, the BTC holding period begins today. If you sell the BTC within a year, the gain is **short-term**, not long-term.
>
> **How this affects RP2:** The BUY-type in-transaction you create for the received crypto should be dated the day of the swap. RP2 calculates the holding period from that date forward, which is exactly the correct IRS treatment.
>
> **Reference:** IRS Digital Assets FAQ Q74 (holding period for exchanged digital assets begins the day after receipt): https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-digital-asset-transactions

### How to Handle Airdrops?
Use an in-transaction and mark the transaction type as AIRDROP. RP2 will collect gain/loss computations for all such transactions in a tab in the tax_report_us output. Also read question on [which tax forms to file](#which-crypto-tax-forms-to-file) and see the [input files](input_files.md) section of the documentation for format details.

> **Tax treatment:** Airdropped tokens are ordinary income at their fair market value on the date you receive them (i.e. gain dominion and control over them) — not a capital gain. The FMV at receipt becomes your cost basis for future disposals. Enter the spot price at the moment you could first access the tokens, not the date the airdrop was announced.
>
> **References:**
> * Revenue Ruling 2019-24 (Rev. Rul. 2019-24) (airdrop income recognised at FMV when dominion and control obtained): https://www.irs.gov/pub/irs-drop/rr-19-24.pdf
> * IRS Digital Assets FAQ (airdrops treated as ordinary income, FMV at receipt is basis): https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-digital-asset-transactions

### How to Handle Donations?
Use an in-transaction (if receiving crypto) or out-transaction (if giving crypto) and mark the transaction type as DONATION. RP2 will collect gain/loss computations for all such transactions in a tab in the tax_report_us output. Also read question on [which tax forms to file](#which-crypto-tax-forms-to-file) and see the [input files](input_files.md) section of the documentation for format details.

### Important: Tax Treatment of Donations vs. Gifts
> **Note:** RP2 computes cost basis and gain/loss for DONATE and GIFT out-transactions the same way it does for SELL. The computed figures appear in dedicated tabs in the tax output for your records and for use by a tax professional. **RP2 does not automatically apply different tax treatment based on transaction type.** The actual tax treatment differs significantly under US law:
>
> * **Charitable donation (DONATE) to a 501(c)(3) (a registered nonprofit charity):** Appreciated crypto donated directly to a qualified charity is generally **not subject to capital gains tax**. Instead the donor may deduct the fair market value at the time of donation. The gain/loss figure RP2 computes shows the appreciation, which your tax professional will use to determine the charitable deduction — not to compute a capital gains liability.
>
> * **Gift (GIFT):** A gift of crypto is generally **not a taxable event for the giver** with respect to capital gains. However, gifts above the annual gift tax exclusion ($18,000 per recipient in 2024 — the amount you can give to one person per year before gift tax filing is required) are subject to gift tax, and the recipient inherits the giver's original cost basis (called *carry-over basis* — meaning the recipient's starting cost for future tax calculations is the same price the giver originally paid). The gain/loss RP2 computes is for record-keeping only.
>
> Always consult a tax professional for the correct treatment in your specific situation and year.

### How to Handle Gifts?
Use an in-transaction (if receiving crypto) or out-transaction (if giving crypto) and mark the transaction type as GIFT. RP2 will collect gain/loss computations for all such transactions in a tab in the tax_report_us output. Also read question on [which tax forms to file](#which-crypto-tax-forms-to-file) and see [Important: Tax Treatment of Donations vs. Gifts](#important-tax-treatment-of-donations-vs-gifts) above. See the [input files](input_files.md) section of the documentation for format details.

> **Important — receiving a gift (basis rules):** When you *receive* a gift of crypto, your cost basis under IRC §1015 depends primarily on whether the property was *appreciated* or *depreciated* at the time of the gift:
>
> * **Appreciated property — donor's basis ≤ FMV at gift date (the common case):** Your basis is the donor's original basis, used for both gain and loss on any future sale.
> * **Depreciated property — donor's basis > FMV at gift date:** A dual-basis rule applies:
>   * Sale at a **gain** (sale price > donor's basis): use the donor's basis.
>   * Sale at a **loss** (sale price < FMV at gift date): use the FMV at gift date as your basis.
>   * Sale price **between** the gift-date FMV and the donor's basis: no gain or loss is recognized.
>
> RP2 has no built-in model for this: there is no way to tag an in-transaction as "received as gift" so that the correct dual-basis rule applies automatically. **Workaround:** Record the in-transaction with the donor's original cost basis as the `spot_price` (converted to per-unit). Keep a note of the FMV at the gift date. When you later sell, manually determine which basis rule applies and adjust if necessary before filing — or consult a tax professional.
>
> **Reference:** IRC §1015 (transferred basis for gifts): https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section1015&edition=prelim

### How to Handle Inherited Crypto?

> **Important — RP2 limitation:** Inherited property receives two IRS benefits that RP2 cannot automatically apply:
>
> 1. **Stepped-up basis (IRC §1014):** The recipient's cost basis is the fair market value on the date of the decedent's death, not the decedent's original purchase price.
> 2. **Automatic long-term holding period (IRC §1223(11)):** Inherited property is treated as held long-term regardless of how long it was actually held — even if you sell it the day you inherit it.
>
> **Workaround:** Enter the inherited crypto as a BUY-type in-transaction dated at the date of death, with `spot_price` set to the FMV at that date. This gives the correct stepped-up cost basis. However, RP2 will still compute the holding period from that date, so if you sell within 365 days of the inheritance date it will incorrectly classify the gain as short-term. You will need to manually override this classification on your tax return or consult your tax professional.
>
> **Reference:** IRC §1014 (stepped-up basis): https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section1014&edition=prelim — IRC §1223(11) (automatic LTCG holding period for inherited property): https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section1223&edition=prelim

### How to Handle Hard Forks?
Use an in-transaction and mark the transaction type as HARDFORK. RP2 will collect gain/loss computations for all such transactions in a tab in the tax_report_us output. Also read question on [which tax forms to file](#which-crypto-tax-forms-to-file) and see the [input files](input_files.md) section of the documentation for format details.

> **Tax treatment:** A hard fork that creates a new asset generates ordinary income equal to the fair market value of the new tokens at the time you receive them. A soft fork (no new asset) and a hard fork that does not produce new tokens for you are both non-events for tax purposes. RP2 models the taxable scenario: enter a HARDFORK in-transaction only when you actually receive new tokens.
>
> **Important — "dominion and control" timing:** Under Rev. Rul. 2019-24, hard fork income is recognized only when the taxpayer actually has the ability to claim the new coins (i.e. gains "dominion and control"), not necessarily at the moment the fork occurs at the blockchain level. If the coins are on an exchange that does not immediately support the new chain, income should be recognized when the exchange distributes the coins or you can otherwise access them — not at the exact moment the fork occurred on the blockchain. Make sure the timestamp of your HARDFORK in-transaction reflects the date you actually received access to the coins.
>
> **References:**
> * Rev. Rul. 2019-24 (hard fork and airdrop income recognised at FMV when dominion and control obtained): https://www.irs.gov/pub/irs-drop/rr-19-24.pdf
> * IRS Digital Assets FAQ Q103-Q107 (soft forks = no income; hard fork without new asset = no income; hard fork with new asset = ordinary income at FMV; basis = FMV included in income): https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-digital-asset-transactions

### How to Handle Miscellaneous Crypto Income?
Miscellaneous income covers gains from reward programs like Coinbase Earn, etc. Use an in-transaction and mark the transaction type as INCOME. RP2 will collect gain/loss computations for all such transactions in a tab in the tax_report_us output. Also read question on [which tax forms to file](#which-crypto-tax-forms-to-file) and see the [input files](input_files.md) section of the documentation for format details.

### How to Handle Crypto Interest?
Use an in-transaction and mark the transaction type as INTEREST. RP2 will collect gain/loss computations for all such transactions in a tab in the tax_report_us output. Also read question on [which tax forms to file](#which-crypto-tax-forms-to-file) and see the [input files](input_files.md) section of the documentation for format details.

### How to Handle Income from Mining?
Use an in-transaction and mark the transaction type as MINING. RP2 will collect gain/loss computations for all such transactions in a tab in the tax_report_us output. Also read question on [which tax forms to file](#which-crypto-tax-forms-to-file) and see the [input files](input_files.md) section of the documentation for format details.

> **Tax treatment:** Mined coins are ordinary income at their fair market value on the date received. The FMV at receipt becomes your cost basis for future disposals. If you mine as a business (self-employed), the income is also subject to self-employment tax.
>
> **Reference:** IRS Notice 2014-21 Q8 (mining rewards are gross income at FMV when received): https://www.irs.gov/pub/irs-drop/n-14-21.pdf

### How to Handle Income from Staking?
Use an in-transaction and mark the transaction type as STAKING. RP2 will collect gain/loss computations for all such transactions in a tab in the tax_report_us output. Also read question on [which tax forms to file](#which-crypto-tax-forms-to-file) and see the [input files](input_files.md) section of the documentation for format details.

> **Tax treatment:** Staking rewards are ordinary income at their fair market value on the date you first have access to them and can freely transfer or sell them. The FMV at receipt is your cost basis for future disposals. This is true even if the rewards are automatically re-staked on your behalf.
>
> **Reference:** Revenue Ruling 2023-14 (Rev. Rul. 2023-14) (staking rewards are income at FMV when received): https://www.irs.gov/pub/irs-drop/rr-23-14.pdf

### How to Handle Losses from Staking?
This is useful to capture situations where the protocol penalizes users (e.g. when their node is offline for too long, slashing, etc.). Use an out-transaction and mark the transaction type as STAKING. RP2 will collect gain/loss computations for all such transactions in a tab in the tax_report_us output. Also read question on [which tax forms to file](#which-crypto-tax-forms-to-file) and see the [input files](input_files.md) section of the documentation for format details.

> **Note on slashing (involuntary stake loss):** If a protocol slashes your stake (forcibly removes crypto from your balance), enter it as an out-transaction with `transaction_type = STAKING`, `crypto_out_no_fee` set to the slashed amount, and `crypto_fee = 0`. RP2 has no dedicated slash transaction type; using an out-transaction correctly deducts the amount from your balance and generates the appropriate gain/loss entry. Do not try to enter a negative amount in an in-transaction — RP2 validates that in-transaction amounts are positive.

### How to Handle Income from Crypto Wages?
Use an in-transaction and mark the transaction type as WAGES. RP2 will collect gain/loss computations for all such transactions in a tab in the tax_report_us output. Also read question on [which tax forms to file](#which-crypto-tax-forms-to-file) and see the [input files](input_files.md) section of the documentation for format details.

> **Tax treatment:** Crypto received as wages is ordinary income at its fair market value on the date received, and is subject to income tax withholding, FICA (Federal Insurance Contributions Act — Social Security and Medicare taxes), and FUTA (Federal Unemployment Tax Act) just like cash wages. The FMV at receipt is your cost basis for future disposals. If you are an independent contractor paid in crypto, the income is self-employment income (IRS FAQ Q60).
>
> **Reference:** IRS Digital Assets FAQ Q57-Q61 (crypto wages and contractor payments = ordinary income at FMV; subject to employment taxes): https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-digital-asset-transactions

### How to Handle Crypto Rewards?
This applies to governance and incentive tokens (e.g. COMP) as well as other crypto rewards (e.g. credit card rewards or Coinbase rewards). Use an in-transaction and mark the transaction type as INCOME. RP2 will collect gain/loss computations for all such transactions in a tab in the tax_report_us output. Also read question on [which tax forms to file](#which-crypto-tax-forms-to-file) and see the [input files](input_files.md) section of the documentation for format details.

### Important: Lost or Stolen Crypto May Not Be Tax-Deductible

RP2 has a LOST out-transaction type for crypto that is lost or stolen. RP2 computes a gain/loss figure for LOST transactions the same way it does for SELL, and includes the result in the tax output.

> **Warning — TCJA 2018 deductibility limitation:** The Tax Cuts and Jobs Act of 2017 severely restricted personal casualty and theft loss deductions for tax years 2018–2025 (IRC §165(h)(5)). Under this law:
>
> * **Personal casualty/theft losses are generally NOT deductible** unless they arise from a federally declared disaster.
> * Losing crypto (lost private keys, forgotten passwords, defunct exchanges) and having crypto stolen are both affected — you almost certainly cannot deduct these losses on a personal return for tax years 2018–2025.
> * **Business theft losses (IRC §165(c)(1)) remain deductible**, so if the crypto was held as part of a business, different rules apply.
>
> **Practical guidance:** The loss figure RP2 computes for LOST transactions may be useful for record-keeping and in case tax law changes, but do not assume it will automatically reduce your tax liability. Consult a tax professional before claiming any loss deduction for lost or stolen crypto.
>
> **References:**
> * IRC §165(h)(5) (TCJA personal casualty loss limitation): https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section165&edition=prelim
> * IRS Digital Assets FAQ Q64 (stolen/lost digital assets): https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-digital-asset-transactions

### How to Handle Fee-only DeFi Transactions?
DeFi opens up new scenarios that have their own tax implications. For example:
* a transaction calls a smart contract function that executes and costs some ETH or BNB;
* investment in a DEFI project where a percentage of invested tokens are "burned";
* send 100 CAKE from one Binance Smart Chain (BSC) wallet to another — the fees are paid in BNB (Binance's native token), not in CAKE.

In RP2 such native crypto costs can be captured via an [OUT/FEE transaction](input_files.md#out-transaction-table-format).

Remember to use the Notes field to provide context about the nature of the transaction. See the [input files](input_files.md) section of the documentation for format details.

### How to Handle DeFi Bridging?
DeFi bridging is the process of moving cryptocurrency from one blockchain network to another (e.g. from Ethereum to Polygon) using a *bridge* protocol — typically by locking tokens on the source chain and receiving equivalent wrapped tokens on the destination chain. There is an ongoing debate on how to manage DeFi bridging from a tax perspective. I don't have a definitive answer to the question, but RP2's basic transaction types (BUY, SELL, FEE, etc.) can be used to describe many tax scenarios in different ways. Read the the [RP2 Defi Wiki](https://github.com/eprbell/rp2/wiki/DEFI-Brainstorming), the [RP2 Defi Brainstorming](https://github.com/eprbell/rp2/issues/4), and always double-check with your tax professional. If you have additional insight on this, feel free to contribute to the issue or open a new one.

### How to Handle DeFi Reflexive Tokens?
Reflexive tokens (also called rebase or elastic supply tokens) automatically adjust every holder's wallet balance up or down — without any action on your part — in order to keep the token's price near a target value. For example, if the price rises above target, every holder's balance increases proportionally; if the price falls below target, balances shrink. There is an ongoing debate on how to manage DeFi reflexive tokens from a tax perspective. I don't have a definitive answer to the question, but RP2's basic transaction types (BUY, SELL, FEE, etc.) can be used to describe many tax scenarios in different ways. Read the the [RP2 Defi Wiki](https://github.com/eprbell/rp2/wiki/DEFI-Brainstorming), the [RP2 Defi Brainstorming](https://github.com/eprbell/rp2/issues/4), and always double-check with your tax professional. If you have additional insight on this, feel free to contribute to the issue or open a new one.

### How to Handle DeFi Yield from Liquidity Pools?
DeFi opens up new scenarios, like liquidity pools, that have their own tax implications. For example:
* lock 100 DRIP forever and then get 1 DRIP per day back for a max of 365 days;
* buy a "node" that consumes 10 STRONG, but after that the node produces 0.1 STRONG per day, forever.

There is an ongoing debate on how to capture this scenario from a tax perspective: how is the locked-forever crypto handled? Are the first yields considered "recovered" capital and the following ones staking? I don't have a definitive answer to the question, but RP2's basic transaction types (BUY, SELL, FEE, etc.) can be used to describe many tax scenarios in different ways. Read the the [RP2 Defi Wiki](https://github.com/eprbell/rp2/wiki/DEFI-Brainstorming), the [RP2 Defi Brainstorming](https://github.com/eprbell/rp2/issues/4), and always double-check with your tax professional. If you have additional insight on this, feel free to contribute to the issue or open a new one.

### How to Handle DeFi Liquidity Pool Deposits and Withdrawals?

When you deposit tokens into a liquidity pool (e.g. Uniswap, Curve) you typically exchange your tokens for LP (liquidity provider) tokens — a receipt representing your share of the pool. When you withdraw, you give back the LP tokens and receive your underlying tokens plus any accumulated trading fees, though the amounts may differ from what you deposited due to *impermanent loss* (a reduction in value that occurs when the price ratio of the pooled tokens shifts away from the ratio at the time you deposited, compared to simply having held the tokens). The IRS has not issued specific guidance on LP tokens, but under the general property rules of IRS Notice 2014-21 each exchange is likely a taxable event.

> **Important — RP2 has no native LP token model.** You must manually decompose each deposit and withdrawal into RP2's basic transaction types:
>
> * **Deposit (e.g. deposit ETH + USDC, receive LP token):**
>   * Enter a SELL-type out-transaction for each token you contributed (ETH, USDC) at FMV on the deposit date.
>   * Enter a BUY-type in-transaction for the LP token received, at the same total FMV.
> * **Withdrawal (e.g. burn LP token, receive ETH + USDC back):**
>   * Enter a SELL-type out-transaction for the LP token at FMV on the withdrawal date.
>   * Enter a BUY-type in-transaction for each token received (ETH, USDC) at FMV.
> * **Fee income accruing continuously in the pool:** Record these as INCOME-type in-transactions when you claim or realize them.
>
> **Note:** There is ongoing debate among tax professionals about whether LP deposits should be treated as non-taxable "contribution" events (analogous to contributing to a partnership) rather than taxable swaps. Consult a tax professional for the most defensible treatment in your situation and year. See also the [RP2 DeFi Brainstorming](https://github.com/eprbell/rp2/issues/4) wiki for community discussion.

### How to Handle Crypto-to-Crypto Swaps on Decentralized Exchanges?

Each swap of one cryptocurrency for another (e.g. ETH → USDC on Uniswap, BTC → ETH via any DEX) is a taxable disposal of the sold asset and a taxable acquisition of the purchased asset. The IRS confirmed this in IRS Digital Assets FAQ Q25 — converting one digital asset to another is a taxable event.

> **RP2 processes each asset independently**, so you must enter both sides of a swap manually:
>
> 1. Enter a SELL-type out-transaction for the asset you sold, at the FMV of what you gave up.
> 2. Enter a BUY-type in-transaction for the asset you received, at the same FMV (i.e. the FMV of what you gave up equals the cost basis of what you received).
>
> RP2 does not validate that the two sides of a swap are consistent with each other. If you omit or mismatch one side, balances or gain/loss figures will be wrong. **Use the Notes field** on both transactions to cross-reference them (e.g. "Swap TX 0xabc… — sold side" and "Swap TX 0xabc… — received side").
>
> **Reference:** IRS Digital Assets FAQ Q25 (converting one digital asset to another is a taxable event): https://www.irs.gov/individuals/international-taxpayers/frequently-asked-questions-on-digital-asset-transactions

### How to Handle NFTs?
RP2 treats NFTs like cryptocurrencies, that is as property. Use a unique asset type for each NFT, both in the config file and in the input spreadsheet (see the [input files](input_files.md) section of the documentation for format details): e.g. ETH_BORED_APE_4363. There is debate on whether NFTs should be treated as *collectibles* instead (an IRS asset category — including art, antiques, and precious metals — taxed at a maximum 28% rate rather than the standard long-term capital gains rates of 0%, 15%, or 20%), but this has not been clarified officially by the IRS yet, to the best of my knowledge. Ask a tax professional for the correct answer in any given year.

### How to Handle Margin Trading?
Margin trading generates normal capital gains and losses, so it can be recorded using RP2's standard transaction types. For more information on this topic check <!-- markdown-link-check-disable -->[CoinTracker's guide to margin trading taxes](https://www.cointracker.io/blog/taxes-on-margin-trading-ultimate-guide)<!-- markdown-link-check-enable --> or ask a tax professional.

### How to Handle Futures and Options?
Calling for help on this question: if you have insight on this please open an issue or a PR.

> **Important — Section 1256 contracts (regulated crypto futures):** Bitcoin and Ether futures traded on regulated exchanges such as the Chicago Mercantile Exchange (CME) may qualify as Section 1256 contracts under IRC §1256. Section 1256 contracts receive special tax treatment that RP2 **does not currently implement**:
>
> * **Mark-to-market at year-end:** All open positions (futures contracts you have not yet settled or closed) are treated as if you sold them at their fair market value on December 31, and any resulting gain or loss is taxable for that year — even though you never actually sold.
> * **60/40 split:** Regardless of actual holding period, 60% of the net gain or loss is treated as long-term capital gain/loss and 40% as short-term.
> * **Loss carryback:** If you have a net loss on Section 1256 contracts, you may apply it retroactively against Section 1256 gains from the previous three tax years — potentially generating a refund — rather than only carrying it forward to offset future income.
>
> If you trade regulated crypto futures, RP2's output will not correctly reflect these rules. Consult a tax professional and file Form 6781 (Gains and Losses From Section 1256 Contracts and Straddles) separately.
>
> **Reference:** IRC §1256: https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section1256&edition=prelim

### Important: Wash Sale Rules Do Not Currently Apply to Crypto

Under IRC §1091, the wash sale rule prevents you from claiming a capital loss if you buy a "substantially identical" security within 30 days before or after selling it at a loss. This rule applies to stocks and securities but **does not currently apply to cryptocurrency** because the IRS treats crypto as property, not a security.

This means:
* You can sell crypto at a loss to realize a tax deduction, then immediately repurchase the same crypto — the loss is not disallowed.
* This "tax-loss harvesting" strategy is currently legal for crypto and is a notable advantage over holding stocks.

> **Warning — potential future change:** Several pieces of legislation have proposed extending wash sale rules to crypto and other digital assets. If such a law passes, wash sale detection would need to be applied retroactively to the effective date. RP2 does not currently implement wash sale detection.
>
> **Stay current:** Check with a tax professional each year and watch for legislative changes, especially if you engage in tax-loss harvesting.
>
> **Reference:** IRC §1091 (wash sale rule, currently applies only to stock and securities): https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section1091&edition=prelim
