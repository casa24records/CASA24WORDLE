# Checklist: Casa 24 Wordle como Discord Activity

> Revisado el **2026-10-28** contra la documentación oficial de Discord (`docs.discord.com/developers/...`), el código del SDK `@discord/embedded-app-sdk` 2.5.0 (npm) y los ejemplos oficiales.
> Complementa a la skill `casa24-discord-activity` (el plan original ya está implementado y se borró). Contexto fijo: Flask en Vercel, una sola app "Casa 24 Wordle", `main` = producción, solo `identify`, Guild Install, sin modo invitado dentro de Discord, **login automático** (sin botón), el servidor manda en la partida.
>
> Leyenda: **[DOC]** = dicho por la documentación. **[SDK]** = leído en el código del SDK 2.5.0. **[OBS]** = observado hoy en servidores reales de Discord, no documentado. **[NO VERIFICADO]** = hay que comprobarlo en Discord real.

---

## 0. Sorpresas frente al plan (leer primero)

1. **Los `onclick=` / `onsubmit=` / `onchange=` en el HTML no funcionan dentro de Discord.** [OBS] La CSP real del proxy es `script-src 'self' 'unsafe-eval' 'nonce-…' blob:`. El proxy añade el nonce a los `<script>` en línea (se ve en apps publicadas), pero los atributos de evento **no** aceptan nonce. Hoy los tenemos en: `index.html:96`, `leaderboard.html:55`, `_discord.html:52` (el `confirm` de borrar datos), `game.html:338` (teclado) y `game.html:362` (tema). Hay que pasarlos a `addEventListener`.
2. **Vue que compila plantillas en el navegador sí funciona.** [OBS] La CSP incluye `'unsafe-eval'` (Vue usa `Function()`), y `style-src` incluye `'unsafe-inline'`.
3. **Los avatares por defecto `cdn.discordapp.com/embed/avatars/…` sí cargan como `<img>`.** [OBS] `img-src` permite **todo** `https://cdn.discordapp.com`. La lista de la doc (`/avatars/`, `/icons/`, `/attachments/`) es solo una lista de "excepciones notables" para peticiones. El plan decía lo contrario.
4. **`subscribeToLayoutModeUpdatesCompat` no existe en el SDK 2.5.0** (ni en 3.0.0-beta.3), aunque la página "Layout" lo muestra. [SDK] Usa `discordSdk.subscribe('ACTIVITY_LAYOUT_MODE_UPDATE', fn)`, igual que el ejemplo oficial `sdk-playground/pages/LayoutMode.tsx`.
5. **El SDK no tiene timeouts.** [SDK] `ready()` y cada comando esperan para siempre si Discord no contesta. Un mensaje `CLOSE` de Discord se lee pero **no avisa a la app**. Los timeouts los ponemos nosotros.
6. **El proxy inyecta un script propio** [OBS] que anula `RTCPeerConnection` y `WebTransport` y **bloquea el registro de Service Workers**. No usamos ninguno, pero no hay que añadirlos.
7. **El SDK es "para una sola página" (SPA).** [DOC] "This SDK is intended for use by a single-page application." Nosotros somos multipágina (`/`, `/<lang>`, `/lb/<lang>`, `/leaderboard`). Cada navegación vuelve a cargar el SDK y repite el handshake. Esto no está documentado: hay que minimizar navegaciones y **conservar siempre la query** (`frame_id`…) al navegar. [NO VERIFICADO] que un segundo handshake en el mismo `frame_id` funcione.
   - **RESUELTO (2026-10-29): un segundo handshake tras navegar NO funciona** [SDK]. `getRPCServerSource()` usa `document.referrer` como `targetOrigin`; tras navegar dentro del iframe el referrer es nuestro propio `https://<id>.discordsays.com/…`, el navegador descarta el mensaje y `READY` nunca llega (era el error "No pudimos conectar"). `location.reload()` sí conserva el referrer. **Solución aplicada: diseño "shell"** (el patrón que recomienda Discord, ejemplo oficial `nested-messages`): `/` sirve `activity.html` sin redirección, que crea el SDK **una sola vez** y **nunca navega**; el juego va en un iframe del mismo origen `/lb/<lang>?embed=1` sin parámetros de Discord y sin SDK (`discord-activity.js` usa la sesión del padre). Mensajes entre ambos: solo objetos, nunca arrays; se comprueban `origin` y `source`. Detalles: skill `casa24-discord-activity`.
8. **La primera vez, Discord muestra un modal de permiso** aunque se use `prompt:'none'` (ver M5). No se puede evitar.
9. **Existe una autenticación opcional del proxy** (`X-Signature-Ed25519`, `X-Signature-Timestamp`, `X-Discord-Proxy-Payload`) para comprobar que una petición pasó por Discord. [DOC] No es obligatoria.
10. **Ya hay SDK 3.0.0-beta** (beta.3 del 2026-10-26). La versión estable es **2.5.0**. Hay que fijar la 2.5.0 y no actualizar sin revisar.

---

## 1. Requisitos obligatorios (MUST)

Formato de cada punto: **Qué** · **Por qué** (cita + URL) · **Cómo lo cumplimos** · **Cómo se verifica**.

### Arranque del SDK

- [ ] **M1. Cargar el SDK solo si están los 3 parámetros, y con `platform` válido.**
  - **Por qué:** [SDK] El constructor lanza `frame_id query param is not defined`, lo mismo con `instance_id` y `platform`, y además `Invalid query param "platform"` si no es `desktop` o `mobile`. [DOC] "When your iframe is loaded within Discord, it will include unique query parameters in its URL." (https://docs.discord.com/developers/activities/how-activities-work)
  - **Cómo:** en `app.py`, el flag `C24_ACTIVITY` es verdadero solo si hay `frame_id`, `instance_id` y `platform ∈ {desktop, mobile}`. En `static/discord-activity.js`, `new DiscordSDK(...)` va dentro de `try/catch`; si falla, se muestra el error de "abre esto desde Discord".
  - **Verificar:** pytest: `/es?frame_id=a&instance_id=b&platform=tv` → no es Activity. Playwright: sin parámetros la web no pide `/static/vendor/discord-embedded-app-sdk-*`.

- [ ] **M2. Esperar `ready()` antes de cualquier comando.**
  - **Por qué:** [DOC] "The `ready()` method of the SDK instance resolves once a successful connection has been established." Después: "After receiving the `READY` payload, your application should perform authorization…" (how-activities-work). [SDK] Llamar a un comando antes del handshake lanza `Attempting to send message before initialization`.
  - **Cómo:** `discord-activity.js`: `await withTimeout(sdk.ready(), 15000)` → `authorize` → token → `authenticate`. El juego no se muestra jugable hasta terminar (ver M10).
  - **Verificar:** Playwright con el SDK simulado (sección 4): el orden de llamadas es `ready, authorize, POST /api/activity/token, authenticate`.

- [ ] **M3. Conservar la query (`frame_id`, `instance_id`, `platform`, `guild_id`, `channel_id`…) en toda la sesión.**
  - **Por qué:** [SDK] El SDK lee `window.location.search` en el constructor de **cada** carga de página. Si una navegación pierde la query, la siguiente página no puede crear el SDK (M1).
  - **Cómo:** `index.js` y `_discord.html` ya conservan la query en `replaceState`. Además, en modo Activity:
    - cualquier enlace o formulario interno (idioma, teclado, tema, `/leaderboard`) añade `location.search`;
    - `/` con parámetros redirige en el servidor a `/lb/<lang>` **manteniendo la query**, para que el jugador entre directo al juego.
  - **Verificar:** test de Playwright que recorre la Activity simulada y comprueba en cada `page.url` que siguen `frame_id` e `instance_id`. Test con pytest de la redirección de `/`.

### Login automático (authorize → token → authenticate)

- [ ] **M4. `authorize` con `client_id`, `response_type:'code'`, `state:''`, `prompt:'none'`, `scope:['identify']`.**
  - **Por qué:** [DOC] Es el ejemplo mínimo oficial (how-activities-work) y la forma del `AuthorizeRequest` (`prompt?: 'none'` es el único valor permitido; https://docs.discord.com/developers/developer-tools/embedded-app-sdk#authorizerequest). El starter oficial (`discord-activity-starter/packages/client/src/main.ts`) usa la misma forma.
  - **Cómo:** `discord-activity.js`. El `client_id` lo inyecta el servidor (`DISCORD_CLIENT_ID`, que es público), nunca el secreto.
  - **Verificar:** test de Playwright que captura los argumentos de `authorize` en el mock y los compara exactamente.

- [ ] **M5. Saber qué ve el jugador la primera vez (modal de permiso).**
  - **Por qué:** [SDK] El JSDoc de `authorize` dice: "If the user does not yet have a valid token for all scopes requested, this command will open an OAuth modal. Once an authorized token is available, it will be returned in the command response." [DOC] "Pop open the OAuth permission modal…" (comentario del ejemplo en how-activities-work). [DOC] "Adding new scopes may prompt an OAuth modal for user permission re-confirmation." [DOC OAuth2] Con `prompt=none`, si el usuario **ya autorizó** esos scopes, se salta la pantalla (https://docs.discord.com/developers/topics/oauth2).
  - **Qué significa:** la **primera vez** Discord muestra su modal de autorización. `prompt:'none'` **no lo evita**. En los siguientes lanzamientos no aparece mientras la autorización siga vigente.
    - Inferencia [NO VERIFICADO]: como es la misma app que la web, quien ya entró con Discord en la web con `identify` probablemente no vea el modal.
    - El texto exacto del modal no está en la documentación. [NO VERIFICADO]
  - **Cómo:** no pedir nunca más scopes que `identify`, porque añadir uno vuelve a mostrar el modal a todos.
  - **Verificar:** manual en Discord (sección 3, punto V3).

- [ ] **M6. Si el jugador rechaza o cierra el modal, mostrar un mensaje claro y la opción de reintentar.**
  - **Por qué:** [SDK] Un comando rechazado llega como error `{code, message}` (evento `ERROR` con nonce → `reject`). [DOC] El código `5000` es "OAuth2 error … check the data object" (https://docs.discord.com/developers/topics/opcodes-and-status-codes#rpc-rpc-error-codes). El código exacto al **cancelar** no está documentado. [NO VERIFICADO]
  - **Cómo:** `discord-activity.js` captura cualquier error de `authorize` y muestra: "Para jugar en Discord necesitamos tu permiso (solo tu nombre de usuario). [Intentar de nuevo]". Ese botón es la **única** excepción a "sin botón de login": solo aparece tras un rechazo y vuelve a llamar a `authorize`. Hay que confirmarlo con el dueño. No hay modo invitado.
  - **Verificar:** mock con `authorize` que rechaza `{code:5000}` → aparece el mensaje y el botón. Al pulsarlo con un mock que acepta, entra al juego.

- [ ] **M7. Canje del código en el servidor, sin `redirect_uri`.**
  - **Por qué:** [DOC] El tutorial y los dos servidores oficiales (`getting-started-activity/server/server.js` y `discord-activity-starter/packages/server/src/app.ts`) envían a `https://discord.com/api/oauth2/token`, como `application/x-www-form-urlencoded`, solo `client_id`, `client_secret`, `grant_type=authorization_code` y `code`. "While setting up a Redirect URI is required, the Embedded App SDK automatically handles redirecting users back to your Activity" → en el Portal basta un marcador `https://127.0.0.1` (https://docs.discord.com/developers/activities/building-an-activity). Para Casa 24 ya existen redirects reales, así que no hace falta añadir el marcador.
  - **Cómo:** `discord_auth.exchange_code(code, redirect_uri=None)`. Si es `None`, **no** se envía el campo (hoy siempre lo envía). Nuevo `POST /api/activity/token`:
    1. canjea el código y llama a `fetch_me`;
    2. hace `upsert_player`;
    3. responde `{access_token, session}`.
    - No guarda el token y no lo escribe en logs.
  - **Verificar:** pytest con Discord simulado: el cuerpo enviado al token URL **no** contiene `redirect_uri`, y `access_token` no aparece ni en la base ni en los logs.

- [ ] **M8. Llamar a `authenticate({access_token})` en el navegador.**
  - **Por qué:** [DOC] "Authenticate with Discord client (using the access_token)". El tutorial lanza un error si `auth == null`. Sin `authenticate`, los comandos que requieren scope fallan con `4006` (how-activities-work, punto 4).
  - **Cómo:** `discord-activity.js`. Después se borra la variable del token. **No** se usan `auth.user.id` ni `username` para decidir nada (M9).
  - **Verificar:** el test de orden de M2 y un test de que el token no queda en `window`, `localStorage` ni `sessionStorage`.

- [ ] **M9. No confiar en datos del cliente: identidad solo del servidor.**
  - **Por qué:** [DOC] "Do not trust data coming from the Discord client as truth… assume any data coming from the Discord Client could be falsified… contact Discord API directly from your application's server" (https://docs.discord.com/developers/activities/development-guides/networking#security-considerations).
  - **Cómo:**
    - El ID sale de `fetch_me` en el servidor.
    - La sesión es el mismo valor firmado que `c24_lb` (`_serializer("c24-lb")`) y viaja en `Authorization: Bearer`.
    - `lb_player_id()` acepta cookie **o** encabezado.
    - `/api/guess` sigue coloreando en el servidor.
    - Los nombres se muestran con `textContent` o con el escape de Jinja/Vue.
  - **Verificar:** pytest: un `Bearer` con firma falsa da 401, y un `instance_id` o `user_id` en la query no cambia el jugador.

- [ ] **M10. Timeouts propios para `ready()` y para cada comando.**
  - **Por qué:** [SDK] `ready()` espera el evento `READY` sin límite. `sendCommand` guarda la promesa hasta que llega una respuesta con su nonce, sin timeout. Fuera de Discord, `window.parent === window`, así que el handshake se envía a sí mismo y nunca llega `READY`.
  - **Cómo:** en `discord-activity.js`, `withTimeout(p, ms)`:
    - `ready`: unos 15 s;
    - `authorize`: **sin** timeout corto, porque el jugador puede tardar leyendo el modal; como mucho unos 5 min;
    - `authenticate`: unos 15 s;
    - el resto: unos 10 s.
    - Al vencer, se muestra "No pudimos conectar con Discord. Cierra y vuelve a abrir la actividad".
  - **Verificar:** Playwright con un mock cuyo `ready()` nunca resuelve, con el reloj acelerado (`page.clock`): aparece el mensaje.

### Red, proxy y CSP

- [ ] **M11. Todo el HTML, JS, CSS, fuentes e imágenes desde nuestro dominio (rutas relativas).**
  - **Por qué:** [DOC] "Because your application is 'sandboxed', it will be unable to make network requests to external URLs" y "the request will fail with a `blocked:csp` error" (https://docs.discord.com/developers/activities/development-guides/local-development#url-mapping y networking). [OBS] CSP real: `default-src 'self'`, `font-src 'self' data:` (**no** Google Fonts), `connect-src` = nuestro `discordsays` + `discord.com` + `cdn.discordapp.com`/`media.discordapp.net`.
  - **Cómo:** Vue, el SDK (`static/vendor/discord-embedded-app-sdk-2.5.0/`, idéntico a npm 2.5.0) y Tailwind compilado (`static/tailwind.css`) ya son locales, igual que VT323 y Gilroy. Usar siempre rutas relativas (`/api/...`, `asset()`), nunca `https://casa-24-wordle.vercel.app/...`. `patchUrlMappings` **no hace falta**, porque no llamamos a dominios externos.
  - **Verificar:** test "CSP de Discord" de la sección 4 (B): cero violaciones y cero peticiones fuera de la lista.

- [ ] **M12. Nada de JavaScript en atributos de HTML (`on*=`, `javascript:`).**
  - **Por qué:** [OBS] `script-src` con nonce y sin `'unsafe-inline'` ni `'unsafe-hashes'`: el navegador bloquea los manejadores en línea. Los `<script>` en línea sí reciben el nonce del proxy (observado en apps publicadas, no documentado).
  - **Cómo:** quitar los 5 atributos de M0-1 y enlazarlos en `index.js` / `game.js` / `theme.js` con `addEventListener`. Esto también sirve en la web.
  - **Verificar:** pytest que busca `\son[a-z]+="` y `javascript:` en `templates/*.html` y falla si encuentra alguno. Más el test CSP (B).

- [ ] **M13. La revisión de "mismo origen" debe aceptar `https://<CLIENT_ID>.discordsays.com`.**
  - **Por qué:** [DOC] El dominio del proxy es `https://<client id>.discordsays.com` (networking → "Construct A Full URL"). El navegador manda ese `Origin`, pero el `Host` que llega a Vercel será otro. [NO VERIFICADO] qué `Host` y `X-Forwarded-Host` exactos llegan.
  - **Cómo:** `_same_origin()` en `app.py` acepta además exactamente `https://{DISCORD_CLIENT_ID}.discordsays.com`, sin comodines.
  - **Verificar:** pytest con `Origin: https://<id>.discordsays.com` → 200, y `Origin: https://evil.discordsays.com` → 403. Manual: en el primer lanzamiento, registrar (sin datos personales) el `Host` y el `Origin` recibidos.

- [ ] **M14. Sesión por encabezado, no por cookie.**
  - **Por qué:** [DOC] Para usar cookies: "the cookie's domain matches your app's full `{clientId}.discordsays.com` domain… explicitly set `SameSite=None Partitioned`" (networking → Using Cookies). Nuestras cookies son `SameSite=Lax` y no viajan en el iframe.
  - **Cómo:** la sesión vive en memoria (`C24Activity.session`) y se envía como `Authorization: Bearer`. No se tocan las cookies de la web. Las preferencias que hoy usan cookie (`keyboard_layout_<lang>`) van a `localStorage` con `try/catch`, o como parámetro, dentro de la Activity.
  - **Verificar:** pytest: `/api/guess`, `/api/state` y `/api/me/delete` funcionan con el encabezado y sin cookie.

- [ ] **M15. Caché: el HTML no se cachea; los demás archivos necesitan "cache busting".**
  - **Por qué:** [DOC] "Discord's application proxy will remove any cache headers for assets whose `content-type` headers include `text/html`. For all non-`text/html` content… be sure your application has a cache-busting strategy" (https://docs.discord.com/developers/activities/development-guides/production-readiness#cache-busting). [OBS] El HTML del proxy sale con `cache-control: no-store, max-age=0`.
  - **Cómo:** ya tenemos `asset()` con `?v=<hash>` y `immutable` en `vercel.json`.
    - Ojo: los ~70 `.mjs` del SDK se importan entre sí **sin** `?v=`.
    - Basta con que la carpeta lleve la versión (`discord-embedded-app-sdk-2.5.0/`) y no se reescriba nunca. Para otra versión, carpeta nueva.
  - **Verificar:** el test existente de `?v=` cubre `discord-activity.js`. Un test comprueba que la ruta del SDK incluye la versión.

### Portal de Discord (configuración, no código)

- [ ] **M16. Activities activadas y URL Mapping `/` → `casa-24-wordle.vercel.app`.**
  - **Por qué:** [DOC] "The URL for your application's html should be set to the `/` route." El destino va sin protocolo: "do not put `https://your-url.com`". "Targets must point to a directory" (local-development → URL Mapping). Al activar Activities "a default Entry Point command called 'Launch' is created for you" con handler `DISCORD_LAUNCH_ACTIVITY (2)`, que abre la Activity y publica un mensaje en el canal (https://docs.discord.com/developers/activities/development-guides/user-actions#setting-up-an-entry-point-command).
  - **Cómo:** Portal → Activities → Settings (Enable Activities) → URL Mappings. **No** borrar ni cambiar el comando "Launch".
  - **Verificar:** manual (no tenemos bot token para listar comandos por API): basta ver que "Casa 24 Wordle" aparece en el App Launcher con Developer Mode. [OBS] Hoy `https://1564412150519169067.discordsays.com/` responde una página vacía con `sandbox` porque Activities aún no está activo; tras activarlo debe servir nuestro HTML.

- [ ] **M17. Plataformas: marcar iOS y Android.**
  - **Por qué:** [DOC] "By default, your Activity will be launchable on web/desktop. To enable or disable support for Web/iOS/Android… check the appropriate checkboxes" (https://docs.discord.com/developers/activities/development-guides/mobile).
  - **Cómo:** Portal → Activities → Settings → Supported Platforms.
  - **Verificar:** manual: aparece en el App Launcher del móvil.

- [ ] **M18. Quién puede abrirla mientras no esté distribuida.**
  - **Por qué:** [DOC] "Launching a non-distributed Activity is limited to you or members of the developer team" (building-an-activity, Step 2). Para Discovery: "we require your team owner to complete identity and application verification" (https://docs.discord.com/developers/discovery/enabling-discovery).
  - **Cómo:** pasar la app a un Team de Discord. [NO VERIFICADO] si un miembro normal del servidor puede abrirla solo con Guild Install, sin verificación. El artículo de ayuda "How Can Users Discover and Play My Activity" devuelve 403 a lectores automáticos.
  - **Verificar:** manual, Fase 4: una cuenta que no es del Team intenta abrirla.

---

## 2. Recomendaciones (SHOULD)

- [ ] **R1. Orientación: vertical por defecto desde el Portal** ("Default Orientation Lock", que puede ser distinto para teléfono y tablet).
  - **Por qué:** [DOC] "the Discord app will apply the orientation lock when launching the application before the SDK has been initialized… smoother application launch" (https://docs.discord.com/developers/activities/development-guides/layout).
  - **Cómo:** en código, opcionalmente, `setOrientationLockState({lock_state: PORTRAIT})` solo si `sdk.platform === 'mobile'`, porque en la tabla de plataformas web está marcado ⛔️. Va en `try/catch`.
  - **Verificar:** manual en el teléfono.

- [ ] **R2. Márgenes seguros con las variables de Discord.**
  - **Por qué:** [DOC] `--sait: var(--discord-safe-area-inset-top, env(safe-area-inset-top))`, y lo mismo para bottom, left y right (mobile → Mobile Safe Areas). El ejemplo oficial `SafeAreas.tsx` lee los valores "on the next tick" porque al principio pueden ser incorrectos.
  - **Cómo:** en `style.css`, `:root` con las 4 variables y padding del contenedor del juego (también funciona en la web gracias a `env()`).
  - **Verificar:** Playwright: con `--discord-safe-area-inset-bottom: 40px` forzado en `<html>`, el teclado sube 40 px. Manual en un iPhone con notch.

- [ ] **R3. Modos de layout (FOCUSED 0 / PIP 1 / GRID 2).**
  - **Por qué:** [DOC] "Activities can subscribe to the layout mode to determine when to optionally change their layouts" (layout). [SDK] Usar `subscribe('ACTIVITY_LAYOUT_MODE_UPDATE', fn)` con `fn({layout_mode})`, porque el helper "Compat" no existe en 2.5.0.
  - **Cómo:** en PIP o GRID se oculta todo menos el tablero (sin teclado ni modales) y se muestra "Toca para jugar". En `try/catch`: clientes viejos pueden responder `INVALID_EVENT` (4004).
  - **Verificar:** mock: `emitEvent('ACTIVITY_LAYOUT_MODE_UPDATE', {layout_mode:1})` → se añade la clase `c24-pip`.

- [ ] **R4. Comandos nuevos: tolerar `INVALID_COMMAND` (4002).**
  - **Por qué:** [DOC] "When an application tries to use a new command with an old Discord app version… respond with error code `INVALID_COMMAND`" (production-readiness → Backward Compatibility).
  - **Cómo:** todo comando opcional (orientación, `shareLink`, `openExternalLink`) va en `try/catch` y falla en silencio.
  - **Verificar:** un mock que rechaza con `{code:4002}` no rompe el juego.

- [ ] **R5. Compartir dentro de Discord.**
  - **Por qué:**
    - [DOC] `shareLink({message, custom_id?})` "Presents the user with a modal to share a link" en web, iOS y Android, sin scopes. Comparte el enlace **de la Activity** (`discord.com/activities/<id>`), no nuestra web (growth-and-referrals).
    - [DOC] `openExternalLink({url})` abre un modal de confirmación de Discord ("Trust this Domain").
    - `navigator.share` y el portapapeles dentro del iframe [NO VERIFICADO].
  - **Cómo:** en la Activity, el botón Compartir llama a `shareLink` con el texto de cuadritos (sin la palabra). Si falla, copia al portapapeles con `try/catch`. Los enlaces externos usan `openExternalLink` con la URL pública.
  - **Verificar:** mock: `shareLink` recibe el mensaje sin la respuesta. Manual en escritorio y móvil.

- [ ] **R6. Mensajes de la consola: no registrar secretos.**
  - **Por qué:** [DOC] "By default, the SDK will send any console `log`, `warn`, `error`, `info`, and `debug` events triggered by your app to the Discord application" (local-development → Logging).
  - **Cómo:** nunca `console.*` con el token, el código o la sesión. Opcional: `new DiscordSDK(id, {disableConsoleLogOverride: true})`, como el `sdk-playground`.
  - **Verificar:** test que busca `console\.(log|info|warn|error|debug)\(.*(token|session|code)` en `discord-activity.js`.

- [ ] **R7. Límites de velocidad de la API de Discord.**
  - **Por qué:** [DOC] "Be sure network requests made by your application's client and server will be able to respect Discord API's rate limiting" (production-readiness). El starter reintenta ante un 429 esperando `retry_after`. [DOC] IP dinámica: "non-zero chance that you will inherit… an IP address which has been banned by Cloudflare… up-to an hour".
  - **Cómo:** en `discord_auth._request_json`, ante un 429 reintentar **una** vez si `Retry-After` ≤ 5 s. Si no, error claro ("Discord está ocupado, prueba en un minuto").
    - No hay límites documentados para el comando `authorize`. [NO VERIFICADO] La única referencia es el código de cierre RPC `4002 RATELIMITED`.
  - **Verificar:** pytest con Discord simulado que responde 429 y luego 200.

- [ ] **R8. Accesibilidad en escritorio.**
  - **Por qué:** [DOC] "Enable users to cycle through Discord buttons and fields on desktop by pressing TAB… ensuring that the activity does not capture control" y "the ESC key to close any open in-activity modals" (https://docs.discord.com/developers/activities/design-patterns).
  - **Cómo:** en `game.js`, el `keydown` global **no** intercepta Tab ni Escape (Escape cierra nuestros modales).
  - **Verificar:** Playwright: Tab mueve el foco fuera del tablero, y Escape cierra Ayuda y Estadísticas.

- [ ] **R9. Funcionar en canales de texto, sin voz.**
  - **Por qué:** [DOC] "All controls, CTAs, and instructions should be clear enough that folks… playing in a text channel are able to quickly start" (design-patterns).
  - **Cómo:** la ayuda de primera vez ya existe. Se mantiene.

- [ ] **R10. Ciclo de vida: cerrar y volver a abrir = nueva instancia.**
  - **Por qué:** [DOC] "When all the users of an application in a channel leave or close the application, that instance has finished its lifecycle… a new `instanceId` will be generated" (multiplayer-experience). [DOC] Un `[CLOSE, {code, message}]` "indicates an error or a need to restart" (how-activities-work), pero [SDK] el SDK no lo expone.
  - **Cómo:** no guardar nada por `instance_id`. Cada lanzamiento repite el login: `authorize` devuelve el código sin modal y la partida se lee de `/api/state`. Al volver a ser visible (`visibilitychange`) se recarga el estado con `/api/state`; esto ya está en la Fase S. Si el servidor responde 401 dentro de la Activity, se repite `authorize` en silencio una sola vez.
  - **Verificar:** Playwright: dos "lanzamientos" con `instance_id` distinto continúan la misma partida del día.

- [ ] **R11. (Opcional) Verificar que las peticiones vienen del proxy.**
  - **Por qué:** [DOC] Headers `X-Signature-Ed25519`, `X-Signature-Timestamp`, `X-Discord-Proxy-Payload`. "Proxy authentication is entirely optional" (multiplayer-experience → Validating Proxy Request Headers).
  - **Cómo:** no por ahora. La seguridad real es la sesión firmada más el servidor que colorea. Anotar como mejora futura (necesitaría PyNaCl y la Public Key de la app).

- [ ] **R12. Evitar `confirm()` / `alert()` y nuevas ventanas.**
  - **Por qué:** iframe con sandbox: el comportamiento no está documentado. [NO VERIFICADO]
  - **Cómo:** usar un diálogo propio para "Borrar mis datos" (ya está en el plan, Fase 3).

- [ ] **R13. Arte y metadatos del App Launcher.**
  - **Por qué:** [DOC] Cover Art (16:9 y 13:11, ≥1024 px), Embedded Background (16:9, ≥1024 px), vídeo opcional (640×360, mp4, <10 s, <1 MB), Max Participants (vacío = "Unlimited participants") (https://docs.discord.com/developers/activities/development-guides/assets-and-metadata).
  - **Cómo:** Portal → Activities → Art Assets. Es tarea del dueño (skill `casa24-branding`).

---

## 3. Cosas que NO se pueden verificar sin Discord real

| # | Qué comprobar | Cómo hacerlo |
|---|---|---|
| V1 | La Activity carga y llega a `ready()` | Escritorio: User Settings → App Settings → Advanced → **Developer Mode** ON. En el servidor de pruebas, abrir el **App Launcher** (cohete) en un canal de voz o texto y lanzar "Casa 24 Wordle". Logs: en el cliente PTB, `View → Developer → Toggle Developer Tools` → Console. |
| V2 | La CSP real no bloquea nada | Igual que V1: en la Console, buscar `Refused to` / `blocked:csp`. En la pestaña Network no debe haber nada en rojo. |
| V3 | Modal de autorización la primera vez, ninguno después | Con una cuenta que **nunca** autorizó la app: abrir → aparece el modal (anotar su texto exacto) → aceptar → juego. Cerrar y reabrir → sin modal. Repetir con una cuenta que ya entró por la web. |
| V4 | Qué pasa si se rechaza el modal | Pulsar cancelar o cerrar el modal y anotar el `code` y el `message` que llegan (los muestra nuestra pantalla de error en modo debug). Comprobar el botón "Intentar de nuevo". |
| V5 | `Host`, `Origin` y `X-Forwarded-Host` que llegan a Vercel | Vercel → Logs del primer `POST /api/activity/token`. Registrar solo esos 3 encabezados, temporalmente, sin IP ni token. |
| V6 | Navegar entre páginas (re-handshake) | Dentro de la Activity, cambiar de idioma o abrir `/leaderboard` y volver. Ver en la Console que `ready()` vuelve a resolverse. |
| V7 | Móvil: orientación, safe areas, PIP | Móvil: Perfil → Appearance → **Developer Mode** ON. Entrar en un canal de voz y lanzar. Logs: User Settings → DEV ONLY → **Debug Logs**, filtrar por `RpcApplicationLogger` o por el ID de la app. Compartir logs: en el canal de voz, deslizar hacia arriba → **Share Application Logs**. Probar iPhone con notch y Android con botones. Minimizar a PIP y volver. |
| V8 | `localStorage` dentro del iframe | Console: `localStorage.setItem('x','1')`, cerrar, reabrir y leer. Es solo para preferencias; la partida vive en el servidor. |
| V9 | Portapapeles, `shareLink`, `openExternalLink` | Pulsar Compartir en escritorio, iOS y Android. Anotar qué modal sale y si se copia. |
| V10 | Miembro que no es del Team | Fase 4: una cuenta normal del servidor de Casa 24 intenta abrirla (M18). |
| V11 | Que el comando "Launch" existe y publica el mensaje | Lanzar desde el App Launcher y ver el mensaje automático en el canal. |
| V12 | Reconexión | Con la Activity abierta, cortar la red 30 s y volver. El juego debe recargar el estado sin perder intentos (gracias a `attempt`/409). |

---

## 4. Cómo simular Discord en nuestras pruebas

### A. `DiscordSDKMock` (rápido, para la lógica de `discord-activity.js`)
- **Qué hace** [SDK `mock.mjs`]:
  - `new DiscordSDKMock(clientId, guildId, channelId, locationId)`. No necesita query.
  - `ready()` resuelve al instante.
  - Comandos por defecto: `authorize → {code:'mock_code'}`, `authenticate → {access_token:'mock_token', user:{id:'mock_user_id', username:'mock_user_username', …}}`, `setOrientationLockState → null`, `shareLink → {success:false}`, `openExternalLink → {opened:false}`…
  - `_updateCommandMocks({...})` cambia respuestas, por ejemplo para que `authorize` rechace.
  - `emitEvent('ACTIVITY_LAYOUT_MODE_UPDATE', {layout_mode:1})` simula eventos.
  - Cada llamada se registra con `console.info('DiscordSDKMock: …')`.
- **Cómo cargarlo en Playwright sin código de pruebas en producción:**
  - interceptar el módulo del SDK y servir un "shim" que exporta el mock con el nombre `DiscordSDK`;
  - el ejemplo oficial `sdk-playground/packages/client/src/discordSdk.tsx` hace algo parecido: usa el mock cuando no hay `frame_id`.
  ```python
  SHIM = """
  import { DiscordSDKMock } from './mock.mjs';
  export * from './index.real.mjs';
  export class DiscordSDK extends DiscordSDKMock {
    constructor(id){ super(id, 'g1', 'c1', null);
      this.platform = new URLSearchParams(location.search).get('platform') || 'desktop';
      this._updateCommandMocks(window.__C24_MOCKS__ || {}); }
  }"""
  page.route("**/vendor/discord-embedded-app-sdk-2.5.0/index.mjs",
             lambda r: r.fulfill(body=SHIM, content_type="text/javascript"))
  page.route("**/vendor/discord-embedded-app-sdk-2.5.0/index.real.mjs",
             lambda r: r.fulfill(path="webapp/static/vendor/discord-embedded-app-sdk-2.5.0/index.mjs",
                                 content_type="text/javascript"))
  page.add_init_script("window.__C24_MOCKS__ = {}")   # o con authorize que rechaza, etc.
  page.goto(base + "/lb/es?frame_id=f1&instance_id=i1&platform=desktop&guild_id=g1&channel_id=c1")
  ```
  `POST /api/activity/token` va contra Flask con `discord_auth` simulado: `exchange_code`/`fetch_me` con monkeypatch, como en los tests actuales del leaderboard.

### B. Prueba "CSP de Discord" (la más importante)
Repite en Playwright lo que hace el proxy. Esto detecta CDN externos, fuentes externas y `onclick=` en un solo test.
1. **Copiar la CSP real** (observada el 2026-10-28, revisada con las líneas `frame-src`/`child-src` que el proxy ahora envía) con `<origin>` = nuestro servidor de pruebas:
   `default-src 'self'; script-src 'self' 'unsafe-eval' 'nonce-TEST' blob:; style-src 'self' 'unsafe-inline' blob:; img-src 'self' blob: data: https://cdn.discordapp.com https://media.discordapp.net; font-src 'self' data:; connect-src 'self' https://discord.com https://cdn.discordapp.com https://media.discordapp.net data: blob:; media-src 'self' blob: data:; worker-src 'self' blob:; frame-src <origin>/ https://discord.com/embeds/video-frame; child-src <origin>/ blob:`
   - Lo que el proxy real envía (3 Activities públicas: `945737671223947305`, `832012774040141894`, `880218394199220334`) [OBS]:
     ```
     frame-src https://<id>.discordsays.com/ wss://<id>.discordsays.com/ https://discord.com/embeds/video-frame ...;
     child-src https://<id>.discordsays.com/ wss://<id>.discordsays.com/ blob:;
     worker-src https://<id>.discordsays.com/ ... blob:;
     ```
   - Una fuente con `/` final vale para todas las rutas, así que el shell puede enmarcar `/lb/<lang>?embed=1`. El HTML del iframe también pasa por el proxy (su propia CSP y nonce, `no-store`).
   - Nunca enviar `X-Frame-Options` ni `frame-ancestors`: Discord enmarca el shell y el shell enmarca el juego.
   - Implementado en `tests/test_activity.py` (`discord_csp()`, `test_browser_discord_csp`).
2. Con `page.route("**/*")`, para respuestas `text/html` de nuestro origen:
   - hacer `route.fetch()`;
   - añadir el encabezado `Content-Security-Policy`;
   - poner `nonce="TEST"` a cada `<script` **sin** `src`, como hace el proxy.
   - Para cualquier petición cuyo host no sea el nuestro, `discord.com` (`/api/`) o `cdn.discordapp.com`/`media.discordapp.net`: `route.abort()` y anotarla.
3. Antes de cargar, con `page.add_init_script`: `document.addEventListener('securitypolicyviolation', e => (window.__csp ||= []).push(e.violatedDirective + ' ' + e.blockedURI))`.
4. Cargar `/?frame_id=f&instance_id=i&platform=desktop` (el shell) con el mock de A, elegir idioma en el selector, y dentro del iframe `/lb/es?embed=1`: jugar un intento, abrir Ayuda, Estadísticas, ranking y la ventana de idioma, cambiar el tema y el teclado.
5. **Comprobar:** `window.__csp` vacío en el shell **y** en el iframe, cero peticiones abortadas, el tablero se pinta, el intento se colorea y el SDK se creó **una sola vez**.

### C. Emular los parámetros y el handshake real (opcional, más fiel)
- Parámetros: siempre `frame_id`, `instance_id` y `platform` (`desktop` o `mobile`). Para más realismo, también `guild_id`, `channel_id`, `location_id` y `mobile_app_version`.
- **Padre falso con el SDK real (sin mock):**
  - El SDK acepta mensajes del **propio origen** de la página (`ALLOWED_ORIGINS` incluye `window.location.origin`) y responde a `window.parent`.
  - Montar una página de prueba en nuestro origen (con `page.route` sobre una URL como `/__test_parent`) con un `<iframe src="/lb/es?frame_id=…">`.
  - Esa página escucha `message` y responde así:
    - al handshake `[0, {v:1, client_id, frame_id}]` → `[1, {cmd:'DISPATCH', evt:'READY', nonce:null, data:{v:1, config:{api_endpoint:'//discord.com/api', environment:'production'}}}]`;
    - a `[1, {cmd:'AUTHORIZE', nonce, args}]` → `[1, {cmd:'AUTHORIZE', evt:null, nonce, data:{code:'test-code'}}]`;
    - a `AUTHENTICATE`, lo mismo con `data` igual al `authenticate` del mock.
  - Para simular un rechazo: `[1, {cmd:'AUTHORIZE', evt:'ERROR', nonce, data:{code:5000, message:'x'}}]`.
  - Así se prueba el protocolo real del SDK 2.5.0.

### D. Pruebas de servidor (pytest)
- `/api/activity/token`:
  - no envía `redirect_uri`;
  - responde `{access_token, session}`;
  - no guarda el token;
  - con un código inválido responde 400/401 con un error genérico.
- La sesión `Bearer` vale igual que la cookie; si es falsa o caducada, 401.
- `_same_origin` acepta solo `https://<CLIENT_ID>.discordsays.com`.
- Ningún template tiene `on*=` ni URLs externas (escanear `templates/` y `static/*.js`).
- Detección de la Activity: los 3 parámetros y `platform` válido.

---

## 5. Versiones verificadas (leídas el 2026-10-28)

| Qué | Versión / fecha | Nota |
|---|---|---|
| `@discord/embedded-app-sdk` (npm, `latest`) | **2.5.0** (publicado 2026-05-05) | También `beta` = 3.0.0-beta.3 (2026-10-26); **no usar**. Builds: `output/index.mjs` (ESM, ~70 archivos con imports relativos y dependencias **incluidas**: zod, uuid, eventemitter3, big-integer, decimal.js-light, lodash.transform y tslib en `output/lib/`) y `output/index.cjs`. **No hay UMD ni bundle de un solo archivo.** Sin imports externos ni URLs de red en tiempo de ejecución (solo `mock.mjs` cita una imagen de ejemplo). Nuestra copia `webapp/static/vendor/discord-embedded-app-sdk-2.5.0/` es idéntica a los `.mjs` de npm, más `LICENSE.md`. |
| Repo `discord/embedded-app-sdk` | v2.5.0 (release 2026-05-05) | CHANGELOG sin cambios de layout ni timeouts |
| Activities Overview / How Activities Work / Building an Activity | 2026-10-28 | |
| Development Guides: Local Development, Networking, Mobile, Layout, Production Readiness, User Actions, Multiplayer Experience, Growth and Referrals, Assets and Metadata | 2026-10-28 | |
| Activity Design Patterns | 2026-10-28 | |
| Embedded App SDK Reference | 2026-10-28 | La documentación de `subscribeToLayoutModeUpdatesCompat` no coincide con el SDK 2.5.0 |
| OAuth2 (topics/oauth2), Opcodes & Status Codes (RPC error codes), RPC | 2026-10-28 | |
| Application Commands → Entry Point | 2026-10-28 | |
| Enabling Discovery | 2026-10-28 | |
| Change Log (entradas 2025–2026 de Activities/SDK/proxy) | 2026-10-28 | 2025-07-30: sin `/.proxy/`. 2025-08-11: SDK 2.1/2.2 (`patchUrlMappings` sin `.proxy`). 2026-01-21: `relationships.read`. 2026-09-22: verificación de edad (Activities con restricción de edad pueden pedirla; no nos afecta). 2026-10-06: `getInstanceConnectedParticipants` → `getActivityInstanceConnectedParticipants`. 2026-10-14: `iss` en respuestas OAuth2 por redirección (solo web). 2026-10-28: flags de escaneo de contenido (no nos afecta). |
| Ejemplos `discord/embedded-app-sdk-examples` (main) | 2026-10-28 | `discord-activity-starter` (client `main.ts`, server `app.ts` + `utils.ts`), `sdk-playground` (`discordSdk.tsx`, `authActions.ts`, `LayoutMode.tsx`, `SafeAreas.tsx`). `discord/getting-started-activity` `server/server.js` |
| CSP real del proxy | 2026-10-28 | Encabezados de `https://<id>.discordsays.com/` de 4 Activities públicas (`945737671223947305`, `832012774040141894`, `880218394199220334`, `1215413995645968394`). Algunas apps tienen dominios extra permitidos (Google/YouTube), así que la lista varía según la app. |

### No se pudo verificar
- Si un miembro que no es del Team puede abrir la Activity solo con Guild Install, sin verificación (el artículo de ayuda da 403).
- El texto exacto del modal de autorización y el código de error al cancelarlo.
- Límites de velocidad del comando `authorize`.
- `Host` / `X-Forwarded-Host` en Vercel a través del proxy.
- ~~Si un segundo handshake (navegación entre páginas) funciona siempre.~~ **Resuelto 2026-10-29: no funciona** (el SDK responde a `document.referrer`); por eso el diseño shell + iframe, ver §0 punto 7.
- Portapapeles, `confirm()` y `localStorage` dentro del iframe en escritorio, iOS y Android.
- Que el proxy añada el nonce a **todos** los `<script>` en línea. Visto en una app publicada; no está documentado. Si falla, mover los scripts en línea de `game.html` a archivos.
