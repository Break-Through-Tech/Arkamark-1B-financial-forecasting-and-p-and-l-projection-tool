# Data Dictionary

## Section 1: Corporación Favorita Sales

_Owned by: Tanzina (sales dataset) — to be filled in once `clean_favorita()` is implemented._

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
