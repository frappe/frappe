import { describe, expect, it } from "vitest";
import { nextTick, ref } from "vue";
import { useRowCursor } from "../useRowCursor";

function setup() {
  const cursor = ref<string | null>(null);
  const rendered = ref(["A", "B", "C"]);
  return { cursor, rendered, ...useRowCursor(cursor, () => rendered.value) };
}

describe("useRowCursor", () => {
  it("follows the pointer and clears when it leaves", () => {
    const { cursor, enter, leave } = setup();
    enter("A");
    expect(cursor.value).toBe("A");
    leave("A");
    expect(cursor.value).toBeNull();
  });

  it("keeps the focused row when the pointer leaves another row", () => {
    const { cursor, focus, enter, leave } = setup();
    focus("A");
    enter("B");
    expect(cursor.value).toBe("B");
    leave("B");
    expect(cursor.value).toBe("A");
  });

  it("keeps the hovered row when focus leaves it", () => {
    const { cursor, enter, focus, blur } = setup();
    enter("B");
    focus("B");
    blur("B");
    expect(cursor.value).toBe("B");
  });

  it("ignores the leave of a row that is not the cursor", () => {
    const { cursor, enter, leave } = setup();
    enter("A");
    enter("B");
    leave("A");
    expect(cursor.value).toBe("B");
  });

  it("drops a row that unmounts under the pointer", async () => {
    const { cursor, rendered, enter } = setup();
    enter("C");
    rendered.value = ["A", "B"];
    await nextTick();
    expect(cursor.value).toBeNull();
  });
});
