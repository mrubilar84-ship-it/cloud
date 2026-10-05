"""Análisis de vigas simplemente apoyadas (determinista, unidades SI: N, m, Pa)."""
from dataclasses import dataclass


@dataclass
class ResultadoViga:
    reaccion_a: float  # N
    reaccion_b: float  # N
    momento_max: float  # N·m
    corte_max: float  # N
    flecha_max: float  # m


def viga_simple(
    largo: float,
    carga_distribuida: float,
    E: float,
    I: float,
    carga_puntual: float = 0.0,
) -> ResultadoViga:
    """Viga simplemente apoyada con carga distribuida w (N/m) y una puntual P (N) al centro."""
    if largo <= 0 or E <= 0 or I <= 0:
        raise ValueError("largo, E e I deben ser positivos")
    w, P, L = carga_distribuida, carga_puntual, largo
    reaccion = w * L / 2 + P / 2
    momento = w * L**2 / 8 + P * L / 4
    flecha = 5 * w * L**4 / (384 * E * I) + P * L**3 / (48 * E * I)
    return ResultadoViga(reaccion, reaccion, momento, reaccion, flecha)
