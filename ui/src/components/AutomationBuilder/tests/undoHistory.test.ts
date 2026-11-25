import { describe, expect, it } from "vitest";
import { effectScope, nextTick, reactive } from "vue";
import { useUndoHistory } from "../useUndoHistory";

/** The builder edits a reactive document; the watch it records through needs a scope. */
function withHistory(state, options) {
  const scope = effectScope();
  const history = scope.run(() =>
    useUndoHistory(
      state,
      (snapshot) => Object.assign(state, snapshot),
      options,
    ),
  );
  return { history, stop: () => scope.stop() };
}

describe("undo history", () => {
  it("steps an edit back", async () => {
    const doc = reactive({ title: "One" });
    const { history, stop } = withHistory(doc);

    doc.title = "Two";
    await nextTick();
    history.flush();
    history.undo();

    expect(doc.title).toBe("One");
    stop();
  });

  it("keeps the server timestamp an undo would otherwise put back", async () => {
    const doc = reactive({ title: "One", modified: "T0", name: "AUTO-0001" });
    const { history, stop } = withHistory(doc, {
      ignore: ["name", "creation", "owner", "modified"],
    });

    doc.title = "Two";
    await nextTick();
    history.flush();
    // A save writes the server's newer timestamp back, then absorbs it.
    doc.modified = "T1";
    history.absorb();
    history.undo();

    expect(doc.title).toBe("One");
    expect(doc.modified).toBe("T1");
    stop();
  });
});
