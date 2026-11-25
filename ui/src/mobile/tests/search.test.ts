import { afterEach, describe, expect, it } from "vitest";
import { nextTick } from "vue";
import { Search } from "../index";
import { mount, rows, unmountAll } from "./mount";

afterEach(unmountAll);

const results = [
  { label: "User List", description: "Open the list", route: "/user" },
  { label: "New User", route: "/user/new" },
];

describe("Search", () => {
  it("lists the results it is given and emits the chosen one", async () => {
    const selected: unknown[] = [];
    const root = await mount(Search, {
      results,
      onSelect: (item: unknown) => selected.push(item),
    });

    expect(rows(root).map((row) => row.textContent?.trim())).toEqual([
      "User ListOpen the list",
      "New User",
    ]);

    rows(root)[1].click();
    expect(selected).toEqual([results[1]]);
  });

  it("reports what is typed through v-model:query and fetches nothing itself", async () => {
    const queries: string[] = [];
    const root = await mount(Search, {
      results: [],
      query: "",
      "onUpdate:query": (value: string) => queries.push(value),
    });

    const input = root.querySelector("input")!;
    input.value = "user";
    input.dispatchEvent(new Event("input"));
    await nextTick();

    expect(queries).toEqual(["user"]);
  });

  it("hands the query to the empty slot, and waits while loading", async () => {
    const empty = ({ query }: { query: string }) => `none for ${query}`;

    const idle = await mount(Search, { results: [], query: "zz" }, { empty });
    expect(idle.textContent).toContain("none for zz");

    const loading = await mount(
      Search,
      { results: [], query: "zz", loading: true },
      { empty }
    );
    expect(loading.textContent).not.toContain("none for zz");
  });
});
