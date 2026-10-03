"""Mapas con proyección geográfica de Plotly (go.Scattergeo / go.Choropleth).

Se usa la cartografía vectorial integrada en Plotly (costas y fronteras de
Natural Earth) en lugar de teselas web: funciona sin conexión a internet y sin
token, y permite zoom, desplazamiento y hover.
"""
import numpy as np
import plotly.graph_objects as go

from config import COLORS, DEPTH_COLORS
from components.charts import STATUS_COLOR
from src.regions import box_outline, cell_bounds

GEO_STYLE = dict(projection_type="natural earth", resolution=50, showland=True, landcolor="#eceee9", showocean=True,
                 oceancolor="#f7f9fa", showcountries=True, countrycolor="#c3c9cb", countrywidth=0.5,
                 coastlinecolor="#9aa5ab", coastlinewidth=0.6, showlakes=False, bgcolor="rgba(0,0,0,0)",
                 lataxis=dict(showgrid=True, gridcolor="#e3e7e9", dtick=10),
                 lonaxis=dict(showgrid=True, gridcolor="#e3e7e9", dtick=10))


def _center_of_boxes(boxes):
    lats = [b[0] for b in boxes] + [b[1] for b in boxes]
    # Para regiones que cruzan el antimeridiano se centra en 180°
    lons = [b[2] for b in boxes] + [b[3] for b in boxes]
    crosses = any(b[3] == 180 for b in boxes) and any(b[2] == -180 for b in boxes)
    lon_c = 180.0 if crosses else (min(lons) + max(lons)) / 2
    if crosses:
        lon_span = (180 - min(b[2] for b in boxes if b[2] > 0)) + (max(b[3] for b in boxes if b[3] < 0) + 180)
    else:
        lon_span = max(lons) - min(lons)
    span = max(max(lats) - min(lats), lon_span)
    return (min(lats) + max(lats)) / 2, lon_c, span


def fig_event_map(res: dict, boxes, show_history=True):
    """Eventos recientes (tamaño = magnitud, color = clase de profundidad)
    sobre la sismicidad histórica de la región en gris."""
    fig = go.Figure()
    for box in boxes:
        lons, lats = box_outline(box)
        fig.add_trace(go.Scattergeo(lon=lons, lat=lats, mode="lines", line=dict(color=COLORS["ink"], width=1.5),
                                    hoverinfo="skip", showlegend=False))
    if show_history:
        h = res["hist_events"]
        if len(h) > 6000:
            h = h.sample(6000, random_state=1)
        fig.add_trace(go.Scattergeo(lon=h["longitude"], lat=h["latitude"], mode="markers",
                                    marker=dict(size=4, color="#8f9aa0", opacity=0.35),
                                    name="Línea base (histórico)", hoverinfo="skip"))
    rec = res["recent_events"]
    for cls, color in DEPTH_COLORS.items():
        r = rec[rec["depth_class"] == cls]
        if not len(r):
            continue
        fig.add_trace(go.Scattergeo(
            lon=r["longitude"], lat=r["latitude"], mode="markers", name=f"Reciente · {cls}",
            marker=dict(size=6 + (r["mag"] - 5.0) * 7, color=color, opacity=0.9),
            customdata=np.stack([r["time"].dt.strftime("%Y-%m-%d %H:%M"), r["mag"].round(2), r["mag_type"],
                                 r["depth"].round(1), r["place"].fillna("—"), r["id"],
                                 np.where(r["gk_dependent"], "sí", "no")], axis=-1),
            hovertemplate="<b>M %{customdata[1]}</b> (%{customdata[2]})<br>%{customdata[0]} UTC"
                          "<br>Profundidad: %{customdata[3]} km<br>Lat %{lat:.2f}, Lon %{lon:.2f}"
                          "<br>%{customdata[4]}<br>En secuencia (GK): %{customdata[6]}"
                          "<br>id: %{customdata[5]}<extra></extra>"))
    lat_c, lon_c, span = _center_of_boxes(boxes)
    lats = [b[0] for b in boxes] + [b[1] for b in boxes]
    pad = max(4, span * 0.25)
    geo = dict(GEO_STYLE, center=dict(lat=lat_c, lon=lon_c), projection_rotation=dict(lon=lon_c),
               lataxis_range=[max(-90, min(lats) - pad), min(90, max(lats) + pad)])
    if lon_c != 180.0:
        lons = [b[2] for b in boxes] + [b[3] for b in boxes]
        geo["lonaxis_range"] = [min(lons) - pad, max(lons) + pad]
    else:
        geo["lonaxis_range"] = [lon_c - span / 2 - pad, lon_c + span / 2 + pad]
    fig.update_layout(geo=geo, height=600, margin=dict(l=0, r=0, t=0, b=0),
                      legend=dict(orientation="v", x=0.01, y=0.99, xanchor="left", yanchor="top",
                                  bgcolor="rgba(255,255,255,0.88)", bordercolor="#c8cfd2", borderwidth=1))
    return fig


def fig_cells_map(df, cells_meta):
    """Celdas 5°x5° coloreadas por el estado de su conteo frente a su propio historial."""
    meta = cells_meta.set_index("cell")
    features, ids = [], []
    for c in df["unidad"]:
        (lat0, lat1, lon0, lon1), = cell_bounds(c)
        features.append({"type": "Feature", "id": c, "properties": {},
                         "geometry": {"type": "Polygon",
                                      # anillo en sentido horario (convención de d3-geo; en antihorario se rellena el resto del globo)
                                      "coordinates": [[[lon0, lat0], [lon0, lat1], [lon1, lat1], [lon1, lat0], [lon0, lat0]]]}})
        ids.append(c)
    geo = {"type": "FeatureCollection", "features": features}
    codes = ["na", "below_ext", "below", "normal", "above", "above_ext"]
    zmap = {c: i for i, c in enumerate(codes)}
    z = df["estado_codigo"].map(zmap)
    colorscale = []
    for i, c in enumerate(codes):
        colorscale += [[i / len(codes), STATUS_COLOR[c]], [(i + 1) / len(codes), STATUS_COLOR[c]]]
    names = [meta.loc[c, "nombre"] if c in meta.index else "" for c in df["unidad"]]
    fig = go.Figure(go.Choropleth(
        geojson=geo, locations=ids, featureidkey="id", z=z, zmin=-0.5, zmax=len(codes) - 0.5, colorscale=colorscale,
        marker=dict(line=dict(width=0.4, color="white")), showscale=False,
        customdata=np.stack([names, df["percentil"].round(1), df["n_actual"], df["mediana_hist"], df["estado"],
                             df["q_fdr"].round(3)], axis=-1),
        hovertemplate="<b>Celda %{location}</b> · %{customdata[0]}<br>Percentil: %{customdata[1]}"
                      "<br>Eventos actuales: %{customdata[2]} · mediana histórica: %{customdata[3]}"
                      "<br>%{customdata[4]}<br>q (FDR): %{customdata[5]}<extra></extra>"))
    fig.update_layout(geo=dict(GEO_STYLE, resolution=110, projection_rotation=dict(lon=170), fitbounds=False),
                      height=500, margin=dict(l=0, r=0, t=0, b=0))
    return fig
