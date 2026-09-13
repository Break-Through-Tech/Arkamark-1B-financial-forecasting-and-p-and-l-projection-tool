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

## Section 3: Derived Columns (to be created later)

None yet. Per the project overview, building the margin structure is an
October (Modeling) milestone task, not part of this September EDA work —
see "Build the 'sales-to-P&L' engine" in Challenge-Project-Overview.md.
When that work starts, it will add, per company-year:
- `cogs_pct` = `costOfRevenue / totalRevenue`
- `gross_margin_pct` = `grossProfit / totalRevenue`
- `opex_pct` = `totalOperatingExpenses / totalRevenue`
- `ebit_margin_pct` = `ebit / totalRevenue`
