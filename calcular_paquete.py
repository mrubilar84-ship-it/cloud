"""Uso: python calcular_paquete.py modelo.dxf secciones.json [combinaciones.json] [--salida carpeta] [--proyecto nombre]
Sin IA, sin clave de API. Genera memoria, resultados y paquete_revision.zip."""
import argparse

from estructural.revision import calcular_paquete

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("dxf"); p.add_argument("secciones"); p.add_argument("combinaciones", nargs="?")
p.add_argument("--salida", default="salida"); p.add_argument("--proyecto", default="Proyecto")
a = p.parse_args()
r = calcular_paquete(a.dxf, a.secciones, a.combinaciones, a.salida, a.proyecto)
print(f"Equilibrio global: {'OK' if r['equilibrio_ok'] else 'FALLA'}")
for adv in r["advertencias"]:
    print(" -", adv)
print("Paquete de revisión:", r["zip"])
