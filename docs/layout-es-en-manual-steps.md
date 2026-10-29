# Rediseño + solo ES/EN + teclado QWERTY-Ñ: pasos manuales y estado

Fecha: 2026-10-29. Rama `layout-es-en`, fusionada en `casa24` y publicada en `main` (producción). Plan completo y fuentes: `docs/plan-layout-es-en.md`.

## Cómo retomar
1. `git checkout layout-es-en`
2. Pruebas: `.venv/bin/python -m pytest -q tests` (435 pasan) y `.venv/bin/python scripts/validate_words.py`.
3. Capturas antes/después: `screenshots/before-after/` (no van a git).
4. Sigue los pasos de abajo en orden.

## Qué cambió (resumen)
- **Diseño estilo NYT** (web y Discord, mismo código):
  - Barra superior con la marca a la izquierda y las acciones a la derecha.
  - El tablero va centrado, con un tamaño máximo, y el teclado justo debajo.
  - Los jugadores aparecen en una columna izquierda de tarjetas, que nunca achica el tablero.
  - Cabe sin scroll desde la vista mini de Discord (240×180) hasta 1920×1080.
- **Solo español e inglés:**
  - Se eliminaron los otros 8 idiomas: datos, código, pruebas y documentos.
  - Los enlaces viejos (`/fr`, `/lb/ko`…) redirigen a `/es` o `/en`.
  - El ranking tiene 3 pestañas: Combinado, ES y EN.
- **Idioma en Discord:**
  - Se usa el idioma de Discord de la persona: si empieza con "es" abre español; si no, inglés.
  - Si la persona ya eligió un idioma en ese dispositivo, se usa ese.
  - El selector solo aparece si Discord no responde.
  - Se cambia con el botón «ES ▾».
- **Teclado español:** QWERTY + Ñ (después de la L), sin tildes. El «Alfabético» sigue en Ajustes.
- **Colores de las vocales:** son flexibles. La «o» vale por «ó» y al revés. La Ñ siempre es su propia letra.
- **«Invitar amigos»:** dentro de Discord, abre la invitación oficial de Discord.
- **Jugadores presentes:** aparecen en «Jugando hoy» apenas abren el juego, aunque no hayan escrito ninguna palabra. Salen de la lista 5 minutos después de cerrarlo si no jugaron.

## Pasos manuales (en orden)

### 1. Revisar
- Mira las capturas en `screenshots/before-after/`: `sheet_before_*` contra `sheet_after_*`, para teléfonos, escritorio y Activity.
- Si quieres verlo en vivo:

  ```
  cd webapp && ../.venv/bin/flask --app app run --port 5050
  ```

  Luego abre http://127.0.0.1:5050.

### 2. Probar la Activity real en Discord (ya en producción)
Abre la Activity en Discord y revisa:
- **En la computadora:** ventana normal, ventana pequeña y vista mini (PIP).
- **En el teléfono:** vertical.
- **Además:** el idioma automático, «Invitar amigos», la Ñ y que la columna de jugadores no tape el tablero.

Si algo falla, avísame y lo corrijo o revierto.

### 3. Base de datos: hecho (2026-10-29)
Me conecté con el CLI de Vercel y conté las filas. **No había ninguna fila de los otros 8 idiomas**: solo existían datos en español e inglés. No se borró nada. La copia local de las credenciales se eliminó. El código nuevo además ignora cualquier idioma que no sea es/en.

### 4. Discord Developer Portal (Discovery)
- **App Directory / Discovery → Supported locales:** deja solo **Spanish** y **English, US** (quita los demás).
- **Descripción y resumen:** cambia cualquier «10 idiomas» por «español e inglés». Los textos sugeridos están en `docs/discord-publish-guide.md`.
- No hay que cambiar nada más. No hay scopes nuevos: «Invitar amigos» y el idioma usan `identify`, como antes.

### 5. Publicar: hecho
- Publicado en `main` el 2026-10-29 por pedido tuyo, después de que pasaran todas las pruebas. Vercel lo despliega solo.
- **Opcional:** borrar el stash viejo («step2 cut-down menu») con `git stash drop stash@{0}`. Ya no hace falta.

## Riesgos y cosas que decidimos no tocar
- **Listas de palabras sin cambios:** la palabra del día de es/en sigue igual. Hay una prueba que lo fija del 26-oct al 5-nov.
- **13 palabras sin forma sin tilde** (vacío/vació, envío/envió…): escritas sin tilde se resuelven a la respuesta del día si es una de ellas. Si no, se resuelven a la primera forma de la lista. Con las vocales flexibles, los colores son iguales.
- **Ventana de Discord muy baja (640×360):** las casillas quedan en 30 px, porque decidimos mantener tablero y teclado apilados en Discord de escritorio. Ponerlos lado a lado daría casillas más grandes, pero cambia esa decisión.
- **Discord no publica tamaños mínimos** para Activities. Probamos nuestro propio set: 240×180, 640×360, 875×400, 400×700 y 390×844.
- **Navegadores viejos:** pueden guardar estadísticas de invitado de idiomas eliminados. Se ignoran y no causan errores.
- **«Combinado»:** baja para quien jugó en otros idiomas, porque esas partidas ya no cuentan.
- **Presencia:** guardar «abrió el juego hoy» usa la misma fila de partida que ya existía. No hay datos nuevos. Si quieres, el texto de Privacidad puede añadir «y cuándo abriste el juego hoy (se borra a los 2 días)». No lo cambié sin tu OK.
- **Sigue pendiente, como antes:** convertir VT323 a WOFF2.
- **Accesibilidad:** foco visible (anillo naranja con borde interior), etiquetas traducidas en botones, teclas y tablero, y contraste de letras ≥ 4.5:1. La única excepción es el naranja sobre crema (2.27), que solo se usa con el anillo interior.

## Fuentes (Discord, consultadas 2026-10-29)
- Layout modes y orientación: https://docs.discord.com/developers/activities/development-guides/layout
- Safe areas en móvil: https://docs.discord.com/developers/activities/development-guides/mobile
- Patrones de diseño: https://docs.discord.com/developers/activities/design-patterns
- Referencia del SDK (`userSettingsGetLocale`, `openInviteDialog`): https://docs.discord.com/developers/developer-tools/embedded-app-sdk
- Objeto de usuario (`locale`): https://docs.discord.com/developers/resources/user
