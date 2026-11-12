import { describe, expect, it } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import { useBulkScope } from "../useBulkScope";

const named = (names: string[]) => names.map((name) => ({ name }));

function setup(loaded = ["A", "B", "C"], total = 1240) {
  const rows = ref(named(loaded));
  const selection = ref<string[]>([]);
  const filters = ref<Record<string, unknown>>({ status: ["=", "Open"] });
  const more = ref(true);
  const exact = ref(true);
  const query = ref("open");
  const scope = effectScope().run(() =>
    useBulkScope({
      selection,
      rows: () => rows.value,
      filters: () => filters.value,
      rowsQuery: () => query.value,
      hasNextPage: () => more.value,
      totalCount: () => total,
      totalApprox: () => false,
      exact: () => exact.value,
    }),
  )!;
  return { scope, rows, selection, filters, more, exact, query };
}

describe("useBulkScope", () => {
  it("offers Select all only when every loaded row is selected and more match", () => {
    const { scope, selection, more } = setup();
    expect(scope.canSelectAll.value).toBe(false);
    selection.value = ["A", "B"];
    expect(scope.canSelectAll.value).toBe(false);
    selection.value = ["A", "B", "C"];
    expect(scope.canSelectAll.value).toBe(true);
    more.value = false;
    expect(scope.canSelectAll.value).toBe(false);
  });

  it("holds Select all back while the total or the filters do not match the rows", () => {
    const { scope, selection, exact } = setup();
    selection.value = ["A", "B", "C"];
    exact.value = false;
    expect(scope.canSelectAll.value).toBe(false);
    exact.value = true;
    expect(scope.canSelectAll.value).toBe(true);
  });

  it("keeps Select all on while a reload empties the rows", async () => {
    const { scope, rows, selection } = setup();
    selection.value = ["A", "B", "C"];
    scope.selectAll();
    await nextTick();
    rows.value = [];
    await nextTick();
    expect(scope.all.value).toBe(true);
    rows.value = named(["C", "B"]);
    await nextTick();
    expect(selection.value).toEqual(["C", "B"]);
  });

  it("sends the names until Select all, then the list's filters", () => {
    const { scope, selection } = setup();
    selection.value = ["A", "B", "C"];
    expect(scope.selected()).toEqual({ names: ["A", "B", "C"] });
    expect(scope.count.value).toBe(3);

    scope.selectAll();
    expect(scope.selected()).toEqual({ filters: { status: ["=", "Open"] } });
    expect(scope.count.value).toBe(1240);
    expect(scope.canSelectAll.value).toBe(false);
  });

  it("drops all-matching when a row is unchecked, keeping the other rows selected", async () => {
    const { scope, selection } = setup();
    selection.value = ["A", "B", "C"];
    scope.selectAll();
    selection.value = ["A", "B"];
    await nextTick();
    expect(scope.all.value).toBe(false);
    expect(scope.selected()).toEqual({ names: ["A", "B"] });
  });

  it("keeps all-matching across a load-more and selects the rows that join", async () => {
    const { scope, rows, selection } = setup();
    selection.value = ["A", "B", "C"];
    scope.selectAll();
    await nextTick();
    rows.value = named(["A", "B", "C", "D"]);
    await nextTick();
    expect(scope.all.value).toBe(true);
    expect(selection.value).toEqual(["A", "B", "C", "D"]);
  });

  it("keeps all-matching across a sort that reorders the rows", async () => {
    const { scope, rows, selection, query } = setup();
    selection.value = ["A", "B", "C"];
    scope.selectAll();
    await nextTick();
    query.value = "open, sorted by date";
    rows.value = named(["C", "B", "A"]);
    await nextTick();
    expect(scope.all.value).toBe(true);
    expect(scope.count.value).toBe(1240);
    expect(selection.value).toEqual(["C", "B", "A"]);
  });

  it("drops all-matching and its selection when the filters change", async () => {
    const { scope, selection, filters } = setup();
    selection.value = ["A", "B", "C"];
    scope.selectAll();
    await nextTick();
    filters.value = { status: ["=", "Closed"] };
    await nextTick();
    expect(scope.all.value).toBe(false);
    expect(selection.value).toEqual([]);
  });

  it("keeps the rows a new filter hides selected and counts them", async () => {
    const { scope, rows, selection, filters, query } = setup();
    selection.value = ["A", "B"];
    filters.value = { status: ["=", "Closed"] };
    rows.value = named(["B", "C"]);
    query.value = "closed";
    await nextTick();
    expect(selection.value).toEqual(["A", "B"]);
    expect(scope.count.value).toBe(2);
    expect(scope.selected()).toEqual({ names: ["A", "B"] });
  });

  it("lets a row that left under the same query leave the selection", async () => {
    const { scope, rows, selection } = setup();
    selection.value = ["A", "B"];
    rows.value = named(["B", "C"]);
    await nextTick();
    expect(selection.value).toEqual(["B"]);
    expect(scope.all.value).toBe(false);
  });

  it("keeps selected names that are not on the loaded page across a reload (Select failed)", async () => {
    const { scope, rows, selection } = setup();
    selection.value = ["X", "Y"];
    rows.value = named(["A", "B", "C"]);
    await nextTick();
    rows.value = named(["B", "C", "D"]);
    await nextTick();
    expect(selection.value).toEqual(["X", "Y"]);
    expect(scope.count.value).toBe(2);
    expect(scope.selected()).toEqual({ names: ["X", "Y"] });
  });

  it("holds Select all back while a hidden row is selected, since it would drop it", async () => {
    const { scope, rows, selection, query } = setup();
    selection.value = ["A", "B", "C"];
    rows.value = named(["B", "C", "D"]);
    query.value = "closed";
    await nextTick();
    selection.value = ["A", "B", "C", "D"];
    expect(scope.canSelectAll.value).toBe(false);
    selection.value = ["C", "B", "D"];
    expect(scope.canSelectAll.value).toBe(true);
  });
});
