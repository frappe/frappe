<template>
	<div
		class="field"
		:class="{ 'field--table': df.fieldtype == 'Table' }"
		v-show="!df.remove"
		:title="df.label || df.fieldname"
		@click="editing = true"
	>
		<div class="field-row">
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
	</div>
</template>

<script setup>
import ConfigureColumnsVue from "./ConfigureColumns.vue";
import { createApp, ref, nextTick, watch, computed } from "vue";

const props = defineProps(["df"]);

let editing = ref(false);
let label_input = ref(null);

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
</style>
