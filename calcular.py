"""Uso: python calcular.py modelo.json [salida.md]"""
import json
import sys

from estructural.calculo.portico import analizar
from estructural.informe.memoria_calculo import generar

modelo = json.load(open(sys.argv[1]))
memoria = generar(modelo, analizar(modelo), modelo.get("proyecto", "Proyecto"))
destino = sys.argv[2] if len(sys.argv) > 2 else "memoria_calculo.md"
open(destino, "w").write(memoria)
print(f"Memoria generada: {destino}")
