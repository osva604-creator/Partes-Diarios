# Prompt para actualizar la PWA según Asistente de Parte Diario V1.1

Copiar este prompt en Codex con abierto el repositorio **Asistente Parte Diario**.

---

Trabajá en la PWA de este repositorio para incorporar las mejoras funcionales de la versión V1.1 de la aplicación de encargados, manteniendo Supabase como backend de la PWA y respetando autenticación, RLS e idempotencia.

## Carpetas y fuentes

- **Repositorio destino:** `C:\Users\dmoya\Documents\GitHub\Asistente Parte Diario\Asistente Parte Diario`
- **Código fuente V1.1:** `C:\Users\dmoya\Documents\GitHub\Asistente Parte Diario\asistente parte diario V1.1\Asistente Parte Diario\Asistente Parte Diario`
- **Paquete completo V1.1 y catálogos:** `C:\Users\dmoya\Documents\GitHub\Asistente Parte Diario\asistente parte diario V1.1\Asistente Parte Diario.zip`
- Dentro del ZIP, los catálogos nuevos están en `Asistente Parte Diario/datos_fuente/base_datos/`.

Leé primero el `AGENTS.md`, `README.md`, `CONTINUAR_DESARROLLO.md` y `documentacion/RECUPERACION_ASISTENTE_20261103.md` de V1.1, además de `docs/relevamiento-y-paridad-funcional.md` y `docs/arquitectura-pwa.md` del destino. El árbol V1.1 extraído puede no contener `datos_fuente`; en ese caso, inspeccioná las cabeceras y conteos desde el ZIP sin extraer ni mostrar datos personales.

## Estado que hay que preservar

- La PWA actual ya tiene login de Supabase, catálogos activos, carga de una tarea mediante `create_daily_report`, claves idempotentes y administración de frentes/equipos por tarea. Extendé esas piezas cuando corresponda; no las reemplaces.
- Supabase de producción ya existe. Usá migraciones aditivas y conservá reportes, ciclos, asignaciones, historiales, frentes y relaciones existentes. No borres ni recrees tablas o filas.
- El árbol de trabajo puede contener cambios locales recientes en `.gitignore`, `docs/despliegue-cloudflare-workers.md`, `pwa/package.json`, `pwa/package-lock.json`, `pwa/wrangler.jsonc` y la eliminación del `wrangler.jsonc` raíz. Preservalos; no restaures ni sobrescribas esos archivos.
- Cloudflare debe seguir usando `pwa/` como único directorio raíz, `npm run build` y `npm run deploy`. No agregues otra configuración de Wrangler en la raíz.
- No copies `datos_app/asistente.db`, `.env.local`, `.temp`, `.venv`, `runtime`, copias de respaldo ni claves. La app V1.1 usa SQLite local; la PWA debe conservar Supabase Auth y la clave publishable. No pongas `service_role` ni claves secretas en `VITE_`.
- No cambies el usuario autenticado de Supabase por el `current_user` local de V1.1: la PWA debe seguir autorizando por Auth/RLS.

## Diferencias V1.1 verificadas

1. **Ubicaciones y centros TOTVS.** `CentroCosto_Finca_Lote.csv` define 672 ubicaciones seleccionables. V1.1 complementa 614 con datos agronómicos de `Inventario_2026.csv`, mantiene 58 sin esos datos y conserva 5 lotes históricos que ya no ofrece para nuevas cargas. Normaliza ceros iniciales para comparar IDs, pero conserva los identificadores originales y las relaciones históricas.
2. **Catálogos separados y filtros encadenados.** V1.1 compone operaciones, grupos, maquinaria, insumos y avance/dosis desde `Operacion.csv`, `Operacion_Maquinaria.csv`, `Operacion_Insumos.csv`, `Operacion_AvanceDosis.csv`, `CentroCosto_GrupoOperacion.csv` y `GrupoOperacion_Operacion.csv`. La selección sigue centro de costo → grupo → operación → maquinaria/insumos compatibles.
3. **Centro de costo por tarea.** Sugiere el centro TOTVS de la ubicación. Si la persona elige otro, muestra un aviso no bloqueante y registra el centro sugerido y elegido en la instantánea de esa tarea.
4. **Datos agronómicos incompletos.** Permite continuar con un lote sin superficie, surcos o plantación, informa que esos datos faltan y no inventa objetivos ni dosis derivados.
5. **Carga como borrador de varias tareas.** Un parte comparte fecha; permite sumar/quitar tareas, revisar el conjunto y guardar todo atómicamente. No deja cambiar la fecha con tareas cargadas; permite continuar o descartar el borrador.
6. **Partes y avance.** V1.1 mejora el acceso al detalle del parte desde su ID, muestra avance y admite filtros por fechas, finca, lote, tarea, insumo, usuario e ID. En la PWA, el alcance de cada resultado debe respetar las políticas RLS vigentes.
7. **Frentes.** V1.1 facilita modificar una asignación existente por tarea/persona/maquinaria; mantiene historial si se archiva o desactiva un frente.
8. **Revisión y envío.** Se puede corregir un documento revisado, descargar el PDF y compartirlo por WhatsApp en móvil; preparar el envío no equivale a confirmarlo.
9. **Intercambio desde PDF.** V1.1 incorpora en cada PDF un adjunto JSON `parte_diario_v1.json`, esquema `asistente-parte-diario`, versión 1, con tareas, asignaciones, insumos y catálogos usados. Valida datos y tamaño antes de importarlos. El diseño del PDF usa fondo blanco, líneas/texto negros y acentos verdes.
10. **Recuperación segura.** V1.1 detecta una base SQLite dañada y evita reemplazarla automáticamente por una base vacía. No migres su base local: la propia documentación de V1.1 informa una recuperación incompleta del historial.

## Trabajo solicitado

### Fase 1: adaptar el modelo y los catálogos

- Compará el esquema Supabase actual y las migraciones con todos los catálogos de V1.1. Confirmá las cabeceras del ZIP y armá un mapeo documentado de cada campo de origen a `farms`, `lots`, `operations`, `machines`, `inputs` y las relaciones necesarias.
- La tabla `lots` actual tiene 619 registros. Prepará la actualización para reflejar las ubicaciones seleccionables TOTVS sin borrar lotes referenciados por partes anteriores. Conservá el ID interno estable de los lotes coincidentes; agregá una marca explícita para distinguir datos agronómicos disponibles y selección para nuevas cargas. Los 5 históricos deben seguir resolviendo sus referencias y no aparecer en el selector de nuevas tareas.
- Modelá centro/grupo/operación y las relaciones de maquinaria e insumos usando las tablas existentes cuando alcancen; agregá tablas/campos solo si hacen falta. Conservá `source_data` y las claves de negocio originales.
- Actualizá los tipos, consultas y filtros de `pwa/src/App.tsx` para que usen el nuevo modelo, y mantené las reglas manual/mecanizada y compatibilidad por grupo.
- La actualización de catálogos debe ser repetible mediante upsert, validar claves duplicadas y centros/relaciones faltantes, e informar conteos antes/después. No incluyas archivos con datos personales o catálogos completos en el diff del código.

### Fase 2: ubicación y carga operativa

- Agregá centro de costo sugerido/elegido y el aviso no bloqueante; guardá el contexto por tarea con IDs, nombres, origen y `changed` para que el registro histórico no dependa de cambios futuros del catálogo.
- Extendé la RPC `create_daily_report` y el tipo de payload de forma aditiva para guardar contexto de costo, varias tareas y asignaciones/insumos por tarea. Conservá transacción atómica, controles de permisos e idempotencia.
- Implementá en la PWA el borrador de parte con fecha común, varias tareas, agregar/quitar/revisar, bloqueo de fecha mientras haya tareas y descarte explícito. Rechazá duplicar operación+lote en el mismo documento.
- Implementá los modos de cantidad según la semántica de V1.1: total a repartir conserva exactamente el total (incluida distribución entera para `SC`); cantidad individual guarda el valor de cada persona y deriva el total por suma. Ausentes, cantidades fijas, reemplazos, horas y maquinaria no deben perder sus valores.
- La ausencia de superficie/surcos/plantación debe mostrarse sin bloquear una carga válida; no completes objetivos ni dosis con valores inventados.

### Fase 3: consulta, revisión y PDF

- Agregá **Partes y avance** con búsqueda, filtros, detalle desde el ID, tareas, personal, maquinaria, insumos, ciclo, objetivo, acumulado y saldo. Los filtros y acciones deben corresponder al acceso permitido por RLS y al rol.
- Agregá corrección con historial/snapshot; una corrección no puede modificar parcialmente el documento ni dejar vigente un PDF anterior. Mantener separados el estado operativo del ciclo y el documental del parte.
- Implementá PDF descargable/compartible con el estilo V1.1 y adjunto estructurado compatible con `report_exchange.py`. Preparar/descargar/compartir no debe marcar el parte como enviado: el envío se confirma y registra por separado. En móviles usar el mecanismo de compartir disponible y ofrecer descarga como alternativa.
- Si la función de importación no puede validarse de forma segura en esta entrega, implementá primero exportación compatible y documentá la limitación; nunca importes automáticamente un adjunto sin mostrar una vista previa y confirmar.

### Fase 4: dejar el plan sincronizado

- Actualizá `docs/relevamiento-y-paridad-funcional.md` con lo efectivamente implementado y los pendientes reales. No marques paridad completa por tener las tablas creadas.
- Dejá entrada guiada por texto y sincronización offline como etapas separadas si no pueden completarse correctamente ahora. Para el parser, traducí la interpretación de `quick_entry.py`; la interpretación solo prepara un borrador y nunca guarda sin confirmación explícita.

## Supabase y despliegue

- Revisá primero las migraciones, RPC, RLS, grants y tipos existentes. Consultá la documentación actual de Supabase antes de modificar el esquema o la CLI. El proyecto vigente es `Partes Diarios` (`dfwslamasfoscxlyzryr`).
- La actualización del catálogo de producción debe ser aditiva y transaccional, con validación de IDs/relaciones y respaldo o export previo. Prepará un resumen exacto de filas y cambios antes de ejecutar cualquier importación remota; no ejecutes comandos contra otro proyecto.
- No expongas valores de `.env.local` en salidas. Configuración cliente: `VITE_SUPABASE_URL` y `VITE_SUPABASE_PUBLISHABLE_KEY`.
- Conservá la publicación de Cloudflare con raíz `pwa`; no cambies la cuenta ni publiques un Worker durante esta tarea.

## Criterios de aceptación

- Una ubicación TOTVS nueva puede elegirse sin inventar datos agronómicos; un lote histórico conserva su detalle y no se ofrece para una nueva carga.
- Finca/lote/costo sugerido, cambio manual y contexto guardado coinciden con V1.1.
- Un parte con dos tareas se guarda completo o no deja ninguna fila; reintentar la misma clave idempotente no duplica el documento.
- El modo total y el individual generan cantidades/avances correctos; los filtros de detalle respetan RLS.
- Corregir un documento conserva la revisión anterior; el PDF representa la versión vigente y solo la confirmación explícita registra un envío.
- El build de producción termina y se muestran los cambios de esquema/importación claramente separados de los cambios de interfaz. No hagas commit ni push.

Antes de editar, informá un plan corto basado en el diff real. Después implementá y verificá las fases; si un cambio requiere decidir una regla de negocio no documentada, dejá esa decisión señalada y no inventes una regla.
