from __future__ import annotations

import logging
from datetime import datetime
from time import perf_counter
from typing import Any
import pandas as pd
from sqlalchemy import bindparam, text

from itacamba_reportes.core.audit.hashing import add_hashes_to_df
from itacamba_reportes.core.db.bulk import bulk_insert_df
from itacamba_reportes.core.db.connection import engine
from itacamba_reportes.outputs.ventas_bi.models import SalesBiIntModel

logger = logging.getLogger(__name__)


def _build_composite_keys(df: pd.DataFrame, cols: list[str]) -> list[str]:
    if df.empty:
        return []
    return ["|".join(parts) for parts in zip(*(df[c].astype(str).tolist() for c in cols))]


def _execute_chunked_ids(
    conn: Any,
    sql_template: str,
    ids: list[int],
    extra_params: dict[str, Any] | None = None,
    chunk_size: int = 1000,
) -> None:
    stmt = text(sql_template).bindparams(bindparam("ids", expanding=True))
    for i in range(0, len(ids), chunk_size):
        params: dict[str, Any] = {"ids": ids[i:i + chunk_size]}
        if extra_params:
            params.update(extra_params)
        conn.execute(stmt, params)

# Columnas SAP de origen vs Columnas calculadas derivadas
SOURCE_COLS = (
    "ejercicio", "sociedad", "organizacion_ventas", "centro", "division", "oficina_ventas",
    "canal_distribucion", "sector", "numero_cuenta", "centro_beneficio", "material",
    "unidad_medida_base", "periodo_contable", "clave_pais", "region_sap", "poblacion_sap",
    "grupo_vendedores", "pagador", "emisor_solicitante", "customer_bill_to", "destinatario",
    "grupo_clientes_2", "atributo_6", "atributo_7", "atributo_10", "clase_factura",
    "nombre_usuario", "texto", "numero_documento", "cantidad", "moneda_sociedad",
    "fe_contabilizacion", "fecha_entrada", "fecha_valor", "documento_comercial",
    "hora_entrada", "moneda_transaccion", "clave_moneda_transaccion", "moneda_fuerte",
    "clave_moneda_fuerte", "numero_doc_referencia", "numero_documento_2", "incoterms",
    "incoterms_parte_2", "clase_documento", "cond_pago", "dias_1", "numero_transporte", "e",
)

DERIVED_COLS = (
    "tipo_embalaje", "nombre_producto", "volumen_toneladas", "nombre_pagador",
    "nombre_solicitante", "vendedor_sap", "vendedor", "vendedor_ok", "gerencia", "equipo",
    "canal", "sub_canal", "dia", "mes", "anio", "tipo_venta", "localidad", "provincia",
    "dpto", "region_m", "ingreso_bruto", "dpto_pagador", "localidad_pagador",
    "codigo_cliente", "bonificaciones", "centro_distribucion", "zona_entrega", "nombre_destinatario",
)


def upsert_ventas_bi_scd2(force_rebuild: bool = False) -> int:
    t0 = perf_counter()
    logger.info("Iniciando acumulacion SCD2 en int_ventas_bi...")

    with engine.connect() as conn:
        df_int = pd.read_sql("SELECT * FROM int_gd20", conn)

    if df_int.empty:
        logger.warning("int_gd20 esta vacio, nada que acumular en int_ventas_bi")
        return 0

    df_int = add_hashes_to_df(df_int, SOURCE_COLS, DERIVED_COLS)
    now = datetime.now().replace(microsecond=0)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    with engine.connect() as conn:
        count_existing = conn.execute(text("SELECT COUNT(*) FROM int_ventas_bi")).scalar() or 0

    if count_existing == 0:
        df_int["version"] = 1
        df_int["is_current"] = True
        df_int["valid_from"] = now
        df_int["valid_to"] = None
        df_int["cd_status"] = "PENDING"
        df_int["full_row_hash"] = df_int["full_hash"]

        cols = [c.name for c in SalesBiIntModel.__table__.columns if c.name not in ("id", "created_at", "updated_at")]
        valid_cols = [c for c in cols if c in df_int.columns]
        rows = bulk_insert_df(SalesBiIntModel, df_int[valid_cols], truncate_first=False)
        logger.info("Carga inicial int_ventas_bi: %d filas insertadas", rows)
        return rows

    query_existing = """
    SELECT id, ejercicio, documento_comercial, numero_documento, material,
           version, source_hash, derived_hash, cd_status, valid_from
    FROM int_ventas_bi
    WHERE is_current = 1
    """
    with engine.connect() as conn:
        df_existing = pd.read_sql(query_existing, conn)

    biz_key = ["ejercicio", "documento_comercial", "numero_documento", "material"]
    df_existing["key"] = _build_composite_keys(df_existing, biz_key)
    df_int["key"] = _build_composite_keys(df_int, biz_key)

    existing_map = df_existing.set_index("key").to_dict(orient="index")

    to_insert = []
    ids_to_expire: list[int] = []
    ids_to_replace_today: list[int] = []
    today_date = now.date()

    for r_dict in df_int.to_dict(orient="records"):
        k = r_dict["key"]
        r_dict["full_row_hash"] = r_dict["full_hash"]

        if k not in existing_map:
            # Documento nuevo en el historico
            r_dict["version"] = 1
            r_dict["is_current"] = True
            r_dict["valid_from"] = now
            r_dict["valid_to"] = None
            r_dict["cd_status"] = "PENDING"
            to_insert.append(r_dict)
        else:
            ext = existing_map[k]
            ext_vf = ext.get("valid_from")
            if hasattr(ext_vf, "date"):
                ext_date = ext_vf.date()
            elif isinstance(ext_vf, str):
                ext_date = pd.to_datetime(ext_vf).date()
            else:
                ext_date = None

            if ext["source_hash"] != r_dict["source_hash"]:
                # Caso 1: Los datos SAP cambiaron. Si se registraron hoy mismo, sobreescribir hoy sin duplicar version
                if ext_date == today_date:
                    ids_to_replace_today.append(int(ext["id"]))
                    r_dict["version"] = ext["version"]
                else:
                    ids_to_expire.append(int(ext["id"]))
                    r_dict["version"] = ext["version"] + 1

                r_dict["is_current"] = True
                r_dict["valid_from"] = now
                r_dict["valid_to"] = None
                r_dict["cd_status"] = "PENDING"
                to_insert.append(r_dict)

            elif ext["derived_hash"] != r_dict["derived_hash"] or force_rebuild:
                # Caso 2: Las reglas de negocio o catalogos cambiaron -> actualizar en sitio
                ids_to_replace_today.append(int(ext["id"]))
                r_dict["version"] = ext["version"]
                r_dict["is_current"] = True
                r_dict["valid_from"] = ext_vf or now
                r_dict["valid_to"] = None
                r_dict["cd_status"] = ext.get("cd_status", "PENDING")
                to_insert.append(r_dict)

    with engine.begin() as conn:
        if ids_to_replace_today:
            _execute_chunked_ids(conn, "DELETE FROM int_ventas_bi WHERE id IN :ids", ids_to_replace_today)

        if ids_to_expire:
            _execute_chunked_ids(
                conn,
                "UPDATE int_ventas_bi SET is_current = 0, valid_to = :val_to WHERE id IN :ids",
                ids_to_expire,
                extra_params={"val_to": now_str},
            )

    if to_insert:
        df_ins = pd.DataFrame(to_insert)
        cols = [c.name for c in SalesBiIntModel.__table__.columns if c.name not in ("id", "created_at", "updated_at")]
        valid_cols = [c for c in cols if c in df_ins.columns]
        bulk_insert_df(SalesBiIntModel, df_ins[valid_cols], truncate_first=False)

    affected = len(to_insert)
    logger.info("Upsert SCD2 completado: %d registros insertados/actualizados (reemplazo hoy=%d, expirados=%d) en %.2fs", affected, len(ids_to_replace_today), len(ids_to_expire), perf_counter() - t0)
    return affected
