# Data Dictionary

## Section 1: Corporación Favorita Sales

**Source file:** `data/raw/train.csv`
**Cleaned output:** `data/processed/favorita_sales_clean.csv` (see `notebooks/02_data_cleaning.py`)
**Grain:** one row per (date, store, product family)
**Coverage:** 3,000,888 rows; 54 stores; 33 product families; 2013-01-01 to 2017-08-15

| Column | Type | Description |
|---|---|---|
| `id` | int | Unique row identifier (0..N-1, matches row order in the raw file) |
| `date` | date | Observation date |
| `store_nbr` | int | Store identifier (1–54) |
| `family` | string | Product-family category (33 distinct values, e.g. `GROCERY I`, `BEVERAGES`, `BOOKS`) |
| `sales` | float | Total sales for a product family at a particular store on a particular date. Fractional values are legitimate (15.4% of rows) — this is not a count, and values should not be rounded. |
| `onpromotion` | int | Number of items in that product family that were being promoted at that store/date. This is a count, not a boolean, and can be 0. |
| `sales_outlier_flag` | int (0/1) | New column added during cleaning. `1` marks a statistically extreme `sales` value relative to that store+family's own history; `0` otherwise. This is a **statistical extremity marker, not a "bad data" indicator** — flagged rows were not altered or removed, and many correspond to real demand events (see below). |

**Cleaning performed:** essentially none — investigation found this dataset already clean (0 nulls, 0 duplicate rows, 0 duplicate `(date, store_nbr, family)` keys, no negative/non-finite `sales` or `onpromotion` values). `clean_favorita()` converts `date` to datetime, asserts these invariants hold, computes `sales_outlier_flag`, and writes the result unchanged otherwise. No rows were added, removed, or modified.

**`sales_outlier_flag` method:** computed per `(store_nbr, family)` group, on `log1p(sales)`, flagging values above that group's own 99.5th percentile. Store+family grain was chosen because sales scale varies enormously across families (e.g. `GROCERY I` vs `BOOKS`) and stores; `log1p` tames the heavy right skew in raw sales (skew ≈7.4 → ≈0.4 after transform); a percentile threshold (rather than IQR/MAD) avoids degenerate zero-width fences on the many zero-heavy or zero-only store/family series. 14,225 rows (0.47%) are flagged. Flagged rows cluster around explainable real-world events — e.g. the April 2016 Ecuador earthquake relief-buying surge and month-start payday cycles — not data errors, which is why they are flagged rather than removed.

**Zero-sales rows (31.3% of the dataset):** legitimate, not missing data. 53 `(store, family)` combinations are 100% zero across their entire history (e.g., a store that never carries "BOOKS"). A zero-sales row means the observation was recorded and nothing sold that day, which is different from an absent row.

**Missing dates:** the panel is a perfectly dense grid (54 stores × 33 families × 1,684 dates = exact row count) except for 4 globally-missing dates: December 25 of 2013, 2014, 2015, and 2016. These are structural Ecuador retail closures (stores are closed on Christmas Day), not missing observations, and were not filled in or otherwise interpolated.

## Section 2: Financial Data of 4400+ Public Companies

**Source file:** `data/raw/incomeStatementHistory_annually.csv`
**Cleaned output:** `data/processed/financials_clean.csv` (see `notebooks/02_data_cleaning.py`)
**Grain:** one row per (company, fiscal year-end date)
**Units:** raw USD (not thousands/millions)

| Column | Type | Description |
|---|---|---|
| `stock` | string | Ticker symbol; unique company identifier in this dataset |
| `endDate` | date | Fiscal period end date for the annual filing |
| `totalRevenue` | float | Total revenue / net sales for the period |
| `costOfRevenue` | float | Cost of goods sold (COGS) |
| `grossProfit` | float | `totalRevenue - costOfRevenue` |
| `totalOperatingExpenses` | float | Total operating expenses (opex), including SG&A |
| `sellingGeneralAdministrative` | float | SG&A expense — subset of `totalOperatingExpenses` |
| `operatingIncome` | float | Operating income (`grossProfit - totalOperatingExpenses`, approx.) |
| `ebit` | float | Earnings before interest and taxes — tracks `operatingIncome` closely in this dataset |
| `incomeBeforeTax` | float | Pre-tax income |
| `incomeTaxExpense` | float | Income tax expense |
| `netIncome` | float | Bottom-line net income |

**Columns dropped during cleaning** (present in the raw file, not in `financials_clean.csv`):

| Column | Reason dropped |
|---|---|
| `discontinuedOperations` | 91% missing — not applicable to most companies |
| `otherOperatingExpenses` | 70% missing |
| `minorityInterest` | 69% missing |
| `researchDevelopment` | 66% missing — only reported by R&D-heavy companies |
| `interestExpense` | 25% missing |
| `netIncomeApplicableToCommonShares` | Redundant with `netIncome` for this project's scope |
| `netIncomeFromContinuingOps` | Redundant with `netIncome` for this project's scope |
| `totalOtherIncomeExpenseNet` | Redundant with `netIncome` for this project's scope |

**Row filtering during cleaning** (raw → clean: 17,511 → 16,263 rows):
- Dropped duplicate `(stock, endDate)` rows (restatements) — 0 rows in current data
- Dropped rows with missing values in any kept numeric column — 234 rows
- Dropped rows with `totalRevenue <= 0` (non-operating filings; makes margin % meaningless) — 1,006 rows
- Dropped rows with negative `costOfRevenue` or `totalOperatingExpenses` (treated as data errors) — 8 rows

**Known limitation:** this dataset has no sector/industry column, so identifying "comparable retail companies" for the margin-benchmarking work requires an external ticker list rather than filtering this file directly.

## Section 3: Oil Price

**Source file:** `data/raw/oil.csv`
**Cleaned output:** `data/processed/oil_clean.csv` (see `clean_oil()` in `notebooks/02_data_cleaning.py`)
**Grain:** one row per calendar date
**Coverage:** 1,688 rows; 2013-01-01 to 2017-08-15 (the sales date range)
**Units:** USD per barrel

| Column | Type | Description |
|---|---|---|
| `date` | date | Calendar date. Every day in the range has exactly one row, weekends and holidays included. |
| `dcoilwtico` | float | Daily WTI (West Texas Intermediate) crude oil price. Where no price was observed, this holds the most recent earlier observed price (see filling below). |
| `dcoilwtico_filled_flag` | int (0/1) | New column added during cleaning. `1` means `dcoilwtico` was filled rather than observed on that date; `0` means it is the raw observed price. 525 rows (31.1%) are flagged. |

**Raw file shape:** 1,218 rows, one per weekday from 2013-01-01 to 2017-08-31, no duplicate dates. Weekends are absent as rows, and 43 weekday rows (all inside the sales range) have a blank price. The blanks are all US market holidays — WTI is a US benchmark — e.g. New Year's Day, MLK Day, Presidents' Day, Good Friday, Memorial Day, Independence Day, Labor Day, Thanksgiving, and Christmas (including observed Monday/Friday dates). The first row, 2013-01-01, is one of them.

**Cleaning performed** (raw → clean: 1,218 → 1,688 rows):
- Dropped the 12 rows after 2017-08-15 (the `test.csv` period), so the series matches the sales date range.
- Added a row for each of the 482 absent calendar dates (241 Saturdays, 241 Sundays).
- Forward-filled the 524 missing prices (482 weekend rows + 42 holiday blanks) with the last observed price. No new price is set on a non-trading day, so the last traded price is the price in effect on that day.
- Backfilled the one remaining blank, 2013-01-01, with the 2013-01-02 price (93.14), because it has no earlier price to forward-fill from. This was chosen over dropping the row so that every sales date has an oil price; it is a single holiday, and the row is still flagged as filled.
- No observed prices were changed.

**Joining to sales:** the output covers all 1,688 calendar days, while the sales panel has 1,684 dates (it has no rows for December 25 of 2013–2016). A join on `date` from sales therefore matches every sales date; the 4 Christmas oil rows simply have no sales counterpart.

## Section 4: Interest Rate

**Source file:** `data/raw/DFF.csv`
**Series:** `DFF` — Federal Funds Effective Rate (daily, percent, not seasonally adjusted)
**Source:** Federal Reserve Economic Data (FRED), Federal Reserve Bank of St. Louis; originally from the Board of Governors of the Federal Reserve System (H.15). Downloaded from https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF
**Download date:** 2026-09-27 (raw file covers 1954-07-01 to 2026-09-24, 26,384 rows)
**Cleaned output:** `data/processed/interest_rate_clean.csv` (see `clean_interest_rate()` in `notebooks/02_data_cleaning.py`)
**Grain:** one row per calendar date
**Coverage:** 1,688 rows; 2013-01-01 to 2017-08-15 (the sales date range)

| Column | Type | Description |
|---|---|---|
| `date` | date | Calendar date. Every day in the range has exactly one row. |
| `dff` | float | Effective federal funds rate, in percent (e.g. `0.13` = 0.13%). Renamed from the raw `DFF` column, lowercased to match `dcoilwtico`. |

**Why a US rate:** Ecuador has used the US dollar as its official currency since 2000, so US policy rates are the interest rates that actually apply there. DFF was chosen over FEDFUNDS (monthly only), DGS10 (business days only, would need filling) and DPRIME (changes only on Fed decisions) because it is published for every calendar day.

**Cleaning performed:** none beyond trimming to the sales date range (26,384 → 1,688 rows). Every date in the range is present with a numeric value, so no filling was needed; `clean_interest_rate()` asserts this.

**Known limitation:** the rate barely moves in this period — 0.06% to 1.16%, near zero until the Fed's first hike in December 2015 — so there is little variation for estimating a sales-to-interest-rate relationship.

## Section 5: Macro Drivers Merged

**Source files:** `data/processed/favorita_family_daily_sales.csv` (from `notebooks/03_favorita_trend_analysis.py`), `data/processed/oil_clean.csv`, `data/processed/interest_rate_clean.csv`
**Cleaned outputs** (see `notebooks/05_macro_drivers_merge.py`):
- `data/processed/macro_drivers_merged.csv` — daily; one row per (date, family); 55,704 rows (33 families × 1,688 days)
- `data/processed/macro_drivers_merged_monthly.csv` — monthly; one row per (month, family); 1,848 rows (33 families × 56 months, 2013-01 to 2017-08)

Sales are chain-wide totals per family (summed across all 54 stores). The 4 Dec-25 closure dates are zero-filled in the family daily sales, so they appear as zero-sales rows here.

**Daily file columns:**

| Column | Type | Description |
|---|---|---|
| `date` | date | Calendar date |
| `family` | string | Product family (33 distinct values) |
| `sales` | float | Chain-wide sales for that family on that date |
| `dcoilwtico` | float | WTI oil price for that date, from `oil_clean.csv` (forward-filled on weekends/holidays) |
| `dcoilwtico_filled_flag` | int (0/1) | `1` if the oil price was filled rather than observed that day |
| `dff` | float | Effective federal funds rate (percent), from `interest_rate_clean.csv` |
| `pre_launch_flag` | int (0/1) | `1` if the date is before the family's launch — its zero sales mean the product line wasn't stocked yet, not zero demand. A family whose first sale is in the first week of 2013 is treated as selling from the start (2013-01-01 is New Year's Day). 5,161 rows. |
| `low_confidence_flag` | int (0/1) | Family-level; the same value on every row for a family. See below. |

**Monthly file columns:**

| Column | Type | Description |
|---|---|---|
| `month` | date | First day of the month |
| `family` | string | Product family |
| `sales` | float | Sum of daily sales in the month |
| `dcoilwtico` | float | Mean oil price over **observed trading days only** (filled weekend/holiday prices excluded, so Friday's price isn't counted three times; matches how FRED builds its monthly average) |
| `dff` | float | Mean rate over all calendar days in the month |
| `days_in_data` | int | Number of days of data in the month |
| `is_partial_month` | int (0/1) | `1` if the month has fewer days of data than calendar days. Only August 2017 (15 of 31 days, data ends 2017-08-15); its summed sales are about half a normal month, so don't read it as a sales drop. |
| `pre_launch_flag` | int (0/1) | `1` if any day in the month is before the family's launch, so the monthly total understates a full month of selling (173 rows) |
| `low_confidence_flag` | int (0/1) | Same family-level flag as the daily file |

**`low_confidence_flag` method:** a family is flagged if its first chain-wide sale is on or after 2014-01-01 (late-introduced), **or** more than 50% of its days have zero sales (sparse; the same threshold as `03_favorita_trend_analysis.py`). 11 families are flagged: BABY CARE, BOOKS, CELEBRATION, HOME AND KITCHEN I, HOME AND KITCHEN II, HOME CARE, LADIESWEAR, MAGAZINES, PET SUPPLIES, PLAYERS AND ELECTRONICS, SCHOOL AND OFFICE SUPPLIES. Ten launched between 2014-01-01 and 2014-03-01; BOOKS launched on 2016-10-08 and is also the only family above the sparse threshold (83% zero days). These families have at most ~3.6 years of history (BOOKS ~10 months), so models and elasticities fit on them are less reliable. PRODUCE (first sale 2013-03-16) is deliberately not flagged: it is ~11% of all sales and only its first 74 days are missing, which `pre_launch_flag` already marks.

**Known limitations:**
- 10 of the 11 flagged families also have whole calendar months of exactly zero chain-wide sales after launch (February, April–June and August 2014, and for 8 of them January 2015 through March, April or May 2015). The gaps start and end on month boundaries across several families at once, so they look like data-recording gaps rather than zero demand. They are not flagged separately; the family-level `low_confidence_flag` covers them, and no unflagged family has a zero-sales month after launch.
- No construction index is available for Ecuador, so the construction-index driver named in the project overview cannot be analyzed. Only oil and the interest rate are included.

## Section 6: Derived Columns (to be created later)

None yet. Per the project overview, building the margin structure is an
October (Modeling) milestone task, not part of this September EDA work —
see "Build the 'sales-to-P&L' engine" in Challenge-Project-Overview.md.
When that work starts, it will add, per company-year:
- `cogs_pct` = `costOfRevenue / totalRevenue`
- `gross_margin_pct` = `grossProfit / totalRevenue`
- `opex_pct` = `totalOperatingExpenses / totalRevenue`
- `ebit_margin_pct` = `ebit / totalRevenue`
