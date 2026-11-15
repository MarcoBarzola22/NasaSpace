import { useEffect, useRef } from "react";
import { getParcelFacts } from "../data/parcels.js";
import { AssumptionTable, ProvenanceBlock, WarningList } from "../workspaces/SimulationResults.jsx";
import { DEMO_LABEL, STATUS_LABELS } from "../workspaces/simulation.js";

export default function AssumptionsDialog({ parcel, simulation, isOpen, onClose }) {
  const dialogRef = useRef(null);
  const response = simulation?.response;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (isOpen && !dialog.open) dialog.showModal();
    if (!isOpen && dialog.open) dialog.close();
  }, [isOpen]);

  function handleBackdropClick(event) {
    if (event.target !== event.currentTarget) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right ||
        event.clientY < bounds.top || event.clientY > bounds.bottom) onClose();
  }

  return (
    <dialog className={response ? "dialog dialog-wide" : "dialog"} ref={dialogRef} onClose={onClose} onClick={handleBackdropClick} aria-labelledby="modalTitle">
      {response ? <>
        <div className="eyebrow">MOTOR DE CÁLCULO / CONTRATO {response.contract_version}</div>
        <h2 id="modalTitle">Supuestos, advertencias y procedencia</h2>
        <p>{STATUS_LABELS[simulation.status]} · Solicitud {response.request_id}. Los valores provienen de la respuesta del motor.</p>
        <h3>Advertencias</h3><WarningList response={response} />
        <AssumptionTable response={response} />
        <h3>Procedencia de NASA POWER</h3><ProvenanceBlock response={response} />
      </> : <>
        <div className="eyebrow">CONTEXTO / PROTOTIPO</div>
        <h2 id="modalTitle">Datos del lote de muestra</h2>
        <p>{DEMO_LABEL}. Esta ventana demuestra cómo consultaríamos las entradas y la procedencia. Los datos son completamente ficticios.</p>
        <div className="modal-list">
          {[
            ["Parcela", `${parcel.name} · ${parcel.id}`],
            ["Ubicación", "San Luis (ejemplo)"],
            ["Modalidad", "Secano"],
            ...getParcelFacts(parcel),
            ["Datos NASA POWER", "Sin consultar"],
            ["Modelo de rendimientos", "No ejecutado"],
          ].map(([label, value]) => (
            <div key={label}><span>{label}</span><strong>{value}</strong></div>
          ))}
        </div>
      </>}
      <button className="modal-close" onClick={onClose} type="button">Cerrar</button>
    </dialog>
  );
}
