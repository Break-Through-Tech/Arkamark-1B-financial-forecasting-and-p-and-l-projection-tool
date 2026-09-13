import pandas as pd
import numpy as np
import os

RAW_DIR = 'data/raw'
PROCESSED_DIR = 'data/processed'

# Only the fields needed for margin-structure analysis (COGS%, opex%, EBIT%) will be kept.
# I dropped discontinuedOperations/otherOperatingExpenses/minorityInterest/
# researchDevelopment/interestExpense because over 25% of their columns are missing and they are structurally absent for
# most companies. I also dropped netIncomeApplicableToCommonShares/netIncomeFromContinuingOps/
# totalOtherIncomeExpenseNet because they are redundant with netIncome for this project's scope.

FINANCIALS_KEEP_COLS = [
    'stock', 'endDate', 'totalRevenue', 'costOfRevenue', 'grossProfit',
    'totalOperatingExpenses', 'sellingGeneralAdministrative',
    'operatingIncome', 'ebit', 'incomeBeforeTax', 'incomeTaxExpense',
    'netIncome',
]


def clean_favorita():
    """This is my teammate's function for cleaning the Favorita sales data."""
    # TODO (by Tanzina).
    raise NotImplementedError("clean_favorita() not yet implemented")


def clean_financials():
    """This cleans the annual income statement data so it's ready for margin
    analysis (COGS%, opex%, EBIT%). See the comment above FINANCIALS_KEEP_COLS
    for why I kept the columns I kept."""

    df = pd.read_csv(f'{RAW_DIR}/incomeStatementHistory_annually.csv')
    rows_start = len(df)
    raw_cols = set(df.columns)

    # A handful of companies file more than one row for the same period
    # (restatements, probably), so I'm just keeping the first one I see.
    dupe_count = df.duplicated(subset=['stock', 'endDate']).sum()
    df = df.drop_duplicates(subset=['stock', 'endDate'], keep='first')

    dropped_cols = sorted(raw_cols - set(FINANCIALS_KEEP_COLS))
    df = df[FINANCIALS_KEEP_COLS].copy()

    df['endDate'] = pd.to_datetime(df['endDate'])
    numeric_cols = [c for c in FINANCIALS_KEEP_COLS if c not in ('stock', 'endDate')]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

    # I'm dropping these rows instead of imputing them. Guessing a company's
    # COGS or EBIT would just distort the margin benchmarks I'm building
    # toward, so I'd rather lose the row than make up a number.
    rows_before_na = len(df)
    df = df.dropna(subset=numeric_cols)
    rows_dropped_na = rows_before_na - len(df)

    # Zero or negative revenue makes a margin % meaningless (you'd get a
    # divide-by-zero or a flipped sign), and it usually means the row is some
    # kind of non-operating filing rather than a normal year of business.
    rows_before_revenue = len(df)
    df = df[df['totalRevenue'] > 0]
    rows_dropped_revenue = rows_before_revenue - len(df)

    # Negative cost or expense figures don't make economic sense here, so
    # I'm treating them as data errors rather than real accounting entries.
    rows_before_negative = len(df)
    df = df[(df['costOfRevenue'] >= 0) & (df['totalOperatingExpenses'] >= 0)]
    rows_dropped_negative = rows_before_negative - len(df)

    print(f"\n{'='*50}")
    print("FINANCIALS CLEANING SUMMARY")
    print(f"{'='*50}")
    print(f"Started with {rows_start} rows, {len(raw_cols)} columns.")
    print(f"Dropped {dupe_count} duplicate (stock, endDate) rows.")
    print(f"Dropped {len(dropped_cols)} sparse/unused columns: {dropped_cols}")
    print(f"Dropped {rows_dropped_na} rows with missing values in the remaining {len(numeric_cols)} numeric columns.")
    print(f"Dropped {rows_dropped_revenue} rows with totalRevenue <= 0.")
    print(f"Dropped {rows_dropped_negative} rows with negative costOfRevenue or totalOperatingExpenses.")
    print(f"Final shape: {df.shape}")

    return df


if __name__ == "__main__":
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    df_financials = clean_financials()
    df_financials.to_csv(f'{PROCESSED_DIR}/financials_clean.csv', index=False)
    print(f"\nSaved cleaned financials to {PROCESSED_DIR}/financials_clean.csv")

    # Tanzina, this try/except is just so the script doesn't crash on my end while
    # clean_favorita() is not implemented. Once you've implemented it, feel free
    # to remove the try/except and call it the same way as clean_financials() above.
    try:
        df_favorita = clean_favorita()
        df_favorita.to_csv(f'{PROCESSED_DIR}/favorita_sales_clean.csv', index=False)
        print(f"\nSaved cleaned Favorita sales to {PROCESSED_DIR}/favorita_sales_clean.csv")
    except NotImplementedError as e:
        print(f"\nSkipping Favorita sales cleaning: {e}")
