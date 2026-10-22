# Módulo RPA: Automatización SAP GUI Scripting (`sap/`)

## 1. Propósito
Proporciona una capa de automatización enterprise para la interfaz gráfica de SAP GUI (SAP GUI Scripting via COM / `pywin32`), estructurada bajo el patrón **Page Object / Action Pattern**.

Reemplaza los scripts VBScript planos e históricos (`Script1.vbs` y `Script2.vbs`) por un diseño desacoplado, resiliente y **100% dinámico y parametrizable**. Ningún código de transacción, periodo, variante o archivo está fijado en duro.

---

## 2. Arquitectura del Módulo

```
src/itacamba_reportes/sap/
├── selectors.py                   # Catálogo centralizado de IDs de la interfaz SAP (Locators)
├── config.py                      # Dataclass de configuración dinámica (SapDownloadConfig)
├── session.py                     # Gestor de conexión COM, reintentos y timeouts
├── exceptions.py                  # Jerarquía tipada de excepciones de automatización
├── actions/                       # Flujos y acciones atómicas reutilizables
│   ├── login_action.py            # Autenticación, control de mandante y multi-logon
│   ├── logout_action.py           # Desconexión segura (/nex)
│   ├── download_action.py         # Motor genérico de descarga dinámicamente parametrizada
│   ├── download_gd20_action.py    # Wrapper especializado para GD20
│   └── download_query_action.py   # Wrapper especializado para ZBCS / Queries
└── README.md                      # Esta documentación técnica
```

---

## 3. Parametrización Dinámica (`config.py`)

La clase `SapDownloadConfig` desacopla completamente los valores de consulta de la lógica de automatización:

```python
from itacamba_reportes.sap import SapDownloadConfig, SapSessionManager
from itacamba_reportes.sap.actions import execute_download_report

# 1. Configuración dinámica para cualquier transacción SAP
config = SapDownloadConfig(
    transaction="gd20",             # Variable: cualquier transacción (ej: gd20, zbcs, sq01)
    ledger="VC",                    # Variable: ledger contable
    variant="Prueba_GD20",          # Variable: variante guardada
    period_low=9,                   # Variable: periodo inicial
    period_high=9,                  # Variable: periodo final
    year=2026,                      # Variable: ejercicio
    layout_row=16,                  # Variable: fila de disposición ALV
    export_filename="GD20_SEP",     # Variable: nombre de archivo exportado
    target_dir="storage/raw/gd20",  # Variable: carpeta destino
)

session_manager = SapSessionManager()
execute_download_report(session_manager, config)
```

### Fábricas Rápidas (Factory Methods)
- `SapDownloadConfig.for_gd20(...)`: Configura una extracción de libro mayor GD20.
- `SapDownloadConfig.for_query(...)`: Configura una extracción de despachos o query operativo (ZBCS).

---

## 4. Inyección de Datos y Catálogo de Selectores (`selectors.py`)

Siguiendo el principio de **Inyección de Dependencias (Dependency Injection)** y **Value Objects puros**, los selectores de SAP están estructurados en `dataclasses` fuertemente tipadas, inmutables (`frozen=True`) y de alta eficiencia de memoria (`slots=True`):

```python
from itacamba_reportes.sap import SELECTORES_SAP, SelectoresSAP, SelectoresGD20

# 1. Uso por defecto (Singleton inmutable canónico)
print(SELECTORES_SAP.gd20.ledger)         # "wnd[0]/usr/ctxtRGUD0-LEDGER"
print(SELECTORES_SAP.barra.okcode)         # "wnd[0]/tbar[0]/okcd"
print(SELECTORES_SAP.login.usuario)        # "wnd[0]/usr/txtRSYST-BNAME"

# 2. Inyección de Dependencias personalizada (útil para pruebas o mandantes distintos)
selectores_custom = SelectoresSAP(
    gd20=SelectoresGD20(ledger="wnd[0]/usr/ctxtCUSTOM-LEDGER")
)
execute_download_report(session_manager, config, selectors=selectores_custom)
```

### Agrupación Semántica
- **`SelectoresVentana`**: IDs de ventanas (`main`, `modal_1`, `modal_2`).
- **`SelectoresBarra`**: Caja de comandos (`okcode`), barra de estado (`status_bar`) y botones estándar (`btn_enter_key`, `btn_back`, `btn_execute_f8`).
- **`SelectoresLogin`**: Campos de autenticación (`usuario`, `password`, `mandante`, `lenguaje`) y controles de multi-logon.
- **`SelectoresGD20`**: Campos del libro mayor, variantes, periodos, selección ALV y menús de exportación a Excel.
- **`SelectoresZBCS`**: Campos de transacciones operativas y rangos de fechas.

---

## 5. Gestor de Sesión (`session.py`)
Maneja la vinculación a la instancia COM `SAPGUI` activa:
- **`find_element(selector, timeout=10.0)`**: Búsqueda con reintentos y tiempo de espera configurable.
- **`element_exists(selector)`**: Verificación no bloqueante de presencia de control.
- **`handle_multilogon_if_present()`**: Detecta si otro usuario o sesión previa quedó abierta y selecciona automáticamente la opción de continuar.
- **`get_status_message()`**: Lee el mensaje de la barra de estado y su severidad (`S`, `W`, `E`, `A`).

---

## 6. Acciones Disponibles (`actions/`)

### `execute_download_report(session_manager, config: SapDownloadConfig)`
Motor genérico que orquesta el ciclo de vida de descarga en SAP:
1. Navega a `config.transaction`.
2. Asigna `ledger` si aplica.
3. Invoca la `variant` si está configurada.
4. Ajusta dinámicamente `period_low` y `period_high`.
5. Aplica filtros de fecha `date_from` y `date_to`.
6. Aplica campos adicionales en `custom_inputs`.
7. Ejecuta reporte (F8).
8. Selecciona disposición de columnas ALV si se definió `layout_row`.
9. Exporta a Excel con el nombre `config.export_filename`.
10. Limpia ventanas y regresa al menú raíz de SAP.
11. Mueve el archivo a `config.target_dir` si se indicó.

### `execute_download_gd20(session_manager, ...)`
Wrapper de conveniencia para transacciones contables GD20 con valores predeterminados seguros pero sobreescribibles.

### `execute_download_query(session_manager, ...)`
Wrapper de conveniencia para transacciones operativas ZBCS con filtros de fecha dinámicos.

---

## 7. Ejecución desde CLI
El pipeline expone un comando de consola para disparar descargas sin modificar código:

```bash
# Descarga dinámica de GD20 para el periodo 9
python -m itacamba_reportes.cli download-sap -t gd20 -l VC -v Prueba_GD20 -p 9 -f GD20_MES9

# Descarga dinámica de Query ZBCS por rango de fechas
python -m itacamba_reportes.cli download-sap -t zbcs --date-from 01.09.2026 --date-to 30.09.2026 -f QUERY_SEP
```

---

## 8. Requisitos Previos en SAP GUI
Para que el motor de scripting funcione:
1. **En el Servidor SAP**: El parámetro de sistema `sapgui/user_scripting` debe estar en `TRUE` (transacción `RZ11`).
2. **En el Cliente Windows**: En Opciones de SAP GUI $\rightarrow$ *Accesibilidad y Scripting* $\rightarrow$ *Scripting*:
   - Habilitar el Scripting.
   - Desactivar *"Notificar cuando se ejecute un script"* (para permitir ejecución desatendida).
