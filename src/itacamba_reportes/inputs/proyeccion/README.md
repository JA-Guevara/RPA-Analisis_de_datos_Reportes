# Slice de Entrada: PROYECCION-SEMANAL.xlsx

## Descripción
Lee las metas de venta comercial y proyecciones semanales entregadas por el área comercial (`RF` mensual y `RF AJUSTADO` semanal).

## Origen
- **Archivo**: `PROYECCION-SEMANAL.xlsx`
- **Hoja**: Detectada dinámicamente con el patrón `^RF AJUSTADO SEMANAL` (ej. `.26` o `OCT 24`).
- **Limpieza**: Códigos de cliente no numéricos se limpian a `0` para consistencia.
- **Destino**: `stg_proyeccion`.

## Uso en Salidas
Se combina mediante unión vertical (`UNION ALL`) en `outputs/despacho_mes` para contrastar el despacho real ejecutado hasta ayer con la proyección de RF ajustado hacia fin de mes.
