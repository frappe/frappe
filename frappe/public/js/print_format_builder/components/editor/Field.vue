<template>
	<div
		:class="[
			preview_doc ? preview_root.classes : 'field field--chip',
			{
				'field--selected': is_selected,
				'field--layer-hover': store.hovered_node.value === df,
				'field--preview': !!preview_doc,
				'field--condition-hidden': preview_doc && !is_field_visible,
			},
		]"
		:style="preview_doc ? preview_root.style : undefined"
		:data-fieldname="preview_data_attr(df.fieldname)"
		:data-fieldtype="preview_data_attr(df.fieldtype)"
		:data-field-uid="field_uid(df)"
		v-show="!df.remove"
		:title="df.label || df.fieldname"
		:aria-label="df.label || df.fieldname"
		tabindex="0"
		@click.stop="select_field($event)"
		@contextmenu="on_context_menu"
		@mouseenter="store.hovered_field.value = df"
		@mouseleave="store.hovered_field.value = null"
		@keydown.enter.prevent="kbd_select($event)"
		@keydown.space.prevent="kbd_select($event)"
	>
		<!-- ── Preview mode: show actual doc values ─────────── -->
		<template v-if="preview_doc">
			<!-- Handle HTML fields: render Jinja2 server-side if needed -->
			<span v-if="template_render_failed" class="text-muted">{{
				__("Couldn't render this template for the previewed document")
			}}</span>
			<div
				v-else-if="df.fieldtype == 'HTML' && df.html"
				v-html="rendered_html ?? df.html"
			></div>
			<!-- Typst can't render in the HTML canvas — show the markup, the PDF preview shows the output -->
			<pre v-else-if="df.fieldtype == 'Typst'" class="typst-block-source">{{
				df.typst || __("Empty Typst block")
			}}</pre>
			<!-- Spacer/Divider: the root element itself is the rendered output -->
			<i
				v-else-if="df.fieldtype == 'Spacer' || df.fieldtype == 'Divider'"
				v-show="false"
			></i>
			<template v-else-if="df.fieldtype == 'Image'">
				<img
					v-if="df.image_url || preview_doc[df.fieldname]"
					:src="df.image_url || preview_doc[df.fieldname]"
					:style="{ maxWidth: '100%', ...(df.width ? { width: df.width } : {}) }"
					:alt="df.label || ''"
				/>
				<span v-else class="text-muted">{{ __("No image — set one in the panel") }}</span>
			</template>
			<FieldPreviewBarcode v-else-if="df.fieldtype == 'Barcode'" :df="df" />
			<div
				v-else-if="df.fieldtype == 'Field Template'"
				v-html="rendered_template || ''"
			></div>
			<!-- Table MultiSelect field: render as a comma-separated value list -->
			<template v-else-if="df.fieldtype == 'Table MultiSelect'">
				<div
					v-if="df.label && df.show_label !== 'hide'"
					class="label"
					:style="label_text_style(df)"
				>
					{{ df.label }}
				</div>
				<div
					class="value"
					:class="{ 'text-muted': !(preview_doc[df.fieldname] || []).length }"
					:style="value_text_style(df)"
				>
					{{ multiselect_display(df) }}
				</div>
			</template>
			<FieldPreviewTable v-else-if="df.fieldtype == 'Table'" :df="df" />
			<FieldPreviewRepeater v-else-if="df.fieldtype == 'Repeater'" :df="df" />
			<template v-else>
				<div
					v-if="df.label && df.show_label !== 'hide'"
					class="label"
					:style="label_text_style(df)"
				>
					{{ df.label }}
				</div>
				<div
					class="value"
					:class="{ 'text-muted': !preview_value }"
					:style="value_text_style(df)"
				>
					<img
						v-if="df.fieldtype == 'Attach Image' && preview_doc[df.fieldname]"
						class="w-100"
						:src="preview_doc[df.fieldname]"
						:alt="df.label || df.fieldname"
					/>
					<a
						v-else-if="df.fieldtype == 'Attach' && preview_doc[df.fieldname]"
						:href="preview_doc[df.fieldname]"
						@click.prevent
						>{{ String(preview_doc[df.fieldname]).split("/").pop() }}</a
					>
					<template v-else-if="df.fieldtype == 'Color' && preview_doc[df.fieldname]">
						<div
							class="color-square"
							:style="{ backgroundColor: preview_doc[df.fieldname] }"
						></div>
						{{ preview_doc[df.fieldname] }}
					</template>
					<!-- Mirrors the star SVG of templates/print_format/macros/Rating.html -->
					<template v-else-if="df.fieldtype == 'Rating' && preview_doc[df.fieldname]">
						<svg
							v-for="i in rating_stars.total"
							:key="i"
							class="rating-star"
							:class="{ active: i <= rating_stars.filled }"
							viewBox="0 0 24 24"
							fill="none"
							xmlns="http://www.w3.org/2000/svg"
						>
							<path
								:fill="i <= rating_stars.filled ? '#f6c35e' : '#dce0e3'"
								:stroke="i <= rating_stars.filled ? '#f6c35e' : '#dce0e3'"
								d="M11.5516 2.90849C11.735 2.53687 12.265 2.53687 12.4484 2.90849L14.8226 7.71919C14.8954 7.86677 15.0362 7.96905 15.1991 7.99271L20.508 8.76415C20.9181 8.82374 21.0818 9.32772 20.7851 9.61699L16.9435 13.3616C16.8257 13.4765 16.7719 13.642 16.7997 13.8042L17.7066 19.0916C17.7766 19.5001 17.3479 19.8116 16.9811 19.6187L12.2327 17.1223C12.087 17.0457 11.913 17.0457 11.7673 17.1223L7.01888 19.6187C6.65207 19.8116 6.22335 19.5001 6.29341 19.0916L7.20028 13.8042C7.2281 13.642 7.17433 13.4765 7.05648 13.3616L3.21491 9.61699C2.91815 9.32772 3.08191 8.82374 3.49202 8.76415L8.80094 7.99271C8.9638 7.96905 9.10458 7.86677 9.17741 7.71919L11.5516 2.90849Z"
							/>
						</svg>
					</template>
					<span v-else-if="preview_value_html" v-html="preview_value_html"></span>
					<span v-else>{{ preview_value || "—" }}</span>
				</div>
			</template>
			<div class="field-preview-actions">
				<div
					class="drag-handle field-drag-handle"
					v-html="frappe.utils.icon('grip', 'xs')"
				></div>
				<button
					class="es-button"
					data-size="xs"
					data-variant="ghost"
					data-icon-button="true"
					:title="__('Copy')"
					@click.stop="store.copy_field(df)"
					v-html="frappe.utils.icon('copy', 'xs')"
				></button>
				<button
					class="es-button"
					data-size="xs"
					data-variant="ghost"
					data-icon-button="true"
					:title="__('Duplicate')"
					@click.stop="store.duplicate_field(df)"
					v-html="frappe.utils.icon('copy-plus', 'xs')"
				></button>
				<button
					class="es-button"
					data-size="xs"
					data-variant="ghost"
					data-icon-button="true"
					:title="__('Save as snippet')"
					@click.stop="save_as_snippet"
					v-html="frappe.utils.icon('bookmark-plus', 'xs')"
				></button>
				<button
					class="es-button"
					data-size="xs"
					data-variant="ghost"
					data-theme="red"
					data-icon-button="true"
					:title="__('Remove field')"
					@click.stop="store.remove_field(df)"
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
						<pre
							v-else-if="df.fieldtype == 'Typst' && df.typst"
							class="typst-block-source"
							>{{ df.typst }}</pre
						>
						<div class="custom-html" v-else-if="df.fieldtype == 'Field Template'">
							{{ df.label }}
						</div>
						<img
							v-else-if="df.fieldtype == 'Image' && df.custom && df.image_url"
							:src="df.image_url"
							class="pf-builder-thumb"
							:alt="df.label || ''"
						/>
						<input
							v-else-if="
								editing && df.fieldtype != 'HTML' && df.fieldtype != 'Typst'
							"
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
								v-if="code_edit"
								class="es-button"
								data-size="xs"
								data-variant="ghost"
								data-icon-button="true"
								:title="code_edit.title"
								@click.stop="code_edit.open"
								v-html="frappe.utils.icon('pencil', 'sm')"
							></button>
							<button
								class="es-button"
								data-size="xs"
								data-variant="ghost"
								data-icon-button="true"
								:title="__('Copy')"
								@click.stop="store.copy_field(df)"
								v-html="frappe.utils.icon('copy', 'sm')"
							></button>
							<button
								class="es-button"
								data-size="xs"
								data-variant="ghost"
								data-icon-button="true"
								:title="__('Duplicate')"
								@click.stop="store.duplicate_field(df)"
								v-html="frappe.utils.icon('copy-plus', 'sm')"
							></button>
							<button
								class="es-button"
								data-size="xs"
								data-variant="ghost"
								data-theme="red"
								data-icon-button="true"
								:title="__('Remove field')"
								@click.stop="store.remove_field(df)"
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
import FieldPreviewBarcode from "./FieldPreviewBarcode.vue";
import FieldPreviewRepeater from "./FieldPreviewRepeater.vue";
import FieldPreviewTable from "./FieldPreviewTable.vue";
import {
	render_jinja_html,
	evaluate_visible_if,
	parse_inline_style,
	field_uid,
} from "../../utils";
import { createApp, ref, nextTick, watch, computed, inject } from "vue";
import { useFieldFormat } from "../../composables/useFieldFormat";
import { useContextMenu } from "../../composables/useContextMenu";

const props = defineProps(["df", "field_orientation"]);

// Per-field text colour for the label and value lines.
function label_text_style(df) {
	return {
		...(df.label_color ? { color: df.label_color } : {}),
	};
}
function value_text_style(df) {
	return {
		...(df.value_color ? { color: df.value_color } : {}),
	};
}

let store = inject("$store");
let editing = ref(false);
let label_input = ref(null);
let rendered_html = ref(null);
let template_render_failed = ref(false);
let rendered_template = ref(null);

let custom_style = computed(() => parse_inline_style(props.df.custom_style));

let is_selected = computed(
	() => store.selected_field.value === props.df || store.selected_fields.value.includes(props.df)
);
let preview_doc = computed(() => store.preview_doc.value);
let is_field_visible = computed(() => evaluate_visible_if(props.df.visible_if, preview_doc.value));

// Mirrors the root markup of templates/print_format/macros/*.html per fieldtype
const preview_root = computed(() => {
	const df = props.df;
	const custom = custom_style.value;
	if (df.fieldtype === "Table") {
		return {
			classes: [
				"child-table",
				`child-table--${df.table_style || "lined"}`,
				df.table_header === "plain" ? "child-table--plain-header" : "",
				df.table_bordered !== false ? "child-table--bordered" : "",
			],
			style: custom,
		};
	}
	if (df.fieldtype === "Repeater") return { classes: ["pfb-repeater"], style: custom };
	if (df.fieldtype === "HTML") return { classes: ["custom-html"], style: custom };
	if (df.fieldtype === "Field Template") return { classes: ["field-template"], style: custom };
	if (df.fieldtype === "Spacer")
		return { classes: [], style: { height: df.height ? `${df.height}px` : "1em", ...custom } };
	if (df.fieldtype === "Divider") {
		return {
			classes: [],
			style: {
				height: "1px",
				margin: "0.5em 0",
				borderBottom: "1px solid",
				borderBottomColor: "var(--dark-border-color)",
				...custom,
			},
		};
	}
	if (df.fieldtype === "Image" || df.fieldtype === "Barcode") {
		return {
			classes: [
				"field",
				df.fieldtype === "Image" ? "print-image" : "print-barcode",
				df.align ? `field-align-${df.align}` : "",
			],
			style: custom,
		};
	}
	const lr = props.field_orientation === "left-right";
	const style = {};
	if ((lr || df.show_label === "inline") && df.label_gap != null) {
		style.gap = df.label_gap + "px";
	}
	return {
		classes: [
			"field",
			lr ? "left-right" : "",
			!lr && df.show_label === "inline" ? "field-inline" : "",
			df.align ? `field-align-${df.align}` : "",
			lr && df.label_justify && !["center", "right"].includes(df.align)
				? `field-justify-${df.label_justify}`
				: "",
		],
		style: { ...style, ...custom },
	};
});

// Spacer/Divider carry no data attributes on the server either
function preview_data_attr(value) {
	if (!preview_doc.value || !value) return undefined;
	if (props.df.fieldtype === "Spacer" || props.df.fieldtype === "Divider") return undefined;
	return value;
}

// Render Jinja2 HTML fields server-side when in preview mode
watch(
	[preview_doc, () => props.df.html],
	async ([doc]) => {
		const html = props.df.html;
		if (!doc || !html || props.df.fieldtype !== "HTML") {
			rendered_html.value = null;
			template_render_failed.value = false;
			return;
		}
		rendered_html.value = await render_jinja_html(
			html,
			store.meta.value?.name,
			store.preview_doc_name.value
		);
		template_render_failed.value = rendered_html.value === null;
	},
	{ immediate: true }
);

// Render Field Template fields server-side when in preview mode
watch(
	[preview_doc, () => props.df.field_template],
	async ([doc]) => {
		if (!doc || props.df.fieldtype !== "Field Template" || !props.df.field_template) {
			rendered_template.value = null;
			template_render_failed.value = false;
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
			template_render_failed.value = rendered_template.value === null;
		} catch {
			rendered_template.value = null;
			template_render_failed.value = true;
		}
	},
	{ immediate: true }
);

const { preview_value, preview_value_html, rating_stars, multiselect_display } = useFieldFormat(
	props,
	store,
	preview_doc
);

function select_field(e) {
	if (e && e.shiftKey && !e.metaKey && !e.ctrlKey) {
		store.select_field_range(props.df);
		return;
	}
	const additive = !!(e && (e.metaKey || e.ctrlKey));
	store.select_field(props.df, additive);
	if (!additive && props.df.fieldtype !== "HTML") {
		editing.value = true;
	}
}
function kbd_select(e) {
	if (e && e.shiftKey && !e.metaKey && !e.ctrlKey) {
		store.select_field_range(props.df);
		return;
	}
	store.select_field(props.df, !!(e.metaKey || e.ctrlKey));
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
		Image: "Img",
		Barcode: "Code",
		"Field Template": "Tmpl",
		Repeater: "Repeat",
	};
	return map[props.df.fieldtype] || props.df.fieldtype?.substring(0, 5) || "";
});

let code_edit = computed(() => {
	if (props.df.fieldtype == "HTML") return { title: __("Edit HTML"), open: edit_html };
	if (props.df.fieldtype == "Typst") return { title: __("Edit Typst"), open: edit_typst };
	return null;
});

function edit_code({ title, key, field, clean }) {
	let d = new frappe.ui.Dialog({
		title,
		fields: [{ fieldname: key, fieldtype: "Code", ...field }],
		primary_action: (values) => {
			props.df[key] = clean(values[key]);
			d.hide();
		},
	});
	d.set_value(key, props.df[key]);
	d.show();
}

function edit_html() {
	edit_code({
		title: __("Edit HTML"),
		key: "html",
		field: { label: __("HTML"), options: "HTML" },
		clean: (html) => frappe.dom.remove_script_and_style(html),
	});
}

function edit_typst() {
	edit_code({
		title: __("Edit Typst"),
		key: "typst",
		field: {
			label: __("Typst Markup"),
			description: __("Use {0} for values from the document.", ["{{ doc.field_name }}"]),
		},
		clean: (typst) => typst || "",
	});
}

function save_as_snippet() {
	frappe.prompt(
		{
			label: __("Snippet name"),
			fieldname: "name",
			fieldtype: "Data",
			reqd: 1,
			default: props.df.label || props.df.fieldname || "",
		},
		({ name }) => {
			store.save_snippet(name, props.df, "Field").then(
				() =>
					frappe.show_alert(
						{ message: __("Field saved as snippet"), indicator: "green" },
						3
					),
				() => {}
			);
		},
		__("Save Field as Snippet"),
		__("Save")
	);
}

const { open: open_context_menu } = useContextMenu();

function on_context_menu(e) {
	store.select_field(props.df);
	open_context_menu(e, [
		{ label: __("Copy"), icon: "copy", action: () => store.copy_field(props.df) },
		{
			label: __("Duplicate"),
			icon: "copy-plus",
			action: () => store.duplicate_field(props.df),
		},
		{ label: __("Save as snippet"), icon: "bookmark-plus", action: save_as_snippet },
		store.clipboard.value && {
			label: __("Paste"),
			icon: "clipboard-paste",
			action: () => store.paste_clipboard(),
		},
		{ divider: true },
		{
			label: __("Delete"),
			icon: "trash",
			danger: true,
			action: () => store.remove_field(props.df),
		},
	]);
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
.field--chip {
	position: relative;
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

.field--chip:active {
	cursor: grabbing;
}

.field--chip.sortable-chosen {
	cursor: grabbing;
}

.field--chip:focus-within {
	border-style: solid;
	border-color: var(--gray-600);
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

.field--chip .custom-html {
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
	position: relative;
}

.field--condition-hidden {
	opacity: 0.35;
}

.field--preview.field--selected::after,
.field--preview:hover::after,
.field--preview.field--layer-hover::after,
.field--chip.field--selected::after,
.field--chip:hover::after,
.field--chip.field--layer-hover::after {
	content: "";
	position: absolute;
	inset: 0;
	z-index: 1;
	border: var(--pfb-ring);
	border-radius: inherit;
	pointer-events: none;
}

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

.pf-builder-thumb {
	max-height: 32px;
	max-width: 120px;
	object-fit: contain;
	border-radius: var(--radius);
	vertical-align: middle;
}

.typst-block-source {
	margin: 0;
	font-family: monospace;
	font-size: var(--text-xs);
	white-space: pre-wrap;
	word-break: break-word;
	color: var(--text-color);
	background: var(--gray-50);
	border-radius: var(--radius-sm);
	padding: 4px 6px;
}
</style>
