"""Análisis elástico lineal de estructuras 3D (barras) con OpenSeesPy.

Unidades: kN, m, kPa. Eje global Z hacia arriba.
Modelo (dict):
  materiales: {nombre: {"E", "G"}}
  secciones:  {nombre: {"A","Iy","Iz","J","material"}}
  nodos:      {id: [x,y,z]}
  apoyos:     {id: [ux,uy,uz,rx,ry,rz]}  (1 = restringido)
  elementos:  [{"id","i","j","seccion","vecxz"?,"liberar_i"?,"liberar_j"?}]
              liberar_*: lista con "mx" (torsión), "my", "mz" (momentos en ejes locales)
  casos:      {nombre: {"nodales": {nid: [Fx,Fy,Fz,Mx,My,Mz]},
                        "distribuidas": {eid: [wx,wy,wz]}}}   # ejes locales, kN/m
  combinaciones: {nombre: {caso: factor}}
Ejes locales: x a lo largo de i→j; y = vecxz × x; z = x × y. Por defecto vecxz = Z global
(o X global si el elemento es vertical).
"""
import math

import openseespy.opensees as ops

K_RIGIDA = 1.0e12
K_MIN = 1.0e-3  # kN·m/rad: evita singularidad en nodos con todas las rotaciones liberadas
N_ESTACIONES = 21
_LIB = {"mx": 4, "my": 5, "mz": 6}  # dirección local de la rotación


def _sub(a, b):
    return [a[k] - b[k] for k in range(3)]


def _cruz(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _norm(a):
    n = math.sqrt(sum(c * c for c in a))
    return [c / n for c in a]


def ejes_locales(modelo: dict, e: dict) -> tuple[list, list, list, float]:
    pi, pj = modelo["nodos"][str(e["i"])], modelo["nodos"][str(e["j"])]
    d = _sub(pj, pi)
    L = math.sqrt(sum(c * c for c in d))
    x = _norm(d)
    vxz = e.get("vecxz") or ([1, 0, 0] if abs(x[2]) > 0.999 else [0, 0, 1])
    y = _norm(_cruz(vxz, x))
    z = _cruz(x, y)
    return x, y, z, L


def _construir(modelo: dict, caso: dict) -> None:
    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)
    for nid, (x, y, z) in modelo["nodos"].items():
        ops.node(int(nid), float(x), float(y), float(z))
    for nid, fijo in modelo["apoyos"].items():
        ops.fix(int(nid), *[int(f) for f in fijo])
    ops.uniaxialMaterial("Elastic", 1, K_RIGIDA)
    ops.uniaxialMaterial("Elastic", 2, K_MIN)
    nodo_extra, ele_extra = 100000, 200000
    for e in modelo["elementos"]:
        x, y, z, L = ejes_locales(modelo, e)
        ops.geomTransf("Linear", e["id"], *(e.get("vecxz") or ([1, 0, 0] if abs(x[2]) > 0.999 else [0, 0, 1])))
        s = modelo["secciones"][e["seccion"]]
        m = modelo["materiales"][s["material"]]
        extremos = []
        for lado, nid in (("liberar_i", e["i"]), ("liberar_j", e["j"])):
            lib = e.get(lado) or []
            if not lib:
                extremos.append(int(nid))
                continue
            nodo_extra += 1
            ele_extra += 1
            ops.node(nodo_extra, *[float(c) for c in modelo["nodos"][str(nid)]])
            dirs = [1, 2, 3] + list(_LIB.values())
            mats = [1, 1, 1] + [2 if k in lib else 1 for k in _LIB]
            ops.element("zeroLength", ele_extra, int(nid), nodo_extra,
                        "-mat", *mats, "-dir", *dirs, "-orient", *x, *y)
            extremos.append(nodo_extra)
        ops.element("elasticBeamColumn", e["id"], extremos[0], extremos[1],
                    s["A"], m["E"], m["G"], s["J"], s["Iy"], s["Iz"], e["id"])
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    for nid, f in caso.get("nodales", {}).items():
        ops.load(int(nid), *f)
    for eid, (wx, wy, wz) in caso.get("distribuidas", {}).items():
        ops.eleLoad("-ele", int(eid), "-type", "-beamUniform", wy, wz, wx)
    ops.constraints("Transformation")
    ops.numberer("RCM")
    ops.system("BandGeneral")
    ops.test("NormDispIncr", 1.0e-8, 10)
    ops.algorithm("Linear")
    ops.integrator("LoadControl", 1.0)
    ops.analysis("Static")
    if ops.analyze(1) != 0:
        raise RuntimeError("OpenSees no pudo resolver el modelo (¿inestable o mal apoyado?)")


def _resolver_caso(modelo: dict, caso: dict) -> dict:
    _construir(modelo, caso)
    ops.reactions()
    res = {
        "desplazamientos": {n: ops.nodeDisp(int(n)) for n in modelo["nodos"]},
        "reacciones": {n: ops.nodeReaction(int(n)) for n in modelo["apoyos"]},
        "elementos": {},
    }
    for e in modelo["elementos"]:
        w = caso.get("distribuidas", {}).get(str(e["id"]), [0, 0, 0])
        res["elementos"][e["id"]] = {"fuerzas": ops.eleResponse(e["id"], "localForce"), "w": list(w),
                                     "L": ejes_locales(modelo, e)[3]}
    return res


def _diagramas(r: dict) -> dict:
    """Esfuerzos internos en estaciones. Convención: esfuerzo en la sección a x desde el nodo i,
    obtenido por equilibrio del tramo izquierdo."""
    f, (wx, wy, wz), L = r["fuerzas"], r["w"], r["L"]
    N1, Vy1, Vz1, T1, My1, Mz1 = f[:6]
    xs = [L * k / (N_ESTACIONES - 1) for k in range(N_ESTACIONES)]
    return {
        "x": xs,
        "N": [-(N1 + wx * x) for x in xs],
        "Vy": [Vy1 + wy * x for x in xs],
        "Vz": [Vz1 + wz * x for x in xs],
        "T": [-T1] * len(xs),
        "Mz": [-Mz1 + Vy1 * x + wy * x**2 / 2 for x in xs],
        "My": [My1 + Vz1 * x + wz * x**2 / 2 for x in xs],
    }


def _combinar(res: dict, factores: dict, n_vals: dict) -> dict:
    primero = res[next(iter(factores))]
    sup = lambda getter, n: [sum(f * getter(res[c])[k] for c, f in factores.items()) for k in range(n)]
    return {
        "desplazamientos": {n: sup(lambda r, n=n: r["desplazamientos"][n], 6) for n in primero["desplazamientos"]},
        "reacciones": {n: sup(lambda r, n=n: r["reacciones"][n], 6) for n in primero["reacciones"]},
        "elementos": {
            eid: {
                "fuerzas": sup(lambda r, eid=eid: r["elementos"][eid]["fuerzas"], 12),
                "w": sup(lambda r, eid=eid: r["elementos"][eid]["w"], 3),
                "L": v["L"],
            }
            for eid, v in primero["elementos"].items()
        },
    }


def _cargas_globales(modelo: dict, factores: dict) -> list:
    tot = [0.0] * 3
    for caso, f in factores.items():
        c = modelo["casos"][caso]
        for fn in c.get("nodales", {}).values():
            for k in range(3):
                tot[k] += f * fn[k]
        for eid, w in c.get("distribuidas", {}).items():
            e = next(x for x in modelo["elementos"] if str(x["id"]) == str(eid))
            x, y, z, L = ejes_locales(modelo, e)
            for k in range(3):
                tot[k] += f * L * (w[0] * x[k] + w[1] * y[k] + w[2] * z[k])
    return tot


def analizar(modelo: dict) -> dict:
    casos = {n: _resolver_caso(modelo, c) for n, c in modelo["casos"].items()}
    combos = modelo.get("combinaciones") or {n: {n: 1.0} for n in modelo["casos"]}
    salida = {}
    for nombre, factores in combos.items():
        r = _combinar(casos, factores, {})
        r["diagramas"] = {eid: _diagramas(v) for eid, v in r["elementos"].items()}
        rs = [sum(v[k] for v in r["reacciones"].values()) for k in range(3)]
        cg = _cargas_globales(modelo, factores)
        r["equilibrio"] = {"cargas": cg, "reacciones": rs, "error": [rs[k] + cg[k] for k in range(3)]}
        salida[nombre] = r
    return salida
