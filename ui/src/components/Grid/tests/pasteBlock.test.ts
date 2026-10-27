import { describe, expect, it } from "vitest";
import { parseBlock, planPaste } from "../pasteBlock";

const columns = [
  { fieldname: "item", label: "Item" },
  { fieldname: "qty", label: "Quantity" },
];

describe("parseBlock", () => {
  it("splits tabs and newlines, keeps quoted tabs and newlines, and drops Excel's last newline", () => {
    expect(parseBlock('a\t"b\tc"\r\n"say ""hi""\nthere"\td\n')).toEqual([
      ["a", "b\tc"],
      ['say "hi"\nthere', "d"],
    ]);
  });
});

describe("planPaste", () => {
  const target = { rowIndex: 0, columnIndex: 0, rowCount: 1, columns, canAddRows: true };

  it("maps the columns by a header line that names them", () => {
    const plan = planPaste([["Quantity", "item"], ["3", "Pen"]], target);
    expect(plan.writes).toEqual([
      { rowIndex: 0, columnIndex: 1, text: "3" },
      { rowIndex: 0, columnIndex: 0, text: "Pen" },
    ]);
  });

  it("drops cells past the last column and skips blank lines", () => {
    const plan = planPaste([["a", "1", "extra"], ["", ""], ["b", "2"]], target);
    expect(plan.addRows).toBe(2);
    expect(plan.writes.map((w) => `${w.rowIndex}.${w.columnIndex}`)).toEqual([
      "0.0",
      "0.1",
      "2.0",
      "2.1",
    ]);
  });
});
