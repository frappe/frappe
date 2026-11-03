// The apps' field actions on a record: the `⋯` rows and the quick action a Phone value brings, over a faked dispatcher.
import { beforeEach, describe, expect, it, vi } from "vitest";

const found = vi.hoisted(() => new Map<string, { label?: string; icon?: string }>());
vi.mock("@/acts/dispatcher", () => ({ acts: { find: (name: string) => found.get(name) } }));
vi.mock("@/i18n", () => ({ __: (text: string) => text }));
vi.mock("@/contributions/registry", () => ({ fieldActionFiles: [] }));

import type { FieldActionItem } from "@/contributions/types";
import { fieldActionQuickActions, fieldActionRows } from "../fieldActionEntries";

const CALL = "shell.crm.make_a_call";
const call: FieldActionItem = { fieldtype: "Phone", act: CALL, quickActionLabel: "Call" };
const fields = [
  { fieldname: "mobile_no", label: "Mobile No", fieldtype: "Phone" },
  { fieldname: "phone", label: "Phone", fieldtype: "Phone" },
  { fieldname: "site", label: "Website", fieldtype: "Data", options: "URL" },
  { fieldname: "cell", label: "Cell", fieldtype: "Data", options: "Phone" },
];
const run = vi.fn();
const pageOf = (doc: Record<string, unknown>, isNew = false) => ({ doc, isNew, meta: { fields }, run }) as any;
const drawn = (entries: any[], page: any) => entries.filter((entry) => entry.when(page));

beforeEach(() => {
  found.clear();
  found.set(CALL, { label: "Make a call", icon: "lucide-phone" });
  run.mockClear();
});

describe("a field action on the record", () => {
  it("draws no row and no quick action while the record holds no number", () => {
    const page = pageOf({ mobile_no: "  ", site: "https://a.b" });
    expect(drawn(fieldActionRows([call]), page)).toEqual([]);
    expect(drawn(fieldActionQuickActions([call]), page)).toEqual([]);
  });

  it("draws none on an unsaved record", () => {
    expect(drawn(fieldActionRows([call]), pageOf({ mobile_no: "111" }, true))).toEqual([]);
  });

  it("draws none while the act's own gate is shut", () => {
    found.clear();
    expect(fieldActionRows([call])).toEqual([]);
    expect(fieldActionQuickActions([call])).toEqual([]);
  });

  it("draws none for an item the value does not pass", () => {
    const only91 = { ...call, when: (value: string) => value.startsWith("+91") };
    expect(drawn(fieldActionRows([only91]), pageOf({ mobile_no: "555" }))).toEqual([]);
  });

  it("runs the act with the only number, from the row and from the quick action", () => {
    const page = pageOf({ mobile_no: " 111 " });
    const [row] = drawn(fieldActionRows([call]), page);
    const [quick] = drawn(fieldActionQuickActions([call]), page);

    row.run(page);
    quick.run(page);

    expect(row).toMatchObject({ label: "Make a call", icon: "lucide-phone", palette: false, group: "field_actions" });
    expect(quick).toMatchObject({ label: "Call", icon: "lucide-phone", palette: false });
    expect(run).toHaveBeenNthCalledWith(1, CALL, "111");
    expect(run).toHaveBeenNthCalledWith(2, CALL, "111");
  });

  it("counts a Data field of Phone options, and one number held by two fields once", () => {
    const page = pageOf({ mobile_no: "111", phone: "111", cell: "" });
    expect(drawn(fieldActionRows([call]), page).map((entry) => entry.name)).toEqual(["shell_crm_make_a_call"]);
  });

  it("asks which number when there are two or more, each with its field label", () => {
    const page = pageOf({ mobile_no: "111", phone: "222", cell: "111" });
    const [row] = drawn(fieldActionRows([call]), page);
    const [quick] = drawn(fieldActionQuickActions([call]), page);

    expect(row.name).toBe("shell_crm_make_a_call_from");
    expect(row.argument.label).toBe("Choose one");
    expect(row.argument.options(page, "")).toEqual([
      { value: "111", label: "111", description: "Mobile No, Cell" },
      { value: "222", label: "222", description: "Phone" },
    ]);
    quick.run(page, "222");
    expect(run).toHaveBeenCalledWith(CALL, "222");
  });

  it("maps the value the act receives", () => {
    const page = pageOf({ mobile_no: "+91 99" });
    const item = { ...call, value: (value: string) => value.replace(/\s/g, "") };
    drawn(fieldActionRows([item]), page)[0].run(page);
    expect(run).toHaveBeenCalledWith(CALL, "+9199");
  });

  it("reads the draft: a number typed before the save brings the row", () => {
    const rows = fieldActionRows([call]);
    expect(drawn(rows, pageOf({}))).toEqual([]);
    expect(drawn(rows, pageOf({ phone: "333" }))).toHaveLength(1);
  });
});
