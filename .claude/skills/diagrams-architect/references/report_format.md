# Reporte final

`make diagram` deja `output/<slug>.report.json`. Es lo que demuestra que la arquitectura fue
validada y no solo escrita. Léelo y responde al usuario con las tres secciones de abajo.

## Campos del JSON

| Campo | Contenido |
|---|---|
| `overall` | `PASS`, `WARN` o `FAIL` |
| `counts` | `error`, `warning`, `info` |
| `env` | versiones de `python`, `diagrams` y `graphviz_dot`: cítalas en el reporte |
| `stages` | resultado por etapa (`validate_ir`, `validate_architecture`, `validate_code`, `validate_layout`, `check_determinism`) |
| `findings[]` | `id`, `severity`, `stage`, `message`, y si aplica `where`, `subject`, `hint` |
| `mapping` | `by_confidence` y `not_exact`: los nodos cuyo icono no es `exact` |
| `artifacts` | rutas del `.diag`, el `.ir.json`, el `.py` y el `.png` |

## Cómo presentarlo

```
Generado:  diagrams_src/<slug>.py  (desde <slug>.diag)
Render:    output/<slug>.png   | o: Graphviz no está instalado (brew install graphviz); el .py está validado
Entorno:   diagrams <versión> · Graphviz <versión> · Python <versión>
Resultado: PASS | WARN | FAIL   (errores N · avisos N · info N)

Solicitado     lo que se dibujó tal como se pidió
Inferido       cada nodo con mapping.not_exact (clase y motivo), y todo componente que agregaste sin que se pidiera
Recomendaciones  findings ARQ* y cualquier sugerencia de arquitectura; aparte y sin aplicar al diagrama
```

## Reglas de contenido

- Un ERROR bloquea: no lo reportes como éxito con una advertencia. Corrige el `.diag` y repite.
- Los WARNING se reportan siempre, con su id. No los resuelvas cambiando la topología pedida.
- Los mapeos que no son `exact` se listan uno por uno con su motivo, no solo se cuentan.
- Si falta Graphviz, no falla el resultado: indica "Render: no ejecutado" y la instrucción de instalación.
- Mira el PNG como control final: ¿se parece razonablemente a lo pedido?
