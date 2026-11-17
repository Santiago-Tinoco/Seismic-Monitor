# Sismicidad en el Tiempo — App Dash (Python)

Aplicación Dash del análisis de series de tiempo de terremotos. La documentación general (cambios, decisiones de
análisis, comparación con Shiny y despliegue) está en `../README.md`.

## Ejecutar

```bash
pip install -r requirements.txt
python scripts/build_catalog.py     # genera data/processed/ (≈10 s)
python app.py                       # http://127.0.0.1:8050
python tests/test_methods.py        # pruebas de los métodos sismológicos
```

## Estructura

```
app.py                     navegación lateral (11 secciones con URL), filtros, callbacks y descargas
config.py                  parámetros del motor de ventanas (heredado)
shared/                    copia de ../shared: params.json, regiones, textos, enlaces, equipo
scripts/build_catalog.py   limpieza + declustering → data/processed/
src/timeseries.py          agregación y pruebas de series de tiempo (réplica: shiny_app/R/timeseries.R)
src/forecasting.py         modelos y validación temporal (réplica: shiny_app/R/models.R)
src/analysis_cache.py      caché por combinación de filtros
src/seismic_analysis.py    energía, Gutenberg-Richter, Mc, b-value
src/anomaly_detection.py   monitor de ventana reciente (heredado; en la sección Modelos)
src/data_processing.py, regions.py, declustering.py, clustering.py, statistics.py
components/sections.py     contenido de las 11 secciones
components/ts_charts.py    gráficos de EDA y series de tiempo
components/pages.py, charts.py, maps.py, tables.py, kpis.py, theme.py   componentes heredados reutilizados
assets/                    style.css, vendor/bootstrap-icons (iconos sin internet), topojson (mapas sin internet)
Procfile, app.yaml         despliegue (Render/Heroku o Google App Engine)
```

## Desplegar

- **Google App Engine:** `python scripts/build_catalog.py && gcloud app deploy app.yaml`
- **Render/Railway/Heroku:** conectar el repositorio. El `Procfile` construye los datos y arranca `gunicorn app:server`.

Las variables de entorno `PORT`, `HOST` y `DASH_DEBUG` son opcionales.
