# Validación arquitectónica y principios de fidelidad

## Los tres niveles de validación

Un script puede ser Python válido, importar clases reales y renderizar sin error
en Graphviz, y aun así representar una arquitectura equivocada. Por eso una
generación exitosa siempre pasa por tres validaciones distintas, en este orden:

1. **Técnica** — ¿el código funciona? → `scripts/validate_diagram.py` (sección
   syntax/imports/diagram_context/conventions de su salida).
2. **Fidelidad** — ¿representa lo que pidió el usuario? → misma herramienta, con
   `--ir` (sección `fidelity`, cuenta nodos/edges/clusters esperados vs generados).
3. **Arquitectónica** — ¿hay inconsistencias o riesgos evidentes? →
   `scripts/validate_architecture.py` sobre el IR.

Las tres son necesarias; ninguna reemplaza a las otras. Un diagrama que compila e
importa bien pero le faltó una arista (`missing_edges > 0`) NO es un resultado
exitoso, aunque Graphviz lo renderice sin quejarse.

## Reglas arquitectónicas (deterministas, `scripts/validate_architecture.py`)

Cinco chequeos ilustrativos, no un motor de Well-Architected completo:

| Categoría | Qué mira | Severidad |
|---|---|---|
| Networking | nodos que actúan como origen de una conexión pero no reciben ninguna entrante y no son el `internet_entrypoint` declarado — posible entry point no modelado | WARNING |
| Seguridad | el `internet_entrypoint` conectado directo (1 salto) a un nodo con pinta de base de datos | WARNING |
| Disponibilidad | `constraints` marca producción/HA y hay un nodo de base de datos sin `tags.multi_az` / `tags.multi_region` | WARNING |
| Observabilidad | `constraints` marca producción y ningún nodo parece de logging/monitoreo | INFO |
| Complejidad | más de ~25 nodos (ajustable con `--max-nodes`) | INFO |

Los `findings` que devuelve el script traen `severity`, `category` y `message` —
volcalos al reporte final tal cual, no los resumas de forma que pierda la
severidad.

### Niveles de severidad (aplican a cualquier hallazgo, no solo a estos cinco)

- **ERROR** — bloquea el resultado: import inventado, sintaxis inválida, una arista
  pedida explícitamente que no aparece en el `.py`. Esto lo produce
  `validate_diagram.py`, no `validate_architecture.py` (que nunca emite ERROR).
- **WARNING** — problema potencial que un humano debería revisar, pero no bloquea
  la generación.
- **INFO** — observación o recomendación.

## Principios de fidelidad (no negociables por defecto)

Estos rigen el comportamiento de la skill en cualquier paso, no solo en la
validación:

- **No inventar infraestructura.** El diagrama representa lo pedido, no una
  versión "mejorada" imaginada por el modelo.
- **No introducir componentes** salvo que el usuario los haya pedido, o sean
  estrictamente necesarios para representar algo que sí pidió (ej. un `Cluster`
  VPC implícito al describir "una instancia EC2 privada").
- **No asumir servicios no mencionados** "porque así sería correcto" — no
  convertir `S3 → Lambda → DynamoDB` en diez servicios con WAF, API Gateway,
  CloudWatch, KMS, etc. sin que se haya pedido.
- **Una recomendación nunca es un requisito.** El reporte separa siempre
  "arquitectura solicitada" (PASS/FAIL) de "recomendaciones" (lista aparte, nunca
  aplicada automáticamente al `.py`).
- **Un WARNING o INFO nunca dispara una corrección silenciosa** de la topología
  solicitada. Se reporta; no se reescribe por cuenta propia.
- **Ante ambigüedad real, preguntar solo si afecta significativamente la
  arquitectura** (ej. "un balanceador" sin decir de qué proveedor, cuando el resto
  del diagrama tampoco lo aclara). Si la ambigüedad es menor, elegí una
  interpretación razonable y dejala anotada en el reporte — nunca la resuelvas en
  silencio sin dejar rastro.
- **Separar siempre, en el reporte final:** componentes solicitados, componentes
  inferidos/de baja confianza, y recomendaciones no incluidas en el diagrama.

## Fuera de alcance

- No es un validador de AWS Well-Architected completo.
- No hace análisis de imagen por visión artificial (cruces de líneas, densidad
  geométrica); si Claude puede ver el PNG renderizado, una revisión visual directa
  ("¿esto se parece a lo que pidieron?") alcanza y es más confiable.
- No divide automáticamente un diagrama grande — solo advierte.
- No mezcla niveles de abstracción (contexto/lógico/despliegue/infraestructura)
  por iniciativa propia.
