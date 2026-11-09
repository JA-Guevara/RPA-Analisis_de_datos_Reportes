# Módulo SAP: Automatización SAP GUI Scripting (`sap/`)

## 1. Propósito y Filosofía
Este módulo proporciona la automatización enterprise para la interfaz gráfica de SAP GUI mediante SAP GUI Scripting (`win32com` / COM).
Sigue una estricta separación de responsabilidades:
1. **Selectores e IDs técnicos (`selectors.py`)**: Puro dato inmutable (`frozen=True, slots=True`). Ningún valor de negocio está hardcodeado aquí.
2. **Configuración de Negocio (`config.py`)**: Únicamente las variables dinámicas que cambian entre corridas (`transaction`, `ledger`, `variant`, `period`, `layout_row`, `export_filename`).
3. **Cero Comentarios de Bloque (`""" """`)**: El código Python se mantiene libre de docstrings inline; toda la documentación se centraliza en este archivo `.md`.

---

## 2. Variables Dinámicas Reales (Auditadas contra VBScript)

A partir de las grabaciones reales (`Script1.vbs`, `Script2.vbs`, `Script4.vbs`), las **únicas variables dinámicas** que intervienen en la descarga son:

| Parámetro | Tipo | Ejemplo GD20 | Ejemplo Query | Control SAP Asociado |
| :--- | :--- | :--- | :--- | :--- |
| `transaction` | `str` | `"gd20"` | `"zbcs"` | Caja de transacciones (`okcd`) |
| `ledger` | `str` | `"VC"` | `""` | Campo Ledger (`RGUD0-LEDGER`) |
| `variant` | `str` | `"Prueba_GD20"` | `""` | Campo Variante (`V-LOW` tras `btn[17]`) |
| `period` | `str / int`| `10` | `""` | Período Contable (`F9008025-LOW`) |
| `layout_row` | `int` | `16` | `None` | Fila en grilla ALV (`btn[33]`) |
| `export_filename` | `str` | `"GD20.xlsx"`| `"QUERY.xlsx"` | Nombre de archivo exportado |

> [!NOTE]
> No se requieren variables de rangos de fechas (inicio/fin) si la transacción utiliza período o variante fija. Los campos en blanco (`""`) son omitidos automáticamente por el motor sin generar errores.

---

## 3. Estructura de Archivos

```
src/itacamba_reportes/sap/
├── selectors.py                   # Catálogo tipado de IDs técnicos de SAP GUI
├── config.py                      # Clases y variables dinámicas editables (CONFIG_GD20, CONFIG_QUERY)
├── session.py                     # Gestor de conexión COM, ciclo de vida de procesos y reintentos
├── exceptions.py                  # Excepciones tipadas (SapConnectionError, SapLoginError, SapExportError)
├── actions/
│   ├── download_action.py         # Motor de descarga y exportación Excel
│   ├── download_gd20_action.py    # Wrapper específico GD20
│   ├── download_query_action.py   # Wrapper específico ZBCS / Query
│   ├── login_action.py            # Autenticación de usuario/clave y manejo de multi-logon
│   └── logout_action.py           # Desconexión /nex y cierre de procesos
└── README.md                      # Documentación funcional y técnica del módulo
```

---

## 4. Dónde Modificar las Variables

Para cambiar cualquier valor operativo, edita directamente las clases en [`config.py`](config.py):

```python
# Modificar para GD20:
CONFIG_GD20.ledger = "VC"
CONFIG_GD20.variant = "Prueba_GD20"
CONFIG_GD20.period = 11
CONFIG_GD20.layout_row = 16

# Modificar para Query cuando tengas los datos:
CONFIG_QUERY.transaction = "zbcs"
CONFIG_QUERY.ledger = "VC"
CONFIG_QUERY.variant = "MI_VARIANTE"
CONFIG_QUERY.period = 11
CONFIG_QUERY.layout_row = 16
```

---

## 5. Pruebas Rápidas

Para probar la descarga directa desde consola:

```powershell
# Probar GD20
python.exe main.py test-sap --task gd20

# Probar Query
python.exe main.py test-sap --task zbcs
```
