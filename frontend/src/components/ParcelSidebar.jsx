import { parcelFacts } from "../data/demo.js";

export default function ParcelSidebar({ onReview }) {
  return (
    <aside className="sidebar" aria-label="Contexto de la parcela">
      <div className="brand">
        <span className="brand-mark">A</span>
        <div>agro<b>DSS</b><small>DECISION SUPPORT</small></div>
      </div>
      <div className="side-section">
        <div className="side-heading"><h3>Parcela de análisis</h3><span>01 / 01</span></div>
        <div className="parcel">
          <div className="parcel-art" role="img" aria-label="Ilustración abstracta del lote">
            <svg viewBox="0 0 240 150" aria-hidden="true" preserveAspectRatio="xMidYMid slice">
              <rect width="240" height="150" fill="#354333" />
              <path d="M0 18 240 -20 M-18 65 220 25 M-18 104 220 62 M-8 160 240 109"
                stroke="#607258" strokeWidth="17" opacity=".48" />
              <path d="M14 -20 94 165M65 -20 143 165M138 -25 210 160" stroke="#1f322a" strokeWidth="4" opacity=".6" />
              <path d="m77 26 86 12 38 68-89 23-51-41z" fill="#77946d" fillOpacity=".65" stroke="#c3d4a6" strokeWidth="2" />
              <circle cx="130" cy="80" r="5" fill="#d6edac" />
              <path d="m130 57v15" stroke="#d6edac" strokeWidth="2" />
              <circle cx="130" cy="80" r="11" fill="none" stroke="#d6edac" opacity=".7" />
            </svg>
            <span className="map-tag">Contorno ilustrativo</span>
          </div>
          <div className="parcel-info">
            <strong>Lote de demostración</strong>
            <p>San Luis, Argentina · Parcela de secano</p>
          </div>
        </div>
        <div className="chips">
          <span className="chip">SECANO</span>
          <span className="chip muted">2 AÑOS</span>
          <span className="chip muted">FICTICIO</span>
        </div>
      </div>
      <div className="side-section">
        <div className="side-heading"><h3>Datos del lote</h3><span>Muestra</span></div>
        <div className="data-table">
          {parcelFacts.map(({ label, value, warning }) => (
            <div className="data-line" key={label}>
              <span>{label}</span><strong className={warning ? "data-warning" : undefined}>{value}</strong>
            </div>
          ))}
        </div>
        <button type="button" className="review-btn" onClick={onReview}>
          Revisar datos y supuestos <span aria-hidden="true">↗</span>
        </button>
      </div>
      <div className="alert-side">
        <strong>△ Prototipo de experiencia</strong>
        <p>Todos los importes, rindes, cantidades de agua y períodos son ficticios. No se ejecutaron modelos ni se consultó NASA.</p>
      </div>
    </aside>
  );
}

