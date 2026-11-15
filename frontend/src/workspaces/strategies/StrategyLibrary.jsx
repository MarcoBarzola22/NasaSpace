import { useState } from "react";
import { DataTable, Panel, Status } from "../Controls.jsx";
import { calculationLabel, reviewLabel, sequenceText, strategyHorizon } from "./model.js";

export default function StrategyLibrary({ strategies, comparisonIds, onToggle, onInspect, onDuplicate, onDelete, notice, inspection }) {
  const [confirmId, setConfirmId] = useState("");
  const pending = strategies.find(({ id }) => id === confirmId);
  return <>
    {notice && <p className="work-status" role="status">{notice}</p>}
    <Panel title="Estrategias agrícolas" description="Definí alternativas de manejo para la parcela y seleccioná cuáles querés comparar."
      actions={<a className="work-button primary" href="#estrategias/editor">+ Crear estrategia</a>}>
      <div className="strategy-library-tools">
        <span role="status">{comparisonIds.length} de 3 seleccionadas</span>
        <a className="work-button" href="#estrategias/comparar">Abrir mesa comparativa</a>
      </div>
      {comparisonIds.length === 3 && <p className="work-note">Retirá una estrategia de la comparación para agregar otra.</p>}
      {pending && <div className="strategy-confirm">
        <p role="alert">¿Eliminar «{pending.name}» de esta sesión y retirarla de la comparación?</p>
        <div className="strategy-actions">
          <button type="button" className="work-button" onClick={() => setConfirmId("")}>Cancelar</button>
          <button type="button" className="work-button" onClick={() => { onDelete(pending.id); setConfirmId(""); }}>Confirmar eliminación</button>
        </div>
      </div>}
      <DataTable caption="Biblioteca de la parcela activa" columns={["Estrategia", "Secuencia", "Etapas", "Horizonte", "Estado", "Acciones"]}
        rows={strategies.map((strategy) => {
          const { id, name, isTemplate, stages } = strategy;
          const included = comparisonIds.includes(id);
          return { id, selected: inspection?.strategyId === id, cells: [
            <><button type="button" className="work-button" aria-pressed={inspection?.strategyId === id} onClick={() => onInspect(id)}>{name}</button><small className="strategy-id">{id}</small></>, sequenceText(strategy),
            stages.length, strategyHorizon(strategy), <>{reviewLabel(strategy)}<small className="strategy-id">{calculationLabel(strategy)}</small></>,
            <div className="strategy-actions">
              <a className="work-button" href={`#estrategias/editor/${id}/detalle`} aria-label={`Ver detalle de ${name}`} onClick={() => onInspect(id)}>Ver detalle</a>
              {isTemplate
                ? <button type="button" className="work-button" onClick={() => onDuplicate(strategy)} aria-label={`Editar copia de ${name}`}>Editar copia</button>
                : <a className="work-button" href={`#estrategias/editor/${id}`} aria-label={`Editar ${name}`} onClick={() => onInspect(id)}>Editar</a>}
              <button type="button" className="work-button" onClick={() => onDuplicate(strategy)} aria-label={`Duplicar ${name}`}>Duplicar</button>
              <button type="button" className="work-button" disabled={!included && comparisonIds.length >= 3}
                onClick={() => onToggle(id)} aria-label={`${included ? "Retirar" : "Comparar"} ${name}`}>{included ? "Retirar" : "Comparar"}</button>
              {!isTemplate && <button type="button" className="work-button" onClick={() => setConfirmId(id)} aria-label={`Eliminar ${name}`}>Eliminar</button>}
            </div>,
          ] };
        })} />
      {comparisonIds.length < 2 && <Status tone="warning">Seleccioná al menos dos estrategias para compararlas.</Status>}
    </Panel>
  </>;
}

