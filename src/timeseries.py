"""Construcción y análisis de series de tiempo sísmicas.

Este módulo tiene una réplica exacta en R (shiny_app/R/timeseries.R). Toda regla
(agregación, periodos completos, rezagos, ventanas, umbrales) se lee de
shared/params.json para que ambas aplicaciones calculen lo mismo.

Reglas de agregación
--------------------
- Periodos de calendario en UTC: día; semana de lunes a domingo; mes; año.
- Se incluyen los periodos sin eventos (conteo = 0). Omitirlos sesgaría la tasa.
- Solo se analizan periodos COMPLETOS dentro del rango de fechas: el primer y
  el último periodo parcial se descartan (p. ej. agosto de 2026, que termina el día 22).
- Conteo = número de eventos. Magnitud media/máxima y profundidad media se
  calculan solo sobre periodos con eventos (NaN si no hay eventos).
- Energía: log10( Σ 10^(1.5 M + 4.8) ) en julios. Se suman energías, nunca magnitudes.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

PARAMS = json.loads((Path(__file__).resolve().parents[1] / "shared" / "params.json").read_text(encoding="utf-8"))

VARIABLES = {
    "n": "Número de eventos",
    "mag_mean": "Magnitud media",
    "mag_max": "Magnitud máxima",
    "depth_mean": "Profundidad media (km)",
    "energy_log10": "Energía liberada (log10 J)",
}


# --------------------------------------------------------------------------
# Filtros y periodos
# --------------------------------------------------------------------------
def filter_events(cat, start, end, min_mag=5.0, depth=(0, 700), region="Global", catalog="complete"):
    """Mismos filtros que en Shiny. start/end son fechas (inclusive, UTC)."""
    t0 = pd.Timestamp(start, tz="UTC")
    t1 = pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
    m = (cat["time"] >= t0) & (cat["time"] < t1) & (cat["mag_binned"] >= min_mag - 1e-9)
    if not (depth[0] <= 0 and depth[1] >= 700):
        d = cat["depth"].clip(lower=0)
        m &= (d >= depth[0]) & (d <= depth[1])
    if region != "Global":
        m &= cat["region"] == region
    if catalog == "declustered":
        m &= ~cat["gk_dependent"].astype(bool)
    return cat.loc[m].sort_values("time")


def period_start(dates: pd.Series, freq: str) -> pd.Series:
    d = dates.dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()
    if freq == "D":
        return d
    if freq == "W":
        return d - pd.to_timedelta(d.dt.weekday, unit="D")
    if freq == "M":
        return d.dt.to_period("M").dt.to_timestamp()
    if freq == "Y":
        return d.dt.to_period("Y").dt.to_timestamp()
    raise ValueError(freq)


def _next_start(s: pd.DatetimeIndex, freq):
    if freq == "D":
        return s + pd.Timedelta(days=1)
    if freq == "W":
        return s + pd.Timedelta(days=7)
    if freq == "M":
        return s + pd.offsets.MonthBegin(1)
    return s + pd.offsets.YearBegin(1)


def complete_period_grid(start, end, freq):
    """Inicios de los periodos completamente contenidos en [start, end]."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    first = period_start(pd.Series([start]).dt.tz_localize("UTC"), freq).iloc[0]
    if first < start:
        first = _next_start(pd.DatetimeIndex([first]), freq)[0]
    starts = pd.date_range(first, end, freq={"D": "D", "W": "7D", "M": "MS", "Y": "YS"}[freq])
    ends = _next_start(starts, freq)
    return starts[ends <= end + pd.Timedelta(days=1)]


def aggregate(events: pd.DataFrame, start, end, freq: str) -> pd.DataFrame:
    grid = complete_period_grid(start, end, freq)
    out = pd.DataFrame({"periodo": grid})
    if len(events):
        e = events.assign(periodo=period_start(events["time"], freq).values)
        e["E"] = 10 ** (PARAMS["energy"]["a"] * e["mag"] + PARAMS["energy"]["b"])
        g = e.groupby("periodo").agg(n=("mag", "size"), mag_mean=("mag", "mean"), mag_max=("mag", "max"),
                                     depth_mean=("depth", "mean"), E=("E", "sum"))
        out = out.merge(g, left_on="periodo", right_index=True, how="left")
    else:
        out[["n", "mag_mean", "mag_max", "depth_mean", "E"]] = np.nan
    out["n"] = out["n"].fillna(0).astype(int)
    out["energy_log10"] = np.where(out["E"] > 0, np.log10(out["E"].where(out["E"] > 0, 1)), np.nan)
    return out.drop(columns="E")


def resolution_table(events, start, end):
    """Justificación de la resolución temporal: ceros, dispersión y huecos."""
    rows = []
    for f in PARAMS["frequencies"]:
        a = aggregate(events, start, end, f)
        n = a["n"].to_numpy(float)
        rows.append({"resolucion": PARAMS["freq_labels"][f], "freq": f, "periodos": len(a),
                     "media": n.mean() if len(n) else np.nan,
                     "varianza": n.var(ddof=1) if len(n) > 1 else np.nan,
                     "dispersion": (n.var(ddof=1) / n.mean()) if len(n) > 1 and n.mean() > 0 else np.nan,
                     "pct_ceros": 100 * np.mean(n == 0) if len(n) else np.nan,
                     "pct_sin_magnitud": 100 * a["mag_mean"].isna().mean() if len(a) else np.nan})
    t = pd.DataFrame(rows)
    ok = t[(t["pct_ceros"] <= 10) & (t["periodos"] >= 60)]
    rec = ok.iloc[0]["freq"] if len(ok) else "M"
    return t, rec


# --------------------------------------------------------------------------
# Pruebas y descriptores
# --------------------------------------------------------------------------
def usable_series(a: pd.DataFrame, var: str):
    """Serie para pruebas: se permite eliminar NaN solo si son <= tolerancia."""
    x = a[var].to_numpy(float)
    frac = np.mean(~np.isfinite(x)) if x.size else 1.0
    if frac > PARAMS["missing_tolerance"]:
        return None, frac
    return x[np.isfinite(x)], frac


def n_lags(n):
    return int(min(PARAMS["acf_max_lags"], max(1, n // 4)))


def acf_pacf(x):
    from statsmodels.tsa.stattools import acf, pacf
    k = n_lags(len(x))
    r = acf(x, nlags=k, adjusted=False, fft=False)
    p = pacf(x, nlags=k, method="ywm")
    band = 1.96 / np.sqrt(len(x))
    return pd.DataFrame({"lag": np.arange(k + 1), "acf": r, "pacf": p}), band


def adf_test(x):
    """ADF con constante y rezagos fijos k = floor(12 (n/100)^(1/4)) (Schwert).
    Equivalente a urca::ur.df(type = "drift", lags = k) en R."""
    import warnings
    from statsmodels.tsa.stattools import adfuller
    k = int(np.floor(12 * (len(x) / 100) ** 0.25))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = adfuller(x, maxlag=k, regression="c", autolag=None)
    stat, p, crit = res[0], res[1], res[4]
    return {"estadistico": stat, "p_valor": p, "rezagos": k, "critico_5": crit["5%"]}


def kpss_test(x):
    """KPSS de nivel, rezagos k = trunc(4 (n/100)^(1/4)) como tseries::kpss.test(lshort=TRUE)."""
    import warnings
    from statsmodels.tsa.stattools import kpss
    k = int(np.trunc(4 * (len(x) / 100) ** 0.25))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        stat, p, _, crit = kpss(x, regression="c", nlags=k)
    return {"estadistico": stat, "p_valor": p, "rezagos": k, "critico_5": crit["5%"]}


def mann_kendall(x):
    """Tendencia monotónica (Mann-Kendall) y pendiente de Sen.
    Supone observaciones independientes: con autocorrelación positiva el
    p-valor es demasiado optimista (se advierte en la interfaz)."""
    x = np.asarray(x, float)
    n = x.size
    if n < 10 or n > PARAMS["mann_kendall_max_n"]:
        return None
    s = 0.0
    slopes = []
    for i in range(n - 1):
        d = x[i + 1:] - x[i]
        s += np.sign(d).sum()
        slopes.append(d / np.arange(1, n - i))
    _, counts = np.unique(x, return_counts=True)
    var = (n * (n - 1) * (2 * n + 5) - np.sum(counts * (counts - 1) * (2 * counts + 5))) / 18
    z = (s - np.sign(s)) / np.sqrt(var) if s != 0 else 0.0
    p = 2 * stats.norm.sf(abs(z))
    return {"S": s, "z": z, "p_valor": p, "sen": float(np.median(np.concatenate(slopes)))}


def kruskal_by_month(a: pd.DataFrame, var="n"):
    """Estacionalidad: ¿difiere la variable entre meses del calendario?"""
    d = a.dropna(subset=[var])
    groups = [g[var].to_numpy() for _, g in d.groupby(d["periodo"].dt.month)]
    if len(groups) < 12:
        return None
    h, p = stats.kruskal(*groups)
    return {"H": h, "p_valor": p}


def stl_decompose(a: pd.DataFrame, var="n"):
    """STL (Cleveland et al., 1990) con los mismos parámetros que stats::stl en R."""
    from statsmodels.tsa.seasonal import STL
    x, _ = usable_series(a, var)
    if x is None or len(x) != len(a) or len(x) < 3 * 12:
        return None
    p = PARAMS["stl"]
    res = STL(pd.Series(x, index=a["periodo"]), period=p["period"], seasonal=p["seasonal"], trend=p["trend"],
              low_pass=p["low_pass"], seasonal_deg=0, trend_deg=1, low_pass_deg=1, robust=True,
              seasonal_jump=int(np.ceil(p["seasonal"] / 10)), trend_jump=int(np.ceil(p["trend"] / 10)),
              low_pass_jump=int(np.ceil(p["low_pass"] / 10))).fit(inner_iter=p["inner"], outer_iter=p["outer"])
    out = pd.DataFrame({"periodo": a["periodo"], "observado": x, "tendencia": res.trend.values,
                        "estacional": res.seasonal.values, "residuo": res.resid.values})
    var_r = np.var(out["residuo"])
    strength = max(0.0, 1 - var_r / np.var(out["estacional"] + out["residuo"]))
    return out, strength


def robust_anomalies(a: pd.DataFrame, var: str, freq: str):
    """z robusto respecto a la mediana y MAD de los w periodos ANTERIORES.
    |z| > 3.5 (Iglewicz & Hoaglin, 1993) se marca como anomalía."""
    w = PARAMS["anomaly_window"][freq]
    thr = PARAMS["anomaly_z"]
    x = a[var].to_numpy(float)
    z = np.full(x.size, np.nan)
    med = np.full(x.size, np.nan)
    for i in range(w, x.size):
        past = x[i - w:i]
        past = past[np.isfinite(past)]
        if past.size < w * 0.8 or not np.isfinite(x[i]):
            continue
        m = np.median(past)
        mad = np.median(np.abs(past - m))
        scale = 1.4826 * mad if mad > 0 else 1.253314 * np.mean(np.abs(past - m))
        med[i] = m
        if scale > 0:
            z[i] = (x[i] - m) / scale
    out = a[["periodo", var]].copy()
    out["mediana_previa"] = med
    out["z_robusto"] = z
    out["anomalia"] = np.abs(z) > thr
    return out


def changepoints(a: pd.DataFrame, var: str, freq: str):
    """Segmentación binaria de cambios en la media (Gaussiana, penalización BIC).
    Para conteos se usa log(1+x) para estabilizar la varianza.
    σ se estima con la MAD de las primeras diferencias (robusta a los saltos)."""
    x, _ = usable_series(a, var)
    if x is None or len(x) != len(a):
        return None
    y = np.log1p(x) if var == "n" else x.copy()
    n = y.size
    minseg = PARAMS["changepoint_min_seg"][freq]
    sigma = 1.4826 * np.median(np.abs(np.diff(y) - np.median(np.diff(y)))) / np.sqrt(2)
    if n < 2 * minseg or sigma <= 0:
        return {"cambios": [], "segmentos": [(0, n, float(np.mean(y)))], "sigma": sigma, "y": y}
    pen = 2 * np.log(n) * sigma ** 2
    cps = []
    for _ in range(PARAMS["changepoint_max"]):
        bounds = [0] + sorted(cps) + [n]
        best = (0.0, None)
        for a0, b0 in zip(bounds[:-1], bounds[1:]):
            seg = y[a0:b0]
            L = seg.size
            if L < 2 * minseg:
                continue
            cs = np.cumsum(seg)
            k = np.arange(minseg, L - minseg + 1)
            m1 = cs[k - 1] / k
            m2 = (cs[-1] - cs[k - 1]) / (L - k)
            gain = k * (L - k) / L * (m1 - m2) ** 2
            j = int(np.argmax(gain))
            if gain[j] > best[0]:
                best = (float(gain[j]), a0 + int(k[j]))
        if best[1] is None or best[0] <= pen:
            break
        cps.append(best[1])
    bounds = [0] + sorted(cps) + [n]
    segs = [(s, e, float(np.mean(y[s:e]))) for s, e in zip(bounds[:-1], bounds[1:])]
    return {"cambios": sorted(cps), "segmentos": segs, "sigma": float(sigma), "y": y}


def interevent_stats(events: pd.DataFrame):
    if len(events) < 3:
        return None
    t = events["t_days"].sort_values().to_numpy()
    dt = np.diff(t)
    return {"n": len(t), "media_dias": dt.mean(), "mediana_dias": float(np.median(dt)),
            "cv": dt.std(ddof=1) / dt.mean() if dt.mean() > 0 else np.nan, "dt": dt}
