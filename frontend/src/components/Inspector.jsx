import { cropLabels, horizonMonths } from "../data/demo.js";
import { formatMoney, formatNumber } from "../data/presentation.js";

function EconomicOverview({ rotation }) {
  return (
    <section className="card economic" aria-label="Resumen económico">
      <div className="small-label">Margen bruto · 2 años</div>
      <div className="main-num">{formatMoney(rotation.margin)}</div>
      <div className="num-sub">ARS/ha · Valores de demostración</div>
      <div className="two-col">
        <div><span>Ingresos</span><strong>{formatMoney(rotation.income)}</strong></div>
        <div><span>Costos directos</span><strong>{formatMoney(rotation.cost)}</strong></div>
      </div>
      <div className="stackbar" role="img" aria-label="Composición del ingreso entre costos directos y margen bruto">
        <div className="costs" style={{ width: rotation.costWidth }} />
        <div className="margin" />
      </div>
      <div className="stack-legend">
        <span><i className="legend-dot" style={{ background: "#a8906b" }} />Costos</span>
        <span><i className="legend-dot" style={{ background: "var(--lime)" }} />Margen</span>
      </div>
    </section>
  );
}

function StatAccordion({ title, unit, color, initiallyOpen, children }) {
  return (
    <details className="stat-accordion" open={initiallyOpen}>
      <summary>
        {title}
        {unit && <span style={{ color, fontSize: 10, marginLeft: "auto" }}>{unit}</span>}
      </summary>
      <div className="stat-body">{children}</div>
    </details>
  );
}

function ResourceBar({ label, value, width, color, children }) {
  return (
    <>
      <div className="stat-kv"><span>{label}</span><strong>{value}</strong></div>
      <div className="thin-bar" aria-hidden="true"><div style={{ width, background: color }} /></div>
      <p className="stat-hint">{children}</p>
    </>
  );
}

export default function Inspector({ rotations, selected, onSelect }) {
  return (
    <aside className="inspector" aria-label="Inspector de estrategia">
      <div className="sticky">
        <div className="inspector-top">
          <span className="eyebrow">Inspector / Estrategia</span>
          <span className="pill-muted">MUESTRA</span>
        </div>
        <h2>{selected.name}</h2>
        <p style={{ fontSize: 11, color: "var(--muted)", margin: "7px 0 0" }}>
          Seleccioná A, B o C para inspeccionar sus indicadores ficticios.
        </p>
        <div className="inspector-tabs">
          {rotations.map(({ id }) => (
            <button key={id} type="button" className="select-rot" aria-pressed={id === selected.id}
              onClick={() => onSelect(id)}>{id}</button>
          ))}
        </div>
        <EconomicOverview rotation={selected} />
        <div className="ins-section">
          <p className="ins-title">ESTADÍSTICAS DE LA ESTRATEGIA <span style={{ color: "var(--subtle)" }}>↧</span></p>
          <StatAccordion title="Agua del suelo" unit="mm" color="var(--blue)" initiallyOpen>
            <ResourceBar label="Al inicio de soja*" value={`${formatNumber(selected.water)} mm`} width={selected.waterWidth}>
              Escala ilustrativa 0–160 mm. No es una lectura de sensor ni una estimación real.
            </ResourceBar>
          </StatAccordion>
          <StatAccordion title="Suelo y cobertura" unit="meses" color="var(--soy)" initiallyOpen>
            <ResourceBar label="Con cultivo vivo*" value={`${selected.cover}/${horizonMonths} meses`} width={selected.coverWidth} color="#94bd90">
              No equivale a suelo desprotegido: los rastrojos pueden aportar cobertura.
            </ResourceBar>
          </StatAccordion>
          <StatAccordion title="Producción por cultivo" unit="t/ha" color="var(--wheat)">
            {cropLabels.map((label, index) => (
              <div className="stat-kv" key={label}>
                <span>{label}</span><strong>{selected.yields[index] === null ? "No corresponde" : `${formatNumber(selected.yields[index])} t/ha*`}</strong>
              </div>
            ))}
            <p className="stat-hint">Sin sumar toneladas de cultivos distintos.</p>
          </StatAccordion>
          <StatAccordion title="Supuestos y limitaciones">
            <p className="stat-desc">Los resultados de esta maqueta no provienen de un modelo. Para una comparación real son necesarios suelo, humedad inicial, calendarios validados y parámetros de los cultivos.</p>
            <p className="stat-hint">No se estiman erosión en toneladas, carbono ni probabilidades futuras.</p>
          </StatAccordion>
        </div>
        <div className="source-box">
          <strong>◇ FUENTE ACTUAL: DEMOSTRACIÓN</strong><br />
          NASA POWER no conectado · FAO-56/FAO-33 no ejecutados · Precios y rendimientos simulados para revisar el diseño.
        </div>
      </div>
    </aside>
  );
}

