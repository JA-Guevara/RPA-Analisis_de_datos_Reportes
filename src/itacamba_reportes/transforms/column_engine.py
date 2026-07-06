"""Motor de catálogo de columnas — ejecuta columnas declaradas en YAML.

Objetivo: que las "fórmulas" de un reporte (los VLOOKUP/concat/copias del
Excel del cliente) vivan en UN archivo declarativo por reporte
(`assets/configs/columnas/<reporte>.yaml`) y agregar/modificar una
columna sea editar un bloque YAML, sin tocar código.

El motor soporta EXACTAMENTE las operaciones que existen en los reportes
del cliente — no es un DSL general (decisión deliberada, ver
Arquitectura_Configuracion_Columnas.md):

    copy     copia otra columna                        (col x = dia)
    const    valor literal                             (cd = "CD")
    case     mapping valor -> valor                    (tipo_embalaje)
    concat   concatena columnas, NA -> ""              (incoterms_im, link)
    lookup   VLOOKUP contra una tabla int_*            (equipo, semana, ...)
             key = col del df, ref_key = col de la tabla lookup
             (NO llamar 'on' al parámetro: YAML lo parsea como bool)
    branch   if/then/else con condición acotada        (codigo_cliente, equipo)

Contratos:
  - Las columnas se ejecutan EN EL ORDEN del YAML (una puede usar el
    resultado de la anterior, igual que las cols encadenadas del Excel).
  - Columnas cuyo nombre empieza con "_" son intermedias: se eliminan al
    final (equivalente a las cols auxiliares del basepanel).
  - `default` se aplica como fillna DESPUÉS de la operación;
    `default_from` usa otra columna como fallback (ej. localidad_im).

Condiciones de `branch` (las únicas que usan los reportes):
    contains:    {col: producto, contains: CEMENTO}       (case-insensitive)
    str_len_lte: {col: destinatario_mcia, str_len_lte: 5}
    equals:      {col: dpto, equals: SANTA CRUZ}          (upper+strip)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from itacamba_reportes.shared.pandas_utils import to_int64

logger = logging.getLogger(__name__)


class ColumnCatalogError(ValueError):
    """Catálogo mal formado — error de configuración, no de datos."""


@dataclass(slots=True)
class ColumnEngine:
    """Ejecuta un catálogo de columnas sobre un DataFrame.

    lookups: dict nombre_tabla -> DataFrame (ej. "int_cartera" -> df).
    """

    lookups: dict[str, pd.DataFrame]

    # ── API ───────────────────────────────────────────────────────────
    def apply(self, df: pd.DataFrame, catalog: dict[str, Any]) -> pd.DataFrame:
        df = df.copy()
        columns: dict[str, Any] = catalog.get("columns") or {}
        if not columns:
            raise ColumnCatalogError("Catálogo sin bloque 'columns'")

        for name, spec in columns.items():
            try:
                serie = self._eval(df, spec, name)
                serie = self._post(df, serie, spec)
                df[name] = serie
            except ColumnCatalogError:
                raise
            except Exception as exc:  # config o datos inesperados: contexto
                raise ColumnCatalogError(
                    f"Columna '{name}': {exc}") from exc

        internas = [c for c in columns if c.startswith("_")]
        df = df.drop(columns=internas, errors="ignore")
        logger.info(
            "Catálogo aplicado: %d columnas (%d intermedias descartadas)",
            len(columns) - len(internas), len(internas),
        )
        return df

    # ── evaluación de una operación (recursiva para branch) ──────────
    def _eval(self, df: pd.DataFrame, spec: dict[str, Any], name: str) -> pd.Series:
        op = spec.get("op")
        if op == "copy":
            return self._op_copy(df, spec)
        if op == "const":
            return pd.Series(spec["value"], index=df.index, dtype="object")
        if op == "case":
            return self._op_case(df, spec)
        if op == "concat":
            return self._op_concat(df, spec)
        if op == "lookup":
            return self._op_lookup(df, spec, name)
        if op == "branch":
            return self._op_branch(df, spec, name)
        raise ColumnCatalogError(f"op desconocida: {op!r}")

    # ── operaciones ──────────────────────────────────────────────────
    @staticmethod
    def _op_copy(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
        src = spec["from"]
        if src not in df.columns:
            return pd.Series(pd.NA, index=df.index, dtype="object")
        return df[src].copy()

    @staticmethod
    def _op_case(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
        """Mapping valor->valor sobre una columna (equivalente a SI anidados
        del Excel por igualdad exacta). Valores sin mapping quedan NA
        (aplicar `default:` en el bloque para el fallback)."""
        col = spec["col"]
        if col not in df.columns:
            return pd.Series(pd.NA, index=df.index, dtype="object")
        mapping = {str(k): v for k, v in (spec.get("mapping") or {}).items()}
        return df[col].astype("string").map(mapping)

    @staticmethod
    def _op_concat(df: pd.DataFrame, spec: dict[str, Any]) -> pd.Series:
        sep = str(spec.get("sep", ""))
        cols = spec["cols"]
        faltan = [c for c in cols if c not in df.columns]
        if faltan:
            return pd.Series(pd.NA, index=df.index, dtype="object")
        out = df[cols[0]].astype("string").fillna("")
        for c in cols[1:]:
            out = out + sep + df[c].astype("string").fillna("")
        return out

    def _op_lookup(self, df: pd.DataFrame, spec: dict[str, Any],
                   name: str) -> pd.Series:
        table = spec["table"]
        ref = self.lookups.get(table)
        if ref is None:
            raise ColumnCatalogError(
                f"tabla lookup {table!r} no cargada (disponibles: "
                f"{sorted(self.lookups)})")

        key_col, ref_key = spec["key"], spec["ref_key"]
        returns = spec["returns"]
        if key_col not in df.columns or ref.empty or ref_key not in ref.columns \
                or returns not in ref.columns:
            return pd.Series(pd.NA, index=df.index, dtype="object")

        norm = spec.get("norm_keys")          # None | strip | upper_strip
        cast_key = spec.get("cast_key")       # None | int64

        ref_keys = ref[ref_key]
        df_keys = df[key_col]
        if cast_key == "int64":
            ref_keys, df_keys = to_int64(ref_keys), to_int64(df_keys)
        elif norm == "strip":
            ref_keys = ref_keys.astype("string").str.strip()
            df_keys = df_keys.astype("string").str.strip()
        elif norm == "upper_strip":
            ref_keys = ref_keys.astype("string").str.upper().str.strip()
            df_keys = df_keys.astype("string").str.upper().str.strip()

        pares = pd.DataFrame({"k": ref_keys, "v": ref[returns]})
        pares = pares.dropna(subset=["k"]).drop_duplicates("k", keep="first")
        mapa = dict(zip(pares["k"], pares["v"]))
        return df_keys.map(mapa)

    def _op_branch(self, df: pd.DataFrame, spec: dict[str, Any],
                   name: str) -> pd.Series:
        cond = spec["if"]
        col = cond["col"]
        if col not in df.columns:
            mask = pd.Series(False, index=df.index)
        elif "contains" in cond:
            mask = (df[col].astype("string")
                    .str.contains(str(cond["contains"]), case=False, na=False))
        elif "str_len_lte" in cond:
            mask = (df[col].astype("string").fillna("")
                    .str.len() <= int(cond["str_len_lte"]))
        elif "equals" in cond:
            mask = (df[col].astype("string").str.upper().str.strip()
                    == str(cond["equals"]).upper().strip())
            mask = mask.fillna(False)
        else:
            raise ColumnCatalogError(
                f"branch de '{name}': condición no soportada {cond!r} "
                "(usar 'contains', 'str_len_lte' o 'equals')")

        then_s = self._post(df, self._eval(df, spec["then"], name), spec["then"])
        else_s = self._post(df, self._eval(df, spec["else"], name), spec["else"])
        return then_s.where(mask, else_s)

    # ── post-proceso común: default / default_from / cast ────────────
    @staticmethod
    def _post(df: pd.DataFrame, serie: pd.Series, spec: dict[str, Any]) -> pd.Series:
        if "default" in spec:
            serie = serie.fillna(spec["default"])
        if "default_from" in spec and spec["default_from"] in df.columns:
            serie = serie.fillna(df[spec["default_from"]])
        if spec.get("cast") == "int64":
            serie = to_int64(serie)
        return serie
