"""Construye los datos procesados a partir del CSV original.

Uso (desde la carpeta del proyecto):
    python scripts/build_catalog.py

Salidas en data/processed/:
    catalog_clean.parquet        catálogo limpio + variables derivadas + declustering
    regions_summary.csv          cobertura de cada región predefinida
    grid_cells_summary.csv       celdas 5°x5° con eventos suficientes
    data_quality_report.json     auditoría, pasos de limpieza y diagnósticos
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import (ANALYSIS_START, CATALOG_PARQUET, CELLS_CSV, MIN_EVENTS_CELL,  # noqa: E402
                    MIN_EXPECTED_PER_90D, PROCESSED_DIR, QUALITY_JSON, RAW_CSV, REGIONS_CSV)
from src.data_processing import (add_derived_variables, annual_counts,  # noqa: E402
                                 audit_raw_catalog, clean_catalog, load_raw_catalog,
                                 magtype_by_era, save_json)
from src.declustering import gardner_knopoff_decluster  # noqa: E402
from src.regions import PREDEFINED_REGIONS  # noqa: E402


def toponym(place):
    if not isinstance(place, str):
        return None
    return place.split(",")[-1].strip() if "," in place else place.split(" of ")[-1].strip()


def main():
    t0 = time.time()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Leyendo {RAW_CSV} ...")
    raw = load_raw_catalog(RAW_CSV)
    audit = audit_raw_catalog(raw)

    clean, steps = clean_catalog(raw)
    cat = add_derived_variables(clean)

    # Catálogo de trabajo (desde 1973)
    work = cat["in_analysis_period"].to_numpy()
    steps.append({"paso": "Periodo de análisis (catálogo de trabajo)",
                  "regla": f"time ≥ {ANALYSIS_START} (completitud temporal)",
                  "filas": int(work.sum()), "eliminadas": int((~work).sum())})

    print("Declustering Gardner-Knopoff (puede tardar ~1 min) ...")
    sub = cat.loc[work]
    dep, clus = gardner_knopoff_decluster(sub["t_days"].to_numpy(), sub["latitude"].to_numpy(),
                                          sub["longitude"].to_numpy(), sub["mag"].to_numpy())
    cat["gk_dependent"] = False
    cat["gk_cluster"] = -1
    cat.loc[work, "gk_dependent"] = dep
    pos_to_id = sub["id"].to_numpy()
    cat.loc[work, "gk_mainshock_id"] = np.where(clus >= 0, pos_to_id[np.clip(clus, 0, None)], None)
    cat.loc[work, "gk_cluster"] = clus
    cat["gk_mainshock_id"] = cat["gk_mainshock_id"].astype(object)

    cat.to_parquet(CATALOG_PARQUET, index=False)

    # ---------------- regiones predefinidas ----------------
    w = cat[work]
    years = (w["time"].max() - pd.Timestamp(ANALYSIS_START, tz="UTC")).days / 365.25
    rows = []
    for name, (boxes, context) in PREDEFINED_REGIONS.items():
        r = w[w["region"] == name]
        rate = len(r) / years
        rows.append({"region": name, "n_eventos": len(r), "eventos_por_año": round(rate, 2),
                     "esperados_90d": round(rate * 90 / 365.25, 2),
                     "habilitada": rate * 90 / 365.25 >= MIN_EXPECTED_PER_90D,
                     "fraccion_dependiente_GK": round(r["gk_dependent"].mean(), 3) if len(r) else np.nan,
                     "n_cajas": len(boxes), "contexto": context})
    regions = pd.DataFrame(rows)
    regions.to_csv(REGIONS_CSV, index=False)

    # ---------------- celdas de malla ----------------
    names = (w.assign(top=w["place"].map(toponym)).dropna(subset=["top"])
             .groupby("cell")["top"].agg(lambda s: s.value_counts().index[0]))
    cells = w.groupby("cell").size().rename("n_eventos").reset_index()
    cells = cells[cells["n_eventos"] >= MIN_EVENTS_CELL].copy()
    cells["nombre"] = cells["cell"].map(names).fillna("sin nombre")
    cells["lat0"] = cells["cell"].str.split("|").str[0].astype(int)
    cells["lon0"] = cells["cell"].str.split("|").str[1].astype(int)
    cells = cells.sort_values(["nombre", "cell"])
    cells.to_csv(CELLS_CSV, index=False)

    # ---------------- reporte de calidad ----------------
    report = {
        "fuente": "CSV con formato del catálogo ComCat del USGS (columnas estándar de la API FDSN). "
                  "El archivo se recibió como 'Significant_Earthquakes.csv'; la consulta exacta de "
                  "descarga no está documentada en el archivo.",
        "raw_audit": audit,
        "cleaning_steps": steps,
        "catalog_end_utc": str(cat["time"].max()),
        "analysis_start": ANALYSIS_START,
        "n_clean_all_years": int(len(cat)),
        "n_working": int(work.sum()),
        "annual_counts": annual_counts(cat),
        "magtype_by_era_pct": magtype_by_era(cat),
        "working_missing_pct": (w[["latitude", "longitude", "depth", "mag", "magType", "place"]]
                                .isna().mean().mul(100).round(3).to_dict()),
        "working_fixed_depth_pct": round(float(w["fixed_depth"].mean() * 100), 2),
        "working_depth_class_pct": w["depth_class"].value_counts(normalize=True).mul(100).round(2).to_dict(),
        "working_mw_family_pct": round(float(w["is_mw_family"].mean() * 100), 2),
        "working_mag_range": [float(w["mag"].min()), float(w["mag"].max())],
        "working_depth_range": [float(w["depth"].min()), float(w["depth"].max())],
        "working_two_decimal_mag_pct": round(float((np.abs(w["mag"] * 10 - np.round(w["mag"] * 10)) > 1e-6).mean() * 100), 2),
        "declustering": {
            "method": "Gardner & Knopoff (1974), ventana simétrica",
            "n_dependent": int(w["gk_dependent"].sum()),
            "pct_dependent": round(float(w["gk_dependent"].mean() * 100), 2),
        },
        "regions_enabled": int(regions["habilitada"].sum()),
        "regions_total": int(len(regions)),
        "pct_working_in_enabled_regions": round(float(w["region"].isin(regions.loc[regions["habilitada"], "region"]).mean() * 100), 2),
        "n_cells_available": int(len(cells)),
        "pct_working_in_cells": round(float(w["cell"].isin(cells["cell"]).mean() * 100), 2),
    }
    save_json(report, QUALITY_JSON)

    print(f"Catálogo limpio: {len(cat):,} eventos | trabajo (≥{ANALYSIS_START[:4]}): {work.sum():,}")
    print(f"Dependientes GK: {report['declustering']['pct_dependent']} %")
    print(f"Regiones habilitadas: {report['regions_enabled']} de {report['regions_total']}")
    print(f"Celdas disponibles: {len(cells)}")
    print(f"Listo en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
