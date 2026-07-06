"""Tests unitarios del ColumnEngine (motor de catálogo de columnas).

Cubren cada operación y las semánticas que la calibración de DESPACHO
fijó como contrato: defaults post-lookup, default_from, normalización de
llaves, branch con las dos condiciones soportadas, columnas intermedias
y errores de configuración.
"""

from __future__ import annotations

import pandas as pd
import pytest

from itacamba_reportes.transforms.column_engine import (
    ColumnCatalogError,
    ColumnEngine,
)


@pytest.fixture()
def df_base() -> pd.DataFrame:
    return pd.DataFrame({
        "destinatario_mcia": [123456, 4321, None],
        "centro_receptor": [" 4B79 ", "4B79", "9999"],
        "producto": ["CEMENTO GRIS", "cal viva", None],
        "vendedor": ["JUAN", "NADIE", "MARIA"],
        "localidad": ["  san matias ", "OTRA", None],
        "dia": [1, 2, 31],
        "incoterms": ["FOB", None, "CIF"],
        "cd": ["CD GUARACACHI", "CD X", None],
    })


@pytest.fixture()
def lookups() -> dict[str, pd.DataFrame]:
    return {
        "int_ref_centro": pd.DataFrame({
            "centro": ["4B79", "4B77"],
            "codigo_sap_cliente": [5412, 5657],
        }),
        "int_ref_equipo": pd.DataFrame({
            "vendedor_sap": ["JUAN", "MARIA"],
            "equipo": ["EQ CEMENTO", "EQ OTRO"],
        }),
        "int_ref_localidad": pd.DataFrame({
            "localidad_despacho": [" SAN MATIAS", "Abapo"],
            "localidad_im": ["RESTO SANTA CRUZ", "RSC"],
        }),
        "int_ref_semana": pd.DataFrame({
            "dia": [1, 2],
            "semana": ["SEMANA 1", "SEMANA 1"],
        }),
    }


def _apply(df, lookups, columns):
    return ColumnEngine(lookups=lookups).apply(df, {"columns": columns})


# ── operaciones básicas ──────────────────────────────────────────────

def test_copy_con_cast(df_base, lookups):
    out = _apply(df_base, lookups, {
        "x": {"op": "copy", "from": "dia", "cast": "int64"},
    })
    assert out["x"].tolist() == [1, 2, 31]
    assert str(out["x"].dtype) == "Int64"


def test_const(df_base, lookups):
    out = _apply(df_base, lookups, {"cd_lit": {"op": "const", "value": "CD"}})
    assert (out["cd_lit"] == "CD").all()


def test_concat_rellena_na_con_vacio(df_base, lookups):
    out = _apply(df_base, lookups, {
        "incoterms_im": {"op": "concat", "cols": ["incoterms", "cd"]},
    })
    # sin separador y NA -> "": replica del comportamiento Excel
    assert out["incoterms_im"].tolist() == ["FOBCD GUARACACHI", "CD X", "CIF"]


# ── lookup ───────────────────────────────────────────────────────────

def test_lookup_con_default(df_base, lookups):
    out = _apply(df_base, lookups, {
        "equipo": {"op": "lookup", "table": "int_ref_equipo",
                   "key": "vendedor", "ref_key": "vendedor_sap",
                   "returns": "equipo", "default": "No encontrado"},
    })
    assert out["equipo"].tolist() == ["EQ CEMENTO", "No encontrado", "EQ OTRO"]


def test_lookup_norm_upper_strip_y_default_from(df_base, lookups):
    out = _apply(df_base, lookups, {
        "localidad_im": {"op": "lookup", "table": "int_ref_localidad",
                         "key": "localidad", "ref_key": "localidad_despacho",
                         "returns": "localidad_im",
                         "norm_keys": "upper_strip",
                         "default_from": "localidad"},
    })
    # match case/espacios-insensitive; sin match conserva la original
    assert out["localidad_im"].tolist()[0] == "RESTO SANTA CRUZ"
    assert out["localidad_im"].tolist()[1] == "OTRA"


def test_lookup_cast_key_int64(df_base, lookups):
    out = _apply(df_base, lookups, {
        "semana": {"op": "lookup", "table": "int_ref_semana",
                   "key": "dia", "ref_key": "dia", "returns": "semana",
                   "cast_key": "int64"},
    })
    assert out["semana"].tolist()[:2] == ["SEMANA 1", "SEMANA 1"]
    assert pd.isna(out["semana"].iloc[2])  # dia 31 sin fila en la ref


def test_lookup_tabla_no_cargada(df_base, lookups):
    with pytest.raises(ColumnCatalogError, match="no cargada"):
        _apply(df_base, lookups, {
            "z": {"op": "lookup", "table": "int_no_existe", "key": "dia",
                  "ref_key": "dia", "returns": "x"},
        })


# ── branch ───────────────────────────────────────────────────────────

def test_branch_contains(df_base, lookups):
    out = _apply(df_base, lookups, {
        "marca": {"op": "branch",
                  "if": {"col": "producto", "contains": "CEMENTO"},
                  "then": {"op": "const", "value": "ES_CEMENTO"},
                  "else": {"op": "const", "value": "NO_CEMENTO"}},
    })
    # contains es case-insensitive y NA cuenta como False
    assert out["marca"].tolist() == ["ES_CEMENTO", "NO_CEMENTO", "NO_CEMENTO"]


def test_branch_str_len_lte_replica_codigo_cliente(df_base, lookups):
    out = _apply(df_base, lookups, {
        "_dest_int": {"op": "copy", "from": "destinatario_mcia",
                      "cast": "int64"},
        "codigo_cliente": {
            "op": "branch",
            "if": {"col": "_dest_int", "str_len_lte": 5},
            "then": {"op": "lookup", "table": "int_ref_centro",
                     "key": "centro_receptor", "ref_key": "centro",
                     "returns": "codigo_sap_cliente", "norm_keys": "strip"},
            "else": {"op": "copy", "from": "_dest_int"},
            "cast": "int64",
        },
    })
    # 123456 (6 dígitos) pasa directo; 4321 (<=5) resuelve por centro;
    # None -> len 0 -> rama lookup, centro 9999 sin match -> NA
    assert out["codigo_cliente"].tolist()[:2] == [123456, 5412]
    assert pd.isna(out["codigo_cliente"].iloc[2])


def test_branch_condicion_desconocida(df_base, lookups):
    with pytest.raises(ColumnCatalogError, match="condición no soportada"):
        _apply(df_base, lookups, {
            "z": {"op": "branch", "if": {"col": "dia", "regex": "x"},
                  "then": {"op": "const", "value": 1},
                  "else": {"op": "const", "value": 2}},
        })


# ── contratos del catálogo ───────────────────────────────────────────

def test_columnas_intermedias_se_descartan(df_base, lookups):
    out = _apply(df_base, lookups, {
        "_tmp": {"op": "const", "value": 1},
        "final": {"op": "copy", "from": "_tmp"},
    })
    assert "_tmp" not in out.columns
    assert (out["final"] == 1).all()


def test_orden_de_ejecucion_encadena_columnas(df_base, lookups):
    out = _apply(df_base, lookups, {
        "a": {"op": "const", "value": "V1"},
        "b": {"op": "copy", "from": "a"},
    })
    assert (out["b"] == "V1").all()


def test_op_desconocida(df_base, lookups):
    with pytest.raises(ColumnCatalogError, match="op desconocida"):
        _apply(df_base, lookups, {"z": {"op": "magia"}})


def test_catalogo_vacio(df_base, lookups):
    with pytest.raises(ColumnCatalogError, match="sin bloque"):
        ColumnEngine(lookups=lookups).apply(df_base, {})


# ── case y equals (agregados en Fase 4 para GD20) ────────────────────

def test_case_mapping_con_default(df_base, lookups):
    df = df_base.assign(umb=["M3", "S50", "XX"])
    out = _apply(df, lookups, {
        "tipo_embalaje": {"op": "case", "col": "umb",
                          "mapping": {"M3": "Granel M3", "T": "Granel t",
                                      "S50": "Embolsado", "PC": "Bolsas Vacias"},
                          "default": "0"},
    })
    assert out["tipo_embalaje"].tolist() == ["Granel M3", "Embolsado", "0"]


def test_case_columna_ausente(df_base, lookups):
    out = _apply(df_base, lookups, {
        "z": {"op": "case", "col": "no_existe", "mapping": {"A": "B"},
              "default": "0"},
    })
    assert (out["z"] == "0").all()


def test_branch_equals_normaliza(df_base, lookups):
    df = df_base.assign(dpto=[" santa cruz ", "BENI", None])
    out = _apply(df, lookups, {
        "region_m": {"op": "branch",
                     "if": {"col": "dpto", "equals": "SANTA CRUZ"},
                     "then": {"op": "const", "value": "SC"},
                     "else": {"op": "copy", "from": "dpto"}},
    })
    assert out["region_m"].tolist()[0] == "SC"
    assert out["region_m"].tolist()[1] == "BENI"
    assert pd.isna(out["region_m"].tolist()[2])
