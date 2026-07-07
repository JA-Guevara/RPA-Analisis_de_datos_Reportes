"""Tests del control de corrida (hash de contenido + calidad + umbrales)."""

from __future__ import annotations

import pandas as pd

from itacamba_reportes.shared.control_corrida import (
    hash_contenido,
    resumen_corrida,
)


def _df():
    return pd.DataFrame({
        "equipo": ["EQ1", "No encontrado", "EQ2", "No encontrado"],
        "canal": ["REVENTA", "OTROS", "REVENTA", "REVENTA"],
        "semana": ["SEMANA 1", None, "SEMANA 2", "SEMANA 2"],
    })


def test_hash_estable_e_independiente_del_orden():
    df = _df()
    h1 = hash_contenido(df)
    h2 = hash_contenido(df.sample(frac=1, random_state=7))  # filas mezcladas
    assert h1 == h2


def test_hash_cambia_si_cambia_un_valor():
    df = _df()
    df2 = df.copy()
    df2.loc[0, "equipo"] = "EQ_MODIFICADO"
    assert hash_contenido(df) != hash_contenido(df2)


def test_resumen_calcula_pct_y_estados():
    r = resumen_corrida(_df(), {
        "columnas": {
            "equipo": {"defaults": ["No encontrado"], "umbral_pct": 60},
            "canal": {"defaults": ["OTROS"], "umbral_pct": 10},
        },
    }, reporte="test")
    filas = {c["columna"]: c for c in r["calidad"]}
    assert filas["equipo"]["sin_match_pct"] == 50.0
    assert filas["equipo"]["estado"] == "OK"      # 50 <= 60
    assert filas["canal"]["sin_match_pct"] == 25.0
    assert filas["canal"]["estado"] == "ALERTA"   # 25 > 10
    assert r["alertas"] == 1
    assert r["filas"] == 4 and len(r["hash_contenido"]) == 16


def test_defaults_incluye_nulos_con_token_na():
    r = resumen_corrida(_df(), {
        "columnas": {"semana": {"defaults": ["<NA>"], "umbral_pct": 10}},
    })
    assert r["calidad"][0]["sin_match_pct"] == 25.0
    assert r["calidad"][0]["estado"] == "ALERTA"


def test_df_vacio_y_columna_ausente_no_rompen():
    r = resumen_corrida(pd.DataFrame(), {"columnas": {"x": {"defaults": ["0"]}}})
    assert r["filas"] == 0 and r["hash_contenido"] == "vacio"
