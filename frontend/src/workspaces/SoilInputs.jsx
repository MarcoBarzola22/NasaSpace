
import { FieldGrid, Panel, Status } from "./Controls.jsx";
import { soilDefinitions, soilErrors, numberValue } from "./preparation.js";
export default function SoilInputs({ draft, patch }) {
  const errors = soilErrors(draft.soil);
  function property(key, label, unit) {
    const record = draft.soil[key] ?? {};
    return <fieldset className="work-fieldset" key={key}><legend>{label}{unit && " (" + unit + ")"}</legend>
      <FieldGrid fields={[["value","Valor"],["unit","Unidad original"],["source","Fuente"],["date","Fecha",{type:"date"}],
        ["basis","Condición",{options:["Medición","Dato declarado","Supuesto"]}]]} values={record} errors={{value:errors[key]}}
        onChange={(field,value)=>patch({soil:{...draft.soil,[key]:{...record,[field]:value}}})}/>
      {key === "depth" && record.unit === "cm" && numberValue(record.value) !== null &&
        <button type="button" className="work-button" onClick={()=>patch({soil:{...draft.soil,depth:{
          ...record, original:{value:record.value,unit:record.unit}, value:String(numberValue(record.value)/100),unit:"m"}}})}>Convertir explícitamente cm a m</button>}
      {record.original && <p className="work-note">Original conservado · {record.original.value} {record.original.unit}</p>}
    </fieldset>;
  }
  return <Panel title="Datos hídricos esenciales" description="Registrá valores y unidades originales con su procedencia.">
    <p className="work-note">Coordenadas declaradas · {draft.identity.latitude || "Sin latitud"} / {draft.identity.longitude || "Sin longitud"} · <a href="#parcela/identificacion">Editar coordenadas</a></p>
    {Math.abs(Number(draft.identity.latitude)) > 60 && <Status tone="warning">Latitud fuera del alcance operativo de ±60°.</Status>}
    {soilDefinitions.slice(0,4).map(([key,label,unit])=>property(key,label,unit))}
    <p className="work-note">Agua disponible (%) expresa la proporción disponible. La humedad inicial original se conserva en otros registros.</p>
    {errors.fallowKc && <Status tone="warning">Kc base del barbecho · {errors.fallowKc}</Status>}
    <details className="work-details"><summary>Parámetros avanzados y otros registros</summary>
      <p className="work-note">Kc base del barbecho · Predeterminado documentado del modelo 0,20. El campo vacío conserva la ausencia de una declaración.</p>
      {property("fallowKc","Kc base del barbecho","adimensional")}
      {[["texture","Textura"],["capacity","Capacidad de almacenamiento hídrico"],["moisture","Humedad inicial"],["rootDepth","Profundidad radicular"]].map(([key,label])=>property(key,label))}
    </details>
  </Panel>;
}
