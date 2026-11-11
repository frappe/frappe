import { beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";

const updateDocument = vi.hoisted(() => vi.fn());
const toastError = vi.hoisted(() => vi.fn());

vi.mock("@framework/ui/api", () => ({
	updateDocument,
	isApiError: (failure: any) => Boolean(failure?.isTimestampMismatch !== undefined),
}));
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
		render: () => h(SwitchCell, { doctype: "Automation Flow", field, row, writable }),
	}).mount(host);
	await nextTick();
	return host.querySelector("button")!;
}

const flow = (enabled: number) =>
	Object.freeze({ name: "AUTO-00001", enabled, modified: "2026-11-11 10:00:00" });

describe("SwitchCell", () => {
	beforeEach(() => {
		updateDocument.mockReset();
		toastError.mockReset();
	});

	it("writes the field with the row's modified and shows the saved value on a frozen row", async () => {
		updateDocument.mockResolvedValue({
			data: { enabled: 1, modified: "2026-11-11 10:00:05" },
		});
		const button = await mountCell(flow(0));
		button.click();
		await flushPromises();
		expect(updateDocument).toHaveBeenCalledWith("Automation Flow", "AUTO-00001", {
			enabled: 1,
			modified: "2026-11-11 10:00:00",
		});
		expect(button.getAttribute("aria-checked")).toBe("true");
		expect(toastError).not.toHaveBeenCalled();
	});

	it("sends the saved modified with the next write", async () => {
		updateDocument
			.mockResolvedValueOnce({ data: { enabled: 1, modified: "2026-11-11 10:00:05" } })
			.mockResolvedValueOnce({ data: { enabled: 0, modified: "2026-11-11 10:00:09" } });
		const button = await mountCell(flow(0));
		button.click();
		await flushPromises();
		button.click();
		await flushPromises();
		expect(updateDocument).toHaveBeenLastCalledWith("Automation Flow", "AUTO-00001", {
			enabled: 0,
			modified: "2026-11-11 10:00:05",
		});
	});

	it("leaves the switch as it was and says why when the server refuses", async () => {
		updateDocument.mockRejectedValue(new Error("Not permitted"));
		const button = await mountCell(flow(1));
		button.click();
		await flushPromises();
		expect(button.getAttribute("aria-checked")).toBe("true");
		expect(toastError).toHaveBeenCalledWith("Not permitted");
	});

	it("tells the person to reload when someone else saved the record", async () => {
		updateDocument.mockRejectedValue(Object.assign(new Error("x"), { isTimestampMismatch: true }));
		const button = await mountCell(flow(1));
		button.click();
		await flushPromises();
		expect(toastError).toHaveBeenCalledWith(expect.stringContaining("Reload the list"));
	});

	it("is disabled without a write right and names its row", async () => {
		const button = await mountCell(flow(1), false);
		expect(button.disabled).toBe(true);
		expect(button.getAttribute("aria-label")).toBe("Enabled AUTO-00001");
		button.click();
		expect(updateDocument).not.toHaveBeenCalled();
	});
});
