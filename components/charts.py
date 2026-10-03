"""Constructores de figuras (sin lógica estadística: solo reciben resultados)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config import COLORS, P_HIGH, P_LOW
from components.theme import empty_figure
from src.statistics import percentile_label

STATUS_COLOR = {"normal": COLORS["normal"], "above": COLORS["above"], "above_ext": COLORS["above_ext"],
                "below": COLORS["below"], "below_ext": COLORS["below_ext"], "na": COLORS["na"]}

SHORT_NAMES = {
    "n_events": "Número de eventos",
    "max_mag": "Magnitud máxima",
    "energy": "Energía liberada",
    "median_depth": "Profundidad mediana",
    "dep_frac": "Fracción en secuencias",
    "cv": "CV tiempos entre eventos",
    "nn_km": "Dist. vecino más cercano",
}


# --------------------------------------------------------------------------
# Resumen
# --------------------------------------------------------------------------
def fig_percentile_strip(table: pd.DataFrame):
    """Percentil de cada indicador frente a sus ventanas históricas."""
    t = table.iloc[::-1].copy()
    names = [SHORT_NAMES[k] for k in t["clave"]]
    fig = go.Figure()
    fig.add_vrect(x0=P_LOW, x1=P_HIGH, fillcolor="#eef0ee", line_width=0, layer="below")
    for x in (P_LOW, 50, P_HIGH):
        fig.add_vline(x=x, line=dict(color="#c8cfd2", width=1, dash="dot" if x != 50 else "solid"))
    valid = t["percentil"].notna()
    fig.add_trace(go.Scatter(
        x=t.loc[valid, "percentil"], y=[n for n, v in zip(names, valid) if v], mode="markers+text",
        marker=dict(size=13, color=[STATUS_COLOR[c] for c in t.loc[valid, "estado_codigo"]],
                    line=dict(color="white", width=2)),
        text=[percentile_label(p) for p in t.loc[valid, "percentil"]], textposition="middle right",
        textfont=dict(size=11, color=COLORS["muted"]),
        customdata=np.stack([t.loc[valid, "actual_txt"], t.loc[valid, "mediana_hist_txt"],
                             t.loc[valid, "estado"], t.loc[valid, "catalogo"]], axis=-1),
        hovertemplate="<b>%{y}</b><br>Actual: %{customdata[0]}<br>Mediana histórica: %{customdata[1]}"
                      "<br>Percentil: %{x:.1f}<br>%{customdata[2]}<br><i>%{customdata[3]}</i><extra></extra>",
        showlegend=False))
    na_names = [n for n, v in zip(names, valid) if not v]
    if na_names:
        fig.add_trace(go.Scatter(x=[50] * len(na_names), y=na_names, mode="text", text=["no evaluable"] * len(na_names),
                                 textfont=dict(size=11, color=COLORS["na"]), hoverinfo="skip", showlegend=False))
    fig.update_xaxes(range=[0, 108], tickvals=[0, 5, 25, 50, 75, 95, 100], title="Percentil respecto a ventanas históricas comparables")
    fig.update_yaxes(categoryorder="array", categoryarray=names, gridcolor="rgba(0,0,0,0)")
    fig.update_layout(height=330, margin=dict(l=170, r=20, t=16, b=48))
    fig.add_annotation(x=(P_LOW + P_HIGH) / 2, y=1.04, yref="paper", showarrow=False,
                       text=f"rango histórico habitual (P{P_LOW:.0f}–P{P_HIGH:.0f})",
                       font=dict(size=10, color=COLORS["muted"]))
    return fig


# --------------------------------------------------------------------------
# Actividad reciente
# --------------------------------------------------------------------------
def fig_cumulative_vs_expected(res: dict):
    """Conteo acumulado en la ventana reciente vs. lo esperado por la línea base."""
    ev = res["recent_events"]
    W = res["window_days"]
    t0 = res["recent_start"]
    model = res["count_model"]
    fig = go.Figure()
    if np.isfinite(model.get("mean", np.nan)):
        from scipy import stats
        frac = np.linspace(0, 1, 60)
        x = [t0 + pd.Timedelta(days=W * f) for f in frac]
        mean = model["mean"] * frac
        if model["model"] == "Binomial Negativa":
            # Escalado de la NB a fracciones de ventana: r proporcional a la duración
            r = model["r"] * np.maximum(frac, 1e-9)
            p = model["p"]
            lo = stats.nbinom.ppf(0.05, r, p)
            hi = stats.nbinom.ppf(0.95, r, p)
        else:
            lo = stats.poisson.ppf(0.05, np.maximum(mean, 1e-9))
            hi = stats.poisson.ppf(0.95, np.maximum(mean, 1e-9))
        fig.add_trace(go.Scatter(x=x + x[::-1], y=list(hi) + list(lo[::-1]), fill="toself",
                                 fillcolor="rgba(167,176,180,0.25)", line=dict(width=0),
                                 name="Intervalo esperado 90 % (modelo de conteos)", hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=x, y=mean, mode="lines", line=dict(color=COLORS["hist_dark"], width=2, dash="dash"),
                                 name="Esperado (media histórica)",
                                 hovertemplate="%{x|%Y-%m-%d}<br>Esperado: %{y:.1f}<extra></extra>"))
    if len(ev):
        # Curva escalonada: en cada evento el acumulado sube de k-1 a k
        x, y = [t0], [0]
        for k, t in enumerate(ev["time"], start=1):
            x += [t, t]
            y += [k - 1, k]
        x.append(res["t_end"])
        y.append(len(ev))
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color=COLORS["recent"], width=2.5, shape="linear"),
                                 name="Observado (acumulado)",
                                 hovertemplate="%{x|%Y-%m-%d %H:%M}<br>Acumulado: %{y}<extra></extra>"))
    else:
        fig.add_trace(go.Scatter(x=[t0, res["t_end"]], y=[0, 0], mode="lines",
                                 line=dict(color=COLORS["recent"], width=2.5), name="Observado (sin eventos)"))
    fig.update_layout(height=320, yaxis_title="Eventos acumulados", xaxis_title="Fecha (UTC)")
    fig.update_xaxes(tickformat="%Y-%m-%d")
    return fig


def fig_magnitude_time(res: dict):
    ev = res["recent_events"]
    if not len(ev):
        return empty_figure("Sin eventos en la ventana reciente con estos filtros.", 300)
    fig = go.Figure()
    for _, r in ev.iterrows():
        fig.add_shape(type="line", x0=r["time"], x1=r["time"], y0=5.0, y1=r["mag"],
                      line=dict(color="#c8cfd2", width=1))
    fig.add_trace(go.Scatter(
        x=ev["time"], y=ev["mag"], mode="markers",
        marker=dict(size=8 + (ev["mag"] - 5) * 6, color=COLORS["recent"], line=dict(color="white", width=1.5)),
        customdata=np.stack([ev["place"].fillna("—"), ev["depth"].round(1).astype(str), ev["mag_type"]], axis=-1),
        hovertemplate="<b>M %{y:.1f}</b> (%{customdata[2]})<br>%{x|%Y-%m-%d %H:%M} UTC<br>%{customdata[0]}"
                      "<br>Profundidad: %{customdata[1]} km<extra></extra>",
        showlegend=False))
    fig.update_layout(height=300, yaxis_title="Magnitud", xaxis_title="Fecha (UTC)")
    fig.update_xaxes(range=[res["recent_start"], res["t_end"]], tickformat="%Y-%m-%d")
    fig.update_yaxes(range=[4.9, max(6.5, ev["mag"].max() + 0.3)])
    return fig


def fig_ecdf_compare(hist_values, recent_values, xlabel, log_x=False):
    """ECDF reciente vs histórico (adecuada para muestras pequeñas)."""
    fig = go.Figure()
    for vals, name, color, width in ((hist_values, "Histórico (línea base)", COLORS["hist_dark"], 2),
                                     (recent_values, "Ventana reciente", COLORS["recent"], 2.5)):
        v = np.sort(np.asarray(vals, dtype=float))
        v = v[np.isfinite(v)]
        if v.size == 0:
            continue
        y = np.arange(1, v.size + 1) / v.size
        fig.add_trace(go.Scatter(x=v, y=y, mode="lines", line=dict(color=color, width=width, shape="hv"),
                                 name=f"{name} (n={v.size})",
                                 hovertemplate=f"{xlabel}: %{{x:.1f}}<br>Fracción ≤ x: %{{y:.2f}}<extra>{name}</extra>"))
    fig.update_layout(height=290, xaxis_title=xlabel, yaxis_title="Fracción acumulada")
    fig.update_yaxes(range=[0, 1.02])
    if log_x:
        fig.update_xaxes(type="log", tickvals=[1, 2, 5, 10, 20, 50, 100, 200, 500], ticktext=["1", "2", "5", "10", "20", "50", "100", "200", "500"])
    return fig


# --------------------------------------------------------------------------
# Línea base
# --------------------------------------------------------------------------
def fig_baseline_distribution(res: dict):
    """Distribución de conteos en ventanas históricas, con el valor actual."""
    n = res["windows"]["n_events"].to_numpy()
    if n.size == 0:
        return empty_figure("No hay ventanas históricas para esta configuración.")
    cur = res["current"]["n_events"]
    vals, freq = np.unique(n, return_counts=True)
    frac = freq / freq.sum()
    fig = go.Figure(go.Bar(x=vals, y=frac, marker=dict(color=COLORS["hist"], line=dict(color="white", width=1)),
                           name="Ventanas históricas",
                           hovertemplate="%{x:.0f} eventos<br>%{y:.1%} de las ventanas<extra></extra>"))
    q = np.percentile(n, [5, 50, 95])
    for v, lab in zip(q, ["P5", "P50", "P95"]):
        fig.add_vline(x=v, line=dict(color=COLORS["hist_dark"], width=1, dash="dot"))
        fig.add_annotation(x=v, y=1.0, yref="paper", text=lab, showarrow=False, yshift=8,
                           font=dict(size=10, color=COLORS["muted"]))
    fig.add_vline(x=cur, line=dict(color=COLORS["recent"], width=3))
    fig.add_annotation(x=cur, y=0.82, yref="paper", text=f"<b>Actual: {cur:.0f}</b><br>{percentile_label(res['table'].iloc[0]['percentil'])}",
                       showarrow=False, xanchor="left", xshift=6, font=dict(color=COLORS["recent"], size=12),
                       bgcolor="rgba(255,255,255,0.85)")
    fig.update_layout(height=320, bargap=0.08, xaxis_title=f"Eventos por ventana de {res['window_days']:.0f} días",
                      yaxis_title="Fracción de ventanas", showlegend=False)
    fig.update_yaxes(tickformat=".0%")
    return fig


def fig_rolling_counts(res: dict):
    """Serie de conteos móviles con la banda P5–P95 de la línea base."""
    w = res["windows"]
    if not len(w):
        return empty_figure("No hay ventanas históricas para esta configuración.")
    n = w["n_events"].to_numpy()
    p5, p50, p95 = np.percentile(n, [5, 50, 95])
    x0, x1 = w["fin"].iloc[0], res["t_end"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[x0, x1, x1, x0], y=[p95, p95, p5, p5], fill="toself", mode="lines",
                             fillcolor="rgba(167,176,180,0.22)", line=dict(width=0), hoverinfo="skip",
                             name="Rango P5–P95 de la línea base"))
    fig.add_trace(go.Scatter(x=[x0, x1], y=[p50, p50], mode="lines", line=dict(color=COLORS["hist_dark"], width=1, dash="dash"),
                             name="Mediana histórica", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=w["fin"], y=n, mode="lines", line=dict(color=COLORS["hist_dark"], width=1),
                             name=f"Conteo móvil ({res['window_days']:.0f} días)",
                             hovertemplate="Ventana que termina el %{x|%Y-%m-%d}<br>%{y:.0f} eventos<extra></extra>"))
    fig.add_trace(go.Scatter(x=[res["t_end"]], y=[res["current"]["n_events"]], mode="markers",
                             marker=dict(size=12, color=COLORS["recent"], line=dict(color="white", width=2)),
                             name="Ventana reciente",
                             hovertemplate="Ventana reciente<br>%{y:.0f} eventos<extra></extra>"))
    fig.update_layout(height=320, yaxis_title="Eventos por ventana", xaxis_title="Fin de la ventana (UTC)")
    return fig


# --------------------------------------------------------------------------
# Magnitud-frecuencia
# --------------------------------------------------------------------------
def fig_gutenberg_richter(mf: dict):
    fig = go.Figure()
    mc = mf["mc"]
    for key, name, color, symbol, s_key in (("fmd_hist", "Histórico", COLORS["hist_dark"], "circle-open", "hist"),
                                            ("fmd_rec", f"Reciente ({mf['years_rec']} años)", COLORS["recent"], "circle", "rec")):
        t = mf[key]
        t = t[t["n_acumulado"] > 0]
        if not len(t):
            continue
        fig.add_trace(go.Scatter(x=t["magnitud"], y=t["tasa_anual_acum"], mode="markers", name=f"{name}: N(≥M)/año",
                                 marker=dict(symbol=symbol, size=8, color=color, line=dict(width=1.5, color=color)),
                                 customdata=t["n_acumulado"],
                                 hovertemplate="M ≥ %{x:.1f}<br>%{y:.3g} eventos/año<br>n = %{customdata}<extra>" + name + "</extra>"))
        s = mf[s_key]
        if s["valid"]:
            xm = np.linspace(mc, t["magnitud"].max(), 30)
            fig.add_trace(go.Scatter(x=xm, y=10 ** (s["a_annual"] - s["b"] * xm), mode="lines",
                                     line=dict(color=color, width=2, dash="dash" if s_key == "hist" else "solid"),
                                     name=f"Ajuste {name.lower()}: b = {s['b']:.2f}", hoverinfo="skip"))
    fig.add_vline(x=mc, line=dict(color=COLORS["ink"], width=1, dash="dot"))
    fig.add_annotation(x=mc, y=1, yref="paper", text=f"Mc = {mc:.1f}", showarrow=False, xanchor="left", xshift=4,
                       font=dict(size=11, color=COLORS["ink"]))
    fig.update_yaxes(type="log", dtick=1, title="Eventos por año con magnitud ≥ M (escala log)")
    fig.update_xaxes(title="Magnitud M")
    fig.update_layout(height=380)
    return fig


def fig_b_series(mf: dict):
    s = mf["series"]
    if s["b"].notna().sum() == 0:
        return empty_figure("Ningún periodo tiene ≥ 50 eventos sobre Mc. Pruebe un periodo de b más largo (10 años).")
    mid = s["inicio"] + (s["fin"] - s["inicio"]) / 2
    colors = [COLORS["recent"] if r else COLORS["hist_dark"] for r in s["reciente"]]
    fig = go.Figure(go.Scatter(
        x=mid, y=s["b"], mode="markers",
        error_y=dict(type="data", array=1.96 * s["sigma"], color="#9aa5ab", thickness=1.2, width=4),
        marker=dict(size=10, color=colors, line=dict(color="white", width=1.5)),
        customdata=np.stack([s["inicio"].dt.strftime("%Y-%m-%d"), s["fin"].dt.strftime("%Y-%m-%d"), s["n"]], axis=-1),
        hovertemplate="%{customdata[0]} → %{customdata[1]}<br>b = %{y:.2f}<br>n = %{customdata[2]}<extra></extra>",
        showlegend=False))
    if mf["hist"]["valid"]:
        fig.add_hline(y=mf["hist"]["b"], line=dict(color=COLORS["hist_dark"], width=1, dash="dash"),
                      annotation_text=f"b histórico = {mf['hist']['b']:.2f}", annotation_position="top left",
                      annotation_font=dict(size=10, color=COLORS["muted"]))
    fig.update_layout(height=320, yaxis_title="b-value (± 1.96 σ Shi-Bolt)",
                      xaxis_title=f"Periodos consecutivos de {mf['years_rec']} años (el último es el reciente)")
    return fig


def fig_mbs(mf: dict):
    t = mf["mbs_hist"]
    t = t[t["n"] >= 2]
    if not len(t):
        return empty_figure("Sin datos para el diagnóstico de Mc.")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t["mc"], y=t["b"], mode="lines+markers", name="b(Mc)",
                             line=dict(color=COLORS["hist_dark"], width=2), marker=dict(size=7),
                             error_y=dict(type="data", array=t["sigma"], color="#c8cfd2", thickness=1),
                             customdata=t["n"], hovertemplate="Mc = %{x:.1f}<br>b = %{y:.3f}<br>n = %{customdata}<extra></extra>"))
    fig.add_trace(go.Scatter(x=t["mc"], y=t["b_avg"], mode="lines", name="b promedio (Mc a Mc+0.5)",
                             line=dict(color=COLORS["recent"], width=2, dash="dash"), hoverinfo="skip"))
    fig.add_vline(x=mf["mc_hist"], line=dict(color=COLORS["ink"], width=1, dash="dot"))
    fig.update_layout(height=290, xaxis_title="Magnitud de completitud candidata", yaxis_title="b-value")
    return fig


# --------------------------------------------------------------------------
# Comparación regional
# --------------------------------------------------------------------------
def fig_regional_dots(df: pd.DataFrame, order: list):
    """Percentil de cada región respecto a SU PROPIO historial (orden geográfico)."""
    d = df.set_index("unidad").reindex(order).dropna(subset=["percentil"]).reset_index()
    fig = go.Figure()
    fig.add_vrect(x0=P_LOW, x1=P_HIGH, fillcolor="#eef0ee", line_width=0, layer="below")
    fig.add_vline(x=50, line=dict(color="#c8cfd2", width=1))
    sym = ["circle-open" if lim else "circle" for lim in d["informacion_limitada"]]
    fig.add_trace(go.Scatter(
        x=d["percentil"], y=d["unidad"], mode="markers",
        marker=dict(size=12, symbol=sym, color=[STATUS_COLOR[c] for c in d["estado_codigo"]],
                    line=dict(width=2, color=[STATUS_COLOR[c] for c in d["estado_codigo"]])),
        customdata=np.stack([d["n_actual"], d["mediana_hist"], d["estado"], d["q_fdr"].round(3), d["modelo"]], axis=-1),
        hovertemplate="<b>%{y}</b><br>Percentil: %{x:.1f}<br>Eventos actuales: %{customdata[0]:.0f}"
                      "<br>Mediana histórica: %{customdata[1]:.0f}<br>%{customdata[2]}<br>q (FDR): %{customdata[3]}<extra></extra>",
        showlegend=False))
    fig.update_xaxes(range=[0, 101], tickvals=[0, 5, 25, 50, 75, 95, 100], title="Percentil respecto a su propio historial")
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed([o for o in order if o in set(d["unidad"])])),
                     gridcolor="rgba(0,0,0,0)")
    fig.update_layout(height=max(360, 22 * len(d) + 80), margin=dict(l=170, r=20, t=16, b=48))
    return fig


# --------------------------------------------------------------------------
# Calidad de datos
# --------------------------------------------------------------------------
def fig_annual_counts(annual: dict, start_year: int):
    yrs = np.array(sorted(int(k) for k in annual))
    n = np.array([annual[str(y)] if str(y) in annual else annual[y] for y in yrs])
    colors = [COLORS["recent"] if y >= start_year else COLORS["hist"] for y in yrs]
    fig = go.Figure(go.Bar(x=yrs, y=n, marker=dict(color=colors), hovertemplate="%{x}: %{y:,} eventos<extra></extra>"))
    fig.add_vline(x=start_year - 0.5, line=dict(color=COLORS["ink"], width=1, dash="dot"))
    fig.add_annotation(x=start_year - 0.5, y=1, yref="paper", text=f"inicio del catálogo de trabajo ({start_year})",
                       showarrow=False, xanchor="right", xshift=-4, font=dict(size=11, color=COLORS["ink"]))
    fig.update_layout(height=300, yaxis_title="Eventos M ≥ 5 por año", xaxis_title="Año", bargap=0.1)
    return fig
