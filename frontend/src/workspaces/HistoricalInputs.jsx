import { useState } from "react";
import { DataTable, Field, FieldGrid, Panel, Status } from "./Controls.jsx";
import { historicalWindows } from "./preparation.js";
export default function HistoricalInputs({ draft, patch }) {
  const config = draft.historical ?? {};
  const [year, setYear] = useState("");
  const [error, setError] = useState("");
  const check = historicalWindows(config);
  const years = config.start_years ?? [];
  return <Panel title="Períodos históricos de análisis" description="Ventanas de dos años para preparar un análisis futuro.">
    <p className="work-note">Referencia del modelo · 1 de julio. Confirmá explícitamente el día y mes de tu análisis.</p>
    <FieldGrid fields={[["start_day","Día de inicio",{inputMode:"numeric"}],["start_month","Mes de inicio",{options:Array.from({length:12},(_,i)=>[String(i+1),String(i+1)])}]]}
      values={config} errors={check.errors} onChange={(key,value)=>patch({historical:{...config,[key]:value}})}/>
    <div className="work-inline"><Field label="Año histórico de inicio" value={year} onChange={setYear} inputMode="numeric" error={error}/>
    <button type="button" className="work-button" onClick={()=>{
      if (!/^\d{4}$/.test(year) || Number(year)<1900 || Number(year)>2200) return setError("Ingresá un año entre 1900 y 2200.");
      if (years.includes(Number(year))) return setError("Este año ya está seleccionado.");
      if (years.length>=10) return setError("Se admiten hasta diez años.");
      patch({historical:{...config,start_years:[...years,Number(year)]}});setYear("");setError("");
    }}>Agregar año</button></div>
    {check.errors.start_years && <Status>{check.errors.start_years}</Status>}
    <DataTable caption="Ventanas históricas declaradas" columns={["Año","Inicio","Fin","Validación temporal","Clima","Acción"]}
      rows={check.rows.map(row=>({id:row.year,cells:[row.year,row.start,row.end,row.error || "Ventana finalizada",
        row.warning || "Disponibilidad pendiente de verificación",
        <button type="button" className="work-button" onClick={()=>patch({historical:{...config,start_years:years.filter(y=>y!==row.year)}})}>Quitar {row.year}</button>]}))}/>
    <Status>Resultados científicos no disponibles. Las series climáticas requieren una futura etapa de ejecución.</Status>
  </Panel>;
}

