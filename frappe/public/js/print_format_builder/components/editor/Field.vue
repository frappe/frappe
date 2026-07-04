<template>
	<div
		class="field"
		:class="{
			'field--table': df.fieldtype == 'Table',
			'field--selected': is_selected,
			'field--preview': !!preview_doc,
			'field--condition-hidden': preview_doc && !is_field_visible,
		}"
		v-show="!df.remove"
		:title="df.label || df.fieldname"
		@click.stop="select_field"
	>
		<!-- ── Preview mode: show actual doc values ─────────── -->
		<template v-if="preview_doc">
			<div class="field-preview-wrap" :style="custom_style">
				<!-- Handle HTML fields: render Jinja2 server-side if needed -->
				<div
					v-if="df.fieldtype == 'HTML' && df.html"
					class="custom-html"
					v-html="rendered_html ?? df.html"
				></div>
				<div v-else-if="df.fieldtype == 'Spacer'" class="field-preview-spacer"></div>
				<div v-else-if="df.fieldtype == 'Divider'" class="field-preview-divider"></div>
				<div
					v-else-if="df.fieldtype == 'Field Template'"
					class="custom-html"
					v-html="rendered_template || ''"
				></div>
				<!-- Table MultiSelect field: render as a comma-separated value list -->
				<div
					v-else-if="df.fieldtype == 'Table MultiSelect'"
					:style="field_style(df, true)"
					:class="[
						'field-preview-lr',
						field_orientation === 'left-right' && df.label_justify
							? `field-preview-lr--${df.label_justify}`
							: '',
						field_orientation === 'left-right' && df.align && df.align !== 'left'
							? `field-preview-lr--align-${df.align}`
							: '',
					]"
				>
					<div v-if="df.label && df.show_label !== 'hide'" class="field-preview-label">
						{{ df.label }}
					</div>
					<div
						class="field-preview-value"
						:class="{ 'text-muted': !(preview_doc[df.fieldname] || []).length }"
					>
						{{ multiselect_display(df) }}
					</div>
				</div>
				<!-- Table field -->
				<div v-else-if="df.fieldtype == 'Table'" class="field-preview-table">
					<div v-if="df.label && df.show_label !== 'hide'" class="field-preview-label">
						{{ df.label }}
					</div>
					<table
						class="preview-table"
						:class="{
							[`preview-table--${df.table_style || 'lined'}`]: true,
							'preview-table--borderless': df.table_bordered === false,
							'preview-table--plain-header': df.table_header === 'plain',
						}"
						:style="
							df.table_radius != null
								? { borderRadius: df.table_radius + 'px', overflow: 'hidden' }
								: {}
						"
					>
						<thead v-if="df.table_header !== 'none'">
							<tr>
								<th
									v-for="col in df.table_columns"
									:key="col.fieldname"
									:class="numeric_align_class(col)"
									:style="{
										...(col.width ? { width: col.width + '%' } : {}),
										...(df.table_cell_padding != null
											? { padding: df.table_cell_padding + 'px' }
											: {}),
									}"
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
									:style="
										df.table_cell_padding != null
											? { padding: df.table_cell_padding + 'px' }
											: {}
									"
								>
									<!-- Merged cell: image (if any) floats left, text lines stack -->
									<div v-if="has_merge(col)" class="pf-cell-merged">
										<template v-if="image_merge(col)">
											<img
												v-if="cell_image(col, row)"
												:src="cell_image(col, row)"
												class="pf-cell-thumb-img"
												:style="thumb_box(col)"
												:alt="col.label || col.fieldname"
											/>
											<span
												v-else
												class="pf-cell-thumb"
												:style="thumb(col, row).style"
												>{{ thumb(col, row).abbr }}</span
											>
										</template>
										<div class="pf-cell-lines">
											<div
												v-for="(mf, mi) in text_merges(col)"
												:key="mi"
												class="pf-merge-line"
												:class="`pf-merge--${mf.style || 'primary'}`"
											>
												{{ format_merged(row, mf.fieldname) }}
											</div>
										</div>
									</div>
									<!-- Single (default) -->
									<template v-else>
										<img
											v-if="
												is_image_field(col, row[col.fieldname]) &&
												row[col.fieldname]
											"
											:src="row[col.fieldname]"
											class="preview-table-img"
											:alt="col.label || col.fieldname"
										/>
										<div
											v-else-if="is_html_content_field(col)"
											class="preview-table-html"
											v-html="format_cell(row, col)"
										></div>
										<span v-else>{{ format_cell(row, col) }}</span>
									</template>
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
				<!-- Repeater field -->
				<div v-else-if="df.fieldtype == 'Repeater'" class="field-preview-repeater">
					<div v-if="df.label && df.show_label !== 'hide'" class="field-preview-label">
						{{ df.label }}
					</div>
					<table class="preview-table preview-table--borderless">
						<colgroup>
							<col
								v-for="(col, ci) in df.repeater_columns || []"
								:key="ci"
								:style="col.width ? { width: col.width + '%' } : {}"
							/>
						</colgroup>
						<tbody>
							<tr
								v-for="(row, i) in (preview_doc[df.source] || []).slice(0, 6)"
								:key="i"
							>
								<td
									v-for="(col, ci) in df.repeater_columns || []"
									:key="ci"
									:style="{
										textAlign: col.align || 'left',
										...(col.color ? { color: col.color } : {}),
									}"
								>
									{{ repeater_cell(col, row) }}
								</td>
							</tr>
							<tr v-if="!(preview_doc[df.source] || []).length">
								<td
									class="text-muted"
									style="text-align: center; font-size: 11px; padding: 6px"
								>
									{{ df.source ? __("No rows") : __("Pick a source table") }}
								</td>
							</tr>
						</tbody>
					</table>
				</div>
				<!-- Regular field -->
				<div
					v-else
					:style="field_style(df)"
					:class="[
						field_orientation === 'left-right' || df.show_label === 'inline'
							? 'field-preview-lr'
							: '',
						field_orientation === 'left-right' && df.label_justify
							? `field-preview-lr--${df.label_justify}`
							: '',
						field_orientation === 'left-right' && df.align && df.align !== 'left'
							? `field-preview-lr--align-${df.align}`
							: '',
					]"
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
			<!-- Top-right actions pill: drag + remove -->
			<div class="field-preview-actions">
				<div
					class="drag-handle field-drag-handle"
					v-html="frappe.utils.icon('grip', 'xs')"
				></div>
				<button
					class="es-button"
					data-size="xs"
					data-variant="ghost"
					data-theme="red"
					data-icon-button="true"
					@click.stop="df['remove'] = true"
					v-html="frappe.utils.icon('x', 'xs')"
				></button>
			</div>
		</template>

		<!-- ── Builder mode: labels + controls ──────────────── -->
		<template v-else>
			<div
				class="field-row"
				:style="{ textAlign: df.align || 'left', ...custom_style }"
				:class="{ 'field-row--lr': field_orientation === 'left-right' }"
			>
				<div
					class="drag-handle field-drag-handle"
					v-html="frappe.utils.icon('grip', 'xs')"
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
						<span class="es-badge">{{ short_fieldtype }}</span>
						<div class="field-actions">
							<button
								v-if="df.fieldtype == 'HTML'"
								class="es-button"
								data-size="xs"
								data-variant="ghost"
								data-icon-button="true"
								@click.stop="edit_html"
								v-html="frappe.utils.icon('pencil', 'sm')"
							></button>
							<button
								class="es-button"
								data-size="xs"
								data-variant="ghost"
								data-theme="red"
								data-icon-button="true"
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
			<div v-if="df.fieldtype == 'Repeater'" class="table-preview">
				<div class="table-columns-list">
					<span v-if="df.source" class="table-col-chip">{{ df.source }}</span>
					<span v-else class="text-muted no-columns-hint">
						{{ __("No source table selected") }}
					</span>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import ConfigureColumnsVue from "../inspector/ConfigureColumns.vue";
import {
	render_jinja_html,
	sanitize_html,
	evaluate_visible_if,
	thumb_hue,
	parse_inline_style,
} from "../../utils";
import { createApp, ref, nextTick, watch, computed, inject } from "vue";

const props = defineProps(["df", "field_orientation"]);

// Inline style for a preview field: text alignment (stacked only) plus an
// optional label-to-value gap. `always_row` is for fields that are always a
// flex row (e.g. Table MultiSelect) regardless of section orientation.
function field_style(df, always_row = false) {
	const style = {};
	if (props.field_orientation !== "left-right") {
		style.textAlign = df.align || "left";
	}
	const is_row =
		always_row || props.field_orientation === "left-right" || df.show_label === "inline";
	if (is_row && df.label_gap != null) {
		style.gap = df.label_gap + "px";
	}
	return style;
}

let store = inject("$store");
let editing = ref(false);
let label_input = ref(null);
let rendered_html = ref(null);
let rendered_template = ref(null);

let custom_style = computed(() => parse_inline_style(props.df.custom_style));

let is_selected = computed(() => store.selected_field.value === props.df);
let preview_doc = computed(() => store.preview_doc.value);
let is_field_visible = computed(() => evaluate_visible_if(props.df.visible_if, preview_doc.value));

// Render Jinja2 HTML fields server-side when in preview mode
watch(
	[preview_doc, () => props.df.html],
	async ([doc]) => {
		const html = props.df.html;
		if (!doc || !html || props.df.fieldtype !== "HTML") {
			rendered_html.value = null;
			return;
		}
		rendered_html.value = await render_jinja_html(
			html,
			store.meta.value?.name,
			store.preview_doc_name.value
		);
	},
	{ immediate: true }
);

// Render Field Template fields server-side when in preview mode
watch(
	[preview_doc, () => props.df.field_template],
	async ([doc]) => {
		if (!doc || props.df.fieldtype !== "Field Template" || !props.df.field_template) {
			rendered_template.value = null;
			return;
		}
		try {
			const tmpl = await frappe.db.get_value(
				"Print Format Field Template",
				props.df.field_template,
				"template"
			);
			const html = tmpl?.message?.template || "";
			rendered_template.value = await render_jinja_html(
				html,
				store.meta.value?.name,
				store.preview_doc_name.value
			);
		} catch {
			rendered_template.value = null;
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
const HTML_CONTENT_FIELDTYPES = new Set(["Text Editor", "Long Text"]);

function numeric_align_class(col) {
	// Merged cells are left-aligned (like the PDF), even on numeric columns
	return !has_merge(col) && NUMERIC_FIELDTYPES.has(col?.fieldtype) ? "col-numeric" : "";
}

function repeater_cell(col, row) {
	return (col.template || [])
		.map((tok) => {
			if (tok.t === "s") return tok.v || "";
			const child_df = repeater_child_df(tok.v);
			return child_df ? format_cell(row || {}, child_df) : row?.[tok.v] ?? "";
		})
		.join("");
}

function repeater_child_df(fieldname) {
	const source = store.meta.value?.fields?.find((f) => f.fieldname === props.df.source);
	if (!source) return null;
	return frappe.get_meta(source.options)?.fields?.find((f) => f.fieldname === fieldname) || null;
}

function multiselect_display(df) {
	const rows = preview_doc.value?.[df.fieldname] || [];
	if (!rows.length) return "—";
	const child_meta = frappe.get_meta(df.options);
	const link_field = child_meta?.fields.find((f) => f.fieldtype === "Link");
	if (!link_field) return "—";
	return (
		rows
			.map((r) => r[link_field.fieldname])
			.filter(Boolean)
			.join(", ") || "—"
	);
}

function is_html_content_field(col) {
	return HTML_CONTENT_FIELDTYPES.has(col?.fieldtype);
}

function format_cell(row, col) {
	const raw = row[col.fieldname];
	if (raw === null || raw === undefined || raw === "") return "";
	if (col.fieldtype === "Check") return raw ? __("Yes") : __("No");
	// HTML content fields: sanitize then return for v-html rendering
	if (HTML_CONTENT_FIELDTYPES.has(col.fieldtype)) return sanitize_html(raw);
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

// ── Merged cell helpers ────────────────────────────────────
// Image fieldtypes that store a URL directly, so they can float left.
const MERGE_IMAGE_FIELDTYPES = new Set(["Attach Image", "Attach"]);

// The column's own field is always the implicit first (primary) line;
// col.merged_fields holds only the extra fields merged in beside it.
function merged_fields(col) {
	const extra = (col.merged_fields || []).filter((mf) => mf && mf.fieldname);
	if (!extra.length) return [];
	return [{ fieldname: col.fieldname, fieldtype: col.fieldtype, style: "primary" }, ...extra];
}

function has_merge(col) {
	return (col.merged_fields || []).length > 0;
}

// The first merged field that is an image — rendered on the left.
function image_merge(col) {
	return merged_fields(col).find((mf) => MERGE_IMAGE_FIELDTYPES.has(mf.fieldtype)) || null;
}

// Remaining fields render as stacked text lines.
function text_merges(col) {
	const img = image_merge(col);
	return merged_fields(col).filter((mf) => mf.fieldname !== img?.fieldname);
}

// Format a merged sub-field using its own child docfield definition.
// Merged lines are plain text, so strip any HTML kept for rich-text
// fields (Text Editor / Long Text) down to its text content.
function format_merged(row, fieldname) {
	const dcol = frappe.meta.get_docfield(props.df.options, fieldname) || {
		fieldname,
		fieldtype: "Data",
	};
	const val = format_cell(row, dcol);
	if (typeof val === "string" && val.includes("<")) {
		const tmp = document.createElement("div");
		tmp.innerHTML = val;
		return (tmp.textContent || tmp.innerText || "").trim();
	}
	return val;
}

function cell_image(col, row) {
	const img = image_merge(col);
	const v = img ? row[img.fieldname] : null;
	return typeof v === "string" && v ? v : null;
}

function thumb_box(col) {
	const s = (col.image_size || 40) + "px";
	return { width: s, height: s };
}

// Initials fallback (abbr + coloured box) when an image field is merged
// but the row has no image. Colour keyed off the first text field.
function thumb(col, row) {
	const raw = String(row[text_merges(col)[0]?.fieldname] ?? "");
	const hue = thumb_hue(raw);
	return {
		abbr: frappe.get_abbr(raw) || "?",
		style: {
			...thumb_box(col),
			fontSize: Math.round((col.image_size || 40) * 0.4) + "px",
			background: `hsl(${hue}, 65%, 92%)`,
			color: `hsl(${hue}, 55%, 35%)`,
		},
	};
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
		"Table MultiSelect": "Multi",
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
		Repeater: "Repeat",
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
	if (value) nextTick(() => label_input.value?.focus());
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
	border-radius: var(--radius);
	border: 1px dashed var(--gray-400);
	padding: 0.4rem 0.5rem;
	font-size: var(--text-sm);
	cursor: grab;
	overflow: hidden;
}

.field:active {
	cursor: grabbing;
}

.field.sortable-chosen,
.field.sortable-ghost {
	cursor: grabbing;
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

.field-actions {
	display: flex;
	align-items: center;
	gap: 2px;
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
	border-radius: var(--radius);
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
	border-radius: var(--radius);
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

.field--condition-hidden {
	opacity: 0.35;
	border-radius: var(--radius);
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
	font-size: var(--text-sm);
	color: var(--pfb-label-color, #6b7280);
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

.field-preview-lr--space-between {
	justify-content: space-between;
}
.field-preview-lr--space-evenly {
	justify-content: space-evenly;
}
.field-preview-lr--align-center {
	justify-content: center;
}
.field-preview-lr--align-right {
	justify-content: flex-end;
}

/* Spacing: value shrinks to natural width so justify-content has room to push it */
.field-preview-lr--space-between .field-preview-value,
.field-preview-lr--space-evenly .field-preview-value {
	flex: none;
}

.field-preview-lr--space-between .field-preview-value {
	text-align: right;
}

/* Align: both label and value shrink to natural width so the pair can be repositioned */
.field-preview-lr--align-center .field-preview-label,
.field-preview-lr--align-center .field-preview-value,
.field-preview-lr--align-right .field-preview-label,
.field-preview-lr--align-right .field-preview-value {
	flex: none;
	width: auto;
}

.field-preview-value {
	font-size: var(--text-sm);
	color: var(--pfb-value-color, var(--text-color));
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

/* Top-right actions pill: drag + remove — hidden until hover/selected */
.field-preview-actions {
	display: none;
	position: absolute;
	top: 2px;
	right: 2px;
	z-index: 2;
	gap: 2px;
	background: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	padding: 1px 2px;
	align-items: center;
	box-shadow: var(--shadow-xs);
}

.field--preview:hover .field-preview-actions,
.field--preview.field--selected .field-preview-actions {
	display: flex;
}

.field-preview-actions .field-drag-handle {
	cursor: grab;
	color: var(--gray-400);
	display: flex;
	align-items: center;
	padding: 2px;
}

.field-preview-actions .field-drag-handle:hover {
	color: var(--gray-600);
}

/* Preview table — exact PDF print_format.css child-table style */
.field-preview-table {
	width: 100%;
	margin-top: 0.5rem;
}

.field-preview-table > .field-preview-label {
	font-size: 0.8em;
	font-weight: var(--weight-semibold);
	color: var(--text-muted);
	margin-bottom: 0.4rem;
}

.preview-table {
	width: 100%;
	border-collapse: collapse;
	font-size: var(--text-sm);
	table-layout: fixed;
}

/* ── Default: bordered + styled header (matches PDF) ─── */
.preview-table th {
	background-color: var(--gray-100);
	color: var(--text-color);
	font-weight: var(--weight-semibold);
	font-size: var(--text-tiny);
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

/* Repeater rows follow the same vertical rhythm as fields in a column */
.field-preview-repeater .preview-table td {
	padding: 0;
	border: none;
}

.field-preview-repeater .preview-table tr + tr td {
	padding-top: 0.4rem;
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

/* ── Merged cells ────────────────────────────────────────── */
.pf-cell-merged {
	display: flex;
	align-items: flex-start;
	gap: 8px;
}

/* size comes from an inline style (col.image_size) */
.pf-cell-thumb-img,
.pf-cell-thumb {
	border-radius: 6px;
	flex-shrink: 0;
}

.pf-cell-thumb-img {
	object-fit: cover;
}

.pf-cell-thumb {
	display: flex;
	align-items: center;
	justify-content: center;
	font-weight: var(--weight-semibold);
	text-transform: uppercase;
	line-height: 1;
}

.pf-cell-lines {
	display: flex;
	flex-direction: column;
	gap: 2px;
	min-width: 0;
}

.pf-merge-line {
	word-break: break-word;
}
.pf-merge--primary,
.pf-merge--secondary {
	color: var(--text-color);
}
.pf-merge--primary {
	font-weight: var(--weight-semibold);
}
.pf-merge--mono-sm,
.pf-merge--muted-sm {
	font-size: 0.85em;
	color: var(--text-muted);
}
.pf-merge--mono-sm {
	font-family: var(--monospace-font-family, monospace);
}

.preview-table-html {
	word-break: break-word;
	white-space: normal;
}

.preview-field-img {
	max-width: 100%;
	max-height: 80px;
	object-fit: contain;
	border-radius: var(--radius);
	display: block;
}
</style>
