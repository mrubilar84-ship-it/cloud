import pytest
import ifcopenshell
import ifcopenshell.api

from estructural.calculo.vigas import viga_simple
from estructural.conocimiento.memoria import Memoria
from estructural.modelos.ifc_lector import leer_ifc


def test_viga_valores_conocidos():
    # L=6 m, w=10 kN/m, acero E=200 GPa, I=8e-5 m4
    r = viga_simple(6, 10e3, 200e9, 8e-5)
    assert r.reaccion_a == pytest.approx(30e3)
    assert r.momento_max == pytest.approx(45e3)  # wL²/8
    assert r.flecha_max == pytest.approx(5 * 10e3 * 6**4 / (384 * 200e9 * 8e-5))


def test_viga_con_puntual():
    r = viga_simple(4, 0, 200e9, 1e-4, carga_puntual=20e3)
    assert r.momento_max == pytest.approx(20e3)  # PL/4
    assert r.corte_max == pytest.approx(10e3)


def test_viga_invalida():
    with pytest.raises(ValueError):
        viga_simple(0, 1, 1, 1)


def test_memoria(tmp_path):
    m = Memoria(str(tmp_path / "m.db"))
    id_ = m.guardar("NCh433", "zonificación", "Zonas sísmicas 1 a 3", "NCh433")
    assert m.buscar("sísmicas", solo_verificado=True) == []
    m.verificar(id_)
    assert len(m.buscar("sísmicas", solo_verificado=True)) == 1


def test_lector_ifc(tmp_path):
    f = ifcopenshell.api.run("project.create_file")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="P")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBeam", name="V1")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcColumn", name="C1")
    ruta = str(tmp_path / "t.ifc")
    f.write(ruta)
    nombres = {(e.tipo, e.nombre) for e in leer_ifc(ruta)}
    assert nombres == {("IfcBeam", "V1"), ("IfcColumn", "C1")}
