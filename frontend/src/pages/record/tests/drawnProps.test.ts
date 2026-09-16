// The host's declared-prop lists, read off frappe-ui itself: an empty list would drop every key.
import { describe, expect, it } from "vitest";
import { recordDrawnProps } from "../drawnProps";

describe("recordDrawnProps", () => {
  it("reads Button's declared props off the component", () => {
    const { button } = recordDrawnProps();
    expect(button).toEqual(
      expect.arrayContaining(["variant", "theme", "size", "tooltip", "disabled", "loading", "route", "iconRight"]),
    );
    expect(button).not.toContain("class");
  });

  it("hand-lists the menu option's keys", () => {
    expect(recordDrawnProps().menuOption).toEqual(
      expect.arrayContaining(["description", "selected", "disabled", "theme", "condition", "route"]),
    );
  });
});
