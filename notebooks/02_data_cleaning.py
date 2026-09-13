import pandas as pd
import numpy as np
import os
import hashlib

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
    """Cleans the Corporacion Favorita sales training data (train.csv).

    Phase 1 investigation (Ticket #8) found this dataset already clean: 0 nulls,
    0 duplicate rows, 0 duplicate (date, store_nbr, family) keys, no negative or
    non-finite sales/onpromotion values, and a perfectly dense panel (54 stores x
    33 families x 1,684 dates = exact row count). So there is almost no row-level
    cleaning to do here -- this function is mostly validation (as assertions,
    documenting the guarantees the raw file already meets) plus one new column:
    a statistical outlier flag."""

    input_path = f'{RAW_DIR}/train.csv'

    # Checksum before and after so we can prove we never wrote back to the raw file.
    with open(input_path, 'rb') as f:
        checksum_before = hashlib.sha256(f.read()).hexdigest()

    df = pd.read_csv(input_path)
    rows_start = len(df)

    df['date'] = pd.to_datetime(df['date'], errors='raise')
    assert df['date'].isna().sum() == 0, "date column has unparseable values"

    # These assertions are expected to PASS without modification -- they document
    # what Phase 1 investigation found rather than fixing anything. If one of
    # these ever fails on a future data refresh, that's a signal to re-investigate,
    # not to silently patch around it.
    assert df['id'].is_unique, "id column has duplicates"
    assert df['id'].min() == 0 and df['id'].max() == rows_start - 1, \
        "id column no longer covers the expected 0..N-1 range"
    assert not df.duplicated(subset=['date', 'store_nbr', 'family']).any(), \
        "duplicate (date, store_nbr, family) business keys found"
    assert df.isnull().sum().sum() == 0, "nulls found in one or more columns"
    assert (df['sales'] >= 0).all() and np.isfinite(df['sales']).all(), \
        "sales has negative or non-finite values"
    assert (df['onpromotion'] >= 0).all(), "onpromotion has negative values"
    assert (df['onpromotion'] % 1 == 0).all(), "onpromotion has non-integer values"
    family_stripped = df['family'].str.strip()
    assert (family_stripped == df['family']).all(), "family has leading/trailing whitespace"
    assert (family_stripped != '').all(), "family has blank values"
    assert rows_start == 3_000_888, "row count no longer matches the investigated raw file"

    # Outlier flag: store+family grain, log1p-transformed, percentile-based.
    # Sales scale varies enormously by family (e.g. GROCERY I vs BOOKS) and by
    # store, so a single global or family-only threshold either over-flags
    # high-volume series or misses anomalies in low-volume ones. log1p tames the
    # heavy right skew (raw sales skew ~7.4, log1p skew ~0.4). A percentile
    # threshold (rather than IQR/MAD) avoids the degenerate zero fences that
    # IQR/MAD produce on the many zero-heavy/zero-only (store, family) series
    # (53 combos are 100% zero sales) -- a percentile still identifies the top
    # of each group's own distribution even when most of it is zero.
    sales_log = np.log1p(df['sales'])
    group_threshold = sales_log.groupby([df['store_nbr'], df['family']]).transform(
        lambda s: s.quantile(0.995)
    )
    df['sales_outlier_flag'] = (sales_log > group_threshold).astype(int)

    assert len(df) == rows_start, "row count changed during cleaning"
    assert list(df.columns) == [
        'id', 'date', 'store_nbr', 'family', 'sales', 'onpromotion', 'sales_outlier_flag'
    ], "unexpected output column set/order"
    assert df['sales_outlier_flag'].isna().sum() == 0, "outlier flag has nulls"

    with open(input_path, 'rb') as f:
        checksum_after = hashlib.sha256(f.read()).hexdigest()
    assert checksum_before == checksum_after, "raw train.csv was modified during cleaning"

    n_flagged = int(df['sales_outlier_flag'].sum())

    print(f"\n{'='*50}")
    print("FAVORITA SALES CLEANING SUMMARY")
    print(f"{'='*50}")
    print(f"Original rows: {rows_start}")
    print(f"Rows removed: 0")
    print(f"Duplicates removed: 0")
    print(f"Missing values handled: 0")
    print(f"Invalid values handled: 0")
    print(f"Outliers flagged: {n_flagged} ({n_flagged / len(df) * 100:.2f}%)")
    print(f"Final rows: {len(df)}")

    return df


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

    df_favorita = clean_favorita()
    df_favorita.to_csv(f'{PROCESSED_DIR}/favorita_sales_clean.csv', index=False)
    print(f"\nSaved cleaned Favorita sales to {PROCESSED_DIR}/favorita_sales_clean.csv")
