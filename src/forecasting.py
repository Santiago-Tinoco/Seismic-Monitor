"""Pronóstico del NÚMERO MENSUAL de eventos (no de sismos individuales).

Réplica exacta en R: shiny_app/R/models.R.

Diseño
------
- Variable: conteo mensual de eventos M >= Mmin en la región y catálogo elegidos.
- Validación temporal: los últimos `test_months` meses son prueba; el resto,
  entrenamiento. Nunca se mezclan al azar.
- Modelos:
    1. Ingenuo: repite el último valor observado (referencia).
    2. Media histórica (climatología): media del entrenamiento; intervalo de una
       Binomial Negativa ajustada por momentos (los conteos están sobredispersos).
    3. Suavizamiento exponencial simple (SES, modelo ETS(A,N,N)): α en una
       rejilla 0.01–0.99 que minimiza el SSE de un paso; nivel inicial = media de
       los primeros 12 meses. Implementado igual en Python y R.
    4. ARIMA(1,0,1) con media, máxima verosimilitud (statsmodels / stats::arima).
- Métricas en el conjunto de prueba: MAE, RMSE y MASE (escala = MAE del
  pronóstico ingenuo de un paso dentro del entrenamiento).
- Intervalos: 80 % y 95 %. Para SES y ARIMA son gaussianos y se truncan en 0.
- Pronóstico a un paso (validación móvil): con los parámetros del entrenamiento,
  en cada mes de prueba se pronostica el mes siguiente usando la información
  observada hasta el mes anterior. Muestra cómo el modelo sigue la dinámica,
  algo que el pronóstico a varios meses (casi plano) no puede mostrar.
- Trayectorias simuladas: escenarios posibles generados con la ecuación del
  modelo y errores aleatorios (semilla fija). Ilustran la variabilidad mensual
  esperada alrededor del pronóstico medio; no son predicciones.

¿Por qué el pronóstico a varios meses es (casi) plano?
    El ingenuo, la media y el SES pronostican un nivel constante por
    construcción, y el ARIMA(1,0,1) vuelve a la media en pocos meses. Es el
    resultado correcto para una serie sin tendencia ni estacionalidad marcadas:
    el mejor valor esperado es el nivel actual, y la incertidumbre se expresa
    en el ancho de los intervalos, no en la forma de la línea.
"""
import warnings

import numpy as np
import pandas as pd
from scipy import stats

from src.timeseries import PARAMS

Z = {80: stats.norm.ppf(0.90), 95: stats.norm.ppf(0.975)}
MODELS = {"naive": "Ingenuo (último valor)", "mean": "Media histórica (Binomial Negativa)",
          "ses": "Suavizamiento exponencial simple", "arima": "ARIMA(1,0,1) con media"}


def _interval(mean, sd):
    out = {}
    for lv, z in Z.items():
        out[f"lo{lv}"] = np.maximum(mean - z * sd, 0)
        out[f"hi{lv}"] = mean + z * sd
    return out


def fit_naive(y, h):
    sigma = np.std(np.diff(y), ddof=1)
    mean = np.repeat(y[-1], h)
    return {"mean": mean, **_interval(mean, sigma * np.sqrt(np.arange(1, h + 1))), "resid": np.diff(y)}


def fit_mean(y, h):
    mu, var = y.mean(), y.var(ddof=1)
    mean = np.repeat(mu, h)
    out = {"mean": mean, "resid": y - mu}
    if var > mu > 0:
        r = mu ** 2 / (var - mu)
        p = r / (r + mu)
        for lv in (80, 95):
            a = (1 - lv / 100) / 2
            out[f"lo{lv}"] = np.repeat(stats.nbinom.ppf(a, r, p), h).astype(float)
            out[f"hi{lv}"] = np.repeat(stats.nbinom.ppf(1 - a, r, p), h).astype(float)
    else:
        for lv in (80, 95):
            a = (1 - lv / 100) / 2
            out[f"lo{lv}"] = np.repeat(stats.poisson.ppf(a, mu), h).astype(float)
            out[f"hi{lv}"] = np.repeat(stats.poisson.ppf(1 - a, mu), h).astype(float)
    return out


def ses_filter(y, alpha, l0):
    level = np.empty(y.size + 1)
    level[0] = l0
    for t in range(y.size):
        level[t + 1] = alpha * y[t] + (1 - alpha) * level[t]
    fitted = level[:-1]
    return fitted, level[-1]


def fit_ses(y, h):
    step = PARAMS["forecast"]["ses_alpha_grid_step"]
    l0 = y[:PARAMS["forecast"]["ses_l0_n"]].mean()
    grid = np.round(np.arange(step, 1.0, step), 4)
    sse = [np.sum((y - ses_filter(y, a, l0)[0]) ** 2) for a in grid]
    alpha = float(grid[int(np.argmin(sse))])
    fitted, last = ses_filter(y, alpha, l0)
    resid = y - fitted
    sigma = np.sqrt(np.sum(resid ** 2) / (y.size - 2))
    mean = np.repeat(last, h)
    sd = sigma * np.sqrt(1 + (np.arange(1, h + 1) - 1) * alpha ** 2)
    return {"mean": mean, **_interval(mean, sd), "resid": resid, "alpha": alpha, "l0": l0, "level": last,
            "sigma": sigma}


def fit_arima(y, h):
    from statsmodels.tsa.arima.model import ARIMA
    order = tuple(PARAMS["forecast"]["arima_order"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = ARIMA(y, order=order, trend="c").fit()
    fc = res.get_forecast(h)
    mean = np.asarray(fc.predicted_mean)
    sd = np.sqrt(np.asarray(fc.var_pred_mean))
    params = dict(zip(res.model.param_names, res.params))
    return {"mean": mean, **_interval(mean, sd), "resid": np.asarray(res.resid), "params": params, "res": res}


FITTERS = {"naive": fit_naive, "mean": fit_mean, "ses": fit_ses, "arima": fit_arima}


# --------------------------------------------------------------------------
# Pronóstico a un paso en el periodo de prueba (parámetros del entrenamiento)
# --------------------------------------------------------------------------
def one_step(y, ntr, model, fit):
    """Pronósticos a un mes vista para y[ntr:], con los parámetros estimados en y[:ntr]."""
    if model == "naive":
        return y[ntr - 1:-1].copy()
    if model == "mean":
        return np.repeat(y[:ntr].mean(), y.size - ntr)
    if model == "ses":
        return ses_filter(y, fit["alpha"], fit["l0"])[0][ntr:]
    if model == "arima":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return np.asarray(fit["res"].apply(y).predict(start=ntr, end=y.size - 1))
    raise ValueError(model)


# --------------------------------------------------------------------------
# Trayectorias simuladas (escenarios posibles, no predicciones)
# --------------------------------------------------------------------------
def simulate(y, model, h, n_paths=3, seed=2026):
    """Simula `n_paths` trayectorias de `h` meses con la ecuación de cada modelo.

    Ingenuo: paseo aleatorio; media: Binomial Negativa (o Poisson); SES: nivel
    que se actualiza con α; ARIMA(1,0,1): recursión con φ, θ y μ desde el último
    valor y el último residuo. Errores gaussianos con la σ estimada. Se truncan
    en 0 y se redondean, porque son conteos.
    """
    rng = np.random.default_rng(seed)
    y = np.asarray(y, float)
    fit = FITTERS[model](y, h)
    paths = np.empty((n_paths, h))
    for i in range(n_paths):
        if model == "naive":
            sigma = np.std(np.diff(y), ddof=1)
            paths[i] = y[-1] + np.cumsum(rng.normal(0, sigma, h))
        elif model == "mean":
            mu, var = y.mean(), y.var(ddof=1)
            if var > mu > 0:
                r = mu ** 2 / (var - mu)
                paths[i] = rng.negative_binomial(r, r / (r + mu), h)
            else:
                paths[i] = rng.poisson(mu, h)
        elif model == "ses":
            lev = fit["level"]
            for t in range(h):
                e = rng.normal(0, fit["sigma"])
                paths[i, t] = lev + e
                lev = lev + fit["alpha"] * e
        elif model == "arima":
            p = fit["params"]
            mu, phi, theta = p["const"], p["ar.L1"], p["ma.L1"]
            sigma = np.sqrt(p["sigma2"])
            prev_y, prev_e = y[-1], fit["resid"][-1]
            for t in range(h):
                e = rng.normal(0, sigma)
                val = mu + phi * (prev_y - mu) + theta * prev_e + e
                paths[i, t] = val
                prev_y, prev_e = val, e
    return np.round(np.maximum(paths, 0))


def ljung_box(resid, lag):
    from statsmodels.stats.diagnostic import acorr_ljungbox
    r = np.asarray(resid, float)
    r = r[np.isfinite(r)]
    t = acorr_ljungbox(r, lags=[lag])
    return float(t["lb_stat"].iloc[0]), float(t["lb_pvalue"].iloc[0])


def evaluate(series: pd.DataFrame, test_months=None):
    """Entrena con el inicio de la serie y evalúa en los últimos meses."""
    test_months = test_months or PARAMS["forecast"]["test_months"]
    y = series["n"].to_numpy(float)
    if y.size < test_months + 36:
        return None
    train, test = y[:-test_months], y[-test_months:]
    ntr = train.size
    scale = np.mean(np.abs(np.diff(train)))
    lag = PARAMS["forecast"]["ljung_box_lag"]
    rows, paths = [], {}
    for key, f in FITTERS.items():
        fc = f(train, test_months)
        err = test - fc["mean"]
        fc["one_step"] = one_step(y, ntr, key, fc)
        err1 = test - fc["one_step"]
        lb, lbp = ljung_box(fc["resid"], lag)
        rows.append({"modelo": MODELS[key], "clave": key, "MAE": np.mean(np.abs(err)),
                     "RMSE": np.sqrt(np.mean(err ** 2)), "MASE": np.mean(np.abs(err)) / scale,
                     "cobertura_95": 100 * np.mean((test >= fc["lo95"]) & (test <= fc["hi95"])),
                     "MAE_1paso": np.mean(np.abs(err1)), "MASE_1paso": np.mean(np.abs(err1)) / scale,
                     "ljung_box_p": lbp,
                     "detalle": (f"α = {fc['alpha']:.2f}" if key == "ses" else
                                 ", ".join(f"{k} = {v:.3f}" for k, v in fc["params"].items()) if key == "arima" else "")})
        paths[key] = fc
    table = pd.DataFrame(rows)
    return {"table": table, "paths": paths, "train_end": series["periodo"].iloc[-test_months - 1],
            "test_periods": series["periodo"].iloc[-test_months:].reset_index(drop=True), "test": test}


def forecast(series: pd.DataFrame, model: str, h: int):
    y = series["n"].to_numpy(float)
    fc = FITTERS[model](y, h)
    last = series["periodo"].iloc[-1]
    periods = pd.date_range(last + pd.offsets.MonthBegin(1), periods=h, freq="MS")
    out = pd.DataFrame({"periodo": periods, "pronostico": fc["mean"]})
    for k in ("lo80", "hi80", "lo95", "hi95"):
        out[k] = fc[k]
    return out
