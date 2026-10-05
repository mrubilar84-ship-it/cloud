"""Genera ejemplos/demo.dxf: pórtico espacial de un piso (6 x 5 m, 4 m de alto) con apoyos y una rótula."""
import ezdxf

doc = ezdxf.new(setup=True)
doc.header["$INSUNITS"] = 6
m = doc.modelspace()
for capa in ["EL_COL", "EL_VIGA", "APOYO_EMPOTRADO", "APOYO_ARTICULADO", "ROTULA", "CARGA_NODAL", "CARGA_DIST"]:
    doc.layers.add(capa)
cols = [(0, 0), (6, 0), (6, 5), (0, 5)]
for x, y in cols:
    m.add_line((x, y, 0), (x, y, 4), dxfattribs={"layer": "EL_COL"})
    m.add_point((x, y, 0), dxfattribs={"layer": "APOYO_EMPOTRADO" if x == 0 else "APOYO_ARTICULADO"})
for a, b in zip(cols, cols[1:] + cols[:1]):
    m.add_line((*a, 4), (*b, 4), dxfattribs={"layer": "EL_VIGA"})
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 4)
    m.add_text("D;0;0;-15", dxfattribs={"layer": "CARGA_DIST", "insert": mid})
m.add_point((6, 5, 4), dxfattribs={"layer": "ROTULA"})
m.add_text("V;10;0;0;0;0;0", dxfattribs={"layer": "CARGA_NODAL", "insert": (0, 0, 4)})
doc.saveas("ejemplos/demo.dxf")
print("ejemplos/demo.dxf creado")
