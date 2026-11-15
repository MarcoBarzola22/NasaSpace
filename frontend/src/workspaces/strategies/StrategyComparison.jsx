import { useState } from "react";
import { ComparisonChart } from "../../components/MetricsPanel.jsx";
import { formatMoney, formatNumber, metrics } from "../../data/presentation.js";
import { DataTable, Panel, Status } from "../Controls.jsx";
import { calculationLabel, comparisonContext, dateTime, reviewLabel, sequenceText, stageName, strategyHorizon } from "./model.js";

const indicatorViews = [["economy", "Economía"], ["water", "Agua"], ["soil", "Cobertura"], ["production", "Producción"]];
const day = 86_400_000;
const iso = (timestamp) => new Date(timestamp).toISOString().slice(0, 10);
const dateLabel = (value) => value || "Sin fecha confirmada";

function OperationMarkers({ strategy, stage, start, range, inspection, inspect }) {
  const operationsByDate = new Map();
  for (const operation of stage.operations) {
    const entries = operationsByDate.get(operation.date) ?? [];
    operationsByDate.set(operation.date, [...entries, operation]);
  }
  return [...operationsByDate].map(([date, operations]) => {
    const label = `${operations.map(({ type }) => type).join(" / ")} · ${date}`;
    return <button key={date} type="button" className="strategy-operation-marker" title={label}
      aria-label={`${strategy.name} · ${label}`}
      aria-pressed={inspection.strategyId === strategy.id && inspection.operationDate === date && inspection.stageId === stage.id}
      style={{ left: `${(dateTime(date) - start) / range * 100}%` }}
      onClick={() => inspect(strategy.id, { stageId: stage.id, operationDate: date })} />;
  });
}

function StageButton({ strategy, stage, inspection, inspect, dated }) {
  const [left, width] = dated || [];
  return <button type="button" className="strategy-timeline-stage" data-kind={stage.kind}
    aria-pressed={inspection.strategyId === strategy.id && inspection.stageId === stage.id}
    aria-label={`${strategy.name} · ${stageName(stage)} · ${dateLabel(stage.startDate)}`}
    style={dated ? { marginLeft: `${left}%`, width: `${width}%` } : undefined}
    onClick={() => inspect(strategy.id, { stageId: stage.id })}>
    {stageName(stage)}{stage.operations.length ? ` · ${stage.operations.length} op.` : ""}
  </button>;
}

export function Timeline({ strategies, inspection, inspect, context }) {
  const { reference, incompatible, undated } = context;
  const excluded = new Set([...incompatible, ...undated].map(({ id }) => id));
  const dated = reference ? strategies.filter(({ id }) => !excluded.has(id)) : [];
  const schematic = reference ? undated : strategies;
  const start = reference ? dateTime(reference.startDate) : 0;
  const end = reference ? dateTime(reference.endDate) : 1;
  const dayRange = Math.max(day, end - start);
  return <Panel title="Cronología de comparación" description="Elegí una etapa para consultar sus fechas, operaciones y observaciones.">
    {dated.length > 0 && <div className="work-table-scroll strategy-timeline-scroll" tabIndex={0} role="region" aria-label="Cronología con escala de fechas">
      <div className="strategy-timeline">
        <div className="strategy-timeline-row"><strong>Horizonte común</strong><div className="strategy-axis">
          <span>{iso(start)}</span><span>{iso(start + dayRange / 2)}</span><span>{iso(end)}</span>
        </div></div>
        {dated.map((strategy) => <div className="strategy-timeline-row" key={strategy.id}>
          <strong>{strategy.name}</strong>
          <div>{strategy.stages.map((stage) => <div className="strategy-track" key={stage.id}>
            <StageButton strategy={strategy} stage={stage} inspect={inspect} inspection={inspection}
              dated={[(dateTime(stage.startDate) - start) / dayRange * 100, (dateTime(stage.endDate) - dateTime(stage.startDate)) / dayRange * 100]} />
            <OperationMarkers strategy={strategy} stage={stage} start={start} range={dayRange} inspection={inspection} inspect={inspect} />
          </div>)}</div>
        </div>)}
      </div>
    </div>}
    {dated.some((strategy) => strategy.stages.some(({ operations }) => operations.length)) && <p className="work-note">Los marcadores señalan operaciones fechadas. Seleccionalos para consultar el detalle.</p>}
    {schematic.length > 0 && <>
      <p className="work-note">Secuencias sin fechas confirmadas. Las posiciones de este esquema son ilustrativas.</p>
      <div className="work-table-scroll strategy-timeline-scroll" tabIndex={0} role="region" aria-label="Secuencias sin escala temporal">
        <div className="strategy-timeline">{schematic.map((strategy) => <div className="strategy-timeline-row" key={strategy.id}>
          <strong>{strategy.name}</strong><div className="strategy-actions">
            {strategy.stages.map((stage) => <StageButton key={stage.id} strategy={strategy} stage={stage} inspection={inspection} inspect={inspect} />)}
          </div>
        </div>)}</div>
      </div>
    </>}
    {incompatible.length > 0 && <Status tone="warning">Horizonte distinto del período de referencia: {incompatible.map(({ name }) => name).join(", ")}. Quedan fuera de la escala común y de la comparación científica.</Status>}
  </Panel>;
}

const resultColumns = {
  economy: [["income", "Ingresos", "ARS/ha"], ["cost", "Costos directos", "ARS/ha"], ["margin", "Margen bruto", "ARS/ha"]],
  water: [["deficit", "Déficit hídrico", "mm"]],
  soil: [["cover", "Cultivo vivo", "meses"]],
  production: [["maize", "Maíz", "t/ha"], ["wheat", "Trigo", "t/ha"], ["soy", "Soja", "t/ha"]],
};
const missing = {
  economy: "Resultados económicos pendientes de cálculo",
  water: "Balance hídrico no disponible para esta estrategia",
  soil: "Cobertura no calculada para esta estrategia",
  production: "Rendimientos no disponibles para esta estrategia",
};

export function Results({ strategies, demoResults, metric, setMetric, inspect, selectedId, scenario, context, visibleMetrics = indicatorViews }) {
  const columns = resultColumns[metric];
  const compatible = strategies.filter((strategy) => !context.incompatible.includes(strategy));
  const available = compatible.filter(({ isTemplate }) => isTemplate).map((strategy) => ({
    ...demoResults.find(({ id }) => id === strategy.id), label: strategy.name,
  }));
  const chartMetric = metrics.find(({ id }) => id === metric);
  return <Panel title="Indicadores comparados" description={`${scenario} · Dos campañas. Las cifras de las plantillas son demostrativas.`}>
    {visibleMetrics.length > 0 && <div className="strategy-actions" role="group" aria-label="Indicador comparado">
      {visibleMetrics.map(([id, label]) => <button type="button" className="work-button" aria-pressed={metric === id}
        key={id} onClick={() => setMetric(id)}>{label}</button>)}
    </div>}
    <DataTable caption="Disponibilidad por estrategia" columns={["Estrategia", ...columns.map(([, label, unit]) => `${label} (${unit})`)]}
      rows={strategies.map((strategy) => {
        const demo = available.find(({ id }) => id === strategy.id);
        return { id: strategy.id, selected: selectedId === strategy.id, cells: [
          strategy.name,
          ...columns.map(([key, label, unit], index) => {
            const value = metric === "production" ? demo?.yields[index] : demo?.[key];
            if (value === null) return "No corresponde";
            if (value === undefined) return index === 0 ? missing[metric] : "Sin resultado";
            const shown = metric === "economy" ? formatMoney(value) : formatNumber(value);
            return <button type="button" className="work-button strategy-result"
              aria-label={`${strategy.name} · ${label}: ${shown} ${unit}`}
              onClick={() => inspect(strategy.id, { result: { label, shown, unit } })}>{shown}</button>;
          }),
        ] };
      })} />
    {available.length >= 2 && metric !== "production" && <ComparisonChart metric={chartMetric} rotations={available} selectedId={selectedId} />}
    {metric === "soil" && <p className="work-note">El barbecho es una etapa de manejo y puede conservar rastrojos. La demo no incluye exposición al viento.</p>}
    {metric === "water" && <p className="work-note">Sin series temporales de agua del suelo o demanda. El déficit de demostración es un valor agregado.</p>}
    {metric === "production" && <p className="work-note">Las cifras de soja corresponden a primera en Barbecho y a segunda en Doble cultivo. En Cobertura se informa soja sin distinguir el tipo.</p>}
  </Panel>;
}

export default function StrategyComparison({ strategies, comparisonIds, onToggle, inspection, inspect, demoResults, scenario, onOpenExplorer, explorerOpen, inspectorOpen }) {
  const [metric, setMetric] = useState("economy");
  const selected = comparisonIds.map((id) => strategies.find((strategy) => strategy.id === id)).filter(Boolean);
  const context = comparisonContext(selected);
  return <>
    <Panel title="Mesa comparativa" description="Seleccioná hasta tres estrategias de esta parcela."
      actions={<button id="economic-explorer-trigger" type="button" className="work-button primary"
        aria-expanded={explorerOpen} aria-controls={explorerOpen ? "economic-explorer" : undefined} onClick={onOpenExplorer}>Explorar precios y costos</button>}>
      <div className="strategy-actions">
        {strategies.map(({ id, name }) => {
          const included = comparisonIds.includes(id);
          return <button type="button" key={id} className="work-button" aria-pressed={included}
            disabled={!included && comparisonIds.length >= 3} aria-label={`${included ? "Retirar" : "Comparar"} ${name}`}
            onClick={() => onToggle(id)}>{name}</button>;
        })}
      </div>
      <p className="work-note" role="status">{selected.length} de 3 seleccionadas{selected.length === 3 ? " · Retirá una para agregar otra." : "."}</p>
      {selected.length < 2 && <Status tone="warning">Seleccioná al menos dos estrategias para compararlas.</Status>}
            {inspectorOpen && <a className="work-button strategy-inspector-jump" href="#parcel-inspector">Ir al inspector</a>}
      <DataTable caption="Alternativas seleccionadas" columns={["Estrategia", "Secuencia", "Horizonte", "Revisión y resultados"]}
        rows={selected.map((strategy) => ({ id: strategy.id, selected: inspection.strategyId === strategy.id, cells: [
          <button type="button" className="work-button" aria-pressed={inspection.strategyId === strategy.id}
            onClick={() => inspect(strategy.id)}>{strategy.name}</button>,
          sequenceText(strategy), strategyHorizon(strategy), <>{reviewLabel(strategy)}<small className="strategy-id">{calculationLabel(strategy)}</small></>,
        ] }))} />
    </Panel>
    {selected.length > 0 && <>
      <Timeline strategies={selected} inspection={inspection} inspect={inspect} context={context} />
      <Results strategies={selected} demoResults={demoResults} metric={metric} setMetric={setMetric} inspect={inspect}
        selectedId={inspection.strategyId} scenario={scenario} context={context} />
    </>}
  </>;
}

export function ContextualInspector({ strategy, inspection, onStage, outsideComparison, onClose }) {
  const stage = strategy?.stages.find(({ id }) => id === inspection.stageId);
  const result = inspection.result;
  const duration = stage && stage.startDate && stage.endDate ? Math.round((dateTime(stage.endDate) - dateTime(stage.startDate)) / day) : null;
  return <aside className="inspector strategy-inspector" id="parcel-inspector" tabIndex={-1} aria-label="Inspector contextual">
    <div className="sticky">
      <div className="inspector-top"><span className="eyebrow">Inspector contextual</span><button type="button" className="work-button" onClick={onClose}>Cerrar</button></div>
      {!strategy ? <p className="work-note">Seleccioná una estrategia o etapa para inspeccionarla.</p> : <>
        <h2>{strategy.name}</h2>
        <p>{sequenceText(strategy)}</p>
        {outsideComparison && <p className="work-note">Activa fuera de la mesa comparativa.</p>}
        <dl className="work-readout">
          <div><dt>Horizonte</dt><dd>{strategyHorizon(strategy)}</dd></div>
          <div><dt>Fechas</dt><dd>{dateLabel(strategy.startDate)} → {dateLabel(strategy.endDate)}</dd></div>
          <div><dt>Revisión</dt><dd>{reviewLabel(strategy)}</dd></div>
          <div><dt>Resultados</dt><dd>{calculationLabel(strategy)}</dd></div>
        </dl>
        {stage ? <>
          <h3>{stageName(stage)}</h3>
          <dl className="work-readout">
            <div><dt>Fechas previstas</dt><dd>{dateLabel(stage.startDate)} → {dateLabel(stage.endDate)}</dd></div>
            <div><dt>Duración</dt><dd>{duration === null ? "Sin dato" : `${duration} días entre fechas`}</dd></div>
            <div><dt>Parámetros del cultivo</dt><dd>{stage.cropId === "custom" ? "Sin modelo disponible para esta especie" : "Sin parámetros verificados en esta sesión"}</dd></div>
            <div><dt>Observaciones</dt><dd>{stage.notes || "Sin observaciones"}</dd></div>
          </dl>
          <h3>Operaciones registradas</h3>
          {stage.operations.length ? <ul className="work-list">{stage.operations.map((operation) => (
            <li key={operation.id} className={operation.date === inspection.operationDate ? "strategy-operation-active" : undefined}><strong>{operation.type}</strong> · {operation.date} {operation.description} {operation.notes}</li>
          ))}</ul> : <p className="work-note">Sin operaciones registradas.</p>}
        </> : result ? <>
          <h3>{result.label}</h3>
          <dl className="work-readout">
            <div><dt>Valor</dt><dd>{result.shown} · {result.unit}</dd></div>
            <div><dt>Fuente</dt><dd>Valores precargados de demostración</dd></div>
            <div><dt>Período</dt><dd>Dos campañas · Sin fecha puntual</dd></div>
            <div><dt>Estado</dt><dd>Referencia de demostración. Cálculo real pendiente.</dd></div>
            <div><dt>Entradas</dt><dd>Importe o indicador de la plantilla. Las entradas de la sesión requieren cálculo en FastAPI.</dd></div>
          </dl>
        </> : <>
          <h3>Etapas de la secuencia</h3>
          <ol className="work-list">{strategy.stages.map((item) => (
            <li key={item.id}>{onStage ? <button className="work-button" type="button" onClick={() => onStage(item.id)}>{stageName(item)}</button> : stageName(item)} · {dateLabel(item.startDate)} → {dateLabel(item.endDate)}</li>
          ))}</ol>
        </>}
      </>}
    </div>
  </aside>;
}

