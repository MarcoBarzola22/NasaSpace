import { useState } from "react";
import { DataTable, Field, FieldGrid, Panel, Status } from "./Controls.jsx";
import LocalFiles from "./LocalFiles.jsx";
import { studyHasResult, studyReviewLabel, updateRecord } from "./session.js";

const groups = [
  ["physical", "Propiedades físicas", ["Textura", "Arena", "Limo", "Arcilla", "Densidad aparente", "Humedad"]],
  ["chemical", "Química del suelo", ["pH", "Conductividad eléctrica", "Materia orgánica", "Carbono orgánico", "Capacidad de intercambio catiónico"]],
  ["nitrogen", "Nitrógeno", ["Nitrógeno total", "N-NO₃", "N-NH₄", "Nitrógeno mineral", "NO₃"]],
  ["phosphorus", "Fósforo", ["Fósforo disponible"]],
  ["potassium", "Potasio", ["Potasio disponible", "Potasio intercambiable"]],
  ["other", "Otros nutrientes", []],
];

const reportFields = [
  ["lab", "Laboratorio"], ["report", "Identificador del informe"], ["sampleDate", "Fecha de muestreo (opcional)", { type: "date" }],
  ["analysisDate", "Fecha del análisis (opcional)", { type: "date" }], ["method", "Método general (opcional)"], ["notes", "Observaciones (opcional)", { multiline: true }],
];
const sampleFields = [
  ["name", "Identificador de muestra"], ["depth", "Intervalo de profundidad (como en el informe)"],
  ["depthUnit", "Unidad de profundidad"], ["notes", "Observaciones (opcional)"],
];
const reviewStates = ["Transcrito por el usuario", "Pendiente de revisión", "Revisado manualmente"];
const resultFields = [
  ["name", "Nombre exacto"], ["value", "Valor informado"], ["unit", "Unidad original"],
  ["method", "Método analítico (opcional)"], ["source", "Referencia específica (opcional)"],
];

export function StudyResults({ studies }) {
  if (!studies.length) return <p className="work-empty">Sin estudios registrados para esta parcela.</p>;
  return studies.map((study) => (
    <div className="study-readout" key={study.id}>
      <h3>{study.report || "Informe sin identificador"}</h3>
      <p>{[study.lab || "Laboratorio sin dato", studyReviewLabel(study), study.notes].filter(Boolean).join(" · ")}</p>
      {study.samples.length > 0 && <DataTable caption="Profundidades registradas" columns={["Muestra", "Profundidad", "Unidad", "Observaciones"]}
        rows={study.samples.map((sample, index) => ({ id: sample.id, cells: [sample.name || `Muestra ${index + 1}`, sample.depth, sample.depthUnit, sample.notes] }))} />}
      {groups.map(([group, title]) => {
        const rows = study.samples.flatMap((sample, index) => sample.results.filter((result) => result.group === group).map((result) => ({
          id: result.id, cells: [sample.name || `Muestra ${index + 1}`, [sample.depth, sample.depthUnit].filter(Boolean).join(" "), result.name,
            result.value, result.unit, result.method, result.source || study.report, result.value?.trim() ? result.review || "Transcrito por el usuario" : "Pendiente de transcripción"],
        })));
        return <details className="work-details" key={group} open={rows.length ? true : undefined}>
          <summary>{title}{rows.length ? ` · ${rows.length}` : ""}</summary>
          <DataTable caption={`${title} por muestra`} columns={["Muestra", "Profundidad", "Parámetro", "Valor", "Unidad", "Método", "Fuente", "Revisión"]} rows={rows} />
        </details>;
      })}
    </div>
  ));
}

function SampleEditor({ sample, update }) {
  const [group, setGroup] = useState(groups[0][0]);
  const [parameter, setParameter] = useState("");
  const [, title, choices] = groups.find(([id]) => id === group);
  return (
    <>
      <FieldGrid fields={sampleFields} values={sample} onChange={(key, value) => update({ [key]: value })} />
      <h3>Transcripción manual</h3>
      <p className="work-note">Copiá el nombre, el valor, la unidad y el método tal como figuran en el informe. Los resultados sin informar quedan como «Sin dato».</p>
      <div className="work-segment" role="group" aria-label="Grupos de parámetros">
        {groups.map(([id, label]) => <button type="button" className="work-button" aria-pressed={id === group} key={id}
          onClick={() => { setGroup(id); setParameter(""); }}>{label}</button>)}
      </div>
      <div className="work-inline parameter-choice">
        {choices.length > 0 && <Field label={`Parámetro de ${title.toLowerCase()}`} value={parameter} onChange={setParameter} options={choices} />}
        <button className="work-button" type="button" onClick={() => {
          update({ results: [...sample.results, { id: crypto.randomUUID(), group, name: parameter }] });
          setParameter("");
        }}>Agregar parámetro</button>
      </div>
      {sample.results.filter((result) => result.group === group).map((result) => (
        <fieldset className="work-fieldset" key={result.id}><legend>{result.name || "Parámetro sin nombre"}</legend>
          <FieldGrid fields={resultFields} values={result} onChange={(key, value) => update({ results: updateRecord(sample.results, result.id, { [key]: value,
            ...(result.review === "Revisado manualmente" ? { review: "Pendiente de revisión" } : {}) }) })} />
          {result.value?.trim() && <Field label="Revisión del parámetro" value={result.review || reviewStates[0]} options={reviewStates}
            onChange={(review) => update({ results: updateRecord(sample.results, result.id, { review }) })} />}
          <button type="button" className="work-button" onClick={() => update({ results: sample.results.filter(({ id }) => id !== result.id) })}>Quitar parámetro</button>
        </fieldset>
      ))}
    </>
  );
}

export default function LabStudies({ studies, onChange }) {
  const [studyId, setStudyId] = useState("");
  const [sampleId, setSampleId] = useState("");
  const study = studies.find(({ id }) => id === studyId);
  const sample = study?.samples.find(({ id }) => id === sampleId) ?? study?.samples[0];
  function addStudy() {
    const id = crypto.randomUUID();
    onChange([...studies, { id, files: [], samples: [] }]);
    setStudyId(id);
    setSampleId("");
  }
  function update(patch) {
    const review = study.review === "Revisado manualmente" ? { review: "Pendiente de revisión" } : {};
    onChange(updateRecord(studies, study.id, { ...review, ...patch }));
  }
  return (
    <>
      <Panel title="Estudios de suelo" description="Informes y transcripciones manuales de la parcela activa."
        actions={<button type="button" className="work-button primary" onClick={addStudy}>Agregar estudio</button>}>
        {studies.length === 0 ? <p className="work-empty">Sin estudios de suelo registrados.</p> : <ul className="study-overview">
          {studies.map((entry, index) => {
            const depths = entry.samples.map(({ depth, depthUnit }) => [depth, depthUnit].filter(Boolean).join(" ")).filter(Boolean);
            const parameters = entry.samples.flatMap(({ results }) => results);
            const count = parameters.filter(({ value }) => value?.trim()).length;
            return <li key={entry.id}>
              <div><h3>{entry.report || "Estudio " + (index + 1)}</h3>
                <p>{entry.lab || "Laboratorio sin informar"} · {"Muestreo · "+(entry.sampleDate || "Sin informar")+" · Análisis · "+(entry.analysisDate || "Sin informar")}</p>
                <p>{entry.samples.length} {entry.samples.length === 1 ? "muestra" : "muestras"} · {parameters.length} {parameters.length === 1 ? "parámetro" : "parámetros"}</p>
                <p>{depths.join(" · ") || "Profundidad sin informar"} · {count} {count === 1 ? "resultado transcrito" : "resultados transcritos"}</p>
                <p>{entry.files.length} documentos adjuntos · {studyReviewLabel(entry)}{entry.files.length > 0 && (" · " + entry.files.map(({ name }) => name).join(", "))}</p>
              </div>
              <button type="button" className="work-button" aria-expanded={study?.id === entry.id}
                aria-label={"Ver detalle de " + (entry.report || "Estudio " + (index + 1))} onClick={() => {
                  setStudyId(study?.id === entry.id ? "" : entry.id);
                  setSampleId("");
                }}>{study?.id === entry.id ? "Ocultar detalle" : "Ver detalle"}</button>
            </li>;
          })}
        </ul>}
      </Panel>
      {study && <Panel title="Detalle del informe">
          <Status>{studyReviewLabel(study)}</Status>
          <LocalFiles key={study.id} label="Seleccionar informe" files={study.files} onChange={(files) => update({ files })} />
          <h3>Datos del informe</h3>
          <FieldGrid fields={reportFields} values={study} onChange={(key, value) => update({ [key]: value })}
            errors={study.sampleDate && study.analysisDate && study.analysisDate < study.sampleDate ? { analysisDate: "La fecha del análisis es anterior al muestreo." } : {}} />
          {studyHasResult(study) && <Field label="Estado de revisión" value={study.review || "Transcrito por el usuario"}
            options={reviewStates} onChange={(review) => update({ review })} />}
      </Panel>}
      {study && <Panel title="Muestras del informe" description="Registrá cada intervalo de profundidad en su propia muestra."
        actions={<button type="button" className="work-button" onClick={() => {
          const id = crypto.randomUUID();
          update({ samples: [...study.samples, { id, results: [] }] });
          setSampleId(id);
        }}>Agregar muestra</button>}>
        {sample ? <>
          <Field label="Muestra activa" value={sample.id} onChange={setSampleId}
            options={study.samples.map(({ id, name }, index) => [id, name || `Muestra ${index + 1}`])} />
          <SampleEditor key={sample.id} sample={sample} update={(patch) => update({ samples: updateRecord(study.samples, sample.id, patch) })} />
        </> : <p className="work-empty">Sin muestras registradas.</p>}
      </Panel>}
      {study && <Panel title="Ficha técnica y comparación"><StudyResults studies={[study]} /></Panel>}
    </>
  );
}

