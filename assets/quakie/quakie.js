/* Quakie — asistente de ayuda de "Sismicidad en el Tiempo".
 *
 * Mismo archivo en Dash (assets/) y en Shiny (www/). Funciona solo en el navegador, sin API externa ni modelo de
 * IA: responde con una base de conocimiento local escrita a partir de la documentación del proyecto (README,
 * textos de shared/content y la propia interfaz). No calcula ni inventa estadísticas: para resultados concretos
 * remite a la sección correspondiente, donde las cifras dependen de los filtros aplicados.
 *
 * Se monta fuera del árbol de Dash/Shiny (en <body>), así que no interfiere con callbacks ni salidas reactivas.
 * La app indica su tipo y el equipo en un elemento oculto #quakie-ctx (data-app, data-team, data-inst).
 */
(function () {
  "use strict";
  if (window.__quakieLoaded) return;
  window.__quakieLoaded = true;

  // ---------------------------------------------------------------- secciones y navegación
  var SECTIONS = {
    inicio:      { name: "Inicio",                       dash: "/",                shiny: "inicio" },
    introduccion:{ name: "Introducción",                 dash: "/introduccion",    shiny: "introduccion" },
    problema:    { name: "Problema y Objetivos",         dash: "/problema",        shiny: "problema" },
    marco:       { name: "Marco Teórico",                dash: "/marco-teorico",   shiny: "marco" },
    eda_uni:     { name: "EDA Univariado",               dash: "/eda-univariado",  shiny: "eda_uni" },
    eda_multi:   { name: "EDA Multivariado",             dash: "/eda-multivariado",shiny: "eda_multi" },
    series:      { name: "Análisis de Series de Tiempo", dash: "/series",          shiny: "series" },
    modelos:     { name: "Modelos",                      dash: "/modelos",         shiny: "modelos" },
    predecir:    { name: "Predecir",                     dash: "/predecir",        shiny: "predecir" },
    enlaces:     { name: "Enlaces",                      dash: "/enlaces",         shiny: "enlaces" },
    equipo:      { name: "Equipo",                       dash: "/equipo",          shiny: "equipo" }
  };

  function ctx() {
    var el = document.getElementById("quakie-ctx");
    var team = [];
    try { team = JSON.parse((el && el.getAttribute("data-team")) || "[]"); } catch (e) { team = []; }
    return { app: (el && el.getAttribute("data-app")) || (window.Shiny ? "shiny" : "dash"),
             team: team, inst: (el && el.getAttribute("data-inst")) || "" };
  }

  function goTo(key) {
    var s = SECTIONS[key]; if (!s) return;
    var el = ctx().app === "shiny" ? document.getElementById("nav_" + s.shiny)
                                   : document.querySelector('.side-nav a[href="' + s.dash + '"]');
    if (el) el.click();
  }

  function currentSection() {
    if (ctx().app === "shiny") {
      var a = document.querySelector(".side-nav .nav-link.active");
      return a && a.id ? a.id.replace(/^nav_/, "") : "inicio";
    }
    var path = window.location.pathname || "/";
    for (var k in SECTIONS) if (SECTIONS[k].dash === path) return k;
    return "inicio";
  }

  // ---------------------------------------------------------------- respuestas
  // Cada intención: palabras clave (sin tildes, en minúsculas), respuesta (HTML) y secciones a las que puede llevar.
  var EDA_TXT = "<p><b>EDA</b> significa <b>Análisis Exploratorio de Datos</b>: describir los datos con estadísticas y " +
    "gráficos antes de modelarlos, para conocer su forma, sus valores atípicos y sus relaciones.</p>" +
    "<ul><li><b>EDA Univariado</b>: una variable a la vez (distribución de la magnitud, la profundidad, los tiempos " +
    "entre eventos y los eventos por periodo; estadística descriptiva y atípicos de Tukey).</li>" +
    "<li><b>EDA Multivariado</b>: relaciones entre variables (profundidad frente a magnitud, magnitud por clase de " +
    "profundidad, Gutenberg-Richter, mapa y correlaciones entre las series mensuales).</li></ul>";

  var INTENTS = [
    { id: "saludo", kw: ["hola", "buenas", "buenos dias", "buenas tardes", "hey", "saludos", "que tal"],
      a: "<p>¡Hola! 🐾 Pregúntame por las secciones, los filtros, los gráficos o los conceptos del análisis " +
         "(series de tiempo, autocorrelación, pronóstico, magnitud…).</p>" },
    { id: "gracias", kw: ["gracias", "genial", "perfecto", "excelente", "muy bien", "listo"],
      a: "<p>¡Con gusto! Si te surge otra duda sobre la plataforma, aquí estoy. 🐾</p>" },
    { id: "quien", kw: ["quien eres", "que eres", "como te llamas", "eres un bot", "quakie"],
      a: "<p>Soy <b>Quakie</b>, el asistente de esta plataforma. Respondo preguntas sencillas sobre cómo usarla y " +
         "sobre los conceptos del análisis. Mis respuestas salen de la documentación del proyecto: no calculo " +
         "resultados nuevos ni hago predicciones de terremotos.</p>" },
    { id: "proyecto", kw: ["que es este proyecto", "de que trata", "proyecto", "objetivo", "proposito", "para que sirve la plataforma",
                           "sismicidad en el tiempo", "pregunta de investigacion"],
      a: "<p><b>Sismicidad en el Tiempo</b> es una plataforma académica que analiza cómo cambia en el tiempo la " +
         "actividad sísmica registrada en el catálogo del USGS para sismos de magnitud M ≥ 5 entre 1973 y 2026.</p>" +
         "<p>Convierte el catálogo en <b>series de tiempo</b> y estudia su tendencia, estacionalidad, autocorrelación " +
         "y agrupamiento; detecta periodos anómalos y compara modelos de pronóstico del número mensual de eventos " +
         "contra modelos de referencia.</p><p>El mismo análisis está implementado en dos aplicaciones equivalentes: " +
         "Dash (Python) y Shiny (R).</p>",
      go: ["problema", "introduccion"] },
    { id: "funciona", kw: ["como funciona", "funciona", "como se usa", "como uso", "como utilizo la plataforma", "dashboard",
                           "plataforma", "empezar", "por donde empiezo", "tutorial", "guia"],
      a: "<p>Así se usa la plataforma:</p><ol style='margin:4px 0 6px;padding-left:18px'>" +
         "<li>Elige una sección en el <b>menú lateral</b> izquierdo.</li>" +
         "<li>En las secciones de análisis (EDA, Series, Modelos y Predecir) aparece arriba el <b>panel de filtros</b>: " +
         "región, fechas, magnitud mínima, profundidad, catálogo, resolución y variable.</li>" +
         "<li>Ajusta los filtros y pulsa <b>Aplicar filtros</b>: todas las tablas y gráficos se recalculan.</li>" +
         "<li>Cada bloque tiene un recuadro de <b>Interpretación</b> y, en varios casos, botones para descargar CSV.</li></ol>" +
         "<p>Pasa el cursor sobre los gráficos para ver valores; puedes hacer zoom y ocultar series desde la leyenda.</p>",
      go: ["inicio", "series"] },
    { id: "contenido", kw: ["que informacion", "informacion contiene", "que datos", "que contiene", "dataset", "conjunto de datos",
                            "catalogo", "columnas", "registros", "variables"],
      a: "<p>Los datos son el catálogo de sismos <b>M ≥ 5</b> del USGS (archivo <i>Significant_Earthquakes.csv</i>, " +
         "con las columnas estándar de ComCat: fecha y hora, latitud, longitud, profundidad, magnitud, tipo de " +
         "magnitud, lugar, red, estado, etc.).</p><p>Según la documentación del proyecto, el archivo tiene 115.493 " +
         "registros entre 1900 y agosto de 2026; tras la limpieza (fechas válidas, solo sismos, revisión más reciente " +
         "de cada id, coordenadas válidas) se analizan <b>86.693 sismos únicos desde 1973</b>, porque antes de ese año " +
         "el catálogo no es comparable.</p><p>A partir de ellos se construyen series de: número de eventos, magnitud " +
         "media y máxima, profundidad media y energía liberada.</p>",
      go: ["introduccion"] },
    { id: "navegar", kw: ["navegar", "secciones", "menu", "ir a", "cambiar de seccion", "moverme", "paginas", "donde esta"],
      a: "<p>Usa el <b>menú lateral</b>. Las secciones son:</p><ul>" +
         "<li><b>Inicio</b>: resumen e indicadores generales.</li>" +
         "<li><b>Introducción</b>, <b>Problema y Objetivos</b> y <b>Marco Teórico</b>: contexto y conceptos.</li>" +
         "<li><b>EDA Univariado</b> y <b>EDA Multivariado</b>: exploración de los datos.</li>" +
         "<li><b>Análisis de Series de Tiempo</b>: series, pruebas, autocorrelación y anomalías.</li>" +
         "<li><b>Modelos</b>: comparación de modelos con validación temporal.</li>" +
         "<li><b>Predecir</b>: pronóstico mensual con intervalos.</li>" +
         "<li><b>Enlaces</b> y <b>Equipo</b>.</li></ul><p>También puedo llevarte directamente:</p>",
      go: ["eda_uni", "series", "modelos", "predecir"] },
    { id: "eda", kw: ["eda", "analisis exploratorio", "exploratorio", "univariado", "multivariado"],
      a: EDA_TXT, go: ["eda_uni", "eda_multi"] },
    { id: "serie", kw: ["serie de tiempo", "series de tiempo", "serie temporal", "que significan las series", "series temporales",
                        "resolucion", "agregacion", "dia semana mes"],
      a: "<p>Una <b>serie de tiempo</b> es una secuencia de observaciones ordenadas en el tiempo. Aquí se construye " +
         "agregando los sismos por periodos de calendario (día, semana, mes o año) y calculando en cada periodo una " +
         "variable: número de eventos, magnitud media o máxima, profundidad media o energía.</p>" +
         "<p>La <b>resolución</b> es una decisión de análisis: con días hay muchos periodos vacíos; con años, pocos " +
         "datos. La sección de series recomienda la más fina con ≤ 10 % de periodos sin eventos y al menos 60 periodos. " +
         "Los modelos de pronóstico trabajan siempre con datos mensuales.</p>",
      go: ["series"] },
    { id: "magnitud", kw: ["magnitud", "escala", "richter", "mw", "mb", "ms", "que tan fuerte", "tamano del sismo"],
      a: "<p>La <b>magnitud</b> mide el tamaño de un sismo en una escala <b>logarítmica</b>: cada unidad de magnitud " +
         "equivale a unas 32 veces más energía liberada. Por eso un sismo M 7 libera mucha más energía que varios M 6.</p>" +
         "<p>El catálogo mezcla escalas: <b>Mw</b> (magnitud de momento, la más robusta), <b>mb</b> (ondas de cuerpo, se " +
         "satura cerca de 6) y <b>Ms</b> (ondas superficiales). La plataforma usa sismos de magnitud ≥ 5.</p>",
      go: ["marco", "eda_uni"] },
    { id: "profundidad", kw: ["profundidad", "hipocentro", "superficial", "intermedia", "profunda", "km"],
      a: "<p>La <b>profundidad</b> es la del hipocentro, en km. Se agrupa en superficial (&lt; 70 km), intermedia " +
         "(70–300 km) y profunda (&gt; 300 km). Valores repetidos como 10 o 33 km suelen ser profundidades fijadas por " +
         "el sistema de localización, no medidas. El filtro <b>Profundidad</b> permite limitar el rango.</p>",
      go: ["eda_uni", "eda_multi"] },
    { id: "energia", kw: ["energia", "julios", "joules", "energia liberada", "energia acumulada"],
      a: "<p>La <b>energía</b> radiada se estima con la relación de Gutenberg y Richter (1956): log₁₀ E [J] = 1.5 M + 4.8. " +
         "A diferencia de la magnitud, la energía sí se puede sumar, así que la energía de un periodo es la suma de la " +
         "de sus eventos. Como crece tanto con la magnitud, la de un periodo la domina su evento mayor: por eso el " +
         "gráfico de energía acumulada tiene saltos verticales.</p>",
      go: ["series"] },
    { id: "grafico", kw: ["interpreto", "interpretar", "como leo", "como se lee", "este grafico", "los graficos", "grafica", "graficos",
                          "que muestra", "que significa este", "leer el grafico"],
      a: function () { return chartHelp(currentSection()); } },
    { id: "filtros", kw: ["filtro", "filtros", "aplicar", "region", "fechas", "magnitud minima", "desclusterizado", "catalogo completo",
                          "variable", "resolucion", "como utilizo los filtros", "para que sirven los filtros"],
      a: "<p>Los <b>filtros</b> (arriba, en las secciones de análisis) definen qué sismos entran al análisis:</p><ul>" +
         "<li><b>Región</b>: global o una zona sísmica.</li><li><b>Fechas</b>: periodo analizado.</li>" +
         "<li><b>Magnitud mínima</b> y <b>Profundidad (km)</b>: umbrales de los eventos.</li>" +
         "<li><b>Catálogo</b>: completo o <i>desclusterizado</i> (sin réplicas ni premonitores, según Gardner-Knopoff).</li>" +
         "<li><b>Resolución</b>: día, semana, mes o año para las series.</li>" +
         "<li><b>Variable</b>: qué serie se analiza (número de eventos, magnitud, profundidad o energía). En Modelos y " +
         "Predecir se usa esa variable, siempre por mes.</li></ul>" +
         "<p>Los cambios se aplican al pulsar <b>Aplicar filtros</b>. Si los filtros dejan muy pocos eventos, la plataforma " +
         "lo indica en lugar de mostrar resultados vacíos.</p>" },
    { id: "acf", kw: ["autocorrelacion", "acf", "pacf", "correlacion parcial", "rezago", "rezagos", "lag", "memoria", "ruido blanco"],
      a: "<p>La <b>autocorrelación (ACF)</b> mide cuánto se parece la serie a sí misma desplazada k periodos (rezagos). " +
         "Valores positivos que decaen lentamente indican persistencia: en los sismos, las secuencias de réplicas " +
         "mantienen la actividad alta varios periodos.</p><p>La <b>autocorrelación parcial (PACF)</b> mide esa relación " +
         "descontando los rezagos intermedios. La <b>banda gris</b> (±1.96/√n) marca los valores compatibles con ruido " +
         "blanco: las barras que la superan indican dependencia temporal.</p>",
      go: ["series"] },
    { id: "pronostico", kw: ["pronostico", "pronosticar", "forecast", "predecir", "prediccion", "futuro", "proximo mes", "horizonte"],
      a: "<p>Un <b>pronóstico</b> es una estimación estadística del valor esperado de la serie en los próximos meses, con " +
         "intervalos de incertidumbre (80 % y 95 %). En <b>Predecir</b> eliges el modelo (ingenuo, media histórica, " +
         "suavizamiento exponencial simple o ARIMA(1,0,1)) y el horizonte (6, 12 o 24 meses).</p>" +
         "<p><b>Importante:</b> pronosticar la frecuencia de eventos no es predecir terremotos: no dice cuándo, dónde ni " +
         "con qué magnitud ocurrirá un sismo.</p>",
      go: ["predecir", "modelos"] },
    { id: "predecir_sismo", kw: ["predecir un terremoto", "proximo terremoto", "cuando temblara", "va a temblar", "habra un terremoto",
                                 "predecir terremotos", "cuando sera el proximo"],
      a: "<p>No. Ni esta plataforma ni ningún método actual puede predecir <b>cuándo, dónde y con qué magnitud</b> " +
         "ocurrirá un terremoto. Lo que hace la sección Predecir es describir estadísticamente cuántos eventos se esperan " +
         "en promedio por mes, con su incertidumbre. Para información oficial sobre amenaza sísmica, consulta al " +
         "servicio geológico de tu país.</p>" },
    { id: "modelos", kw: ["modelo", "modelos", "arima", "ses", "suavizamiento", "ingenuo", "media historica", "binomial", "mase",
                          "mae", "rmse", "validacion", "metricas", "mejor modelo"],
      a: "<p>La sección <b>Modelos</b> compara cuatro modelos de series de tiempo para la variable elegida, agregada por mes:</p><ul>" +
         "<li><b>Ingenuo</b>: repite el último mes (referencia).</li>" +
         "<li><b>Media histórica</b>: promedio del entrenamiento; para conteos, intervalos de una Binomial Negativa.</li>" +
         "<li><b>Suavizamiento exponencial simple (SES)</b>: pondera más los meses recientes.</li>" +
         "<li><b>ARIMA(1,0,1)</b>: recoge la autocorrelación de corto plazo.</li></ul>" +
         "<p>Se entrena con el pasado y se evalúa con los últimos 36 meses. Métricas: MAE, RMSE y <b>MASE</b> " +
         "(MASE &lt; 1 significa mejor que el pronóstico ingenuo). No se usan regresiones: la información está en la " +
         "historia de la propia serie.</p>",
      go: ["modelos"] },
    { id: "sin_resultados", kw: ["no aparece", "no me aparece", "no aparecen", "aparece", "no veo", "no sale", "no hay resultados", "sin resultados", "no muestra", "vacio", "no se pueden ajustar",
                                 "error", "no funciona", "no carga", "muy pocos eventos", "demasiado corta"],
      a: "<p>Si un modelo no muestra resultados, la plataforma explica el motivo en un recuadro amarillo. Los casos son:</p><ul>" +
         "<li>El rango de fechas tiene menos de 72 meses completos (36 de prueba y 36 de entrenamiento).</li>" +
         "<li>Con los filtros quedan menos de 30 eventos: la serie mensual es casi toda ceros.</li>" +
         "<li>La variable elegida (magnitud, profundidad o energía) no existe en más del 5 % de los meses porque esos " +
         "meses no tienen eventos.</li></ul><p>Solución: amplía las fechas o la región, baja la magnitud mínima, amplía la " +
         "profundidad, usa el catálogo completo o elige <b>Número de eventos</b>. Si tras pulsar <b>Aplicar filtros</b> no ves " +
         "cambios, espera a que termine el indicador de carga.</p>" },
    { id: "estacionariedad", kw: ["estacionaria", "estacionariedad", "adf", "kpss", "raiz unitaria", "dickey"],
      a: "<p>Una serie es <b>estacionaria</b> si su media, su varianza y su autocorrelación no cambian en el tiempo. Se " +
         "evalúa con dos pruebas opuestas: <b>ADF</b> (hipótesis nula: hay raíz unitaria, no es estacionaria) y <b>KPSS</b> " +
         "(hipótesis nula: es estacionaria). La tabla de la sección de series indica la decisión al 5 % y el recuadro de " +
         "interpretación combina ambas.</p>",
      go: ["series"] },
    { id: "tendencia", kw: ["tendencia", "mann", "kendall", "sen", "estacionalidad", "stl", "kruskal", "ciclo anual", "aumenta"],
      a: "<p>La <b>tendencia</b> (cambio de largo plazo) se evalúa con la prueba no paramétrica de <b>Mann-Kendall</b> y se " +
         "cuantifica con la <b>pendiente de Sen</b>. La <b>estacionalidad</b> se explora con la descomposición <b>STL</b> y " +
         "la prueba de Kruskal-Wallis entre meses. Ojo: parte de una tendencia en conteos puede deberse a cambios en la red " +
         "de detección y en las escalas de magnitud.</p>",
      go: ["series"] },
    { id: "anomalias", kw: ["anomalia", "anomalias", "atipico", "inusual", "z robusto", "cambio de regimen", "regimen", "monitor"],
      a: "<p>Una <b>anomalía</b> es un periodo cuyo valor se aparta de su historial reciente: se calcula un z robusto con la " +
         "mediana y la MAD de los periodos anteriores y se marca cuando |z| &gt; 3.5 (rombos en el gráfico). Un <b>cambio de " +
         "régimen</b> es un cambio persistente del nivel medio (líneas oscuras por segmento). En <b>Modelos</b> está además " +
         "el monitor de ventana reciente, que compara la ventana actual con todas las ventanas históricas.</p>",
      go: ["series", "modelos"] },
    { id: "declustering", kw: ["replica", "replicas", "premonitor", "declustering", "desclusterizar", "gardner", "knopoff", "agrupamiento", "rafagas"],
      a: "<p>Tras un sismo grande vienen <b>réplicas</b>, así que los sismos llegan en ráfagas (agrupamiento). El " +
         "<i>declustering</i> de Gardner y Knopoff (1974) separa los eventos principales de réplicas y premonitores con " +
         "ventanas de distancia y tiempo que crecen con la magnitud. Elige <b>Catálogo: Desclusterizado (GK)</b> en los " +
         "filtros para analizar solo los eventos principales.</p>",
      go: ["series"] },
    { id: "gutenberg", kw: ["gutenberg", "b-value", "valor b", "frecuencia magnitud", "completitud", "mc"],
      a: "<p>La relación de <b>Gutenberg-Richter</b> dice que el número de sismos con magnitud ≥ M disminuye de forma " +
         "exponencial: log₁₀ N(≥ M) = a − b·M, con b cercano a 1. Por eso los sismos pequeños son mucho más numerosos que " +
         "los grandes. La estimación de b y de la magnitud de completitud (Mc) está en <b>EDA Multivariado</b>.</p>",
      go: ["eda_multi"] },
    { id: "datos", kw: ["donde puedo encontrar los datos", "donde estan los datos", "descargar", "fuente", "usgs", "comcat",
                        "csv", "enlaces", "bajar los datos", "origen de los datos"],
      a: "<p>Los datos provienen del catálogo <b>ComCat</b> del Servicio Geológico de los Estados Unidos (USGS). En la " +
         "sección <b>Enlaces</b> están la búsqueda del catálogo, el servicio web de eventos y el glosario de columnas.</p>" +
         "<p>Dentro de la plataforma puedes descargar en CSV las series, las estadísticas, los resultados de las pruebas, " +
         "la evaluación de modelos y los pronósticos con los botones <b>Descargar…</b> de cada sección.</p>" +
         "<p><a href='https://earthquake.usgs.gov/earthquakes/search/' target='_blank' rel='noopener'>Abrir el buscador del USGS ↗</a></p>",
      go: ["enlaces"] },
    { id: "equipo", kw: ["quienes", "desarrollaron", "autores", "equipo", "integrantes", "hicieron", "creadores", "universidad", "curso"],
      a: function () {
        var c = ctx();
        var names = c.team.length ? "<ul>" + c.team.map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("") + "</ul>" : "";
        return "<p>El proyecto fue desarrollado por:</p>" + names +
               (c.inst ? "<p>" + esc(c.inst) + "</p>" : "") + "<p>Los detalles están en la sección <b>Equipo</b>.</p>";
      },
      go: ["equipo"] },
    { id: "cifra", kw: ["cuantos sismos hubo", "cuantos terremotos hubo", "cuantos hubo", "cuantos eventos hubo", "cual fue el mayor",
                        "cual fue el terremoto mas", "cuantos sismos", "cuantos terremotos", "estadistica de", "dato exacto", "cifra"],
      a: "<p>No calculo cifras por mi cuenta, para no darte un número que no corresponda a tus filtros. Puedes obtenerlo " +
         "en la plataforma:</p><ol style='margin:4px 0 6px;padding-left:18px'><li>Elige la región, las fechas y la " +
         "magnitud mínima en los <b>filtros</b> y pulsa <b>Aplicar filtros</b>.</li><li>En <b>EDA Univariado</b> verás el " +
         "número de eventos y su estadística descriptiva; en <b>Series de Tiempo</b>, los valores por día, semana, mes o " +
         "año (también descargables en CSV).</li></ol>",
      go: ["eda_uni", "series"] },
    { id: "dash_shiny", kw: ["dash", "shiny", "python", "diferencia entre", "dos aplicaciones", "lenguaje"],
      a: "<p>El proyecto tiene dos aplicaciones equivalentes: <b>Dash</b> (Python) y <b>Shiny</b> (R). Usan el mismo " +
         "conjunto de datos, las mismas reglas de limpieza y los mismos parámetros, y una comparación funcional comprueba " +
         "que dan resultados equivalentes. Así se verifica que las conclusiones no dependen de la herramienta.</p>" },
    { id: "video", kw: ["video", "presentacion", "demostracion", "recorrido", "ver el video"],
      a: "<p>En <b>Inicio</b> está el <b>video de presentación</b> del proyecto: un recorrido por la plataforma narrado por " +
         "el equipo. Usa los controles del reproductor para pausarlo, adelantarlo o verlo a pantalla completa.</p>",
      go: ["inicio"] },
    { id: "kpi", kw: ["indicadores", "kpi", "tarjetas", "inicio", "resumen"],
      a: "<p>En <b>Inicio</b> hay indicadores generales del catálogo completo (sin filtros): número de sismos analizados, " +
         "promedio mensual, magnitud máxima, profundidad mediana, energía total estimada y porcentaje de eventos que forman " +
         "parte de secuencias. Debajo hay accesos directos a las secciones principales.</p>",
      go: ["inicio"] }
  ];

  var CHART_HELP = {
    inicio: "<p>En <b>Inicio</b> no hay gráficos de análisis: las tarjetas resumen el catálogo completo. Abre una sección de " +
            "análisis y vuelve a preguntarme para obtener ayuda con sus gráficos.</p>",
    eda_uni: "<p>En <b>EDA Univariado</b>:</p><ul><li><b>Histogramas y diagramas de caja</b>: la forma de la distribución; " +
             "los puntos fuera de los bigotes son atípicos según Tukey (en variables asimétricas son valores extremos " +
             "esperables, no errores).</li><li><b>Eventos por periodo</b>: si la varianza es mucho mayor que la media hay " +
             "sobredispersión (agrupamiento).</li><li><b>Tiempo entre eventos</b> (escala log₁₀): un coeficiente de variación " +
             "mayor que 1 indica que los sismos llegan en ráfagas.</li></ul>",
    eda_multi: "<p>En <b>EDA Multivariado</b>:</p><ul><li><b>Profundidad vs. magnitud</b>: la correlación de Spearman mide la " +
               "relación; con tantos datos, lo importante es su tamaño, no el p-valor.</li><li><b>Cajas por clase de " +
               "profundidad</b>: compara las medianas de magnitud.</li><li><b>Gutenberg-Richter</b>: puntos = número " +
               "acumulado de eventos con magnitud ≥ M (escala log); la recta indica el valor b.</li><li><b>Mapa</b>: tamaño = " +
               "magnitud, color = clase de profundidad.</li><li><b>Mapas de calor</b>: correlaciones entre series y actividad " +
               "por región y año; las franjas intensas de un solo año suelen ser secuencias de réplicas.</li></ul>",
    series: "<p>En <b>Series de Tiempo</b>:</p><ul><li><b>Serie</b>: gris = valor por periodo; línea azul = media móvil; " +
            "rombos = periodos anómalos.</li><li><b>Energía acumulada</b>: cada salto vertical es un sismo muy grande.</li>" +
            "<li><b>Cajas por década</b>: compara niveles entre décadas.</li><li><b>ACF/PACF</b>: barras fuera de la banda " +
            "gris indican dependencia temporal.</li><li><b>STL</b>: separa tendencia, estacionalidad y residuo.</li>" +
            "<li><b>Anomalías y cambios de régimen</b>: las líneas oscuras son el nivel medio de cada segmento.</li></ul>",
    modelos: "<p>En <b>Modelos</b>:</p><ul><li><b>Gráfico de evaluación</b>: la zona sombreada es el periodo de prueba, que " +
             "no se usa para ajustar; compara cada línea de color con la serie observada (negra).</li><li><b>Tabla</b>: " +
             "el mejor modelo es el de menor MASE; MASE &lt; 1 mejora al ingenuo. La cobertura ideal del IC95 es cercana " +
             "a 95 %.</li><li><b>ACF de residuos</b>: si las barras quedan dentro de la banda gris, el modelo captó la " +
             "dependencia temporal.</li></ul>",
    predecir: "<p>En <b>Predecir</b>:</p><ul><li>Línea negra: serie observada. Línea azul gruesa: pronóstico medio.</li>" +
              "<li>Bandas azules: intervalos del 80 % y 95 %; la incertidumbre está en su ancho.</li><li>Líneas punteadas " +
              "de colores: trayectorias simuladas (escenarios posibles, no predicciones).</li><li>Línea discontinua: media " +
              "histórica.</li><li>Usa los botones 3, 6, 15 años y Todo para cambiar la ventana.</li><li>El gráfico de " +
              "validación muestra cómo habría funcionado el modelo en los últimos 36 meses.</li></ul>" +
              "<p>Que el pronóstico sea casi plano es lo esperado en una serie sin tendencia ni estacionalidad marcadas.</p>"
  };
  ["introduccion", "problema", "marco", "enlaces", "equipo"].forEach(function (k) {
    CHART_HELP[k] = "<p>La sección <b>" + SECTIONS[k].name + "</b> es de texto y no tiene gráficos. Los gráficos están en " +
                    "EDA, Series de Tiempo, Modelos y Predecir.</p>";
  });
  function chartHelp(sec) {
    return (CHART_HELP[sec] || CHART_HELP.inicio) +
      "<p style='margin-top:6px'>Además, cada bloque tiene un recuadro de <b>Interpretación</b> escrito para los filtros aplicados.</p>";
  }

  var FALLBACK = "<p>No tengo información suficiente para responder eso con seguridad. 🐾 Puedo ayudarte con el " +
    "uso de la plataforma (secciones, filtros, gráficos, descargas) y con los conceptos del análisis (series de " +
    "tiempo, autocorrelación, modelos, pronóstico, magnitud, réplicas…).</p><p>Prueba con una de estas preguntas:</p>";

  var SUGGEST = ["¿Cómo funciona esta plataforma?", "¿Cómo interpreto los gráficos?",
                 "¿Qué significan las series de tiempo?", "¿Cómo utilizo los filtros?"];

  // ---------------------------------------------------------------- coincidencia de preguntas
  function norm(s) {
    return (" " + String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/[¿?¡!.,;:()"']/g, " ").replace(/\s+/g, " ") + " ");
  }
  function score(q, intent) {
    var sc = 0;
    intent.kw.forEach(function (k) {
      var kn = norm(k);
      if (q.indexOf(kn) >= 0) sc += 1 + (kn.trim().split(" ").length - 1) * 1.5;   // frases pesan más
      else if (kn.trim().length >= 6 && q.indexOf(" " + kn.trim()) >= 0) sc += 0.6; // prefijo (plural, etc.)
    });
    return sc;
  }
  function answer(text) {
    var q = norm(text), best = null, bestSc = 0;
    INTENTS.forEach(function (it) { var s = score(q, it); if (s > bestSc) { bestSc = s; best = it; } });
    if (!best || bestSc < 1) return { html: FALLBACK, chips: SUGGEST };
    return { html: typeof best.a === "function" ? best.a() : best.a, go: best.go || [] };
  }

  // ---------------------------------------------------------------- interfaz
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  // Personaje: una piedrita sonriente con una onda sísmica (sin imágenes externas).
  function avatar(cls) {
    return '<svg class="quakie-avatar ' + (cls || "") + '" viewBox="0 0 48 48" aria-hidden="true">' +
      '<circle cx="24" cy="24" r="23" fill="#fff"/>' +
      '<path d="M10 30c0-9 6-16 14-16s14 7 14 16c0 4-3 7-7 7H17c-4 0-7-3-7-7z" fill="#e9eef0" stroke="#1f5f74" stroke-width="2"/>' +
      '<circle cx="19.5" cy="26" r="2.1" fill="#1d262b"/><circle cx="28.5" cy="26" r="2.1" fill="#1d262b"/>' +
      '<circle cx="20.2" cy="25.3" r=".7" fill="#fff"/><circle cx="29.2" cy="25.3" r=".7" fill="#fff"/>' +
      '<path d="M21 31c1.8 1.6 4.2 1.6 6 0" fill="none" stroke="#1d262b" stroke-width="1.6" stroke-linecap="round"/>' +
      '<circle cx="16" cy="30" r="1.6" fill="#f2c9a0" opacity=".8"/><circle cx="32" cy="30" r="1.6" fill="#f2c9a0" opacity=".8"/>' +
      '<g class="qk-wave"><path d="M6 12h6l2.5-5 3 9 2.5-6 2 2h4" fill="none" stroke="#c4741c" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round"/></g></svg>';
  }

  function build() {
    if (document.querySelector(".quakie-root")) return;
    var root = document.createElement("div");
    root.className = "quakie-root";
    root.innerHTML =
      '<section class="quakie-panel" role="dialog" aria-label="Quakie, asistente de la plataforma" aria-hidden="true">' +
      '  <header class="quakie-head">' + avatar() +
      '    <div><div class="quakie-title">Quakie</div><div class="quakie-sub">Asistente de la plataforma</div></div>' +
      '    <button type="button" class="quakie-min" aria-label="Minimizar Quakie" title="Minimizar">–</button>' +
      '  </header>' +
      '  <div class="quakie-log" aria-live="polite"></div>' +
      '  <div class="quakie-form" role="group" aria-label="Escribir pregunta">' +
      '    <input class="quakie-input" type="text" maxlength="300" placeholder="Escribe tu pregunta…" aria-label="Pregunta para Quakie">' +
      '    <button class="quakie-send" type="button">Enviar</button>' +
      '  </div>' +
      '  <div class="quakie-foot">Respuestas basadas en la documentación del proyecto · no predice terremotos</div>' +
      '</section>' +
      '<button type="button" class="quakie-fab" aria-expanded="false" aria-label="Abrir Quakie, asistente de ayuda" title="Quakie · ayuda">' +
      avatar() + '<span class="quakie-fab-label">Quakie</span></button>';
    document.body.appendChild(root);

    var panel = root.querySelector(".quakie-panel"), log = root.querySelector(".quakie-log");
    var fab = root.querySelector(".quakie-fab"), input = root.querySelector(".quakie-input");
    var started = false;

    function scroll() { log.scrollTop = log.scrollHeight; }
    function addUser(t) { var d = document.createElement("div"); d.className = "qk-msg qk-user"; d.textContent = t; log.appendChild(d); }
    function addBot(html, go, chips) {
      var d = document.createElement("div"); d.className = "qk-msg qk-bot"; d.innerHTML = html;
      var acts = document.createElement("div"); acts.className = "qk-actions";
      (go || []).forEach(function (k) {
        if (!SECTIONS[k]) return;
        var b = document.createElement("button"); b.type = "button"; b.className = "qk-chip qk-go";
        b.textContent = "Ir a " + SECTIONS[k].name + " →"; b.addEventListener("click", function () { goTo(k); });
        acts.appendChild(b);
      });
      (chips || []).forEach(function (c) { acts.appendChild(chip(c)); });
      if (acts.children.length) d.appendChild(acts);
      log.appendChild(d); scroll();
    }
    function chip(text) {
      var b = document.createElement("button"); b.type = "button"; b.className = "qk-chip"; b.textContent = text;
      b.addEventListener("click", function () { ask(text); }); return b;
    }
    function ask(text) {
      text = String(text || "").trim(); if (!text) return;
      addUser(text);
      var r = answer(text);
      setTimeout(function () { addBot(r.html, r.go, r.chips); }, 180);
    }
    function open(state) {
      var isOpen = state === undefined ? !root.classList.contains("open") : state;
      root.classList.toggle("open", isOpen);
      fab.setAttribute("aria-expanded", String(isOpen));
      fab.setAttribute("aria-label", isOpen ? "Minimizar Quakie" : "Abrir Quakie, asistente de ayuda");
      panel.setAttribute("aria-hidden", String(!isOpen));
      if (isOpen && !started) {
        started = true;
        addBot("<p>¡Hola! Soy Quakie 🐾. Estoy aquí para ayudarte a explorar nuestra plataforma de análisis sísmico. " +
               "¿Qué te gustaría saber?</p>", [], SUGGEST);
      }
      if (isOpen) setTimeout(function () { input.focus(); }, 60);
    }

    fab.addEventListener("click", function () { open(); });
    root.querySelector(".quakie-min").addEventListener("click", function () { open(false); fab.focus(); });
    // Sin <form>: Shiny intercepta el envío de formularios. Enter y el botón envían la pregunta.
    function send() { var t = input.value; input.value = ""; ask(t); }
    root.querySelector(".quakie-send").addEventListener("click", send);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); e.stopPropagation(); send(); }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && root.classList.contains("open")) { open(false); fab.focus(); }
    });
    window.Quakie = { open: function () { open(true); }, close: function () { open(false); }, ask: ask, _answer: answer };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();
