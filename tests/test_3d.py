import ezdxf
import pytest

from estructural.calculo.estructura3d import analizar
from estructural.informe.memoria_calculo_3d import generar
from estructural.modelos.dxf_lector import leer_dxf

E = 2e8
I = 8e-5
BASE = {
    "materiales": {"a": {"E": E, "G": E / 2.6}},
    "secciones": {"S": {"A": 0.005, "Iy": I, "Iz": I, "J": 1e-5, "material": "a"}},
}


def viga(apoyo_j, carga, **extra):
    m = dict(BASE, nodos={"1": [0, 0, 0], "2": [3, 0, 0], "3": [6, 0, 0]},
             apoyos={"1": [1] * 6, "3": apoyo_j},
             elementos=[{"id": 1, "i": 1, "j": 2, "seccion": "S"}, {"id": 2, "i": 2, "j": 3, "seccion": "S"}],
             casos={"D": carga})
    m.update(extra)
    return m


def test_voladizo_3d():
    m = dict(BASE, nodos={"1": [0, 0, 0], "2": [3, 0, 0]}, apoyos={"1": [1] * 6},
             elementos=[{"id": 1, "i": 1, "j": 2, "seccion": "S"}],
             casos={"P": {"nodales": {"2": [0, 0, -10, 0, 0, 0]}}})
    r = analizar(m)["P"]
    assert r["desplazamientos"]["2"][2] == pytest.approx(-10 * 27 / (3 * E * I), rel=1e-6)
    assert r["reacciones"]["1"][2] == pytest.approx(10)
    d = r["diagramas"][1]["My"]
    assert abs(d[0]) == pytest.approx(30) and d[-1] == pytest.approx(0, abs=1e-9)


def test_empotrado_apoyo_simple():
    w = {"distribuidas": {"1": [0, 0, -10], "2": [0, 0, -10]}}
    r = analizar(viga([1, 1, 1, 0, 0, 0], w))["D"]
    assert r["reacciones"]["3"][2] == pytest.approx(22.5)  # 3wL/8
    assert r["reacciones"]["1"][2] == pytest.approx(37.5)  # 5wL/8
    assert abs(r["reacciones"]["1"][4]) == pytest.approx(45)  # wL²/8


def test_rotula_intermedia_vuelve_isostatica_la_viga():
    w = {"distribuidas": {"1": [0, 0, -10], "2": [0, 0, -10]}}
    m = viga([1, 1, 1, 0, 0, 0], w)
    m["elementos"][0]["liberar_j"] = ["my"]
    r = analizar(m)["D"]
    assert r["reacciones"]["3"][2] == pytest.approx(15)  # tramo 2 simplemente apoyado (3 m)
    assert r["diagramas"][2]["My"][0] == pytest.approx(0, abs=1e-4)  # residuo del resorte K_MIN


def test_mz_con_carga_en_y():
    w = {"distribuidas": {"1": [0, -10, 0], "2": [0, -10, 0]}}
    r = analizar(viga([1, 1, 1, 0, 0, 0], w))["D"]
    mz = r["diagramas"][1]["Mz"] + r["diagramas"][2]["Mz"]
    assert min(mz) == pytest.approx(-45) and max(mz) == pytest.approx(25.3125, rel=1e-4)


def test_combinaciones_y_equilibrio():
    m = viga([1, 1, 1, 0, 0, 0], {}, casos={
        "D": {"distribuidas": {"1": [0, 0, -10], "2": [0, 0, -10]}},
        "V": {"nodales": {"2": [5, 0, 0, 0, 0, 0]}}},
        combinaciones={"U": {"D": 1.2, "V": 1.0}})
    r = analizar(m)["U"]
    assert all(abs(e) < 1e-4 for e in r["equilibrio"]["error"])
    assert "✅ cumple" in generar(m, {"U": r}, "t")


def test_demo_dxf(tmp_path):
    import json, subprocess, sys
    subprocess.run([sys.executable, "crear_dxf_demo.py"], check=True, capture_output=True)
    sec = json.load(open("ejemplos/secciones_demo.json"))
    m = leer_dxf("ejemplos/demo.dxf", sec["secciones"], sec["materiales"])
    assert len(m["elementos"]) == 8 and len(m["nodos"]) == 8
    assert sum(1 for e in m["elementos"] if "liberar_i" in e or "liberar_j" in e) == 3
    for r in analizar(m).values():
        assert all(abs(e) < 1e-4 for e in r["equilibrio"]["error"])


def _dxf(tmp_path, entidades):
    doc = ezdxf.new()
    msp = doc.modelspace()
    entidades(msp)
    ruta = str(tmp_path / "t.dxf")
    doc.saveas(ruta)
    return ruta


def test_dxf_errores(tmp_path):
    sec = {"S": BASE["secciones"]["S"]}
    mat = BASE["materiales"]
    sin_apoyo = _dxf(tmp_path, lambda m: m.add_line((0, 0, 0), (1, 0, 0), dxfattribs={"layer": "EL_S"}))
    with pytest.raises(ValueError, match="apoyos"):
        leer_dxf(sin_apoyo, sec, mat)
    seccion_mala = _dxf(tmp_path, lambda m: m.add_line((0, 0, 0), (1, 0, 0), dxfattribs={"layer": "EL_XYZ"}))
    with pytest.raises(ValueError, match="XYZ"):
        leer_dxf(seccion_mala, sec, mat)
    def apoyo_flotante(m):
        m.add_line((0, 0, 0), (1, 0, 0), dxfattribs={"layer": "EL_S"})
        m.add_point((5, 5, 5), dxfattribs={"layer": "APOYO_EMPOTRADO"})
    with pytest.raises(ValueError, match="ningún nodo"):
        leer_dxf(_dxf(tmp_path, apoyo_flotante), sec, mat)
