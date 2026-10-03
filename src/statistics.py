"""Herramientas estadísticas genéricas: ventanas, percentiles, conteos.

Ninguna función de este módulo sabe de sismología; reciben arreglos.
"""
import numpy as np
import pandas as pd
from scipy import stats

from config import P_EXT_HIGH, P_EXT_LOW, P_HIGH, P_LOW


# --------------------------------------------------------------------------
# Ventanas temporales
# --------------------------------------------------------------------------
def build_historical_windows(baseline_start_day, recent_start_day, window_days, stride_days):
    """Extremos (inicio, fin] de las ventanas históricas de longitud W.

    Las ventanas terminan como máximo en el inicio de la ventana reciente, de
    modo que el historial nunca contiene datos del periodo evaluado.
    """
    first_end = baseline_start_day + window_days
    if first_end > recent_start_day:
        return np.array([]), np.array([])
    # Se alinean los extremos para que la última ventana termine exactamente
    # en el inicio de la ventana reciente.
    ends = np.arange(recent_start_day, first_end - 1e-9, -stride_days)[::-1]
    return ends - window_days, ends


def window_slices(event_days, starts, ends):
    """Índices [lo, hi) de los eventos (ordenados) dentro de cada (inicio, fin]."""
    lo = np.searchsorted(event_days, starts, side="right")
    hi = np.searchsorted(event_days, ends, side="right")
    return lo, hi


def window_counts(event_days, starts, ends):
    lo, hi = window_slices(event_days, starts, ends)
    return hi - lo


def non_overlapping_mask(n_windows, window_days, stride_days):
    """Selecciona ventanas sin solapamiento (cada W/stride ventanas),
    contando desde la última hacia atrás."""
    step = max(1, int(round(window_days / stride_days)))
    idx = np.arange(n_windows)
    return ((n_windows - 1 - idx) % step) == 0


# --------------------------------------------------------------------------
# Percentiles y resumen de distribuciones
# --------------------------------------------------------------------------
def empirical_percentile(distribution, value):
    """Percentil de 'value' en la distribución histórica (rango medio).

    P = 100 · [ #(x < v) + 0.5 · #(x = v) ] / n

    El rango medio es necesario con datos discretos (conteos): con muchos
    empates, '#(x <= v)' sobreestimaría el percentil.
    """
    x = np.asarray(distribution, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0 or not np.isfinite(value):
        return np.nan
    below = np.sum(x < value)
    equal = np.sum(x == value)
    return 100.0 * (below + 0.5 * equal) / x.size


def percentile_label(pct):
    """'P97'; por encima de 99.5 se muestra con un decimal (P99.9) para no escribir P100."""
    if pct is None or not np.isfinite(pct):
        return "—"
    return f"P{pct:.1f}" if pct >= 99.5 or pct < 0.5 else f"P{pct:.0f}"


def describe_distribution(distribution):
    x = np.asarray(distribution, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {k: np.nan for k in ["n", "media", "desv_est", "P5", "P25", "P50",
                                    "P75", "P90", "P95", "P99"]}
    q = np.percentile(x, [5, 25, 50, 75, 90, 95, 99])
    return {"n": int(x.size), "media": float(x.mean()), "desv_est": float(x.std(ddof=1)) if x.size > 1 else np.nan,
            "P5": q[0], "P25": q[1], "P50": q[2], "P75": q[3], "P90": q[4], "P95": q[5], "P99": q[6]}


def classify_percentile(pct):
    """Regla operacional del proyecto (ver config): devuelve (código, texto)."""
    if not np.isfinite(pct):
        return "na", "Sin datos suficientes"
    if pct > P_EXT_HIGH:
        return "above_ext", f"Muy por encima (>P{P_EXT_HIGH:.0f})"
    if pct > P_HIGH:
        return "above", f"Por encima (>P{P_HIGH:.0f})"
    if pct < P_EXT_LOW:
        return "below_ext", f"Muy por debajo (<P{P_EXT_LOW:.0f})"
    if pct < P_LOW:
        return "below", f"Por debajo (<P{P_LOW:.0f})"
    return "normal", "Dentro del rango histórico"


# --------------------------------------------------------------------------
# Modelos de conteo
# --------------------------------------------------------------------------
def fit_count_model(counts):
    """Ajuste por momentos de Poisson o Binomial Negativa a conteos por ventana.

    Si la varianza supera a la media (sobredispersión, típica por réplicas),
    se usa la Binomial Negativa con
        r = μ² / (s² − μ),   p = r / (r + μ)
    y si no, Poisson(μ).
    """
    x = np.asarray(counts, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 5:
        return {"model": "insuficiente", "mean": np.nan, "var": np.nan, "phi": np.nan, "n_windows": int(x.size)}
    mu, var = x.mean(), x.var(ddof=1)
    out = {"mean": mu, "var": var, "phi": var / mu if mu > 0 else np.nan, "n_windows": int(x.size)}
    if mu <= 0:
        out["model"] = "degenerado"
    elif var > mu * 1.0001:
        r = mu ** 2 / (var - mu)
        out.update(model="Binomial Negativa", r=r, p=r / (r + mu))
    else:
        out["model"] = "Poisson"
    return out


def count_tail_probabilities(model, n):
    """P(N >= n) y P(N <= n) bajo el modelo ajustado."""
    if model.get("model") == "Binomial Negativa":
        dist = stats.nbinom(model["r"], model["p"])
    elif model.get("model") == "Poisson":
        dist = stats.poisson(model["mean"])
    else:
        return np.nan, np.nan
    return float(dist.sf(n - 1)), float(dist.cdf(n))


def count_interval(model, level=0.90):
    """Intervalo central esperado de conteos (p. ej. 90 %: P5–P95 del modelo)."""
    if model.get("model") == "Binomial Negativa":
        dist = stats.nbinom(model["r"], model["p"])
    elif model.get("model") == "Poisson":
        dist = stats.poisson(model["mean"])
    else:
        return np.nan, np.nan
    a = (1 - level) / 2
    return float(dist.ppf(a)), float(dist.ppf(1 - a))


def two_sided_p(p_upper, p_lower):
    if not (np.isfinite(p_upper) and np.isfinite(p_lower)):
        return np.nan
    return float(min(1.0, 2 * min(p_upper, p_lower)))


def bh_fdr(pvals):
    """q-valores de Benjamini-Hochberg (ignora NaN)."""
    p = np.asarray(pvals, dtype=float)
    q = np.full_like(p, np.nan)
    ok = np.isfinite(p)
    if not ok.any():
        return q
    pv = p[ok]
    m = pv.size
    order = np.argsort(pv)
    ranked = pv[order] * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(ranked, 1.0)
    q[ok] = out
    return q


def to_frame(d: dict) -> pd.DataFrame:
    return pd.DataFrame([d])
