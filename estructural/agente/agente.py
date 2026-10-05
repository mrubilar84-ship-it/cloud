"""Agente de cálculo estructural: Claude orquesta, el código determinista calcula."""
import json
from datetime import datetime
from pathlib import Path

from estructural.agente.herramientas import DEFINICIONES, Herramientas

MODELO = "claude-opus-5-5"
MAX_ITERACIONES = 30

SISTEMA = """Eres un asistente de ingeniería estructural. Operas un motor de cálculo determinista \
(OpenSees, análisis elástico lineal de barras 3D) mediante herramientas, y ayudas a un ingeniero a \
analizar estructuras y emitir memorias de cálculo.

Reglas:
- Todo número que reportes debe venir de una herramienta. Nunca calcules ni estimes resultados por tu cuenta.
- Si faltan datos (apoyos, perfiles, cargas, combinaciones), pregunta con preguntar_usuario en vez de suponer.
- Las combinaciones de carga y cualquier criterio de diseño son supuestos: justifícalos y espera la aprobación.
- Después de calcular, revisa el equilibrio global y si los desplazamientos y esfuerzos son plausibles; \
si algo no cuadra, dilo claramente y no emitas la memoria.
- Usa buscar_norma antes de citar una norma. Solo las entradas verificadas son confiables; las no \
verificadas debes presentarlas como tales. Nunca afirmes que la estructura "cumple" una norma: el motor \
solo calcula esfuerzos y deformaciones, no verifica resistencia.
- Termina siempre recordando que el resultado requiere revisión y firma de un ingeniero responsable.
Responde en español, de forma concisa."""


class Agente:
    def __init__(self, cliente, carpeta: str, preguntar=input, aprobar=None, modelo: str = MODELO):
        self.cliente, self.modelo = cliente, modelo
        self.carpeta = Path(carpeta)
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self._preguntar = preguntar
        aprobar = aprobar or (lambda t: input(f"\n[APROBACIÓN] {t}\n¿Aprobar? (s/n): ").strip().lower() in ("s", "si", "sí", "y"))
        self.herramientas = Herramientas(str(carpeta), self._preguntar_usuario, aprobar)
        self.mensajes: list = []
        self.registro = self.carpeta / "registro.jsonl"

    def _preguntar_usuario(self, texto: str) -> str:
        return self._preguntar(f"\n[AGENTE PREGUNTA] {texto}\n> ")

    def _log(self, tipo: str, **datos) -> None:
        with open(self.registro, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": datetime.now().isoformat(timespec="seconds"), "tipo": tipo, **datos},
                               ensure_ascii=False, default=str) + "\n")

    def turno(self, texto_usuario: str) -> str:
        """Procesa un mensaje del usuario y devuelve la respuesta final del agente."""
        self.mensajes.append({"role": "user", "content": texto_usuario})
        self._log("usuario", texto=texto_usuario)
        for _ in range(MAX_ITERACIONES):
            resp = self.cliente.messages.create(
                model=self.modelo, max_tokens=16000, system=SISTEMA, tools=DEFINICIONES,
                thinking={"type": "adaptive"}, output_config={"effort": "high"},
                messages=self.mensajes,
            )
            self.mensajes.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason == "refusal":
                self._log("rechazo", detalle=str(getattr(resp, "stop_details", None)))
                return "El modelo rechazó esta solicitud por sus políticas de seguridad. Reformula la petición."
            if resp.stop_reason == "max_tokens":
                return "La respuesta se cortó por límite de longitud; pide un resumen más breve."
            llamadas = [b for b in resp.content if b.type == "tool_use"]
            if resp.stop_reason != "tool_use" or not llamadas:
                texto = "\n".join(b.text for b in resp.content if b.type == "text")
                self._log("agente", texto=texto)
                return texto
            resultados = []
            for b in llamadas:  # todos los tool_result en un solo mensaje
                salida = self.herramientas.ejecutar(b.name, dict(b.input))
                self._log("herramienta", nombre=b.name, entrada=dict(b.input), salida=salida)
                resultados.append({"type": "tool_result", "tool_use_id": b.id,
                                   "content": json.dumps(salida, ensure_ascii=False, default=str),
                                   **({"is_error": True} if "error" in salida else {})})
            self.mensajes.append({"role": "user", "content": resultados})
        return "Se alcanzó el máximo de pasos sin terminar. Revisa registro.jsonl y reformula la tarea."


def conversar(agente: Agente, primer_mensaje: str) -> None:
    """Bucle interactivo: el agente responde, el usuario continúa; vacío o 'salir' termina."""
    msg = primer_mensaje
    while msg and msg.strip().lower() not in ("salir", "exit"):
        print("\n" + agente.turno(msg))
        msg = input("\nTú (vacío para salir): ")
