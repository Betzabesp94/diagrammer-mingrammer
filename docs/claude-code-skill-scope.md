# Referencia para una futura Skill de Claude Code: "generar diagramas con `diagrams`"

> **Estado: documento de investigación y alcance. La skill NO está creada.**
> Este archivo es el insumo para correr `skill-creator` más adelante — no reemplaza ese paso.

## 1. Objetivo de la skill (propuesta)

Que Claude Code, al recibir un pedido de diagrama de arquitectura, **modele, valide y traduzca**
esa intención en un script `.py` correcto en `diagrams_src/`, usando la librería
[`diagrams`](https://diagrams.mingrammer.com/) de este repo (siguiendo la convención de
`plantilla.py`), y opcionalmente lo renderice con `render.sh` / `make render`.

Una distinción central del diseño: **"el código funciona" no es lo mismo que "el diagrama es
correcto"**. Un script puede ser Python válido, importar clases reales de `diagrams` y renderizar
sin errores en Graphviz, y aun así representar una arquitectura equivocada (una conexión que
falta, un servicio mapeado al ícono incorrecto, una topología que no es la que pidió el usuario).
Por eso la skill no es solo "Claude escribe Python": es "Claude modela la arquitectura, la valida,
y recién después la traduce a código" — ver secciones 4 y 6.

## 2. Referencia de la librería que la skill debe conocer

Extraída del código fuente instalado (`diagrams==0.25.1`, ver `.venv/lib/*/site-packages/diagrams/__init__.py`)
al momento de escribir este documento — **no como verdad permanente**:

> **Importante:** esta lista describe lo que existe en la versión instalada *hoy*. La skill no
> debe hardcodear `diagrams==0.25.1` ni esta lista de módulos como fuente de verdad en cada
> ejecución. Antes de generar código debe re-detectar, contra la instalación real:
> - la versión instalada (`importlib.metadata.version("diagrams")`),
> - los módulos y clases realmente disponibles (introspección real — `dir(modulo)`, intento de
>   `import` — nunca solo lo que "suena correcto" por conocimiento del modelo),
> - las convenciones vigentes del repo (`plantilla.py`, `render.sh`, `Makefile`,
>   `requirements.txt`).
>
> Si el repo actualiza la versión de `diagrams`, este documento puede quedar desactualizado en
> los detalles finos; la introspección en tiempo de ejecución es la que manda.

- **`Diagram`**: contexto principal (`with Diagram(...):`). Parámetros clave: `name`, `filename`
  (sin extensión), `direction` (`LR`/`TB`/`RL`/`BT`), `outformat` (string o **lista** de formatos),
  `show` (siempre `False` en código generado por la skill), `strict` (colapsa aristas duplicadas),
  `autolabel` (antepone el nombre de clase al label), `graph_attr`/`node_attr`/`edge_attr`.
- **`Cluster`** (alias `Group`): agrupamiento visual anidable; solo debe usarse para límites
  reales (VPC, subnet, namespace, dominio).
- **`Node`**: cada ícono es una subclase (`diagrams.aws.compute.EC2(label)`, etc.). Todo nodo
  debe crearse dentro de un `Diagram` activo (usa un contextvar global; si no hay uno, lanza
  `EnvironmentError`).
- **`Edge`** y los operadores `>>` (adelante), `<<` (atrás), `-` (sin dirección). Una lista a un
  lado del operador produce fan-out/fan-in automático.
- **Proveedores disponibles** (todos incluidos en el mismo paquete, sin instalaciones extra):
  `aws`, `gcp`, `azure`, `k8s`, `onprem`, `generic`, `custom`, `c4`, `programming`, `saas`,
  `alibabacloud`, `oci`, `ibm`, `digitalocean`, `openstack`, `outscale`, `elastic`, `firebase`,
  `gis`. Cada uno se organiza en submódulos por categoría (`compute`, `network`, `database`,
  `security`, `analytics`, `storage`, `integration`, `management`…).
- **`diagrams.custom.Custom(label, icon_path)`**: único caso de nodo que no viene de un módulo
  de proveedor — requiere una ruta a un PNG local. Es el fallback cuando no existe ícono oficial.
- **Dependencia externa dura**: Graphviz (`dot`) tiene que estar instalado en el sistema. La
  skill **no debe intentar instalarlo**; debe detectarlo (`render.sh --check` / `make check`) y
  avisar con instrucciones si falta, tal como ya hace este repo.
- **Convención de salida del repo**: `OUT = Path(__file__).resolve().parent.parent / "output" / "<nombre>"`,
  `FMT = os.getenv("FORMAT", "png")` — la skill debe generar el `.py` siguiendo exactamente este
  patrón (visto en `ejemplo_aws.py` y `plantilla.py`) para que `render.sh`/`make render` funcionen
  sin cambios.

## 3. La pregunta central: ¿qué formato de input le conviene a Claude Code?

Se evaluaron tres formatos de entrada para que Claude Code arme el `.py`: un **prompt tipo
Eraser** (DSL de nodo→nodo, ej. `Load Balancer > EC2 Web Server`), **código Mermaid**
(`flowchart`/`architecture-beta`), o un **prompt general en lenguaje natural**.

| Criterio | Prompt tipo Eraser | Código Mermaid | Prompt general (lenguaje natural) |
|---|---|---|---|
| Fidelidad topológica (quién se conecta con quién, sin que Claude tenga que inferir) | **Alta** — cada línea es una arista explícita; grupos con corchetes | Alta en `flowchart` (`-->`) y con `subgraph` para grupos | Media — depende de qué tan bien describa el usuario el flujo; Claude infiere |
| Mapeo directo a clase/ícono de `diagrams` (`EC2`, `RDS`, …) | **Alta** — sus labels ya suelen nombrar el servicio cloud tal cual (`"EC2 Web Server"`), casi 1:1 con el import correcto | Baja/Media — los nodos son cajas genéricas sin taxonomía de proveedor (salvo `architecture-beta`, aún experimental); hay que adivinar el servicio a partir de texto libre | Media/Alta — cuando el usuario nombra servicios reales (lo habitual al pedir un diagrama de arquitectura), Claude ya sabe mapear "un load balancer de AWS" → `ELB`/`ALB` |
| Fricción para quien pide el diagrama | Media — sintaxis nueva a aprender o generar | Media — el usuario tiene que "pensar en nodos y aristas" antes de escribir, aunque ya conozca Mermaid | **Baja** — es pedirlo como en una conversación normal |
| Redundancia con el resto del stack | Ninguna sintaxis `.eraser` existe hoy en este repo | **Alta**: este mismo repo es la contraparte de un proyecto en Mermaid (ver comparativa en el README); pedirle a Claude "convertí este Mermaid a `diagrams`" reabre la pregunta de cuál es la fuente de verdad | Ninguna — es la interfaz nativa de una skill de Claude Code |
| Escalabilidad en diagramas grandes/con muchas conexiones | Buena — bajo riesgo de "olvidar" una arista, cada una es una línea | Buena, mismo motivo | Peor **si no hay un paso intermedio** — en topologías con más de ~8-10 nodos, la prosa libre aumenta el riesgo de conexiones faltantes u ambiguas |

### Recomendación

**Input primario: prompt general en lenguaje natural.** Es la interfaz nativa de Claude Code, no
le exige al usuario aprender una sintaxis nueva, y no compite con Mermaid (que este mismo repo ya
posiciona como la opción cuando el diagrama tiene que vivir y diffear en un `.md`). Pedir código
Mermaid como input estándar mezclaría los dos paradigmas que el README compara explícitamente, y
no resuelve el problema real (mapear texto libre a un ícono de proveedor) mejor que un prompt
directo — solo le agrega sintaxis intermedia sin beneficio.

**Mitigación para el punto débil (topologías grandes/ambiguas):** en vez de un "paso de
razonamiento informal", esto se formaliza como un **modelo intermedio explícito** (sección 4):
la skill arma primero una representación estructurada de nodos, clusters y aristas, la valida, y
recién después la traduce a Python. Esto resuelve de raíz el problema de "conexiones que
desaparecen" sin imponerle al usuario ninguna sintaxis nueva.

**Atajos opcionales aceptados, no promovidos como flujo principal:**
- Si el usuario ya escribió una lista tipo Eraser o un diagrama Mermaid existente y pide
  "pasame esto a `diagrams`", la skill debe poder tomarlo como especificación estructurada y
  volcarlo directamente al modelo intermedio (mejor entrada que prosa, mismo destino).
- No se debe instruir al usuario a preferir ese camino: agrega fricción sin mejorar el resultado
  para el caso común.

## 4. Modelo intermedio de arquitectura (Architecture Intermediate Representation)

Esta es la mejora estructural más importante sobre la primera versión de este documento: intercalar
un **modelo intermedio** entre "intención del usuario" y "código Python", en vez de que Claude
pase directamente de una frase como *"CloudFront delante de un ALB que distribuye tráfico a ECS"*
a `CloudFront() >> ALB() >> ECS()`.

No tiene que ser un archivo que quede versionado en el repo — puede ser un objeto conceptual
interno del razonamiento de la skill. Su función es permitir **validar la arquitectura antes de
preocuparse por cómo representarla visualmente**. Forma aproximada:

```yaml
architecture:
  provider: aws

nodes:
  - id: cloudfront
    service: "Amazon CloudFront"
    diagrams_class: diagrams.aws.network.CloudFront
    confidence: exact

  - id: alb
    service: "Application Load Balancer"
    diagrams_class: diagrams.aws.network.ELB
    confidence: exact

  - id: ecs
    service: "Amazon ECS"
    diagrams_class: diagrams.aws.compute.ECS
    confidence: exact

clusters:
  - id: vpc
    type: vpc
    contains: [ecs]

edges:
  - source: cloudfront
    target: alb
    protocol: HTTPS
    type: network        # network | event | data | invocation | dependency | authentication

  - source: alb
    target: ecs
    protocol: HTTP
    type: network

constraints:
  internet_entrypoint: cloudfront
  requested_only: true    # la skill no agrega componentes no pedidos (ver sección 7)
```

### Por qué el campo `type` en las aristas

Una flecha no siempre significa una conexión de red directa. `S3 → Lambda` normalmente representa
una notificación de evento, no una llamada HTTP; lo mismo con `EventBridge/SQS/SNS/CloudWatch →
Lambda`. Distinguir `network` de `event`/`data`/`invocation`/`dependency`/`authentication` en el
modelo intermedio le permite a la skill decidir mejor cómo representar la arista en `diagrams`
(`A >> B` liso para una llamada directa, `A >> Edge(label="event", style="dashed") >> B` para un
evento asíncrono) en vez de dibujar todo con la misma flecha sólida.

### Niveles de confianza en el mapeo a `diagrams`

No todos los mapeos de "servicio mencionado por el usuario" → "clase de `diagrams`" tienen el
mismo grado de certeza. Cada nodo del modelo intermedio debe llevar una etiqueta:

| Nivel | Significa | Qué hace la skill |
|---|---|---|
| `exact` | El servicio nombrado tiene una clase 1:1 verificada en la librería instalada (ej. Amazon EC2 → `diagrams.aws.compute.EC2`) | Usarla directo, sin reportar nada especial |
| `inferred` | El usuario describió un rol/función ("servicio interno de procesamiento"), no un servicio puntual; la skill eligió una clase razonable | Usarla y **reportarla** para que el usuario la confirme |
| `generic` | No hay ícono oficial del proveedor para ese servicio | Usar `diagrams.generic.*` y reportarlo |
| `custom` | No hay ícono en ningún proveedor ni genérico aplicable | Usar `diagrams.custom.Custom` y pedir/reportar qué ícono se usó |
| `ambiguous` | Dos o más clases son igual de plausibles para lo descrito | Preguntar al usuario **solo si la ambigüedad afecta significativamente la arquitectura**; si no, elegir una interpretación razonable y reportarla (ver sección 7) |

**Regla dura, sin excepciones:** la skill nunca genera un `import` que no haya verificado contra
la instalación real (introspección de módulos/clases). Nunca asume que
`from diagrams.aws.bedrock import Bedrock` existe "porque suena correcto" — si el ícono no está,
se reporta como `FAIL` en la validación técnica (sección 6) y se degrada a `generic`/`custom` en
vez de inventar un path de import.

## 5. Scope propuesto de la skill

**Se activa cuando** el usuario pide crear/generar un diagrama de arquitectura (cloud, k8s,
on-prem, C4) y quiere el resultado como código versionable en `diagrams_src/` de este repo —no
como imagen suelta ni como Mermaid.

**Input aceptado:**
- Principal: descripción en lenguaje natural de los componentes, proveedor(es), agrupamientos
  (VPC/subnet/namespace) y flujo de datos.
- Alternativo: una lista estructurada tipo Eraser o un Mermaid existente, tratados como
  especificación ya resuelta (se vuelcan directo al modelo intermedio en vez de reinterpretarse
  como prosa).

**Proceso (pipeline propuesto):**
1. **Inspeccionar el repo y la instalación real** de `diagrams` (versión, módulos, clases,
   convenciones de `plantilla.py`/`render.sh`/`Makefile`) — nunca asumir lo descrito en la
   sección 2 como definitivo.
2. **Extraer la intención arquitectónica** del prompt (o del input estructurado alternativo).
3. **Construir el modelo intermedio** (sección 4): nodos, clusters, aristas con protocolo/tipo,
   constraints.
4. **Validar el modelo intermedio** — dimensiones de fidelidad y arquitectura (sección 6) —
   *antes* de escribir una sola línea de Python.
5. **Resolver cada nodo a una clase real** de `diagrams.<provider>.*` con su nivel de confianza
   (sección 4); si no hay ícono oficial, usar `diagrams.custom.Custom` y marcarlo explícitamente.
6. **Generar el `.py`** en `diagrams_src/<slug>.py` siguiendo el patrón de `plantilla.py`
   (`OUT` vía `__file__`, `FMT` vía `os.getenv`, `show=False`).
7. **Validación técnica/estática** del Python generado (sección 6).
8. **Renderizar** con `render.sh`/`make render` (o avisar si falta Graphviz, sin intentar
   instalarlo).
9. **Validar el artefacto renderizado**: que exista, que tenga tamaño > 0, que el proceso de
   Graphviz haya terminado sin error. Dado que la skill corre dentro de Claude Code —que es
   multimodal—, una revisión visual liviana del PNG generado (¿se ve razonable?, ¿coincide con lo
   pedido?) es más simple y más confiable que construir heurísticas de visión por computadora
   (cruces de líneas, densidad de nodos); esto último queda fuera de alcance (ver "Fuera de
   alcance").
10. **Producir el reporte de arquitectura** (sección 8): mapeos, validaciones, warnings.
11. **Separar recomendaciones de lo solicitado** (sección 7) en el mismo reporte.

**Output esperado — contrato explícito:**

```
Requerido:
  - diagrams_src/<slug>.py

Opcional (si Graphviz está disponible):
  - output/<slug>.png

Reporte requerido:
  - componentes detectados y su mapeo (con nivel de confianza)
  - clusters / boundaries identificados
  - conexiones generadas vs. esperadas
  - resultados de validación (técnica / fidelidad / arquitectónica)
  - warnings, separados de recomendaciones
```

**Fuera de alcance (non-goals):**
- No genera diagramas Mermaid ni administra el proyecto hermano en Mermaid.
- No es una skill genérica de diagramación de UI/wireframes/flowcharts no técnicos.
- No instala Graphviz ni otras dependencias de sistema — solo detecta y avisa.
- No soporta otros formatos de diagrama-como-código (PlantUML, draw.io, Structurizr) en esta
  primera versión.
- No mantiene estado entre diagramas: cada `.py` generado es independiente y editable a mano
  después.
- **No es un validador de AWS Well-Architected completo.** La sección 6 define un set chico y
  determinístico de reglas ilustrativas, no un motor exhaustivo — construir eso es un proyecto
  aparte y un riesgo de falsos positivos si se sobredimensiona en la v1.
- No hace análisis de imagen por visión artificial (conteo de cruces, densidad geométrica); usa
  en su lugar la capacidad multimodal de Claude para una revisión visual directa del PNG.
- No divide automáticamente un diagrama grande en varios archivos — solo advierte que
  convendría dividirlo (sección 6).
- No mezcla ni reordena niveles de abstracción (contexto / lógico / despliegue / infraestructura)
  por iniciativa propia; si el usuario pide un nivel, se respeta ese nivel.

**Riesgos / decisiones abiertas para cuando se implemente:**
- Cómo decidir entre `generic.*` y `Custom` cuando el servicio existe pero en un proveedor no
  mencionado por el usuario.
- Cómo tratar arquitecturas multi-cloud en un mismo diagrama (¿un `Cluster` por proveedor?).
- Si la skill debe renderizar siempre por default o solo generar el código y dejar el render
  como paso explícito del usuario.
- Versión mínima de `diagrams` a soportar si el repo actualiza `requirements.txt`.
- Cómo calibrar sin arbitrariedad los umbrales de "diagrama demasiado complejo" (sección 6) para
  que la advertencia sea útil y no ruido.
- Cómo evitar que las reglas arquitectónicas determinísticas generen falsos positivos que
  frustren al usuario (ver principio de no bloquear por `WARNING` en sección 6).
- Dónde vive el corpus de casos de prueba de la skill (sección 9) — probablemente en el paquete
  de la skill una vez creada con `skill-creator`, no en este repo.

## 6. Validación y calidad del output

La skill no debe considerar exitoso un diagrama únicamente porque el script Python sea válido y
Graphviz pueda renderizarlo. Debe validar tres dimensiones distintas:

### 6.1 Validación técnica — ¿el código funciona?

- El `.py` compila (`python -m py_compile diagrams_src/<slug>.py`).
- Los imports existen y las clases de `diagrams` usadas existen **en la instalación real**
  (introspección, no memoria del modelo — ver sección 4).
- Los parámetros usados en `Diagram`/`Cluster`/`Edge`/`Node` son válidos para la versión
  instalada.
- Hay un `Diagram` activo antes de crear cualquier `Node` (si no, la librería lanza
  `EnvironmentError` — debe evitarse, no capturarse después).
- `show=False`, `filename` sin extensión, `FORMAT` respetado vía `os.getenv`, `OUT` resuelto
  igual que en `plantilla.py`.
- No se agregan dependencias nuevas no autorizadas al `requirements.txt`.
- El render con Graphviz termina sin error (o, si Graphviz no está instalado, se informa el
  problema operacional en vez de fallar en silencio).

### 6.2 Validación de fidelidad — ¿el diagrama representa lo que pidió el usuario?

- Todos los nodos solicitados están representados (cobertura de nodos).
- Todas las conexiones explícitas están representadas — comparar aristas esperadas vs.
  generadas por conteo (`Expected edges: N / Generated edges: N / Missing: 0 / Unexpected: 0`)
  es suficiente para detectar el error típico de LLM donde una arquitectura larga
  (`A → B → C → D`) pierde algún tramo al traducirse.
- Los `Cluster` representan los boundaries mencionados (VPC, subnet, namespace), ni más ni menos.
- No se agregan componentes no solicitados sin marcarlos explícitamente como recomendación
  separada (sección 7).
- Los mapeos con confianza `inferred`, `generic`, `custom` o `ambiguous` quedan reportados.

### 6.3 Validación arquitectónica — ¿hay inconsistencias o riesgos evidentes?

Un conjunto **chico y determinístico** de reglas, no un motor de Well-Architected completo.
Sirven para detectar lo obvio, no para auditar exhaustivamente:

| Categoría | Ejemplos de chequeo |
|---|---|
| Networking | ¿Un componente marcado como interno queda alcanzable directo desde "Internet" sin ningún entry point (load balancer, API gateway, CDN)? |
| Seguridad | ¿Una base de datos (`RDS`, `Dynamodb`, etc.) aparece conectada directo a un nodo de entrada pública? |
| Disponibilidad | ¿El requisito menciona "producción" o "alta disponibilidad" y el diagrama muestra una única instancia/AZ sin ninguna nota al respecto? |
| Observabilidad | ¿El requisito menciona "arquitectura productiva" y no aparece ningún componente de logging/monitoreo? (esto es **solo una advertencia informativa**, nunca una razón para agregar servicios de oficio — ver sección 7) |
| Complejidad | ¿El diagrama tiene una cantidad de nodos que dificulta la lectura (aprox. >20-30, a calibrar)? Sugerir dividirlo, sin dividirlo automáticamente. |

Los hallazgos se clasifican en tres niveles:

- **ERROR** — impide considerar válido el output (ej.: un import que no existe, sintaxis Python
  inválida, una arista solicitada que no se generó).
- **WARNING** — problema potencial que requiere revisión humana, pero no bloquea la generación
  (ej.: base de datos single-AZ, ausencia de un componente de seguridad mencionado por el
  usuario).
- **INFO** — observación o recomendación (ej.: "no se muestran zonas de disponibilidad").

**Regla explícita: un `WARNING` nunca dispara una corrección silenciosa de la arquitectura
solicitada.** La skill reporta, no reescribe por su cuenta lo que el usuario pidió.

## 7. Principios de fidelidad arquitectónica

Estos principios van al contrato de comportamiento de la skill, no son negociables por defecto:

- **No inventar infraestructura.** El diagrama generado debe representar la arquitectura
  solicitada, no una versión "mejorada" imaginada por el modelo.
- **No introducir componentes** salvo que el usuario los haya pedido explícitamente o sean
  estrictamente necesarios para representar algo que sí pidió (ej.: un `Cluster` VPC implícito
  en "una instancia EC2 privada").
- **No asumir servicios AWS/GCP/Azure no mencionados** solo porque "así sería una arquitectura
  correcta" (ej.: no convertir `S3 → Lambda → DynamoDB` en una arquitectura de diez servicios con
  WAF, API Gateway, CloudWatch, KMS, etc. sin que se haya pedido).
- **No confundir una recomendación arquitectónica con un requisito.** El reporte debe separar
  siempre "arquitectura solicitada" (`Architecture fidelity: PASS/FAIL`) de "recomendaciones"
  (lista aparte, nunca aplicada automáticamente).
- **No modificar la topología solicitada silenciosamente** para resolver un `WARNING` o
  `INFO` de la sección 6.
- **Ante ambigüedad, preguntar solo si afecta significativamente la arquitectura**; si no,
  elegir una interpretación razonable y reportarla (nunca elegir en silencio sin dejar rastro en
  el reporte).
- **Distinguir siempre, en el reporte final, entre**: componentes solicitados, componentes
  inferidos/mapeados con baja confianza, y recomendaciones no incluidas en el diagrama.

## 8. Formato del reporte (ejemplo)

Los pasos 10 y 11 de la sección 5 deberían producir algo con esta forma (valores ilustrativos):

```
Generated:
  diagrams_src/customer-platform.py

Rendered:
  output/customer-platform.png

Validation
──────────
Syntax                    PASS
diagrams imports          PASS
Graphviz rendering        PASS
Topology coverage         PASS   (expected edges: 6, generated: 6, missing: 0)
Cluster boundaries        PASS
Architecture consistency  WARNING (1)

Architecture warnings
──────────────────────
[W001] RDS is represented as Single-AZ; the request mentioned "production".

Icon mapping
────────────
5 exact
1 generic  (no official icon for the described internal service)
0 custom

Recommendations (not applied)
──────────────────────────────
- Consider adding WAF in front of the public ALB.
- Consider Multi-AZ for the production RDS instance.
```

Esto es lo que convierte a la skill de "Claude escribe Python" a "Claude genera y valida un
artefacto arquitectónico versionable" — el reporte es tan parte del output como el `.py`.

## 9. Evaluación de la skill: casos de prueba sugeridos

No forma parte de este documento crear la infraestructura de tests todavía (la skill no existe),
pero conviene dejar planteado el corpus mínimo para cuando se implemente. `skill-creator` ya
soporta correr evals y benchmarks de una skill — ese es el lugar natural para estos casos, no una
carpeta nueva dentro de `diagrams_src/`.

| Caso | Qué prueba |
|---|---|
| AWS, 5 nodos (equivalente a `ejemplo_aws.py`) | Caso básico end-to-end |
| VPC con subnets anidadas | Clusters anidados |
| CloudFront → WAF → ALB → ECS → RDS | Topología con varias conexiones (cobertura de aristas) |
| Lambda + API Gateway | Mapeo de servicios serverless |
| Servicio sin ícono oficial (ej. uno nuevo de AWS aún no soportado por `diagrams`) | Fallback a `generic`/`custom`, nunca un import inventado |
| "Arquitectura productiva" con RDS single-AZ | Disparo de `WARNING` de disponibilidad |
| Multi-cloud (AWS + GCP en el mismo diagrama) | Manejo de múltiples proveedores |
| Mermaid o Eraser existente como input | Input alternativo (sección 3) |
| Arquitectura de 30+ componentes | Advertencia de complejidad, sin auto-split |
| Graphviz no instalado en el entorno | Manejo de error operacional, sin intentar instalar nada |
| Prompt con ambigüedad real (ej. "un balanceador" sin decir de qué proveedor) | Pregunta solo si la ambigüedad es significativa |

Cada caso, al definirse formalmente como eval, debería declarar un resultado esperado mínimo
(cantidad de nodos/edges/clusters, y qué warnings debería disparar) para poder evaluar la skill
de forma objetiva y no "a ojo".

## 10. Próximo paso

Con este documento como base, generar la skill formalmente con `skill-creator` (fuera del
alcance de esta tarea, tal como se pidió).
