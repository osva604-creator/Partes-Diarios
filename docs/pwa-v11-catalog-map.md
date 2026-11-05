# Mapeo de catálogos V1.1 → PWA

Este documento registra el contrato de importación, no incluye registros de catálogo. Los encabezados y conteos se leyeron del ZIP V1.1 (`Asistente Parte Diario/datos_fuente/base_datos/`). El árbol V1.1 extraído no contiene `datos_fuente`; tampoco se encontró `documentacion/RECUPERACION_ASISTENTE_20261103.md` como archivo independiente. Las instrucciones de recuperación disponibles en `CONTINUAR_DESARROLLO.md` se consultaron.

## Conteos y claves de negocio

| CSV | Filas | Clave y destino |
|---|---:|---|
| `CentroCosto.csv` | 24 | `ID_Centro_costo` → `cost_centers.cost_center_id`; `Centro_costo` → `name` |
| `CentroCosto_Finca_Lote.csv` | 672 | `ID_Unico_APD` → clave de negocio de `lots`; finca/lote TOTVS y centro sugerido quedan en `source_data` y columnas tipadas |
| `CentroCosto_GrupoOperacion.csv` | 266 | `(ID_Centro_costo, ID_Grupo_operacion)` → `cost_center_operation_groups` |
| `GrupoOperacion_Operacion.csv` | 306 | `(ID_Grupo_operacion, ID_Operacion)` → `operation_group_operations` |
| `Operacion.csv` | 303 | `ID_Operacion` → `operations.operation_code`; nombre, unidad y tipo → columnas tipadas |
| `Operacion_AvanceDosis.csv` | 303 | `ID_Operacion` → `operations`; `Unidad_avance` conserva la unidad de avance en `source_data` mientras se acuerda si reemplaza o complementa `unit` |
| `Operacion_Maquinaria.csv` | 303 | `ID_Operacion` + `Grupo_Op_Maq` → compatibilidad operación/grupo; se expande a `operation_machines` por `machines.operational_group` |
| `Operacion_Insumos.csv` | 283 en lector V1.1 | `ID_Operacion` + campo `Insumos` (`SI/NO`) -> `operations.allows_inputs`; no contiene codigos de producto compatibles |
| `Maquinaria.csv` | 504 | `ID_Equipo` identifica el registro; `Equipo` es el código operativo; grupo, marca, modelo, patente y adquisición → `machines` |
| `Insumos.csv` | 149 | `ID` → `inputs.input_code`; `Insumo` → descripción; `Unidad Medida` → unidad |
| `Inventario_2026.csv` | 619 | Suplemento agronómico, cruzado por `ID_UNICO`; finca/lote se validan contra la ubicación TOTVS y sus IDs se comparan sin ceros iniciales |

Los encabezados se preservan en `source_data` para que los valores de origen y las claves originales sigan disponibles. No se normalizan ni sobrescriben los IDs originales. Los ceros iniciales solo se ignoran en la comparación de IDs numéricos.

## Transformación de ubicaciones

- `ID_Finca_APD` se vincula a `farms.id`; `Finca_TTS`, `ID_Finca_TTS`, `ID_Seccion_TTS`, `Seccion_TTS`, `Lote_TTS` y `Fch.Validez_TTS` se conservan en `source_data`.
- `ID_Lote_APD` → `lots.lot_code`; `Lote_TTS` → `lot_name`; `ID_Unico_APD` → `totvs_location_id` y clave de negocio.
- `ID_CentroCosto_TTS`/`CentroCosto_TTS` → centro sugerido tipado en `lots`; `ID_Centro_costo`/`Centro_costo` del inventario no reemplaza esa sugerencia.
- `CULTIVO`, `VARIEDAD`, `AREA B`, `AREA N`, `SURCOS`, `Año Plantacion` y `Dist Plantacion` → `crop`, `variety`, `gross_area`, `net_area`, `furrows`, `planting_year` y `planting_distance`.
- Se esperan 614 ubicaciones con complemento de inventario y 58 ubicaciones seleccionables con agronomía incompleta. Estas últimas llevan `agronomic_data_available=false`; sus objetivos/dosis no se rellenan por inferencia.
- Los cinco lotes del inventario sin ubicación TOTVS permanecen en `lots` para resolver referencias históricas y se marcan `selectable=false`. No se desactivan ni borran sus relaciones.

## Relaciones funcionales

`cost_center_operation_groups` habilita los grupos por centro; `operation_group_operations` define operaciones por grupo; `operation_machines` limita la maquinaria compatible a los equipos cuyo grupo coincide con `Grupo_Op_Maq`; `operation_inputs` limita insumos por operación. Se conservan `operations.machine_groups` y `source_data` como compatibilidad y referencia de origen. Si una fuente referencia un centro, grupo, operación, máquina o insumo ausente, la carga debe fallar completa y listar la clave faltante.

La migración `20261105120000_pwa_v11_catalogs_and_report_context.sql` agrega el esquema y marca de selección, pero no contiene datos. No se ejecutó ninguna carga remota. Para una sincronización, el proceso debe comparar conteos antes/después, validar claves duplicadas y relaciones, y usar upsert transaccional sin borrar filas. Se debe generar y revisar ese resumen y disponer de un respaldo/export de producción antes de ejecutar la importación en el proyecto `dfwslamasfoscxlyzryr`.

## Campos de tarea guardados

`report_tasks.cost_center_context` guarda IDs, nombres, origen y `changed` como snapshot; `catalog_snapshot` conserva lote y operación al momento de la carga. Ambos se escriben dentro de `create_daily_report`, junto con todas las tareas, asignaciones e insumos de la misma transacción.


## Hallazgos de validacion del paquete

- La exportacion de produccion esta guardada en la carpeta ignorada `supabase/.temp/`; conteos y estado del proyecto se documentan en `docs/pwa-v11-supabase-review.md`.
- `Maquinaria.csv` tiene 504 filas y 503 valores distintos de `ID_Equipo`. Las dos filas con el mismo ID no son iguales y discrepan en codigo de equipo y atributos. No se eligio una fila por inferencia.
- La implementacion V1.1 lee `Operacion_Insumos.csv` con pandas y usa el campo `Insumos` como indicador `SI/NO` para `allows_inputs`; no modela compatibilidad por producto. Esa lectura da 283 filas, 282 claves y un duplicado exacto. Las relaciones `operation_inputs` quedan vacias, por lo que en esas operaciones la PWA muestra todos los insumos activos.
- Se aplicaron la migracion base y ajustes de politicas/validaciones en Supabase; las tablas nuevas siguen vacias hasta resolver estos hallazgos y calcular un plan de upsert con diferencias exactas.
