// A list's switch cell saves its Check field with the row's `modified`, and the row changes only when the server accepts.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";

const updateDocument = vi.hoisted(() => vi.fn());
const toastError = vi.hoisted(() => vi.fn());

vi.mock("@framework/ui/api", () => ({ updateDocument }));
vi.mock("frappe-ui", () => ({
  Switch: {
    props: ["modelValue", "disabled"],
    emits: ["update:modelValue"],
    template: `<button :disabled="disabled" :aria-checked="modelValue" @click="$emit('update:modelValue', !modelValue)" />`,
  },
  toast: { error: toastError },
}));
vi.mock("@/recordPage", () => ({
  errorMessage: (failure: Error) => failure.message,
}));

import SwitchCell from "../SwitchCell.vue";

const field = { fieldname: "enabled", fieldtype: "Check", label: "Enabled" };

const flushPromises = () => new Promise((resolve) => setTimeout(resolve));

async function mountCell(row: Record<string, unknown>, writable = true) {
  const host = document.createElement("div");
  createApp({
    render: () =>
      h(SwitchCell, { doctype: "Automation Flow", field, row, writable }),
  }).mount(host);
  await nextTick();
  return host.querySelector("button")!;
}

describe("SwitchCell", () => {
  beforeEach(() => {
    updateDocument.mockReset();
    toastError.mockReset();
  });

  it("writes the field with the row's modified and takes the saved values", async () => {
    const row = {
      name: "AUTO-00001",
      enabled: 0,
      modified: "2026-11-11 10:00:00",
    };
    updateDocument.mockResolvedValue({
      data: { enabled: 1, modified: "2026-11-11 10:00:05" },
    });
    const button = await mountCell(row);
    button.click();
    await flushPromises();
    expect(updateDocument).toHaveBeenCalledWith(
      "Automation Flow",
      "AUTO-00001",
      {
        enabled: 1,
        modified: "2026-11-11 10:00:00",
      }
    );
    expect(row).toMatchObject({ enabled: 1, modified: "2026-11-11 10:00:05" });
  });

  it("leaves the row as it was and says why when the server refuses", async () => {
    const row = {
      name: "AUTO-00001",
      enabled: 1,
      modified: "2026-11-11 10:00:00",
    };
    updateDocument.mockRejectedValue(new Error("Document has been modified"));
    const button = await mountCell(row);
    button.click();
    await flushPromises();
    expect(row.enabled).toBe(1);
    expect(toastError).toHaveBeenCalledWith("Document has been modified");
  });

  it("is disabled without a write right", async () => {
    const button = await mountCell({ name: "AUTO-00001", enabled: 1 }, false);
    expect(button.disabled).toBe(true);
  });
});
