export const workspaces = [
  { id: "parcela", label: "Mi parcela", icon: "m12 2 10 5-10 5L2 7z M2 12l10 5 10-5 M2 17l10 5 10-5", sections: [
    ["identificacion", "Identificación"], ["mapa", "Mapa de parcelas"], ["suelo", "Caracterización del suelo"], ["laboratorio", "Estudios de suelo"], ["antecedentes", "Antecedentes del lote"],
  ] },
  { id: "estrategias", label: "Explorar estrategias", icon: "M20 8a8 8 0 1 0 0 8m0-12v4h-4m4 12v-4h-4", sections: [
    ["alternativas", "Alternativas"], ["biblioteca", "Biblioteca"], ["editor", "Editor de estrategia"], ["comparar", "Mesa comparativa"], ["cronologia", "Cronología agrícola"], ["clima", "Clima histórico"], ["agua", "Agua y cobertura"], ["produccion", "Producción"],
  ] },
  { id: "economia", label: "Economía", icon: "M20 6c0 2-3.6 3-8 3s-8-1-8-3 3.6-3 8-3 8 1 8 3z M4 6v6c0 2 3.6 3 8 3s8-1 8-3V6 M4 12v6c0 2 3.6 3 8 3s8-1 8-3v-6", sections: [
    ["precios", "Precios"], ["costos", "Costos de actividades"], ["comparacion", "Comparación económica"], ["avanzada", "Exploración avanzada"],
  ] },
  { id: "interpretacion", label: "Interpretación", icon: "M3 20h18 M6 17v-5m6 5V5m6 12V9", sections: [
    ["resultados", "Explicación de resultados"], ["procedencia", "Procedencia"], ["advertencias", "Advertencias y consistencia"], ["nutricion", "Estudios y nutrición"],
  ] },
  { id: "informe", label: "Informe", icon: "M5 3h10l4 4v14H5z M14 3v5h5 M8 12h8m-8 4h8", sections: [
    ["resumen", "Vista general"], ["impresion", "Impresión"], ["gestion", "Gestión del análisis"],
  ] },
];

export const periods = [
  ["two-campaigns", "Dos campañas"],
  ["first-campaign", "Primera campaña"],
  ["second-campaign", "Segunda campaña"],
];

export const scenarios = [["historical", "Histórico · demo"]];
const legacyRoutes = { rotations: "#estrategias/alternativas", metrics: "#economia/comparacion", sources: "#interpretacion/procedencia",
  "parcel-context": "#parcela/mapa", "parcel-inspector": "#estrategias/alternativas" };

export function readRoute(hash = "") {
  const path = hash.slice(1);
  const resolved = Object.hasOwn(legacyRoutes, path) ? legacyRoutes[path].slice(1) : path;
  const [workspaceId, sectionId, strategyId, mode] = resolved.split("/");
  const workspace = workspaces.find(({ id }) => id === workspaceId) ?? workspaces[1];
  const section = workspace.sections.find(([id]) => id === sectionId) ?? workspace.sections[0];
  return { workspace, section: section[0], strategyId, detail: mode === "detalle" };
}

