"""Motor de evaluación: actividad reciente vs. ventanas históricas comparables.

Flujo
-----
1. Se filtran los eventos de la región con los filtros del usuario.
2. La ventana reciente es (T_fin − W, T_fin], donde T_fin es la fecha del
   último evento del catálogo (2026-08-22), no la fecha de hoy.
3. Se construyen ventanas históricas de la misma duración W, móviles con paso
   max(1, W/10) días, desde el inicio de la línea base hasta el inicio de la
   ventana reciente (sin solapamiento con ella).
4. Cada indicador se calcula en todas las ventanas históricas y en la
   reciente; la reciente se ubica en esa distribución con un percentil
   empírico (rango medio).
5. Para el conteo de eventos se añade un modelo de conteos (Binomial
   Negativa o Poisson) ajustado a ventanas históricas SIN solapamiento, que
   da P(N >= n) y P(N <= n).
6. El estado general se basa en el indicador principal (tasa de eventos).
   Los demás indicadores se informan por separado. No se construye un
   índice compuesto (ver Metodología).

Qué catálogo usa cada indicador
-------------------------------
- Tasa, magnitud máxima, energía, profundidad, b-value: catálogo SELECCIONADO
  (completo o desclusterizado, según el selector).
- Agrupamiento temporal y espacial: SIEMPRE catálogo COMPLETO.
"""
from dataclasses import dataclass, replace
from functools import lru_cache

import numpy as np
import pandas as pd

from config import (ANALYSIS_START, CATALOG_MIN_MAG, CATALOG_PARQUET, CELLS_CSV,
                    MAX_ZERO_FRACTION, MIN_EVENTS_BVALUE, MIN_EVENTS_CLUSTER,
                    MIN_EVENTS_DEPTH, REGIONS_CSV, SENS_MIN_MAGS, SENS_WINDOWS,
                    WINDOW_OPTIONS, WINDOW_STRIDE_DIVISOR)
from src import clustering as cl
from src import seismic_analysis as sa
from src import statistics as st

DAYS_PER_YEAR = 365.25
EPOCH = pd.Timestamp("1970-01-01", tz="UTC")


# --------------------------------------------------------------------------
# Datos
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def load_catalog() -> pd.DataFrame:
    cat = pd.read_parquet(CATALOG_PARQUET)
    cat = cat[cat["in_analysis_period"]].sort_values("t_days").reset_index(drop=True)
    return cat


@lru_cache(maxsize=1)
def load_regions_summary() -> pd.DataFrame:
    return pd.read_csv(REGIONS_CSV)


@lru_cache(maxsize=1)
def load_cells_summary() -> pd.DataFrame:
    return pd.read_csv(CELLS_CSV)


def catalog_end_day() -> float:
    return float(load_catalog()["t_days"].max())


def day_to_timestamp(day: float) -> pd.Timestamp:
    return EPOCH + pd.to_timedelta(day, unit="D")


def year_start_day(year: int) -> float:
    return (pd.Timestamp(f"{year}-01-01", tz="UTC") - EPOCH).total_seconds() / 86400.0


@dataclass(frozen=True)
class Selection:
    region_type: str = "region"          # "region" | "cell"
    region_key: str = "Norte de los Andes"
    window_days: int = 90
    min_mag: float = 5.0
    depth_min: float = 0.0
    depth_max: float = 700.0
    catalog: str = "complete"            # "complete" | "declustered"
    mag_scale: str = "all"               # "all" | "mw"
    baseline_start: int = 1973
    b_period_years: int = 5


CATALOG_LABEL = {"complete": "Catálogo completo", "declustered": "Catálogo desclusterizado"}


def filter_events(sel: Selection, catalog_kind: str, region: bool = True) -> pd.DataFrame:
    """Aplica región, magnitud, profundidad, escala y tipo de catálogo."""
    cat = load_catalog()
    m = np.ones(len(cat), dtype=bool)
    if region:
        col = "cell" if sel.region_type == "cell" else "region"
        m &= (cat[col] == sel.region_key).to_numpy()
    m &= (cat["mag_binned"] >= sel.min_mag - 1e-9).to_numpy()
    full_depth = sel.depth_min <= 0 and sel.depth_max >= 700
    if not full_depth:
        d = cat["depth"].clip(lower=0)
        m &= (d >= sel.depth_min).to_numpy() & (d <= sel.depth_max).to_numpy()
    if sel.mag_scale == "mw":
        m &= cat["is_mw_family"].to_numpy()
    if catalog_kind == "declustered":
        m &= ~cat["gk_dependent"].to_numpy()
    return cat.loc[m]


# --------------------------------------------------------------------------
# Indicadores por ventana
# --------------------------------------------------------------------------
def _per_window(func, lo, hi, min_n, *arrays):
    out = np.full(lo.size, np.nan)
    for k in range(lo.size):
        a, b = lo[k], hi[k]
        if b - a >= min_n:
            out[k] = func(*(x[a:b] for x in arrays))
    return out


def _max_or_nan(x):
    return float(np.max(x)) if x.size else np.nan


def _median_observed(x):
    x = x[np.isfinite(x)]
    return float(np.median(x)) if x.size >= MIN_EVENTS_DEPTH else np.nan


def _dep_frac(x):
    return float(np.mean(x))


def _cv(t):
    return cl.coefficient_of_variation(t)


def _nn(lat, lon):
    return cl.nearest_neighbor_median_km(lat, lon)


def _window_geometry(sel: Selection, window_days=None):
    W = float(window_days or sel.window_days)
    t_end = catalog_end_day()
    recent_start = t_end - W
    base_start = year_start_day(sel.baseline_start)
    stride = max(1.0, float(int(W // WINDOW_STRIDE_DIVISOR)))
    starts, ends = st.build_historical_windows(base_start, recent_start, W, stride)
    return W, t_end, recent_start, base_start, stride, starts, ends


INDICATORS = [
    # clave, nombre, catálogo, unidad, dirección interpretativa
    ("n_events", "Número de eventos (tasa)", "selected", "eventos"),
    ("max_mag", "Magnitud máxima", "selected", "M"),
    ("energy", "Energía sísmica liberada", "selected", "log10 J"),
    ("median_depth", "Profundidad mediana", "selected", "km"),
    ("dep_frac", "Fracción de eventos en secuencias (GK)", "complete", "%"),
    ("cv", "Agrupamiento temporal (CV de tiempos entre eventos)", "complete", "—"),
    ("nn_km", "Distancia mediana al vecino más cercano", "complete", "km"),
]

INDICATOR_HELP = {
    "n_events": "Eventos con M ≥ magnitud mínima en la ventana. Indicador principal del estado general.",
    "max_mag": "Mayor magnitud de la ventana. Solo se comparan ventanas con al menos un evento.",
    "energy": "Suma de energías estimadas con log10 E = 1.5M + 4.8 (J). Depende casi por completo del evento mayor, "
              "por eso no es independiente de la magnitud máxima.",
    "median_depth": f"Mediana de las profundidades observadas (≥ {MIN_EVENTS_DEPTH} eventos). "
                    "El 43 % del catálogo tiene profundidades fijas (10/33/35 km).",
    "dep_frac": "Proporción de eventos de la ventana que el declustering de Gardner-Knopoff asigna a una secuencia "
                "(réplicas o premonitores). Mide agrupamiento espacio-temporal.",
    "cv": f"Coeficiente de variación de los tiempos entre eventos (≥ {MIN_EVENTS_CLUSTER} eventos). "
          "CV ≈ 1: ocurrencia tipo Poisson; CV > 1: eventos agrupados en el tiempo.",
    "nn_km": f"Mediana de la distancia de cada evento a su vecino más cercano (≥ {MIN_EVENTS_CLUSTER} eventos). "
             "Valores bajos: eventos más concentrados en el espacio.",
}


def _indicator_arrays(ev_sel, ev_all, starts, ends):
    """Calcula los 7 indicadores para un conjunto de ventanas."""
    t_sel = ev_sel["t_days"].to_numpy()
    lo, hi = st.window_slices(t_sel, starts, ends)
    n = (hi - lo).astype(float)

    mags = ev_sel["mag"].to_numpy()
    e_lin = 10 ** sa.energy_log10_joules(mags)
    cum = np.concatenate([[0.0], np.cumsum(e_lin)])
    energy = cum[hi] - cum[lo]                       # J (0 si no hay eventos)

    out = {
        "n_events": n,
        "max_mag": _per_window(_max_or_nan, lo, hi, 1, mags),
        "energy": energy,
        "median_depth": _per_window(_median_observed, lo, hi, MIN_EVENTS_DEPTH, ev_sel["depth"].to_numpy()),
    }
    t_all = ev_all["t_days"].to_numpy()
    lo2, hi2 = st.window_slices(t_all, starts, ends)
    out["dep_frac"] = _per_window(_dep_frac, lo2, hi2, 5, ev_all["gk_dependent"].to_numpy().astype(float))
    out["cv"] = _per_window(_cv, lo2, hi2, MIN_EVENTS_CLUSTER, t_all)
    out["nn_km"] = _per_window(_nn, lo2, hi2, MIN_EVENTS_CLUSTER,
                               ev_all["latitude"].to_numpy(), ev_all["longitude"].to_numpy())
    out["n_complete"] = (hi2 - lo2).astype(float)
    return out


def _fmt(key, value):
    if not np.isfinite(value):
        return "—"
    if key == "n_events":
        return f"{value:.0f}"
    if key == "energy":
        return f"{np.log10(value):.2f}" if value > 0 else "0 (sin eventos)"
    if key == "max_mag":
        return f"{value:.1f}"
    if key == "dep_frac":
        return f"{value * 100:.0f} %"
    if key in ("median_depth", "nn_km"):
        return f"{value:.0f}"
    return f"{value:.2f}"


@lru_cache(maxsize=64)
def assess(sel: Selection) -> dict:
    """Evaluación completa de una selección (cacheada)."""
    W, t_end, recent_start, base_start, stride, starts, ends = _window_geometry(sel)
    ev_sel = filter_events(sel, sel.catalog)
    ev_all = filter_events(sel, "complete")

    hist = _indicator_arrays(ev_sel, ev_all, starts, ends)
    cur = _indicator_arrays(ev_sel, ev_all, np.array([recent_start]), np.array([t_end]))
    cur = {k: float(v[0]) for k, v in cur.items()}

    windows = pd.DataFrame({"inicio": [day_to_timestamp(s) for s in starts],
                            "fin": [day_to_timestamp(e) for e in ends], **hist})

    # Modelo de conteos sobre ventanas sin solapamiento
    if len(starts):
        no_ov = st.non_overlapping_mask(len(starts), W, stride)
        count_model = st.fit_count_model(hist["n_events"][no_ov])
    else:
        no_ov = np.array([], dtype=bool)
        count_model = st.fit_count_model([])
    p_up, p_low = st.count_tail_probabilities(count_model, cur["n_events"])
    exp_lo, exp_hi = st.count_interval(count_model, 0.90)

    rows = []
    for key, name, kind, unit in INDICATORS:
        dist = hist[key]
        value = cur[key]
        if key == "max_mag":
            dist = dist[np.isfinite(dist)]
        pct = st.empirical_percentile(dist, value)
        code, text = st.classify_percentile(pct)
        desc = st.describe_distribution(dist)
        rows.append({
            "clave": key, "indicador": name,
            "catalogo": CATALOG_LABEL[sel.catalog] if kind == "selected" else CATALOG_LABEL["complete"],
            "unidad": unit,
            "actual": value, "actual_txt": _fmt(key, value),
            "mediana_hist": desc["P50"], "mediana_hist_txt": _fmt(key, desc["P50"]),
            "rango_p5_p95_txt": f"{_fmt(key, desc['P5'])} – {_fmt(key, desc['P95'])}",
            "percentil": pct, "estado_codigo": code, "estado": text,
            "ventanas_validas": desc["n"],
            "p_superior": p_up if key == "n_events" else np.nan,
            "p_inferior": p_low if key == "n_events" else np.nan,
        })
    table = pd.DataFrame(rows)

    zero_frac = float(np.mean(hist["n_events"] == 0)) if len(starts) else np.nan
    daily_rate = (count_model.get("mean", np.nan) / W) if np.isfinite(count_model.get("mean", np.nan)) else np.nan
    rec_window = next((w for w in WINDOW_OPTIONS if np.isfinite(daily_rate) and daily_rate * w >= np.log(1 / MAX_ZERO_FRACTION)), None)

    rate_row = table.iloc[0]
    status = _overall_status(rate_row["estado_codigo"], zero_frac)
    explanations = _explanations(table, sel, W)
    warnings = _warnings(sel, zero_frac, rec_window, ev_sel, hist, cur, len(starts))

    recent_sel = ev_sel[ev_sel["t_days"] > recent_start]
    recent_all = ev_all[ev_all["t_days"] > recent_start]
    hist_sel = ev_sel[(ev_sel["t_days"] > base_start) & (ev_sel["t_days"] <= recent_start)]

    return {
        "selection": sel,
        "window_days": W, "stride_days": stride,
        "t_end": day_to_timestamp(t_end), "recent_start": day_to_timestamp(recent_start),
        "baseline_start": day_to_timestamp(base_start),
        "baseline_years": (recent_start - base_start) / DAYS_PER_YEAR,
        "n_windows": int(len(starts)), "n_windows_independent": int(no_ov.sum()),
        "table": table, "windows": windows, "non_overlapping": no_ov,
        "current": cur, "count_model": count_model,
        "expected_interval_90": (exp_lo, exp_hi),
        "p_upper": p_up, "p_lower": p_low,
        "zero_fraction": zero_frac, "recommended_window": rec_window,
        "status": status, "explanations": explanations, "warnings": warnings,
        "recent_events": recent_sel, "recent_events_complete": recent_all,
        "hist_events": hist_sel,
        "events_selected": ev_sel, "events_complete": ev_all,
    }


def _overall_status(code, zero_frac):
    if code in ("above", "above_ext"):
        label = "ACTIVIDAD POR ENCIMA DE LO ESPERADO HISTÓRICO"
    elif code in ("below", "below_ext"):
        label = "ACTIVIDAD POR DEBAJO DE LO ESPERADO HISTÓRICO"
    elif code == "normal":
        label = "ACTIVIDAD DENTRO DEL RANGO HISTÓRICO"
    else:
        label = "SIN DATOS SUFICIENTES"
    limited = np.isfinite(zero_frac) and zero_frac > MAX_ZERO_FRACTION
    return {"code": code, "label": label, "limited": bool(limited)}


def _ordinal(p):
    return st.percentile_label(p)


def _explanations(table, sel, W):
    out = []
    for _, r in table.iterrows():
        if not np.isfinite(r["percentil"]):
            out.append(f"{r['indicador']}: no evaluable con los datos de esta ventana.")
            continue
        where = {"normal": "dentro del rango histórico",
                 "above": "por encima del P95 histórico", "above_ext": "por encima del P99 histórico",
                 "below": "por debajo del P5 histórico", "below_ext": "por debajo del P1 histórico"}[r["estado_codigo"]]
        out.append(f"{r['indicador']}: {r['actual_txt']} ({_ordinal(r['percentil'])} de las ventanas históricas "
                   f"de {W:.0f} días; mediana histórica {r['mediana_hist_txt']}) — {where}.")
    return out


def _warnings(sel, zero_frac, rec_window, ev_sel, hist, cur, n_windows):
    w = []
    if n_windows == 0:
        w.append("La línea base es más corta que la ventana elegida: no hay ventanas históricas.")
        return w
    if np.isfinite(zero_frac) and zero_frac > MAX_ZERO_FRACTION:
        txt = (f"El {zero_frac * 100:.0f} % de las ventanas históricas de {sel.window_days} días no tiene eventos: "
               "con tan pocos eventos el percentil del conteo es poco informativo.")
        if rec_window:
            txt += f" Para esta región y filtros se recomienda una ventana de al menos {rec_window} días."
        w.append(txt)
    if cur["n_events"] < MIN_EVENTS_CLUSTER:
        w.append(f"La ventana reciente tiene menos de {MIN_EVENTS_CLUSTER} eventos: las métricas de "
                 "agrupamiento temporal y espacial no se calculan.")
    if sel.mag_scale == "mw":
        w.append("Filtro 'solo familia Mw': excluye eventos con mb/ms, cuya proporción cambió con el tiempo; "
                 "los conteos absolutos no son comparables con el catálogo completo.")
    return w


# --------------------------------------------------------------------------
# Evaluación solo de conteos (para sensibilidad y comparación regional)
# --------------------------------------------------------------------------
def count_assessment_from_days(t_days, W, base_start, t_end):
    recent_start = t_end - W
    stride = max(1.0, float(int(W // WINDOW_STRIDE_DIVISOR)))
    starts, ends = st.build_historical_windows(base_start, recent_start, W, stride)
    t = np.sort(np.asarray(t_days, dtype=float))
    if len(starts) == 0:
        return None
    hist = st.window_counts(t, starts, ends).astype(float)
    n_cur = float(np.sum((t > recent_start) & (t <= t_end)))
    no_ov = st.non_overlapping_mask(len(starts), W, stride)
    model = st.fit_count_model(hist[no_ov])
    p_up, p_low = st.count_tail_probabilities(model, n_cur)
    pct = st.empirical_percentile(hist, n_cur)
    code, text = st.classify_percentile(pct)
    return {"n_actual": n_cur, "mediana_hist": float(np.median(hist)), "media_hist": float(hist.mean()),
            "percentil": pct, "estado_codigo": code, "estado": text,
            "p_superior": p_up, "p_inferior": p_low, "p_bilateral": st.two_sided_p(p_up, p_low),
            "fraccion_ceros": float(np.mean(hist == 0)), "modelo": model.get("model"),
            "phi": model.get("phi", np.nan)}


@lru_cache(maxsize=64)
def sensitivity(sel: Selection) -> pd.DataFrame:
    t_end = catalog_end_day()
    base = year_start_day(sel.baseline_start)
    rows = []
    for mmin in SENS_MIN_MAGS:
        ev = filter_events(replace(sel, min_mag=mmin), sel.catalog)
        for W in SENS_WINDOWS:
            r = count_assessment_from_days(ev["t_days"].to_numpy(), W, base, t_end)
            if r is None:
                continue
            r.update(ventana_dias=W, mag_min=mmin,
                     informacion_limitada=r["fraccion_ceros"] > MAX_ZERO_FRACTION)
            rows.append(r)
    return pd.DataFrame(rows)


@lru_cache(maxsize=32)
def regional_comparison(sel: Selection, unit: str = "region") -> pd.DataFrame:
    """Cada unidad contra SU PROPIO historial (no es un ranking)."""
    t_end = catalog_end_day()
    base = year_start_day(sel.baseline_start)
    ev = filter_events(sel, sel.catalog, region=False)
    if unit == "region":
        reg = load_regions_summary()
        keys = reg.loc[reg["habilitada"], "region"].tolist()
        col = "region"
    else:
        keys = load_cells_summary()["cell"].tolist()
        col = "cell"
    groups = {k: g["t_days"].to_numpy() for k, g in ev[ev[col].isin(keys)].groupby(col)}
    rows = []
    for k in keys:
        r = count_assessment_from_days(groups.get(k, np.array([])), sel.window_days, base, t_end)
        if r is None:
            continue
        r["unidad"] = k
        rows.append(r)
    df = pd.DataFrame(rows)
    if len(df):
        df["q_fdr"] = st.bh_fdr(df["p_bilateral"].to_numpy())
        df["informacion_limitada"] = df["fraccion_ceros"] > MAX_ZERO_FRACTION
    return df


# --------------------------------------------------------------------------
# Magnitud-frecuencia y b-value
# --------------------------------------------------------------------------
@lru_cache(maxsize=32)
def magnitude_frequency(sel: Selection) -> dict:
    """b-value histórico vs reciente con Mc estimada (MBS).

    El periodo reciente para b es de 'b_period_years' años (no la ventana de
    conteo), porque el b-value necesita >= 50 eventos sobre Mc.
    """
    t_end = catalog_end_day()
    Y = sel.b_period_years
    rec_start = t_end - Y * DAYS_PER_YEAR
    base = year_start_day(sel.baseline_start)
    ev = filter_events(replace(sel, min_mag=CATALOG_MIN_MAG), sel.catalog)
    floor = max(CATALOG_MIN_MAG, sel.min_mag)

    hist = ev[(ev["t_days"] > base) & (ev["t_days"] <= rec_start)]
    rec = ev[ev["t_days"] > rec_start]
    m_hist = hist["mag_binned"].to_numpy()
    m_rec = rec["mag_binned"].to_numpy()

    mc_hist, mbs_hist, method_hist = sa.estimate_mc_mbs(m_hist, mc_min=floor)
    if m_rec.size >= MIN_EVENTS_BVALUE:
        mc_rec, mbs_rec, method_rec = sa.estimate_mc_mbs(m_rec, mc_min=floor)
    else:
        mc_rec, mbs_rec, method_rec = np.nan, None, "muestra insuficiente"
    mc = float(np.nanmax([mc_hist, mc_rec]))

    yrs_hist = (rec_start - base) / DAYS_PER_YEAR
    s_hist = sa.b_value_summary(m_hist, mc, yrs_hist)
    s_rec = sa.b_value_summary(m_rec, mc, Y)

    delta = s_rec["b"] - s_hist["b"] if (s_hist["valid"] and s_rec["valid"]) else np.nan
    lr, p_lr = (sa.compare_b_values_lrt(m_hist, m_rec, mc) if np.isfinite(delta) else (np.nan, np.nan))
    if np.isfinite(delta) and s_hist["boot"].size and s_rec["boot"].size:
        d_boot = s_rec["boot"] - s_hist["boot"]
        d_lo, d_hi = np.nanpercentile(d_boot, [2.5, 97.5])
    else:
        d_lo, d_hi = np.nan, np.nan

    # b-value en periodos consecutivos de Y años (alineados con T_fin)
    edges = np.arange(t_end, base - 1e-9, -Y * DAYS_PER_YEAR)[::-1]
    series = []
    for a, b in zip(edges[:-1], edges[1:]):
        mm = ev.loc[(ev["t_days"] > a) & (ev["t_days"] <= b), "mag_binned"].to_numpy()
        bv, n = sa.b_value_aki_utsu(mm, mc)
        ok = n >= MIN_EVENTS_BVALUE and np.isfinite(bv)
        series.append({"inicio": day_to_timestamp(a), "fin": day_to_timestamp(b), "n": int(n),
                       "b": bv if ok else np.nan,
                       "sigma": sa.b_sigma_shi_bolt(mm, mc, bv) if ok else np.nan,
                       "reciente": b >= t_end - 1e-6})
    series = pd.DataFrame(series)
    b_hist_periods = series.loc[~series["reciente"], "b"].dropna()
    pct_b = st.empirical_percentile(b_hist_periods, s_rec["b"]) if s_rec["valid"] else np.nan

    fmd_hist = sa.frequency_magnitude_table(m_hist)
    fmd_rec = sa.frequency_magnitude_table(m_rec)
    for t, yrs in ((fmd_hist, yrs_hist), (fmd_rec, Y)):
        t["tasa_anual_acum"] = t["n_acumulado"] / yrs
        t["tasa_anual_bin"] = t["n_bin"] / yrs

    return {"mc": mc, "mc_hist": mc_hist, "mc_rec": mc_rec,
            "mc_method_hist": method_hist, "mc_method_rec": method_rec,
            "mbs_hist": mbs_hist, "mbs_rec": mbs_rec,
            "hist": s_hist, "rec": s_rec, "delta_b": delta, "delta_ci": (d_lo, d_hi),
            "lr": lr, "p_value": p_lr, "percentile_vs_periods": pct_b,
            "series": series, "fmd_hist": fmd_hist, "fmd_rec": fmd_rec,
            "years_hist": yrs_hist, "years_rec": Y,
            "rec_start": day_to_timestamp(rec_start), "baseline_start": day_to_timestamp(base),
            "catalog_label": CATALOG_LABEL[sel.catalog]}


def analysis_start_timestamp():
    return pd.Timestamp(ANALYSIS_START, tz="UTC")
