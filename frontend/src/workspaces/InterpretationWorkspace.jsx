import { useState } from "react";
import ContextNotes from "../components/ContextNotes.jsx";
import { DataTable, Field, Panel, Status } from "./Controls.jsx";
import { amountError, economicEntryErrors } from "./economics.js";
import { StudyResults } from "./LabStudies.jsx";
import { studyReviewLabel, validateIdentity } from "./session.js";

const indicators = [
  ["income", "Ingresos", "Valor de venta ilustrativo de dos campañas", "ARS/ha", "Ingresos de demostración", "Resumen económico"],
  ["cost", "Costos directos", "Costos directos ilustrativos de dos campañas", "ARS/ha", "Costos precargados de demostración", "Resumen económico"],
  ["margin", "Margen bruto", "Saldo entre ingresos y costos directos en dos campañas", "ARS/ha", "Ingresos y costos de demostración", "Resumen económico"],
  ["deficit", "Déficit hídrico", "Déficit ilustrativo por estrategia", "mm", "Escenario ficticio precargado", "Balance FAO-56 previsto, sin ejecución"],
  ["cover", "Cobertura", "Tiempo ilustrativo con cultivo vivo", "meses", "Secuencia de cultivos de demostración", "Conteo de períodos previsto, sin ejecución"],
  ["yield", "Rendimiento", "Rendimiento ilustrativo para cada cultivo comercial", "t/ha", "Muestra general, sin datos por parcela", "Respuesta al déficit FAO-33 prevista, sin ejecución"],
];

export function getWarnings(draft) {
  const soil = Object.values(draft.soil);
  const labResults = draft.studies.flatMap((study) => study.samples.flatMap(({ results }) => results));
  return [
    ["Dato faltante", draft.identity.area ? "Revisar el expediente para ver campos sin dato." : "Superficie declarada sin dato."],
    ["Unidad por revisar", [...soil, ...draft.prices, ...draft.costs, ...labResults].some(({ value, amount, unit }) => (value || amount) && !unit)
      ? "Hay entradas con valor y sin unidad. Revisá su compatibilidad al integrar el cálculo." : "Compatibilidad de unidades pendiente de revisión profesional."],
    ...Object.entries(validateIdentity(draft.identity)).map(([field, message]) => [`Fecha o formato · ${field === "lastYear" || field === "firstYear" ? "Horizonte" : field === "area" ? "Superficie" : "Coordenadas"}`, message]),
    ...draft.studies.filter(({ sampleDate, analysisDate }) => sampleDate && analysisDate && analysisDate < sampleDate)
      .map(() => ["Fecha inválida", "Un estudio tiene fecha de análisis anterior al muestreo."]),
    ...([...draft.prices, ...draft.costs].some(({ amount }) => amountError(amount))
      ? [["Importe inválido", "Hay precios o costos declarados con un importe inválido."]] : []),
    ...[...draft.prices, ...draft.costs].filter(({ amount }) => amount).flatMap((row) => {
      const { currency, unit, date } = economicEntryErrors(row);
      return [currency, unit, date].filter(Boolean).map((message) => ["Entrada económica por revisar", message]);
    }),
    ["Calendario no confirmado", "Siembra, cosecha y terminación requieren confirmación."],
    ["Resultado no calculable", "Recálculo pendiente de integración con el servicio científico."],
    ["Parámetro supuesto", soil.some(({ basis }) => basis === "Supuesto") ? "Hay valores de suelo identificados como supuestos." : "La capacidad hídrica de la demostración es un supuesto."],
    ["Revisión profesional", draft.studies.some((study) => studyReviewLabel(study) !== "Revisado manualmente")
      ? "Hay estudios pendientes de transcripción o revisión." : "La demostración requiere revisión agronómica antes del uso técnico."],
    ...(draft.identity.production === "Con riego" ? [["Fuera del alcance actual", "El MVP representa secano."]] : []),
  ];
}

export default function InterpretationWorkspace({ section, draft, requestedIndicator, interpretationEvidence }) {
  const [selection, setSelection] = useState(null);
  const fallback = indicators.some(([id]) => id === requestedIndicator) ? requestedIndicator : "margin";
  const indicatorId = selection?.route === requestedIndicator ? selection?.id ?? fallback : fallback;
  const [, title, description, unit, inputs, method] = indicators.find(([id]) => id === indicatorId);
  const evidence = interpretationEvidence?.indicatorId === indicatorId ? interpretationEvidence : undefined;
  if (section === "nutricion") return <Panel title="Estudios y nutrición">
    <Status>Los indicadores de nutrientes se presentan como información de laboratorio. No forman parte de los cálculos agronómicos del MVP actual.</Status>
    <StudyResults studies={draft.studies} />
  </Panel>;
  if (section === "advertencias") return <Panel title="Advertencias y consistencia" description="Comprobaciones de formato y disponibilidad. La validación agronómica corresponde al servicio de cálculo.">
    <DataTable caption="Controles del análisis" columns={["Tipo", "Situación"]}
      rows={getWarnings(draft).map(([type, message], index) => ({ id: index, cells: [type, message] }))} />
  </Panel>;
  if (section === "procedencia") return <>
    <Panel title="Procedencia de los datos"><DataTable caption="Inventario de fuentes" columns={["Fuente", "Disponibilidad", "Procedencia"]}
      rows={[
        ["NASA POWER", "Pendiente de integración", "Series climáticas previstas"],
        ["Datos declarados", Object.values(draft.identity).some(Boolean) || Object.keys(draft.soil).length ? "Disponibles en sesión" : "Sin dato", "Edición manual por parcela"],
        ["Estudios de laboratorio", `${draft.studies.length} en sesión`, "Informe y transcripción manual"],
        ["Rendimientos observados", draft.history.some(({ yield: observed }) => observed) ? "Disponibles en sesión" : "Sin dato", "Antecedentes declarados"],
        ["Bibliografía y parámetros", "Pendiente de integración", "Procedimientos FAO-56 y FAO-33 previstos"],
        ["Supuestos", "Demostración", "Parámetros y resultados ficticios del prototipo"],
      ].map(([source, status, basis]) => ({ id: source, cells: [source, status, basis] }))} /></Panel><ContextNotes />
  </>;
  return <Panel title="Explicación de resultados" description="Unidad, origen y alcance de los indicadores de demostración.">
    <Field label="Indicador" options={indicators.map(([id, label]) => [id, label])} value={indicatorId}
      onChange={(id) => setSelection({ route: requestedIndicator, id: id || "margin" })} />
    <h3>{title}</h3>
    {evidence && <p className="work-note">{evidence.strategyName} · {evidence.label} · {evidence.shown} {evidence.unit} · Dos campañas · Demostración</p>}
    <dl className="work-readout">{[["Qué representa", description], ["Unidad", unit], ["Entradas", inputs],
      ["Procedencia", "Demostración · valores precargados"], ["Modelo o procedimiento", method],
      ["Supuestos", "Horizonte común de dos campañas en secano"], ["Limitaciones", "Sin resultado calculado ni validación profesional."]]
      .map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>
  </Panel>;
}

