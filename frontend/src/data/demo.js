// Fixed rotations and sample yields from the original prototype.
const maize = { tone: "maize", name: "Maíz", note: "Cultivo comercial" };

export const rotations = [
  {
    id: "A", sequence: "Maíz → Barbecho invernal → Soja 1.ª", shortSequence: "Maíz – Barbecho – Soja 1.ª", label: "Barbecho", caption: "Referencia",
    name: "A · Maíz / barbecho / soja 1.ª",
    yields: [7.2, null, 3.6],
    phases: [
      maize,
      { tone: "fallow", name: "Barbecho", note: "Rastrojos posibles" },
      { tone: "soy", name: "Soja 1.ª", note: "Cultivo comercial" },
    ],
  },
  {
    id: "B", sequence: "Maíz → Centeno de cobertura → Soja", shortSequence: "Maíz – Centeno – Soja", label: "Centeno", caption: "De cobertura",
    name: "B · Centeno de cobertura",
    yields: [7.2, null, 3.4],
    phases: [
      maize,
      { tone: "rye", name: "Centeno", note: "Sin venta de grano" },
      { tone: "soy", name: "Soja", note: "Cultivo comercial" },
    ],
  },
  {
    id: "C", sequence: "Maíz → Trigo → Soja 2.ª", shortSequence: "Maíz – Trigo – Soja 2.ª", label: "Trigo", caption: "Grano",
    name: "C · Maíz / trigo / soja 2.ª",
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
