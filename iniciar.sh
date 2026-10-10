#!/usr/bin/env bash
# Arranca todo con un comando: la API del motor (con el asistente) y el tablero.
#
#   ./iniciar.sh            # tablero en http://localhost:3000, API en :8000
#   ./iniciar.sh --build    # recompila el tablero aunque no haya cambios
#   PUERTO=3001 ./iniciar.sh
#
# Compila el tablero solo si no hay compilación o si cambió algo desde la última (Next solo
# sirve lo que había al compilar). Si la API ya está corriendo, la reutiliza. Ctrl+C apaga
# lo que este script arrancó.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOTOR="$RAIZ/motor-procesamiento"
TABLERO="$RAIZ/Road2Tech/Frontend"
PYTHON="$MOTOR/.venv/bin/python"
API="http://127.0.0.1:8000"
PUERTO="${PUERTO:-3000}"
FORZAR_BUILD=0
[[ "${1:-}" == "--build" ]] && FORZAR_BUILD=1

aviso() { printf '\033[1;36m▸ %s\033[0m\n' "$*"; }
error() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- requisitos
[[ -x "$PYTHON" ]] || error "No está $PYTHON. Instala el motor (ver 'Instalación' en motor-procesamiento/README.md)."
command -v npm >/dev/null || error "Falta Node.js/npm para el tablero."
if ! grep -qsE '^(export )?(APIGEMINI|GEMINI_API_KEY)=.+' "$RAIZ/.env"; then
  aviso "Sin clave de Gemini en $RAIZ/.env: el tablero funciona, pero el asistente no (pon APIGEMINI=tu-clave)."
fi
if ss -ltn 2>/dev/null | grep -qE "[:.]$PUERTO\b"; then
  error "El puerto $PUERTO ya está ocupado. Usa otro: PUERTO=3001 ./iniciar.sh"
fi

# ---------------------------------------------------------------- API del motor
PID_API=""
apagar() {
  if [[ -n "$PID_API" ]] && kill -0 "$PID_API" 2>/dev/null; then
    aviso "Apagando la API del motor"
    kill "$PID_API" 2>/dev/null || true
  fi
}
trap apagar EXIT
trap 'exit 130' INT TERM

if curl -sf -m 2 "$API/salud" >/dev/null; then
  curl -sf -m 2 "$API/chat" >/dev/null ||
    error "En :8000 corre una API de antes del asistente. Apágala y vuelve a correr este script."
  aviso "La API del motor ya estaba corriendo en :8000; uso esa"
else
  aviso "Arrancando la API del motor en :8000"
  cd "$MOTOR"
  "$PYTHON" -m cruce.api > >(sed -u 's/^/[motor] /') 2>&1 &
  PID_API=$!
  for _ in $(seq 1 40); do
    curl -sf -m 1 "$API/salud" >/dev/null && break
    kill -0 "$PID_API" 2>/dev/null || error "La API no arrancó (¿el puerto 8000 está ocupado?)"
    sleep 0.25
  done
  curl -sf -m 1 "$API/salud" >/dev/null || error "La API no respondió en 10 s"
fi

# ---------------------------------------------------------------- tablero
cd "$TABLERO"
if [[ ! -d node_modules ]]; then
  aviso "Instalando dependencias del tablero (solo la primera vez)"
  npm ci
fi
if [[ "$FORZAR_BUILD" == 1 || ! -f .next/BUILD_ID ]] ||
   [[ -n "$(find app components lib types public next.config.ts package.json tailwind.config.ts \
            -newer .next/BUILD_ID -print -quit 2>/dev/null)" ]]; then
  aviso "Compilando el tablero (hay cambios desde la última compilación)"
  npm run build
fi

aviso "Tablero en http://localhost:$PUERTO   (Ctrl+C para apagar)"
npm start -- -p "$PUERTO"
