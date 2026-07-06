"""Diff de calibración: hojas del libro del cliente vs lo generado.

Compara las hojas DESPACHOS BI / DESPACHO_MES del basepanel (o libro
equivalente) contra los .pkl producidos por simular_despacho.py (o
contra un export del bot), columna por columna:

    % paridad, nº de mismatches y ejemplos lado a lado.

Uso:
    python tools/calibracion/diff_contra_libro.py LIBRO.xlsx
        [--sim CARPETA_PKL] [--hoja-bi "DESPACHOS BI"]
        [--hoja-mes "DESPACHO_MES"] [--reporte salida.xlsx]

El mapeo header_cliente -> col_generada vive en HEADER_MAP_* (ajustar
ahí si el cliente renombra columnas).
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ─────────────────────────────────────────────────────────────────────
# Mapeo headers del libro cliente -> columnas generadas (int_despacho_bi)
# Claves en forma normalizada (minúsculas, sin acentos).
# ─────────────────────────────────────────────────────────────────────
HEADER_MAP_BI: dict[str, str] = {
    "centro proveedor": "centro_proveedor",
    "sucursal": "sucursal",
    "material": "material",
    "producto": "nombre_material",
    "dia natural": "dia_natural",
    "documento venta": "documento_venta",
    "destinatario mcia.": "destinatario_mcia",
    "nombre del centro destinatario": "nombre_centro_destinatario",
    "poblacion": "poblacion",
    "incoterms": "incoterms",
    "clase doc.ventas": "clase_doc_ventas",
    "tipo de venta": "tipo_venta",
    "centro receptor": "centro_receptor",
    "nombre del centro receptor": "nombre_centro_receptor",
    "clase de expedicion": "clase_expedicion",
    "vc - embalaje": "vc_embalaje",
    "transportista": "transportista",
    "nombre del transportista": "nombre_transportista",
    "ruta": "ruta",
    "nombre de la ruta": "nombre_ruta",
    "distancia": "distancia",
    "cantidad": "cantidad",
    "fecha": "fecha",
    "despacho(t)": "despacho_t",
    "departamento": "departamento",
    "traslados (t)": "traslados_t",
    "dia": "dia",
    "mes": "mes",
    "ano": "anio",
    "grupo de producto": "grupo_producto",
    "tipo de traslado": "tipo_traslado",
    "producto.1": "producto",
    "centro de distribucion": "centro_distribucion",
    "provincia": "provincia",
    "semana ano": "semana_anio",
    "zona de descarga": "zona_descarga",
    "cd": "cd",
    "localidad": "localidad",
    "tipo de venta2": "tipo_venta_2",
    # ── enriquecidas (formulas del cliente) ──
    "codigo cliente": "codigo_cliente",
    "vendedor": "vendedor_cartera",
    "desarrollador": "desarrollador",
    "equipo": "equipo",
    "localidad im": "localidad_im",
    "incoterms im": "incoterms_im",
    "gerencia": "gerencia",
    "semana": "semana",
    "x": "x",
}

HEADER_MAP_MES: dict[str, str] = {
    "gerencia": "gerencia",
    "equipo": "equipo",
    "departamento": "departamento",
    "localidad": "localidad",
    "centro de distribucion": "centro_distribucion",
    "producto": "producto",
    "incoterms": "incoterms",
    "fecha": "fecha",
    "mes": "mes",
    "dia": "dia",
    "codigo cliente": "codigo_cliente",
    "rf": "rf",
    "despacho(t)": "despacho_t",
    "rf ajustado _ im": "rf_ajustado_im",
    "proyeccion": "proyeccion",
    "nombre cliente": "nombre_cliente",
    "vendedor": "vendedor",
    "tipo de venta": "tipo_venta",
    "canal": "canal",
    "semana2": "semana2",
}

KEYS_BI: list[tuple[str, str]] = [
    ("documento venta", "documento_venta"),
    ("material", "material"),
    ("dia", "dia"),
    ("cantidad", "cantidad"),
]

KEYS_MES: list[tuple[str, str]] = [
    ("codigo cliente", "codigo_cliente"),
    ("producto", "producto"),
    ("dia", "dia"),
    ("centro de distribucion", "centro_distribucion"),
    ("incoterms", "incoterms"),
]


def norm_header(h: object) -> str:
    s = str(h).strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


_DATE_RE = r"^\d{1,2}/\d{1,2}/\d{4}( 0?0:00(:00)?)?$"


def norm_cell(v: object):
    """Normaliza para comparar: strings trim/upper-colapsados, números a
    4 decimales, fechas (Timestamp o 'dd/mm/yyyy') a ISO-date."""
    if pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.normalize().date().isoformat()
    if isinstance(v, (int, float)):
        return round(float(v), 4)
    s = str(v).strip()
    if s == "":
        return None
    import re
    if re.match(_DATE_RE, s):
        ts = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if not pd.isna(ts):
            return ts.normalize().date().isoformat()
    try:
        return round(float(s.replace(",", ".")), 4)
    except ValueError:
        return " ".join(s.upper().split())


def compare(cli: pd.DataFrame, gen: pd.DataFrame, header_map: dict[str, str],
            key_pairs: list[tuple[str, str]], label: str,
            max_examples: int = 4) -> pd.DataFrame:
    cli = cli.copy()
    cli.columns = [norm_header(c) for c in cli.columns]
    gen = gen.copy()

    faltan_cli = [c for c, _ in key_pairs if c not in cli.columns]
    faltan_gen = [g for _, g in key_pairs if g not in gen.columns]
    if faltan_cli or faltan_gen:
        raise SystemExit(
            f"[{label}] llaves ausentes: cliente={faltan_cli} generado={faltan_gen}\n"
            f"Headers cliente: {list(cli.columns)}"
        )

    def make_key(df: pd.DataFrame, cols: list[str]) -> pd.Series:
        parts = [df[c].map(norm_cell).astype(str) for c in cols]
        key = parts[0]
        for p in parts[1:]:
            key = key + "||" + p
        return key

    cli["_k"] = make_key(cli, [c for c, _ in key_pairs])
    gen["_k"] = make_key(gen, [g for _, g in key_pairs])
    cli["_k"] += "#" + cli.groupby("_k").cumcount().astype(str)
    gen["_k"] += "#" + gen.groupby("_k").cumcount().astype(str)

    m = cli.merge(gen, on="_k", how="outer", suffixes=("_cli", "_gen"),
                  indicator=True)
    n_both = int((m["_merge"] == "both").sum())
    print(f"\n{'=' * 74}\n[{label}] cliente={len(cli)}  generado={len(gen)}  "
          f"alineadas={n_both}  solo_cliente={int((m['_merge'] == 'left_only').sum())}  "
          f"solo_generado={int((m['_merge'] == 'right_only').sum())}")

    both = m[m["_merge"] == "both"]
    results = []
    for cli_col, gen_col in header_map.items():
        cc = f"{cli_col}_cli" if f"{cli_col}_cli" in both.columns else cli_col
        gc = f"{gen_col}_gen" if f"{gen_col}_gen" in both.columns else gen_col
        if cc not in both.columns:
            results.append((cli_col, gen_col, None, None, "NO ESTA EN LIBRO"))
            continue
        if gc not in both.columns:
            results.append((cli_col, gen_col, None, None, "NO ESTA EN GENERADO"))
            continue
        a = both[cc].map(norm_cell)
        b = both[gc].map(norm_cell)
        eq = (a == b) | (a.isna() & b.isna())
        pct = 100.0 * eq.sum() / len(both) if len(both) else 0.0
        ejemplos = ""
        if pct < 100.0:
            bad = both.loc[~eq, [cc, gc]].head(max_examples)
            ejemplos = "; ".join(
                f"cli={r[cc]!r} gen={r[gc]!r}" for _, r in bad.iterrows()
            )
        results.append(
            (cli_col, gen_col, round(pct, 2), int((~eq).sum()), ejemplos))

    rep = pd.DataFrame(
        results,
        columns=["col_cliente", "col_generada", "pct_match", "n_mismatch",
                 "ejemplos"],
    ).sort_values(["pct_match"], na_position="first")
    with pd.option_context("display.max_colwidth", 80, "display.width", 220):
        print(rep.to_string(index=False))
    return rep


def pick_sheet(xl: pd.ExcelFile, wanted: str) -> str | None:
    objetivo = norm_header(wanted)
    for s in xl.sheet_names:
        if norm_header(s) == objetivo:
            return s
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("libro", type=Path, help="Libro del cliente (.xlsx/.xlsm)")
    parser.add_argument("--sim", type=Path,
                        default=PROJECT_ROOT / "storage" / "calibracion",
                        help="Carpeta con los .pkl de simular_despacho.py")
    parser.add_argument("--hoja-bi", default="DESPACHOS BI")
    parser.add_argument("--hoja-mes", default="DESPACHO_MES")
    parser.add_argument("--reporte", type=Path, default=None,
                        help="Ruta .xlsx para volcar el reporte del diff")
    args = parser.parse_args()

    xl = pd.ExcelFile(args.libro)
    print("Hojas del libro:", xl.sheet_names)
    reportes: dict[str, pd.DataFrame] = {}

    hoja_bi = pick_sheet(xl, args.hoja_bi)
    if hoja_bi:
        cli_bi = xl.parse(hoja_bi)
        gen_bi = pd.read_pickle(args.sim / "int_despacho_bi.pkl")
        reportes["DESPACHOS_BI"] = compare(
            cli_bi, gen_bi, HEADER_MAP_BI, KEYS_BI, f"{hoja_bi} vs int_despacho_bi")
    else:
        print(f"AVISO: hoja '{args.hoja_bi}' no encontrada en el libro")

    hoja_mes = pick_sheet(xl, args.hoja_mes)
    if hoja_mes:
        cli_mes = xl.parse(hoja_mes)
        gen_mes = pd.read_pickle(args.sim / "int_despacho_mes.pkl")
        reportes["DESPACHO_MES"] = compare(
            cli_mes, gen_mes, HEADER_MAP_MES, KEYS_MES,
            f"{hoja_mes} vs int_despacho_mes")
    else:
        print(f"AVISO: hoja '{args.hoja_mes}' no encontrada en el libro")

    if args.reporte and reportes:
        with pd.ExcelWriter(args.reporte, engine="openpyxl") as writer:
            for name, rep in reportes.items():
                rep.to_excel(writer, sheet_name=name, index=False)
        print(f"\nReporte del diff -> {args.reporte}")

    if not reportes:
        sys.exit(1)


if __name__ == "__main__":
    main()
