import { FieldGrid, Status } from "../Controls.jsx";
import { advancedFields, cropIssues, cropReference, durationKeys } from "./agronomy.js";
export function DeclaredParameter({ label, unit, value = {}, onChange, error, reference }) {
 return <fieldset className="work-fieldset"><legend>{label} ({unit})</legend>
   {reference && <p className="work-note">{reference.value === null ? "Sin referencia disponible" : "Referencia disponible · "+reference.value+" "+reference.unit} · {reference.status} · {reference.source} {reference.note}</p>}
   <FieldGrid fields={[["value","Valor declarado"],["unit","Unidad"],["source","Fuente"],
     ["basis","Procedencia",{options:["Medición declarada","Dato declarado","Supuesto del usuario","Referencia documentada"]}],["notes","Observaciones"]]}
     values={value} errors={{value:error}} onChange={(key,next)=>onChange({...value,[key]:next})}/>
 </fieldset>;
}
export default function AgronomicInputs({stage, update}) {
 const data=stage.agronomy ?? {}, reference=cropReference(stage), errors=cropIssues(stage);
 const set=(key,value)=>update({agronomy:{...data,[key]:value}});
 if(!["commercial","cover"].includes(stage.kind)) return <p className="work-note">El barbecho y los manejos conservan sus operaciones y observaciones sobre rastrojos.</p>;
 return <div className="agronomic-inputs">
   {Object.keys(errors).length>0 && <Status tone="warning">Preparación incompleta · {Object.values(errors).join(" ")}</Status>}
   {stage.kind==="commercial" && <>
     <p className="work-note">Ym representa el rendimiento de referencia sin limitación hídrica. El motor estima con él el rendimiento de cada escenario histórico.</p>
     <DeclaredParameter label="Rendimiento de referencia sin limitación hídrica" unit="t/ha" value={data.ym} error={errors.ym} onChange={value=>set("ym",value)}/>
   </>}
   <h3>Siembra relativa a la ventana histórica</h3>
   <FieldGrid fields={[["window_year","Campaña relativa",{options:[["1","Primera"],["2","Segunda"]]}],
     ["day","Día de siembra",{inputMode:"numeric"}],["month","Mes de siembra",{inputMode:"numeric"}]]}
     values={data.sowing ?? {}} errors={{day:errors.sowing}} onChange={(key,value)=>set("sowing",{...data.sowing,[key]:value})}/>
   <p className="work-note">La campaña relativa requiere confirmación. Las fechas de inicio y finalización del editor son declaraciones del calendario.</p>
   <DeclaredParameter label="Cobertura de rastrojos posterior al cultivo" unit="%" value={data.residue} error={errors.residue} onChange={value=>set("residue",value)}/>
   <details className="work-details"><summary>Duraciones del ciclo del cultivo</summary>
     <p className="work-note">{reference?.reference_values.stage_lengths_days.value
       ? "Referencia disponible · "+JSON.stringify(reference.reference_values.stage_lengths_days.value)+" días · "+reference.reference_values.stage_lengths_days.source
       : "Sin referencia completa. Declarar las cuatro duraciones."}</p>
     <FieldGrid fields={durationKeys.map((key,i)=>[key,["Inicial","Desarrollo","Media","Final"][i]+" (días)",{inputMode:"numeric"}])}
       values={data.durations ?? {}} errors={{initial:errors.durations}} onChange={(key,value)=>set("durations",{...data.durations,[key]:value})}/>
     <FieldGrid fields={[["durationSource","Fuente de las duraciones"]]} values={data} onChange={set}/>
   </details>
   {reference && <details className="work-details"><summary>Parámetros agronómicos avanzados</summary>
     <p className="work-note">Catálogo documental 1.0 · revisado 15/11/2026. Las referencias conservadas requieren revisión para la parcela.</p>
     {advancedFields.filter(([key])=>key!=="ky" || stage.kind==="commercial").map(([key,label,unit])=>
       <DeclaredParameter key={key} label={label+" · "+key} unit={unit} value={data.advanced?.[key]} reference={reference.reference_values[key]}
         error={errors[key]} onChange={value=>set("advanced",{...data.advanced,[key]:value})}/>)}
   </details>}
 </div>;
}

