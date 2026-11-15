import HistoricalInputs from "./HistoricalInputs.jsx";
import StrategyLibrary from "./strategies/StrategyLibrary.jsx";
import StrategyEditor, { StrategyDetails } from "./strategies/StrategyEditor.jsx";
import StrategyComparison, { Results, Timeline } from "./strategies/StrategyComparison.jsx";
import { validIdentity } from "./session.js";
import { comparisonContext } from "./strategies/model.js";
import { DataTable, Panel, Status } from "./Controls.jsx";
import SimulationResults, { DemoNotice, EngineGate, FindingsTables, ProvenanceBlock, ScenarioTable } from "./SimulationResults.jsx";

const variables = [
  ["Precipitación", "mm"], ["Temperatura", "°C"], ["Radiación solar", "MJ/m²/día"], ["Viento", "m/s"],
];

export default function ExploreWorkspace({ section, parcel, parcelRotations,
   metricId, onMetric, periodLabel, draft, patch, strategyBook, scenario, explorerOpen, onOpenExplorer, engine }) {
  if (section === "biblioteca") return <StrategyLibrary key={parcel.id} {...strategyBook} />;
  if (section === "editor") {
    const { item, details, missingItem, onSave, onDuplicate } = strategyBook;
    if (missingItem) return <Panel title="Estrategia no disponible">
      <p>Esta estrategia no pertenece al expediente de la parcela activa.</p>
      <a className="work-button" href="#estrategias/biblioteca">Volver a biblioteca</a>
    </Panel>;
    if (item && (item.isTemplate || details)) return <StrategyDetails strategy={item} onDuplicate={onDuplicate} />;
    return <StrategyEditor key={`${parcel.id}-${item?.id || "new"}`} original={item} parcel={parcel} onSave={onSave} />;
  }
  if (section === "comparar") return <StrategyComparison {...strategyBook} demoResults={parcelRotations}
    parcelName={parcel.name} scenario={scenario} draft={draft} onOpenExplorer={onOpenExplorer} explorerOpen={explorerOpen} />;
  const compared = strategyBook.comparisonIds.map((id) => strategyBook.strategies.find((strategy) => strategy.id === id)).filter(Boolean);
  const context = comparisonContext(compared);
  const { simulation } = strategyBook;
  if (section === "cronologia") return compared.length ? <Timeline strategies={compared} inspection={strategyBook.inspection}
    inspect={strategyBook.inspect} context={context} /> : <Status>Seleccioná estrategias en la mesa comparativa.</Status>;
  const identity = validIdentity(draft.identity);
  if (section === "clima") return <><HistoricalInputs draft={draft} patch={patch} /><Panel title="Clima histórico" description={`NASA POWER · Horizonte de referencia: ${periodLabel}`}>
    <EngineGate engine={engine}>
      {simulation?.response && <><ScenarioTable response={simulation.response} /><ProvenanceBlock response={simulation.response} /></>}
    </EngineGate>
    {!simulation?.response && <DataTable caption="Variables que se consultan a NASA POWER" columns={["Variable", "Unidad"]}
      rows={variables.map(([label, unit]) => ({ id: label, cells: [label, unit] }))} />}
  </Panel></>;
  if (section === "agua") return simulation?.response ? <Panel title="Agua y cobertura · resultados del motor" description="Balance hídrico FAO-56, estrés hídrico y exposición del suelo por escenario histórico.">
    <EngineGate engine={engine}><FindingsTables run={simulation.run} strategies={strategyBook.strategies} /></EngineGate>
  </Panel> : <>
    <EngineGate engine={engine} />
    <DemoNotice>Datos ficticios · Dos campañas completas.</DemoNotice>
    <Results strategies={compared} demoResults={parcelRotations} selectedId={strategyBook.inspection.strategyId}
      metric={metricId} setMetric={onMetric} visibleMetrics={[["water", "Agua"], ["soil", "Cobertura"]]}
      inspect={strategyBook.inspect} scenario={scenario} context={context} />
  </>;
  if (section === "produccion") return simulation?.response
    ? <SimulationResults run={simulation.run} status={simulation.status} strategies={strategyBook.strategies} summary /> : <>
    <EngineGate engine={engine} />
    <DemoNotice>Rendimientos de muestra general en t/ha para el horizonte de dos campañas.</DemoNotice>
    <Results strategies={compared} demoResults={parcelRotations} selectedId={strategyBook.inspection.strategyId}
      metric="production" setMetric={onMetric} visibleMetrics={[]} inspect={strategyBook.inspect} scenario={scenario} context={context} />
    <Panel title="Supuestos de producción"><p>La soja de A y de B corresponde a primera y la de C a segunda. El centeno se representa como cobertura, sin comercialización de grano.</p></Panel>
  </>;
  return null;
}

