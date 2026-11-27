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


def _norm_key_token(v: Any) -> str:
    if v is None or pd.isna(v):
        return ""
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else str(v)
    s = str(v).strip()
    return s[:-2] if s.endswith(".0") and s[:-2].lstrip("-").isdigit() else s


def _build_composite_keys(df: pd.DataFrame, cols: list[str]) -> list[str]:
    if df.empty:
        return []
    norm_cols: list[list[str]] = []
    for c in cols:
        if c not in df.columns:
            norm_cols.append([""] * len(df))
        else:
            norm_cols.append([_norm_key_token(v) for v in df[c].tolist()])

    base_keys = ["|".join(parts) for parts in zip(*norm_cols)]
    seen: dict[str, int] = {}
    unique_keys: list[str] = []
    for bk in base_keys:
        occ = seen.get(bk, 0)
        seen[bk] = occ + 1
        unique_keys.append(f"{bk}#{occ}")
    return unique_keys


def _build_scoped_existing_query(df_int: pd.DataFrame) -> tuple[str, dict[str, Any]]:
    base_select = """
    SELECT id, ejercicio, periodo_contable, documento_comercial, numero_documento,
           numero_cuenta, destinatario, material, version, source_hash, derived_hash,
           cd_status, valid_from
    FROM int_ventas_bi
    WHERE is_current = 1
    """
    if "ejercicio" not in df_int.columns or "periodo_contable" not in df_int.columns:
        return base_select, {}

    pairs_df = df_int[["ejercicio", "periodo_contable"]].drop_duplicates()
    if pairs_df.empty or len(pairs_df) > 24:
        return base_select, {}

    clauses: list[str] = []
    params: dict[str, Any] = {}
    for idx, (ej_val, per_val) in enumerate(pairs_df.itertuples(index=False, name=None)):
        if pd.isna(ej_val):
            ej_clause = "ejercicio IS NULL"
        else:
            ej_key = f"ej_{idx}"
            params[ej_key] = int(float(ej_val))
            ej_clause = f"ejercicio = :{ej_key}"

        if pd.isna(per_val):
            per_clause = "periodo_contable IS NULL"
        else:
            per_key = f"per_{idx}"
            params[per_key] = int(float(per_val))
            per_clause = f"periodo_contable = :{per_key}"

        clauses.append(f"({ej_clause} AND {per_clause})")

    return f"{base_select} AND ({' OR '.join(clauses)})", params


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

    model_cols = [c.name for c in SalesBiIntModel.__table__.columns if c.name not in ("id", "created_at", "updated_at")]

    if count_existing == 0:
        df_int["version"] = 1
        df_int["is_current"] = True
        df_int["valid_from"] = now
        df_int["valid_to"] = None
        df_int["cd_status"] = "PENDING"
        df_int["full_row_hash"] = df_int["full_hash"]

        valid_cols = [c for c in model_cols if c in df_int.columns]
        rows = bulk_insert_df(SalesBiIntModel, df_int[valid_cols], truncate_first=False)
        logger.info("Carga inicial int_ventas_bi: %d filas insertadas", rows)
        return rows

    sort_order_cols = [
        c for c in ("ejercicio", "documento_comercial", "numero_documento", "numero_cuenta", "destinatario", "material", "id")
        if c in df_int.columns
    ]
    if sort_order_cols:
        df_int = df_int.sort_values(by=sort_order_cols, kind="mergesort", na_position="first").reset_index(drop=True)

    query_existing, query_params = _build_scoped_existing_query(df_int)
    with engine.connect() as conn:
        df_existing = pd.read_sql(text(query_existing), conn, params=query_params)

    existing_sort_cols = [
        c for c in ("ejercicio", "documento_comercial", "numero_documento", "numero_cuenta", "destinatario", "material", "id")
        if c in df_existing.columns
    ]
    if not df_existing.empty and existing_sort_cols:
        df_existing = df_existing.sort_values(by=existing_sort_cols, kind="mergesort", na_position="first").reset_index(drop=True)

    biz_key = ["ejercicio", "documento_comercial", "numero_documento", "numero_cuenta", "destinatario", "material"]
    df_int["key"] = _build_composite_keys(df_int, biz_key)
    df_existing["key"] = _build_composite_keys(df_existing, biz_key)

    df_ext_slim = df_existing[["key", "id", "version", "source_hash", "derived_hash", "cd_status", "valid_from"]].rename(
        columns={
            "id": "id_ext",
            "version": "version_ext",
            "source_hash": "source_hash_ext",
            "derived_hash": "derived_hash_ext",
            "cd_status": "cd_status_ext",
            "valid_from": "valid_from_ext",
        }
    )
    merged = df_int.merge(df_ext_slim, on="key", how="left", sort=False)

    is_new = merged["id_ext"].isna()
    src_changed = (~is_new) & (merged["source_hash"] != merged["source_hash_ext"])
    der_changed = (~is_new) & (~src_changed) & ((merged["derived_hash"] != merged["derived_hash_ext"]) | force_rebuild)

    ext_dates = pd.to_datetime(merged["valid_from_ext"], errors="coerce").dt.date
    today_date = now.date()
    is_today = src_changed & (ext_dates == today_date)
    is_hist = src_changed & (~is_today)

    ids_to_replace_today = [
        int(x) for x in merged.loc[is_today | der_changed, "id_ext"].dropna().tolist()
    ]
    ids_to_expire = [
        int(x) for x in merged.loc[is_hist, "id_ext"].dropna().tolist()
    ]

    batches: list[pd.DataFrame] = []
    if is_new.any():
        df_new = df_int.loc[is_new.values].copy()
        df_new["full_row_hash"] = df_new["full_hash"]
        df_new["version"] = 1
        df_new["is_current"] = True
        df_new["valid_from"] = now
        df_new["valid_to"] = None
        df_new["cd_status"] = "PENDING"
        batches.append(df_new)

    if is_today.any():
        df_tod = df_int.loc[is_today.values].copy()
        df_tod["full_row_hash"] = df_tod["full_hash"]
        df_tod["version"] = merged.loc[is_today, "version_ext"].astype(int).values
        df_tod["is_current"] = True
        df_tod["valid_from"] = now
        df_tod["valid_to"] = None
        df_tod["cd_status"] = "PENDING"
        batches.append(df_tod)

    if is_hist.any():
        df_hist = df_int.loc[is_hist.values].copy()
        df_hist["full_row_hash"] = df_hist["full_hash"]
        df_hist["version"] = (merged.loc[is_hist, "version_ext"].astype(int) + 1).values
        df_hist["is_current"] = True
        df_hist["valid_from"] = now
        df_hist["valid_to"] = None
        df_hist["cd_status"] = "PENDING"
        batches.append(df_hist)

    if der_changed.any():
        df_der = df_int.loc[der_changed.values].copy()
        df_der["full_row_hash"] = df_der["full_hash"]
        df_der["version"] = merged.loc[der_changed, "version_ext"].astype(int).values
        df_der["is_current"] = True
        vf_series = pd.to_datetime(merged.loc[der_changed, "valid_from_ext"], errors="coerce").fillna(now)
        df_der["valid_from"] = vf_series.dt.to_pydatetime()
        df_der["valid_to"] = None
        df_der["cd_status"] = merged.loc[der_changed, "cd_status_ext"].fillna("PENDING").values
        batches.append(df_der)

    df_ins = pd.concat(batches, ignore_index=True) if batches else pd.DataFrame()
    valid_cols = [c for c in model_cols if c in df_ins.columns] if not df_ins.empty else []

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

        if not df_ins.empty:
            bulk_insert_df(SalesBiIntModel, df_ins[valid_cols], truncate_first=False, conn=conn)

    affected = len(df_ins)
    tot_vol = float(pd.to_numeric(df_int["volumen_toneladas"], errors="coerce").sum()) if "volumen_toneladas" in df_int.columns else 0.0
    tot_ing = float(pd.to_numeric(df_int["ingreso_bruto"], errors="coerce").sum()) if "ingreso_bruto" in df_int.columns else 0.0
    logger.info(
        "Upsert SCD2 completado: %d registros insertados/actualizados (reemplazo hoy=%d, expirados=%d) | vol_gd20=%.2f t | ingreso_bruto=%.2f en %.2fs",
        affected,
        len(ids_to_replace_today),
        len(ids_to_expire),
        tot_vol,
        tot_ing,
        perf_counter() - t0,
    )
    return affected
