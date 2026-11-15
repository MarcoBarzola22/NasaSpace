export default function WorkspaceHeader({ onReview }) {
  return (
    <>
      <div className="topline">
        <div className="crumb">
          <span>Espacio de trabajo</span><span className="sep">/</span>
          <span className="crumb-current">Comparador de rotaciones</span>
        </div>
        <div className="top-actions">
          <span className="demo-tag">● DATOS FICTICIOS · DEMO</span>
          <button className="print-button" onClick={() => window.print()} type="button">
            <svg aria-hidden="true" className="ico" viewBox="0 0 24 24">
              <path d="M6 9V3h12v6M6 18H4V9h16v9h-2M6 15h12v6H6z" />
            </svg>
            Imprimir vista
          </button>
        </div>
      </div>
      <header className="hero">
        <div className="eyebrow">ANÁLISIS DE ROTACIONES / SAN LUIS</div>
        <h1>Una parcela.<br /><span>Tres decisiones.</span></h1>
        <p>
          Compará cómo cambian las condiciones y los resultados de <em>tres secuencias agrícolas</em> durante dos años. Esta es una maqueta funcional para evaluar la experiencia visual, no una simulación agronómica.
        </p>
        <button className="review-btn mobile-review" type="button" onClick={onReview}>
          Revisar datos y supuestos <span aria-hidden="true">↗</span>
        </button>
      </header>
    </>
  );
}

