## Ticket #19: Trend Analysis (`03_favorita_trend_analysis.py`)

Daily sales aggregated by family, summed across all 54 stores, over 1688 days (2013-01-01 to 2017-08-15). The 4 known Dec-25 closure dates were zero-filled. Trend is a coarse first-90-day vs. last-90-day average comparison (+/-15% threshold); this is descriptive, not a statistical trend test.

### Families trending up (30)

- **HOME CARE**: from a zero base (first 90d avg 0.0 -> last 90d avg 16462.2)
- **HOME AND KITCHEN I**: from a zero base (first 90d avg 0.0 -> last 90d avg 1730.5)
- **HOME AND KITCHEN II**: from a zero base (first 90d avg 0.0 -> last 90d avg 1716.1)
- **CELEBRATION**: from a zero base (first 90d avg 0.0 -> last 90d avg 728.5)
- **SCHOOL AND OFFICE SUPPLIES**: from a zero base (first 90d avg 0.0 -> last 90d avg 704.6)
- **LADIESWEAR**: from a zero base (first 90d avg 0.0 -> last 90d avg 635.8)
- **PLAYERS AND ELECTRONICS**: from a zero base (first 90d avg 0.0 -> last 90d avg 630.5)
- **PET SUPPLIES**: from a zero base (first 90d avg 0.0 -> last 90d avg 482.8)
- **MAGAZINES**: from a zero base (first 90d avg 0.0 -> last 90d avg 347.3)
- **BABY CARE**: from a zero base (first 90d avg 0.0 -> last 90d avg 10.2)
- **BOOKS**: from a zero base (first 90d avg 0.0 -> last 90d avg 1.8)
- **PRODUCE**: +286360.7% (first 90d avg 44.9 -> last 90d avg 128493.5)
- **LAWN AND GARDEN**: +571.6% (first 90d avg 131.6 -> last 90d avg 884.0)
- **BEVERAGES**: +248.2% (first 90d avg 55568.1 -> last 90d avg 193472.1)
- **DAIRY**: +168.3% (first 90d avg 18179.1 -> last 90d avg 48773.4)
- **BEAUTY**: +146.6% (first 90d avg 129.6 -> last 90d avg 319.7)
- **POULTRY**: +112.2% (first 90d avg 10082.5 -> last 90d avg 21390.2)
- **FROZEN FOODS**: +85.5% (first 90d avg 3914.6 -> last 90d avg 7263.5)
- **GROCERY II**: +83.2% (first 90d avg 909.4 -> last 90d avg 1666.0)
- **GROCERY I**: +79.9% (first 90d avg 140349.9 -> last 90d avg 252513.8)
- **PERSONAL CARE**: +69.2% (first 90d avg 10122.6 -> last 90d avg 17131.9)
- **DELI**: +68.6% (first 90d avg 10169.4 -> last 90d avg 17144.0)
- **AUTOMOTIVE**: +66.0% (first 90d avg 237.9 -> last 90d avg 395.0)
- **BREAD/BAKERY**: +63.6% (first 90d avg 18262.4 -> last 90d avg 29879.5)
- **HOME APPLIANCES**: +62.2% (first 90d avg 16.3 -> last 90d avg 26.4)
- **EGGS**: +57.7% (first 90d avg 6876.6 -> last 90d avg 10846.0)
- **LIQUOR,WINE,BEER**: +57.3% (first 90d avg 3272.0 -> last 90d avg 5147.7)
- **HARDWARE**: +55.9% (first 90d avg 51.2 -> last 90d avg 79.8)
- **CLEANING**: +47.4% (first 90d avg 47302.4 -> last 90d avg 69702.7)
- **MEATS**: +20.0% (first 90d avg 17100.5 -> last 90d avg 20526.5)

### Families trending down (1)

- **LINGERIE**: -29.3% (first 90d avg 522.5 -> last 90d avg 369.3)

### Relatively stable families (2)

- PREPARED FOODS, SEAFOOD

### Sparse families, >50% zero-sales days chain-wide (1)

- **BOOKS**: 83.0% of days at zero chain-wide sales

### Visually obvious repeating patterns (qualitative, from the overview and per-family charts)

- Short-term repeating patterns: Several families appear to show recurring short-term variation in daily sales. Weekly seasonality will be formally examined during the decomposition analysis.
- Annual cycle: several families show a same-direction bump in their 28-day rolling mean recurring around the same time of year across multiple years (visible in the overview grid). Annual patterns are visible in some families but were not formally tested in this analysis and can be explored later if needed.

### Notable anomalies / structural changes

- The April 2016 Ecuador earthquake relief-buying surge and month-start payday cycles are documented in `data/DATA_DICTIONARY.md` as the main source of `sales_outlier_flag` spikes; these remain visible as short raw-sales spikes above the rolling means in the per-family charts.
- The 4 Dec-25 closure dates appear as a zero dip in the raw series each year by construction (zero-filled, not an organic demand drop).
- 11 families (BABY CARE, BOOKS, CELEBRATION, HOME AND KITCHEN I, HOME AND KITCHEN II, HOME CARE, LADIESWEAR, MAGAZINES, PET SUPPLIES, PLAYERS AND ELECTRONICS, SCHOOL AND OFFICE SUPPLIES) show chain-wide sales of exactly 0 for their first 90 days, then a jump to non-zero. Spot-checking the raw data confirms this is a genuine product-line introduction (first non-zero sale chain-wide falls around 2014-01-01 for these families), not an aggregation artifact -- but it means the first-90d/last-90d 'trend' comparison for these families reflects assortment timing, not organic demand growth, and should be read with that caveat.

## Time-Series Decomposition (`04_favorita_decomposition.py`)

**Method:** STL decomposition with weekly period (7 days)

Full per-family ratios are in `data/processed/favorita_seasonality_summary.csv`.

**Results:**
- Strong weekly seasonality (ratio >= 4.5): 12 families
- Medium weekly seasonality (2.0 <= ratio < 4.5): 12 families
- Weak weekly seasonality (ratio < 2.0): 9 families

**Strongest weekly patterns:**
1. EGGS (7.003)
2. BREAD/BAKERY (6.460)
3. POULTRY (5.926)

**Weakest weekly patterns:**
1. BOOKS (0.352)
2. BABY CARE (0.530)
3. LAWN AND GARDEN (0.797)

**Families with many zero-sales days (>10% zeros):**
- BOOKS (83.0%)
- BABY CARE (47.2%)
- LADIESWEAR (39.8%)
- SCHOOL AND OFFICE SUPPLIES (39.8%)
- CELEBRATION (39.6%)
- PLAYERS AND ELECTRONICS (39.6%)
- PET SUPPLIES (39.2%)
- HOME CARE (38.0%)
- MAGAZINES (36.0%)
- HOME AND KITCHEN II (30.7%)
- HOME AND KITCHEN I (30.7%)
- LIQUOR,WINE,BEER (10.8%)
These families have many zero-sales days, so their seasonality ratios should be interpreted with caution.

**STL failures:** None

## Data Files for Downstream Work

Use `data/processed/favorita_family_daily_sales.csv` as the main sales dataset for forecasting and macro analysis.

`data/processed/favorita_seasonality_summary.csv` is a supporting reference showing the relative strength of weekly seasonality for each family.

## Ticket #19: Trend Analysis (`03_favorita_trend_analysis.py`)

Daily sales aggregated by family, summed across all 54 stores, over 1688 days (2013-01-01 to 2017-08-15). The 4 known Dec-25 closure dates were zero-filled. Trend is a coarse first-90-day vs. last-90-day average comparison (+/-15% threshold); this is descriptive, not a statistical trend test.

### Families trending up (30)

- **HOME CARE**: from a zero base (first 90d avg 0.0 -> last 90d avg 16462.2)
- **HOME AND KITCHEN I**: from a zero base (first 90d avg 0.0 -> last 90d avg 1730.5)
- **HOME AND KITCHEN II**: from a zero base (first 90d avg 0.0 -> last 90d avg 1716.1)
- **CELEBRATION**: from a zero base (first 90d avg 0.0 -> last 90d avg 728.5)
- **SCHOOL AND OFFICE SUPPLIES**: from a zero base (first 90d avg 0.0 -> last 90d avg 704.6)
- **LADIESWEAR**: from a zero base (first 90d avg 0.0 -> last 90d avg 635.8)
- **PLAYERS AND ELECTRONICS**: from a zero base (first 90d avg 0.0 -> last 90d avg 630.5)
- **PET SUPPLIES**: from a zero base (first 90d avg 0.0 -> last 90d avg 482.8)
- **MAGAZINES**: from a zero base (first 90d avg 0.0 -> last 90d avg 347.3)
- **BABY CARE**: from a zero base (first 90d avg 0.0 -> last 90d avg 10.2)
- **BOOKS**: from a zero base (first 90d avg 0.0 -> last 90d avg 1.8)
- **PRODUCE**: +286360.7% (first 90d avg 44.9 -> last 90d avg 128493.5)
- **LAWN AND GARDEN**: +571.6% (first 90d avg 131.6 -> last 90d avg 884.0)
- **BEVERAGES**: +248.2% (first 90d avg 55568.1 -> last 90d avg 193472.1)
- **DAIRY**: +168.3% (first 90d avg 18179.1 -> last 90d avg 48773.4)
- **BEAUTY**: +146.6% (first 90d avg 129.6 -> last 90d avg 319.7)
- **POULTRY**: +112.2% (first 90d avg 10082.5 -> last 90d avg 21390.2)
- **FROZEN FOODS**: +85.5% (first 90d avg 3914.6 -> last 90d avg 7263.5)
- **GROCERY II**: +83.2% (first 90d avg 909.4 -> last 90d avg 1666.0)
- **GROCERY I**: +79.9% (first 90d avg 140349.9 -> last 90d avg 252513.8)
- **PERSONAL CARE**: +69.2% (first 90d avg 10122.6 -> last 90d avg 17131.9)
- **DELI**: +68.6% (first 90d avg 10169.4 -> last 90d avg 17144.0)
- **AUTOMOTIVE**: +66.0% (first 90d avg 237.9 -> last 90d avg 395.0)
- **BREAD/BAKERY**: +63.6% (first 90d avg 18262.4 -> last 90d avg 29879.5)
- **HOME APPLIANCES**: +62.2% (first 90d avg 16.3 -> last 90d avg 26.4)
- **EGGS**: +57.7% (first 90d avg 6876.6 -> last 90d avg 10846.0)
- **LIQUOR,WINE,BEER**: +57.3% (first 90d avg 3272.0 -> last 90d avg 5147.7)
- **HARDWARE**: +55.9% (first 90d avg 51.2 -> last 90d avg 79.8)
- **CLEANING**: +47.4% (first 90d avg 47302.4 -> last 90d avg 69702.7)
- **MEATS**: +20.0% (first 90d avg 17100.5 -> last 90d avg 20526.5)

### Families trending down (1)

- **LINGERIE**: -29.3% (first 90d avg 522.5 -> last 90d avg 369.3)

### Relatively stable families (2)

- PREPARED FOODS, SEAFOOD

### Sparse families, >50% zero-sales days chain-wide (1)

- **BOOKS**: 83.0% of days at zero chain-wide sales

### Visually obvious repeating patterns (qualitative, from the overview and per-family charts)

- Short-term repeating patterns: Several families appear to show recurring short-term variation in daily sales. Weekly seasonality will be formally examined during the decomposition analysis.
- Annual cycle: several families show a same-direction bump in their 28-day rolling mean recurring around the same time of year across multiple years (visible in the overview grid); which families and which months is deferred to the seasonal-strength analysis in Ticket #20.

### Notable anomalies / structural changes

- The April 2016 Ecuador earthquake relief-buying surge and month-start payday cycles are documented in `data/DATA_DICTIONARY.md` as the main source of `sales_outlier_flag` spikes; these remain visible as short raw-sales spikes above the rolling means in the per-family charts.
- The 4 Dec-25 closure dates appear as a zero dip in the raw series each year by construction (zero-filled, not an organic demand drop).
- 11 families (BABY CARE, BOOKS, CELEBRATION, HOME AND KITCHEN I, HOME AND KITCHEN II, HOME CARE, LADIESWEAR, MAGAZINES, PET SUPPLIES, PLAYERS AND ELECTRONICS, SCHOOL AND OFFICE SUPPLIES) show chain-wide sales of exactly 0 for their first 90 days, then a jump to non-zero. Spot-checking the raw data confirms this is a genuine product-line introduction (first non-zero sale chain-wide falls around 2014-01-01 for these families), not an aggregation artifact -- but it means the first-90d/last-90d 'trend' comparison for these families reflects assortment timing, not organic demand growth, and should be read with that caveat.

