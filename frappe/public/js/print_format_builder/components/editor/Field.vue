<template>
	<div
		class="field"
		:class="{
			'field--table': df.fieldtype == 'Table',
			'field--selected': is_selected,
			'field--preview': !!preview_doc,
		}"
		v-show="!df.remove"
		:title="df.label || df.fieldname"
		@click.stop="select_field"
	>
		<!-- ── Preview mode: show actual doc values ─────────── -->
		<template v-if="preview_doc">
			<div class="field-preview-wrap">
				<!-- Handle HTML fields: render Jinja2 server-side if needed -->
				<div
					v-if="df.fieldtype == 'HTML' && df.html"
					class="custom-html"
					v-html="rendered_html ?? df.html"
				></div>
				<div v-else-if="df.fieldtype == 'Spacer'" class="field-preview-spacer"></div>
				<div v-else-if="df.fieldtype == 'Divider'" class="field-preview-divider"></div>
				<!-- Table field -->
				<div v-else-if="df.fieldtype == 'Table'" class="field-preview-table">
					<div v-if="df.label" class="field-preview-label">{{ df.label }}</div>
					<table
						class="preview-table"
						:class="{
							[`preview-table--${df.table_style || 'lined'}`]: true,
							'preview-table--borderless': df.table_bordered === false,
							'preview-table--plain-header': df.table_header === 'plain',
						}"
					>
						<thead>
							<tr>
								<th
									v-for="col in df.table_columns"
									:key="col.fieldname"
									:class="numeric_align_class(col)"
								>
									{{ col.label || col.fieldname }}
								</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="(row, i) in (preview_doc[df.fieldname] || []).slice(0, 4)"
								:key="i"
								:class="i % 2 === 0 ? 'odd' : 'even'"
							>
								<td
									v-for="col in df.table_columns"
									:key="col.fieldname"
									:class="numeric_align_class(col)"
								>
									<img
										v-if="
											is_image_field(col, row[col.fieldname]) &&
											row[col.fieldname]
										"
										:src="row[col.fieldname]"
										class="preview-table-img"
										:alt="col.label || col.fieldname"
									/>
									<span v-else>{{ format_cell(row, col) }}</span>
								</td>
							</tr>
							<tr v-if="!preview_doc[df.fieldname]?.length">
								<td
									:colspan="df.table_columns?.length || 1"
									class="text-muted"
									style="text-align: center; font-size: 11px; padding: 6px"
								>
									{{ __("No rows") }}
								</td>
							</tr>
						</tbody>
					</table>
				</div>
				<!-- Regular field -->
				<div
					v-else
					:style="{ textAlign: df.align || 'left' }"
					:class="{ 'field-preview-lr': field_orientation === 'left-right' }"
				>
					<div v-if="df.label && df.show_label !== 'hide'" class="field-preview-label">
						{{ df.label }}
					</div>
					<div class="field-preview-value" :class="{ 'text-muted': !preview_value }">
						<img
							v-if="is_image_field(df, preview_value) && preview_value"
							:src="preview_value"
							class="preview-field-img"
							:alt="df.label || df.fieldname"
						/>
						<span v-else>{{ preview_value || "—" }}</span>
					</div>
				</div>
			</div>
			<!-- Drag + remove — top-right corner on hover; remove button hidden in clean-preview -->
			<div class="field-preview-actions">
				<div
					class="drag-handle field-drag-handle"
					v-html="frappe.utils.icon('drag', 'xs')"
				></div>
				<button
					class="btn btn-xs btn-icon field-remove-btn"
					@click.stop="df['remove'] = true"
					v-html="frappe.utils.icon('x', 'xs')"
				></button>
			</div>
		</template>

		<!-- ── Builder mode: labels + controls ──────────────── -->
		<template v-else>
			<div
				class="field-row"
				:style="{ textAlign: df.align || 'left' }"
				:class="{ 'field-row--lr': field_orientation === 'left-right' }"
			>
				<div
					class="drag-handle field-drag-handle"
					v-html="frappe.utils.icon('drag', 'xs')"
				></div>
				<div class="field-body">
					<div class="field-content">
						<div
							class="custom-html"
							v-if="df.fieldtype == 'HTML' && df.html"
							v-html="df.html"
						></div>
						<div class="custom-html" v-else-if="df.fieldtype == 'Field Template'">
							{{ df.label }}
						</div>
						<input
							v-else-if="editing && df.fieldtype != 'HTML'"
							ref="label_input"
							class="label-input"
							type="text"
							:placeholder="__('Label')"
							v-model="df.label"
							@keydown.enter="editing = false"
							@blur="editing = false"
						/>
						<span v-else-if="df.label">{{ df.label }}</span>
						<i class="text-muted" v-else>{{ __("No Label") }} ({{ df.fieldname }})</i>
					</div>
					<div class="field-meta">
						<span class="fieldtype-badge">{{ short_fieldtype }}</span>
						<div class="field-actions">
							<button
								v-if="df.fieldtype == 'HTML'"
								class="btn btn-xs btn-icon"
								@click.stop="edit_html"
								v-html="frappe.utils.icon('edit', 'sm')"
							></button>
							<button
								class="btn btn-xs btn-icon"
								@click.stop="df['remove'] = true"
								v-html="frappe.utils.icon('x', 'sm')"
							></button>
						</div>
					</div>
				</div>
			</div>
			<div v-if="df.fieldtype == 'Table'" class="table-preview">
				<div class="table-columns-list">
					<span
						class="table-col-chip"
						:class="{ 'table-col-chip--invalid': tf.invalid_width }"
						v-for="tf in df.table_columns"
						:key="tf.fieldname"
						:title="tf.label || tf.fieldname"
					>
						{{ tf.label || tf.fieldname }}
					</span>
					<span
						v-if="!df.table_columns || !df.table_columns.length"
						class="text-muted no-columns-hint"
					>
						{{ __("No columns configured") }}
					</span>
				</div>
				<button class="configure-columns-btn" @click.stop="configure_columns">
					<span v-html="frappe.utils.icon('settings-2', 'xs')"></span>
					{{ __("Configure Columns") }}
				</button>
			</div>
		</template>
	</div>
</template>

<script setup>
import ConfigureColumnsVue from "../inspector/ConfigureColumns.vue";
import { createApp, ref, nextTick, watch, computed, inject } from "vue";

const props = defineProps(["df", "field_orientation"]);

let store = inject("$store");
let editing = ref(false);
let label_input = ref(null);
let rendered_html = ref(null);
let render_pending = ref(false);

let is_selected = computed(() => store.selected_field.value === props.df);
let preview_doc = computed(() => store.preview_doc.value);

// Render Jinja2 HTML fields server-side when in preview mode
watch(
	[preview_doc, () => props.df.html],
	async ([doc]) => {
		const html = props.df.html;
		if (!doc || !html || props.df.fieldtype !== "HTML") {
			rendered_html.value = null;
			return;
		}
		if (!html.includes("{{") && !html.includes("{%")) {
			rendered_html.value = html;
			return;
		}
		if (render_pending.value) return;
		render_pending.value = true;
		try {
			const r = await frappe.call(
				"frappe.utils.print_format_generator.render_jinja_template",
				{
					template: html,
					doctype: store.meta.value.name,
					docname: store.preview_doc_name.value,
				}
			);
			rendered_html.value = r.message ?? html;
		} catch {
			rendered_html.value = html;
		} finally {
			render_pending.value = false;
		}
	},
	{ immediate: true }
);

let preview_value = computed(() => {
	if (!preview_doc.value || !props.df.fieldname) return null;
	const raw = preview_doc.value[props.df.fieldname];
	if (raw === null || raw === undefined || raw === "") return null;
	const ft = props.df.fieldtype;
	// Check fields return an <input> element from frappe.format — handle directly
	if (ft === "Check") return raw ? __("Yes") : __("No");
	try {
		const formatted = frappe.format(raw, props.df, { only_value: true }, preview_doc.value);
		// If frappe.format returned HTML markup, extract the text content
		if (typeof formatted === "string" && formatted.includes("<")) {
			const tmp = document.createElement("div");
			tmp.innerHTML = formatted;
			return tmp.textContent || tmp.innerText || String(raw);
		}
		return formatted;
	} catch {
		return String(raw);
	}
});

const IMAGE_FIELDTYPES = new Set(["Attach Image", "Image", "Attach"]);
const IMAGE_EXTENSIONS = /\.(png|jpe?g|gif|webp|svg|bmp|ico)(\?.*)?$/i;
function is_image_field(col, value) {
	if (IMAGE_FIELDTYPES.has(col?.fieldtype)) return true;
	// Heuristic: any field whose value looks like an image URL
	if (value && typeof value === "string" && IMAGE_EXTENSIONS.test(value)) return true;
	return false;
}

const NUMERIC_FIELDTYPES = new Set(["Currency", "Float", "Int", "Percent"]);
function numeric_align_class(col) {
	return NUMERIC_FIELDTYPES.has(col?.fieldtype) ? "col-numeric" : "";
}

function format_cell(row, col) {
	const raw = row[col.fieldname];
	if (raw === null || raw === undefined || raw === "") return "";
	if (col.fieldtype === "Check") return raw ? __("Yes") : __("No");
	try {
		const formatted = frappe.format(raw, col, { only_value: true }, row);
		if (typeof formatted === "string" && formatted.includes("<")) {
			const tmp = document.createElement("div");
			tmp.innerHTML = formatted;
			return tmp.textContent || tmp.innerText || String(raw);
		}
		return formatted;
	} catch {
		return String(raw);
	}
}

function select_field() {
	store.selected_field.value = props.df;
	store.selected_letterhead.value = false;
	store.selected_lh_footer.value = false;
	if (props.df.fieldtype !== "HTML") {
		editing.value = true;
	}
}

let short_fieldtype = computed(() => {
	const map = {
		Data: "Data",
		Currency: "₹",
		Int: "Int",
		Float: "Float",
		Date: "Date",
		Datetime: "DateTime",
		Check: "Check",
		Select: "Select",
		Table: "Table",
		"Long Text": "Text",
		Text: "Text",
		Link: "Link",
		Signature: "Sign",
		Attach: "File",
		"Attach Image": "Img",
		HTML: "HTML",
		Spacer: "Space",
		Divider: "Line",
		"Field Template": "Tmpl",
	};
	return map[props.df.fieldtype] || props.df.fieldtype?.substring(0, 5) || "";
});

function edit_html() {
	let d = new frappe.ui.Dialog({
		title: __("Edit HTML"),
		fields: [{ label: __("HTML"), fieldname: "html", fieldtype: "Code", options: "HTML" }],
		primary_action: ({ html }) => {
			html = frappe.dom.remove_script_and_style(html);
			props.df["html"] = html;
			d.hide();
		},
	});
	d.set_value("html", props.df.html);
	d.show();
}

function configure_columns() {
	let dialog = new frappe.ui.Dialog({
		title: __("Configure columns for {0}", [props.df.label]),
		fields: [
			{ fieldtype: "HTML", fieldname: "columns_area" },
			{
				label: "",
				fieldtype: "Autocomplete",
				placeholder: __("Add Column"),
				fieldname: "add_column",
				options: get_all_columns(),
				onchange: () => {
					let fieldname = dialog.get_value("add_column");
					if (fieldname) {
						let column = get_column_to_add(fieldname);
						if (column) {
							props.df.table_columns.push(column);
							props.df["table_columns"] = props.df.table_columns;
							dialog.set_value("add_column", "");
						}
					}
				},
			},
		],
		on_page_show: () => {
			const app = createApp(ConfigureColumnsVue, { df: props.df });
			SetVueGlobals(app);
			app.mount(dialog.get_field("columns_area").$wrapper.get(0));
		},
		on_hide: () => {
			props.df["table_columns"] = props.df.table_columns.filter((col) => !col.invalid_width);
		},
	});
	dialog.show();
}

function get_all_columns() {
	let meta = frappe.get_meta(props.df.options);
	let more_columns = [{ label: __("Sr No."), value: "idx" }];
	return more_columns.concat(
		meta.fields
			.map((tf) => {
				if (frappe.model.no_value_type.includes(tf.fieldtype)) return;
				return { label: tf.label, value: tf.fieldname };
			})
			.filter(Boolean)
	);
}

function get_column_to_add(fieldname) {
	const standard = {
		idx: { label: __("Sr No."), fieldtype: "Data", fieldname: "idx", width: 10 },
	};
	if (fieldname in standard) return standard[fieldname];
	return { ...frappe.meta.get_docfield(props.df.options, fieldname), width: 10 };
}

function validate_table_columns() {
	if (props.df.fieldtype != "Table") return;
	let total = 0;
	for (let col of props.df.table_columns) {
		if (!col.width) col.width = 10;
		total += col.width;
		col.invalid_width = total > 100;
	}
}

watch(editing, (value) => {
	if (value) nextTick(() => label_input.value.focus());
});
watch(
	() => props.df.table_columns,
	() => validate_table_columns(),
	{ deep: true }
);
</script>

<style scoped>
.field {
	display: flex;
	flex-direction: column;
	gap: 0;
	width: 100%;
	min-width: 0;
	background-color: var(--bg-light-gray);
	border-radius: var(--border-radius);
	border: 1px dashed var(--gray-400);
	padding: 0.4rem 0.5rem;
	font-size: var(--text-sm);
	cursor: default;
	overflow: hidden;
}

.field:focus-within {
	border-style: solid;
	border-color: var(--gray-600);
}

.field--selected {
	border-style: solid;
	border-color: var(--gray-500);
}

.field-row {
	display: flex;
	align-items: center;
	gap: 0.25rem;
	width: 100%;
	min-width: 0;
}

.field-drag-handle {
	cursor: grab;
	color: var(--gray-400);
	display: flex;
	align-items: center;
	flex-shrink: 0;
}

.field-drag-handle:hover {
	color: var(--gray-600);
}

.field-body {
	flex: 1;
	min-width: 0;
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.5rem;
}

.field-content {
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.field-meta {
	display: flex;
	align-items: center;
	gap: 0.25rem;
	flex-shrink: 0;
}

.fieldtype-badge {
	font-size: 10px;
	color: var(--text-muted);
	background: var(--gray-100);
	border: 1px solid var(--gray-300);
	border-radius: var(--border-radius-sm);
	padding: 1px 4px;
	white-space: nowrap;
}

.field-actions {
	display: flex;
	align-items: center;
	gap: 2px;
}

.field-actions .btn-icon {
	box-shadow: none;
	padding: 2px;
}

.field-actions .btn-icon:hover {
	background-color: var(--fg-color);
}

.custom-html {
	word-break: break-all;
}

.label-input {
	background-color: transparent;
	border: none;
	padding: 0;
	width: 100%;
}

.label-input:focus {
	outline: none;
}

/* Table field preview */
.table-preview {
	margin-top: 0.5rem;
	padding-top: 0.5rem;
	border-top: 1px solid var(--gray-300);
	display: flex;
	flex-direction: column;
	gap: 0.4rem;
}

.table-columns-list {
	display: flex;
	flex-wrap: wrap;
	gap: 4px;
}

.table-col-chip {
	display: inline-block;
	background: var(--fg-color);
	border: 1px solid var(--gray-300);
	border-radius: var(--border-radius-sm);
	padding: 1px 6px;
	font-size: var(--text-xs);
	color: var(--text-color);
	white-space: nowrap;
	max-width: 100px;
	overflow: hidden;
	text-overflow: ellipsis;
	vertical-align: middle;
}

.table-col-chip--invalid {
	border-color: var(--red-300);
	color: var(--red-500);
	background: var(--red-50);
}

.configure-columns-btn {
	align-self: flex-start;
	display: inline-flex;
	align-items: center;
	gap: 4px;
	font-size: var(--text-xs);
	font-weight: 500;
	color: var(--text-muted);
	background: var(--gray-50);
	border: 1px solid var(--gray-200);
	border-radius: var(--border-radius);
	padding: 3px 8px;
	cursor: pointer;
	outline: none;
	transition: color 0.15s, border-color 0.15s, background 0.15s;
	line-height: 1.4;
}

.configure-columns-btn:hover {
	color: var(--gray-800);
	border-color: var(--gray-400);
	background: var(--gray-100);
}

.configure-columns-btn:focus {
	outline: none;
	box-shadow: none;
}

.no-columns-hint {
	font-size: var(--text-xs);
}

/* ── Left-right label orientation (builder mode) ────────── */
.field-row--lr {
	flex-direction: row;
	align-items: center;
}

/* ── Preview mode ────────────────────────────────────────── */
.field--preview {
	border: 1px solid transparent;
	background: transparent;
	padding: 0;
	position: relative;
}

.field--preview:hover {
	border-color: var(--gray-200);
	background: var(--gray-50);
}

.field--preview.field--selected {
	border-style: solid;
	border-color: var(--gray-500);
	background: var(--fg-color);
}

.field-preview-wrap {
	padding: 2px 4px;
	width: 100%;
}

.field-preview-label {
	font-size: 0.72em;
	font-weight: 600;
	color: var(--gray-500);
	margin-bottom: 1px;
}

/* Left-right: label and value side by side */
.field-preview-lr {
	display: flex;
	align-items: baseline;
	gap: 6px;
}

.field-preview-lr .field-preview-label {
	flex-shrink: 0;
	margin-bottom: 0;
	white-space: nowrap;
}

.field-preview-lr .field-preview-value {
	flex: 1;
	min-width: 0;
}

.field-preview-value {
	font-size: var(--text-sm);
	color: var(--text-color);
	word-break: break-word;
}

.field-preview-spacer {
	height: 12px;
}

.field-preview-divider {
	height: 1px;
	background: var(--gray-300);
	margin: 4px 0;
}

/* Preview actions — drag + remove — hidden until hover/selected */
.field-preview-actions {
	display: none;
	position: absolute;
	top: 2px;
	right: 2px;
	gap: 2px;
	background: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius-sm);
	padding: 1px 2px;
	align-items: center;
	box-shadow: var(--shadow-xs);
}

.field--preview:hover .field-preview-actions,
.field--preview.field--selected .field-preview-actions {
	display: flex;
}

.field-preview-actions .btn-icon {
	box-shadow: none;
	padding: 2px;
}

/* Preview table — exact PDF print_format.css child-table style */
.field-preview-table {
	width: 100%;
	margin-top: 0.5rem;
}

.field-preview-table > .field-preview-label {
	font-size: 0.8em;
	font-weight: 600;
	color: var(--text-muted);
	margin-bottom: 0.4rem;
}

.preview-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 0.9em;
}

/* ── Default: bordered + styled header (matches PDF) ─── */
.preview-table th {
	background-color: var(--gray-100);
	color: var(--text-color);
	font-weight: 600;
	font-size: 0.85em;
	padding: 0.45rem 0.6rem;
	border: 1px solid var(--gray-200);
	text-align: left;
}

.preview-table td {
	padding: 0.45rem 0.6rem;
	border: 1px solid var(--gray-200);
	vertical-align: top;
	color: var(--text-color);
}

/* lined (default): no alternating rows */
.preview-table--lined tr.odd td,
.preview-table--lined tr.even td {
	background-color: var(--fg-color);
}

/* striped: alternating row background */
.preview-table--striped tr.odd td {
	background-color: var(--fg-color);
}

.preview-table--striped tr.even td {
	background-color: var(--gray-50);
}

/* plain: no borders, bottom divider only */
.preview-table--plain th,
.preview-table--plain td {
	border: none;
	border-bottom: 1px solid var(--gray-200);
}

.preview-table--plain th {
	background-color: transparent;
	border-bottom: 2px solid var(--gray-300);
}

.preview-table--plain tr.odd td,
.preview-table--plain tr.even td {
	background-color: var(--fg-color);
}

/* Numeric columns right-aligned — same as PDF */
.preview-table .col-numeric {
	text-align: right;
}

/* ── Borderless variant ──────────────────────────────── */
.preview-table--borderless th,
.preview-table--borderless td {
	border: none;
	border-bottom: 1px solid var(--gray-200);
}

/* ── Plain header variant ───────────────────────────── */
.preview-table--plain-header th {
	background-color: transparent;
	border-bottom: 2px solid var(--gray-300);
}

.preview-table-img {
	width: auto;
	height: 60px;
	max-width: 80px;
	object-fit: contain;
	display: block;
}

.preview-field-img {
	max-width: 100%;
	max-height: 80px;
	object-fit: contain;
	border-radius: var(--border-radius-sm);
	display: block;
}
</style>
