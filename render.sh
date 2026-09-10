#!/usr/bin/env bash
#
# Renderiza un diagrama de diagrams_src/ dentro de output/.
#
#   ./render.sh ejemplo_aws.py           -> output/ejemplo_aws.png
#   FORMAT=svg ./render.sh ejemplo_aws   -> output/ejemplo_aws.svg
#   ./render.sh --check                  -> verifica los prerequisitos y sale
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$ROOT/diagrams_src"
OUT_DIR="$ROOT/output"
FORMAT="${FORMAT:-png}"

rojo()  { printf '\033[31m%s\033[0m\n' "$*" >&2; }
verde() { printf '\033[32m%s\033[0m\n' "$*"; }

die() { rojo "error: $*"; exit 1; }

hint_graphviz() {
  cat >&2 <<'EOF'

Graphviz es una dependencia del SISTEMA (no un paquete Python). Instalalo con:

  macOS          brew install graphviz
  Ubuntu/Debian  sudo apt install graphviz
  Fedora         sudo dnf install graphviz
  Windows        choco install graphviz   (o: winget install Graphviz.Graphviz)

Verificá con: dot -V
EOF
}

# --- Intérprete de Python: el venv del proyecto si existe, si no python3 ------
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="$(command -v python3 || true)"
fi
[[ -n "$PYTHON" ]] || die "no encontré python3 en el PATH."

check_prereqs() {
  command -v dot >/dev/null 2>&1 || { rojo "error: no encontré el binario 'dot' (Graphviz)."; hint_graphviz; exit 1; }
  "$PYTHON" -c "import diagrams" 2>/dev/null || die "la librería 'diagrams' no está instalada. Corré: make install"
}

if [[ "${1:-}" == "--check" ]]; then
  check_prereqs
  verde "OK  python    $("$PYTHON" --version) -> $PYTHON"
  verde "OK  graphviz  $(dot -V 2>&1)"
  verde "OK  diagrams  $("$PYTHON" -c 'from importlib.metadata import version; print(version("diagrams"))' 2>/dev/null || echo instalada)"
  exit 0
fi

if [[ $# -lt 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat >&2 <<EOF
uso: ./render.sh <script.py>        (o solo el nombre, o la ruta completa)
     FORMAT=svg ./render.sh <script.py>
     ./render.sh --check

scripts disponibles en diagrams_src/:
$(ls "$SRC_DIR"/*.py 2>/dev/null | xargs -n1 basename | sed 's/^/  /' || echo "  (ninguno)")
EOF
  exit 1
fi

# --- Resolver el script: acepta "ejemplo_aws", "ejemplo_aws.py" o la ruta -----
arg="$1"
[[ "$arg" == *.py ]] || arg="$arg.py"

if   [[ -f "$arg" ]];             then SCRIPT="$arg"
elif [[ -f "$SRC_DIR/$arg" ]];    then SCRIPT="$SRC_DIR/$arg"
elif [[ -f "$SRC_DIR/$(basename "$arg")" ]]; then SCRIPT="$SRC_DIR/$(basename "$arg")"
else die "no encontré '$1' (ni en el directorio actual ni en diagrams_src/)."
fi

check_prereqs
mkdir -p "$OUT_DIR"

echo "renderizando $(basename "$SCRIPT") -> $FORMAT ..."
FORMAT="$FORMAT" "$PYTHON" "$SCRIPT"

generado="$OUT_DIR/$(basename "${SCRIPT%.py}").$FORMAT"
if [[ -f "$generado" ]]; then
  verde "listo: ${generado#"$ROOT"/}"
else
  # El script puede usar otro nombre de salida que el del archivo .py.
  verde "listo (revisá output/)"
fi
