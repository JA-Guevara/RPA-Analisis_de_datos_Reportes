"""Tokens-string que representan NULL en los Excels SAP / Referencias.

Centralizado aqui para evitar drift entre la capa de ingestion (readers)
y la capa de persistencia (mappers). El superset incluye:

    - Strings vacios y signos placeholder ('', '#', '-', '--')
    - Variantes 'N/A' / 'NA'
    - Literales 'null' / 'None' / 'nan' (case-mix tipico de Excel)
    - 'Sin asignar' y 'Not assigned' (tokens SAP)
    - Errores Excel ('#REF!', '#N/A')

Si el negocio agrega un nuevo token, se modifica UNA sola vez aqui.
"""

from __future__ import annotations


NULL_TOKENS: frozenset[str] = frozenset({
    "", "#", "-", "--",
    "N/A", "n/a", "NA",
    "null", "NULL", "None", "none",
    "nan", "NaN",
    "Sin asignar", "sin asignar", "SIN ASIGNAR",
    "Not assigned", "not assigned", "NOT ASSIGNED",
    "#REF!", "#N/A",
})
