from __future__ import annotations

from sqlalchemy import BigInteger, Column, Integer, String

from itacamba_reportes.persistence.base import Base
from itacamba_reportes.persistence.mixins import TimestampsMixin


class CentroIntModel(Base, TimestampsMixin):
    """Catalogo SAP de Centros.

    NOTA: ni `centro` ni `codigo_sap_cliente` son clave primaria logica
    porque el Excel admite:
      - Filas con `centro` NULL (clientes sin centro asociado).
      - Multiples `centro` apuntando al mismo `codigo_sap_cliente`
        (un cliente puede tener varios centros).
      - Centros sin codigo cliente.
    Persistimos todo lo que viene del Excel; deduplicacion fila completa
    se hace en el reader.
    """

    __tablename__ = "int_ref_centro"

    id = Column(Integer, primary_key=True, autoincrement=True)

    centro             = Column(String(10), index=True, nullable=True)
    codigo_sap_cliente = Column(BigInteger, index=True, nullable=True)
    tipo               = Column(String(50))
