# Constitución de AgroDSS — principios innegociables

1. **Stack simple:** solo React+Vite (frontend) y Python+FastAPI (backend). Toda dependencia, servicio o base de datos nueva requiere aprobación humana registrada en el PR.
2. **Fidelidad a la investigación:** solo FAO-56 (agua) y FAO-33 (rendimiento) con datos diarios de NASA POWER. Prohibido inventar rendimientos, parámetros, porcentajes de acierto o probabilidades futuras; un dato faltante se marca como supuesto visible, nunca se rellena.
3. **Lógica separada de la interfaz:** todo cálculo agronómico o económico vive en `backend/`; el frontend solo muestra y envía datos (verificable: ninguna fórmula en `frontend/`).
4. **Tests obligatorios:** toda fórmula del balance hídrico, FAO-33 o margen tiene tests de conservación de masa, unidades y límites (`0 ≤ almacenamiento ≤ capacidad`, `ETa ≤ ETc`, `0 ≤ Ya ≤ Ym`). Sin tests verdes no hay merge.
5. **Persistencia mínima y offline:** series NASA POWER precargadas y versionadas en archivos (CSV/JSON) con su procedencia; la demo funciona sin conexión. Sin base de datos salvo aprobación.
6. **Política de tokens:** el agente se rige solo por esta constitución y `AGENTS.md`. Prohibido leer o reprocesar `docs/Documentacion.md` en tareas diarias; solo con orden humana explícita.
