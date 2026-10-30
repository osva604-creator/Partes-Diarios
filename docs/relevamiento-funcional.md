# Relevamiento funcional — Asistente de parte diario

Estado: primer relevamiento del código actual, 29/10/2026. Este documento sirve como especificación de paridad para la reconstrucción PWA. Las reglas marcadas como “confirmar” requieren contraste con usuarios antes de cerrar la migración.

## Estado actual de la reconstrucción (30/10/2026)

- La PWA implementa autenticación Supabase, lectura de catálogos activos y carga inicial de una tarea mediante la RPC transaccional `create_daily_report`.
- La base conectada tiene el esquema y la RPC, pero aún no tiene catálogos ni frentes activos. La carga operativa requiere importar los maestros y crear/configurar frentes.
- La carga inicial permite elegir una finca, lote, operación, frente y personas; reparte el total en partes iguales. Aún no cubre paridad funcional con la app Streamlit.
- El inventario local contiene filas repetidas para los IDs de lote `0010401` y `0201601`; se debe definir si son variantes que se agregan o un duplicado a descartar antes de importar.

## Módulos y flujos observados

1. **Partes y avance**: resumen filtrable de partes, trabajos/ciclos por lote y tarea, objetivo y cantidad acumulada, detalles de asignaciones e insumos; permite cargar tareas, acumular partes en un ciclo abierto, cerrar el trabajo y borrar selecciones con actualización de acumulados.
2. **Carga de parte**: fecha común del parte; finca, lote y cultivo por tarea; tarea/operación, unidad, cantidad, objetivo, modo de distribución, frente, personal, vehículo, ausencias/reemplazos, horas por persona, lecturas de maquinaria, observaciones e insumos/dosis/consumo. Admite varias tareas en un único parte y guarda encabezado, tareas y detalles en una transacción.
3. **Frentes**: crear frentes, agregar/quitar personas y vehículos habituales; además permite configuraciones por tarea y archivar frentes.
4. **Carga manual por texto**: interpreta nombres, códigos, cantidades expresadas con números o palabras, fecha relativa, finca/lote, tarea, personal, frente, vehículo asociado a cada persona, insumo/dosis/consumo y observaciones; produce borrador editable. Confirmar guarda en la misma base y el borrador no se vuelve a guardar al recargar.
5. **Mis partes / revisión documental**: búsqueda e intervalo de fechas para partes enviados, vista de detalle, edición de encabezado y tareas, snapshot de revisiones, PDF aprobado y preparación/reenvío por WhatsApp.
6. **Configuración**: identificador de usuario actual, horas sugeridas por persona, número de WhatsApp y plantilla del mensaje (`{id}`, `{fecha}`). El código actual usa un identificador local simple, no autenticación central.

## Reglas de negocio observadas

- Catálogos fuente: personal, maquinaria, operaciones, lotes e insumos desde archivos maestros. Las operaciones indican unidad, tipo manual/mecanizada, grupos de maquinaria admitidos y si puede usar insumos.
- Una tarea manual no admite vehículos. Una tarea mecanizada filtra maquinaria por grupos operativos configurados; sin grupo asignado quedan disponibles todas las máquinas.
- Identidad del ciclo de trabajo: lote + operación + número de ciclo. Se agrega a un ciclo abierto coincidente; si no existe se crea el siguiente. Estado operativo Abierto/Cerrado es independiente del estado documental.
- Objetivo se propone desde los datos maestros o desde el parte; el avance suma cantidades de partes. “Cantidad individual” no usa objetivo. Redistribuir conserva cantidades fijas y excluye ausentes.
- El reparto debe conservar el total; para unidades enteras se redistribuyen enteros. Ausentes no reciben cantidad; cantidad fija conserva el valor configurado; presentes comparten saldo.
- Horas/persona, vehículo por persona, reemplazos y lecturas de máquina se conservan como detalle de la asignación.
- Un parte puede tener varias tareas; cada línea se vincula a lote/tarea/ciclo, frente, cantidad, cultivo, asignaciones e insumos. El encabezado guarda fecha, creador, secuencia/ID y orden de servicio.
- Insumos guardan dosis y consumo real por producto/unidad; conversiones entre unidades de masa están permitidas, masa↔volumen exige corrección explícita.
- Cambios al documento guardan revisión anterior. Documento enviado corregido pasa a Corregido y necesita nueva revisión/PDF. Envío se registra luego de preparar el archivo y confirmar manualmente WhatsApp.
- Borrado de partes recalcula los acumulados derivados. Cierre de una tarea no implica envío documental.
- Matching de texto normaliza acentos/caso, busca coincidencias aproximadas y códigos con contexto. Si la coincidencia no es segura se deja vacía para revisión; la interpretación no persiste datos por sí sola.

## Modelo actual (SQLite)

`daily_reports` (encabezado/estado documental), `work_cycles` (trabajo por lote-operación-ciclo), `partial_parts` (tareas parciales y metadatos), `partial_allocations` (personas, asistencia, cantidad, vehículo, reemplazo, horas y lecturas), `partial_inputs` (productos/dosis/consumo), `fronts`, `front_members`, `front_task_members`, `part_sequences`, `local_user_preferences`; `report_revisions` conserva snapshots JSON.

## Criterios de paridad para PWA

- Mantener flujos y resultados existentes, incluyendo PDF y distinción entre estado operativo/documental.
- Añadir navegación adaptable: escritorio con navegación lateral y tablas; móvil con navegación inferior, formularios por pasos, tarjetas y acciones táctiles. “Mejoras” de flujo no deben alterar reglas ni cálculos.
- Borradores locales offline con cola de sincronización idempotente; mostrar claramente sincronización pendiente/error y evitar duplicados. No se afirma modo offline para consultar o editar datos nuevos no descargados.
- Auth Supabase obligatoria; autorización por roles vía RLS; conservar actoría e historial. Clave publicable solamente en cliente; secretos nunca en PWA.
- Roles definidos: un administrador (alta de usuarios, catálogos, correcciones, revisión y cierre); usuarios normales (carga de partes, borradores y configuración de frentes). Catálogos son lectura para usuarios normales. Partes y avance son visibles para todos inicialmente.
- PDF se genera desde datos aprobados del servidor o cliente con una plantilla de paridad visual; guardar versión/hash para reconocer qué documento se envió.

## Diferencia de producto por dispositivo

- **Móvil simplificado:** cargar un parte en pasos (lote/tarea → cantidad → frente/personal → opcionales → confirmar), con botones táctiles, pocos campos simultáneos, borrador automático y confirmación clara. Mostrar cargas recientes como tarjetas. Funciones avanzadas detrás de “Más opciones”.
- **PC completa:** navegación lateral persistente, métricas, tabla de partes/avance, filtros y operaciones en lote; formulario multi-tarea y edición detallada; herramientas administrativas visibles solo al rol administrador.
- Se comparte el modelo y las validaciones: simplificar la presentación y la secuencia de entrada no cambia los datos posibles ni los cálculos.

## Preguntas de relevamiento pendientes

- Confirmar actores/roles y si todos los miembros de la organización ven todos los partes o hay restricciones por frente, equipo o autor.
- Confirmar el identificador de usuario actual (“pyni”) y cómo se mapeará a cuentas Auth y formato/alcance de IDs.
- Confirmar política de edición/borrado luego de aprobación/envío y quién puede cerrar/reabrir un ciclo.
- Confirmar la relación exacta entre objetivos del inventario, áreas netas/brutas y conversión por operación/unidad.
- Capturar ejemplos de PDF considerado vigente y revisar comportamiento esperado de WhatsApp en navegadores móviles y escritorio.
- Definir política offline para catálogos y conflictos si dos usuarios guardan sobre el mismo ciclo a la vez.

