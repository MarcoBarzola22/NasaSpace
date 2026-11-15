import { updateRecord } from "./session.js";

export const saleCrops = ["Maíz", "Soja", "Trigo"];
export const priceSources = ["Ingresado por el usuario", "Referencia BCR declarada", "Otra fuente declarada"];
export const costCategories = ["Semillas", "Implantación", "Fertilizantes e insumos", "Aplicaciones y manejo",
  "Terminación del centeno", "Cosecha", "Otros costos directos"];

export function amountValue(value) {
  const amount = String(value ?? "").trim();
  if (!/^(?:\d+(?:[.,]\d+)?|[.,]\d+)$/.test(amount)) return null;
  const number = Number(amount.replace(",", "."));
  return Number.isFinite(number) ? number : null;
}

export function amountError(value) {
  return value && amountValue(value) === null ? "Ingresá un importe no negativo, sin separador de miles." : undefined;
}

export function priceRowsForCrop(rows, crop) {
  return rows.filter((row) => row.crop === crop && (!row.unit || /^(?:[A-Z]{3}\/)?t$/i.test(row.unit.trim())));
}

export function editPrice(rows, record, crop, patch, id) {
  const next = { ...record, ...patch, crop, unit: "t" };
  return record ? updateRecord(rows, record.id, next) : [...rows, { ...next, id }];
}

export function hasEconomicEntries({ prices, costs }) {
  return [...prices, ...costs].some(({ id: _id, ...fields }) => Object.values(fields).some(Boolean));
}

function comparableUnit(row) {
  const unit = row.unit?.trim().toLowerCase();
  const prefix = row.currency ? row.currency.toLowerCase() + "/" : "";
  return prefix && unit?.startsWith(prefix) ? unit.slice(prefix.length) : unit;
}

export function describeAmount(row) {
  if (!row || row.amount === "" || row.amount === undefined) return "Sin dato";
  const unit = comparableUnit(row);
  return [row.amount, [row.currency, unit].filter(Boolean).join("/")].filter(Boolean).join(" ");
}

export function economicChanges(original, current) {
  return ["prices", "costs"].flatMap((kind) => {
    const before = new Map(original[kind].map((row) => [row.id, row]));
    const after = new Map(current[kind].map((row) => [row.id, row]));
    return [...new Set([...before.keys(), ...after.keys()])].flatMap((id) => {
      const from = before.get(id);
      const to = after.get(id);
      const fields = [...new Set([...Object.keys(from ?? {}), ...Object.keys(to ?? {})])];
      if (!fields.some((field) => field !== "id" && (from?.[field] || "") !== (to?.[field] || ""))) return [];

      const originalAmount = amountValue(from?.amount);
      const editedAmount = amountValue(to?.amount);
      const sameUnit = from?.currency && from.currency === to?.currency && comparableUnit(from) && comparableUnit(from) === comparableUnit(to);
      const delta = sameUnit && originalAmount !== null && editedAmount !== null ? editedAmount - originalAmount : null;
      const row = to || from;
      return [{ id, kind, label: kind === "prices" ? row.crop || "Precio sin cultivo"
        : [row.strategy, row.category || row.description || row.operation || "Actividad sin identificar"].filter(Boolean).join(" · "),
        original: describeAmount(from), edited: describeAmount(to), delta,
        metadataChanged: fields.some((field) => field !== "id" && field !== "amount" && (from?.[field] || "") !== (to?.[field] || "")) }];
    });
  });
}

export function marginAxis(values) {
  const minimum = Math.min(0, ...values);
  const maximum = Math.max(0, ...values);
  const range = maximum - minimum || 1;
  const zero = (-minimum / range) * 100 || 0;
  return { minimum, maximum, zero, position: (value) => ((value - minimum) / range) * 100 };
}

