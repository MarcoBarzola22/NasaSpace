import AgronomicInputs, { DeclaredParameter } from "./AgronomicInputs.jsx";
import { rangeError } from "../preparation.js";
import { useState } from "react";
import { FieldGrid, Panel, Status } from "../Controls.jsx";
import { updateRecord } from "../session.js";
import { blankStage, blankStrategy, calculationLabel, cropOptions, operationTypes, orderStages,
  reviewLabel, saveStrategy, stageKinds, stageName, strategyHorizon, validateStrategy } from "./model.js";

const date = { type: "date" };
const year = { inputMode: "numeric", maxLength: 4 };
const identification = [
  ["name", "Nombre de la estrategia"], ["description", "Descripción (opcional)", { multiline: true }],
  ["firstCampaign", "Campaña inicial", year], ["lastCampaign", "Campaña final", year],
  ["startDate", "Inicio del horizonte", date], ["endDate", "Fin del horizonte", date],
  ["notes", "Observaciones del agrónomo (opcional)", { multiline: true }],
];
const operationFields = [
  ["type", "Tipo de operación", { options: operationTypes }], ["date", "Fecha de operación", date],
  ["description", "Descripción de la operación"], ["notes", "Observaciones de la operación", { multiline: true }],
];
const newId = () => crypto.randomUUID();

function StageEditor({ stage, index, errors = {}, update, remove, move, canMoveUp, canMoveDown }) {
  const hasCrop = ["commercial", "cover"].includes(stage.kind);
  const fields = [
    ["kind", "Tipo de etapa", { options: stageKinds }],
    ...(hasCrop ? [["cropId", "Cultivo", { options: cropOptions(stage) }]] : []),
    ...(hasCrop && stage.cropId === "custom" ? [["customCropName", "Nombre del cultivo"]] : []),
    ...(stage.kind === "management" ? [["management", "Nombre del manejo"]] : []),
    ["startDate", "Fecha de inicio de etapa", date], ["endDate", "Fecha de fin de etapa", date],
    ["notes", "Observaciones de la etapa", { multiline: true }],
  ];
  function change(key, value) {
    update(key === "kind" ? { kind: value || "commercial", cropId: "", customCropName: "" } : { [key]: value });
  }
  return (
    <fieldset className="work-fieldset strategy-stage">
      <legend>{index + 1}. {stageName(stage)}</legend>
      <div className="strategy-actions">
        <button type="button" className="work-button" disabled={!canMoveUp} onClick={() => move(-1)} aria-label={`Subir etapa ${index + 1}`}>Subir</button>
        <button type="button" className="work-button" disabled={!canMoveDown} onClick={() => move(1)} aria-label={`Bajar etapa ${index + 1}`}>Bajar</button>
        <button type="button" className="work-button" onClick={remove} aria-label={`Quitar etapa ${index + 1} y sus operaciones`}>Quitar etapa</button>
      </div>
      <FieldGrid fields={fields} values={stage} errors={errors} onChange={change} />
      {hasCrop && stage.cropId === "custom" && <Status tone="warning">Sin modelo disponible para esta especie.</Status>}
      <AgronomicInputs stage={stage} update={update} />
      <h3>Operaciones</h3>
      {stage.operations.map((operation, operationIndex) => (
        <fieldset className="work-fieldset" key={operation.id}><legend>{operation.type || `Operación ${operationIndex + 1}`}</legend>
          <FieldGrid fields={operationFields} values={operation}
            errors={Object.fromEntries(operationFields.map(([key]) => [key, errors[`${operation.id}-${key}`]]))}
            onChange={(key, value) => update({ operations: updateRecord(stage.operations, operation.id, { [key]: value }) })} />
          <button type="button" className="work-button"
            onClick={() => update({ operations: stage.operations.filter(({ id }) => id !== operation.id) })}>Quitar operación</button>
        </fieldset>
      ))}
      <button type="button" className="work-button" onClick={() => update({ operations: [...stage.operations,
        { id: newId(), type: "", date: "", description: "", notes: "" }] })}>Agregar operación</button>
    </fieldset>
  );
}

export function StrategyDetails({ strategy, onDuplicate }) {
  return <Panel title={strategy.name} description={strategy.description || strategyHorizon(strategy)}
    actions={<div className="strategy-actions">
      {!strategy.isTemplate && <a className="work-button" href={`#estrategias/editor/${strategy.id}`}>Editar estrategia</a>}
      <button type="button" className="work-button" onClick={() => onDuplicate(strategy)}>Duplicar estrategia</button>
    </div>}>
    <Status>{reviewLabel(strategy)} · {calculationLabel(strategy)}</Status>
    <ol className="work-list">{strategy.stages.map((stage) => (
      <li key={stage.id}><strong>{stageName(stage)}</strong> · {stage.startDate || "Sin fecha"} → {stage.endDate || "Sin fecha"}
        {stage.notes && <p>{stage.notes}</p>}
        {stage.operations.length > 0 && <ul>{stage.operations.map((operation) => (
          <li key={operation.id}>{operation.type} · {operation.date} {operation.description} {operation.notes}</li>
        ))}</ul>}
      </li>
    ))}</ol>
    {strategy.notes && <p>{strategy.notes}</p>}
  </Panel>;
}

export default function StrategyEditor({ original, parcel, onSave }) {
  const [strategy, setStrategy] = useState(() => original ?? blankStrategy(parcel.id, newId()));
  const [attempted, setAttempted] = useState(false);
  const validation = validateStrategy(strategy);
  const stages = orderStages(strategy.stages);
  function setStages(next) { setStrategy((previous) => ({ ...previous, stages: next })); }
  function move(index, offset) {
    const next = [...stages];
    [next[index], next[index + offset]] = [next[index + offset], next[index]];
    setStages(next);
  }
  function submit(event) {
    event.preventDefault();
    setAttempted(true);
    if (validation.valid) onSave(saveStrategy(strategy));
  }
  return <form onSubmit={submit} noValidate>
    <Panel title={original ? "Editar estrategia" : "Crear estrategia"} description={`${parcel.name} · ${parcel.id} · Horizonte de dos campañas`}>
      <FieldGrid fields={identification} values={strategy} errors={attempted ? validation.errors : {}}
        onChange={(key, value) => setStrategy((previous) => ({ ...previous, [key]: value }))} />
    </Panel>
    <DeclaredParameter label="Cobertura inicial por rastrojos" unit="%" value={strategy.initialResidue}
      error={rangeError(strategy.initialResidue?.value,0,100)} onChange={initialResidue=>setStrategy(previous=>({...previous,initialResidue}))}/>
    <Panel title="Cronología editable" description="Las etapas se ordenan por inicio previsto. Podés reordenar etapas con la misma fecha o sin fecha."
      actions={<button type="button" className="work-button"
        onClick={() => setStages([...stages, blankStage(newId())])}>Agregar etapa</button>}>
      {attempted && validation.errors.stages && <p className="field-error" role="alert">{validation.errors.stages}</p>}
      {validation.overlaps.length > 0 && <Status tone="warning">
        Calendario pendiente de revisión agronómica. Solapamientos: {validation.overlaps.join("; ")}.
      </Status>}
      {stages.map((stage, index) => (
        <StageEditor key={stage.id} stage={stage} index={index} errors={attempted ? validation.stageErrors[stage.id] : undefined}
          canMoveUp={index > 0 && stages[index - 1].startDate === stage.startDate}
          canMoveDown={index < stages.length - 1 && stages[index + 1].startDate === stage.startDate}
          move={(offset) => move(index, offset)} update={(patch) => setStages(updateRecord(stages, stage.id, patch))}
          remove={() => setStages(stages.filter(({ id }) => id !== stage.id))} />
      ))}
      {attempted && !validation.valid && <p className="field-error" role="alert">Revisá los campos señalados antes de guardar.</p>}
      <div className="strategy-actions">
        <button type="submit" className="work-button primary">Guardar estrategia</button>
        <a className="work-button" href="#estrategias/biblioteca">Volver a biblioteca</a>
      </div>
    </Panel>
  </form>;
}

