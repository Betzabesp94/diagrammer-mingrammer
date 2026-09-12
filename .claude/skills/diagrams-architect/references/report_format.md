# Formato del reporte final

El reporte es tan parte del output como el `.py` — es lo que convierte esto de
"Claude escribe Python" a "Claude genera y valida un artefacto arquitectónico
versionable". Usá esta estructura siempre, adaptando el contenido pero no las
secciones (omití una sección solo si genuinamente no aplica, ej. no hubo
recomendaciones):

```
Generated:
  diagrams_src/<slug>.py

Rendered:
  output/<slug>.png            (o: "no renderizado — Graphviz no está instalado, ver `make check`")

Validation
──────────
Syntax                    PASS
diagrams imports          PASS
Diagram context           PASS
Repo conventions          PASS
Topology fidelity         PASS   (expected: 6 nodes / 6 edges / 1 cluster — generated: igual)
Architecture consistency  WARNING (1)

Architecture warnings
──────────────────────
[W001] RDS está representado como Single-AZ; el pedido mencionó "producción".

Icon mapping
────────────
5 exact
1 inferred  (mapeo por rol descrito, no por nombre de servicio — confirmar)
1 generic   (no hay ícono oficial para el servicio descrito)
0 custom

Recommendations (not applied)
──────────────────────────────
- Considerar agregar WAF delante del ALB público.
- Considerar Multi-AZ para la instancia RDS de producción.
```

## Reglas de contenido

- **Errors bloquean, warnings no.** Si `validate_diagram.py` devuelve
  `overall: FAIL`, el resultado NO se presenta como exitoso — se corrige (o, si no
  se puede resolver sin inventar algo, se reporta el bloqueo explícitamente) antes
  de ofrecer el `.py` como terminado. Los warnings e infos de
  `validate_architecture.py` se reportan siempre, nunca bloquean.
- **Mapeos con confianza `inferred`/`generic`/`custom`/`ambiguous` siempre se
  listan**, no solo se cuentan — decí qué nodo y por qué.
- **Recomendaciones van aparte, nunca mezcladas con lo solicitado.** Si agregaste
  algo al `.py` que el usuario no pidió explícitamente (ej. un `Cluster` VPC
  implícito), decilo en el cuerpo de la respuesta, no lo escondas.
- Si no se pudo renderizar (Graphviz ausente), decilo en `Rendered:` con la
  instrucción de `make check` — nunca falles el resultado completo por eso ni
  intentes instalar Graphviz.
