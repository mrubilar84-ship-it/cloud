"""Construye un modelo 3D a partir de un DXF con convención de capas.

(Un DWG se guarda como DXF desde AutoCAD/BricsCAD/LibreCAD: Guardar como → DXF.)

Capas:
  EL_<SECCION>       LINE: barra con esa sección (debe existir en el JSON de secciones)
  APOYO_EMPOTRADO    POINT en un nodo: restringe los 6 grados de libertad
  APOYO_ARTICULADO   POINT: restringe ux,uy,uz
  APOYO_RODILLO      POINT: restringe solo uz
  ROTULA             POINT: libera my y mz en todas las barras que llegan a ese nodo
  CARGA_NODAL        TEXT en un nodo: "caso;Fx;Fy;Fz;Mx;My;Mz"  (kN, kN·m, ejes globales)
  CARGA_DIST         TEXT: "caso;wx;wy;wz" (kN/m, ejes locales), aplicada a la barra más cercana
Coordenadas: se escalan según $INSUNITS del DXF (mm, cm, m); sin dato se asumen metros.
"""
import math

import ezdxf

APOYOS = {
    "APOYO_EMPOTRADO": [1, 1, 1, 1, 1, 1],
    "APOYO_ARTICULADO": [1, 1, 1, 0, 0, 0],
    "APOYO_RODILLO": [0, 0, 1, 0, 0, 0],
}
_ESCALA = {0: 1.0, 4: 1e-3, 5: 1e-2, 6: 1.0}
TOL = 1e-3


def _dist_punto_segmento(p, a, b):
    ab = [b[k] - a[k] for k in range(3)]
    ap = [p[k] - a[k] for k in range(3)]
    t = max(0.0, min(1.0, sum(ab[k] * ap[k] for k in range(3)) / sum(c * c for c in ab)))
    q = [a[k] + t * ab[k] for k in range(3)]
    return math.dist(p, q)


def leer_dxf(ruta: str, secciones: dict, materiales: dict) -> dict:
    doc = ezdxf.readfile(ruta)
    esc = _ESCALA.get(doc.header.get("$INSUNITS", 6), 1.0)
    msp = doc.modelspace()
    p3 = lambda v: tuple(round(c * esc, 4) for c in v)

    nodos: dict[tuple, int] = {}

    def nodo(p):
        for q, i in nodos.items():
            if math.dist(p, q) < TOL:
                return i
        nodos[p] = len(nodos) + 1
        return nodos[p]

    elementos = []
    for ln in msp.query("LINE"):
        capa = ln.dxf.layer.upper()
        if not capa.startswith("EL_"):
            continue
        sec = ln.dxf.layer[3:]
        if sec not in secciones:
            raise ValueError(f"Sección '{sec}' (capa {ln.dxf.layer}) no está en el archivo de secciones")
        i, j = nodo(p3(ln.dxf.start)), nodo(p3(ln.dxf.end))
        if i == j:
            raise ValueError(f"Barra de largo cero en capa {ln.dxf.layer}")
        elementos.append({"id": len(elementos) + 1, "i": i, "j": j, "seccion": sec})
    if not elementos:
        raise ValueError("El DXF no tiene barras (LINE en capas EL_<SECCION>)")

    def nodo_existente(p, capa):
        for q, i in nodos.items():
            if math.dist(p, q) < TOL:
                return i
        raise ValueError(f"{capa}: el punto {p} no coincide con ningún nodo de la estructura")

    apoyos: dict[str, list] = {}
    rotulas: set[int] = set()
    for pt in msp.query("POINT"):
        capa = pt.dxf.layer.upper()
        if capa in APOYOS:
            apoyos[str(nodo_existente(p3(pt.dxf.location), capa))] = APOYOS[capa]
        elif capa == "ROTULA":
            rotulas.add(nodo_existente(p3(pt.dxf.location), capa))
    if not apoyos:
        raise ValueError("No hay apoyos (POINT en capas APOYO_*): la estructura sería inestable")
    for e in elementos:
        if e["i"] in rotulas:
            e["liberar_i"] = ["my", "mz"]
        if e["j"] in rotulas:
            e["liberar_j"] = ["my", "mz"]

    coords = {i: q for q, i in nodos.items()}
    casos: dict[str, dict] = {}
    for tx in msp.query("TEXT"):
        capa = tx.dxf.layer.upper()
        if capa not in ("CARGA_NODAL", "CARGA_DIST"):
            continue
        campos = [c.strip() for c in tx.dxf.text.split(";")]
        caso, vals = campos[0], [float(v) for v in campos[1:]]
        c = casos.setdefault(caso, {"nodales": {}, "distribuidas": {}})
        p = p3(tx.dxf.insert)
        if capa == "CARGA_NODAL":
            if len(vals) != 6:
                raise ValueError(f"CARGA_NODAL '{tx.dxf.text}': se esperan 6 valores")
            c["nodales"][str(nodo_existente(p, capa))] = vals
        else:
            if len(vals) != 3:
                raise ValueError(f"CARGA_DIST '{tx.dxf.text}': se esperan 3 valores")
            e = min(elementos, key=lambda e: _dist_punto_segmento(p, coords[e["i"]], coords[e["j"]]))
            c["distribuidas"][str(e["id"])] = vals
    if not casos:
        raise ValueError("No hay cargas (TEXT en capas CARGA_NODAL / CARGA_DIST)")

    return {
        "materiales": materiales,
        "secciones": secciones,
        "nodos": {str(i): list(q) for q, i in nodos.items()},
        "apoyos": apoyos,
        "elementos": elementos,
        "casos": casos,
    }
