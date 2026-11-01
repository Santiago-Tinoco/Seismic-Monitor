### Contexto

Los terremotos liberan de forma súbita la energía elástica acumulada por la deformación de la litosfera, sobre todo en los límites de placas. Su ocurrencia no es regular: la mayor parte de la actividad global se concentra en zonas de subducción (Cinturón de Fuego del Pacífico, Andes, arco de la Sonda) y llega en secuencias, con un evento principal seguido de réplicas cuya tasa decae con el tiempo (ley de Omori).

### ¿Por qué un análisis temporal?

Un catálogo sísmico es, ante todo, una lista de eventos ordenada en el tiempo. Convertirlo en series de tiempo (número de eventos, magnitud, profundidad y energía por día, semana, mes o año) permite responder preguntas que una tabla de eventos no responde:

- ¿La actividad registrada aumenta, disminuye o se mantiene estable?
- ¿Hay ciclos o estacionalidad?
- ¿Cuánto dura la "memoria" de la serie después de un sismo grande?
- ¿Qué periodos se apartan de lo habitual?
- ¿Es posible anticipar estadísticamente cuántos eventos se registrarán el próximo mes?

### Conjunto de datos

Se usa el archivo `Significant_Earthquakes.csv`, con las columnas estándar del catálogo ComCat del Servicio Geológico de los Estados Unidos (USGS). El archivo tiene 115.493 registros entre 1900 y el 22 de agosto de 2026, y **solo incluye eventos de magnitud ≥ 5,0**.

Después de la limpieza quedan 86.693 sismos únicos desde 1973. Antes de ese año el catálogo detecta menos de la mitad de los eventos M ≥ 5 que se registran después, así que esos años no son comparables y se excluyen.

### Alcance

El proyecto describe y modela el **comportamiento temporal registrado** de la sismicidad M ≥ 5. Puede caracterizar tendencias, agrupamientos, anomalías y la frecuencia esperada de eventos por mes.

**No predice cuándo, dónde ni con qué magnitud ocurrirá un terremoto concreto.** Los pronósticos de la sección *Predecir* se refieren al número de eventos que se registrarán por mes en una región, con su incertidumbre.
