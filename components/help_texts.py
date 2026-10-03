"""Glosario breve para ayudas emergentes (atributo title)."""
from dash import html

GLOSSARY = {
    "percentil": "Porcentaje de ventanas históricas de la misma duración con un valor menor que el actual "
                 "(los empates cuentan la mitad). P97 = por encima de ~97 % de las ventanas históricas. "
                 "No es una probabilidad de que ocurra un sismo.",
    "b": "Parámetro de la relación de Gutenberg-Richter que describe la proporción relativa de sismos pequeños "
         "y grandes. b ≈ 1 en la mayoría de regiones tectónicas.",
    "mc": "Magnitud de completitud: magnitud mínima por encima de la cual el catálogo se considera "
          "suficientemente completo para el análisis.",
    "energia": "Energía sísmica radiada estimada con log10 E = 1.5M + 4.8 (julios). Es aditiva: se suman "
               "energías, no magnitudes. Se muestra en escala logarítmica.",
    "tasa": "Número de eventos dividido por la duración de la ventana.",
    "iet": "Tiempo entre eventos consecutivos. Su coeficiente de variación (CV) vale ≈ 1 para ocurrencia "
           "aleatoria tipo Poisson y > 1 cuando los eventos llegan agrupados.",
    "gk": "Declustering de Gardner & Knopoff (1974): separa eventos principales de réplicas y premonitores "
          "con ventanas de distancia y tiempo que crecen con la magnitud.",
    "nb": "Binomial Negativa: modelo de conteos que admite varianza mayor que la media (sobredispersión), "
          "típica cuando hay secuencias de réplicas.",
    "fdr": "q-valor de Benjamini-Hochberg: p-valor corregido por haber evaluado muchas regiones a la vez.",
    "linea_base": "Conjunto de ventanas históricas de la misma duración que la ventana reciente, desde el "
                  "año de inicio elegido hasta el comienzo de la ventana reciente.",
}


def term(label: str, key: str):
    """Texto con subrayado punteado y ayuda emergente."""
    return html.Span(label, title=GLOSSARY[key], className="term")
