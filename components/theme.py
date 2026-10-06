"""Plantilla Plotly común a todos los gráficos."""
import plotly.graph_objects as go
import plotly.io as pio

from config import COLORS


# --------------------------------------------------------------------------
# Tipografías
# --------------------------------------------------------------------------

FONT = "Open Sans, Helvetica, Arial, sans-serif"
MONO = "Open Sans, Helvetica, Arial, sans-serif"


# --------------------------------------------------------------------------
# Paleta geológica
# --------------------------------------------------------------------------

GEO_COLORS = {
    "ink": "#3E2723",
    "muted": "#756E67",
    "grid": "#E3DCD2",
    "paper": "#FFFFFF",

    "recent": "#C75B12",
    "hist": "#B8A58C",
    "hist_dark": "#806B55",

    "above": "#D9822B",
    "above_ext": "#9C3F0B",

    "below": "#8C6A43",
    "below_ext": "#5E452D",

    "normal": "#A7A095",
    "na": "#C8C1B8",
}


# --------------------------------------------------------------------------
# Actualizar la paleta global utilizada por los gráficos
# --------------------------------------------------------------------------

COLORS.update(GEO_COLORS)


# --------------------------------------------------------------------------
# Plantilla Plotly
# --------------------------------------------------------------------------

pio.templates["sismo"] = go.layout.Template(
    layout=dict(
        font=dict(
            family=FONT,
            size=12,
            color=COLORS["ink"],
        ),

        paper_bgcolor=COLORS["paper"],
        plot_bgcolor=COLORS["paper"],

        colorway=[
            COLORS["recent"],
            COLORS["hist_dark"],
            COLORS["above"],
            COLORS["below"],
        ],

        margin=dict(
            l=56,
            r=20,
            t=36,
            b=48,
        ),

        xaxis=dict(
            gridcolor=COLORS["grid"],
            linecolor="#CFC5B7",
            zeroline=False,
            ticks="outside",
            tickcolor="#CFC5B7",
            title=dict(
                font=dict(
                    size=12,
                    color=COLORS["muted"],
                )
            ),
        ),

        yaxis=dict(
            gridcolor=COLORS["grid"],
            linecolor="#CFC5B7",
            zeroline=False,
            ticks="outside",
            tickcolor="#CFC5B7",
            title=dict(
                font=dict(
                    size=12,
                    color=COLORS["muted"],
                )
            ),
        ),

        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(
                size=11,
                color=COLORS["muted"],
            ),
            bgcolor="rgba(0,0,0,0)",
        ),

        hoverlabel=dict(
            font=dict(
                family=FONT,
                size=12,
            ),
            bgcolor="#FFFFFF",
            bordercolor="#CFC5B7",
        ),

        title=dict(
            font=dict(
                size=13,
                color=COLORS["ink"],
            ),
            x=0,
            xanchor="left",
        ),
    )
)

pio.templates.default = "sismo"


GRAPH_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "lasso2d",
        "select2d",
        "autoScale2d",
    ],
    "toImageButtonOptions": {
        "format": "png",
        "scale": 2,
    },

    # Cartografía Natural Earth servida localmente.
    "topojsonURL": "/assets/topojson/",
}


def empty_figure(message: str, height=280):
    fig = go.Figure()

    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(
            color=COLORS["muted"],
            size=13,
            family=FONT,
        ),
    )

    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)

    fig.update_layout(height=height)

    return fig
