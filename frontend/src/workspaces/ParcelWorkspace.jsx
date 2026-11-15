import ParcelMap from "../components/ParcelMap.jsx";
import { FieldGrid, Panel, Status } from "./Controls.jsx";
import LabStudies from "./LabStudies.jsx";
import LocalFiles from "./LocalFiles.jsx";
import { updateRecord, validateIdentity } from "./session.js";

const identityFields = [
  ["name", "Nombre declarado"], ["identifier", "Identificador declarado"], ["province", "Provincia"], ["locality", "Localidad o referencia"],
  ["latitude", "Latitud (°; opcional)", { type: "number", step: "any" }], ["longitude", "Longitud (°; opcional)", { type: "number", step: "any" }],
  ["area", "Superficie (ha)", { type: "number", step: "any" }], ["production", "Tipo de producción", { options: ["Secano", "Con riego"] }],
  ["firstYear", "Año inicial", { inputMode: "numeric", maxLength: 4 }], ["lastYear", "Año final", { inputMode: "numeric", maxLength: 4 }],
  ["notes", "Observaciones generales (opcional)", { multiline: true }],
];

const soilProperties = [
  ["texture", "Textura"], ["depth", "Profundidad efectiva"], ["capacity", "Capacidad de almacenamiento hídrico"],
  ["moisture", "Humedad inicial"], ["rootDepth", "Profundidad radicular"], ["fieldCapacity", "Capacidad de campo"],
  ["wiltingPoint", "Punto de marchitez permanente"],
];

const soilFields = [
  ["value", "Valor"], ["unit", "Unidad"], ["source", "Fuente"], ["date", "Fecha (opcional)", { type: "date" }],
  ["basis", "Condición", { options: ["Medición", "Dato declarado", "Supuesto"] }],
];

const historyFields = [
  ["crop", "Cultivo previo"], ["season", "Campaña"], ["yield", "Rendimiento observado"], ["unit", "Unidad original"],
  ["fallow", "Barbechos"], ["residue", "Rastrojos"], ["management", "Manejo relevante"], ["notes", "Observaciones", { multiline: true }],
];

export default function ParcelWorkspace({ section, parcels, parcel, onSelectParcel, draft, patch }) {
  if (section === "mapa") return (
    <Panel title="Mapa de parcelas" description="Imagen aérea ilustrativa. Los contornos permiten identificar las parcelas ficticias.">
      <ParcelMap parcels={parcels} activeParcelId={parcel.id} onSelect={onSelectParcel} />
    </Panel>
  );
  if (section === "laboratorio") return <LabStudies key={parcel.id} studies={draft.studies} onChange={(studies) => patch({ studies })} />;
  if (section === "suelo") return (
    <Panel title="Propiedades físicas" description="Registrá valores con su unidad y procedencia. Los campos vacíos se consideran sin dato.">
      {soilProperties.map(([key, label]) => (
        <fieldset className="work-fieldset" key={key}><legend>{label}</legend>
          <FieldGrid fields={soilFields} values={draft.soil[key] || {}} onChange={(field, value) => patch({
            soil: { ...draft.soil, [key]: { ...draft.soil[key], [field]: value } },
          })} />
        </fieldset>
      ))}
    </Panel>
  );
  if (section === "antecedentes") return (
    <Panel title="Antecedentes declarados" description="Información de referencia del lote. Las entradas se conservan mientras dure la sesión."
      actions={<button type="button" className="work-button primary" onClick={() => patch({ history: [...draft.history, { id: crypto.randomUUID() }] })}>Agregar antecedente</button>}>
      {draft.history.length === 0 && <p className="work-empty">Sin antecedentes declarados.</p>}
      {draft.history.map((record, index) => <fieldset className="work-fieldset" key={record.id}><legend>{record.crop || `Antecedente ${index + 1}`}</legend>
        <FieldGrid fields={historyFields} values={record} onChange={(key, value) => patch({ history: updateRecord(draft.history, record.id, { [key]: value }) })} />
        <button type="button" className="work-button" onClick={() => patch({ history: draft.history.filter(({ id }) => id !== record.id) })}>Quitar antecedente</button>
      </fieldset>)}
      <LocalFiles key={parcel.id} files={draft.historyFiles} onChange={(historyFiles) => patch({ historyFiles })} label="Seleccionar referencias del lote" />
    </Panel>
  );
  return (
    <Panel title="Identificación del lote" description="Datos declarados para la parcela activa. Podés dejar campos sin informar mientras preparás el análisis.">
      <FieldGrid fields={identityFields} values={draft.identity} errors={validateIdentity(draft.identity)}
        onChange={(key, value) => patch({ identity: { ...draft.identity, [key]: value } })} />
      {draft.identity.production === "Con riego" && <Status tone="warning">El MVP solo representa sistemas de secano. Los escenarios de esta demo no incluyen riego.</Status>}
      <p className="work-note">Los campos válidos se reflejan en la ficha y el informe. Las cifras de demostración quedan como referencia independiente.</p>
    </Panel>
  );
}

