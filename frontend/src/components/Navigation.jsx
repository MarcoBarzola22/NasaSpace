import { useState } from "react";
import { workspaces } from "../workspaces/routes.js";

function WorkspaceLinks({ activeWorkspace, onNavigate }) {
  return workspaces.map(({ id, label, icon, sections }) => (
    <a key={id} href={`#${id}/${sections[0][0]}`} className={`rail-link${activeWorkspace === id ? " active" : ""}`}
      aria-current={activeWorkspace === id ? "page" : undefined} onClick={onNavigate}>
      <svg aria-hidden="true" className="ico" viewBox="0 0 24 24"><path d={icon} /></svg>
      <span>{label}</span>
    </a>
  ));
}

export default function Navigation({ activeWorkspace }) {
  const [open, setOpen] = useState(false);
  return (
    <nav className="rail" aria-label="Navegación principal">
      <div className="desktop-workspace-links"><WorkspaceLinks activeWorkspace={activeWorkspace} /></div>
      <details className="mobile-workspaces" open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary>Espacios de trabajo</summary>
        <WorkspaceLinks activeWorkspace={activeWorkspace} onNavigate={() => setOpen(false)} />
      </details>
    </nav>
  );
}

