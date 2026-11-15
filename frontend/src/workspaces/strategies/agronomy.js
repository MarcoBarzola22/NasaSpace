import catalog from "../../data/crop-reference.json";
import { numberValue, rangeError, recurringDate } from "../preparation.js";
export const cropCodes = {maize:"maize","soy-first":"soybean_first","soy-second":"soybean_second",wheat:"wheat",rye:"rye_cover"};
export const durationKeys = ["initial","development","mid","late"];
export const advancedFields = [
 ["kc_initial","Kc inicial","adimensional",0,2],["kc_mid","Kc medio","adimensional",0,2],["kc_end","Kc final","adimensional",0,2],
 ["root_depth_initial_m","Profundidad radicular inicial","m",0,Infinity,true],
 ["root_depth_max_m","Profundidad radicular máxima","m",0,Infinity,true],
 ["depletion_fraction_p","Fracción de agotamiento p","adimensional",0,1,true,true],["ky","Factor de respuesta Ky","adimensional",0,2],
];
export function cropReference(stage) { return catalog.crops.find(c=>c.crop_code===cropCodes[stage.cropId]); }
export function cropIssues(stage) {
 const data=stage.agronomy ?? {}, errors={};
 if (!["commercial","cover"].includes(stage.kind)) return errors;
 const reference=cropReference(stage);
 if (!reference) errors.catalog="Sin modelo disponible para esta especie.";
 if(stage.kind==="commercial") {
   const issue=rangeError(data.ym?.value,0,30,true); if(issue) errors.ym=issue;
   if(data.ym?.value && data.ym.unit!=="t/ha") errors.ym="La unidad requerida es t/ha.";
 }
 const sowing=data.sowing ?? {};
 if(!["1","2"].includes(String(sowing.window_year)) || !recurringDate(sowing.day,sowing.month)) errors.sowing="Completá campaña relativa, día y mes válidos de siembra.";
 const manual=durationKeys.some(k=>String(data.durations?.[k]??"").trim());
 if(manual || !reference?.reference_values.stage_lengths_days.value)
   if(!durationKeys.every(k=>Number.isInteger(numberValue(data.durations?.[k])) && numberValue(data.durations[k])>0 && numberValue(data.durations[k])<=365))
     errors.durations="Completá las cuatro duraciones con enteros de 1 a 365 días.";
 const residue=rangeError(data.residue?.value,0,100);if(residue) errors.residue=residue;
 if(data.residue?.value && data.residue.unit!=="%") errors.residue="La unidad requerida es %.";
 for(const [key,,unit,min,max,exMin,exMax] of advancedFields) {
   if(key==="ky" && stage.kind==="cover") continue;
   const entry=data.advanced?.[key];
   if(entry?.value !== undefined && String(entry.value).trim()) {
     const issue=rangeError(entry.value,min,max,exMin,exMax);
     if(issue || entry.unit!==unit) errors[key]=issue || "Revisá la unidad requerida " + unit + ".";
   }
 }
 const root=(key)=>numberValue(data.advanced?.[key]?.value) ?? reference?.reference_values[key]?.value;
 if(root("root_depth_initial_m")>root("root_depth_max_m")) errors.root_depth_initial_m="La raíz inicial no puede superar la máxima.";
 return errors;
}
export function strategyIssues(strategy) {
 const issues=strategy.stages.flatMap(stage=>Object.entries(cropIssues(stage)).map(([key,message])=>({stageId:stage.id,key,message})));
 const residue=rangeError(strategy.initialResidue?.value,0,100);
 if(strategy.initialResidue?.value && strategy.initialResidue.unit!=="%") issues.unshift({key:"initialResidue",message:"La unidad requerida para rastrojos es %."});
 if(residue) issues.unshift({key:"initialResidue",message:"Cobertura inicial de rastrojos · "+residue});
 return issues;
}

