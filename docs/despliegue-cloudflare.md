# Publicar la PWA en Cloudflare Pages

El código permanece en GitHub. Cloudflare Pages se conecta al repositorio y compila la aplicación cada vez que se actualiza la rama de producción.

## Crear el proyecto

En Cloudflare Dashboard, abrir Workers & Pages → Create application → Pages → Connect to Git y autorizar el repositorio osva604-creator/Partes-Diarios.

Usar esta configuración:

| Ajuste | Valor |
|---|---|
| Rama de producción | main |
| Directorio raíz | pwa |
| Comando de compilación | npm run build |
| Directorio de salida | dist |

En Settings → Variables and Secrets → Build, configurar para producción:

- VITE_SUPABASE_URL: URL del proyecto Supabase.
- VITE_SUPABASE_PUBLISHABLE_KEY: clave publishable/anon del cliente.

La clave publishable se incluye en el JavaScript que descarga el navegador; el acceso a los datos debe seguir protegido por RLS. No configurar claves service_role ni claves secretas de Supabase como variables VITE_.

Guardar y desplegar. Cloudflare asignará una dirección *.pages.dev; se puede añadir un dominio propio desde Custom domains. Los siguientes pushes a main desplegarán automáticamente.

Pages detecta la aplicación React como SPA porque el build no genera un 404.html de nivel superior; las rutas no encontradas sirven la aplicación raíz.

## Estado

La aplicación compila localmente con Vite y está lista para Git integration. La conexión con Cloudflare aún debe crearse desde una cuenta Cloudflare con acceso al repositorio; no hay una sesión ni un token Cloudflare configurado en este entorno.
