# Revisión Supabase de PWA V1.1

Actualizado: 05/11/2026. Proyecto revisado: `Partes Diarios` (`dfwslamasfoscxlyzryr`).

## Cambios aplicados

- Se aplicó la migración `pwa_v11_catalogs_and_report_context` y se verificó su registro remoto. Agrega marcas de selección/agronomía, contexto por tarea, relaciones de catálogos, validaciones atómicas de carga e índices de claves foráneas. No se importaron catálogos.
- Se aplicó `tune_pwa_v11_catalog_policies`: cada catálogo nuevo conserva lectura para sesiones activas y usa políticas separadas de inserción, actualización y borrado para administración. Se eliminaron políticas permisivas duplicadas en `SELECT`.
- Se confirmo RLS en las seis tablas nuevas, cuatro politicas por tabla y cero filas. Se cambiaron 5 lotes historicos a `selectable=false` con cruce normalizado de IDs; el total sigue en 619 y quedan 614 seleccionables. Partes, tareas, ciclos e idempotencia siguen en cero.
- Antes de cualquier importación, se exportaron `farms`, `lots`, `operations`, `machines` e `inputs` a `supabase/.temp/pwa_v11_catalog_backup_20261105.json` (ignorado por Git).

## Resultado de los asesores

- Seguridad: queda una advertencia de configuración Auth: la protección contra contraseñas filtradas está desactivada. No se cambia desde SQL y las herramientas conectadas no exponen su ajuste; debe habilitarse en Auth del proyecto.
- Rendimiento: no quedan avisos de claves foráneas sin índice ni políticas permisivas duplicadas. El asesor informa índices existentes sin uso observado; se dejaron intactos porque el proyecto aún no tiene partes/ciclos y la mayoría sirven a esas consultas. El índice de idempotencia y los cuatro índices inversos nuevos están incluidos.
- Salud: sin avisos.
- En los registros de las últimas 24 horas aparecen 21 entradas `LOG`, dos `ERROR` (SQLSTATE `42883` y `42501`) y una desconexión normal. El muestreo no expuso mensajes ni datos personales y no vincula esos errores con la migración aplicada.

## Importación de catálogos: revisión previa

Estado remoto antes de cargar: fincas 27, lotes 619, operaciones 299, maquinas 517 e insumos 149. Centros, grupos y las cuatro tablas de relacion nuevas: 0. Hay 0 partes existentes. Despues del ajuste quedan 614 lotes seleccionables y 5 historicos no seleccionables; las tablas de catalogos V1.1 siguen vacias.

Conteos del paquete V1.1: 24 centros; 672 ubicaciones; 619 filas de inventario; 266 relaciones centro/grupo; 306 grupo/operación; 303 operaciones; 504 filas de maquinaria (503 claves `ID_Equipo` distintas); 149 insumos. Las 672 ubicaciones cubren 614 IDs existentes normalizados y agregan 58; los otros 5 lotes existentes deben quedar no seleccionables. 58 ubicaciones no tienen fila de inventario.

La importacion completa esta detenida por una colision: dos filas comparten `ID_Equipo` pero difieren en `Equipo`, grupo y atributos. La tabla actual usa `equipment_code` como clave primaria, asi que no permite guardar ambas con el mapeo documentado. Falta decidir si la clave pasa a ser `Equipo` y `ID_Equipo` queda en `source_data`, o si se corrige el duplicado en la fuente. No se ejecuto upsert parcial ni se eligio una fila por inferencia.

El CSV `Operacion_Insumos.csv` se reinterpreto siguiendo `app_core.py` de V1.1: contiene el indicador `SI/NO` por operacion, no una lista de productos compatibles. El lector fuente obtiene 283 filas, 282 claves (un duplicado exacto), 37 `SI`, 160 `NO`, 86 vacias; las operaciones sin fila quedan sin insumos. Por eso `allows_inputs` se importa desde ese indicador y la relacion especifica operacion/producto queda vacia. No se ejecuta un upsert completo hasta resolver la clave de maquinaria y fijar el resumen antes/despues.

## Pendiente funcional

La PWA ya captura ausentes, cantidades fijas, reemplazos, horas, lecturas e insumos. Quedan pendientes el editor de correccion transaccional, importacion de JSON con vista previa, importacion completa de catalogos, parser de texto, guardado offline y validacion visual autenticada. Hasta sincronizar catalogos V1.1, el selector de centro se mantiene opcional.
