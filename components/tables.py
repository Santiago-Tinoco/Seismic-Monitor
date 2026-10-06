"""Estructura general: encabezado, panel de control y pestañas."""
from dash import dcc, html

from config import (
    B_PERIOD_OPTIONS,
    BASELINE_START_OPTIONS,
    DEFAULT_B_PERIOD,
    DEFAULT_WINDOW,
    WINDOW_OPTIONS,
)
from components.help_texts import GLOSSARY


TABS = [
    ("resumen", "Resumen"),
    ("reciente", "Actividad reciente"),
    ("mapa", "Mapa"),
    ("linea_base", "Línea base"),
    ("gr", "Magnitud–frecuencia"),
    ("anomalias", "Anomalías y sensibilidad"),
    ("regional", "Comparación regional"),
    ("eventos", "Eventos"),
    ("datos", "Datos y método"),
]


def header(catalog_end):
    return html.Header(
        html.Div([
            html.Span(
                "Monitor de actividad sismica",
                className="brand"
            ),
        ], className="header-inner"),
        className="app-header"
    )

def control(label, component, help_text=None):
    lab = html.Label(label, title=help_text) if help_text else html.Label(label)
    return html.Div([lab, component], className="control")


def sidebar(region_options, default_region):
    return html.Aside(
        [
            html.Div("Región", className="side-title"),

            control(
                "Unidad espacial",
                dcc.RadioItems(
                    id="in-region-type",
                    value="region",
                    className="radio-stack",
                    options=[
                        {
                            "label": "Regiones predefinidas",
                            "value": "region",
                        },
                        {
                            "label": "Celdas de malla 5° × 5°",
                            "value": "cell",
                        },
                    ],
                ),
            ),

            control(
                "Región",
                dcc.Dropdown(
                    id="in-region",
                    options=region_options,
                    value=default_region,
                    clearable=False,
                    searchable=True,
                ),
            ),

            html.Div("Periodo", className="side-title"),

            control(
                "Ventana reciente (días)",
                dcc.RadioItems(
                    id="in-window",
                    value=DEFAULT_WINDOW,
                    className="pills",
                    options=[
                        {"label": str(w), "value": w}
                        for w in WINDOW_OPTIONS
                    ],
                ),
                "Duración de la ventana reciente. Se compara con todas las ventanas históricas de la misma duración.",
            ),

            control(
                "Inicio de la línea base",
                dcc.Dropdown(
                    id="in-baseline",
                    value=BASELINE_START_OPTIONS[0],
                    clearable=False,
                    options=[
                        {"label": str(y), "value": y}
                        for y in BASELINE_START_OPTIONS
                    ],
                ),
                GLOSSARY["linea_base"],
            ),

            html.Div("Eventos", className="side-title"),

            control(
                "Magnitud mínima",
                dcc.Dropdown(
                    id="in-minmag",
                    value=5.0,
                    clearable=False,
                    options=[
                        {
                            "label": f"M ≥ {m:.1f}",
                            "value": m,
                        }
                        for m in (5.0, 5.5, 6.0, 6.5, 7.0)
                    ],
                ),
                "El catálogo solo contiene M ≥ 5.0.",
            ),

            control(
                "Profundidad (km)",
                dcc.RangeSlider(
                    id="in-depth",
                    min=0,
                    max=700,
                    step=10,
                    value=[0, 700],
                    allowCross=False,
                    marks={
                        0: "0",
                        70: "70",
                        300: "300",
                        700: "700",
                    },
                    tooltip={"placement": "bottom"},
                ),
            ),

            control(
                "Escalas de magnitud",
                dcc.RadioItems(
                    id="in-scale",
                    value="all",
                    className="radio-stack",
                    options=[
                        {
                            "label": "Todas (magnitud preferida del USGS)",
                            "value": "all",
                        },
                        {
                            "label": "Solo familia Mw",
                            "value": "mw",
                        },
                    ],
                ),
                "La familia Mw incluye mw, mww, mwc, mwb, mwr y mwp. "
                "Excluir mb/ms reduce la mezcla de escalas pero cambia los conteos.",
            ),

            html.Div("Catálogo", className="side-title"),

            dcc.RadioItems(
                id="in-catalog",
                value="complete",
                className="radio-stack",
                options=[
                    {
                        "label": "Catálogo completo",
                        "value": "complete",
                    },
                    {
                        "label": "Catálogo desclusterizado (Gardner-Knopoff)",
                        "value": "declustered",
                    },
                ],
            ),

            html.P(
                "Afecta a tasa, magnitud, energía, profundidad y b-value. "
                "El agrupamiento temporal y espacial usa siempre el catálogo completo.",
                className="side-note",
                title=GLOSSARY["gk"],
            ),

            html.Div("b-value", className="side-title"),

            control(
                "Periodo reciente para b (años)",
                dcc.RadioItems(
                    id="in-bperiod",
                    value=DEFAULT_B_PERIOD,
                    className="pills",
                    options=[
                        {"label": str(y), "value": y}
                        for y in B_PERIOD_OPTIONS
                    ],
                ),
                "El b-value necesita ≥ 50 eventos sobre Mc, por eso usa un periodo propio más largo que la ventana.",
            ),
        ],
        className="sidebar",
    )


def main_layout(catalog_end, region_options, default_region):
    return html.Div(
        [
            header(catalog_end),

            html.Div(
                [
                    sidebar(region_options, default_region),

                    html.Main(
                        [
                            dcc.Tabs(
                                id="tabs",
                                value="resumen",
                                className="tabs",
                                children=[
                                    dcc.Tab(
                                        label=lab,
                                        value=val,
                                        className="tab",
                                        selected_className="tab--selected",
                                    )
                                    for val, lab in TABS
                                ],
                            ),

                            dcc.Loading(
                                html.Div(
                                    id="tab-content",
                                    className="page-content",
                                ),
                                type="dot",
                                color="#C75B12",
                            ),
                        ],
                        className="main",
                    ),
                ],
                className="body",
            ),

            html.Footer(
                "Proyecto académico de análisis de datos sísmicos. "
                "Esta herramienta describe desviaciones estadísticas; "
                "no predice terremotos.",
                className="footer",
            ),

            dcc.Download(id="dl-windows"),
            dcc.Download(id="dl-gr"),
            dcc.Download(id="dl-anomaly"),
            dcc.Download(id="dl-sens"),
            dcc.Download(id="dl-regional"),
            dcc.Download(id="dl-events"),
        ],
        className="app",
    )
