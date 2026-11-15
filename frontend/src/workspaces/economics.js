import { updateRecord } from "./session.js";
import { crops, stageName } from "./strategies/model.js";

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
  const unit = Object.hasOwn(patch, "currency") ? "t" : record?.unit || "t";
  const next = { ...record, ...patch, crop, unit };
  return record ? updateRecord(rows, record.id, next) : [...rows, { ...next, id }];
}

export function hasEconomicEntries({ prices, costs }) {
  return [...prices, ...costs].some(({ id: _id, ...fields }) => Object.values(fields).some(Boolean));
}

export function economicEntryErrors(row) {
  const [prefix, denominator] = (row.unit ?? "").trim().split("/");
  const unitCurrency = denominator && /^[A-Z]{3}$/i.test(prefix) ? prefix.toUpperCase() : undefined;
  return {
    amount: amountValue(row.amount) === null ? amountError(row.amount) || "Indicá el importe." : undefined,
    currency: !["ARS", "USD"].includes(row.currency) ? "Indicá una moneda válida." : undefined,
    unit: !row.unit?.trim() ? "Indicá la unidad de la entrada."
      : unitCurrency && row.currency && unitCurrency !== row.currency ? "La moneda de la unidad no coincide con la moneda declarada." : undefined,
    date: row.sourceType === priceSources[1] && !row.date ? "Indicá la fecha de la referencia BCR." : undefined,
  };
}

export function economicEntryIssue(row) {
  return Object.values(economicEntryErrors(row)).find(Boolean);
}

export function economicResultNotice(draft) {
  return hasEconomicEntries(draft) ? "Entradas modificadas. Resultados pendientes de cálculo." : "";
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
      const delta = sameUnit && !economicEntryIssue(from) && !economicEntryIssue(to) && originalAmount !== null && editedAmount !== null ? editedAmount - originalAmount : null;
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


// --- Normalised economic inputs for the contract 1.0 (no result is calculated here) ---

const soyGeneric = "Soja";
const normal = (text) => String(text ?? "").trim().toLowerCase();

function stageLabels(stage) {
  const label = crops.find(([id]) => id === stage.cropId)?.[1];
  const generic = stage.cropId?.startsWith("soy") ? soyGeneric : stage.cropId === "rye" ? "Centeno" : undefined;
  return [...new Set([label, stageName(stage), generic].filter(Boolean))];
}

/** Single declared price per tonne of the crop of a stage; `null` when missing or ambiguous. */
function stagePrice(prices, stage) {
  for (const label of stageLabels(stage)) {
    const rows = priceRowsForCrop(prices, label).filter((row) => !economicEntryIssue(row));
    const options = new Set(rows.map((row) => `${amountValue(row.amount)} ${row.currency}`));
    if (options.size === 1) return { amount: amountValue(rows[0].amount), currency: rows[0].currency };
    if (options.size > 1) return null;
  }
  return null;
}

/**
 * Declared prices and direct costs per crop stage, with one common currency.
 * `costPerHa` adds the valid cost rows (per hectare) assigned to the stage, either through a
 * linked operation or through the declared crop. A missing value stays `null`: the backend then
 * reports the margin as not computed. Mixed currencies leave every value in `null`.
 */
export function economicSummary(draft, strategies) {
  const stages = {};
  const currencies = new Set();
  const unassignedCostIds = [];
  for (const strategy of strategies) {
    const cropStages = strategy.stages.filter(({ kind }) => kind === "commercial" || kind === "cover");
    const costs = Object.fromEntries(cropStages.map(({ id }) => [id, null]));
    for (const row of draft.costs.filter((cost) => cost.strategy === strategy.id)) {
      const amount = amountValue(row.amount);
      const targets = cropStages.filter((stage) => stage.operations.some(({ id }) => id === row.operationId));
      const byCrop = targets.length ? targets : cropStages.filter((stage) => stageLabels(stage).some((label) => normal(label) === normal(row.crop)));
      if (economicEntryIssue(row) || amount === null || comparableUnit(row) !== "ha" || byCrop.length !== 1) {
        unassignedCostIds.push(row.id);
        continue;
      }
      costs[byCrop[0].id] = (costs[byCrop[0].id] ?? 0) + amount;
      currencies.add(row.currency);
    }
    stages[strategy.id] = Object.fromEntries(cropStages.map((stage) => {
      const price = stage.kind === "commercial" ? stagePrice(draft.prices, stage) : null;
      if (price) currencies.add(price.currency);
      return [stage.id, { pricePerT: price?.amount ?? null, costPerHa: costs[stage.id] }];
    }));
  }
  const incompatible = currencies.size > 1;
  if (incompatible) for (const entries of Object.values(stages)) for (const entry of Object.values(entries)) Object.assign(entry, { pricePerT: null, costPerHa: null });
  return { currency: currencies.size === 1 ? [...currencies][0] : null, currencies: [...currencies].sort(), incompatible, stages, unassignedCostIds };
}
