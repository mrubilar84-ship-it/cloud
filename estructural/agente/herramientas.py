"""Herramientas que el agente puede llamar. Todo cálculo lo hace código determinista."""
import json
import os
from pathlib import Path

from estructural.calculo.estructura3d import analizar
from estructural.conocimiento.memoria import Memoria
from estructural.informe.memoria_calculo_3d import generar
from estructural.modelos.dxf_lector import leer_dxf

DEFINICIONES = [
    {
        "name": "leer_dxf",
        "description": "Lee un DXF (capas EL_<perfil>, APOYO_*, ROTULA, CARGA_NODAL, CARGA_DIST) y un JSON de "
        "secciones/materiales, y construye el modelo. Devuelve un resumen o el error de validación.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ruta_dxf": {"type": "string"},
                "ruta_secciones": {"type": "string", "description": "JSON con 'materiales' y 'secciones'"},
            },
            "required": ["ruta_dxf", "ruta_secciones"],
        },
    },
    {
        "name": "definir_combinaciones",
        "description": "Define las combinaciones de carga del modelo cargado (supuesto de diseño: requiere "
        "aprobación del usuario). Formato: {nombre: {caso: factor}}.",
        "input_schema": {
            "type": "object",
            "properties": {
                "combinaciones": {
                    "type": "object",
                    "additionalProperties": {"type": "object", "additionalProperties": {"type": "number"}},
                },
                "justificacion": {"type": "string", "description": "Por qué esos factores y qué norma los respalda"},
            },
            "required": ["combinaciones", "justificacion"],
        },
    },
    {
        "name": "calcular_estructura",
        "description": "Ejecuta el análisis elástico lineal 3D (OpenSees) del modelo cargado y devuelve un "
        "resumen por combinación: equilibrio global, desplazamiento máximo, reacciones y esfuerzos máximos.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "generar_memoria",
        "description": "Escribe la memoria de cálculo (Markdown) con los últimos resultados. Requiere aprobación "
        "del usuario. Solo se guarda en la carpeta de salidas.",
        "input_schema": {
            "type": "object",
            "properties": {"nombre_archivo": {"type": "string"}, "proyecto": {"type": "string"}},
            "required": ["nombre_archivo", "proyecto"],
        },
    },
    {
        "name": "buscar_norma",
        "description": "Busca en la memoria de normas y criterios. Por defecto solo entradas verificadas por un ingeniero.",
        "input_schema": {
            "type": "object",
            "properties": {"texto": {"type": "string"}, "incluir_no_verificado": {"type": "boolean"}},
            "required": ["texto"],
        },
    },
    {
        "name": "guardar_criterio",
        "description": "Guarda un criterio o dato de norma en la memoria, siempre como NO verificado. Requiere "
        "aprobación del usuario.",
        "input_schema": {
            "type": "object",
            "properties": {
                "norma": {"type": "string"}, "tema": {"type": "string"},
                "contenido": {"type": "string"}, "fuente": {"type": "string"},
            },
            "required": ["norma", "tema", "contenido", "fuente"],
        },
    },
    {
        "name": "preguntar_usuario",
        "description": "Hace una pregunta al usuario y devuelve su respuesta. Úsala cuando falten datos; no supongas.",
        "input_schema": {
            "type": "object",
            "properties": {"pregunta": {"type": "string"}},
            "required": ["pregunta"],
        },
    },
]


class Herramientas:
    def __init__(self, carpeta: str, preguntar, aprobar):
        """preguntar(texto)->str ; aprobar(texto)->bool (inyectables para tests y Colab)."""
        self.carpeta = Path(carpeta)
        (self.carpeta / "salidas").mkdir(parents=True, exist_ok=True)
        self.memoria = Memoria(str(self.carpeta / "memoria.db"))
        self.preguntar, self.aprobar = preguntar, aprobar
        self.modelo = None
        self.resultados = None

    def ejecutar(self, nombre: str, args: dict) -> dict:
        """Devuelve siempre un dict serializable; los errores vuelven como {'error': ...}."""
        try:
            return getattr(self, f"_{nombre}")(**args)
        except (ValueError, KeyError, FileNotFoundError, RuntimeError, TypeError) as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def _leer_dxf(self, ruta_dxf, ruta_secciones):
        sec = json.load(open(ruta_secciones))
        self.modelo = leer_dxf(ruta_dxf, sec["secciones"], sec["materiales"])
        self.resultados = None
        m = self.modelo
        return {
            "nodos": len(m["nodos"]), "barras": len(m["elementos"]),
            "secciones_usadas": sorted({e["seccion"] for e in m["elementos"]}),
            "apoyos": {n: a for n, a in m["apoyos"].items()},
            "barras_con_rotula": [e["id"] for e in m["elementos"] if "liberar_i" in e or "liberar_j" in e],
            "casos_de_carga": {
                c: {"cargas_nodales": len(v["nodales"]), "cargas_distribuidas": len(v["distribuidas"])}
                for c, v in m["casos"].items()
            },
            "combinaciones_definidas": m.get("combinaciones", {}),
        }

    def _definir_combinaciones(self, combinaciones, justificacion):
        self._requiere_modelo()
        for nombre, factores in combinaciones.items():
            for caso in factores:
                if caso not in self.modelo["casos"]:
                    raise ValueError(f"Combinación '{nombre}': el caso '{caso}' no existe "
                                     f"(casos: {list(self.modelo['casos'])})")
        if not self.aprobar(f"Combinaciones propuestas: {json.dumps(combinaciones)}\nJustificación: {justificacion}"):
            return {"aprobado": False, "mensaje": "El usuario NO aprobó estas combinaciones."}
        self.modelo["combinaciones"] = combinaciones
        self.resultados = None
        return {"aprobado": True}

    def _calcular_estructura(self):
        self._requiere_modelo()
        self.resultados = analizar(self.modelo)
        out = {}
        for nombre, r in self.resultados.items():
            desp = {n: max(abs(v) for v in d[:3]) for n, d in r["desplazamientos"].items()}
            nodo_max = max(desp, key=desp.get)
            esf = {
                eid: max(max(abs(v) for v in d[k]) for k in ("My", "Mz"))
                for eid, d in r["diagramas"].items()
            }
            top = sorted(esf, key=esf.get, reverse=True)[:5]
            out[nombre] = {
                "equilibrio_ok": all(abs(e) < 1e-4 for e in r["equilibrio"]["error"]),
                "error_equilibrio_kN": [float(f"{e:.2e}") for e in r["equilibrio"]["error"]],
                "desplazamiento_max_mm": {"nodo": nodo_max, "valor": round(1000 * desp[nodo_max], 3)},
                "reacciones_kN": {n: [round(v, 2) for v in d[:3]] for n, d in r["reacciones"].items()},
                "momento_max_por_barra_kNm": {str(e): round(esf[e], 2) for e in top},
            }
        return out

    def _generar_memoria(self, nombre_archivo, proyecto):
        if self.resultados is None:
            raise ValueError("No hay resultados: ejecuta calcular_estructura primero")
        destino = self.carpeta / "salidas" / (os.path.basename(nombre_archivo) or "memoria.md")
        if not self.aprobar(f"¿Emitir la memoria de cálculo '{destino.name}' para el proyecto '{proyecto}'?"):
            return {"aprobado": False, "mensaje": "El usuario NO aprobó emitir la memoria."}
        destino.write_text(generar(self.modelo, self.resultados, proyecto), encoding="utf-8")
        return {"aprobado": True, "archivo": str(destino)}

    def _buscar_norma(self, texto, incluir_no_verificado=False):
        filas = self.memoria.buscar(texto, solo_verificado=not incluir_no_verificado)
        return {"resultados": filas, "nota": "verificado=0 significa NO revisado por un ingeniero"}

    def _guardar_criterio(self, norma, tema, contenido, fuente):
        if not self.aprobar(f"¿Guardar en la memoria (como NO verificado)?\n[{norma}] {tema}: {contenido}\nFuente: {fuente}"):
            return {"aprobado": False}
        return {"aprobado": True, "id": self.memoria.guardar(norma, tema, contenido, fuente), "verificado": False}

    def _preguntar_usuario(self, pregunta):
        return {"respuesta": self.preguntar(pregunta)}

    def _requiere_modelo(self):
        if self.modelo is None:
            raise ValueError("No hay modelo cargado: ejecuta leer_dxf primero")
