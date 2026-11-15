import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ComparisonChart } from "../src/components/MetricsPanel.jsx";
import { metrics } from "../src/data/presentation.js";
import { amountError, amountValue, economicChanges, economicEntryErrors, editPrice, marginAxis, priceRowsForCrop } from "../src/workspaces/economics.js";
import { updateParcelDraft, updateRecord } from "../src/workspaces/session.js";

const original = {
  prices: [{ id: "price", crop: "Soja", amount: "200", currency: "USD", unit: "USD/t" }],
  costs: [{ id: "cost", strategy: "B", category: "Semillas", amount: "50", currency: "USD", unit: "ha" }],
};

describe("Economic input exploration", () => {
  it("validates decimal input without accepting negative, empty or ambiguous amounts", () => {
    expect(amountValue("0")).toBe(0);
    expect(amountValue("31,25")).toBe(31.25);
    expect(amountError("-1")).toBeTruthy();
    expect(amountError("1.123,00")).toBeTruthy();
    expect(amountValue("")).toBeNull();
  });

  it("edits prices independently from costs and restores both without touching parcel data", () => {
    const drafts = updateParcelDraft({}, "P-02", () => ({ ...original, identity: { name: "Mi lote" } }));
    const prices = editPrice(original.prices, original.prices[0], "Soja", { amount: "250" });
    const costs = updateRecord(original.costs, "cost", { amount: "60" });
    const withPrice = updateParcelDraft(drafts, "P-02", () => ({ prices }));
    expect(withPrice["P-02"].costs).toBe(original.costs);
    const withCost = updateParcelDraft(withPrice, "P-02", () => ({ costs }));
    expect(withCost["P-02"].prices).toBe(prices);
    expect(economicChanges(original, withCost["P-02"]).map(({ delta }) => delta)).toEqual([50, 10]);
    const reset = updateParcelDraft(withCost, "P-02", () => original);
    expect(reset["P-02"].identity.name).toBe("Mi lote");
    expect(economicChanges(original, reset["P-02"])).toEqual([]);
  });

  it("makes no difference across currencies or incompatible price units", () => {
    const prices = editPrice(original.prices, original.prices[0], "Soja", { currency: "ARS", amount: "240" });
    expect(prices[0].unit).toBe("t");
    expect(economicChanges(original, { ...original, prices })[0].delta).toBeNull();
    expect(priceRowsForCrop([...original.prices, { crop: "Soja", unit: "kg" }, { crop: "Soja de primera", unit: "t" }], "Soja"))
      .toEqual(original.prices);
  });

  it("rejects mismatched currency labels before comparing two amounts", () => {
    const a = { ...original.prices[0], currency: "ARS" };
    const b = { ...a, amount: "400" };
    expect(economicEntryErrors(a).unit).toContain("no coincide");
    expect(economicChanges({ ...original, prices: [a] }, { ...original, prices: [b] })[0].delta).toBeNull();
  });

  it("represents negative margins to the left of the same zero as positive margins", () => {
    const scale = marginAxis([-100, 0, 300]);
    expect(scale.zero).toBe(25);
    const html = renderToStaticMarkup(<ComparisonChart metric={metrics[0]}
      rotations={[{ id: "A", label: "Barbecho", margin: -100 }, { id: "B", label: "Centeno", margin: 0 }, { id: "C", label: "Trigo", margin: 300 }]} selectedId="A" />);
    expect(html).toContain('class="bar selected negative" style="left:0%;width:25%"');
    expect(html).toContain('style="left:25%;width:75%"');
    expect(marginAxis([0, 0, 0]).position(0)).toBe(0);
  });
});

