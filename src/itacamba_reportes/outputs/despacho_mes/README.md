# Slice de Salida: DESPACHO MES (Resumen Mensual + Proyección)

## Descripción
Resumen ejecutivo de ventas y despachos del **mes en curso**. Combina el despacho real ejecutado día a día con la proyección de cierre comercial (`RF` y `RF AJUSTADO`).

## Unión Vertical (`UNION ALL`)
En lugar de cruzar por llaves foráneas complejas, apila:
1. **Despacho Real**: Filas ejecutadas de `int_query` hasta el día de ayer.
2. **Proyección Comercial**: Filas de `stg_proyeccion` (RF Ajustado Semanal).

## Cálculo de la Columna `proyeccion`
$$\text{Proyección} = \begin{cases} \text{Despacho Real} & \text{si } \text{día} < \text{día de hoy} \\ \text{RF Ajustado} & \text{si } \text{día} \ge \text{día de hoy} \end{cases}$$

Agrupado por: Gerencia, Equipo, Departamento, Localidad, Centro de Distribución, Producto, Incoterms, Día y Cliente.
