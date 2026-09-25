<template>
	<div
		class="field-row"
		:style="{ textAlign: df.align || 'left', ...text_style, ...custom_style }"
		:class="{ 'field-row--lr': field_orientation === 'left-right' }"
	>
		<div class="drag-handle field-drag-handle" v-html="frappe.utils.icon('grip', 'xs')"></div>
		<div class="field-body">
			<div class="field-content">
				<div
					class="custom-html"
					v-if="df.fieldtype == 'HTML' && df.html"
					v-html="strip_unsafe_html(df.html)"
				></div>
				<pre v-else-if="df.fieldtype == 'Typst' && df.typst" class="typst-block-source">{{
					df.typst
				}}</pre>
				<div class="custom-html" v-else-if="df.fieldtype == 'Field Template'">
					{{ df.label }}
				</div>
				<div
					v-else-if="df.fieldtype == 'Static Text' && df.text"
					:style="static_text_style"
				>
					{{ df.text }}
				</div>
				<img
					v-else-if="df.fieldtype == 'Image' && df.custom && df.image_url"
					:src="df.image_url"
					class="pf-builder-thumb"
					:alt="df.label || ''"
				/>
				<input
					v-else-if="editing && df.fieldtype != 'HTML' && df.fieldtype != 'Typst'"
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

<script setup>
import { computed, inject, nextTick, ref, watch } from "vue";
import { strip_unsafe_html } from "../../utils";
import { useFieldStyles } from "./useFieldRoot";
import { open_html_editor } from "../../composables/useHtmlEditorDialog";

const props = defineProps(["df", "field_orientation"]);
const store = inject("$store");
const { custom_style, text_style, static_text_style } = useFieldStyles(props);

const editing = ref(false);
const label_input = ref(null);
watch(editing, (value) => {
	if (value) nextTick(() => label_input.value?.focus());
});
defineExpose({ edit: () => (editing.value = true) });

const SHORT_FIELDTYPE = {
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
const short_fieldtype = computed(
	() => SHORT_FIELDTYPE[props.df.fieldtype] || props.df.fieldtype?.substring(0, 5) || ""
);

const code_edit = computed(() => {
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
	open_html_editor({
		title: __("Edit HTML"),
		initial_html: props.df.html || "",
		doctype: store.meta.value?.name,
		docname: store.preview_doc_name.value,
		on_save: (html) => (props.df.html = html),
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
</script>

<style scoped>
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

.no-columns-hint {
	font-size: var(--text-xs);
}

.field-row--lr {
	flex-direction: row;
	align-items: center;
}

.pf-builder-thumb {
	max-height: 32px;
	max-width: 120px;
	object-fit: contain;
	border-radius: var(--radius);
	vertical-align: middle;
}
</style>
