"""Bloques de cifras clave y estado general."""
import numpy as np
from dash import html

from components.help_texts import term
from src.statistics import percentile_label

STATUS_CLASS = {"above": "st-above", "above_ext": "st-above-ext", "below": "st-below",
                "below_ext": "st-below-ext", "normal": "st-normal", "na": "st-na"}


def status_chip(code, text):
    return html.Span([html.Span(className=f"dot {STATUS_CLASS[code]}"), text], className="chip")


def status_banner(res):
    s = res["status"]
    row = res["table"].iloc[0]
    others = res["table"].iloc[1:]
    out_of_range = others[others["estado_codigo"].isin(["above", "above_ext", "below", "below_ext"])]
    contributors = [status_chip(r["estado_codigo"], f"{r['indicador']}: {percentile_label(r['percentil'])}")
                    for _, r in out_of_range.iterrows()]
    pct = row["percentil"]
    detail = (f"Número de eventos en el percentil {pct:.0f} de {res['n_windows']:,} ventanas históricas "
              f"de {res['window_days']:.0f} días" if np.isfinite(pct) else "Sin ventanas comparables.")
    children = [
        html.Div("EVALUACIÓN ESTADÍSTICA", className="eyebrow"),
        html.Div(s["label"], className=f"status-label {STATUS_CLASS[s['code']]}-text"),
        html.Div(detail, className="status-detail"),
    ]
    if s["limited"]:
        children.append(html.Div("Información limitada: la ventana es corta para la actividad de esta región "
                                 "(ver avisos).", className="status-limited"))
    if contributors:
        children.append(html.Div([html.Span("Otros indicadores fuera del rango P5–P95: ", className="muted")]
                                 + contributors, className="contributors"))
    else:
        children.append(html.Div("Ningún otro indicador está fuera del rango P5–P95 de su historial.",
                                 className="contributors muted"))
    return html.Div(children, className=f"status-banner {STATUS_CLASS[s['code']]}-border")


def kpi(label, value, sub=None, help_key=None):
    lab = term(label, help_key) if help_key else label
    return html.Div([html.Div(lab, className="kpi-label"), html.Div(value, className="kpi-value"),
                     html.Div(sub or "", className="kpi-sub")], className="kpi")


def kpi_row(res, mf):
    cur = res["current"]
    W = res["window_days"]
    n = cur["n_events"]
    rate_day = n / W
    rate_txt = f"{rate_day:.2f} /día" if rate_day >= 0.1 else f"{rate_day * 365.25:.1f} /año"
    med = res["table"].iloc[0]["mediana_hist"]
    e = cur["energy"]
    b = mf["rec"]
    b_txt = f"{b['b']:.2f} ± {b['sigma']:.2f}" if b["valid"] else "no estimable"
    b_sub = (f"últimos {mf['years_rec']} años · histórico {mf['hist']['b']:.2f}" if mf["hist"]["valid"]
             else f"últimos {mf['years_rec']} años")
    depth = cur["median_depth"]
    return html.Div([
        kpi("Eventos", f"{n:.0f}", f"mediana histórica {med:.0f}" if np.isfinite(med) else ""),
        kpi("Tasa", rate_txt, f"ventana de {W:.0f} días", "tasa"),
        kpi("Magnitud máxima", f"M {cur['max_mag']:.1f}" if np.isfinite(cur["max_mag"]) else "—", ""),
        kpi("Energía liberada", f"10^{np.log10(e):.1f} J" if e > 0 else "0 J", "estimada, escala log", "energia"),
        kpi("Profundidad mediana", f"{depth:.0f} km" if np.isfinite(depth) else "—", "valores observados"),
        kpi("b-value reciente", b_txt, b_sub, "b"),
    ], className="kpi-row")
