# DSL de entrada (`.diag`)

Subconjunto de la sintaxis de eraser.io, compilado por `scripts/parse_dsl.py`. Un archivo UTF-8,
una sentencia por línea. Los comentarios son `// ...` o una línea que empieza con `#`.
Cualquier error se reporta como `PAR001` con `línea:columna`; nada se descarta en silencio.

## Directivas (opcionales, al inicio y fuera de los grupos)

| Directiva | Valores | Efecto |
|---|---|---|
| `title: Texto` | texto | título del diagrama |
| `direction:` | `LR` `RL` `TB` `BT` | sentido de lectura (por defecto `LR`) |
| `provider:` | `aws` `gcp` `azure` `k8s` `onprem`… | proveedor por defecto para iconos sin prefijo (`aws`) |
| `slug:` | identificador | nombre de archivo y de salida (por defecto, el nombre del `.diag`) |
| `splines:` | `spline` `ortho` `polyline` `curved` `line` | trazado de aristas (ver `style_system.md`) |
| `legend:` | `on` `off` | leyenda automática (por defecto `on`) |
| `entrypoint: Nodo` | nombre de un nodo | nodo expuesto a internet; activa las reglas ARQ001 y ARQ002 |
| `production: true` | `true` `false` | activa las reglas ARQ003 y ARQ004 |
| `project: Nombre` | texto | proyecto o cliente del diagrama; va a `meta.project` del IR y decide el board de Miro (ver `miro.md`) |
| `style.VARIABLE: valor` | ver `style_system.md` | sobrescribe una variable del bloque STYLE (ej. `style.FONT_SIZE_NODE: 13`) |

## Nodos

```
Nombre [icon: aws-ec2, label: "Servidor web", tag.multi_az: true, gv.penwidth: 2]
```

| Atributo | Significado |
|---|---|
| `icon: <proveedor>-<servicio>` | icono oficial. `aws-ec2`, `aws-api-gateway`, `onprem-postgresql`… Se resuelve contra la instalación real |
| `label: "Texto"` | texto visible; por defecto, el nombre |
| `service: "Texto"` | nombre del servicio, solo informativo |
| `standalone: true` | el nodo no necesita aristas (no se reporta como huérfano) |
| `tag.<clave>: valor` | metadato libre que leen las reglas (ej. `tag.multi_az: true`) |
| `gv.<atributo>: valor` | atributo de Graphviz que pasa directo (se reporta como INFO) |

Un nodo sin `icon` intenta resolver su nombre (`API Gateway` → `aws.network.APIGateway`, confianza
`inferred`); si no hay clase oficial usa un icono genérico y se reporta `RES003`.
Los nombres distinguen mayúsculas. Un nodo que solo aparece en una conexión se crea solo.

## Grupos

```
VPC [boundary: true] {
  Subred pública [boundary: true] {
    ALB [icon: aws-alb]
  }
}
```

Se anidan. `boundary: true` marca un límite real (VPC, subred, namespace) y evita el aviso de
cluster con un solo nodo. Los labels de grupo deben ser únicos en todo el diagrama, porque
Graphviz fusiona los repetidos (`CLU004`). Un nodo pertenece al grupo donde se declara.

## Conexiones (una por línea)

| Sintaxis | Significado |
|---|---|
| `A > B` | A llama a B |
| `A < B` | B llama a A (se guarda como `B > A`) |
| `A <> B` | ambos sentidos |
| `A - B` | sin flecha |
| `A > B, C` | una arista de A a cada destino (también `A, B > C`) |
| `A > B: "HTTPS"` | con etiqueta |
| `A > B: "evento" [type: event, emphasis: true]` | con tipo y énfasis |

- `type`: `network` (por defecto), `event` (discontinua), `data`, `invocation`, `dependency`
  (punteada), `authentication` (color de acento). Los trazos con significado generan leyenda.
- `emphasis: true` marca un paso del **flujo principal**: lo resalta con el color de acento y más grosor, y define
  qué flechas pueden llevar etiqueta. Solo los pasos del flujo principal llevan texto; las relaciones secundarias van
  sin etiqueta y se explican aparte (`FLW001`). Si nada lleva `emphasis`, se reporta `FLW007`.
- La etiqueta dice un verbo o un protocolo: `"HTTPS"`, `"publica evento"`, `"lee"`.
  Nunca `"usa"` ni `"conecta"` (`TXT003`).
- No hay cadenas: `A > B > C` es un error. Escribe una arista por línea.
- El guion solo es operador entre espacios: `Back-end` es un nombre.

## Cómo elegir el icono

```bash
.venv/bin/python .claude/skills/diagrams-architect/scripts/introspect_diagrams.py resolve api-gateway --provider aws
.venv/bin/python .claude/skills/diagrams-architect/scripts/introspect_diagrams.py search bedrock
```

`resolve` devuelve `exact`, `ambiguous` (varias clases; elige la del módulo preferido y lista las
alternativas) o `none`. Nunca escribas un import a mano: si `none`, usa el icono genérico.

## Errores frecuentes

| Mensaje | Causa |
|---|---|
| `una línea admite una sola conexión` | cadena `A > B > C` |
| `atributo 'x' no válido para nodo` | clave desconocida; los permitidos se listan en el hint |
| `grupo sin cerrar` / `'}' sin grupo abierto` | llaves desbalanceadas |
| `el grupo 'X' ya existe` | label de grupo repetido |
| `el nodo 'X' ya fue declarado` | dos declaraciones del mismo nodo |
| `entrypoint 'X' no es un nodo` | el nombre no coincide con ningún nodo |

## Cuando algo no cabe en el DSL

En este orden: `tag.*` para metadatos → `gv.*` para un atributo de Graphviz (INFO) → si no se puede
dibujar, queda en `unsupported` del IR y se reporta (`RES010`). Nunca se descarta en silencio.
Si el mismo caso se repite, se extiende el esquema subiendo `schema_version`.
