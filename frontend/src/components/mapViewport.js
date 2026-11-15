export const initialViewport = { zoom: 1, x: 0, y: 0 };

export function zoomViewport(viewport, step) {
  const zoom = Math.min(2.4, Math.max(1, Math.round((viewport.zoom + step) * 10) / 10));
  return zoom === 1 ? initialViewport : { ...viewport, zoom };
}

export function panViewport(viewport, drag, point) {
  return {
    ...viewport,
    x: drag.originX + point.clientX - drag.clientX,
    y: drag.originY + point.clientY - drag.clientY,
  };
}
