import json
import subprocess
import sys
from types import SimpleNamespace as NS

from estructural.agente.agente import Agente


def texto(t):
    return NS(type="text", text=t)


def llamada(id_, nombre, **args):
    return NS(type="tool_use", id=id_, name=nombre, input=args)


def resp(*bloques, stop="tool_use"):
    return NS(content=list(bloques), stop_reason=stop, stop_details=None)


class ClienteFalso:
    """Reproduce una secuencia de respuestas y guarda las peticiones recibidas."""

    def __init__(self, respuestas):
        self.respuestas, self.peticiones = list(respuestas), []
        self.messages = self

    def create(self, **kw):
        self.peticiones.append(dict(kw, messages=list(kw["messages"])))  # copia: la lista original sigue creciendo
        return self.respuestas.pop(0)


def _preparar(tmp_path):
    subprocess.run([sys.executable, "crear_dxf_demo.py"], check=True, capture_output=True)
    return "ejemplos/demo.dxf", "ejemplos/secciones_demo.json"


def _flujo(dxf, sec, memoria="m.md"):
    return [
        resp(llamada("1", "leer_dxf", ruta_dxf=dxf, ruta_secciones=sec)),
        resp(llamada("2", "definir_combinaciones", combinaciones={"U": {"D": 1.2, "V": 1.0}}, justificacion="x")),
        resp(llamada("3", "calcular_estructura")),
        resp(llamada("4", "generar_memoria", nombre_archivo=memoria, proyecto="Demo")),
        resp(texto("Listo. Requiere revisión de un ingeniero."), stop="end_turn"),
    ]


def test_flujo_completo(tmp_path):
    dxf, sec = _preparar(tmp_path)
    cli = ClienteFalso(_flujo(dxf, sec))
    ag = Agente(cli, str(tmp_path), preguntar=lambda t: "", aprobar=lambda t: True)
    out = ag.turno("analiza")
    assert "ingeniero" in out
    md = (tmp_path / "salidas" / "m.md").read_text()
    assert "✅ cumple" in md
    # petición: modelo, thinking y herramientas; tool_results de una iteración van en un solo mensaje
    p = cli.peticiones[0]
    assert p["model"] == "claude-opus-5-5" and p["thinking"] == {"type": "adaptive"}
    assert {t["name"] for t in p["tools"]} >= {"leer_dxf", "calcular_estructura", "generar_memoria"}
    # el registro de auditoría guarda cada herramienta
    lineas = [json.loads(l) for l in open(tmp_path / "registro.jsonl")]
    assert [l["nombre"] for l in lineas if l["tipo"] == "herramienta"] == [
        "leer_dxf", "definir_combinaciones", "calcular_estructura", "generar_memoria"]


def test_aprobacion_denegada_no_escribe(tmp_path):
    dxf, sec = _preparar(tmp_path)
    cli = ClienteFalso(_flujo(dxf, sec))
    ag = Agente(cli, str(tmp_path), preguntar=lambda t: "", aprobar=lambda t: False)
    ag.turno("analiza")
    assert not (tmp_path / "salidas" / "m.md").exists()
    ultimo = cli.peticiones[-1]["messages"][-1]["content"][0]["content"]
    assert "NO aprobó" in ultimo or "No hay resultados" in ultimo


def test_errores_vuelven_como_tool_result_con_is_error(tmp_path):
    cli = ClienteFalso([
        resp(llamada("1", "calcular_estructura")),  # sin modelo cargado
        resp(texto("Falta cargar el modelo."), stop="end_turn"),
    ])
    ag = Agente(cli, str(tmp_path), preguntar=lambda t: "", aprobar=lambda t: True)
    ag.turno("calcula")
    r = cli.peticiones[1]["messages"][-1]["content"][0]
    assert r["is_error"] is True and "leer_dxf" in r["content"]


def test_nombre_de_archivo_no_escapa_de_salidas(tmp_path):
    dxf, sec = _preparar(tmp_path)
    flujo = _flujo(dxf, sec, memoria="../../escape.md")
    ag = Agente(ClienteFalso(flujo), str(tmp_path), preguntar=lambda t: "", aprobar=lambda t: True)
    ag.turno("analiza")
    assert (tmp_path / "salidas" / "escape.md").exists()
    assert not (tmp_path.parent / "escape.md").exists()


def test_memoria_normas_guardar_y_buscar(tmp_path):
    cli = ClienteFalso([
        resp(llamada("1", "guardar_criterio", norma="NCh433", tema="zonas", contenido="Zonas 1-3", fuente="NCh433")),
        resp(llamada("2", "buscar_norma", texto="zonas")),
        resp(llamada("3", "buscar_norma", texto="zonas", incluir_no_verificado=True)),
        resp(texto("ok"), stop="end_turn"),
    ])
    ag = Agente(cli, str(tmp_path), preguntar=lambda t: "", aprobar=lambda t: True)
    ag.turno("guarda")
    solo_verif = json.loads(cli.peticiones[2]["messages"][-1]["content"][0]["content"])
    todo = json.loads(cli.peticiones[3]["messages"][-1]["content"][0]["content"])
    assert solo_verif["resultados"] == [] and len(todo["resultados"]) == 1


def test_rechazo_y_limite_de_pasos(tmp_path):
    ag = Agente(ClienteFalso([resp(stop="refusal")]), str(tmp_path), preguntar=lambda t: "", aprobar=lambda t: True)
    assert "rechazó" in ag.turno("x")
    bucle = ClienteFalso([resp(llamada(str(i), "preguntar_usuario", pregunta="?")) for i in range(40)])
    ag = Agente(bucle, str(tmp_path / "b"), preguntar=lambda t: "r", aprobar=lambda t: True)
    assert "máximo de pasos" in ag.turno("x")


def test_la_sdk_acepta_los_parametros_de_la_peticion():
    import inspect
    import anthropic
    params = inspect.signature(anthropic.Anthropic(api_key="x").messages.create).parameters
    assert {"thinking", "output_config", "tools", "system", "max_tokens"} <= set(params)
