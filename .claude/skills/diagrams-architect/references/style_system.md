# Sistema de estilo (look tipo Miro)

El estilo vive en **un solo bloque** al inicio del `.py` generado, entre `# === STYLE ===` y
`# === END STYLE ===`. Fuera de él no puede haber ningún literal de color, fuente ni tamaño
(`validate_code.py` lo comprueba por AST). El look se logra con nodos nativos de `diagrams` (icono
oficial garantizado), zonas pastel por cluster, una sola familia sans y flechas finas y neutras.

## Variables

| Variable | Por defecto | Notas |
|---|---|---|
| `FONT_FAMILY` / `FONT_FAMILY_BOLD` | Helvetica / Helvetica-Bold | una sola familia; la jerarquía sale del tamaño y el peso |
| `FONT_SIZE_TITLE` / `_CLUSTER` / `_NODE` / `_EDGE` | 20 / 13 / 12 / 10 | al menos 13 px al DPI de salida (96) |
| `FONT_COLOR` | `#1F2933` | contraste ≥ 4.5:1 con cada zona y con el fondo |
| `PALETTE` | 5 zonas pastel, 1 acento | `bg`, `zones[5]`, `accent`, `border`, `edge` |
| `DIRECTION` | `LR` | también `TB`, `RL`, `BT` |
| `NODESEP` / `RANKSEP` | 0.70 / 0.95 | espacio entre nodos y entre niveles |
| `SPLINES` | `spline` | ver más abajo |
| `NODE_WIDTH` | 1.4 | **también dimensiona el icono**; no lo subas para "ensanchar" labels |
| `LABEL_WRAP` | 15 | caracteres por línea; el wrap se hace al generar, no al renderizar |
| `PENWIDTH_EDGE`, `PAD`, `CLUSTER_MARGIN` | 1.0 / 0.5 / 16 | |

Cambiar fuente, tamaño o paleta = editar solo este bloque.

## Cómo cambiarlo de forma persistente

- **En el `.diag`**: `style.FONT_SIZE_NODE: 13`, `style.LABEL_WRAP: 20`, `splines: ortho`, `direction: TB`.
  Se regenera siempre igual. Es la vía correcta.
- **Editando el bloque STYLE del `.py`**: sirve para probar. `check_determinism` lo reporta como `DET004`
  (INFO) y se pierde al regenerar. Editar cualquier otra parte del `.py` es `DET001` (ERROR).

## Reglas que el sistema aplica solo

- **Zonas**: cada cluster recibe un color distinto de sus hermanos y de su padre. Con más de 5 hermanos
  no hay colores suficientes: `CLU006` pide dividir el diagrama. `diagrams` colorea por profundidad
  (`depth % 4`), así que el generador pasa siempre `zone(i)`.
- **Aristas**: finas y neutras. El color o el trazo solo aparece con significado (`type` o `emphasis`)
  y entonces se genera una **leyenda** con una arista de muestra por trazo.
- **Etiquetas de arista**: con `splines=ortho` Graphviz no las coloca bien, así que el generador usa
  `xlabel`. Por defecto `SPLINES` es `spline`.
- **Aristas y tipografía**: `Edge` de `diagrams` fuerza su propia fuente en cada arista; el helper
  `link()` inyecta `EDGE_ATTR` para que el bloque STYLE gobierne también las flechas.
- **Atributos de `extensions`**: los de estilo (`penwidth`, `color`…) se promueven a constantes
  `EXT_<SUJETO>_<ATRIBUTO>` dentro de STYLE; los demás (`rank`, `minlen`…) quedan como literales.

## Fuentes (regla dura)

Nunca una fuente informal o hand-drawn (Comic Sans, Bradley Hand, Chalkboard…): no está garantizada
fuera de la máquina donde se genera y Graphviz la sustituye en silencio. Permitidas: Helvetica-Bold
(por defecto), Arial, Times-Roman.

## Limitaciones conocidas

- La leyenda ocupa bastante alto, porque `dot` ubica cada muestra como un componente aparte.
- `NODE_WIDTH` mayor que 1.4 agranda el icono hasta pisar el label.
- Los cruces de aristas (`LAY006`) son una cota aproximada.

## Descartado y por qué: tarjetas HTML

Se evaluó un patrón de tarjetas (tablas HTML-like de Graphviz con icono, título y descripción dentro del label). Se
descartó porque: (1) el `.py` deja de leerse como documentación: un nodo pasa de una línea a unas 15
de HTML; (2) el escape es frágil, con tres niveles de comillas, y un `&` en un label rompe el render
sin error de Python; (3) el estilo embebido en strings es inverificable por AST, así que la regla
"nada fuera de STYLE" no se podría comprobar; (4) el mismo look se consigue con clusters pastel, una
sola sans y jerarquía por tamaño. No lo reintroduzcas sin resolver esos cuatro puntos.
