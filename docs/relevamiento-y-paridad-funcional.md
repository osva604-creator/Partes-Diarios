# Relevamiento y paridad funcional

**Estado:** implementación de paridad en curso
**Actualizado:** 04/11/2026

## Objetivo

Completar la PWA para que permita realizar los mismos trabajos que la aplicación Streamlit, conservando las reglas de negocio y los resultados. La experiencia puede adaptarse a cada dispositivo: no es necesario copiar las mismas pantallas.

La paridad se considera alcanzada cuando una persona puede completar en la PWA los flujos operativos y documentales definidos aquí, con validaciones y resultados equivalentes a Streamlit.

## Estado de partida

- Streamlit ofrece carga guiada y detallada, frentes con asignación por tarea, consulta de ciclos/partes, edición de asignaciones, revisión documental, PDF y preparación de WhatsApp.
- Streamlit guarda en una base SQLite de la instalación. No tiene autenticación ni roles; el código de usuario configurable identifica partes y preferencias, pero no es un permiso.
- La PWA requiere sesión de Supabase, lee catálogos, guarda una tarea por parte y permite administrar frentes con equipos por tarea y máquina habitual por integrante. También tiene permisos RLS de propietario/administrador.
- La PWA aún no permite consultar partes/avance, armar partes con varias tareas, hacer entrada por texto, revisar documentos, generar PDF ni preparar envíos.
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
| Parte detallado de una tarea | Operador de campo; PC o móvil. | Fecha, finca, lote, cultivo, operación, cantidad, frente o carga manual, observaciones, objetivo e integrantes. Resultado: encabezado, línea ligada a ciclo y asignaciones; el flujo puede sumar otras tareas antes de guardar. | Reusa ciclo abierto por lote+operación o crea el siguiente. Unidades `SC`, `HA`, `TN` usan total a repartir; otras cantidad individual. `HA` sugiere área neta y luego bruta; `SC`, surcos. Exceder objetivo muestra aviso y permite continuar. Requiere cantidad positiva y al menos una persona. Ciclo cerrado o cambio concurrente requiere actualizar. | Streamlit disponible a quien acceda al SQLite local. PWA requiere cuenta activa y RPC transaccional; valida entidades activas, asignaciones y claves idempotentes. | PWA crea un renglón. Diferencia observada: modo inicia manualmente en total a repartir; aun si se cambia a cantidad individual distribuye el valor igual entre seleccionados y lo envía como cantidad de tarea. Objetivo vacío toma la cantidad del parte, en lugar del objetivo de lote/ciclo. Aceptación: comparar suma, asignaciones, objetivo y acumulado por unidad/modo. | Parcial: diferencias de semántica y objetivo. |
| Encabezado y parte con varias tareas | Operador en una sesión de navegador. | Una fecha común; finca/lote/cultivo, tarea, frente, cantidad, asignaciones, nota e insumos por línea. OS se completa al revisar. Resultado: un encabezado y varios renglones/ciclos, códigos de parte y línea. Se pueden quitar renglones o descartar el borrador. | Todas las líneas comparten fecha; se rechaza duplicar operación+lote dentro del mismo parte. Con frente configurado se seleccionan tareas y se completan secuencialmente. Guardado es atómico: un error revierte todas las líneas. | Sin roles en Streamlit. RPC PWA acepta arreglo y es atómica, pero la interfaz solo manda una tarea. | Pendiente. Aceptación: armar 2+ líneas, editar/quitar antes de guardar y provocar un fallo controlado en una línea para confirmar que no queda ninguna fila parcial. | Pendiente. |
| Distribución, asistencia, reemplazos y maquinaria | Operador/supervisor; tabla de escritorio prioritaria. | Elegir equipo desde frente o manualmente; cantidad y estado por persona, reemplazo, máquina, horas y lecturas H-Km. Resultado: asignación individual por tarea. Acciones: añadir/quitar/reemplazar persona, aplicar horas sugeridas y redistribuir. | En total a repartir, presentes comparten saldo; fijo conserva cantidad; ausente recibe cero. `SC` distribuye enteros sin perder total; otros modos distribuyen decimales. Fijos no pueden superar el total. No repetir persona. Máquina debe ser compatible; cuando la tarea la exige debe existir al menos una entre presentes. Lecturas van en pares, enteras, fin≥inicio y asociadas a máquina. Error conserva borrador. | Streamlit no aplica roles. PWA hoy solo valida campos básicos vía RPC/RLS. | PWA selecciona personas con checkbox, una máquina común y fija 12 horas; reparte a 3 decimales y ajusta el residuo en la última persona. Aceptación: comparar todas las filas y suma para ausente/fijo/reemplazo, distintas máquinas y lecturas; validar unidad, grupos permitidos y precisión. | Parcial, cobertura reducida. |
| Insumos, dosis y conversiones | Operador; PC o móvil. | Uno o varios productos, dosis por unidad de trabajo, cantidad real consumida; búsqueda por código/nombre y sugerencias frecuentes. Resultado: producto, dosis, unidad y consumo por tarea. | Consumo sugerido = cantidad de trabajo × dosis. Insumo `TN` se muestra como KGS para dosis. Convierte masa GR/KG/TN; masa↔volumen exige revisión. No repetir producto; tarea puede no aceptar insumos. Error de unidad incompatible se informa sin cerrar el borrador. | Catálogos de solo lectura para el usuario PWA; RPC valida que el producto exista/esté activo. | La interfaz PWA no selecciona ni envía insumos. Aceptación: guardar varios productos distintos, dosis y consumo editables; conversión compatible correcta; combinación incompatible requiere corrección explícita. | Pendiente. |
| Resumen de partes, avance y exportación | Operador y supervisión; escritorio preferido por grilla ancha, responsive a móvil. | Fecha/rango, finca, lote, tarea, insumo, ID de parte y búsqueda libre por finca/lote/tarea/insumo/personal; ordenar, seleccionar y descargar CSV. Resultado: ciclos/partes pendientes, métricas abiertos/cerrados/avance y detalle de asignaciones, máquinas, insumos, notas, objetivo, cargado y restante. | Filtros se encadenan. Avance = acumulado/objetivo, limitado al 100% visual. Enviados dejan la bandeja de pendientes, pero siguen sumando al ciclo y aparecen en Mis partes. Búsqueda vacía muestra mensaje; CSV refleja tabla filtrada. | Cualquier usuario con acceso al SQLite local ve esos datos. El modelo RLS PWA comparte lectura entre usuarios activos. | No hay listado, filtros, métricas ni exportación. Aceptación: filas y acumulados coinciden tras cada parte; enviar cambia estado/lista sin alterar acumulado; CSV coincide con el conjunto visible. | Pendiente. |
| Corrección, eliminación y cierre de ciclo | Operador desde tabla/detalle en PC. | Selección de líneas; revisar/preview/descargar PDF de un encabezado; borrar partes no enviados; cerrar tarea del lote. Resultado: documento corregido con revisión, acumulado recalculado o ciclo Cerrado con fecha. | No borrar enviado ni documento con historial de envío. Validar cantidad>0, no negativos, ausente=0, suma de asignaciones para total, lecturas válidas y referencias. Cierre de total a repartir bloqueado si resta >0,01; individual no usa objetivo. | Streamlit no separa por rol. Arquitectura PWA prevé revisión/corrección/cierre para admin; UI aún no lo implementa. | No permite editar, eliminar ni cerrar ciclos. Aceptación: corrección inválida no modifica versión actual; borrar no enviado recalcula; enviado se conserva; cierre respeta saldo. Definir rol habilitado. | Pendiente. |
| Entrada guiada por texto | Operador en campo; móvil o PC. | Frase con fecha, finca/lote, tarea, cantidad/unidad, personas/legajos, frente, vehículo, insumo/dosis/consumo y observaciones. Resultado: borrador revisable; interpretar nunca guarda por sí solo. | Normaliza acentos/caso; reconoce cantidades numéricas y escritas, ayer/anteayer y varios formatos de fecha; códigos con contexto. Elige coincidencia aproximada solo si supera a la siguiente por ≥3 puntos; ambigüedades quedan vacías. Informa legajo inexistente, fecha o unidad dudosa y conversión incompatible. | Mismo acceso local que otros flujos; no hay rol. PWA no tiene parser ni borrador offline. | Pendiente. Aceptación: frases inequívocas completan campos esperados; ambiguas quedan sin asignar; editar y descartar no persiste; confirmar guarda una vez. | Pendiente. |
| Revisión documental e historial | Revisor/operador; diálogo de navegador, adaptable. Sin rol técnico hoy. | Cambiar fecha/OS, cantidad, cultivo, nota, personal/estado/cantidad/horas/máquina/lecturas e insumos. Resultado: snapshot anterior y nueva versión; estados Borrador/Corregido y luego Revisado. | Guardado atómico. Verifica que las líneas no hayan cambiado desde que se abrió; cantidades positivas/no negativas, ausente sin cantidad, suma asignada, lecturas válidas. Revisar incrementa versión PDF y limpia datos de envío; corrección de enviado conserva historial y exige nueva revisión. | Streamlit local no distingue rol. Arquitectura PWA limita revisión al admin; falta decidir permisos de borrador propio. | Sin revisión, edición ni historial. Aceptación: snapshot antes/después fiel; error no aplica cambios parciales; corregido no usa PDF anterior. Definir roles. | Pendiente. |
| PDF, preparación y envío WhatsApp | Operador/revisor; móvil comparte archivo, PC descarga y usa WhatsApp Web. | Parte revisado, destinatario y plantilla. Resultado: PDF vigente, archivo compartido/descargado y mensaje con ID/fecha; confirmación explícita registra hora, destinatario, canal y usuario. Mis partes permite volver a descargar/reenviar. | PDF final solo Revisado/Enviado. Preparar no marca enviado. Confirmar envío es una acción separada. Corregir limpia el envío vigente y requiere generar nueva versión; el historial se conserva. Error al construir PDF aparece en pantalla. | Streamlit local sin roles; preferencias por código local. PWA aún no genera documento ni envía. | Pendiente. Aceptación: PDF coincide con versión aprobada, versión identificable, preparar no confirma, confirmar deja registro único y reenvío conserva historia. | Pendiente. |
| Mis partes enviados | Autor según código configurado; PC o móvil. | Lista solo documentos Enviado cuyo `created_by` coincide con código local; buscar por ID/finca/lote/tarea, rango de fechas; abrir detalle, PDF y reenviar. Resultado: documento enviado y datos de cada línea. | Sin documentos/coincidencias muestra estado vacío. No enviado se ve en Partes y avance. Error de bundle/PDF se informa. Filtro depende del código editable, no de identidad verificada. | No es control de acceso: se puede cambiar el código. PWA aún no tiene lista. | Pendiente. Aceptación: la lista devuelve reportes que permite la política de cuenta decidida; búsqueda/fechas y detalle coinciden; parte enviado sigue sumando al ciclo. Definir si “Mis” es autoría o equipo. | Pendiente. |
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
