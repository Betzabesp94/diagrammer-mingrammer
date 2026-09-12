# Modelo intermedio de arquitectura (IR)

Representación estructurada que la skill arma internamente entre "lo que pidió el
usuario" y "el código Python". No hace falta guardarlo como archivo salvo que se use
`--ir` con `scripts/validate_diagram.py` o `scripts/validate_architecture.py` — en
ese caso escribilo a un archivo temporal en el workspace (no en `diagrams_src/`).

## Por qué existe

Pasar directo de una frase a `CloudFront() >> ALB() >> ECS()` hace que sea fácil
"perder" una conexión en arquitecturas largas, o mapear un servicio al ícono
equivocado sin darse cuenta. El IR separa dos preguntas que conviene no mezclar:
**¿qué arquitectura es?** (este archivo) y **¿cómo se dibuja?** (el `.py`).

## Forma

```json
{
  "provider": "aws",
  "nodes": [
    {
      "id": "cloudfront",
      "service": "Amazon CloudFront",
      "diagrams_class": "diagrams.aws.network.CloudFront",
      "confidence": "exact",
      "tags": {}
    },
    {
      "id": "alb",
      "service": "Application Load Balancer",
      "diagrams_class": "diagrams.aws.network.ELB",
      "confidence": "exact",
      "tags": {}
    },
    {
      "id": "db",
      "service": "Amazon RDS Postgres",
      "diagrams_class": "diagrams.aws.database.RDS",
      "confidence": "exact",
      "tags": {"multi_az": true}
    }
  ],
  "clusters": [
    {"id": "vpc", "contains": ["alb", "db"]}
  ],
  "edges": [
    {"source": "cloudfront", "target": "alb", "protocol": "HTTPS", "type": "network"},
    {"source": "alb", "target": "db", "protocol": "TCP/5432", "type": "network"}
  ],
  "constraints": {
    "internet_entrypoint": "cloudfront",
    "production": true,
    "notes": "arquitectura productiva, mencionó alta disponibilidad"
  }
}
```

### Campos de `nodes[]`

| Campo | Uso |
|---|---|
| `id` | identificador interno estable (se usa en `edges`/`clusters`), no el nombre visible |
| `service` | como lo nombró o describió el usuario ("Application Load Balancer", "un balanceador") |
| `diagrams_class` | path completo verificado con `scripts/introspect_diagrams.py check` — nunca un path adivinado |
| `confidence` | `exact` / `inferred` / `generic` / `custom` / `ambiguous` (ver tabla abajo) |
| `tags` | metadata libre usada por `validate_architecture.py` (`multi_az`, `multi_region`, u otras que agregues) |

### Niveles de confianza

| Nivel | Significa | Qué hace la skill |
|---|---|---|
| `exact` | Hay una clase 1:1 verificada para el servicio nombrado | Usarla directo, sin nota especial en el reporte |
| `inferred` | El usuario describió un rol ("servicio interno de procesamiento"), no un servicio puntual | Usar una clase razonable y **reportarla** para que el usuario la confirme |
| `generic` | No hay ícono oficial de ningún proveedor para eso | Usar `diagrams.generic.*` y reportarlo |
| `custom` | Tampoco hay ícono genérico aplicable | Usar `diagrams.custom.Custom` y reportar qué ícono/ruta se usó |
| `ambiguous` | Dos o más clases son igual de plausibles | Preguntar solo si la ambigüedad cambia la arquitectura de forma significativa; si no, elegir y reportar |

**Regla dura:** un nodo nunca pasa a `diagrams_class` sin que `introspect_diagrams.py
check` (o `search`) haya confirmado que existe. Si no existe, se degrada de
`exact`/`inferred` a `generic` o `custom` — nunca se inventa un path porque "suena
correcto" (ver el caso real `aws.bedrock.Bedrock`, que no existe: la clase real es
`diagrams.aws.ml.Bedrock`).

### Campos de `edges[]`

`type` distingue una llamada de red directa (`network`) de una notificación
asíncrona (`event`, típico de `S3 → Lambda` o `SQS/SNS/EventBridge → Lambda`), un
flujo de datos (`data`), una invocación (`invocation`), una dependencia en tiempo
de build/deploy (`dependency`) o un chequeo de identidad (`authentication`). Esto
le permite a la skill decidir el estilo de la `Edge` en el `.py` (sólida para
`network`, `style="dashed"` con label para `event`, etc.) en vez de dibujar todo
igual.

### `constraints`

Objeto libre. Los campos que hoy usa `scripts/validate_architecture.py`:

- `internet_entrypoint`: id del nodo que recibe tráfico público (si existe).
- `production` (bool) — o, si no está explícito, el script también busca palabras
  como "producción"/"production"/"alta disponibilidad" en cualquier valor string
  del objeto (ej. en `notes`).

Se puede extender con más campos libres; el script solo lee lo que conoce y
ninguna clave rara rompe nada.

## Multi-cloud

Un solo IR puede tener nodos con distinto `diagrams_class` de distintos
proveedores (`diagrams.aws.*`, `diagrams.gcp.*`, ...). Usá un `Cluster` por
proveedor o por boundary lógico si ayuda a la lectura, pero no es obligatorio —
depende de si el usuario pidió agrupar por proveedor o por función.
