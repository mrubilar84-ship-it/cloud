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


def test_portico_equilibrio_y_memoria(tmp_path):
    import json
    from estructural.calculo.portico import analizar
    from estructural.informe.memoria_calculo import generar

    modelo = json.load(open("ejemplos/portico_simple.json"))
    res = analizar(modelo)
    for r in res.values():
        assert abs(r["equilibrio"]["error_x"]) < 1e-6
        assert abs(r["equilibrio"]["error_y"]) < 1e-6
    # carga vertical simétrica: reacciones verticales iguales, 1.4·12·6/2 = 50.4 kN
    assert res["1.4D"]["reacciones"]["1"][1] == pytest.approx(50.4)
    assert res["1.4D"]["reacciones"]["4"][1] == pytest.approx(50.4)
    md = generar(modelo, res, "Prueba")
    assert "✅ cumple" in md and "❌" not in md


def test_viga_vs_opensees():
    from estructural.calculo.portico import analizar

    m = {"materiales": {"a": {"E": 2e8}}, "secciones": {"S": {"A": 0.005, "I": 8e-5, "material": "a"}},
         "nodos": {"1": [0, 0], "2": [3, 0], "3": [6, 0]}, "apoyos": {"1": [1, 1, 0], "3": [0, 1, 0]},
         "elementos": [{"id": 1, "i": 1, "j": 2, "seccion": "S"}, {"id": 2, "i": 2, "j": 3, "seccion": "S"}],
         "casos": {"D": {"distribuidas": {"1": -10.0, "2": -10.0}}}}
    r = analizar(m)["D"]
    ref = viga_simple(6, 10e3, 200e9, 8e-5)
    assert r["desplazamientos"]["2"][1] == pytest.approx(-ref.flecha_max, rel=1e-6)
    assert max(r["diagramas"][1]["M"]) * 1e3 == pytest.approx(ref.momento_max, rel=1e-6)
