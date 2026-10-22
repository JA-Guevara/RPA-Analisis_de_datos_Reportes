# Slice de Entrada: GD20.xlsx (BASE PANEL del mes)

## Descripción
Lee los movimientos contables de ventas extraídos de SAP (transacción GD20) y genera el compuesto del mes (`int_gd20`), correspondiente a la hoja `BASE PANEL` de `basepanel.xlsm`.

## Ingesta Cruda (`ingest.py`)
- Carga las 49 columnas de SAP a `stg_gd20`.
- Soporta alias de cabecera como `Incoterms (parte 2)`.

## Transformación en Base de Datos (`transform.py`)
Toda la lógica de negocio se ejecuta mediante un `INSERT INTO ... SELECT ... LEFT JOIN` directo en la Base de Datos:
1. **Macro `EliminarFilasFechaActual`**: Descarta los registros con fecha igual o posterior al día de corrida para no procesar jornadas incompletas (desactivable en cierre de mes con flag `--fin-de-mes`).
2. **Macro `EliminarMonedaSociedad`**: Para cuenta `33111020` (bonificación), el ingreso bruto se fija en `0`.
3. **Macro `CambiarSignoVolumen`**: Para cuenta `33111020`, las toneladas bonificadas se asignan con signo positivo.
4. **Macro `DPTO_0`**: Si el destinatario no cuenta con departamento asignado, utiliza automáticamente los datos del pagador.
5. **Lookups**: Cruces indexados contra `int_ref_material`, `int_cartera`, `int_ref_equipo`, `int_ref_almacen` y `int_ref_centro`.
