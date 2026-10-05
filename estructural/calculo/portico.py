"""Análisis elástico lineal de pórticos 2D con OpenSeesPy.

Unidades: kN, m, kPa (E en kPa, A en m², I en m⁴).
Cada caso de carga se analiza por separado y las combinaciones se obtienen por
superposición lineal (válido para análisis elástico de primer orden).
"""
import openseespy.opensees as ops

N_ESTACIONES = 21


def _construir(modelo: dict, caso: dict) -> None:
    ops.wipe()
    ops.model("basic", "-ndm", 2, "-ndf", 3)
    for nid, (x, y) in modelo["nodos"].items():
        ops.node(int(nid), float(x), float(y))
    for nid, fijo in modelo["apoyos"].items():
        ops.fix(int(nid), *[int(f) for f in fijo])
    ops.geomTransf("Linear", 1)
    for e in modelo["elementos"]:
        s = modelo["secciones"][e["seccion"]]
        E = modelo["materiales"][s["material"]]["E"]
        ops.element("elasticBeamColumn", e["id"], int(e["i"]), int(e["j"]), s["A"], E, s["I"], 1)
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    for nid, (fx, fy, mz) in caso.get("nodales", {}).items():
        ops.load(int(nid), fx, fy, mz)
    for eid, w in caso.get("distribuidas", {}).items():
        ops.eleLoad("-ele", int(eid), "-type", "-beamUniform", w)  # w: kN/m, eje local y
    ops.constraints("Transformation")
    ops.numberer("RCM")
    ops.system("BandGeneral")
    ops.test("NormDispIncr", 1.0e-10, 10)
    ops.algorithm("Linear")
    ops.integrator("LoadControl", 1.0)
    ops.analysis("Static")
    if ops.analyze(1) != 0:
        raise RuntimeError("OpenSees no pudo resolver el modelo (¿estructura inestable?)")


def _longitud(modelo: dict, e: dict) -> float:
    xi, yi = modelo["nodos"][str(e["i"])]
    xj, yj = modelo["nodos"][str(e["j"])]
    return ((xj - xi) ** 2 + (yj - yi) ** 2) ** 0.5


def _resolver_caso(modelo: dict, caso: dict) -> dict:
    _construir(modelo, caso)
    ops.reactions()
    desp = {n: ops.nodeDisp(int(n)) for n in modelo["nodos"]}
    reac = {n: ops.nodeReaction(int(n)) for n in modelo["apoyos"]}
    elems = {}
    for e in modelo["elementos"]:
        f = ops.eleResponse(e["id"], "localForce")  # [N1,V1,M1,N2,V2,M2]
        elems[e["id"]] = {
            "fuerzas": f,
            "w": caso.get("distribuidas", {}).get(str(e["id"]), 0.0),
            "L": _longitud(modelo, e),
        }
    return {"desplazamientos": desp, "reacciones": reac, "elementos": elems}


def _diagramas(res_elem: dict) -> dict:
    """Momento (flexión positiva = tracción abajo) y corte a lo largo del elemento."""
    N1, V1, M1, N2, V2, M2 = res_elem["fuerzas"]
    w, L = res_elem["w"], res_elem["L"]
    xs = [L * k / (N_ESTACIONES - 1) for k in range(N_ESTACIONES)]
    M = [-M1 + V1 * x + w * x**2 / 2 for x in xs]
    V = [V1 + w * x for x in xs]
    return {"x": xs, "M": M, "V": V, "N": [-N1] * len(xs)}


def _combinar(resultados: dict, factores: dict) -> dict:
    """Superposición lineal de casos."""
    primero = resultados[next(iter(factores))]
    out = {"desplazamientos": {}, "reacciones": {}, "elementos": {}}
    for n in primero["desplazamientos"]:
        out["desplazamientos"][n] = [
            sum(f * resultados[c]["desplazamientos"][n][k] for c, f in factores.items())
            for k in range(3)
        ]
    for n in primero["reacciones"]:
        out["reacciones"][n] = [
            sum(f * resultados[c]["reacciones"][n][k] for c, f in factores.items())
            for k in range(3)
        ]
    for eid, base in primero["elementos"].items():
        out["elementos"][eid] = {
            "fuerzas": [
                sum(f * resultados[c]["elementos"][eid]["fuerzas"][k] for c, f in factores.items())
                for k in range(6)
            ],
            "w": sum(f * resultados[c]["elementos"][eid]["w"] for c, f in factores.items()),
            "L": base["L"],
        }
    return out


def _equilibrio(modelo: dict, factores: dict) -> dict:
    """Σ reacciones + Σ cargas aplicadas debe ser ≈ 0."""
    fx = fy = 0.0
    for caso, f in factores.items():
        c = modelo["casos"][caso]
        for fxn, fyn, _ in c.get("nodales", {}).values():
            fx += f * fxn
            fy += f * fyn
        for eid, w in c.get("distribuidas", {}).items():
            e = next(x for x in modelo["elementos"] if str(x["id"]) == str(eid))
            xi, yi = modelo["nodos"][str(e["i"])]
            xj, yj = modelo["nodos"][str(e["j"])]
            L = _longitud(modelo, e)
            c_, s_ = (xj - xi) / L, (yj - yi) / L
            fx += f * w * L * (-s_)  # eje local y = (-sin, cos)
            fy += f * w * L * c_
    return {"cargas": (fx, fy)}


def analizar(modelo: dict) -> dict:
    """Devuelve resultados por combinación, con diagramas y verificación de equilibrio."""
    casos = {n: _resolver_caso(modelo, c) for n, c in modelo["casos"].items()}
    combos = modelo.get("combinaciones") or {n: {n: 1.0} for n in modelo["casos"]}
    salida = {}
    for nombre, factores in combos.items():
        r = _combinar(casos, factores)
        r["diagramas"] = {eid: _diagramas(v) for eid, v in r["elementos"].items()}
        rx = sum(v[0] for v in r["reacciones"].values())
        ry = sum(v[1] for v in r["reacciones"].values())
        fx, fy = _equilibrio(modelo, factores)["cargas"]
        r["equilibrio"] = {"error_x": rx + fx, "error_y": ry + fy, "cargas": (fx, fy), "reacciones": (rx, ry)}
        salida[nombre] = r
    return salida
