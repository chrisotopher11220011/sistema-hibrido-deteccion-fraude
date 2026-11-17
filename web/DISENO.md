# Sistema de diseño de la página de simulación

Definido con la skill `frontend-design` antes de escribir código (plan en `docs/planes/fase-6.md`). Las gráficas siguen la skill `dataviz`. Los valores viven como variables CSS al principio de `estilos.css`; este documento explica por qué son esos.

## Concepto: mesa de verificación

Una mesa de un banco donde se verifican transacciones. La transacción actual es una **boleta** con el borde perforado de los comprobantes; el nivel cae sobre ella como un **sello** de tinta. Es lo único llamativo de la página. Contadores, gráficas, bandeja e historial son sobrios y quedan sobre el papel.

Principios:

1. La boleta y su sello son el momento memorable; el resto, silencioso.
2. Cada nivel se dice tres veces: color, forma y palabra.
3. Primero el veredicto, después la verdad: la etiqueta real aparece tras una pausa y en un recuadro aparte.
4. Las palabras dicen lo que el sistema hace: «señala para revisión», nunca que hubo fraude.

## Color

| Variable | Claro | Oscuro | Uso |
|---|---|---|---|
| `--papel` | `#e9eeea` | `#0e1715` | Fondo: papel de seguridad verde grisáceo |
| `--hoja` | `#f7f9f6` | `#15211e` | Paneles, boleta y gráficas |
| `--tinta` | `#13302c` | `#e3ece7` | Texto principal: tinta de billete |
| `--tinta-2` | `#48605b` | `#a9bab3` | Texto secundario |
| `--filete` | `#c6d2cc` | `#2a3a36` | Líneas finas y bordes |
| `--sello` | `#4b2e83` | `#b7a3f0` | Acciones, foco e interacción |

### Niveles

| Nivel | Forma | Marca claro / oscuro | Texto claro / oscuro |
|---|---|---|---|
| Sin alerta | Círculo hueco | `#2a78d6` / `#3987e5` | `#1c5cab` / `#86b6ef` |
| Revisión recomendada | Rombo | `#c98300` / `#c98500` | `#7a5000` / `#e3a83a` |
| Alerta prioritaria | Triángulo | `#c7305f` / `#e85682` | `#a3224b` / `#f08aa8` |
| Error de evaluación | Aspa, borde discontinuo | sin color propio (`--tinta-2`) | `--tinta-2` |

Las tres marcas de color pasan el validador de `dataviz` con `--pairs all` en los dos temas (banda de luminosidad, croma, separación para daltonismo ≥ 8 y visión normal ≥ 15):

```
node scripts/validate_palette.js "#2a78d6,#c98300,#c7305f" --mode light --surface "#f7f9f6" --pairs all
node scripts/validate_palette.js "#3987e5,#c98500,#e85682" --mode dark --surface "#15211e" --pairs all
```

El ámbar claro queda en 2,95:1 frente a la hoja (aviso del validador): por eso el texto usa la variante oscura y el historial ofrece los mismos datos en una tabla. El verde se evitó para «sin alerta» porque se lee como «aprobada» o «legítima», y el sistema no afirma eso.

## Tipografía

Una sola familia: **Atkinson Hyperlegible Next** (variable, pesos 200–800), del Braille Institute, con licencia SIL OFL 1.1 (`fuentes/OFL.txt`). Se eligió porque distingue caracteres parecidos (`0` con barra frente a `O`, `1`, `l` e `I`), que es lo que pide un proyector y un público con distintas capacidades visuales. Se incluye solo el subconjunto latino (34 KB), servido por la API.

Escala de tercera mayor sobre 16 px: 13, 16, 20, 25, 31, 39 y 49 px (`--t-1` a `--t5`). Cifras tabulares en tablas, contadores y ejes. Sin mayúsculas en etiquetas ni monoespaciada.

## Espacio y forma

Espaciado en múltiplos de 4 px (`--e1` a `--e7`). Radio de 6 px en paneles y 4 px en botones. Una sola sombra, la de la boleta. Controles de al menos 44 px de alto.

## Disposición

Alineada a la izquierda. Una columna hasta 832 px (la ventana en mosaico de Hyprland, unos 640 px, cabe sin desbordar); dos columnas desde 832 px; boleta y cuadro lado a lado desde 1152 px.

## Componentes

| Componente | Clase | Notas |
|---|---|---|
| Boleta del caso | `.boleta` | Borde perforado (`::before`), único elemento con sombra |
| Sello del nivel | `.sello[data-nivel]` | Borde doble, rotado 1,5°; animación única al llegar, desactivada con «reducir movimiento» |
| Nivel en línea | `.nivel[data-nivel]` | Icono más nombre, en historial, bandeja y leyenda |
| Estado | `.estado[data-tipo]` | Cargando, listo, en curso, pausa, fin y error; siempre dice qué hacer |
| Pendiente | `.pendiente[data-nivel]` | Borde izquierdo del color del nivel |
| Botones | `.boton`, `--principal`, `--discreto` | El principal es la acción de la zona |

## Gráficas

- **Puntuación frente a umbrales:** puntos de 9 px con anillo de 2 px del color de la hoja, eje y único, umbrales rotulados directamente, leyenda arriba, globo con ratón y con teclado (flechas), área de toque de 24 px. Se dibuja en `<canvas>` para seguir fluida con miles de puntos.
- **Línea de tiempo de alertas:** una marca por transacción en la misma escala horizontal; la altura crece con el nivel.
- **Matriz de confusión:** tabla HTML 2×2.
- **Pista del caso:** la puntuación frente a los dos umbrales.
- **Variables que más pesaron:** barras finas de un solo color, sin leyenda.

El historial es la vista en texto de todas las gráficas.

## Modos

- **Temas:** el del sistema por defecto; el botón «Tema» alterna sistema, claro y oscuro, y se recuerda.
- **Presentación:** letra al 125 %, texto secundario con el contraste del principal, bordes más marcados y foco de 4 px. Las gráficas escalan su letra con la página.
- **Colores forzados:** bordes y barras usan `CanvasText`.
