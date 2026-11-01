"""Figuras del análisis exploratorio y de series de tiempo (sin cálculos estadísticos)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import COLORS, DEPTH_COLORS
from components.theme import empty_figure

ACCENT = COLORS["recent"]
HIST = COLORS["hist_dark"]


def fig_hist_box(values, xlabel, bins=40, log_x=False, color=ACCENT):
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return empty_figure("Sin datos con estos filtros.")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22], vertical_spacing=0.03)
    x = np.log10(v[v > 0]) if log_x else v
    fig.add_trace(go.Histogram(x=x, nbinsx=bins, marker=dict(color=color, line=dict(color="white", width=1)),
                               hovertemplate="%{x}<br>%{y:,} eventos<extra></extra>", showlegend=False), 1, 1)
    fig.add_trace(go.Box(x=x, marker=dict(color=color, size=3), line=dict(color=color), boxpoints="outliers",
                         name="", showlegend=False, hoverinfo="x"), 2, 1)
    fig.update_xaxes(title_text=("log10 " + xlabel) if log_x else xlabel, row=2, col=1)
    fig.update_yaxes(title_text="Eventos", row=1, col=1)
    fig.update_yaxes(showticklabels=False, row=2, col=1)
    fig.update_layout(height=340, bargap=0.05)
    return fig


def fig_bar_counts(series: pd.Series, xlabel, horizontal=True, color=ACCENT):
    s = series.sort_values()
    fig = go.Figure(go.Bar(x=s.values if horizontal else s.index, y=s.index if horizontal else s.values,
                           orientation="h" if horizontal else "v", marker=dict(color=color),
                           hovertemplate="%{y}: %{x:,}<extra></extra>" if horizontal else "%{x}: %{y:,}<extra></extra>"))
    fig.update_layout(height=320, xaxis_title=xlabel if horizontal else "", yaxis_title="" if horizontal else xlabel)
    return fig


def fig_mag_depth(ev: pd.DataFrame):
    if not len(ev):
        return empty_figure("Sin datos.")
    d = ev.dropna(subset=["depth"])
    if len(d) > 8000:
        d = d.sample(8000, random_state=1)
    fig = go.Figure()
    for cls, color in DEPTH_COLORS.items():
        r = d[d["depth_class"] == cls]
        fig.add_trace(go.Scattergl(x=r["depth"].clip(lower=0.5), y=r["mag"], mode="markers", name=cls,
                                   marker=dict(size=4, color=color, opacity=0.45),
                                   hovertemplate="Prof. %{x:.0f} km<br>M %{y:.1f}<extra></extra>"))
    fig.update_xaxes(type="log", title="Profundidad (km, escala log)", tickvals=[1, 3, 10, 30, 70, 100, 300, 700])
    fig.update_yaxes(title="Magnitud")
    fig.update_layout(height=380)
    return fig


def fig_box_by(ev, value, group, order, ylabel):
    fig = go.Figure()
    for g in order:
        v = ev.loc[ev[group] == g, value].dropna()
        if len(v):
            fig.add_trace(go.Box(y=v, name=f"{g} (n={len(v):,})", marker=dict(color=ACCENT, size=3),
                                 line=dict(color=ACCENT), boxpoints="outliers"))
    fig.update_layout(height=360, showlegend=False, yaxis_title=ylabel)
    return fig


def fig_fmd(fmd: pd.DataFrame, b, mc, a_annual=None):
    t = fmd[fmd["n_acumulado"] > 0]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t["magnitud"], y=t["n_acumulado"], mode="markers", name="N(≥M) acumulado",
                             marker=dict(color=ACCENT, size=7), hovertemplate="M ≥ %{x:.1f}: %{y:,}<extra></extra>"))
    fig.add_trace(go.Bar(x=t["magnitud"], y=t["n_bin"], name="Eventos por intervalo de 0.1",
                         marker=dict(color=COLORS["hist"]), opacity=0.6,
                         hovertemplate="M = %{x:.1f}: %{y:,}<extra></extra>"))
    if b is not None and np.isfinite(b):
        n_mc = t.loc[np.isclose(t["magnitud"], mc), "n_acumulado"]
        if len(n_mc):
            a = np.log10(n_mc.iloc[0]) + b * mc
            xm = np.linspace(mc, t["magnitud"].max(), 30)
            fig.add_trace(go.Scatter(x=xm, y=10 ** (a - b * xm), mode="lines", line=dict(color=HIST, dash="dash"),
                                     name=f"Gutenberg-Richter, b = {b:.2f}", hoverinfo="skip"))
    fig.add_vline(x=mc, line=dict(color=COLORS["ink"], dash="dot", width=1))
    fig.update_yaxes(type="log", dtick=1, title="Número de eventos (escala log)")
    fig.update_xaxes(title="Magnitud")
    fig.update_layout(height=360, barmode="overlay")
    return fig


def fig_corr(corr: pd.DataFrame):
    labels = list(corr.columns)
    fig = go.Figure(go.Heatmap(z=corr.values, x=labels, y=labels, zmin=-1, zmax=1,
                               colorscale=[[0, COLORS["below"]], [0.5, "#f2f2f0"], [1, COLORS["above"]]],
                               text=np.round(corr.values, 2), texttemplate="%{text}",
                               hovertemplate="%{x} – %{y}: %{z:.2f}<extra></extra>", colorbar=dict(title="ρ")))
    fig.update_layout(height=380, margin=dict(l=150, b=110))
    return fig


def fig_heat_region_year(tab: pd.DataFrame):
    fig = go.Figure(go.Heatmap(z=tab.values, x=tab.columns, y=tab.index,
                               colorscale=[[0, "#f7f9f9"], [1, ACCENT]], colorbar=dict(title="eventos"),
                               hovertemplate="%{y} · %{x}: %{z} eventos<extra></extra>"))
    fig.update_layout(height=max(380, 18 * len(tab) + 80), margin=dict(l=170))
    return fig


# --------------------------------------------------------------------------
# Series de tiempo
# --------------------------------------------------------------------------
def fig_series(a: pd.DataFrame, var, label, roll=None, anomalies=None, segments=None):
    fig = go.Figure()
    kind = go.Bar if var == "n" and len(a) <= 800 else go.Scatter
    if kind is go.Bar:
        fig.add_trace(go.Bar(x=a["periodo"], y=a[var], marker=dict(color=COLORS["hist"]), name=label,
                             hovertemplate="%{x|%Y-%m-%d}: %{y:,.2f}<extra></extra>"))
    else:
        fig.add_trace(go.Scattergl(x=a["periodo"], y=a[var], mode="lines", line=dict(color=COLORS["hist"], width=1),
                                   name=label, hovertemplate="%{x|%Y-%m-%d}: %{y:,.2f}<extra></extra>"))
    if roll and roll > 1:
        fig.add_trace(go.Scatter(x=a["periodo"], y=a[var].rolling(roll, min_periods=max(1, roll // 2), center=True).mean(),
                                 mode="lines", line=dict(color=ACCENT, width=2.2), name=f"Media móvil centrada ({roll} periodos)",
                                 hoverinfo="skip"))
    if anomalies is not None and anomalies["anomalia"].any():
        an = anomalies[anomalies["anomalia"]]
        fig.add_trace(go.Scatter(x=an["periodo"], y=an.iloc[:, 1], mode="markers", name="Anomalía (|z| > 3.5)",
                                 marker=dict(color=COLORS["above"], size=9, symbol="diamond", line=dict(color="white", width=1)),
                                 customdata=an["z_robusto"],
                                 hovertemplate="%{x|%Y-%m-%d}<br>valor %{y:,.2f}<br>z = %{customdata:.1f}<extra></extra>"))
    if segments:
        for s, e, m in segments:
            fig.add_trace(go.Scatter(x=[a["periodo"].iloc[s], a["periodo"].iloc[e - 1]], y=[m, m], mode="lines",
                                     line=dict(color=COLORS["below_ext"], width=3), showlegend=False,
                                     hovertemplate=f"Media del segmento: {m:,.2f}<extra></extra>"))
    fig.update_layout(height=360, yaxis_title=label, xaxis_title="Periodo (UTC)", bargap=0)
    return fig


def fig_multi_series(a: pd.DataFrame, labels: dict):
    keys = list(labels)
    fig = make_subplots(rows=len(keys), cols=1, shared_xaxes=True, vertical_spacing=0.025,
                        subplot_titles=[labels[k] for k in keys])
    for i, k in enumerate(keys, start=1):
        fig.add_trace(go.Scattergl(x=a["periodo"], y=a[k], mode="lines", line=dict(color=ACCENT, width=1.2),
                                   showlegend=False, hovertemplate="%{x|%Y-%m}: %{y:,.2f}<extra>" + labels[k] + "</extra>"),
                      i, 1)
    fig.update_layout(height=150 * len(keys) + 60, margin=dict(t=40))
    fig.update_annotations(font=dict(size=13, color=COLORS["muted"]), x=0, xanchor="left")
    return fig


def fig_cumulative_energy(a: pd.DataFrame):
    e = 10 ** a["energy_log10"].fillna(-np.inf)
    cum = np.cumsum(np.where(np.isfinite(e), e, 0))
    fig = go.Figure(go.Scatter(x=a["periodo"], y=cum, mode="lines", line=dict(color=ACCENT, width=2, shape="hv"),
                               hovertemplate="%{x|%Y-%m-%d}<br>%{y:.3e} J<extra></extra>"))
    fig.update_layout(height=300, yaxis_title="Energía acumulada (J)", xaxis_title="Periodo")
    fig.update_yaxes(exponentformat="power")
    return fig


def fig_by_decade(a: pd.DataFrame, var, label):
    d = a.dropna(subset=[var]).copy()
    d["decada"] = (d["periodo"].dt.year // 10 * 10).astype(str) + "s"
    fig = go.Figure()
    for dec, g in d.groupby("decada"):
        fig.add_trace(go.Box(y=g[var], name=f"{dec} (n={len(g)})", marker=dict(color=ACCENT, size=3),
                             line=dict(color=ACCENT), boxpoints="outliers"))
    fig.update_layout(height=330, showlegend=False, yaxis_title=label)
    return fig


def fig_acf(tab: pd.DataFrame, band, col, title):
    t = tab[tab["lag"] > 0]
    fig = go.Figure()
    fig.add_hrect(y0=-band, y1=band, fillcolor="#eef0ee", line_width=0, layer="below")
    for _, r in t.iterrows():
        fig.add_shape(type="line", x0=r["lag"], x1=r["lag"], y0=0, y1=r[col], line=dict(color=ACCENT, width=2))
    fig.add_trace(go.Scatter(x=t["lag"], y=t[col], mode="markers", marker=dict(color=ACCENT, size=6),
                             hovertemplate="rezago %{x}: %{y:.3f}<extra></extra>", showlegend=False))
    fig.update_layout(height=280, title=title, xaxis_title="Rezago", yaxis_title=col.upper())
    fig.update_yaxes(range=[min(-0.2, t[col].min() - 0.05), max(0.3, t[col].max() + 0.05)])
    return fig


def fig_stl(stl: pd.DataFrame):
    comps = [("observado", "Observado"), ("tendencia", "Tendencia"), ("estacional", "Estacional"), ("residuo", "Residuo")]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, subplot_titles=[c[1] for c in comps])
    for i, (k, _) in enumerate(comps, start=1):
        fig.add_trace(go.Scatter(x=stl["periodo"], y=stl[k], mode="lines", line=dict(color=ACCENT if i != 1 else HIST, width=1.3),
                                 showlegend=False, hovertemplate="%{x|%Y-%m}: %{y:.1f}<extra></extra>"), i, 1)
    fig.update_layout(height=560, margin=dict(t=40))
    fig.update_annotations(font=dict(size=13, color=COLORS["muted"]), x=0, xanchor="left")
    return fig


def fig_interevent(dt):
    v = np.log10(np.asarray(dt)[np.asarray(dt) > 0] * 24)
    fig = go.Figure(go.Histogram(x=v, nbinsx=60, marker=dict(color=ACCENT, line=dict(color="white", width=0.5)),
                                 hovertemplate="log10 horas %{x}<br>%{y:,}<extra></extra>"))
    fig.update_layout(height=300, xaxis_title="log10 (tiempo entre eventos, horas)", yaxis_title="Frecuencia")
    return fig


# --------------------------------------------------------------------------
# Modelos y pronóstico
# --------------------------------------------------------------------------
MODEL_COLORS = {"naive": "#9aa5ab", "mean": "#c4741c", "ses": "#1f5f74", "arima": "#2b6a9e"}


def fig_model_test(series, ev, labels):
    fig = go.Figure()
    hist = series.iloc[-(len(ev["test"]) + 60):]
    fig.add_trace(go.Scatter(x=hist["periodo"], y=hist["n"], mode="lines", line=dict(color=COLORS["ink"], width=1.5),
                             name="Observado", hovertemplate="%{x|%Y-%m}: %{y}<extra></extra>"))
    for k, fc in ev["paths"].items():
        fig.add_trace(go.Scatter(x=ev["test_periods"], y=fc["mean"], mode="lines",
                                 line=dict(color=MODEL_COLORS[k], width=2, dash="dash" if k == "naive" else "solid"),
                                 name=labels[k], hovertemplate="%{x|%Y-%m}: %{y:.1f}<extra>" + labels[k] + "</extra>"))
    fig.add_vrect(x0=ev["test_periods"].iloc[0], x1=ev["test_periods"].iloc[-1], fillcolor="#eef0ee", line_width=0, layer="below")
    fig.add_annotation(x=ev["test_periods"].iloc[0], y=1, yref="paper", text="periodo de prueba", showarrow=False,
                       xanchor="left", font=dict(size=12, color=COLORS["muted"]))
    fig.update_layout(height=380, yaxis_title="Eventos por mes", xaxis_title="Mes")
    return fig


def fig_forecast(series, fc, label, years_back=15):
    hist = series[series["periodo"] >= series["periodo"].iloc[-1] - pd.DateOffset(years=years_back)]
    x = list(fc["periodo"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x + x[::-1], y=list(fc["hi95"]) + list(fc["lo95"][::-1]), fill="toself",
                             fillcolor="rgba(31,95,116,0.12)", line=dict(width=0), name="Intervalo 95 %", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x + x[::-1], y=list(fc["hi80"]) + list(fc["lo80"][::-1]), fill="toself",
                             fillcolor="rgba(31,95,116,0.25)", line=dict(width=0), name="Intervalo 80 %", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=hist["periodo"], y=hist["n"], mode="lines", line=dict(color=COLORS["ink"], width=1.4),
                             name="Observado", hovertemplate="%{x|%Y-%m}: %{y}<extra></extra>"))
    fig.add_trace(go.Scatter(x=x, y=fc["pronostico"], mode="lines+markers", line=dict(color=ACCENT, width=2.5),
                             marker=dict(size=5), name=f"Pronóstico — {label}",
                             customdata=np.stack([fc["lo95"], fc["hi95"]], axis=-1),
                             hovertemplate="%{x|%Y-%m}: %{y:.1f} eventos<br>IC95 %{customdata[0]:.0f}–%{customdata[1]:.0f}<extra></extra>"))
    fig.update_layout(height=420, yaxis_title="Eventos por mes", xaxis_title="Mes")
    return fig


def fig_residual_acf(resid, max_lag=24):
    r = np.asarray(resid, float)
    r = r[np.isfinite(r)] - np.nanmean(r)
    den = np.sum(r ** 2)
    ac = [np.sum(r[k:] * r[:-k]) / den for k in range(1, max_lag + 1)]
    band = 1.96 / np.sqrt(r.size)
    fig = go.Figure()
    fig.add_hrect(y0=-band, y1=band, fillcolor="#eef0ee", line_width=0, layer="below")
    fig.add_trace(go.Bar(x=list(range(1, max_lag + 1)), y=ac, marker=dict(color=ACCENT),
                         hovertemplate="rezago %{x}: %{y:.3f}<extra></extra>"))
    fig.update_layout(height=260, xaxis_title="Rezago", yaxis_title="ACF de residuos", title="ACF de los residuos (entrenamiento)")
    return fig
