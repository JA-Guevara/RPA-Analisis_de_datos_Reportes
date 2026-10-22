# Itacamba Reportes - Motor ELT Database-First

Sistema automatizado de procesamiento masivo, transformación relacional y versionado histórico de datos comerciales y operativos de Itacamba Cemento S.A.

## 1. Paradigma Arquitectónico

El sistema sigue estrictamente los principios de **Database-First ELT + Vertical Slicing + Screaming Architecture**:
- **E-L (Extract & Load):** Ingesta cruda y veloz de archivos Excel con motor Rust Calamine directo a tablas de Staging (`stg_*`) sin validaciones pesadas ni cálculos en memoria RAM.
- **T (Transform):** Todo el procesamiento de negocio, cruces dimensionales, resolución de fórmulas de Excel y macros VBA se ejecutan directamente en la Base de Datos mediante SQL set-based.
- **Vertical Slicing:** Cada entidad o flujo de reporte vive en su propio módulo independiente con sus modelos, ingesta, transformación y documentación.

## 2. Mapa de Módulos

- `core/`: Motor compartido de base de datos, conexión resiliente (SQL Server / SQLite), bulk inserts, lector Calamine y hashing SCD2.
- `inputs/`: Vertical slices de ingesta y normalización:
  - `referencias/`: Catálogos maestros (Almacenes, Centros, Materiales, Equipos, Localidades, Semanas).
  - `cartera/`: Padrón general de clientes y normalización de donaciones.
  - `query/`: Despachos operativos de SAP ZBCS (layout IM de 24 columnas).
  - `proyeccion/`: Proyecciones comerciales semanales (RF Ajustado).
  - `gd20/`: Facturación comercial de SAP GD20 -> BASE PANEL.
- `outputs/`: Vertical slices de generación y acumulación de reportes para Power BI:
  - `ventas_bi/`: Histórico acumulativo multianual de facturación con SCD Tipo 2 (SHA-256).
  - `despacho_bi/`: Histórico acumulativo real de despachos.
  - `despacho_mes/`: Resumen del mes en curso combinando despacho real + proyección comercial (`UNION ALL`).

## 3. Comandos CLI

```bash
# Inicializar esquemas en base de datos
python main.py init-db

# Ejecución por slice
python main.py run-referencias
python main.py run-cartera
python main.py run-query
python main.py run-proyeccion
python main.py run-gd20
python main.py run-ventas-bi
python main.py run-despacho-bi
python main.py run-despacho-mes

# Ejecución completa de punta a punta
python main.py run-all
```
