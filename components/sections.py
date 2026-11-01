"""Contenido de las 11 secciones del Proyecto EDA (versión Dash)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from dash import dcc, html

from components import ts_charts as tc
from components.maps import GEO_STYLE
from components.pages import graph, section
from components.tables import simple_table
from src import analysis_cache as ac
from src import timeseries as ts
from src.forecasting import MODELS

SHARED = Path(__file__).resolve().parents[1] / "shared"
TS_LABELS = ts.VARIABLES
FREQ_LABELS = ts.PARAMS["freq_labels"]
DISCLAIMER = ("Pronosticar la frecuencia estadística de eventos no equivale a predecir cuándo, dónde o con qué "
              "magnitud ocurrirá un terremoto.")


def md(name):
    return dcc.Markdown((SHARED / "content" / name).read_text(encoding="utf-8"), mathjax=True, className="markdown")


def fmt(v, f="{:,.2f}"):
    return f.format(v) if v is not None and np.isfinite(v) else "—"


def page_title(title, question):
    return html.Div([html.H2(title), html.P(question, className="question")], className="page-title")


def filter_note(f):
    reg = f["region"]
    return html.Div(f"Filtros aplicados · Región: {reg} · {f['start']} → {f['end']} · M ≥ {f['min_mag']:.1f} · "
                    f"Profundidad {f['depth_min']:.0f}–{f['depth_max']:.0f} km · "
                    f"{'Catálogo completo' if f['catalog'] == 'complete' else 'Catálogo desclusterizado (GK)'}",
                    className="filter-note")


def kpi(label, value, sub=""):
    return html.Div([html.Div(label, className="kpi-label"), html.Div(value, className="kpi-value"),
                     html.Div(sub, className="kpi-sub")], className="kpi")


# --------------------------------------------------------------------------
# 1. Inicio
# --------------------------------------------------------------------------
NAV_CARDS = [("/series", "bi-graph-up", "Análisis de series de tiempo",
              "Conteos, magnitud, profundidad y energía por día, semana, mes y año; ACF, estacionariedad y anomalías."),
             ("/eda-univariado", "bi-bar-chart", "EDA univariado", "Distribuciones, atípicos y estadística descriptiva."),
             ("/modelos", "bi-diagram-3", "Modelos", "Comparación de modelos de conteo mensual con validación temporal."),
             ("/predecir", "bi-calendar2-week", "Predecir", "Pronóstico del número mensual de eventos con intervalos.")]


def page_inicio():
    k = ac.global_kpis()
    return [
        html.Div([
            html.Div("PROYECTO EDA", className="eyebrow"),
            html.H1("Análisis de series de tiempo de terremotos"),
            html.P("Análisis Exploratorio de Datos Sísmicos · Evolución temporal de la actividad sísmica", className="lead"),
            html.P("Objetivo general: analizar el comportamiento temporal de la actividad sísmica registrada en el "
                   "catálogo USGS M ≥ 5 (1973–2026) mediante análisis exploratorio, pruebas de series de tiempo y "
                   "modelos de pronóstico de conteos, a escala global y regional."),
            html.P("El análisis convierte el catálogo de eventos en series de tiempo, estudia su tendencia, "
                   "estacionalidad, autocorrelación y agrupamiento, detecta periodos anómalos y compara modelos de "
                   "pronóstico del número mensual de eventos contra modelos de referencia."),
        ], className="hero"),
        html.Div([
            kpi("Sismos analizados", f"{k['n']:,}", f"M ≥ 5 · {k['years']:.1f} años (1973–2026)"),
            kpi("Promedio mensual", f"{k['per_month']:.0f}", f"eventos/mes en {k['months']} meses completos"),
            kpi("Magnitud máxima", f"M {k['max_mag']:.1f}", f"{k['max_date']:%Y-%m-%d} · {k['max_place']}"),
            kpi("Profundidad mediana", f"{k['depth_median']:.0f} km", "todos los eventos"),
            kpi("Energía total estimada", f"10^{k['energy_log10']:.1f} J", "suma de 10^(1.5M+4.8)"),
            kpi("Eventos en secuencias", f"{k['dependent_pct']:.0f} %", "réplicas/premonitores (Gardner-Knopoff)"),
        ], className="kpi-grid"),
        html.Div([dcc.Link(html.Div([html.I(className=f"bi {icon} card-icon"), html.H4(t), html.P(d)], className="nav-card"),
                           href=href) for href, icon, t, d in NAV_CARDS], className="nav-cards"),
        html.P(DISCLAIMER, className="disclaimer"),
    ]


# --------------------------------------------------------------------------
# 2–4. Textos
# --------------------------------------------------------------------------
def page_text(title, question, file, extra=None):
    body = [page_title(title, question), html.Div(md(file), className="card")]
    if extra:
        body += extra
    return body


def dataset_table(report):
    a = report["raw_audit"]
    rows = [["Registros en el archivo", f"{a['n_rows']:,}"],
            ["Periodo del archivo", f"{a['time_min'][:10]} → {a['time_max'][:16]} UTC"],
            ["Columnas", ", ".join(a["columns"])],
            ["Sismos únicos analizados (desde 1973)", f"{report['n_working']:,}"],
            ["Rango de magnitud", f"{report['working_mag_range'][0]:.1f} – {report['working_mag_range'][1]:.1f}"],
            ["Profundidad", f"{report['working_depth_range'][0]:.0f} – {report['working_depth_range'][1]:.0f} km; "
                            f"{report['working_fixed_depth_pct']:.0f} % con valores fijos (10/33/35 km)"],
            ["Escalas de magnitud", f"{len(a['mag_types'])} tipos; familia Mw = {report['working_mw_family_pct']:.0f} %"],
            ["Ids repetidos (revisiones)", f"{a['duplicated_ids']:,} filas"]]
    steps = pd.DataFrame(report["cleaning_steps"])[["paso", "regla", "filas", "eliminadas"]]
    steps.columns = ["Paso", "Regla", "Filas", "Eliminadas"]
    return [section("Descripción del conjunto de datos", "¿Qué contiene el catálogo y cómo se depuró?",
                    [simple_table(pd.DataFrame(rows, columns=["Ítem", "Valor"])), html.H4("Pasos de limpieza"),
                     simple_table(steps)])]


# --------------------------------------------------------------------------
# 5. EDA univariado
# --------------------------------------------------------------------------
def page_eda_uni(f):
    k = ac.key(f)
    ev = ac.events(k)
    if len(ev) < 5:
        return [page_title("EDA univariado", ""), filter_note(f), html.Div("Muy pocos eventos con estos filtros.", className="warning-box")]
    a = ac.series(k, f["freq"])
    dt = np.diff(ev["t_days"].to_numpy()) * 24
    stats_rows = []
    for name, vals in (("Magnitud", ev["mag"]), ("Profundidad (km)", ev["depth"]),
                       ("Energía por evento (log10 J)", 1.5 * ev["mag"] + 4.8),
                       ("Tiempo entre eventos (h)", dt),
                       (f"Eventos por {FREQ_LABELS[f['freq']].split(' ')[0].lower()}", a["n"])):
        d = ac.descriptive(vals)
        stats_rows.append({"Variable": name, **{kk: d.get(kk, np.nan) for kk in
                           ["n", "media", "mediana", "desv_est", "min", "P25", "P75", "P95", "max", "asimetria",
                            "curtosis", "atipicos_tukey"]}})
    st = pd.DataFrame(stats_rows)
    fmt_map = {c: "{:,.2f}" for c in st.columns if c not in ("Variable", "n", "atipicos_tukey")}
    fmt_map.update({"n": "{:,.0f}", "atipicos_tukey": "{:,.0f}"})
    fixed = ev["depth"].isin(ts.PARAMS["fixed_depths_km"]).mean() * 100
    mt = ev["mag_type"].value_counts().head(10)
    dc = ev["depth_class"].value_counts()
    return [
        page_title("EDA univariado", "¿Cómo se distribuye cada variable del catálogo por separado?"), filter_note(f),
        section("Estadística descriptiva", "Resumen de cada variable con los filtros aplicados",
                [simple_table(st, fmt_map),
                 html.Button("Descargar estadísticas (CSV)", id="btn-dl-uni", className="btn")],
                interpretation=["Atípicos según Tukey (fuera de Q1 − 1.5·IQR y Q3 + 1.5·IQR). En variables "
                                "asimétricas como la magnitud o los tiempos entre eventos, estos 'atípicos' son la "
                                "cola natural de la distribución (sismos grandes, réplicas muy seguidas), no errores."]),
        html.Div([
            section("Magnitud", "¿Cómo se reparten las magnitudes?", graph(tc.fig_hist_box(ev["mag"], "Magnitud", bins=45)),
                    interpretation=f"La distribución decrece desde M 5.0 (truncamiento del catálogo) con una cola "
                                   f"derecha larga, como predice Gutenberg-Richter. Mediana M {ev['mag'].median():.2f}; "
                                   f"asimetría {ev['mag'].skew():.2f}."),
            section("Profundidad", "¿A qué profundidad ocurren los sismos?",
                    graph(tc.fig_hist_box(ev["depth"].clip(lower=1), "Profundidad (km)", bins=50, log_x=True)),
                    interpretation=f"Escala logarítmica. El {fixed:.0f} % de los eventos tiene una profundidad fija "
                                   "(10, 33 o 35 km): son los picos estrechos del histograma."),
        ], className="two-col"),
        html.Div([
            section("Frecuencia de eventos por periodo",
                    f"¿Cuántos eventos ocurren por {FREQ_LABELS[f['freq']].split(' ')[0].lower()}?",
                    graph(tc.fig_hist_box(a["n"], "Eventos por periodo", bins=40)),
                    interpretation=f"Media {a['n'].mean():.2f}, varianza {a['n'].var():.2f}: la varianza es "
                                   f"{a['n'].var() / max(a['n'].mean(), 1e-9):.1f} veces la media (Poisson = 1), "
                                   "lo que indica sobredispersión por agrupamiento."),
            section("Tiempo entre eventos", "¿Cada cuánto ocurre un sismo?",
                    graph(tc.fig_interevent(np.diff(ev['t_days'].to_numpy()))),
                    interpretation=f"Mediana {np.median(dt):.1f} h; CV = {np.std(dt, ddof=1) / np.mean(dt):.2f} "
                                   "(un proceso de Poisson tendría CV = 1)."),
        ], className="two-col"),
        html.Div([
            section("Escalas de magnitud", "¿Qué tipo de magnitud reporta cada evento?",
                    graph(tc.fig_bar_counts(mt, "Eventos"))),
            section("Clases de profundidad", "¿Qué proporción es superficial, intermedia o profunda?",
                    graph(tc.fig_bar_counts(dc, "Eventos"))),
        ], className="two-col"),
    ]


# --------------------------------------------------------------------------
# 6. EDA multivariado
# --------------------------------------------------------------------------
def page_eda_multi(f):
    from scipy import stats
    import plotly.graph_objects as go
    from config import DEPTH_COLORS
    k = ac.key(f)
    ev = ac.events(k)
    if len(ev) < 20:
        return [page_title("EDA multivariado", ""), filter_note(f), html.Div("Muy pocos eventos con estos filtros.", className="warning-box")]
    d = ev.dropna(subset=["depth"])
    rho, p = stats.spearmanr(d["depth"], d["mag"])
    order = ["Superficial (<70 km)", "Intermedia (70–300 km)", "Profunda (>300 km)"]
    groups = [ev.loc[ev["depth_class"] == g, "mag"].to_numpy() for g in order if (ev["depth_class"] == g).sum() > 4]
    kw = stats.kruskal(*groups) if len(groups) > 1 else None
    gr = ac.gutenberg_richter(k)
    m = ac.series(k, "M")
    corr = m[["n", "mag_mean", "mag_max", "depth_mean", "energy_log10"]].rename(columns=TS_LABELS).corr(method="spearman")
    # mapa
    smp = ev if len(ev) <= 6000 else ev.sample(6000, random_state=1)
    fig_map = go.Figure()
    for cls, color in DEPTH_COLORS.items():
        r = smp[smp["depth_class"] == cls]
        fig_map.add_trace(go.Scattergeo(lon=r["longitude"], lat=r["latitude"], mode="markers", name=cls,
                                        marker=dict(size=2 + (r["mag"] - 5) * 2.5, color=color, opacity=0.6),
                                        customdata=np.stack([r["time"].dt.strftime("%Y-%m-%d"), r["mag"]], axis=-1),
                                        hovertemplate="%{customdata[0]} · M %{customdata[1]}<extra></extra>"))
    fig_map.update_layout(geo=dict(GEO_STYLE, resolution=110, projection_rotation=dict(lon=150)), height=460,
                          margin=dict(l=0, r=0, t=0, b=0), legend=dict(x=0.01, y=0.02, bgcolor="rgba(255,255,255,0.85)"))
    blocks = [page_title("EDA multivariado", "¿Cómo se relacionan las variables entre sí, en el espacio y en el tiempo?"),
              filter_note(f),
              html.Div([
                  section("Magnitud frente a profundidad", "¿Los sismos profundos son más grandes o más pequeños?",
                          graph(tc.fig_mag_depth(ev)),
                          interpretation=f"Correlación de Spearman ρ = {rho:.3f} (p = {p:.2g}). Con n = {len(d):,}, "
                                         "cualquier correlación sale 'significativa'; lo que importa es el tamaño: "
                                         f"{'despreciable' if abs(rho) < 0.1 else 'débil' if abs(rho) < 0.3 else 'moderada'}."),
                  section("Magnitud por clase de profundidad", "Comparación por categorías",
                          graph(tc.fig_box_by(ev, "mag", "depth_class", order, "Magnitud")),
                          interpretation=(f"Kruskal-Wallis H = {kw.statistic:.1f}, p = {kw.pvalue:.2g}. Las medianas "
                                          "son casi iguales: la diferencia, si existe, está en la cola de eventos grandes."
                                          if kw else "Clases insuficientes para comparar.")),
              ], className="two-col"),
              ]
    if gr:
        s = gr["summary"]
        blocks.append(section("Frecuencia frente a magnitud (Gutenberg-Richter)",
                              "¿Cómo disminuye el número de eventos al aumentar la magnitud?",
                              graph(tc.fig_fmd(gr["fmd"], s["b"], gr["mc"])),
                              interpretation=f"Mc = {gr['mc']:.1f} ({gr['method']}); b = {fmt(s['b'], '{:.3f}')} ± "
                                             f"{fmt(s['sigma'], '{:.3f}')} (n = {s['n']:,}). Cada unidad de magnitud "
                                             f"reduce el número de eventos unas {10 ** s['b']:.0f} veces."
                              if s["valid"] else "Muestra insuficiente para b-value."))
    blocks.append(html.Div([
        section("Distribución espacial", "¿Dónde ocurren los eventos filtrados?", graph(fig_map),
                interpretation="Tamaño = magnitud; color = clase de profundidad. Muestra de hasta 6.000 eventos."),
        section("Correlación entre variables mensuales", "Spearman entre series agregadas por mes",
                graph(tc.fig_corr(corr)),
                interpretation="La energía mensual y la magnitud máxima están casi determinadas por el evento mayor, "
                               "por eso su correlación es muy alta: no son indicadores independientes."),
    ], className="two-col"))
    if f["region"] == "Global":
        reg = ev.dropna(subset=["region"])
        tab = pd.crosstab(reg["region"], reg["time"].dt.year)
        blocks.append(section("Distribución espacio-temporal por región", "Eventos por región y año",
                              graph(tc.fig_heat_region_year(tab)),
                              interpretation="Las franjas horizontales intensas de un solo año corresponden a "
                                             "secuencias de réplicas (p. ej. Sumatra 2004–2005, Japón 2011)."))
    return blocks


# --------------------------------------------------------------------------
# 7. Series de tiempo
# --------------------------------------------------------------------------
def _stationarity_text(adf, kpss):
    adf_rej = adf["estadistico"] < adf["critico_5"]
    kpss_rej = kpss["estadistico"] > kpss["critico_5"]
    if adf_rej and not kpss_rej:
        return "ADF rechaza raíz unitaria y KPSS no rechaza estacionariedad: la serie es compatible con estacionariedad."
    if not adf_rej and kpss_rej:
        return "ADF no rechaza raíz unitaria y KPSS rechaza estacionariedad: la serie no es estacionaria."
    if adf_rej and kpss_rej:
        return ("Ambas pruebas rechazan: la serie no tiene raíz unitaria pero su nivel no es constante "
                "(cambios de nivel, tendencia o memoria larga). Coincide con los cambios de régimen detectados.")
    return "Ninguna prueba rechaza: los datos no son concluyentes."


def page_series(f):
    k = ac.key(f)
    freq, var = f["freq"], f["var"]
    a = ac.series(k, freq)
    res_tab, rec = ac.resolution(k)
    label = TS_LABELS[var]
    t = ac.tests(k, freq, var)
    rt = res_tab.rename(columns={"resolucion": "Resolución", "periodos": "Periodos", "media": "Media de eventos",
                                 "varianza": "Varianza", "dispersion": "Índice de dispersión", "pct_ceros": "% periodos sin eventos",
                                 "pct_sin_magnitud": "% sin magnitud/profundidad"}).drop(columns="freq")
    roll = {"D": 30, "W": 13, "M": 12, "Y": 5}[freq]
    blocks = [page_title("Análisis de series de tiempo", "¿Cómo evoluciona en el tiempo la actividad sísmica registrada?"),
              filter_note(f),
              section("Elección de la resolución temporal", "¿Qué frecuencia de agregación es adecuada?",
                      simple_table(rt, {c: "{:,.2f}" for c in rt.columns if c != "Resolución"}),
                      interpretation=[f"Resolución actual: {FREQ_LABELS[freq]}. Recomendada para estos filtros: "
                                      f"{FREQ_LABELS[rec]} (la más fina con ≤ 10 % de periodos sin eventos y ≥ 60 periodos).",
                                      "Con muchos periodos vacíos, la magnitud y la profundidad medias quedan indefinidas "
                                      "y las pruebas de series de tiempo pierden sentido. Los modelos de pronóstico usan "
                                      "conteos mensuales: es la escala con suficientes eventos por periodo en la mayoría "
                                      "de regiones, sin perder demasiados puntos.",
                                      "Solo se usan periodos completos: el último mes (agosto 2026) termina el día 22 y se excluye."]),
              section(f"Serie: {label}", f"Evolución por {FREQ_LABELS[freq].lower()}",
                      [graph(tc.fig_series(a, var, label, roll=roll,
                                           anomalies=t.get("anom"),
                                           segments=None)),
                       html.Div([html.Button("Descargar serie (CSV)", id="btn-dl-series", className="btn"),
                                 html.Button("Descargar resultados de pruebas (CSV)", id="btn-dl-tests", className="btn")],
                                className="btn-row")],
                      interpretation="Barras/línea gris: valor por periodo. Línea azul: media móvil centrada. Rombos: "
                                     "periodos anómalos (ver más abajo)."),
              section("Todas las variables temporales", "Número de eventos, magnitud, profundidad y energía por periodo",
                      graph(tc.fig_multi_series(a, TS_LABELS)),
                      interpretation="La magnitud y la profundidad medias solo existen en periodos con eventos. La "
                                     "energía se calcula sumando energías por evento, nunca magnitudes."),
              html.Div([
                  section("Energía sísmica acumulada", "¿Cómo se acumula la energía liberada?",
                          graph(tc.fig_cumulative_energy(a)),
                          interpretation="Los saltos verticales son sismos individuales muy grandes (M ≥ 8.5): la "
                                         "energía de todo el periodo está dominada por unos pocos eventos."),
                  section("Comparación de periodos", f"{label} por década", graph(tc.fig_by_decade(a, var, label)),
                          interpretation="Las décadas incompletas (1970s desde 1973, 2020s hasta 2026) tienen menos periodos."),
              ], className="two-col")]
    if t["n"] < 20:
        blocks.append(html.Div(f"Las pruebas de series de tiempo requieren una serie sin huecos: "
                               f"{t['missing_frac'] * 100:.0f} % de periodos sin valor para '{label}'. Use una "
                               "resolución más gruesa o el número de eventos.", className="warning-box"))
        return blocks
    adf, kp, mk = t["adf"], t["kpss"], t.get("mk")
    tests_tab = pd.DataFrame([
        {"Prueba": "ADF (H₀: raíz unitaria)", "Estadístico": adf["estadistico"], "Valor crítico 5 %": adf["critico_5"],
         "p-valor": adf["p_valor"], "Rezagos": adf["rezagos"],
         "Decisión (5 %)": "Rechaza H₀" if adf["estadistico"] < adf["critico_5"] else "No rechaza"},
        {"Prueba": "KPSS nivel (H₀: estacionaria)", "Estadístico": kp["estadistico"], "Valor crítico 5 %": kp["critico_5"],
         "p-valor": kp["p_valor"], "Rezagos": kp["rezagos"],
         "Decisión (5 %)": "Rechaza H₀" if kp["estadistico"] > kp["critico_5"] else "No rechaza"},
    ])
    blocks.append(section("Estacionariedad", "¿Son constantes la media y la varianza de la serie?",
                          simple_table(tests_tab, {"Estadístico": "{:.3f}", "Valor crítico 5 %": "{:.3f}", "p-valor": "{:.4f}"}),
                          interpretation=[_stationarity_text(adf, kp),
                                          "Supuestos: ADF con constante y rezagos fijos k = ⌊12(n/100)^¼⌋; KPSS con "
                                          "ventana de Bartlett k = ⌊4(n/100)^¼⌋. Ambas suponen que la estructura "
                                          "de la serie no cambia; los cambios de nivel pueden hacer que rechacen las dos. "
                                          "El p-valor de KPSS está acotado entre 0.01 y 0.10 por la tabla de referencia."]))
    trend_txt = ("Serie demasiado larga para Mann-Kendall en esta resolución (n > 3.000): use semana o mes."
                 if mk is None else
                 f"Mann-Kendall: S = {mk['S']:,.0f}, z = {mk['z']:.2f}, p = {mk['p_valor']:.2g}. Pendiente de Sen: "
                 f"{mk['sen']:+.4f} por periodo. Con autocorrelación positiva el p-valor es optimista; además, parte "
                 "de la tendencia en conteos M ≥ 5 puede deberse a cambios en la red y en las escalas de magnitud.")
    blocks.append(html.Div([
        section("Autocorrelación (ACF)", "¿Cuánto 'recuerda' la serie su pasado?",
                graph(tc.fig_acf(t["acf"], t["band"], "acf", "")),
                interpretation=f"Banda gris: ±1.96/√n = ±{t['band']:.3f}. Rezago 1: {t['acf']['acf'].iloc[1]:.3f}. "
                               "Autocorrelaciones positivas que decaen lentamente indican persistencia (secuencias "
                               "de réplicas y cambios de nivel)."),
        section("Autocorrelación parcial (PACF)", "¿Qué rezagos aportan información directa?",
                graph(tc.fig_acf(t["acf"], t["band"], "pacf", "")),
                interpretation="Método de Yule-Walker (igual que pacf() de R). Un corte después de pocos rezagos "
                               "sugiere una componente autorregresiva de orden bajo."),
    ], className="two-col"))
    trend_blocks = [html.P(trend_txt)]
    if freq == "M" and t.get("stl"):
        stl, strength = t["stl"]
        kw = t.get("kruskal")
        blocks.append(section("Tendencia y estacionalidad (STL)", "¿Hay tendencia de largo plazo o un ciclo anual?",
                              graph(tc.fig_stl(stl)),
                              interpretation=[trend_txt,
                                              f"Fuerza de la estacionalidad (Wang et al., 2006): {strength:.3f} (0 = nula, 1 = dominante). "
                                              + (f"Kruskal-Wallis entre meses del año: H = {kw['H']:.2f}, p = {kw['p_valor']:.3f}. "
                                                 if kw else "")
                                              + "No se espera estacionalidad física en la sismicidad tectónica.",
                                              "STL robusto con periodo 12, ventana estacional 13 y de tendencia 23."]))
    else:
        blocks.append(section("Tendencia", "¿Aumenta o disminuye la serie?", trend_blocks,
                              interpretation="La descomposición STL y la prueba de estacionalidad se calculan con resolución mensual."))
    an = t["anom"]
    cp = t["cp"]
    n_an = int(an["anomalia"].sum())
    an_tab = an[an["anomalia"]].copy()
    an_tab["periodo"] = an_tab["periodo"].dt.strftime("%Y-%m-%d")
    seg_txt = "—"
    if cp and cp["cambios"]:
        seg_txt = "; ".join(f"{a['periodo'].iloc[c]:%Y-%m-%d}" for c in cp["cambios"])
    segs = [(s, e, (np.expm1(m) if var == "n" else m)) for s, e, m in cp["segmentos"]] if cp else None
    blocks.append(section("Anomalías y cambios de régimen", "¿Qué periodos se apartan de su historial reciente?",
                          [graph(tc.fig_series(a, var, label, anomalies=an, segments=segs)),
                           simple_table(an_tab.rename(columns={"periodo": "Periodo", var: label, "mediana_previa": "Mediana previa",
                                                               "z_robusto": "z robusto"}).drop(columns="anomalia").tail(15),
                                        {"Mediana previa": "{:.2f}", "z robusto": "{:.2f}", label: "{:,.2f}"})],
                          interpretation=[f"{n_an} periodos con |z| > {ts.PARAMS['anomaly_z']}, donde z se calcula con la "
                                          f"mediana y la MAD de los {ts.PARAMS['anomaly_window'][freq]} periodos anteriores "
                                          "(se muestran los 15 más recientes). Casi todas las anomalías de conteo coinciden "
                                          "con secuencias de réplicas de sismos grandes.",
                                          f"Cambios de régimen en el nivel medio (segmentación binaria, penalización BIC, "
                                          f"segmento mínimo {ts.PARAMS['changepoint_min_seg'][freq]} periodos): {seg_txt}. "
                                          "Líneas oscuras: nivel medio de cada segmento. Un cambio de régimen puede reflejar "
                                          "cambios del catálogo (detección, escalas de magnitud), no solo de la sismicidad."]))
    ie = ts.interevent_stats(ac.events_complete(k))
    if ie:
        phi = a["n"].var() / a["n"].mean() if a["n"].mean() > 0 else np.nan
        blocks.append(section("Agrupamiento temporal", "¿Los sismos llegan al azar o en ráfagas?",
                              graph(tc.fig_interevent(ie["dt"])),
                              interpretation=f"Catálogo completo: CV de los tiempos entre eventos = {ie['cv']:.2f} "
                                             f"(Poisson = 1); índice de dispersión de los conteos por periodo = {phi:.1f} "
                                             "(Poisson = 1). Ambos indican agrupamiento: las réplicas llegan en ráfagas. "
                                             "Con el catálogo desclusterizado el índice de dispersión baja."))
    return blocks


# --------------------------------------------------------------------------
# 8. Modelos
# --------------------------------------------------------------------------
def page_modelos(f, test_months, monitor_window):
    k = ac.key(f)
    ev = ac.model_eval(k, test_months)
    s = ac.series(k, "M")
    head = [page_title("Modelos", "¿Qué métodos describen y pronostican mejor la frecuencia mensual de eventos?"),
            filter_note(f),
            section("Métodos seleccionados y justificación", "¿Por qué estos modelos y no una regresión?",
                    dcc.Markdown("""
- **Variable modelada:** número de eventos por mes. Es la resolución más fina con pocos meses vacíos en la mayoría de regiones (ver *Series de tiempo*). La magnitud y la energía no se pronostican: dependen de eventos individuales y la energía la domina un único sismo.
- **Sin regresión:** el enfoque anterior relacionaba variables independientes entre sí. Aquí la información está en la propia historia de la serie (autocorrelación), así que se usan modelos de series de tiempo.
- **Referencias obligatorias:** *Ingenuo* (repite el último mes) y *Media histórica* (con intervalos de una Binomial Negativa, porque los conteos están sobredispersos). Un modelo solo aporta si supera a estas referencias.
- **Suavizamiento exponencial simple:** pondera más los meses recientes. Es adecuado para un nivel que cambia lentamente, sin tendencia ni estacionalidad marcadas (lo que muestran STL y Kruskal-Wallis).
- **ARIMA(1,0,1) con media:** recoge la autocorrelación de corto plazo que muestran la ACF y la PACF. Supone estacionariedad alrededor de la media; las pruebas ADF/KPSS indican cambios de nivel, así que sus intervalos pueden ser optimistas.
- **No se usó SARIMA:** la estacionalidad anual es débil (ver STL), así que un término estacional añadiría parámetros sin justificación.
- **Validación temporal:** los últimos meses son el conjunto de prueba y nunca se usan para ajustar. Métricas: MAE, RMSE y MASE (MASE < 1 = mejor que el ingenuo de un paso dentro del entrenamiento).
""", className="markdown"))]
    if ev is None:
        return head + [html.Div("La serie mensual es demasiado corta para entrenar y evaluar con estos filtros.", className="warning-box")]
    tab = ev["table"].copy()
    best = tab.loc[tab["MASE"].idxmin()]
    view = tab.drop(columns="clave").rename(columns={"modelo": "Modelo", "cobertura_95": "Cobertura IC95 (%)",
                                                     "ljung_box_p": "Ljung-Box p (residuos)", "detalle": "Parámetros"})
    sel_model = best["clave"]
    blocks = head + [
        section(f"Evaluación en los últimos {test_months} meses",
                f"Entrenamiento hasta {ev['train_end']:%Y-%m}; prueba {ev['test_periods'].iloc[0]:%Y-%m} → {ev['test_periods'].iloc[-1]:%Y-%m}",
                [graph(tc.fig_model_test(s, ev, MODELS)),
                 simple_table(view, {"MAE": "{:.2f}", "RMSE": "{:.2f}", "MASE": "{:.3f}", "Cobertura IC95 (%)": "{:.1f}",
                                     "Ljung-Box p (residuos)": "{:.3f}"}),
                 html.Button("Descargar evaluación (CSV)", id="btn-dl-eval", className="btn")],
                interpretation=[f"Menor error en el periodo de prueba: {best['modelo']} (MASE = {best['MASE']:.3f}). "
                                + ("Ningún modelo supera al ingenuo de un paso (MASE > 1): los pronósticos a varios meses "
                                   "son difíciles porque las secuencias de réplicas no se pueden anticipar."
                                   if best["MASE"] >= 1 else "Este modelo mejora al ingenuo de un paso."),
                                "Ljung-Box (12 rezagos) sobre los residuos del entrenamiento: p < 0.05 indica que queda "
                                "autocorrelación sin explicar. Cobertura: porcentaje de meses de prueba dentro del "
                                "intervalo del 95 % (lo ideal es cerca de 95 %)."]),
        section("Diagnóstico de residuos", f"¿Los residuos del mejor modelo ({best['modelo']}) son ruido blanco?",
                graph(tc.fig_residual_acf(ev["paths"][sel_model]["resid"])),
                interpretation="Si las barras quedan dentro de la banda gris, el modelo captó la dependencia temporal."),
        section("Monitor de ventana reciente (detección de anomalías)",
                "¿La actividad de la ventana reciente está fuera de su historial? (motor del dashboard anterior)",
                [dcc.RadioItems(id="mon-window", value=monitor_window, className="pills",
                                options=[{"label": f"{w} días", "value": w} for w in (30, 90, 180, 365, 730)]),
                 dcc.Loading(html.Div(id="monitor-content"), type="dot", color="#1f5f74")],
                interpretation="Compara la ventana más reciente con todas las ventanas históricas de igual duración "
                               "(percentiles y Binomial Negativa). Se conserva del dashboard anterior como método de "
                               "detección de anomalías."),
    ]
    return blocks


# --------------------------------------------------------------------------
# 9. Predecir
# --------------------------------------------------------------------------
def page_predecir_controls(model, horizon):
    return section("Configuración del pronóstico", "Variable pronosticada: número de eventos M ≥ Mmin por mes",
                   html.Div([
                       html.Div([html.Label("Modelo"), dcc.Dropdown(id="pred-model", value=model, clearable=False,
                                options=[{"label": v, "value": k} for k, v in MODELS.items()])], className="control"),
                       html.Div([html.Label("Horizonte (meses)"), dcc.RadioItems(id="pred-h", value=horizon, className="pills",
                                options=[{"label": str(h), "value": h} for h in ts.PARAMS["forecast"]["horizons"]])],
                                className="control"),
                       html.Button([html.I(className="bi bi-play-fill"), " Generar pronóstico"], id="btn-forecast",
                                   className="btn btn-primary"),
                   ], className="pred-controls"))


def page_predecir_result(f, model, h):
    k = ac.key(f)
    s = ac.series(k, "M")
    if len(s) < 72:
        return html.Div("La serie mensual es demasiado corta para pronosticar con estos filtros.", className="warning-box")
    fcst = ac.model_forecast(k, model, h)
    ev = ac.model_eval(k, ts.PARAMS["forecast"]["test_months"])
    row = ev["table"].set_index("clave").loc[model] if ev else None
    tab = fcst.copy()
    tab["periodo"] = tab["periodo"].dt.strftime("%Y-%m")
    tab.columns = ["Mes", "Pronóstico", "IC80 inf.", "IC80 sup.", "IC95 inf.", "IC95 sup."]
    return html.Div([
        section("Serie observada y pronóstico", f"{MODELS[model]} · horizonte {h} meses · desde {fcst['periodo'].iloc[0]:%Y-%m}",
                [graph(tc.fig_forecast(s, fcst, MODELS[model])),
                 simple_table(tab, {c: "{:.1f}" for c in tab.columns if c != "Mes"}),
                 html.Button("Descargar pronóstico (CSV)", id="btn-dl-forecast", className="btn")],
                interpretation=[f"El modelo se reajusta con todos los meses completos hasta {s['periodo'].iloc[-1]:%Y-%m}. "
                                "El primer mes pronosticado (agosto 2026) es el mes incompleto del catálogo.",
                                (f"Desempeño en la validación temporal ({ts.PARAMS['forecast']['test_months']} meses): "
                                 f"MAE = {row['MAE']:.1f}, RMSE = {row['RMSE']:.1f}, MASE = {row['MASE']:.3f}, cobertura "
                                 f"del IC95 = {row['cobertura_95']:.0f} %." if row is not None else "")]),
        section("Supuestos y limitaciones", "Cómo leer este pronóstico", dcc.Markdown(f"""
- **Qué se pronostica:** el número de eventos M ≥ {f['min_mag']:.1f} por mes en la región *{f['region']}* ({'catálogo completo' if f['catalog'] == 'complete' else 'catálogo desclusterizado'}). No se pronostican sismos individuales.
- **Supuestos:** el proceso futuro se comporta como el pasado reciente (nivel y variabilidad); los cambios de red o de escalas de magnitud no se repiten; los intervalos de SES y ARIMA son gaussianos, se truncan en 0 y no incluyen la incertidumbre de los parámetros.
- **Limitaciones:** un sismo grande genera cientos de réplicas en pocas semanas, y ningún modelo de esta sección puede anticiparlo: esos meses quedarán fuera de los intervalos. Con el catálogo desclusterizado la serie es más estable y los intervalos son más fiables.
- **{DISCLAIMER}**
""", className="markdown")),
    ])


# --------------------------------------------------------------------------
# 10–11. Enlaces y equipo
# --------------------------------------------------------------------------
def page_enlaces():
    links = json.loads((SHARED / "links.json").read_text(encoding="utf-8"))
    blocks = [page_title("Enlaces", "Fuentes de datos, documentación, referencias y herramientas")]
    for group, items in links.items():
        lis = [html.Li([html.A(i["titulo"], href=i["url"], target="_blank") if i["url"] else html.Span(i["titulo"]),
                        html.Span(f" — {i['nota']}", className="muted")]) for i in items]
        blocks.append(section(group, "", html.Ul(lis, className="link-list")))
    return blocks


def page_equipo():
    t = json.loads((SHARED / "team.json").read_text(encoding="utf-8"))
    cards = [html.Div([html.I(className="bi bi-person-circle team-icon"), html.H4(m["nombre"]), html.P(m["rol"]),
                       html.P(m.get("contacto", ""), className="muted")], className="team-card") for m in t["integrantes"]]
    return [page_title("Equipo", "Integrantes y contexto académico"),
            html.Div(cards, className="team-grid"),
            section("Información académica", "",
                    simple_table(pd.DataFrame([["Institución", t["institucion"]], ["Programa", t["programa"]],
                                               ["Curso", t["curso"]], ["Periodo", t["periodo"]]], columns=["Ítem", "Valor"])))]
