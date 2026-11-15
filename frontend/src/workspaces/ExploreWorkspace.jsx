import HistoricalInputs from "./HistoricalInputs.jsx";
import StrategyLibrary from "./strategies/StrategyLibrary.jsx";
import StrategyEditor, { StrategyDetails } from "./strategies/StrategyEditor.jsx";
import StrategyComparison, { Results, Timeline } from "./strategies/StrategyComparison.jsx";
import { validIdentity } from "./session.js";
import { comparisonContext } from "./strategies/model.js";
import { DataTable, Panel, Status } from "./Controls.jsx";

const variables = [
  ["Precipitación", "mm"], ["Temperatura", "°C"], ["Radiación solar", "MJ/m²/día"], ["Viento", "m/s"],
];

export default function ExploreWorkspace({ section, parcel, parcelRotations,
   metricId, onMetric, periodLabel, draft, patch, strategyBook, scenario, explorerOpen, onOpenExplorer }) {
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
  if (section === "cronologia") return compared.length ? <Timeline strategies={compared} inspection={strategyBook.inspection}
    inspect={strategyBook.inspect} context={context} /> : <Status>Seleccioná estrategias en la mesa comparativa.</Status>;
  const identity = validIdentity(draft.identity);
  if (section === "clima") return <><HistoricalInputs draft={draft} patch={patch} /><Panel title="Clima histórico" description={`NASA POWER · Horizonte de referencia: ${periodLabel}`}>
    <Status tone="warning">Pendiente de integración. La aplicación no dispone de series climáticas para este lote.</Status>
    <dl className="work-readout"><div><dt>Horizonte declarado</dt><dd>{identity.firstYear || "Sin inicio"} · {identity.lastYear || "Sin final"}</dd></div>
      <div><dt>Fechas exactas de la serie</dt><dd>Sin dato</dd></div><div><dt>Procedencia</dt><dd>NASA POWER previsto</dd></div></dl>
    <DataTable caption="Disponibilidad de variables" columns={["Variable", "Unidad prevista", "Datos", "Faltantes"]}
      rows={variables.map(([label, unit]) => ({ id: label, cells: [label, unit, "Sin serie", "No evaluables"] }))} />
  </Panel></>;
  if (section === "agua") return <>
    <Status>Datos ficticios · Dos campañas completas.</Status>
    <Results strategies={compared} demoResults={parcelRotations} selectedId={strategyBook.inspection.strategyId}
      metric={metricId} setMetric={onMetric} visibleMetrics={[["water", "Agua"], ["soil", "Cobertura"]]}
      inspect={strategyBook.inspect} scenario={scenario} context={context} />
    <Panel title="Disponibilidad de resultados hídricos y de cobertura">
      <DataTable caption="Detalle disponible" columns={["Indicador", "Disponibilidad"]} rows={[
        ["Evolución del agua del suelo", "Sin serie"], ["Demanda del cultivo", "Sin serie"], ["Días o etapas con déficit", "Sin desglose"],
        ["Rastrojos de la parcela", "Consultar antecedentes declarados"], ["Exposición potencial al viento", "Pendiente de integración"],
      ].map(([label, state]) => ({ id: label, cells: [label, state] }))} />
    </Panel>
  </>;
  if (section === "produccion") return <>
    <Status>Demostración · Rendimientos de muestra general en t/ha para el horizonte de dos campañas.</Status>
    <Results strategies={compared} demoResults={parcelRotations} selectedId={strategyBook.inspection.strategyId}
      metric="production" setMetric={onMetric} visibleMetrics={[]} inspect={strategyBook.inspect} scenario={scenario} context={context} />
    <Panel title="Supuestos de producción"><p>La soja de A corresponde a primera y la de C a segunda. El escenario B registra soja de forma general. El centeno se representa como cobertura, sin comercialización de grano.</p></Panel>
  </>;
  return null;
}

