from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pandas as pd
from sqlalchemy import create_engine, text

from itacamba_reportes.core.audit.hashing import add_hashes_to_df, compute_row_hash
from itacamba_reportes.core.db.base import Base
from itacamba_reportes.core.db.bulk import bulk_insert_df
from itacamba_reportes.inputs.referencias.models import ChannelRefModel


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
        from itacamba_reportes.inputs.referencias.models import ChannelRefModel

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


if __name__ == "__main__":
    unittest.main()
