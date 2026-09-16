# Methodology: Affordability-Pressure Index

**This is an independent, transparent construction from public ACS data.
It is not an official City of Los Angeles, LAHD, or LA County metric, and
should not be presented or cited as one.**

## Components

Three ACS 5-year (2019-2023) indicators, each min-max normalized to a
0-100 scale across all LA County tracts:

| Component | Source | Direction |
|---|---|---|
| `pct_severely_rent_burdened` | % of renter households paying 50%+ of income on rent (ACS table B25070) | Higher = more pressure |
| `pct_renter_occupied` | % of occupied units that are renter-occupied (ACS table B25003) | Higher = more pressure |
| `median_household_income` | Median household income (ACS table B19013) | Inverted: lower income = more pressure |

## Normalization

Min-max normalization: `(value - min) / (max - min) * 100`, computed
across all LA County tracts with complete data for all three components.
Income is inverted (`100 - normalized_value`) so that all three components
point the same direction (higher = more pressure) before combining.

**Why min-max instead of z-scores**: min-max keeps every component on an
intuitive, bounded 0-100 scale that's easy to explain to a
non-technical stakeholder ("this tract scores 80 out of 100 on rent
burden relative to the rest of the county"). The tradeoff: it's sensitive
to outliers at the extremes, since one unusually high/low tract stretches
the whole scale. Worth knowing if a single tract's score looks
suspiciously close to 0 or 100.

## Sensitivity check: two weighting schemes

| Scheme | Rent burden | Renter share | Low income |
|---|---|---|---|
| A (equal weight) | 33% | 33% | 33% |
| B (burden-weighted) | 50% | 25% | 25% |

Scheme B weights rent burden higher because it's the most direct
affordability *outcome*; renter share and income are contributing context
rather than the outcome itself. Both schemes are computed side by side in
`sql/analysis/03_affordability_pressure_index.sql` (`pressure_score_equal_weight`
and `pressure_score_burden_weighted`, with matching rank columns) so a
reader can see whether the ranking is sensitive to the choice of weights.
**If the two schemes produce very different top-10 lists, that's worth
flagging in the findings as a real limitation of the index; if they
largely agree, that's evidence the ranking is robust to this particular
methodological choice.**

## Two real data-quality issues found and fixed during development

**1. Census sentinel value (`-666666666`) masquerading as real data.**
Real ACS pulls contain this exact value wherever an estimate couldn't be
computed (typically zero-population or too-small-sample tracts) --
confirmed by inspecting real pulled data, where every affected tract's
`median_household_income` showed exactly `-666666666`. Left as a plain
numeric cast, this would be read as a genuine (and absurd) value and badly
distort min-max normalization for every other tract. Fixed in
`sql/staging/02_stg_acs.sql` with `NULLIF(value, -666666666)` applied to
every ACS numeric field, not just income -- the same sentinel can appear
on any suppressed estimate.

**2. Near-zero-population tracts producing statistically meaningless
percentages.** A handful of tracts (many in the Census's `9800-9899`
special-land-use numbering, consistent with parks/industrial/institutional
land) have fewer than 100 -- sometimes fewer than 20, sometimes zero --
occupied housing units. A single household in one of these tracts can
produce a "100% rent burdened" figure that is mathematically correct but
reflects one household, not a neighborhood pattern. Both
`sql/analysis/03_affordability_pressure_index.sql` and
`sql/analysis/04_need_vs_development_gap.sql` now require
`tenure_total_occupied_units >= 100` before a tract is eligible for the
ranking. **100 is a judgment call, not an official statistical standard**
-- easy to change in either file's `WHERE` clause, and worth reporting as
a sensitivity check alongside the weighting-scheme comparison if time
allows.

## Known limitations

- Built from 3 components only; doesn't include overcrowding, cost burden
  at other income-share thresholds, or eviction-risk indicators, which
  weren't available in a comparably clean form for this MVP.
- ACS 5-year estimates are averaged over 5 years, so the index reflects a
  smoothed multi-year picture, not a single point in time.
- Min-max normalization means the score is *relative to other LA County
  tracts in this dataset*, not an absolute measure of hardship.
- Correlation, not causation: a tract scoring high on this index and low
  on development activity indicates a pattern worth investigating, not a
  causal claim that low development *caused* affordability pressure (or
  vice versa).
