import { DataTable, Panel } from "./Controls.jsx";
import { soilErrors, historicalWindows, numberValue } from "./preparation.js";
import { strategyIssues } from "./strategies/agronomy.js";
import { validateStrategy } from "./strategies/model.js";
import { economicEntryIssue } from "./economics.js";
import { CostAssignment } from "./SimulationResults.jsx";
export function preparationRows(draft, economy) {
 const latitude=numberValue(draft.identity.latitude), longitude=numberValue(draft.identity.longitude);
 const coordinates=latitude===null || longitude===null ? "Incompleto" : Math.abs(latitude)>90 || Math.abs(longitude)>180 ? "Con errores"
   : Math.abs(latitude)>60 || draft.identity.production==="Con riego" ? "Fuera del alcance del modelo" : "Completo según el formulario";
 const soil=soilErrors(draft.soil);
 const windows=historicalWindows(draft.historical);
 const economic=[...draft.prices,...draft.costs];
 const costUnits=new Set(draft.costs.map(row=>(row.unit ?? "").split("/").at(-1)).filter(Boolean));
 const currencies=new Set(economic.map(row=>row.currency).filter(Boolean));
 return [
  ["Coordenadas","#parcela/identificacion",coordinates],
  ["Datos hídricos","#parcela/suelo",Object.keys(soil).length ? "Incompleto o con errores" : Object.values(draft.soil).some(row=>row.basis==="Supuesto") ? "Basado en supuestos" : "Completo según el formulario"],
  ["Períodos históricos","#estrategias/clima",windows.valid ? "Completo según el formulario" : "Incompleto o con errores"],
  ["Estrategias","#estrategias/biblioteca",draft.strategies.length===0 ? "Sin información" : draft.strategies.every(s=>validateStrategy(s).valid && !strategyIssues(s).length) ? "Entradas agronómicas completas según el formulario" : "Entradas agronómicas pendientes"],
  ["Entradas económicas","#economia/precios",currencies.size>1 ? "Monedas incompatibles" : costUnits.size>1 ? "Bases de costos incompatibles · Revisar unidades" : !draft.prices.length || !draft.costs.length || economic.some(economicEntryIssue) ? "Economía pendiente de datos"
    : !economy ? "Entradas registradas" : economy.unassignedCosts.length ? economy.unassignedCosts.length + " costo(s) fuera del cálculo · Revisar vínculo o unidad"
    : "Entradas registradas · " + economy.assignedCosts.length + " costo(s) entran al cálculo"],
 ];
}
export default function PreparationReview({draft, economy}) {
 return <Panel title="Preparación para simular" description="Validación del formulario antes de ejecutar el motor. La revisión técnica de las entradas corresponde al profesional.">
   <DataTable caption="Preparación del análisis" columns={["Categoría","Estado"]} rows={preparationRows(draft, economy).map(([label,href,status])=>({id:label,cells:[<a className="work-link" href={href}>{label}</a>,status]}))}/>
   {economy?.unassignedCosts.length > 0 && <CostAssignment economy={economy} onlyExcluded />}
 </Panel>;
}

