"""Validaciones previas, resumen de resultados y paquete de revisión (ZIP) para entregar a un revisor."""
import json
import zipfile
from datetime import datetime
from pathlib import Path

from estructural.calculo.estructura3d import analizar
from estructural.informe.memoria_calculo_3d import TOL_EQ, generar
from estructural.modelos.dxf_lector import leer_dxf


def validar_modelo(modelo: dict) -> list[str]:
    """Advertencias sobre datos sospechosos (típicamente errores de unidades)."""
    av = []
    for n, s in modelo["secciones"].items():
        if s["A"] > 1 or s["Iy"] > 1 or s["Iz"] > 1:
            av.append(f"Sección {n}: A o I demasiado grande; ¿olvidaste convertir cm²/cm⁴ a m²/m⁴?")
        if s["A"] < 1e-5 or s["Iy"] < 1e-10 or s["Iz"] < 1e-10:
            av.append(f"Sección {n}: A o I demasiado pequeña; ¿convertiste dos veces o usaste mm?")
        if s["Iz"] > s["Iy"]:
            av.append(f"Sección {n}: Iz > Iy. Iy debe ser el eje FUERTE (el de flexión vertical de una viga).")
    for n, m in modelo["materiales"].items():
        if not 1e6 < m["E"] < 1e9:
            av.append(f"Material {n}: E={m['E']:.2e} kPa fuera de rango usual (acero≈2e8, hormigón≈2.5e7).")
    for e in modelo["elementos"]:
        if e["seccion"] not in modelo["secciones"]:
            av.append(f"Barra {e['id']}: sección '{e['seccion']}' no existe")
    if not modelo.get("combinaciones"):
        av.append("No se definieron combinaciones: se calculó cada caso por separado con factor 1.0. "
                  "Define combinaciones según tu norma.")
    av.append("Orientación de perfiles por defecto (eje fuerte vertical en vigas; en columnas, en dirección X). "
              "El DXF aún no permite cambiarla: revisa que corresponda a tu diseño.")
    return av


def resumen(modelo: dict, resultados: dict) -> dict:
    out = {}
    for nombre, r in resultados.items():
        desp = {n: max(abs(v) for v in d[:3]) for n, d in r["desplazamientos"].items()}
        nmax = max(desp, key=desp.get)
        out[nombre] = {
            "equilibrio_ok": all(abs(e) < TOL_EQ for e in r["equilibrio"]["error"]),
            "equilibrio": r["equilibrio"],
            "desplazamiento_max_mm": {"nodo": nmax, "valor": round(1000 * desp[nmax], 3)},
            "reacciones": {n: [round(v, 3) for v in d] for n, d in r["reacciones"].items()},
            "esfuerzos_max_por_barra": {
                str(eid): {k: round(max(abs(v) for v in d[k]), 3) for k in ("N", "Vy", "Vz", "T", "My", "Mz")}
                for eid, d in r["diagramas"].items()
            },
        }
    return out


def calcular_paquete(dxf: str, secciones: str, combinaciones: str | None, salida: str,
                     proyecto: str = "Proyecto") -> dict:
    """Ejecuta todo el flujo y deja memoria, resultados y un ZIP de revisión en `salida`."""
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    sec = json.load(open(secciones))
    modelo = leer_dxf(dxf, sec["secciones"], sec["materiales"])
    if combinaciones:
        combos = json.load(open(combinaciones))["combinaciones"]
        for nombre, f in combos.items():
            faltan = [c for c in f if c not in modelo["casos"]]
            if faltan:
                raise ValueError(f"Combinación '{nombre}': casos inexistentes {faltan} "
                                 f"(casos del DXF: {list(modelo['casos'])})")
        modelo["combinaciones"] = combos
    advertencias = validar_modelo(modelo)
    resultados = analizar(modelo)
    res = resumen(modelo, resultados)
    ok = all(v["equilibrio_ok"] for v in res.values())
    if not ok:
        advertencias.insert(0, "❌ El equilibrio global NO cumple: NO usar estos resultados.")

    memoria = generar(modelo, resultados, proyecto)
    datos = {
        "proyecto": proyecto, "fecha": datetime.now().isoformat(timespec="seconds"),
        "equilibrio_global_ok": ok, "advertencias": advertencias,
        "modelo": {"nodos": len(modelo["nodos"]), "barras": len(modelo["elementos"]),
                   "apoyos": modelo["apoyos"], "casos": list(modelo["casos"]),
                   "combinaciones": modelo.get("combinaciones", {}),
                   "barras_con_rotula": [e["id"] for e in modelo["elementos"]
                                         if "liberar_i" in e or "liberar_j" in e]},
        "resultados": res,
    }
    (salida / "memoria_calculo.md").write_text(memoria, encoding="utf-8")
    (salida / "resultados.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    (salida / "modelo_resuelto.json").write_text(json.dumps(modelo, ensure_ascii=False, indent=1), encoding="utf-8")
    leeme = ["# Paquete de revisión", f"Proyecto: {proyecto}", f"Equilibrio global: {'OK' if ok else 'FALLA'}", "",
             "## Advertencias"] + [f"- {a}" for a in advertencias] + [
             "", "## Contenido", "- memoria_calculo.md: memoria completa",
             "- resultados.json: resumen numérico (para revisión rápida)",
             "- modelo_resuelto.json: modelo tal como se calculó",
             "- entradas/: DXF y JSON originales"]
    (salida / "LEEME_revision.md").write_text("\n".join(leeme), encoding="utf-8")
    zip_path = salida / "paquete_revision.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ("LEEME_revision.md", "memoria_calculo.md", "resultados.json", "modelo_resuelto.json"):
            z.write(salida / f, f)
        for entrada in (dxf, secciones, combinaciones):
            if entrada:
                z.write(entrada, f"entradas/{Path(entrada).name}")
    return {"zip": str(zip_path), "equilibrio_ok": ok, "advertencias": advertencias}
