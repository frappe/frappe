import { describe, expect, it } from "vitest";
import { ref } from "vue";
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
});
