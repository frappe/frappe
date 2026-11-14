import { shallowRef } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import { finderGroups, type FinderHost } from "../editorFinder";
import { activePanel, type PanelIndex } from "../panelIndex";
import { mountEditor, taskNote } from "./editorFixture";

let stop: () => void;
afterEach(() => {
  stop();
  activePanel.value = null;
});

function mount() {
  const state = taskNote();
  state.layouts.Details![0].layout[0].sections[1].label = "More";
  const mounted = mountEditor(state);
  stop = mounted.stop;
  const find = vi.fn();
  const findSetting = vi.fn();
  const host: FinderHost = {
    canvas: mounted.canvas,
    scope: null,
    panelShown: true,
    find,
    findSetting,
  };
  return { ...mounted, host, find, findSetting };
}

const labels = (groups: ReturnType<typeof finderGroups>) =>
  groups.map((group) => group.label);

describe("the header finder", () => {
  it("lists the fields with their section on the right, and the Settings rows", () => {
    const { host } = mount();
    const groups = finderGroups(host, "");
    expect(labels(groups)).toEqual(["Fields", "Settings"]);
    const fields = groups[0].items;
    expect(fields.map((item) => item.label)).toEqual(
      expect.arrayContaining(["Subject", "Notes"]),
    );
    expect(fields.find((item) => item.label === "Notes")!.suffix).toBe("More");
    expect(groups[0].items.length).toBeLessThanOrEqual(6);
    expect(groups[1].items.length).toBeLessThanOrEqual(6);
  });

  it("matches a field by label, fieldname or section, and a setting by its words", () => {
    const { host } = mount();
    expect(finderGroups(host, "subj")[0].items.map((item) => item.key)).toEqual(
      ["field-subject"],
    );
    expect(
      finderGroups(host, "more")[0].items.map((item) => item.key),
    ).toContain("field-notes");
    const settings = finderGroups(host, "title").find(
      (group) => group.label === "Settings",
    )!;
    expect(settings.items.map((item) => item.key)).toContain(
      "setting-title_field",
    );
    expect(
      settings.items.find((item) => item.key === "setting-title_field")!.suffix,
    ).toBe("Form");
    expect(finderGroups(host, "zzzz")).toEqual([]);
  });

  it("a pick finds the field or the setting", () => {
    const { host, find, findSetting } = mount();
    finderGroups(host, "subj")[0].items[0].pick();
    finderGroups(host, "title")
      .find((group) => group.label === "Settings")!
      .items[0].pick();
    expect([find.mock.calls, findSetting.mock.calls.length]).toEqual([
      [["subject"]],
      1,
    ]);
  });

  it("puts the selected field's properties first, only while its panel shows", () => {
    const { host, canvas } = mount();
    canvas.select({ kind: "field", fieldname: "subject" });
    const open = shallowRef(false);
    const panel: PanelIndex = {
      groups: new Map([[1, { label: "Field", open }]]),
      rows: new Map([
        [
          1,
          {
            group: 1,
            label: "Required",
            text: "Required mandatory",
            el: () => null,
          },
        ],
      ]),
    };
    activePanel.value = panel;
    const groups = finderGroups(host, "mandatory");
    expect(labels(groups)).toEqual(["Properties of Subject"]);
    expect([groups[0].items[0].label, groups[0].items[0].suffix]).toEqual([
      "Required",
      "Field",
    ]);
    expect(finderGroups({ ...host, panelShown: false }, "mandatory")).toEqual(
      [],
    );
  });
});
