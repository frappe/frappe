// The list draws a Phone column's cells (a Phone field, or a Data field whose options say Phone)
// with the field actions, and every other column's cell as plain text.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

const columns = [
	{ fieldname: "mobile_no", label: "Mobile No" },
	{ fieldname: "phone", label: "Phone" },
	{ fieldname: "status", label: "Status" },
	{ fieldname: "email_id", label: "Email" },
];
const metaFields = [
	{ fieldname: "mobile_no", fieldtype: "Phone" },
	{ fieldname: "phone", fieldtype: "Data", options: "Phone" },
	{ fieldname: "status", fieldtype: "Data" },
	{ fieldname: "email_id", fieldtype: "Data", options: "Email" },
];

vi.mock("@/list/useListView", () => ({
	useListView: () => ({
		columns: ref(columns),
		rows: ref([{ name: "L1" }]),
		selection: ref([]),
		pageSize: ref(20),
		rowsKey: () => "",
		loading: ref(false),
		error: ref(null),
		rowCount: ref(1),
		totalCount: ref(1),
		totalCapped: ref(false),
		totalUnknown: ref(false),
		hasCounts: ref(true),
		hasNextPage: ref(false),
		rowActions: [],
		fieldOf: (fieldname: string) => metaFields.find((field) => field.fieldname === fieldname),
		columnsCustomized: ref(false),
		rowLink: () => ({}),
	}),
}));
vi.mock("@framework/ui/experimental/List", async () => {
	const { defineComponent, h } = await import("vue");
	const stub = () => defineComponent({ setup: () => () => null });
	return {
		ListBulkBar: stub(),
		ListFooter: stub(),
		// Draws the `cell` slot once per column, the way the table does per row.
		List: defineComponent({
			props: ["columns"],
			setup:
				(props, { slots }) =>
				() =>
					h(
						"div",
						props.columns.map((column: { fieldname: string }) =>
							h("div", { "data-column": column.fieldname }, slots.cell?.({ row: { name: "L1" }, column, value: "555" }))
						)
					),
		}),
	};
});
vi.mock("@/shell/PageState.vue", () => ({ default: defineComponent({ render: () => null }) }));

import { FieldActionsKey } from "@framework/ui/fields/types";
import ListView from "../ListView.vue";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

describe("a list's Phone columns", () => {
	it("draw the field actions in a Phone cell and none in another column's", async () => {
		const root = document.createElement("div");
		document.body.appendChild(root);
		const host = { controls: ref(null), onCreate: vi.fn(), acts: () => ({ drawn: () => null }) };
		const app = createApp(
			defineComponent({ render: () => h(ListView, { view: { doctype: "CRM Lead", filters: ref([]), sort: ref([]) } as never, host: host as never }) })
		);
		app.provide(FieldActionsKey, {
			for: (field, value, record) => [
				{ act: "a", label: `Call ${field.fieldname} ${value} ${JSON.stringify(record ?? null)}`, run: vi.fn() },
			],
		});
		app.mount(root);
		mounted.push(app);
		await nextTick();

		const labelIn = (column: string) =>
			root.querySelector(`[data-column='${column}'] [data-slot='field-action']`)?.getAttribute("aria-label");
		expect(labelIn("mobile_no")).toBe("Call mobile_no 555 null");
		expect(labelIn("phone")).toBe("Call phone 555 null");
		// An Email cell tells the host which row it sits on, and draws its button before the address.
		expect(labelIn("email_id")).toBe(
			'Call email_id 555 {"doctype":"CRM Lead","name":"L1","surface":"list"}'
		);
		const cell = root.querySelector("[data-column='email_id'] > div")!;
		expect(cell.firstElementChild?.getAttribute("data-slot")).toBe("email-cell-actions");
		expect(labelIn("status")).toBeUndefined();
		expect(root.querySelector("[data-column='status']")?.textContent).toBe("555");
	});
});
