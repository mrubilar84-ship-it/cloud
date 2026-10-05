"""Uso: python agente.py modelo.dxf secciones.json
Requiere la variable de entorno ANTHROPIC_API_KEY. AGENTE_DIR define dónde se guardan memoria,
registro y salidas (por defecto ./agente_datos)."""
import os
import sys

import anthropic

from estructural.agente.agente import Agente, conversar

if len(sys.argv) < 3:
    sys.exit(__doc__)
agente = Agente(anthropic.Anthropic(), os.environ.get("AGENTE_DIR", "agente_datos"))
conversar(agente, f"Analiza esta estructura. DXF: {sys.argv[1]} ; secciones: {sys.argv[2]}. "
                  "Propón combinaciones de carga, calcula, revisa los resultados y prepara la memoria de cálculo.")
