"""GD20 Business Rules — calculos puros + reglas VBA/Power Query."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


_HARDCODED_CONSTANTS: dict[str, float | int] = {
    "numero_cuenta_bonificacion": 33111020,
    "codigo_cliente_invalido":    0,
    "factor_ingreso_bruto":       0.87,
    "factor_volumen_granel_m3":   1.42,
    "factor_volumen_embolsado":   20,
}


@dataclass(slots=True)
class Gd20BusinessRulesUseCase:

    config: dict | None = None

    def _const(self, key: str):
        if self.config is None:
            return _HARDCODED_CONSTANTS[key]
        return self.config.get("constants", {}).get(key, _HARDCODED_CONSTANTS[key])

    def execute(self, df: pd.DataFrame) -> pd.DataFrame:
        df = self._calc_tipo_embalaje(df)
        df = self._calc_ingreso_bruto(df)
        df = self._calc_dates(df)
        df = self._calc_volumen_y_bonificaciones(df)
        # NOTA: _calc_region_m REMOVIDO. REGION M ahora la calcula
        # Gd20NormalizeUseCase._lookup_localidad usando int_ref_localidad.
        df = self._rule_bonificacion_cleanup(df)
        # NOTA: _rule_codigo_cliente_zero_fill DESACTIVADO por default.
        # Pisaba los IDs numericos (destinatario, customer_bill_to,
        # emisor_solicitante) con el valor de pagador cuando
        # codigo_cliente=0. Validado contra BASE PANEL del Excel:
        # BP NO aplica esta sobreescritura sobre los IDs. Resultaba en
        # 171 filas con destinatario incorrecto (= pagador en vez del
        # rebate real del raw SAP).
        # El metodo sigue disponible si en el futuro se necesita activarlo
        # via gd20.yaml con target_cols especificas (ej: solo nombres).
        df = self._rule_post_replaces(df)
        return df

    @staticmethod
    def _calc_region_m(df: pd.DataFrame) -> pd.DataFrame:
        """REGION M = DPTO (version simplificada).

        En Excel original: si DPTO == "Santa Cruz", lookup LOCALIDAD en
        REFERENCIAS!A:B (LOCALIDAD IM); else DPTO. Hasta cargar tabla de
        localidades, usamos DPTO directo.
        """
        if "dpto" in df.columns:
            df["region_m"] = df["dpto"].astype("string")
        else:
            df["region_m"] = "0"
        return df

    @staticmethod
    def _calc_tipo_embalaje(df: pd.DataFrame) -> pd.DataFrame:
        umb = df["unidad_medida_base"].astype("string")
        df["tipo_embalaje"] = pd.Series("0", index=df.index, dtype="string")
        df.loc[umb == "M3",  "tipo_embalaje"] = "Granel M3"
        df.loc[umb == "T",   "tipo_embalaje"] = "Granel t"
        df.loc[umb == "S50", "tipo_embalaje"] = "Embolsado"
        df.loc[umb == "PC",  "tipo_embalaje"] = "Bolsas Vacias"
        return df

    def _calc_ingreso_bruto(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula ingreso_bruto replicando la formula EXACTA del Excel cliente:

            =SI( O( Y(DPTO_PAGADOR='Pando'; INCOTERMS='CIF');
                    Y(DPTO_PAGADOR='GENERIC'; INCOTERMS='FCA') );
                 moneda_sociedad * -1;
                 (moneda_sociedad / 0.87) * -1 )

        Es decir:
        - Si (dpto_pagador='Pando' AND incoterms='CIF') OR
             (dpto_pagador='GENERIC' AND incoterms='FCA')
          → moneda_sociedad * -1   (SIN dividir por 0.87, son exportaciones
            o ventas a Pando CIF donde el monto ya viene neto)
        - SINO → (moneda_sociedad / 0.87) * -1   (default, descuenta IVA)

        Validado vs BASE PANEL mayo 2026: 0 filas mismatch (1995/1995).
        """
        factor = float(self._const("factor_ingreso_bruto"))
        moneda = pd.to_numeric(df["moneda_sociedad"], errors="coerce")

        # Default: divide por factor e invierte signo
        df["ingreso_bruto"] = moneda / factor * -1

        # Excepcion: dpto_pagador+incoterms especificos → sin factor
        if "dpto_pagador" in df.columns and "incoterms" in df.columns:
            dpto = df["dpto_pagador"].astype("string").str.strip().str.upper()
            inco = df["incoterms"].astype("string").str.strip().str.upper()
            cond_pando = (dpto == "PANDO") & (inco == "CIF")
            cond_generic = (dpto == "GENERIC") & (inco == "FCA")
            mask = cond_pando | cond_generic
            n = int(mask.sum())
            if n > 0:
                df.loc[mask, "ingreso_bruto"] = moneda.loc[mask] * -1
                logger.info(
                    "Rule ingreso_bruto sin factor: %d filas "
                    "(Pando+CIF=%d, GENERIC+FCA=%d)",
                    n, int(cond_pando.sum()), int(cond_generic.sum()),
                )
        return df

    @staticmethod
    def _calc_dates(df: pd.DataFrame) -> pd.DataFrame:
        fe = pd.to_datetime(df["fe_contabilizacion"], errors="coerce")
        df["dia"]  = fe.dt.day.astype("Int64")
        df["mes"]  = fe.dt.month.astype("Int64")
        df["anio"] = fe.dt.year.astype("Int64")
        return df

    def _calc_volumen_y_bonificaciones(self, df: pd.DataFrame) -> pd.DataFrame:
        cantidad = pd.to_numeric(df["cantidad"], errors="coerce")
        emb = df["tipo_embalaje"].astype("string")
        f_m3 = float(self._const("factor_volumen_granel_m3"))
        f_emb = float(self._const("factor_volumen_embolsado"))

        vol = pd.Series(0.0, index=df.index, dtype="float64")
        vol.loc[emb == "Granel M3"] = (cantidad * -1) * f_m3
        vol.loc[emb == "Granel t"]  = cantidad * -1
        vol.loc[emb == "Embolsado"] = (cantidad * -1) / f_emb
        df["volumen_toneladas"] = vol

        bonif_account = int(self._const("numero_cuenta_bonificacion"))
        nc = pd.to_numeric(df["numero_cuenta"], errors="coerce")
        df["bonificaciones"] = vol.where(nc == bonif_account, other=pd.NA)
        return df

    def _rule_bonificacion_cleanup(self, df: pd.DataFrame) -> pd.DataFrame:
        rule = (self.config or {}).get("bonificacion_cleanup", {})
        if rule and not rule.get("enabled", True):
            return df
        if "numero_cuenta" not in df.columns:
            logger.warning("Rule bonificacion_cleanup skipped: falta col 'numero_cuenta'")
            return df

        bonif_account = int(self._const("numero_cuenta_bonificacion"))
        nc = pd.to_numeric(df["numero_cuenta"], errors="coerce")
        is_bonif = nc == bonif_account
        n = int(is_bonif.sum())
        if n == 0:
            return df

        if "moneda_sociedad" in df.columns:
            df.loc[is_bonif, "moneda_sociedad"] = None
        if "volumen_toneladas" in df.columns:
            vol = pd.to_numeric(df["volumen_toneladas"], errors="coerce")
            df.loc[is_bonif, "volumen_toneladas"] = -vol.loc[is_bonif]
        logger.info("Rule bonificacion_cleanup: %d filas (moneda=NULL, vol invertido)", n)
        return df

    def _rule_codigo_cliente_zero_fill(self, df: pd.DataFrame) -> pd.DataFrame:
        rule = (self.config or {}).get("codigo_cliente_zero_fill", {})
        if rule and not rule.get("enabled", True):
            return df
        if "codigo_cliente" not in df.columns:
            logger.warning("Rule codigo_cliente_zero_fill skipped: falta col 'codigo_cliente'")
            return df

        invalido = int(self._const("codigo_cliente_invalido"))
        cc = pd.to_numeric(df["codigo_cliente"], errors="coerce")
        is_zero = cc == invalido
        n = int(is_zero.sum())
        if n == 0:
            return df

        target_cols = (rule.get("fill_columns")
                       or ["emisor_solicitante", "customer_bill_to", "destinatario"])
        fill_from = rule.get("fill_from") or "pagador"
        if fill_from not in df.columns:
            logger.warning("Rule codigo_cliente_zero_fill skipped: falta col '%s'", fill_from)
            return df

        for col in target_cols:
            if col in df.columns:
                df.loc[is_zero, col] = df.loc[is_zero, fill_from]
        logger.info("Rule codigo_cliente_zero_fill: %d filas (cols %s <- %s)",
                    n, target_cols, fill_from)
        return df

    def _rule_post_replaces(self, df: pd.DataFrame) -> pd.DataFrame:
        replaces = (self.config or {}).get("post_replaces", {})
        if not replaces:
            # NOTA: removidos GENERIC→EXPORTACION en dpto/region_m/dpto_pagador.
            # Validado contra BASE PANEL del cliente (1995 filas mayo 2026):
            # el cliente DEJA 'GENERIC' literal en esos campos. Aplicar el
            # replace generaba 18 filas mismatch (todas Z4RF exportación).
            # tipo_venta AGENCIA→VENTA INDIRECTA se mantiene (validado OK).
            replaces = {
                "tipo_venta":   {"AGENCIA": "VENTA INDIRECTA"},
            }

        applied = []
        for col, mapping in replaces.items():
            if col not in df.columns:
                continue
            series = df[col].astype("string")
            for old, new in mapping.items():
                series = series.str.replace(old, new, regex=False)
            df[col] = series
            applied.append(col)
        if applied:
            logger.info("Rule post_replaces: aplicado en cols %s", applied)
        return df
