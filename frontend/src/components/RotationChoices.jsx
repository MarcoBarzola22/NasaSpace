const components = ["Maíz", "Soja 1.ª", "Soja 2.ª", "Centeno de cobertura", "Trigo", "Barbecho"];

export default function RotationChoices({ rotations, selectedId, onSelect }) {
  return (
    <section className="card rotation-choices" aria-labelledby="rotation-choices-title">
      <div className="rotation-choices-heading">
        <h2 id="rotation-choices-title">Rotaciones a comparar</h2>
        <span>Tres alternativas predefinidas</span>
      </div>
      <div className="rotation-options" role="radiogroup" aria-labelledby="rotation-choices-title">
        {rotations.map(({ id, sequence }) => (
          <label className="rotation-option" key={id}>
            <input type="radio" name="comparison-rotation" value={id} checked={id === selectedId}
              onChange={() => onSelect(id)} aria-label={`${id} · ${sequence}`} />
            <span className="rotation-option-code">{id}</span>
            <span className="rotation-option-sequence">{sequence}</span>
          </label>
        ))}
      </div>
      <div className="rotation-components">
        <h3>Componentes de la rotación</h3>
        <ul>{components.map((name) => <li key={name}>{name}</li>)}</ul>
      </div>
    </section>
  );
}
