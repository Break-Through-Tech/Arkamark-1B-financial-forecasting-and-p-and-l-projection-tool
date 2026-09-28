import os
import pandas as pd

FAMILY_DAILY_CSV = 'data/processed/favorita_family_daily_sales.csv'
OIL_CSV = 'data/processed/oil_clean.csv'
RATE_CSV = 'data/processed/interest_rate_clean.csv'
DAILY_OUT_CSV = 'data/processed/macro_drivers_merged.csv'
MONTHLY_OUT_CSV = 'data/processed/macro_drivers_merged_monthly.csv'

# A family is low-confidence if it launched chain-wide on or after this date,
# or if more than SPARSE_THRESHOLD of its days have zero chain-wide sales.
# 10 families launched between 2014-01-01 and 2014-03-01 and BOOKS on
# 2016-10-08, so they have at most ~3.6 years (BOOKS: ~10 months) of history
# versus ~4.6 years for the rest. The cutoff deliberately excludes PRODUCE
# (first sale 2013-03-16, ~11% of all sales), whose 74 zero days at the start
# are marked row-by-row with pre_launch_flag instead of flagging the family.
LATE_LAUNCH_CUTOFF = pd.Timestamp('2014-01-01')
SPARSE_THRESHOLD = 0.50   # same ">50% zero-sales days" threshold as 03_favorita_trend_analysis.py

# 2013-01-01 is New Year's Day and most stores were closed, so 4 families
# (AUTOMOTIVE, HARDWARE, HOME APPLIANCES, SEAFOOD) first sell on 2013-01-02.
# A family whose first sale falls in the first week is treated as selling
# from the start, so that holiday isn't marked as "pre-launch".
SERIES_START = pd.Timestamp('2013-01-01')
START_GRACE_DAYS = 7

N_FAMILIES = 33
N_DAYS = 1_688
N_MONTHS = 56             # 2013-01 through 2017-08


def load_inputs():
    """Load the family-level daily sales (from 03) and the cleaned oil and
    interest-rate series (from 02)."""
    sales = pd.read_csv(FAMILY_DAILY_CSV, parse_dates=['date'])
    oil = pd.read_csv(OIL_CSV, parse_dates=['date'])
    rate = pd.read_csv(RATE_CSV, parse_dates=['date'])

    assert len(sales) == N_FAMILIES * N_DAYS, "family daily sales row count changed"
    assert not sales.duplicated(subset=['date', 'family']).any(), "duplicate (date, family) rows"
    assert sales['sales'].isna().sum() == 0, "family daily sales has missing values"
    assert len(oil) == len(rate) == N_DAYS, "macro series don't cover the sales calendar"

    return sales, oil, rate


def family_confidence(sales):
    """Per family: first chain-wide sale date, launch date, share of
    zero-sales days, and the low-confidence flag. Returns one row per family."""
    first_sale = sales[sales['sales'] > 0].groupby('family')['date'].min()
    pct_zero_days = (sales['sales'] == 0).groupby(sales['family']).mean()

    in_first_week = first_sale < SERIES_START + pd.Timedelta(days=START_GRACE_DAYS)
    launch_date = first_sale.where(~in_first_week, SERIES_START)

    families = pd.DataFrame({
        'first_sale_date': first_sale,
        'launch_date': launch_date,
        'pct_zero_days': pct_zero_days,
    })
    is_late = families['first_sale_date'] >= LATE_LAUNCH_CUTOFF
    is_sparse = families['pct_zero_days'] > SPARSE_THRESHOLD
    families['low_confidence_flag'] = (is_late | is_sparse).astype(int)
    families.index.name = 'family'
    return families


def build_daily(sales, oil, rate, families):
    """Join each family's daily sales to that day's oil price and interest
    rate. The macro series are one row per date, so each value repeats across
    the 33 families on that date."""
    daily = sales.merge(oil, on='date', how='left', validate='many_to_one')
    daily = daily.merge(rate, on='date', how='left', validate='many_to_one')
    daily = daily.merge(families[['launch_date', 'low_confidence_flag']],
                        left_on='family', right_index=True, how='left', validate='many_to_one')

    # Days before a family's launch are zeros because the product line wasn't
    # stocked yet, not because nobody bought it.
    daily['pre_launch_flag'] = (daily['date'] < daily['launch_date']).astype(int)
    daily = daily.drop(columns='launch_date')

    daily = daily.sort_values(['family', 'date']).reset_index(drop=True)
    return daily[[
        'date', 'family', 'sales', 'dcoilwtico', 'dcoilwtico_filled_flag', 'dff',
        'pre_launch_flag', 'low_confidence_flag',
    ]]


def build_monthly(daily):
    """Aggregate the daily merged data to one row per (month, family):
    sales summed, oil and interest rate averaged."""
    daily = daily.copy()
    daily['month'] = daily['date'].dt.to_period('M').dt.to_timestamp()

    # Oil is averaged over observed trading days only. The forward-filled
    # weekend/holiday prices would otherwise count Friday's price three times.
    # This matches how FRED builds its own monthly oil average. DFF is published
    # for every calendar day, so it is averaged over all days in the month.
    daily['oil_observed'] = daily['dcoilwtico'].where(daily['dcoilwtico_filled_flag'] == 0)

    monthly = daily.groupby(['month', 'family']).agg(
        sales=('sales', 'sum'),
        dcoilwtico=('oil_observed', 'mean'),
        dff=('dff', 'mean'),
        days_in_data=('date', 'nunique'),
        pre_launch_days=('pre_launch_flag', 'sum'),
        low_confidence_flag=('low_confidence_flag', 'first'),
    ).reset_index()

    # August 2017 only has 15 days of data (through 2017-08-15), so its summed
    # sales are about half a normal month. It's kept, but flagged, so it isn't
    # read as a sales drop.
    monthly['is_partial_month'] = (monthly['days_in_data'] < monthly['month'].dt.days_in_month).astype(int)
    monthly['pre_launch_flag'] = (monthly['pre_launch_days'] > 0).astype(int)
    monthly = monthly.drop(columns='pre_launch_days')

    monthly = monthly.sort_values(['family', 'month']).reset_index(drop=True)
    return monthly[[
        'month', 'family', 'sales', 'dcoilwtico', 'dff', 'days_in_data',
        'is_partial_month', 'pre_launch_flag', 'low_confidence_flag',
    ]]


if __name__ == "__main__":
    print(f"\n{'=' * 50}")
    print("MACRO DRIVERS MERGE")
    print(f"{'=' * 50}")

    sales, oil, rate = load_inputs()
    families = family_confidence(sales)
    daily = build_daily(sales, oil, rate, families)
    monthly = build_monthly(daily)

    assert len(daily) == N_FAMILIES * N_DAYS, "daily row count changed during merge"
    assert daily.isna().sum().sum() == 0, "daily merged data has missing values"
    assert abs(daily['sales'].sum() - sales['sales'].sum()) < 1e-6 * sales['sales'].sum(), \
        "daily sales total changed during merge"
    assert len(monthly) == N_FAMILIES * N_MONTHS, "unexpected monthly row count"
    assert monthly.isna().sum().sum() == 0, "monthly merged data has missing values"
    assert abs(monthly['sales'].sum() - daily['sales'].sum()) < 1e-6 * daily['sales'].sum(), \
        "monthly sales total doesn't match daily"
    assert monthly['is_partial_month'].sum() == N_FAMILIES, "expected only August 2017 to be partial"
    assert families['low_confidence_flag'].sum() == 11, "low-confidence family count changed"

    os.makedirs(os.path.dirname(DAILY_OUT_CSV), exist_ok=True)
    daily.to_csv(DAILY_OUT_CSV, index=False)
    monthly.to_csv(MONTHLY_OUT_CSV, index=False)

    low_conf = families[families['low_confidence_flag'] == 1].sort_values('first_sale_date')
    print(f"Daily rows: {len(daily)} ({N_FAMILIES} families x {N_DAYS} days)")
    print(f"Monthly rows: {len(monthly)} ({N_FAMILIES} families x {N_MONTHS} months)")
    print(f"Partial months flagged: {monthly.loc[monthly['is_partial_month'] == 1, 'month'].dt.strftime('%Y-%m').unique().tolist()}")
    print(f"Pre-launch daily rows flagged: {daily['pre_launch_flag'].sum()}")
    print(f"Low-confidence families ({len(low_conf)}):")
    for family, row in low_conf.iterrows():
        print(f"  - {family}: first sale {row['first_sale_date'].date()}, {row['pct_zero_days']:.1%} zero days")
    print(f"\nSaved daily merged data to {DAILY_OUT_CSV}")
    print(f"Saved monthly merged data to {MONTHLY_OUT_CSV}")
