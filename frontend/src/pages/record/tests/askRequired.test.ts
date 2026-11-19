// What the save path takes from the required-fields dialog.
import { describe, expect, it, vi } from "vitest";
import { askRequired } from "../askRequired";
import { SAVE_CANCELLED, shownInDialog } from "../saveResponse";

const layout = [] as any;

describe("askRequired", () => {
  it("resolves the values the dialog closes with", async () => {
    const dialog = { open: vi.fn(async () => ({ batch: "B1" })) } as any;

    await expect(askRequired(dialog, layout, {}, "Deal")).resolves.toEqual({ batch: "B1" });
  });

  it("tells the dialog a Submit asked, so its primary button reads Save and submit", async () => {
    const dialog = { open: vi.fn(async () => ({ batch: "B1" })) } as any;

    await askRequired(dialog, layout, {}, "Deal", true);

    expect(dialog.open.mock.calls[0][1]).toMatchObject({ submitting: true });
  });

  it("throws the cancelled error when the dialog closes with nothing", async () => {
    const dialog = { open: vi.fn(async () => undefined) } as any;

    const error = await askRequired(dialog, layout, {}, "Deal").catch((one) => one);

    expect(error.name).toBe(SAVE_CANCELLED);
    expect(shownInDialog(error)).toBe(true);
  });
});
