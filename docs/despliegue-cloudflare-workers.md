# Publicar la PWA en Cloudflare Workers

El repositorio permanece en GitHub y el Worker sirve el build de produccion de Vite. wrangler.jsonc en la raiz y pwa/wrangler.jsonc cubren los dos directorios raiz posibles de Cloudflare; ambos compilan la PWA y publican dist como assets estaticos con fallback SPA.

## Conectar el repositorio

En Cloudflare Dashboard, abrir Workers & Pages -> partes-diarios -> Settings -> Build y conectar el repositorio osva604-creator/Partes-Diarios, rama main. Se recomienda fijar el directorio raiz en pwa; si Cloudflare usa la raiz del repositorio, tambien esta cubierta por wrangler.jsonc.

Configurar:

| Ajuste | Valor |
|---|---|
| Build command | npm run build |
| Deploy command | npx wrangler deploy |

En Settings → Build → Build variables, definir VITE_SUPABASE_URL y VITE_SUPABASE_PUBLISHABLE_KEY para producción. Vite las incorpora al bundle durante la compilación; las variables de runtime del Worker no reemplazan las variables de build.

La clave publishable/anon se distribuye al navegador por diseño. Las tablas deben permanecer protegidas por RLS. No usar claves service_role ni claves secretas de Supabase en variables VITE_.

Una vez guardados los ajustes, volver a ejecutar el build/deploy. La URL del Worker conserva el subdominio workers.dev; los siguientes pushes a main publican la nueva versión.

## Estado

El sitio existente respondia HTTP 200 pero servia el index.html de desarrollo de Vite (/src/main.tsx); no publicaba los bundles ni el manifiesto de produccion. La configuracion de Wrangler corrige el directorio de assets al build dist. El primer build con la configuracion anidada termino exitosamente, pero la URL publica aun entregaba la version anterior; se agrego configuracion en la raiz para cubrir la raiz efectiva del Worker.
