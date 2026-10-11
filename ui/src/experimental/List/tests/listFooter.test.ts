import { afterEach, describe, expect, it } from "vitest";
import { reactive } from "vue";
import { ListFooter } from "../index";
import { flush, mount, unmountAll } from "./mount";

afterEach(unmountAll);

function loadMore(root: HTMLElement) {
  return Array.from(root.querySelectorAll("button")).find((button) =>
    button.textContent?.includes("Load More")
  );
}

describe("ListFooter counts", () => {
  it("shows a placeholder until the counts are known", async () => {
    const { root } = await mount(ListFooter, { hasCounts: false });
    expect(root.textContent).not.toContain(" of ");
    expect(loadMore(root)).toBeUndefined();
  });

  it("shows N of M, and Load More only while rows remain", async () => {
    const state = reactive({ rowCount: 20, totalCount: 50 });
    const clicks: number[] = [];
    const { root } = await mount(ListFooter, {
      hasCounts: true,
      get rowCount() {
        return state.rowCount;
      },
      get totalCount() {
        return state.totalCount;
      },
      "onLoad-more": () => clicks.push(1),
    });
    expect(root.textContent).toContain("20 of 50");

    loadMore(root)!.click();
    expect(clicks).toHaveLength(1);

    state.rowCount = 50;
    await flush();
    expect(loadMore(root)).toBeUndefined();
  });

  it("a capped total reads N of M+, and Load More follows hasNextPage over the counts", async () => {
    const state = reactive({ hasNextPage: true });
    const { root } = await mount(ListFooter, {
      hasCounts: true,
      rowCount: 1000,
      totalCount: 1000,
      totalCapped: true,
      get hasNextPage() {
        return state.hasNextPage;
      },
    });
    expect(root.textContent).toContain("1000 of 1000+");
    expect(loadMore(root)).toBeDefined();

    state.hasNextPage = false;
    await flush();
    expect(loadMore(root)).toBeUndefined();
  });
});

describe("ListFooter page size", () => {
  it("a tab click updates the model and emits page-size", async () => {
    const state = reactive({ pageSize: 20 });
    const chosen: number[] = [];
    const { root } = await mount(ListFooter, {
      hasCounts: true,
      get pageSize() {
        return state.pageSize;
      },
      "onUpdate:pageSize": (value: number) => (state.pageSize = value),
      "onPage-size": (value: number) => chosen.push(value),
    });

    const tab = Array.from(
      root.querySelectorAll<HTMLElement>("[role='radio']")
    ).find((item) => item.textContent?.trim() === "100")!;
    tab.click();
    await flush();

    expect(state.pageSize).toBe(100);
    expect(chosen).toEqual([100]);
  });

  it("a restored page size emits nothing", async () => {
    const state = reactive({ pageSize: 20 });
    const chosen: number[] = [];
    const { root } = await mount(ListFooter, {
      hasCounts: true,
      get pageSize() {
        return state.pageSize;
      },
      "onPage-size": (value: number) => chosen.push(value),
    });

    state.pageSize = 500;
    await flush();
    expect(chosen).toEqual([]);
    expect(
      root
        .querySelector("[role='radio'][aria-checked='true']")
        ?.textContent?.trim()
    ).toBe("500");
  });
});
