import { useEffect, useRef } from "react";
import { DataTable, Field, FieldGrid } from "./Controls.jsx";
import { amountError, amountValue, costCategories, economicChanges, editPrice, priceRowsForCrop, priceSources, saleCrops } from "./economics.js";
import { stageName } from "./strategies/model.js";
import { updateRecord } from "./session.js";

const currencies = ["ARS", "USD"];
const amount = { inputMode: "decimal", autoComplete: "off" };
const costFields = [
  ["crop", "Cultivo"],
  ["category", "Actividad", { options: costCategories }],
  ["period", "Campaña o fecha"],
  ["amount", "Costo", amount],
  ["unit", "Unidad"],
  ["currency", "Moneda", { options: currencies }],
  ["source", "Fuente o supuesto"],
];

function PriceEditor({ rows, onChange, crops }) {
  return <>
    <h3>Precios de venta</h3>
    <p className="work-note">Precio por tonelada. Las referencias BCR y otras fuentes se declaran manualmente.</p>
    {crops.map((crop) => {
      const matches = priceRowsForCrop(rows, crop);
      return (matches.length ? matches : [null]).map((record, index) => {
        const price = record || {};
        const set = (field, value) => onChange(editPrice(rows, record, crop, { [field]: value }, record ? undefined : crypto.randomUUID()));
        const sourceType = price.sourceType || (priceSources.includes(price.source) ? price.source : price.source ? priceSources[2] : "");
        return <fieldset className="work-fieldset" key={`${crop}-${index}`}>
          <legend>{crop}{matches.length > 1 ? ` · Registro ${index + 1}` : ""}</legend>
          <FieldGrid fields={[
            ["amount", `Precio (${price.currency ? `${price.currency}/t` : "por tonelada"})`, amount],
            ["currency", "Moneda", { options: currencies }],
            ["sourceType", "Procedencia", { options: priceSources }],
            ["date", "Fecha de referencia", { type: "date" }],
            ["source", "Detalle o referencia de la fuente"],
          ]} values={{ ...price, sourceType }} onChange={set} errors={{
            amount: amountError(price.amount) || (price.amount && !price.currency ? "Elegí la moneda del precio." : undefined),
            date: sourceType === priceSources[1] && !price.date ? "Indicá la fecha de la referencia BCR." : undefined,
          }} />
        </fieldset>;
      });
    })}
    {rows.some((row) => !crops.some((crop) => priceRowsForCrop([row], crop).length)) &&
      <p className="work-note">En Precios podés consultar los registros con otra unidad o condición comercial.</p>}
  </>;
}

function ActivityCostEditor({ rows, onChange, strategies }) {
  return <>
    <h3>Presupuesto de actividades</h3>
    <p className="work-note">Declarar un costo registra una entrada económica. El calendario de cultivos conserva sus actividades.</p>
    {rows.length === 0 && <p className="work-empty">Todavía no hay costos por actividad declarados.</p>}
    {rows.map((row, index) => {
      const strategy = strategies.find(({ id }) => id === row.strategy);
      const operations = strategy?.stages.flatMap((stage) => stage.operations.map((operation) => ({
        ...operation, crop: stageName(stage),
      }))) ?? [];
      const linked = operations.find(({ id }) => id === row.operationId);
      function change(field, value) {
        const operation = operations.find(({ id }) => id === value);
        const patch = field === "strategy" ? { strategy: value, operationId: "" }
          : field === "operationId" ? { operationId: value, ...(operation ? { operation: operation.type, crop: operation.crop } : {}) }
            : { [field]: value };
        onChange(updateRecord(rows, row.id, patch));
      }
      const fields = [
        ["strategy", "Estrategia", { options: strategies.map(({ id, name }) => [id, name]) }],
        ...(strategy && !strategy.isTemplate ? [["operationId", "Operación vinculada", {
          options: operations.map(({ id, type, date, crop }) => [id, `${type} · ${crop} · ${date}`]),
        }]] : [["operation", "Operación declarada"]]),
        ...costFields,
      ];
      return (
      <fieldset className="work-fieldset" key={row.id}>
        <legend>{row.category || row.operation || `Costo ${index + 1}`}</legend>
        <FieldGrid fields={fields.map(([key, label, props]) => [
          key, label, key === "category" && row.category && !costCategories.includes(row.category)
            ? { options: [...costCategories, row.category] } : key === "crop" && linked ? { readOnly: true } : props,
        ])} values={{ ...row, crop: linked?.crop ?? row.crop, operationId: linked?.id || "" }} onChange={change}
          errors={{ amount: amountError(row.amount), currency: row.amount && !row.currency ? "Indicá la moneda." : undefined,
            unit: row.amount && !row.unit ? "Indicá la unidad del costo." : undefined,
            operationId: strategy && !strategy.isTemplate && !linked ? "Vinculá una operación registrada en la estrategia." : undefined }} />
        {row.operationId && !linked && <p className="field-error">El vínculo anterior ya no está disponible. Elegí una operación vigente.</p>}
        <button type="button" className="work-button" onClick={() => onChange(rows.filter(({ id }) => row.id !== id))}>Quitar costo</button>
      </fieldset>
    ); })}
    <button type="button" className="work-button" onClick={() => onChange([...rows, { id: crypto.randomUUID() }])}>Declarar costo</button>
  </>;
}

function ImpactSummary({ changes }) {
  const formatter = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 12, signDisplay: "exceptZero" });
  return <>
    <h3>Impacto de los cambios</h3>
    <p className="work-note">La diferencia compara entradas de la misma moneda y unidad. El impacto en los resultados requiere cálculo en FastAPI.</p>
    <DataTable caption="Variación de las entradas" columns={["Entrada", "Original", "Modificado", "Diferencia"]}
      rows={changes.map(({ id, kind, label, original, edited, delta, metadataChanged }) => ({
        id: `${kind}-${id}`, cells: [<>{label}{metadataChanged && <small className="work-note"> · Datos de la entrada modificados</small>}</>,
          original, edited, delta === null ? "No comparable" : formatter.format(delta)],
      }))} empty="Todavía no hay modificaciones respecto de los valores originales." />
  </>;
}

export default function EconomicExplorer({ parcel, scenario, selected, strategies, draft, baseline, patch, onClose }) {
  const closeButton = useRef(null);
  const changes = economicChanges(baseline, draft);
  const active = strategies.find(({ id }) => id === selected?.id);
  const commercialCrops = [...new Set((active?.stages ?? []).filter(({ kind }) => kind === "commercial").map((stage) =>
    stage.cropId?.startsWith("soy") ? "Soja" : stageName(stage)))];
  const priceCrops = [...new Set([...saleCrops, ...commercialCrops.filter((name) => name !== "Cultivo sin identificar")])];
  const missingPrices = commercialCrops.filter((crop) =>
    !priceRowsForCrop(draft.prices, crop).some(({ amount, currency }) => currency && amountValue(amount) !== null));
  const missingOperations = (active?.stages ?? []).flatMap(({ operations }) => operations)
    .filter(({ id }) => !draft.costs.some((cost) => cost.strategy === active.id && cost.operationId === id &&
      cost.currency && cost.unit && amountValue(cost.amount) !== null));

  useEffect(() => {
    closeButton.current.focus();
  }, []);

  useEffect(() => {
    function onKey(event) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <aside id="economic-explorer" className="economic-drawer" aria-labelledby="economic-explorer-title">
      <header className="economic-drawer-heading">
        <div><h2 id="economic-explorer-title">Explorar precios y costos</h2>
          <p>{parcel.name} · {scenario} · Dos campañas · {selected?.name || "Sin estrategia seleccionada"}</p></div>
        <button ref={closeButton} className="work-button" type="button" onClick={onClose}>Cerrar</button>
      </header>
      <p className="work-status warning" role="status">Resultados pendientes de cálculo · Integración con FastAPI pendiente.</p>
      {missingPrices.length > 0 && <p className="work-note">Precios pendientes de la estrategia activa: {missingPrices.join(", ")}.</p>}
      {missingOperations.length > 0 && <p className="work-note">Operaciones sin costo declarado: {missingOperations.map(({ type, date }) => `${type} (${date})`).join(", ")}.</p>}
      <PriceEditor crops={priceCrops} rows={draft.prices} onChange={(prices) => patch({ prices })} />
      <ActivityCostEditor strategies={strategies} rows={draft.costs} onChange={(costs) => patch({ costs })} />
      <ImpactSummary changes={changes} />
      <p className="work-note">Restablecer recupera los precios y costos que tenía esta parcela al abrir el explorador por primera vez en esta sesión.</p>
      <button type="button" className="work-button" disabled={!changes.length}
        onClick={() => patch({ prices: baseline.prices, costs: baseline.costs })}>Restablecer valores</button>
    </aside>
  );
}

