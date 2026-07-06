from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, UniqueConstraint

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.mixins import TimestampsMixin


class CarteraIntModel(Base, TimestampsMixin):

    __tablename__ = "int_cartera"
    __table_args__ = (
        UniqueConstraint(
            "cliente",
            "sector",
            "organizacion_ventas",
            "oficina_ventas",
            name="uq_int_cartera_cliente_sector_org_oficina",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente = Column(BigInteger, index=True, nullable=False)
    nombre_cliente = Column(String(500))

    attribute_10 = Column(String(100))
    attribute_7 = Column(String(100))
    attribute_6 = Column(String(100))

    poblacion = Column(String(200))
    barrio = Column(String(200))
    calle = Column(String(500))
    codigo_postal = Column(String(20))
    region = Column(String(10))
    region_nombre = Column(String(100))

    telefono = Column(String(50))
    nit = Column(String(50))
    gcd_cod_emplaz_fiscal = Column(String(50))

    grupo_cuentas = Column(String(20))
    grupo_cuentas_desc = Column(String(200))

    sector = Column(String(10))
    sector_desc = Column(String(200))

    canal_distribucion = Column(String(20))
    canal_distribucion_desc = Column(String(200))

    organizacion_ventas = Column(String(20))
    organizacion_ventas_desc = Column(String(200))

    oficina_ventas = Column(String(20))
    oficina_ventas_desc = Column(String(200))

    grupo_vendedores = Column(String(20))
    equipo = Column(String(100))
    representante_ventas = Column(String(100))
    vendedor = Column(String(100))
    coordinador_ventas = Column(String(100))
    coordinador = Column(String(100))

    via_pago = Column(String(50))
    condicion_pago = Column(String(50))
    trilha = Column(String(50))
    canal = Column(String(50))

    zemailadd = Column(String(100))
    zvcrisk = Column(String(50))
    tipo_operacion = Column(String(50))
    contador = Column(Integer)
    fecha_inclusion = Column(DateTime)
