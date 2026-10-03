"""Contenido de cada sección del dashboard.

Cada sección sigue el mismo patrón: título → pregunta → gráfico/tabla →
interpretación, y declara qué catálogo usa.
"""
import numpy as np
import pandas as pd
from dash import dcc, html

from config import (ANALYSIS_START, MAX_ZERO_FRACTION, MIN_EVENTS_BVALUE,
                    MIN_EVENTS_CLUSTER, P_HIGH, P_LOW)
from components import charts, maps
from components.kpis import kpi_row, status_banner, status_chip
from components.tables import (events_table, indicator_table, percentile_note,
                               sensitivity_table, simple_table)
from components.theme import GRAPH_CONFIG
from src.statistics import percentile_label
from src.anomaly_detection import CATALOG_LABEL, INDICATOR_HELP, load_cells_summary
from src.regions import PREDEFINED_REGIONS, region_boxes, region_description

DISCLAIMER = ("Esta evaluación identifica desviaciones estadísticas respecto al comportamiento sísmico histórico "
              "de la región. No predice sismos futuros ni estima la probabilidad de que ocurran.")


# --------------------------------------------------------------------------
# Piezas comunes
# --------------------------------------------------------------------------
def graph(fig, gid=None):
    kw = {"id": gid} if gid else {}
    return dcc.Graph(figure=fig, config=GRAPH_CONFIG, **kw)


def catalog_badge(kind):
    cls = "badge badge-complete" if kind == "complete" else "badge badge-declustered"
    return html.Span(CATALOG_LABEL[kind], className=cls)


def section(title, question, body, badges=None, interpretation=None, extra=None):
    if badges:
        seen, uniq = set(), []
        for b in badges:
            key = getattr(b, "children", None)
            if key not in seen:
                seen.add(key)
                uniq.append(b)
        badges = uniq
    head = [html.Div([html.H3(title), html.Div(badges or [], className="badges")], className="section-head"),
            html.P(question, className="question")]
    parts = head + (body if isinstance(body, list) else [body])
    if interpretation:
        items = interpretation if isinstance(interpretation, list) else [interpretation]
        parts.append(html.Div([html.Div("Interpretación", className="eyebrow")] + [html.P(t) for t in items],
                              className="interpretation"))
    if extra:
        parts += extra if isinstance(extra, list) else [extra]
    return html.Section(parts, className="card")


def context_bar(res, sel):
    name = sel.region_key if sel.region_type == "region" else f"Celda {sel.region_key}"
    items = [
        ("Región", name),
        ("Ventana reciente", f"{res['recent_start']:%Y-%m-%d} → {res['t_end']:%Y-%m-%d} ({res['window_days']:.0f} días)"),
        ("Línea base", f"{res['baseline_start']:%Y} → {res['recent_start']:%Y-%m-%d} · {res['n_windows']:,} ventanas "
                       f"(~{res['n_windows_independent']} sin solapamiento)"),
        ("Filtros", f"M ≥ {sel.min_mag:.1f} · prof. {sel.depth_min:.0f}–{sel.depth_max:.0f} km · "
                    f"{'todas las escalas' if sel.mag_scale == 'all' else 'solo familia Mw'}"),
    ]
    return html.Div([html.Div([html.Span(k, className="ctx-k"), html.Span(v, className="ctx-v")], className="ctx-item")
                     for k, v in items], className="context-bar")


def warnings_box(res):
    if not res["warnings"]:
        return None
    return html.Div([html.Div("Avisos sobre esta selección", className="eyebrow")]
                    + [html.P(w) for w in res["warnings"]], className="warning-box")


def status_legend():
    items = [("normal", f"Dentro de P{P_LOW:.0f}–P{P_HIGH:.0f}"), ("above", f"> P{P_HIGH:.0f}"), ("above_ext", "> P99"),
             ("below", f"< P{P_LOW:.0f}"), ("below_ext", "< P1"), ("na", "Sin datos")]
    return html.Div([html.Span("Color = desviación estadística respecto al propio historial (no peligro): ", className="muted")]
                    + [status_chip(c, t) for c, t in items], className="contributors")


def disclaimer():
    return html.Div(DISCLAIMER, className="disclaimer")


# --------------------------------------------------------------------------
# 1. Resumen
# --------------------------------------------------------------------------
def page_overview(sel, res, mf):
    desc = region_description(sel.region_type, sel.region_key)
    why = [html.Li(t) for t in res["explanations"]]
    blocks = [
        context_bar(res, sel),
        html.P(desc, className="region-desc"),
        warnings_box(res),
        html.Div([status_banner(res), kpi_row(res, mf)], className="overview-top"),
        section("Indicadores frente a su historial",
                "¿Qué indicadores de la ventana reciente se apartan de las ventanas históricas comparables?",
                [status_legend(), graph(charts.fig_percentile_strip(res["table"]))],
                badges=[catalog_badge(sel.catalog), catalog_badge("complete")] if sel.catalog != "complete"
                else [catalog_badge("complete")],
                interpretation=[percentile_note(),
                                "El estado general se basa solo en el número de eventos (indicador principal). "
                                "Los demás indicadores se muestran por separado para saber qué contribuye a la "
                                "desviación; no se combinan en un índice."],
                extra=[html.Div([html.Div("¿Por qué?", className="eyebrow"), html.Ul(why, className="why-list")],
                                className="why")]),
        disclaimer(),
    ]
    return [b for b in blocks if b is not None]


# --------------------------------------------------------------------------
# 2. Actividad reciente
# --------------------------------------------------------------------------
def _quantile_rows(hist, rec, col, label, fmt="{:.2f}"):
    rows = []
    for name, s in (("Histórico", hist[col]), ("Reciente", rec[col])):
        s = s.dropna()
        if s.empty:
            rows.append({"Conjunto": name, "n": 0})
            continue
        rows.append({"Conjunto": name, "n": len(s), "Media": fmt.format(s.mean()), "Mediana": fmt.format(s.median()),
                     "P25": fmt.format(s.quantile(.25)), "P75": fmt.format(s.quantile(.75)),
                     "P90": fmt.format(s.quantile(.90)), "Máx.": fmt.format(s.max())})
    return pd.DataFrame(rows).fillna("—")


def page_recent(sel, res):
    rec, hist = res["recent_events"], res["hist_events"]
    n = res["current"]["n_events"]
    m = res["count_model"]
    lo, hi = res["expected_interval_90"]
    if np.isfinite(m.get("mean", np.nan)):
        txt_count = (f"Se registraron {n:.0f} eventos en {res['window_days']:.0f} días. La línea base espera en promedio "
                     f"{m['mean']:.1f} eventos por ventana, con un intervalo central del 90 % de {lo:.0f} a {hi:.0f} "
                     f"(modelo {m['model']}). P(N ≥ {n:.0f}) = {res['p_upper']:.3f}.")
    else:
        txt_count = "No hay línea base suficiente para estimar lo esperado."
    fixed = rec["fixed_depth"].mean() * 100 if len(rec) else np.nan
    depth_note = (f"En la ventana reciente, el {fixed:.0f} % de las profundidades tiene un valor fijo (10, 33 o 35 km); "
                  "esos valores no son profundidades resueltas." if np.isfinite(fixed) else "")
    return [
        context_bar(res, sel),
        warnings_box(res),
        section("Conteo acumulado frente a lo esperado",
                "¿Llegaron más (o menos) eventos de lo esperado a lo largo de la ventana reciente?",
                graph(charts.fig_cumulative_vs_expected(res)), badges=[catalog_badge(sel.catalog)],
                interpretation=[txt_count, "La banda gris es el rango esperado según la línea base, escalado a la "
                                           "fracción de ventana transcurrida."]),
        section("Magnitud y momento de cada evento",
                "¿Cuándo ocurrieron los eventos recientes y de qué tamaño fueron?",
                graph(charts.fig_magnitude_time(res)), badges=[catalog_badge(sel.catalog)]),
        html.Div([
            section("Magnitudes", "¿Las magnitudes recientes son distintas de las habituales?",
                    [graph(charts.fig_ecdf_compare(hist["mag"], rec["mag"], "Magnitud")),
                     simple_table(_quantile_rows(hist, rec, "mag", "Magnitud"))],
                    badges=[catalog_badge(sel.catalog)],
                    interpretation="Curvas desplazadas a la derecha indican magnitudes mayores. La comparación por "
                                   "ventanas está en la sección de anomalías (magnitud máxima)."),
            section("Profundidades", "¿La profundidad de los eventos recientes es diferente de la habitual?",
                    [graph(charts.fig_ecdf_compare(hist["depth"].clip(lower=0.5), rec["depth"].clip(lower=0.5),
                                                   "Profundidad (km, escala log)", log_x=True)),
                     simple_table(_quantile_rows(hist, rec, "depth", "Profundidad", "{:.0f}"))],
                    badges=[catalog_badge(sel.catalog)],
                    interpretation=depth_note or None),
        ], className="two-col"),
        disclaimer(),
    ]


# --------------------------------------------------------------------------
# 3. Mapa
# --------------------------------------------------------------------------
def page_map(sel, res):
    t = res["table"].set_index("clave")
    nn, dep = t.loc["nn_km"], t.loc["dep_frac"]
    boxes = region_boxes(sel.region_type, sel.region_key)
    interp = [
        f"Distancia mediana al vecino más cercano: {nn['actual_txt']} km en la ventana reciente frente a "
        f"{nn['mediana_hist_txt']} km de mediana histórica ({'P' + format(nn['percentil'], '.0f') if np.isfinite(nn['percentil']) else 'no evaluable'}). "
        "Un percentil bajo indica eventos más concentrados de lo habitual.",
        f"Fracción de eventos en secuencias (Gardner-Knopoff): {dep['actual_txt']} "
        f"({'P' + format(dep['percentil'], '.0f') if np.isfinite(dep['percentil']) else 'no evaluable'}).",
        "Codificación: tamaño = magnitud; color = clase de profundidad. Se usan tres clases y no una escala "
        "continua porque el 43 % del catálogo tiene profundidades fijas (10/33/35 km), que en una escala continua "
        "aparecen como bandas artificiales.",
        f"Las métricas espaciales requieren ≥ {MIN_EVENTS_CLUSTER} eventos en la ventana. No se usa DBSCAN: "
        "su resultado depende de epsilon y min_samples, que no tienen un valor físico claro en un catálogo M ≥ 5 "
        "global, y la pregunta (¿más o menos concentrado que de costumbre?) se responde con una métrica de distancia.",
    ]
    return [
        context_bar(res, sel),
        section("Sismicidad reciente sobre la línea base",
                "¿Dónde ocurrió la actividad reciente y está más concentrada que de costumbre?",
                graph(maps.fig_event_map(res, boxes)),
                badges=[catalog_badge(sel.catalog), html.Span("métricas espaciales: catálogo completo", className="badge badge-complete")],
                interpretation=interp),
        disclaimer(),
    ]


# --------------------------------------------------------------------------
# 4. Línea base histórica
# --------------------------------------------------------------------------
def page_baseline(sel, res):
    rows = []
    w = res["windows"]
    for _, r in res["table"].iterrows():
        x = w[r["clave"]].to_numpy(dtype=float)
        if r["clave"] == "energy":
            x = np.where(x > 0, np.log10(np.where(x > 0, x, 1)), np.nan)
        if r["clave"] == "dep_frac":
            x = x * 100
        x = x[np.isfinite(x)]
        if x.size == 0:
            continue
        q = np.percentile(x, [5, 25, 50, 75, 90, 95, 99])
        rows.append({"Indicador": r["indicador"], "Ventanas": x.size, "Media": x.mean(), "Desv. est.": x.std(ddof=1),
                     "P5": q[0], "P25": q[1], "P50": q[2], "P75": q[3], "P90": q[4], "P95": q[5], "P99": q[6]})
    stats_df = pd.DataFrame(rows)
    fmt = {c: "{:.2f}" for c in ["Media", "Desv. est.", "P5", "P25", "P50", "P75", "P90", "P95", "P99"]}
    m = res["count_model"]
    pct = res["table"].iloc[0]["percentil"]
    model_txt = (f"Modelo de conteos ajustado en {m['n_windows']} ventanas sin solapamiento: {m['model']} "
                 f"(media {m['mean']:.2f}, varianza {m['var']:.2f}, índice de dispersión φ = {m['phi']:.2f}). "
                 + ("φ > 1 indica sobredispersión: los eventos llegan agrupados y un modelo de Poisson subestimaría "
                    "la variabilidad." if m.get("phi", 0) > 1 else "")) if np.isfinite(m.get("mean", np.nan)) else ""
    return [
        context_bar(res, sel),
        warnings_box(res),
        section("Distribución histórica del número de eventos",
                f"¿Qué tan común es observar {res['current']['n_events']:.0f} eventos en {res['window_days']:.0f} días en esta región?",
                graph(charts.fig_baseline_distribution(res)), badges=[catalog_badge(sel.catalog)],
                interpretation=[
                    (f"La ventana reciente está en el percentil {pct:.0f}: su conteo supera aproximadamente al "
                     f"{pct:.0f} % de las ventanas históricas de la misma duración. No significa una probabilidad "
                     f"del {pct:.0f} % de que ocurra un sismo." if np.isfinite(pct) else "Sin percentil calculable."),
                    model_txt]),
        section("Conteo móvil a lo largo del historial",
                "¿Cómo varió el número de eventos por ventana desde el inicio de la línea base?",
                graph(charts.fig_rolling_counts(res)), badges=[catalog_badge(sel.catalog)],
                interpretation=[f"Ventanas móviles de {res['window_days']:.0f} días con paso de {res['stride_days']:.0f} días. "
                                "Los picos suelen corresponder a secuencias de réplicas de un sismo grande; con el "
                                "catálogo desclusterizado se atenúan.",
                                "Las ventanas móviles se solapan y no son independientes: sirven para el percentil "
                                "empírico; el modelo de conteos usa solo ventanas sin solapamiento."]),
        section("Estadísticos de la línea base",
                "¿Cuál es el rango habitual de cada indicador?",
                [simple_table(stats_df, {**fmt, "Ventanas": "{:,.0f}"}),
                 html.P("Energía en log10 J; fracción en secuencias en %; profundidad y distancias en km.", className="muted small"),
                 html.Button("Descargar ventanas históricas (CSV)", id="btn-dl-windows", className="btn")],
                badges=[catalog_badge(sel.catalog), catalog_badge("complete")]),
        disclaimer(),
    ]


# --------------------------------------------------------------------------
# 5. Magnitud-frecuencia
# --------------------------------------------------------------------------
def _fmt(v, f="{:.2f}"):
    return f.format(v) if v is not None and np.isfinite(v) else "—"


def page_gr(sel, mf):
    h, r = mf["hist"], mf["rec"]
    tab = pd.DataFrame([
        {"Periodo": f"Histórico ({mf['baseline_start']:%Y} → {mf['rec_start']:%Y-%m-%d})",
         "Mc estimada": _fmt(mf["mc_hist"], "{:.1f}") + f" ({mf['mc_method_hist']})",
         "n (M ≥ Mc)": h["n"], "b": _fmt(h["b"], "{:.3f}"), "σ Shi-Bolt": _fmt(h["sigma"], "{:.3f}"),
         "IC 95 % bootstrap": f"{_fmt(h['ci_low'], '{:.3f}')} – {_fmt(h['ci_high'], '{:.3f}')}",
         "a (anual)": _fmt(h["a_annual"], "{:.2f}")},
        {"Periodo": f"Reciente (últimos {mf['years_rec']} años)",
         "Mc estimada": _fmt(mf["mc_rec"], "{:.1f}") + f" ({mf['mc_method_rec']})",
         "n (M ≥ Mc)": r["n"], "b": _fmt(r["b"], "{:.3f}"), "σ Shi-Bolt": _fmt(r["sigma"], "{:.3f}"),
         "IC 95 % bootstrap": f"{_fmt(r['ci_low'], '{:.3f}')} – {_fmt(r['ci_high'], '{:.3f}')}",
         "a (anual)": _fmt(r["a_annual"], "{:.2f}")},
    ])
    if np.isfinite(mf["delta_b"]):
        lo, hi = mf["delta_ci"]
        sig = mf["p_value"] < 0.05 and (lo > 0 or hi < 0)
        interp_b = [
            f"Δb = b reciente − b histórico = {mf['delta_b']:+.3f} (IC 95 % bootstrap {lo:+.3f} a {hi:+.3f}); "
            f"test de razón de verosimilitudes p = {mf['p_value']:.3f}.",
            ("La distribución magnitud-frecuencia reciente presenta una diferencia estadística respecto al "
             "comportamiento histórico." if sig else
             "No hay evidencia estadística de que la distribución magnitud-frecuencia reciente difiera de la histórica."),
            "Un b-value más bajo o más alto no se interpreta aquí como señal de un sismo futuro: solo describe un "
            "cambio en la proporción de eventos pequeños y grandes.",
        ]
    else:
        interp_b = [f"El b-value reciente no es estimable: se necesitan al menos {MIN_EVENTS_BVALUE} eventos con "
                    f"M ≥ Mc ({mf['mc']:.1f}) en el periodo reciente; hay {r['n']}. Pruebe un periodo más largo, "
                    "una región con más actividad o una magnitud mínima menor."]
    pct = mf["percentile_vs_periods"]
    return [
        section("Relación de Gutenberg-Richter",
                "¿Cambió la proporción entre sismos pequeños y grandes?",
                [graph(charts.fig_gutenberg_richter(mf)), simple_table(tab)],
                badges=[catalog_badge(sel.catalog)],
                interpretation=["El b-value se estima utilizando únicamente eventos por encima de la magnitud de "
                                "completitud para reducir el sesgo producido por eventos faltantes de baja magnitud. "
                                f"Para comparar ambos periodos se usa la misma Mc = {mf['mc']:.1f} "
                                "(la mayor de las dos estimadas)."] + interp_b,
                extra=[html.Button("Descargar tablas magnitud-frecuencia (CSV)", id="btn-dl-gr", className="btn")]),
        html.Div([
            section("b-value por periodos",
                    f"¿El b-value reciente es inusual frente a otros periodos de {mf['years_rec']} años?",
                    graph(charts.fig_b_series(mf)), badges=[catalog_badge(sel.catalog)],
                    interpretation=[
                        (f"El b reciente está en el percentil {pct:.0f} de los periodos históricos con b estimable."
                         if np.isfinite(pct) else "No hay suficientes periodos para un percentil."),
                        "Precaución: la composición de escalas de magnitud cambió con el tiempo (ms y mwc antes de "
                        "2010; mww y mb después). Parte de la variación de b entre décadas puede deberse al catálogo "
                        "y no a la sismicidad. Compare con el filtro 'solo familia Mw'."]),
            section("Diagnóstico de Mc",
                    "¿Desde qué magnitud el catálogo es suficientemente completo?",
                    graph(charts.fig_mbs(mf)), badges=[catalog_badge(sel.catalog)],
                    interpretation=[
                        "Método de estabilidad del b-value (MBS): Mc es el primer valor en que b deja de cambiar "
                        "más que su incertidumbre. La búsqueda empieza en 5.0 porque el catálogo está truncado ahí: "
                        "la máxima curvatura (MAXC) devolvería siempre 5.0 y no sirve."]),
        ], className="two-col"),
        disclaimer(),
    ]


# --------------------------------------------------------------------------
# 6. Anomalías y sensibilidad
# --------------------------------------------------------------------------
def page_anomalies(sel, res, sens):
    n_out = int(sens["estado_codigo"].isin(["above", "above_ext"]).sum()) if len(sens) else 0
    n_below = int(sens["estado_codigo"].isin(["below", "below_ext"]).sum()) if len(sens) else 0
    n_tot = len(sens)
    sens_txt = (f"{n_out} de {n_tot} combinaciones ventana × magnitud mínima quedan por encima del P{P_HIGH:.0f} y "
                f"{n_below} por debajo del P{P_LOW:.0f}. Si la conclusión cambia al mover la ventana o la magnitud "
                "mínima, la desviación depende de esa decisión y debe reportarse con cautela.")
    help_items = [html.Li([html.Strong(r["indicador"] + ": "), INDICATOR_HELP[r["clave"]]]) for _, r in res["table"].iterrows()]
    return [
        context_bar(res, sel),
        warnings_box(res),
        section("Anomalías por indicador",
                "¿Qué tan extrema es la actividad reciente en cada indicador respecto a su propio historial?",
                [indicator_table(res["table"]),
                 html.Button("Descargar resultados de anomalía (CSV)", id="btn-dl-anomaly", className="btn")],
                badges=[catalog_badge(sel.catalog), html.Span("agrupamiento: catálogo completo", className="badge badge-complete")],
                interpretation=[percentile_note(),
                                "Para el número de eventos se reportan además P(N ≥ actual) y P(N ≤ actual) bajo el "
                                "modelo de conteos ajustado a ventanas sin solapamiento. Son probabilidades del "
                                "conteo observado bajo el comportamiento histórico, no probabilidades de un sismo."],
                extra=[html.Details([html.Summary("Qué mide cada indicador"), html.Ul(help_items)], className="details")]),
        section("Análisis de sensibilidad",
                "¿La conclusión depende de la ventana o de la magnitud mínima elegidas?",
                sensitivity_table(sens), badges=[catalog_badge(sel.catalog)],
                interpretation=[sens_txt,
                                "Cada celda: percentil del número de eventos y conteo actual vs. mediana histórica. "
                                "Celdas con borde punteado: más del "
                                f"{MAX_ZERO_FRACTION * 100:.0f} % de las ventanas históricas no tienen eventos "
                                "(información limitada). M ≥ 2, 3 o 4 no se pueden evaluar: el catálogo empieza en 5.0."],
                extra=[html.Button("Descargar sensibilidad (CSV)", id="btn-dl-sens", className="btn")]),
        section("¿Por qué no hay un índice compuesto?",
                "Decisión metodológica",
                html.Div([
                    html.P("El número de eventos, la magnitud máxima y la energía no son indicadores independientes: "
                           "la energía depende casi por completo del evento mayor y suele crecer con el conteo. Una "
                           "suma ponderada A = Σ wᵢ zᵢ contaría dos veces la misma señal, y no hay una base física "
                           "para elegir los pesos."),
                    html.P("Además, las distribuciones son asimétricas y discretas (conteos con muchos ceros), así "
                           "que los z-scores no tienen la interpretación habitual. Por eso el dashboard presenta las "
                           "anomalías por indicador y un estado general basado únicamente en el indicador principal "
                           "(tasa de eventos)."),
                ])),
        disclaimer(),
    ]


# --------------------------------------------------------------------------
# 7. Comparación regional
# --------------------------------------------------------------------------
def page_regional(sel, reg_df, cell_df):
    order = list(PREDEFINED_REGIONS.keys())
    # orden geográfico: latitud media descendente (no por percentil)
    lat_mid = {k: np.mean([(b[0] + b[1]) / 2 for b in v[0]]) for k, v in PREDEFINED_REGIONS.items()}
    order = sorted(order, key=lambda k: -lat_mid[k])
    n_sig = int((reg_df["q_fdr"] < 0.05).sum()) if len(reg_df) else 0
    tab = reg_df.copy()
    tab = tab.set_index("unidad").reindex([o for o in order if o in set(tab["unidad"])]).reset_index()
    tab_view = pd.DataFrame({
        "Región": tab["unidad"], "Eventos actuales": tab["n_actual"].map("{:.0f}".format),
        "Mediana histórica": tab["mediana_hist"].map("{:.1f}".format),
        "Percentil propio": tab["percentil"].map(percentile_label),
        "Estado": tab["estado"], "P(N ≥ actual)": tab["p_superior"].map("{:.3f}".format),
        "q FDR (bilateral)": tab["q_fdr"].map("{:.3f}".format),
        "Información": np.where(tab["informacion_limitada"], "limitada", "suficiente"),
    })
    n_cells_out = int(cell_df["estado_codigo"].isin(["above", "above_ext", "below", "below_ext"]).sum()) if len(cell_df) else 0
    return [
        section("Cada región frente a su propio historial",
                f"¿Qué regiones tienen actividad reciente ({sel.window_days} días, M ≥ {sel.min_mag:.1f}) fuera de su rango habitual?",
                [status_legend(), graph(charts.fig_regional_dots(reg_df, order))], badges=[catalog_badge(sel.catalog)],
                interpretation=[
                    "Las regiones están ordenadas de norte a sur, no por su valor. Cada punto compara la región con "
                    "su propio historial; no compara regiones entre sí ni mide peligrosidad o riesgo.",
                    f"Con corrección por comparaciones múltiples (Benjamini-Hochberg), {n_sig} de {len(reg_df)} regiones "
                    "tienen q < 0.05. Un percentil alto con q grande indica una desviación que el modelo de conteos "
                    "(sobredispersado) todavía considera compatible con la variabilidad histórica.",
                    "Círculos vacíos: información limitada (más del 10 % de las ventanas históricas sin eventos)."],
                extra=[simple_table(tab_view),
                       html.Button("Descargar comparación regional (CSV)", id="btn-dl-regional", className="btn")]),
        section("Celdas de 5° × 5°",
                "¿Hay otras zonas, fuera de las regiones predefinidas, con actividad fuera de su rango habitual?",
                [status_legend(), graph(maps.fig_cells_map(cell_df, load_cells_summary()))], badges=[catalog_badge(sel.catalog)],
                interpretation=[f"{n_cells_out} de {len(cell_df)} celdas (con ≥ 60 eventos desde 1973) están fuera de "
                                f"su rango P{P_LOW:.0f}–P{P_HIGH:.0f}. Con cientos de celdas, ~10 % quedarían fuera "
                                "por azar: use la columna q FDR antes de concluir.",
                                "Una celda aislada suele ser una secuencia local de réplicas; varias celdas contiguas "
                                "indican un cambio a escala de segmento."]),
        disclaimer(),
    ]


# --------------------------------------------------------------------------
# 8. Eventos
# --------------------------------------------------------------------------
def page_events(sel, res):
    ev = res["recent_events_complete"]
    return [
        context_bar(res, sel),
        section("Eventos de la ventana reciente",
                "¿Qué eventos componen la actividad reciente?",
                [events_table(ev),
                 html.Div([html.Button("Descargar todos los eventos filtrados 1973–2026 (CSV)", id="btn-dl-events",
                                       className="btn")], className="btn-row")],
                badges=[catalog_badge("complete")],
                interpretation=["Se muestra el catálogo completo con la columna 'En secuencia (GK)' para que se vea "
                                "qué eventos retira el declustering. La tabla permite ordenar, filtrar (p. ej. "
                                "'>= 6' en Magnitud) y exportar la vista (botón Export)."]),
    ]


# --------------------------------------------------------------------------
# 9. Datos y método
# --------------------------------------------------------------------------
FILTER_MAP = pd.DataFrame([
    {"Componente": "Estado, cifras clave, percentiles, anomalías", "Región": "sí", "Ventana": "sí", "Mag. mín.": "sí",
     "Profundidad": "sí", "Escala": "sí", "Catálogo": "sí (agrupamiento: siempre completo)", "Inicio línea base": "sí"},
    {"Componente": "Actividad reciente", "Región": "sí", "Ventana": "sí", "Mag. mín.": "sí", "Profundidad": "sí",
     "Escala": "sí", "Catálogo": "sí", "Inicio línea base": "sí"},
    {"Componente": "Mapa", "Región": "sí", "Ventana": "sí", "Mag. mín.": "sí", "Profundidad": "sí", "Escala": "sí",
     "Catálogo": "sí (métricas espaciales: completo)", "Inicio línea base": "sí"},
    {"Componente": "Gutenberg-Richter / b-value", "Región": "sí", "Ventana": "no (usa periodo de b)",
     "Mag. mín.": "como piso de Mc", "Profundidad": "sí", "Escala": "sí", "Catálogo": "sí", "Inicio línea base": "sí"},
    {"Componente": "Sensibilidad", "Región": "sí", "Ventana": "no (recorre 30–730 d)", "Mag. mín.": "no (recorre 5.0–6.0)",
     "Profundidad": "sí", "Escala": "sí", "Catálogo": "sí", "Inicio línea base": "sí"},
    {"Componente": "Comparación regional", "Región": "no (todas)", "Ventana": "sí", "Mag. mín.": "sí",
     "Profundidad": "sí", "Escala": "sí", "Catálogo": "sí", "Inicio línea base": "sí"},
    {"Componente": "Tabla de eventos", "Región": "sí", "Ventana": "sí", "Mag. mín.": "sí", "Profundidad": "sí",
     "Escala": "sí", "Catálogo": "no (completo con columna GK)", "Inicio línea base": "no"},
])

METHODOLOGY_MD = r"""
#### Fuente de datos
Archivo `Significant_Earthquakes.csv`, con las 22 columnas del formato CSV del catálogo ComCat del USGS. El archivo
no documenta la consulta exacta de descarga; contiene solo eventos con M ≥ 5.0.

#### Catálogo de trabajo
Desde el 1973-01-01 (salto de completitud con el inicio del catálogo PDE), solo `type = earthquake`, un registro por
`id` (la revisión con `updated` más reciente) y magnitud binneada a ΔM = 0.1. La profundidad faltante no se imputa:
no afecta los conteos y las métricas de profundidad usan solo valores observados.

#### Ventana reciente y línea base
La ventana reciente es $(T_{fin} - W,\ T_{fin}]$, donde $T_{fin}$ es la fecha del último evento del catálogo, no la
fecha actual. La línea base está formada por todas las ventanas de la misma duración $W$, móviles con paso
$\max(1, \lfloor W/10 \rfloor)$ días, desde el año de inicio elegido hasta el comienzo de la ventana reciente. Nunca se
comparan 30 días contra todo el historial: siempre ventanas de igual duración. La línea base se recalcula en cada
selección; si se añaden datos nuevos al CSV, basta con volver a ejecutar `scripts/build_catalog.py`.

#### Tasa de eventos
$\text{tasa} = N / W$ (eventos por día, o por año si es baja). Para cada ventana histórica $k$: $N_k$ = número de eventos
en $(t_k - W,\ t_k]$.

#### Percentil empírico
$P = 100 \cdot \dfrac{\#\{x_k < v\} + 0.5\,\#\{x_k = v\}}{n}$. Con conteos hay muchos empates; el rango medio evita
sobreestimar el percentil. **El percentil indica la posición respecto a ventanas históricas comparables, no la
probabilidad de un sismo.**

#### Modelo de conteos
En ventanas sin solapamiento se ajusta por momentos una Binomial Negativa si $s^2 > \bar{x}$
($r = \bar{x}^2/(s^2 - \bar{x})$, $p = r/(r+\bar{x})$) o una Poisson si no. Se reportan $P(N \ge n)$ y $P(N \le n)$.
No se usan z-scores sobre conteos: el EDA mostró que no son normales (exceso de ceros, sobredispersión con
φ mediano ≈ 2 por región).

#### Energía
$\log_{10} E\,[\mathrm{J}] = 1.5\,M + 4.8$ (Gutenberg & Richter, 1956). Es una aproximación; se suma la energía
(no las magnitudes) y se muestra en $\log_{10}$ J.

#### Magnitud de completitud (Mc)
Estabilidad del b-value (MBS; Cao & Gao, 2002; Woessner & Wiemer, 2005): para cada Mc candidato desde 5.0 se calcula
$b(M_c)$ y el promedio $\bar{b}$ entre $M_c$ y $M_c + 0.5$; Mc es el primer valor con $|\bar{b} - b(M_c)| \le \sigma_b$.
Si no converge, se usa 5.0 y se indica. Para comparar dos periodos se usa la mayor de las dos Mc.

#### Gutenberg-Richter y b-value
$\log_{10} N(\ge M) = a - bM$. Estimador de máxima verosimilitud de Aki-Utsu con corrección por binning:
$b = \dfrac{\log_{10} e}{\bar{M} - (M_c - \Delta M/2)}$. Incertidumbre de Shi & Bolt (1982):
$\sigma_b = 2.3\,b^2\sqrt{\sum (M_i - \bar{M})^2 / (n(n-1))}$, más un intervalo bootstrap del 95 %. Se exige
$n \ge 50$. La diferencia entre periodos se evalúa con una razón de verosimilitudes de dos exponenciales
($LR \sim \chi^2_1$), equivalente al test de Utsu (1992).

#### Agrupamiento temporal
(1) Fracción de eventos que el declustering de Gardner-Knopoff asigna a secuencias y (2) coeficiente de variación de
los tiempos entre eventos, $CV = \sigma_{\Delta t}/\mu_{\Delta t}$ ($CV \approx 1$ para Poisson). Ambas con el catálogo
completo.

#### Agrupamiento espacial
Mediana de la distancia (gran círculo) de cada evento a su vecino más cercano, con el catálogo completo. Se compara
contra la misma métrica en las ventanas históricas.

#### Declustering
Gardner & Knopoff (1974), ventanas $L(M) = 10^{0.1238M + 0.983}$ km y $T(M) = 10^{0.5409M - 0.547}$ días
($M < 6.5$) o $10^{0.032M + 2.7389}$ días ($M \ge 6.5$), aplicadas antes y después de cada evento principal. Está
**desactivado por defecto**. Con el catálogo desclusterizado se analizan la tasa, la magnitud, la energía, la
profundidad y el b-value de la actividad independiente; el agrupamiento siempre usa el catálogo completo.

#### Definición operacional de anomalía
Un indicador se considera **inusual** cuando su valor actual está por encima del P95 o por debajo del P5 de las
ventanas históricas comparables, y **muy inusual** fuera de P1–P99. Es una definición del proyecto, no una ley
universal. El estado general usa solo la tasa de eventos.

#### Índice compuesto
No se implementa (ver la sección de anomalías): los indicadores están correlacionados y no hay base para los pesos.

#### Machine learning
No se usa. La pregunta se responde con estadística sobre ventanas comparables; Isolation Forest o DBSCAN
añadirían parámetros sin interpretación física clara y no mejorarían la respuesta.
"""

LIMITATIONS_MD = """
- **Una anomalía estadística no implica causalidad ni permite predecir la ocurrencia de un terremoto.**
- **Completitud:** el catálogo solo tiene M ≥ 5.0. No hay información sobre la sismicidad menor, que es donde suelen
  verse los cambios de tasa a corto plazo. Antes de 1973 el catálogo es incompleto y se excluye.
- **Cambios en la red y en las escalas de magnitud:** la composición de `magType` cambió (ms y mwc antes de 2010; mww
  y mb después). El dataset no permite homogeneizar magnitudes; los conteos cerca de M 5.0 y el b-value pueden
  reflejar cambios de procedimiento. El filtro "solo familia Mw" permite comprobarlo, a costa de perder eventos.
- **Incertidumbre de magnitud y localización:** `magError`, `horizontalError` y `depthError` faltan en 58–71 % de
  los registros y no se usan. El 43 % de las profundidades son valores fijos (10, 33, 35 km).
- **Tamaño de muestra:** en ventanas cortas (7–30 días) la mayoría de las regiones tienen pocos eventos y el
  percentil es poco informativo (el dashboard lo avisa). El b-value necesita ≥ 50 eventos sobre Mc.
- **Duración del catálogo:** ~53 años de línea base equivalen a pocas decenas de ventanas independientes de 1–2 años;
  los percentiles extremos (P99) de ventanas largas se estiman con pocos datos.
- **Dependencia entre ventanas:** las ventanas móviles se solapan; el modelo de conteos usa ventanas sin solapamiento,
  pero las secuencias de réplicas siguen introduciendo dependencia temporal (autocorrelación positiva en el EDA).
- **Declustering:** Gardner-Knopoff fue calibrado en California. En cinturones de alta tasa con M ≥ 5 marca como
  dependientes a eventos que solo coinciden por cercanía (≈ 58 % del catálogo de trabajo queda marcado). Por eso es
  opcional y las comparaciones se hacen siempre contra el historial de la misma región, donde ese sesgo es similar.
- **Sensibilidad a la región y a la ventana:** las cajas regionales son una decisión de análisis; moverlas cambia los
  conteos. La sección de sensibilidad muestra cuánto depende la conclusión de la ventana y de la magnitud mínima.
- **Fecha final:** el catálogo termina el 2026-08-22; "reciente" se refiere a ese momento, no a hoy.
- **Comparaciones múltiples:** al revisar muchas regiones o celdas, algunas saldrán fuera de P5–P95 por azar; use los
  q-valores FDR.
"""


def page_data_method(report, regions):
    a = report["raw_audit"]
    steps = pd.DataFrame(report["cleaning_steps"]).rename(columns={"paso": "Paso", "regla": "Regla",
                                                                   "filas": "Filas", "eliminadas": "Eliminadas"})
    miss = pd.DataFrame([{"Columna": k, "% faltante (archivo original)": v} for k, v in a["missing_pct"].items() if v > 0])
    era = pd.DataFrame(report["magtype_by_era_pct"]).T.fillna(0)
    era.insert(0, "Periodo", era.index)
    reg = regions.rename(columns={"region": "Región", "n_eventos": "Eventos desde 1973", "eventos_por_año": "Eventos/año",
                                  "esperados_90d": "Esperados por 90 d", "fraccion_dependiente_GK": "Fracción en secuencias (GK)",
                                  "contexto": "Contexto tectónico"})
    reg["Habilitada"] = np.where(regions["habilitada"], "sí", "no (pocos eventos)")
    reg = reg[["Región", "Eventos desde 1973", "Eventos/año", "Esperados por 90 d", "Fracción en secuencias (GK)",
               "Habilitada", "Contexto tectónico"]]
    summary = pd.DataFrame([
        ["Registros en el archivo", f"{a['n_rows']:,}"],
        ["Periodo del archivo", f"{a['time_min'][:10]} → {a['time_max'][:16]} UTC"],
        ["Formato de fecha", f"{a['time_format']}; fechas inválidas: {a['invalid_times']}; ordenado en el archivo: "
                             f"{'sí' if a['time_sorted_in_file'] else 'no'}"],
        ["Ids repetidos", f"{a['duplicated_ids']:,} filas (revisiones del mismo evento)"],
        ["Sismos únicos (todos los años)", f"{report['n_clean_all_years']:,}"],
        ["Catálogo de trabajo (desde 1973)", f"{report['n_working']:,} eventos"],
        ["Rango de magnitud", f"{report['working_mag_range'][0]:.2f} – {report['working_mag_range'][1]:.2f}"],
        ["Escalas de magnitud", f"{len(a['mag_types'])} tipos; familia Mw = {report['working_mw_family_pct']:.1f} % del catálogo de trabajo"],
        ["Magnitudes con 2 decimales", f"{report['working_two_decimal_mag_pct']:.1f} % (se binnean a 0.1)"],
        ["Rango de profundidad", f"{report['working_depth_range'][0]:.1f} – {report['working_depth_range'][1]:.1f} km "
                                 f"({a['depth_negative']} negativas en el archivo: sobre el nivel de referencia)"],
        ["Profundidades fijas (10/33/35 km)", f"{report['working_fixed_depth_pct']:.1f} %"],
        ["Cobertura espacial", f"lat {a['lat_range'][0]:.1f} a {a['lat_range'][1]:.1f}, lon {a['lon_range'][0]:.1f} a {a['lon_range'][1]:.1f}"],
        ["Regiones predefinidas habilitadas", f"{report['regions_enabled']} de {report['regions_total']} "
                                              f"({report['pct_working_in_enabled_regions']:.1f} % de los eventos)"],
        ["Celdas 5°×5° disponibles", f"{report['n_cells_available']} ({report['pct_working_in_cells']:.1f} % de los eventos)"],
        ["Eventos en secuencias (GK)", f"{report['declustering']['pct_dependent']:.1f} %"],
    ], columns=["Ítem", "Valor"])
    return [
        section("Calidad del catálogo", "¿Qué contiene el dataset y qué se descartó?",
                [simple_table(summary), html.H4("Pasos de limpieza"), simple_table(steps),
                 html.H4("Valores faltantes en el archivo original"),
                 simple_table(miss, {"% faltante (archivo original)": "{:.2f}"})]),
        section("Completitud temporal", "¿Desde cuándo el catálogo es comparable?",
                graph(charts.fig_annual_counts(report["annual_counts"], int(ANALYSIS_START[:4]))),
                interpretation="El número anual de eventos M ≥ 5 se duplica en 1973. Antes de ese año el catálogo no "
                               "detecta todos los M ≥ 5 y compararlo con años recientes inflaría cualquier anomalía. "
                               "(El EDA usaba 1968 como inicio; aquí se corrige a 1973.)"),
        section("Escalas de magnitud por periodo", "¿Son comparables las magnitudes a lo largo del tiempo?",
                simple_table(era, {c: "{:.1f}" for c in era.columns if c != "Periodo"}),
                interpretation="Porcentaje de eventos por escala en cada periodo. El cambio de ms/mwc a mww/mb es un "
                               "cambio de procedimiento del catálogo, no de la sismicidad."),
        section("Regiones predefinidas", "¿Qué regiones tienen información suficiente?",
                simple_table(reg, {"Eventos/año": "{:.1f}", "Esperados por 90 d": "{:.2f}",
                                   "Fracción en secuencias (GK)": "{:.2f}"}),
                interpretation="Cajas lat/lon trazadas sobre cinturones sísmicos continuos visibles en el catálogo, sin "
                               "superposición. Se habilitan las que tienen al menos 2 eventos esperados por ventana de "
                               "90 días. Son una decisión de análisis, no fronteras oficiales."),
        section("Qué filtros afectan a cada componente", "Trazabilidad de la interactividad",
                simple_table(FILTER_MAP)),
        section("Metodología", "¿Cómo se calcula cada resultado?",
                dcc.Markdown(METHODOLOGY_MD, mathjax=True, className="markdown")),
        section("Limitaciones", "¿Qué no puede concluirse con estos datos?",
                dcc.Markdown(LIMITATIONS_MD, className="markdown")),
        disclaimer(),
    ]
