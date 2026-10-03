"""Parámetros globales del proyecto.

Todas las decisiones metodológicas "arbitrarias" del dashboard están aquí,
para que sean visibles, documentables y fáciles de cambiar en un análisis de
sensibilidad.
"""
from pathlib import Path

# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
RAW_CSV = ROOT / "data" / "raw" / "Significant_Earthquakes.csv"
PROCESSED_DIR = ROOT / "data" / "processed"
CATALOG_PARQUET = PROCESSED_DIR / "catalog_clean.parquet"
QUALITY_JSON = PROCESSED_DIR / "data_quality_report.json"
REGIONS_CSV = PROCESSED_DIR / "regions_summary.csv"
CELLS_CSV = PROCESSED_DIR / "grid_cells_summary.csv"

# --------------------------------------------------------------------------
# Catálogo de trabajo
# --------------------------------------------------------------------------
# El conteo anual de M>=5 salta de ~550-620 eventos/año (1968-1972) a
# >1.300 eventos/año desde 1973 (inicio del catálogo PDE del USGS).
# Antes de 1973 el catálogo no es comparable -> se excluye del análisis.
ANALYSIS_START = "1973-01-01"
CATALOG_MIN_MAG = 5.0          # truncamiento del catálogo (no es una Mc estimada)
MAG_BIN = 0.1                  # resolución de binning de magnitud (ΔM)

# Escalas de magnitud de momento presentes en el catálogo
MW_FAMILY = ["mw", "mww", "mwc", "mwb", "mwr", "mwp"]

# Profundidades por defecto (valores fijados cuando no se resuelve la profundidad)
FIXED_DEPTHS_KM = [10.0, 33.0, 35.0]
DEPTH_CLASSES = [(-10, 70, "Superficial (<70 km)"),
                 (70, 300, "Intermedia (70–300 km)"),
                 (300, 800, "Profunda (>300 km)")]

# --------------------------------------------------------------------------
# Ventanas y línea base
# --------------------------------------------------------------------------
WINDOW_OPTIONS = [7, 30, 90, 180, 365, 730]   # días
DEFAULT_WINDOW = 90
BASELINE_START_OPTIONS = [1973, 1980, 1990, 2000]
# Paso entre ventanas históricas móviles = max(1, W // WINDOW_STRIDE_DIVISOR)
WINDOW_STRIDE_DIVISOR = 10
# Si más de esta fracción de ventanas históricas tiene 0 eventos, la ventana
# se marca como "información insuficiente".
MAX_ZERO_FRACTION = 0.10

# --------------------------------------------------------------------------
# Reglas operacionales de anomalía (definición del proyecto, no ley universal)
# --------------------------------------------------------------------------
P_LOW, P_HIGH = 5.0, 95.0        # fuera de [P5, P95]  -> inusual
P_EXT_LOW, P_EXT_HIGH = 1.0, 99.0  # fuera de [P1, P99] -> muy inusual
ALPHA = 0.05

# Tamaños mínimos de muestra
MIN_EVENTS_DEPTH = 5             # mediana de profundidad por ventana
MIN_EVENTS_CLUSTER = 10          # CV de tiempos y vecino más cercano
MIN_EVENTS_BVALUE = 50           # b-value
MIN_EVENTS_CELL = 60             # celdas 5°x5° disponibles (criterio del EDA)
GRID_STEP = 5                    # grados

# Regiones predefinidas: criterio de inclusión
MIN_EXPECTED_PER_90D = 2.0       # >= 2 eventos esperados por ventana de 90 días

# b-value
B_PERIOD_OPTIONS = [2, 5, 10]    # años
DEFAULT_B_PERIOD = 5
MC_CANDIDATES_MAX = 6.0
MBS_AVG_WIDTH = 0.5              # ancho (en M) del promedio móvil de b en MBS
N_BOOTSTRAP = 300
RANDOM_SEED = 42

# Sensibilidad
SENS_WINDOWS = [30, 90, 180, 365, 730]
SENS_MIN_MAGS = [5.0, 5.5, 6.0]

# --------------------------------------------------------------------------
# Paleta (sobria; el color indica desviación estadística, no peligro)
# --------------------------------------------------------------------------
COLORS = {
    "ink": "#1d262b",
    "muted": "#5d6b72",
    "grid": "#e3e7e9",
    "paper": "#ffffff",
    "bg": "#f4f5f2",
    "hist": "#a7b0b4",        # historial / línea base
    "hist_dark": "#6f7b80",
    "recent": "#1f5f74",      # ventana reciente
    "above": "#c4741c",       # por encima de lo esperado
    "above_ext": "#8a4d10",
    "below": "#2b6a9e",       # por debajo de lo esperado
    "below_ext": "#1b4870",
    "normal": "#a3aaa4",      # gris neutro: punto medio divergente
    "na": "#b9bfc2",
}
DEPTH_COLORS = {
    "Superficial (<70 km)": "#e0b34a",
    "Intermedia (70–300 km)": "#3a8a8c",
    "Profunda (>300 km)": "#2b2d5c",
}
