// A Link field's Filters row: the target's meta through the meta cache, and a refused read.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, type App } from "vue";

const { toast, getMeta } = vi.hoisted(() => ({
	toast: { error: vi.fn(), success: vi.fn() },
	getMeta: vi.fn(),
}));
vi.mock("frappe-ui", async (importOriginal) => ({
	...(await importOriginal<typeof import("frappe-ui")>()),
	toast,
}));
vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	getMeta,
}));

import { ApiError } from "@framework/ui/api";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import LinkFiltersRow from "../LinkFiltersRow.vue";
import { mountEditor, taskNote } from "./editorFixture";

let app: App | undefined;
let stop: (() => void) | undefined;
afterEach(() => {
	app?.unmount();
	stop?.();
	app = stop = undefined;
	document.body.innerHTML = "";
	resetDoctypeMeta();
	getMeta.mockReset();
});

const CUSTOMER = {
	name: "Customer",
	fields: [
		{ fieldname: "disabled", label: "Disabled", fieldtype: "Check" },
		{ fieldname: "company", label: "Company", fieldtype: "Link", options: "Company" },
	],
};

async function mount(link_filters: string) {
	const state = taskNote();
	state.definition.fields.push(
		{ fieldname: "customer", label: "Customer", fieldtype: "Link", options: "Customer", link_filters },
		{ fieldname: "company", label: "Billing Company", fieldtype: "Link", options: "Company" },
	);
	const editor = mountEditor(state);
	stop = editor.stop;
	const host = document.body.appendChild(document.createElement("div"));
	app = createApp({ render: () => h(LinkFiltersRow, { canvas: editor.canvas, field: editor.canvas.field("customer")! }) });
	app.mount(host);
	for (let i = 0; i < 4; i++) await nextTick();
	await new Promise((resolve) => setTimeout(resolve, 0));
	return document.querySelector<HTMLButtonElement>('[data-rule-row="customer.link_filters"]')!;
}

describe("a Link field's Filters row", () => {
	it("reads the target's fields once, and says the filters in words", async () => {
		getMeta.mockResolvedValue({ data: CUSTOMER });
		const row = await mount(JSON.stringify([["Customer", "company", "=", "eval:doc.company"]]));
		expect(getMeta).toHaveBeenCalledTimes(1);
		expect(getMeta.mock.calls[0][0]).toBe("Customer");
		expect(row.disabled).toBe(false);
		expect(row.textContent).toContain("Company is this record's Billing Company");
	});

	it("opens the filters in the same dialog, titled with the field", async () => {
		getMeta.mockResolvedValue({ data: CUSTOMER });
		const row = await mount("");
		row.click();
		await vi.waitFor(() => expect(document.querySelector("[data-rule-editor]")).not.toBeNull());
		const dialog = document.querySelector("[role=dialog]")!;
		const title = document.getElementById(dialog.getAttribute("aria-labelledby")!)!;
		expect(title.textContent).toBe("Filters · Customer");
		expect(document.querySelector("[data-rule-clear]")!.textContent).toBe("Clear filters");
	});

	it("says Any <DocType> with no filters", async () => {
		getMeta.mockResolvedValue({ data: CUSTOMER });
		expect((await mount("")).textContent).toContain("Any Customer");
	});

	it("shows the row disabled, with a note, when the target cannot be read", async () => {
		getMeta.mockRejectedValue(new ApiError({ type: "PermissionError", message: "No" }, 403));
		const row = await mount("");
		expect(row.disabled).toBe(true);
		expect(document.querySelector("[data-link-filters-note]")!.textContent).toContain(
			"You cannot read Customer",
		);
	});

	it("still opens stored filters as code when the target cannot be read, so they can be cleared", async () => {
		getMeta.mockRejectedValue(new ApiError({ type: "PermissionError", message: "No" }, 403));
		const row = await mount(JSON.stringify([["Customer", "disabled", "=", 0]]));
		expect(row.disabled).toBe(false);
		expect(document.querySelector("[data-link-filters-note]")!.textContent).toContain("show as code");
	});
});
