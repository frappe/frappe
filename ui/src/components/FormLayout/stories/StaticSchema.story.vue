<template>
	<div class="p-6 max-w-3xl">
		<!-- No `@change`: `FormLayout` emits nothing. Per-field actions/side-effects
		     ride the node's `ui.on`; "react to all" would be `watch(doc, …)`. -->
		<FormLayout v-model:doc="doc" :layout="layout" />
		<pre class="mt-6 text-xs text-ink-gray-6">doc = {{ doc }}</pre>
	</div>
</template>

<script setup lang="ts">
import { reactive } from "vue";
import FormLayout from "../FormLayout.vue";
import { registerFieldType } from "../../Fields/fieldTypes";
import DemoLinkField from "./DemoLinkField.vue";
import DemoCurrencyField from "./DemoCurrencyField.vue";
import DemoTableMultiSelectField from "./DemoTableMultiSelectField.vue";
import type { FormLayoutSchema } from "../types";
import type { UploadTransport } from "../../FileUpload/types";

// Fake transport for the stories: no backend, just a placeholder URL and a
// simulated progress ramp (honoring the abort signal). The Attach/Attach Image
// fields receive it via their `ui.props` overlay.
const fakeTransport: UploadTransport = (file, _args, ctx) =>
	new Promise((resolve, reject) => {
		const total = file.size || 1000;
		let loaded = 0;
		const onAbort = () => reject(new DOMException("Cancelled", "AbortError"));
		ctx.signal.addEventListener("abort", onAbort, { once: true });
		const tick = () => {
			if (ctx.signal.aborted) return;
			loaded = Math.min(total, loaded + Math.ceil(total / 4));
			ctx.onProgress(loaded, total);
			if (loaded < total) {
				setTimeout(tick, 250);
			} else {
				ctx.signal.removeEventListener("abort", onAbort);
				resolve({
					file_url: `https://placehold.co/600x400?text=${encodeURIComponent(file.name)}`,
				});
			}
		};
		setTimeout(tick, 250);
	});

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
	// Drives the `view` of the Markdown/HTML editors below (the `editor_view`
	// Select field writes it; their `ui.props.view` getters read it back).
	editor_view: "auto",
	reference_id: "REF-0001",
	quantity: 1234,
	amount: 1234567.5,
	progress: 42.5,
	currency: "USD",
	rating: 0.6,
	duration: 5445,
	ref_type: "User",
	// Code-family fields hold strings (Frappe JSON/Code fields store strings).
	// Seeded long + already 2-space pretty-printed (matches the JSON field's
	// commit format, so blur won't reformat) to exercise the editor's height
	// cap + Expand/Collapse action — it overflows the collapsed height on load.
	settings: JSON.stringify(
		{
			theme: "dark",
			retries: 3,
			timeout: 30000,
			features: {
				search: true,
				notifications: true,
				betaPanels: false,
			},
			integrations: [
				{ name: "github", enabled: true },
				{ name: "slack", enabled: false },
				{ name: "jira", enabled: true },
			],
			limits: { maxUsers: 50, maxProjects: 10, storageGb: 100 },
			locale: "en-US",
		},
		null,
		2
	),
	script: "def greet(name):\n\treturn f'Hello, {name}!'",
	readme: "# Project\n\nSome **bold** text and a [link](https://frappe.io).",
	snippet: "<h2>Title</h2>\n<p>Edit the HTML and preview it.</p>",
	styles: ".card {\n\t.title { color: var(--ink-gray-9); }\n}",
	manifest: "name: app\nversion: 1\ndeps:\n  - frappe\n  - vue",
	feed: '<rss version="2.0">\n\t<channel><title>Feed</title></channel>\n</rss>',
	// Attach fields hold a single `file_url` string (or null); Image mirrors one.
	// Pre-seeded so preview / hover-zoom / Replace are exercisable without first
	// uploading: a non-image file (paperclip + open-original) and an image
	// (thumbnail + hover-zoom).
	attachment: "https://frappe.io/files/sample-report.pdf",
	photo: "https://placehold.co/600x400?text=Photo",
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
	// Every registered fieldtype as a grid column — the "does this render in a
	// 34px cell" audit surface. Sibling columns back the relative fieldtypes:
	// `cur` → `amt` (Currency code), `link_type` → `dyn` (Dynamic Link target),
	// `aimg` → `img` (Image mirror).
	all_fieldtypes: [
		{
			data: "Alpha",
			linked: "Administrator",
			link_type: "User",
			dyn: "Administrator",
			sel: "Open",
			auto: "Bug",
			chk: 1,
			stars: 0.6,
			int_v: 42,
			float_v: 3.14,
			cur: "USD",
			amt: 1999.5,
			pct: 75,
			dur: 3665,
			date_v: "2026-06-14",
			dt_v: "2026-06-14 10:30:00",
			time_v: "10:30:00",
			stext: "Short note",
			text_v: "Some text spanning the cell width.",
			ltext: "A longer body of text for the long-text column.",
			pwd: "s3cret",
			phone_v: "+1 555 0100",
			code_v: "print('hi')",
			json_v: '{ "a": 1 }',
			md_v: "# Title",
			html_v: "<p>hi</p>",
			geo: null,
			attach_v: "https://frappe.io/files/sample-report.pdf",
			aimg: "https://placehold.co/600x400?text=Row+1",
			ro: "RO-1",
			assignees: [{ user: "Administrator" }],
			lines: [{ label: "x", val: 1 }],
		},
		{
			data: "Bravo",
			linked: "Guest",
			link_type: "Contact",
			dyn: "",
			sel: "Closed",
			auto: "Chore",
			chk: 0,
			stars: 0.2,
			int_v: 7,
			float_v: 2.5,
			cur: "EUR",
			amt: 49.99,
			pct: 10,
			dur: 90,
			date_v: "2026-07-01",
			dt_v: "2026-07-01 09:00:00",
			time_v: "09:00:00",
			stext: "",
			text_v: "",
			ltext: "",
			pwd: "",
			phone_v: "",
			code_v: "x = 1",
			json_v: '{ "b": 2 }',
			md_v: "## Sub",
			html_v: "<em>row 2</em>",
			geo: null,
			attach_v: null,
			aimg: "https://placehold.co/600x400?text=Row+2",
			ro: "RO-2",
			assignees: [],
			lines: [],
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
							{
								// A *value* field's commit-time side-effect rides `ui.on.change`
								// (the home the removed `@change` used to serve) — here it
								// derives `amount` from the committed quantity, writing a sibling
								// on the reactive `doc`. This is exactly where field-change
								// scripting would attach.
								fieldname: "quantity",
								fieldtype: "Int",
								label: "Quantity",
								ui: { on: { change: (value) => onQuantityCommit(value) } },
							},
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
								description: "Add one row per line item; drag to reorder.",
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
		name: "code-editors-tab",
		label: "Code editors",
		sections: [
			{
				name: "code-editors",
				columns: [
					{
						name: "code-col",
						fields: [
							{
								// Drives the layout of the Markdown/HTML editors below —
								// a Select field inside the form, so the control is itself
								// part of the schema (writes `doc.editor_view`).
								fieldname: "editor_view",
								fieldtype: "Select",
								label: "Editor view (Markdown / HTML)",
								options: "auto\nsplit\nstacked\neditor",
							},
							{
								// JSON: highlighting + lint gutter on invalid JSON, and
								// pretty-printed on commit (blur).
								fieldname: "settings",
								fieldtype: "JSON",
								label: "Settings (JSON)",
								placeholder: '{ "key": "value" }',
							},
							{
								// Code: language derived from `options` (core's Ace mode).
								fieldname: "script",
								fieldtype: "Code",
								label: "Script (Python)",
								options: "Python",
							},
							{
								// SCSS via the `lang-sass` package (Code option → scss).
								fieldname: "styles",
								fieldtype: "Code",
								label: "Styles (SCSS)",
								options: "SCSS",
							},
							{
								// YAML highlighting (Code option → yaml).
								fieldname: "manifest",
								fieldtype: "Code",
								label: "Manifest (YAML)",
								options: "YAML",
							},
							{
								// XML highlighting (Code option → xml).
								fieldname: "feed",
								fieldtype: "Code",
								label: "Feed (XML)",
								options: "XML",
							},
							{
								// Markdown Editor: live sanitized preview (stacked or split).
								// `view` getter lets the Select above force the layout.
								fieldname: "readme",
								fieldtype: "Markdown Editor",
								label: "Readme (Markdown)",
								ui: {
									props: {
										get view() {
											return doc.editor_view;
										},
									},
								},
							},
							{
								// HTML Editor: live sanitized preview (stacked or split).
								fieldname: "snippet",
								fieldtype: "HTML Editor",
								label: "Snippet (HTML)",
								ui: {
									props: {
										get view() {
											return doc.editor_view;
										},
									},
								},
							},
						],
					},
				],
			},
		],
	},
	{
		name: "pickers-tab",
		label: "Pickers",
		sections: [
			{
				name: "pickers",
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
		],
	},
	{
		name: "attachments-tab",
		label: "Attachments",
		sections: [
			{
				name: "attachments",
				columns: [
					{
						name: "attach-col",
						fields: [
							{
								// Single `file_url` string. The fake transport is supplied via
								// the `ui.props` overlay — not part of FieldMeta.
								fieldname: "attachment",
								fieldtype: "Attach",
								label: "Attachment",
								ui: { props: { transport: fakeTransport } },
							},
							{
								// Attach Image: same component, image-only + crop enabled.
								fieldname: "photo",
								fieldtype: "Attach Image",
								label: "Photo",
								ui: { props: { transport: fakeTransport } },
							},
							{
								// Display-only: mirrors the URL held by the `photo` field above.
								fieldname: "photo_preview",
								fieldtype: "Image",
								label: "Photo preview",
								options: "photo",
							},
						],
					},
				],
			},
		],
	},
	{
		name: "display-tab",
		label: "Display-only",
		sections: [
			{
				name: "display",
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
							{
								// Self-describing: presentation + action live on the node's
								// `ui` overlay. The click rides `ui.on.click` (no `@change`
								// hack, no host fieldname dispatch); `props` style the Button.
								fieldname: "send_invite",
								fieldtype: "Button",
								label: "Send invite",
								ui: {
									props: { variant: "solid", theme: "blue", size: "md" },
									on: { click: () => sendInvite() },
								},
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
			{
				name: "grid-all-fieldtypes",
				label: "Every fieldtype as a column",
				columns: [
					{
						name: "all-col",
						fields: [
							{
								// One column per registered fieldtype. Input-like types
								// edit inline; types that can't fit a 34px cell (code
								// editors, nested Table, Table MultiSelect, Image, and
								// display-only Heading/HTML) render a read-only summary
								// and edit in the row dialog (TableField's denylist).
								// Each column is fixed-width so the grid scrolls
								// horizontally; sibling columns back the relative
								// fieldtypes (Currency/Dynamic Link/Image).
								fieldname: "all_fieldtypes",
								fieldtype: "Table",
								label: "All fieldtypes",
								options: "All Fieldtype Detail",
								childFields: [
									{
										fieldname: "data",
										fieldtype: "Data",
										label: "Data",
										width: 140,
									},
									{
										fieldname: "linked",
										fieldtype: "Link",
										label: "Link",
										options: "User",
										width: 160,
									},
									{
										fieldname: "link_type",
										fieldtype: "Select",
										label: "Link Type",
										options: "User\nContact",
										width: 130,
									},
									{
										fieldname: "dyn",
										fieldtype: "Dynamic Link",
										label: "Dynamic Link",
										options: "link_type",
										width: 160,
									},
									{
										fieldname: "sel",
										fieldtype: "Select",
										label: "Select",
										options: "Open\nIn Progress\nClosed",
										width: 140,
									},
									{
										fieldname: "auto",
										fieldtype: "Autocomplete",
										label: "Autocomplete",
										options: "Bug\nFeature\nChore",
										width: 150,
									},
									{
										fieldname: "chk",
										fieldtype: "Check",
										label: "Check",
										width: 80,
									},
									{
										fieldname: "stars",
										fieldtype: "Rating",
										label: "Rating",
										options: "5",
										width: 130,
									},
									{
										fieldname: "int_v",
										fieldtype: "Int",
										label: "Int",
										width: 100,
									},
									{
										fieldname: "float_v",
										fieldtype: "Float",
										label: "Float",
										width: 100,
									},
									{
										fieldname: "cur",
										fieldtype: "Select",
										label: "Currency Code",
										options: "USD\nEUR\nINR",
										width: 130,
									},
									{
										fieldname: "amt",
										fieldtype: "Currency",
										label: "Currency",
										options: "cur",
										precision: 2,
										width: 140,
									},
									{
										fieldname: "pct",
										fieldtype: "Percent",
										label: "Percent",
										precision: 1,
										width: 110,
									},
									{
										fieldname: "dur",
										fieldtype: "Duration",
										label: "Duration",
										width: 200,
									},
									{
										fieldname: "date_v",
										fieldtype: "Date",
										label: "Date",
										width: 140,
									},
									{
										fieldname: "dt_v",
										fieldtype: "Datetime",
										label: "Datetime",
										width: 190,
									},
									{
										fieldname: "time_v",
										fieldtype: "Time",
										label: "Time",
										width: 130,
									},
									{
										fieldname: "stext",
										fieldtype: "Small Text",
										label: "Small Text",
										width: 160,
									},
									{
										fieldname: "text_v",
										fieldtype: "Text",
										label: "Text",
										width: 180,
									},
									{
										fieldname: "ltext",
										fieldtype: "Long Text",
										label: "Long Text",
										width: 180,
									},
									{
										fieldname: "pwd",
										fieldtype: "Password",
										label: "Password",
										width: 140,
									},
									{
										fieldname: "phone_v",
										fieldtype: "Phone",
										label: "Phone",
										width: 160,
									},
									{
										fieldname: "code_v",
										fieldtype: "Code",
										label: "Code",
										options: "Python",
										width: 220,
									},
									{
										fieldname: "json_v",
										fieldtype: "JSON",
										label: "JSON",
										width: 220,
									},
									{
										fieldname: "md_v",
										fieldtype: "Markdown Editor",
										label: "Markdown",
										width: 240,
									},
									{
										fieldname: "html_v",
										fieldtype: "HTML Editor",
										label: "HTML Editor",
										width: 240,
									},
									{
										fieldname: "geo",
										fieldtype: "Geolocation",
										label: "Geolocation",
										width: 200,
									},
									{
										fieldname: "attach_v",
										fieldtype: "Attach",
										label: "Attach",
										width: 200,
										ui: { props: { transport: fakeTransport } },
									},
									{
										fieldname: "aimg",
										fieldtype: "Attach Image",
										label: "Attach Image",
										width: 200,
										ui: { props: { transport: fakeTransport } },
									},
									{
										fieldname: "img",
										fieldtype: "Image",
										label: "Image",
										options: "aimg",
										width: 160,
									},
									{
										fieldname: "html_disp",
										fieldtype: "HTML",
										label: "HTML",
										options: "<em>static</em>",
										width: 160,
									},
									{
										fieldname: "heading_v",
										fieldtype: "Heading",
										label: "Heading",
										width: 140,
									},
									{
										fieldname: "btn",
										fieldtype: "Button",
										label: "Button",
										width: 140,
										ui: { on: { click: () => console.log("row button") } },
									},
									{
										fieldname: "ro",
										fieldtype: "Read Only",
										label: "Read Only",
										width: 130,
									},
									{
										fieldname: "assignees",
										fieldtype: "Table MultiSelect",
										label: "Table MultiSelect",
										options: "Assignee Detail",
										width: 260,
										childFields: [
											{
												fieldname: "user",
												fieldtype: "Link",
												options: "User",
											},
										],
									},
									{
										fieldname: "lines",
										fieldtype: "Table",
										label: "Table (nested)",
										options: "Nested Line",
										width: 260,
										childFields: [
											{
												fieldname: "label",
												fieldtype: "Data",
												label: "Label",
											},
											{ fieldname: "val", fieldtype: "Int", label: "Val" },
										],
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

// Button action, wired on the node via `ui.on.click`.
function sendInvite() {
	console.log("invite sent");
}

// Value-field commit side-effect, wired via `ui.on.change`. Derives `amount`
// (unit price 100) from the committed quantity — observe it in the doc dump.
function onQuantityCommit(value: any) {
	doc.amount = Number(value) * 100;
}
</script>
