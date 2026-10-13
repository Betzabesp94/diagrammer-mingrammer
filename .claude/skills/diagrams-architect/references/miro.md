# Publicar en Miro (MCP)

Si el MCP de Miro está conectado, el diagrama se publica además como **board editable**, con los
mismos íconos de AWS que el PNG. El `.diag` sigue siendo la fuente de verdad: el board es una copia
derivada, como el `.py` y el PNG. Probado el 13/10/2026 con `calificacion_leads` (ver "Qué se verificó").

## 1. Cuándo aplica

- **Se publica** cuando hay herramientas `canvas_*` de Miro disponibles (en este entorno, `mcp__claude_ai_Miro__canvas_*`).
  Si aparecen solo como herramientas diferidas, cárgalas con `ToolSearch` (consulta: `miro canvas`); si el servidor
  aún está conectando, espera ese resultado antes de decir que no hay Miro.
- **Solo después de que el pipeline termine en `PASS` o `WARN`.** Con `FAIL` no se publica nada.
- **Sin MCP de Miro**, el flujo normal no cambia: PNG + reporte, y el reporte dice "Miro: no disponible".
- Las herramientas `diagram_*`, `layout_*`, `context_*` y `doc_*` fueron retiradas el 14/09/2026. No las uses
  aunque el modelo las recuerde: la familia vigente es `canvas_*`.

## 2. Antes de enviar nada: destino y privacidad

Los diagramas son de clientes. Publicar en Miro envía a un servicio externo los textos del diagrama (labels, notas,
nombres de grupos) y deja los datos en la cuenta de Miro del usuario.

1. **Confirma el board destino** antes del primer envío de una conversación:
   - Si el usuario dio una URL de board, úsala.
   - Si no, pregunta si quiere un board nuevo. Para crearlo existe `board_create` (carga su esquema con `ToolSearch`),
     pero crear un board es una acción en la cuenta del usuario: confirma antes equipo o espacio y nombre.
2. **Nunca compartas** el board (`board_share`, `space_share`) ni cambies roles sin que el usuario lo pida.
3. **Los íconos son lo único público**: salen de jsDelivr (paquete de la librería `diagrams`). Nada del diagrama
   se sube a servicios públicos. Miro copia esas imágenes a su almacenamiento al crear.
4. Si el `.diag` marca datos personales o sensibles (por ejemplo un nodo "Datos personales"), menciónalo al pedir
   la confirmación del board.

## 3. Herramientas y orden

| Paso | Herramienta | Nota |
|---|---|---|
| 1 | `canvas_get_canvas_composer_skill` | Una vez por conversación. Sin argumentos devuelve el enrutador; luego `step="design"` y `step="dsl"`. El paso `dsl` trae la gramática del SVG y es largo: léelo completo. |
| 2 | `canvas_create_from_svg` | Crea el diagrama. `miro_url` es obligatorio en todas las `canvas_*`. |
| 3 | `canvas_read_as_svg` | Lee de vuelta un área (`scope_x/y/width/height`) para verificar. |
| 4 | `canvas_update_from_svg` | Itera sobre el `result_svg` más reciente. |
| — | `canvas_search` | Para ubicar contenido de un board que no creaste en esta conversación. |

No cargues `canvas_load_format_skill`: sirve para Mermaid, presentaciones y prototipos, no para este flujo.
El widget Mermaid (`data-type="diagram"`) tampoco se usa: el layout ya lo resuelve Graphviz y los íconos AWS van como
imagen. No se probó para este caso.

## 4. De IR a SVG de Miro

Entradas: `diagrams_src/<slug>.ir.json` (nodos, clusters, aristas, estilos) y `output/<slug>.svg` (posiciones que
calculó Graphviz). Genera el SVG de Miro **desde esos dos archivos**, no desde tu memoria del `.diag`.

### Íconos: URL pública con versión fija

El SVG de Graphviz ya trae, por nodo, la ruta del PNG: `.../site-packages/resources/<proveedor>/<categoría>/<archivo>.png`.
Lo que sigue a `site-packages/` se pega a este prefijo:

```
https://cdn.jsdelivr.net/gh/mingrammer/diagrams@<VERSIÓN>/resources/<proveedor>/<categoría>/<archivo>.png
```

- `<VERSIÓN>` es `env.diagrams` del reporte, sin prefijo `v` (por ejemplo `0.25.1`). Nunca `@latest`, ni una rama.
- Los nombres de archivo no se adivinan (`integration/sqs.png` da 404; el real tiene el nombre largo del servicio).
  Sácalos del `href` del SVG de Graphviz o de `Clase._icon` y `Clase._icon_dir`.
- Verifica cada URL distinta una sola vez con `curl -sIL <url>`: debe dar `200` y `content-type: image/png`.
  Si una da 404, ese nodo se dibuja como rectángulo con su label (ver abajo) y se reporta.
- El paquete de íconos nativo de Miro no se puede usar por API; no lo intentes.

### Elementos

| IR | Elemento en el SVG de Miro |
|---|---|
| Nodo con ícono | `<image id="<id del IR>" data-type="image" href="<URL jsDelivr>" x y width height>` de unos 100x100, más un `<textArea>` centrado debajo con el `label` (ancho fijo de 190 a 230, `text-align="center"`, `font-size="14"`) |
| Nodo sin ícono (nota, texto) | `<rect>` redondeado con `data-content` y el color del IR (`gv.fillcolor`) |
| Cluster de primer nivel | Un frame `<g data-frame="<label>">` con `fill` = `bgcolor` del cluster |
| Cluster anidado o con borde especial | `<rect rx="12">` con `fill`, `stroke` = `pencolor` y `data-content` arriba a la izquierda |
| Cluster con `style: dashed` | `stroke-dasharray="5,5"` en el rect. **Un frame no admite borde**, así que un grupo punteado es siempre un rect |
| Arista | `<line data-start data-end data-arrow="end">` entre los ids locales de las imágenes |
| Arista `<>` | `data-arrow="both"` |
| Arista `type: async` o `event`, o nodo `dashed` | `stroke-dasharray="5,5"` |
| Label de arista | `data-content` corto; Miro lo dibuja sobre la línea |

### Reglas del SVG

- **Orden de creación = z-order.** Primero los rects de cluster, luego los conectores, al final imágenes y textos.
- **Los frames no se anidan.** Un frame por cluster de primer nivel; lo que esté dentro es rect. Los conectores que
  cruzan frames funcionan, pero la spec recomienda evitarlo salvo que el diagrama lo pida: aquí suele hacer falta, está bien.
- Dentro de un frame las coordenadas son **relativas** a su `translate`; fuera, absolutas.
- Fija `data-start-side` y `data-end-side` según `direction` (`LR`: derecha a izquierda; `TB`: abajo a arriba) y usa
  `data-shape="straight"` o `"elbowed"`, nunca `curved`.
- Posiciones: toma las de Graphviz (el eje `y` del SVG de Graphviz es negativo y viene dentro de un `transform`;
  normaliza restando el mínimo) y escálalas para que dos nodos no queden a menos de 60 px. Un ícono es de 100 px.
- **Escapa** `&`, `<` y `>` en todo atributo y texto (`&amp;`, `&lt;`, `&gt;`). Un `&` sin escapar hace fallar todo el SVG.
  Sin saltos de línea dentro de `data-content`.
- Usa **los colores del `.diag`** (`gv.bgcolor`, `gv.pencolor`, `gv.fillcolor`). La guía de estilo "Bright Paper"
  que devuelve el composer son valores por omisión; la paleta que pidió el usuario tiene prioridad. De esa guía sí se
  respetan las reglas técnicas, no las estéticas.
- Texto largo: el `textArea` hace wrap por ancho y crece en altura. Deja al menos 60 px de aire bajo cada nodo, y
  tras crear reposiciona lo que choque (ver "Después de crear").
- Tope de `svg`: 200 000 caracteres por llamada. Un diagrama grande se divide por frame en varias llamadas
  (primero los frames y nodos, después los conectores entre frames); además avisa `SIZ001` o `SIZ002`.

## 5. Después de crear

1. **Lee la respuesta completa.** Revisa `failed_items` y `skipped`: si algo falló, corrígelo con `canvas_update_from_svg`.
2. **Auto-colocación.** Si hay contenido en el área pedida, Miro desplaza todo el lote y lo avisa
   (`auto-placement moved this batch by x=…`). Desde ese momento usa las coordenadas del `result_svg`, no las que enviaste.
3. **Dimensiones cambiadas.** Si la respuesta reporta ids con otra altura (los `textArea` crecen), reposiciona lo que se
   superponga con `canvas_update_from_svg` antes de dar el trabajo por terminado.
4. **Verifica con `canvas_read_as_svg`** sobre el área devuelta: mismo número de nodos (`<image>`), de aristas
   (`<line data-start>`) y de grupos que el IR. Que la lectura coincida prueba la estructura, **no** que se vea bien:
   el render no se puede ver desde aquí. Pide al usuario que abra el board y confirme, sobre todo con textos largos.
5. **Guarda el vínculo** en `diagrams_src/<slug>.miro.json` (la carpeta está ignorada por git):
   URL del board, `data-miro-id` del frame, y el mapa `id del IR` a `data-miro-id`. Sirve para actualizar sin duplicar.

## 6. Actualizar un diagrama ya publicado

- El cambio va primero al `.diag`; se regenera el IR y el PNG; después se actualiza el board. Nunca al revés.
- Parte del `result_svg` más reciente o de un `canvas_read_as_svg` fresco del área, y reutiliza los `data-miro-id`
  **tal cual**. Jamás inventes ni copies de memoria un `data-miro-id`.
- Elementos nuevos: sin `data-miro-id`. Elementos que cambian: con su `data-miro-id` y solo los atributos que cambian.
- `canvas_update_from_svg` es aditivo: quitar un elemento del SVG no lo borra. **Borrar** exige `data-deleted="true"`
  y es irreversible desde aquí: confirma con el usuario cada elemento antes de enviarlo.
- Si el usuario editó el board a mano, lee el área antes de actualizar y no pises sus cambios sin avisar.
  Pregunta si las ediciones manuales se deben conservar o si el `.diag` manda.
- Un widget con `data-locked="true"` o `data-read-only="true"` no se toca.

## 7. Qué se verificó (13/10/2026)

Prueba con 3 nodos, 2 conectores, un frame con color y un rect punteado en un board de prueba.

| Pregunta | Resultado |
|---|---|
| ¿Los conectores se enganchan a imágenes? | Sí. `data-start` y `data-end` aceptan `<image>` y se conservan en la lectura. No se probó mover un ícono a mano. |
| ¿Bordes punteados y colores por grupo? | Punteado en rect y en conectores sí; en frames no (solo `fill`). Color por grupo: `fill` del frame o del rect. |
| ¿Textos largos? | `textArea` con ancho fijo hace wrap y crece en altura (59, 79 y 98 px para 14 px de fuente). Falta confirmar el render. |
| ¿jsDelivr con versión fija? | Sí, `diagrams@0.24.4` y `@0.25.1` sirven `image/png`. |
| Lo que cambia Miro | Reescribe el `href` de las imágenes a `api.miro.com/.../resources/images/...`; pone `open_sans` y `#1a1a1a` si no fijas fuente ni color; devuelve los conectores con `x1=0 y1=0 x2=1 y2=1` (lo que vale son `data-start` y `data-end`). |

## 8. Qué reportar

Agrega al reporte final (ver `report_format.md`) una línea de Miro:

```
Miro:      <URL del board>?moveToWidget=<id del frame>   | o: no disponible / no publicado (motivo)
           N nodos · N aristas · N grupos · N íconos sin URL (lista)
```

Lista aparte cualquier cosa del PNG que el board no conserva, y deja claro que el `.diag` sigue siendo la fuente.

## 9. Fallos y degradación

- MCP desconectado o sin permisos: termina con PNG y reporte, y dilo. No reintentes en bucle.
- Error al parsear el SVG: casi siempre es un `&`, `<` o `>` sin escapar, o una comilla dentro de un atributo.
- URL de ícono con 404: no la sustituyas por otra al azar; dibuja el nodo como rect con label y repórtalo como inferido.
- Board sin permiso de edición: avisa al usuario; no crees otro board por tu cuenta.
