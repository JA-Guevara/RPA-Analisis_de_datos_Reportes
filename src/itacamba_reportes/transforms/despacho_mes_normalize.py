"""Despacho Mes Normalize — los 5 lookups vivos del Excel DESPACHO_MES.

Equivale a las fórmulas vivas de las cols P-T de la hoja:

    NOMBRE CLIENTE = VLOOKUP(K, CARTERA, 2, 0)        -> int_cartera.nombre_cliente
    VENDEDOR       = VLOOKUP(K, CARTERA, 33, 0)       -> int_cartera.vendedor
    TIPO DE VENTA  = VLOOKUP(K, REFERENCIAS.I:J, 2)   -> int_cartera.canal_distribucion (proxy)
    CANAL          = VLOOKUP(VLOOKUP(K,CART,3), REF.D:F, 3) -> doble lookup
    SEMANA2        = VLOOKUP(día, REF.U:V, 2, 0)      -> int_ref_semana.semana

Defaults configurables vía YAML.

TIPO DE VENTA: el lookup original apunta a REFERENCIAS!I:J del
basepanel, hoja que NO existe en Referencias.xlsx. Hasta que negocio
defina la fuente canónica, usamos int_cartera.canal_distribucion como
PROXY (es lo más cercano semánticamente). Cuando exista
int_ref_tipo_venta, cambiar el lookup acá.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from itacamba_reportes.shared.pandas_utils import to_int64

logger = logging.getLogger(__name__)


_HARDCODED_DEFAULTS: dict[str, str] = {
    "nombre_cliente": "Prospecto",
    "vendedor":       "Prospecto",
    "tipo_venta":     "VENTA DIRECTA",
    "canal":          "OTROS",
    "semana2":        "SEMANA 0",
}


@dataclass(slots=True)
class DespachoMesNormalizeUseCase:

    cartera_df: pd.DataFrame
    almacen_df: pd.DataFrame
    semana_df: pd.DataFrame
    config: dict | None = None

    def _default(self, key: str) -> str:
        if self.config is None:
            return _HARDCODED_DEFAULTS[key]
        return self.config.get("defaults", {}).get(key, _HARDCODED_DEFAULTS[key])

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._lookup_cartera(df)
        df = self._lookup_canal(df)
        df = self._lookup_semana(df)
        return df

    # ───────────────────────────────────────────────────────────────────
    # PASO 1: cartera lookup
    #   codigo_cliente -> nombre_cliente, vendedor, tipo_venta (proxy)
    # ───────────────────────────────────────────────────────────────────
    def _lookup_cartera(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.cartera_df.empty:
            df["nombre_cliente"] = self._default("nombre_cliente")
            df["vendedor"]       = self._default("vendedor")
            df["tipo_venta"]     = self._default("tipo_venta")
            df["_attr10"]        = pd.NA
            return df

        cart = (
            self.cartera_df[[
                "cliente", "nombre_cliente", "vendedor",
                "canal_distribucion_desc", "attribute_10",
            ]]
            .drop_duplicates("cliente", keep="first")
            .rename(columns={
                "cliente":                 "codigo_cliente",
                "canal_distribucion_desc": "tipo_venta",  # proxy hasta confirmar fuente
                "attribute_10":            "_attr10",
            })
        )
        cart["codigo_cliente"] = to_int64(cart["codigo_cliente"])

        df["codigo_cliente"] = to_int64(df["codigo_cliente"])
        df = df.merge(cart, on="codigo_cliente", how="left")

        df["nombre_cliente"] = df["nombre_cliente"].fillna(self._default("nombre_cliente"))
        df["vendedor"]       = df["vendedor"].fillna(self._default("vendedor"))
        df["tipo_venta"]     = df["tipo_venta"].fillna(self._default("tipo_venta"))
        return df

    # ───────────────────────────────────────────────────────────────────
    # PASO 2: doble lookup canal
    #   _attr10 (de cartera) -> int_ref_almacen.canal
    # ───────────────────────────────────────────────────────────────────
    def _lookup_canal(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.almacen_df.empty or "_attr10" not in df.columns:
            df["canal"] = self._default("canal")
            df = df.drop(columns=["_attr10"], errors="ignore")
            return df

        alm = (
            self.almacen_df[["descripcion_sap", "canal"]]
            .dropna(subset=["descripcion_sap"])
            .drop_duplicates("descripcion_sap", keep="first")
            .rename(columns={"descripcion_sap": "_attr10"})
        )
        df = df.merge(alm, on="_attr10", how="left")
        df["canal"] = df["canal"].fillna(self._default("canal"))
        df = df.drop(columns=["_attr10"], errors="ignore")
        return df

    # ───────────────────────────────────────────────────────────────────
    # PASO 3: lookup semana
    #   dia -> int_ref_semana.semana
    # ───────────────────────────────────────────────────────────────────
    def _lookup_semana(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.semana_df.empty or "dia" not in df.columns:
            df["semana2"] = self._default("semana2")
            return df

        sem = (
            self.semana_df[["dia", "semana"]]
            .dropna(subset=["dia"])
            .drop_duplicates("dia", keep="first")
            .rename(columns={"semana": "semana2"})
        )
        sem["dia"] = pd.to_numeric(sem["dia"], errors="coerce").astype("Int64")

        df["dia"] = pd.to_numeric(df["dia"], errors="coerce").astype("Int64")
        df = df.merge(sem, on="dia", how="left")
        df["semana2"] = df["semana2"].fillna(self._default("semana2"))
        return df
