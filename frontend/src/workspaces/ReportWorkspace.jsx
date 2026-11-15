import { horizonMonths } from "../data/demo.js";
import { DataTable, Field, Panel, Status } from "./Controls.jsx";
import { EconomicComparison } from "./EconomyWorkspace.jsx";
import { getWarnings } from "./InterpretationWorkspace.jsx";
import { exportDraft, validIdentity } from "./session.js";

export function ReportContent({ parcel, draft, parcelRotations, selected, scenario, periodLabel, strategies }) {
  const identity = validIdentity(draft.identity);
  return <article className="report-content">
    <header><p className="eyebrow">AgroDSS · Informe de análisis</p><h2>{parcel.name} · {parcel.displayId}</h2>
      <p>Horizonte de dos campañas · {scenario}</p></header>
    <Status>Datos ficticios de demostración. Los resultados no se calcularon con las entradas declaradas.</Status>
    <dl className="work-readout">
      <div><dt>Período de consulta</dt><dd>{periodLabel} · Los agregados corresponden al horizonte completo.</dd></div>
      <div><dt>Localidad declarada</dt><dd>{[identity.locality, identity.province].filter(Boolean).join(" · ") || "Sin dato"}</dd></div>
      <div><dt>Superficie declarada</dt><dd>{identity.area ? `${identity.area} ha` : "Sin informar"}</dd></div>
      <div><dt>Sistema declarado</dt><dd>{identity.production || "Sin dato"}</dd></div>
      <div><dt>Años declarados</dt><dd>{identity.firstYear || "Inicio sin informar"} · {identity.lastYear || "Fin sin informar"}</dd></div>
      <div><dt>Estrategia seleccionada</dt><dd>{selected.name} · {selected.sequence}</dd></div>
    </dl>
    <DataTable caption="Estrategias del expediente" columns={["Estrategia", "Secuencia"]}
      rows={strategies.map(({ id, name, sequence }) => ({ id, cells: [name, sequence], selected: id === selected.id }))} />
    <h3>Referencia económica de las plantillas</h3>
    <EconomicComparison rotations={parcelRotations} selectedId={selected.id} />
    <DataTable caption={`Agua y cobertura · Resumen ficticio de ${horizonMonths} meses`}
      columns={["Estrategia", "Déficit (mm)", "Meses con cultivo vivo"]} numericColumns={[1, 2]}
      rows={parcelRotations.map(({ id, deficit, cover }) => ({ id, cells: [id, deficit, cover], selected: id === selected.id }))} />
    <h3>Supuestos y advertencias</h3>
    <ul className="work-list">{getWarnings(draft).map(([type, message], index) => (
      <li key={index}><strong>{type}.</strong> {message}</li>
    ))}</ul>
    <h3>Observaciones profesionales</h3><p className="report-notes">{draft.notes || "Sin observaciones declaradas."}</p>
  </article>;
}

function downloadReport({ parcel, draft, parcelRotations, selected, scenario, periodLabel, referenceParcel }) {
  const payload = {
    context: { parcelId: parcel.id, strategyId: selected.id, scenario, period: periodLabel },
    declared: exportDraft(draft),
    demonstration: { parcel: { id: parcel.id, name: referenceParcel.name, area: referenceParcel.area, texture: referenceParcel.texture },
      unit: "ARS/ha", horizon: "Dos campañas", comparisons: parcelRotations.map(({ id, income, cost, margin, deficit, cover }) =>
        ({ id, income, cost, margin, deficitMm: deficit, coverMonths: cover })) },
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `agrodss-${parcel.id}-sesion.json`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function ReportWorkspace({ section, patch, ...report }) {
  if (section === "gestion") return <Panel title="Gestión del análisis" description="Los datos se conservan en la sesión abierta. Exportá una copia antes de cerrar o recargar.">
    <Field label="Observaciones profesionales" multiline value={report.draft.notes} onChange={(notes) => patch({ notes })} />
    <p className="work-note">El JSON incluye entradas, resultados de demostración y metadatos de adjuntos. Los archivos originales se conservan por separado.</p>
    <button type="button" className="work-button primary" onClick={() => downloadReport(report)}>Exportar datos de sesión (JSON)</button>
  </Panel>;
  return <>
    {section === "impresion" && <Panel title="Impresión" description="El navegador prepara el informe con sus unidades, supuestos y advertencias.">
      <button type="button" className="work-button primary" onClick={() => window.print()}>Imprimir informe</button>
    </Panel>}
    <Panel title={section === "impresion" ? "Vista previa" : "Vista general"}><ReportContent {...report} /></Panel>
  </>;
}

