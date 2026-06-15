import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import { useChildRowModel } from "../useChildRowModel";

describe("useChildRowModel", () => {
  it("reads link values out of the stored child rows", () => {
    const rows = [{ user: "a@x.com" }, { user: "b@x.com" }];
    const value = useChildRowModel(
      () => rows,
      () => "user",
      () => {}
    );
    expect(value.value).toEqual(["a@x.com", "b@x.com"]);
  });

  it("treats a non-array (or absent) value as empty", () => {
    const value = useChildRowModel(
      () => undefined,
      () => "user",
      () => {}
    );
    expect(value.value).toEqual([]);
  });

  it("emits update:modelValue and change as child rows on write", () => {
    const emit = vi.fn();
    const value = useChildRowModel(
      () => [],
      () => "user",
      emit
    );
    value.value = ["a@x.com"];
    expect(emit).toHaveBeenCalledWith("update:modelValue", [
      { user: "a@x.com" },
    ]);
    expect(emit).toHaveBeenCalledWith("change", [{ user: "a@x.com" }]);
  });

  it("reuses the existing row object for values that stay selected", () => {
    const kept = { user: "a@x.com", doctype: "Assignee", name: "row-1" };
    const emit = vi.fn();
    const value = useChildRowModel(
      () => [kept],
      () => "user",
      emit
    );
    // re-select the same value plus a new one
    value.value = ["a@x.com", "b@x.com"];
    const next = emit.mock.calls.find((c) => c[0] === "update:modelValue")![1];
    // existing row preserved by reference (name/doctype survive); new one minted
    expect(next[0]).toBe(kept);
    expect(next[1]).toEqual({ user: "b@x.com" });
  });

  it("is reactive to the underlying rows ref", () => {
    const rows = ref<Record<string, any>[]>([{ user: "a@x.com" }]);
    const value = useChildRowModel(
      () => rows.value,
      () => "user",
      () => {}
    );
    expect(value.value).toEqual(["a@x.com"]);
    rows.value = [{ user: "a@x.com" }, { user: "c@x.com" }];
    expect(value.value).toEqual(["a@x.com", "c@x.com"]);
  });
});
