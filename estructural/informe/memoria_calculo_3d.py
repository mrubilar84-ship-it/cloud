"""Memoria de cálculo (Markdown) para modelos 3D."""
from datetime import date

from estructural.informe.memoria_calculo import _tabla

TOL_EQ = 1e-4


def generar(modelo: dict, resultados: dict, proyecto: str = "Proyecto sin nombre") -> str:
    L = [f"# Memoria de cálculo 3D — {proyecto}", f"Fecha: {date.today().isoformat()}", "",
         "> **Aviso:** documento generado automáticamente. Requiere revisión y firma de un "
         "ingeniero responsable antes de cualquier uso en obra.", "",
         "## 1. Método y supuestos",
         "- Análisis elástico lineal de primer orden, barras 3D (OpenSeesPy, `elasticBeamColumn`).",
         "- Unidades: kN, m, kPa. Eje global Z hacia arriba. Combinaciones por superposición lineal.",
         "- Ejes locales: x de i a j; y = vecxz × x; z = x × y. Rótulas modeladas como liberación "
         "de rotación en el extremo de la barra.",
         "- **No incluye** verificación de resistencia según norma, pandeo, P-Δ ni sismo.", "",
         "## 2. Secciones",
         _tabla(["Sección", "Material", "A [m²]", "Iy [m⁴]", "Iz [m⁴]", "J [m⁴]"],
                [[n, s["material"], f"{s['A']:.4e}", f"{s['Iy']:.4e}", f"{s['Iz']:.4e}", f"{s['J']:.4e}"]
                 for n, s in modelo["secciones"].items()]), "",
         "## 3. Geometría",
         _tabla(["Nodo", "x", "y", "z", "Apoyo (ux,uy,uz,rx,ry,rz)"],
                [[n, *c, modelo["apoyos"].get(n, "libre")] for n, c in modelo["nodos"].items()]), "",
         _tabla(["Barra", "i", "j", "Sección", "Rótula i", "Rótula j"],
                [[e["id"], e["i"], e["j"], e["seccion"], ",".join(e.get("liberar_i", [])) or "-",
                  ",".join(e.get("liberar_j", [])) or "-"] for e in modelo["elementos"]]), "",
         "## 4. Casos de carga"]
    for nombre, c in modelo["casos"].items():
        L.append(f"**{nombre}**")
        L += [f"- Nodo {n}: [Fx,Fy,Fz,Mx,My,Mz] = {f}" for n, f in c.get("nodales", {}).items()]
        L += [f"- Barra {e}: [wx,wy,wz] = {w} kN/m (ejes locales)" for e, w in c.get("distribuidas", {}).items()]
        L.append("")
    L.append("## 5. Resultados")
    for i, (nombre, r) in enumerate(resultados.items(), 1):
        L += [f"### 5.{i} Combinación {nombre}", "", "**Desplazamientos [mm, mrad]**",
              _tabla(["Nodo", "ux", "uy", "uz", "rx", "ry", "rz"],
                     [[n, *(f"{1000 * v:.3f}" for v in d)] for n, d in r["desplazamientos"].items()]), "",
              "**Reacciones [kN, kN·m]**",
              _tabla(["Nodo", "Rx", "Ry", "Rz", "Mx", "My", "Mz"],
                     [[n, *(f"{v:.3f}" for v in d)] for n, d in r["reacciones"].items()]), "",
              "**Esfuerzos máximos por barra (ejes locales)**",
              _tabla(["Barra", "|N| máx", "|Vy| máx", "|Vz| máx", "|T| máx", "|My| máx", "|Mz| máx"],
                     [[eid, *(f"{max(abs(v) for v in d[k]):.3f}" for k in ("N", "Vy", "Vz", "T", "My", "Mz"))]
                      for eid, d in r["diagramas"].items()]), ""]
        q = r["equilibrio"]
        ok = all(abs(e) < TOL_EQ for e in q["error"])
        L += ["**Equilibrio global (Σ cargas + Σ reacciones = 0)**",
              f"- Σ cargas = {[round(v, 3) for v in q['cargas']]} kN; "
              f"Σ reacciones = {[round(v, 3) for v in q['reacciones']]} kN",
              f"- Resultado: {'✅ cumple' if ok else '❌ NO cumple'} (error = {[f'{e:.1e}' for e in q['error']]})", ""]
    return "\n".join(L)
