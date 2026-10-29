# Manual: encender Casa 24 Wordle dentro de Discord (Activity)

> Escrito el **2026-10-28** para el dueño. Un paso a la vez, en orden.
> Detalle técnico y fuentes: `docs/discord-activity-checklist.md` y la skill `casa24-discord-activity`.
> Los nombres de botones están en **inglés**, como aparecen en el Discord Developer Portal y en Vercel. Si tu Discord está en español, el nombre puede variar un poco (por ejemplo "Configuración de usuario" en vez de "User Settings").

Datos fijos:
- App de Discord: **Casa 24 Wordle**, Client ID `1564412150519169067` (es público, no es un secreto).
- Vercel: equipo **Casa 24**, proyecto **casa24-wordle**, producción **https://casa-24-wordle.vercel.app**. Lo que se sube a `main` se publica solo.
- Portal de Discord: **https://discord.com/developers/applications**

Leyenda:
- **¿Puedo hacerlo ya?** → **Sí, antes del push** (no cambia nada de la web ni de lo que ven los jugadores) o **No, después del push**.
- **[NO VERIFICADO]** = la documentación de Discord no lo dice claro; al lado explico cómo comprobarlo.
- Nunca pegues secretos (Client Secret, `SECRET_KEY`, `DATABASE_URL`, contraseñas) en el chat ni en archivos.

---

## Resumen: el orden más seguro

| Parte | Qué | Cuándo |
|---|---|---|
| A | Pasos 1–9: Team, revisar la app, Redirect, instalación, plataformas, Developer Mode | **Ya, antes del push.** No cambian la web. |
| B | Paso 10: me dices "haz el push" y yo subo el código a `main` | Cuando termines la Parte A |
| C | Pasos 11–16: **URL Mapping** y **Enable Activities** (el "interruptor"), y las pruebas | **Solo después del push** |
| D | Apagarla sin tocar código | Cuando quieras |
| E | Fase 4: que la abran miembros que no son del Team | Cuando la Parte C funcione |

**Por qué el interruptor va al final.** Mientras **Enable Activities** esté apagado, la Activity no aparece en ningún App Launcher, así que nadie puede abrirla. Si la enciendes **antes** del push:
- la web **no** se rompe (la web no depende de esto);
- pero tú y los miembros del Team verían en Discord la versión vieja de la página, que no sabe hablar con Discord: pantalla en blanco o "cargando" para siempre.

No es peligroso, solo confuso. Por eso: todo lo demás ahora, el push, y después el interruptor.

> **Actualización 2026-10-29 (selector de idioma y arreglo de "No pudimos conectar"): no hace falta ningún cambio en el Portal.** El URL Mapping sigue siendo `/` → `casa-24-wordle.vercel.app`; ahora `/` dentro de Discord abre una página pequeña que se conecta con Discord una sola vez y muestra el juego dentro. Solo hay que hacer el push y volver a probar los Pasos 13–16.

---

## Parte A — Antes del push (seguro)

### Paso 0. Lo que necesitas
- La cuenta de Discord que es **dueña** de la app "Casa 24 Wordle".
- **Autenticación en dos pasos (2FA)** activada en esa cuenta: Discord → **User Settings → My Account → Enable Two-Factor Auth**. Los Teams y la verificación la piden [NO VERIFICADO si es obligatoria para crear el Team; si el Portal la pide, actívala].
- Permiso **Manage Server** (Administrar servidor) en el servidor de Casa 24, para instalar la app ahí.
- Discord de escritorio (Mac/Windows) y Discord en el teléfono.

**¿Puedo hacerlo ya?** Sí.

---

### Paso 1. Crear el Team "Casa 24"
Mientras la Activity no esté "distribuida", **solo tú y los miembros del Team** pueden abrirla. El Team sirve para que otras personas de Casa 24 la prueben.

1. Abre https://discord.com/developers/teams
2. Pulsa **New Team**.
3. Nombre: **Casa 24**. Pulsa **Create**.
4. Dentro del Team, pulsa **Invite Member** y escribe el nombre de usuario de cada persona que vaya a probar. Rol: **Developer** (o **Read-only** si solo van a probar).
5. Cada persona invitada tiene que **aceptar** la invitación (le llega por correo o la ve al entrar al Portal).

**¿Puedo hacerlo ya?** Sí. No cambia nada de la web.

**Qué deberías ver si salió bien:** en **Teams** aparece "Casa 24" y, en **Members**, las personas con estado aceptado (no "pending").

---

### Paso 2. Pasar la app al Team
1. Portal → **Applications** → **Casa 24 Wordle** → **General Information**.
2. Baja hasta el final de la página y pulsa **Transfer App to Team**.
3. Elige **Casa 24** y confirma.

Ojo:
- [NO VERIFICADO] No vi un botón para devolver la app a tu cuenta personal. Tómalo como un cambio permanente. El dueño del Team (tú) sigue mandando.
- El **Client ID no cambia**. El **Client Secret** debería seguir igual [NO VERIFICADO]. El Paso 9 lo comprueba.

**¿Puedo hacerlo ya?** Sí.

**Qué deberías ver si salió bien:** en **Applications**, "Casa 24 Wordle" aparece bajo el Team "Casa 24". En **General Information**, el **Application ID** sigue siendo `1564412150519169067`.

---

### Paso 3. Revisar la app
En **Casa 24 Wordle**:
1. **General Information**: nombre "Casa 24 Wordle", el ícono de Kolo y una descripción corta. (El ícono y la descripción se ven en el App Launcher.)
2. **OAuth2**: el **Client ID** es `1564412150519169067`. **No** pulses **Reset Secret** (rompería el login de la web hasta cambiarlo en Vercel).
3. **Bot**: no hace falta nada. No usamos bot.

**¿Puedo hacerlo ya?** Sí.

**Qué deberías ver si salió bien:** todo igual que antes; solo miraste.

---

### Paso 4. Redirects: añadir `https://127.0.0.1` y conservar los 3 que ya hay
La guía de Discord pide al menos un Redirect para las Activities y sugiere `https://127.0.0.1` como marcador. Nuestro código de la Activity no lo usa, pero no estorba.

1. **OAuth2** → sección **Redirects**.
2. **Deja como están** estos tres (son los del login de la web):
   - `https://casa-24-wordle.vercel.app/auth/discord/callback`
   - `https://casa24-wordle-git-leaderboard-discord-casa-24.vercel.app/auth/discord/callback`
   - `http://127.0.0.1:5050/auth/discord/callback`
3. Pulsa **Add Another** y escribe `https://127.0.0.1`
4. Pulsa **Save Changes** (la barra verde que aparece abajo).

**¿Puedo hacerlo ya?** Sí. Añadir un Redirect no cambia nada para los que ya existen.

**Qué deberías ver si salió bien:** 4 Redirects en la lista y ningún aviso rojo.

---

### Paso 5. Installation: solo "Guild Install"
Queremos que la app se instale en **servidores** (Guild Install), no que cada usuario se la lleve a cualquier chat (User Install).

1. **Installation** (menú izquierdo).
2. En **Installation Contexts**: deja marcado **Guild Install** y **desmarca User Install**.
3. En **Install Link** elige **Discord Provided Link**.
4. En **Default Install Settings → Guild Install → Scopes**: solo **applications.commands**. **No** añadas `bot`.
5. Pulsa **Save Changes**.

**¿Puedo hacerlo ya?** Sí. El login de la web usa otra cosa (OAuth2 con `identify`) y no depende de esto [comprobado en el Paso 9].

**Qué deberías ver si salió bien:** **Guild Install** marcado, **User Install** sin marcar, y un enlace que empieza por `https://discord.com/oauth2/authorize?client_id=1564412150519169067`.

---

### Paso 6. Instalar la app en el servidor de Casa 24
1. Copia el **Install Link** del Paso 5 y ábrelo en el navegador.
2. Elige **Add to Server** (no "Add to My Apps").
3. Elige el servidor de **Casa 24** y pulsa **Continue** → **Authorize**.

**¿Puedo hacerlo ya?** Sí. Mientras Activities esté apagado, la app instalada no muestra nada a los miembros.

**Qué deberías ver si salió bien:** un mensaje "Authorized" o "Success". En Discord: **Server Settings → Integrations** muestra "Casa 24 Wordle".

---

### Paso 7. Activities → Settings: plataformas y orientación (sin encender todavía)
1. **Activities** (menú izquierdo) → **Settings**.
2. **No marques Enable Activities todavía.** Ese es el interruptor (Paso 12).
3. **Supported Platforms**: marca **Web/Desktop**, **iOS** y **Android**.
4. **Default Orientation Lock State**: **Portrait** (vertical) para **phone** y para **tablet**.
5. Pulsa **Save Changes**.

**¿Puedo hacerlo ya?** Sí, si el Portal te deja. [NO VERIFICADO] Puede que estas opciones estén grises hasta marcar **Enable Activities**. Si están grises, **no pasa nada**: déjalas para el Paso 12 y hazlas justo después de encender.

**Qué deberías ver si salió bien:** las tres plataformas marcadas y "Portrait" en las dos listas, sin aviso rojo al guardar.

---

### Paso 8. Developer Mode en tu Discord (escritorio y teléfono)
Sirve para ver apps que aún no están distribuidas y para leer los mensajes de error.

- **Escritorio:** **User Settings** (el engranaje abajo a la izquierda) → **Advanced** → **Developer Mode**: encendido.
- **Teléfono:** toca tu foto de perfil → engranaje (**Settings**) → **Appearance** (en algunas versiones está en **Advanced**) → **Developer Mode**: encendido.

**¿Puedo hacerlo ya?** Sí. Solo cambia tu Discord.

**Qué deberías ver si salió bien:** en escritorio, al hacer clic derecho sobre tu nombre aparece **Copy User ID**. En el teléfono aparece una sección **DEV ONLY** en Settings.

---

### Paso 9. Comprobar que la web sigue igual
Después de los pasos 2, 4 y 5, entra a https://casa-24-wordle.vercel.app en una ventana privada:
1. Pulsa el botón de Discord → **Authorize** → vuelves al juego con tu avatar.
2. Abre https://casa-24-wordle.vercel.app/leaderboard

**¿Puedo hacerlo ya?** Sí.

**Qué deberías ver si salió bien:** el login funciona como siempre.
**Si vuelves a `/?login=failed`:** el secreto cambió con el traspaso al Team. Ve a **OAuth2 → Reset Secret**, cópialo **sin pegarlo en el chat**, y en **Vercel → Casa 24 → casa24-wordle → Settings → Environment Variables** cambia `DISCORD_CLIENT_SECRET` (Production, Preview y Development). Luego **Deployments → los tres puntos del último → Redeploy**.

---

## Parte B — El push (lo hago yo)

### Paso 10. Me dices "haz el push"
Cuando termines la Parte A, escríbeme algo como **"Portal listo, haz el push"**. Yo:
1. corro todas las pruebas;
2. subo el código a `main` (Vercel lo publica solo en 1–2 minutos);
3. compruebo que la web sigue igual y que la página de la Activity no pide nada fuera de nuestro dominio;
4. te aviso.

**¿Puedo hacerlo ya?** Solo cuando la Parte A esté lista.

**Qué deberías ver si salió bien:** en **Vercel → casa24-wordle → Deployments**, el último despliegue de **Production** en **Ready** (verde), y la web igual que antes.

---

## Parte C — Encender (solo después del push)

### Paso 11. Activities → URL Mappings
Le dice a Discord qué página abrir dentro de la Activity.

1. **Activities** → **URL Mappings**.
2. En la fila **Root Mapping**:
   - **PREFIX:** `/`
   - **TARGET:** `casa-24-wordle.vercel.app`
3. Escríbelo **sin** `https://`, **sin** `/` al final y sin espacios.
4. No añadas más filas (no llamamos a otros dominios).
5. Pulsa **Save Changes**.

**¿Puedo hacerlo ya?** **No, después del push.** (Técnicamente no rompe la web, pero junto con el Paso 12 es lo que hace que Discord abra nuestra página. Hazlos juntos y en este orden.)

**Qué deberías ver si salió bien:** una sola fila `/` → `casa-24-wordle.vercel.app` guardada. Si abres `https://1564412150519169067.discordsays.com/` en el navegador, después de encender (Paso 12) debería verse nuestra web en vez de una página vacía [NO VERIFICADO: cómo responde el proxy fuera de Discord].

---

### Paso 12. Enable Activities (el interruptor)
1. **Activities** → **Settings**.
2. Marca **Enable Activities**. Si aparece un aviso, acéptalo.
3. Si en el Paso 7 las opciones estaban grises, hazlas ahora: **Supported Platforms** (Web/Desktop, iOS, Android) y **Default Orientation Lock State** → **Portrait** para phone y tablet.
4. Pulsa **Save Changes**.

Al encenderlo, Discord crea solo un comando llamado **Launch** (el "Entry Point"). **No lo borres ni lo cambies.**

**¿Puedo hacerlo ya?** **No, después del push y del Paso 11.**

**Qué deberías ver si salió bien:** **Enable Activities** marcado. En **Activities** aparecen más secciones (por ejemplo **Art Assets**).

---

### Paso 13. Abrirla en el escritorio
1. Cierra y vuelve a abrir Discord (para que vea los cambios).
2. Entra al servidor de Casa 24.
3. **En un canal de voz:** únete al canal y pulsa el botón del cohete (**Activities**, en la barra de controles de la llamada). Elige **Casa 24 Wordle**.
4. **En un canal de texto:** pulsa el ícono de apps / cohete en la barra donde escribes mensajes (**App Launcher**) y elige **Casa 24 Wordle**.

**¿Puedo hacerlo ya?** Después del Paso 12.

**Qué deberías ver si salió bien:**
- La primera vez, el modal de permiso (Paso 14).
- **La primera vez en ese dispositivo** el juego abre en el idioma de tu Discord: **español** si tu Discord está en español (cualquier variante), **inglés** en cualquier otro caso. Solo si Discord no lo dice (versión vieja o no responde en 3 segundos) sale **"Elige tu idioma / Choose your language"** con 2 botones (Español, English).
- Un momento con Kolo y "Conectando…", luego "Cargando juego…" (en el idioma elegido).
- Después, el juego directo en modo leaderboard. **Sin** botón de "Iniciar sesión" y **sin** modo invitado.
- **Cierra y vuelve a abrir la Activity:** abre directo en el último idioma usado en ese dispositivo (y más rápido), aunque cambies el idioma de Discord.
- **Para cambiar de idioma:** toca el título de arriba, **"Casa 24 ES ▾"**. Se abre una ventana con los 2 idiomas (Español, English); elige el otro. El juego cambia sin volver a conectar con Discord y sin pedir permiso otra vez. La próxima vez abrirá en ese idioma.
- El ranking se abre en una ventana dentro del juego (ícono del trofeo).
- En el canal aparece un mensaje automático de Discord diciendo que abriste la Activity (lo publica el comando **Launch**).

---

### Paso 14. La primera vez: el modal "Authorize" (es normal)
La primera vez que una persona abre la Activity, Discord muestra una ventana que pide permiso para ver su **nombre de usuario** (permiso `identify`). Es normal y **sale una sola vez** por persona.

1. Pulsa **Authorize**.
2. Si cierras y vuelves a abrir, **no** debería salir otra vez.
3. Quien ya entró por la web con Discord probablemente no lo vea nunca [NO VERIFICADO].

Si alguien pulsa **Cancel**: verá "Para jugar en Discord necesitamos tu permiso (solo tu nombre de usuario)." y el botón **Intentar de nuevo / Try again**. No hay forma de jugar en Discord sin ese permiso (decisión: sin modo invitado dentro de Discord).

**Qué deberías ver si salió bien:** tras **Authorize**, el juego carga en pocos segundos. Anota el texto exacto del modal (lo usaremos para la ayuda) [NO VERIFICADO: el texto no está en la documentación].

---

### Paso 15. Abrirla en el teléfono
1. Cierra Discord por completo y vuelve a abrirlo.
2. Entra a un **canal de voz** del servidor de Casa 24.
3. Toca el cohete (**Activities**) y elige **Casa 24 Wordle**.
4. Prueba también en un canal de texto (ícono de apps junto a donde escribes).

**Qué deberías ver si salió bien:**
- El juego en **vertical**, aunque gires el teléfono.
- El teclado del juego **no** queda tapado por la barra de abajo del teléfono ni por el notch.
- La primera vez el juego abre en el idioma de tu Discord (el selector de 2 botones solo sale si Discord no lo dice, y cabe en la pantalla).
- Si minimizas la Activity (ventanita flotante, "PIP"), se ve solo el tablero; al tocarla vuelve el juego completo.
- Cambia de idioma con **"Casa 24 ES ▾"** también en el teléfono.
- Si es posible, prueba en un iPhone y en un Android.

---

### Paso 16. Tu prueba de sincronización web ↔ Discord
El servidor guarda la partida; la web y Discord solo la muestran. Esta prueba lo confirma. Hazla con **un idioma que no hayas jugado hoy** (`es` o `en`).

1. **Web:** entra con Discord en https://casa-24-wordle.vercel.app, abre el juego de ese idioma y escribe **2 palabras** (sin ganar).
2. **Discord:** abre la Activity con la misma cuenta y elige ese idioma (con el título **"Casa 24 ES ▾"**).
   - **Esperado:** ves las **mismas 2 filas** con los mismos colores.
3. **Discord:** termina la partida (gana o pierde).
   - **Esperado:** sale la ventana final con tu puesto y tus puntos.
4. **Web:** vuelve a la pestaña de la web (o recárgala).
   - **Esperado:** la partida aparece **terminada**, con el mismo resultado. Si la pestaña ya estaba abierta, se actualiza sola al volver a ella (o en un minuto como máximo).
5. **Leaderboard:** abre https://casa-24-wordle.vercel.app/leaderboard, pestaña de ese idioma.
   - **Esperado:** tus puntos subieron **una sola vez** (no el doble).
6. **Extra (opcional):** con web y Discord abiertos a la vez en otra partida, escribe una palabra en cada uno casi al mismo tiempo.
   - **Esperado:** el segundo **no** guarda su palabra; se repinta con lo que ya hizo el primero. Nunca se pierden ni se duplican intentos.

Si algo no coincide, mándame en qué paso falló y el idioma (sin capturas con datos de otras personas).

---

## Parte D — Apagarla sin tocar código

Cualquiera de las dos sirve. La primera es la más limpia.

1. **Apagar del todo (recomendado):** **Activities → Settings** → desmarca **Enable Activities** → **Save Changes**.
   - La Activity desaparece del App Launcher.
   - [NO VERIFICADO] Las personas que ya la tenían abierta quizá sigan hasta cerrarla. El comando **Launch** podría borrarse; al volver a encender, Discord lo crea de nuevo.
2. **Cortarle la página:** **Activities → URL Mappings** → borra la fila `/` → **Save Changes**.
   - La Activity sigue en el App Launcher, pero se abre en blanco. Sirve solo para una pausa corta.

**La web no se ve afectada** por ninguna de las dos.

Si lo que falla es **la web** (no Discord), eso no se arregla en el Portal: en **Vercel → casa24-wordle → Deployments**, abre el despliegue anterior que funcionaba → los tres puntos → **Promote to Production** (o **Instant Rollback**). Avísame y lo revisamos.

---

## Parte E — Fase 4: que la abran miembros que no son del Team

### Paso 17. Probar con un miembro de Casa 24 que NO esté en el Team
1. Pide a alguien del servidor de Casa 24 que **no** esté en el Team (ni tenga Developer Mode) que abra el App Launcher en un canal del servidor.
2. ¿Aparece **Casa 24 Wordle**? ¿Puede abrirla y jugar?

**Qué deberías ver si salió bien:** puede abrirla, sale el modal **Authorize** una vez, y su resultado aparece en `/leaderboard`.

[NO VERIFICADO] La documentación dice: "Launching a non-distributed Activity is limited to you or members of the developer team". No está claro si instalarla en el servidor (Paso 6) ya basta para los demás miembros. Esta prueba lo responde.

### Paso 18. Si no puede: verificación y Discovery
Solo si el Paso 17 falla.

1. **App Verification:** Portal → **Casa 24 Wordle** → **App Verification** (o **Verification**). Sigue los pasos que muestre.
   - Discord pide que **el dueño del Team verifique su identidad**. Ten a mano, **para subirlos tú directamente en Discord** (nunca en el chat):
     - un documento oficial con foto (cédula o pasaporte);
     - tu teléfono con cámara para la selfie, si la piden;
     - 2FA activado en tu cuenta.
2. **Datos de la app** que conviene tener listos en **General Information**:
   - descripción corta y clara;
   - ícono;
   - **Terms of Service URL** y **Privacy Policy URL** (si las piden). Hoy la web solo tiene la ventana "ⓘ Privacidad", no una página propia: **pendiente**, avísame y la hago.
3. **Discovery:** Portal → **Discovery** → **Discovery Status** y **Discovery Settings**. Rellena:
   - categoría y etiquetas;
   - en **Activities → Art Assets**: **Cover Art** (16:9 y 13:11, de 1024 px o más) y **Embedded Background** (16:9, 1024 px o más). Opcional: un vídeo corto (640×360, mp4, menos de 10 s y menos de 1 MB).
4. La revisión puede tardar hasta **24 horas**.

**Qué deberías ver si salió bien:** en **Discovery Status** el estado pasa a aprobado o listado, y el miembro del Paso 17 ya puede abrirla.

---

## Variables de entorno (Vercel)

**No hace falta ninguna variable nueva para la Activity.** La Activity usa las mismas que el login de la web:

| Nombre | Para qué | ¿Cambia? |
|---|---|---|
| `DISCORD_CLIENT_ID` | El ID público de la app | No |
| `DISCORD_CLIENT_SECRET` | Canjear el permiso de Discord por el nombre de usuario | No (solo si el Paso 9 falla) |
| `SECRET_KEY` | Firmar la sesión de la web y de la Activity | No |
| `DATABASE_URL` (+ las de Neon) | La base de datos del leaderboard | No |
| `DEMO_PASSWORD` | Developer view | No |
| `ADMIN_DISCORD_IDS` (opcional) | Quién puede ocultar nombres | No |
| `PUBLIC_URL` (opcional, ya existía) | La dirección pública para los enlaces de "Compartir" | Solo si al compartir desde Discord sale un enlace `discordsays.com`; entonces ponle `https://casa-24-wordle.vercel.app` |

Recuerda: los cambios de variables solo valen para **despliegues nuevos** (Vercel → **Deployments** → **Redeploy**).

---

## Problemas y soluciones

Para ver errores:
- **Escritorio:** con Developer Mode encendido, la forma más fácil es instalar **Discord PTB** (la versión de pruebas de Discord para escritorio) y abrir **View → Developer → Toggle Developer Tools** → pestaña **Console**. En el Discord normal ese menú puede no estar.
- **Teléfono:** **Settings → DEV ONLY → Debug Logs**, y filtra por `RpcApplicationLogger` o por `1564412150519169067`. Para mandármelos: en el canal de voz, desliza hacia arriba → **Share Application Logs**.
- **Servidor:** **Vercel → casa24-wordle → Logs** (busca respuestas 4xx/5xx de `/api/...`).

| Lo que ves | Causa probable | Qué hacer |
|---|---|---|
| Casa 24 Wordle **no aparece** en el App Launcher | **Enable Activities** apagado; Developer Mode apagado; no eres del Team y aún no está distribuida; en el móvil falta marcar iOS/Android; Discord no se ha reiniciado | Revisa los Pasos 7, 8, 12 y 17. Cierra Discord del todo y vuelve a abrirlo |
| **Pantalla en blanco** | Falta el URL Mapping o está mal escrito (con `https://` o `/` al final); el push aún no se hizo; un archivo bloqueado por la CSP | Revisa el Paso 11. Mira la Console: si dice `Refused to…` o `blocked:csp`, mándame esa línea |
| Se queda en **"Conectando…"** o sale "No pudimos conectar con Discord" | Discord no respondió al "saludo" en 10 segundos (red lenta, Discord viejo), el canje con nuestro servidor tardó más de 15 s, o **falta un archivo del SDK en el deploy** | Pulsa **Intentar de nuevo**. Si no, cierra y vuelve a abrir la Activity y actualiza Discord. Si se repite, mándame los logs |
| Se queda **siempre** en "Conectando…" (a todos, en todos los dispositivos) | Un archivo de `/static/vendor/` da **404** en Vercel (pasó una vez con los archivos `lib/` del SDK, que no se habían subido) | Revisa los logs de Vercel (`vercel logs` o Vercel → casa24-wordle → **Logs**) buscando **404** en rutas `/static/vendor/…`. Mándame la ruta: es un arreglo de código |
| Sale el selector de idioma **cada vez** | Discord no deja guardar datos en ese dispositivo (almacenamiento bloqueado) y además no nos dice su idioma | Normal en ese caso; elige el idioma y juega. Avísame en qué dispositivo pasa |
| Mensaje de que **hace falta tu permiso** | Se pulsó **Cancel** en el modal | Pulsa **Intentar de nuevo** y luego **Authorize** |
| Errores **CSP** (`Refused to load…`, `Refused to execute inline event handler`, `blocked:csp`) | Algo se pide fuera de nuestro dominio, o quedó un `onclick=` en el HTML | Mándame la línea exacta de la Console. Es un arreglo de código |
| **401** en `/api/state`, `/api/guess` o `/api/live` (Vercel Logs) | La sesión de la Activity venció o no llegó | La Activity pide el permiso otra vez, en silencio, una sola vez. Si sigue, cierra y abre de nuevo |
| **403** en `POST /api/activity/token` o `/api/guess` | La revisión de "mismo origen" no reconoce `1564412150519169067.discordsays.com` | Es de código: mándame la hora aproximada y lo reviso en los logs |
| **400** con error `discord` en `POST /api/activity/token` | Discord no aceptó el canje: `DISCORD_CLIENT_SECRET` incorrecto o reseteado | Revisa el Paso 9 |
| **429** en `POST /api/activity/token` | Muchísimos inicios a la vez (más de 120 por minuto entre todos) | Espera un minuto |
| **429** | Demasiadas peticiones por minuto | Espera un minuto |
| **503** `store` | La base de datos (Neon) no responde | Revisa el estado de Neon y `DATABASE_URL` |
| La partida **no coincide** entre web y Discord | La web estaba abierta desde antes y aún no se actualizó | Vuelve a la pestaña o espera un minuto. Si sigue distinto, Paso 16 y avísame |
| Al compartir sale un enlace `discordsays.com` | La dirección pública no se detecta bien | Pon `PUBLIC_URL` (sección de variables) y redeploy |
| El móvil no queda en vertical | Falta **Default Orientation Lock State → Portrait** | Paso 7/12 |
| El teclado queda tapado en el teléfono | Márgenes seguros (safe areas) | Mándame modelo de teléfono y una captura |
| La web dejó de funcionar | No es el Portal | Parte D, último párrafo (rollback en Vercel) |

---

## Cosas que solo se pueden comprobar en Discord real

| Qué | Cómo comprobarlo |
|---|---|
| Que la Activity llega a conectarse (`ready`) | Paso 13 con la Console abierta: no debe haber errores rojos |
| Que la CSP no bloquea nada | Console: buscar `Refused to` y `blocked:csp`. Pestaña **Network**: nada en rojo |
| El modal sale solo la primera vez | Paso 14 con una cuenta que nunca usó la app; después, cerrar y abrir |
| Qué pasa al cancelar el modal | Pulsar **Cancel** y anotar el mensaje que sale |
| Idioma de Discord la primera vez (es → Español, otro → English); abrir directo en el último idioma la segunda | Paso 13: abrir, cambiar con "ES ▾", cerrar, volver a abrir |
| Cambiar de idioma ("Casa 24 ES ▾") o abrir el leaderboard dentro de la Activity | Hacerlo y ver que no se pierde la sesión ni vuelve a salir "Conectando…" |
| Móvil: vertical, márgenes, ventanita (PIP) | Paso 15 en iPhone y Android |
| Compartir dentro de Discord | Pulsar **Compartir** al terminar, en escritorio y móvil: dentro de Discord **copia** el texto (no abre el menú del sistema); si no puede copiar, sale una ventana con el texto para copiarlo a mano |
| Miembros fuera del Team | Paso 17 |
| Reconexión | Con la Activity abierta, quitar el wifi 30 s y volver: no se pierden intentos |
| Que el mensaje de **Launch** se publica en el canal | Paso 13 |
