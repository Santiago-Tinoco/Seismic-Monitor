"""Declustering de Gardner & Knopoff (1974).

Se usa para separar actividad "independiente" (eventos principales) de la
actividad dependiente (réplicas y premonitores) con ventanas espacio-temporales
que crecen con la magnitud del evento principal:

    L(M) = 10^(0.1238 M + 0.983)               [km]
    T(M) = 10^(0.032 M + 2.7389)   si M >= 6.5  [días]
    T(M) = 10^(0.5409 M - 0.547)   si M <  6.5  [días]

Algoritmo (ventana simétrica en el tiempo):
  1. Ordenar los eventos por magnitud descendente.
  2. El evento de mayor magnitud aún no asignado es un evento principal.
  3. Todo evento no asignado, de magnitud <= la del principal, situado a
     menos de L(M) km y a menos de T(M) días (antes o después) se marca como
     dependiente y se asigna al mismo cluster.
  4. Repetir hasta recorrer todos los eventos.

Limitación importante: este catálogo solo contiene M >= 5.0, así que las
réplicas de menor magnitud no existen en el dataset. El declustering solo
puede retirar eventos dependientes de M >= 5.0.
"""
import numpy as np

EARTH_RADIUS_KM = 6371.0


def gk_distance_window_km(mag):
    return 10 ** (0.1238 * np.asarray(mag) + 0.983)


def gk_time_window_days(mag):
    mag = np.asarray(mag, dtype=float)
    return np.where(mag >= 6.5, 10 ** (0.032 * mag + 2.7389), 10 ** (0.5409 * mag - 0.547))


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def gardner_knopoff_decluster(t_days, lat, lon, mag):
    """Devuelve (is_dependent, cluster_id).

    t_days debe estar ordenado de forma ascendente.
    cluster_id = posición del evento principal del cluster; -1 si el evento
    no pertenece a ningún cluster (evento aislado).
    """
    t = np.asarray(t_days, dtype=float)
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    mag = np.asarray(mag, dtype=float)
    if np.any(np.diff(t) < 0):
        raise ValueError("t_days debe estar ordenado.")

    n = len(t)
    assigned = np.zeros(n, dtype=bool)
    dependent = np.zeros(n, dtype=bool)
    cluster = np.full(n, -1, dtype=np.int64)

    order = np.lexsort((t, -mag))          # magnitud descendente, luego tiempo
    L = gk_distance_window_km(mag)
    T = gk_time_window_days(mag)

    for i in order:
        if assigned[i]:
            continue
        assigned[i] = True
        lo = np.searchsorted(t, t[i] - T[i], side="left")
        hi = np.searchsorted(t, t[i] + T[i], side="right")
        idx = np.arange(lo, hi)
        idx = idx[(~assigned[idx]) & (mag[idx] <= mag[i])]
        if idx.size == 0:
            continue
        d = haversine_km(lat[i], lon[i], lat[idx], lon[idx])
        members = idx[d <= L[i]]
        if members.size:
            assigned[members] = True
            dependent[members] = True
            cluster[members] = i
            cluster[i] = i
    return dependent, cluster
