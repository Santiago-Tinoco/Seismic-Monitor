"""Métricas de agrupamiento temporal y espacial dentro de una ventana.

Se calculan SIEMPRE sobre el catálogo completo: el declustering elimina
precisamente el agrupamiento que estas métricas intentan medir.

Temporal
  - Fracción de eventos dependientes (Gardner-Knopoff): proporción de los
    eventos de la ventana que pertenecen a una secuencia (réplicas o
    premonitores) según el declustering global.
  - Coeficiente de variación de los tiempos entre eventos (CV = σ/μ):
    CV ≈ 1 para un proceso de Poisson; CV > 1 indica agrupamiento.

Espacial
  - Distancia mediana al vecino más cercano (km, gran círculo): valores
    pequeños indican eventos más concentrados en el espacio.
"""
import numpy as np

from config import MIN_EVENTS_CLUSTER
from src.declustering import haversine_km


def inter_event_times_days(t_days):
    t = np.sort(np.asarray(t_days, dtype=float))
    return np.diff(t)


def coefficient_of_variation(t_days, min_n=MIN_EVENTS_CLUSTER):
    dt = inter_event_times_days(t_days)
    if dt.size + 1 < min_n or dt.mean() <= 0:
        return np.nan
    return float(dt.std(ddof=1) / dt.mean())


def burstiness(cv):
    """Goh & Barabási (2008): B = (CV − 1)/(CV + 1); B=0 Poisson, B>0 en ráfagas."""
    return (cv - 1) / (cv + 1) if np.isfinite(cv) else np.nan


def dependent_fraction(is_dependent, min_n=5):
    x = np.asarray(is_dependent, dtype=bool)
    if x.size < min_n:
        return np.nan
    return float(x.mean())


def nearest_neighbor_median_km(lat, lon, min_n=MIN_EVENTS_CLUSTER):
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    n = lat.size
    if n < min_n:
        return np.nan
    d = haversine_km(lat[:, None], lon[:, None], lat[None, :], lon[None, :])
    np.fill_diagonal(d, np.inf)
    return float(np.median(d.min(axis=1)))
