# Catálogo de findings

Cada script devuelve el mismo contrato JSON: `overall` (`PASS` | `WARN` | `FAIL`), `counts` y
`findings[]` con `id`, `severity`, `message`, `where`, `subject`, `hint`. `make diagram` los junta en
`output/<slug>.report.json`. Lee primero `overall` y `counts`, y vuelve aquí solo por los ids que aparezcan.

- **ERROR** bloquea: corrige el `.diag` y repite. **WARNING** merece revisión humana. **INFO** informa.
- **Nunca cambies la topología pedida para callar un WARNING**: se reporta, no se corrige en silencio.
- Exit code: 0 sin ERROR, 1 con ERROR, 2 si falla la herramienta.

## Entrada y esquema

| Id | Sev. | Significa | Remedio |
|---|---|---|---|
| PAR001 | ERROR | error de sintaxis en el `.diag`, con `línea:columna` | corregir esa línea (ver `dsl.md`) |
| SCH001 | ERROR | el IR no cumple `ir.schema.json` | revisar el campo indicado en `where` |
| SCH004 | ERROR | id o variable duplicados | renombrar uno de los dos |
| SCH005 | ERROR | cluster con prefijo reservado `cluster_` | renombrar el grupo |
| SCH006 | ERROR | referencia a un cluster que no existe | corregir `cluster` o `parent` |
| SCH007 | ERROR | ciclo en el árbol de clusters | romper el ciclo |

## Resolución de iconos

| Id | Sev. | Significa | Remedio |
|---|---|---|---|
| RES002 | INFO | el nombre existe en varios módulos; se eligió uno | fijar el icono con `icon:` si importa cuál |
| RES003 | WARNING | no hay clase oficial; se usa un icono genérico | `introspect_diagrams.py search`, o aceptar el genérico |
| RES004 | INFO | icono inferido a partir del label | declarar `icon:` para fijarlo |
| RES010 | INFO/WARNING | algo no se pudo dibujar y quedó en `unsupported` | informar al usuario |
| RES011 | INFO | atributo de Graphviz pasado por `gv.*` | solo informativo |

## Conectividad

| Id | Sev. | Significa | Remedio |
|---|---|---|---|
| CONN001 | ERROR | arista a un nodo inexistente | corregir el nombre |
| CONN002 | WARNING | arista duplicada | quitar una |
| CONN003 | WARNING | nodo sin aristas | conectarlo o marcarlo `standalone: true` |
| CONN004 | WARNING | self-loop | revisar el modelado |

## Clusters, tamaño y texto

| Id | Sev. | Significa | Remedio |
|---|---|---|---|
| CLU001 | WARNING | cluster vacío | quitarlo |
| CLU002 | WARNING | cluster con un solo nodo | quitarlo o marcarlo `boundary: true` si es un límite real |
| CLU003 | WARNING | profundidad mayor que 3 | aplanar |
| CLU004 | ERROR | labels de cluster repetidos (Graphviz fusiona los subgrafos) | labels únicos |
| CLU005 | WARNING | hermanos, o hijo y padre, con el mismo color | cambiar `zone` |
| CLU006 | ERROR | más de 5 clusters hermanos exceden la paleta | dividir el diagrama |
| SIZ001 / SIZ002 | WARNING | más de 20 nodos / más de 25 aristas | dividir por dominio o por flujo |
| TXT001 | WARNING | el label estimado no cabe en el nodo | bajar `LABEL_WRAP` o subir `NODE_WIDTH` |
| TXT002 | WARNING | tamaño de fuente ilegible al DPI de salida | subir `FONT_SIZE_*` |
| TXT003 | WARNING | etiqueta de arista vaga (`usa`, `conecta`) | usar un verbo o un protocolo |
| SIZ003 | INFO | más de 14 componentes en el flujo (sin notas ni íconos sin flechas, como la banda transversal; sí cuentan los `standalone`): cuesta leerlos en una vista de Miro o ejecutiva | agrupar o dividir el diagrama |

## Flujo y legibilidad

Cuentan solo las flechas que se dibujan entre componentes: no las invisibles (`gv.style: invis`) ni las anclas de las
notas. Nunca bloquean; ajusta el `.diag` si el pedido lo permite, o repórtalas.

| Id | Sev. | Significa | Remedio |
|---|---|---|---|
| FLW001 | WARNING | una flecha fuera del flujo principal lleva etiqueta. El máximo de etiquetas es la cantidad de pasos del flujo principal (flechas con `emphasis: true`) | quitar la etiqueta de lo secundario y explicarlo aparte, o marcar la flecha como `emphasis` si es del flujo principal |
| FLW002 | WARNING | etiqueta de flecha de más de 3 palabras (no cuentan marcadores como `①` ni conectores como `y`, `de`, `a`, `por`) | acortarla; el detalle va en la explicación |
| FLW003 | WARNING | un nodo con más de 7 conexiones (hub tipo telaraña) | acercar o agrupar sus vecinos, o dividir el diagrama |
| FLW004 | WARNING | más de 2 flechas de ida y vuelta (`<>`) | una sola dirección: la respuesta síncrona está implícita |
| FLW005 | WARNING | más de 2 notas ancladas a componentes | dejar las que aportan; el resto va en la explicación |
| FLW006 | WARNING | 2 o más elementos "a validar" (punteados) llegan por separado al mismo destino | agruparlos en un cluster punteado con una sola flecha |
| FLW007 | INFO | hay flechas con etiqueta pero ninguna marcada como flujo principal: `FLW001` no se pudo evaluar | marcar los pasos del flujo principal con `[emphasis: true]` |

## Estilo y código

| Id | Sev. | Significa | Remedio |
|---|---|---|---|
| STY020 | ERROR | fuente fuera de la lista permitida | `Helvetica`, `Arial` o `Times-Roman` |
| STY021 | ERROR | contraste menor que 4.5:1 (WCAG AA) | oscurecer `FONT_COLOR` o aclarar la zona |
| STY022 | ERROR | más de 5 colores de zona | reducir la paleta |
| STY023 | ERROR | color que no es `#RRGGBB` | corregir |
| STY000 | ERROR | faltan las marcas `# === STYLE ===` | regenerar el `.py` |
| STY001–STY004 | ERROR | color, atributo, clave o fuente fuera del bloque STYLE | regenerar; no edites el `.py` |
| STY005 | ERROR | `Cluster` sin `zone(...)` | regenerar |
| STY010 | ERROR | `splines=ortho` con `label=` | usar `xlabel` (lo hace el generador) o `splines: spline` |
| CODE001 | ERROR | el `.py` no compila | regenerar |
| CODE002 | ERROR | import inexistente | resolver con `introspect_diagrams.py` |
| CODE003 | ERROR | nodo fuera del `with Diagram` | regenerar |
| CODE004 | ERROR | incumple `OUT`, `FMT` o `show=False` | regenerar |
| CODE005 | ERROR | fuente hand-drawn prohibida | usar Helvetica-Bold |
| CODE006 | ERROR | no hay `with Diagram(...)` | regenerar |

En archivos escritos a mano (modo lenient) STY000–STY005 bajan a INFO y se agrupan en un finding por id.

## Fidelidad del código frente al IR (solo modo strict)

| Id | Significa |
|---|---|
| FID000 | no hay IR contra el que comparar (WARNING) |
| FID001 / FID002 | falta un nodo del IR / sobra un nodo en el código |
| FID003 | clase distinta |
| FID004 / FID005 | falta una arista / sobra una arista |
| FID006 | flecha distinta o invertida |
| FID007 | etiqueta de arista distinta |
| FID008 | cluster faltante, sobrante, con otro padre o con un nodo en otro cluster |
| FID009 | label de nodo distinto |
| FID010 | forma no canónica (el `.py` se editó a mano) |
| FID012 | tipo o énfasis de arista distinto |
| FID013 | zona de color distinta |
| FID014 | variable distinta |
| FID020 / FID021 | modo lenient: conteo heurístico (INFO) / faltan elementos frente al IR (WARNING) |

## Layout (mide la geometría real con `dot -Tjson`)

| Id | Sev. | Significa |
|---|---|---|
| LAY000 | INFO | falta Graphviz: layout sin verificar (no falla; nunca se instala solo) |
| LAY001 | WARNING | dos nodos, incluido su texto, se solapan |
| LAY002 | WARNING | la etiqueta de una arista cae sobre un nodo |
| LAY003 | WARNING | el label mide más que su nodo (medido, no estimado) |
| LAY004 | ERROR | la membresía de un cluster no coincide con el IR (bug de generación) |
| LAY005 | WARNING | un nodo sobresale del borde de su cluster |
| LAY006 | WARNING | cruces de aristas sobre el umbral; es una cota aproximada |
| LAY007 | WARNING | fuente ilegible al DPI de salida |
| LAY008 | WARNING | lienzo de más de 3000 pt por lado: al reducirlo no se lee |
| LAY010 | WARNING | `dot` avisa que `ortho` no maneja etiquetas de aristas |
| LAY099 | INFO/ERROR | otro aviso de `dot` / fallo al generar el layout |
| LAY100 | INFO | resumen: tamaño del lienzo, nodos, aristas y cruces |

## Determinismo

| Id | Sev. | Significa |
|---|---|---|
| DET000 | INFO | sin Graphviz: solo se verificó la generación |
| DET001 | ERROR | el `.py` en disco no es lo que genera el IR (se editó a mano) |
| DET002 | ERROR | dos renders del mismo `.py` dieron SVG distintos |
| DET003 | ERROR | no se pudo renderizar el SVG |
| DET004 | INFO | solo se editó el bloque STYLE: sirve para probar, se sobrescribe al regenerar |

El criterio es **misma máquina, mismas versiones**: otra versión de Graphviz o de la fuente cambia las
métricas de texto y el layout. Por eso las versiones van en `env` del reporte y no dentro del `.py`.
La comparación se hace en SVG; el PNG no es reproducible byte a byte por los metadatos de compresión.

## Arquitectura (nunca bloquean)

| Id | Sev. | Significa |
|---|---|---|
| ARQ001 | WARNING | a esos nodos no llega tráfico y no son el entrypoint |
| ARQ002 | WARNING | el entrypoint público conecta directo a una base de datos |
| ARQ003 | WARNING | base de datos sin `multi_az` en una arquitectura productiva |
| ARQ004 | INFO | arquitectura productiva sin logging ni monitoreo |
| ARQ010 | INFO | no se declaró `entrypoint`: no se aplicaron las reglas de red y seguridad |
