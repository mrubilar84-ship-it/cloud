"""Uso: python calcular3d.py modelo.dxf secciones.json [memoria.md]
       python calcular3d.py modelo.json [memoria.md]   (modelo ya en JSON)"""
import json
import sys

from estructural.calculo.estructura3d import analizar
from estructural.informe.memoria_calculo_3d import generar
from estructural.modelos.dxf_lector import leer_dxf

if sys.argv[1].lower().endswith(".dxf"):
    sec = json.load(open(sys.argv[2]))
    modelo = leer_dxf(sys.argv[1], sec["secciones"], sec["materiales"])
    destino = sys.argv[3] if len(sys.argv) > 3 else "memoria_calculo_3d.md"
else:
    modelo = json.load(open(sys.argv[1]))
    destino = sys.argv[2] if len(sys.argv) > 2 else "memoria_calculo_3d.md"
open(destino, "w").write(generar(modelo, analizar(modelo), modelo.get("proyecto", "Proyecto")))
print(f"Memoria generada: {destino}")
