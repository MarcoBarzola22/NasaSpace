import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import App from "../src/App.jsx";
import Inspector from "../src/components/Inspector.jsx";
import MetricsPanel from "../src/components/MetricsPanel.jsx";
import RotationTimeline from "../src/components/RotationTimeline.jsx";
import { rotations } from "../src/data/demo.js";

const onSelect = () => {};

describe("AgroDSS workspace", () => {
  it("starts with Centeno selected in the timeline, inspector and economics chart", () => {
    const html = renderToStaticMarkup(<App />);

    expect(html).toContain("B · Centeno de cobertura");
    expect(html).toContain("570.000");
    expect(html).toMatch(/class="rotation-row active" aria-pressed="true"><span[^>]*><span[^>]*>B</);
    expect(html).toMatch(/class="select-rot" aria-pressed="true">B</);
    expect(html).toMatch(/class="barrow selected"><div[^>]*>Estrategia B</);
    expect(html).toContain("DATOS FICTICIOS");
  });

  it.each(rotations)("keeps strategy $id consistent across the comparison and inspector", (rotation) => {
    const html = renderToStaticMarkup(
      <>
        <RotationTimeline rotations={rotations} selectedId={rotation.id} onSelect={onSelect} />
        <MetricsPanel rotations={rotations} selectedId={rotation.id} />
        <Inspector rotations={rotations} selected={rotation} onSelect={onSelect} />
      </>,
    );

    expect(html).toContain(rotation.name);
    expect(html).toContain(`${rotation.water} mm`);
    expect(html).toContain(`${rotation.cover}/24 meses`);
    expect(html).toContain(`aria-pressed="true">${rotation.id}</button>`);
    expect(html).toContain(`class="barrow selected"><div class="name">Estrategia ${rotation.id}`);
  });

  it("exposes linked metric tabs, assumptions, expandable stats and print data", () => {
    const html = renderToStaticMarkup(<App />);

    for (const label of ["Economía", "Agua", "Suelo", "Producción"]) {
      expect(html).toMatch(new RegExp(`role="tab"[^>]*aria-controls="metric-panel"[^>]*>${label}</button>`));
    }

    expect(html).toContain('role="tabpanel" aria-labelledby="tab-economy"');
    expect(html).toContain('<details class="stat-accordion" open="">');
    expect(html).toContain('aria-labelledby="modalTitle"');
    expect(html).toContain("Valores ficticios de prueba — resumen de las tres alternativas");
  });
});

