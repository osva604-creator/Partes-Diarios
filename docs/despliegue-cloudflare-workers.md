# Publicar la PWA en Cloudflare Workers

El repositorio permanece en GitHub y el Worker sirve el build de producción de Vite. La configuración está en pwa/wrangler.jsonc: compila la PWA y publica pwa/dist como assets estáticos con fallback SPA.

## Conectar el repositorio

En Cloudflare Dashboard, abrir Workers & Pages → partes-diarios → Settings → Build y conectar el repositorio osva604-creator/Partes-Diarios, rama main, con directorio raíz pwa.

Configurar:

| Ajuste | Valor |
|---|---|
| Build command | npm run build |
| Deploy command | npx wrangler deploy |

En Settings → Build → Build variables, definir VITE_SUPABASE_URL y VITE_SUPABASE_PUBLISHABLE_KEY para producción. Vite las incorpora al bundle durante la compilación; las variables de runtime del Worker no reemplazan las variables de build.

La clave publishable/anon se distribuye al navegador por diseño. Las tablas deben permanecer protegidas por RLS. No usar claves service_role ni claves secretas de Supabase en variables VITE_.

Una vez guardados los ajustes, volver a ejecutar el build/deploy. La URL del Worker conserva el subdominio workers.dev; los siguientes pushes a main publican la nueva versión.

## Estado

El sitio existente respondía HTTP 200 pero servía el index.html de desarrollo de Vite (/src/main.tsx); no publicaba los bundles ni el manifiesto de producción. La configuración de Wrangler corrige el directorio de assets al build dist.
