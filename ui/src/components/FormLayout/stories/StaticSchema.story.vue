<template>
	<div class="p-6 max-w-3xl">
		<FormLayout v-model:doc="doc" :layout="layout" @change="onChange" />
		<pre class="mt-6 text-xs text-ink-gray-6">doc = {{ doc }}</pre>
	</div>
</template>

<script setup lang="ts">
import { reactive } from "vue";
import FormLayout from "../FormLayout.vue";
import { registerFieldType } from "../fieldTypes";
import DemoLinkField from "./DemoLinkField.vue";
import DemoCurrencyField from "./DemoCurrencyField.vue";
import DemoTableMultiSelectField from "./DemoTableMultiSelectField.vue";
import type { FormLayoutSchema } from "../types";

// Override two fieldtypes for this story only. `{ global: false }` scopes the
// registration to this component's lifetime and auto-restores the previous
// mapping on unmount — so it doesn't leak into other stories (a global register
// here would also change the DoctypeLayout story). Called synchronously in setup
// so it's in place before the child fields render.
//   - Link: a behaviour-wired field (create/redirect/edit).
//   - Currency: a *fully custom* field — shows the registry override still wins.
registerFieldType("Link", DemoLinkField, { global: false });
registerFieldType("Currency", DemoCurrencyField, { global: false });
// Table MultiSelect: override the lib's select-only field with one that turns on
// `creatable` + wires `@create` — the app-owned create pattern (like DemoLinkField).
registerFieldType("Table MultiSelect", DemoTableMultiSelectField, {
	global: false,
});

const doc = reactive<Record<string, any>>({
	reference_id: "REF-0001",
	quantity: 1234,
	amount: 1234567.5,
	progress: 42.5,
	currency: "USD",
	rating: 0.6,
	duration: 5445,
	ref_type: "User",
	items: [
		{ item: "Widget", qty: 2, rate: 19.99, in_stock: true },
		{ item: "Gadget", qty: 5, rate: 4.5, in_stock: false },
	],
	// --- Grid edge-case data (second tab) -----------------------------------
	// Per-row conditionals: the two rows differ only by `qty`, so each cell
	// resolves its read-only/hidden/mandatory state against its OWN row — the
	// first row is fully editable, the second (qty 0) shows the flipped states.
	cond_items: [
		{ qty: 3, rate: 19.99, discount: 10, reason: "" },
		{ qty: 0, rate: 0, discount: 0, reason: "Backordered" },
	],
	// Parent-driven: every row's `rate` is read-only while this check is on,
	// via `eval:parent.lock_rates` — toggling it re-resolves all rows live.
	lock_rates: true,
	priced_items: [
		{ item: "Widget", rate: 19.99 },
		{ item: "Gadget", rate: 4.5 },
	],
	// Whole-grid read-only (`readOnly: true` on the Table field → disabled grid).
	locked_items: [
		{ item: "Nail", sku: "SKU-1", qty: 10, rate: 5 },
		{ item: "Hammer", sku: "SKU-2", qty: 3, rate: 12 },
	],
	// Empty grid → "No rows" placeholder.
	empty_items: [],
	// Many columns → horizontal scroll, scroll shadows, drag-to-resize.
	wide_items: [
		{
			c1: "alpha",
			c2: "bravo",
			c3: "charlie",
			c4: "delta",
			c5: "echo",
			c6: "foxtrot",
			c7: "golf",
		},
	],
});

const layout: FormLayoutSchema = [
	{
		name: "details",
		label: "Details",
		sections: [
			{
				name: "people",
				label: "People",
				columns: [
					{
						name: "col1",
						fields: [
							{
								fieldname: "owner",
								fieldtype: "Link",
								label: "Owner",
								options: "User",
							},
						],
					},
					{
						name: "col2",
						fields: [
							{
								fieldname: "title",
								fieldtype: "Data",
								label: "Title",
								placeholder: "Enter a title",
							},
						],
					},
				],
			},
			{
				name: "conditional",
				label: "Conditional",
				columns: [
					{
						name: "cond-col",
						fields: [
							{
								fieldname: "has_owner",
								fieldtype: "Check",
								label: "Assign an owner",
							},
							{
								fieldname: "assigned_to",
								fieldtype: "Link",
								label: "Assigned To",
								options: "User",
								// Shown only when the controlling check is ticked, and required then.
								dependsOn: "eval:doc.has_owner",
								mandatoryDependsOn: "eval:doc.has_owner",
							},
							{
								fieldname: "reference_id",
								fieldtype: "Data",
								label: "Reference ID (read-only)",
								readOnly: true,
							},
						],
					},
				],
			},
			{
				name: "fieldtypes",
				label: "Fieldtypes",
				columns: [
					{
						name: "col-a",
						fields: [
							{
								fieldname: "status",
								fieldtype: "Select",
								label: "Status",
								options: "Open\nIn Progress\nClosed",
							},
							{ fieldname: "active", fieldtype: "Check", label: "Active" },
							{ fieldname: "due_date", fieldtype: "Date", label: "Due Date" },
							{ fieldname: "remind_at", fieldtype: "Datetime", label: "Remind At" },
							{ fieldname: "start_time", fieldtype: "Time", label: "Start Time" },
						],
					},
					{
						name: "col-b",
						fields: [
							{ fieldname: "quantity", fieldtype: "Int", label: "Quantity" },
							// `options` names the sibling field holding this row's currency code.
							{
								fieldname: "currency",
								fieldtype: "Select",
								label: "Currency",
								options: "USD\nEUR\nINR",
							},
							{
								fieldname: "amount",
								fieldtype: "Currency",
								label: "Amount",
								options: "currency",
								precision: 2,
							},
							{
								fieldname: "progress",
								fieldtype: "Percent",
								label: "Progress",
								precision: 1,
							},
							{
								fieldname: "notes",
								fieldtype: "Text",
								label: "Notes",
								placeholder: "Add notes",
							},
							{ fieldname: "secret", fieldtype: "Password", label: "Secret" },
							{
								fieldname: "phone",
								fieldtype: "Phone",
								label: "Phone",
								placeholder: "+1 555 123 4567",
							},
							{
								fieldname: "config",
								fieldtype: "JSON",
								label: "Config (JSON)",
								placeholder: '{ "key": "value" }',
							},
						],
					},
				],
			},
			{
				name: "pickers",
				label: "Pickers",
				columns: [
					{
						name: "pick-col",
						fields: [
							{
								fieldname: "tags",
								fieldtype: "Autocomplete",
								label: "Tag",
								options: "Bug\nFeature\nChore",
								placeholder: "Pick or type a tag",
							},
							{
								fieldname: "rating",
								fieldtype: "Rating",
								label: "Rating",
								// star count (Frappe stores the value as a 0..1 fraction)
								options: "5",
							},
							{
								fieldname: "duration",
								fieldtype: "Duration",
								label: "Time spent",
							},
							{
								fieldname: "ref_type",
								fieldtype: "Select",
								label: "Reference Type",
								options: "User\nContact",
							},
							{
								// `options` names the sibling field holding the target doctype.
								fieldname: "ref_name",
								fieldtype: "Dynamic Link",
								label: "Reference Name",
								options: "ref_type",
							},
							{
								// `options` names the child doctype; its single Link
								// field (here `user`) names the real target doctype and
								// the key each stored row holds the value under. In the
								// doctype-driven flow `childFields` is resolved from the
								// child meta — for this static schema we supply it inline.
								fieldname: "assignees",
								fieldtype: "Table MultiSelect",
								label: "Assignees",
								options: "Assignee Detail",
								childFields: [
									{
										fieldname: "user",
										fieldtype: "Link",
										options: "User",
									},
								],
							},
						],
					},
				],
			},
			{
				name: "table-section",
				label: "Items",
				columns: [
					{
						name: "table-col",
						fields: [
							{
								// `options` names the child doctype; `childFields`
								// are its grid columns (in the doctype-driven flow
								// they're resolved from the child meta — supplied
								// inline here). The grid renders each cell via the
								// fieldtype registry; the edit action opens the row
								// as a form (FormLayout) in a dialog.
								fieldname: "items",
								fieldtype: "Table",
								label: "Line Items",
								options: "Item Detail",
								childFields: [
									{
										fieldname: "item",
										fieldtype: "Data",
										label: "Item",
										reqd: true,
									},
									{
										fieldname: "qty",
										fieldtype: "Int",
										label: "Qty",
									},
									{
										fieldname: "rate",
										fieldtype: "Currency",
										label: "Rate",
									},
									{
										fieldname: "in_stock",
										fieldtype: "Check",
										label: "In Stock",
									},
									{
										fieldname: "notes",
										fieldtype: "Small Text",
										label: "Notes",
									},
								],
							},
						],
					},
				],
			},
			{
				name: "display",
				label: "Display-only",
				columns: [
					{
						name: "display-col",
						fields: [
							{
								fieldname: "section_heading",
								fieldtype: "Heading",
								label: "Contact details",
							},
							{
								fieldname: "help_html",
								fieldtype: "HTML",
								label: "Help",
								options:
									"<p>Fill in the fields above. <strong>Phone</strong> is optional.</p>",
							},
						],
					},
				],
			},
			{
				name: "misc",
				label: "Miscellaneous",
				collapsible: true,
				opened: false,
				columns: [
					{
						name: "col3",
						fields: [
							{
								fieldname: "mystery",
								fieldtype: "SomethingUnknown",
								label: "Unknown fieldtype (falls back to text)",
							},
						],
					},
				],
			},
		],
	},
	{
		name: "grid-edge",
		label: "Grid edge cases",
		sections: [
			{
				name: "per-row-cond",
				label: "Per-row conditionals",
				columns: [
					{
						name: "per-row-col",
						fields: [
							{
								// Each cell resolves its conditionals against its own row, so
								// the two rows below render differently from the same columns —
								// matching what the row-edit dialog shows for that row.
								fieldname: "cond_items",
								fieldtype: "Table",
								label: "Conditional Items (edit qty to flip the row)",
								options: "Conditional Item",
								childFields: [
									{ fieldname: "qty", fieldtype: "Int", label: "Qty" },
									{
										// Read-only while qty is 0 (`!doc.qty`) — editable otherwise.
										fieldname: "rate",
										fieldtype: "Currency",
										label: "Rate",
										readOnlyDependsOn: "eval:!doc.qty",
									},
									{
										// Hidden when qty is 0 → that row renders an empty cell.
										fieldname: "discount",
										fieldtype: "Percent",
										label: "Discount %",
										dependsOn: "eval:doc.qty > 0",
									},
									{
										// Mandatory when qty is 0 (a reason is required for a
										// zero-qty line). Per-row `reqd` drives validation and shows
										// in the row-edit dialog; the grid header star stays static.
										fieldname: "reason",
										fieldtype: "Data",
										label: "Reason",
										mandatoryDependsOn: "eval:!doc.qty",
									},
								],
							},
						],
					},
				],
			},
			{
				name: "parent-driven",
				label: "Parent-driven (eval:parent.x)",
				columns: [
					{
						name: "parent-col",
						fields: [
							{
								// A doc-level control the child rows read via `parent`.
								fieldname: "lock_rates",
								fieldtype: "Check",
								label: "Lock all rates",
							},
							{
								fieldname: "priced_items",
								fieldtype: "Table",
								label: "Priced Items (toggle the check to lock every Rate)",
								options: "Priced Item",
								childFields: [
									{ fieldname: "item", fieldtype: "Data", label: "Item" },
									{
										// `parent` is the doc the table lives on, so every row's
										// rate follows the doc-level `lock_rates` — desk's
										// `parent = this.frm.doc`. Re-resolves live on toggle.
										fieldname: "rate",
										fieldtype: "Currency",
										label: "Rate",
										readOnlyDependsOn: "eval:parent.lock_rates",
									},
								],
							},
						],
					},
				],
			},
			{
				name: "grid-states",
				label: "Read-only, empty & missing columns",
				columns: [
					{
						name: "states-col",
						fields: [
							{
								// `readOnly: true` disables structural actions (add/delete/
								// reorder/select), renders every cell read-only, and makes a
								// click anywhere on a row open the dialog as a read-only viewer.
								fieldname: "locked_items",
								fieldtype: "Table",
								label: "Read-only grid (click a row to view)",
								readOnly: true,
								options: "Locked Item",
								childFields: [
									{ fieldname: "item", fieldtype: "Link", label: "CRM Product" },
									{ fieldname: "sku", fieldtype: "Data", label: "SKU" },
									{ fieldname: "qty", fieldtype: "Int", label: "Qty" },
									{ fieldname: "rate", fieldtype: "Currency", label: "Rate" },
								],
							},
							{
								// No rows → the grid shows its "No rows" placeholder.
								fieldname: "empty_items",
								fieldtype: "Table",
								label: "Empty grid",
								options: "Empty Item",
								childFields: [
									{ fieldname: "item", fieldtype: "Data", label: "Item" },
									{ fieldname: "qty", fieldtype: "Int", label: "Qty" },
								],
							},
							{
								// No `childFields` resolved → the grid shows "No columns to
								// display" (e.g. when a child meta is absent).
								fieldname: "no_columns",
								fieldtype: "Table",
								label: "Grid with no columns",
								options: "Columnless Item",
							},
						],
					},
				],
			},
			{
				name: "grid-wide",
				label: "Wide grid (scroll + resize)",
				columns: [
					{
						name: "wide-col",
						fields: [
							{
								// Enough columns to overflow → horizontal scroll with the frozen
								// `#`/edit columns, scroll shadows, and drag-to-resize handles.
								// Each column declares a default `width` (px) from the layout;
								// dragging a column's right edge still overrides it.
								fieldname: "wide_items",
								fieldtype: "Table",
								label: "Wide Items",
								options: "Wide Item",
								childFields: [
									{
										fieldname: "c1",
										fieldtype: "Data",
										label: "Column One",
										width: 200,
									},
									{
										fieldname: "c2",
										fieldtype: "Data",
										label: "Column Two",
										width: 200,
									},
									{
										fieldname: "c3",
										fieldtype: "Data",
										label: "Column Three",
										width: 200,
									},
									{
										fieldname: "c4",
										fieldtype: "Data",
										label: "Column Four",
										width: 200,
									},
									{
										fieldname: "c5",
										fieldtype: "Data",
										label: "Column Five",
										width: 200,
									},
									{
										fieldname: "c6",
										fieldtype: "Data",
										label: "Column Six",
										width: 200,
									},
									{
										fieldname: "c7",
										fieldtype: "Data",
										label: "Column Seven",
										width: 200,
									},
								],
							},
						],
					},
				],
			},
		],
	},
];

function onChange(fieldname: string, value: any) {
	console.log("change", fieldname, value);
}
</script>
