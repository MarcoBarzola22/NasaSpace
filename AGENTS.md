# AGENTS.md — AgroDSS (Anthropics Boys · NASA Space Apps 2026)

> **REGLA 0 — AHORRO DE TOKENS (INNEGOCIABLE): PROHIBIDO leer, abrir, buscar (grep) o resumir la documentación extensa `docs/Documentacion.md` (alias «AgroDSS_Investigacion_y_fundamentos.md») durante tareas diarias de código. Guíate ÚNICAMENTE por este archivo y por `docs/constitution.md`. Solo puedes leerla si un humano lo ordena explícitamente en la tarea («lee la documentación extensa»). Si falta información, pregunta al humano; no la busques allí.**

## Proyecto
AgroDSS es un sistema de apoyo a decisiones para ingenieros agrónomos de San Luis (Argentina) que compara rotaciones de cultivos de secano en un horizonte de dos años. Calcula el balance hídrico diario del suelo con **FAO-56** y la respuesta del rendimiento al déficit hídrico con **FAO-33**, usando series climáticas diarias de **NASA POWER**, y estima ingresos/márgenes con precios ingresados manualmente.

**Arquitectura:** `frontend/` (React + Vite) consume la API de `backend/` (Python + FastAPI). Toda la lógica científica vive en el backend.

## Comandos
```bash
# Backend (desde backend/)
python -m venv .venv && .venv\Scripts\activate      # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload                       # API en http://localhost:8000
pytest                                              # tests
ruff check . && ruff format --check .               # linter / formato

# Frontend (desde frontend/)
npm install
npm run dev                                         # http://localhost:5173
npm run test                                        # Vitest
npm run lint                                        # ESLint
npm run build                                       # verifica que compila
```

## Estilo y convenciones
- **Código en inglés**: variables, funciones, clases, módulos, commits y comentarios técnicos.
- **Interfaz de usuario en español**: textos visibles, mensajes de error al usuario y reportes.
- Python: type hints, funciones puras para fórmulas, unidades en el nombre (`et0_mm`, `rain_mm`, `wind_ms`, `yield_t_ha`).
- React: componentes funcionales; la UI solo muestra y envía datos, nunca calcula agronomía.

## Reglas
1. **REGLA 0 (arriba) siempre prevalece: no leer la documentación extensa en tareas diarias.**
2. **Solo modelos aprobados:**
   - FAO-56: ET₀ Penman–Monteith; `ETc = Kc × ET₀` (Kc por cultivo y etapa); balance diario de zona radicular. Secano ⇒ riego = 0.
   - FAO-33: `1 − Ya/Ym = Ky × (1 − ETa/ETm)`.
   - Economía: `ingreso = rendimiento (t/ha) × precio manual`; `margen bruto = ingreso − costos directos`. Un margen bruto negativo no es «pérdida neta».
   - Suelo: solo proxy de días con cultivo vivo vs. días de viento fuerte (umbral documentado). Nada de toneladas de erosión, nitrógeno ni carbono.
   - PROHIBIDO sin aprobación humana: AquaCrop, APSIM, DSSAT, RUSLE/RWEQ, Monte Carlo, ML, nuevas fuentes satelitales (IMERG, SMAP, Landsat…) y fuentes solo de EE. UU. (NLDAS, PRISM, SSURGO, CDL, OpenET…).
3. **No rellenar datos faltantes:** nunca interpolar ni inventar valores. Marcar el dato como `assumption` (supuesto visible en la UI) o limitar/bloquear el resultado.
4. **No asumir calibración:** Kc, Ky, Ym y parámetros de suelo son entradas o supuestos declarados, no valores validados. No mostrar precisión, porcentajes de acierto ni probabilidades futuras; las salidas son escenarios históricos descriptivos.
5. **Procedencia de datos:** cada serie registra fuente, variable, unidad, fechas y faltantes. Un dato NASA POWER es modelo/reanálisis de celda, no medición del lote; etiquetarlo así.
6. **Separar lógica e interfaz:** fórmulas y validaciones en `backend/`; el frontend no replica cálculos.
7. **Alcance mínimo:** no añadir dependencias, servicios ni bases de datos sin aprobación.

## Al terminar cualquier tarea (obligatorio)
- [ ] `pytest` y `npm run test` pasan (o los del área tocada).
- [ ] `ruff check .` y `npm run lint` sin errores.
- [ ] `npm run build` compila y el backend arranca sin errores de import.
- [ ] Cálculos básicos verificados: conservación de masa del balance, unidades coherentes, `0 ≤ almacenamiento ≤ capacidad`, `ETa ≤ ETc` y agua disponible, `0 ≤ Ya ≤ Ym`, cronología diaria continua.
- [ ] Reportar al humano qué cambió, qué tests corrieron y cualquier supuesto nuevo.
