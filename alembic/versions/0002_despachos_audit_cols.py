from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_despachos_audit"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _add_col_if_missing(inspector, table: str, name: str, ddl_col: sa.Column) -> None:
    existing = {c["name"] for c in inspector.get_columns(table)}
    if name not in existing:
        op.add_column(table, ddl_col)


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    raw_5 = [
        ("atributo_7",                    sa.String(20)),
        ("departamento_facturacion",      sa.String(100)),
        ("nombre_transportista_persona",  sa.String(200)),
        ("telefono_1",                    sa.String(50)),
        ("tipo_servicio_transporte",      sa.String(100)),
    ]
    for tbl in ("stg_query", "int_query"):
        if tbl in insp.get_table_names():
            for name, sa_type in raw_5:
                _add_col_if_missing(
                    insp, tbl, name,
                    sa.Column(name, sa_type, nullable=True),
                )

    despacho_cols = [
        ("atributo_7",                    sa.String(20)),
        ("departamento_facturacion",      sa.String(100)),
        ("nombre_transportista_persona",  sa.String(200)),
        ("telefono_1",                    sa.String(50)),
        ("tipo_servicio_transporte",      sa.String(100)),
        ("placa",                         sa.String(50)),
        ("tp_vehiculo",                   sa.String(100)),
        ("distancia_km",                  sa.Integer()),
        ("traslados",                     sa.Numeric(18, 4)),
        ("link",                          sa.String(500)),
    ]
    if "int_despacho_bi" in insp.get_table_names():
        for name, sa_type in despacho_cols:
            _add_col_if_missing(
                insp, "int_despacho_bi", name,
                sa.Column(name, sa_type, nullable=True),
            )


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    def drop_if_present(table: str, name: str) -> None:
        if table not in insp.get_table_names():
            return
        existing = {c["name"] for c in insp.get_columns(table)}
        if name in existing:
            op.drop_column(table, name)

    for tbl in ("int_query", "stg_query"):
        for name in ("tipo_servicio_transporte", "telefono_1",
                     "nombre_transportista_persona", "departamento_facturacion",
                     "atributo_7"):
            drop_if_present(tbl, name)

    for name in ("link", "traslados", "distancia_km", "tp_vehiculo", "placa",
                 "tipo_servicio_transporte", "telefono_1",
                 "nombre_transportista_persona", "departamento_facturacion",
                 "atributo_7"):
        drop_if_present("int_despacho_bi", name)
