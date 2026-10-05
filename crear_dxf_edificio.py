"""Genera ejemplos/edificio_2pisos.dxf: edificio de 2 pisos, 2x2 vanos (5 m), altura de piso 3,5 m."""
import ezdxf

VANO, ALTO, NV, NP = 5.0, 3.5, 2, 2
doc = ezdxf.new(setup=True)
doc.header["$INSUNITS"] = 6
m = doc.modelspace()
for capa in ["EL_COL", "EL_VIGA", "APOYO_EMPOTRADO", "APOYO_ARTICULADO", "ROTULA", "CARGA_NODAL", "CARGA_DIST"]:
    doc.layers.add(capa)

for i in range(NV + 1):
    for j in range(NV + 1):
        x, y = i * VANO, j * VANO
        for p in range(NP):  # columnas
            m.add_line((x, y, p * ALTO), (x, y, (p + 1) * ALTO), dxfattribs={"layer": "EL_COL"})
        borde = i in (0, NV) and j in (0, NV)
        m.add_point((x, y, 0), dxfattribs={"layer": "APOYO_EMPOTRADO" if borde else "APOYO_ARTICULADO"})

for p in range(1, NP + 1):
    z = p * ALTO
    for i in range(NV + 1):
        for j in range(NV):  # vigas en Y
            a, b = (i * VANO, j * VANO, z), (i * VANO, (j + 1) * VANO, z)
            m.add_line(a, b, dxfattribs={"layer": "EL_VIGA"})
            m.add_text("D;0;0;-12", dxfattribs={"layer": "CARGA_DIST", "insert": (a[0], a[1] + VANO / 2, z)})
    for j in range(NV + 1):
        for i in range(NV):  # vigas en X
            a, b = (i * VANO, j * VANO, z), ((i + 1) * VANO, j * VANO, z)
            m.add_line(a, b, dxfattribs={"layer": "EL_VIGA"})
            m.add_text("D;0;0;-12", dxfattribs={"layer": "CARGA_DIST", "insert": (a[0] + VANO / 2, a[1], z)})
    for j in range(NV + 1):  # viento en dirección X sobre la fachada x=0
        m.add_text(f"V;{8 if p == NP else 12};0;0;0;0;0", dxfattribs={"layer": "CARGA_NODAL", "insert": (0, j * VANO, z)})

m.add_point((VANO, VANO, ALTO), dxfattribs={"layer": "ROTULA"})  # rótula esférica en nodo central, nivel 1
doc.saveas("ejemplos/edificio_2pisos.dxf")
print("ejemplos/edificio_2pisos.dxf creado")
