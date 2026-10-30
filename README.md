# Asistente de parte diario

## Reconstrucción PWA

El trabajo de reconstrucción para PC y móvil está en `pwa/`. El relevamiento funcional está en `docs/relevamiento-funcional.md` y las decisiones técnicas en `docs/arquitectura-pwa.md`.

Para iniciar el frontend: `cd pwa`, copiar `.env.example` a `.env.local`, colocar la URL y la clave publishable del proyecto **Partes Diarios**, luego ejecutar `npm install` y `npm run dev`. No colocar claves secret/service-role en variables `VITE_` ni en el cliente.

La PWA ya permite iniciar sesión, consultar los datos maestros y guardar un parte simple de una tarea en Supabase. Los catálogos maestros ya están cargados; para empezar a registrar partes falta crear y configurar al menos un frente. Todavía no incluye sincronización offline, revisión de partes ni generación de PDF. La guía del estado y próximos pasos está en `docs/arquitectura-pwa.md`.

Aplicación para interpretar y registrar partes diarios agrícolas.

## Inicio

Para ejecutar la versión de escritorio desde este repositorio, instalá Python 3.12 o posterior, creá un entorno e instalá las dependencias:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Colocá los archivos maestros en `datos_fuente\txt` y ejecutá:

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Los archivos maestros, la base SQLite local, el entorno virtual y el runtime portable no se guardan en Git.

Los archivos originales se leen desde `datos_fuente` y no se modifican. Para personal,
maquinaria, operaciones, inventario e insumos, la aplicación usa exclusivamente los
archivos de `datos_fuente\txt`; los Excel y el PDF anteriores quedan ignorados.

## Carga de partes

1. En `Partes y avance`, elegí `Carga parte`.
2. Completá fecha, finca, lote, tarea y cantidad.
3. Seleccioná personal directamente o usá uno o varios frentes configurados.
4. Revisá la distribución automática. Podés ajustar cantidades, ausencias,
   reemplazos y vehículos; redistribuir el saldo; o quitar integrantes.
5. Si corresponde, seleccioná insumo y dosis y revisá la cantidad real del insumo.
6. Pulsá `Guardar parte`.

El primer parte crea el trabajo al guardarse. Los siguientes partes del mismo lote
y tarea se suman al trabajo abierto. El objetivo del lote se propone desde los
datos maestros y puede ajustarse al cargar el primer parte, en `Avance del lote y
objetivo`; si no hay objetivo, se usa la cantidad del parte. Al completar la tarea,
podés finalizarla desde la misma pantalla.

En `Resumen`, la tabla `Parte diario` muestra los partes y el avance del lote,
con personal, vehículos e insumos. Para borrar partes, marcá sus casilleros y pulsá
`Eliminar partes seleccionados`; los acumulados se recalculan.

## Revisión, PDF y envío

1. En `Partes y avance > Resumen`, seleccioná una fila del ID que querés revisar.
2. `Revisar y enviar` permite modificar fecha, orden de servicio, cantidades,
   cultivo, observaciones, personal, vehículos, lecturas e insumos de todas las
   tareas incluidas en ese ID.
3. Pulsá `Guardar y aprobar` y luego `Enviar por WhatsApp` dentro de la misma ventana.
   En celulares se abre el menú nativo para compartir el PDF. En PC el PDF se descarga
   y se abre WhatsApp para adjuntarlo.

`Vista previa` sirve únicamente para comprobar el contenido y `Descargar PDF` permite
guardar una copia aprobada. Al completar el envío, la columna `Estado` cambia a
`Enviado` automáticamente.

El estado del documento (`Borrador`, `Corregido`, `Revisado` o `Enviado`) es
independiente del estado operativo del trabajo (`Abierto` o `Cerrado`). Si se
corrige un documento revisado o enviado, el PDF anterior deja de considerarse
vigente y debe aprobarse una nueva versión.

El número de WhatsApp y el texto sugerido se guardan por usuario en
`Configuración`. El mensaje admite `{id}` y `{fecha}`.

En `Frentes` podés conservar y editar el personal y sus vehículos habituales.
## Carga rápida mediante texto

En `Carga manual`, escribí el parte con nombres o códigos. Por ejemplo:

`Ayer legajo 4, tarea 4510, máquina 2098, finca Luisiana, lote 0501, ocho horas.`

La aplicación prepara `Revisar registro` y completa los datos que puede identificar.
No muestra tablas de coincidencias. Los datos faltantes o ambiguos deben completarse
en la ficha antes de confirmar. Podés revisar la fecha, finca, lote, tarea, cantidad,
personal, frentes, vehículos, reemplazos, insumo, dosis y consumo real.

`Confirmar y guardar parte` guarda el registro y sus distribuciones en la misma base
de datos de `Partes y avance`. La confirmación crea el trabajo si hace falta, o suma
el parte al trabajo abierto. Recargar la pantalla después de guardar no vuelve a
guardar el mismo borrador. `Ver en Partes y avance` abre el resumen.

La interpretación está separada en `quick_entry.py`: recibe texto y genera un
borrador, sin guardar datos. Esa misma entrada puede recibir una futura
transcripción de voz; la captura de voz todavía no está implementada.

Los frentes, trabajos, partes y distribuciones se guardan en `datos_app\asistente.db`.
