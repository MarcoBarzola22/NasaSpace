# Constitución de AgroDSS — principios innegociables

1. **Stack simple:** solo React+Vite (frontend) y Python+FastAPI (backend). Toda dependencia, servicio o base de datos nueva requiere aprobación humana registrada en el PR.
2. **Origen de Datos (Exclusividad NASA) y Fidelidad:** Es OBLIGATORIO extraer los datos climáticos y ambientales de las bases de datos de la NASA (ej. NASA POWER, SMAP, GPM) tal como exige el desafío. Los cálculos usarán solo FAO-56 y FAO-33 con estos datos. Prohibido inventar rendimientos, parámetros o probabilidades; si falta un dato, se marca como supuesto visible, nunca se rellena.
3. **Lógica separada de la interfaz:** todo cálculo agronómico o económico vive en `backend/`; el frontend solo muestra y envía datos (verificable: ninguna fórmula en `frontend/`).
4. **Tests obligatorios:** toda fórmula del balance hídrico, FAO-33 o margen tiene tests de conservación de masa, unidades y límites (`0 ≤ almacenamiento ≤ capacidad`, `ETa ≤ ETc`, `0 ≤ Ya ≤ Ym`). Sin tests verdes no hay merge.
5. Persistencia mínima: consulta en vivo a NASA POWER sin base de datos ni caché; la demo requiere conexión a internet.
6. **Política de tokens:** el agente se rige solo por esta constitución y `AGENTS.md`. Prohibido leer o reprocesar `docs/Documentacion.md` en tareas diarias; solo con orden humana explícita.