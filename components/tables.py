"""Tablas (DataTable para datos navegables, html.Table para resúmenes)."""
import numpy as np
import pandas as pd
from dash import dash_table, html

from config import COLORS, P_HIGH, P_LOW
from components.kpis import status_chip
from src.statistics import percentile_label

TABLE_STYLE = dict(
    style_table={"overflowX": "auto"},
    style_cell={"fontFamily": "IBM Plex Sans, sans-serif", "fontSize": "13px", "padding": "6px 10px",
                "border": "none", "borderBottom": f"1px solid {COLORS['grid']}", "textAlign": "left",
                "color": COLORS["ink"], "whiteSpace": "normal", "height": "auto"},
    style_header={"fontWeight": "600", "backgroundColor": "#f7f8f6", "color": COLORS["muted"],
                  "borderBottom": "1px solid #c8cfd2", "fontSize": "12px"},
)


def simple_table(df: pd.DataFrame, numeric_fmt=None, class_name="simple-table"):
    numeric_fmt = numeric_fmt or {}
    head = html.Thead(html.Tr([html.Th(c) for c in df.columns]))
    rows = []
    for _, r in df.iterrows():
        cells = []
        for c in df.columns:
            v = r[c]
            if c in numeric_fmt and isinstance(v, (int, float, np.floating, np.integer)) and np.isfinite(v):
                v = numeric_fmt[c].format(v)
            cells.append(html.Td(v if not (isinstance(v, float) and np.isnan(v)) else "—"))
        rows.append(html.Tr(cells))
    return html.Table([head, html.Tbody(rows)], className=class_name)


def indicator_table(table: pd.DataFrame):
    rows = []
    for _, r in table.iterrows():
        pct = percentile_label(r["percentil"])
        extra = ""
        if r["clave"] == "n_events" and np.isfinite(r["p_superior"]):
            extra = f"P(N ≥ actual) = {r['p_superior']:.3f} · P(N ≤ actual) = {r['p_inferior']:.3f}"
        rows.append(html.Tr([
            html.Td([html.Div(r["indicador"], className="ind-name"), html.Div(extra, className="ind-extra")]),
            html.Td(r["catalogo"], className="muted small"),
            html.Td(r["actual_txt"], className="num"),
            html.Td(r["mediana_hist_txt"], className="num"),
            html.Td(r["rango_p5_p95_txt"], className="num"),
            html.Td(pct, className="num strong"),
            html.Td(status_chip(r["estado_codigo"], r["estado"])),
            html.Td(f"{r['ventanas_validas']:,}", className="num muted"),
        ]))
    head = html.Thead(html.Tr([html.Th(h) for h in ["Indicador", "Catálogo", "Actual", "Mediana hist.",
                                                     "Rango P5–P95", "Percentil", "Estado", "Ventanas"]]))
    return html.Table([head, html.Tbody(rows)], className="simple-table indicator-table")


def sensitivity_table(df: pd.DataFrame):
    if df.empty:
        return html.Div("Sin datos.", className="muted")
    windows = sorted(df["ventana_dias"].unique())
    mags = sorted(df["mag_min"].unique())
    head = html.Thead(html.Tr([html.Th("Magnitud mínima")] + [html.Th(f"{w} días") for w in windows]))
    body = []
    for m in mags:
        cells = [html.Td(f"M ≥ {m:.1f}", className="strong")]
        for w in windows:
            r = df[(df["ventana_dias"] == w) & (df["mag_min"] == m)]
            if r.empty:
                cells.append(html.Td("—"))
                continue
            r = r.iloc[0]
            arrow = {"above": "▲", "above_ext": "▲▲", "below": "▼", "below_ext": "▼▼"}.get(r["estado_codigo"], "")
            txt = f"{percentile_label(r['percentil'])} {arrow}".strip()
            sub = f"{r['n_actual']:.0f} vs {r['mediana_hist']:.0f}"
            cls = f"sens-cell sens-{r['estado_codigo']}" + (" sens-limited" if r["informacion_limitada"] else "")
            cells.append(html.Td([html.Div(txt, className="sens-main"), html.Div(sub, className="sens-sub")],
                                 className=cls, title=f"{r['estado']} · P(N≥n) = {r['p_superior']:.3f}"
                                 + (" · información limitada (muchas ventanas sin eventos)" if r["informacion_limitada"] else "")))
        body.append(html.Tr(cells))
    return html.Table([head, html.Tbody(body)], className="simple-table sens-table")


EVENT_COLUMNS = [
    ("time_utc", "Fecha y hora (UTC)"), ("mag", "Magnitud"), ("mag_type", "Escala"),
    ("depth", "Prof. (km)"), ("latitude", "Lat"), ("longitude", "Lon"), ("place", "Lugar"),
    ("region", "Región"), ("cell", "Celda"), ("gk", "En secuencia (GK)"), ("status", "Estado"),
    ("net", "Red"), ("id", "ID USGS"),
]


def events_frame(ev: pd.DataFrame) -> pd.DataFrame:
    d = ev.copy()
    d["time_utc"] = d["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    d["gk"] = np.where(d["gk_dependent"], "sí", "no")
    d["depth"] = d["depth"].round(1)
    d["region"] = d["region"].fillna("—")
    return d[[c for c, _ in EVENT_COLUMNS]].sort_values("time_utc", ascending=False)


def events_table(ev: pd.DataFrame, table_id="events-table"):
    d = events_frame(ev)
    return dash_table.DataTable(
        id=table_id, data=d.to_dict("records"),
        columns=[{"name": n, "id": c, "type": "numeric" if c in ("mag", "depth", "latitude", "longitude") else "text"}
                 for c, n in EVENT_COLUMNS],
        sort_action="native", filter_action="native", page_action="native", page_size=20,
        export_format="csv", export_headers="display",
        style_data_conditional=[{"if": {"filter_query": "{mag} >= 7"}, "fontWeight": "600"}],
        **TABLE_STYLE)


def percentile_note():
    return (f"Estado: dentro del rango = P{P_LOW:.0f}–P{P_HIGH:.0f}; fuera de ese rango = inusual respecto al "
            "historial de la región. Es una regla operacional del proyecto, no un umbral físico.")
