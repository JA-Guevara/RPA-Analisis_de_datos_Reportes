"""Reportes como slices verticales: una carpeta = un reporte completo.

Cada slice contiene pipeline.py (orquestacion), config.yaml (parametros),
columnas.yaml (formulas del cliente, ejecuta ColumnEngine), manifest.yaml
(portada tecnica), reglas.py (logica compleja) y README.md.
Los modelos SQLAlchemy permanecen centralizados en persistence/models
(registro unico de metadata para Alembic; varios reportes comparten
tablas). Decision documentada en Plan_Refactor_Controlado_2026-07-06.
"""
