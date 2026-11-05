# Relevamiento y paridad funcional

**Estado:** implementación de paridad en curso
**Actualizado:** 05/11/2026

## Objetivo

Completar la PWA para que permita realizar los mismos trabajos que la aplicación Streamlit, conservando las reglas de negocio y los resultados. La experiencia puede adaptarse a cada dispositivo: no es necesario copiar las mismas pantallas.

La paridad se considera alcanzada cuando una persona puede completar en la PWA los flujos operativos y documentales definidos aquí, con validaciones y resultados equivalentes a Streamlit.

## Estado de partida

- Streamlit ofrece carga guiada y detallada, frentes con asignación por tarea, consulta de ciclos/partes, edición de asignaciones, revisión documental, PDF y preparación de WhatsApp.
- Streamlit guarda en una base SQLite de la instalación. No tiene autenticación ni roles; el código de usuario configurable identifica partes y preferencias, pero no es un permiso.
- La PWA requiere sesión de Supabase, lee catálogos, guarda partes de varias tareas y permite administrar frentes con equipos por tarea y máquina habitual por integrante. También tiene permisos RLS de propietario/administrador.
- Estado actualizado: la PWA arma partes de varias tareas, consulta bajo RLS, abre el detalle, genera PDF revisado con JSON V1 adjunto y registra la confirmacion separada del envio.
- Catalogos V1.1 importados en Supabase con upsert transaccional y respaldo previo. Correccion atomica disponible para ajustar filas existentes; importacion JSON con vista previa agrega contenido solo al borrador local. Siguen pendientes parser de texto, sincronizacion offline y verificacion visual autenticada.
- Las dos aplicaciones tienen distinta identidad, persistencia y secuencia de IDs. La paridad se medirá comparando campos, asignaciones, ciclos y resultados derivados, no el ID literal.

## Pruebas iniciales

**03/11/2026**

- `npm run build` en `pwa/`: correcto; generó el build de producción y el service worker.
- `pytest tests`: 17 pruebas aprobadas. Se actualizaron dos expectativas de conteos maestros en `tests/test_matching.py` para que correspondan a los datos actuales (561 personas y 299 operaciones).
- Supabase: se crearon dos frentes activos de prueba, `[PRUEBA PWA] Frente demo 01` y `[PRUEBA PWA] Frente demo 02`. Se verificó que un usuario autenticado los puede leer mediante RLS.
- La prueba de `create_daily_report` encontró un bloqueo: con las políticas vigentes, un usuario normal no puede bloquear/actualizar su fila de `report_sequences`, y la RPC falla al generar `report_code`.
- Se aplicó `20261103185852_fix_report_sequence_rpc_access`: la RPC delega el incremento atómico de la secuencia propia a una función interna en el esquema `private`, sin abrir actualización directa de secuencias desde el cliente.
- La prueba posterior a la migración guardó el parte como usuario autenticado y el reintento con la misma clave devolvió el mismo ID (`replayed=true`). La transacción de prueba se revirtió completa: no quedaron integrantes, partes ni ciclos temporales; solo permanecen los dos frentes demo.
- Pendiente: probar el recorrido desde la interfaz con una sesión real.

**04/11/2026**

- Se agregó en la PWA la sección **Frentes**: crear frentes, cambiar el nombre, asignar/quitar personal, asociar una máquina por integrante y desactivar frentes propios.
- Se aplicó `20261104174243_add_front_management`: ahora solo la persona creadora o un administrador puede modificar los integrantes y las asignaciones de un frente. La sustitución del equipo se ejecuta en una sola transacción.
- Se agregó la configuración de integrantes y máquina por operación mediante `front_task_members`, aplicada en la migración `20261104180942_add_front_task_member_management`. La carga recupera el equipo de la combinación frente+tarea y preselecciona la máquina habitual.
- La carga distingue cantidad total a repartir de cantidad individual por persona; los ciclos individuales no usan objetivo y el total del trabajo se calcula con la suma de cantidades asignadas.
- Pruebas de permisos simulando sesiones autenticadas: el propietario pudo reemplazar el equipo; un usuario distinto recibió denegación. Las pruebas se revirtieron y no modificaron los frentes de demostración.
- `npm run build` en `pwa/`: correcto, incluye la sección nueva y genera el service worker.
- Pendiente: probar creación, edición y carga desde la interfaz con una sesión real; el recorrido visual no se ha verificado en navegador.

**05/11/2026 — actualización PWA V1.1**

- Se agrego y aplico el esquema aditivo V1.1, ajustes de politicas, validaciones de insumos/asignaciones y la clave surrogate de maquinaria. El upsert productivo se completo con respaldo previo; conteos y seguridad en `docs/pwa-v11-supabase-review.md`.
- Se documento el mapeo del ZIP en `docs/pwa-v11-catalog-map.md` y se agrego el importador repetible `scripts/prepare_pwa_v11_catalog_import.py`. La carga productiva se completo en una transaccion con respaldo previo; no se borraron filas.
- La interfaz ahora permite agregar/quitar varias tareas a un borrador de fecha común, revisar y descartar el conjunto, bloquear la fecha mientras contiene tareas, rechazar combinaciones lote+operación repetidas y enviar el conjunto en una sola llamada idempotente a `create_daily_report`. Los modos total/individual conservan la cantidad y distribución; `SC` distribuye enteros.
- La selección de lote ofrece centros de costo, filtra operaciones por grupo si las relaciones están cargadas, avisa al elegir un centro distinto y captura el snapshot en cada tarea. Los lotes no elegibles no aparecen; la agronomía faltante se informa sin bloquear ni derivar objetivo de inventario/cantidad.
- Se agrego Partes y avance con rango de fechas, busqueda por ID/texto, detalle y tablas de personal, maquinaria, insumos y ciclo. Las consultas pasan por Supabase/RLS. El acumulado suma las tareas visibles del ciclo.
- El PDF requiere estado Revisado/Enviado; incorpora `parte_diario_v1.json` (schema `asistente-parte-diario` v1). En movil ofrece compartir archivo; tambien se permite descarga/JSON separado. Estas acciones no registran envio.
- Administración puede guardar una revisión: la RPC crea un snapshot de parte, tareas, asignaciones e insumos y aumenta `pdf_version`. La persona autora o administración puede confirmar el envío después de compartir, indicando canal y destinatario opcional. Las acciones de snapshot y envío usan RPC con validación de rol/propiedad.
- Se agrego `correct_daily_report`: conserva el snapshot anterior, actualiza todo en una transaccion, cambia el estado documental a `Corregido`, limpia revision/envio y aumenta `pdf_version`. Administracion puede editar cabecera, tareas y valores de filas existentes; el PDF requiere nueva revision. No permite sumar/quitar filas durante una correccion.
- La importacion JSON valida esquema, tamano, claves, catalogos, relaciones y cantidades; requiere elegir el frente y aceptar la vista previa antes de poblar el borrador. Guardar en Supabase sigue siendo una accion aparte.
- Pendiente: prueba visual autenticada; conversiones avanzadas, parser de texto y flujo offline.
- `npm.cmd run build` desde `pwa/`: correcto. El upsert productivo se verifico con conteos y validaciones de RLS; no se hicieron pruebas visuales autenticadas.

## Pasos

### 1. Completar la matriz de paridad

Relevar los flujos existentes en Streamlit y registrar para cada uno:

- quién lo usa y desde qué dispositivo;
- datos de entrada y resultado esperado;
- reglas, cálculos y validaciones;
- permisos requeridos;
- comportamiento ante errores y datos incompletos;
- criterios para confirmar que la PWA se comporta igual.

El relevamiento de código de la primera pasada está registrado en la matriz incluida al final. La columna de aceptación indica cómo comparar resultados además de nombres de campos. Las reglas derivadas del código quedan marcadas como observadas; las decisiones de producto siguen abiertas hasta validarlas con las personas usuarias.

**Estado del paso 1:** relevamiento de código completado y matriz inicial registrada. Falta validar con usuarios los criterios señalados como decisiones de producto; esta validación no impide usar la matriz para guiar el desarrollo.

### 2. Resolver frentes y permisos

La administración y lectura de equipos por tarea quedó implementada. La configuración se guarda en una RPC transaccional que valida propietario/administrador, integrantes activos y grupos de máquinas.

Antes de habilitar escrituras, hacer coincidir las reglas de la interfaz con las políticas de Supabase. El servidor debe comprobar, como mínimo, que las personas y la maquinaria seleccionadas sean válidas para el frente y la tarea. Los permisos de base de datos deben limitar quién puede crear, cambiar o quitar esos datos.

**Estado:** implementación de interfaz, lectura de configuración por tarea y permisos de propietario/administrador completada. Falta validar el recorrido visual con una sesión real y confirmar en terreno las configuraciones de los frentes operativos.

**Criterio de cierre:** propietario/admin configura los integrantes por tarea; la carga recupera la combinación correcta y otro usuario no puede modificarla. La validación SQL de permisos está aprobada; falta la comprobación visual con sesión real.

### 3. Completar el recorrido operativo principal

Cerrar el recorrido de punta a punta:

1. Configurar un frente con integrantes.
2. Cargar un parte con los datos de lote, tarea, cantidad y asignaciones.
3. Guardarlo de forma atómica y evitar duplicados al reintentar.
4. Consultar el parte guardado y el avance correspondiente.
5. Corregir una carga permitida y cerrar el ciclo cuando corresponda.

La primera entrega debe cubrir el resumen de partes y avances; guardar datos sin poder comprobar su efecto no completa el flujo operativo.

**Criterio de cierre:** los datos guardados, las cantidades asignadas y los acumulados del lote/ciclo coinciden con las reglas relevadas.

### 4. Completar los casos avanzados de carga

Agregar las capacidades que Streamlit ya ofrece y confirmar en la matriz:

- varias tareas dentro de un mismo parte;
- distribución total o cantidades individuales;
- ausencias, cantidades fijas y reemplazos;
- maquinaria por persona y lecturas de maquinaria;
- horas por persona;
- insumos, dosis, consumo real y conversiones de unidad;
- objetivos, observaciones y validaciones específicas de cada operación.

Implementar las reglas críticas en el servidor además de dar feedback inmediato en la interfaz. La interfaz puede simplificar la secuencia en móvil, pero no debe cambiar los datos posibles ni los cálculos.

### 5. Completar la revisión documental

Implementar la búsqueda de partes, edición permitida, historial de revisiones, aprobación, generación de PDF y preparación/envío por WhatsApp. Mantener separadas las reglas del estado documental y del estado operativo del ciclo.

**Criterio de cierre:** una corrección conserva la revisión anterior; un PDF aprobado representa la versión vigente; el estado de envío se registra según la confirmación del usuario.

### 6. Incorporar trabajo sin conexión

Cuando los flujos en línea y el modelo de datos estén estables, incorporar borradores locales, una cola de sincronización, reintentos idempotentes y estados visibles de pendiente/error. Definir también cómo resolver conflictos si cambió el ciclo mientras el dispositivo estaba desconectado.

**Criterio de cierre:** recuperar la conexión sincroniza cada borrador una sola vez, informa el resultado y permite recuperar cargas con error sin perder datos.

## Orden recomendado de entregas

1. Matriz de paridad y decisiones de permisos.
2. Administración de frentes con validación en base de datos.
3. Carga y consulta del recorrido operativo principal.
4. Casos avanzados de carga y carga manual por texto.
5. Revisión, historial, PDF y envío.
6. Borradores y sincronización sin conexión.

Cada entrega debe incluir sus criterios de aceptación y actualizar la matriz. No avanzar a una etapa suponiendo que una función está completa solo porque se guardan filas en la base: comprobar el resultado visible y sus efectos en ciclos y acumulados.

## Matriz de paridad

El alcance de actores y dispositivos de Streamlit se infiere del código: operador de campo/administrativo con acceso a la instalación, navegador de escritorio como presentación principal y estilos adaptables para pantalla chica. No hay autenticación técnica. En PWA el actor es una cuenta Auth activa; puede usar navegador o instalar la PWA en móvil/escritorio. La columna de permisos registra el comportamiento observado, no una decisión sobre qué roles debería haber. Fuentes: [streamlit_app.py](../streamlit_app.py), [quick_entry.py](../quick_entry.py), [app_core.py](../app_core.py), [app_store.py](../app_store.py) y [PWA App.tsx](../pwa/src/App.tsx).

| Flujo | Actor y dispositivo | Entradas → resultado en Streamlit | Reglas, validaciones y errores | Permisos observados | PWA actual y criterio de aceptación | Estado |
|---|---|---|---|---|---|---|
| Sesión, preferencias y catálogos | Operador; navegador de escritorio o pantalla chica. PWA: cuenta autenticada desde móvil o escritorio. | Código de usuario, horas sugeridas, teléfono y plantilla WhatsApp; archivos maestros de lotes, personal, operaciones, maquinaria e insumos. Resultado: catálogos y preferencias disponibles para cargar. | El código se normaliza a minúsculas y alfanumérico; vacío se convierte en `usuario`. Horas entre 0 y 48 en pasos de 0,5. Mensaje admite `{id}` y `{fecha}`. Archivos o columnas/filas inválidas generan advertencia/error. | Streamlit no autentica ni distingue roles; cualquiera con acceso puede cambiar el código. PWA requiere sesión Supabase activa y lee catálogos activos según RLS. | Login y lectura implementados. Aceptación: solo cuenta activa accede; usuario normal solo lee maestros; persistir preferencias por cuenta. IDs locales y secuencias PWA no necesitan coincidir literalmente. | Parcial: identidad y preferencias distintas. |
| Frentes y equipo por tarea | Responsable que prepara el equipo; Streamlit prioriza escritorio, con CSS adaptable. PWA: creador del frente o administrador. | Crear frente con nombre; elegir frente, operación, persona y máquina habitual compatible. Resultado: personas y máquina asociadas a una tarea del frente. Quitar integrante o archivar lo saca de nuevas cargas y conserva referencias históricas. | Nombre requerido. Máquina filtrada por grupo operativo de la tarea; trabajo manual no admite máquina. Una asignación por frente+tarea+persona. Errores al guardar deben dejar visible el estado anterior. | SQLite local no aplica permisos. PWA restringe edición a creador/admin mediante RLS; otros usuarios deben recibir denegación. | Configurar integrantes y máquina habitual por operación, cargar el equipo al elegir frente+tarea y desactivar frente: implementado. La RPC valida propietario/admin y asignaciones compatibles; falta la comprobación visual de interfaz con sesión real. | Parcial: SQL aprobado; validación visual pendiente. |
| Parte detallado de una tarea | Operador de campo; PC o movil. | Fecha, finca/lote, costo, cultivo, operacion, cantidad, frente, observaciones y personal en borrador multi tarea. | SC/HA/TN usan total a repartir; otras unidades, cantidad individual. Objetivo ausente se guarda como sin dato. Requiere cantidad positiva y personas. | Supabase Auth/RLS; RPC atomica e idempotente. | Borrador, costo y distribucion implementados; ausencias/fijos, reemplazos, horas, lecturas e insumos ahora se guardan por persona/tarea. Falta verificacion visual autenticada. | Parcial. |
| Encabezado y parte con varias tareas | Operador en una sesion de navegador. | Fecha comun; finca/lote/cultivo, tarea, frente, cantidad, personal y nota. Se puede sumar/quitar tareas y descartar. | No cambia la fecha con tareas; se rechaza repetir lote+operacion. Una llamada RPC guarda el arreglo en una transaccion con clave idempotente. | Cuenta activa por Supabase/RLS; catalogos V1.1 importados. | UI y RPC implementadas, incluidas distribucion avanzada e insumos por tarea. Falta verificacion visual y fallo intencional de una linea en entorno de prueba. | Parcial. |
| Distribucion, asistencia, reemplazos y maquinaria | Operador/supervisor; PC y movil. | Seleccion multiple, estado por persona, cantidades individuales/fijas, reemplazo, maquina, horas y lecturas. | Total exacto; fijo conserva valor; ausente=0; SC entero. Valida reemplazo activo, horas 0-24 y lecturas emparejadas/ordenadas en interfaz y servidor. | Supabase Auth/RLS y RPC transaccional. | Captura implementada y enviada por tarea. Falta validar visualmente con cuenta autenticada y comparar escenarios controlados. | Parcial. |
| Insumos, dosis y conversiones | Operador; PC o movil. | Productos compatibles por tarea, dosis, consumo y unidad; varios productos. | Valida duplicados, valores y compatibilidad en interfaz y base. Conversiones entre masa/volumen y sugerencias frecuentes pendientes. | Supabase Auth/RLS; solo tareas con `allows_inputs` aceptan productos. | Seleccion y persistencia transaccional implementadas. Falta probar conversiones y verificar con catalogos poblados. | Parcial. |
| Resumen de partes, avance e intercambio | Operador; adaptable a movil/escritorio. | Rango de fechas y busqueda de ID, finca, lote, tarea, insumo, persona y usuario; detalle con tareas, personal, maquinaria, insumos, ciclo, objetivo, acumulado y saldo. Exporta/importa JSON V1 con vista previa y PDF. | Los select y sumas siguen RLS; la importacion solo crea borrador local tras validar y confirmar; el guardado remoto se hace por separado. El acumulado se suma desde tareas visibles del ciclo. No se ofrece CSV ni metricas de bandeja. | PWA limita resultados/detalle a filas autorizadas; la carga usa RPC idempotente. | Listado, filtros, detalle, ciclo, exportacion y vista previa de importacion implementados; CSV, ordenar, metricas agregadas y prueba con usuarios reales pendientes. | Parcial. |
| Correccion, eliminacion y cierre de ciclo | Administracion; PC o movil. | Revision crea snapshot y aumenta la version del PDF; correccion edita filas actuales; borrado y cierre siguen pendientes. | RPC de revision/correccion es admin-only; corregir limpia revision/envio y aumenta version; RPC de envio comprueba autor/admin. Revisar/corregir no cierra el ciclo. | Alineado con roles definidos en arquitectura. | Editor y RPC atomica implementados para cabecera y filas existentes, guardando snapshot previo. No permite agregar/quitar tareas, asignaciones ni insumos. Borrado y cierre/reapertura de ciclos no implementados. | Parcial. |
| Entrada guiada por texto | Operador en campo; móvil o PC. | Frase con fecha, finca/lote, tarea, cantidad/unidad, personas/legajos, frente, vehículo, insumo/dosis/consumo y observaciones. Resultado: borrador revisable; interpretar nunca guarda por sí solo. | Normaliza acentos/caso; reconoce cantidades numéricas y escritas, ayer/anteayer y varios formatos de fecha; códigos con contexto. Elige coincidencia aproximada solo si supera a la siguiente por ≥3 puntos; ambigüedades quedan vacías. Informa legajo inexistente, fecha o unidad dudosa y conversión incompatible. | Mismo acceso local que otros flujos; no hay rol. PWA no tiene parser ni borrador offline. | Pendiente. Aceptación: frases inequívocas completan campos esperados; ambiguas quedan sin asignar; editar y descartar no persiste; confirmar guarda una vez. | Pendiente. |
| Revision documental e historial | Administracion; adaptable. | Accion explicita de revisar; snapshot de encabezado/tareas/asignaciones/insumos; correccion y version nueva del PDF. | Snapshot y transicion de estado usan RPC; la correccion guarda el documento completo en una transaccion y no modifica el estado del ciclo. | Solo administracion revisa/corrige; autor o administracion registra envio. | Editor de correccion e historial previo implementados; una correccion borra el envio vigente e invalida el PDF anterior, y exige revisar de nuevo. El editor conserva las filas existentes. Conflictos/concurrencia visual pendientes. | Parcial. |
| PDF, preparacion y envio WhatsApp | Autor o administracion; PC y movil. | PDF descargable con adjunto JSON parte_diario_v1.json, schema v1; compartir en movil; confirmacion separada guarda hora, destinatario, canal y usuario. | PDF requiere estado Revisado/Enviado. Preparar/compartir no modifica estado; confirmar requiere revision. No inicia WhatsApp ni redacta mensaje automaticamente. | RLS y permisos por rol/propietario en backend. | PDF embebido, descarga/compartir, revision y confirmacion separada implementados; reenvio/historial y verificacion visual pendientes. | Parcial. |
| Mis partes enviados | Autor segun cuenta Supabase; PC o movil. | Partes enviados se pueden encontrar desde Partes y avance y abrir su detalle/PDF. | La lista general muestra estados conforme a RLS; no hay vista personal separada ni boton de reenvio. | RLS vigente y propiedad en confirmacion de envio. | Parte enviado continua apareciendo en lista general; vista personal separada, busqueda por autor y reenvio pendientes. | Parcial. |
| Trabajo sin conexión y recuperación | Streamlit usa SQLite de la instalación; no ofrece cola explícita. PWA orientada a campo puede perder conexión. | Streamlit persiste en disco local mientras la instalación esté accesible. PWA tiene shell cacheado, pero no parte offline. Resultado futuro: borrador pendiente, cola de sync y estado recuperable. | RPC idempotente evita duplicados al reintentar en línea. Resolver colisión si el ciclo cambia durante desconexión queda pendiente; catálogo no descargado no está disponible offline. | Streamlit: acceso al equipo/instalación. PWA: cuenta activa y RLS cuando vuelve a conectar. | No hay guardado offline. Aceptación: en modo avión, conservar borrador tras recarga; al reconectar guardar una vez o mostrar error recuperable y permitir reintentar. | Pendiente. |

### Escenarios mínimos de aceptación

| Escenario controlado | Resultado que se compara |
|---|---|
| Unidad `SC`, total 5, dos personas | Asignaciones enteras suman 5; objetivo proviene de surcos del lote; acumulado coincide. |
| Unidad `HA`, con/sin área neta | Usa área neta y, si falta, bruta; exceso advierte pero permite guardar. |
| Unidad individual (por ejemplo horas) | Cada persona carga su cantidad; total de tarea sigue la regla acordada, no se divide como cantidad total. |
| Ausente, presente y cantidad fija | Ausente=0; fijo se conserva; saldo se reparte; total permanece exacto. |
| Máquina requerida/manual y lecturas | Máquina compatible obligatoria si corresponde; tarea manual sin máquina; lecturas emparejadas, enteras y fin≥inicio. |
| Insumo con dosis y consumo real | Guarda unidad/cantidad y recalcula dosis correctamente; incompatibilidad exige revisión. |
| Dos tareas en un parte | Fecha común; repetición operación+lote rechazada; error en una tarea revierte el parte entero. |
| Enviado corregido | Conserva snapshot previo, invalida envío vigente y requiere nueva revisión/PDF; nunca permite borrar. |
| Filtros y estado enviado | Resultados filtrados coinciden; enviado sale de pendientes sin restarse del acumulado. |

Ejecutar con datos ficticios en copia local/entorno de prueba. Comparar relaciones y valores de negocio (líneas, asignaciones, insumos, ciclos), no IDs generados por cada motor.

## Decisiones de producto pendientes

Registrar las respuestas en este documento antes de cerrar las reglas afectadas:

- qué roles pueden crear y editar frentes;
- si todos los usuarios ven todos los partes o hay restricciones adicionales;
- quién puede corregir o borrar un parte y en qué estados;
- quién puede cerrar o reabrir un ciclo;
- cómo resolver cargas simultáneas o cambios hechos durante una desconexión;
- qué formato y comportamiento de PDF/WhatsApp se considera vigente.
