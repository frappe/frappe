import { afterEach, describe, expect, it } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";
import type { App } from "vue";
import TableField from "../TableField.vue";
import { parsePastedText } from "../parseText";
import { ResolveFieldKey } from "../../FormLayout/types";
import { resetFormatDefaults, setFormatDefaults } from "../../FormLayout/formatDefaults";
import { CommitKey } from "../types";
import type { FieldMeta } from "../types";

const StubField = defineComponent({
  props: ["modelValue"],
  setup: (props) => () => h("input", { value: props.modelValue ?? "" }),
});

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
  resetFormatDefaults();
});

const CHILD_FIELDS: FieldMeta[] = [
  { fieldname: "item", fieldtype: "Data" },
  { fieldname: "qty", fieldtype: "Int" },
  { fieldname: "rate", fieldtype: "Currency" },
  { fieldname: "done", fieldtype: "Check" },
  { fieldname: "note", fieldtype: "Data", readOnly: true },
];

const changed: unknown[][] = [];
CHILD_FIELDS[1].ui = {
  on: { change: (value: unknown, row: any) => changed.push([value, row.item]) },
};

function render(rows: Record<string, any>[]) {
  const value = ref(rows);
  const commits: string[] = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(TableField, {
        field: { fieldname: "items", fieldtype: "Table", childFields: CHILD_FIELDS },
        modelValue: value.value,
        "onUpdate:modelValue": (next: any) => (value.value = next),
      }),
  });
  app.provide(ResolveFieldKey, () => StubField);
  app.provide(CommitKey, {
    pending: () => {},
    commit: (fieldname: string) => commits.push(fieldname),
    rowChanged: () => {},
  });
  app.mount(host);
  return { value, commits };
}

function paste(text: string) {
  const target = host!.querySelector<HTMLInputElement>('.grid-cell[data-fieldname="item"] input')!;
  const event = new Event("paste", { bubbles: true, cancelable: true });
  Object.defineProperty(event, "clipboardData", { value: { getData: () => text } });
  target.dispatchEvent(event);
}

describe("TableField paste", () => {
  it("commits each pasted value as its column's control would", async () => {
    const { value, commits } = render([{ name: "a" }]);
    paste("Pen\t2.7\t1,250.50\tTRUE\tkept out\nInk\tx\t3\t0");
    await nextTick();
    expect(value.value).toHaveLength(2);
    expect(value.value[0]).toMatchObject({ item: "Pen", qty: 2, rate: 1250.5, done: 1 });
    expect(value.value[0].note).toBeUndefined();
    expect(value.value[1]).toMatchObject({ item: "Ink", qty: 0, rate: 3, done: 0 });
    expect(commits.filter((f) => f === "note")).toEqual([]);
    // Ink's `x` parses to the 0 its new row already holds: no commit, no change.
    expect(changed).toEqual([[2, "Pen"]]);
  });
});

describe("parsePastedText", () => {
  it("turns a date in the site's format into yyyy-mm-dd and keeps anything else", () => {
    setFormatDefaults({ date_format: "dd/mm/yyyy" });
    expect(parsePastedText("Date", "27/10/2026")).toBe("2026-10-27");
    expect(parsePastedText("Date", "2026-10-27")).toBe("2026-10-27");
    expect(parsePastedText("Date", "next week")).toBe("next week");
  });

  it("turns a pasted star count into the fraction a Rating stores", () => {
    expect(parsePastedText("Rating", "4")).toBe(0.8);
    expect(parsePastedText("Rating", "3", "10")).toBe(0.3);
    expect(parsePastedText("Rating", "0.5")).toBe(0.5);
  });

  it("reads a Check as 1 or 0 and leaves text alone", () => {
    expect(parsePastedText("Check", "1")).toBe(1);
    expect(parsePastedText("Check", "false")).toBe(0);
    expect(parsePastedText("Data", " 007 ")).toBe(" 007 ");
  });
});
