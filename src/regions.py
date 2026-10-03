"""Definición de regiones de análisis.

Dos tipos de unidad espacial:

1. Regiones predefinidas: cajas lat/lon trazadas sobre cinturones sísmicos
   continuos que se ven en el propio catálogo (mapa de eventos M>=5 desde 1973).
   Una región puede estar formada por varias cajas (p. ej. para cruzar el
   antimeridiano). Las cajas no se superponen: cada evento pertenece como
   máximo a una región. Solo se habilitan las que cumplen el criterio de
   cobertura (>= MIN_EXPECTED_PER_90D eventos esperados por ventana de 90 días),
   que se verifica en scripts/build_catalog.py.

2. Celdas de malla de 5°x5° (misma partición del EDA), para explorar
   cualquier otra zona con >= MIN_EVENTS_CELL eventos.

Las cajas son una decisión de análisis (no fronteras oficiales). La
descripción tectónica es general y sirve solo como contexto.
"""
import numpy as np
import pandas as pd

from config import GRID_STEP

# nombre -> (lista de cajas (lat_min, lat_max, lon_min, lon_max), contexto)
PREDEFINED_REGIONS = {
    "Norte de los Andes": (
        [(-5, 13, -82, -66)],
        "Subducción de Nazca bajo Sudamérica (Colombia, Ecuador, occidente de Venezuela); incluye el nido de Bucaramanga."),
    "Perú": (
        [(-18, -5, -82, -66)],
        "Subducción de Nazca bajo Sudamérica."),
    "Chile norte": (
        [(-28, -18, -76, -62)],
        "Subducción de Nazca; incluye sismicidad intermedia bajo Bolivia y el noroeste argentino."),
    "Chile centro-sur": (
        [(-46, -28, -78, -62)],
        "Subducción de Nazca bajo Sudamérica."),
    "México": (
        [(14, 22, -110, -94)],
        "Subducción de Cocos y Rivera bajo Norteamérica."),
    "Centroamérica": (
        [(7, 16, -94, -82)],
        "Subducción de Cocos bajo la placa Caribe."),
    "Caribe": (
        [(13, 21, -76, -58), (10, 13, -66, -58)],
        "Límite Caribe–Norteamérica: La Española, Puerto Rico y arco de las Antillas Menores."),
    "California–Cascadia": (
        [(32, 50, -130, -114)],
        "Sistema de San Andrés, zona de Mendocino y subducción de Cascadia."),
    "Aleutianas–Alaska": (
        [(50, 64, 165, 180), (50, 64, -180, -140)],
        "Subducción del Pacífico bajo Norteamérica."),
    "Kuriles–Kamchatka": (
        [(42, 60, 140, 165)],
        "Subducción del Pacífico (Hokkaido oriental, Kuriles, Kamchatka)."),
    "Japón": (
        [(30, 42, 128, 146)],
        "Subducción de las placas Pacífico y Filipinas (Honshu, Shikoku, Kyushu)."),
    "Izu-Bonin–Marianas": (
        [(10, 30, 136, 150)],
        "Subducción del Pacífico bajo la placa Filipinas."),
    "Ryukyu–Taiwán": (
        [(21, 30, 119, 132)],
        "Subducción de Filipinas bajo Eurasia y colisión de Taiwán."),
    "Filipinas": (
        [(5, 21, 116, 128)],
        "Fosas de Filipinas y de Manila."),
    "Sumatra–Andamán–Java": (
        [(-12, 15, 90, 105), (-12, -5, 105, 120)],
        "Arco de la Sonda: subducción Indo-Australiana bajo la placa Sonda."),
    "Banda–Molucas": (
        [(-12, 5, 120, 135)],
        "Arco de Banda, Mar de Molucas y Sulawesi oriental."),
    "Nueva Guinea": (
        [(-12, 0, 135, 154)],
        "Nueva Guinea y Nueva Bretaña."),
    "Islas Salomón": (
        [(-13, -4, 154, 164)],
        "Subducción de la placa Australiana bajo el Pacífico."),
    "Vanuatu": (
        [(-23, -13, 164, 172)],
        "Subducción de la placa Australiana (fosa de Nuevas Hébridas)."),
    "Fiyi–Tonga–Kermadec": (
        [(-40, -14, 176, 180), (-40, -14, -180, -170)],
        "Subducción del Pacífico bajo la placa Australiana; incluye la sismicidad profunda de Fiyi."),
    "Nueva Zelanda": (
        [(-48, -40, 165, 180)],
        "Límite Pacífico–Australia en Nueva Zelanda (Alpine Fault y Hikurangi sur)."),
    "Turquía–Egeo": (
        [(34, 42, 19, 44)],
        "Anatolia y arco Helénico."),
    "Irán–Zagros": (
        [(25, 40, 44, 64)],
        "Colisión Arabia–Eurasia."),
    "Hindu Kush–Pamir": (
        [(34, 40, 66, 76)],
        "Sismicidad intermedia de Hindu Kush y Pamir."),
    "Himalaya–Tíbet": (
        [(25, 34, 76, 100)],
        "Colisión India–Eurasia."),
    "Arco de Scotia": (
        [(-62, -54, -40, -20)],
        "Fosa de Sandwich del Sur y límite Scotia–Sudamérica."),
}


def _in_box(lat, lon, box):
    lat_min, lat_max, lon_min, lon_max = box
    upper = lon <= lon_max if lon_max >= 180 else lon < lon_max
    return (lat >= lat_min) & (lat < lat_max) & (lon >= lon_min) & upper


def assign_predefined_region(df: pd.DataFrame) -> pd.Series:
    """Devuelve el nombre de la región predefinida de cada evento (o NaN)."""
    out = pd.Series(np.nan, index=df.index, dtype=object)
    lat, lon = df["latitude"].to_numpy(), df["longitude"].to_numpy()
    for name, (boxes, _) in PREDEFINED_REGIONS.items():
        mask = np.zeros(len(df), dtype=bool)
        for box in boxes:
            mask |= _in_box(lat, lon, box)
        overlap = mask & out.notna().to_numpy()
        if overlap.any():
            raise ValueError(f"La región '{name}' se superpone con otra región.")
        out[mask] = name
    return out


def assign_grid_cell(df: pd.DataFrame, step: int = GRID_STEP) -> pd.Series:
    """Celda de malla 'lat|lon' (esquina SW). lon=180 se asigna a -180."""
    lon = df["longitude"].where(df["longitude"] < 180, -180.0)
    lat = df["latitude"].clip(upper=90 - 1e-9)
    lat_b = (np.floor(lat / step) * step).astype(int)
    lon_b = (np.floor(lon / step) * step).astype(int)
    return lat_b.astype(str) + "|" + lon_b.astype(str)


def cell_bounds(cell: str, step: int = GRID_STEP):
    lat0, lon0 = (int(v) for v in cell.split("|"))
    return [(lat0, lat0 + step, lon0, lon0 + step)]


def region_boxes(region_type: str, key: str):
    if region_type == "cell":
        return cell_bounds(key)
    return PREDEFINED_REGIONS[key][0]


def region_description(region_type: str, key: str) -> str:
    if region_type == "cell":
        lat0, lon0 = (int(v) for v in key.split("|"))
        return (f"Celda de malla {GRID_STEP}°×{GRID_STEP}°: latitud {lat0}° a {lat0 + GRID_STEP}°, "
                f"longitud {lon0}° a {lon0 + GRID_STEP}°.")
    return PREDEFINED_REGIONS[key][1]


def box_outline(box):
    """Coordenadas (lons, lats) de un rectángulo para dibujarlo en el mapa."""
    lat_min, lat_max, lon_min, lon_max = box
    lons = [lon_min, lon_max, lon_max, lon_min, lon_min]
    lats = [lat_min, lat_min, lat_max, lat_max, lat_min]
    return lons, lats
