from __future__ import annotations

import re
from dataclasses import dataclass, field

CUENTA_BONIFICACION = 33111020
DONACION_NOMBRES = ("Cliente Donaciones", "DONACIONES DTM", "CLIENTE GENERICO SIN FACTURA", "DONACIONES COMERCIAL")
INGRESO_SIN_IVA = (("PANDO", "CIF"), ("GENERIC", "FCA"))
FACTOR_IVA = 0.87
FACTOR_M3_A_T = 1.42
FACTOR_BOLSA_A_T = 20
EMBALAJE = (("M3", "Granel M3"), ("T", "Granel t"), ("S50", "Embolsado"), ("PC", "Bolsas Vacias"))


@dataclass(frozen=True, slots=True)
class Ref:
    alias: str
    table: str
    key: str
    values: tuple[str, ...]
    numeric_key: bool = False


@dataclass(frozen=True, slots=True)
class Col:
    name: str
    excel: str
    header: str
    kind: str
    excel_formula: str
    sql: str
    stage: int = 1
    status: str = "igual"
    note: str = ""


@dataclass(frozen=True, slots=True)
class Catalog:
    refs: tuple[Ref, ...]
    cols: tuple[Col, ...]
    source_filter: str = "/* DATE_FILTER */"
    extra: dict = field(default_factory=dict)


REFS = (
    Ref("r_mat", "int_ref_material", "codigo", ("descripcion",), numeric_key=True),
    Ref("r_vend", "int_ref_equipo", "vendedor_sap", ("vendedor", "vendedor_ok", "equipo")),
    Ref("r_grp", "int_ref_equipo", "grupo_vendedores", ("equipo",)),
    Ref("r_eq", "int_ref_equipo", "equipo", ("gerencia",)),
    Ref("r_seg", "int_ref_almacen", "descripcion_sap", ("segmento",)),
    Ref("r_can", "int_ref_almacen", "segmento", ("canal",)),
    Ref("r_tipo", "int_ref_centro", "codigo_sap_cliente", ("tipo",), numeric_key=True),
    Ref("r_cen", "int_ref_centro", "centro", ("codigo_sap_cliente",)),
    Ref("r_loc", "int_ref_localidad", "localidad_despacho", ("localidad_im",)),
)


def lk(alias: str, value: str, default: str) -> str:
    return f"CASE WHEN {alias}.k IS NULL THEN {default} ELSE COALESCE(NULLIF(CAST({alias}.{value} AS NVARCHAR(500)), ''), '0') END"


def cart(alias: str, value: str, default: str = "'0'") -> str:
    return f"CASE WHEN {alias}.cliente IS NULL THEN {default} ELSE COALESCE(NULLIF(CAST({alias}.{value} AS NVARCHAR(500)), ''), '0') END"


VOLUMEN = (
    "(CASE b.unidad_medida_base "
    + " ".join(f"WHEN '{u}' THEN {f}" for u, f in (("M3", f"(b.cantidad * -1) * {FACTOR_M3_A_T}"), ("T", "b.cantidad * -1"), ("S50", f"(b.cantidad * -1) / {FACTOR_BOLSA_A_T}.0")))
    + f" ELSE 0 END) * (CASE WHEN b.numero_cuenta = {CUENTA_BONIFICACION} THEN -1 ELSE 1 END)"
)

COLS = (
    Col("tipo_embalaje", "AX", "TIPO DE EMBALAJE", "regla", 'IF(L2="M3","Granel M3",IF(L2="T","Granel t",IF(L2="S50","Embolsado",IF(L2="PC","Bolsas Vacias","0"))))',
        "CASE b.unidad_medida_base " + " ".join(f"WHEN '{u}' THEN '{t}'" for u, t in EMBALAJE) + " ELSE '0' END"),
    Col("nombre_producto", "AY", "NOMBRE DE PRODUCTO", "cruce", "IFERROR(VLOOKUP(K2*1,REFERENCIAS!L:M,2,0),0)", lk("r_mat", "v1", "'0'")),
    Col("volumen_toneladas", "AZ", "VOLUMEN TONELADAS", "regla+macro", 'IF(AX2="Granel M3",(AD2*-1)*1.42,IF(AX2="Granel t",AD2*-1,IF(AX2="Embolsado",(AD2*-1)/20,0))) + macro CambiarSignoVolumen', VOLUMEN,
        status="corregido", note="CambiarSignoVolumen: la cuenta 33111020 invierte el signo"),
    Col("nombre_pagador", "BA", "NOMBRE PAGADOR", "cruce", "IFERROR(VLOOKUP(R2*1,'CARTERA CATASTRO'!A:B,2,0),0)", cart("c_pag", "nombre_cliente")),
    Col("nombre_solicitante", "BB", "NOMBRE SOLICITANTE", "cruce+macro", "IFERROR(VLOOKUP(S2*1,'CARTERA CATASTRO'!A:B,2,0),0)  (S reemplazado por DPTO_0)", cart("c_sol", "nombre_cliente"), status="corregido"),
    Col("vendedor_sap", "BC", "VENDEDOR SAP", "cruce+macro", "IFERROR(VLOOKUP(U2*1,'CARTERA CATASTRO'!A:AG,33,0),0)", cart("c_dst", "vendedor"), status="corregido"),
    Col("nombre_destinatario", "BY", "NOMBRE DESTINATARIO", "cruce+macro", "IFERROR(VLOOKUP(U2*1,'CARTERA CATASTRO'!A:D,2,0),0)", cart("c_dst", "nombre_cliente"), status="corregido"),
    Col("localidad", "BN", "LOCALIDAD", "cruce+macro", "IFERROR(VLOOKUP(U2*1,'CARTERA CATASTRO'!A:D,4,0),0)", cart("c_dst", "poblacion"), status="corregido"),
    Col("provincia", "BO", "PROVINCIA", "cruce+macro", "IFERROR(VLOOKUP(U2*1,'CARTERA CATASTRO'!A:G,7,0),[Población SAP])", cart("c_dst", "attribute_6", "b.poblacion"), status="corregido"),
    Col("dpto", "BP", "DPTO", "cruce+macro", "IFERROR(VLOOKUP(U2*1,'CARTERA CATASTRO'!A:I,9,0),0)", cart("c_dst", "region_nombre"), status="corregido"),
    Col("sub_canal_key", "-", "(intermedia)", "cruce", "VLOOKUP(U2,'CARTERA CATASTRO'!A:C,3,0)", "c_dst.attribute_10"),
    Col("tipo_venta", "BM", "TIPO DE VENTA", "cruce", 'IFERROR(VLOOKUP(R2*1,REFERENCIAS!I:J,2,FALSE),"VENTA DIRECTA")', lk("r_tipo", "v1", "'VENTA DIRECTA'")),
    Col("dpto_pagador", "BS", "DPTO PAGADOR", "cruce", "IFERROR(VLOOKUP(R2*1,'CARTERA CATASTRO'!A:I,9,0),0)", cart("c_pag", "region_nombre")),
    Col("localidad_pagador", "BT", "LOCALIDAD PAGADOR", "cruce", "IFERROR(VLOOKUP(R2,'CARTERA CATASTRO'!A:D,4,0),0)", cart("c_pag", "poblacion")),
    Col("codigo_cliente", "BU", "CÓDIGO CLIENTE", "cruce", "IFERROR(VLOOKUP(D2,REFERENCIAS!H:I,2,0),R2)",
        "CASE WHEN r_cen.k IS NULL THEN b.cliente ELSE COALESCE(r_cen.v1, 0) END", status="decision",
        note="El Excel da 0 si el centro existe sin código (527 filas en oct); confirmar si se replica o se usa el pagador"),
    Col("dia", "BJ", "DIA", "regla", "DAY(AF2)", "DAY(b.fe_contabilizacion)"),
    Col("mes", "BK", "MES", "regla", "MONTH(AF2)", "MONTH(b.fe_contabilizacion)"),
    Col("anio", "BL", "AÑO", "regla", "YEAR(AF2)", "YEAR(b.fe_contabilizacion)"),
    Col("bonificaciones", "BV", "BONIFICACIONES", "regla+macro", '+IF(I2=33111020,AZ2,"")', f"CASE WHEN b.numero_cuenta = {CUENTA_BONIFICACION} THEN {VOLUMEN} END", status="corregido",
        note="Vacía (NULL) fuera de la cuenta; VENTAS BI la pasa a 0"),
    Col("centro_distribucion", "BW", "CENTRO DE DISTRIBUCIÓN", "cruce", 'IFERROR(VLOOKUP(R2,QUERY!BS:BZ,7,0),"OTROS")', "'OTROS'", status="decision",
        note="Regla rota en el Excel (QUERY termina en AN): definir con el área"),
    Col("zona_entrega", "BX", "ZONA DE ENTREGA", "cruce", 'IFERROR(VLOOKUP(R2,QUERY!BS:CA,8,0),"OTROS")', "'OTROS'", status="decision",
        note="Regla rota en el Excel: definir con el área"),
    Col("vendedor", "BD", "VENDEDOR", "cruce", "IFERROR(VLOOKUP(BC2,REFERENCIAS!O:S,2,0),0)", lk("r_vend", "v1", "'0'"), stage=2),
    Col("vendedor_ok", "BE", "VENDEDOR OK", "cruce", "IFERROR(VLOOKUP(BC2,REFERENCIAS!O:S,3,0),0)", lk("r_vend", "v2", "'0'"), stage=2),
    Col("equipo", "BG", "EQUIPO", "regla+cruce", 'IF(NOT(ISERROR(FIND("CEMENTO",AY2))),IFERROR(VLOOKUP(BC2,REFERENCIAS!O:S,4,0),0),IFERROR(VLOOKUP(Q2,REFERENCIAS!N:S,5,0),"No encontrado"))',
        "CASE WHEN {contains_cemento} THEN " + lk("r_vend", "v3", "'0'") + " ELSE " + lk("r_grp", "v1", "'No encontrado'") + " END", stage=2,
        note="FIND distingue mayúsculas; se usa primera coincidencia (no MIN)"),
    Col("sub_canal", "BI", "SUB CANAL", "cruce", "IFERROR(VLOOKUP(VLOOKUP(U2,'CARTERA CATASTRO'!A:C,3,0),REFERENCIAS!D:E,2,0),\"OTROS\")", lk("r_seg", "v1", "'OTROS'"), stage=2),
    Col("region_m", "BQ", "REGION M", "regla+cruce", 'IFERROR(IF(BP2="Santa Cruz",VLOOKUP(BN2,REFERENCIAS!A:B,2,0),BP2),0)', "CASE WHEN UPPER(s1.dpto) = 'SANTA CRUZ' THEN " + lk("r_loc", "v1", "'0'") + " ELSE s1.dpto END", stage=2),
    Col("ingreso_bruto", "BR", "INGRESO BRUTO", "regla+macro", 'IF(OR(AND(BP2="Pando",AQ2="CIF"),AND(BP2="GENERIC",AQ2="FCA")),AE2*-1,(AE2/0.87)*-1)  (AE vaciada por EliminarMonedaSociedad)',
        f"CASE WHEN b.numero_cuenta = {CUENTA_BONIFICACION} THEN 0 WHEN " + " OR ".join(f"(UPPER(s1.dpto) = '{d}' AND UPPER(b.incoterms) = '{i}')" for d, i in INGRESO_SIN_IVA) + f" THEN b.moneda_sociedad * -1 ELSE (b.moneda_sociedad / {FACTOR_IVA}) * -1 END",
        stage=2, status="corregido", note="Usa el DPTO ya resuelto por DPTO_0"),
    Col("gerencia", "BF", "GERENCIA", "cruce", "IFERROR(VLOOKUP(BG2,REFERENCIAS!R:S,2,0),0)", lk("r_eq", "v1", "'0'"), stage=3),
    Col("canal", "BH", "CANAL", "cruce", 'IFERROR(VLOOKUP(BI2,REFERENCIAS!E:F,2,0),"OTROS")', lk("r_can", "v1", "'OTROS'"), stage=3),
)

STAGE_JOINS = {
    1: (("r_mat", "b.material"), ("r_tipo", "b.cliente"), ("r_cen", "b.centro")),
    2: (("r_vend", "s1.vendedor_sap"), ("r_grp", "b.grupo_vendedores"), ("r_seg", "s1.sub_canal_key"), ("r_loc", "s1.localidad")),
    3: (("r_eq", "s2.equipo"), ("r_can", "s2.sub_canal")),
}

CATALOG = Catalog(REFS, COLS)

SAP_COLUMNS = (
    "ejercicio", "sociedad", "organizacion_ventas", "centro", "division", "oficina_ventas", "canal_distribucion", "sector",
    "numero_cuenta", "centro_beneficio", "material", "unidad_medida_base", "periodo_contable", "clave_pais_region", "region",
    "poblacion", "grupo_vendedores", "cliente", "emisor_orden", "customer_bill_to", "customer_rebate", "grupo_clientes_2",
    "atributo_6", "atributo_7", "atributo_10", "clase_factura", "nombre_usuario", "texto", "numero_documento", "cantidad",
    "moneda_sociedad", "fe_contabilizacion", "fecha_entrada", "fecha_valor", "documento_comercial", "hora_entrada",
    "moneda_transaccion", "clave_moneda_transaccion", "moneda_fuerte", "clave_moneda_fuerte", "numero_doc_referencia",
    "numero_documento_2", "incoterms", "incoterms_parte_2", "clase_documento", "cond_pago", "dias_1", "numero_transporte", "e",
)

INT_RENAMES = {"clave_pais_region": "clave_pais", "region": "region_sap", "poblacion": "poblacion_sap", "cliente": "pagador", "emisor_orden": "emisor_solicitante", "customer_rebate": "destinatario"}


def contains_cemento(dialect: str) -> str:
    if dialect == "mssql":
        return "CHARINDEX('CEMENTO', COALESCE(s1.nombre_producto, '') COLLATE Latin1_General_CS_AS) > 0"
    return "strpos(COALESCE(s1.nombre_producto, ''), 'CEMENTO') > 0"


def ref_cte(ref: Ref) -> str:
    vals = ", ".join(f"{v} AS v{i + 1}" for i, v in enumerate(ref.values))
    key = ref.key if ref.numeric_key else f"UPPER(LTRIM(RTRIM({ref.key})))"
    where = f"{ref.key} IS NOT NULL" + ("" if not ref.numeric_key else f" AND {ref.key} <> 0") + ("" if ref.numeric_key else f" AND {ref.key} <> ''")
    return (f"{ref.alias} AS (SELECT k, {', '.join(f'v{i + 1}' for i in range(len(ref.values)))} FROM ("
            f"SELECT {key} AS k, {vals}, ROW_NUMBER() OVER (PARTITION BY {key} ORDER BY id) AS rn FROM {ref.table} WHERE {where}) x WHERE rn = 1)")


def join(alias: str, expr: str, numeric: bool) -> str:
    on = f"{alias}.k = {expr}" if numeric else f"{alias}.k = UPPER(LTRIM(RTRIM(CAST({expr} AS NVARCHAR(500)))))"
    return f"LEFT JOIN {alias} ON {on}"


def render(dialect: str = "mssql", date_filter: str = "/* DATE_FILTER */") -> str:
    refs = {r.alias: r for r in CATALOG.refs}
    ctes = [ref_cte(r) for r in CATALOG.refs]
    flag = f"(c0.cliente IS NULL OR COALESCE(NULLIF(c0.region_nombre, ''), '0') = '0')"
    ctes.append(
        "b AS (SELECT g.*, "
        f"CASE WHEN {flag} THEN g.cliente ELSE g.customer_rebate END AS dest_ef, "
        f"CASE WHEN {flag} THEN g.cliente ELSE g.emisor_orden END AS sol_ef, "
        f"CASE WHEN {flag} THEN g.cliente ELSE g.customer_bill_to END AS bill_ef "
        f"FROM stg_gd20 g LEFT JOIN int_cartera c0 ON c0.cliente = g.customer_rebate {date_filter})"
    )
    for stage in (1, 2, 3):
        cols = [c for c in CATALOG.cols if c.stage == stage]
        prev = "b" if stage == 1 else f"s{stage - 1}"
        rebase = (lambda x: x) if stage == 1 else (lambda x: re.sub(r"\bb\.", f"{prev}.", x))
        select = ", ".join(f"{rebase(c.sql.replace('{contains_cemento}', contains_cemento(dialect)))} AS {c.name}" for c in cols)
        joins = " ".join(join(a, rebase(e), refs[a].numeric_key) for a, e in STAGE_JOINS[stage])
        if stage == 1:
            joins = ("LEFT JOIN int_cartera c_pag ON c_pag.cliente = b.cliente "
                     "LEFT JOIN int_cartera c_sol ON c_sol.cliente = b.sol_ef "
                     "LEFT JOIN int_cartera c_dst ON c_dst.cliente = b.dest_ef " + joins)
            ctes.append(f"s1 AS (SELECT b.*, {select} FROM b {joins})")
        else:
            ctes.append(f"s{stage} AS (SELECT {prev}.*, {select} FROM {prev} {joins})")
    sap = []
    for c in SAP_COLUMNS:
        src = {"emisor_orden": "s3.sol_ef", "customer_bill_to": "s3.bill_ef", "customer_rebate": "s3.dest_ef"}.get(c, f"s3.{c}")
        if c == "moneda_sociedad":
            src = f"CASE WHEN s3.numero_cuenta = {CUENTA_BONIFICACION} THEN NULL ELSE s3.moneda_sociedad END"
        sap.append((INT_RENAMES.get(c, c), src))
    calc = [(c.name, f"s3.{c.name}") for c in CATALOG.cols if c.name != "sub_canal_key"]
    targets = ", ".join(n for n, _ in sap + calc)
    values = ", ".join(e for _, e in sap + calc)
    body = ",\n".join(ctes)
    return f"TRUNCATE TABLE [int_gd20];\nWITH {body}\nINSERT INTO [int_gd20] ({targets})\nSELECT {values} FROM s3" if dialect == "mssql" else \
        f"DELETE FROM int_gd20;\nINSERT INTO int_gd20 ({targets})\nWITH {body}\nSELECT {values} FROM s3"
