"""
Realistic mock data generator for fintech app stats.

Figures are estimates based on publicly reported numbers from press releases,
earnings calls, and news articles. This is DEMO DATA — not official figures.

Sources used to calibrate baselines:
- Cash App: Block Q4 2023 earnings (~57M monthly transacting actives)
- Venmo: PayPal annual reports (~90M+ users, ~60M active)
- PayPal: PayPal annual reports (~430M accounts)
- Chime: TechCrunch / Plaid reports (~14-22M members)
- Zelle: Zelle/Early Warning 2023 report (~120M enrolled)
- Robinhood: Robinhood Q4 2023 (~23M funded accounts)
- Dave: Dave 2023 10-K (~7-8M members)
- Current: Business Insider 2021 (~4M members, estimated ~6M by 2024)
- SoFi: SoFi Q4 2023 (~7.5M members)
- Revolut US: Estimates from press coverage (~500K-1M US users)
- Klarna US: Klarna 2023 reports (~37M US users)
- Affirm: Affirm Q4 FY2024 (~18M active consumers)
"""

import numpy as np
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta

# Seed for reproducibility
RNG = np.random.default_rng(42)

# Baseline MAU (millions) as of ~late 2023, and monthly growth rate
# Format: (mau_millions, dau_ratio, monthly_downloads_k, annual_growth_pct)
_BASELINES = {
    "Cash App":   dict(mau=52.0,  dau_ratio=0.30, downloads_k=2200, growth=0.06),
    "Venmo":      dict(mau=58.0,  dau_ratio=0.25, downloads_k=1800, growth=0.04),
    "PayPal":     dict(mau=82.0,  dau_ratio=0.20, downloads_k=2500, growth=0.02),
    "Chime":      dict(mau=16.0,  dau_ratio=0.28, downloads_k=950,  growth=0.08),
    "Zelle":      dict(mau=48.0,  dau_ratio=0.22, downloads_k=800,  growth=0.05),
    "Robinhood":  dict(mau=10.5,  dau_ratio=0.35, downloads_k=700,  growth=0.03),
    "Dave":       dict(mau=7.2,   dau_ratio=0.20, downloads_k=380,  growth=0.05),
    "Current":    dict(mau=5.8,   dau_ratio=0.25, downloads_k=290,  growth=0.09),
    "SoFi":       dict(mau=6.8,   dau_ratio=0.22, downloads_k=320,  growth=0.12),
    "Revolut":    dict(mau=0.9,   dau_ratio=0.38, downloads_k=180,  growth=0.18),
    "Klarna":     dict(mau=31.0,  dau_ratio=0.18, downloads_k=1100, growth=0.07),
    "Affirm":     dict(mau=16.5,  dau_ratio=0.15, downloads_k=600,  growth=0.10),
}

# Anchor date: baselines above are calibrated to this month
_ANCHOR = date(2023, 10, 1)

# Seasonality multipliers by month (index 1=Jan..12=Dec)
# Fintech apps see surges in Jan (new year), Apr (tax season), Nov-Dec (holidays/spending)
_SEASONALITY = {
    1:  1.08,   # Jan — New Year resolutions, new accounts
    2:  0.97,
    3:  1.02,
    4:  1.05,   # Apr — tax refunds drive Cash App / Venmo
    5:  0.98,
    6:  0.96,
    7:  0.94,
    8:  0.95,
    9:  0.97,
    10: 1.00,
    11: 1.04,   # Nov — holiday shopping surge
    12: 1.06,   # Dec — holiday transfers, gifting
}


def _months_between(d1: date, d2: date) -> int:
    """Number of complete months from d1 to d2 (can be negative)."""
    return (d2.year - d1.year) * 12 + (d2.month - d1.month)


def generate(
    app_name: str,
    metric: str,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """
    Generate a monthly time series of estimated metric values for one app.

    Args:
        app_name:   Must be a key in _BASELINES
        metric:     "Downloads", "DAU", or "MAU"
        start_date: Start month (day component ignored)
        end_date:   End month (day component ignored)

    Returns:
        DataFrame with columns [date, app_name, value]
    """
    if app_name not in _BASELINES:
        raise ValueError(f"No mock baseline for '{app_name}'")

    cfg = _BASELINES[app_name]

    # Build list of month-start dates
    months = []
    d = start_date.replace(day=1)
    end = end_date.replace(day=1)
    while d <= end:
        months.append(d)
        d = (d + relativedelta(months=1))

    records = []
    for month in months:
        offset = _months_between(_ANCHOR, month)
        monthly_growth = (1 + cfg["growth"]) ** (offset / 12)
        seasonal = _SEASONALITY[month.month]

        # Small random noise ±3%
        noise = 1.0 + RNG.uniform(-0.03, 0.03)

        if metric == "MAU":
            value = cfg["mau"] * 1_000_000 * monthly_growth * seasonal * noise
        elif metric == "DAU":
            mau = cfg["mau"] * 1_000_000 * monthly_growth * seasonal * noise
            value = mau * cfg["dau_ratio"] * RNG.uniform(0.97, 1.03)
        elif metric == "Downloads":
            value = cfg["downloads_k"] * 1_000 * monthly_growth * seasonal * noise
        else:
            raise ValueError(f"Unknown metric: {metric}")

        records.append({"date": pd.Timestamp(month), "app_name": app_name, "value": round(value)})

    return pd.DataFrame(records)


def generate_multi(
    app_names: list,
    metric: str,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """Generate and combine mock data for multiple apps."""
    frames = [generate(n, metric, start_date, end_date) for n in app_names]
    return pd.concat(frames, ignore_index=True)
