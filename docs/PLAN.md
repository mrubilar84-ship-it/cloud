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

## Fase 1c (hecha) — 3D, rótulas, apoyos y entrada DXF
- `estructural/calculo/estructura3d.py`: barras 3D, apoyos por grado de libertad, rótulas
  (liberación de `mx`/`my`/`mz` en extremos). Rótulas con resorte residual K_MIN=1e-3 kN·m/rad
  (error en momentos ~1e-5 kN·m; evita singularidad en nodos totalmente articulados).
- `estructural/modelos/dxf_lector.py`: convención de capas (`EL_<perfil>`, `APOYO_*`, `ROTULA`,
  `CARGA_NODAL`, `CARGA_DIST`). Un DWG se guarda como DXF desde el programa CAD.
- Uso: `python crear_dxf_demo.py` y luego
  `python calcular3d.py ejemplos/demo.dxf ejemplos/secciones_demo.json memoria.md`
- Validado contra soluciones analíticas (voladizo, empotrado-articulado, rótula intermedia).
- Pendiente: interfaz gráfica (visor web 3D), losas/placas, diafragmas, verificación por norma.

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
