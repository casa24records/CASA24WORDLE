# Rebrand: "Casa 24 Wordle" → "El Wordle by Casa 24"

> Plan del dueño, decidido el **2026-11-04**. Documento para retomar más tarde.

## Cómo retomar

- **Rama:** `rebrand-el-wordle`.
- **Assets fuente** (PNG con transparencia, del diseñador): `design/rebrand-v1.1/`
  - `el-wordle-titler.png` (título "El Wordle"), `hoodie-kolo-cropped.png` / `hoodie-kolo.png` (Kolo con hoodie y audífonos), `casa24-door-white.png` (puerta de Casa 24, blanca), `icon-1024.png` (icono de la Activity, opaco), `banner-680x240.png`, `banner-alt-480x280.png`.
- **Reconstruir los assets del juego:**

  ```
  .venv/bin/python scripts/brand_assets.py --rebrand design/rebrand-v1.1
  ```

  Escribe `webapp/static/images/brand/el-wordle.webp` (alto 160), `kolo-hoodie.webp` (alto 192), `kolo-hoodie-full.webp` (cuerpo entero, alto 420), `casa24-door.webp` (alto 96), `og-image.png` (para og:image / twitter:image) y reemplaza los favicons de `webapp/static/favicon/` a partir de `icon-1024.png`. El camino antiguo de Kolo (`brand_assets.py "/ruta/al/brand pack"`) sigue igual.
- **Tests:** `.venv/bin/python -m pytest -q tests`
- **Referencia visual:** `Explained.pdf` **no está en el repo público**: sus capturas muestran nombres de usuario reales de Discord. Lo guarda el dueño en `~/Downloads/v1.1 01_10_26/`.

## Pendiente manual

- Subidas al Developer Portal de Discord (icono, nombre, descripción, banners): ver `docs/discord-activity-checklist.md`, sección "2026-11-04 · Rebrand: El Wordle by Casa 24 — Developer Portal uploads".

## Plan

Rebrand "Casa 24 Wordle" → "El Wordle by Casa 24". **Explained.pdf es la referencia principal: si el plan y el PDF no coinciden, gana el PDF.**

### Decisiones (2026-11-04)

- Solo modo oscuro.
- Terms · Privacy y Borrar mis datos al pie de How to play.
- Se quitan tipo de teclado y modo fácil.
- Ámbar `#FFB800`.
- Medallas SVG 1/2/3.
- How to play igual que el PDF (BLUNT/FARTS/DREAM en inglés y, por ahora, también en español).
- Imágenes WebP; Portal en PNG.
- Stats como el PDF (fecha, n/6 verde si ganaste, Next word, timer, Share; sin "You won!" ni "View leaderboard"), y al terminar además Kolo al azar + grid limpio.

### Paleta

| Rol | Color |
|---|---|
| bg | `#0F1A12` |
| surface | `#17241A` |
| correct | `#2F7A48` |
| present | `#FFB800` (texto `#0A0B09`) |
| absent | `#2C302D` |
| key | `#5D6D61` |
| lime (botón de idioma) | `#EFFF5E` |
| win (marcador) | `#32DD65` |
| accent (X, pestaña activa) | `#FFB800` |
| texto | `#F4EFE6` |
| sutil | `#B9B0A3` |
| línea | `#34453A` |

Naranja de Kolo `#FF7944` solo para "You" y contadores.

### Header

Kolo hoodie + Titler + botón lima "EN ▾"; a la derecha info, trofeo, stats, puerta (casa24records.com; en Discord con `openExternalLink`).

### Leaderboard

Pestañas EN · ESP · MIX, medallas, X ámbar.

### Rail

Invite friends + mini-boards con la paleta nueva.

### Decisiones durante la implementación (owner, 2026-11-04)
- **Stats:** la ventana que se abre sola al terminar muestra además el Kolo al azar, el grid limpio y el ranking/estadísticas. Si tocas el ícono de stats (aunque ya hayas ganado) sale la ventana compacta del PDF: fecha, n/6 (verde si ganaste), Next word, timer, Share.
- **Teclado alfabético escondido:** sin Settings, **Ctrl+⌘+A** en Mac (Ctrl+Alt+Shift+A en otros) alterna QWERTY ↔ alfabético (recarga con `?layout=`; el servidor lo guarda en la cookie `keyboard_layout_<lang>`). Dvorak se quitó.
- **Developer view escondido:** sin tarjeta; **Ctrl+⌘+D** en Mac (Ctrl+Alt+Shift+D en otros) abre `/demo` (si hay `DEMO_PASSWORD`). Desde "Sin portada" (abajo) funciona en las páginas de juego de la web.
- ~~**Portada (`/`):** si no iniciaste sesión con Discord, landing con poca letra y mucha marca (título El Wordle, Kolo con hoodie, "Iniciar con Discord", "Jugar como invitado" es/en). Si ya iniciaste sesión, `/` te manda directo al juego `/lb/<idioma>`: el de la cookie `c24_lang` (la guarda el juego), si no el idioma de tu computadora (`Accept-Language`). `/?menu=1` muestra la landing igual.~~ Reemplazado el mismo día por "Sin portada".
- **Idioma en la web:** el botón lima "EN ▾" del header abre la misma ventana de idioma que en Discord; las opciones son links a `/lb/<code>` (con sesión) o `/<code>` (invitado).
- **Tamaños de banners:** el checklist del Portal (R13) pide Cover Art 16:9 y 13:11 de ≥1024 px; los banners entregados (680×240, 480×280) quizá no sirvan ahí. Preguntar al diseñador si el Portal los rechaza.
- **Sin portada (owner, 2026-11-04, después del rebrand):** "en web debe ser como el app, entras directo como guest y arriba a la izquierda dejas lo de discord". Se borraron `index.html`, `index.js` y el CSS de la landing; `/` manda directo al juego (con sesión de Discord → `/lb/<idioma>`, si no → `/<idioma>` como invitado; idioma: cookie `c24_lang`, si no `Accept-Language`, si no es). Discord va arriba a la izquierda del header del juego ("Iniciar con Discord" o tu avatar con su menú). Los avisos (`?login=failed|cancelled`, `?deleted=1`) llegan al juego como toast. `/?menu=1` ya no existe; el link de vuelta de `/leaderboard` y las páginas legales dice "Jugar/Play".
