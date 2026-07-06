"""GD20 Normalize - aplica los 7 lookups contra tablas referencia."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from itacamba_reportes.shared.pandas_utils import to_int64

logger = logging.getLogger(__name__)


_HARDCODED_DEFAULTS: dict[str, str] = {
    "vendedor_sap":        "0",
    "vendedor_ok":         "0",
    "vendedor":            "0",
    "equipo":              "No encontrado",
    "gerencia":            "0",
    "canal":               "0",
    "sub_canal":           "0",
    "tipo_venta":          "VENTA DIRECTA",
    "centro_distribucion": "OTROS",
    "zona_entrega":        "OTROS",
    "nombre_producto":     "0",
    "nombre_pagador":      "0",
    "nombre_solicitante":  "0",
    "nombre_destinatario": "0",
    "localidad":           "0",
    "provincia":           "0",
    "dpto":                "0",
    "localidad_pagador":   "0",
    "dpto_pagador":        "0",
    "region_m_sc_default": "RESTO SANTA CRUZ",
}


# Overrides por CENTRO físico — sobreescribe campos cuando un centro
# específico tiene asignación fija de equipo/gerencia/vendedor_ok,
# independiente del vendedor_sap (regla del Excel original validada
# contra BASE PANEL mayo 2026).
# Estructura: {centro: {when_field: value_match, target_field: new_value}}
#   - "when": condiciones que deben cumplirse (None = aplica siempre)
#   - "set":  campos a sobreescribir
_HARDCODED_CENTRO_OVERRIDES: dict[str, dict] = {
    "4B05": {
        "when": {"equipo": "LOGISTICA"},
        "set":  {"equipo": "CLINQUER"},
    },
    "4B06": {
        "when": {"equipo": "LOGISTICA"},
        "set":  {"equipo": "CLINQUER"},
    },
    "4B3A": {
        "when": None,  # aplica siempre
        "set":  {"equipo": "INSUMOS AGRICOLAS", "gerencia": "OTROS"},
    },
    "4B94": {
        "when": None,
        "set":  {
            "equipo":      "AGREGADOS",
            "gerencia":    "OTROS",
            "vendedor_ok": "AGREGADOS",
        },
    },
    "4B95": {
        "when": {"equipo": "DESARROLLADORES OTROS DPTOS."},
        "set":  {
            "equipo":      "DESARROLLADORES SCZ",
            "gerencia":    "GERENCIA SCZ+CHACO",
            "vendedor_ok": "FREDDY ROMAN",
        },
    },
}


@dataclass(slots=True)
class Gd20NormalizeUseCase:

    cartera_df: pd.DataFrame
    equipo_df: pd.DataFrame
    almacen_df: pd.DataFrame
    material_df: pd.DataFrame
    centro_df: pd.DataFrame
    query_df: pd.DataFrame
    localidad_df: pd.DataFrame
    config: dict | None = None

    def _default(self, key: str) -> str:
        if self.config is None:
            return _HARDCODED_DEFAULTS[key]
        return self.config.get("defaults", {}).get(key, _HARDCODED_DEFAULTS[key])

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        # ORDEN IMPORTANTE: material va ANTES que equipo porque la lógica
        # de equipo del cliente es condicional al producto (si contiene
        # "CEMENTO" usa vendedor_sap, sino usa grupo_vendedores).
        df = self._lookup_cartera(df)
        df = self._lookup_material(df)   # nombre_producto (para condicional CEMENTO)
        df = self._lookup_equipo(df)     # equipo + vendedor + vendedor_ok + gerencia
        df = self._lookup_almacen(df)
        df = self._lookup_centro(df)
        df = self._lookup_query(df)
        df = self._lookup_localidad(df)
        df = self._lookup_centro_equipo_override(df)
        # NOTA: _lookup_query_nombre_destinatario DESACTIVADO por default.
        # QUERY.Nombre_del_centro_destinatario contiene el nombre del PUNTO
        # DE DESCARGA con dirección abreviada (ej. "REGNANS/COTOCA"),
        # NO el nombre legal/completo del cliente. Pisa el valor correcto
        # que ya trae cartera (ej. "CONSTRUCTORA REGNANS S.R.L.").
        # Validado contra BASE PANEL del cliente: BP usa nombre de cartera
        # (54% mismatch entre cartera y QUERY en GD20 mayo 2026).
        # El método sigue disponible si en el futuro se necesita activarlo
        # con target específico (ej. solo para destinatarios = centros 4xxx).
        if (self.config or {}).get("override_nombre_dest_from_query", False):
            df = self._lookup_query_nombre_destinatario(df)
        return df

    def _lookup_cartera(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.cartera_df.empty:
            logger.warning("int_cartera vacio")
            return df

        cart = self.cartera_df[[
            "cliente", "nombre_cliente", "vendedor",
            "poblacion", "attribute_6", "region_nombre",
        ]].drop_duplicates("cliente", keep="first")
        cart["cliente"] = to_int64(cart["cliente"])

        df["_dest_int"] = to_int64(df["destinatario"])
        d1 = cart.rename(columns={
            "nombre_cliente": "nombre_destinatario",
            "vendedor":       "vendedor_sap",
            "poblacion":      "localidad",
            "attribute_6":    "provincia",
            "region_nombre":  "dpto",
            "cliente":        "_dest_int",
        })
        df = df.merge(d1[["_dest_int", "nombre_destinatario", "vendedor_sap",
                          "localidad", "provincia", "dpto"]],
                      on="_dest_int", how="left")

        df["_pag_int"] = to_int64(df["pagador"])
        d2 = cart.rename(columns={
            "nombre_cliente": "nombre_pagador",
            "poblacion":      "localidad_pagador",
            "region_nombre":  "dpto_pagador",
            "cliente":        "_pag_int",
        })
        df = df.merge(d2[["_pag_int", "nombre_pagador", "localidad_pagador", "dpto_pagador"]],
                      on="_pag_int", how="left")

        df["_sol_int"] = to_int64(df["emisor_solicitante"])
        d3 = cart.rename(columns={"nombre_cliente": "nombre_solicitante", "cliente": "_sol_int"})
        df = df.merge(d3[["_sol_int", "nombre_solicitante"]], on="_sol_int", how="left")

        cart_attr10 = self.cartera_df[["cliente", "attribute_10"]].drop_duplicates(
            "cliente", keep="first")
        cart_attr10["cliente"] = to_int64(cart_attr10["cliente"])
        df = df.merge(
            cart_attr10.rename(columns={"attribute_10": "_attr10_dest", "cliente": "_dest_int"}),
            on="_dest_int", how="left",
        )
        df = df.drop(columns=["_dest_int", "_pag_int", "_sol_int"], errors="ignore")

        for col in ["nombre_destinatario", "vendedor_sap", "localidad", "provincia",
                    "dpto", "nombre_pagador", "localidad_pagador", "dpto_pagador",
                    "nombre_solicitante"]:
            if col in df.columns:
                df[col] = df[col].fillna(self._default(col))
        return df

    def _lookup_equipo(self, df: pd.DataFrame) -> pd.DataFrame:
        """Replica EXACTA de las 4 formulas del cliente (BASE PANEL cols BC-BG).

        Cliente:
            BC (vendedor_sap)  = ya viene de _lookup_cartera (CARTERA col 33)
            BD (vendedor)      = VLOOKUP(BC, REFERENCIAS!O:S, 2, 0)
            BE (vendedor_ok)   = VLOOKUP(BC, REFERENCIAS!O:S, 3, 0)
            BF (gerencia)      = VLOOKUP(BG, REFERENCIAS!R:S, 2, 0)      ← por EQUIPO
            BG (equipo)        = IF(producto contiene "CEMENTO",
                                    VLOOKUP(BC, REFERENCIAS!O:S, 4, 0),   ← por vendedor_sap
                                    VLOOKUP(Q,  REFERENCIAS!N:S, 5, 0))   ← por grupo_vendedores

        Es decir:
          - vendedor, vendedor_ok: SIEMPRE por vendedor_sap.
          - equipo: CONDICIONAL al producto.
            * Si producto contiene "CEMENTO" → equipo via vendedor_sap.
            * Si NO contiene "CEMENTO" → equipo via grupo_vendedores (Q del raw).
          - gerencia: por equipo (resultado del lookup anterior).

        Requiere que nombre_producto YA este calculado (_lookup_material).
        """
        if self.equipo_df.empty:
            df["vendedor_ok"] = self._default("vendedor_ok")
            df["equipo"]      = self._default("equipo")
            df["gerencia"]    = self._default("gerencia")
            df["vendedor"]    = self._default("vendedor")
            return df

        # --- 1) vendedor + vendedor_ok: lookup por vendedor_sap (SIEMPRE) ---
        eq_by_sap = self.equipo_df[["vendedor_sap", "vendedor", "vendedor_ok", "equipo"]].dropna(
            subset=["vendedor_sap"]).drop_duplicates("vendedor_sap", keep="first")
        df = df.merge(
            eq_by_sap.rename(columns={"equipo": "_equipo_por_vendedor"}),
            on="vendedor_sap", how="left",
        )

        # --- 2) equipo via grupo_vendedores (fallback cuando NO es cemento) ---
        eq_by_grupo = self.equipo_df[["grupo_vendedores", "equipo"]].dropna(
            subset=["grupo_vendedores"]).drop_duplicates("grupo_vendedores", keep="first")
        df = df.merge(
            eq_by_grupo.rename(columns={"equipo": "_equipo_por_grupo"}),
            on="grupo_vendedores", how="left",
        )

        # --- 3) Aplicar la lógica condicional CEMENTO ---
        if "nombre_producto" in df.columns:
            es_cemento = df["nombre_producto"].astype("string").str.contains(
                "CEMENTO", case=False, na=False,
            )
        else:
            # Si nombre_producto no esta calculado, fallback al vendedor_sap (caso edge)
            logger.warning("_lookup_equipo: nombre_producto no disponible, "
                           "usando vendedor_sap como default para equipo")
            es_cemento = pd.Series(True, index=df.index)

        df["equipo"] = df["_equipo_por_vendedor"].where(
            es_cemento, df["_equipo_por_grupo"],
        )
        n_cemento = int(es_cemento.sum())
        n_no_cemento = int((~es_cemento).sum())
        logger.info(
            "Equipo lookup: %d filas via vendedor_sap (CEMENTO), %d via grupo_vendedores",
            n_cemento, n_no_cemento,
        )

        # --- 4) gerencia: VLOOKUP por equipo en REF.Equipo col S ---
        eq_to_ger = self.equipo_df[["equipo", "gerencia"]].dropna(
            subset=["equipo"]).drop_duplicates("equipo", keep="first")
        df = df.merge(eq_to_ger, on="equipo", how="left", suffixes=("", "_ger"))

        # --- 5) Limpieza + defaults ---
        df["vendedor"]    = df["vendedor"].fillna(self._default("vendedor"))
        df["vendedor_ok"] = df["vendedor_ok"].fillna(self._default("vendedor_ok"))
        df["equipo"]      = df["equipo"].fillna(self._default("equipo"))
        df["gerencia"]    = df["gerencia"].fillna(self._default("gerencia"))
        df = df.drop(
            columns=["_equipo_por_vendedor", "_equipo_por_grupo"],
            errors="ignore",
        )
        return df

    def _lookup_almacen(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.almacen_df.empty:
            df["sub_canal"] = self._default("sub_canal")
            df["canal"]     = self._default("canal")
            df = df.drop(columns=["_attr10_dest"], errors="ignore")
            return df

        alm = self.almacen_df[["descripcion_sap", "segmento", "canal"]].drop_duplicates(
            "descripcion_sap", keep="first")
        df = df.merge(
            alm.rename(columns={"descripcion_sap": "_attr10_dest", "segmento": "sub_canal"}),
            on="_attr10_dest", how="left",
        )
        df["sub_canal"] = df["sub_canal"].fillna(self._default("sub_canal"))
        df["canal"]     = df["canal"].fillna(self._default("canal"))
        df = df.drop(columns=["_attr10_dest"], errors="ignore")
        return df

    def _lookup_material(self, df: pd.DataFrame) -> pd.DataFrame:
        """Replica VLOOKUP(material, REFERENCIAS!L:M, 2, 0) → nombre_producto.

        Debe ejecutarse ANTES de _lookup_equipo porque la logica de equipo
        depende de si nombre_producto contiene 'CEMENTO' o no.
        """
        if self.material_df.empty:
            df["nombre_producto"] = self._default("nombre_producto")
            return df

        mat = self.material_df[["codigo", "descripcion"]].drop_duplicates("codigo", keep="first")
        mat["codigo"] = to_int64(mat["codigo"])

        df["_mat_int"] = to_int64(df["material"])
        df = df.merge(
            mat.rename(columns={"codigo": "_mat_int", "descripcion": "nombre_producto"}),
            on="_mat_int", how="left",
        )
        df["nombre_producto"] = df["nombre_producto"].fillna(self._default("nombre_producto"))
        df = df.drop(columns=["_mat_int"], errors="ignore")
        return df

    def _lookup_centro(self, df: pd.DataFrame) -> pd.DataFrame:
        default_tv = self._default("tipo_venta")
        df["codigo_cliente"] = pd.NA

        if self.centro_df.empty or "codigo_sap_cliente" not in self.centro_df.columns:
            df["tipo_venta"] = default_tv
            return df

        cen = self.centro_df[["codigo_sap_cliente", "tipo"]].dropna(
            subset=["codigo_sap_cliente"]).drop_duplicates("codigo_sap_cliente", keep="first")
        cen["codigo_sap_cliente"] = to_int64(cen["codigo_sap_cliente"])
        df["_pag_for_tipo"] = to_int64(df["pagador"])
        df = df.merge(
            cen.rename(columns={"codigo_sap_cliente": "_pag_for_tipo", "tipo": "tipo_venta"}),
            on="_pag_for_tipo", how="left",
        )
        df["tipo_venta"] = df["tipo_venta"].fillna(default_tv)
        df = df.drop(columns=["_pag_for_tipo"], errors="ignore")

        if "centro" in self.centro_df.columns and "centro" in df.columns:
            cen2 = self.centro_df[["centro", "codigo_sap_cliente"]].dropna(
                subset=["centro"]).drop_duplicates("centro", keep="first")
            df = df.drop(columns=["codigo_cliente"], errors="ignore")
            df = df.merge(
                cen2.rename(columns={"codigo_sap_cliente": "codigo_cliente"}),
                on="centro", how="left",
            )
            df["codigo_cliente"] = df["codigo_cliente"].fillna(0)
        return df

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

    def _lookup_localidad(self, df: pd.DataFrame) -> pd.DataFrame:
        """REGION M: si DPTO=='SANTA CRUZ' lookup case-insensitive
        LOCALIDAD -> LOCALIDAD IM (int_ref_localidad). Sino, REGION M = DPTO.
        """
        df["region_m"] = df["dpto"].astype("string")
        if self.localidad_df.empty:
            logger.warning("int_ref_localidad vacio; region_m queda = dpto plano")
            return df

        is_sc = df["dpto"].astype("string").str.upper().str.strip() == "SANTA CRUZ"
        if not is_sc.any():
            return df

        loc = self.localidad_df[["localidad_despacho", "localidad_im"]].dropna(
            subset=["localidad_despacho"]).drop_duplicates(
            "localidad_despacho", keep="first").copy()
        loc["_loc_norm"] = loc["localidad_despacho"].astype("string").str.upper().str.strip()
        loc = loc.drop_duplicates("_loc_norm", keep="first")

        df["_loc_norm"] = df["localidad"].astype("string").str.upper().str.strip()
        df = df.merge(
            loc[["_loc_norm", "localidad_im"]].rename(columns={"localidad_im": "_region_m_lookup"}),
            on="_loc_norm", how="left",
        )

        sc_default = self._default("region_m_sc_default")
        df.loc[is_sc, "region_m"] = (
            df.loc[is_sc, "_region_m_lookup"].fillna(sc_default)
        )
        df = df.drop(columns=["_loc_norm", "_region_m_lookup"], errors="ignore")
        return df

    def _lookup_centro_equipo_override(self, df: pd.DataFrame) -> pd.DataFrame:
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
        overrides = (self.config or {}).get(
            "centro_overrides", _HARDCODED_CENTRO_OVERRIDES,
        )
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

    def _lookup_query_nombre_destinatario(self, df: pd.DataFrame) -> pd.DataFrame:
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
