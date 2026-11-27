from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
from sqlalchemy import create_engine, text

from itacamba_reportes.core.audit.hashing import add_hashes_to_df, compute_row_hash
from itacamba_reportes.core.db.base import Base
from itacamba_reportes.core.db.bulk import bulk_insert_df
from itacamba_reportes.inputs.referencias.models import ChannelRefModel, RouteRefModel


class TestEltPipeline(unittest.TestCase):
    def test_audit_hashing(self):
        row1 = {"col_a": "123", "col_b": "ABC"}
        row2 = {"col_a": "123", "col_b": "ABC"}
        row3 = {"col_a": "123", "col_b": "XYZ"}

        h1 = compute_row_hash(row1, ("col_a", "col_b"))
        h2 = compute_row_hash(row2, ("col_a", "col_b"))
        h3 = compute_row_hash(row3, ("col_a", "col_b"))

        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertEqual(len(h1), 64)

    def test_add_hashes_to_df(self):
        df = pd.DataFrame({
            "src_1": ["A", "B"],
            "src_2": [1, 2],
            "der_1": ["X", "Y"],
        })
        df_hashed = add_hashes_to_df(df, ("src_1", "src_2"), ("der_1",))
        self.assertIn("source_hash", df_hashed.columns)
        self.assertIn("derived_hash", df_hashed.columns)
        self.assertIn("full_hash", df_hashed.columns)
        self.assertEqual(len(df_hashed), 2)

    def test_bulk_insert_with_engine(self):
        mem_engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=mem_engine)

        df = pd.DataFrame([
            {"descripcion_sap": "TEST_ALMACEN_1", "canal": "DIRECTO", "segmento": "RETAIL"},
            {"descripcion_sap": "TEST_ALMACEN_2", "canal": "DISTRIB", "segmento": "MAYORISTA"},
        ])
        rows = bulk_insert_df(ChannelRefModel, df, truncate_first=True, engine=mem_engine)
        self.assertEqual(rows, 2)

        with mem_engine.connect() as conn:
            count = conn.execute(
                text("SELECT count(*) FROM int_ref_almacen WHERE descripcion_sap LIKE 'TEST_ALMACEN_%'")
            ).scalar()
            self.assertEqual(count, 2)

    def test_route_ref_model_bulk_insert(self):
        mem_engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=mem_engine)

        df = pd.DataFrame([
            {"codigo_ruta": "4B2910", "ruta": "RUTA_1", "departamento": "SANTA CRUZ", "localidad": "YANAIGUA"},
            {"codigo_ruta": "4B2911", "ruta": "RUTA_2", "departamento": "SANTA CRUZ", "localidad": "VILLA ESPERANZA"},
        ])
        rows = bulk_insert_df(RouteRefModel, df, truncate_first=True, engine=mem_engine)
        self.assertEqual(rows, 2)

        with mem_engine.connect() as conn:
            count = conn.execute(
                text("SELECT count(*) FROM int_ref_ruta WHERE codigo_ruta LIKE '4B291%'")
            ).scalar()
            self.assertEqual(count, 2)

    def test_sql_transformation_files_exist(self):
        src_root = Path(__file__).resolve().parents[1] / "src" / "itacamba_reportes"
        expected_sql = [
            src_root / "inputs" / "cartera" / "transform.sql",
            src_root / "inputs" / "query" / "transform.sql",
            src_root / "inputs" / "gd20" / "transform.sql",
            src_root / "outputs" / "despacho_bi" / "transform.sql",
            src_root / "outputs" / "despacho_mes" / "transform.sql",
        ]
        for p in expected_sql:
            self.assertTrue(p.exists(), f"Falta archivo SQL: {p}")
            content = p.read_text(encoding="utf-8").strip()
            self.assertGreater(len(content), 50, f"El archivo SQL {p.name} está vacío")

    def test_model_field_types(self):
        from itacamba_reportes.inputs.cartera.models import CustomerIntModel, CustomerStgModel
        from itacamba_reportes.inputs.query.models import QueryIntModel
        from itacamba_reportes.inputs.referencias.models import ChannelRefModel, RouteRefModel

        self.assertEqual(ChannelRefModel.segmento.type.length, 100)
        self.assertEqual(QueryIntModel.dia.type.python_type, int)
        self.assertEqual(QueryIntModel.despacho_t.type.precision, 18)

        stg_cols = {c.name for c in CustomerStgModel.__table__.columns}
        self.assertTrue({"nombre_cliente", "vendedor", "equipo", "region_nombre"}.issubset(stg_cols))

        unique_indexes = [idx for idx in CustomerIntModel.__table__.indexes if idx.unique]
        self.assertTrue(any("cliente" in [c.name for c in idx.columns] for idx in unique_indexes))

    def test_sap_rpa_module(self):
        from dataclasses import FrozenInstanceError

        from itacamba_reportes.sap import (
            SELECTORES_SAP,
            SapConnectionError,
            SapDownloadConfig,
            SapSessionManager,
            SelectoresGD20,
            SelectoresSAP,
            selectors,
        )
        from itacamba_reportes.sap.actions import (
            execute_download_gd20,
            execute_download_query,
            execute_download_report,
            execute_login,
        )

        self.assertTrue(hasattr(selectors, "OKCODE"))
        self.assertTrue(hasattr(selectors, "GD20_LEDGER"))
        self.assertTrue(hasattr(selectors, "GD20_MENU_EXPORT_EXCEL"))

        # Verificacion de Selectores Estructurados e Inmutables (Dependency Injection)
        self.assertEqual(SELECTORES_SAP.ventana.main, "wnd[0]")
        self.assertEqual(SELECTORES_SAP.barra.okcode, "wnd[0]/tbar[0]/okcd")
        self.assertEqual(SELECTORES_SAP.login.usuario, "wnd[0]/usr/txtRSYST-BNAME")
        self.assertEqual(SELECTORES_SAP.gd20.ledger, "wnd[0]/usr/ctxtRGUD0-LEDGER")
        self.assertEqual(SELECTORES_SAP.zbcs.okcode, "zbcs")

        # Inmutabilidad estricta (frozen=True)
        with self.assertRaises(FrozenInstanceError):
            SELECTORES_SAP.gd20.ledger = "MODIFICADO"

        # Inyeccion de dependencias con selectores customizados
        custom_selectors = SelectoresSAP(gd20=SelectoresGD20(ledger="CUSTOM_LEDGER_LOCATOR"))
        self.assertEqual(custom_selectors.gd20.ledger, "CUSTOM_LEDGER_LOCATOR")
        self.assertEqual(custom_selectors.barra.okcode, "wnd[0]/tbar[0]/okcd")

        mgr = SapSessionManager(connection_index=0, session_index=0)
        self.assertEqual(mgr.connection_index, 0)
        self.assertEqual(mgr.session_index, 0)

        cfg_dynamic = SapDownloadConfig(
            transaction="gd20",
            ledger="VC",
            variant="Variante_Cierre",
            period_low=10,
            period_high=10,
            export_filename="GD20_OCTUBRE",
        )
        self.assertEqual(cfg_dynamic.transaction, "gd20")
        self.assertEqual(cfg_dynamic.period_low, 10)
        self.assertEqual(cfg_dynamic.export_filename, "GD20_OCTUBRE")

        cfg_gd20 = SapDownloadConfig.for_gd20(transaction="gd20", period=9)
        self.assertEqual(cfg_gd20.period_low, 9)
        self.assertEqual(cfg_gd20.period_high, 9)
        self.assertEqual(cfg_gd20.ledger, "VC")

        cfg_query = SapDownloadConfig.for_query(transaction="zbcs", date_from="01.10.2026", date_to="15.10.2026")
        self.assertEqual(cfg_query.transaction, "zbcs")
        self.assertEqual(cfg_query.date_from, "01.10.2026")

    def test_defensive_reader_validation(self):
        import tempfile
        from itacamba_reportes.core.io.reader import (
            ExcelSourceSpec,
            FastExcelReader,
            MissingColumnsError,
            SheetNotFoundError,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_file = tmp_path / "TEST_DATA.xlsx"
            df = pd.DataFrame({"col_a": [1, 2], "col_b": ["x", "y"]})
            with pd.ExcelWriter(test_file) as writer:
                df.to_excel(writer, sheet_name="HOJA_REAL", index=False)

            # Caso 1: Hoja inexistente lanza SheetNotFoundError de inmediato
            spec_bad_sheet = ExcelSourceSpec(
                name="test",
                file_pattern="TEST_DATA.xlsx",
                sheet="HOJA_INEXISTENTE",
            )
            reader_bad_sheet = FastExcelReader(spec_bad_sheet, tmp_path)
            with self.assertRaises(SheetNotFoundError):
                reader_bad_sheet.read_raw()

            # Caso 2: Columna requerida faltante lanza MissingColumnsError de inmediato
            spec_missing_col = ExcelSourceSpec(
                name="test",
                file_pattern="TEST_DATA.xlsx",
                sheet="HOJA_REAL",
                required_columns=("col_a", "col_c_obligatoria"),
            )
            reader_missing_col = FastExcelReader(spec_missing_col, tmp_path)
            with self.assertRaises(MissingColumnsError):
                reader_missing_col.read_raw()

            # Caso 3: Lectura exitosa con validacion aprobada
            spec_ok = ExcelSourceSpec(
                name="test",
                file_pattern="TEST_DATA.xlsx",
                sheet="HOJA_REAL",
                required_columns=("col_a", "col_b"),
            )
            reader_ok = FastExcelReader(spec_ok, tmp_path)
            df_read = reader_ok.read_raw()
            self.assertEqual(len(df_read), 2)
            self.assertIn("col_a", df_read.columns)

    def test_clean_exporter_excludes_technical_columns(self):
        import tempfile
        import openpyxl
        from itacamba_reportes.core.io.exporter import ExcelReportExporter

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            exporter = ExcelReportExporter(tmp_path)

            df_with_tech = pd.DataFrame({
                "cliente": [101, 102],
                "volumen": [15.5, 20.0],
                "id": [1, 2],
                "created_at": ["2026-10-22", "2026-10-22"],
                "version": [1, 2],
                "is_current": [True, True],
                "source_hash": ["hash1", "hash2"],
            })

            target = exporter.export(df_with_tech, "REPORTE_TEST")
            wb = openpyxl.load_workbook(target)

            # Verificacion 1: No existe la hoja de CONTROL por defecto
            self.assertNotIn("CONTROL", wb.sheetnames)
            self.assertIn("Data", wb.sheetnames)

            # Verificacion 2: No se exportan columnas tecnicas
            sheet = wb["Data"]
            headers = [cell.value for cell in sheet[1]]
            self.assertIn("cliente", headers)
            self.assertIn("volumen", headers)
            self.assertNotIn("id", headers)
            self.assertNotIn("created_at", headers)
            self.assertNotIn("version", headers)
            self.assertNotIn("is_current", headers)
            self.assertNotIn("source_hash", headers)

    def test_exporter_multi_sheet_historial_ventas(self):
        import tempfile
        import openpyxl
        from itacamba_reportes.core.io.exporter import ExcelReportExporter

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            exporter = ExcelReportExporter(tmp_path)

            df_ventas = pd.DataFrame({
                "Nº documento": [1001, 1002],
                "Cantidad": [10.5, 20.0],
                "id": [1, 2],
                "is_current": [True, True],
            })
            df_despachos = pd.DataFrame({
                "Documento venta": [5001, 5002],
                "x": [15, 16],
                "created_at": ["2026-10-26", "2026-10-26"],
            })

            target = exporter.export_multi_sheet(
                sheets={
                    "VENTAS": df_ventas,
                    "DESPACHOS": df_despachos,
                },
                file_name="HISTORIAL VENTAS.xlsx",
                timestamped=False,
            )

            self.assertEqual(target.name, "HISTORIAL VENTAS.xlsx")
            wb = openpyxl.load_workbook(target)
            self.assertEqual(wb.sheetnames, ["VENTAS", "DESPACHOS"])

            ws_v = wb["VENTAS"]
            headers_v = [cell.value for cell in ws_v[1]]
            self.assertIn("Nº documento", headers_v)
            self.assertNotIn("id", headers_v)
            self.assertNotIn("is_current", headers_v)
            self.assertEqual(ws_v.cell(2, headers_v.index("Nº documento") + 1).value, 1001)
            self.assertEqual(ws_v.cell(2, headers_v.index("Cantidad") + 1).value, 10.5)

            ws_d = wb["DESPACHOS"]
            headers_d = [cell.value for cell in ws_d[1]]
            self.assertIn("Documento venta", headers_d)
            self.assertIn("x", headers_d)
            self.assertNotIn("created_at", headers_d)
            self.assertEqual(ws_d.cell(2, headers_d.index("Documento venta") + 1).value, 5001)
            self.assertEqual(ws_d.cell(2, headers_d.index("x") + 1).value, 15)
            wb.close()

    def test_exporter_single_sheet_values_not_blank(self):
        import tempfile
        import openpyxl
        from itacamba_reportes.core.io.exporter import ExcelReportExporter

        with tempfile.TemporaryDirectory() as tmp:
            exporter = ExcelReportExporter(Path(tmp))
            df = pd.DataFrame({
                "Nº documento": [1001, 1002],
                "Cantidad": [10.5, 20.0],
                "id": [1, 2],
            })
            target = exporter.export(df, "TEST_SINGLE")
            wb = openpyxl.load_workbook(target)
            ws = wb["Data"]
            headers = [cell.value for cell in ws[1]]
            self.assertEqual(ws.cell(2, headers.index("Nº documento") + 1).value, 1001)
            self.assertEqual(ws.cell(2, headers.index("Cantidad") + 1).value, 10.5)
            wb.close()

    def test_export_historial_ventas_in_memory_reuse(self):
        import tempfile
        import openpyxl
        from itacamba_reportes.outputs.historial_ventas.export import export_historial_ventas

        with tempfile.TemporaryDirectory() as tmp:
            df_v = pd.DataFrame({"Nº documento": [999], "Cantidad": [50.0]})
            df_d = pd.DataFrame({"Documento venta": [888], "x": [25]})
            target = export_historial_ventas(
                df_ventas=df_v,
                df_despachos=df_d,
                target_dir=Path(tmp),
            )
            wb = openpyxl.load_workbook(target)
            self.assertEqual(wb.sheetnames, ["VENTAS", "DESPACHOS"])
            self.assertEqual(wb["VENTAS"].cell(2, 1).value, 999)
            self.assertEqual(wb["DESPACHOS"].cell(2, 1).value, 888)
            wb.close()

    def test_state_file_signature_and_change_detection(self):
        import tempfile
        from itacamba_reportes.core import state

        with tempfile.TemporaryDirectory() as tmp:
            tmp_state_file = Path(tmp) / "test_pipeline_state.json"
            orig_state_path = state.STATE_PATH
            state.STATE_PATH = tmp_state_file
            try:
                test_file = Path(tmp) / "test_cartera.xlsx"
                test_file.write_bytes(b"CONTENIDO INICIAL CARTERA 123")

                self.assertTrue(state.has_file_changed("cartera", test_file))
                state.save_file_signature("cartera", test_file)
                self.assertFalse(state.has_file_changed("cartera", test_file))

                test_file.write_bytes(b"CONTENIDO MODIFICADO NUEVA CARTERA 456789")
                self.assertTrue(state.has_file_changed("cartera", test_file))
                state.save_file_signature("cartera", test_file)
                self.assertFalse(state.has_file_changed("cartera", test_file))
            finally:
                state.STATE_PATH = orig_state_path

    def test_alembic_single_baseline_schema(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from itacamba_reportes.core.settings import EnvConfig
        import subprocess

        alembic_versions_dir = EnvConfig.PROJECT_ROOT / "alembic" / "versions"
        py_files = [f for f in alembic_versions_dir.glob("*.py") if not f.name.startswith("__")]
        # Debe existir exactamente 1 archivo de migracion baseline inicial
        self.assertEqual(len(py_files), 1, f"Se esperaba exactamente 1 version de Alembic, encontradas: {py_files}")

        cfg = Config(str(EnvConfig.PROJECT_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(EnvConfig.PROJECT_ROOT / "alembic"))
        script_dir = ScriptDirectory.from_config(cfg)
        heads = script_dir.get_heads()
        self.assertEqual(len(heads), 1)
        self.assertEqual(heads[0], "0001_baseline")

        # Verificar que la generacion offline de SQL para upgrade head funciona sin errores
        res = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
            cwd=str(EnvConfig.PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"alembic upgrade head --sql fallo: {res.stderr}")
        self.assertIn("CREATE TABLE int_cartera", res.stdout)
        self.assertIn("CREATE TABLE int_ref_ruta", res.stdout)
        self.assertIn("CREATE TABLE int_ventas_bi", res.stdout)
        self.assertIn("CREATE TABLE pipeline_executions", res.stdout)
        self.assertIn("0001_baseline", res.stdout)

    def test_column_mappings_export(self):
        from itacamba_reportes.core.io.column_mappings import (
            VENTAS_BI_MAPPING,
            DESPACHO_MES_MAPPING,
            DESPACHO_BI_MAPPING,
            map_export_columns,
        )
        self.assertEqual(len(VENTAS_BI_MAPPING), 77)
        self.assertEqual(len(DESPACHO_MES_MAPPING), 20)
        self.assertEqual(len(DESPACHO_BI_MAPPING), 79)
        self.assertIn("Fecha", DESPACHO_MES_MAPPING.values())
        self.assertIn("Mes", DESPACHO_MES_MAPPING.values())
        self.assertIn("x", DESPACHO_BI_MAPPING.values())
        self.assertEqual(DESPACHO_BI_MAPPING["dia"], "x")
        self.assertEqual(list(DESPACHO_BI_MAPPING.values())[0], "Centro Proveedor")
        self.assertEqual(list(DESPACHO_BI_MAPPING.values())[55], "x")
        self.assertEqual(list(DESPACHO_BI_MAPPING.values())[56], "XX")
        self.assertEqual(list(DESPACHO_BI_MAPPING.values())[68], "Columna12")
        self.assertEqual(list(DESPACHO_BI_MAPPING.values())[69], "Cod. Pagador mcía.")
        self.assertEqual(list(DESPACHO_BI_MAPPING.values())[-1], "RT")

        df_dummy = pd.DataFrame({
            "gerencia": ["SCZ"],
            "equipo": ["EQ1"],
            "fecha": ["2026-10-01"],
            "mes": [10],
            "dia": [1],
        })
        mapped = map_export_columns(df_dummy, DESPACHO_MES_MAPPING)
        self.assertEqual(list(mapped.columns), ["GERENCIA", "EQUIPO", "Fecha", "Mes", "Día"])

        df_bi_dummy = pd.DataFrame({
            "centro_origen": ["4B05"],
            "dia": [20],
        })
        mapped_bi = map_export_columns(df_bi_dummy, DESPACHO_BI_MAPPING)
        self.assertEqual(list(mapped_bi.columns), ["Centro Proveedor", "x"])
        self.assertEqual(mapped_bi["x"].iloc[0], 20)

        # Validar que un DataFrame completo produce exactamente las 79 columnas oficiales en orden
        full_dummy = pd.DataFrame({k: [None] for k in DESPACHO_BI_MAPPING.keys()})
        mapped_full = map_export_columns(full_dummy, DESPACHO_BI_MAPPING)
        self.assertEqual(len(mapped_full.columns), 79)
        self.assertEqual(list(mapped_full.columns), list(DESPACHO_BI_MAPPING.values()))

    def test_migration_matches_all_models_exactly(self):
        import importlib.util
        from itacamba_reportes.core.db.base import Base
        import itacamba_reportes.core.db.schema

        spec = importlib.util.spec_from_file_location("baseline", "alembic/versions/0001_baseline_esquema_inicial_elt.py")
        baseline = importlib.util.module_from_spec(spec)

        created_tables = {}
        class MockOp:
            @staticmethod
            def create_table(name, *columns, **kwargs):
                created_tables[name] = [c.name for c in columns if getattr(c, "name", None)]
            @staticmethod
            def create_index(*args, **kwargs): pass
            @staticmethod
            def drop_table(*args, **kwargs): pass
            @staticmethod
            def drop_index(*args, **kwargs): pass
            @staticmethod
            def f(x): return x

        spec.loader.exec_module(baseline)
        baseline.op = MockOp()
        baseline.upgrade()

        self.assertEqual(len(created_tables), 18)
        self.assertEqual(len(Base.metadata.tables), 18)
        for tname, mtable in Base.metadata.tables.items():
            self.assertIn(tname, created_tables)
            m_cols = set(c.name for c in mtable.columns)
            mig_cols = set(created_tables[tname])
            self.assertEqual(m_cols, mig_cols, f"Discrepancia de columnas en tabla {tname}: {m_cols ^ mig_cols}")

    def test_ensure_all_tables_exist_creates_missing_table(self):
        from itacamba_reportes.core.db.base import Base
        from itacamba_reportes.core.db.schema import ensure_all_tables_exist
        import itacamba_reportes.core.db.connection as conn_mod
        from sqlalchemy import create_engine, inspect

        mem_eng = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(mem_eng, tables=[t for n, t in Base.metadata.tables.items() if n != "int_despacho_bi"])
        insp = inspect(mem_eng)
        self.assertFalse(insp.has_table("int_despacho_bi"))

        orig_engine = conn_mod._engine
        conn_mod.set_engine(mem_eng)
        try:
            ensure_all_tables_exist()
            insp2 = inspect(mem_eng)
            self.assertTrue(insp2.has_table("int_despacho_bi"))
            self.assertEqual(len(insp2.get_columns("int_despacho_bi")), 71)
        finally:
            conn_mod.set_engine(orig_engine)

    def test_despacho_bi_dataframe_exports_79_columns(self):
        from sqlalchemy import create_engine, text
        from sqlalchemy.pool import StaticPool
        import itacamba_reportes.core.db.connection as conn_mod
        from itacamba_reportes.core.db.base import Base
        from itacamba_reportes.core.io.column_mappings import DESPACHO_BI_MAPPING
        import itacamba_reportes.outputs.despacho_bi.export as export_mod

        mem_eng = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(mem_eng)
        orig_engine = conn_mod._engine
        orig_export_engine = export_mod.engine
        conn_mod.set_engine(mem_eng)
        export_mod.engine = mem_eng

        try:
            with mem_eng.begin() as conn:
                conn.execute(text("""
                    INSERT INTO int_despacho_bi (
                        centro_origen, nro_pedido, cod_ruta, dia,
                        cod_pagador, pagador, precio_pedido, unidad_entrega,
                        fecha_facturacion, nro_factura, tipo_pos_pedido,
                        documento_referencia, codigo_ferretero, rt
                    ) VALUES (
                        '4B05', 2053424533, '4B0501', 15,
                        5123456, 'PAGADOR TEST', 120.5, 'T',
                        '2026-10-15 00:00:00', 987654, 'TAN',
                        'REF-01', 'FERR-99', '4B0501'
                    )
                """))

            df = export_mod.get_despacho_bi_dataframe()
            self.assertEqual(len(df), 1)
            self.assertEqual(len(df.columns), 79)
            self.assertEqual(list(df.columns), list(DESPACHO_BI_MAPPING.values()))
            self.assertIsNone(df["XX"].iloc[0])
            self.assertIsNone(df["Columna12"].iloc[0])
            self.assertEqual(df["Cod. Pagador mcía."].iloc[0], 5123456)
            self.assertEqual(df["Pagador mcía."].iloc[0], "PAGADOR TEST")
            self.assertEqual(float(df["Precio pedido"].iloc[0]), 120.5)
            self.assertEqual(df["Unid. Venta"].iloc[0], "T")
            self.assertEqual(df["Nro de factura"].iloc[0], 987654)
            self.assertEqual(df["Tipo pos. ped."].iloc[0], "TAN")
            self.assertEqual(df["Documento Referencia"].iloc[0], "REF-01")
            self.assertEqual(df["Código Ferretero"].iloc[0], "FERR-99")
            self.assertEqual(df["RT"].iloc[0], "4B0501")
        finally:
            conn_mod.set_engine(orig_engine)
            export_mod.engine = orig_export_engine

    def test_sync_table_columns_adds_new_columns(self):
        from sqlalchemy import create_engine, inspect, text
        import itacamba_reportes.core.db.connection as conn_mod
        from itacamba_reportes.core.db.schema import sync_table_columns

        mem_eng = create_engine("sqlite:///:memory:")
        with mem_eng.begin() as conn:
            conn.execute(text("CREATE TABLE int_query (id INTEGER PRIMARY KEY, dia INTEGER)"))
            conn.execute(text("CREATE TABLE int_despacho_bi (id INTEGER PRIMARY KEY, dia INTEGER)"))

        orig_engine = conn_mod._engine
        conn_mod.set_engine(mem_eng)
        try:
            sync_table_columns()
            insp = inspect(mem_eng)
            q_cols = {c["name"] for c in insp.get_columns("int_query")}
            d_cols = {c["name"] for c in insp.get_columns("int_despacho_bi")}
            expected_new = {
                "precio_pedido", "unidad_entrega", "fecha_facturacion",
                "nro_factura", "tipo_pos_pedido", "documento_referencia",
                "codigo_ferretero",
            }
            self.assertTrue(expected_new.issubset(q_cols))
            self.assertTrue((expected_new | {"rt"}).issubset(d_cols))
        finally:
            conn_mod.set_engine(orig_engine)

    def test_clean_and_truncate_all_tables(self):
        from sqlalchemy import create_engine, inspect, text
        from sqlalchemy.pool import StaticPool
        import itacamba_reportes.core.db.connection as conn_mod
        from itacamba_reportes.core.db.base import Base
        from itacamba_reportes.core.db.schema import drop_all_tables, truncate_all_tables
        from itacamba_reportes.cli import main

        mem_eng = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(mem_eng)
        orig_engine = conn_mod._engine
        conn_mod.set_engine(mem_eng)

        try:
            # 1. Insertar un registro en una tabla
            with mem_eng.begin() as conn:
                conn.execute(text("INSERT INTO int_ref_centro (centro, nombre) VALUES ('C1', 'TEST')"))
            
            with mem_eng.connect() as conn:
                count = conn.execute(text("SELECT COUNT(*) FROM int_ref_centro")).scalar()
                self.assertEqual(count, 1)

            # 2. Ejecutar truncate_all_tables
            cleared = truncate_all_tables(reset_state=True)
            self.assertIn("int_ref_centro", cleared)
            with mem_eng.connect() as conn:
                count_after = conn.execute(text("SELECT COUNT(*) FROM int_ref_centro")).scalar()
                self.assertEqual(count_after, 0)

            # 3. Probar CLI clean-db --force
            res = main(["clean-db", "--force"])
            self.assertEqual(res, 0)

            # 4. Probar drop_all_tables
            dropped = drop_all_tables(reset_state=True)
            self.assertIn("int_ref_centro", dropped)
            insp = inspect(mem_eng)
            self.assertFalse(insp.has_table("int_ref_centro"))
        finally:
            conn_mod.set_engine(orig_engine)

    def test_zero_docstrings_in_src(self):
        import ast
        import glob
        src_path = Path(__file__).resolve().parents[1] / "src"
        docstring_findings = []
        for py_file in src_path.rglob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                    ds = ast.get_docstring(node)
                    if ds:
                        docstring_findings.append(f"{py_file.name}:{node.name if hasattr(node, 'name') else 'module'}")
        self.assertEqual(docstring_findings, [])

    def test_cli_default_to_run_all(self):
        from unittest.mock import patch
        from itacamba_reportes.cli import main

        with patch("itacamba_reportes.cli.run_all", return_value=0) as mock_run_all, \
             patch("itacamba_reportes.cli.ensure_schema_current"):
            result = main([])
            self.assertEqual(result, 0)
            mock_run_all.assert_called_once_with(force_cartera=False, is_fin_de_mes=False, corte_fecha=None)

    def test_ventas_bi_scd2_update_with_expire(self):
        from datetime import datetime, timedelta
        from sqlalchemy import create_engine, text
        import itacamba_reportes.core.db.connection as conn_mod
        from itacamba_reportes.core.db.base import Base
        from itacamba_reportes.outputs.ventas_bi.transform import upsert_ventas_bi_scd2

        mem_eng = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(mem_eng)
        orig_engine = conn_mod._engine
        conn_mod.set_engine(mem_eng)

        try:
            # 1. Poblar int_gd20 con 1 registro
            with mem_eng.begin() as conn:
                conn.execute(text("""
                    INSERT INTO int_gd20 (
                        ejercicio, documento_comercial, numero_documento, material,
                        sociedad, organizacion_ventas, centro, cantidad
                    ) VALUES (
                        2026, 'DOC1', 'NUM1', 'MAT1',
                        'SOC1', 'ORG1', 'C1', 10.0
                    )
                """))

            # 2. Carga inicial SCD2
            inserted = upsert_ventas_bi_scd2()
            self.assertEqual(inserted, 1)

            # 3. Simular que el registro se creo ayer para forzar expiracion
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            with mem_eng.begin() as conn:
                conn.execute(text(f"UPDATE int_ventas_bi SET valid_from = '{yesterday}'"))

            # 4. Modificar dato en int_gd20 (cambio de cantidad)
            with mem_eng.begin() as conn:
                conn.execute(text("UPDATE int_gd20 SET cantidad = 20.0 WHERE documento_comercial = 'DOC1'"))

            # 5. Segunda corrida: debe expirar registro anterior y crear version 2
            updated = upsert_ventas_bi_scd2()
            self.assertEqual(updated, 1)

            # 6. Validar estado en BD
            with mem_eng.connect() as conn:
                rows = conn.execute(text("SELECT id, version, is_current, valid_to FROM int_ventas_bi ORDER BY version")).fetchall()
                self.assertEqual(len(rows), 2)
                # Registro anterior expirado
                self.assertEqual(rows[0][1], 1)
                self.assertEqual(rows[0][2], 0)
                self.assertIsNotNone(rows[0][3])
                # Registro nuevo activo
                self.assertEqual(rows[1][1], 2)
                self.assertEqual(rows[1][2], 1)
                self.assertIsNone(rows[1][3])
        finally:
            conn_mod.set_engine(orig_engine)

    def test_cli_argument_normalization(self):
        from unittest.mock import patch
        from itacamba_reportes.cli import main

        with patch("itacamba_reportes.cli.run_all", return_value=0) as mock_run_all, \
             patch("itacamba_reportes.cli.ensure_schema_current"):
            # Probar 'run all' con espacio
            res = main(["run", "all"])
            self.assertEqual(res, 0)
            mock_run_all.assert_called_once()

            # Probar 'run_all' con guion bajo
            mock_run_all.reset_mock()
            res2 = main(["run_all"])
            self.assertEqual(res2, 0)
            mock_run_all.assert_called_once()

            # Probar sin argumentos (default)
            mock_run_all.reset_mock()
            res3 = main([])
            self.assertEqual(res3, 0)
            mock_run_all.assert_called_once()

    def test_sap_query_3_months_and_flow(self):
        from itacamba_reportes.sap.config import CONFIG_QUERY, CONFIG_GD20
        from itacamba_reportes.sap.session import SapSessionManager
        from itacamba_reportes.sap.actions import execute_download_all_sap

        cfg_q = CONFIG_QUERY.to_download_config(date_to_override="08.11.2026")
        self.assertEqual(cfg_q.transaction, "ZVCSD381")
        self.assertEqual(cfg_q.sociedad, "4253")
        self.assertEqual(cfg_q.variant, "/IM")
        self.assertEqual(cfg_q.date_to, "08.11.2026")
        self.assertEqual(cfg_q.date_from, "08.08.2026")

        cfg_gd20 = CONFIG_GD20.to_download_config()
        self.assertEqual(cfg_gd20.layout_name, "//AVRILGD20")
        self.assertEqual(cfg_gd20.variant, "BOT_GD20")
        self.assertEqual(cfg_gd20.ledger, "VC")

        self.assertTrue(hasattr(SapSessionManager, "return_to_main_menu"))
        self.assertTrue(callable(execute_download_all_sap))

    def test_vectorized_hashing_matches_row_hash_exactly(self):
        df = pd.DataFrame({
            "src_str": [" ABC ", None, "XYZ"],
            "src_flt": [12.34567, float("nan"), 0.0],
            "der_int": [10, 20, None],
        })
        df_vec = add_hashes_to_df(df.copy(), ("src_str", "src_flt"), ("der_int",))
        for i, row in df.iterrows():
            self.assertEqual(df_vec["source_hash"].iloc[i], compute_row_hash(row, ("src_str", "src_flt")))
            self.assertEqual(df_vec["derived_hash"].iloc[i], compute_row_hash(row, ("der_int",)))
            self.assertEqual(df_vec["full_hash"].iloc[i], compute_row_hash(row, ("src_str", "src_flt", "der_int")))

        empty_df = pd.DataFrame({"src_str": pd.Series([], dtype="object"), "der_int": pd.Series([], dtype="int64")})
        empty_hashed = add_hashes_to_df(empty_df, ("src_str",), ("der_int",))
        self.assertEqual(len(empty_hashed), 0)

    def test_export_all_reports_parallel_reuses_in_memory_dfs(self):
        from unittest.mock import patch
        from itacamba_reportes.cli import export_all_reports_parallel

        df_v = pd.DataFrame({"Nº documento": [1]})
        df_d = pd.DataFrame({"Documento venta": [2]})

        with patch("itacamba_reportes.outputs.ventas_bi.export.export_ventas_bi", return_value=(Path("V.xlsx"), df_v)) as mock_v, \
             patch("itacamba_reportes.outputs.despacho_bi.export.export_despacho_bi", return_value=(Path("D.xlsx"), df_d)) as mock_d, \
             patch("itacamba_reportes.outputs.despacho_mes.export.export_despacho_mes", return_value=Path("M.xlsx")) as mock_m, \
             patch("itacamba_reportes.outputs.historial_ventas.export.export_historial_ventas", return_value=Path("H.xlsx")) as mock_h:
            export_all_reports_parallel()

            mock_v.assert_called_once_with(return_df=True)
            mock_d.assert_called_once_with(return_df=True)
            mock_m.assert_called_once_with()
            mock_h.assert_called_once_with(df_ventas=df_v, df_despachos=df_d)

    def test_bridge_steps_include_proyeccion_despacho_bi_and_mes(self):
        from unittest.mock import patch
        from itacamba_reportes.ui.bridge import BotBridge

        bridge = BotBridge()
        with patch("itacamba_reportes.inputs.referencias.pipeline.run_pipeline") as mock_ref, \
             patch("itacamba_reportes.inputs.proyeccion.pipeline.run_pipeline") as mock_proy:
            bridge._step_referencias()
            mock_ref.assert_called_once_with()
            mock_proy.assert_called_once_with()

        with patch("itacamba_reportes.inputs.query.pipeline.run_pipeline") as mock_q, \
             patch("itacamba_reportes.outputs.despacho_bi.pipeline.run_pipeline") as mock_dbi, \
             patch("itacamba_reportes.outputs.despacho_mes.pipeline.run_pipeline") as mock_dmes:
            bridge._step_query(is_fin_de_mes=True, corte_fecha="2026-10-31", incluir_hasta=True)
            mock_q.assert_called_once_with(corte_fecha="2026-10-31", is_fin_de_mes=True, incluir_hasta=True)
            mock_dbi.assert_called_once_with(do_export=False)
            mock_dmes.assert_called_once_with(
                corte_fecha="2026-10-31",
                is_fin_de_mes=True,
                incluir_hasta=True,
                do_export=False,
            )

    def test_resolve_dia_corte_and_download_query_non_mutating(self):
        from unittest.mock import patch
        from itacamba_reportes.outputs.despacho_mes.transform import resolve_dia_corte
        from itacamba_reportes.sap.config import CONFIG_QUERY
        from itacamba_reportes.sap.actions.download_query_action import execute_download_query
        from itacamba_reportes.sap.session import SapSessionManager

        self.assertEqual(resolve_dia_corte(dia_corte=15), 15)
        self.assertEqual(resolve_dia_corte(corte_fecha="2026-10-31", incluir_hasta=False, is_fin_de_mes=False), 31)
        self.assertEqual(resolve_dia_corte(corte_fecha="2026-10-31", incluir_hasta=True, is_fin_de_mes=True), 32)
        self.assertEqual(resolve_dia_corte(is_fin_de_mes=True), 32)

        orig_variant = CONFIG_QUERY.variant
        orig_soc = CONFIG_QUERY.sociedad
        with patch("itacamba_reportes.sap.actions.download_query_action.execute_download_report", return_value=Path("Q.xlsx")):
            execute_download_query(SapSessionManager(), variant="/CUSTOM", sociedad="9999")
        self.assertEqual(CONFIG_QUERY.variant, orig_variant)
        self.assertEqual(CONFIG_QUERY.sociedad, orig_soc)

    def test_env_config_reload_updates_paths_and_settings(self):
        import os
        import tempfile
        from itacamba_reportes.core.settings import EnvConfig

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            exp_dir = Path(tmp) / "exports"
            exp_dir.mkdir()
            env_path.write_text(f"EXPORT_PATH={exp_dir}\nSAP_SISTEMA=QAS\n", encoding="utf-8")
            env_clean = {
                k: v for k, v in os.environ.items()
                if k not in (
                    "PATH_INSUMOS_FIJOS",
                    "PATH_INSUMOS_DINAMICOS",
                    "PATH_REPORTES_SALIDA",
                    "EXPORT_PATH",
                    "DATA_PATH",
                    "SAP_SISTEMA",
                )
            }
            try:
                with patch.dict(os.environ, env_clean, clear=True):
                    EnvConfig.reload(env_path)
                    self.assertEqual(EnvConfig.EXPORT_PATH, exp_dir)
                    self.assertEqual(EnvConfig.REPORTS_OUTPUT_PATH, exp_dir)
                    self.assertEqual(EnvConfig.SAP_SISTEMA, "QAS")
            finally:
                EnvConfig.reload()

    def test_transform_query_sql_placeholders(self):
        from unittest.mock import MagicMock, patch
        import itacamba_reportes.inputs.query.transform as qry_mod

        executed_sql: list[str] = []
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = lambda stmt, *a, **kw: executed_sql.append(str(stmt)) or MagicMock(scalar=lambda: 5)
        mock_eng = MagicMock()
        mock_eng.begin.return_value.__enter__.return_value = mock_conn
        mock_eng.connect.return_value.__enter__.return_value = mock_conn

        with patch.object(qry_mod, "engine", mock_eng), \
             patch("itacamba_reportes.core.db.schema.sync_table_columns"):
            qry_mod.transform_query(target_month=(2026, 10), corte_fecha="2026-10-31", incluir_hasta=True)

        full_sql = "\n".join(executed_sql)
        self.assertIn("f_calc.fecha_efectiva < '2026-11-01'", full_sql)
        self.assertIn("YEAR(f_calc.fecha_efectiva) = 2026 AND MONTH(f_calc.fecha_efectiva) = 10", full_sql)
        self.assertNotIn("/* OUTER_CUTOFF_FILTER */", full_sql)
        self.assertNotIn("/* MONTH_SELECTOR */", full_sql)

    def test_cartera_sap_guard_and_ui_tasks(self):
        from itacamba_reportes.sap.config import CONFIG_CARTERA
        from itacamba_reportes.sap.exceptions import SapAutomationError
        from itacamba_reportes.ui.bridge import BotBridge, SAP_TASKS_PATH

        with self.assertRaises(SapAutomationError) as ctx:
            CONFIG_CARTERA.to_download_config()
        self.assertIn("CARTERA", str(ctx.exception))

        bridge = BotBridge()
        with patch.object(bridge, "test_sap_logon", side_effect=AssertionError("SAP GUI no debe abrirse para cartera")):
            res = bridge.download_sap("cartera")
        self.assertEqual(res.get("status"), "error")
        self.assertIn("CARTERA.xlsx", res.get("message", ""))

        default_ids = {item["id"] for item in bridge._default_sap_tasks()}
        self.assertEqual(default_ids, {"gd20", "zbcs", "all"})
        stored_tasks = json.loads(SAP_TASKS_PATH.read_text(encoding="utf-8"))
        self.assertEqual({item["id"] for item in stored_tasks}, {"gd20", "zbcs", "all"})

    def test_bridge_resolve_sap_period_from_config(self):
        from itacamba_reportes.sap.config import CONFIG_QUERY
        from itacamba_reportes.ui.bridge import BotBridge

        bridge = BotBridge()
        profiles = [
            {
                "id": "diaria",
                "activa": True,
                "mesEjecucion": "2026-11",
                "fechaDesde": "2026-11-01",
                "fechaHasta": "2026-11-25",
            },
            {
                "id": "cierre",
                "activa": False,
                "mesEjecucion": "2026-10",
                "fechaDesde": "2026-10-01",
                "fechaHasta": "2026-10-31",
            },
            {
                "id": "solo_mes",
                "activa": False,
                "mesEjecucion": "2026-09",
                "fechaDesde": "",
                "fechaHasta": "",
            },
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            prof_file = Path(tmp_dir) / "execution_profiles.json"
            prof_file.write_text(json.dumps(profiles), encoding="utf-8")
            with patch("itacamba_reportes.ui.bridge.PROFILES_PATH", prof_file):
                self.assertEqual(
                    bridge._resolve_sap_period_from_config(),
                    ("11", "11", "25.11.2026"),
                )
                self.assertEqual(
                    bridge._resolve_sap_period_from_config(profile_id="cierre:2026-11-01"),
                    ("10", "10", "31.10.2026"),
                )
                self.assertEqual(
                    bridge._resolve_sap_period_from_config(
                        fecha_desde="2026-10-01",
                        corte_fecha="2026-11-15",
                    ),
                    ("10", "11", "15.11.2026"),
                )
                self.assertEqual(
                    bridge._resolve_sap_period_from_config(
                        corte_fecha="2026-09-30",
                        profile_id="solo_mes",
                    ),
                    ("9", "9", "30.09.2026"),
                )

        q_cfg = CONFIG_QUERY.to_download_config(date_to_override="2026-11-25")
        self.assertEqual(q_cfg.date_from, "25.08.2026")
        self.assertEqual(q_cfg.date_to, "25.11.2026")

        from itacamba_reportes.sap.config import CONFIG_GD20

        gd20_cfg = CONFIG_GD20.to_download_config(
            period_override="10",
            period_high_override="11",
            year_override="2027",
        )
        self.assertEqual(gd20_cfg.period_low, "10")
        self.assertEqual(gd20_cfg.period_high, "11")
        self.assertEqual(gd20_cfg.year_low, "2027")
        self.assertIsNone(gd20_cfg.year_high)
        self.assertEqual(gd20_cfg.variant, "BOT_GD20")
        self.assertEqual(gd20_cfg.layout_name, "//AVRILGD20")

        gd20_cross = CONFIG_GD20.to_download_config(
            period_override="12",
            period_high_override="1",
            year_override="2026",
            year_high_override="2027",
        )
        self.assertEqual(gd20_cross.year_low, "2026")
        self.assertEqual(gd20_cross.year_high, "2027")

        self.assertEqual(
            bridge._resolve_sap_config_dates(
                fecha_desde="2026-12-01",
                corte_fecha="2026-12-31",
            ),
            ("12", "12", "2026", "2026", "31.12.2026"),
        )
        self.assertEqual(
            bridge._resolve_sap_config_dates(
                fecha_desde="2027-01-01",
                corte_fecha="2027-01-15",
            ),
            ("1", "1", "2027", "2027", "15.01.2027"),
        )
        self.assertEqual(
            bridge._resolve_sap_config_dates(
                fecha_desde="2026-12-01",
                corte_fecha="2027-01-10",
            ),
            ("12", "1", "2026", "2027", "10.01.2027"),
        )

    def test_return_to_main_menu_avoids_logoff_confirm(self):
        from itacamba_reportes.sap.session import SapSessionManager

        def _build_mgr(active_wnd_name: str, window_title: str, tx: str):
            pressed: list[str] = []
            mgr = SapSessionManager()
            session = MagicMock()
            session.Info = SimpleNamespace(Transaction=tx)
            session.ActiveWindow = SimpleNamespace(Name=active_wnd_name, Text=window_title)
            mgr._session = session
            mgr.maximize = MagicMock()

            def fake_press(selector: str, timeout: float = 5.0):
                pressed.append(selector)
                if selector == "wnd[0]/tbar[0]/btn[15]":
                    session.ActiveWindow = SimpleNamespace(
                        Name="wnd[1]",
                        Text="¿Desea salir del sistema SAP?",
                    )
                elif selector == "wnd[1]/usr/btnSPOP-OPTION2":
                    session.Info.Transaction = "SESSION_MANAGER"
                    session.ActiveWindow = SimpleNamespace(
                        Name="wnd[0]",
                        Text="SAP Easy Access",
                    )

            def fake_exists(selector: str, timeout: float = 1.0) -> bool:
                wnd_name = session.ActiveWindow.Name
                if wnd_name == "wnd[1]" and selector in (
                    "wnd[1]/usr/btnSPOP-OPTION1",
                    "wnd[1]/usr/btnSPOP-OPTION2",
                ):
                    return True
                return selector == "wnd[0]/tbar[0]/okcd"

            mgr.press_button = MagicMock(side_effect=fake_press)
            mgr.element_exists = MagicMock(side_effect=fake_exists)
            mgr.set_text = MagicMock()
            mgr.send_vkey = MagicMock()
            return mgr, pressed

        # Caso A: popup de cierre de sesion ya abierto en wnd[1]
        mgr_a, pressed_a = _build_mgr("wnd[1]", "Salir del sistema", "SESSION_MANAGER")
        mgr_a.return_to_main_menu()
        self.assertIn("wnd[1]/usr/btnSPOP-OPTION2", pressed_a)
        self.assertNotIn("wnd[1]/usr/btnSPOP-OPTION1", pressed_a)

        # Caso B: dentro de transaccion, btn[15] dispara confirmacion de logoff
        mgr_b, pressed_b = _build_mgr("wnd[0]", "GD20", "GD20")
        mgr_b.return_to_main_menu()
        self.assertIn("wnd[0]/tbar[0]/btn[15]", pressed_b)
        self.assertIn("wnd[1]/usr/btnSPOP-OPTION2", pressed_b)
        self.assertNotIn("wnd[1]/usr/btnSPOP-OPTION1", pressed_b)

        # Caso C: popup de salida de lista en ZVCSD381 SI debe confirmar SPOP-OPTION1
        mgr_c = SapSessionManager()
        pressed_c: list[str] = []
        sess_c = MagicMock()
        sess_c.Info = SimpleNamespace(Transaction="ZVCSD381")
        sess_c.ActiveWindow = SimpleNamespace(Name="wnd[0]", Text="Lista ZVCSD381")
        mgr_c._session = sess_c
        mgr_c.maximize = MagicMock()
        mgr_c.set_text = MagicMock()
        mgr_c.send_vkey = MagicMock()

        def press_c(selector: str, timeout: float = 5.0):
            pressed_c.append(selector)
            if selector == "wnd[0]/tbar[0]/btn[15]":
                sess_c.ActiveWindow = SimpleNamespace(Name="wnd[1]", Text="Salir de la lista")
            elif selector == "wnd[1]/usr/btnSPOP-OPTION1":
                sess_c.Info.Transaction = "SESSION_MANAGER"
                sess_c.ActiveWindow = SimpleNamespace(Name="wnd[0]", Text="SAP Easy Access")

        mgr_c.press_button = MagicMock(side_effect=press_c)
        mgr_c.element_exists = MagicMock(
            side_effect=lambda s, timeout=1.0: sess_c.ActiveWindow.Name == "wnd[1]"
            and s in ("wnd[1]/usr/btnSPOP-OPTION1", "wnd[1]/usr/btnSPOP-OPTION2")
        )
        mgr_c.return_to_main_menu()
        self.assertIn("wnd[1]/usr/btnSPOP-OPTION1", pressed_c)

    def test_execute_download_report_freshness_check(self):
        from itacamba_reportes.sap.actions.download_action import execute_download_report
        from itacamba_reportes.sap.config import SapDownloadConfig
        from itacamba_reportes.sap.exceptions import SapExportError

        def _make_mgr():
            mgr = MagicMock()
            mgr.session.ActiveWindow = SimpleNamespace(Name="wnd[0]", Text="SAP")
            mgr.element_exists.side_effect = lambda s, timeout=0.0: s == "wnd[0]/mbar/menu[0]/menu[3]/menu[1]"
            return mgr

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_home = Path(tmp_dir) / "home"
            sap_gui_dir = tmp_home / "Documents" / "SAP" / "SAP GUI"
            sap_gui_dir.mkdir(parents=True, exist_ok=True)
            target_dir = Path(tmp_dir) / "target"
            target_dir.mkdir(parents=True, exist_ok=True)

            exported_name = "TEST_FRESH_EXPORT_9129.xlsx"
            exported_file = sap_gui_dir / exported_name
            exported_file.write_bytes(b"stale-content")
            os.utime(exported_file, (900.0, 900.0))

            cfg = SapDownloadConfig(
                transaction="gd20",
                export_filename=exported_name,
                target_dir=target_dir,
            )

            now_ts = {"val": 1000.0}

            def fake_time() -> float:
                return now_ts["val"]

            def fake_sleep(seconds: float) -> None:
                if seconds == 0.5:
                    now_ts["val"] += 35.0

            with patch("pathlib.Path.home", return_value=tmp_home), \
                 patch("itacamba_reportes.sap.actions.download_action.SapSecurityWatchdog") as _m_wd, \
                 patch("itacamba_reportes.sap.actions.download_action.close_excel_workbook_by_name", return_value=0), \
                 patch("itacamba_reportes.sap.actions.download_action.time.sleep", side_effect=fake_sleep), \
                 patch("itacamba_reportes.sap.actions.download_action.time.time", side_effect=fake_time):
                with self.assertRaises(SapExportError):
                    execute_download_report(_make_mgr(), cfg)

            now_ts["val"] = 1000.0
            os.utime(exported_file, (1001.0, 1001.0))
            with patch("pathlib.Path.home", return_value=tmp_home), \
                 patch("itacamba_reportes.sap.actions.download_action.SapSecurityWatchdog") as _m_wd, \
                 patch("itacamba_reportes.sap.actions.download_action.close_excel_workbook_by_name", return_value=0), \
                 patch("itacamba_reportes.sap.actions.download_action.time.sleep", side_effect=fake_sleep), \
                 patch("itacamba_reportes.sap.actions.download_action.time.time", side_effect=fake_time):
                out_path = execute_download_report(_make_mgr(), cfg)

            self.assertEqual(out_path, target_dir / exported_name)
            self.assertTrue(out_path.exists())
            self.assertFalse(exported_file.exists())

    def test_gd20_dynamic_fiscal_year_by_label(self):
        from itacamba_reportes.sap.actions.download_action import execute_download_report
        from itacamba_reportes.sap.config import SapDownloadConfig
        from itacamba_reportes.sap.session import SapSessionManager

        f_reg = SimpleNamespace(Type="GuiCTextField", Name="F9008005-LOW", text="0", Changeable=True, Top=80, Left=120)
        f_year_low = SimpleNamespace(Type="GuiTextField", Name="F9008007-LOW", text="2026", Changeable=True, Top=120, Left=120)
        f_year_high = SimpleNamespace(Type="GuiTextField", Name="F9008007-HIGH", text="", Changeable=True, Top=120, Left=240)
        f_soc = SimpleNamespace(Type="GuiTextField", Name="F9008008-LOW", text="4253", Changeable=True, Top=140, Left=120)

        usr_area = SimpleNamespace(
            Children=[
                SimpleNamespace(Type="GuiLabel", Name="%_F9008005_%_APP_%-TEXT", Text="Clase de registro:", Top=80, Left=10),
                f_reg,
                SimpleNamespace(Type="GuiLabel", Name="%_F9008007_%_APP_%-TEXT", Text="Ejercicio:", Top=120, Left=10),
                f_year_low,
                f_year_high,
                SimpleNamespace(Type="GuiLabel", Name="%_F9008008_%_APP_%-TEXT", Text="Sociedad:", Top=140, Left=10),
                f_soc,
            ]
        )

        mgr = SapSessionManager()
        mgr.find_element = MagicMock(return_value=usr_area)

        ok = mgr.set_selection_field_by_label(("ejercicio", "fiscal year"), value_low="2027")
        self.assertTrue(ok)
        self.assertEqual(f_year_low.text, "2027")
        self.assertEqual(f_year_high.text, "")
        self.assertEqual(f_soc.text, "4253")
        self.assertEqual(f_reg.text, "0")

        # Cruce de anio seguido de retorno a anio unico limpia el campo HIGH
        self.assertTrue(mgr.set_selection_field_by_label(("ejercicio",), value_low="2026", value_high="2027"))
        self.assertEqual((f_year_low.text, f_year_high.text), ("2026", "2027"))
        self.assertTrue(mgr.set_selection_field_by_label(("ejercicio",), value_low="2027", value_high=None))
        self.assertEqual((f_year_low.text, f_year_high.text), ("2027", ""))

        # Fallback por alineacion vertical (Top) sin nombre %-STEM-%
        f_alt = SimpleNamespace(Type="GuiTextField", Name="TXT_ANIO-LOW", text="2025", Changeable=True, Top=200, Left=150)
        usr_top = SimpleNamespace(
            Children=[
                SimpleNamespace(Type="GuiLabel", Name="LBL_EJ", Text="Ejercicio", Top=200, Left=20),
                f_alt,
            ]
        )
        mgr.find_element = MagicMock(return_value=usr_top)
        self.assertTrue(mgr.set_selection_field_by_label(("ejercicio",), value_low="2027"))
        self.assertEqual(f_alt.text, "2027")

        # Si no existe el campo Ejercicio, devuelve False sin romper
        mgr.find_element = MagicMock(return_value=SimpleNamespace(Children=[]))
        self.assertFalse(mgr.set_selection_field_by_label(("ejercicio",), value_low="2027"))

        # Verificar que execute_download_report invoca set_selection_field_by_label tras cargar variante y antes de F8
        call_order: list[str] = []
        fake_mgr = MagicMock()
        fake_mgr.session.ActiveWindow = SimpleNamespace(Name="wnd[0]", Text="GD20")

        def fake_exists(selector: str, timeout: float = 0.0) -> bool:
            return selector in (
                "wnd[0]/tbar[1]/btn[17]",
                "wnd[0]/usr/ctxtF9008025-LOW",
                "wnd[0]/usr/ctxtF9008025-HIGH",
            )

        def fake_press(selector: str, timeout: float = 5.0) -> None:
            call_order.append(f"press:{selector}")

        def fake_set_label(**kwargs) -> bool:
            call_order.append(f"year:{kwargs.get('value_low')}")
            return True

        fake_mgr.element_exists.side_effect = fake_exists
        fake_mgr.press_button.side_effect = fake_press
        fake_mgr.set_selection_field_by_label.side_effect = fake_set_label

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_home = Path(tmp_dir) / "home"
            sap_dir = tmp_home / "Documents" / "SAP" / "SAP GUI"
            sap_dir.mkdir(parents=True, exist_ok=True)
            target_dir = Path(tmp_dir) / "target"
            target_dir.mkdir(parents=True, exist_ok=True)
            fname = "TEST_GD20_YEAR_9129.xlsx"
            exported = sap_dir / fname
            exported.write_bytes(b"ok")
            os.utime(exported, (1001.0, 1001.0))

            cfg = SapDownloadConfig.for_gd20(
                period="1",
                year="2027",
                layout_name=None,
                export_filename=fname,
                target_dir=target_dir,
            )
            now_box = {"val": 1000.0}
            with patch("pathlib.Path.home", return_value=tmp_home), \
                 patch("itacamba_reportes.sap.actions.download_action.SapSecurityWatchdog"), \
                 patch("itacamba_reportes.sap.actions.download_action.close_excel_workbook_by_name", return_value=0), \
                 patch("itacamba_reportes.sap.actions.download_action.time.sleep", return_value=None), \
                 patch("itacamba_reportes.sap.actions.download_action.time.time", side_effect=lambda: now_box["val"]):
                execute_download_report(fake_mgr, cfg)

        self.assertLess(call_order.index("press:wnd[0]/tbar[1]/btn[17]"), call_order.index("year:2027"))
        self.assertLess(call_order.index("year:2027"), call_order.index("press:wnd[0]/tbar[1]/btn[8]"))

    def test_sap_wait_for_alv_and_separate_lifecycles(self):
        from itacamba_reportes.sap.actions import execute_download_gd20, execute_download_query
        from itacamba_reportes.sap.actions.download_action import _wait_for_alv_after_f8
        from itacamba_reportes.sap.exceptions import SapExportError
        from itacamba_reportes.sap.selectors import SELECTORES_SAP

        # 1. _wait_for_alv_after_f8 detecta menu_export_excel cuando Query carga sin btn[33]
        mgr_ok = MagicMock()
        mgr_ok.get_status_message.return_value = ("", "")
        calls = {"n": 0}

        def exists_after_two(selector: str, timeout: float = 0.0) -> bool:
            if selector == SELECTORES_SAP.gd20.menu_export_excel:
                calls["n"] += 1
                return calls["n"] >= 2
            return False

        mgr_ok.element_exists.side_effect = exists_after_two
        with patch("itacamba_reportes.sap.actions.download_action.time.sleep", return_value=None):
            _wait_for_alv_after_f8(mgr_ok, SELECTORES_SAP, "ZVCSD381", timeout=5.0)
        self.assertEqual(calls["n"], 2)

        # 2. Error en sbar aborta de inmediato sin esperar timeout completo
        mgr_err = MagicMock()
        mgr_err.get_status_message.return_value = ("E", "No existen partidas")
        with self.assertRaises(SapExportError):
            _wait_for_alv_after_f8(mgr_err, SELECTORES_SAP, "ZVCSD381", timeout=45.0)

        # 3. Flujo separado GD20 y Query con ensure_ready + close_at_end garantizado en finally
        mgr_gd = MagicMock()
        with patch("itacamba_reportes.sap.actions.download_gd20_action.execute_download_report", return_value=Path("GD20.xlsx")) as m_dl, \
             patch("itacamba_reportes.sap.actions.download_gd20_action.finalize_sap_session") as m_fin:
            out = execute_download_gd20(mgr_gd, period_low=11, year=2026, ensure_ready=True, close_at_end=True)
        self.assertEqual(out, Path("GD20.xlsx"))
        mgr_gd.ensure_connected_and_ready.assert_called_once_with(auto_launch=True)
        m_dl.assert_called_once()
        m_fin.assert_called_once_with(mgr_gd, close_at_end=True)

        mgr_q = MagicMock()
        with patch("itacamba_reportes.sap.actions.download_query_action.execute_download_report", side_effect=SapExportError("boom")), \
             patch("itacamba_reportes.sap.actions.download_query_action.finalize_sap_session") as m_fin_q:
            with self.assertRaises(SapExportError):
                execute_download_query(mgr_q, date_to="26.11.2026", ensure_ready=True, close_at_end=True)
        mgr_q.ensure_connected_and_ready.assert_called_once_with(auto_launch=True)
        m_fin_q.assert_called_once_with(mgr_q, close_at_end=True)

    def test_cli_download_sap_separate_gd20_and_query_flags(self):
        from itacamba_reportes import cli

        captured_cfgs: list[object] = []
        fake_mgr = MagicMock()

        def fake_dl(_mgr, cfg):
            captured_cfgs.append(cfg)
            return Path(cfg.export_filename)

        with patch("itacamba_reportes.sap.SapSessionManager", return_value=fake_mgr), \
             patch("itacamba_reportes.sap.actions.execute_download_report", side_effect=fake_dl), \
             patch("itacamba_reportes.sap.actions.finalize_sap_session") as m_fin:
            rc1 = cli.main(["download-sap", "-t", "gd20", "-y", "2027", "-p", "1", "--period-high", "2", "--layout", "//AVRILGD20"])
            rc2 = cli.main(["download-sap", "-t", "query", "--date-to", "26.11.2026", "--keep-open"])

        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)
        self.assertEqual(len(captured_cfgs), 2)
        gd_cfg, q_cfg = captured_cfgs
        self.assertEqual(gd_cfg.year_low, "2027")
        self.assertEqual(gd_cfg.period_low, "1")
        self.assertEqual(gd_cfg.period_high, "2")
        self.assertEqual(gd_cfg.layout_name, "//AVRILGD20")
        self.assertEqual(q_cfg.transaction, "ZVCSD381")
        self.assertEqual(q_cfg.date_from, "26.08.2026")
        self.assertEqual(q_cfg.date_to, "26.11.2026")
        self.assertEqual(m_fin.call_args_list[0].kwargs["close_at_end"], True)
        self.assertEqual(m_fin.call_args_list[1].kwargs["close_at_end"], False)

    def test_bridge_validate_web_configuration_and_zbcs_layout(self):
        from itacamba_reportes.ui.bridge import BotBridge, SAP_TASKS_PATH

        bridge = BotBridge()
        stored = json.loads(SAP_TASKS_PATH.read_text(encoding="utf-8"))
        zbcs_stored = next(t for t in stored if t["id"] == "zbcs")
        zbcs_default = next(t for t in bridge._default_sap_tasks() if t["id"] == "zbcs")
        self.assertEqual(zbcs_stored["layout"], "")
        self.assertEqual(zbcs_default["layout"], "")

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            fijos = root / "fijos"
            din = root / "dinamicos"
            rep = root / "reports"
            for d in (fijos, din, rep):
                d.mkdir(parents=True, exist_ok=True)
            (fijos / "REFERENCIAS.xlsx").write_bytes(b"ok")
            (fijos / "PROYECCION-SEMANAL.xlsx").write_bytes(b"ok")
            (din / "CARTERA.xlsx").write_bytes(b"ok")
            (din / "GD20.xlsx").write_bytes(b"ok")
            (din / "QUERY.xlsx").write_bytes(b"ok")
            sap_exe = root / "saplogon.exe"
            sap_exe.write_bytes(b"exe")

            env_file = root / ".env"
            env_file.write_text(
                "\n".join([
                    f"SAP_LOGON_PATH={sap_exe}",
                    "SAP_AMBIENT=PRD",
                    "SAP_SYSTEM=E05",
                    "SAP_MANDANTE=300",
                    "SAP_USER=bot_user",
                    "SAP_PASSWORD=test_pass",
                    "DB_SERVER=127.0.0.1",
                    "DB_NAME=ItacambaTest",
                    "DB_USER=sa",
                    "DB_PASSWORD=db_pass",
                    f"PATH_INSUMOS_FIJOS={fijos}",
                    f"PATH_INSUMOS_DINAMICOS={din}",
                    f"PATH_REPORTES_SALIDA={rep}",
                ]),
                encoding="utf-8",
            )
            prof_json = json.dumps({
                "id": "diaria",
                "nombre": "Corrida Diaria",
                "mesEjecucion": "2026-11",
                "fechaDesde": "2026-11-01",
                "fechaHasta": "2026-11-26",
            })
            with patch.dict(os.environ, {}, clear=False), \
                 patch("itacamba_reportes.ui.bridge.ENV_FILE_PATH", env_file), \
                 patch.object(bridge, "test_sql_connection", return_value={"ok": True, "message": "SQL OK"}), \
                 patch.object(bridge, "test_sap_logon", return_value={"ok": True, "message": "SAP OK"}):
                res = bridge.validate_web_configuration(profile_id="diaria", profile_json=prof_json)

            self.assertTrue(res["ok"])
            self.assertEqual(res["errors"], 0)
            self.assertEqual(res["sap_resolved"]["gd20_year"], "2026")
            self.assertEqual(res["sap_resolved"]["gd20_period"], "11")
            self.assertEqual(res["sap_resolved"]["query_date_from"], "26.08.2026")
            self.assertEqual(res["sap_resolved"]["query_date_to"], "26.11.2026")

            bad_prof = json.dumps({
                "id": "bad",
                "nombre": "Rango malo",
                "fechaDesde": "2026-11-28",
                "fechaHasta": "2026-11-10",
            })
            with patch.dict(os.environ, {}, clear=False), \
                 patch("itacamba_reportes.ui.bridge.ENV_FILE_PATH", env_file), \
                 patch.object(bridge, "test_sql_connection", return_value={"ok": False, "message": "VPN off"}), \
                 patch.object(bridge, "test_sap_logon", return_value={"ok": True, "message": "SAP OK"}):
                res_bad = bridge.validate_web_configuration(profile_json=bad_prof)
            self.assertFalse(res_bad["ok"])
            self.assertGreaterEqual(res_bad["errors"], 2)

            # Tambien resuelve correctamente cuando .env solo define DATA_PATH + EXPORT_PATH
            env_alt = root / ".env.alt"
            env_alt.write_text(
                "\n".join([
                    f"SAP_LOGON_PATH={sap_exe}",
                    "SAP_AMBIENT=PRD",
                    "SAP_USER=bot_user",
                    "SAP_PASSWORD=test_pass",
                    "DATABASE_URL=mssql+pyodbc://sa:x@localhost/db",
                    f"DATA_PATH={root}",
                    f"EXPORT_PATH={rep}",
                ]),
                encoding="utf-8",
            )
            env_clean = {
                k: v for k, v in os.environ.items()
                if k not in ("PATH_INSUMOS_FIJOS", "PATH_INSUMOS_DINAMICOS", "PATH_REPORTES_SALIDA", "PATH_LOGS_STORAGE")
            }
            with patch.dict(os.environ, env_clean, clear=True), \
                 patch("itacamba_reportes.ui.bridge.ENV_FILE_PATH", env_alt), \
                 patch.object(bridge, "test_sql_connection", return_value={"ok": True, "message": "SQL OK"}), \
                 patch.object(bridge, "test_sap_logon", return_value={"ok": True, "message": "SAP OK"}):
                res_alt = bridge.validate_web_configuration(profile_id="diaria")
            self.assertTrue(res_alt["ok"], res_alt["checks"])
            self.assertEqual(res_alt["sap_resolved"]["gd20_year"], "2026")
            self.assertEqual(res_alt["sap_resolved"]["gd20_period"], "11")

    def test_win_dialogs_security_popup_and_excel_closer(self):
        from itacamba_reportes.sap.win_dialogs import (
            SapSecurityWatchdog,
            close_excel_workbook_by_name,
            dismiss_sap_security_popup,
        )

        # 1. Simular dialogo Win32 "Seguridad SAP GUI" con Recordar + Permitir + Rechazar
        posted: list[tuple[int, int]] = []
        sent: list[tuple[int, int]] = []

        titles = {
            100: "Seguridad SAP GUI",
            101: "&Recordar mi decisión",
            102: "&Permitir",
            103: "&Rechazar",
            200: "Otra ventana cualquiera",
            201: "Permitir",
        }
        classes = {101: "Button", 102: "Button", 103: "Button", 201: "Button"}

        fake_win32con = SimpleNamespace(BM_GETCHECK=0x00F0, BM_CLICK=0x00F5, BST_CHECKED=1)

        class _FakeWin32Gui:
            @staticmethod
            def IsWindowVisible(hwnd):
                return True

            @staticmethod
            def IsWindowEnabled(hwnd):
                return True

            @staticmethod
            def GetWindowText(hwnd):
                return titles.get(hwnd, "")

            @staticmethod
            def GetClassName(hwnd):
                return classes.get(hwnd, "#32770")

            @staticmethod
            def EnumWindows(cb, extra):
                for top in (100, 200):
                    cb(top, extra)

            @staticmethod
            def EnumChildWindows(parent, cb, extra):
                for ch in ({100: (101, 102, 103), 200: (201,)}[parent]):
                    cb(ch, extra)

            @staticmethod
            def SetForegroundWindow(hwnd):
                pass

            @staticmethod
            def SendMessage(hwnd, msg, wparam, lparam):
                sent.append((hwnd, msg))
                if hwnd == 101 and msg == 0x00F0:
                    return 0  # desmarcado inicialmente
                return 0

            @staticmethod
            def PostMessage(hwnd, msg, wparam, lparam):
                posted.append((hwnd, msg))

        with patch.dict(sys.modules, {"win32gui": _FakeWin32Gui, "win32con": fake_win32con}), \
             patch("itacamba_reportes.sap.win_dialogs.time.sleep", return_value=None):
            count = dismiss_sap_security_popup(remember_decision=True)

        self.assertEqual(count, 1)
        self.assertIn((101, fake_win32con.BM_CLICK), sent)
        self.assertEqual(posted, [(102, fake_win32con.BM_CLICK)])

        # 2. Watchdog ejecuta y detiene hilo limpiamente
        with patch("itacamba_reportes.sap.win_dialogs.dismiss_sap_security_popup", return_value=1):
            with SapSecurityWatchdog(poll_interval=0.01) as wd:
                import time as _t
                _t.sleep(0.03)
        self.assertGreaterEqual(wd.dismissed_count, 1)

        # 3. close_excel_workbook_by_name solo cierra libros exportados y respeta libros del usuario
        class _FakeWorkbooks(list):
            @property
            def Count(self) -> int:
                return len(self)

        wb_query = MagicMock()
        wb_query.Name = "QUERY.xlsx"
        wb_query.FullName = r"C:\tmp\QUERY.xlsx"
        wb_user = MagicMock()
        wb_user.Name = "Presupuesto.xlsx"
        wb_user.FullName = r"C:\tmp\Presupuesto.xlsx"

        books_mixed = _FakeWorkbooks([wb_query, wb_user])
        wb_query.Close.side_effect = lambda SaveChanges=False: books_mixed.remove(wb_query)
        app_mixed = MagicMock()
        app_mixed.Workbooks = books_mixed

        wb_gd20 = MagicMock()
        wb_gd20.Name = "GD20.xlsx"
        wb_gd20.FullName = r"C:\tmp\GD20.xlsx"
        books_only = _FakeWorkbooks([wb_gd20])
        wb_gd20.Close.side_effect = lambda SaveChanges=False: books_only.remove(wb_gd20)
        app_only = MagicMock()
        app_only.Workbooks = books_only

        class _FakeEnum:
            def Next(self, _n):
                return []

        class _FakeRot:
            def EnumRunning(self):
                return _FakeEnum()

        active_holder = {"app": app_mixed}
        fake_pythoncom = SimpleNamespace(
            CoInitialize=MagicMock(),
            CoUninitialize=MagicMock(),
            GetRunningObjectTable=lambda: _FakeRot(),
            CreateBindCtx=lambda _x: None,
            IID_IDispatch=0,
        )
        fake_win32com_client = SimpleNamespace(
            GetActiveObject=lambda prog_id: active_holder["app"],
            Dispatch=lambda obj: obj,
        )
        fake_win32com = SimpleNamespace(client=fake_win32com_client)

        with patch.dict(sys.modules, {"pythoncom": fake_pythoncom, "win32com": fake_win32com, "win32com.client": fake_win32com_client}), \
             patch("itacamba_reportes.sap.win_dialogs._has_excel_window", return_value=True):
            closed_n = close_excel_workbook_by_name(["QUERY.xlsx"], wait_timeout=0.0)
            active_holder["app"] = app_only
            closed_gd = close_excel_workbook_by_name(["GD20.xlsx"], wait_timeout=0.0)

        self.assertEqual(closed_n, 1)
        wb_query.Close.assert_called_once_with(SaveChanges=False)
        wb_user.Close.assert_not_called()
        app_mixed.Quit.assert_not_called()

        self.assertEqual(closed_gd, 1)
        wb_gd20.Close.assert_called_once_with(SaveChanges=False)
        app_only.Quit.assert_called_once()

    def test_segmented_routes_env_reader_and_io_resolution(self):
        from itacamba_reportes.core.io.reader import FastExcelReader
        from itacamba_reportes.core.settings import EnvConfig
        from itacamba_reportes.inputs.cartera.ingest import CARTERA_SPEC
        from itacamba_reportes.inputs.gd20.ingest import GD20_SPEC
        from itacamba_reportes.inputs.proyeccion.ingest import resolve_proyeccion_path
        from itacamba_reportes.inputs.query.ingest import QUERY_SPEC
        from itacamba_reportes.inputs.referencias.ingest import resolve_referencias_path
        from itacamba_reportes.outputs.historial_ventas.export import export_historial_ventas

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fijos_dir = root / "custom_fixed_area"
            din_dir = root / "custom_daily_sap"
            rep_dir = root / "custom_bi_delivery"
            for d in (fijos_dir, din_dir, rep_dir):
                d.mkdir(parents=True, exist_ok=True)

            (fijos_dir / "REFERENCIAS.xlsx").write_bytes(b"ref")
            (fijos_dir / "PROYECCION-SEMANAL.xlsx").write_bytes(b"proy")
            (din_dir / "GD20.xlsx").write_bytes(b"gd20")
            (din_dir / "QUERY.xlsx").write_bytes(b"query")
            (din_dir / "CARTERA.xlsx").write_bytes(b"cartera")

            env_path = root / ".env"
            env_path.write_text(
                "\n".join([
                    f"PATH_INSUMOS_FIJOS={fijos_dir}",
                    f"PATH_INSUMOS_DINAMICOS={din_dir}",
                    f"PATH_REPORTES_SALIDA={rep_dir}",
                ]),
                encoding="utf-8",
            )
            env_clean = {
                k: v for k, v in os.environ.items()
                if k not in ("PATH_INSUMOS_FIJOS", "PATH_INSUMOS_DINAMICOS", "PATH_REPORTES_SALIDA", "DATA_PATH", "EXPORT_PATH")
            }
            try:
                with patch.dict(os.environ, env_clean, clear=True):
                    EnvConfig.reload(env_path)
                    self.assertEqual(EnvConfig.FIXED_INPUTS_PATH, fijos_dir)
                    self.assertEqual(EnvConfig.DYNAMIC_INPUTS_PATH, din_dir)
                    self.assertEqual(EnvConfig.REPORTS_OUTPUT_PATH, rep_dir)
                    self.assertEqual(EnvConfig.EXPORT_PATH, rep_dir)

                    self.assertEqual(resolve_referencias_path(), fijos_dir / "REFERENCIAS.xlsx")
                    self.assertEqual(resolve_proyeccion_path(), fijos_dir / "PROYECCION-SEMANAL.xlsx")
                    self.assertEqual(FastExcelReader(GD20_SPEC, EnvConfig.DYNAMIC_INPUTS_PATH).resolve_path(), din_dir / "GD20.xlsx")
                    self.assertEqual(FastExcelReader(QUERY_SPEC, EnvConfig.DYNAMIC_INPUTS_PATH).resolve_path(), din_dir / "QUERY.xlsx")
                    self.assertEqual(FastExcelReader(CARTERA_SPEC, EnvConfig.DYNAMIC_INPUTS_PATH).resolve_path(), din_dir / "CARTERA.xlsx")

                    # Validar que exportar historial escribe en REPORTS_OUTPUT_PATH y sincroniza en FIXED_INPUTS_PATH
                    import pandas as pd
                    df_dummy = pd.DataFrame([{"col": 1}])
                    out_hist = export_historial_ventas(df_ventas=df_dummy, df_despachos=df_dummy)
                    self.assertIsNotNone(out_hist)
                    self.assertEqual(out_hist.parent, rep_dir)
                    self.assertTrue(out_hist.exists())
                    self.assertTrue((fijos_dir / "HISTORIAL VENTAS.xlsx").exists())
            finally:
                EnvConfig.reload()

    def test_bridge_segmented_routes_save_seed_and_validation(self):
        from itacamba_reportes.ui.bridge import BotBridge
        from itacamba_reportes.core.settings import EnvConfig

        bridge = BotBridge()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fijos_dir = root / "fijos_seg"
            din_dir = root / "din_seg"
            rep_dir = root / "rep_seg"
            for d in (fijos_dir, din_dir, rep_dir):
                d.mkdir(parents=True, exist_ok=True)
            (fijos_dir / "REFERENCIAS.xlsx").write_bytes(b"ok")
            (fijos_dir / "PROYECCION-SEMANAL.xlsx").write_bytes(b"ok")
            sap_exe = root / "saplogon.exe"
            sap_exe.write_bytes(b"exe")

            env_file = root / ".env"
            env_file.write_text("SAP_AMBIENT=PRD\n", encoding="utf-8")

            env_clean = {
                k: v for k, v in os.environ.items()
                if k not in ("PATH_INSUMOS_FIJOS", "PATH_INSUMOS_DINAMICOS", "PATH_REPORTES_SALIDA", "DATA_PATH", "EXPORT_PATH")
            }
            try:
                with patch.dict(os.environ, env_clean, clear=True), \
                     patch("itacamba_reportes.ui.bridge.ENV_FILE_PATH", env_file), \
                     patch("itacamba_reportes.core.db.connection.set_engine"):
                    # 1. _read_env_file expone las 3 rutas aunque aun no esten escritas en .env
                    items = bridge._read_env_file()
                    keys = [it["clave"] for it in items]
                    for expected_key in ("PATH_INSUMOS_FIJOS", "PATH_INSUMOS_DINAMICOS", "PATH_REPORTES_SALIDA"):
                        self.assertIn(expected_key, keys)

                    # 2. Guardar variables segmentadas desde UI y verificar resumen de rutas
                    vars_payload = [
                        {"clave": "SAP_LOGON_PATH", "valor": str(sap_exe), "categoria": "sap", "activa": True},
                        {"clave": "SAP_AMBIENT", "valor": "PRD", "categoria": "sap", "activa": True},
                        {"clave": "SAP_USER", "valor": "bot", "categoria": "sap", "activa": True},
                        {"clave": "SAP_PASSWORD", "valor": "secret", "categoria": "sap", "activa": True},
                        {"clave": "DATABASE_URL", "valor": "mssql+pyodbc://sa:x@localhost/db", "categoria": "db", "activa": True},
                        {"clave": "PATH_INSUMOS_FIJOS", "valor": str(fijos_dir), "categoria": "rutas", "activa": True},
                        {"clave": "PATH_INSUMOS_DINAMICOS", "valor": str(din_dir), "categoria": "rutas", "activa": True},
                        {"clave": "PATH_REPORTES_SALIDA", "valor": str(rep_dir), "categoria": "rutas", "activa": True},
                    ]
                    save_res = bridge.save_env_variables(json.dumps(vars_payload))
                    self.assertEqual(save_res["status"], "ok")

                    with patch.object(bridge, "test_sql_connection", return_value={"ok": True, "message": "SQL OK"}), \
                         patch.object(bridge, "test_sap_logon", return_value={"ok": True, "message": "SAP OK"}):
                        val_res = bridge.validate_web_configuration(profile_json=json.dumps({
                            "id": "diaria",
                            "nombre": "Diaria",
                            "fechaDesde": "2026-11-01",
                            "fechaHasta": "2026-11-26",
                        }))

                    self.assertTrue(val_res["ok"], val_res["checks"])
                    self.assertEqual(len(val_res["routes_summary"]), 3)
                    seg_check = next(c for c in val_res["checks"] if c["id"] == "routes_segmentation")
                    self.assertEqual(seg_check["status"], "ok")

                    # 3. Colision entre rutas debe reportar error
                    vars_payload[-1]["valor"] = str(din_dir)
                    bridge.save_env_variables(json.dumps(vars_payload))
                    with patch.object(bridge, "test_sql_connection", return_value={"ok": True, "message": "SQL OK"}), \
                         patch.object(bridge, "test_sap_logon", return_value={"ok": True, "message": "SAP OK"}):
                        coll_res = bridge.validate_web_configuration(profile_json=json.dumps({
                            "id": "diaria",
                            "nombre": "Diaria",
                            "fechaDesde": "2026-11-01",
                            "fechaHasta": "2026-11-26",
                        }))
                    self.assertFalse(coll_res["ok"])
                    self.assertTrue(any(c["id"] == "routes_collision" and c["status"] == "error" for c in coll_res["checks"]))
            finally:
                EnvConfig.reload()

    def test_blank_profiles_and_monthly_day1_schedule_lifecycle(self):
        from itacamba_reportes.ui.bridge import BotBridge

        bridge = BotBridge()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_profiles = root / "missing_profiles.json"
            with patch("itacamba_reportes.ui.bridge.PROFILES_PATH", missing_profiles):
                self.assertEqual(bridge.get_execution_profiles(), [])

            # Schedule de 30 dias incluyendo dia 1 con mes_actual (hasta ayer) y descargarSap activo
            perfil = {
                "id": "mensual_real",
                "nombre": "Rutina Mensual 30 Ciclos",
                "frecuencia": "diaria",
                "horaFija": "06:00",
                "mesEjecucion": "2027-01",
                "descargarSap": True,
            }
            asignaciones = {
                f"2027-01-{day:02d}": {"tipo": "mes_actual", "incluirDia": False, "hora": "06:00"}
                for day in range(1, 31)
            }
            cal = {"id": "mensual_real", "mes": "2027-01", "asignaciones": asignaciones}

            with patch.object(bridge, "_activate_schedule_jobs", return_value={"status": "started", "total": 30}) as mock_act:
                res = bridge.start_profile_schedule(perfil, cal)
            self.assertEqual(res["status"], "started")
            jobs_arg = mock_act.call_args[0][0]
            self.assertEqual(len(jobs_arg), 30)
            self.assertEqual(jobs_arg[0]["fecha"], "2027-01-01")
            self.assertEqual(jobs_arg[0]["params"]["fechaDesde"], "2026-12-01")
            self.assertTrue(jobs_arg[0]["params"]["descargarSap"])

            # Al detener programacion mientras una corrida esta en curso, tambien solicita parada cooperativa
            bridge._scheduler_active = True
            bridge._is_running = True
            bridge._stop_requested = False
            stop_res = bridge.stop_schedule()
            self.assertEqual(stop_res["status"], "ok")
            self.assertFalse(stop_res["active"])
            self.assertTrue(bridge._stop_requested)
            bridge._is_running = False
            bridge._stop_requested = False

    def test_cached_file_change_detection_and_cartera_dynamic_path(self):
        from unittest.mock import MagicMock
        from itacamba_reportes.core import state
        from itacamba_reportes.core.settings import EnvConfig
        import itacamba_reportes.inputs.cartera.pipeline as cartera_pl
        import itacamba_reportes.inputs.gd20.pipeline as gd20_pl
        import itacamba_reportes.inputs.proyeccion.pipeline as proy_pl
        import itacamba_reportes.inputs.query.pipeline as query_pl
        import itacamba_reportes.inputs.referencias.pipeline as ref_pl

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fijos_dir = root / "fijos"
            din_dir = root / "dinamicos"
            data_legacy = root / "legacy"
            fijos_dir.mkdir()
            din_dir.mkdir()
            data_legacy.mkdir()

            (fijos_dir / "REFERENCIAS.xlsx").write_bytes(b"ref_v1")
            (fijos_dir / "PROYECCION-SEMANAL.xlsx").write_bytes(b"proy_v1")
            (din_dir / "CARTERA.xlsx").write_bytes(b"cart_v1")
            (din_dir / "QUERY.xlsx").write_bytes(b"qry_v1")
            (din_dir / "GD20.xlsx").write_bytes(b"gd20_v1")

            state_file = root / "state.json"
            mock_conn = MagicMock()
            mock_conn.execute.return_value.scalar.return_value = 10
            mock_eng = MagicMock()
            mock_eng.connect.return_value.__enter__.return_value = mock_conn

            with patch.object(state, "STATE_PATH", state_file), \
                 patch.object(EnvConfig, "FIXED_INPUTS_PATH", fijos_dir), \
                 patch.object(EnvConfig, "DYNAMIC_INPUTS_PATH", din_dir), \
                 patch.object(EnvConfig, "DATA_PATH", data_legacy), \
                 patch.object(cartera_pl, "engine", mock_eng), \
                 patch.object(ref_pl, "engine", mock_eng), \
                 patch.object(proy_pl, "engine", mock_eng), \
                 patch.object(query_pl, "engine", mock_eng), \
                 patch.object(gd20_pl, "engine", mock_eng), \
                 patch("itacamba_reportes.core.audit.tracker.record_execution"):

                # 1. CARTERA usa DYNAMIC_INPUTS_PATH y omite segunda pasada si no cambio
                with patch.object(cartera_pl, "ingest_cartera", return_value=10) as m_ing_c, \
                     patch.object(cartera_pl, "transform_cartera", return_value=10) as m_trn_c:
                    cartera_pl.run_pipeline()
                    cartera_pl.run_pipeline()
                    self.assertEqual(m_ing_c.call_count, 1)
                    self.assertEqual(m_trn_c.call_count, 1)

                # 2. REFERENCIAS y PROYECCION omiten re-ingesta si el archivo no cambio
                with patch.object(ref_pl, "ingest_referencias", return_value={"int_ref_material": 5}) as m_ing_r:
                    ref_pl.run_pipeline()
                    ref_pl.run_pipeline()
                    self.assertEqual(m_ing_r.call_count, 1)

                with patch.object(proy_pl, "ingest_proyeccion", return_value=8) as m_ing_p:
                    proy_pl.run_pipeline()
                    proy_pl.run_pipeline()
                    self.assertEqual(m_ing_p.call_count, 1)

                # 3. QUERY y GD20 omiten lectura Excel si no cambio, pero SIEMPRE ejecutan transformacion SQL
                with patch.object(query_pl, "ingest_query", return_value=20) as m_ing_q, \
                     patch.object(query_pl, "transform_query", return_value=15) as m_trn_q:
                    query_pl.run_pipeline(corte_fecha="2026-11-26")
                    query_pl.run_pipeline(corte_fecha="2026-11-27")
                    self.assertEqual(m_ing_q.call_count, 1)
                    self.assertEqual(m_trn_q.call_count, 2)

                with patch.object(gd20_pl, "ingest_gd20", return_value=30) as m_ing_g, \
                     patch.object(gd20_pl, "transform_gd20", return_value=25) as m_trn_g:
                    gd20_pl.run_pipeline(corte_fecha="2026-11-26")
                    gd20_pl.run_pipeline(corte_fecha="2026-11-27")
                    self.assertEqual(m_ing_g.call_count, 1)
                    self.assertEqual(m_trn_g.call_count, 2)

                # Al cambiar GD20.xlsx (nueva descarga SAP), vuelve a ingestar
                (din_dir / "GD20.xlsx").write_bytes(b"gd20_v2_updated_by_sap")
                with patch.object(gd20_pl, "ingest_gd20", return_value=32) as m_ing_g2, \
                     patch.object(gd20_pl, "transform_gd20", return_value=27):
                    gd20_pl.run_pipeline(corte_fecha="2026-11-28")
                    self.assertEqual(m_ing_g2.call_count, 1)

    def test_exports_no_timestamp_and_atomic_replace(self):
        from sqlalchemy import create_engine, text
        from sqlalchemy.pool import StaticPool
        import itacamba_reportes.core.db.connection as conn_mod
        from itacamba_reportes.core.db.base import Base
        from itacamba_reportes.core.settings import EnvConfig
        import itacamba_reportes.outputs.ventas_bi.export as v_exp
        import itacamba_reportes.outputs.despacho_bi.export as d_exp
        import itacamba_reportes.outputs.despacho_mes.export as m_exp

        mem_eng = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(mem_eng)
        orig_eng = conn_mod._engine
        conn_mod.set_engine(mem_eng)

        try:
            with mem_eng.begin() as conn:
                conn.execute(text("INSERT INTO int_ventas_bi (ejercicio, documento_comercial, numero_documento, material, version, is_current, valid_from, cd_status) VALUES (2026, 1, 1, 1, 1, 1, '2026-11-01 00:00:00', 'PENDING')"))
                conn.execute(text("INSERT INTO int_despacho_bi (nro_pedido, cod_destinatario, codigo_cliente, dia, mes, anio) VALUES (1, 1, 1, 15, 11, 2026)"))
                conn.execute(text("INSERT INTO int_despacho_mes (dia, codigo_cliente, despacho_t, rf, rf_ajustado_im, proyeccion) VALUES (15, 1, 10.0, 5.0, 5.0, 10.0)"))

            with tempfile.TemporaryDirectory() as tmp:
                rep_dir = Path(tmp) / "reports"
                rep_dir.mkdir()
                with patch.object(EnvConfig, "REPORTS_OUTPUT_PATH", rep_dir), \
                     patch.object(EnvConfig, "EXPORT_PATH", rep_dir), \
                     patch.object(v_exp, "engine", mem_eng), \
                     patch.object(d_exp, "engine", mem_eng), \
                     patch.object(m_exp, "engine", mem_eng):
                    p_v = v_exp.export_ventas_bi()
                    p_d = d_exp.export_despacho_bi()
                    p_m = m_exp.export_despacho_mes(corte_fecha="2026-11-27")
                    # Segunda corrida debe sobrescribir exactamente los mismos nombres sin marca de fecha
                    p_v2 = v_exp.export_ventas_bi()

                    self.assertEqual(p_v.name, "VENTAS_BI.xlsx")
                    self.assertEqual(p_v2, p_v)
                    self.assertEqual(p_d.name, "DESPACHO_BI.xlsx")
                    self.assertEqual(p_m.name, "DESPACHO_MES.xlsx")
                    self.assertEqual(sorted(f.name for f in rep_dir.iterdir()), ["DESPACHO_BI.xlsx", "DESPACHO_MES.xlsx", "VENTAS_BI.xlsx"])
        finally:
            conn_mod.set_engine(orig_eng)

    def test_scd2_multi_line_document_no_collision_and_atomic_tx(self):
        from datetime import datetime, timedelta
        from sqlalchemy import create_engine, text
        import itacamba_reportes.core.db.connection as conn_mod
        from itacamba_reportes.core.db.base import Base
        import itacamba_reportes.outputs.ventas_bi.transform as v_tr

        mem_eng = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(mem_eng)
        orig_eng = conn_mod._engine
        conn_mod.set_engine(mem_eng)

        try:
            with mem_eng.begin() as conn:
                conn.execute(text("""
                    INSERT INTO int_gd20 (ejercicio, periodo_contable, documento_comercial, numero_documento, material, numero_cuenta, destinatario, cantidad)
                    VALUES
                        (2026, 11, 1001, 5001, 20001, 33111010, 7001, -10.0),
                        (2026, 11, 1001, 5001, 20001, 33111020, 7001, -2.0)
                """))

            with patch.object(v_tr, "engine", mem_eng):
                inserted = v_tr.upsert_ventas_bi_scd2()
                self.assertEqual(inserted, 2)

                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
                with mem_eng.begin() as conn:
                    conn.execute(text(f"UPDATE int_ventas_bi SET valid_from = '{yesterday}'"))
                    conn.execute(text("UPDATE int_gd20 SET cantidad = -12.0 WHERE numero_cuenta = 33111010"))

                # Atomicidad ante fallo de insercion: si falla bulk_insert_df, NO debe quedar expirada la fila vieja
                with patch.object(v_tr, "bulk_insert_df", side_effect=RuntimeError("Fallo simulado VPN")):
                    with self.assertRaises(RuntimeError):
                        v_tr.upsert_ventas_bi_scd2()
                with mem_eng.connect() as conn:
                    live_before = conn.execute(text("SELECT COUNT(*) FROM int_ventas_bi WHERE is_current = 1")).scalar()
                    self.assertEqual(live_before, 2)

                updated = v_tr.upsert_ventas_bi_scd2()
                self.assertEqual(updated, 1)

            with mem_eng.connect() as conn:
                active_rows = conn.execute(text(
                    "SELECT numero_cuenta, cantidad, version FROM int_ventas_bi WHERE is_current = 1 ORDER BY numero_cuenta"
                )).fetchall()
                self.assertEqual(len(active_rows), 2)
                self.assertEqual((active_rows[0][0], float(active_rows[0][1]), active_rows[0][2]), (33111010, -12.0, 2))
                self.assertEqual((active_rows[1][0], float(active_rows[1][1]), active_rows[1][2]), (33111020, -2.0, 1))
        finally:
            conn_mod.set_engine(orig_eng)

    def test_coerce_numeric_warns_and_sync_table_indexes(self):
        import logging
        from sqlalchemy import create_engine, inspect
        from itacamba_reportes.core.db.base import Base
        import itacamba_reportes.core.db.connection as conn_mod
        from itacamba_reportes.core.db.schema import sync_table_indexes
        from itacamba_reportes.core.io.reader import coerce_numeric_series

        s = pd.Series(["10.5", "#", "", "1.250,50", "texto_malo"])
        with self.assertLogs("itacamba_reportes.core.io.reader", level=logging.WARNING) as cm:
            out = coerce_numeric_series(s, "cantidad", context="gd20", fill_zero=True)
        self.assertEqual(float(out.iloc[0]), 10.5)
        self.assertEqual(float(out.iloc[1]), 0.0)
        self.assertEqual(float(out.iloc[3]), 0.0)
        self.assertIn("2 valor(es) no numérico(s)", "\n".join(cm.output))

        mem_eng = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(mem_eng)
        orig_eng = conn_mod._engine
        conn_mod.set_engine(mem_eng)
        try:
            with mem_eng.begin() as conn:
                conn.exec_driver_sql("DROP INDEX IF EXISTS ix_int_ventas_bi_is_current_periodo")
                conn.exec_driver_sql("DROP INDEX IF EXISTS ix_int_despacho_bi_anio_mes")
            sync_table_indexes()
            insp = inspect(mem_eng)
            v_idx = {ix["name"] for ix in insp.get_indexes("int_ventas_bi")}
            d_idx = {ix["name"] for ix in insp.get_indexes("int_despacho_bi")}
            self.assertIn("ix_int_ventas_bi_is_current_periodo", v_idx)
            self.assertIn("ix_int_despacho_bi_anio_mes", d_idx)
        finally:
            conn_mod.set_engine(orig_eng)

    def test_bridge_obsolete_env_classification_and_cleanup(self):
        from itacamba_reportes.ui.bridge import BotBridge
        from itacamba_reportes.core.settings import EnvConfig

        bridge = BotBridge()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env_file = root / ".env"
            env_file.write_text(
                "\n".join([
                    "SAP_AMBIENT=PRD",
                    "SAP_USER=bot_sap",
                    "MAIL_HOST=smtp.office365.com",
                    "MAIL_PASSWORD=old_mail_pwd",
                    "CLICK_CONFIDENCE=0.8",
                    "CLICK_TIMEOUT=10",
                    "SAP_PROCESS=saplogon.exe",
                    "SAP_WINDOW_TITLE=SAP Logon 770",
                    f"PATH_INSUMOS_FIJOS={root}",
                ]),
                encoding="utf-8",
            )
            try:
                with patch("itacamba_reportes.ui.bridge.ENV_FILE_PATH", env_file), \
                     patch("itacamba_reportes.core.db.connection.set_engine"):
                    items = bridge._read_env_file()
                    obs = [it["clave"] for it in items if it["categoria"] == "obsoletas"]
                    self.assertEqual(set(obs), {"MAIL_HOST", "MAIL_PASSWORD", "CLICK_CONFIDENCE", "CLICK_TIMEOUT", "SAP_PROCESS", "SAP_WINDOW_TITLE"})

                    clean_res = bridge.clean_obsolete_env_variables()
                    self.assertEqual(clean_res["status"], "ok")
                    self.assertEqual(clean_res["removed"], 6)

                    saved_txt = env_file.read_text(encoding="utf-8")
                    self.assertIn("SAP_AMBIENT=PRD", saved_txt)
                    self.assertIn("SAP_USER=bot_sap", saved_txt)
                    self.assertNotIn("CLICK_CONFIDENCE", saved_txt)
                    self.assertNotIn("MAIL_HOST", saved_txt)
            finally:
                EnvConfig.reload()

    def test_bulk_insert_mssql_fast_executemany_direct(self):
        from unittest.mock import MagicMock
        import numpy as np
        from itacamba_reportes.core.db.bulk import bulk_insert_df
        from itacamba_reportes.inputs.query.models import QueryStgModel

        captured = {}
        fake_cursor = MagicMock()
        fake_cursor.fast_executemany = False
        fake_cursor.executemany.side_effect = lambda sql, params: captured.update({"sql": sql, "params": params, "fast": fake_cursor.fast_executemany})
        fake_driver = MagicMock()
        fake_driver.cursor.return_value = fake_cursor
        fake_raw = MagicMock()
        fake_raw.driver_connection = fake_driver
        fake_conn = MagicMock()
        fake_conn.connection = fake_raw
        fake_eng = MagicMock()
        fake_eng.dialect.name = "mssql"
        fake_conn.engine = fake_eng

        df = pd.DataFrame({
            "nro_pedido": [101, 102],
            "material": ["CEMENTO", "CLINKER"],
            "cantidad_ton": [10.5, np.nan],
            "fecha_salida": [pd.Timestamp("2026-11-27"), pd.NaT],
        })
        rows = bulk_insert_df(QueryStgModel, df, truncate_first=False, engine=fake_eng, conn=fake_conn)
        self.assertEqual(rows, 2)
        self.assertTrue(captured["fast"])
        self.assertIn("INSERT INTO [stg_query]", captured["sql"])
        self.assertIsNone(captured["params"][1][2])
        self.assertIsNone(captured["params"][1][3])
        fake_cursor.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
