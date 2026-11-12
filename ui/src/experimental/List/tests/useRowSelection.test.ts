import { describe, expect, it } from "vitest";
import { nextTick, ref } from "vue";
import { useRowSelection } from "../useRowSelection";

function setup(selected: string[] = []) {
  const selection = ref(selected);
  const rows = ref([{ name: "A" }, { name: "B" }, { name: "C" }]);
  const rowKey = ref("name");
  return { selection, rows, ...useRowSelection(selection, rows, rowKey) };
}

describe("useRowSelection", () => {
  it("toggles one row in and out", () => {
    const { selection, toggle } = setup();
    toggle("B");
    expect(selection.value).toEqual(["B"]);
    toggle("B");
    expect(selection.value).toEqual([]);
  });

  it("reports none, some and all", () => {
    const { selection, selectAllState } = setup();
    expect(selectAllState.value).toBe("none");
    selection.value = ["A"];
    expect(selectAllState.value).toBe("some");
    selection.value = ["A", "B", "C"];
    expect(selectAllState.value).toBe("all");
  });

  it("reads some while only rows that are not shown are selected", () => {
    const { selectAllState } = setup(["Z"]);
    expect(selectAllState.value).toBe("some");
  });

  it("select-all adds every shown row and keeps rows selected elsewhere", () => {
    const { selection, toggleSelectAll } = setup(["Z"]);
    toggleSelectAll();
    expect(selection.value).toEqual(["Z", "A", "B", "C"]);
  });

  it("select-all on a full selection clears only the shown rows", () => {
    const { selection, toggleSelectAll } = setup(["Z", "A", "B", "C"]);
    toggleSelectAll();
    expect(selection.value).toEqual(["Z"]);
  });

  it("reads the key the host names", () => {
    const selection = ref<string[]>([]);
    const rows = ref([{ id: 1 }, { id: 2 }]);
    const { toggleSelectAll } = useRowSelection(selection, rows, ref("id"));
    toggleSelectAll();
    expect(selection.value).toEqual(["1", "2"]);
  });

  describe("ranges", () => {
    function five(selected: string[] = []) {
      const selection = ref(selected);
      const rows = ref(["A", "B", "C", "D", "E"].map((name) => ({ name })));
      return { selection, ...useRowSelection(selection, rows, ref("name")) };
    }

    it("selects the rows between the last toggled row and a shift-toggled one", () => {
      const { selection, toggle } = five();
      toggle("B");
      toggle("D", true);
      expect([...selection.value].sort()).toEqual(["B", "C", "D"]);
    });

    it("runs a range upwards too", () => {
      const { selection, toggle } = five();
      toggle("D");
      toggle("B", true);
      expect([...selection.value].sort()).toEqual(["B", "C", "D"]);
    });

    it("gives the range the state the clicked row takes", () => {
      const { selection, toggle } = five(["A", "B", "C", "D", "E"]);
      toggle("B");
      toggle("D", true);
      expect([...selection.value].sort()).toEqual(["A", "E"]);
    });

    it("toggles one row when nothing was toggled before", () => {
      const { selection, toggle } = five();
      toggle("C", true);
      expect(selection.value).toEqual(["C"]);
    });

    it("forgets the anchor once the selection empties", async () => {
      const { selection, toggle } = five();
      toggle("A");
      selection.value = [];
      await nextTick();
      toggle("D", true);
      expect(selection.value).toEqual(["D"]);
    });

    it("forgets the anchor when the toggle itself empties the selection", () => {
      const { selection, toggle } = five();
      toggle("A");
      toggle("A");
      toggle("D", true);
      expect(selection.value).toEqual(["D"]);
    });

    it("extends from the anchor and moves it", () => {
      const { selection, toggle, extendTo } = five();
      toggle("B");
      extendTo("C");
      extendTo("E");
      expect([...selection.value].sort()).toEqual(["B", "C", "D", "E"]);
    });

    it("extends to a row alone when there is no anchor, and ignores an anchor that is gone", () => {
      const lone = five();
      lone.extendTo("C");
      expect(lone.selection.value).toEqual(["C"]);

      const selection = ref<string[]>([]);
      const rows = ref([{ name: "A" }, { name: "B" }]);
      const gone = useRowSelection(selection, rows, ref("name"));
      gone.toggle("A");
      rows.value = [{ name: "B" }, { name: "C" }];
      gone.extendTo("C");
      expect([...selection.value].sort()).toEqual(["A", "C"]);
    });
  });
});
