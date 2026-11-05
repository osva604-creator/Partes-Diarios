# Publicar la PWA en Cloudflare Workers

La aplicación web vive en `pwa/`; ese es el único directorio raíz que debe usar la integración Git de Cloudflare. El Worker publica el contenido generado en `pwa/dist`, con fallback para las rutas de la SPA. La configuración de assets está en `pwa/wrangler.jsonc`.

## Configuracion unica

En Cloudflare Dashboard, abrir **Workers & Pages → partes-diarios → Settings → Build** y conectar:

| Ajuste | Valor |
|---|---|
| Repositorio | `osva604-creator/Partes-Diarios` |
| Rama de producción | `main` |
| Directorio raíz | `pwa` |
| Build command | `npm run build` |
| Deploy command | `npm run deploy` |

El directorio raíz es necesario: allí están `package.json`, el lockfile y `wrangler.jsonc`. Cloudflare ejecuta el build command configurado en el Dashboard; Wrangler solo define qué assets publicar. No agregues otro comando de build en Wrangler ni ejecutes el build desde la raíz general del repositorio.

En **Settings → Build → Build variables and secrets**, definir `VITE_SUPABASE_URL` y `VITE_SUPABASE_PUBLISHABLE_KEY`. Esas variables se usan durante el build de Vite y quedan incluidas en el bundle; las variables de runtime del Worker no las sustituyen. Wrangler está fijado en `package.json` y `package-lock.json` para que Cloudflare use la misma versión en cada publicación.

La PWA se conecta directamente desde el navegador al proyecto de Supabase existente. Solo necesita la URL y la clave publishable; no requiere una clave secreta, `service_role`, un binding de Worker ni un segundo proyecto. Las tablas expuestas tienen RLS habilitado.

Después de guardar esta configuración, cada push a `main` compila y publica automáticamente. Para publicar manualmente desde `pwa/`, usar `npm run deploy`.
