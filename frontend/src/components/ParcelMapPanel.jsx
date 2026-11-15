import ParcelMap from "./ParcelMap.jsx";

export default function ParcelMapPanel({ parcels, activeParcel, onSelectParcel }) {
  return (
    <section id="rotations" className="card timeline-card parcel-workspace" aria-labelledby="parcel-map-heading">
      <div className="section-title parcel-workspace-header">
        <h2 id="parcel-map-heading">Explorador de parcelas</h2>
      </div>
      <ParcelMap parcels={parcels} activeParcelId={activeParcel.id} onSelect={onSelectParcel} />
      <div className="map-status">
        <span className="map-caption">
          <svg className="ico" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v5m0-9v.1" /></svg>
          Vista aérea ilustrativa · Parcelas ficticias
        </span>
        <span role="status">{activeParcel.displayId ?? activeParcel.id} · Parcela activa</span>
      </div>
    </section>
  );
}
