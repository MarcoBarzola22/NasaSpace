import { describe, expect, it } from "vitest";
import { historicalWindows, rangeError, soilErrors } from "../src/workspaces/preparation.js";
import { cropCodes, cropIssues } from "../src/workspaces/strategies/agronomy.js";
import { blankStage, blankStrategy, saveStrategy, duplicateStrategy } from "../src/workspaces/strategies/model.js";
const soil={fieldCapacity:{value:"0.3",unit:"m³/m³"},wiltingPoint:{value:"0.1",unit:"m³/m³"},depth:{value:"1.5",unit:"m"},availableWater:{value:"0",unit:"%"}};
describe("Local agronomic preparation",()=>{
 it("accepts zero available water and a coherent soil",()=>expect(soilErrors(soil)).toEqual({}));
 it.each([["fieldCapacity","0"],["fieldCapacity","1.1"],["wiltingPoint","0.3"],["depth","0"],["depth","3.1"],["availableWater","101"],["availableWater","-1"]])("rejects %s = %s",(key,value)=>expect(soilErrors({...soil,[key]:{...soil[key],value}})[key]).toBeTruthy());
 it("preserves original wrong units as an error",()=>expect(soilErrors({...soil,depth:{value:"100",unit:"cm"}}).depth).toContain("Unidad"));
 it.each(["0","100"])("accepts residue endpoint %s",value=>expect(rangeError(value,0,100)).toBeUndefined());
 it("creates two-year windows without climate data",()=>expect(historicalWindows({start_day:"1",start_month:"7",start_years:[2010,2015]},"2026-11-15").rows).toMatchObject([{start:"2010-07-01",end:"2012-06-30"},{start:"2015-07-01",end:"2017-06-30"}]));
 it.each([{start_day:29,start_month:2,start_years:[2010]},{start_day:1,start_month:7,start_years:[2010,2010]},{start_day:1,start_month:7,start_years:[2026]}])("rejects invalid or unfinished windows %j",config=>expect(historicalWindows(config,"2026-11-15").valid).toBe(false));
 it("warns about coverage without rejecting a historical date",()=>expect(historicalWindows({start_day:1,start_month:7,start_years:[1980]},"2026-11-15").rows[0].warning).toBeTruthy());
 it("centralizes catalog identifiers",()=>expect(cropCodes).toMatchObject({"soy-first":"soybean_first","soy-second":"soybean_second",rye:"rye_cover"}));
 const stage={...blankStage("stage"),cropId:"maize",agronomy:{ym:{value:"10",unit:"t/ha"},residue:{value:"40",unit:"%"},sowing:{window_year:"1",day:"15",month:"10"}}};
 it("uses documented durations for maize without copying them into declarations",()=>expect(cropIssues(stage)).toEqual({}));
 it.each(["soy-second","rye"])("requires all four durations for %s",cropId=>expect(cropIssues({...stage,cropId}).durations).toBeTruthy());
 it("rejects partially overridden durations",()=>expect(cropIssues({...stage,agronomy:{...stage.agronomy,durations:{initial:"20"}}}).durations).toBeTruthy());
 it("does not require grain yield for cover",()=>expect(cropIssues({...stage,kind:"cover",cropId:"rye",agronomy:{...stage.agronomy,ym:undefined}}).ym).toBeUndefined());
 it("unknown crop remains without model",()=>expect(cropIssues({...stage,cropId:"custom"}).catalog).toBeTruthy());
 it("validates root ordering against references",()=>expect(cropIssues({...stage,agronomy:{...stage.agronomy,advanced:{root_depth_initial_m:{value:"2",unit:"m"}}}}).root_depth_initial_m).toBeTruthy());
 it("retains declarations during saving and duplication",()=>{
   const strategy={...blankStrategy("P-02","custom"),name:"Test",stages:[stage],initialResidue:{value:"30",unit:"%"}};
   expect(saveStrategy(strategy).initialResidue).toEqual(strategy.initialResidue);
   let counter=0;
   const copy=duplicateStrategy(strategy,()=>String(++counter));
   expect(copy.stages[0].agronomy).toEqual(stage.agronomy);
   expect(copy.id).not.toBe(strategy.id);
 });
});

