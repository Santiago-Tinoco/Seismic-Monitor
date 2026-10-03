"""Análisis sismológico: energía, distribución magnitud-frecuencia, Mc y b-value.

Referencias de los métodos implementados:
  - Energía: Gutenberg & Richter (1956), log10 E[J] = 1.5 M + 4.8
  - b-value: Aki (1965) con corrección por binning de Utsu (1965)
  - Incertidumbre de b: Shi & Bolt (1982) y bootstrap
  - Mc: estabilidad del b-value (MBS), Cao & Gao (2002) en la versión de
        Woessner & Wiemer (2005)
  - Comparación de dos b-values: razón de verosimilitudes de dos
        exponenciales (equivalente al test de Utsu, 1992, basado en AIC)
"""
import numpy as np
import pandas as pd
from scipy import stats

from config import (CATALOG_MIN_MAG, MAG_BIN, MBS_AVG_WIDTH, MC_CANDIDATES_MAX,
                    MIN_EVENTS_BVALUE, N_BOOTSTRAP, RANDOM_SEED)

LOG10_E = np.log10(np.e)


# --------------------------------------------------------------------------
# Magnitud y energía
# --------------------------------------------------------------------------
def bin_magnitudes(mag, dm=MAG_BIN):
    """Redondea a la resolución ΔM (redondeo 'mitad hacia arriba', sin el
    redondeo bancario de np.round). Parte del catálogo tiene 2 decimales."""
    m = np.asarray(mag, dtype=float)
    return np.round(np.floor(m / dm + 0.5 + 1e-9) * dm, 3)


def energy_log10_joules(mag):
    """log10 de la energía sísmica radiada estimada, en julios.

    Relación de Gutenberg & Richter (1956): log10 E = 1.5 M + 4.8 (E en J).
    Es una aproximación: fue calibrada con Ms y su uso con mb o Mw mezcladas
    añade incertidumbre. La energía es aditiva; la magnitud no.
    """
    return 1.5 * np.asarray(mag, dtype=float) + 4.8


def total_energy_log10(mag):
    """log10 de la suma de energías (no la suma de magnitudes)."""
    m = np.asarray(mag, dtype=float)
    if m.size == 0:
        return np.nan
    le = energy_log10_joules(m)
    mx = le.max()
    return mx + np.log10(np.sum(10 ** (le - mx)))


# --------------------------------------------------------------------------
# Distribución magnitud-frecuencia (Gutenberg-Richter)
# --------------------------------------------------------------------------
def frequency_magnitude_table(mag_binned, m_min=CATALOG_MIN_MAG, dm=MAG_BIN):
    """Tabla con conteo por bin (no acumulado) y N(>=M) (acumulado)."""
    m = np.asarray(mag_binned, dtype=float)
    if m.size == 0:
        return pd.DataFrame(columns=["magnitud", "n_bin", "n_acumulado"])
    edges = np.round(np.arange(m_min, m.max() + dm / 2, dm), 3)
    n_bin = np.array([np.sum(np.isclose(m, e)) for e in edges])
    n_cum = np.array([np.sum(m >= e - 1e-9) for e in edges])
    return pd.DataFrame({"magnitud": edges, "n_bin": n_bin, "n_acumulado": n_cum})


def b_value_aki_utsu(mag_binned, mc, dm=MAG_BIN):
    """Estimador de máxima verosimilitud de b para magnitudes binneadas.

        b = log10(e) / ( mean(M) - (Mc - ΔM/2) ),   M >= Mc
    """
    m = np.asarray(mag_binned, dtype=float)
    m = m[m >= mc - 1e-9]
    n = m.size
    if n < 2:
        return np.nan, n
    denom = m.mean() - (mc - dm / 2.0)
    if denom <= 0:
        return np.nan, n
    return LOG10_E / denom, n


def b_sigma_shi_bolt(mag_binned, mc, b):
    """Error estándar de Shi & Bolt (1982):
        σ_b = 2.3 b² sqrt( Σ(Mi - M̄)² / (n(n-1)) )
    """
    m = np.asarray(mag_binned, dtype=float)
    m = m[m >= mc - 1e-9]
    n = m.size
    if n < 2 or not np.isfinite(b):
        return np.nan
    return 2.3 * b ** 2 * np.sqrt(np.sum((m - m.mean()) ** 2) / (n * (n - 1)))


def b_bootstrap_ci(mag_binned, mc, n_boot=N_BOOTSTRAP, seed=RANDOM_SEED, level=0.95):
    m = np.asarray(mag_binned, dtype=float)
    m = m[m >= mc - 1e-9]
    if m.size < MIN_EVENTS_BVALUE:
        return np.nan, np.nan, np.array([])
    rng = np.random.default_rng(seed)
    samples = rng.choice(m, size=(n_boot, m.size), replace=True)
    denom = samples.mean(axis=1) - (mc - MAG_BIN / 2.0)
    bs = np.where(denom > 0, LOG10_E / denom, np.nan)
    lo, hi = np.nanpercentile(bs, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return lo, hi, bs


def a_value(n_above_mc, b, mc, years=None):
    """a de G-R: log10 N(>=Mc) + b·Mc. Si se da 'years', se normaliza a 1 año."""
    if n_above_mc <= 0 or not np.isfinite(b):
        return np.nan
    n = n_above_mc / years if years else n_above_mc
    return np.log10(n) + b * mc


def estimate_mc_mbs(mag_binned, mc_min=CATALOG_MIN_MAG, mc_max=MC_CANDIDATES_MAX,
                    dm=MAG_BIN, width=MBS_AVG_WIDTH, min_n=MIN_EVENTS_BVALUE):
    """Magnitud de completitud por estabilidad del b-value (MBS).

    Para cada Mc candidato se calcula b(Mc) y el promedio b_avg de los b
    estimados entre Mc y Mc + width. Mc es el primer candidato con
    |b_avg - b(Mc)| <= σ_b (Shi-Bolt). La búsqueda empieza en el
    truncamiento del catálogo (5.0): por debajo no hay datos, así que Mc
    nunca puede ser menor que 5.0.

    Devuelve (Mc, tabla de diagnóstico, método usado).
    """
    m = np.asarray(mag_binned, dtype=float)
    cands = np.round(np.arange(mc_min, mc_max + dm / 2, dm), 3)
    rows = []
    for c in cands:
        b, n = b_value_aki_utsu(m, c, dm)
        rows.append({"mc": c, "b": b, "n": n, "sigma": b_sigma_shi_bolt(m, c, b)})
    tab = pd.DataFrame(rows)
    k = int(round(width / dm))
    tab["b_avg"] = [tab["b"].iloc[i:i + k + 1].mean() if i + k < len(tab) else np.nan
                    for i in range(len(tab))]
    tab["estable"] = ((tab["b_avg"] - tab["b"]).abs() <= tab["sigma"]) & (tab["n"] >= min_n)
    ok = tab[tab["estable"]]
    if len(ok):
        return float(ok["mc"].iloc[0]), tab, "MBS"
    # Sin estabilidad demostrable: se usa el truncamiento y se informa.
    return float(mc_min), tab, "truncamiento (MBS no converge)"


def compare_b_values_lrt(mag1, mag2, mc, dm=MAG_BIN):
    """Test de razón de verosimilitudes para H0: b1 = b2.

    Bajo G-R, M - (Mc - ΔM/2) es exponencial con tasa β = b·ln(10).
    LR = 2 [ n1 ln β1 + n2 ln β2 - N ln β0 ],  β0 = pooled; LR ~ χ²(1).
    (El estadístico ΔAIC de Utsu, 1992, es LR - 2.)
    """
    x1 = np.asarray(mag1, dtype=float)
    x2 = np.asarray(mag2, dtype=float)
    x1 = x1[x1 >= mc - 1e-9] - (mc - dm / 2)
    x2 = x2[x2 >= mc - 1e-9] - (mc - dm / 2)
    n1, n2 = x1.size, x2.size
    if n1 < 2 or n2 < 2 or x1.mean() <= 0 or x2.mean() <= 0:
        return np.nan, np.nan
    beta1, beta2 = 1 / x1.mean(), 1 / x2.mean()
    beta0 = (n1 + n2) / (x1.sum() + x2.sum())
    lr = 2 * (n1 * np.log(beta1) + n2 * np.log(beta2) - (n1 + n2) * np.log(beta0))
    lr = max(lr, 0.0)
    return lr, float(stats.chi2.sf(lr, df=1))


def b_value_summary(mag_binned, mc, years=None):
    """b, σ (Shi-Bolt), IC bootstrap 95 %, a-value anual y n."""
    b, n = b_value_aki_utsu(mag_binned, mc)
    valid = n >= MIN_EVENTS_BVALUE and np.isfinite(b)
    if not valid:
        return {"b": np.nan, "sigma": np.nan, "ci_low": np.nan, "ci_high": np.nan,
                "a_annual": np.nan, "n": int(n), "valid": False, "boot": np.array([])}
    lo, hi, boot = b_bootstrap_ci(mag_binned, mc)
    return {"b": b, "sigma": b_sigma_shi_bolt(mag_binned, mc, b), "ci_low": lo, "ci_high": hi,
            "a_annual": a_value(n, b, mc, years), "n": int(n), "valid": True, "boot": boot}
