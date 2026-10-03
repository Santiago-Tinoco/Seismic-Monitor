# Monitor de Actividad Sísmica

Plataforma interactiva para evaluar si la actividad sísmica reciente de una región presenta desviaciones
estadísticamente significativas respecto a su propio comportamiento histórico.

> Esta herramienta identifica desviaciones estadísticas respecto al historial sísmico. **No predice terremotos**
> ni estima la probabilidad de que ocurran. Un percentil alto indica que la ventana reciente supera a la mayoría
> de las ventanas históricas comparables; no es una probabilidad de sismo.

---

## 1. Instalación

Requiere Python 3.10 o superior (probado con 3.13).

### 1. Descargar este repositorio como .zip

### 2. Descomprimir el archivo .zip en una carpeta llamada "monitor_sismico" y copie la ruta de esta carpeta

### 3. Abra Anaconda Powershell Prompt y corra el siguiente codigo

```bash
cd "C:/ruta/hasta/monitor_sismico"
conda create -n seismic_monitor python=3.13
conda activate seismic_monitor
pip install -r requirements.txt
```

## 2. Ejecución

```bash
python scripts/build_catalog.py
python app.py
python tests/test_methods.py      # validación de los métodos (o: python -m pytest tests -q)
```

Una vez ya haya corrido "python scripts/build_catalog.py" por primera vez, cada que vuelva a iniciar la
aplicación no es necesario volverlo a correr, simplemente corra:

```bash
conda activate seismic_monitor
python app.py
```

## 3. Estructura

```
seismic_monitor/
├── app.py                       UI: layout, callbacks y descargas
├── config.py                    todos los parámetros metodológicos (ventanas, umbrales, paleta)
├── requirements.txt
├── data/
│   ├── raw/Significant_Earthquakes.csv     original, nunca se modifica
│   └── processed/                          generado por scripts/build_catalog.py
│       ├── catalog_clean.parquet           catálogo limpio + variables derivadas + declustering
│       ├── regions_summary.csv             cobertura de las regiones predefinidas
│       ├── grid_cells_summary.csv          celdas 5°×5° con ≥ 60 eventos
│       └── data_quality_report.json        auditoría y pasos de limpieza
├── scripts/build_catalog.py     DATA → PROCESSING
├── src/
│   ├── data_processing.py       carga, auditoría, limpieza, variables derivadas
│   ├── regions.py               regiones predefinidas y malla 5°×5°
│   ├── declustering.py          Gardner-Knopoff (1974)
│   ├── seismic_analysis.py      energía, Gutenberg-Richter, Mc (MBS), b-value, test de b
│   ├── statistics.py            ventanas, percentiles, Poisson/Binomial Negativa, FDR
│   ├── clustering.py            CV de tiempos entre eventos, vecino más cercano
│   └── anomaly_detection.py     motor: actual vs. ventanas históricas, sensibilidad, comparación regional
├── components/
│   ├── theme.py                 plantilla Plotly
│   ├── charts.py, maps.py       figuras
│   ├── kpis.py, tables.py       cifras clave y tablas
│   ├── help_texts.py            glosario de ayudas emergentes
│   ├── layout.py                encabezado, panel de control, pestañas
│   └── pages.py                 contenido de cada sección (incluye metodología y limitaciones)
├── assets/style.css, assets/topojson/
└── tests/test_methods.py
```

Flujo: `DATA → PROCESSING (build_catalog) → STATISTICS (statistics, seismic_analysis, clustering) →
ANOMALY ENGINE (anomaly_detection) → VISUALIZATION (components) → UI (app.py)`.

## 4. Dataset

`data/raw/Significant_Earthquakes.csv`: 115.493 filas, 22 columnas del formato CSV del catálogo ComCat del USGS
(más una columna de índice exportada), de 1900-10-09 a 2026-08-22, con solo M ≥ 5.0.

| Paso de limpieza | Filas | Eliminadas |
|---|---|---|
| Archivo original | 115.493 | — |
| Solo `type == earthquake` | 115.001 | 492 |
| Un registro por `id` (la revisión con `updated` más reciente) | 102.307 | 12.694 |
| Catálogo de trabajo: desde 1973-01-01 | 86.693 | 15.614 |

Además: las fechas se convierten a UTC y se ordenan; las magnitudes se binnean a 0.1; la profundidad faltante no se
imputa (las métricas de profundidad usan solo valores observados); `nst`, `gap`, `dmin`, `rms` y las columnas de
error no se usan (25–71 % de faltantes).

## 5. Parámetros (panel izquierdo)

| Control | Opciones | Afecta a |
|---|---|---|
| Unidad espacial / región | 25 regiones predefinidas o 233 celdas 5°×5° | todo excepto la comparación regional |
| Ventana reciente | 7, 30, 90, 180, 365, 730 días | estado, actividad, mapa, línea base, anomalías, comparación regional, eventos |
| Inicio de la línea base | 1973, 1980, 1990, 2000 | todas las comparaciones |
| Magnitud mínima | 5.0–7.0 | todo (en b-value actúa como piso de Mc) |
| Profundidad | 0–700 km | todo |
| Escalas | todas / solo familia Mw | todo |
| Catálogo | completo (por defecto) / desclusterizado | tasa, magnitud, energía, profundidad y b-value. El agrupamiento temporal y espacial usa siempre el catálogo completo |
| Periodo de b | 2, 5, 10 años | solo magnitud-frecuencia |

Cada sección muestra una etiqueta con el catálogo que utiliza. La tabla completa de qué filtro afecta a cada
componente está en la pestaña *Datos y método*.

## 6. Metodología (resumen)

- **Regiones:** cajas lat/lon trazadas sobre cinturones sísmicos continuos visibles en el catálogo, sin
  superposición. Se habilitan las que tienen ≥ 2 eventos esperados por ventana de 90 días (25 de 26; Nueva Zelanda
  queda fuera). Cubren el 80.8 % de los eventos; las celdas 5°×5° cubren el 89.4 %.
- **Línea base:** ventanas de igual duración W, móviles con paso max(1, ⌊W/10⌋) días, desde el año de inicio
  elegido hasta el comienzo de la ventana reciente. La ventana reciente termina en el último evento del catálogo.
- **Percentil empírico** (rango medio): P = 100·[#(x<v) + 0.5·#(x=v)]/n.
- **Conteos:** Binomial Negativa (o Poisson si no hay sobredispersión) ajustada por momentos sobre ventanas sin
  solapamiento, que da P(N ≥ n) y P(N ≤ n).
- **Energía:** log10 E[J] = 1.5M + 4.8 (Gutenberg & Richter, 1956; es una aproximación).
- **Mc:** estabilidad del b-value (MBS), buscando desde 5.0.
- **b-value:** máxima verosimilitud de Aki-Utsu con corrección por binning, σ de Shi-Bolt, bootstrap del 95 %, n ≥ 50.
  La diferencia entre periodos se evalúa con un test de razón de verosimilitudes (equivalente al de Utsu).
- **Agrupamiento:** fracción de eventos en secuencias (Gardner-Knopoff), CV de los tiempos entre eventos y distancia
  mediana al vecino más cercano. Siempre con el catálogo completo.
- **Anomalía (definición operacional):** fuera de P5–P95 = inusual; fuera de P1–P99 = muy inusual. El estado general
  usa solo la tasa de eventos.
- **Comparación regional:** cada región contra su propio historial, ordenadas geográficamente, con q-valores de
  Benjamini-Hochberg.
- **No se implementa** índice compuesto ni machine learning (la justificación está en la app).

Las ecuaciones completas están en la pestaña *Datos y método → Metodología*.

## 7. Validación

`tests/test_methods.py` comprueba:

1. el estimador de b recupera b conocidos (0.8, 1.0 y 1.3) en catálogos sintéticos de Gutenberg-Richter;
2. MBS detecta Mc ≥ 5.3 cuando se eliminan eventos pequeños;
3. el test de b no rechaza muestras iguales y sí rechaza b distintos;
4. la energía se suma de forma lineal;
5. el percentil de rango medio funciona en casos conocidos;
6. los conteos por ventana coinciden con un cálculo por fuerza bruta y nunca se solapan con la ventana reciente;
7. la cola del modelo de conteos coincide con la Poisson teórica;
8. FDR;
9. el declustering marca réplicas cercanas y no eventos lejanos;
10. el percentil del catálogo real coincide con un recálculo independiente.

Comprobación manual sugerida: descargar *ventanas históricas (CSV)* y recalcular el percentil en Excel con
`(CONTAR.SI(<actual) + 0.5·CONTAR.SI(=actual)) / n`.

## 8. Limitaciones

- Una anomalía estadística no implica causalidad ni permite predecir un terremoto.
- El catálogo solo tiene M ≥ 5.0 y antes de 1973 es incompleto.
- Las escalas de magnitud se mezclan y su composición cambió con el tiempo (ms y mwc → mww y mb). Esto afecta los
  conteos cerca de M 5.0 y el b-value.
- El 43 % de las profundidades son fijas (10, 33 o 35 km).
- En ventanas cortas hay pocos eventos y la app lo advierte. El b-value necesita ≥ 50 eventos.
- Gardner-Knopoff marca como dependiente el 58 % del catálogo de trabajo: en cinturones de alta tasa con M ≥ 5
  sobreestima las secuencias. Por eso es opcional y siempre se compara contra la misma región.
- Las ventanas móviles se solapan y hay autocorrelación temporal por las réplicas.
- Las cajas regionales son una decisión de análisis; la sección de sensibilidad muestra la dependencia de la
  ventana y de la magnitud mínima.
- Computacionalmente: los resultados se cachean en memoria (`lru_cache`), así que la primera consulta de cada
  combinación tarda ≈0.1–0.5 s. La app está pensada para uso local o académico, no para muchos usuarios
  simultáneos.

## 9. Actualizar el catálogo

Reemplace `data/raw/Significant_Earthquakes.csv` por una descarga más reciente con las mismas columnas (por ejemplo,
de la API FDSN del USGS con `minmagnitude=5`) y vuelva a ejecutar `python scripts/build_catalog.py`. La línea base y
la ventana reciente se recalculan solas a partir de la nueva fecha final.
