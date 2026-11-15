import { ComparisonChart } from "../components/MetricsPanel.jsx";
import { formatMoney, metrics } from "../data/presentation.js";
import { DataTable, Field, Panel, Status } from "./Controls.jsx";
import { hasEconomicEntries, priceSources } from "./economics.js";
import { updateRecord } from "./session.js";

const crops = ["Maíz", "Soja", "Soja de primera", "Soja de segunda", "Trigo"];
const priceFields = [
  ["crop", "Cultivo", { options: crops }], ["amount", "Precio", { type: "number", min: 0, step: "any" }],
  ["currency", "Moneda", { options: ["ARS", "USD"] }], ["unit", "Unidad comercial"], ["source", "Fuente del precio"],
  ["sourceType", "Procedencia", { options: priceSources }], ["date", "Fecha de referencia", { type: "date" }],
];
const categories = ["Implantación", "Semillas", "Insumos", "Fertilización declarada", "Manejo", "Terminación de cobertura", "Cosecha", "Otros costos directos"];
const costFields = [
  ["strategy", "Estrategia", { options: ["A", "B", "C"] }], ["operation", "Cultivo u operación"], ["category", "Tipo de actividad", { options: categories }],
  ["crop", "Cultivo"], ["description", "Descripción"], ["amount", "Costo", { type: "number", min: 0, step: "any" }],
  ["currency", "Moneda", { options: ["ARS", "USD"] }], ["unit", "Unidad"], ["period", "Fecha o campaña"], ["source", "Fuente o supuesto"],
];

function EditableEntries({ caption, fields, rows, onChange }) {
  return <>
    <DataTable caption={caption} columns={[...fields.map(([, label]) => label), "Acción"]}
      rows={rows.map((row, index) => ({ id: row.id, cells: [
        ...fields.map(([key, label, props]) => <Field label={`${label} · Fila ${index + 1}`} value={row[key]} {...props}
          error={key === "amount" && Number(row.amount) < 0 ? "Ingresá un importe no negativo." : undefined}
          onChange={(value) => onChange(updateRecord(rows, row.id, key === "strategy" || key === "operation" ? { [key]: value, operationId: "" } : { [key]: value }))} />),
        <button type="button" className="work-button" aria-label={`Quitar fila ${index + 1}`}
          onClick={() => onChange(rows.filter(({ id }) => id !== row.id))}>Quitar</button>,
      ] }))} />
    <button type="button" className="work-button primary" onClick={() => onChange([...rows, { id: crypto.randomUUID() }])}>Agregar fila</button>
  </>;
}

export function EconomicComparison({ rotations, selectedId, onInspectResult }) {
  function value(id, label, amount) {
    const shown = formatMoney(amount);
    return onInspectResult ? <button type="button" className="work-button strategy-result" aria-label={label + " de " + id}
      onClick={() => onInspectResult(id, { result: { label, shown, unit: "ARS/ha" } })}>{shown}</button> : shown;
  }
  return (
    <DataTable caption="Economía ficticia · ARS/ha · Dos campañas" numericColumns={[1, 2, 3]} columns={["Estrategia", "Ingresos", "Costos directos", "Margen bruto"]}
      rows={rotations.map(({ id, label, income, cost, margin }) => ({ id, selected: id === selectedId,
        cells: [`${id} · ${label}`, value(id, "Ingresos", income), value(id, "Costos directos", cost), value(id, "Margen bruto", margin)] }))} />
  );
}

export default function EconomyWorkspace({ section, parcelRotations, selectedId, draft, patch, parcel, scenario, explorerOpen, onOpenExplorer, strategyBook, onInspectResult }) {
  const entriesChanged = hasEconomicEntries(draft);
  const pending = entriesChanged ? <Status tone="warning">Entradas modificadas. Resultados pendientes de cálculo.</Status> : null;
  if (section === "avanzada") return <Panel title="Exploración económica avanzada" description="Pendiente de integración. Capacidades previstas para cuando exista soporte del servicio de cálculo.">
    <ul className="work-list"><li>Comparación por hectárea y superficie total</li><li>Sensibilidad a precios y rendimientos</li><li>Punto de equilibrio</li><li>Flujo de caja</li></ul>
  </Panel>;
  if (section === "comparacion") return <>
        {pending}<Panel title="Comparación económica"
      description={`${scenario} · Dos años · Valores de demostración`}
      actions={<button id="economic-explorer-trigger" type="button" className="work-button primary"
        aria-expanded={explorerOpen} aria-controls={explorerOpen ? "economic-explorer" : undefined} onClick={onOpenExplorer}>
        Explorar precios y costos
      </button>}>
      <EconomicComparison rotations={parcelRotations} selectedId={selectedId} onInspectResult={onInspectResult} />
      <h3>Margen bruto de demostración</h3>
      <ComparisonChart metric={metrics[0]} rotations={parcelRotations} selectedId={selectedId} />
      <p className="work-note">La tabla y el gráfico muestran la referencia de demostración del horizonte completo. Las entradas editadas requieren cálculo en FastAPI.</p>
    </Panel>
    <Panel title="Desglose de costos declarados" description="Detalle de las filas ingresadas. Se conservan las monedas y unidades originales.">
      <DataTable caption="Actividades declaradas" numericColumns={[3]} columns={["Estrategia", "Actividad", "Categoría", "Costo", "Moneda", "Unidad", "Fecha o campaña"]}
        rows={draft.costs.map(({ id, strategy, operation, category, amount, currency, unit, period }) => ({
          id, cells: [strategyBook?.strategies.find(({ id }) => id === strategy)?.name || strategy, operation, category, amount, currency, unit, period],
        }))} />
    </Panel>
  </>;
  const isPrice = section === "precios";
  const key = isPrice ? "prices" : "costs";
  const fields = isPrice ? priceFields : costFields.map(([id, label, options]) => [id, label,
    id === "strategy" && strategyBook ? { options: strategyBook.strategies.map((strategy) => [strategy.id, strategy.name]) } : options]);
  return <Panel title={isPrice ? "Precios declarados" : "Costos de actividades"} description="Edición disponible en esta sesión. Los cambios se conservan por parcela.">
    {pending}
    <EditableEntries caption={isPrice ? "Precios de cultivos" : "Presupuesto de actividades"} fields={fields}
      rows={draft[key]} onChange={(rows) => patch({ [key]: rows })} />
  </Panel>;
}

