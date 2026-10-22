# Inputs - Slices Verticales de Ingesta y Normalización

Agrupa los módulos encargados de leer las fuentes crudas externas (Excel provenientes de SAP o de planificación comercial), cargarlas a tablas `stg_*` y aplicar las reglas de normalización para generar las tablas `int_*`.

## Slices de Entrada

| Módulo | Archivo Origen | Tabla Staging | Tabla Intermedia | Descripción |
|---|---|---|---|---|
| `referencias` | `REFERENCIAS.xlsx` | — | `int_ref_*` | 6 catálogos maestros: Almacén, Centros, Materiales, Equipos de venta, Localidades y Semanas. |
| `cartera` | `CARTERA.xlsx` | `stg_cartera` | `int_cartera` | Padrón de clientes con índice `orden_origen` y macro `ModificarDonaciones`. |
| `query` | `QUERY.xlsx` | `stg_query` | `int_query` | Despachos operativos de SAP ZBCS (layout IM de 24 columnas). Filtra el mes objetivo (`EliminarMeses`). |
| `proyeccion` | `PROYECCION-SEMANAL.xlsx` | `stg_proyeccion` | — | Proyecciones comerciales semanales (RF Ajustado semanal). Sanea códigos cliente no numéricos a 0. |
| `gd20` | `GD20.xlsx` | `stg_gd20` | `int_gd20` | Facturación de SAP GD20 a BASE PANEL (49 columnas origen -> 77 columnas normalizadas con macros VBA en SQL). |

## Principio de Diseño
Ningún slice de entrada realiza transformaciones complejas en Python ni bucles celda por celda. La ingesta es directa a Base de Datos y la transformación se ejecuta vía SQL nativo.
