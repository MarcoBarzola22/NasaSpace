export default function RotationTimeline({ rotations, selectedId, onSelect }) {
  return (
    <section id="rotations" className="card timeline-card" aria-label="Comparación temporal de rotaciones">
      <div className="section-title">
        <div>
          <div className="eyebrow">01 / Secuencia agrícola</div>
          <h2>Dos campañas, tres estrategias</h2>
        </div>
        <div className="small-info">Misma parcela · Mismo horizonte<br />Seleccioná una estrategia</div>
      </div>
      <div className="timeline-head">
        <span />
        <div className="timeline-labels">
          <div>AÑO 1 · VERANO</div><div>INVIERNO</div><div>AÑO 2 · VERANO</div>
        </div>
      </div>
      <div className="rotation-list">
        {rotations.map(({ id, label, caption, phases }) => (
          <button type="button" key={id} className={id === selectedId ? "rotation-row active" : "rotation-row"}
            aria-pressed={id === selectedId} onClick={() => onSelect(id)}>
            <span className="rotation-id">
              <span className="letter">{id}</span>
              <span><strong>{label}</strong><small>{caption}</small></span>
            </span>
            <span className="phases">
              {phases.map(({ tone, name, note }) => (
                <span className={`phase ${tone}`} key={tone}><strong>{name}</strong><span>{note}</span></span>
              ))}
            </span>
          </button>
        ))}
      </div>
      <div className="timeline-foot">
        <div className="legend">
          <span><i className="legend-dot dot-1" />Maíz</span>
          <span><i className="legend-dot dot-2" />Soja</span>
          <span><i className="legend-dot dot-3" />Trigo</span>
          <span><i className="legend-dot dot-4" />Barbecho</span>
        </div>
        <div><strong>Esquema</strong> · No representa duraciones ni fechas reales</div>
      </div>
    </section>
  );
}

