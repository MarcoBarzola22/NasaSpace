import { useRef, useState } from "react";
import { cropLabels } from "../data/demo.js";
import { formatNumber, metrics } from "../data/presentation.js";

function ComparisonChart({ metric, rotations, selectedId }) {
  return (
    <>
      <div className="chart-axis" aria-hidden="true">
        {metric.ticks.map((tick) => <span key={tick}>{tick}</span>)}
      </div>
      <div className="barrows">
        {rotations.map((rotation) => {
          const isSelected = rotation.id === selectedId;
          return (
            <div className={isSelected ? "barrow selected" : "barrow"} key={rotation.id}>
              <div className="name">Estrategia {rotation.id}<small>{rotation.label}</small></div>
              <div className="bar-track" aria-hidden="true">
                <div className={isSelected ? "bar selected" : "bar"} style={{ width: rotation[metric.widthKey] }} />
              </div>
              <div className="bar-val">{metric.format(rotation[metric.valueKey])}</div>
            </div>
          );
        })}
      </div>
      <div className="axis-caption">
        <span><b>Eje X:</b> {metric.axis}</span><span><b>Eje Y:</b> estrategias A, B y C</span>
      </div>
    </>
  );
}

function ProductionTable({ rotations, selectedId }) {
  return (
    <>
      <table className="production-table">
        <thead>
          <tr>
            <th scope="col">Alternativa</th>
            {cropLabels.map((label) => <th scope="col" key={label}>{label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rotations.map(({ id, label, yields }) => (
            <tr className={id === selectedId ? "sel" : undefined} key={id}>
              <td>{id} · {label}</td>
              {yields.map((value, index) => (
                <td key={cropLabels[index]}>{value === null ? "—" : formatNumber(value)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="axis-caption">Tabla: columnas = cultivos, filas = estrategias. Unidad = toneladas por hectárea (t/ha). No es un gráfico de ejes.</div>
    </>
  );
}

export default function MetricsPanel({ rotations, selectedId }) {
  const [metricIndex, setMetricIndex] = useState(0);
  const tabRefs = useRef([]);
  const metric = metrics[metricIndex];

  function handleTabKeyDown(event, index) {
    const nextIndex = {
      ArrowLeft: (index + metrics.length - 1) % metrics.length,
      ArrowRight: (index + 1) % metrics.length,
      Home: 0,
      End: metrics.length - 1,
    }[event.key];

    if (typeof nextIndex !== "number") return;
    event.preventDefault();
    setMetricIndex(nextIndex);
    tabRefs.current[nextIndex].focus();
  }

  return (
    <section id="metrics" className="card metrics-card" aria-label="Comparación de indicadores">
      <div className="metrics-top">
        <div>
          <div className="eyebrow">02 / Resultados comparados</div>
          <h2>Explorar por indicador</h2>
        </div>
        <div role="tablist" className="tablist" aria-label="Indicador comparado">
          {metrics.map(({ id, label }, index) => (
            <button type="button" className="tab" role="tab" key={id} id={`tab-${id}`}
              aria-controls="metric-panel" aria-selected={index === metricIndex}
              tabIndex={index === metricIndex ? 0 : -1}
              ref={(element) => { tabRefs.current[index] = element; }}
              onClick={() => setMetricIndex(index)}
              onKeyDown={(event) => handleTabKeyDown(event, index)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <p className="metric-sub">{metric.description}</p>
      <div className="metric-view" id="metric-panel" role="tabpanel" aria-labelledby={`tab-${metric.id}`} tabIndex={0}>
        <div className="chart-title">{metric.title}</div>
        {metric.id === "production"
          ? <ProductionTable rotations={rotations} selectedId={selectedId} />
          : <ComparisonChart metric={metric} rotations={rotations} selectedId={selectedId} />}
      </div>
    </section>
  );
}

