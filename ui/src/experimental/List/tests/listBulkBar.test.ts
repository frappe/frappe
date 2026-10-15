import { afterEach, describe, expect, it } from "vitest";
import { reactive } from "vue";
import { ListBulkBar } from "../index";
import { flush, mount, unmountAll } from "./mount";

afterEach(unmountAll);

function button(root: HTMLElement, label: string) {
  return Array.from(root.querySelectorAll("button")).find(
    (item) =>
      item.textContent?.includes(label) ||
      item.getAttribute("aria-label") === label
  );
}

describe("ListBulkBar", () => {
  it("stays hidden with nothing selected", async () => {
    const { root } = await mount(ListBulkBar, { selection: [] });
    expect(root.textContent).not.toContain("selected");
  });

  it("shows the count and hands the selection to an action", async () => {
    const received: string[][] = [];
    const { root } = await mount(ListBulkBar, {
      selection: ["A", "B"],
      actions: [
        {
          label: "Delete",
          theme: "red",
          onClick: (names: string[]) => received.push(names),
        },
      ],
    });
    expect(root.textContent).toContain("2 selected");

    button(root, "Delete")!.click();
    expect(received).toEqual([["A", "B"]]);
  });

  it("the clear button empties the selection", async () => {
    const state = reactive({ selection: ["A"] });
    const { root } = await mount(ListBulkBar, {
      get selection() {
        return state.selection;
      },
      "onUpdate:selection": (value: string[]) => (state.selection = value),
    });

    button(root, "Clear selection")!.click();
    await flush();

    expect(state.selection).toEqual([]);
  });
});
