### Sismicidad
La sismicidad es la distribución de los terremotos en el espacio y el tiempo. En escala global se concentra en los límites de placas: zonas de subducción, dorsales, fallas transformantes y zonas de colisión continental.

### Magnitud y profundidad
La **magnitud** mide el tamaño de un sismo en escala logarítmica. El catálogo mezcla varias escalas:

- *Mw*: magnitud de momento, la más robusta.
- *mb*: ondas de cuerpo; se satura cerca de 6.
- *Ms*: ondas superficiales.

Las escalas no son completamente equivalentes, y su proporción en el catálogo cambia con el tiempo.

La **profundidad** del hipocentro se clasifica en tres grupos:

- superficial (< 70 km);
- intermedia (70–300 km);
- profunda (> 300 km).

Valores repetidos como 10 y 33 km suelen ser profundidades fijadas por el sistema de localización, no profundidades medidas.

### Energía sísmica
La magnitud no es aditiva: dos sismos M 6 no equivalen a un M 12. La energía radiada sí lo es, y se estima con la relación de Gutenberg y Richter (1956):

$$\log_{10} E\,[\mathrm{J}] = 1.5\,M + 4.8$$

Cada unidad de magnitud multiplica la energía por unos 32. Por eso la energía de un periodo la domina su evento mayor. Esta relación es una aproximación: fue calibrada con Ms y, para Mw, coincide con $E \approx M_0 / 2\times10^4$ (Kanamori, 1977).

### Frecuencia de eventos y Gutenberg-Richter
El número de eventos con magnitud ≥ M sigue aproximadamente la relación $\log_{10} N(\ge M) = a - bM$, con $b \approx 1$. Por eso, en cualquier periodo, los sismos pequeños son mucho más numerosos que los grandes.

### Catálogos sísmicos y completitud
Un catálogo es *completo* por encima de la magnitud a partir de la cual se detectan todos los eventos. La red mundial mejoró con el tiempo: este catálogo es comparable para M ≥ 5 desde 1973 (inicio del catálogo PDE del USGS). Cualquier tendencia que se observe puede deberse en parte a cambios en la detección y en las escalas de magnitud.

### Series de tiempo
Una serie de tiempo es una secuencia de observaciones ordenadas en el tiempo. Aquí se construyen agregando eventos por periodos de calendario. La **resolución temporal** es una decisión de análisis:

- una resolución fina (días) da muchos periodos con pocos eventos o ninguno;
- una resolución gruesa (años) da pocos datos para estimar estructura temporal.

### Estacionariedad
Una serie es (débilmente) estacionaria si su media, su varianza y su autocorrelación no cambian en el tiempo. Se evalúa con dos pruebas de hipótesis opuestas:

- **ADF** (Dickey-Fuller aumentada). H₀: hay raíz unitaria, es decir, la serie no es estacionaria.
- **KPSS**. H₀: la serie es estacionaria en nivel.

Usarlas juntas permite distinguir cuatro casos:

- ADF rechaza y KPSS no rechaza: la serie es estacionaria.
- ADF no rechaza y KPSS rechaza: no es estacionaria.
- Las dos rechazan: la serie es estacionaria alrededor de cambios de nivel o tiene memoria larga.
- Ninguna rechaza: los datos no son concluyentes.

### Tendencia y estacionalidad
La **tendencia** es el cambio de largo plazo. Se evalúa con la prueba no paramétrica de **Mann-Kendall** y se cuantifica con la **pendiente de Sen**; ninguna de las dos es una regresión. La prueba supone independencia, así que con autocorrelación positiva su p-valor es optimista.

La **estacionalidad** es un patrón que se repite con periodo fijo, por ejemplo un ciclo anual. Se explora con la descomposición **STL** (Cleveland et al., 1990) y con la prueba de Kruskal-Wallis entre meses del año. Para la sismicidad tectónica no se espera estacionalidad física, así que su ausencia es un resultado esperable.

### Autocorrelación
- La **función de autocorrelación (ACF)** mide la correlación entre la serie y la misma serie desplazada k periodos.
- La **autocorrelación parcial (PACF)** mide esa misma correlación descontando los rezagos intermedios.

Las bandas ±1.96/√n indican qué valores serían compatibles con ruido blanco. En los catálogos sísmicos, la autocorrelación positiva refleja secuencias de réplicas que se extienden durante varios periodos.

### Agrupamiento temporal
Si los sismos ocurrieran al azar (proceso de Poisson), los tiempos entre eventos seguirían una distribución exponencial, con coeficiente de variación CV = 1, y la varianza de los conteos sería igual a su media (índice de dispersión φ = 1). Valores CV > 1 y φ > 1 indican agrupamiento.

El *declustering* de Gardner y Knopoff (1974) separa los eventos principales de las réplicas y los premonitores usando ventanas de distancia y tiempo que crecen con la magnitud.

### Detección de anomalías y cambios de régimen
- Una **anomalía** es un periodo cuyo valor se aparta de su historial reciente. Aquí se mide con un z robusto respecto a la mediana y la MAD de los periodos anteriores, y se marca cuando |z| > 3.5 (Iglewicz y Hoaglin, 1993).
- Un **cambio de régimen** es un cambio persistente en el nivel medio. Se detecta por segmentación binaria con penalización BIC.

### Modelos de series de tiempo
- **Suavizamiento exponencial simple (SES):** el pronóstico es un promedio ponderado de las observaciones pasadas, con pesos que decrecen geométricamente según el parámetro α.
- **ARIMA(p,d,q):** combina autorregresión (p), diferenciación (d) y medias móviles (q). Supone una serie estacionaria (después de diferenciar) y residuos que sean ruido blanco.
- **Modelos de conteo:** la Binomial Negativa describe conteos con varianza mayor que la media.

Todo modelo se compara con referencias simples (último valor, media histórica) mediante validación temporal: se entrena con el pasado y se evalúa con el periodo más reciente. Las métricas son MAE, RMSE y MASE; un MASE < 1 significa mejor que el pronóstico ingenuo.

### Pronóstico de frecuencia ≠ predicción de terremotos
Pronosticar cuántos eventos se esperan en promedio en un mes, con un intervalo de incertidumbre, es una descripción estadística de la tasa de actividad. **No indica cuándo, dónde ni con qué magnitud ocurrirá un sismo.**
