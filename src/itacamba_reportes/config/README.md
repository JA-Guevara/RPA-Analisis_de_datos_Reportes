# config

Configuración técnica del runtime: variables de entorno, fuentes de datos parametrizables, settings de logging y mail.

## Qué va aquí

- `env_config.py` — `EnvConfig`: lee `.env` y expone `DB_SERVER`, `DB_USER`, `DB_PASSWORD`, `DATA_PATH`, `LOG_LEVEL`. Validado con `pydantic-settings`.
- `data_sources.py` — instancias concretas de `ExcelSource` (CARTERA_SOURCE, GD20_SOURCE, REFERENCIAS_SOURCE) que combinan el catálogo de dominio con `${DATA_PATH}`.
- `settings.py` (si existe) — settings transversales (timezone, locale, etc.).
- `logging.py`, `mail_config.py` — configuración de telemetría y notificaciones.

## Qué NO va

- Constantes del negocio: van en `domain/constants/`.
- Lógica que dependa de los valores cargados: usa el config, pero vive en su propia capa.

## Ejemplo

```python
# config/env_config.py
from pydantic_settings import BaseSettings


class EnvConfig(BaseSettings):
    DB_SERVER: str
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str = "Reportes_Itacamba"
    DB_PORT: int = 1433
    DATA_PATH: Path
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"


# config/data_sources.py
env = EnvConfig()
CARTERA_SOURCE = ExcelSource(
    name="cartera",
    path_template=str(env.DATA_PATH / "dinamicos" / "CARTERA*.xlsx"),
    sheet=0,
    metadata_rows_to_skip=6,
)
```

## Regla mental

Si el valor cambia entre entornos (DEV, STAGING, PROD), va al `.env` y se expone vía `EnvConfig`. Si es parte del negocio "para Itacamba", va a `domain/constants/`.

> Pendiente de seguridad: rotar `DB_PASSWORD`, crear `.env.example` sin secrets, mover credenciales a un secret manager.
