# Reglas de arquitectura y principios de fidelidad

`scripts/validate_architecture.py` corre cuatro reglas pequeñas y deterministas sobre el IR. No es un
validador de Well-Architected: atrapa lo obvio. **Ninguna bloquea**: los findings llegan al reporte
tal cual y el usuario decide.

| Id | Sev. | Regla |
|---|---|---|
| ARQ001 | WARNING | nodos a los que no llega tráfico y que no son el `entrypoint` |
| ARQ002 | WARNING | el `entrypoint` público conecta directo a una base de datos |
| ARQ003 | WARNING | base de datos sin `tag.multi_az` / `tag.multi_region` en una arquitectura `production: true` |
| ARQ004 | INFO | arquitectura productiva sin logging ni monitoreo |
| ARQ010 | INFO | sin `entrypoint` declarado no se pueden aplicar ARQ001 y ARQ002 |

Se activan declarando en el `.diag` `entrypoint: <Nodo>` y `production: true`. El tamaño del
diagrama lo cubren `SIZ001` y `SIZ002` en `validate_ir.py`.

## Principios de fidelidad (no negociables por defecto)

- **No inventes infraestructura.** El diagrama representa lo pedido, no una versión "mejorada".
- **No agregues componentes** que el usuario no pidió, salvo los estrictamente necesarios para
  representar algo que sí pidió (por ejemplo, el cluster VPC implícito de "una instancia privada").
  En ese caso, márcalo como inferido en el reporte.
- **No asumas servicios no mencionados**: no conviertas `S3 → Lambda → DynamoDB` en diez servicios
  con WAF, CloudWatch y KMS sin que se pidan.
- **Una recomendación no es un requisito.** Va aparte en el reporte y no se aplica al diagrama.
- **Un WARNING o INFO nunca dispara una corrección silenciosa** de la topología pedida.
- **Ante una ambigüedad real, pregunta solo si cambia la arquitectura.** Si es menor, elige una
  interpretación razonable y déjala anotada: nunca la resuelvas sin dejar rastro.
- **Separa siempre en el reporte final** lo solicitado, lo inferido y las recomendaciones.

## Fuera de alcance

No audita AWS Well-Architected completo, no divide un diagrama grande por su cuenta (solo advierte),
y no mezcla niveles de abstracción (contexto, lógico, despliegue) por iniciativa propia.
