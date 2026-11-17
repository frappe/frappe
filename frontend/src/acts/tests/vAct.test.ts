// `v-act` and `withAct`: the marks the act-control check (playwright/tests/desk_v2_act_controls.spec.js) reads.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, withDirectives } from "vue";

const perform = vi.hoisted(() => vi.fn());
vi.mock("../dispatcher", () => ({ acts: { perform } }));

import { vAct } from "../vAct";
import { withAct } from "../menuAct";

beforeEach(() => perform.mockReset());

function mount(mark: () => unknown) {
  const host = document.createElement("div");
  const Root = defineComponent(() => () => withDirectives(h("button"), [[vAct, mark()]]));
  createApp(Root).mount(host);
  return host.querySelector("button")!;
}

describe("v-act", () => {
  it("names the act in data-act and performs it on a click", () => {
    const button = mount(() => "list.create");
    expect(button.dataset.act).toBe("list.create");
    button.click();
    expect(perform).toHaveBeenCalledWith("list.create");
  });

  it("passes a value along with the name", () => {
    const button = mount(() => ["editor.open_tab", "settings"]);
    button.click();
    expect(perform).toHaveBeenCalledWith("editor.open_tab", "settings");
  });

  it("follows the mark when it changes", async () => {
    const name = ref("header.save");
    const button = mount(() => name.value);
    name.value = "header.delete";
    await nextTick();
    expect(button.dataset.act).toBe("header.delete");
    button.click();
    expect(perform).toHaveBeenCalledWith("header.delete");
  });
});

describe("withAct", () => {
  it("keeps the row and draws its label with the act on it", () => {
    const row = withAct({ label: "Delete", theme: "red", onClick: () => {} }, "header.delete");
    expect(row.theme).toBe("red");
    const mark = (row.slots as any).label();
    expect(mark.props["data-act"]).toBe("header.delete");
    expect(JSON.stringify(mark.children[0].props.class)).toContain("text-ink-red-7");
  });

  it("draws the colour of the row the menu holds, so a theme added later shows", () => {
    const row = withAct({ label: "Log out", onClick: () => {} }, "shell.log_out");
    const mark = (row.slots as any).label({ item: { ...row, theme: "red" } });
    expect(JSON.stringify(mark.children[0].props.class)).toContain("text-ink-red-7");
  });
});
