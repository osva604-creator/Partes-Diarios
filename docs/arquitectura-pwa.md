# Preparación de arquitectura PWA

## Destino Supabase

- Proyecto: `Partes Diarios`
- Project ref: `dfwslamasfoscxlyzryr`
- Región: `us-east-1`
- URL: `https://dfwslamasfoscxlyzryr.supabase.co`
- Estado al 30/10/2026: proyecto activo; esquema, políticas RLS y RPC de creación atómica verificados en el proyecto conectado.
- Migraciones locales: `20261029192631_initial_agricultural_parts`, `20261029192647_tighten_part_permissions`, `20261029193222_atomic_report_creation`, `20261103185852_fix_report_sequence_rpc_access`, `20261104174243_add_front_management` y `20261104180942_add_front_task_member_management`.

La clave publishable/anon se configura mediante `.env.local`, nunca se copia al código fuente. Nunca usar service-role/secret key en navegador. Las tablas están en `public` con RLS forzado para que la integración con PostgREST funcione con el endpoint estándar.

## Roles iniciales

- `administrador`: mantiene catálogos, administra perfiles, consulta y corrige partes, cierra ciclos y revisa historial.
- `usuario`: carga partes y trabaja con borradores propios; puede consultar partes y avances; configura frentes y preferencias propias/de equipo.
- Los usuarios normales no escriben catálogos ni modifican partes ya revisados/enviados. La UI debe respetar esto además del RLS.
- Todo registro nuevo de Auth recibe el rol `usuario`. Una persona administradora debe promover manualmente la cuenta designada en `profiles.role` tras su alta. La tabla no permite autoasignar permisos desde `user_metadata`.

Las partes son visibles para todos los usuarios activos inicialmente, para que el avance sea compartido; borrado y corrección de documentos quedan limitados al administrador. Revisar si el dueño de un borrador debe poder borrarlo antes del flujo de aprobaciones.

## Stack propuesto

- React + TypeScript + Vite para la aplicación web instalable.
- `@supabase/supabase-js` con lockfile; la versión efectiva queda fijada en `package-lock.json`.
- PWA: Web App Manifest, service worker, assets cacheados y base IndexedDB para borradores/cola offline.
- Supabase Postgres para datos centrales, Auth para sesiones, Storage privado para PDF si se decide persistirlos. RPC transaccional para guardar un parte completo, asignar IDs concurrentes y validar cambios en ciclos.
- PDF generado a partir de una versión revisada e inmutable. Realtime opcional para refrescar avances; UI debe seguir siendo útil sin canal activo.

## Modelo destino (borrador)

Catálogos: `farms`, `lots`, `personnel`, `machines`, `operations`, `inputs` (con clave de negocio de origen y campos maestros tipados); `operation_machine_groups` si se normaliza el grupo.

Operación: `fronts`, `front_members`, `front_task_members`, `work_cycles`, `daily_reports`, `report_tasks`, `allocations`, `part_inputs`, `report_revisions`, `user_preferences`. `organization_id` se agrega a entidades compartidas si hay multi-organización; `created_by`/`updated_by` usan UUID de `auth.users`; códigos visibles de negocio se conservan separados de UUID internos.

`public.create_daily_report` implementa el guardado atómico con clave de idempotencia, secuencia por usuario, creación/reuso de ciclo y escritura de tareas, asignaciones e insumos. El cliente actual ya usa esta RPC para guardar un parte de una tarea. La RPC verifica catálogos activos, cantidades y maquinaria en tareas manuales. Queda pendiente endurecer la concurrencia al asignar un nuevo número de ciclo y validar en servidor que cada persona y maquinaria pertenezca al frente elegido.

## Diferencia entre móvil y escritorio

- **Escritorio:** flujo completo de revisión, tabla densa de avance con filtros/orden, alta múltiple de tareas, edición detallada de personal/vehículos/insumos e historial.
- **Móvil:** PWA simplificada para operación en campo: Inicio, Cargar parte, Mis cargas y Frentes; formulario guiado por pasos cortos con fecha predeterminada, selectores grandes, personal desde frente por defecto, resumen antes de guardar y confirmación visible. Los ajustes avanzados (ausencias, reemplazos, lecturas, distribución manual, varios insumos) quedan en secciones plegables.
- La adaptación es deliberada, no solo CSS: no se muestra la grilla ancha ni herramientas administrativas en móvil normal. Funciones raras siguen accesibles en “Avanzado” para no perder paridad.

## Esqueleto de app

## Estado de implementación

- Implementado: login por correo/contraseña, sesión persistente, lectura de catálogos activos, formulario de una tarea, asignaciones por tarea, modo de cantidad total o individual, distribución igualitaria, guardado en `create_daily_report` y administración inicial de frentes con integrantes y máquina habitual por tarea.
- Maestros cargados en Supabase: 27 fincas, 619 lotes, 299 operaciones, 561 personas, 517 máquinas y 149 insumos; todos están activos. Los dos IDs de lote repetidos (`0010401` y `0201601`) corresponden a variedades distintas del mismo lote: se consolidaron sumando superficie bruta, neta y surcos, y conservando ambas variedades. Nueve equipos con IDs internos repetidos recibieron un `equipment_code` compuesto; sus códigos visibles se conservaron.
- Hay dos frentes ficticios activos de prueba; antes de operar, crear/configurar los frentes reales y sus equipos por tarea (`front_task_members`).
- Pendiente: consulta de partes/avance, carga con varias tareas, ausencias/reemplazos/maquinaria por persona, insumos, borradores y cola offline, revisión documental, PDF y envío.
- El modo sin conexión está limitado al shell cacheado; todavía no se guardan partes offline.
- Para ejecutar localmente: `cd pwa`, copiar `.env.example` a `.env.local`, configurar URL y clave publishable, y usar `npm run dev`. La guía de publicación Cloudflare Pages está en `docs/despliegue-cloudflare.md`; la clave del bundle es publishable y RLS controla el acceso. No incluir claves secret/service-role en el cliente.

