"""Extrae elementos estructurales de un archivo IFC."""
from dataclasses import dataclass

import ifcopenshell
import ifcopenshell.util.element as util_el

TIPOS = ("IfcBeam", "IfcColumn", "IfcSlab", "IfcWall", "IfcMember", "IfcFooting")


@dataclass
class Elemento:
    id: str
    tipo: str
    nombre: str
    material: str | None
    propiedades: dict


def leer_ifc(ruta: str) -> list[Elemento]:
    modelo = ifcopenshell.open(ruta)
    elementos = []
    for tipo in TIPOS:
        for e in modelo.by_type(tipo):
            mat = util_el.get_material(e)
            elementos.append(
                Elemento(
                    id=e.GlobalId,
                    tipo=tipo,
                    nombre=e.Name or "",
                    material=getattr(mat, "Name", None) if mat else None,
                    propiedades=util_el.get_psets(e),
                )
            )
    return elementos
