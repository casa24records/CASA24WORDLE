# Guía: hacer pública la Activity de Casa 24 Wordle en Discord

> Escrita el **2026-10-29** para el dueño. Sigue los pasos en orden.
> Completa la **Parte E** de `docs/discord-activity-manual.md`; los detalles técnicos están en `docs/discord-activity-checklist.md`.
> Los botones aparecen en **inglés**, tal como se ven en el Discord Developer Portal (https://discord.com/developers/applications).
> **[NO VERIFICADO]** significa que la documentación pública de Discord no lo dice claro, o que no pudimos leer el artículo (los artículos de ayuda para desarrolladores, `support-dev.discord.com`, rechazan a los lectores automáticos). Al lado de cada uno explico cómo comprobarlo.
> **Nunca** pegues en el chat tu documento de identidad, tu selfie, contraseñas, el Client Secret ni otros secretos. Todo eso se sube **solo** dentro de Discord o de Stripe.

Datos fijos:
- App: **Casa 24 Wordle**, Client ID `1564412150519169067` (es público).
- Dueña de la app: el Developer Team **Casa 24**.
- Web: https://casa-24-wordle.vercel.app
- Términos: https://casa-24-wordle.vercel.app/terms
- Privacidad: https://casa-24-wordle.vercel.app/privacy
- Correo de contacto y soporte: **casa24records@gmail.com**

---

## 0. Lo importante en 30 segundos

Discord tiene **dos estados** para una Activity:

| Estado | Quién la ve y la abre | Dónde |
|---|---|---|
| **Sin verificar** (estado actual) | Solo tú, los miembros del Team y los **App Testers** | Solo en **servidores de menos de 25 miembros** y en DMs |
| **Verificada** | **Cualquier persona de Discord** | En **cualquier servidor**, sin importar su tamaño |

Lo que dice Discord (artículo de ayuda "What are Verified and Unverified Activities?", leído en resultados de búsqueda; el artículo completo da error 403 a lectores automáticos):
- Las Activities sin verificar son "only visible to you, your development team, and app testers", "not discoverable by the general Discord community" y "limited to servers with fewer than 25 members".
- Las verificadas son "visible to everyone on Discord" y "playable in any server, regardless of size".
- La documentación oficial (Building an Activity) dice: "Launching a non-distributed Activity is limited to you or members of the developer team."

**Respuesta a "¿basta con Guild Install + Public Bot?": No.** Instalar la app en el servidor (Guild Install) y marcar **Public Bot** **no** la hace jugable para los miembros normales. Para eso, la app tiene que estar **verificada** (App Verification).

**Discovery** (salir en el App Directory y en las listas del App Launcher) es **un paso extra y opcional** que va **después** de la verificación. No hace falta para que los miembros de tu servidor la abran.

Por eso hay dos caminos:
- **Camino rápido (sin revisión de Discord):** sirve **solo si el servidor de Casa 24 tiene menos de 25 miembros**. Añades a los jugadores como **App Testers**. Ver el Paso 2.
- **Camino público (el que quieres):** App Verification (Pasos 3–8) y, si quieres, Discovery (Pasos 9–11).

---

## 1. Qué preparar antes (lista)

**Textos** (yo te los puedo redactar; pídemelo):
- **Descripción corta** (1–2 frases), por ejemplo: "La palabra del día de Casa 24, en español e inglés. Juega dentro de Discord y compite en el ranking del servidor." Tiene que **describir con exactitud** lo que hace la app (Developer Terms 1(b)).
- **Descripción larga** para el App Directory (solo si haces Discovery): cómo se juega, idiomas, ranking, qué datos usa.
- **Etiquetas (tags)**: por ejemplo `wordle`, `word game`, `puzzle`, `daily`, `multilingual`. Discord limita cuántas se pueden poner; el Portal te dirá el máximo. [NO VERIFICADO el número exacto]
- **Categoría**: probablemente "Games". [NO VERIFICADO: las opciones exactas solo se ven en el Portal]
- **Max Participants** (opcional): déjalo vacío. Así Discord muestra "Unlimited participants".

**URLs** (ya existen o las está creando otro agente):
- Terms of Service URL: `https://casa-24-wordle.vercel.app/terms`
- Privacy Policy URL: `https://casa-24-wordle.vercel.app/privacy`
- Correo de soporte: `casa24records@gmail.com`
- **Servidor de soporte (Support Server)**: Discord lo pide para el App Directory. Puede ser el mismo servidor de Casa 24, si es público o tiene un enlace de invitación permanente. Si ese servidor no es "Community", puede que el Portal no te deje elegirlo. [NO VERIFICADO; el Portal lo indicará]

**Imágenes** (requisitos de la documentación "Assets and Metadata"):

| Dónde | Qué | Tamaño y formato |
|---|---|---|
| General Information → **App Icon** | Ícono de la app | Cuadrado. Recomendado: PNG de 1024×1024 o 512×512. [NO VERIFICADO el mínimo exacto] |
| Activities → Art Assets → **Cover Art** | Imagen principal en el estante de Activities. Mejor si lleva el título y arte de fondo | Se muestra a **16:9 y a 13:11**, **mínimo 1024 px de ancho**. Recomendado: 1920×1080 con lo importante en el centro, para que el recorte a 13:11 no corte el título |
| Activities → Art Assets → **Embedded Background** | Fondo detrás de la Activity en la vista de cuadrícula | **16:9**, **mínimo 1024 px de ancho**. El dibujo va **en los bordes**; el centro queda vacío |
| Activities → Art Assets → **Video Preview** (opcional) | Se reproduce al pasar el ratón por la portada | **640×360, MP4, menos de 10 s y menos de 1 MB** |
| Discovery Settings (solo si haces Discovery) | Capturas o imágenes de la ficha del App Directory | [NO VERIFICADO] Los tamaños los indica el propio Portal |

Para las imágenes puedes usar a Kolo y los colores de marca (skill `casa24-branding`).

**Identidad (solo la persona dueña del Team "Casa 24"):**
- Un **documento oficial con foto** (cédula o pasaporte), que subirás **directamente en la ventana de Stripe** que abre Discord. **No necesitas cuenta de Stripe**, solo el documento.
- Un teléfono con cámara, por si piden selfie.
- **2FA activado** en tu cuenta de Discord: **User Settings → My Account → Enable Authenticator App**. [NO VERIFICADO que el checklist lo exija, pero el Portal suele pedirlo para acciones de Team; actívalo igual]
- Edad: Stripe verifica a un adulto. [NO VERIFICADO si hay una edad mínima exacta para Activities; antes existía un proceso con "sponsor" (padre o tutor) para menores. Si eres mayor de 18, no te afecta]

---

## 2. Camino rápido (sin revisión): App Testers. Solo para servidores de menos de 25 miembros

Úsalo **mientras** esperas la verificación, o si el servidor es pequeño.

1. Portal → **Casa 24 Wordle** → menú izquierdo **App Testers**.
2. Escribe el **nombre de usuario** de cada persona y envía la invitación. Discord permite **hasta 50 App Testers**.
3. Cada persona tiene que **revisar su correo y aceptar la invitación**.
4. Tienen que jugar en un servidor de **menos de 25 miembros** (o en un DM). Si el servidor de Casa 24 tiene 25 o más miembros, **este camino no sirve allí**.

**Qué deberías ver si salió bien:** el tester ve "Casa 24 Wordle" en el App Launcher del servidor pequeño y puede jugar. Seguirá viendo la marca de "sin verificar" o de desarrollo.

[NO VERIFICADO] Si los App Testers necesitan **Developer Mode** encendido. Pruébalo con uno.

---

## 3. Antes de verificar: revisar la app en el Portal (sin revisión, inmediato)

**General Information**:
1. **Name**: `Casa 24 Wordle`.
2. **App Icon**: sube el ícono.
3. **Description**: la descripción corta del punto 1.
4. **Tags**: añade las etiquetas.
5. **Terms of Service URL**: `https://casa-24-wordle.vercel.app/terms`
6. **Privacy Policy URL**: `https://casa-24-wordle.vercel.app/privacy`
7. **Interactions Endpoint URL**: **déjalo vacío**. No tenemos bot ni comandos propios, y no es un requisito para una Activity. [NO VERIFICADO; si el checklist lo pidiera, avísame]
8. Pulsa **Save Changes**.

Antes de pegar las URLs, ábrelas en el navegador y comprueba que cargan (las está creando otro agente).

**Installation**:
- **Installation Contexts**: solo **Guild Install** (User Install sin marcar), como en el manual.
- **Install Link**: **Discord Provided Link**.
- **Default Install Settings → Guild Install → Scopes**: solo `applications.commands`. **Sin** `bot` y sin permisos.

**Bot**:
- **Public Bot**: **actívalo** cuando vayas a hacerla pública. Así cualquier administrador de servidor puede instalar la app con el Install Link. Si queda apagado, solo tú o el Team pueden instalarla. [NO VERIFICADO si el checklist de verificación o de Discovery lo exige; es muy probable para Discovery]
- Todo lo demás **apagado**: Privileged Gateway Intents y **Requires OAuth2 Code Grant**. **Nunca** pulses **Reset Token**.
- No hace falta pedir Privileged Intents. Discord separó la revisión de intents de App Verification.

**OAuth2**:
- **Redirects**: deja los 4 que ya hay. No hace falta añadir nada.
- Solo usamos el scope `identify`. No pidas más scopes: el Developer Policy pide no pedir más datos de los necesarios.

**Activities → Settings**:
- **Enable Activities**: encendido (ya lo está).
- **Supported Platforms**: Web/Desktop, iOS y Android.
- **Default Orientation Lock State**: Portrait en phone y tablet.
- Si aparece una opción de **restricción de edad** ("age-restricted", "Age gate" o parecida), **no la marques**. El juego es apto para todo público. Las Activities con restricción de edad pueden pedir a cada jugador que confirme su edad (changelog del 22-09-2026), y eso solo añade fricción. [NO VERIFICADO el nombre exacto]

**Activities → URL Mappings**: sin cambios (`/` → `casa-24-wordle.vercel.app`).

**Activities → Art Assets**: sube **Cover Art**, **Embedded Background** y, si quieres, **Video Preview** (tamaños en el punto 1).

---

## 4. App Verification: abrir el checklist

1. Portal → **Casa 24 Wordle** → menú izquierdo **App Verification**.
2. Verás un **checklist**. Cada punto pasa a **verde** cuando se cumple.
3. Según la ayuda de Discord ("How Do I Get My App Verified?", leída en resultados de búsqueda), los requisitos son:
   - que la **persona dueña del Team** verifique su **identidad** a través de **Stripe**;
   - que estén completos los datos de la app: **name, description, icon, privacy policy, terms of service**.
4. Los mínimos de servidores (75 o 100) son para **bots**: al llegar a 100 servidores, los bots están **obligados** a verificarse. Una Activity puede verificarse sin tener ese número de servidores. [NO VERIFICADO del todo: si el checklist pide un mínimo, lo verás allí]
5. [NO VERIFICADO] Si hay un **cuestionario sobre datos** (data protection, data usage). Si aparece, responde con lo del punto 12 ("Qué datos guardamos").

**No depende de Discord.** Solo es mirar la lista.

---

## 5. Verificar la identidad (dueño del Team)

1. En el checklist de **App Verification**, pulsa el botón de verificar identidad. El texto exacto puede variar. [NO VERIFICADO]
2. Se abre **Stripe Identity**. Sube el documento con foto y haz la selfie si la piden.
3. Al verificar al dueño del Team, queda verificado **todo el Team**.

**Tiempo:** Stripe suele responder en minutos. [NO VERIFICADO; si tarda, espera un día]

---

## 6. Dejar todo en verde

Vuelve a **App Verification** y comprueba que **todos** los puntos están en verde. Si alguno está en rojo, el propio Portal dice qué falta. Normalmente es una URL, el ícono o la descripción.

---

## 7. Enviar: "Verify App"

1. Cuando todo esté en verde, pulsa **Verify App** (o **Submit**).
2. A partir de aquí **depende de la revisión de Discord**. Una persona de Discord revisa la app.

**Tiempo:** Discord no publica un plazo para App Verification. [NO VERIFICADO] Cuenta con **de unos días a algunas semanas**. Discord avisa por correo y en el Portal.

**Si la rechazan:** el correo explica el motivo. Mándame el texto del motivo (sin datos personales) y lo arreglamos.

---

## 8. Probar con alguien que NO sea del Team

Cuando el Portal diga que la app está **verificada**:
1. Pide a un miembro normal del servidor de Casa 24 (que no esté en el Team ni sea App Tester, y sin Developer Mode) que abra el **App Launcher** en un canal del servidor y busque **Casa 24 Wordle**.
2. Debería poder abrirla, ver el modal **Authorize** una vez y jugar.
3. Para que también la abran en otros servidores, alguien con permiso **Manage Server** puede instalarla allí con el **Install Link** (necesita **Public Bot** activado, ver el Paso 3).

**¿Desaparece la marca "<>" de desarrollo?** Esa marca y la opción **Use Activity URL Override** salen **porque tú tienes Developer Mode encendido** o porque la app no está verificada. Los jugadores normales no deberían verlas cuando la app esté verificada. [NO VERIFICADO; compruébalo con el miembro del punto 1]

---

## 9. (Opcional) Discovery: Discovery Status

Esto hace que la app salga en el **App Directory** y en las secciones del **App Launcher**, para que gente de **otros servidores** la encuentre buscando.

1. Portal → **Casa 24 Wordle** → **Discovery** → **Discovery Status**.
2. Allí ves los **requisitos para calificar** (qualification criteria). Según la documentación "Enabling Discovery", el primero es: "we require your team owner to complete identity and application verification". Por eso Discovery va **después** de los Pasos 4–7.
3. Cumple los demás puntos que muestre. Según la ayuda de Discord, para el App Directory hace falta además un **support server** y una **descripción**.

---

## 10. (Opcional) Discovery Settings: la ficha de la app

Portal → **Discovery** → **Discovery Settings**. Rellena:
- descripción larga, categoría y etiquetas;
- imágenes de la ficha;
- **support server** y enlaces: web `https://casa-24-wordle.vercel.app`, Terms y Privacy;
- idiomas, si lo pide. El juego está **solo en español e inglés** (decisión del 2026-10-29): marca solo Spanish y English (US).

Pulsa **Save Changes**.

---

## 11. (Opcional) Enable Discovery

1. Vuelve a **Discovery Status** y pulsa el botón para activar Discovery (**Enable Discovery**).
2. Documentación oficial: "Once you enable Discovery, it may take up to **24 hours** for your app to appear in the App Directory and App Launcher."

**Qué deberías ver si salió bien:** al buscar "Casa 24 Wordle" en el App Directory (https://discord.com/discovery/applications), aparece la ficha.

---

## Resumen de tiempos

| Paso | ¿Depende de Discord? | Tiempo |
|---|---|---|
| 1–3 Preparar, App Testers, revisar el Portal | No | Lo que tardes tú |
| 5 Identidad (Stripe) | Stripe | Minutos u horas [NO VERIFICADO] |
| 7 Verify App | **Sí, revisión humana** | No publicado; días o semanas [NO VERIFICADO] |
| 11 Enable Discovery | Sí | Hasta **24 h** para aparecer (documentado) |

---

## 12. Qué exige Discord a la app (políticas)

Fuentes: Discord **Developer Terms of Service** y **Developer Policy** (`support-dev.discord.com`). Las citas vienen de resultados de búsqueda y de terceros, porque el texto completo da 403 a lectores automáticos. **Léelos tú en el navegador antes de enviar.**

- **Política de privacidad obligatoria**, que describa "clearly, accurately, and fully" qué datos recogemos, cómo los usamos y compartimos, cuánto tiempo los guardamos y **cómo pedir su borrado**. Tiene que cumplir las leyes de privacidad aplicables (se citan GDPR y CCPA). El **enlace** tiene que estar en el Developer Portal y ser **fácil de encontrar desde la propia app**.
- **Borrado a petición:** hay que dar a los usuarios una forma **fácil** de pedir que se modifiquen o borren sus datos de la API. Nosotros ya tenemos "borrar mis datos" (`/api/me/delete`); falta que **se vea desde la Activity** y que la política lo explique.
- **Si la app deja de funcionar**, hay que borrar todos los datos de la API (Terms 9(b), según cita de terceros [NO VERIFICADO literal]).
- **No** vender los datos, no usarlos para publicidad ni para entrenar IA, y no contactar a los usuarios fuera de la app (Developer Policy, según cita de terceros [NO VERIFICADO literal]). Nosotros no hacemos nada de eso.
- **Seguridad:** proteger el **Client Secret** y avisar a Discord si hay un acceso no autorizado a los datos.
- **Nombre y descripción exactos:** tienen que describir lo que hace la app.
- **Menores:** Discord permite usuarios desde los 13 años (según el país). El juego no tiene contenido para adultos. No marques restricción de edad.
- **Monetización:** ninguna. No hay que configurar nada de Monetization.

**Qué datos guardamos** (para la política de privacidad y para cualquier cuestionario):
- Discord: **ID de usuario**, **nombre de usuario**, **hash del avatar** (solo para mostrar la foto). Scope `identify`, **sin correo electrónico**.
- Juego: intentos del día, resultados, puntos y rachas (ranking y vista en vivo).
- No guardamos el token de acceso de Discord. La sesión es una cookie o encabezado firmado.
- Proveedores: Vercel (hosting) y Neon (base de datos Postgres).
- Los demás jugadores ven tu nombre, avatar, puntos y los colores de tu tablero. **Nunca** ven tus palabras.
- Borrado: botón "borrar mis datos", o por correo a casa24records@gmail.com.

---

## 13. Qué debe ajustar el código/la web

1. **Páginas `/terms` y `/privacy`** (las está creando otro agente). Deben:
   - cargar sin iniciar sesión, en una URL fija con `https://`, sin redirecciones raras;
   - **la privacidad** debe tener todo lo de la lista "Qué datos guardamos", el tiempo que guardamos los datos, cómo borrarlos (botón y correo `casa24records@gmail.com`), los proveedores (Vercel, Neon), que no vendemos datos, edad mínima según Discord y una fecha de "última actualización";
   - **los términos** deben decir qué es el juego, las reglas de uso (sin trampas ni abuso), que los usuarios deben cumplir las leyes y los Términos de Discord, sin garantías, contacto y fecha.
2. **Enlaces dentro de la Activity**: desde la ventana "ⓘ Privacidad" (o el menú) del juego, enlaces visibles a **Privacidad** y **Términos**. Dentro de Discord, los enlaces externos deben abrirse con `discordSdk.commands.openExternalLink(...)` (Discord muestra un aviso antes de salir), porque una navegación normal rompería la Activity: la regla es que el documento principal nunca navega. Otra opción es mostrar el texto dentro de una ventana del propio juego. [Tarea de código]
3. **"Borrar mis datos" visible dentro de la Activity**, sin `onclick` en línea (CSP). Ya existe en la web; hay que confirmar que funciona dentro de Discord con el encabezado Bearer.
4. **No mostrar nunca** el correo ni datos privados de otros jugadores. Hoy ya es así; hay que mantenerlo.
5. **Footer de la web**: enlaces a `/terms` y `/privacy` también en la versión web.
6. Las páginas `/terms` y `/privacy` no deben depender de la CSP de la Activity: se abren fuera de Discord.
7. No hace falta ningún cambio de código para que la verificación sea posible: no usamos bot, ni comandos, ni Interactions Endpoint.

---

## Fuentes (leídas el 2026-10-29)

- Enabling Discovery: https://docs.discord.com/developers/discovery/enabling-discovery (cita de verificación del dueño del Team y "up to 24 hours").
- Discovery overview: https://docs.discord.com/developers/discovery/overview
- Building an Activity: https://docs.discord.com/developers/activities/building-an-activity ("Launching a non-distributed Activity is limited to you or members of the developer team").
- Assets and Metadata: https://docs.discord.com/developers/activities/development-guides/assets-and-metadata (tamaños de Cover Art, Embedded Background y Video Preview).
- Change Log: https://docs.discord.com/developers/change-log (22-09-2026, Age Assurance).
- Artículos de ayuda (403 a lectores automáticos; contenido tomado de resultados de búsqueda):
  - What are Verified and Unverified Activities? https://support-dev.discord.com/hc/en-us/articles/26576097154199
  - How Can Users Discover and Play My Activity? https://support-dev.discord.com/hc/en-us/articles/21204493235991
  - Unverified/Private Activity Safety: https://support-dev.discord.com/hc/en-us/articles/21692628851351
  - How Do I Get My App Verified? https://support-dev.discord.com/hc/en-us/articles/23926564536471
  - Developer Terms of Service: https://support-dev.discord.com/hc/en-us/articles/8562894815383
  - Developer Policy: https://support-dev.discord.com/hc/en-us/articles/8563934450327
  - Age Assurance (developers): https://support-dev.discord.com/hc/en-us/articles/38338398970263

---

## Estado al 2026-10-29
- **App Verification: aprobada.** El `<>` y "Use Activity URL Override" que ve el dueño salen por ser del Team con Developer Mode; comprobar con Developer Mode apagado o con una cuenta que no sea del Team.
- **Discovery Status — falta:** servidor de soporte **Community** (Server Settings → Enable Community, luego elegirlo como Support Server), **Summary**, **descripción larga**, al menos un **locale** y la **Description** de General Information.
- **Locales de Discovery (lo cambia el dueño en el Portal):** desde el 2026-10-29 el juego es solo español e inglés. En Discovery Settings deja **solo Spanish y English (US)**; quita cualquier otro idioma que se haya marcado antes (francés, portugués, alemán, etc.), porque la ficha tiene que describir con exactitud la app.
- **Textos sugeridos:**
  - Resumen: "El Wordle diario de Casa 24 Records: adivina la palabra del día en 6 intentos, en español o inglés, y compite en el ranking con tus amigos."
  - Descripción larga: juego diario (misma palabra para todos, 6 intentos, verde/naranja/gris), ranking con la cuenta de Discord (menos intentos = más puntos, rachas, puesto), quién juega hoy en vivo (solo colores, sin spoilers), español e inglés, misma partida en Discord y en casa-24-wordle.vercel.app, enlace a /privacy.
