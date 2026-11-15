import { useEffect, useRef, useState } from "react";
import aerialImage from "../assets/parcel-aerial-v2.jpg";
import { mapWidth, mapHeight } from "../data/parcels.js";
import { initialViewport, panViewport, zoomViewport } from "./mapViewport.js";
import "../styles/parcel-map.css";

export default function ParcelMap({ parcels, activeParcelId, onSelect }) {
  const [viewport, setViewport] = useState(initialViewport);
  const [isDragging, setDragging] = useState(false);
  const surfaceRef = useRef(null);
  const dragRef = useRef(null);

  function changeZoom(step) {
    setViewport((current) => zoomViewport(current, step));
  }

  useEffect(() => {
    const surface = surfaceRef.current;

    function handleWheel(event) {
      if (event.deltaY === 0) return;
      event.preventDefault();
      changeZoom(event.deltaY < 0 ? 0.15 : -0.15);
    }

    surface.addEventListener("wheel", handleWheel, { passive: false });
    return () => surface.removeEventListener("wheel", handleWheel);
  }, []);

  function startDrag(event) {
    if (!event.isPrimary || event.button !== 0 || event.target.closest("button, [data-parcel]")) return;
    event.preventDefault();
    const { pointerId, clientX, clientY } = event;
    event.currentTarget.setPointerCapture(pointerId);
    dragRef.current = { pointerId, clientX, clientY, originX: viewport.x, originY: viewport.y };
    setDragging(true);
  }

  function moveDrag(event) {
    const drag = dragRef.current;
    if (drag?.pointerId !== event.pointerId) return;
    const { clientX, clientY } = event;
    setViewport((current) => panViewport(current, drag, { clientX, clientY }));
  }

  function endDrag(event) {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null;
    setDragging(false);
  }

  return (
    <div ref={surfaceRef} className={isDragging ? "map-surface dragging" : "map-surface"}
      onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={endDrag}
      onPointerCancel={endDrag} onLostPointerCapture={endDrag}>
      <div className="map-stage" style={{ transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})` }}>
        <svg className="map-cover" viewBox={`0 0 ${mapWidth} ${mapHeight}`} preserveAspectRatio="none" aria-label="Parcelas ficticias">
          <image href={aerialImage} width={mapWidth} height={mapHeight} preserveAspectRatio="none" aria-hidden="true" />
          <polygon className="map-casing" points={parcels.find(({ id }) => id === activeParcelId).points} aria-hidden="true" />
          {parcels.map(({ id, name, points }) => (
            <polygon key={id} points={points} data-parcel={id} role="button" tabIndex={0}
              className={id === activeParcelId ? "map-field selected" : "map-field"}
              aria-label={`${name}, ${id}`} aria-pressed={id === activeParcelId}
              onClick={() => onSelect(id)}
              onKeyDown={(event) => {
                if (event.key !== "Enter" && event.key !== " ") return;
                event.preventDefault();
                onSelect(id);
              }} />
          ))}
        </svg>
        {parcels.map(({ id, label, labelPosition }) => (
          <div key={id} className={id === activeParcelId ? "map-label selected" : "map-label"} style={labelPosition} aria-hidden="true">
            <strong>{id} · {label}</strong>
          </div>
        ))}
      </div>
      <div className="map-tools" role="group" aria-label="Controles del mapa">
        <button type="button" aria-label="Acercar" onClick={() => changeZoom(0.25)}>+</button>
        <button type="button" aria-label="Alejar" onClick={() => changeZoom(-0.25)}>−</button>
        <button type="button" aria-label="Restablecer vista" onClick={() => setViewport(initialViewport)}>
          <svg className="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9V4h5m6 0h5v5m0 6v5h-5m-6 0H4v-5 M9 9h6v6H9z" /></svg>
        </button>
      </div>
    </div>
  );
}
