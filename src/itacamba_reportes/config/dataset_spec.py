"""Pydantic schemas para validar YAMLs de dataset."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceSpec(BaseModel):
    """Definición de la fuente Excel de un dataset (de dónde y cómo leer)."""

    type: Literal["excel"] = "excel"
    file_pattern: str
    subdir: str | None = None
    sheet: int | str = 0
    header_row: int = 0
    metadata_rows_to_skip: int = 0
    expected_columns: int | None = None
    column_renames: dict[str, str] = Field(default_factory=dict)
    dedupe_on: list[str] = Field(default_factory=list)
    dedupe_case_insensitive: bool = False


class DtypeSpec(BaseModel):
    type: Literal["datetime", "Int64", "string", "float64"]
    dayfirst: bool = False


class TransformSpec(BaseModel):
    column: str
    op: Literal["uppercase", "lowercase", "replace", "strip"]
    map: dict[str, str] | None = None


class SapTokensSpec(BaseModel):
    null_marker: str = "#"
    unassigned: list[str] = Field(default_factory=list)


class DonacionItem(BaseModel):
    cliente_nombre: str
    label_canal: str
    label_subcanal: str | None = None


class DonacionesLookup(BaseModel):
    description: str | None = None
    last_updated: str | None = None
    items: list[DonacionItem]


class RegionesLookup(BaseModel):
    description: str | None = None
    items: list[str]


class CuentaEspecialItem(BaseModel):
    cuenta_sap: int
    tipo: str
    descripcion: str | None = None


class CuentasEspecialesLookup(BaseModel):
    description: str | None = None
    items: list[CuentaEspecialItem]


class LookupsSpec(BaseModel):
    donaciones: DonacionesLookup | None = None
    regiones_validas: RegionesLookup | None = None
    cuentas_especiales: CuentasEspecialesLookup | None = None


class ToIntModelSpec(BaseModel):
    rename: dict[str, str]
    drop: list[str] = Field(default_factory=list)


class RuleSpec(BaseModel):
    name: str
    config: str | None = None
    target_columns: list[str] = Field(default_factory=list)


class LoadSpec(BaseModel):
    table: str
    mode: Literal["upsert", "replace_all", "replace_month", "append"] = "upsert"
    unique_key: list[str] = Field(default_factory=list)


class DatasetSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset: str
    version: int = 1
    description: str | None = None

    source: SourceSpec

    rename_by_position: dict[int, str] = Field(default_factory=dict)
    dtypes: dict[str, str | DtypeSpec] = Field(default_factory=dict)

    sap_tokens: SapTokensSpec = Field(default_factory=SapTokensSpec)
    transforms: list[TransformSpec] = Field(default_factory=list)
    lookups: LookupsSpec = Field(default_factory=LookupsSpec)

    to_int_model: ToIntModelSpec | None = None
    rules: list[RuleSpec] = Field(default_factory=list)
    output_contract: str | None = None
    load: LoadSpec | None = None

    def get_lookup(self, path: str) -> Any:
        target: Any = self
        for part in path.split("."):
            target = getattr(target, part, None)
            if target is None:
                raise KeyError(f"Path '{path}' no resuelve en DatasetSpec")
        return target
