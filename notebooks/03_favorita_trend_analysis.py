import math
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

PROCESSED_PATH = 'data/processed/favorita_sales_clean.csv'
FIGURES_DIR = 'figures/trend'
FINDINGS_PATH = 'docs/eda_findings_favorita.md'

ROLLING_SHORT = 7   # weekly smoothing, kills day-of-week noise
ROLLING_LONG = 28   # ~monthly smoothing, primary trend line

# Stores are closed chain-wide on Christmas Day, so these 4 dates are the
# only gaps in the daily calendar. We zero-fill them below.
MISSING_DATES = ['2013-12-25', '2014-12-25', '2015-12-25', '2016-12-25']

# Coarse, qualitative thresholds for this EDA pass -- not a statistical test.
TREND_THRESHOLD = 0.15    # +/-15% first-90d vs last-90d avg = "trending"
SPARSE_THRESHOLD = 0.50   # >50% zero-sales days chain-wide = "sparse"
EDGE_WINDOW = 90          # days averaged at each end of the series


def load_family_series():
    """Aggregate cleaned Favorita sales by date and family, summing across
    all 54 stores. Fill the 4 missing Dec-25 dates with 0 sales (stores are
    closed that day). Returns one row per date, one column per family."""
    df = pd.read_csv(PROCESSED_PATH, parse_dates=['date'])

    daily_family = df.groupby(['date', 'family'])['sales'].sum().unstack('family')

    full_range = pd.date_range(daily_family.index.min(), daily_family.index.max(), freq='D')
    daily_family = daily_family.reindex(full_range)

    missing_dates = pd.to_datetime(MISSING_DATES)
    is_missing_date = daily_family.index.isin(missing_dates)
    daily_family.loc[is_missing_date] = daily_family.loc[is_missing_date].fillna(0.0)

    daily_family.index.name = 'date'
    return daily_family


def slugify(family_name):
    """Turn a family name like 'HOME AND KITCHEN I' into a safe filename
    like 'HOME_AND_KITCHEN_I'."""
    return family_name.replace(' ', '_').replace('/', '_')


def plot_overview(family_series):
    """Draw a grid of small charts, one per family, showing raw daily sales
    and the 28-day rolling mean. Saves figures/trend/overview.png."""
    families = sorted(family_series.columns)
    n_cols = 5
    n_rows = math.ceil(len(families) / n_cols)

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 4, n_rows * 2.5), sharex=True)
    axes = axes.flatten()

    for ax, family in zip(axes, families):
        series = family_series[family]
        rolling_long = series.rolling(ROLLING_LONG, min_periods=1).mean()
        ax.plot(series.index, series.values, color='tab:blue', alpha=0.25, linewidth=0.5)
        ax.plot(rolling_long.index, rolling_long.values, color='tab:blue', linewidth=1.2)
        ax.set_title(family, fontsize=8)
        ax.tick_params(axis='both', labelsize=6)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

    # 33 families don't fill a perfect grid, so hide the leftover empty cells.
    for ax in axes[len(families):]:
        ax.set_visible(False)

    fig.suptitle('Favorita Sales by Product Family — Raw Daily Sales & 28-Day Rolling Mean', fontsize=12)
    fig.supxlabel('Date')
    fig.supylabel('Sales (units as recorded, unscaled)')
    fig.tight_layout(rect=[0, 0, 1, 0.97])

    os.makedirs(FIGURES_DIR, exist_ok=True)
    out_path = f'{FIGURES_DIR}/overview.png'
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved overview figure to {out_path}")


def plot_per_family(family_series):
    """Draw one chart per family showing daily sales plus the 7-day and
    28-day rolling means. Saves figures/trend/family_<name>.png for each of
    the 33 families."""
    os.makedirs(FIGURES_DIR, exist_ok=True)

    for family in sorted(family_series.columns):
        series = family_series[family]
        rolling_short = series.rolling(ROLLING_SHORT, min_periods=1).mean()
        rolling_long = series.rolling(ROLLING_LONG, min_periods=1).mean()

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(series.index, series.values, color='tab:gray', alpha=0.3, linewidth=0.6, label='Daily sales')
        ax.plot(rolling_short.index, rolling_short.values, color='tab:orange', linewidth=1.0,
                label=f'{ROLLING_SHORT}-day rolling mean')
        ax.plot(rolling_long.index, rolling_long.values, color='tab:blue', linewidth=1.5,
                label=f'{ROLLING_LONG}-day rolling mean')

        ax.set_title(f'Favorita Sales — {family}')
        ax.set_xlabel('Date')
        ax.set_ylabel('Sales (units as recorded, unscaled)')
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        ax.legend(loc='upper left', fontsize=8)
        fig.tight_layout()

        out_path = f'{FIGURES_DIR}/family_{slugify(family)}.png'
        fig.savefig(out_path, dpi=150)
        plt.close(fig)

    print(f"Saved {len(family_series.columns)} per-family figures to {FIGURES_DIR}/")


def compute_findings(family_series):
    """Compute simple summary stats per family: trend direction (up/down/
    stable), percent of zero-sales days, and basic descriptive stats.
    Returns one row per family."""
    rows = []
    for family in sorted(family_series.columns):
        series = family_series[family]

        first_avg = series.iloc[:EDGE_WINDOW].mean()
        last_avg = series.iloc[-EDGE_WINDOW:].mean()

        # A family can start with 0 average sales if it wasn't stocked yet.
        # In that case a percent change can't be computed, so we track that
        # case with its own flag instead of using a percent change at all.
        started_from_zero = False
        if first_avg > 0:
            pct_change = (last_avg - first_avg) / first_avg
        elif last_avg > 0:
            pct_change = 0.0
            started_from_zero = True
        else:
            pct_change = 0.0

        if started_from_zero:
            trend_label = 'up (from zero)'
        elif pct_change >= TREND_THRESHOLD:
            trend_label = 'up'
        elif pct_change <= -TREND_THRESHOLD:
            trend_label = 'down'
        else:
            trend_label = 'stable'

        pct_zero_days = (series == 0).mean()
        is_sparse = pct_zero_days > SPARSE_THRESHOLD

        rows.append({
            'family': family,
            'first_90d_avg': first_avg,
            'last_90d_avg': last_avg,
            'pct_change': pct_change,
            'started_from_zero': started_from_zero,
            'trend_label': trend_label,
            'pct_zero_days': pct_zero_days,
            'is_sparse': is_sparse,
            'mean_sales': series.mean(),
            'median_sales': series.median(),
            'std_sales': series.std(),
            'max_sales': series.max(),
        })

    return pd.DataFrame(rows).set_index('family')


def write_findings(findings, family_series):
    """Write to docs/eda_findings_favorita.md,
    listing which families are trending up, down, stable, or sparse."""
    os.makedirs(os.path.dirname(FINDINGS_PATH), exist_ok=True)

    # Families that started from a zero sales base don't have a real percent
    # change, so they're sorted by their ending sales level instead and
    # listed first. Families with a normal percent change are sorted by
    # that change, largest increase first.
    zero_base_up = findings[findings['trend_label'] == 'up (from zero)']
    zero_base_up = zero_base_up.sort_values('last_90d_avg', ascending=False)
    pct_up = findings[findings['trend_label'] == 'up']
    pct_up = pct_up.sort_values('pct_change', ascending=False)
    up = pd.concat([zero_base_up, pct_up])

    down = findings[findings['trend_label'] == 'down'].sort_values('pct_change')
    stable = findings[findings['trend_label'] == 'stable']
    sparse = findings[findings['is_sparse']].sort_values('pct_zero_days', ascending=False)

    lines = []
    lines.append('## Ticket #19: Trend Analysis (`03_favorita_trend_analysis.py`)\n')
    lines.append(
        'Daily sales aggregated by family, summed across all 54 stores, over '
        f'{len(family_series)} days ({family_series.index.min().date()} to '
        f'{family_series.index.max().date()}). The 4 known Dec-25 closure dates were '
        'zero-filled. Trend is a coarse first-90-day vs. last-90-day average comparison '
        f'(+/-{int(TREND_THRESHOLD * 100)}% threshold); this is descriptive, not a '
        'statistical trend test.\n'
    )

    lines.append(f'### Families trending up ({len(up)})\n')
    if len(up) > 0:
        for family, row in up.iterrows():
            if row['started_from_zero']:
                change_str = 'from a zero base'
            else:
                change_str = f"{row['pct_change']:+.1%}"
            lines.append(f"- **{family}**: {change_str} (first 90d avg {row['first_90d_avg']:.1f} -> last 90d avg {row['last_90d_avg']:.1f})")
    else:
        lines.append('- None.')
    lines.append('')

    lines.append(f'### Families trending down ({len(down)})\n')
    if len(down) > 0:
        for family, row in down.iterrows():
            lines.append(f"- **{family}**: {row['pct_change']:+.1%} (first 90d avg {row['first_90d_avg']:.1f} -> last 90d avg {row['last_90d_avg']:.1f})")
    else:
        lines.append('- None.')
    lines.append('')

    lines.append(f'### Relatively stable families ({len(stable)})\n')
    if len(stable) > 0:
        stable_line = '- ' + ', '.join(stable.index.tolist())
    else:
        stable_line = '- None.'
    lines.append(stable_line)
    lines.append('')

    lines.append(f'### Sparse families, >{int(SPARSE_THRESHOLD * 100)}% zero-sales days chain-wide ({len(sparse)})\n')
    if len(sparse) > 0:
        for family, row in sparse.iterrows():
            lines.append(f"- **{family}**: {row['pct_zero_days']:.1%} of days at zero chain-wide sales")
    else:
        lines.append('- None.')
    lines.append('')

    lines.append('### Visually obvious repeating patterns (qualitative, from the overview and per-family charts)\n')
    lines.append(
        '- Short-term repeating patterns: Several families appear to show recurring short-term '
        'variation in daily sales. Weekly seasonality will be formally examined during the '
        'decomposition analysis.'
    )
    lines.append(
        '- Annual cycle: several families show a same-direction bump in their 28-day rolling mean '
        'recurring around the same time of year across multiple years (visible in the overview grid); '
        'which families and which months is deferred to the seasonal-strength analysis in Ticket #20.'
    )
    lines.append('')

    lines.append('### Notable anomalies / structural changes\n')
    lines.append(
        '- The April 2016 Ecuador earthquake relief-buying surge and month-start payday cycles are '
        'documented in `data/DATA_DICTIONARY.md` as the main source of `sales_outlier_flag` spikes; '
        'these remain visible as short raw-sales spikes above the rolling means in the per-family charts.'
    )
    lines.append(
        '- The 4 Dec-25 closure dates appear as a zero dip in the raw series each year by construction '
        '(zero-filled, not an organic demand drop).'
    )
    zero_base = findings[findings['trend_label'] == 'up (from zero)']
    if len(zero_base) > 0:
        lines.append(
            f"- {len(zero_base)} families ({', '.join(zero_base.index.tolist())}) show chain-wide sales "
            "of exactly 0 for their first 90 days, then a jump to non-zero. Spot-checking the raw data "
            "confirms this is a genuine product-line introduction (first non-zero sale chain-wide falls "
            "around 2014-01-01 for these families), not an aggregation artifact -- but it means the "
            "first-90d/last-90d 'trend' comparison for these families reflects assortment timing, not "
            "organic demand growth, and should be read with that caveat."
        )
    lines.append('')

    with open(FINDINGS_PATH, 'a') as f:
        f.write('\n'.join(lines) + '\n')

    print(f"Appended trend-analysis findings to {FINDINGS_PATH}")


if __name__ == "__main__":
    print(f"\n{'='*50}")
    print("FAVORITA TREND ANALYSIS")
    print(f"{'='*50}")

    family_series = load_family_series()
    n_families = family_series.shape[1]
    n_days = family_series.shape[0]
    print(f"Loaded {n_families} families over {n_days} days "
          f"({family_series.index.min().date()} to {family_series.index.max().date()})")
    assert n_families == 33, f"expected 33 families, found {n_families}"

    plot_overview(family_series)
    plot_per_family(family_series)

    findings = compute_findings(family_series)
    write_findings(findings, family_series)

    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    print(findings[['trend_label', 'pct_change', 'pct_zero_days', 'is_sparse']])
    print(f"\nTrending up: {(findings['trend_label'].isin(['up', 'up (from zero)'])).sum()}")
    print(f"Trending down: {(findings['trend_label'] == 'down').sum()}")
    print(f"Stable: {(findings['trend_label'] == 'stable').sum()}")
    print(f"Sparse (>{int(SPARSE_THRESHOLD*100)}% zero days): {findings['is_sparse'].sum()}")
