# Guía para actualizar el sitio

Esta guía es para el refugio. No necesitas saber programar: casi todo se cambia
en **dos archivos de texto** dentro de la carpeta `data`.

Ábrelos con cualquier editor de texto (TextEdit en Mac, Bloc de notas en Windows,
o Visual Studio Code). Guarda siempre en formato **texto plano**, no en Word.

---

## Regla de oro

Los archivos `.json` son quisquillosos con la puntuación:

- Cada dato va entre **comillas dobles**: `"Milo"` ✅ · `'Milo'` ❌
- Cada línea termina en **coma**, menos la última de cada bloque.
- Si borras una llave `{` o un corchete `[` de más, el sitio deja de cargar.

**Antes de tocar nada, haz una copia del archivo.** Si algo se rompe, la
recuperas y listo. También puedes pegar el archivo en https://jsonlint.com
para que te diga si tiene un error y en qué línea.

---

## Publicar un animal nuevo

En `data/animales.json`, copia un bloque completo (desde `{` hasta `}`), pégalo
antes del `]` final, pon una coma entre los dos bloques y cambia los datos.

Qué significa cada campo:

| Campo | Qué poner |
|---|---|
| `id` | Un apodo corto, sin espacios ni acentos. Debe ser distinto al de los demás. |
| `nombre` | El nombre como se ve en la página. |
| `especie` | `perro` o `gato`. |
| `sexo` | `macho` o `hembra`. |
| `edad_meses` | La edad **en meses**. Un año = 12, dos años = 24. La página lo convierte sola. |
| `peso_kg` | Sólo el número. |
| `tamano` | `chico`, `mediano` o `grande`. |
| `color` | El color del recuadro: `arena`, `lavanda`, `coral`, `turquesa` o `menta`. |
| `foto` | La ruta de la foto, por ejemplo `img/animales/nina.jpg`. |
| `urgente` | `true` le pone la etiqueta roja «lleva mucho esperando». `false` la quita. |
| `esterilizado`, `vacunado`, `desparasitado` | `true` o `false`. |
| `convive` | `true` o `false` para niños, perros y gatos. **Esto alimenta los filtros de búsqueda**, contéstalo con cuidado. |
| `cuota` | Sólo el número, en pesos. |
| `es` / `en` | El texto en español y en inglés: `resumen` (una línea), `historia` (el párrafo largo) y `caracter` (dos o tres palabras). |

### Las fotos

- Cuadradas, mínimo 1000 × 1000 píxeles.
- El animal centrado, mirando a la cámara si se puede.
- Guárdalas en `img/animales/` con el mismo `id` del animal: `nina.jpg`.
- Menos de 400 KB cada una, para que la página cargue rápido en celular.

Los dibujos que dicen **«foto pendiente»** son provisionales. Mientras aparezcan,
es que a ese animal todavía le falta su foto real.

---

## Cuando un animal ya fue adoptado

Borra su bloque completo de `animales.json`, desde su `{` hasta su `}`, y cuida
que no quede una coma suelta antes del `]` final.

Acuérdate de bajar el número de `en_refugio` en `data/config.json`
y de subir el de `adoptados`.

---

## Cambiar datos del refugio

Todo está en `data/config.json`: dirección, horarios, teléfono, WhatsApp,
redes sociales, CLABE, enlaces de PayPal y Mercado Pago, cifras, montos de
padrinazgo y lista de necesidades.

**El WhatsApp se escribe sin `+` ni espacios**, con la clave del país y el 1 de
celular: `5219841234567`. Si este número está mal, **ninguna solicitud llega**.
Es lo primero que hay que revisar si dejan de escribirte.

Para quitar un medio de donación de la página, cambia su `activo` a `false`.

---

## Después de guardar

1. Recarga la página en el navegador.
2. Si no ves el cambio, abre el sitio con **Cmd + Shift + R** (Mac) o
   **Ctrl + F5** (Windows) para forzar la recarga.
3. Si la página aparece vacía o sin animales, es que el archivo `.json` tiene un
   error de puntuación: recupera tu copia de respaldo.

---

## Lo que este sitio **no** hace

- No guarda ningún dato: las solicitudes llegan a tu WhatsApp y viven ahí.
- No cobra ni procesa pagos: los botones de donación mandan a PayPal y
  Mercado Pago, que son quienes cobran.
- No manda correos automáticos.

Esto está declarado en el aviso de privacidad. Si algún día se agrega un
formulario que sí guarde datos, o una herramienta de estadísticas, hay que
actualizar ese aviso.
