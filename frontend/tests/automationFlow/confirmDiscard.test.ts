import { describe, expect, it, vi } from "vitest";

const dialogConfirm = vi.hoisted(() => vi.fn());
vi.mock("frappe-ui", () => ({ dialog: { confirm: dialogConfirm } }));

import { confirmDiscard } from "../../../frappe/automation/doctype/automation_flow/frontend/flow/confirmDiscard";

const answerWith = (handler: "onConfirm" | "onCancel") =>
  dialogConfirm.mockImplementationOnce((options) => options[handler]({ close: () => {} }));

describe("the discard question", () => {
  it("answers true when the person discards", async () => {
    answerWith("onConfirm");

    expect(await confirmDiscard()).toBe(true);
  });

  // frappe-ui calls `onCancel` for the Cancel button, Escape and a click outside alike.
  it("answers false when the dialog is cancelled or dismissed with Escape", async () => {
    answerWith("onCancel");

    expect(await confirmDiscard()).toBe(false);
  });
});
