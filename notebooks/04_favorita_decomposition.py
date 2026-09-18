import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.seasonal import STL

INPUT_CSV = 'data/processed/favorita_family_daily_sales.csv'
FIGURES_DIR = 'figures/decomposition'
FINDINGS_PATH = 'docs/eda_findings_favorita.md'
SUMMARY_CSV_PATH = 'data/processed/favorita_seasonality_summary.csv'

PERIOD = 7                    # weekly seasonality
ZERO_SALES_THRESHOLD = 0.10   # flag families with >10% zero-sales days
MIN_RESIDUAL_VAR = 1e-6       # guard against dividing by a near-zero residual

# Descriptive EDA thresholds for this dataset, chosen after reviewing the
# ratio distribution -- not a statistical significance test.
STRONG_THRESHOLD = 4.5
MEDIUM_THRESHOLD = 2.0


def load_family_series():
    """Load the family-level daily sales CSV (long format: one row per
    date/family) and pivot to one column per family, one row per date."""
    df = pd.read_csv(INPUT_CSV, parse_dates=['date'])
    family_series = df.pivot(index='date', columns='family', values='sales')
    family_series = family_series.sort_index()  # guarantee time ordering before STL
    return family_series


def slugify(family_name):
    """Turn a family name like 'LIQUOR,WINE,BEER' into a safe filename like
    'LIQUOR_WINE_BEER'."""
    return family_name.replace(',', '_').replace('/', '_').replace(' ', '_')


def decompose_family(series):
    """Run STL decomposition with weekly seasonality (period=7) on a single
    family's daily sales series. Returns the STL result, or None if STL
    raises an exception, so the caller can skip that family and continue."""
    try:
        return STL(series, period=PERIOD).fit()
    except Exception as e:
        print(f"  STL failed: {e}")
        return None


def seasonality_strength(result):
    """Ratio of seasonal variance to residual variance -- higher means the
    weekly pattern is large relative to the leftover noise. Guards against a
    near-zero residual variance, which would make the ratio blow up without
    actually meaning strong seasonality."""
    residual_var = np.var(result.resid)
    if residual_var < MIN_RESIDUAL_VAR:
        return np.nan
    return np.var(result.seasonal) / residual_var


def plot_family(family, series, result, out_path):
    """Draw a 4-panel chart (observed, trend, seasonal, residual) for one
    family, sharing the date axis across panels, and save it as a PNG."""
    fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True)

    axes[0].plot(series.index, series.values, color='tab:gray', linewidth=0.7)
    axes[0].set_ylabel('Observed')

    axes[1].plot(series.index, result.trend, color='tab:blue', linewidth=1.2)
    axes[1].set_ylabel('Trend')

    axes[2].plot(series.index, result.seasonal, color='tab:orange', linewidth=0.7)
    axes[2].set_ylabel('Seasonal')

    axes[3].plot(series.index, result.resid, color='tab:red', linewidth=0.5)
    axes[3].set_ylabel('Residual')
    axes[3].set_xlabel('Date')

    fig.suptitle(f'{family} — STL Decomposition (period={PERIOD})')
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def categorize(ratio):
    """Label a seasonality strength ratio as Strong/Medium/Weak using the
    fixed thresholds above. A NaN ratio (near-zero residual variance) is
    labeled Unknown rather than guessed."""
    if pd.isna(ratio):
        return 'Unknown'
    if ratio >= STRONG_THRESHOLD:
        return 'Strong'
    if ratio >= MEDIUM_THRESHOLD:
        return 'Medium'
    return 'Weak'


def compute_results(family_series):
    """Loop through every family: run STL, compute seasonality strength,
    save a 4-panel figure, and record zero-sales rate. Returns a DataFrame
    (one row per successfully decomposed family) and a list of families
    where STL failed."""
    os.makedirs(FIGURES_DIR, exist_ok=True)

    rows = []
    failed = []
    for family in sorted(family_series.columns):
        series = family_series[family]
        pct_zero_days = (series == 0).mean()

        result = decompose_family(series)
        if result is None:
            failed.append(family)
            continue

        strength = seasonality_strength(result)

        out_path = f'{FIGURES_DIR}/family_{slugify(family)}.png'
        plot_family(family, series, result, out_path)

        rows.append({
            'family': family,
            'seasonality_strength': strength,
            'pct_zero_days': pct_zero_days,
            'zero_sales_flagged': pct_zero_days > ZERO_SALES_THRESHOLD,
        })

    return pd.DataFrame(rows).set_index('family'), failed


def write_findings(ranked, failed):
    """Append a short decomposition-findings summary to
    docs/eda_findings_favorita.md: category counts, top/bottom 3 families,
    and the sparse (>10% zero-sales days) list. The full per-family ratios
    already live in SUMMARY_CSV_PATH, so the Markdown stays a human-readable
    summary rather than repeating the table."""
    strong = ranked[ranked['seasonality_strength'] >= STRONG_THRESHOLD]
    medium = ranked[(ranked['seasonality_strength'] >= MEDIUM_THRESHOLD) & (ranked['seasonality_strength'] < STRONG_THRESHOLD)]
    weak = ranked[ranked['seasonality_strength'] < MEDIUM_THRESHOLD]
    sparse = ranked[ranked['zero_sales_flagged']]

    lines = []
    lines.append('## Time-Series Decomposition (`04_favorita_decomposition.py`)\n')
    lines.append(f'**Method:** STL decomposition with weekly period ({PERIOD} days)\n')
    lines.append(f'Full per-family ratios are in `{SUMMARY_CSV_PATH}`.\n')

    lines.append('**Results:**')
    lines.append(f'- Strong weekly seasonality (ratio >= {STRONG_THRESHOLD}): {len(strong)} families')
    lines.append(f'- Medium weekly seasonality ({MEDIUM_THRESHOLD} <= ratio < {STRONG_THRESHOLD}): {len(medium)} families')
    lines.append(f'- Weak weekly seasonality (ratio < {MEDIUM_THRESHOLD}): {len(weak)} families\n')

    lines.append('**Strongest weekly patterns:**')
    for i, (family, row) in enumerate(ranked.head(3).iterrows(), start=1):
        lines.append(f"{i}. {family} ({row['seasonality_strength']:.3f})")
    lines.append('')

    lines.append('**Weakest weekly patterns:**')
    for i, (family, row) in enumerate(ranked.tail(3).sort_values('seasonality_strength').iterrows(), start=1):
        lines.append(f"{i}. {family} ({row['seasonality_strength']:.3f})")
    lines.append('')

    lines.append(f'**Families with many zero-sales days (>{int(ZERO_SALES_THRESHOLD * 100)}% zeros):**')
    for family, row in sparse.sort_values('pct_zero_days', ascending=False).iterrows():
        lines.append(f"- {family} ({row['pct_zero_days']:.1%})")
    lines.append(
        'These families have many zero-sales days, so their seasonality ratios should be '
        'interpreted with caution.\n'
    )

    lines.append(f"**STL failures:** {'None' if not failed else ', '.join(failed)}\n")

    with open(FINDINGS_PATH, 'a') as f:
        f.write('\n'.join(lines) + '\n')

    print(f"Appended decomposition findings to {FINDINGS_PATH}")


def export_summary_csv(ranked):
    """Save a simple numeric summary CSV (family, seasonality_ratio,
    zero_sales_pct) sorted strongest to weakest, so downstream work can use
    the ratios directly instead of parsing the 33 PNGs or the findings doc."""
    summary = ranked.reset_index()[['family', 'seasonality_strength', 'pct_zero_days']]
    summary = summary.rename(columns={
        'seasonality_strength': 'seasonality_ratio',
        'pct_zero_days': 'zero_sales_pct',
    })
    summary['zero_sales_pct'] = summary['zero_sales_pct'] * 100
    summary.to_csv(SUMMARY_CSV_PATH, index=False)
    print(f"Saved seasonality summary to {SUMMARY_CSV_PATH}")


if __name__ == "__main__":
    print(f"\n{'=' * 50}")
    print("FAVORITA DECOMPOSITION")
    print(f"{'=' * 50}")

    family_series = load_family_series()
    n_families = family_series.shape[1]
    n_days = family_series.shape[0]
    print(f"Loaded {n_families} families over {n_days} days "
          f"({family_series.index.min().date()} to {family_series.index.max().date()})")
    assert n_families == 33, f"expected 33 families, found {n_families}"
    assert n_days == 1688, f"expected 1688 days, found {n_days}"

    results, failed = compute_results(family_series)
    ranked = results.sort_values('seasonality_strength', ascending=False)
    write_findings(ranked, failed)
    export_summary_csv(ranked)

    print(f"\n{'=' * 50}")
    print("SEASONALITY STRENGTH (sorted, strongest first)")
    print(f"{'=' * 50}")
    print(ranked)

    print(f"\nFamilies processed: {len(results)}/{n_families}")
    print(f"STL failures: {len(failed)}")
    print(f"Flagged for >{int(ZERO_SALES_THRESHOLD * 100)}% zero-sales days: {results['zero_sales_flagged'].sum()}")
