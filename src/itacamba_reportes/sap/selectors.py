from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SelectoresVentana:
    main: str = "wnd[0]"
    modal_1: str = "wnd[1]"
    modal_2: str = "wnd[2]"


@dataclass(frozen=True, slots=True)
class SelectoresBarra:
    okcode: str = "wnd[0]/tbar[0]/okcd"
    status_bar: str = "wnd[0]/sbar"
    btn_enter_key: int = 0
    btn_save: str = "wnd[0]/tbar[0]/btn[11]"
    btn_back: str = "wnd[0]/tbar[0]/btn[15]"
    btn_cancel: str = "wnd[0]/tbar[0]/btn[12]"
    btn_execute_f8: str = "wnd[0]/tbar[1]/btn[8]"


@dataclass(frozen=True, slots=True)
class SelectoresLogin:
    usuario: str = "wnd[0]/usr/txtRSYST-BNAME"
    password: str = "wnd[0]/usr/pwdRSYST-BCODE"
    mandante: str = "wnd[0]/usr/txtRSYST-MANDT"
    lenguaje: str = "wnd[0]/usr/txtRSYST-LANGU"
    multilogon_opt2: str = "wnd[1]/usr/radMULTI_LOGON_OPT2"
    multilogon_confirm: str = "wnd[1]/tbar[0]/btn[0]"


@dataclass(frozen=True, slots=True)
class SelectoresGD20:
    ledger: str = "wnd[0]/usr/ctxtRGUD0-LEDGER"
    btn_get_variant: str = "wnd[0]/tbar[1]/btn[17]"
    popup_variant_name: str = "wnd[1]/usr/txtV-LOW"
    popup_btn_find_variant: str = "wnd[1]/tbar[0]/btn[8]"
    period_low: str = "wnd[0]/usr/ctxtF9008025-LOW"
    period_high: str = "wnd[0]/usr/ctxtF9008025-HIGH"
    btn_choose_layout: str = "wnd[0]/tbar[1]/btn[33]"
    layout_combo: str = "wnd[1]/usr/subSUB_CONFIGURATION:SAPLSALV_CUL_LAYOUT_CHOOSE:0500/cmbG51_SCREEN-USPEC_LBOX"
    layout_grid: str = "wnd[1]/usr/subSUB_CONFIGURATION:SAPLSALV_CUL_LAYOUT_CHOOSE:0500/cntlD500_CONTAINER/shellcont/shell"
    menu_export_excel: str = "wnd[0]/mbar/menu[0]/menu[3]/menu[1]"
    export_filename: str = "wnd[1]/usr/ssubSUB_CONFIGURATION:SAPLSALV_GUI_CUL_EXPORT_AS:0512/txtGS_EXPORT-FILE_NAME"
    export_dir_path: str = "wnd[1]/usr/ctxtDY_PATH"
    export_file_name_direct: str = "wnd[1]/usr/ctxtDY_FILENAME"
    export_btn_generate: str = "wnd[1]/tbar[0]/btn[20]"
    export_btn_replace: str = "wnd[1]/tbar[0]/btn[11]"
    exit_confirm_dialog: str = "wnd[1]/usr/btnSPOP-OPTION2"


@dataclass(frozen=True, slots=True)
class SelectoresZBCS:
    okcode: str = "zbcs"
    fecha_desde: str = "wnd[0]/usr/ctxtS_ERDAT-LOW"
    fecha_hasta: str = "wnd[0]/usr/ctxtS_ERDAT-HIGH"


@dataclass(frozen=True, slots=True)
class SelectoresSAP:
    ventana: SelectoresVentana = field(default_factory=SelectoresVentana)
    barra: SelectoresBarra = field(default_factory=SelectoresBarra)
    login: SelectoresLogin = field(default_factory=SelectoresLogin)
    gd20: SelectoresGD20 = field(default_factory=SelectoresGD20)
    zbcs: SelectoresZBCS = field(default_factory=SelectoresZBCS)


SELECTORES_SAP = SelectoresSAP()

# Aliases de compatibilidad directa
WND_MAIN = SELECTORES_SAP.ventana.main
WND_MODAL_1 = SELECTORES_SAP.ventana.modal_1
WND_MODAL_2 = SELECTORES_SAP.ventana.modal_2
OKCODE = SELECTORES_SAP.barra.okcode
STATUS_BAR = SELECTORES_SAP.barra.status_bar
BTN_ENTER_KEY = SELECTORES_SAP.barra.btn_enter_key
BTN_SAVE = SELECTORES_SAP.barra.btn_save
BTN_BACK = SELECTORES_SAP.barra.btn_back
BTN_CANCEL = SELECTORES_SAP.barra.btn_cancel
BTN_EXECUTE_F8 = SELECTORES_SAP.barra.btn_execute_f8
LOGIN_USER = SELECTORES_SAP.login.usuario
LOGIN_PASSWORD = SELECTORES_SAP.login.password
LOGIN_MANDANTE = SELECTORES_SAP.login.mandante
LOGIN_LANGUAGE = SELECTORES_SAP.login.lenguaje
POPUP_MULTILOGON_OPT2 = SELECTORES_SAP.login.multilogon_opt2
POPUP_MULTILOGON_CONFIRM = SELECTORES_SAP.login.multilogon_confirm
GD20_LEDGER = SELECTORES_SAP.gd20.ledger
GD20_BTN_GET_VARIANT = SELECTORES_SAP.gd20.btn_get_variant
GD20_POPUP_VARIANT_NAME = SELECTORES_SAP.gd20.popup_variant_name
GD20_POPUP_BTN_FIND_VARIANT = SELECTORES_SAP.gd20.popup_btn_find_variant
GD20_PERIOD_LOW = SELECTORES_SAP.gd20.period_low
GD20_PERIOD_HIGH = SELECTORES_SAP.gd20.period_high
GD20_BTN_CHOOSE_LAYOUT = SELECTORES_SAP.gd20.btn_choose_layout
GD20_LAYOUT_COMBO = SELECTORES_SAP.gd20.layout_combo
GD20_LAYOUT_GRID = SELECTORES_SAP.gd20.layout_grid
GD20_MENU_EXPORT_EXCEL = SELECTORES_SAP.gd20.menu_export_excel
GD20_EXPORT_FILENAME = SELECTORES_SAP.gd20.export_filename
GD20_EXPORT_BTN_GENERATE = SELECTORES_SAP.gd20.export_btn_generate
GD20_EXPORT_BTN_REPLACE = SELECTORES_SAP.gd20.export_btn_replace
GD20_EXIT_CONFIRM_DIALOG = SELECTORES_SAP.gd20.exit_confirm_dialog
ZBCS_OKCODE = SELECTORES_SAP.zbcs.okcode
ZBCS_FECHA_DESDE = SELECTORES_SAP.zbcs.fecha_desde
ZBCS_FECHA_HASTA = SELECTORES_SAP.zbcs.fecha_hasta
