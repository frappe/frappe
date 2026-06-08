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
];

function onChange(fieldname: string, value: any) {
	console.log("change", fieldname, value);
}
</script>
