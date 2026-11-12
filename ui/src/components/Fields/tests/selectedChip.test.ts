// A selected link is a 20px chip in a panel row and a 28px one in the form; a row at rest holds the × as empty space.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h } from "vue";
import type { App } from "vue";
import SelectedChip from "../../TableMultiSelect/SelectedChip.vue";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = host = undefined;
});

function render(props: Record<string, unknown>) {
  host = document.createElement("div");
  document.body.appendChild(host);
  const removed: number[] = [];
  app = createApp({ render: () => h(SelectedChip, { label: "Sales", onRemove: () => removed.push(1), ...props }) });
  app.mount(host);
  return { chip: host.firstElementChild as HTMLElement, cross: host.querySelector<HTMLElement>('[role="button"]'), removed };
}

describe("SelectedChip", () => {
  it("is 20 high in a panel and 28 high in the form", () => {
    expect(render({ panel: true }).chip.className).toContain("h-5");
    app!.unmount();
    expect(render({}).chip.className).toContain("h-7");
  });

  it("draws no × when removable is omitted", () => {
    expect(render({ panel: true }).cross).toBeNull();
  });

  it("holds the × as invisible space when removable is false, and does not remove", () => {
    const { cross, removed } = render({ panel: true, removable: false });

    expect(cross!.className).toContain("invisible");
    expect(cross!.getAttribute("aria-hidden")).toBe("true");
    cross!.click();
    expect(removed).toEqual([]);
  });

  it("lets a click on the held × reach the row, so the row opens", () => {
    const { cross } = render({ panel: true, removable: false });
    let reached = false;
    host!.addEventListener("click", () => (reached = true));

    cross!.click();

    expect(reached).toBe(true);
  });

  it("keeps a click on the live × from reaching the row", () => {
    const { cross } = render({ removable: true });
    let reached = false;
    host!.addEventListener("click", () => (reached = true));

    cross!.click();

    expect(reached).toBe(false);
  });

  it("removes on a click of the × when removable is true", () => {
    const { cross, removed } = render({ removable: true });

    expect(cross!.className).not.toContain("invisible");
    cross!.click();
    expect(removed).toEqual([1]);
  });
});
