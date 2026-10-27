# Plan: Casa 24 Wordle como Discord Activity

> Estado: **consulta y plan, sin implementar**. Escrito el 2026-10-27.
> Objetivo: que el juego funcione también **dentro de Discord**, con **un solo repo, un solo despliegue y un solo código de juego**. Lo que se arregle en la web debe quedar arreglado también en Discord.

---

## 0. Cómo retomar este plan
1. Lee primero estas skills del repo (`.claude/skills/`):
   - `casa24-wordle`: mapa del proyecto y flujo del juego.
   - `casa24-leaderboard`: login de Discord, datos, anti-trampa, rutas y base de datos.
   - `casa24-deploy`: Vercel, variables y GitHub → producción.
   - `casa24-responsive`: layout y rendimiento. Aquí está pendiente compilar Tailwind.
   - `casa24-decisions`: decisiones ya tomadas; no las reabras.
2. Revisa la sección **6 (Decisiones pendientes)**. Si no hay respuestas, pregúntaselas al dueño antes de escribir código.
3. Vuelve a verificar la documentación de Discord (sección 9). Cambia seguido: en julio de 2025 cambió el proxy y en octubre de 2026 llegaron las previsualizaciones de enlaces.
4. Empieza por la **Fase 0** y trabaja en una rama (por ejemplo `discord-activity`). Haz commit tras cada paso y despliega solo previews hasta la Fase 4.
5. Las reglas del dueño siguen vigentes:
   - explicar en lenguaje simple;
   - cambios pequeños;
   - ningún secreto en el chat ni en archivos;
   - producción solo con su OK;
   - usar varios agentes en paralelo cuando ayude;
   - actualizar las skills al terminar.

---

## 1. Estado actual del proyecto (2026-10-27)
- **Stack:**
  - Flask (`webapp/app.py`) y Vue 3.5.13 desde `cdn.jsdelivr.net`, compilando templates en el navegador.
  - Tailwind Play CDN (`cdn.tailwindcss.com`).
  - No hay paso de build. Las fuentes (VT323) e imágenes (WebP de Kolo) son locales.
- **Hosting:**
  - Vercel, equipo **Casa 24** (scope `casa-24`), proyecto `casa24-wordle`.
  - Producción en **https://casa-24-wordle.vercel.app**.
  - GitHub `casa24records/CASA24WORDLE`: `main` se publica solo en producción; las otras ramas generan previews `casa24-wordle-git-<rama>-casa-24.vercel.app`.
- **Modos:**
  - **Invitado:** las 10 lenguas, partida y estadísticas solo en localStorage.
  - **Leaderboard** (es/en): login de Discord OAuth2 con scope `identify`, por redirección.
    - Cookie firmada `c24_lb`, que solo contiene el ID de Discord: HttpOnly, Secure, SameSite=Lax, 30 días.
    - En este modo el servidor colorea cada intento (`POST /api/guess`) y la palabra nunca llega al navegador.
- **Datos:**
  - Base Neon Postgres `casa24-wordle-db`, con las tablas `wordle_players`, `wordle_results`, `wordle_games` y `wordle_rate`.
  - Solo se guardan `discord_id`, `username` y los resultados.
  - El token se descarta tras leer `/users/@me`.
  - El avatar viaja solo al navegador del jugador (`#dc=<hash>`, que se guarda en localStorage `c24_dc_avatar`).
- **Variables de entorno** (solo nombres): `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `SECRET_KEY`, `DATABASE_URL` (más los `PG*`/`POSTGRES_*` de Neon), `DEMO_PASSWORD` y, opcional, `ADMIN_DISCORD_IDS`.
- **App de Discord actual:** "Casa 24 Wordle", Client ID `1564412150519169067`. Solo OAuth2, sin bot ni Activities. Tiene 3 Redirects: producción, preview de rama y `http://127.0.0.1:5050`.
- **Pruebas:** unas 180 (pytest + Playwright), con Discord simulado y la base en memoria (`MemoryStore`).

---

## 2. Recomendación
1. **Discord Activity con el Embedded App SDK (`@discord/embedded-app-sdk`) y sin bot.** Es la única forma documentada de *jugar dentro* de Discord. Al activar Activities, Discord crea solo el comando "Launch" (Entry Point).
2. **Mismas páginas y mismo despliegue.** Se detecta la Activity por `frame_id` + `instance_id` + `platform` en la URL, y **solo entonces** se carga el SDK. La web no cambia.
3. **Login en Discord:** el SDK llama a `authorize` (solo `identify`), luego un nuevo endpoint `/api/activity/token` reutiliza `exchange_code` + `fetch_me`, y al final el SDK llama a `authenticate`. La sesión viaja en un **encabezado firmado** (el mismo dato que hoy va en `c24_lb`), no en cookies.
4. **Servir Vue, Tailwind (compilado) y el SDK desde `/static`.** Discord bloquea los CDN externos. Además, esto acelera la web.
5. **Una segunda app de Discord "de pruebas"** apuntando a un preview. La app real apunta solo a producción.

### Alternativas consideradas
| Opción | Pros | Contras |
|---|---|---|
| **Activity (recomendada)** | Se juega dentro de Discord; sin bot; mismo código | Proxy y CSP de Discord, login distinto, hay que servir todo localmente |
| Solo enlace / **previsualización de enlace** (`discord:component-embed`, changelog del 5 de octubre de 2026) | Cero infraestructura, sin app ni bot; bonito para compartir el puzzle del día | No se juega dentro de Discord |
| Bot con comandos/botones (`LAUNCH_ACTIVITY` o publicar resultados) | Comandos tipo `/wordle`, publicar resultados | Necesita un endpoint de interacciones; más mantenimiento. Se puede sumar después |

---

## 3. Hechos verificados en la documentación oficial (2026-10-27)
- **Activity:** "Activities are web apps hosted in an iframe that use the Embedded App SDK to communicate with Discord clients."
  - Se lanza desde el **Entry Point command**, que se crea solo y se llama "Launch", o respondiendo una interacción con `LAUNCH_ACTIVITY`.
  - No necesita usuario bot. La única excepción es la verificación opcional de instancias, que requiere un *Bot token*.
- **El SDK no funciona fuera de Discord:**
  - Su constructor lanza un error si faltan `frame_id`, `instance_id` o `platform` (`desktop`/`mobile`).
  - La guía dice: "Once you add the SDK to your app, you will not be able to view your app inside your web browser."
  - Existe `DiscordSDKMock` para pruebas.
- **Flujo de auth:**
  1. `authorize({client_id, response_type:'code', state:'', prompt:'none', scope:[...]})`.
  2. El cliente hace POST del `code` a nuestro backend.
  3. El backend hace POST a `https://discord.com/api/oauth2/token` con `client_id`, `client_secret`, `grant_type=authorization_code` y `code`, **sin `redirect_uri`** (así lo hacen los ejemplos oficiales).
  4. El cliente llama a `authenticate({access_token})`.
  - El Portal igualmente pide un Redirect; la guía sugiere `https://127.0.0.1` como marcador.
- **Scopes:**
  - El ejemplo mínimo oficial usa solo `['identify']`. El tutorial pide además `guilds` y `applications.commands`, pero **no son obligatorios**:
    - `guilds`: canales y servidores (`getChannel`, `/users/@me/guilds`).
    - `applications.commands`: necesario si quieres **User Install** (que la Activity te siga a cualquier servidor o DM).
    - `rpc.activities.write`: solo para el "rich presence" (`setActivity`).
    - `guilds.members.read`: apodos y permisos en el servidor.
- **El token llega al cliente:** `authenticate` lo exige en el navegador. No hace falta guardarlo en el servidor.
- **Proxy:**
  - Todo pasa por `https://<client_id>.discordsays.com`. El prefijo `/.proxy/` ya no es obligatorio (changelog del 30 de julio de 2025).
  - Para dominios externos se usan **URL Mappings** más `patchUrlMappings`.
- **CSP:** se bloquea todo lo externo excepto `discord.com/api/` y `cdn.discordapp.com` / `media.discordapp.net` en `/attachments/`, `/avatars/` y `/icons/`.
  - `cdn.discordapp.com/embed/avatars/` (avatares por defecto) **no está en la lista**.
- **Cookies en el iframe:** el dominio debe ser `{clientId}.discordsays.com` y hay que usar `SameSite=None; Partitioned`. Las cookies Lax actuales no llegan.
- **Caché:** el proxy quita las cabeceras de caché de las respuestas `text/html`.
- **URL Mappings:**
  - Están en Activities → URL Mappings. La raíz `/` va al HTML; el destino se escribe sin `https://`, puede llevar ruta pero debe ser un directorio, y los prefijos largos van antes que los cortos.
  - Patrón recomendado: una app de Discord por entorno ("development-only application").
- **Distribución:**
  - "Launching a non-distributed Activity is limited to you or members of the developer team."
  - Para Discovery pública se exige verificación de identidad y de la app, y luego Discovery Status/Settings. Puede tardar hasta 24 h.
- **Móvil:**
  - Hay que marcar iOS y Android en Activities → Settings → Supported Platforms; si no, solo aparece en web y escritorio.
  - Hay bloqueo de orientación en el Portal y en el SDK: `setOrientationLockState`.
  - Modos de layout: focused, picture-in-picture y grid (`subscribeToLayoutModeUpdatesCompat`).
  - Márgenes seguros: `--discord-safe-area-inset-*`.
- **Otros:**
  - No hay WebRTC.
  - Una IP de servidor cambiante (como la de Vercel) puede heredar un bloqueo de Cloudflare; la guía sugiere una IP estática para llamar a la API de Discord.

### No verificado (hay que comprobarlo en la práctica)
- Si **miembros normales de un servidor** (que no son del equipo) pueden abrir la Activity tras instalarla en ese servidor, **sin** verificación ni Discovery. El artículo del centro de ayuda "How Can Users Discover and Play My Activity" no se pudo leer automáticamente.
- Qué `Host`, `Origin` y `X-Forwarded-Host` llegan exactamente a Vercel a través del proxy de Discord. Esto afecta a la revisión "mismo origen".
- Si `localStorage` funciona de forma estable dentro de la Activity. Se asume que está particionado o que no es confiable.
- Si `getActivityInstanceConnectedParticipants` funciona antes de `authenticate`. No lo necesitamos.

---

## 4. Qué rompe hoy dentro de Discord (auditoría del código)
| Tema | Dónde | Problema en la Activity | Arreglo |
|---|---|---|---|
| CDN externos | `index.html`, `game.html` (Tailwind Play CDN, Vue en jsdelivr) | Bloqueados por la CSP | Servir desde `/static/vendor/` y compilar Tailwind (también mejora la web) |
| Avatares por defecto | `_discord.html` (`cdn.discordapp.com/embed/avatars/N.png`) | Ruta no permitida | Círculo genérico local dentro de la Activity |
| Cookies `c24_lb`, `c24_oauth`, `session` (Developer view), `keyboard_layout_<lang>` | `app.py` (`_set_lb_cookie`, login, demo, ruta de idioma) | Lax no viaja en un iframe de otro sitio | Sesión por encabezado `Authorization: Bearer <session firmada>`; la cookie sigue igual para la web |
| Revisión "mismo origen" | `app.py` `_same_origin` (logout, `/api/guess`, delete, admin hide) | El origen será `<id>.discordsays.com`, así que daría 403 | Permitir `<DISCORD_CLIENT_ID>.discordsays.com` |
| Login por redirección | `app.py` `/auth/discord/login` y `discord_auth.authorize_url` (`prompt=none`) | No se puede navegar a discord.com dentro del iframe | En la Activity: SDK `authorize`/`authenticate` + `/api/activity/token` |
| Clave de guardado de la partida | `game.js` (`saveToLocalStorage`/`loadFromLocalStorage` usan `href.substring(lastIndexOf('/')+1)`, que incluye la query) | Los parámetros `?frame_id=…` cambian la clave en cada lanzamiento, así que se pierde la partida | Usar solo `location.pathname`. **Este arreglo sirve también en la web** |
| `replaceState` | `index.js` (limpia `?login=`) y `_discord.html` (`#dc=`) | Podría borrar `frame_id`/`instance_id` | Conservar la query |
| Compartir | `game.js` (`navigator.share`/clipboard, texto con `window.location.origin`) | Bloqueado o limitado; daría un enlace de discordsays | Siempre la URL pública; en la Activity, copiar al portapapeles o SDK `openExternalLink` |
| `confirm()` | `_discord.html` ("Borrar mis datos") | Puede estar suprimido en el iframe | Diálogo propio |
| Navegación al login | `game.js` (redirige a `/auth/discord/login` en un 401) e `index.js` (reescribe enlaces `[data-dc-login]`) | No sirve en la Activity | `C24Activity.login()` |
| Cabeceras | `app.py`, `vercel.json` | No hay `X-Frame-Options` ni CSP (bien) | Ninguno. **No añadir `X-Frame-Options: DENY`** en el futuro |

Piezas que **se reutilizan** tal cual:
- `discord_auth.exchange_code(code, redirect_uri)`, haciendo `redirect_uri` opcional;
- `discord_auth.fetch_me(token)`;
- `lb_store().upsert_player(id, username)`;
- `_serializer("c24-lb")`, para firmar la sesión;
- `/api/guess` y toda la lógica de puntos, rachas y ranking;
- `lb_enabled()`;
- los templates y el parcial `_discord.html`.

---

## 5. Diseño propuesto (capa fina de "Discord")
```
webapp/
  static/
    discord-activity.js     NUEVO: detecta el entorno, crea el SDK, ready(), login, expone window.C24Activity
    vendor/
      vue.global.prod.js    NUEVO (antes venía de jsdelivr)
      embedded-app-sdk.mjs  NUEVO (build ESM del SDK, versión fijada)
    tailwind.css            NUEVO (compilado; reemplaza el Play CDN)
  templates/_discord.html   + macro activity(): incluye discord-activity.js solo si C24_ACTIVITY
  app.py                    + flag `activity` (los 3 params), POST /api/activity/token,
                              sesión por encabezado en lb_player_id(), origen discordsays permitido
  discord_auth.py           exchange_code con redirect_uri opcional
  static/game.js            fetch con Authorization si hay C24Activity.session; login vía C24Activity;
                              compartir; clave de guardado = pathname
  static/index.js           ocultar login/logout en la Activity; diálogo en vez de confirm()
tests/test_activity.py      NUEVO: token endpoint (Discord simulado), sesión por encabezado,
                              origen permitido, nada de token/avatar guardado, web intacta
```

### Flujo de login dentro de Discord
1. La página carga con `?frame_id&instance_id&platform`. El servidor pone `C24_ACTIVITY=true`.
2. `discord-activity.js` crea `new DiscordSDK(CLIENT_ID)` y espera `ready()`.
3. Llama a `authorize({client_id, response_type:'code', state:'', prompt:'none', scope:['identify']})` y recibe `code`.
4. Hace `POST /api/activity/token {code}`. El servidor:
   1. cambia el código por el token (sin `redirect_uri`);
   2. lee `/users/@me` y se queda solo con id y username;
   3. hace `upsert_player`;
   4. responde `{access_token, session}`, donde `session` es el mismo token firmado que la cookie `c24_lb`.
5. El cliente llama a `authenticate({access_token})` y luego descarta el token.
6. Guarda `session` **solo en memoria** (`C24Activity.session`).
7. `/api/guess` y demás llamadas envían `Authorization: Bearer <session>`. El servidor acepta la cookie (web) **o** el encabezado (Activity).

**Privacidad:** se mantienen las mismas reglas.
- Solo `identify`.
- Se guardan únicamente el ID y el nombre de usuario.
- El token no se guarda en ningún sitio (ni en la base, ni en logs, ni en localStorage).
- No hay avatar en la base. Dentro de Discord se puede mostrar un círculo genérico o el avatar que dé el SDK, solo en pantalla.

---

## 6. Decisiones pendientes (preguntar al dueño)
1. **¿Se pueden descargar y guardar en el repo** Vue, el SDK de Discord y el compilador de Tailwind? El sistema de seguridad bloqueó antes descargar y ejecutar binarios, así que hace falta el OK explícito o que lo haga el dueño. Sin esto, la Activity no carga.
2. **¿User Install?** Que se pueda abrir en cualquier servidor o DM implica pedir también `applications.commands`. La otra opción es solo **Guild Install**, en servidores donde se instale.
3. **¿Partida individual o compartida?** Lo compartido, como ver el progreso de los demás en la llamada, es otro proyecto.
4. **¿Modo invitado dentro de Discord?** Recomendación: no. Dentro de Discord todos juegan con su cuenta y cuentan para el ranking.
5. **¿Quién es el dueño del Team de Discord** (para la verificación) y **qué servidor de pruebas** usamos?

---

## 7. Plan por fases ("cómo sé que funcionó")
**Fase 0. Preparar la web, sin Discord todavía (rama `discord-activity`):**
1. Servir `vue.global.prod.js` y el SDK desde `/static/vendor/` y compilar Tailwind a `/static/tailwind.css`. Todo pasa por `asset()` y los tests de `?v=`.
2. Arreglar la clave de guardado (`pathname`) y los `replaceState` para que conserven la query.
3. Añadir el flag `C24_ACTIVITY` (servidor y página).
- ✔ Todas las pruebas pasan y la web se ve igual (revisar capturas).
- ✔ `/es?frame_id=x&instance_id=y&platform=desktop` no pide nada fuera de nuestro dominio. Comprobarlo con Playwright mirando las peticiones.

**Fase 1. "Hola Discord" (app de pruebas + preview):**
1. El dueño hace los pasos manuales 1–7.
2. `discord-activity.js` carga el SDK solo en la Activity y llama a `ready()`.
3. Jugar como invitado dentro de Discord.
- ✔ Desde el App Launcher del servidor de pruebas se abre el juego en escritorio y se puede terminar una partida.

**Fase 2. Login dentro de Discord:**
1. `/api/activity/token` y `exchange_code` con `redirect_uri` opcional.
2. Sesión por encabezado en `lb_player_id()`.
3. Origen `discordsays` permitido.
4. Hacer `authorize` y `authenticate` en el cliente.
- ✔ Juegas en Discord en modo leaderboard y apareces en `/leaderboard` de la web con el mismo usuario.
- ✔ `tests/test_activity.py` confirma que no se guarda token ni avatar y que la web sigue igual.

**Fase 3. Pulir dentro de Discord:**
1. Compartir.
2. Diálogo propio en lugar de `confirm()`.
3. Ocultar login y logout.
4. Móvil: orientación vertical, picture-in-picture, `--discord-safe-area-*` y tamaños.
- ✔ Funciona en escritorio y en el teléfono (iOS y Android) y nada se tapa, con las mismas medidas que la skill `casa24-responsive`.

**Fase 4. Distribución y producción:**
1. Instalar la app de pruebas en el servidor de Casa 24 y probar con una cuenta que **no** sea del equipo.
2. Si no puede abrirla, hacer la verificación (Developer Portal → App Verification).
3. Con el OK del dueño:
   - activar Activities en la app real;
   - URL Mapping `/` → `casa-24-wordle.vercel.app`;
   - merge a `main`.
- ✔ Un miembro normal de Casa 24 abre el Wordle desde el App Launcher y su resultado aparece en el ranking de la web.

**Tamaño:** unos 14 pasos pequeños en 5 fases. Al terminar, crear la skill `casa24-discord-activity` y actualizar `casa24-leaderboard`, `casa24-deploy` y `casa24-wordle`.

---

## 8. Pasos manuales del dueño (en orden, con nombres de pantallas)
1. **Discord Developer Portal → Teams → New Team.** Crear "Casa 24" y asignarle la app (o crear las apps dentro del Team). Así otros del equipo pueden lanzar la Activity mientras no esté distribuida.
2. **Applications → New Application:** "Casa 24 Wordle (dev)", la app de pruebas.
   - **OAuth2:** copiar el **Client ID**; **Reset Secret** y copiar el secreto (no pegarlo en el chat).
   - **Redirects:** añadir `https://127.0.0.1` (marcador que pide la guía).
3. **Activities → Settings** (app de pruebas):
   - marcar **Enable Activities**;
   - **Supported Platforms:** web/escritorio, **iOS** y **Android**;
   - **Default Orientation Lock:** Portrait.
4. **Activities → URL Mappings:** PREFIX `/` → TARGET `casa24-wordle-git-discord-activity-casa-24.vercel.app` (preview de la rama; sin `https://`).
5. **Installation → Installation Contexts:** **Guild Install**. Añadir **User Install** solo si en la decisión 2 se elige que sí.
6. **Vercel → casa24-wordle → Settings → Environment Variables**, marcando **solo Preview**: `DISCORD_CLIENT_ID` y `DISCORD_CLIENT_SECRET` de la app *de pruebas*. Las de producción no se tocan.
7. **App de Discord → User Settings → Advanced → Developer Mode** encendido. Abrir el **App Launcher** (🚀) en un canal de voz o de texto del servidor de pruebas y lanzar "Casa 24 Wordle (dev)".
8. **Al final, en la app real "Casa 24 Wordle":** repetir los pasos 3–5 con el URL Mapping `/` → `casa-24-wordle.vercel.app`. Para Discovery pública: **App Verification**, y luego **Discovery → Discovery Status / Settings**.

---

## 9. Riesgos (de mayor a menor)
1. **CDN bloqueados:** necesitamos Vue, el SDK y Tailwind servidos localmente, y para eso hace falta permiso de descarga.
2. **Distribución:** no está confirmado que miembros que no son del equipo puedan abrirla sin verificación.
3. **Sesión por encabezado:** es un cambio delicado del login; requiere pruebas y no puede romper la cookie de la web.
4. **Proxy, `Host`/`Origin` y la revisión de origen:** hay que verificarlo en el primer preview.
5. **localStorage particionado:** las estadísticas de invitado de Discord y de la web van por separado. El ranking no se ve afectado porque vive en el servidor.
6. **Compartir, `confirm()` y avatares por defecto** están limitados en el iframe.
7. **Móvil:** layouts picture-in-picture y grid, y márgenes seguros.
8. **Bloqueo de Cloudflare** por la IP cambiante de Vercel al llamar a la API de Discord. Es poco probable; vigilarlo.
9. **La documentación de Discord cambia seguido:** reverificar antes de cada fase.

---

## 10. Fuentes (consultadas el 2026-10-27)
Todas las URL `discord.com/developers/docs/...` redirigen (301) a `docs.discord.com/developers/...`.
- Overview: https://docs.discord.com/developers/activities/overview
- Cómo funcionan: https://docs.discord.com/developers/activities/how-activities-work
- Tutorial: https://docs.discord.com/developers/activities/building-an-activity
- Guías de desarrollo: https://docs.discord.com/developers/activities/development-guides (networking, local-development, mobile, layout, production-readiness, user-actions, multiplayer-experience)
- SDK: https://docs.discord.com/developers/developer-tools/embedded-app-sdk y el repo `discord/embedded-app-sdk` (v2.5.0, `src/Discord.ts`)
- Ejemplos: `discord/embedded-app-sdk-examples` (`discord-activity-starter`, server `app.ts`)
- Discovery: https://docs.discord.com/developers/discovery/enabling-discovery
- Changelog: https://docs.discord.com/developers/change-log (30 de julio de 2025: proxy sin `/.proxy/`; 5 de octubre de 2026: link previews `discord:component-embed`; 26 de septiembre de 2024: Activities GA y user installs)
- Ayuda (no se pudo leer automáticamente): "How Can Users Discover and Play My Activity" en support-dev.discord.com
