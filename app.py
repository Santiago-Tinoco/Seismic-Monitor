"""Proyecto EDA — Análisis de series de tiempo de terremotos (Dash).

Ejecutar (desde dash_app/):
    python scripts/build_catalog.py     # solo la primera vez o si cambia el CSV
    python app.py                       # http://127.0.0.1:8050
"""
import os

import numpy as np
import pandas as pd
from dash import Dash, Input, Output, State, dcc, html

from config import CATALOG_PARQUET, QUALITY_JSON
from components import sections as sec
from components.pages import page_anomalies, page_regional
from src import analysis_cache as ac
from src import timeseries as ts
from src.anomaly_detection import (Selection, assess, load_regions_summary, regional_comparison,
                                   sensitivity)
from src.data_processing import load_json

if not CATALOG_PARQUET.exists():
    raise SystemExit("Falta data/processed/catalog_clean.parquet. Ejecute: python scripts/build_catalog.py")

REPORT = load_json(QUALITY_JSON)
REGIONS = load_regions_summary()
REGION_OPTIONS = ["Global"] + REGIONS.loc[REGIONS["habilitada"], "region"].tolist()

NAV = [("/", "bi-house-door", "Inicio"),
       ("/introduccion", "bi-journal-text", "Introducción"),
       ("/problema", "bi-question-circle", "Problema y Objetivos"),
       ("/marco-teorico", "bi-book", "Marco Teórico"),
       ("/eda-univariado", "bi-bar-chart", "EDA Univariado"),
       ("/eda-multivariado", "bi-grid-3x3-gap", "EDA Multivariado"),
       ("/series", "bi-graph-up", "Análisis de Series de Tiempo"),
       ("/modelos", "bi-diagram-3", "Modelos"),
       ("/predecir", "bi-calendar2-week", "Predecir"),
       ("/enlaces", "bi-link-45deg", "Enlaces"),
       ("/equipo", "bi-people", "Equipo")]
FILTER_PAGES = {"/eda-univariado", "/eda-multivariado", "/series", "/modelos", "/predecir"}

# Tipografía Open Sans servida localmente desde assets/vendor/open-sans (Dash carga assets/ automáticamente)
app = Dash(__name__, title="Proyecto EDA · Series de tiempo sísmicas", suppress_callback_exceptions=True)
server = app.server


def sidebar():
    return html.Nav([
        html.Div([html.Div("Proyecto EDA", className="side-brand"),
                  html.Div("Series de tiempo de terremotos", className="side-sub")], className="side-head"),
        html.Div([dcc.Link([html.I(className=f"bi {icon}"), html.Span(label)], href=href, id=f"nav-{i}",
                           className="nav-link") for i, (href, icon, label) in enumerate(NAV)], className="nav-list"),
        html.Div(["Catálogo USGS M ≥ 5 · 1973–2026"], className="side-foot"),
    ], className="side-nav")


def filter_panel():
    d = ac.DEFAULT_FILTERS
    return html.Div([
        html.Div([html.Label("Región"), dcc.Dropdown(id="f-region", value=d["region"], clearable=False,
                                                     options=REGION_OPTIONS)], className="fcol"),
        html.Div([html.Label("Fechas"), dcc.DatePickerRange(id="f-dates", start_date=d["start"], end_date=d["end"],
                                                            min_date_allowed=d["start"], max_date_allowed=d["end"],
                                                            display_format="YYYY-MM-DD")], className="fcol"),
        html.Div([html.Label("Magnitud mínima"), dcc.Dropdown(id="f-mag", value=5.0, clearable=False,
                 options=[{"label": f"M ≥ {m:.1f}", "value": m} for m in (5.0, 5.5, 6.0, 6.5, 7.0)])], className="fcol fcol-s"),
        html.Div([html.Label("Profundidad (km)"), dcc.RangeSlider(id="f-depth", min=0, max=700, step=10, value=[0, 700],
                 marks={0: "0", 70: "70", 300: "300", 700: "700"}, allowCross=False)], className="fcol"),
        html.Div([html.Label("Catálogo"), dcc.Dropdown(id="f-catalog", value="complete", clearable=False,
                 options=[{"label": "Completo", "value": "complete"},
                          {"label": "Desclusterizado (GK)", "value": "declustered"}])], className="fcol fcol-s"),
        html.Div([html.Label("Resolución"), dcc.Dropdown(id="f-freq", value="M", clearable=False,
                 options=[{"label": v, "value": k} for k, v in ts.PARAMS["freq_labels"].items()])], className="fcol fcol-s"),
        html.Div([html.Label("Variable"), dcc.Dropdown(id="f-var", value="n", clearable=False,
                 options=[{"label": v, "value": k} for k, v in ts.VARIABLES.items()])], className="fcol"),
        html.Button([html.I(className="bi bi-arrow-repeat"), " Aplicar filtros"], id="btn-apply", className="btn btn-primary"),
    ], id="filter-panel", className="filter-panel")


app.layout = html.Div([
    dcc.Location(id="url"),
    dcc.Store(id="filters", data=ac.DEFAULT_FILTERS),
    dcc.Store(id="pred-store", data={"model": "ses", "h": ts.PARAMS["forecast"]["default_horizon"]}),
    sidebar(),
    html.Div([
        html.Header([html.Div([html.Span("Proyecto EDA", className="brand"),
                               html.Span(" · Análisis de series de tiempo de terremotos", className="brand-theme")]),
                     html.Div("Análisis Exploratorio de Datos Sísmicos · Evolución temporal de la actividad sísmica",
                              className="brand-sub")], className="top-header"),
        filter_panel(),
        dcc.Loading(html.Div(id="page", className="page"), type="dot", color="#1f5f74"),
        html.Footer("Proyecto académico. Los análisis describen la actividad sísmica registrada; no predicen terremotos.",
                    className="footer"),
    ], className="content"),
    *[dcc.Download(id=i) for i in ("dl-uni", "dl-series", "dl-tests", "dl-eval", "dl-forecast", "dl-anomaly",
                                   "dl-sens", "dl-regional")],
], className="app-shell")


# --------------------------------------------------------------------------
# Navegación y filtros
# --------------------------------------------------------------------------
@app.callback([Output(f"nav-{i}", "className") for i in range(len(NAV))] + [Output("filter-panel", "style")],
              Input("url", "pathname"))
def highlight_nav(path):
    path = path or "/"
    classes = ["nav-link active" if href == path else "nav-link" for href, _, _ in NAV]
    return classes + [{} if path in FILTER_PAGES else {"display": "none"}]


@app.callback(Output("filters", "data"), Input("btn-apply", "n_clicks"),
              State("f-region", "value"), State("f-dates", "start_date"), State("f-dates", "end_date"),
              State("f-mag", "value"), State("f-depth", "value"), State("f-catalog", "value"),
              State("f-freq", "value"), State("f-var", "value"), prevent_initial_call=True)
def apply_filters(n, region, start, end, mag, depth, catalog, freq, var):
    return {"region": region, "start": str(start)[:10], "end": str(end)[:10], "min_mag": float(mag),
            "depth_min": float(depth[0]), "depth_max": float(depth[1]), "catalog": catalog, "freq": freq, "var": var}


@app.callback(Output("page", "children"), Input("url", "pathname"), Input("filters", "data"),
              State("pred-store", "data"))
def render(path, f, pred):
    path = path or "/"
    if path == "/":
        return sec.page_inicio()
    if path == "/introduccion":
        return sec.page_text("Introducción", "Contexto, importancia del análisis temporal y datos", "introduccion.md",
                             sec.dataset_table(REPORT))
    if path == "/problema":
        return sec.page_text("Problema y Objetivos", "Qué se quiere responder y por qué", "problema.md")
    if path == "/marco-teorico":
        return sec.page_text("Marco Teórico", "Conceptos sismológicos y de series de tiempo", "marco_teorico.md")
    if path == "/eda-univariado":
        return sec.page_eda_uni(f)
    if path == "/eda-multivariado":
        return sec.page_eda_multi(f)
    if path == "/series":
        return sec.page_series(f)
    if path == "/modelos":
        return sec.page_modelos(f, ts.PARAMS["forecast"]["test_months"], 90)
    if path == "/predecir":
        return [sec.page_title("Predecir", "Pronóstico estadístico del número mensual de eventos"), sec.filter_note(f),
                html.Div(sec.DISCLAIMER, className="warning-box strong"),
                sec.page_predecir_controls(pred["model"], pred["h"]),
                dcc.Loading(html.Div(sec.page_predecir_result(f, pred["model"], pred["h"]), id="pred-result"),
                            type="dot", color="#1f5f74")]
    if path == "/enlaces":
        return sec.page_enlaces()
    if path == "/equipo":
        return sec.page_equipo()
    return html.Div("Página no encontrada.", className="warning-box")


@app.callback(Output("pred-result", "children"), Output("pred-store", "data"), Input("btn-forecast", "n_clicks"),
              State("pred-model", "value"), State("pred-h", "value"), State("filters", "data"), prevent_initial_call=True)
def run_forecast(n, model, h, f):
    return sec.page_predecir_result(f, model, int(h)), {"model": model, "h": int(h)}


# --------------------------------------------------------------------------
# Monitor de ventana reciente (motor heredado del dashboard anterior)
# --------------------------------------------------------------------------
def monitor_selection(f, window):
    return Selection(region_type="region", region_key=f["region"], window_days=int(window), min_mag=float(f["min_mag"]),
                     depth_min=float(f["depth_min"]), depth_max=float(f["depth_max"]), catalog=f["catalog"])


@app.callback(Output("monitor-content", "children"), Input("mon-window", "value"), State("filters", "data"))
def render_monitor(window, f):
    if f["region"] == "Global":
        sel = Selection(region_key="Norte de los Andes", window_days=int(window), min_mag=float(f["min_mag"]),
                        depth_min=float(f["depth_min"]), depth_max=float(f["depth_max"]), catalog=f["catalog"])
        return [html.Div("Con 'Global' se muestra solo la comparación regional: elija una región en los filtros "
                         "para ver la tabla de indicadores.", className="warning-box")] + \
            page_regional(sel, regional_comparison(sel, "region"), regional_comparison(sel, "cell"))[:1]
    sel = monitor_selection(f, window)
    return page_anomalies(sel, assess(sel), sensitivity(sel))[2:4]


# --------------------------------------------------------------------------
# Descargas
# --------------------------------------------------------------------------
def _tag(f):
    return f"{f['region'].replace(' ', '_')}_{f['start']}_{f['end']}_M{f['min_mag']:.1f}_{f['catalog']}"


@app.callback(Output("dl-series", "data"), Input("btn-dl-series", "n_clicks"), State("filters", "data"), prevent_initial_call=True)
def dl_series(n, f):
    a = ac.series(ac.key(f), f["freq"])
    return dcc.send_data_frame(a.to_csv, f"serie_{f['freq']}_{_tag(f)}.csv", index=False)


@app.callback(Output("dl-tests", "data"), Input("btn-dl-tests", "n_clicks"), State("filters", "data"), prevent_initial_call=True)
def dl_tests(n, f):
    t = ac.tests(ac.key(f), f["freq"], f["var"])
    rows = []
    for name in ("adf", "kpss", "mk", "kruskal"):
        if t.get(name):
            rows += [{"prueba": name, "medida": k, "valor": v} for k, v in t[name].items()]
    if t.get("cp"):
        rows.append({"prueba": "cambios_regimen", "medida": "indices", "valor": ";".join(map(str, t["cp"]["cambios"]))})
    if "acf" in t:
        rows += [{"prueba": "acf", "medida": f"lag_{int(r.lag)}", "valor": r.acf} for r in t["acf"].itertuples()]
        rows += [{"prueba": "pacf", "medida": f"lag_{int(r.lag)}", "valor": r.pacf} for r in t["acf"].itertuples()]
    return dcc.send_data_frame(pd.DataFrame(rows).to_csv, f"pruebas_{f['freq']}_{f['var']}_{_tag(f)}.csv", index=False)


@app.callback(Output("dl-uni", "data"), Input("btn-dl-uni", "n_clicks"), State("filters", "data"), prevent_initial_call=True)
def dl_uni(n, f):
    ev = ac.events(ac.key(f))
    rows = [{"variable": k, **ac.descriptive(v)} for k, v in
            (("magnitud", ev["mag"]), ("profundidad", ev["depth"]),
             ("tiempo_entre_eventos_h", np.diff(ev["t_days"].to_numpy()) * 24))]
    return dcc.send_data_frame(pd.DataFrame(rows).to_csv, f"descriptivas_{_tag(f)}.csv", index=False)


@app.callback(Output("dl-eval", "data"), Input("btn-dl-eval", "n_clicks"), State("filters", "data"), prevent_initial_call=True)
def dl_eval(n, f):
    ev = ac.model_eval(ac.key(f), ts.PARAMS["forecast"]["test_months"])
    return dcc.send_data_frame(ev["table"].to_csv, f"evaluacion_modelos_{_tag(f)}.csv", index=False)


@app.callback(Output("dl-forecast", "data"), Input("btn-dl-forecast", "n_clicks"), State("filters", "data"),
              State("pred-store", "data"), prevent_initial_call=True)
def dl_forecast(n, f, p):
    fc = ac.model_forecast(ac.key(f), p["model"], int(p["h"]))
    return dcc.send_data_frame(fc.to_csv, f"pronostico_{p['model']}_{p['h']}m_{_tag(f)}.csv", index=False)


@app.callback(Output("dl-anomaly", "data"), Input("btn-dl-anomaly", "n_clicks"), State("mon-window", "value"),
              State("filters", "data"), prevent_initial_call=True)
def dl_anomaly(n, w, f):
    t = assess(monitor_selection(f, w))["table"].drop(columns=["actual_txt", "mediana_hist_txt"])
    return dcc.send_data_frame(t.to_csv, f"monitor_anomalias_{w}d_{_tag(f)}.csv", index=False)


@app.callback(Output("dl-sens", "data"), Input("btn-dl-sens", "n_clicks"), State("mon-window", "value"),
              State("filters", "data"), prevent_initial_call=True)
def dl_sens(n, w, f):
    return dcc.send_data_frame(sensitivity(monitor_selection(f, w)).to_csv, f"monitor_sensibilidad_{_tag(f)}.csv", index=False)


@app.callback(Output("dl-regional", "data"), Input("btn-dl-regional", "n_clicks"), State("mon-window", "value"),
              State("filters", "data"), prevent_initial_call=True)
def dl_regional(n, w, f):
    sel = Selection(region_key="Norte de los Andes", window_days=int(w), min_mag=float(f["min_mag"]),
                    depth_min=float(f["depth_min"]), depth_max=float(f["depth_max"]), catalog=f["catalog"])
    return dcc.send_data_frame(regional_comparison(sel, "region").to_csv, f"comparacion_regional_{w}d.csv", index=False)


if __name__ == "__main__":
    app.run(debug=os.environ.get("DASH_DEBUG", "0") == "1", host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", 8050)))
