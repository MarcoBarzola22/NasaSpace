const sections = [
  { id: "overview", label: "Vista general", path: "M3 10.5 12 3l9 7.5V21h-7v-7H10v7H3z" },
  { id: "rotations", label: "Rotaciones", path: "M4 7h16M4 12h16M4 17h16M7 5v4m6 1v4m5 1v4" },
  { id: "metrics", label: "Indicadores", path: "M4 20V9m6 11V4m6 16v-7m5 7H3" },
  { id: "sources", label: "Fuentes y límites", path: "M12 11v5m0-9v.1", circle: true },
];

export default function Navigation({ activeSection }) {
  return (
    <nav className="rail" aria-label="Navegación del prototipo">
      <a className="rail-logo" href="#overview" aria-label="AgroDSS, inicio">A<span className="rail-logo-dot">.</span></a>
      {sections.map(({ id, label, path, circle }) => {
        const isActive = activeSection === id;
        return (
          <a key={id} href={`#${id}`} className={isActive ? "rail-link active" : "rail-link"}
            aria-current={isActive ? "location" : undefined} title={label} aria-label={label}>
            <svg aria-hidden="true" className="ico" viewBox="0 0 24 24">
              {circle && <circle cx="12" cy="12" r="9" />}
              <path d={path} />
            </svg>
          </a>
        );
      })}
      <div className="rail-bottom">AGRONOMÍA / DECISIONES</div>
    </nav>
  );
}

