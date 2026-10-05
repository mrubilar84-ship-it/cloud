# Agente de cálculo estructural — plan por fases

Principio: **el cálculo lo hace código determinista y probado; la IA orquesta, explica y aprende.**
Todo resultado requiere revisión y firma de un ingeniero responsable.

## Fase 1 (hecha) — Núcleo
- `estructural/calculo/vigas.py`: viga simplemente apoyada (reacciones, M, V, flecha).
- `estructural/modelos/ifc_lector.py`: lee vigas, pilares, losas, muros del IFC.
- `estructural/conocimiento/memoria.py`: memoria de normas/criterios con flag `verificado`.

## Fase 1b (hecha) — Cálculo con OpenSeesPy
- `estructural/calculo/portico.py`: pórtico 2D elástico lineal, casos de carga y combinaciones.
- `estructural/informe/memoria_calculo.py`: memoria de cálculo en Markdown con verificación de equilibrio.
- Uso: `python calcular.py ejemplos/portico_simple.json memoria.md`
- OpenSeesPy corre directo en Python; **Kaggle no es necesario** (solo sería útil para cálculos muy pesados).
- Pendiente: 3D, verificación por norma (acero/hormigón), P-Δ, sismo, perfiles normalizados.

## Fase 2 — API y n8n
- API (FastAPI) que expone: subir IFC → listar elementos → calcular → informe.
- Flujo n8n: webhook/archivo → API → agente IA (explica) → informe.
- Desplegar API + PostgreSQL + n8n en Railway.

## Fase 3 — DWG
- DWG es propietario: convertir a DXF (ODA File Converter / LibreDWG) y leer con `ezdxf`.
- Un DWG de planos 2D no trae el modelo estructural: requiere reglas o revisión humana.

## Fase 4 — Más cálculo y normas
- Hormigón armado (ACI 318 / NCh430), acero (AISC / NCh427), cargas y sismo (NCh433).
- Cada fórmula de norma: función + tests con ejemplos resueltos de la propia norma.

## Aprendizaje de normas
- El agente guarda criterios en `Memoria` marcados como **no verificados**.
- Solo entradas `verificado=1` (revisadas por un ingeniero) se usan en cálculos.
- Las fórmulas nuevas nunca se aceptan sin implementación + test.
