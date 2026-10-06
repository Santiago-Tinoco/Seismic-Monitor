"""Monitor de Actividad Sísmica — aplicación Dash.

Ejecutar (desde la carpeta del proyecto):
    python scripts/build_catalog.py     # solo la primera vez o si cambia el CSV
    python app.py                       # http://127.0.0.1:8050
"""
import os

import numpy as np
import pandas as pd
from dash import Dash, Input, Output, State, dcc, no_update

from config import CATALOG_PARQUET, QUALITY_JSON
from components import pages
from components.layout import main_layout
from src.anomaly_detection import (Selection, assess, catalog_end_day, day_to_timestamp,
                                   load_cells_summary, load_regions_summary, magnitude_frequency,
                                   regional_comparison, sensitivity)
from src.data_processing import load_json
from components.tables import events_frame

if not CATALOG_PARQUET.exists():
    raise SystemExit("No existe data/processed/catalog_clean.parquet. Ejecute primero: python scripts/build_catalog.py")

REPORT = load_json(QUALITY_JSON)
REGIONS = load_regions_summary()
CELLS = load_cells_summary()
DEFAULT_REGION = "Norte de los Andes"


def region_options(region_type):
    if region_type == "cell":
        return [{"label": f"{r.nombre} [{r.cell}] · {r.n_eventos} ev.", "value": r.cell} for r in CELLS.itertuples()]
    enabled = REGIONS[REGIONS["habilitada"]]
    return [{"label": r.region, "value": r.region} for r in enabled.itertuples()]


app = Dash(__name__, title="Monitor de Actividad Sísmica", suppress_callback_exceptions=True,
           external_stylesheets=["https://fonts.googleapis.com/css2?family=Open+Sans:ital,wght@0,300..8001,300..800"
                                 "&display=swap"])
server = app.server
app.layout = main_layout(day_to_timestamp(catalog_end_day()), region_options("region"), DEFAULT_REGION)

CONTROLS = [Input("in-region-type", "value"), Input("in-region", "value"), Input("in-window", "value"),
            Input("in-baseline", "value"), Input("in-minmag", "value"), Input("in-depth", "value"),
            Input("in-scale", "value"), Input("in-catalog", "value"), Input("in-bperiod", "value")]
CONTROL_STATES = [State(c.component_id, c.component_property) for c in CONTROLS]


def make_selection(region_type, region, window, baseline, minmag, depth, scale, catalog, bperiod):
    return Selection(region_type=region_type, region_key=region, window_days=int(window),
                     min_mag=float(minmag), depth_min=float(depth[0]), depth_max=float(depth[1]),
                     catalog=catalog, mag_scale=scale, baseline_start=int(baseline),
                     b_period_years=int(bperiod))


def _valid_region(region_type, region):
    vals = {o["value"] for o in region_options(region_type)}
    return region in vals


@app.callback(Output("in-region", "options"), Output("in-region", "value"),
              Input("in-region-type", "value"), State("in-region", "value"))
def update_region_options(region_type, current):
    opts = region_options(region_type)
    values = [o["value"] for o in opts]
    if current in values:
        return opts, current
    if region_type == "cell":
        # celda por defecto: la que contiene el nido de Bucaramanga si existe, si no la primera
        return opts, "5|-75" if "5|-75" in values else values[0]
    return opts, DEFAULT_REGION


@app.callback(Output("tab-content", "children"), Input("tabs", "value"), *CONTROLS)
def render_tab(tab, region_type, region, window, baseline, minmag, depth, scale, catalog, bperiod):
    if not _valid_region(region_type, region):
        return no_update
    sel = make_selection(region_type, region, window, baseline, minmag, depth, scale, catalog, bperiod)
    if tab == "datos":
        return pages.page_data_method(REPORT, REGIONS)
    if tab == "regional":
        return pages.page_regional(sel, regional_comparison(sel, "region"), regional_comparison(sel, "cell"))
    if tab == "gr":
        return pages.page_gr(sel, magnitude_frequency(sel))
    res = assess(sel)
    if tab == "resumen":
        return pages.page_overview(sel, res, magnitude_frequency(sel))
    if tab == "reciente":
        return pages.page_recent(sel, res)
    if tab == "mapa":
        return pages.page_map(sel, res)
    if tab == "linea_base":
        return pages.page_baseline(sel, res)
    if tab == "anomalias":
        return pages.page_anomalies(sel, res, sensitivity(sel))
    if tab == "eventos":
        return pages.page_events(sel, res)
    return no_update


# --------------------------------------------------------------------------
# Descargas CSV
# --------------------------------------------------------------------------
def _tag(sel):
    key = sel.region_key.replace("|", "_").replace(" ", "_")
    return f"{key}_{sel.window_days}d_M{sel.min_mag:.1f}_{sel.catalog}"


@app.callback(Output("dl-windows", "data"), Input("btn-dl-windows", "n_clicks"), *CONTROL_STATES,
              prevent_initial_call=True)
def download_windows(n, *args):
    sel = make_selection(*args)
    w = assess(sel)["windows"].copy()
    w["energy_log10_J"] = np.where(w["energy"] > 0, np.log10(w["energy"].where(w["energy"] > 0, 1)), np.nan)
    return dcc.send_data_frame(w.to_csv, f"ventanas_historicas_{_tag(sel)}.csv", index=False)


@app.callback(Output("dl-anomaly", "data"), Input("btn-dl-anomaly", "n_clicks"), *CONTROL_STATES,
              prevent_initial_call=True)
def download_anomaly(n, *args):
    sel = make_selection(*args)
    t = assess(sel)["table"].drop(columns=["actual_txt", "mediana_hist_txt"])
    return dcc.send_data_frame(t.to_csv, f"anomalias_{_tag(sel)}.csv", index=False)


@app.callback(Output("dl-sens", "data"), Input("btn-dl-sens", "n_clicks"), *CONTROL_STATES,
              prevent_initial_call=True)
def download_sens(n, *args):
    sel = make_selection(*args)
    return dcc.send_data_frame(sensitivity(sel).to_csv, f"sensibilidad_{_tag(sel)}.csv", index=False)


@app.callback(Output("dl-gr", "data"), Input("btn-dl-gr", "n_clicks"), *CONTROL_STATES,
              prevent_initial_call=True)
def download_gr(n, *args):
    sel = make_selection(*args)
    mf = magnitude_frequency(sel)
    a = mf["fmd_hist"].assign(periodo="historico")
    b = mf["fmd_rec"].assign(periodo=f"reciente_{mf['years_rec']}a")
    summary = pd.DataFrame([
        {"periodo": "historico", "mc": mf["mc"], **{k: mf["hist"][k] for k in ("b", "sigma", "ci_low", "ci_high", "a_annual", "n")}},
        {"periodo": "reciente", "mc": mf["mc"], **{k: mf["rec"][k] for k in ("b", "sigma", "ci_low", "ci_high", "a_annual", "n")}},
        {"periodo": "diferencia", "mc": mf["mc"], "b": mf["delta_b"], "ci_low": mf["delta_ci"][0],
         "ci_high": mf["delta_ci"][1], "p_lrt": mf["p_value"]},
    ])
    out = pd.concat([summary.assign(tabla="resumen_b"), pd.concat([a, b]).assign(tabla="frecuencia_magnitud"),
                     mf["series"].assign(tabla="b_por_periodo")], ignore_index=True)
    return dcc.send_data_frame(out.to_csv, f"gutenberg_richter_{_tag(sel)}.csv", index=False)


@app.callback(Output("dl-regional", "data"), Input("btn-dl-regional", "n_clicks"), *CONTROL_STATES,
              prevent_initial_call=True)
def download_regional(n, *args):
    sel = make_selection(*args)
    out = pd.concat([regional_comparison(sel, "region").assign(tipo="region"),
                     regional_comparison(sel, "cell").assign(tipo="celda")])
    return dcc.send_data_frame(out.to_csv, f"comparacion_regional_{sel.window_days}d_M{sel.min_mag:.1f}.csv", index=False)


@app.callback(Output("dl-events", "data"), Input("btn-dl-events", "n_clicks"), *CONTROL_STATES,
              prevent_initial_call=True)
def download_events(n, *args):
    sel = make_selection(*args)
    ev = events_frame(assess(sel)["events_complete"])
    return dcc.send_data_frame(ev.to_csv, f"eventos_{_tag(sel)}.csv", index=False)


if __name__ == "__main__":
    app.run(debug=os.environ.get("DASH_DEBUG", "0") == "1", host=os.environ.get("HOST", "127.0.0.1"),
            port=int(os.environ.get("PORT", 8050)))
