import { useRef } from "react";
import { marginAxis } from "../workspaces/economics.js";
import { formatNumber, metrics } from "../data/presentation.js";

export function ComparisonChart({ metric, rotations, selectedId }) {
  const signed = metric.id === "economy";
  const scale = signed ? marginAxis(rotations.map((rotation) => rotation[metric.valueKey])) : null;
  const ticks = scale ? [...new Set([scale.minimum, 0, scale.maximum])] : metric.ticks;
  return (
    <>
      <div className={signed ? "chart-axis signed-axis" : "chart-axis"} aria-hidden="true">
        {ticks.map((tick) => <span key={tick} style={signed ? { left: `${scale.position(tick)}%` } : undefined}>
          {signed ? formatNumber(tick) : tick}
        </span>)}
      </div>
      <div className="barrows">
        {rotations.map((rotation) => {
          const isSelected = rotation.id === selectedId;
          const value = rotation[metric.valueKey];
          const point = scale?.position(value);
          return (
            <div className={isSelected ? "barrow selected" : "barrow"} key={rotation.id}>
              <div className="name">{rotation.isTemplate === false ? rotation.label : `Estrategia ${rotation.id}`}{rotation.isTemplate !== false && <small>{rotation.label}</small>}</div>
              <div className={signed ? "bar-track signed-track" : "bar-track"} aria-hidden="true">
                {signed && <i className="chart-zero" style={{ left: `${scale.zero}%` }} />}
                <div className={`bar${isSelected ? " selected" : ""}${signed && value < 0 ? " negative" : ""}`}
                  style={signed ? { left: `${Math.min(point, scale.zero)}%`, width: `${Math.abs(point - scale.zero)}%` }
                    : { width: rotation[metric.widthKey] }} />
              </div>
              <div className="bar-val">{signed ? formatNumber(value) : metric.format(value)}</div>
            </div>
          );
        })}
      </div>
      <div className="axis-caption">
        <span><b>Eje X:</b> {metric.axis}</span><span><b>Eje Y:</b> estrategias de la comparación</span>
      </div>
    </>
  );
}

function ProductionTable({ rotations, selectedId }) {
  const headings = ["Maíz", "Trigo", "Soja 1.ª", "Soja (general)", "Soja 2.ª"];
  return (
    <>
      <div className="work-table-scroll" tabIndex={0} role="region" aria-label="Rendimientos por cultivo"><table className="production-table">
        <thead>
          <tr>
            <th scope="col">Alternativa</th>
            {headings.map((label) => <th scope="col" key={label}>{label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rotations.map(({ id, label, yields }) => (
            <tr className={id === selectedId ? "sel" : undefined} key={id}>
              <td>{id} · {label}</td>
              {[yields[0], yields[1], id === "A" ? yields[2] : null, id === "B" ? yields[2] : null, id === "C" ? yields[2] : null].map((value, index) => (
                <td key={headings[index]}>{value === null ? "—" : formatNumber(value)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table></div>
      <div className="axis-caption">Tabla: columnas = cultivos, filas = estrategias. Unidad = toneladas por hectárea (t/ha). No es un gráfico de ejes.</div>
    </>
  );
}

export default function MetricsPanel({ rotations, selectedId, parcelName, metricId = "economy", onMetric, allowedMetrics }) {
  const tabs = allowedMetrics ? metrics.filter(({ id }) => allowedMetrics.includes(id)) : metrics;
  const metricIndex = Math.max(0, tabs.findIndex(({ id }) => id === metricId));
  const tabRefs = useRef([]);
  const metric = tabs[metricIndex];

  function handleTabKeyDown(event, index) {
    const nextIndex = {
      ArrowLeft: (index + tabs.length - 1) % tabs.length,
      ArrowRight: (index + 1) % tabs.length,
      Home: 0,
      End: tabs.length - 1,
    }[event.key];

    if (typeof nextIndex !== "number") return;
    event.preventDefault();
    onMetric(tabs[nextIndex].id);
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
          {tabs.map(({ id, label }, index) => (
            <button type="button" className="tab" role="tab" key={id} id={`tab-${id}`}
              aria-controls="metric-panel" aria-selected={index === metricIndex}
              tabIndex={index === metricIndex ? 0 : -1}
              ref={(element) => { tabRefs.current[index] = element; }}
              onClick={() => onMetric(id)}
              onKeyDown={(event) => handleTabKeyDown(event, index)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <p className="metric-sub">{metric.id !== "production" && <strong>{parcelName} · </strong>}{metric.description}</p>
      <div className="metric-view" id="metric-panel" role="tabpanel" aria-labelledby={`tab-${metric.id}`} tabIndex={0}>
        <div className="chart-title">{metric.title}</div>
        {metric.id === "production"
          ? <ProductionTable rotations={rotations} selectedId={selectedId} />
          : <ComparisonChart metric={metric} rotations={rotations} selectedId={selectedId} />}
      </div>
    </section>
  );
}
