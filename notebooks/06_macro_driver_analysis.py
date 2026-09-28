import math
import os
import warnings

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.stattools import adfuller

INPUT_CSV = 'data/processed/macro_drivers_merged_monthly.csv'
FIGURES_DIR = 'figures/macro'
LAG_CORR_CSV = 'data/processed/macro_lag_correlations.csv'
COMPARISON_CSV = 'data/processed/macro_correlation_comparison.csv'
ADF_CSV = 'data/processed/macro_adf_tests.csv'
REGRESSION_CSV = 'data/processed/macro_lag_regressions.csv'

TOTAL = 'TOTAL_CORE'
DRIVERS = {'dcoilwtico': 'Oil price (WTI)', 'dff': 'Fed funds rate (DFF)'}
MAX_LAG = 6               # months; lag k pairs sales in month t with the driver in month t-k
PERIOD = 12               # monthly data, annual seasonality
MIN_OBS = 24              # skip a test/correlation with fewer overlapping months than this
ADF_ALPHA = 0.05
N_LARGEST = 5             # largest families get lag regressions alongside TOTAL

# Recording gaps: in 10 months (Feb, Apr-Jun, Aug 2014; Jan-May 2015) PRODUCE
# and 10 late-launched families record almost nothing -- e.g. PRODUCE ~7k vs.
# ~3.4M in a normal month -- which also drags the all-family total down ~35%.
# These are not exact zeros, so the merge step's flags don't catch them. A
# month is a gap month if at least GAP_MIN_FAMILIES families fall below
# GAP_RATIO of their own median over the last 24 months; a family is
# gap-affected if it is that low in any gap month. Gap-affected months are
# masked, so those families are analyzed only after their last gap.
GAP_RATIO = 0.10
GAP_MIN_FAMILIES = 5
EXPECTED_GAP_MONTHS = ['2014-02', '2014-04', '2014-05', '2014-06', '2014-08',
                       '2015-01', '2015-02', '2015-03', '2015-04', '2015-05']

# Transforms, from "most likely to show a coincidental shared trend" to "least":
#   level        - log sales vs log oil / the rate itself
#   differenced  - month-over-month change: seasonally adjusted log sales, log oil, rate in pp
#   yoy          - 12-month change (removes seasonality, keeps slow trends)
#   stl_residual - what's left after STL removes trend and seasonality
TRANSFORMS = ['level', 'differenced', 'yoy', 'stl_residual']
# Lag correlations and regressions use only the transforms that are stationary
# for sales and oil (yoy isn't for oil -- see macro_adf_tests.csv).
LAG_TRANSFORMS = ['differenced', 'stl_residual']

# Chart colors (validated categorical slots 1-3 + neutral ink/chrome).
SALES_COLOR = '#2a78d6'
OIL_COLOR = '#eb6834'
RATE_COLOR = '#1baf7a'
DRIVER_COLORS = {'dcoilwtico': OIL_COLOR, 'dff': RATE_COLOR}
INK = '#0b0b0b'
INK_SECONDARY = '#52514e'
INK_MUTED = '#898781'
GRID = '#e1e0d9'
BASELINE = '#c3c2b7'
SURFACE = '#fcfcfb'

plt.rcParams.update({
    'figure.facecolor': SURFACE,
    'axes.facecolor': SURFACE,
    'axes.edgecolor': BASELINE,
    'axes.labelcolor': INK_SECONDARY,
    'axes.titlecolor': INK,
    'axes.grid': True,
    'grid.color': GRID,
    'grid.linewidth': 0.6,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'xtick.color': INK_MUTED,
    'ytick.color': INK_MUTED,
    'text.color': INK,
    'legend.frameon': False,
})


def load_monthly():
    """Load the monthly merged data, drop the partial August 2017 month, and
    return (sales, drivers, flags, core_families).
    sales has one column per family plus TOTAL (the core-family total), with
    pre-launch and recording-gap months masked; drivers has one column per
    macro driver."""
    df = pd.read_csv(INPUT_CSV, parse_dates=['month'])
    df = df[df['is_partial_month'] == 0]

    sales = df.pivot(index='month', columns='family', values='sales')

    # Pre-launch months are zeros because the family wasn't stocked yet; mask
    # them so they don't look like real demand.
    pre_launch = df.pivot(index='month', columns='family', values='pre_launch_flag')
    sales = sales.mask(pre_launch == 1)

    near_empty = sales.lt(GAP_RATIO * sales.iloc[-24:].median())
    gap_months = near_empty.index[near_empty.sum(axis=1) >= GAP_MIN_FAMILIES]
    assert gap_months.strftime('%Y-%m').tolist() == EXPECTED_GAP_MONTHS, \
        "recording-gap months changed; re-investigate"
    gap_affected = near_empty.loc[gap_months].any()
    # A gap-affected family's near-empty months are all masked (for PRODUCE
    # that includes most of 2013), not just the chain-wide gap months.
    sales = sales.mask(near_empty & gap_affected)

    low_confidence = df.groupby('family')['low_confidence_flag'].first()
    core_families = sorted(f for f in sales.columns if not gap_affected[f] and not low_confidence[f])
    # TOTAL sums only families with no recording gaps, so it's an unbroken
    # 55-month series; the all-family total dips ~35% in every gap month.
    sales[TOTAL] = sales[core_families].sum(axis=1)
    low_confidence[TOTAL] = 0
    gap_affected[TOTAL] = False

    drivers = df.groupby('month')[list(DRIVERS)].first()

    assert len(sales) == 55, "expected 55 complete months (2013-01 to 2017-07)"
    assert drivers.notna().all().all(), "driver series has missing months"
    assert sorted(gap_affected[gap_affected].index) == sorted(
        ['PRODUCE'] + [f for f in low_confidence.index if low_confidence[f] and f != 'BOOKS']), \
        "gap-affected families changed; re-investigate"
    assert len(core_families) == 21, "expected 21 core families"

    flags = pd.DataFrame({
        'low_confidence_flag': low_confidence.astype(int),
        'gap_affected_flag': gap_affected.astype(int),
    })
    return sales, drivers, flags, core_families


def flag_values(flags, name):
    """Low-confidence and gap-affected flags for a series (0 for the drivers)."""
    if name in flags.index:
        return flags.loc[name].to_dict()
    return {col: 0 for col in flags.columns}


def analysis_window(series):
    """Longest trailing run of positive, unmasked months. Log transforms and
    STL need an unbroken positive series, so a family with pre-launch or
    recording-gap months is analyzed only after its last one. For the core
    families this is the full 55 months."""
    series = series.loc[series.first_valid_index():]
    usable = series.notna() & (series > 0)
    if usable.all():
        return series
    last_gap = usable[~usable].index.max()
    return series[series.index > last_gap]


def transform(series, kind, log):
    """Apply one of TRANSFORMS to a monthly series. Sales and oil are logged
    first so changes are percentages; the interest rate is already a percent,
    so its changes are in percentage points."""
    x = np.log(series) if log else series.astype(float)
    if kind == 'level':
        return x
    if kind == 'yoy':
        return x.diff(PERIOD)

    if len(x) < 2 * PERIOD:
        return pd.Series(np.nan, index=x.index)
    stl = STL(x, period=PERIOD, robust=True).fit()
    if kind == 'stl_residual':
        return pd.Series(stl.resid, index=x.index)
    if kind == 'differenced':
        # Sales are seasonally adjusted before differencing, so December peaks
        # can't line up with oil moves by coincidence. Oil and the fed funds
        # rate have no meaningful seasonality, so they're differenced as-is.
        adjusted = x - stl.seasonal if log and series.name not in DRIVERS else x
        return adjusted.diff()
    raise ValueError(kind)


def adf_pvalue(x):
    x = x.dropna()
    if len(x) < MIN_OBS:
        return np.nan, np.nan
    stat, pvalue, *_ = adfuller(x, autolag='AIC')
    return stat, pvalue


def lagged_corr(y, x, lag):
    """Pearson correlation between y in month t and x in month t-lag."""
    pair = pd.concat([y, x.shift(lag)], axis=1).dropna()
    if len(pair) < MIN_OBS:
        return np.nan, np.nan, len(pair)
    r, p = stats.pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
    return r, p, len(pair)


def benjamini_hochberg(pvalues):
    """False-discovery-rate adjusted p-values (q-values). Many correlations are
    tested at once, so some raw p < 0.05 results are expected by chance."""
    p = pd.Series(pvalues)
    valid = p.dropna().sort_values()
    n = len(valid)
    q = valid * n / np.arange(1, n + 1)
    q = q[::-1].cummin()[::-1].clip(upper=1.0)
    return q.reindex(p.index)


def build_transformed(sales, drivers):
    """Return {transform: DataFrame} with every sales series and driver
    transformed over its own analysis window."""
    out = {}
    for kind in TRANSFORMS:
        cols = {}
        for name in sales.columns:
            window = analysis_window(sales[name])
            cols[name] = transform(window.rename(name), kind, log=True)
        cols['dcoilwtico'] = transform(drivers['dcoilwtico'], kind, log=True)
        cols['dff'] = transform(drivers['dff'], kind, log=False)
        out[kind] = pd.DataFrame(cols)
    return out


def run_adf(transformed, flags):
    rows = []
    for kind, frame in transformed.items():
        for name in frame.columns:
            stat, pvalue = adf_pvalue(frame[name])
            rows.append({
                'series': name,
                'transform': kind,
                'adf_stat': stat,
                'adf_pvalue': pvalue,
                'stationary': (pvalue < ADF_ALPHA) if pd.notna(pvalue) else np.nan,
                'n_obs': int(frame[name].notna().sum()),
                **flag_values(flags, name),
            })
    return pd.DataFrame(rows)


def correlation_comparison(transformed, families, flags):
    """Same-month (lag 0) correlation of each family with each driver under
    every transform, one row per (family, driver). A correlation that is
    strong in levels but vanishes once trends are removed was a shared trend,
    not a real relationship."""
    rows = []
    for family in families:
        for driver in DRIVERS:
            row = {'family': family, 'driver': driver, **flag_values(flags, family)}
            for kind in TRANSFORMS:
                frame = transformed[kind]
                r, p, n = lagged_corr(frame[family], frame[driver], 0)
                row[f'{kind}_corr'] = r
                row[f'{kind}_pvalue'] = p
                row[f'{kind}_n'] = n
            rows.append(row)
    return pd.DataFrame(rows)


def lag_correlations(transformed, families, flags):
    """Cross-correlations for lags 0..MAX_LAG on the stationary transforms.
    One row per (family, driver, transform, lag)."""
    rows = []
    for kind in LAG_TRANSFORMS:
        frame = transformed[kind]
        for family in families:
            for driver in DRIVERS:
                for lag in range(MAX_LAG + 1):
                    r, p, n = lagged_corr(frame[family], frame[driver], lag)
                    rows.append({
                        'family': family, 'driver': driver, 'transform': kind,
                        'lag_months': lag, 'correlation': r, 'pvalue': p, 'n_obs': n,
                        **flag_values(flags, family),
                    })
    result = pd.DataFrame(rows)
    result['qvalue'] = np.nan
    for kind in LAG_TRANSFORMS:
        in_kind = result['transform'] == kind
        result.loc[in_kind, 'qvalue'] = benjamini_hochberg(result.loc[in_kind, 'pvalue'])
    return result


def lag_regressions(transformed, series_names):
    """Simple lag regressions: sales_t = a + b * driver_(t-lag), one driver
    and one lag at a time, on the stationary transforms. On the differenced
    series b is an elasticity for oil (% sales change per 1% oil change) and a
    semi-elasticity for the rate (% sales change per 1 pp rate change).
    Standard errors are Newey-West (HAC) because monthly changes can be
    autocorrelated."""
    rows = []
    for kind in LAG_TRANSFORMS:
        frame = transformed[kind]
        for name in series_names:
            for driver in DRIVERS:
                for lag in range(MAX_LAG + 1):
                    pair = pd.concat([frame[name], frame[driver].shift(lag)], axis=1).dropna()
                    if len(pair) < MIN_OBS:
                        continue
                    X = sm.add_constant(pair.iloc[:, 1])
                    fit = sm.OLS(pair.iloc[:, 0], X).fit(cov_type='HAC', cov_kwds={'maxlags': 3})
                    rows.append({
                        'series': name, 'driver': driver, 'transform': kind, 'lag_months': lag,
                        'coef': fit.params.iloc[1], 'std_err': fit.bse.iloc[1],
                        'pvalue': fit.pvalues.iloc[1], 'r_squared': fit.rsquared,
                        'n_obs': int(fit.nobs),
                    })
    return pd.DataFrame(rows)


def format_date_axis(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))


def plot_total_overview(sales, drivers):
    """Total monthly sales, oil, and the fed funds rate as three stacked
    panels on a shared date axis (separate y-scales, never a dual axis)."""
    fig, axes = plt.subplots(3, 1, figsize=(10, 7.5), sharex=True)
    panels = [
        (sales[TOTAL] / 1e6, SALES_COLOR, 'Sales (millions)',
         'Total sales, 21 core families (excludes families with recording gaps)'),
        (drivers['dcoilwtico'], OIL_COLOR, 'USD per barrel', 'Oil price (WTI, monthly mean of trading days)'),
        (drivers['dff'], RATE_COLOR, 'Percent', 'Effective fed funds rate (DFF, monthly mean)'),
    ]
    for ax, (series, color, ylabel, title) in zip(axes, panels):
        ax.plot(series.index, series.values, color=color, linewidth=2)
        ax.set_title(title, loc='left', fontsize=10)
        ax.set_ylabel(ylabel, fontsize=9)
        format_date_axis(ax)
    fig.suptitle('Total sales vs. macro drivers, monthly (2013-01 to 2017-07)', fontsize=12, x=0.01, ha='left')
    fig.tight_layout()
    save(fig, 'overview_total.png')


def plot_family_overview(sales, drivers, flags):
    """One small panel per family: sales, oil and the rate each standardized
    (z-score) so they share one axis. This is the 'levels' view -- series that
    trend together will look related whether or not they are."""
    families = sorted(c for c in sales.columns if c != TOTAL)
    n_cols = 6
    n_rows = math.ceil(len(families) / n_cols)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(n_cols * 3.2, n_rows * 2.2), sharex=True, sharey=True)
    axes = axes.flatten()

    def z(s):
        return (s - s.mean()) / s.std()

    oil_z, rate_z = z(drivers['dcoilwtico']), z(drivers['dff'])
    for ax, family in zip(axes, families):
        ax.plot(oil_z.index, oil_z.values, color=OIL_COLOR, linewidth=1.2)
        ax.plot(rate_z.index, rate_z.values, color=RATE_COLOR, linewidth=1.2)
        # Pre-launch and recording-gap months are masked in load_monthly(), so
        # they show as breaks in the line rather than as dips.
        ax.plot(sales.index, z(sales[family]).values, color=SALES_COLOR, linewidth=1.6)
        notes = [label for label, col in (('low confidence', 'low_confidence_flag'),
                                          ('recording gaps', 'gap_affected_flag'))
                 if flags.loc[family, col]]
        title = family + (f" ({', '.join(notes)})" if notes else '')
        ax.set_title(title, fontsize=7, loc='left', color=INK_SECONDARY if notes else INK)
        ax.tick_params(labelsize=6)
        format_date_axis(ax)
    for ax in axes[len(families):]:
        ax.set_visible(False)

    handles = [plt.Line2D([], [], color=c, linewidth=2) for c in (SALES_COLOR, OIL_COLOR, RATE_COLOR)]
    fig.legend(handles, ['Family sales', 'Oil price', 'Fed funds rate'], loc='upper right', ncol=3, fontsize=9)
    fig.suptitle('Family sales vs. oil and the fed funds rate, each standardized (z-score), monthly',
                 fontsize=12, x=0.01, ha='left')
    fig.supylabel('Standard deviations from own mean', fontsize=9, color=INK_SECONDARY)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    save(fig, 'overview_families.png')


def plot_ccf(lag_corr, series_names, kind):
    """Cross-correlation bars by lag for TOTAL and the largest families, one
    row per series and one column per driver. The dashed band is the
    approximate 95% range for a correlation of zero (+/- 1.96 / sqrt(n))."""
    data = lag_corr[(lag_corr['transform'] == kind) & (lag_corr['family'].isin(series_names))]
    fig, axes = plt.subplots(len(series_names), len(DRIVERS), figsize=(9, 1.9 * len(series_names)),
                             sharex=True, sharey=True, squeeze=False)
    for i, name in enumerate(series_names):
        for j, driver in enumerate(DRIVERS):
            ax = axes[i, j]
            d = data[(data['family'] == name) & (data['driver'] == driver)].sort_values('lag_months')
            ax.bar(d['lag_months'], d['correlation'], width=0.6, color=DRIVER_COLORS[driver])
            band = 1.96 / math.sqrt(d['n_obs'].median())
            for y in (band, -band):
                ax.axhline(y, color=INK_MUTED, linewidth=0.8, linestyle='--')
            ax.axhline(0, color=BASELINE, linewidth=1)
            ax.set_ylim(-1, 1)
            ax.set_xticks(range(MAX_LAG + 1))
            ax.tick_params(labelsize=7)
            ax.grid(axis='x', visible=False)
            if i == 0:
                ax.set_title(DRIVERS[driver], fontsize=10)
            if j == 0:
                ax.set_ylabel(name, fontsize=8)
    fig.supxlabel('Lag (months the driver leads sales)', fontsize=9, color=INK_SECONDARY)
    label = 'month-over-month changes (sales seasonally adjusted)' if kind == 'differenced' else 'STL residuals'
    fig.suptitle(f'Cross-correlation of sales with macro drivers, {label}', fontsize=11, x=0.01, ha='left')
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    save(fig, f'ccf_{kind}.png')


def plot_transform_comparison(comparison, series_names):
    """Same-month correlation under each transform for TOTAL and the largest
    families: shows how much of the levels correlation survives once shared
    trends and seasonality are removed."""
    fig, axes = plt.subplots(1, len(DRIVERS), figsize=(10, 0.45 * len(series_names) * len(TRANSFORMS) / 2 + 1.5),
                             sharey=True)
    labels = {'level': 'Levels', 'differenced': 'Differenced', 'yoy': 'Year-over-year', 'stl_residual': 'STL residual'}
    markers = {'level': 'o', 'differenced': 's', 'yoy': '^', 'stl_residual': 'D'}
    y = np.arange(len(series_names))
    offsets = np.linspace(-0.27, 0.27, len(TRANSFORMS))
    for ax, driver in zip(axes, DRIVERS):
        d = comparison[comparison['driver'] == driver].set_index('family').loc[series_names]
        for offset, kind in zip(offsets, TRANSFORMS):
            ax.scatter(d[f'{kind}_corr'], y + offset, s=36, marker=markers[kind],
                       color=DRIVER_COLORS[driver] if kind == 'level' else INK_SECONDARY,
                       label=labels[kind], zorder=3)
        ax.axvline(0, color=BASELINE, linewidth=1)
        ax.set_xlim(-1, 1)
        ax.set_title(DRIVERS[driver], fontsize=10)
        ax.set_xlabel('Same-month correlation', fontsize=9)
        ax.grid(axis='y', visible=False)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(series_names, fontsize=8)
    axes[0].invert_yaxis()
    # Levels are drawn in each driver's color, so the legend uses neutral ink
    # markers that describe the shape only.
    handles = [plt.Line2D([], [], linestyle='', marker=markers[k], markersize=7, color=INK_SECONDARY)
               for k in TRANSFORMS]
    fig.legend(handles, [labels[k] for k in TRANSFORMS], loc='lower center', ncol=len(TRANSFORMS), fontsize=9)
    fig.suptitle('Correlation with macro drivers: levels vs. trend-removed transforms', fontsize=11, x=0.01, ha='left')
    fig.tight_layout(rect=[0, 0.05, 1, 0.95])
    save(fig, 'correlation_by_transform.png')


def save(fig, filename):
    os.makedirs(FIGURES_DIR, exist_ok=True)
    out_path = f'{FIGURES_DIR}/{filename}'
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    print(f"\n{'=' * 50}")
    print("MACRO DRIVER ANALYSIS")
    print(f"{'=' * 50}")

    # statsmodels warns about short samples and HAC on small n; the MIN_OBS
    # guard already handles those cases.
    warnings.filterwarnings('ignore', category=UserWarning)
    warnings.filterwarnings('ignore', category=RuntimeWarning)

    sales, drivers, flags, core_families = load_monthly()
    families = [TOTAL] + sorted(c for c in sales.columns if c != TOTAL)
    all_sales = pd.read_csv(INPUT_CSV).query('is_partial_month == 0')['sales'].sum()
    core_share = sales[TOTAL].sum() / all_sales
    # Largest families are picked from the core set, so none has recording gaps
    # (PRODUCE, the 3rd-largest overall, is gap-affected).
    share = sales[core_families].sum().sort_values(ascending=False) / all_sales
    largest = share.head(N_LARGEST).index.tolist()
    focus = [TOTAL] + largest
    print(f"Loaded {len(sales)} complete months, {len(families) - 1} families + {TOTAL}")
    print(f"{TOTAL}: {len(core_families)} families, {core_share:.1%} of all sales")
    print(f"Gap-affected families (analyzed after their last gap): "
          f"{', '.join(flags.index[flags['gap_affected_flag'] == 1])}")
    print(f"Largest core families ({share.head(N_LARGEST).sum():.0%} of sales): {', '.join(largest)}")

    transformed = build_transformed(sales, drivers)
    adf = run_adf(transformed, flags)
    comparison = correlation_comparison(transformed, families, flags)
    lag_corr = lag_correlations(transformed, families, flags)
    regressions = lag_regressions(transformed, focus)

    assert len(comparison) == len(families) * len(DRIVERS), "unexpected comparison row count"
    assert len(lag_corr) == len(families) * len(DRIVERS) * len(LAG_TRANSFORMS) * (MAX_LAG + 1), \
        "unexpected lag correlation row count"
    assert lag_corr.loc[lag_corr['family'].isin(focus), 'correlation'].notna().all(), \
        "missing lag correlations for TOTAL or the largest families"

    os.makedirs(os.path.dirname(LAG_CORR_CSV), exist_ok=True)
    lag_corr.to_csv(LAG_CORR_CSV, index=False)
    comparison.to_csv(COMPARISON_CSV, index=False)
    adf.to_csv(ADF_CSV, index=False)
    regressions.to_csv(REGRESSION_CSV, index=False)
    for path in (LAG_CORR_CSV, COMPARISON_CSV, ADF_CSV, REGRESSION_CSV):
        print(f"Saved {path}")

    plot_total_overview(sales, drivers)
    plot_family_overview(sales, drivers, flags)
    for kind in LAG_TRANSFORMS:
        plot_ccf(lag_corr, focus, kind)
    plot_transform_comparison(comparison, focus)

    print(f"\n{'=' * 50}")
    print("SUMMARY")
    print(f"{'=' * 50}")
    print("\nADF p-values (stationary if < 0.05):")
    print(adf[adf['series'].isin(focus + list(DRIVERS))]
          .pivot(index='series', columns='transform', values='adf_pvalue')[TRANSFORMS].round(3))
    print("\nSame-month correlation by transform:")
    print(comparison[comparison['family'].isin(focus)]
          .set_index(['family', 'driver'])[[f'{k}_corr' for k in TRANSFORMS]].round(2).to_string())
    reliable = (lag_corr['low_confidence_flag'] == 0) & (lag_corr['gap_affected_flag'] == 0)
    significant = lag_corr[(lag_corr['qvalue'] < 0.05) & reliable]
    print(f"\nLag correlations significant after FDR correction (q < 0.05, core families + {TOTAL} only): "
          f"{len(significant)} of {int(reliable.sum())}")
    if len(significant):
        print(significant.sort_values('qvalue')[['family', 'driver', 'transform', 'lag_months', 'correlation', 'qvalue']]
              .round(3).to_string(index=False))
