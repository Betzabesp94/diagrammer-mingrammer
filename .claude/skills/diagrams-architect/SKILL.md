---
name: diagrams-architect
description: >-
  Genera y valida diagramas de arquitectura como código Python en diagrams_src/
  de este repo usando la librería diagrams (mingrammer). Modela primero la
  arquitectura (nodos, clusters, conexiones), resuelve cada componente a una
  clase real vía introspección de la instalación (nunca imports inventados),
  valida sintaxis/imports/topología/convenciones (OUT, FMT, show=False),
  renderiza con render.sh si Graphviz está disponible, y reporta mapeos,
  validaciones arquitectónicas básicas (exposición pública, seguridad, HA/AZ,
  complejidad) y recomendaciones separadas de lo pedido. Usar SIEMPRE que el
  usuario pida crear, armar, dibujar, actualizar o convertir a código un
  diagrama de arquitectura (AWS, GCP, Azure, Kubernetes, on-prem, multi-cloud,
  C4) para este repo, incluso si no menciona 'diagrams' explícitamente, por
  ejemplo 'dibujame la arquitectura de...', 'pasame este Mermaid a
  diagrams_src', 'agregale un WAF al diagrama de X' o 'quiero un diagrama
  estilo Miro/pizarra colaborativa con tarjetas e íconos'.
---

# diagrams-architect

Genera diagramas de arquitectura como código versionable (`diagrams_src/<slug>.py`)
usando la librería Python `diagrams`, siguiendo las convenciones de este repo.

La idea central: **"el código funciona" no es lo mismo que "el diagrama es
correcto"**. Un script puede ser Python válido, importar clases reales y
renderizar sin error en Graphviz, y aun así representar una arquitectura
equivocada — una conexión que falta, un ícono mapeado al servicio incorrecto, un
componente que el usuario no pidió. Por eso el flujo es: **modelar → validar →
recién ahí traducir a código**, no "escribir Python directo".

## Antes de generar nada: releer el estado real

No asumas versiones ni convenciones de memoria. Al empezar cada tarea:

1. Confirmá la versión de `diagrams` instalada y el entorno:
   ```bash
   .venv/bin/python .claude/skills/diagrams-architect/scripts/introspect_diagrams.py version
   ./render.sh --check   # avisa si falta Graphviz — nunca lo instales vos
   ```
2. Si algo en `diagrams_src/plantilla.py`, `diagrams_src/ejemplo_aws.py`, `Makefile`
   o `render.sh` parece distinto de lo descrito en
   `references/repo_conventions.md`, confiá en el archivo real, no en la
   referencia — y si notás una diferencia real, decilo en el reporte.

## Input aceptado

**Primario: pedido en lenguaje natural.** Es lo esperable — el usuario describe
componentes, proveedor(es), agrupamientos (VPC/subnet/namespace) y flujo de datos
en prosa. Vos armás el modelo intermedio a partir de esa descripción.

**Alternativo: una especificación ya estructurada** — un diagrama Mermaid
existente, una lista tipo "A → B → C", o un JSON/YAML que ya luce como el modelo
intermedio. Tratalo como una especificación ya resuelta: volcala directo al
modelo intermedio (sección siguiente) en vez de reinterpretarla como si fuera
prosa libre. No le pidas al usuario que reescriba su Mermaid en lenguaje natural.

## El pipeline

### 1. Construir el modelo intermedio (IR)

Antes de pensar en clases de `diagrams`, armá mentalmente (o en un JSON temporal
si el diagrama es grande y preferís no perder track) la estructura de
`references/ir_schema.md`: nodos con un `id` y un `service` tal como lo describió
el usuario, clusters para límites reales, edges con su `type`
(`network`/`event`/`data`/`invocation`/`dependency`/`authentication`), y
`constraints` (¿hay un entry point de internet? ¿se mencionó "producción"?).

En este paso **no resolvas todavía clases de diagrams** — solo capturá la
arquitectura tal como la pidieron. Esto es lo que evita que una topología larga
(A→B→C→D→E) pierda un tramo al traducirse: contás las aristas acá, antes de que
se disuelvan en código.

### 2. Resolver cada nodo a una clase real (nunca por memoria)

Para cada nodo, buscá la clase con el script de introspección — no confíes en que
un import "suena correcto":

```bash
PY=.venv/bin/python
SCRIPT=.claude/skills/diagrams-architect/scripts/introspect_diagrams.py
$PY $SCRIPT check aws.compute.EC2          # ¿existe exactamente ese path?
$PY $SCRIPT search "load balancer"         # no sé el nombre exacto de la clase
$PY $SCRIPT search bedrock                 # ejemplo real: "aws.bedrock" NO existe,
                                            # la clase real es diagrams.aws.ml.Bedrock
$PY $SCRIPT classes aws.network            # ver todo lo que trae un módulo
$PY $SCRIPT providers                      # aws, gcp, azure, k8s, onprem, generic, ...
```

Asigná el nivel de confianza correspondiente (`exact` / `inferred` / `generic` /
`custom` / `ambiguous`, tabla completa en `references/ir_schema.md`) y guardalo —
va al reporte final, no se pierde. Si `check`/`search` no devuelven nada
razonable, degradá a `diagrams.generic.*` (agnóstico de proveedor) o, como último
recurso, `diagrams.custom.Custom(label, icon_path)` con una ruta a un PNG local —
y reportalo explícitamente. Nunca generes un `from diagrams.x.y import Z` que no
haya pasado por este chequeo.

### 3. Validar el modelo intermedio arquitectónicamente — antes de escribir Python

```bash
.venv/bin/python .claude/skills/diagrams-architect/scripts/validate_architecture.py <ir.json>
```

Esto corre las cinco reglas deterministas de `references/architecture_rules.md`
(networking, seguridad, disponibilidad, observabilidad, complejidad) y devuelve
`findings` con severidad. Ningún finding de este script bloquea nada — todos son
WARNING/INFO — pero **tienen que llegar al reporte final tal cual**, nunca
resolverse en silencio cambiando la topología pedida.

### 4. Generar `diagrams_src/<slug>.py`

Seguí exactamente `references/repo_conventions.md` (que resume `plantilla.py` /
`ejemplo_aws.py`): `OUT` vía `Path(__file__)`, `FMT` vía `os.getenv`, `show=False`,
nombres de variable por rol, `Cluster` solo para límites reales, `direction`
según el tipo de arquitectura. No agregues nodos, edges ni clusters que no estén
en el IR del paso 1 — si te parece que falta algo importante (ej. un `Cluster`
VPC implícito al decir "una instancia privada"), agregalo pero marcalo
explícitamente como inferencia en el reporte, nunca en silencio.

**Dos patrones de rendering, misma arquitectura por debajo:**

- **Clásico (default):** `ClassName("label")` + `a >> Edge(...) >> b`. Más
  corto, ya cumple todas las convenciones — usalo salvo que el pedido diga lo
  contrario.
- **Design system "pizarra/Miro" (opcional):** cuando el usuario pide
  explícitamente una estética más visual/informal ("estilo Miro", "board
  colaborativo", "pizarra", tarjetas con ícono+descripción, flechas numeradas
  con badges), usá `service_card()` / `internal_card()` / `flow()` /
  `sticky_note()` — ver `references/design_system.md` y copiá el bloque de
  `assets/design_system_template.py`. Es una capa de *rendering* sobre el
  mismo IR: no agrega, quita ni reinterpreta nodos/edges/clusters respecto del
  paso 1, solo cambia cómo se dibujan.

### 5. Validar el `.py` generado (técnica + fidelidad)

```bash
.venv/bin/python .claude/skills/diagrams-architect/scripts/validate_diagram.py \
    diagrams_src/<slug>.py --ir <ir.json>
```

(Omití `--ir` si no armaste un JSON explícito del modelo — igual vas a obtener
`syntax`/`imports`/`diagram_context`/`conventions`, solo que sin el conteo de
fidelidad automático; en ese caso comparalo vos a mano contra el IR mental del
paso 1.)

Si `overall` es `FAIL`, **no está terminado**: mirá `failed_dimensions`, corregí,
y volvé a correr. Un import que no existe, un nodo creado fuera del
`with Diagram(...)`, o `missing_edges > 0` son bloqueantes — no se reportan como
"éxito con una advertencia".

### 6. Renderizar (si Graphviz está disponible)

```bash
make render FILE=<slug>.py
# o: ./render.sh <slug>
```

Si `render.sh --check` ya avisó que falta Graphviz, no lo intentes igual ni
instales nada — reportá el `.py` como generado y validado, y anotá en "Rendered:"
que falta Graphviz con la instrucción (`brew install graphviz` / etc., la misma
que ya imprime `render.sh`).

Si renderizó, y podés ver la imagen (sos multimodal), mirala: ¿se parece
razonablemente a lo pedido? Esto reemplaza heurísticas de visión por computadora
(cruces de líneas, densidad) — más simple y más confiable acá.

### 7. Reportar

Usá exactamente la estructura de `references/report_format.md`. El reporte no es
opcional ni un anexo — es lo que demuestra que la arquitectura fue validada, no
solo "escrita". Separá siempre tres cosas en la respuesta al usuario:

- **Lo solicitado** — tal como se generó.
- **Lo inferido** — nodos con confianza `inferred`/`generic`/`custom`/`ambiguous`,
  o componentes que agregaste sin que te lo pidieran explícitamente.
- **Recomendaciones** — findings de `validate_architecture.py` y cualquier otra
  sugerencia de Solutions Architect, listadas aparte, nunca aplicadas al `.py`
  sin que el usuario lo pida.

## Reglas duras (ver `references/architecture_rules.md` para el detalle completo)

- Nunca generes un import de `diagrams` que no haya sido verificado por
  `introspect_diagrams.py`.
- Nunca agregues infraestructura, servicios o componentes que el usuario no pidió,
  salvo que sean estrictamente necesarios para representar algo que sí pidió — y
  en ese caso, decilo.
- Un `WARNING` o `INFO` de validación nunca dispara una corrección silenciosa de
  la topología pedida.
- Ante ambigüedad, preguntá solo si cambia la arquitectura de forma significativa;
  si no, elegí una interpretación razonable y anotala en el reporte.
- No instales Graphviz ni ninguna dependencia — solo detectá y avisá.
- Un diagrama por archivo en `diagrams_src/`; no mezcles varios pedidos en un
  mismo `.py` salvo que el usuario lo pida así.
- **Tipografía: siempre `Helvetica-Bold`/`Helvetica`** (fallback `Arial`,
  después `Times-Roman`). **Nunca uses `Bradley Hand` ni otras fuentes
  "hand-drawn"**, ni siquiera si el pedido describe una estética
  informal/pizarra/Miro — la regla aplica tanto a `fontname=...` como a un
  `FACE="..."` dentro de un label HTML del design system;
  `scripts/validate_diagram.py` chequea las dos formas y lo marca como error.
  Conseguí el look "pizarra" con colores/clusters/cards/sticky notes (ver
  `references/design_system.md`), no con la fuente.

## Fuera de alcance

No generes Mermaid (ese es el proyecto hermano — si el usuario quiere Mermaid,
decíselo en vez de improvisar). No es una skill de wireframes/UI/flowcharts no
técnicos. No es un validador de Well-Architected exhaustivo — ver
`references/architecture_rules.md`. No dividís automáticamente un diagrama
grande, solo lo advertís.

## Recursos de esta skill

| Archivo | Cuándo leerlo |
|---|---|
| `scripts/introspect_diagrams.py` | Siempre, para resolver cada nodo a una clase real (paso 2) |
| `scripts/validate_diagram.py` | Siempre, después de generar el `.py` (paso 5) |
| `scripts/validate_architecture.py` | Cuando armaste el IR y antes de generar el `.py` (paso 3) |
| `references/ir_schema.md` | Al construir el modelo intermedio — esquema completo y niveles de confianza |
| `references/architecture_rules.md` | Detalle de las 5 reglas arquitectónicas y los principios de fidelidad no negociables |
| `references/report_format.md` | Formato exacto del reporte final |
| `references/repo_conventions.md` | Anatomía de un `.py` de este repo, si necesitás más detalle que el resumen de arriba |
| `references/design_system.md` | Patrón opcional "pizarra/Miro": cards de servicio, badges numerados, estilos semánticos de conexión |
| `assets/design_system_template.py` | Bloque copy-paste con los helpers del design system (`service_card`, `internal_card`, `flow`, `sticky_note`) |
