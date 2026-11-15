import { formatNumber } from "../data/presentation.js";

const rows = [
  ["income", "Ingresos ($/ha, 2 años)"],
  ["cost", "Costos directos ($/ha, 2 años)"],
  ["margin", "Margen bruto ($/ha, 2 años)"],
  ["water", "Agua ilustrativa al inicio de soja (mm)"],
];

export default function PrintSummary({ rotations }) {
  return (
    <div className="print-only">
      <table className="print-table">
        <caption>Valores ficticios de prueba — resumen de las tres alternativas</caption>
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

