"""Caché de cálculos por combinación de filtros (los filtros se aplican con el botón)."""
from functools import lru_cache

import numpy as np
import pandas as pd

from src import forecasting as fc
from src import seismic_analysis as sa
from src import timeseries as ts
from src.anomaly_detection import load_catalog

DEFAULT_FILTERS = {"region": "Global", "start": ts.PARAMS["analysis_start"], "end": ts.PARAMS["default_end"],
                   "min_mag": 5.0, "depth_min": 0, "depth_max": 700, "catalog": "complete", "freq": "M",
                   "var": "n"}


def key(f):
    return (f["region"], f["start"], f["end"], float(f["min_mag"]), float(f["depth_min"]), float(f["depth_max"]),
            f["catalog"])


@lru_cache(maxsize=32)
def events(k):
    region, start, end, mmin, dmin, dmax, catalog = k
    return ts.filter_events(load_catalog(), start, end, mmin, (dmin, dmax), region, catalog)


@lru_cache(maxsize=32)
def events_complete(k):
    return events(k[:-1] + ("complete",))


@lru_cache(maxsize=64)
def series(k, freq):
    return ts.aggregate(events(k), k[1], k[2], freq)


@lru_cache(maxsize=32)
def resolution(k):
    return ts.resolution_table(events(k), k[1], k[2])


@lru_cache(maxsize=64)
def tests(k, freq, var):
    a = series(k, freq)
    x, frac = ts.usable_series(a, var)
    out = {"missing_frac": frac, "n": 0 if x is None else len(x)}
    if x is None or len(x) < 20:
        return out
    out["acf"], out["band"] = ts.acf_pacf(x)
    out["adf"] = ts.adf_test(x)
    out["kpss"] = ts.kpss_test(x)
    out["mk"] = ts.mann_kendall(x)
    if freq == "M":
        out["kruskal"] = ts.kruskal_by_month(a, var)
        out["stl"] = ts.stl_decompose(a, var)
    out["anom"] = ts.robust_anomalies(a, var, freq)
    out["cp"] = ts.changepoints(a, var, freq)
    return out


@lru_cache(maxsize=16)
def gutenberg_richter(k):
    m = events(k)["mag_binned"].to_numpy()
    if m.size < 50:
        return None
    mc, _, method = sa.estimate_mc_mbs(m)
    s = sa.b_value_summary(m, mc)
    return {"mc": mc, "method": method, "summary": s, "fmd": sa.frequency_magnitude_table(m)}


@lru_cache(maxsize=16)
def model_eval(k, test_months):
    return fc.evaluate(series(k, "M"), test_months)


@lru_cache(maxsize=32)
def model_forecast(k, model, h):
    return fc.forecast(series(k, "M"), model, h)


def descriptive(values):
    v = pd.Series(values, dtype=float).dropna()
    if v.empty:
        return {}
    q1, q3 = v.quantile([0.25, 0.75])
    iqr = q3 - q1
    return {"n": len(v), "media": v.mean(), "mediana": v.median(), "desv_est": v.std(), "min": v.min(),
            "P25": q1, "P75": q3, "P95": v.quantile(0.95), "max": v.max(), "asimetria": v.skew(),
            "curtosis": v.kurt(), "atipicos_tukey": int(((v < q1 - 1.5 * iqr) | (v > q3 + 1.5 * iqr)).sum())}


def global_kpis():
    cat = load_catalog()
    k = key(DEFAULT_FILTERS)
    ev = events(k)
    a = series(k, "M")
    big = ev.loc[ev["mag"].idxmax()]
    years = (pd.Timestamp(DEFAULT_FILTERS["end"]) - pd.Timestamp(DEFAULT_FILTERS["start"])).days / 365.25
    e_total = np.log10(np.sum(10 ** (1.5 * ev["mag"] + 4.8)))
    return {"n": len(ev), "years": years, "per_month": a["n"].mean(), "max_mag": big["mag"],
            "max_place": big["place"], "max_date": big["time"], "depth_median": ev["depth"].median(),
            "dependent_pct": 100 * cat["gk_dependent"].mean(), "energy_log10": e_total,
            "months": len(a)}
