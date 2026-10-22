from __future__ import annotations

from sqlalchemy import BigInteger, Column, Integer, String
from itacamba_reportes.core.db.base import Base, TimestampsMixin


class ChannelRefModel(Base, TimestampsMixin):
    __tablename__ = "int_ref_almacen"

    id = Column(Integer, primary_key=True, autoincrement=True)
    descripcion_sap = Column(String(100), index=True)
    canal = Column(String(50))
    # Columna segmento: capacidad ampliada a 100 caracteres para evitar truncamientos
    segmento = Column(String(100))


class CenterRefModel(Base, TimestampsMixin):
    __tablename__ = "int_ref_centro"

    id = Column(Integer, primary_key=True, autoincrement=True)
    centro = Column(String(20), index=True)
    nombre = Column(String(150))
    codigo_sap_cliente = Column(BigInteger, index=True)
    tipo = Column(String(50))


class SalesTeamRefModel(Base, TimestampsMixin):
    __tablename__ = "int_ref_equipo"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vendedor_sap = Column(String(150), index=True)
    vendedor = Column(String(150))
    vendedor_ok = Column(String(150))
    grupo_vendedores = Column(String(20), index=True)
    equipo = Column(String(150), index=True)
    gerencia = Column(String(150))


class LocalityRefModel(Base, TimestampsMixin):
    __tablename__ = "int_ref_localidad"

    id = Column(Integer, primary_key=True, autoincrement=True)
    localidad_despacho = Column(String(150), index=True)
    localidad_im = Column(String(150))


class MaterialRefModel(Base, TimestampsMixin):
    __tablename__ = "int_ref_material"

    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(BigInteger, index=True)
    descripcion = Column(String(250))


class WeekRefModel(Base, TimestampsMixin):
    __tablename__ = "int_ref_semana"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dia = Column(Integer, index=True)
    semana = Column(String(50))
