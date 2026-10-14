---
name: diagrams-architect
description: >-
  Genera y valida diagramas de arquitectura como código Python (librería diagrams de mingrammer)
  en este repo, de forma determinista y con estilo limpio tipo Miro. El modelo describe la
  arquitectura en un DSL corto (.diag); los scripts la convierten a un IR, generan el .py,
  verifican sintaxis, imports, fidelidad, texto, layout y estilo, renderizan con Graphviz y
  reportan mapeos de iconos, avisos de arquitectura (exposición pública, seguridad, alta
  disponibilidad) y recomendaciones por separado. Usar SIEMPRE que el usuario pida crear, armar,
  dibujar, actualizar, ajustar o pasar a código un diagrama de arquitectura (AWS, GCP, Azure,
  Kubernetes, on-prem, multi-cloud, C4) para este repo, aunque no mencione 'diagrams'. Ejemplos:
  'dibuja la arquitectura de...', 'arma un diagrama de...', 'convierte este Mermaid a diagrams_src',
  'pasa esto a código', 'agrega un WAF al diagrama de X', 'actualiza el diagrama con una cola',
  'diagrama estilo Miro con íconos de AWS', 'súbelo a Miro', 'ponlo en el board', o un texto con
  sintaxis tipo eraser.io (`A > B`). Si el MCP de Miro está conectado, publica además el diagrama
  como board editable con los mismos íconos.
---

# diagrams-architect

El modelo **modela** la arquitectura; los scripts **generan y verifican**. Nunca se escribe el `.py`
a mano: sale del IR (`diagrams_src/<slug>.ir.json`), que sale del `.diag`. Mismo `.diag` y mismas
versiones producen el mismo `.py`, byte a byte, y el mismo render.

> **Carpetas.** `diagrams_ref/` guarda las referencias versionadas (`plantilla.diag`, `ejemplo_aws.diag`).
> `diagrams_src/` es donde van tus diagramas y está en `.gitignore`: nunca los agregues a git.

## Flujo

1. **Escribe `diagrams_src/<slug>.diag`.** Si el pedido viene en lenguaje natural, tradúcelo tú a ese DSL
   (no al `.py` ni al IR). Si ya viene con sintaxis tipo eraser o es un Mermaid, pásalo al DSL tal cual.
2. **Ejecuta** `make diagram IN=diagrams_src/<slug>.diag`. Corre en orden, y se detiene en el primer ERROR:
   `parse_dsl` → `resolve_ir` → `validate_ir` → `validate_architecture` → `generate_diagram` →
   `validate_code` → render → `validate_layout` → `check_determinism`.
3. **Lee** `output/<slug>.report.json`. Si `overall` es `FAIL`, corrige **el `.diag`** y repite.
4. **Mira el PNG** como control final: ¿se parece a lo pedido?
5. **Publica en Miro si está disponible** (ver abajo). Con el MCP de Miro conectado se hace siempre, salvo que el pipeline
   termine en `FAIL` o el usuario diga que no.
6. **Reporta** según `references/report_format.md`, separando lo solicitado, lo inferido y las recomendaciones.

Antes de empezar, `./render.sh --check` indica si falta Graphviz. Si falta, no lo instales: genera y
valida el `.py`, y avisa en el reporte con la instrucción de instalación.

## Miro (MCP)

Después de un pipeline en `PASS` o `WARN`, comprueba si hay herramientas `canvas_*` de Miro (si están diferidas,
`ToolSearch` con `miro canvas`). Si las hay, publica el diagrama como board editable; si no, sigue con PNG y reporte
y avisa "Miro: no disponible". El procedimiento completo está en `references/miro.md`; lo esencial:

- **Un board por proyecto, un frame por diagrama.** El proyecto sale de `project:` en el `.diag` (si falta, pregunta y
  agrégalo) y su board de `diagrams_src/miro_boards.json`. Si el proyecto no tiene board, pregunta si crear uno
  (`board_create`) o usar una URL; nunca crees, reutilices un board de prueba ni mezcles proyectos sin confirmación.
- **Orden:** `canvas_get_canvas_composer_skill` (pasos `design` y `dsl`, una vez por conversación) →
  `canvas_create_from_svg` → `canvas_read_as_svg` para verificar → `canvas_update_from_svg` para iterar.
  Las herramientas `diagram_*`, `layout_*`, `context_*` y `doc_*` fueron retiradas: no las uses.
- **El SVG sale del IR y del SVG de Graphviz** (posiciones y ruta del PNG de cada nodo), no de memoria.
- **Íconos como imagen desde jsDelivr con versión fija**: `https://cdn.jsdelivr.net/gh/mingrammer/diagrams@<env.diagrams>/resources/<proveedor>/<categoría>/<archivo>.png`.
  Verifica la URL (`200`, `image/png`); si falla, el nodo se dibuja como rect con label y se reporta.
- **Grupos:** el diagrama es un frame; cada cluster es un rect de color dentro, en columnas por capa con la banda
  transversal abajo (un frame no admite borde, así que lo punteado siempre es rect). Conectores antes que nodos
  (el orden de creación es el z-order) y `&`, `<`, `>` escapados.
- **Verifica y reporta:** revisa `failed_items`, reposiciona lo que Miro redimensione, compara conteos con el IR y pide
  al usuario que mire el render; la lectura prueba la estructura, no la apariencia.
- **El `.diag` manda.** Los cambios se hacen en el `.diag` y se re-publican con los `data-miro-id` guardados en
  `diagrams_src/<slug>.miro.json`. Borrar elementos del board siempre se confirma antes.

## El DSL en un vistazo

```
title: Pedidos
direction: LR
entrypoint: Cliente          // nodo expuesto a internet
production: true

Cliente [icon: aws-users]
Sistema [boundary: true] {   // grupo; se anidan
  API [icon: aws-api-gateway, label: "API de pedidos"]
  Cola [icon: aws-sqs]
  Datos [icon: aws-dynamodb, tag.multi_az: true]
}
Cliente > API: "HTTPS"       // > < <> -   |   A > B, C   |   etiqueta tras ':'
API > Cola: "publica evento" [type: event]
Cola > Datos: "escribe"
```

Operadores: `A > B`, `A < B`, `A <> B`, `A - B`, fan-out `A > B, C` y etiqueta `A > B: "HTTPS"`.
Gramática completa, atributos y errores: `references/dsl.md`.

## Reglas al escribir el `.diag`

- **Una arista por línea** y **etiquetas específicas**: un verbo o un protocolo (`"HTTPS"`, `"lee"`, `"publica evento"`),
  nunca `"usa"` ni `"conecta"`.
- **Iconos reales**: usa `icon: <proveedor>-<servicio>`. Nunca escribas ni inventes un import. Para buscar
  una clase: `.venv/bin/python .claude/skills/diagrams-architect/scripts/introspect_diagrams.py resolve <nombre> --provider aws`
  (o `search <texto>`). Si no existe, el icono cae a uno genérico y se reporta (`RES003`).
- **Grupos solo para límites reales** (VPC, subred, namespace; `boundary: true`). Evita grupos de un solo
  nodo y más de 5 grupos hermanos.
- **Declara `entrypoint:` y `production:`** si corresponde: activan las reglas de seguridad y alta disponibilidad.
- **Cada nodo debe tener aristas**, o marcarse `standalone: true`.
- No agregues nodos, aristas ni grupos que el usuario no pidió. Si algo implícito hace falta (por ejemplo, la VPC
  de "una instancia privada"), agrégalo y repórtalo como inferido.

## Cómo leer el reporte

`overall` es `PASS`, `WARN` o `FAIL`. Lee `overall`, `counts` y los ids de `findings`; abre
`references/validations.md` solo para los ids que aparezcan.

- **ERROR** (bloquea): corrige el `.diag`. Ejemplos: `PAR001` sintaxis, `CONN001` arista a un nodo inexistente,
  `CLU004` labels de grupo repetidos, `CLU006` más de 5 grupos hermanos, `FID*` el código no es el IR.
- **WARNING**: se reporta siempre, con su id. Ejemplos: `CONN003` nodo huérfano, `TXT001` label largo,
  `LAY001`–`LAY008` problemas de layout, `ARQ*` avisos de arquitectura.
- **INFO**: informa (icono inferido, leyenda, versiones).

**Nunca cambies la topología pedida para callar un warning**: se reporta y el usuario decide. Un warning de
arquitectura (`ARQ*`) es una recomendación, no un requisito, y no se aplica al diagrama.

## Estilo

El estilo vive en un único bloque `# === STYLE ===` del `.py` (fuente, tamaños, paleta, dirección, separaciones,
splines). Para cambiarlo de forma persistente usa directivas en el `.diag`: `style.FONT_SIZE_NODE: 13`,
`style.LABEL_WRAP: 20`, `splines: ortho`, `direction: TB`. Editar el bloque en el `.py` sirve para probar y se
pierde al regenerar. Detalle, paleta y contraste: `references/style_system.md`.

## Reglas duras

1. **Nunca edites el `.py` ni el `.ir.json`**: se regeneran. Cualquier cambio va en el `.diag`.
2. **Nunca instales Graphviz** ni nada del sistema por tu cuenta.
3. **Nunca uses una fuente hand-drawn o informal** (Comic Sans, Bradley Hand…): solo Helvetica, Arial o Times-Roman.
4. **Nunca agregues a git** archivos de `diagrams_src/` ni de `output/`.
5. **Registra versiones** (`env` del reporte: `diagrams` y Graphviz) en el reporte final.
6. Los archivos escritos a mano en `diagrams_src/` se validan (`make validate FILE=...`), no se regeneran.
7. **Nunca publiques en Miro con el pipeline en `FAIL`**, ni envíes datos a un board que no sea el del proyecto,
   ni compartas un board, ni borres elementos sin confirmación. Solo los íconos viajan a servicios públicos.

## Fuera de alcance

No genera Mermaid (existe un proyecto hermano para eso); no audita Well-Architected completo; no divide un
diagrama grande por su cuenta (solo avisa con `SIZ001`/`SIZ002`/`LAY008` y sugiere dividir); no mezcla
niveles de abstracción por iniciativa propia.

## Recursos

| Archivo | Cuándo leerlo |
|---|---|
| `references/dsl.md` | escribir o corregir un `.diag`; un error `PAR001` |
| `references/validations.md` | cualquier id de finding del reporte |
| `references/style_system.md` | cambiar fuente, tamaño o paleta; labels que desbordan; `ortho` |
| `references/ir_schema.md` | depurar el IR o un error `SCH*` |
| `references/architecture_rules.md` | avisos `ARQ*` y principios de fidelidad |
| `references/miro.md` | publicar o actualizar un diagrama en Miro con el MCP |
| `references/report_format.md` | redactar la respuesta final |
| `references/repo_conventions.md` | carpetas, comandos y forma del `.py` generado |
| `scripts/` | `pipeline.py` orquesta todo; los demás se pueden ejecutar solos para depurar |
| `evals/pipeline_evals.json` | casos verificables por script (`make evals`) |
