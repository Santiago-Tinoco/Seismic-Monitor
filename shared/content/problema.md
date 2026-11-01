### Planteamiento del problema

Los catálogos sísmicos acumulan décadas de registros, pero su lectura directa no muestra si la actividad cambia con el tiempo, si tiene patrones repetitivos o si un periodo reciente es inusual. Además, los eventos no son independientes: las réplicas producen ráfagas de actividad que violan los supuestos de los métodos estadísticos más simples. Por eso hace falta un análisis que trate el catálogo como una serie de tiempo y que tenga en cuenta su estructura.

### Pregunta de investigación

¿Cómo ha evolucionado en el tiempo la actividad sísmica registrada (M ≥ 5) entre 1973 y 2026? ¿Presenta tendencia, estacionalidad, dependencia temporal, agrupamientos o anomalías? ¿Es posible pronosticar estadísticamente la frecuencia mensual de eventos mejor que un modelo de referencia?

### Objetivo general

Analizar el comportamiento temporal de la actividad sísmica registrada en el catálogo USGS M ≥ 5 (1973–2026) mediante análisis exploratorio, pruebas de series de tiempo y modelos de pronóstico de conteos, a escala global y regional.

### Objetivos específicos

1. Depurar el catálogo y documentar su calidad: duplicados, completitud temporal, faltantes y escalas de magnitud.
2. Caracterizar la distribución de magnitudes, profundidades y frecuencia de eventos (EDA univariado y multivariado).
3. Construir series de tiempo diarias, semanales, mensuales y anuales, y justificar la resolución adecuada para cada análisis.
4. Evaluar la tendencia, la estacionalidad, la estacionariedad, la autocorrelación y el agrupamiento temporal de las series.
5. Detectar periodos anómalos y cambios de régimen con criterios estadísticos explícitos.
6. Comparar modelos de pronóstico del número mensual de eventos con validación temporal y modelos de referencia.
7. Implementar los análisis en dos aplicaciones equivalentes (Dash y Shiny) y verificar que producen los mismos resultados.

### Justificación

Conocer la variabilidad temporal "normal" de la sismicidad es la base para reconocer cuándo un periodo se aparta de ella, y para cuantificar la incertidumbre de cualquier estimación de frecuencia. El enfoque de series de tiempo sustituye al de regresión porque la variable de interés es el propio proceso temporal de los eventos, no la relación entre variables independientes. Implementar el mismo análisis en Python y R permite comprobar que los resultados no dependen de la herramienta.
