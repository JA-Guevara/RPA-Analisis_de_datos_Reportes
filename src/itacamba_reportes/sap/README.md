# Módulo SAP: Automatización SAP GUI Scripting (`sap/`)

## 1. Propósito y Filosofía
Este módulo proporciona la automatización enterprise para la interfaz gráfica de SAP GUI mediante SAP GUI Scripting (`win32com` / COM).
Sigue una estricta separación de responsabilidades:
1. **Selectores e IDs técnicos (`selectors.py`)**: Puro dato inmutable (`frozen=True, slots=True`). Ningún valor de negocio está hardcodeado aquí.
2. **Configuración de Negocio (`config.py`)**: Únicamente las variables dinámicas que cambian entre corridas (`transaction`, `ledger`, `variant`, `period`, `layout_row`, `export_filename`).
3. **Cero Comentarios de Bloque (`""" """`)**: El código Python se mantiene libre de docstrings inline; toda la documentación se centraliza en este archivo `.md`.

---

## 2. Variables Dinámicas Reales (Auditadas contra VBScript)

A partir de las grabaciones reales (`Script5.vbs`, `Script6 qyery.vbs`, `Script4.vbs`), las variables dinámicas que intervienen en la descarga son:

| Parámetro | Tipo | Ejemplo GD20 | Ejemplo Query | Control SAP Asociado |
| :--- | :--- | :--- | :--- | :--- |
| `transaction` | `str` | `"gd20"` | `"ZVCSD381"` | Caja de transacciones (`okcd`) |
| `ledger` | `str` | `"VC"` | `""` | Campo Ledger (`RGUD0-LEDGER`) |
| `sociedad` | `str` | `"4253"` | `"4253"` | Sociedad (`P_BUKRS`) |
| `variant` | `str` | `"BOT_GD20"` | `"/IM"` | Variante / Disposición (`BOT_GD20`, `P_VARI`) |
| `period` | `str / int` | Mes actual | `None` | Período Contable (`F9008025-LOW`) |
| `date_from` / `date_to` | `str` | `None` | 3 meses atrás → Hoy | Rango móvil (`S_BUDAT-LOW` / `S_BUDAT-HIGH`) |
| `layout_name` | `str` | `"//AVRILGD20"` | `""` | Búsqueda dinámica en grilla ALV (`btn[33]`) |
| `export_filename` | `str` | `"GD20.xlsx"` | `"QUERY.xlsx"` | Nombre de archivo exportado |

> [!NOTE]
> El flujo unificado (`execute_download_all_sap`) realiza **1 solo login**, ejecuta GD20, regresa limpiamente al menú principal (`return_to_main_menu`), ejecuta Query (`ZVCSD381` con 3 meses móviles) y finaliza con cierre en 2 niveles (`/nex` + `taskkill`).

---

## 3. Estructura de Archivos

```
src/itacamba_reportes/sap/
├── selectors.py                   # Catálogo tipado de IDs técnicos de SAP GUI
├── config.py                      # Clases y variables dinámicas editables (CONFIG_GD20, CONFIG_QUERY)
├── session.py                     # Gestor de conexión COM, ciclo de vida de procesos y retorno a menú
├── exceptions.py                  # Excepciones tipadas (SapConnectionError, SapLoginError, SapExportError)
├── actions/
│   ├── download_action.py         # Motor de descarga individual y flujo conjunto (execute_download_all_sap)
│   ├── download_gd20_action.py    # Wrapper específico GD20
│   ├── download_query_action.py   # Wrapper específico ZVCSD381 / Query
│   ├── login_action.py            # Autenticación de usuario/clave y manejo de multi-logon
│   └── logout_action.py           # Desconexión /nex y cierre de procesos
└── README.md                      # Documentación funcional y técnica del módulo
```

---

## 4. Dónde Modificar las Variables

Para cambiar cualquier valor operativo, edita directamente las clases en [`config.py`](config.py):

```python
# Configuración GD20:
CONFIG_GD20.ledger = "VC"
CONFIG_GD20.variant = "BOT_GD20"
CONFIG_GD20.layout_name = "//AVRILGD20"

# Configuración Query (ZVCSD381 con ventana móvil de 3 meses):
CONFIG_QUERY.transaction = "ZVCSD381"
CONFIG_QUERY.sociedad = "4253"
CONFIG_QUERY.variant = "/IM"
CONFIG_QUERY.months_back = 3
```

---

## 5. Pruebas Rápidas

Para probar la descarga directa desde consola:

```powershell
# Descarga conjunta (GD20 + Query en 1 solo Login)
python main.py download-sap -t all

# Descarga individual GD20 / Query
python main.py download-sap -t gd20
python main.py download-sap -t query
```
