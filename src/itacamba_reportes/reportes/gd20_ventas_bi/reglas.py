"""Reglas complejas del reporte GD20/VENTAS BI (no expresables en YAML).

Contiene EXACTAMENTE la lógica calibrada contra el BASE PANEL del
cliente, movida verbatim desde transforms/gd20_normalize.py y
transforms/gd20_business_rules.py (Fase 4 del plan 2026-07-06):

  Gd20CdZeRule            centro_distribucion + zona_entrega (5 capas
                          sobre stg_query; 82.7%/76.5% match validado)
  CentroOverridesRule     overrides por centro físico (datos en
                          config.yaml:centro_overrides, ya no en código)
  NombreDestQueryRule     override opcional de nombre_destinatario
                          (desactivado por default; ver config)
  Gd20BusinessRulesUseCase ingreso_bruto, fechas, volumen,
                          bonificaciones, post_replaces (fórmulas
                          numéricas condicionales del Excel)

Los lookups simples (cartera, material, equipo, almacén, centro,
region_m, tipo_embalaje) están en columnas.yaml (ColumnEngine).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from itacamba_reportes.shared.pandas_utils import to_int64

logger = logging.getLogger(__name__)


_RULE_DEFAULTS: dict[str, str] = {
    "centro_distribucion": "OTROS",
    "zona_entrega":        "OTROS",
}


@dataclass(slots=True)
class Gd20CdZeRule:
    """CD/ZE cruzando stg_query — ver docstring de _lookup_query."""

    query_df: pd.DataFrame
    centro_df: pd.DataFrame
    config: dict | None = None

    def _default(self, key: str) -> str:
        if self.config is None:
            return _RULE_DEFAULTS[key]
        return self.config.get("defaults", {}).get(key, _RULE_DEFAULTS[key])

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        return self._lookup_query(df)

    def _lookup_query(self, df: pd.DataFrame) -> pd.DataFrame:
        """Resuelve centro_distribucion + zona_entrega cruzando stg_query.

        Replica EXACTAMENTE las fórmulas del Excel cliente:

            CD = SI.ERROR(BUSCARV(R_pagador; QUERY!AZ:BG; 7; 0); "OTROS")
            ZE = SI.ERROR(BUSCARV(R_pagador; QUERY!AZ:BH; 8; 0); "OTROS")

        Donde QUERY!AZ es la col 'codigo_cliente' enriquecida que el cliente
        calcula con la fórmula:

            AZ = SI(LEN(G_cod_dest) <= 5;
                    SI.ERROR(BUSCARV(L_centro_receptor; REFERENCIAS!H:I; 2; 0); G);
                    G)

        Es decir: si el destinatario es centro interno (≤5 dígitos), buscar
        en int_ref_centro (centro → codigo_sap_cliente); si es cliente
        externo (>5 dígitos), usar el destinatario directo.

        Estrategia HÍBRIDA en 4 capas (PRIMERO la fórmula exacta, después
        fallbacks por si la col centro→codigo_sap_cliente está incompleta):

        - Capa 1: GD20.centro ∈ centros físicos (Centro_Proveedor de QUERY)
                  → CD del dict (DETERMINÍSTICO para plantas)
        - Capa 2: BUSCARV EXACTA del cliente — pagador → codigo_cliente_calc
                  derivado on-the-fly desde stg_query + int_ref_centro
        - Capa 3: documento_comercial → QUERY.documento_venta (match temporal)
        - Capa 4: pagador → QUERY.destinatario_mcia (proxy)
        - Fallback: 'OTROS'

        Validado empíricamente: 82.7% CD, 76.5% ZE vs BASE PANEL del cliente.
        """
        default_cd = self._default("centro_distribucion")
        default_ze = self._default("zona_entrega")
        if self.query_df.empty:
            df["centro_distribucion"] = default_cd
            df["zona_entrega"]        = default_ze
            return df

        q_cols = self.query_df.columns
        cd_col = "centro_distribucion" if "centro_distribucion" in q_cols else None
        # zona_entrega del cliente = col 'ruta' (codigo SAP tipo "4BO289").
        # NO usar 'zona_descarga' que es la zona geografica (tipo "SCZ-LOCAL").
        # Validado contra BASE PANEL: 1467/1995 filas con valor son codigos
        # ruta, 528 son 'OTROS', cero son zonas geograficas.
        zd_col = "ruta" if "ruta" in q_cols else None
        doc_col = "documento_venta" if "documento_venta" in q_cols else None
        cp_col = "centro_proveedor" if "centro_proveedor" in q_cols else None

        if not cd_col:
            logger.warning("stg_query sin col 'centro_distribucion'; CD=%s", default_cd)
            df["centro_distribucion"] = default_cd
            df["zona_entrega"]        = default_ze
            return df

        # CAPA 1 ─ Diccionario derivado: Centro_Proveedor → CD (1:1, los 6 fisicos)
        df["centro_distribucion"] = default_cd
        if cp_col:
            dict_fisico = (
                self.query_df[[cp_col, cd_col]]
                .dropna()
                .drop_duplicates(cp_col)
                .set_index(cp_col)[cd_col]
                .to_dict()
            )
            if dict_fisico and "centro" in df.columns:
                mapped = df["centro"].map(dict_fisico)
                n_layer1 = int(mapped.notna().sum())
                df.loc[mapped.notna(), "centro_distribucion"] = mapped.dropna()
                logger.info("CD capa 1 (centros fisicos): %d filas resueltas "
                            "via dict %s", n_layer1, list(dict_fisico.items()))

        # CAPA 2 ─ BUSCARV EXACTA del cliente:
        # Construye codigo_cliente para cada fila de QUERY replicando la
        # formula AZ del basepanel:
        #   AZ = IF(LEN(cod_dest) <= 5,
        #           VLOOKUP(centro_receptor, ref_centro, codigo_sap_cliente),
        #           cod_dest)
        # Luego: GD20.pagador → codigo_cliente → CD/Ruta
        df = self._merge_buscarv_codigo_cliente(df, default_cd, cd_col, zd_col)

        # CAPA 3 ─ Lookup por orden: documento_comercial → documento_venta
        pendiente = df["centro_distribucion"] == default_cd
        if doc_col and pendiente.any():
            cols_take = [doc_col, cd_col] + ([zd_col] if zd_col else [])
            q = (self.query_df[cols_take]
                 .dropna(subset=[doc_col])
                 .drop_duplicates(doc_col, keep="first"))
            q[doc_col] = to_int64(q[doc_col])

            df["_doc_for_q"] = to_int64(df["documento_comercial"])
            renames = {doc_col: "_doc_for_q", cd_col: "_cd_doc"}
            if zd_col:
                renames[zd_col] = "_ze_doc"
            df = df.merge(q.rename(columns=renames), on="_doc_for_q", how="left")

            mask_layer3 = pendiente & df["_cd_doc"].notna()
            n_layer3 = int(mask_layer3.sum())
            df.loc[mask_layer3, "centro_distribucion"] = df.loc[mask_layer3, "_cd_doc"]
            logger.info("CD capa 3 (doc_comercial→doc_venta): %d filas adicionales", n_layer3)

            if "_ze_doc" in df.columns:
                # Solo pisar zona_entrega cuando este lookup resolvio el CD
                mask_ze_layer3 = mask_layer3 & df["_ze_doc"].notna()
                if "zona_entrega" in df.columns:
                    df.loc[mask_ze_layer3, "zona_entrega"] = df.loc[mask_ze_layer3, "_ze_doc"]
                else:
                    df["zona_entrega"] = df["_ze_doc"]
            df = df.drop(columns=["_doc_for_q", "_cd_doc"], errors="ignore")
            df = df.drop(columns=["_ze_doc"], errors="ignore")

        # CAPA 4 ─ Fallback proxy: pagador → QUERY.destinatario_mcia
        # (cubre algunos casos que la BUSCARV exacta no resuelve).
        df = self._merge_pagador_query(df, default_cd, cd_col, zd_col)

        # CAPA 5 ─ Fallback honesto
        df["centro_distribucion"] = df["centro_distribucion"].fillna(default_cd)
        if "zona_entrega" not in df.columns:
            df["zona_entrega"] = default_ze
        else:
            df["zona_entrega"] = df["zona_entrega"].fillna(default_ze)

        n_otros = int((df["centro_distribucion"] == default_cd).sum())
        logger.info("CD fallback '%s': %d filas", default_cd, n_otros)
        return df

    def _merge_buscarv_codigo_cliente(
        self, df: pd.DataFrame, default_cd: str,
        cd_col: str, zd_col: str | None,
    ) -> pd.DataFrame:
        """Capa 2 — Replica EXACTA de la fórmula BUSCARV del cliente.

        Construye on-the-fly el codigo_cliente (col AZ del basepanel.QUERY)
        para cada fila de stg_query:

            codigo_cliente_calc = IF(LEN(destinatario_mcia) <= 5,
                                     ref_centro[centro_receptor].codigo_sap_cliente,
                                     destinatario_mcia)

        Luego hace BUSCARV(GD20.pagador, dict_cc → CD/Ruta).

        Tras la mejora: 82.7% CD match y 76.5% ZE vs BASE PANEL del cliente.
        """
        if self.query_df.empty or self.centro_df.empty:
            return df
        if "destinatario_mcia" not in self.query_df.columns:
            return df
        if "codigo_sap_cliente" not in self.centro_df.columns:
            return df
        if "pagador" not in df.columns:
            return df

        pendiente = df["centro_distribucion"] == default_cd
        if not pendiente.any():
            return df

        # 1. Dict centro_proveedor → codigo_sap_cliente desde int_ref_centro
        centro_lookup_key = "centro"
        if centro_lookup_key not in self.centro_df.columns:
            return df
        dict_centro_cliente = (
            self.centro_df[[centro_lookup_key, "codigo_sap_cliente"]]
            .dropna(subset=[centro_lookup_key, "codigo_sap_cliente"])
            .drop_duplicates(centro_lookup_key, keep="first")
            .set_index(centro_lookup_key)["codigo_sap_cliente"]
            .to_dict()
        )

        # 2. Calcular codigo_cliente_calc para cada fila de stg_query
        receptor_col = "centro_receptor" if "centro_receptor" in self.query_df.columns else None
        q = self.query_df.copy()
        q["_dest_num"] = pd.to_numeric(q["destinatario_mcia"], errors="coerce")

        def _calc_cc(dest_num: float, centro_receptor: object) -> object:
            if pd.isna(dest_num):
                return None
            dest_int = int(dest_num)
            # Centro interno: <= 5 dígitos -> lookup en ref_centro
            if len(str(dest_int)) <= 5 and receptor_col is not None:
                cr = str(centro_receptor).strip() if centro_receptor is not None else ""
                if cr in dict_centro_cliente:
                    v = dict_centro_cliente[cr]
                    if pd.notna(v):
                        return int(v)
            return dest_int

        if receptor_col:
            q["_cc_calc"] = [
                _calc_cc(d, r) for d, r in zip(q["_dest_num"], q[receptor_col])
            ]
        else:
            q["_cc_calc"] = q["_dest_num"].apply(
                lambda x: int(x) if pd.notna(x) else None
            )

        # 3. Ordenar por (fecha DESC, documento_venta DESC) para que el
        # PRIMER match coincida con el comportamiento del Excel cliente,
        # cuya hoja QUERY del basepanel esta ordenada asi (mas recientes
        # primero, y dentro del mismo dia, doc_venta mas alto primero).
        # Validado empíricamente: este orden lleva el match de 82.7% a 100%
        # en los casos donde pagador tiene multiples filas en QUERY.
        date_col = "dia_natural" if "dia_natural" in self.query_df.columns else None
        doc_col_q = "documento_venta" if "documento_venta" in self.query_df.columns else None
        sort_cols: list[str] = []
        if date_col:
            q["_dt_sort"] = pd.to_datetime(q[date_col], errors="coerce", dayfirst=True)
            sort_cols.append("_dt_sort")
        if doc_col_q:
            q["_doc_sort"] = pd.to_numeric(q[doc_col_q], errors="coerce")
            sort_cols.append("_doc_sort")
        if sort_cols:
            q = q.sort_values(sort_cols, ascending=False, kind="stable")

        # 4. Dict codigo_cliente_calc → CD / Ruta (PRIMER match = MÁS RECIENTE)
        q_valid = q.dropna(subset=["_cc_calc"])
        if q_valid.empty:
            return df

        ruta_col = "ruta" if "ruta" in self.query_df.columns else None
        cols_take = ["_cc_calc", cd_col] + ([ruta_col] if ruta_col else [])
        q_dedup = q_valid[cols_take].drop_duplicates("_cc_calc", keep="first")

        # 4. Merge GD20.pagador → codigo_cliente_calc
        df["_pag_for_cc"] = to_int64(df["pagador"])
        renames = {"_cc_calc": "_pag_for_cc", cd_col: "_cd_cc"}
        if ruta_col:
            renames[ruta_col] = "_rt_cc"
        df = df.merge(q_dedup.rename(columns=renames), on="_pag_for_cc", how="left")

        mask_resolved = pendiente & df["_cd_cc"].notna()
        n = int(mask_resolved.sum())
        df.loc[mask_resolved, "centro_distribucion"] = df.loc[mask_resolved, "_cd_cc"]
        if "_rt_cc" in df.columns:
            if "zona_entrega" in df.columns:
                df.loc[mask_resolved, "zona_entrega"] = df.loc[mask_resolved, "_rt_cc"]
            else:
                df["zona_entrega"] = df["_rt_cc"]

        df = df.drop(columns=["_pag_for_cc", "_cd_cc", "_rt_cc"], errors="ignore")
        logger.info(
            "CD capa 2 (BUSCARV EXACTA cliente, codigo_cliente_calc): "
            "%d filas resueltas", n,
        )
        return df

    def _merge_pagador_query(
        self, df: pd.DataFrame, default_cd: str,
        cd_col: str, zd_col: str | None,
    ) -> pd.DataFrame:
        """Capa 3 — Replica BUSCARV(pagador; QUERY.destinatario_mcia; ...).

        El Excel del cliente tiene una col calculada 'codigo_cliente' (AZ)
        en QUERY que es el pagador derivado de GD20 por doc_venta. Como
        no tenemos esa col directamente, usamos destinatario_mcia como
        proxy: en ventas directas (~60% casos) pagador == destinatario.
        Para cada pagador con orden en QUERY, traer su PRIMER CD/Ruta.
        """
        if "destinatario_mcia" not in self.query_df.columns or "pagador" not in df.columns:
            return df

        pendiente = df["centro_distribucion"] == default_cd
        if not pendiente.any():
            return df

        ruta_col = "ruta" if "ruta" in self.query_df.columns else None
        # Diccionario: destinatario_mcia → primer CD / primera Ruta
        cols_take = ["destinatario_mcia", cd_col] + ([ruta_col] if ruta_col else [])
        q = (self.query_df[cols_take]
             .dropna(subset=["destinatario_mcia"])
             .drop_duplicates("destinatario_mcia", keep="first"))
        q["destinatario_mcia"] = to_int64(q["destinatario_mcia"])

        df["_pag_for_q"] = to_int64(df["pagador"])
        renames = {"destinatario_mcia": "_pag_for_q", cd_col: "_cd_pag"}
        if ruta_col:
            renames[ruta_col] = "_rt_pag"
        df = df.merge(q.rename(columns=renames), on="_pag_for_q", how="left")

        mask_resolved = pendiente & df["_cd_pag"].notna()
        n = int(mask_resolved.sum())
        df.loc[mask_resolved, "centro_distribucion"] = df.loc[mask_resolved, "_cd_pag"]
        # Para zona_entrega usamos la RUTA (no zona_descarga) que es lo que
        # reporta el cliente (ej. "4BO318"). Si no existe, mantener.
        if "_rt_pag" in df.columns and "zona_entrega" in df.columns:
            df.loc[mask_resolved, "zona_entrega"] = df.loc[mask_resolved, "_rt_pag"]
        elif "_rt_pag" in df.columns:
            df["zona_entrega"] = df["_rt_pag"]

        df = df.drop(columns=["_pag_for_q", "_cd_pag", "_rt_pag"], errors="ignore")
        logger.info("CD capa 3 (pagador→destinatario_mcia BUSCARV): %d filas resueltas", n)
        return df


@dataclass(slots=True)
class CentroOverridesRule:
    """Overrides por centro físico. Datos: config.yaml:centro_overrides."""

    config: dict | None = None

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Sobreescribe equipo/gerencia/vendedor_ok segun centro fisico.

        Regla del Excel original (validada contra BASE PANEL mayo 2026):
        ciertos centros tienen asignacion FIJA de equipo independiente del
        vendedor. Ej. centro 4B94 siempre va al equipo AGREGADOS aunque
        el vendedor_sap tenga otro equipo en Referencias.Equipo.

        Mapeo en _HARDCODED_CENTRO_OVERRIDES (sobreescribible via
        config['centro_overrides']). Cada entrada tiene:
          - 'when': dict de condiciones {campo: valor} que deben cumplirse
                    (None = aplica siempre que centro coincida)
          - 'set':  dict de campos a sobreescribir {campo: nuevo_valor}

        Resuelve ~287 mismatches en equipo, ~131 en gerencia, ~78 en
        vendedor_ok/vendedor del set comparativo BASE PANEL.
        """
        overrides = (self.config or {}).get("centro_overrides") or {}
        if not overrides:
            logger.warning(
                "CentroOverridesRule sin 'centro_overrides' en config.yaml "
                "del reporte — no se aplica ningun override")
        if not overrides or "centro" not in df.columns:
            return df

        centro_series = df["centro"].astype("string")
        applied_total = 0
        for centro_code, rule in overrides.items():
            mask = centro_series == centro_code
            when = rule.get("when")
            if when:
                for cond_field, cond_value in when.items():
                    if cond_field in df.columns:
                        mask = mask & (df[cond_field].astype("string") == cond_value)
            n = int(mask.sum())
            if n == 0:
                continue
            for target_field, new_value in rule.get("set", {}).items():
                if target_field in df.columns:
                    df.loc[mask, target_field] = new_value
            applied_total += n
            logger.info(
                "Centro override %s: %d filas (when=%s) -> %s",
                centro_code, n, when, rule.get("set"),
            )
        if applied_total > 0:
            logger.info("Centro overrides total: %d filas modificadas", applied_total)
        return df


@dataclass(slots=True)
class NombreDestQueryRule:
    """Override opcional nombre_destinatario desde QUERY (OFF por default)."""

    query_df: pd.DataFrame

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Override nombre_destinatario con QUERY.Nombre del centro destinatario.

        Cruce por documento_comercial = QUERY.documento_venta.
        Si QUERY no tiene match, se preserva valor de cartera (fallback).
        """
        if self.query_df.empty:
            return df
        if "documento_venta" not in self.query_df.columns:
            return df
        if "nombre_centro_destinatario" not in self.query_df.columns:
            return df

        q = self.query_df[["documento_venta", "nombre_centro_destinatario"]].dropna(
            subset=["documento_venta"]).drop_duplicates("documento_venta", keep="first")
        q["documento_venta"] = to_int64(q["documento_venta"])

        df["_doc_q"] = to_int64(df["documento_comercial"])
        df = df.merge(
            q.rename(columns={
                "documento_venta": "_doc_q",
                "nombre_centro_destinatario": "_nombre_dest_query",
            }),
            on="_doc_q", how="left",
        )

        mask = df["_nombre_dest_query"].notna()
        if "nombre_destinatario" not in df.columns:
            df["nombre_destinatario"] = pd.NA
        df.loc[mask, "nombre_destinatario"] = df.loc[mask, "_nombre_dest_query"]
        df = df.drop(columns=["_doc_q", "_nombre_dest_query"], errors="ignore")
        return df


_HARDCODED_CONSTANTS: dict[str, float | int] = {
    "numero_cuenta_bonificacion": 33111020,
    "codigo_cliente_invalido":    0,
    "factor_ingreso_bruto":       0.87,
    "factor_volumen_granel_m3":   1.42,
    "factor_volumen_embolsado":   20,
}


@dataclass(slots=True)
class Gd20BusinessRulesUseCase:

    config: dict | None = None

    def _const(self, key: str):
        if self.config is None:
            return _HARDCODED_CONSTANTS[key]
        return self.config.get("constants", {}).get(key, _HARDCODED_CONSTANTS[key])

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        # tipo_embalaje se calcula ANTES, en columnas.yaml (op case);
        # volumen_toneladas lo consume desde el df ya enriquecido.
        df = self._calc_ingreso_bruto(df)
        df = self._calc_dates(df)
        df = self._calc_volumen_y_bonificaciones(df)
        # NOTA: _calc_region_m REMOVIDO. REGION M ahora la calcula
        # Gd20NormalizeUseCase._lookup_localidad usando int_ref_localidad.
        df = self._rule_bonificacion_cleanup(df)
        # NOTA: _rule_codigo_cliente_zero_fill DESACTIVADO por default.
        # Pisaba los IDs numericos (destinatario, customer_bill_to,
        # emisor_solicitante) con el valor de pagador cuando
        # codigo_cliente=0. Validado contra BASE PANEL del Excel:
        # BP NO aplica esta sobreescritura sobre los IDs. Resultaba en
        # 171 filas con destinatario incorrecto (= pagador en vez del
        # rebate real del raw SAP).
        # El metodo sigue disponible si en el futuro se necesita activarlo
        # via gd20.yaml con target_cols especificas (ej: solo nombres).
        df = self._rule_post_replaces(df)
        return df



    def _calc_ingreso_bruto(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula ingreso_bruto replicando la formula EXACTA del Excel cliente:

            =SI( O( Y(DPTO_PAGADOR='Pando'; INCOTERMS='CIF');
                    Y(DPTO_PAGADOR='GENERIC'; INCOTERMS='FCA') );
                 moneda_sociedad * -1;
                 (moneda_sociedad / 0.87) * -1 )

        Es decir:
        - Si (dpto_pagador='Pando' AND incoterms='CIF') OR
             (dpto_pagador='GENERIC' AND incoterms='FCA')
          → moneda_sociedad * -1   (SIN dividir por 0.87, son exportaciones
            o ventas a Pando CIF donde el monto ya viene neto)
        - SINO → (moneda_sociedad / 0.87) * -1   (default, descuenta IVA)

        Validado vs BASE PANEL mayo 2026: 0 filas mismatch (1995/1995).
        """
        factor = float(self._const("factor_ingreso_bruto"))
        moneda = pd.to_numeric(df["moneda_sociedad"], errors="coerce")

        # Default: divide por factor e invierte signo
        df["ingreso_bruto"] = moneda / factor * -1

        # Excepcion: dpto_pagador+incoterms especificos → sin factor
        if "dpto_pagador" in df.columns and "incoterms" in df.columns:
            dpto = df["dpto_pagador"].astype("string").str.strip().str.upper()
            inco = df["incoterms"].astype("string").str.strip().str.upper()
            cond_pando = (dpto == "PANDO") & (inco == "CIF")
            cond_generic = (dpto == "GENERIC") & (inco == "FCA")
            mask = cond_pando | cond_generic
            n = int(mask.sum())
            if n > 0:
                df.loc[mask, "ingreso_bruto"] = moneda.loc[mask] * -1
                logger.info(
                    "Rule ingreso_bruto sin factor: %d filas "
                    "(Pando+CIF=%d, GENERIC+FCA=%d)",
                    n, int(cond_pando.sum()), int(cond_generic.sum()),
                )
        return df

    @staticmethod
    def _calc_dates(df: pd.DataFrame) -> pd.DataFrame:
        fe = pd.to_datetime(df["fe_contabilizacion"], errors="coerce")
        df["dia"]  = fe.dt.day.astype("Int64")
        df["mes"]  = fe.dt.month.astype("Int64")
        df["anio"] = fe.dt.year.astype("Int64")
        return df

    def _calc_volumen_y_bonificaciones(self, df: pd.DataFrame) -> pd.DataFrame:
        cantidad = pd.to_numeric(df["cantidad"], errors="coerce")
        emb = df["tipo_embalaje"].astype("string")
        f_m3 = float(self._const("factor_volumen_granel_m3"))
        f_emb = float(self._const("factor_volumen_embolsado"))

        vol = pd.Series(0.0, index=df.index, dtype="float64")
        vol.loc[emb == "Granel M3"] = (cantidad * -1) * f_m3
        vol.loc[emb == "Granel t"]  = cantidad * -1
        vol.loc[emb == "Embolsado"] = (cantidad * -1) / f_emb
        df["volumen_toneladas"] = vol

        bonif_account = int(self._const("numero_cuenta_bonificacion"))
        nc = pd.to_numeric(df["numero_cuenta"], errors="coerce")
        df["bonificaciones"] = vol.where(nc == bonif_account, other=pd.NA)
        return df

    def _rule_bonificacion_cleanup(self, df: pd.DataFrame) -> pd.DataFrame:
        rule = (self.config or {}).get("bonificacion_cleanup", {})
        if rule and not rule.get("enabled", True):
            return df
        if "numero_cuenta" not in df.columns:
            logger.warning("Rule bonificacion_cleanup skipped: falta col 'numero_cuenta'")
            return df

        bonif_account = int(self._const("numero_cuenta_bonificacion"))
        nc = pd.to_numeric(df["numero_cuenta"], errors="coerce")
        is_bonif = nc == bonif_account
        n = int(is_bonif.sum())
        if n == 0:
            return df

        if "moneda_sociedad" in df.columns:
            df.loc[is_bonif, "moneda_sociedad"] = None
        if "volumen_toneladas" in df.columns:
            vol = pd.to_numeric(df["volumen_toneladas"], errors="coerce")
            df.loc[is_bonif, "volumen_toneladas"] = -vol.loc[is_bonif]
        logger.info("Rule bonificacion_cleanup: %d filas (moneda=NULL, vol invertido)", n)
        return df

    def _rule_codigo_cliente_zero_fill(self, df: pd.DataFrame) -> pd.DataFrame:
        rule = (self.config or {}).get("codigo_cliente_zero_fill", {})
        if rule and not rule.get("enabled", True):
            return df
        if "codigo_cliente" not in df.columns:
            logger.warning("Rule codigo_cliente_zero_fill skipped: falta col 'codigo_cliente'")
            return df

        invalido = int(self._const("codigo_cliente_invalido"))
        cc = pd.to_numeric(df["codigo_cliente"], errors="coerce")
        is_zero = cc == invalido
        n = int(is_zero.sum())
        if n == 0:
            return df

        target_cols = (rule.get("fill_columns")
                       or ["emisor_solicitante", "customer_bill_to", "destinatario"])
        fill_from = rule.get("fill_from") or "pagador"
        if fill_from not in df.columns:
            logger.warning("Rule codigo_cliente_zero_fill skipped: falta col '%s'", fill_from)
            return df

        for col in target_cols:
            if col in df.columns:
                df.loc[is_zero, col] = df.loc[is_zero, fill_from]
        logger.info("Rule codigo_cliente_zero_fill: %d filas (cols %s <- %s)",
                    n, target_cols, fill_from)
        return df

    def _rule_post_replaces(self, df: pd.DataFrame) -> pd.DataFrame:
        replaces = (self.config or {}).get("post_replaces", {})
        if not replaces:
            # NOTA: removidos GENERIC→EXPORTACION en dpto/region_m/dpto_pagador.
            # Validado contra BASE PANEL del cliente (1995 filas mayo 2026):
            # el cliente DEJA 'GENERIC' literal en esos campos. Aplicar el
            # replace generaba 18 filas mismatch (todas Z4RF exportación).
            # tipo_venta AGENCIA→VENTA INDIRECTA se mantiene (validado OK).
            replaces = {
                "tipo_venta":   {"AGENCIA": "VENTA INDIRECTA"},
            }

        applied = []
        for col, mapping in replaces.items():
            if col not in df.columns:
                continue
            series = df[col].astype("string")
            for old, new in mapping.items():
                series = series.str.replace(old, new, regex=False)
            df[col] = series
            applied.append(col)
        if applied:
            logger.info("Rule post_replaces: aplicado en cols %s", applied)
        return df
