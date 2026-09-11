import { describe, expect, it } from "vitest";
import { createCommitChannel } from "../commitChannel";
import type { RowAddress } from "@framework/ui/components/Fields/types";

function channel() {
  const fired: string[] = [];
  const addressed: (RowAddress | undefined)[] = [];
  const commits = createCommitChannel({
    dispatch: (event, row) => void (fired.push(event), addressed.push(row)),
  });
  return { commits, fired, addressed };
}

const row: RowAddress = { parentfield: "products", key: "row-1" };

describe("createCommitChannel", () => {
  it("fires a top-level field under its own name", () => {
    const { commits, fired } = channel();
    commits.commit("status", "Won");
    expect(fired).toEqual(["status"]);
  });

  it("addresses a child field by its table", () => {
    const { commits, fired } = channel();
    commits.commit("qty", 3, row);
    expect(fired).toEqual(["products.qty"]);
  });

  it("fires add and remove on the same dotted family", () => {
    const { commits, fired } = channel();
    commits.rowChanged(row, "add");
    commits.rowChanged(row, "remove");
    expect(fired).toEqual(["products.onAdd", "products.onRemove"]);
  });

  // A handle for a removed row throws on every access, so `.onRemove` gets `(page)` alone.
  it("carries the row on add and drops it on remove", () => {
    const { commits, addressed } = channel();
    commits.rowChanged(row, "add");
    commits.rowChanged(row, "remove");
    expect(addressed).toEqual([row, undefined]);
  });

  it("fires nothing while an edit is only pending", () => {
    const { commits, fired } = channel();
    commits.pending("qty", 3);
    expect(fired).toEqual([]);
  });

  it("flushes a pending edit once, then has nothing left to flush", async () => {
    const { commits, fired } = channel();
    commits.pending("qty", 3);
    await commits.flush();
    await commits.flush();
    expect(fired).toEqual(["qty"]);
  });

  it("flushes the pending edit at its row address", async () => {
    const { commits, fired } = channel();
    commits.pending("qty", 3, row);
    await commits.flush();
    expect(fired).toEqual(["products.qty"]);
  });

  it("a commit clears the pending edit, so a later save does not refire it", async () => {
    const { commits, fired } = channel();
    commits.pending("qty", 3);
    commits.commit("qty", 3);
    await commits.flush();
    expect(fired).toEqual(["qty"]);
  });

  it("a row add or remove clears the pending edit", async () => {
    const { commits, fired } = channel();
    commits.pending("qty", 3, row);
    commits.rowChanged(row, "remove");
    await commits.flush();
    expect(fired).toEqual(["products.onRemove"]);
  });

  it("ignores the echo a widget re-emits as it commits", async () => {
    const { commits, fired } = channel();
    commits.commit("qty", 3);
    commits.pending("qty", 3);
    await commits.flush();
    expect(fired).toEqual(["qty"]);
  });

  it("ignores the commit a repaint fires as it unmounts a focused input", async () => {
    const { commits, fired } = channel();
    commits.pending("qty", 3);
    await commits.flush();
    commits.commit("qty", 3);
    expect(fired).toEqual(["qty"]);
  });

  it("takes a real edit after a commit of the same field", async () => {
    const { commits, fired } = channel();
    commits.commit("qty", 3);
    commits.pending("qty", 4);
    await commits.flush();
    expect(fired).toEqual(["qty", "qty"]);
  });

  it("does not flush the same edit twice", async () => {
    const { commits, fired } = channel();
    commits.pending("qty", 3);
    await commits.flush();
    commits.pending("qty", 3);
    await commits.flush();
    expect(fired).toEqual(["qty"]);
  });

  it("awaits the handler it flushes, so the save cannot outrun it", async () => {
    const order: string[] = [];
    const commits = createCommitChannel({
      dispatch: async (event) => {
        await Promise.resolve();
        order.push(event);
      },
    });
    commits.pending("qty", 3);
    await commits.flush();
    order.push("beforeSave");
    expect(order).toEqual(["qty", "beforeSave"]);
  });
});
