import { useEffect, useRef } from "react";
import { getParcelFacts } from "../data/parcels.js";

export default function AssumptionsDialog({ parcel, isOpen, onClose }) {
  const dialogRef = useRef(null);

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
    <dialog className="dialog" ref={dialogRef} onClose={onClose} onClick={handleBackdropClick} aria-labelledby="modalTitle">
      <div className="eyebrow">CONTEXTO / PROTOTIPO</div>
      <h2 id="modalTitle">Datos del lote de muestra</h2>
      <p>Esta ventana demuestra cómo consultaríamos las entradas y la procedencia. Los datos son completamente ficticios. El prototipo no envía ni guarda información.</p>
      <div className="modal-list">
        {[
          ["Parcela", `${parcel.name} · ${parcel.id}`],
          ["Ubicación", "San Luis (ejemplo)"],
          ["Modalidad", "Secano"],
          ...getParcelFacts(parcel),
          ["Datos NASA POWER", "No conectados"],
          ["Modelo de rendimientos", "No ejecutado"],
        ].map(([label, value]) => (
          <div key={label}><span>{label}</span><strong>{value}</strong></div>
        ))}
      </div>
      <button className="modal-close" onClick={onClose} type="button">Cerrar</button>
    </dialog>
  );
}
