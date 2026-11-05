# Revisión Supabase de PWA V1.1

Actualizado: 05/11/2026. Proyecto revisado: `Partes Diarios` (`dfwslamasfoscxlyzryr`).

## Cambios aplicados

- Se aplicaron la migracion `pwa_v11_catalogs_and_report_context`, los ajustes de politicas y triggers, y `use_machine_code_primary_key`. `machines.machine_id` es la nueva PK surrogate; `machine_code` conserva unicidad y todas las FK existentes. No se borraron filas.
- Se aplicó `tune_pwa_v11_catalog_policies`: cada catálogo nuevo conserva lectura para sesiones activas y usa políticas separadas de inserción, actualización y borrado para administración. Se eliminaron políticas permisivas duplicadas en `SELECT`.
- Se confirmo RLS en las seis tablas nuevas, con cuatro politicas por tabla. Tras la importacion hay 24 centros, 34 grupos, 266 relaciones centro/grupo, 306 grupo/operacion, 30.103 operacion/maquina y cero operacion/insumo. Se cambiaron 5 lotes historicos a `selectable=false`; se conservan los 619 IDs previos y quedan 614 elegibles entre ellos. Partes, tareas, ciclos e idempotencia siguen en cero.
- Se aplico `atomic_report_correction`: la RPC `correct_daily_report` solo la puede ejecutar administracion, guarda primero el snapshot completo y aplica la correccion en una transaccion. Restablece el documento a `Corregido`, limpia los datos de revision/envio y aumenta `pdf_version`; requiere una nueva revision para habilitar el PDF vigente. La RPC publica no es ejecutable por `anon`; la funcion interna queda en `private`.
- Antes de cualquier importación, se exportaron `farms`, `lots`, `operations`, `machines` e `inputs` a `supabase/.temp/pwa_v11_catalog_backup_20261105.json` (ignorado por Git).

## Resultado de los asesores

- Seguridad: queda una advertencia de configuración Auth: la protección contra contraseñas filtradas está desactivada. No se cambia desde SQL y las herramientas conectadas no exponen su ajuste; debe habilitarse en Auth del proyecto.
- Rendimiento: no quedan avisos de claves foráneas sin índice ni políticas permisivas duplicadas. El asesor informa índices existentes sin uso observado; se dejaron intactos porque el proyecto aún no tiene partes/ciclos y la mayoría sirven a esas consultas. El índice de idempotencia y los cuatro índices inversos nuevos están incluidos.
- Salud: sin avisos.
- Tras la migracion de correccion: RPC publica/interna presentes; `authenticated` puede llamar la RPC y `anon` no. No se probaron escrituras con un reporte real porque la base sigue sin partes ni revisiones.
- En los registros de las últimas 24 horas aparecen 21 entradas `LOG`, dos `ERROR` (SQLSTATE `42883` y `42501`) y una desconexión normal. El muestreo no expuso mensajes ni datos personales y no vincula esos errores con la migración aplicada.

## Importación de catálogos: revisión previa

Antes del upsert: fincas 27, lotes 619 (614 seleccionables/5 historicos), operaciones 299 activas, maquinas 517 activas, insumos 149; tablas de catalogo nuevas vacias. El respaldo de produccion esta en `supabase/.temp/pwa_v11_catalog_backup_20261105.json`.

El upsert completo se ejecuto en una transaccion. Despues: fincas 29 (+2); lotes 677 (+58, 614 existentes actualizados, 5 historicos preservados y 58 sin agronomia); 672 ubicaciones seleccionables; operaciones 308 (303 activas, 9 insertadas, 5 antiguas desactivadas); maquinas 517 (504 activas, 13 antiguas desactivadas); insumos 149. Sin borrados.

La duplicidad de `ID_Equipo` se resolvio conservando ambos valores fuente en `equipment_code`/`source_data` y agregando `machine_id` como PK surrogate. La clave operativa unica `machine_code` se mantiene para las FK existentes y para la PWA. Se uso `Equipo` como clave de upsert, coherente con el cargador V1.1.

`Operacion_Insumos.csv` se importo como indicador de `operations.allows_inputs` siguiendo el codigo V1.1 (37 operaciones permiten insumos). No enumera productos compatibles; por eso `operation_inputs` queda vacia y el selector muestra los 149 insumos activos en esas tareas. De los 30.103 vinculos operacion/maquina almacenados, 28.973 corresponden a operaciones y equipos activos; 1.130 se conservan ligados unicamente a las 5 operaciones o 13 maquinas desactivadas.

## Pendiente funcional

La PWA captura ausentes, cantidades fijas, reemplazos, horas, lecturas e insumos. El editor de correccion transaccional ya esta implementado para editar cabecera, cantidades/notas, asignaciones existentes e insumos existentes. Conserva el conjunto de filas actual: agregar o quitar tareas, personas o insumos durante la correccion requiere una fase posterior. La importacion JSON valida formato, tamano, catalogos, relaciones, asignaciones e insumos, muestra vista previa y solo luego incorpora los datos al borrador local; todavia hace falta la accion separada de guardar el parte. Siguen pendientes el parser de texto, el guardado offline y la validacion visual autenticada.
