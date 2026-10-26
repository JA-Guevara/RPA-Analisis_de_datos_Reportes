from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0002_add_int_ref_ruta'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if 'int_ref_ruta' not in tables:
        op.create_table('int_ref_ruta',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('codigo_ruta', sa.String(length=50), nullable=True),
            sa.Column('ruta', sa.String(length=200), nullable=True),
            sa.Column('departamento', sa.String(length=100), nullable=True),
            sa.Column('localidad', sa.String(length=150), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_int_ref_ruta_codigo_ruta'), 'int_ref_ruta', ['codigo_ruta'], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if 'int_ref_ruta' in tables:
        op.drop_index(op.f('ix_int_ref_ruta_codigo_ruta'), table_name='int_ref_ruta')
        op.drop_table('int_ref_ruta')
