
export function numberValue(value) {
  const text = String(value ?? "").trim();
  return /^-?(?:\d+(?:[.,]\d+)?|[.,]\d+)$/.test(text) ? Number(text.replace(",", ".")) : null;
}
export function rangeError(value, min, max, exclusiveMin = false, exclusiveMax = false) {
  const n = numberValue(value);
  if (n === null) return "Ingresá un valor numérico.";
  return (exclusiveMin ? n <= min : n < min) || (exclusiveMax ? n >= max : n > max)
    ? "Valor fuera del rango permitido." : undefined;
}
export const soilDefinitions = [
  ["fieldCapacity", "Capacidad de campo", "m³/m³", 0, 1, true],
  ["wiltingPoint", "Punto de marchitez permanente", "m³/m³", 0, 1, false, true],
  ["depth", "Profundidad efectiva", "m", 0, 3, true],
  ["availableWater", "Agua inicialmente disponible", "%", 0, 100],
  ["fallowKc", "Kc base del barbecho", "adimensional", 0, 1, true],
];
export function soilErrors(soil) {
  const errors = {};
  for (const [key, , unit, min, max, exclusiveMin, exclusiveMax] of soilDefinitions) {
    const row = soil[key] ?? {};
    if (key === "fallowKc" && !row.value) continue;
    errors[key] = rangeError(row.value, min, max, exclusiveMin, exclusiveMax);
    if (row.value && row.unit !== unit) errors[key] = "Unidad requerida " + unit + ". Conservá el original y revisá su unidad.";
  }
  const fc = numberValue(soil.fieldCapacity?.value);
  const wp = numberValue(soil.wiltingPoint?.value);
  if (fc !== null && wp !== null && wp >= fc) errors.wiltingPoint = "Debe ser menor que la capacidad de campo.";
  return Object.fromEntries(Object.entries(errors).filter(([, error]) => error));
}
export function recurringDate(day, month) {
  const d = Number(day), m = Number(month);
  return Number.isInteger(d) && Number.isInteger(m) && m >= 1 && m <= 12 && d >= 1 &&
    d <= [31,28,31,30,31,30,31,31,30,31,30,31][m - 1];
}
export function historicalWindows(config = {}, today = new Date().toISOString().slice(0,10)) {
  const errors = {};
  const years = config.start_years ?? [];
  if (!recurringDate(config.start_day, config.start_month)) errors.start_day = "Elegí día y mes válidos. El 29 de febrero no es un inicio recurrente.";
  if (!years.length || years.length > 10) errors.start_years = "Seleccioná entre 1 y 10 años.";
  if (new Set(years.map(Number)).size !== years.length) errors.start_years = "Los años no pueden repetirse.";
  const rows = years.map((year) => {
    if (!/^\d{4}$/.test(String(year)) || Number(year) < 1900 || Number(year) > 2200 || errors.start_day)
      return { year, error: "Fecha o año inválido." };
    const start = new Date(Date.UTC(Number(year), Number(config.start_month)-1, Number(config.start_day)));
    const finish = new Date(Date.UTC(Number(year)+2, Number(config.start_month)-1, Number(config.start_day)-1));
    const end = finish.toISOString().slice(0,10);
    return { year, start: start.toISOString().slice(0,10), end,
      error: end >= today ? "Ventana aún no finalizada." : undefined,
      warning: Number(year) < 1984 ? "Fuera de la cobertura común documentada desde 1984." : undefined };
  });
  return { errors, rows, valid: !Object.keys(errors).length && rows.every(({ error }) => !error) };
}
