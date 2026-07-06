"""Reglas de negocio sobre CARTERA."""

from __future__ import annotations

import logging

import pandas as pd

from itacamba_reportes.transforms.common import BusinessRule
from itacamba_reportes.config.dataset_spec import (
    DonacionesLookup,
    RegionesLookup,
    SapTokensSpec,
)

logger = logging.getLogger(__name__)


class ApplyDonationsFromSpecRule(BusinessRule):
    """Replica el VBA ModificarDonaciones.

    Para cada cliente del lookup (4 nombres conocidos), si las columnas
    vendedor / coordinador estan en "Sin asignar"/"Not assigned"/null,
    las reemplaza por el label_canal del item ("DONACION" en todos los
    casos actuales).
    """

    name = "apply_donations_classification"
    COLUMN_NAME = "nombre_cliente"
    TARGET_COLUMNS: tuple[str, ...] = ("vendedor", "coordinador")

    def __init__(self, lookup: DonacionesLookup, sap_tokens: SapTokensSpec) -> None:
        self._index = {item.cliente_nombre: item for item in lookup.items}
        self._unassigned = set(sap_tokens.unassigned)
        self._null_marker = sap_tokens.null_marker

    def apply(self, df: pd.DataFrame, **_: object) -> pd.DataFrame:
        df = df.copy()
        if self.COLUMN_NAME not in df.columns:
            logger.warning("Col '%s' no existe, skip", self.COLUMN_NAME)
            return df

        is_donation = df[self.COLUMN_NAME].isin(self._index.keys())
        if not is_donation.any():
            return df

        logger.info("Clasificando %d filas como DONACION", int(is_donation.sum()))
        for target_col in self.TARGET_COLUMNS:
            df = self._apply_label(df, is_donation, target_col)
        return df

    def _apply_label(
        self,
        df: pd.DataFrame,
        is_donation: pd.Series,
        target_col: str,
    ) -> pd.DataFrame:
        if target_col not in df.columns:
            logger.warning("Col target '%s' no existe, skip", target_col)
            return df

        col_values = df[target_col]
        is_empty = (
            col_values.isna()
            | col_values.isin(self._unassigned)
            | (col_values == self._null_marker)
        )
        mask = is_donation & is_empty
        if not mask.any():
            return df

        for idx in df.index[mask]:
            item = self._index[df.loc[idx, self.COLUMN_NAME]]
            df.loc[idx, target_col] = item.label_canal

        logger.info(
            "  '%s' actualizado en %d filas (vacio -> DONACION)",
            target_col,
            int(mask.sum()),
        )
        return df


class ValidateRegionFromLookupRule(BusinessRule):

    name = "validate_region_from_lookup"
    COLUMN_NAME = "region"

    def __init__(self, lookup: RegionesLookup, *, strict: bool = False) -> None:
        self._valid = set(lookup.items)
        self._strict = strict

    def apply(self, df: pd.DataFrame, **_: object) -> pd.DataFrame:
        if self.COLUMN_NAME not in df.columns:
            logger.warning("Col '%s' no existe, skip", self.COLUMN_NAME)
            return df

        non_null = df[self.COLUMN_NAME].dropna()
        invalid = ~non_null.isin(self._valid)
        if not invalid.any():
            return df

        invalid_values = sorted(set(non_null[invalid].astype(str).unique()))
        msg = f"region: {int(invalid.sum())} filas con valores invalidos: {invalid_values}"
        if self._strict:
            raise ValueError(msg)
        logger.warning(msg)
        return df
