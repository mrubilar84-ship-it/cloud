import json
import subprocess
import sys
import zipfile

import pytest

from estructural.revision import calcular_paquete, validar_modelo

SEC, COMB = "ejemplos/secciones_demo.json", "ejemplos/combinaciones_demo.json"


@pytest.fixture(scope="module", autouse=True)
def dxf():
    subprocess.run([sys.executable, "crear_dxf_edificio.py"], check=True, capture_output=True)
    return "ejemplos/edificio_2pisos.dxf"


def test_paquete_completo(tmp_path, dxf):
    r = calcular_paquete(dxf, SEC, COMB, str(tmp_path), "Demo")
    assert r["equilibrio_ok"]
    with zipfile.ZipFile(r["zip"]) as z:
        nombres = set(z.namelist())
    assert {"LEEME_revision.md", "memoria_calculo.md", "resultados.json", "modelo_resuelto.json",
            "entradas/edificio_2pisos.dxf", "entradas/secciones_demo.json",
            "entradas/combinaciones_demo.json"} <= nombres
    datos = json.load(open(tmp_path / "resultados.json"))
    assert set(datos["resultados"]) == {"1.4D", "1.2D+1.0V"}
    assert datos["modelo"]["barras_con_rotula"]  # la rótula del DXF quedó registrada


def test_sin_combinaciones_advierte(tmp_path, dxf):
    r = calcular_paquete(dxf, SEC, None, str(tmp_path))
    assert any("combinaciones" in a for a in r["advertencias"])


def test_combinacion_con_caso_inexistente(tmp_path, dxf):
    malas = tmp_path / "c.json"
    malas.write_text(json.dumps({"combinaciones": {"X": {"NOEXISTE": 1.0}}}))
    with pytest.raises(ValueError, match="NOEXISTE"):
        calcular_paquete(dxf, SEC, str(malas), str(tmp_path / "s"))


def test_detecta_errores_de_unidades():
    modelo = {"materiales": {"a": {"E": 200e9}},  # E en Pa en vez de kPa
              "secciones": {"S": {"A": 53.8, "Iy": 8356, "Iz": 604, "J": 20, "material": "a"}},  # cm sin convertir
              "elementos": [], "casos": {}}
    av = " ".join(validar_modelo(modelo))
    assert "cm²/cm⁴" in av and "fuera de rango" in av
    modelo["secciones"]["S"] = {"A": 0.005, "Iy": 1e-5, "Iz": 8e-5, "J": 1e-7, "material": "a"}
    assert "Iz > Iy" in " ".join(validar_modelo(modelo))
