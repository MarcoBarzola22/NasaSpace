import { formatNumber } from "../data/presentation.js";
import { RangeTables, WarningList } from "../workspaces/SimulationResults.jsx";
import { DEMO_LABEL } from "../workspaces/simulation.js";

const rows = [
  ["income", "Ingresos ($/ha, 2 años)"],
  ["cost", "Costos directos ($/ha, 2 años)"],
  ["margin", "Margen bruto ($/ha, 2 años)"],
  ["deficit", "Déficit hídrico ficticio (mm)"],
];

/** Printed summary: the ranges of the engine when it was run, the demo fixtures otherwise. */
export default function PrintSummary({ rotations, parcel, simulation, strategies }) {
  if (simulation?.response) return (
    <div className="print-only">
      <RangeTables run={simulation.run} strategies={strategies} />
      <WarningList response={simulation.response} />
    </div>
  );
  return (
    <div className="print-only">
      <table className="print-table">
        <caption>{DEMO_LABEL} · Valores ficticios de prueba — {parcel.name} · {parcel.id}</caption>
        <thead>
          <tr>
            <th scope="col">Indicador</th>
            {rotations.map(({ id, label }) => <th scope="col" key={id}>{id} · {label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map(([key, label]) => (
            <tr key={key}>
              <td>{label}</td>
              {rotations.map((rotation) => <td key={rotation.id}>{formatNumber(rotation[key])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
