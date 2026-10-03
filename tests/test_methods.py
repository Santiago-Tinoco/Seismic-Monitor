"""Validación de los métodos con datos sintéticos y controles sobre el catálogo real.

Ejecutar desde la carpeta del proyecto:
    python -m pytest tests -q          (si pytest está instalado)
    python tests/test_methods.py       (sin pytest)
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import CATALOG_PARQUET  # noqa: E402
from src import seismic_analysis as sa  # noqa: E402
from src import statistics as st  # noqa: E402
from src.declustering import gardner_knopoff_decluster, haversine_km  # noqa: E402

RNG = np.random.default_rng(0)


def synthetic_gr(b=1.0, mc=5.0, n=5000, dm=0.1):
    """Magnitudes G-R con un b conocido, binneadas a dm (umbral continuo mc - dm/2)."""
    beta = b * np.log(10)
    m = (mc - dm / 2) + RNG.exponential(1 / beta, n)
    return sa.bin_magnitudes(m, dm)


def test_b_value_recovers_true_value():
    for b_true in (0.8, 1.0, 1.3):
        m = synthetic_gr(b=b_true, n=20000)
        b, n = sa.b_value_aki_utsu(m, 5.0)
        sigma = sa.b_sigma_shi_bolt(m, 5.0, b)
        assert abs(b - b_true) < 4 * sigma, (b_true, b, sigma)


def test_mc_mbs_finds_completeness_when_small_events_missing():
    m = synthetic_gr(b=1.0, mc=5.0, n=30000)
    # Eliminar el 70 % de los eventos entre 5.0 y 5.3 (catálogo incompleto)
    drop = (m < 5.35) & (RNG.random(m.size) < 0.7)
    mc, _, method = sa.estimate_mc_mbs(m[~drop])
    assert method == "MBS" and mc >= 5.3, mc


def test_lrt_detects_and_rejects_difference():
    a = synthetic_gr(b=1.0, n=3000)
    b_same = synthetic_gr(b=1.0, n=3000)
    b_diff = synthetic_gr(b=0.7, n=3000)
    assert sa.compare_b_values_lrt(a, b_same, 5.0)[1] > 0.01
    assert sa.compare_b_values_lrt(a, b_diff, 5.0)[1] < 1e-6


def test_energy_is_additive_not_magnitude():
    # Dos eventos M6 liberan ~2 veces la energía de uno, no la de un M12
    two = sa.total_energy_log10(np.array([6.0, 6.0]))
    assert abs(two - (sa.energy_log10_joules(6.0) + np.log10(2))) < 1e-9


def test_midrank_percentile():
    assert st.empirical_percentile([0, 0, 0, 0], 0) == 50.0
    assert st.empirical_percentile([1, 2, 3, 4], 5) == 100.0
    assert st.empirical_percentile([1, 2, 3, 4], 2.5) == 50.0


def test_window_counts_match_brute_force():
    t = np.sort(RNG.uniform(0, 1000, 500))
    starts, ends = st.build_historical_windows(0, 900, 30, 3)
    fast = st.window_counts(t, starts, ends)
    brute = np.array([np.sum((t > s) & (t <= e)) for s, e in zip(starts, ends)])
    assert np.array_equal(fast, brute)
    assert ends[-1] == 900 and np.all(ends <= 900)  # nunca se solapa con la ventana reciente


def test_negative_binomial_tail_on_poisson_data():
    x = RNG.poisson(4, 5000)
    model = st.fit_count_model(x)
    p_up, _ = st.count_tail_probabilities(model, 10)
    from scipy import stats
    assert abs(p_up - stats.poisson(4).sf(9)) < 0.01


def test_bh_fdr_monotone_and_bounded():
    q = st.bh_fdr([0.01, 0.04, 0.03, 0.5])
    assert np.all(q <= 1) and np.all(q >= [0.01, 0.04, 0.03, 0.5])


def test_gardner_knopoff_flags_aftershocks_not_distant_events():
    # Principal M7 en (0,0) t=0; réplica a 20 km a t=5 d; evento lejano a 2000 km
    lat = np.array([0.0, 0.18, 18.0])
    lon = np.array([0.0, 0.0, 0.0])
    t = np.array([0.0, 5.0, 6.0])
    mag = np.array([7.0, 5.5, 5.5])
    dep, clus = gardner_knopoff_decluster(t, lat, lon, mag)
    assert list(dep) == [False, True, False]
    assert clus[1] == 0
    assert abs(haversine_km(0, 0, 0.18, 0) - 20.0) < 0.1


def test_real_catalog_consistency():
    if not CATALOG_PARQUET.exists():
        return
    from src.anomaly_detection import Selection, assess
    res = assess(Selection(region_key="Japón", window_days=365))
    ev = res["events_selected"]
    n_rec = (ev["time"] > res["recent_start"]).sum()
    assert n_rec == res["current"]["n_events"]
    w = res["windows"]
    pct = 100 * (np.sum(w["n_events"] < res["current"]["n_events"])
                 + 0.5 * np.sum(w["n_events"] == res["current"]["n_events"])) / len(w)
    assert abs(pct - res["table"].iloc[0]["percentil"]) < 1e-9


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for f in tests:
        f()
        print("OK ", f.__name__)
    print(f"{len(tests)} pruebas superadas")
