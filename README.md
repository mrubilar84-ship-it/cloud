# Agente de cálculo estructural

Claude orquesta; el cálculo lo hace código determinista (OpenSeesPy). Entrada: DXF con convención de
capas (ver `estructural/modelos/dxf_lector.py`) + JSON de secciones. Salida: memoria de cálculo.

> Los resultados requieren revisión y firma de un ingeniero responsable. El motor calcula esfuerzos y
> deformaciones; **no verifica resistencia según norma**.

## Usar en Google Colab (sin instalar nada)
1. Abre `agente_colab.ipynb` en Colab (Archivo → Abrir cuaderno → GitHub → este repositorio, rama
   `claude/hola-d69076`).
2. En 🔑 *Secretos* agrega `ANTHROPIC_API_KEY` (y `GITHUB_TOKEN` si el repositorio es privado).
3. Ejecuta las celdas en orden. La memoria y los resultados quedan en tu Drive: `MyDrive/agente_estructural`.

## Usar en un computador
```
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # no la compartas ni la subas al repositorio
python agente.py ejemplos/edificio_2pisos.dxf ejemplos/secciones_demo.json
```

## Cómo funciona el agente
Herramientas: `leer_dxf`, `definir_combinaciones`, `calcular_estructura`, `generar_memoria`,
`buscar_norma`, `guardar_criterio`, `preguntar_usuario`. Pide **aprobación humana** antes de fijar
combinaciones, guardar criterios y emitir la memoria. Cada paso queda en `registro.jsonl`.
Lo que aprende se guarda como *no verificado* hasta que un ingeniero lo apruebe.

## Pruebas
`python -m pytest` (21 tests; el agente se prueba con un modelo simulado, sin gastar API).
