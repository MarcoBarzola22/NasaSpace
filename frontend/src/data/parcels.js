// Fictional fixtures transcribed from the map prototype.
export const mapWidth = 1586;
export const mapHeight = 992;
export const initialParcelId = "P-02";

export const parcels = [
  {
    id: "P-01", name: "Parcela Norte", label: "Norte",
    subtitle: "San Luis, Argentina · Secano",
    points: "189,65 780,234 380,824 15,699", labelPosition: { left: "24%", top: "41%" },
    area: "64 ha", texture: "Franco-arenosa", depth: "1,10 m", initialWater: 98, capacity: 160, waterWidth: "61%",
    scenarios: {
      A: { income: 1420000, cost: 980000, margin: 440000, cover: 11, deficit: 37,
        costWidth: "69.01%", marginWidth: "55.00%", coverWidth: "45.83%", deficitWidth: "23.13%" },
      B: { income: 1390000, cost: 1060000, margin: 330000, cover: 16, deficit: 49,
        costWidth: "76.26%", marginWidth: "41.25%", coverWidth: "66.67%", deficitWidth: "30.63%" },
      C: { income: 1780000, cost: 1390000, margin: 390000, cover: 19, deficit: 72,
        costWidth: "78.09%", marginWidth: "48.75%", coverWidth: "79.17%", deficitWidth: "45.00%" },
    },
  },
  {
    id: "P-02", name: "Parcela Central", label: "Central",
    subtitle: "San Luis, Argentina · Secano",
    points: "467,739 951,20 1144,76 1350,482", labelPosition: { left: "58%", top: "43%" },
    area: "88 ha", texture: "Franca", previousCrop: "Barbecho", depth: "1,35 m", initialWater: 132, capacity: 195, waterWidth: "68%",
    scenarios: {
      A: { income: 1780000, cost: 1120000, margin: 660000, cover: 12, deficit: 24,
        costWidth: "62.92%", marginWidth: "82.50%", coverWidth: "50.00%", deficitWidth: "15.00%" },
      B: { income: 1800000, cost: 1200000, margin: 600000, cover: 17, deficit: 32,
        costWidth: "66.67%", marginWidth: "75.00%", coverWidth: "70.83%", deficitWidth: "20.00%" },
      C: { income: 2060000, cost: 1570000, margin: 490000, cover: 20, deficit: 54,
        costWidth: "76.21%", marginWidth: "61.25%", coverWidth: "83.33%", deficitWidth: "33.75%" },
    },
  },
  {
    id: "P-03", name: "Parcela Sur", label: "Sur",
    subtitle: "San Luis, Argentina · Secano",
    points: "449,771 1360,503 1545,891 1514,960 395,960", labelPosition: { left: "64%", top: "79%" },
    area: "72 ha", texture: "Franco-arcillosa", depth: "0,90 m", initialWater: 76, capacity: 125, waterWidth: "61%",
    scenarios: {
      A: { income: 1250000, cost: 970000, margin: 280000, cover: 10, deficit: 64,
        costWidth: "77.60%", marginWidth: "35.00%", coverWidth: "41.67%", deficitWidth: "40.00%" },
      B: { income: 1220000, cost: 1040000, margin: 180000, cover: 16, deficit: 78,
        costWidth: "85.25%", marginWidth: "22.50%", coverWidth: "66.67%", deficitWidth: "48.75%" },
      C: { income: 1520000, cost: 1390000, margin: 130000, cover: 19, deficit: 102,
        costWidth: "91.45%", marginWidth: "16.25%", coverWidth: "79.17%", deficitWidth: "63.75%" },
    },
  },
];

export function getParcelFacts(parcel) {
  return [
    ["Superficie", parcel.area],
    ["Textura", parcel.texture],
    ["Profundidad efectiva", parcel.depth],
    ["Agua inicial (ficticia)", `${parcel.initialWater} mm`],
  ];
}
