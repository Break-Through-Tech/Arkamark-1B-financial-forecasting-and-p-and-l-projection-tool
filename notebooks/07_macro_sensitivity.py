import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

LAG_CORR_CSV = 'data/processed/macro_lag_correlations.csv'
MONTHLY_CSV = 'data/processed/macro_drivers_merged_monthly.csv'
CLASSIFICATION_CSV = 'data/processed/macro_sensitivity_classification.csv'
FIGURES_DIR = 'figures/macro'
HEATMAP_PATH = f'{FIGURES_DIR}/sensitivity_heatmap.png'
FINDINGS_PATH = 'docs/eda_findings_macro.md'
DOC_TITLE = '# Macro Driver Findings'
SECTION_HEADING = '## Macro Driver Sensitivity (`07_macro_sensitivity.py`)'

TOTAL = 'TOTAL_CORE'
DRIVERS = {'dcoilwtico': 'Oil price (WTI)', 'dff': 'Fed funds rate (DFF)'}
FEATURE_NAMES = {'dcoilwtico': 'oil_dlog_lag{lag}', 'dff': 'dff_diff_lag{lag}'}
MAX_LAG = 6

# Classification thresholds, per (family, driver), over lags 0..MAX_LAG.
# STL residuals are the primary test (stationary for every series, including
# DFF); the differenced series is the confirmation check.
#   sensitive        - some lag has STL q < Q_THRESHOLD AND the differenced
#                      correlation at the same lag has the same sign with
#                      p < CONFIRM_P
#   weakly sensitive - some lag has STL q < Q_THRESHOLD and the differenced
#                      correlation at that lag has the same sign, but p >= CONFIRM_P
#   independent      - neither (including lags where the two transforms disagree
#                      in sign, which are listed as conflicting in the caveats)
# q is the Benjamini-Hochberg FDR-adjusted p-value from 06, across all tests of
# that transform, so looking at 7 lags x 34 series is already accounted for.
Q_THRESHOLD = 0.05
CONFIRM_P = 0.05

# Strength of the relationship, by |STL-residual correlation| at the best lag.
STRONG_R = 0.50
MODERATE_R = 0.30

LABEL_ORDER = ['sensitive', 'weakly sensitive', 'independent', 'insufficient data']

# Diverging blue <-> red with a neutral gray midpoint (validated palette).
BLUE_END = '#104281'
BLUE = '#2a78d6'
MIDPOINT = '#f0efec'
RED = '#e34948'
RED_END = '#a52a2a'
INK = '#0b0b0b'
INK_SECONDARY = '#52514e'
INK_MUTED = '#898781'
SURFACE = '#fcfcfb'


def load_lag_correlations():
    """Wide table: one row per (family, driver, lag) with the correlation,
    p-value and q-value from both stationary transforms."""
    df = pd.read_csv(LAG_CORR_CSV)
    # pivot (not pivot_table) keeps all-NaN rows, e.g. short-history families
    # whose longer lags have too few months to correlate.
    wide = df.pivot(index=['family', 'driver', 'lag_months'], columns='transform',
                    values=['correlation', 'pvalue', 'qvalue'])
    wide.columns = [f'{stat}_{kind}' for stat, kind in wide.columns]
    flags = df.groupby('family')[['low_confidence_flag', 'gap_affected_flag']].first()
    return wide.reset_index(), flags


def classify_lags(wide):
    """Tag each (family, driver, lag) as confirmed, same-sign only,
    conflicting, or not significant on STL residuals."""
    significant = wide['qvalue_stl_residual'] < Q_THRESHOLD
    same_sign = np.sign(wide['correlation_stl_residual']) == np.sign(wide['correlation_differenced'])
    confirmed = significant & same_sign & (wide['pvalue_differenced'] < CONFIRM_P)

    wide = wide.copy()
    wide['lag_status'] = 'not significant'
    wide.loc[significant & ~same_sign, 'lag_status'] = 'conflicting'
    wide.loc[significant & same_sign, 'lag_status'] = 'same sign'
    wide.loc[confirmed, 'lag_status'] = 'confirmed'
    return wide


def format_lags(lags):
    """[0, 1] -> '0-1', [1, 3] -> '1, 3', [6] -> '6'."""
    runs, start = [], lags[0]
    for prev, cur in zip(lags, lags[1:] + [None]):
        if cur != prev + 1:
            runs.append(str(start) if start == prev else f'{start}-{prev}')
            start = cur
    return ', '.join(runs)


def parse_lags(window):
    """Inverse of format_lags: '0-1, 3' -> [0, 1, 3]."""
    lags = []
    for part in window.split(', '):
        lo, _, hi = part.partition('-')
        lags.extend(range(int(lo), int(hi or lo) + 1))
    return lags


def lag_phrase(window):
    return f"lag {window}" if window.isdigit() else f"lags {window}"


def strength(r):
    r = abs(r)
    if r >= STRONG_R:
        return 'strong'
    if r >= MODERATE_R:
        return 'moderate'
    return 'weak'


def classify(wide, flags):
    """One row per (family, driver): label, best lag, lag window, direction,
    strength. Families flagged low-confidence or gap-affected in 06 get
    'insufficient data' and aren't classified."""
    rows = []
    for (family, driver), g in wide.groupby(['family', 'driver']):
        unreliable = bool(flags.loc[family, 'low_confidence_flag'] or flags.loc[family, 'gap_affected_flag'])
        row = {'family': family, 'driver': driver, 'label': None, 'best_lag_months': np.nan,
               'lag_window': '', 'direction': '', 'strength': '',
               'stl_residual_corr': np.nan, 'differenced_corr': np.nan, 'stl_residual_qvalue': np.nan,
               'conflicting_lags': ', '.join(str(l) for l in g.loc[g['lag_status'] == 'conflicting', 'lag_months'])}
        if unreliable:
            row['label'] = 'insufficient data'
            row['conflicting_lags'] = ''
            rows.append(row)
            continue

        confirmed = g[g['lag_status'] == 'confirmed']
        same_sign = g[g['lag_status'].isin(['confirmed', 'same sign'])]
        if len(confirmed):
            row['label'] = 'sensitive'
            best_from = confirmed
        elif len(same_sign):
            row['label'] = 'weakly sensitive'
            best_from = same_sign
        else:
            row['label'] = 'independent'
            rows.append(row)
            continue

        best = best_from.loc[best_from['correlation_stl_residual'].abs().idxmax()]
        # The window is every lag that is significant on STL residuals with the
        # same sign in both transforms (and the same sign as the best lag). It
        # lists the lags themselves, so a conflicting lag in between (e.g.
        # BEVERAGES lag 2) is never included.
        window = same_sign[np.sign(same_sign['correlation_stl_residual']) == np.sign(best['correlation_stl_residual'])]
        lags = sorted(window['lag_months'].astype(int))
        row.update({
            'best_lag_months': int(best['lag_months']),
            'lag_window': format_lags(lags),
            'direction': 'positive' if best['correlation_stl_residual'] > 0 else 'negative',
            'strength': strength(best['correlation_stl_residual']),
            'stl_residual_corr': best['correlation_stl_residual'],
            'differenced_corr': best['correlation_differenced'],
            'stl_residual_qvalue': best['qvalue_stl_residual'],
        })
        rows.append(row)
    return pd.DataFrame(rows)


def family_labels(classification):
    """A family's overall label is its strongest label across drivers."""
    rank = {label: i for i, label in enumerate(LABEL_ORDER)}
    best = classification.assign(rank=classification['label'].map(rank)).groupby('family')['rank'].min()
    return best.map(dict(enumerate(LABEL_ORDER)))


def plot_heatmap(wide, overall):
    """Family x lag heatmap of STL-residual correlations, one panel per driver.
    Markers show how each cell fared in the classification: filled = confirmed
    by the differenced series, open = significant with the same sign only,
    x = the two transforms disagree in sign."""
    reliable = overall[overall != 'insufficient data']
    order = [TOTAL] + sorted((f for f in reliable.index if f != TOTAL),
                             key=lambda f: (LABEL_ORDER.index(reliable[f]), f))
    cmap = LinearSegmentedColormap.from_list('diverging', [BLUE_END, BLUE, MIDPOINT, RED, RED_END])

    fig, axes = plt.subplots(1, len(DRIVERS), figsize=(11, 0.34 * len(order) + 1.8), sharey=True)
    fig.patch.set_facecolor(SURFACE)
    for ax, driver in zip(axes, DRIVERS):
        d = wide[wide['driver'] == driver]
        grid = d.pivot(index='family', columns='lag_months', values='correlation_stl_residual').loc[order]
        status = d.pivot(index='family', columns='lag_months', values='lag_status').loc[order]
        image = ax.imshow(grid.values, cmap=cmap, vmin=-0.7, vmax=0.7, aspect='auto')

        for i, family in enumerate(order):
            for j, lag in enumerate(grid.columns):
                s = status.loc[family, lag]
                if s == 'confirmed':
                    ax.plot(j, i, marker='o', markersize=7, color=INK)
                elif s == 'same sign':
                    ax.plot(j, i, marker='o', markersize=7, markerfacecolor='none', markeredgecolor=INK, markeredgewidth=1.3)
                elif s == 'conflicting':
                    ax.plot(j, i, marker='x', markersize=7, color=INK, markeredgewidth=1.3)

        # Hairlines between label groups.
        labels = [reliable[f] for f in order]
        for i in range(1, len(order)):
            if labels[i] != labels[i - 1] or i == 1:
                ax.axhline(i - 0.5, color=SURFACE, linewidth=3)

        ax.set_xticks(range(len(grid.columns)))
        ax.set_xticklabels(grid.columns, fontsize=8, color=INK_MUTED)
        ax.set_xlabel('Lag (months the driver leads sales)', fontsize=9, color=INK_SECONDARY)
        ax.set_title(DRIVERS[driver], fontsize=10, color=INK)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)

    axes[0].set_yticks(range(len(order)))
    axes[0].set_yticklabels([f'{f}  ({reliable[f]})' for f in order], fontsize=8, color=INK)

    colorbar = fig.colorbar(image, ax=axes, fraction=0.025, pad=0.02)
    colorbar.set_label('Correlation (STL residuals)', fontsize=9, color=INK_SECONDARY)
    colorbar.ax.tick_params(labelsize=8, colors=INK_MUTED)
    colorbar.outline.set_visible(False)

    handles = [
        plt.Line2D([], [], linestyle='', marker='o', markersize=7, color=INK),
        plt.Line2D([], [], linestyle='', marker='o', markersize=7, markerfacecolor='none', markeredgecolor=INK),
        plt.Line2D([], [], linestyle='', marker='x', markersize=7, color=INK),
    ]
    fig.legend(handles, [
        'Significant (q < 0.05) and confirmed in differenced series (p < 0.05)',
        'Significant, same sign in differenced series but not confirmed',
        'Significant, but differenced series has the opposite sign',
    ], loc='lower left', fontsize=8, frameon=False, ncol=1, bbox_to_anchor=(0.01, 0.0))
    fig.suptitle('Macro driver sensitivity by family and lag (families with reliable history only)',
                 fontsize=11, x=0.01, ha='left', color=INK)
    fig.subplots_adjust(left=0.27, right=0.86, top=0.92, bottom=0.14)

    os.makedirs(FIGURES_DIR, exist_ok=True)
    fig.savefig(HEATMAP_PATH, dpi=150)
    plt.close(fig)
    print(f"Saved {HEATMAP_PATH}")


def feature_recommendations(classification):
    """Recommended and candidate lagged features, from the classification.
    Features use the month-over-month (differenced) form because STL residuals
    are computed with a centered smoother that uses later months, which would
    leak future data into a forecasting model."""
    recommended, candidates = [], []
    for _, row in classification[classification['label'].isin(['sensitive', 'weakly sensitive'])].iterrows():
        features = [FEATURE_NAMES[row['driver']].format(lag=lag) for lag in parse_lags(row['lag_window'])]
        entry = (row['family'], row['driver'], features, row)
        (recommended if row['label'] == 'sensitive' else candidates).append(entry)
    return recommended, candidates


def md_table(df):
    header = '| ' + ' | '.join(df.columns) + ' |'
    divider = '|' + '|'.join('---' for _ in df.columns) + '|'
    body = ['| ' + ' | '.join(str(v) for v in row) + ' |' for row in df.itertuples(index=False)]
    return '\n'.join([header, divider] + body)


def write_findings(classification, overall, recommended, candidates):
    """Write this script's section of docs/eda_findings_macro.md (appended the
    first time, replaced in place on later runs)."""
    n_reliable = int((overall != 'insufficient data').sum())
    counts = overall.value_counts()

    lines = [f'{SECTION_HEADING}\n']
    lines.append(
        'Classifies each product family by how its sales relate to the two macro drivers -- the WTI oil '
        'price and the US effective federal funds rate (DFF) -- at lags of 0 to 6 months, using the '
        'monthly lag correlations from `notebooks/06_macro_driver_analysis.py` '
        '(`data/processed/macro_lag_correlations.csv`). Full per-family, per-driver results are in '
        f'`{CLASSIFICATION_CSV}`.\n'
    )

    lines.append('### Method and thresholds\n')
    lines.append(
        '- Correlations are computed on two stationary versions of each monthly series (see 06): '
        '**STL residuals** (trend and seasonality removed) and **month-over-month changes** '
        '(log sales seasonally adjusted, log oil, DFF in percentage points). Raw levels are not used: '
        'sales, oil and DFF all trend over 2013-2017, so level correlations (about -0.8 with oil, +0.6 '
        'with DFF) mostly reflect shared trends.'
    )
    lines.append(
        f'- **Sensitive:** at some lag, the STL-residual correlation is significant after '
        f'false-discovery-rate correction (q < {Q_THRESHOLD}) **and** the month-over-month correlation '
        f'at the same lag has the same sign with p < {CONFIRM_P}.'
    )
    lines.append(
        f'- **Weakly sensitive:** at some lag, the STL-residual correlation has q < {Q_THRESHOLD} and the '
        f'month-over-month correlation has the same sign, but p >= {CONFIRM_P}.'
    )
    lines.append('- **Independent:** neither of the above.')
    lines.append(
        '- **Insufficient data:** families marked low-confidence or recording-gap-affected in 06; they '
        'have at most ~26 usable months, so they are not classified.'
    )
    lines.append(
        f'- **Strength** is the size of the STL-residual correlation at the best lag: strong |r| >= '
        f'{STRONG_R}, moderate {MODERATE_R} <= |r| < {STRONG_R}, weak below. The **lag window** is every '
        'lag that is significant with the same sign in both transforms.'
    )
    lines.append(
        f"- A family's overall label is its strongest label across the two drivers. Result: "
        f"{counts.get('sensitive', 0)} sensitive, {counts.get('weakly sensitive', 0)} weakly sensitive, "
        f"{counts.get('independent', 0)} independent (of {n_reliable} series with reliable history, "
        f"including `{TOTAL}`), {counts.get('insufficient data', 0)} insufficient data.\n"
    )

    lines.append('### Classification\n')
    table = classification.copy()
    table['overall'] = table['family'].map(overall)
    table['rank'] = table['overall'].map({l: i for i, l in enumerate(LABEL_ORDER)})
    table['family_sort'] = table['family'].where(table['family'] != TOTAL, '')
    table = table.sort_values(['rank', 'family_sort', 'driver'])

    def cell(row):
        if row['label'] in ('independent', 'insufficient data'):
            return row['label']
        return (f"**{row['label']}** -- {row['direction']}, {row['strength']} "
                f"(r = {row['stl_residual_corr']:+.2f} at lag {int(row['best_lag_months'])}; "
                f"{lag_phrase(row['lag_window'])} significant; month-over-month r = {row['differenced_corr']:+.2f})")

    wide_table = table.assign(result=table.apply(cell, axis=1)).pivot_table(
        index=['rank', 'family_sort', 'family', 'overall'], columns='driver', values='result', aggfunc='first'
    ).reset_index().sort_values(['rank', 'family_sort'])
    out = pd.DataFrame({
        'Family': wide_table['family'].map(lambda f: f'`{f}`' if f == TOTAL else f),
        'Overall': wide_table['overall'],
        'Oil (WTI)': wide_table['dcoilwtico'],
        'Fed funds rate (DFF)': wide_table['dff'],
    })
    lines.append(md_table(out))
    lines.append('')

    lines.append('### Heatmap\n')
    lines.append(f'![Macro driver sensitivity heatmap](../{HEATMAP_PATH})\n')
    lines.append(
        'Each cell is the STL-residual correlation between the family\'s sales in month t and the driver in '
        'month t - lag (red = sales rise when the driver rises; blue = sales fall). Filled dots are '
        'significant and confirmed by the month-over-month series; open dots are significant with the '
        'same sign but not confirmed; x marks are significant on STL residuals but with the opposite sign '
        'month-over-month. Families with insufficient data are omitted.\n'
    )

    lines.append('### Which drivers matter\n')
    active = classification[classification['label'].isin(['sensitive', 'weakly sensitive'])]
    for driver, name in DRIVERS.items():
        d = active[active['driver'] == driver].sort_values(['label', 'family'], key=lambda s: s.map(
            {l: i for i, l in enumerate(LABEL_ORDER)}) if s.name == 'label' else s)
        if len(d) == 0:
            lines.append(f'- **{name}:** no family is sensitive or weakly sensitive.')
            continue
        parts = [f"{r['family']} ({r['label']}, {r['direction']}, {r['strength']}, {lag_phrase(r['lag_window'])})"
                 for _, r in d.iterrows()]
        lines.append(f"- **{name}:** {'; '.join(parts)}.")
    total_label = overall[TOTAL]
    monthly = pd.read_csv(MONTHLY_CSV).query('is_partial_month == 0')
    sensitive_share = (monthly.loc[monthly['family'].map(overall).eq('sensitive'), 'sales'].sum()
                       / monthly['sales'].sum())
    lines.append(
        f'- **`{TOTAL}` is {total_label}** of both drivers: no lag is significant for total sales. The '
        f'sensitive families are small (together {sensitive_share:.1%} of sales), and their relationships '
        'point in different directions.'
    )
    positive = active[(active['driver'] == 'dcoilwtico') & (active['direction'] == 'positive')]['family'].tolist()
    negative = active[(active['driver'] == 'dcoilwtico') & (active['direction'] == 'negative')]['family'].tolist()
    lines.append(
        f"- **Direction:** most oil relationships are positive ({', '.join(positive)}): sales rise after "
        'oil rises. That is consistent with Ecuador being an oil exporter, where higher oil prices mean more '
        f"income and spending, but this analysis cannot establish cause. Negative: {', '.join(negative) or 'none'}."
    )
    lines.append('')

    lines.append('### Caveats\n')
    conflicting = classification[classification['conflicting_lags'] != '']
    lines.append(
        '- **Short history:** 55 complete months (2013-01 to 2017-07). Most of the oil variation is a single '
        'episode, the 2014-2015 price collapse, so a relationship may reflect that one event rather than a '
        'repeatable response.'
    )
    lines.append(
        '- **Weak confirmation overall:** on the month-over-month series, no lag correlation survives the '
        'false-discovery-rate correction, and fewer reach p < 0.05 than chance alone would produce. Even '
        '"sensitive" relationships should be treated as hypotheses to test in a model, not as established effects.'
    )
    lines.append(
        '- **DFF barely moves:** it stays near zero until December 2015 and only reaches 1.16% by mid-2017, '
        'so there is too little variation to measure interest-rate sensitivity.'
    )
    if len(conflicting):
        parts = [f"{r['family']} / {DRIVERS[r['driver']]} (lag {r['conflicting_lags']})" for _, r in conflicting.iterrows()]
        lines.append(
            f"- **Conflicting signals** (significant on STL residuals, opposite sign month-over-month), treated "
            f"as independent: {'; '.join(parts)}."
        )
    lines.append(
        f"- **Excluded families:** the {counts.get('insufficient data', 0)} insufficient-data families (the "
        'late-launched and recording-gap families, including PRODUCE, ~11% of sales) have at most ~26 usable '
        'months and are not classified. Revisit them if more history becomes available.'
    )
    lines.append('- **Correlation, not causation:** other factors that moved at the same time (e.g. the April 2016 '
                 'earthquake, store openings) are not controlled for.\n')

    lines.append('### Recommended lagged macro features\n')
    lines.append(
        'Features should use the **month-over-month change** form, not STL residuals: STL uses a centered '
        'smoother that looks at later months, which would leak future information into a forecast. '
        'Definitions, on the monthly data in `macro_drivers_merged_monthly.csv`:'
    )
    lines.append('- `oil_dlog_lag{k}` = log(oil in month t - k) - log(oil in month t - k - 1), where oil is the '
                 'monthly mean of observed WTI trading days')
    lines.append('- `dff_diff_lag{k}` = DFF in month t - k minus DFF in month t - k - 1, in percentage points')
    lines.append('- Do **not** use oil or DFF levels as features: they trend with sales and will produce '
                 'spurious fits.\n')

    def feature_rows(entries):
        return pd.DataFrame([{
            'Family': family,
            'Driver': DRIVERS[driver],
            'Features': ', '.join(f'`{f}`' for f in features),
            'Expected sign': row['direction'],
        } for family, driver, features, row in entries])

    lines.append('**Recommended** (sensitive families; include in the first feature set):\n')
    lines.append(md_table(feature_rows(recommended)) if recommended else '- None.')
    lines.append('')
    lines.append('**Candidates** (weakly sensitive; keep only if they improve out-of-sample accuracy in '
                 'backtesting):\n')
    lines.append(md_table(feature_rows(candidates)) if candidates else '- None.')
    lines.append('')
    all_features = sorted({f for _, _, features, _ in recommended + candidates for f in features},
                          key=lambda f: (f.split('_lag')[0], int(f.split('_lag')[1])))
    lines.append(
        f"**All features above, combined** (if one shared feature set is used across families): "
        f"{', '.join(f'`{f}`' for f in all_features)}. With only 55 months, testing this many features at once "
        'risks overfitting, so prefer adding them family by family. For '
        f'`{TOTAL}` and the independent families, no macro features are recommended; seasonality, '
        'trend and calendar effects are likely to matter more.\n'
    )

    section = '\n'.join(lines) + '\n'
    existing = ''
    if os.path.exists(FINDINGS_PATH):
        with open(FINDINGS_PATH) as f:
            existing = f.read()

    # Same pattern as 03/04: replace this section in place on reruns so the doc
    # never gets a duplicate copy, and leave any other sections untouched.
    os.makedirs(os.path.dirname(FINDINGS_PATH), exist_ok=True)
    start = existing.find(SECTION_HEADING)
    if start == -1:
        with open(FINDINGS_PATH, 'a') as f:
            f.write(section if existing else f'{DOC_TITLE}\n\n{section}')
        print(f"Appended macro sensitivity findings to {FINDINGS_PATH}")
    else:
        end = existing.find('\n## ', start + len(SECTION_HEADING))
        end = len(existing) if end == -1 else end + 1
        with open(FINDINGS_PATH, 'w') as f:
            f.write(existing[:start] + section + existing[end:])
        print(f"Replaced existing macro sensitivity findings in {FINDINGS_PATH}")


if __name__ == "__main__":
    print(f"\n{'=' * 50}")
    print("MACRO DRIVER SENSITIVITY")
    print(f"{'=' * 50}")

    wide, flags = load_lag_correlations()
    assert wide['lag_months'].max() == MAX_LAG, "lag range changed in 06"
    wide = classify_lags(wide)
    classification = classify(wide, flags)
    overall = family_labels(classification)

    assert len(classification) == len(flags) * len(DRIVERS), "expected one row per (family, driver)"
    assert overall.value_counts().to_dict() == {
        'independent': 14, 'insufficient data': 12, 'sensitive': 4, 'weakly sensitive': 4,
    }, "classification counts changed; re-check the findings text"

    os.makedirs(os.path.dirname(CLASSIFICATION_CSV), exist_ok=True)
    classification.assign(overall_label=classification['family'].map(overall)).to_csv(CLASSIFICATION_CSV, index=False)
    print(f"Saved {CLASSIFICATION_CSV}")

    plot_heatmap(wide, overall)
    recommended, candidates = feature_recommendations(classification)
    write_findings(classification, overall, recommended, candidates)

    print(f"\n{'=' * 50}")
    print("SUMMARY")
    print(f"{'=' * 50}")
    for label in LABEL_ORDER:
        families = sorted(overall[overall == label].index)
        print(f"{label} ({len(families)}): {', '.join(families)}")
    print("\nSensitive / weakly sensitive pairs:")
    active = classification[classification['label'].isin(['sensitive', 'weakly sensitive'])]
    print(active[['family', 'driver', 'label', 'direction', 'strength', 'best_lag_months', 'lag_window',
                  'stl_residual_corr', 'differenced_corr']].round(2).to_string(index=False))
