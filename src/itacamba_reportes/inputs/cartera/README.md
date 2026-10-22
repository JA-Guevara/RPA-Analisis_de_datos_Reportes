# Slice de Entrada: CARTERA.xlsx (Catastro de Clientes)

## Descripción
Lee la información de clientes que llega por correo automático (`CARTERA*.xlsx`), la vuelca en `stg_cartera`, y ejecuta la transformación en la Base de Datos para generar `int_cartera`.

## Estructura de Extracción y Cabecera
- **Hoja origen**: `Q_VCBO_ZSDI_I03_CAD_CLIENTE_000`
- **Fila de cabecera**: Fila 6 (índice 6, fila 7 de Excel).
- **Mapeo de Columnas Pareadas**:
  - `Col 0 (Cliente)` -> `cliente` (`BigInteger`)
  - `Col 1 (Unnamed: 1)` -> `nombre_cliente` (`String(500)`)
  - `Col 2 (Attribute 10)` -> `attribute_10` (`String(100)`)
  - `Col 3 (Población)` -> `poblacion` (`String(200)`)
  - `Col 4 (Barrio)` -> `barrio` (`String(200)`)
  - `Col 5 (Attribute 7)` -> `attribute_7` (`String(100)`)
  - `Col 6 (Attribute 6)` -> `attribute_6` (`String(100)`)
  - `Col 7 (Región)` -> `region` (`String(20)`)
  - `Col 8 (Unnamed: 8)` -> `region_nombre` (`String(100)`)
  - `Col 9 (Grupo de cuentas)` -> `grupo_cuentas` (`String(20)`)
  - `Col 21 (Sector)` -> `sector` (`String(20)`)
  - `Col 22 (Unnamed: 22)` -> `sector_desc` (`String(200)`)
  - `Col 23 (Canal Distribución)` -> `canal_distribucion` (`String(20)`)
  - `Col 24 (Unnamed: 24)` -> `canal_distribucion_desc` (`String(200)`)
  - `Col 25 (Organización de Ventas)` -> `organizacion_ventas` (`String(20)`)
  - `Col 27 (Oficina de Ventas)` -> `oficina_ventas` (`String(20)`)
  - `Col 29 (Grupo de vendedores)` -> `grupo_vendedores` (`String(20)`)
  - `Col 30 (Unnamed: 30)` -> `equipo` (`String(100)`)
  - `Col 32 (Unnamed: 32)` -> `vendedor` (`String(150)`)
  - `Col 34 (Unnamed: 34)` -> `coordinador` (`String(150)`)
  - `Col 36 (Unnamed: 36)` -> `canal` (`String(100)`)
  - `Col 37 (Condición pago)` -> `condicion_pago` (`String(50)`)

## Reglas de Negocio Aplicadas en BD (`transform.sql`)
1. **Deduplicación Estricta (`ROW_NUMBER() OVER(PARTITION BY cliente ORDER BY orden_origen ASC) = 1`)**:
   - `stg_cartera` almacena todas las filas originales (~50.130 filas).
   - `int_cartera` retiene únicamente **un registro único por cliente** (el primer match), emulando fielmente el comportamiento de `VLOOKUP(..., FALSO)` de Excel.
   - Cuenta con índice único en `cliente` (`ix_int_cartera_cliente`), garantizando que los cruces con `int_gd20`, `despacho_bi` y `despacho_mes` sean 1:1 y nunca produzcan multiplicación cartesiana de filas.
2. **Normalización de Nombres**: Reemplazo de tildes en departamentos (`POTOSÍ -> POTOSI`) y conversión a mayúsculas.
3. **Macro `ModificarDonaciones`**: Para cuentas de donaciones (`DONACIONES DTM`, `Cliente Donaciones`, `CLIENTE GENERICO SIN FACTURA`, `DONACIONES COMERCIAL`), asigna automáticamente `vendedor = 'DONACION'` y `coordinador = 'DONACION'`.
