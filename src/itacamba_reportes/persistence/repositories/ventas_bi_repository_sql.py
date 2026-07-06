"""Impl SQL repo int_ventas_bi - Fact Table histórica con SCD Type 2 by-hash.

Patrón profesional Data Warehouse:

  - int_ventas_bi es el FACT TABLE histórico acumulativo
  - Cada fila representa UNA VERSIÓN de (documento_comercial, numero_documento,
    ejercicio, material). Si SAP corrige, se cierra la versión actual
    (is_current=0, valid_to=NOW) y se inserta una nueva (version+1).
  - Detección O(1) de cambios vía source_hash y derived_hash (SHA256).
  - Sticky semántico en derivados volátiles (CD, ZE): se actualizan solo
    cuando cd_status='PENDING' (rescate de OTROS).
  - Idempotencia total: corridas idénticas no producen cambios.
  - Trazabilidad: cada fila apunta a su source_execution_id.

Flujo del MERGE (en 3 pasos atómicos):

  STEP 1: Cargar int_gd20 a tabla temp con hashes calculados (Python).
  STEP 2: Cerrar versiones cuyo source_hash cambió.
  STEP 3: INSERT nuevas versiones (docs nuevos + SAP corregido).
  STEP 4: UPDATE in-place para rescatar PENDING (CD pasa de OTROS a real).

Flag force_rebuild: ignora el sticky y recalcula todos los derivados.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from itacamba_reportes.persistence.row_hasher import (
    DERIVED_COLS,
    SOURCE_COLS,
    add_hashes_to_dataframe,
)
from itacamba_reportes.persistence.engine import SessionLocal, engine
from itacamba_reportes.persistence.models.int.gd20_model import (
    Gd20IntModel,
)
from itacamba_reportes.persistence.models.int.ventas_bi_model import (
    VentasBiIntModel,
)
from itacamba_reportes.persistence.session import get_session

logger = logging.getLogger(__name__)


# Cols que NO se tocan en updates (preservan trazabilidad histórica)
_IMMUTABLE_ON_UPDATE = {
    "id", "created_at", "version", "is_current", "valid_from",
}

# Cols sticky: solo se actualizan en rescate (PENDING → RESOLVED)
# o en force_rebuild. Nunca se tocan en REFRESH.
_STICKY_COLS = {"centro_distribucion", "zona_entrega"}


def _clean_for_sql(value: Any) -> Any:
    """Normaliza valores para pyodbc/SQL Server.

    SQL Server rechaza:
      - float('nan')        → convertir a None
      - pd.NA, pd.NaT       → convertir a None
      - numpy.nan en numerics → convertir a None
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass  # tipos no comparables con isna (ej. listas) caen acá
    return value


def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    """Aplica _clean_for_sql a todos los valores de un dict de params."""
    return {k: _clean_for_sql(v) for k, v in params.items()}


class VentasBiIntRepositoryImpl:

    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or SessionLocal

    def count(self) -> int:
        with get_session(self.session_factory) as session:
            return (
                session.query(VentasBiIntModel)
                .filter(VentasBiIntModel.is_current == True)  # noqa: E712
                .count()
            )

    # ─────────────────────────────────────────────────────────────────
    # Interfaz legacy (compat con pipeline existente).
    # Internamente llama upsert_scd2_from_int_gd20 sin execution_id.
    # ─────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────
    # MERGE SCD2 by-hash (la implementación profesional)
    # ─────────────────────────────────────────────────────────────────
    def upsert_scd2_from_int_gd20(
        self,
        execution_id: str | None = None,
        force_rebuild: bool = False,
    ) -> dict[str, int]:
        """Aplica MERGE SCD2 dirigido por hash. Devuelve métricas detalladas.

        Returns: {processed, inserted, versioned, rescued, updated, skipped}
        """
        # ── 0. Self-heal: backfill de hashes para filas vigentes sin hash ──
        # Necesario en la PRIMERA corrida después de la migración 0006:
        # las filas existentes tienen source_hash=NULL → todo aparecería como
        # "SAP corrigió" y versionariamos todo el histórico innecesariamente.
        backfilled = self._backfill_hashes_if_needed()
        if backfilled > 0:
            logger.info(
                "SCD2 self-heal: %d filas vigentes recibieron hashes "
                "(post-migracion 0006)", backfilled,
            )

        # ── 1. Leer int_gd20 a DataFrame ───────────────────────────────
        df = self._load_gd20_with_hashes()
        if df.empty:
            logger.warning("int_gd20 vacio, sin acciones")
            return {
                "processed": 0, "inserted": 0, "versioned": 0,
                "rescued": 0, "refreshed": 0, "updated": 0, "skipped": 0,
            }

        # ── 2. Leer estado actual (is_current=1) ───────────────────────
        current = self._load_current_state()
        logger.info(
            "SCD2 merge start: %d filas en int_gd20, %d filas vigentes en int_ventas_bi",
            len(df), len(current),
        )

        # ── 3. Clasificar cada fila por acción ─────────────────────────
        df = self._classify_rows(df, current, force_rebuild=force_rebuild)

        # ── 4. Ejecutar acciones agrupadas (en orden seguro) ──────────
        now = datetime.utcnow()
        metrics = {
            "processed": len(df), "inserted": 0, "versioned": 0,
            "rescued": 0, "refreshed": 0, "updated": 0, "skipped": 0,
        }
        with get_session(self.session_factory) as session:
            # STEP A: Cerrar versiones obsoletas (SAP corrigió)
            versioned_ids = df.loc[df["_action"] == "VERSION", "_existing_id"].dropna().tolist()
            if versioned_ids:
                placeholders = ", ".join(f":id{i}" for i in range(len(versioned_ids)))
                close_sql = text(f"""
                    UPDATE int_ventas_bi
                    SET is_current = 0, valid_to = :ts
                    WHERE id IN ({placeholders})
                """)
                params = {"ts": now}
                for i, vid in enumerate(versioned_ids):
                    params[f"id{i}"] = int(vid)
                session.execute(close_sql, params)
                logger.info("SCD2: %d versiones cerradas (SAP corrigió)", len(versioned_ids))

            # STEP B: INSERT nuevas versiones (INSERT y VERSION)
            to_insert = df[df["_action"].isin(["INSERT", "VERSION"])]
            if len(to_insert) > 0:
                rows_inserted, rows_versioned = self._bulk_insert_new(
                    session, to_insert, execution_id, now,
                )
                metrics["inserted"] = rows_inserted
                metrics["versioned"] = rows_versioned

            # STEP C: Rescatar PENDING (CD pasó de OTROS a real)
            to_rescue = df[df["_action"] == "RESCUE"]
            if len(to_rescue) > 0:
                rescued = self._bulk_rescue(session, to_rescue, execution_id, now)
                metrics["rescued"] = rescued

            # STEP D: REFRESH de derivados NO sticky (cd_status=RESOLVED,
            #         derived_hash cambió pero CD/ZE quedan congelados)
            to_refresh = df[df["_action"] == "REFRESH"]
            if len(to_refresh) > 0:
                refreshed = self._bulk_refresh(session, to_refresh, execution_id, now)
                metrics["refreshed"] = refreshed

            # STEP E: force_rebuild → UPDATE todos los derivados incl. sticky
            to_update = df[df["_action"] == "UPDATE_FORCE"]
            if len(to_update) > 0:
                updated = self._bulk_update_force(session, to_update, execution_id, now)
                metrics["updated"] = updated

            metrics["skipped"] = int((df["_action"] == "SKIP").sum())

        logger.info(
            "SCD2 merge done: processed=%d inserted=%d versioned=%d "
            "rescued=%d refreshed=%d updated=%d skipped=%d",
            metrics["processed"], metrics["inserted"], metrics["versioned"],
            metrics["rescued"], metrics["refreshed"], metrics["updated"],
            metrics["skipped"],
        )
        return metrics

    # ─────────────────────────────────────────────────────────────────
    # HELPERS PRIVADOS
    # ─────────────────────────────────────────────────────────────────

    def _load_gd20_with_hashes(self) -> pd.DataFrame:
        """Lee int_gd20 a DataFrame y agrega cols source_hash, derived_hash, full_row_hash."""
        if engine is None:
            raise RuntimeError("Engine SQL no inicializado")
        df = pd.read_sql_table(Gd20IntModel.__tablename__, engine)
        if df.empty:
            return df
        df = add_hashes_to_dataframe(df)
        return df

    def _backfill_hashes_if_needed(self) -> int:
        """Self-heal: calcula source_hash/derived_hash/full_row_hash para filas
        vigentes que aún no los tienen (post-migración 0006).

        Carga las filas con source_hash NULL, recalcula los 3 hashes desde su
        propio contenido, y los persiste. Idempotente — si todas las filas
        ya tienen hashes, no hace nada.

        Returns: cantidad de filas backfileadas (0 si no hubo trabajo).
        """
        if engine is None:
            raise RuntimeError("Engine SQL no inicializado")

        # Leer filas vigentes con hashes faltantes
        query = text("""
            SELECT * FROM int_ventas_bi
            WHERE is_current = 1
              AND (source_hash IS NULL OR derived_hash IS NULL OR full_row_hash IS NULL)
        """)
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        if df.empty:
            return 0

        # Recalcular hashes desde el contenido de cada fila
        df = add_hashes_to_dataframe(df)

        # Persistir vía executemany (batch único, aprovecha fast_executemany del engine)
        update_sql = text("""
            UPDATE int_ventas_bi
            SET source_hash   = :sh,
                derived_hash  = :dh,
                full_row_hash = :fh
            WHERE id = :id
        """)
        params_list = [
            _clean_params({
                "sh": row["source_hash"],
                "dh": row["derived_hash"],
                "fh": row["full_row_hash"],
                "id": int(row["id"]),
            })
            for _, row in df.iterrows()
        ]
        with get_session(self.session_factory) as session:
            if params_list:
                session.execute(update_sql, params_list)
        return len(df)

    def _load_current_state(self) -> pd.DataFrame:
        """Lee solo las filas vigentes (is_current=1) con sus claves + hashes + status."""
        if engine is None:
            raise RuntimeError("Engine SQL no inicializado")
        query = text("""
            SELECT id, ejercicio, documento_comercial, numero_documento, material,
                   version, source_hash, derived_hash, cd_status, centro_distribucion
            FROM int_ventas_bi
            WHERE is_current = 1
        """)
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        return df

    @staticmethod
    def _make_business_key(df: pd.DataFrame) -> pd.Series:
        return (
            df["ejercicio"].astype("string") + "_" +
            df["documento_comercial"].astype("string") + "_" +
            df["numero_documento"].astype("string") + "_" +
            df["material"].astype("string")
        )

    def _classify_rows(
        self, df: pd.DataFrame, current: pd.DataFrame, force_rebuild: bool,
    ) -> pd.DataFrame:
        """Agrega col `_action` y `_existing_id` a cada fila del DF.

        Acciones posibles:
          - INSERT:        doc nuevo, no existe en BI
          - VERSION:       SAP cambió (source_hash distinto) → cerrar+nueva versión
          - RESCUE:        cd_status=PENDING + nuevo_CD!=OTROS → refresca TODO incl. CD/ZE
          - REFRESH:       derived_hash cambió, pero CD ya RESOLVED → refresca derivados
                           NO sticky (nombres, equipo, gerencia), NO toca CD/ZE
          - UPDATE_FORCE:  force_rebuild=True → actualizar TODOS los derivados incl. CD/ZE
          - SKIP:          sin cambios o cd_status=LOCKED
        """
        df = df.copy()
        df["_bk"] = self._make_business_key(df)

        if current.empty:
            df["_action"] = "INSERT"
            df["_existing_id"] = None
            return df

        current = current.copy()
        current["_bk"] = self._make_business_key(current)
        cur_lookup = current.set_index("_bk")[[
            "id", "version", "source_hash", "derived_hash", "cd_status"
        ]].to_dict(orient="index")

        actions: list[str] = []
        ids: list[int | None] = []
        for _, row in df.iterrows():
            bk = row["_bk"]
            actual = cur_lookup.get(bk)
            if actual is None:
                actions.append("INSERT")
                ids.append(None)
                continue

            src_changed = actual["source_hash"] != row["source_hash"]
            drv_changed = actual["derived_hash"] != row["derived_hash"]
            cd_status = actual["cd_status"]

            if src_changed:
                actions.append("VERSION")
                ids.append(actual["id"])
            elif force_rebuild and drv_changed:
                actions.append("UPDATE_FORCE")
                ids.append(actual["id"])
            elif drv_changed and cd_status == "LOCKED":
                # Admin congeló esta fila — no la toques
                actions.append("SKIP")
                ids.append(actual["id"])
            elif (drv_changed
                  and cd_status == "PENDING"
                  and row.get("centro_distribucion") not in (None, "OTROS")):
                # CD pasa de OTROS a valor real → refresca TODO + sube cd_status
                actions.append("RESCUE")
                ids.append(actual["id"])
            elif drv_changed:
                # Otros derivados cambiaron (ej. nombre_destinatario, equipo)
                # pero CD ya estaba RESOLVED → refresca SIN tocar CD/ZE (sticky)
                actions.append("REFRESH")
                ids.append(actual["id"])
            else:
                # source_hash y derived_hash iguales → idempotente
                actions.append("SKIP")
                ids.append(actual["id"])

        df["_action"] = actions
        df["_existing_id"] = ids
        return df

    def _common_columns(self) -> list[str]:
        """Cols compartidas entre int_gd20 y int_ventas_bi (excluyendo metadatos)."""
        excluded = {"id", "created_at", "updated_at"}
        gd20_cols = {c.name for c in Gd20IntModel.__table__.columns}
        ventas_cols = {c.name for c in VentasBiIntModel.__table__.columns}
        common = (gd20_cols & ventas_cols) - excluded
        return sorted(common)

    def _compute_next_versions(
        self, session: Session, df_new: pd.DataFrame,
    ) -> dict[tuple, int]:
        """Calcula `next_version` para TODAS las business keys en UNA sola query.

        Estrategia: un único SELECT GROUP BY contra int_ventas_bi devuelve el
        MAX(version) por clave. Las claves nuevas (no existen) se default a 0,
        por lo que `next_version = MAX(version) + 1` resuelve INSERT y VERSION
        en la misma operación.

        Returns: dict {(ejercicio, doc_com, num_doc, material) -> next_version}.
        """
        if df_new.empty:
            return {}

        # Claves unicas a consultar (puede haber duplicados en df_new si SAP
        # repite filas - tomar set evita query inflada)
        keys_df = df_new[
            ["ejercicio", "documento_comercial", "numero_documento", "material"]
        ].drop_duplicates()

        # Cargar TODOS los max(version) en una sola query (sin filtrar por keys:
        # SQL Server prefiere un table-scan agrupado que miles de OR con bind params).
        # Si int_ventas_bi crece mucho, refinamos a una temp table con keys.
        sql = text("""
            SELECT ejercicio, documento_comercial, numero_documento, material,
                   MAX(version) AS max_v
            FROM int_ventas_bi
            GROUP BY ejercicio, documento_comercial, numero_documento, material
        """)
        existing: dict[tuple, int] = {}
        for r in session.execute(sql):
            existing[(int(r.ejercicio), int(r.documento_comercial),
                      int(r.numero_documento), int(r.material))] = int(r.max_v)

        # Resolver next_version por cada fila pendiente
        out: dict[tuple, int] = {}
        for _, row in keys_df.iterrows():
            key = (int(row["ejercicio"]), int(row["documento_comercial"]),
                   int(row["numero_documento"]), int(row["material"]))
            out[key] = existing.get(key, 0) + 1
        return out

    def _bulk_insert_new(
        self, session: Session, df_new: pd.DataFrame,
        execution_id: str | None, now: datetime,
    ) -> tuple[int, int]:
        """Inserta filas nuevas (acciones INSERT y VERSION) en batch (executemany)."""
        if df_new.empty:
            return 0, 0

        common = self._common_columns()

        # PASO 1: resolver next_version para todas las claves en UNA query agrupada
        next_versions = self._compute_next_versions(session, df_new)

        # PASO 2: construir la lista completa de params (1 dict por fila)
        params_list: list[dict] = []
        inserted = 0
        versioned = 0

        for _, row in df_new.iterrows():
            key = (int(row["ejercicio"]), int(row["documento_comercial"]),
                   int(row["numero_documento"]), int(row["material"]))
            next_v = next_versions[key]

            cd = row.get("centro_distribucion")
            cd_status = "PENDING" if (cd is None or cd == "OTROS") else "RESOLVED"
            cd_locked_at = now if cd_status == "RESOLVED" else None

            params = {c: row.get(c) for c in common}
            params.update({
                "version": next_v,
                "is_current": True,
                "valid_from": now,
                "valid_to": None,
                "source_hash": row["source_hash"],
                "derived_hash": row["derived_hash"],
                "full_row_hash": row["full_row_hash"],
                "cd_status": cd_status,
                "cd_locked_at": cd_locked_at,
                "source_execution_id": execution_id,
                "created_at": now,
                "updated_at": now,
            })
            params_list.append(_clean_params(params))

            if next_v == 1:
                inserted += 1
            else:
                versioned += 1
            # NOTA: si una misma key aparece N veces en df_new (duplicado),
            # next_v se queda fijo en next_versions[key] — todas las filas
            # quedan en la misma version. Es el comportamiento esperado:
            # un MERGE no debe versionar contra sí mismo.

        # PASO 3: un solo executemany — fast_executemany pyodbc lo convierte
        #         en un TVP (table-valued param) → 1 round-trip al servidor
        col_list = list(params_list[0].keys())
        cols_sql = ", ".join(col_list)
        vals_sql = ", ".join(f":{c}" for c in col_list)
        insert_sql = text(f"""
            INSERT INTO int_ventas_bi ({cols_sql})
            VALUES ({vals_sql})
        """)
        session.execute(insert_sql, params_list)

        return inserted, versioned

    def _bulk_rescue(
        self, session: Session, df_rescue: pd.DataFrame,
        execution_id: str | None, now: datetime,
    ) -> int:
        """UPDATE in-place de derivados para filas PENDING que rescatan su CD.

        Batched via executemany — 1 round-trip al servidor.
        """
        if df_rescue.empty:
            return 0

        update_sql = text("""
            UPDATE int_ventas_bi SET
                centro_distribucion = :cd,
                zona_entrega        = :ze,
                derived_hash        = :drv,
                full_row_hash       = :full,
                cd_status           = 'RESOLVED',
                cd_locked_at        = :ts,
                updated_at          = :ts,
                source_execution_id = :exec_id
            WHERE id = :id
        """)
        params_list = [
            _clean_params({
                "cd": row.get("centro_distribucion"),
                "ze": row.get("zona_entrega"),
                "drv": row["derived_hash"],
                "full": row["full_row_hash"],
                "ts": now,
                "exec_id": execution_id,
                "id": int(row["_existing_id"]),
            })
            for _, row in df_rescue.iterrows()
        ]
        session.execute(update_sql, params_list)
        return len(params_list)

    def _bulk_refresh(
        self, session: Session, df_refresh: pd.DataFrame,
        execution_id: str | None, now: datetime,
    ) -> int:
        """UPDATE de derivados NO sticky.

        Se usa cuando `derived_hash` cambió pero `cd_status='RESOLVED'`:
        otros derivados (nombre_destinatario, equipo, gerencia, etc.) cambian,
        pero CD/ZE ya están congelados y NO deben moverse (sticky).

        NO toca: source_hash, version, valid_from, is_current, cd_status,
                 ni las cols sticky (centro_distribucion, zona_entrega).
        """
        if df_refresh.empty:
            return 0

        non_sticky_derived = [c for c in DERIVED_COLS if c not in _STICKY_COLS]
        if not non_sticky_derived:
            return 0

        assigns = ", ".join(f"{c} = :{c}" for c in non_sticky_derived)
        update_sql = text(f"""
            UPDATE int_ventas_bi SET
                {assigns},
                derived_hash        = :_drv,
                full_row_hash       = :_full,
                updated_at          = :_ts,
                source_execution_id = :_exec_id
            WHERE id = :_id
        """)

        params_list: list[dict] = []
        for _, row in df_refresh.iterrows():
            params = {c: row.get(c) for c in non_sticky_derived}
            params.update({
                "_drv": row["derived_hash"],
                "_full": row["full_row_hash"],
                "_ts": now,
                "_exec_id": execution_id,
                "_id": int(row["_existing_id"]),
            })
            params_list.append(_clean_params(params))

        session.execute(update_sql, params_list)
        return len(params_list)

    def _bulk_update_force(
        self, session: Session, df_force: pd.DataFrame,
        execution_id: str | None, now: datetime,
    ) -> int:
        """UPDATE forzado de TODOS los derivados (flag --force-rebuild).

        Batched via executemany — 1 round-trip al servidor.
        """
        if df_force.empty:
            return 0

        derived_assigns = ", ".join(f"{c} = :{c}" for c in DERIVED_COLS)
        update_sql = text(f"""
            UPDATE int_ventas_bi SET
                {derived_assigns},
                derived_hash        = :_drv,
                full_row_hash       = :_full,
                updated_at          = :_ts,
                source_execution_id = :_exec_id
            WHERE id = :_id
        """)

        params_list: list[dict] = []
        for _, row in df_force.iterrows():
            params = {c: row.get(c) for c in DERIVED_COLS}
            params.update({
                "_drv": row["derived_hash"],
                "_full": row["full_row_hash"],
                "_ts": now,
                "_exec_id": execution_id,
                "_id": int(row["_existing_id"]),
            })
            params_list.append(_clean_params(params))

        session.execute(update_sql, params_list)
        return len(params_list)
