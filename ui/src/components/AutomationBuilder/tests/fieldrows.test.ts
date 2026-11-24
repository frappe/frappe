import { describe, expect, it } from "vitest";
import { useFieldRows } from "../params";

function harness(initial = {}) {
  let params = initial;
  const state = useFieldRows(
    () => params,
    (next) => {
      params = next;
    },
  );
  return { state, read: () => params };
}

describe("field/value row editing", () => {
  it("keeps a new empty row on screen even though params cannot store it", () => {
    const { state, read } = harness({ values: { status: "Junk" } });

    state.addRow();

    expect(state.rows.value).toEqual([
      { field: "status", value: "Junk" },
      { field: "", value: "" },
    ]);
    expect(read().values).toEqual({ status: "Junk" });
  });

  it("writes a row through to params once its field is chosen", () => {
    const { state, read } = harness({ values: { status: "Junk" } });

    state.addRow();
    state.setRow(1, "field", "lost_reason");
    state.setRow(1, "value", "Other");

    expect(read().values).toEqual({ status: "Junk", lost_reason: "Other" });
  });

  it("clears the value when the row switches to another field", () => {
    const { state } = harness({ values: { status: "Junk" } });

    state.setRow(0, "field", "lost_reason");

    expect(state.rows.value[0]).toEqual({ field: "lost_reason", value: "" });
  });

  it("removes a row", () => {
    const { state, read } = harness({
      values: { status: "Junk", lost_reason: "Other" },
    });

    state.removeRow(0);

    expect(read().values).toEqual({ lost_reason: "Other" });
  });

  it("reloads its rows when the step being edited changes", () => {
    let params = { values: { status: "Junk" } };
    const state = useFieldRows(
      () => params,
      (next) => {
        params = next;
      },
    );

    params = { values: { priority: "High" } };
    state.reload();

    expect(state.rows.value).toEqual([{ field: "priority", value: "High" }]);
  });
});
