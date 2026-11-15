// Fictional fixtures copied from the prototype. Widths are display values.
const maize = { tone: "maize", name: "Maíz", note: "Cultivo comercial" };

export const rotations = [
  {
    id: "A", label: "Barbecho", caption: "Referencia",
    name: "A · Maíz / barbecho / soja 1.ª",
    income: 1820000, cost: 1110000, margin: 710000, water: 140, cover: 11,
    costWidth: "61.0%", marginWidth: "88.75%", waterWidth: "87.5%", coverWidth: "45.83333333333333%",
    yields: [7.2, null, 3.6],
    phases: [
      maize,
      { tone: "fallow", name: "Barbecho", note: "Rastrojos posibles" },
      { tone: "soy", name: "Soja 1.ª", note: "Cultivo comercial" },
    ],
  },
  {
    id: "B", label: "Centeno", caption: "De cobertura",
    name: "B · Centeno de cobertura",
    income: 1810000, cost: 1240000, margin: 570000, water: 112, cover: 15,
    costWidth: "68.5%", marginWidth: "71.25%", waterWidth: "70%", coverWidth: "62.5%",
    yields: [7.2, null, 3.4],
    phases: [
      maize,
      { tone: "rye", name: "Centeno", note: "Sin venta de grano" },
      { tone: "soy", name: "Soja", note: "Cultivo comercial" },
    ],
  },
  {
    id: "C", label: "Trigo", caption: "Grano",
    name: "C · Maíz / trigo / soja 2.ª",
    income: 2180000, cost: 1570000, margin: 610000, water: 96, cover: 16,
    costWidth: "72.0%", marginWidth: "76.25%", waterWidth: "60%", coverWidth: "66.66666666666666%",
    yields: [7.2, 2.5, 2.1],
    phases: [
      maize,
      { tone: "wheat", name: "Trigo", note: "Cosecha potencial" },
      { tone: "soy", name: "Soja 2.ª", note: "Implantación posterior" },
    ],
  },
];

export const cropLabels = ["Maíz", "Trigo", "Soja"];
export const horizonMonths = 24;

export const parcelFacts = [
  { label: "Superficie", value: "80 ha*" },
  { label: "Textura", value: "Franco-arenosa*" },
  { label: "Profundidad", value: "1,20 m*" },
  { label: "Agua inicial", value: "Supuesto*" },
  { label: "Clima NASA POWER", value: "No conectado", warning: true },
];

export const assumptions = [
  ["Ubicación", "San Luis (ejemplo)"],
  ["Modalidad", "Secano"],
  ["Superficie", "80 ha — ficticio"],
  ["Textura del suelo", "Franco-arenosa — ficticio"],
  ["Humedad inicial", "Supuesto no validado"],
  ["Datos NASA POWER", "No conectados"],
  ["Modelo de rendimientos", "No ejecutado"],
];

