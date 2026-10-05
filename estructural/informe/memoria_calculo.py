"""Genera la memoria de cálculo en Markdown a partir del modelo y los resultados."""
from datetime import date


def _tabla(encabezado: list[str], filas: list[list]) -> str:
    out = ["| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)]
    out += ["| " + " | ".join(str(c) for c in f) + " |" for f in filas]
    return "\n".join(out)


def generar(modelo: dict, resultados: dict, proyecto: str = "Proyecto sin nombre") -> str:
    L = [f"# Memoria de cálculo — {proyecto}", f"Fecha: {date.today().isoformat()}", ""]
    L += [
        "> **Aviso:** documento generado automáticamente. Requiere revisión y firma de un "
        "ingeniero responsable antes de cualquier uso en obra.",
        "",
        "## 1. Método y supuestos",
        "- Análisis elástico lineal de primer orden, pórtico plano (2D), OpenSeesPy (`elasticBeamColumn`).",
        "- Unidades: kN, m, kPa. Combinaciones por superposición lineal de casos.",
        "- Convención: momento positivo = tracción en la fibra inferior (eje local y hacia arriba).",
        "- **No incluye** verificación de resistencia según norma (NCh/ACI/AISC), pandeo, "
        "efectos P-Δ ni análisis sísmico.",
        "",
        "## 2. Materiales y secciones",
        _tabla(["Material", "E [kPa]"], [[n, f"{m['E']:.3e}"] for n, m in modelo["materiales"].items()]),
        "",
        _tabla(
            ["Sección", "Material", "A [m²]", "I [m⁴]"],
            [[n, s["material"], f"{s['A']:.4e}", f"{s['I']:.4e}"] for n, s in modelo["secciones"].items()],
        ),
        "",
        "## 3. Geometría",
        _tabla(["Nodo", "x [m]", "y [m]", "Apoyo (ux,uy,rz)"],
               [[n, c[0], c[1], modelo["apoyos"].get(n, "libre")] for n, c in modelo["nodos"].items()]),
        "",
        _tabla(["Elemento", "Nodo i", "Nodo j", "Sección"],
               [[e["id"], e["i"], e["j"], e["seccion"]] for e in modelo["elementos"]]),
        "",
        "## 4. Casos de carga",
    ]
    for nombre, c in modelo["casos"].items():
        L.append(f"**{nombre}**")
        for n, (fx, fy, mz) in c.get("nodales", {}).items():
            L.append(f"- Nodo {n}: Fx={fx} kN, Fy={fy} kN, Mz={mz} kN·m")
        for e, w in c.get("distribuidas", {}).items():
            L.append(f"- Elemento {e}: w={w} kN/m (eje local y)")
        L.append("")
    if modelo.get("combinaciones"):
        L.append("**Combinaciones:** " + "; ".join(
            f"{n} = " + " + ".join(f"{f}·{c}" for c, f in fs.items())
            for n, fs in modelo["combinaciones"].items()))
        L.append("")

    L.append("## 5. Resultados")
    for i, (nombre, r) in enumerate(resultados.items(), 1):
        L += [f"### 5.{i} Combinación {nombre}", "", "**Desplazamientos nodales**",
              _tabla(["Nodo", "ux [mm]", "uy [mm]", "rz [mrad]"],
                     [[n, *(f"{1000 * v:.3f}" for v in d)] for n, d in r["desplazamientos"].items()]),
              "", "**Reacciones**",
              _tabla(["Nodo", "Rx [kN]", "Ry [kN]", "Mz [kN·m]"],
                     [[n, *(f"{v:.3f}" for v in d)] for n, d in r["reacciones"].items()]),
              "", "**Esfuerzos máximos por elemento**",
              _tabla(["Elemento", "M máx [kN·m]", "M mín [kN·m]", "|V| máx [kN]", "|N| máx [kN]"],
                     [[eid, f"{max(d['M']):.3f}", f"{min(d['M']):.3f}",
                       f"{max(abs(v) for v in d['V']):.3f}", f"{max(abs(v) for v in d['N']):.3f}"]
                      for eid, d in r["diagramas"].items()]),
              ""]
        q = r["equilibrio"]
        ok = abs(q["error_x"]) < 1e-6 and abs(q["error_y"]) < 1e-6
        L += ["**Verificación de equilibrio global**",
              f"- Σ cargas = ({q['cargas'][0]:.3f}, {q['cargas'][1]:.3f}) kN; "
              f"Σ reacciones = ({q['reacciones'][0]:.3f}, {q['reacciones'][1]:.3f}) kN",
              f"- Resultado: {'✅ cumple' if ok else '❌ NO cumple'} "
              f"(error x={q['error_x']:.2e}, y={q['error_y']:.2e})", ""]
    return "\n".join(L)
