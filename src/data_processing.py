"""Carga, limpieza y preparación del catálogo.

El archivo original en data/raw/ nunca se modifica. Cada paso de limpieza
queda registrado (filas antes/después) en el reporte de calidad.
"""
import json

import numpy as np
import pandas as pd

from config import (ANALYSIS_START, CATALOG_MIN_MAG, DEPTH_CLASSES,
                    FIXED_DEPTHS_KM, MAG_BIN, MW_FAMILY)
from src.regions import assign_grid_cell, assign_predefined_region
from src.seismic_analysis import bin_magnitudes, energy_log10_joules

EXPECTED_COLUMNS = ["time", "latitude", "longitude", "depth", "mag", "magType",
                    "nst", "gap", "dmin", "rms", "net", "id", "updated", "place",
                    "type", "horizontalError", "depthError", "magError", "magNst",
                    "status", "locationSource", "magSource"]


def load_raw_catalog(path) -> pd.DataFrame:
    """Lee el CSV original. La primera columna sin nombre es un índice exportado."""
    df = pd.read_csv(path)
    unnamed = [c for c in df.columns if c.startswith("Unnamed")]
    df = df.drop(columns=unnamed)
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(f"Faltan columnas esperadas en el CSV: {missing}")
    return df


def audit_raw_catalog(df: pd.DataFrame) -> dict:
    """Auditoría del archivo crudo (antes de cualquier filtro)."""
    t = pd.to_datetime(df["time"], errors="coerce", utc=True)
    missing = (df.isna().mean() * 100).round(2).sort_values(ascending=False)
    return {
        "n_rows": int(len(df)),
        "n_columns": int(df.shape[1]),
        "columns": list(df.columns),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "missing_pct": missing.to_dict(),
        "invalid_times": int(t.isna().sum()),
        "time_min": str(t.min()),
        "time_max": str(t.max()),
        "time_sorted_in_file": bool(t.is_monotonic_increasing),
        "time_format": "ISO 8601 UTC (sufijo Z)",
        "duplicated_ids": int(df["id"].duplicated().sum()),
        "fully_duplicated_rows": int(df.duplicated().sum()),
        "event_types": df["type"].value_counts().to_dict(),
        "status": df["status"].value_counts().to_dict(),
        "networks_top": df["net"].value_counts().head(8).to_dict(),
        "mag_types": df["magType"].value_counts().to_dict(),
        "mag_min": float(df["mag"].min()),
        "mag_max": float(df["mag"].max()),
        "depth_min": float(df["depth"].min()),
        "depth_max": float(df["depth"].max()),
        "depth_missing": int(df["depth"].isna().sum()),
        "depth_negative": int((df["depth"] < 0).sum()),
        "lat_range": [float(df["latitude"].min()), float(df["latitude"].max())],
        "lon_range": [float(df["longitude"].min()), float(df["longitude"].max())],
    }


def clean_catalog(df: pd.DataFrame):
    """Limpieza documentada. Devuelve (catálogo limpio con todos los años, pasos)."""
    steps = []

    def log(name, new, rule):
        steps.append({"paso": name, "regla": rule, "filas": int(len(new)),
                      "eliminadas": int((steps[-1]["filas"] if steps else len(new)) - len(new))})
        return new

    out = df.copy()
    log("Archivo original", out, "—")

    out["time"] = pd.to_datetime(out["time"], errors="coerce", utc=True)
    out["updated"] = pd.to_datetime(out["updated"], errors="coerce", utc=True)
    out = log("Fecha válida", out[out["time"].notna()], "time convertible a fecha UTC")

    out = log("Solo sismos", out[out["type"].astype(str).str.lower() == "earthquake"],
              "type == 'earthquake' (excluye explosiones nucleares, erupciones, etc.)")

    # Para ids repetidos se conserva la solución con 'updated' más reciente
    out = out.sort_values(["id", "updated"])
    out = log("Id único (revisión más reciente)", out.drop_duplicates("id", keep="last"),
              "por id repetido se conserva la fila con 'updated' más reciente")

    out = log("Coordenadas y magnitud válidas",
              out[out["latitude"].between(-90, 90) & out["longitude"].between(-180, 180)
                  & out["mag"].notna()],
              "latitud en [-90, 90], longitud en [-180, 180], magnitud no nula")

    out = log("Magnitud ≥ truncamiento", out[out["mag"] >= CATALOG_MIN_MAG - 1e-9],
              f"mag ≥ {CATALOG_MIN_MAG}")

    out = out.sort_values("time").reset_index(drop=True)
    return out, steps


def add_derived_variables(df: pd.DataFrame) -> pd.DataFrame:
    """Variables derivadas. Ninguna reemplaza a una columna original."""
    out = df.copy()
    out["year"] = out["time"].dt.year
    out["t_days"] = (out["time"] - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds() / 86400.0
    out["mag_type"] = out["magType"].astype(str).str.lower()
    out["is_mw_family"] = out["mag_type"].isin(MW_FAMILY)
    out["mag_binned"] = bin_magnitudes(out["mag"].to_numpy(), MAG_BIN)
    out["log10_energy_J"] = energy_log10_joules(out["mag"].to_numpy())
    # Profundidad: se conservan los faltantes como NaN (no se imputa: la
    # profundidad no se usa para contar eventos; las métricas de profundidad
    # se calculan solo sobre valores observados).
    out["depth_missing"] = out["depth"].isna()
    out["fixed_depth"] = out["depth"].isin(FIXED_DEPTHS_KM)
    depth_for_class = out["depth"].clip(lower=0)
    cuts = [DEPTH_CLASSES[0][0]] + [c[1] for c in DEPTH_CLASSES]
    labels = [c[2] for c in DEPTH_CLASSES]
    out["depth_class"] = pd.cut(depth_for_class, bins=cuts, labels=labels).astype(object)
    out["region"] = assign_predefined_region(out)
    out["cell"] = assign_grid_cell(out)
    out["in_analysis_period"] = out["time"] >= pd.Timestamp(ANALYSIS_START, tz="UTC")
    return out


def annual_counts(df: pd.DataFrame) -> dict:
    return df.groupby("year").size().astype(int).to_dict()


def magtype_by_era(df: pd.DataFrame) -> dict:
    eras = pd.cut(df["year"], [1899, 1972, 1990, 2000, 2010, 2015, 2020, 2030],
                  labels=["1900–1972", "1973–1990", "1991–2000", "2001–2010",
                          "2011–2015", "2016–2020", "2021–2026"])
    top = df["mag_type"].value_counts().head(7).index
    mt = df["mag_type"].where(df["mag_type"].isin(top), "otras")
    tab = pd.crosstab(eras, mt, normalize="index").mul(100).round(1)
    return {str(k): v for k, v in tab.to_dict(orient="index").items()}


def save_json(obj, path):
    def default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        return str(o)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=default)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
