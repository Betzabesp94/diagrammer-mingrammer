# IR canónico v2

Es la única fuente de verdad: el `.py` se genera a partir de él y no se escribe a mano. Lo produce
`resolve_ir.py` a partir del `.diag`; el modelo casi nunca lo escribe. El contrato formal es
`ir.schema.json` (lo interpreta `validate_ir.py`). Las reglas entre campos están abajo.

```json
{
  "schema_version": 2, "title": "Web app", "slug": "web_app", "provider": "aws", "direction": "LR",
  "nodes":    [{"id": "api", "var": "api", "label": "API", "label_wrapped": "API",
                "icon": "aws-api-gateway", "diagrams_class": "diagrams.aws.network.APIGateway",
                "confidence": "exact", "cluster": "vpc", "standalone": false, "role": "service",
                "tags": {}, "extensions": {}}],
  "clusters": [{"id": "vpc", "label": "VPC", "parent": null, "zone": 0, "boundary": true, "extensions": {}}],
  "edges":    [{"id": "e1", "source": "web", "target": "api", "arrow": "forward", "label": "HTTPS",
                "type": "network", "emphasis": false, "role": "flow", "extensions": {}}],
  "constraints": {"internet_entrypoint": "web", "production": true},
  "style_overrides": {}, "legend": {"auto": true, "entries": []}, "unsupported": [], "meta": {}
}
```

## Campos que calcula `resolve_ir.py` (el generador no decide nada)

| Campo | Qué es |
|---|---|
| `nodes[].var` | nombre de variable Python, único, sin pisar palabras reservadas ni builtins (`list` → `list_`) |
| `nodes[].label_wrapped` | label con saltos de línea según `LABEL_WRAP` |
| `nodes[].diagrams_class` | clase real; `diagrams.generic.blank.Blank` si no hay clase oficial |
| `nodes[].confidence` | ver tabla de abajo |
| `clusters[].zone` | índice de color: distinto de sus hermanos y de su padre |
| `edges[].type` | `network` si no se indicó |
| `legend` | entradas de la leyenda automática; sus nodos, cluster y aristas llevan `role: "legend"` |

## `confidence`

| Valor | Cuándo | Acción |
|---|---|---|
| `exact` | `icon:` resuelto a una sola clase | nada |
| `inferred` | clase deducida del nombre, o varias candidatas | se lista en el reporte (`RES002`, `RES004`) |
| `generic` | sin clase oficial | icono genérico y `RES003` (WARNING) |
| `custom`, `ambiguous` | reservados | sin uso hoy |

## Invariantes (las comprueba `validate_ir.py`)

- Ids `^[a-z][a-z0-9_]*$`, únicos entre nodos y clusters; los clusters no pueden empezar con `cluster_`.
- Un nodo pertenece a un solo cluster (`nodes[].cluster`); el anidamiento sale de `clusters[].parent`, sin ciclos.
- Cada arista une nodos existentes. `A < B` se normaliza a `B > A`; `arrow` ∈ `forward|both|none`.
- Los labels de cluster son únicos en todo el diagrama.
- Mismo `.diag` y mismas versiones → mismo IR, byte a byte (`irlib.dump_json`).

## Expresividad, en este orden

`tags` (metadato) → `extensions` (atributo de Graphviz, INFO `RES011`) → `unsupported`
(`{where, feature, detail, severity}`, `RES010`; nunca se descarta en silencio) → extender el esquema
subiendo `schema_version`, solo si el caso se repite.
