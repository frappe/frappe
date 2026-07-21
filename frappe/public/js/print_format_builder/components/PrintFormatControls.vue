<template>
	<div class="pfb-sidebar">
		<!-- Tab bar -->
		<div class="pfb-tabbar" role="tablist">
			<button
				v-for="tab in tabs"
				:key="tab.id"
				class="pfb-tab"
				:class="{ active: activeTab === tab.id }"
				:title="tab.label"
				role="tab"
				:aria-selected="activeTab === tab.id"
				@click="activeTab = tab.id"
			>
				<span class="pfb-tab-label">{{ tab.label }}</span>
			</button>
		</div>

		<!-- ── Fields ────────────────────────────────────────── -->
		<div v-if="activeTab === 'fields'" class="pfb-tab-body pfb-fields-tab">
			<!-- Search -->
			<div class="pfb-search-wrap">
				<span
					class="pfb-search-icon text-muted"
					v-html="frappe.utils.icon('search', 'xs')"
				></span>
				<input
					ref="search_input"
					class="pfb-search"
					type="text"
					:placeholder="__('Search fields...')"
					v-model="search_text"
				/>
				<kbd class="pfb-search-kbd" @click="focus_search">/</kbd>
			</div>

			<!-- Header -->
			<div class="pfb-fields-header">
				<span class="pfb-fields-header-title">
					{{ __("DOCUMENT FIELDS") }}
					<span class="pfb-fields-header-sep">·</span>
					{{ (meta.name || "").toUpperCase() }}
				</span>
			</div>

			<!-- Groups -->
			<div
				v-for="group in field_groups"
				:key="group.label || '__root__'"
				class="pfb-field-group"
			>
				<div v-if="group.label" class="pfb-group-label">{{ group.label }}</div>
				<draggable
					:list="group.fields"
					:group="{ name: 'fields', pull: 'clone', put: false }"
					:sort="false"
					:clone="clone_field"
					item-key="fieldname"
					v-bind="DRAG_OPTIONS"
					@start="setDragging(true)"
					@end="setDragging(false)"
				>
					<template #item="{ element }">
						<div
							class="pfb-field-row"
							:title="element.fieldname"
							@click="add_to_layout(element)"
						>
							<span
								class="pfb-field-drag"
								v-html="frappe.utils.icon('grip', 'xs')"
							></span>
							<span class="pfb-field-label">{{ element.label }}</span>
							<span class="pfb-field-type">{{ element.fieldtype }}</span>
						</div>
					</template>
				</draggable>
			</div>

			<div v-if="!field_groups.length" class="pfb-empty">
				{{
					search_text
						? __("No fields match your search.")
						: __("This document type has no printable fields.")
				}}
			</div>
		</div>

		<!-- ── Blocks ─────────────────────────────────────────── -->
		<div v-else-if="activeTab === 'blocks'" class="pfb-tab-body">
			<div class="pfb-group-label">{{ __("Content") }}</div>
			<draggable
				:list="draggable_blocks"
				:group="{ name: 'fields', pull: 'clone', put: false }"
				:sort="false"
				:clone="clone_field"
				item-key="fieldname"
				v-bind="DRAG_OPTIONS"
				@start="setDragging(true)"
				@end="setDragging(false)"
			>
				<template #item="{ element }">
					<div
						class="pfb-block-card"
						:title="element.desc"
						@click="add_to_layout(element)"
					>
						<span
							class="pfb-block-icon"
							v-html="frappe.utils.icon(element.icon, 'sm')"
						></span>
						<div class="pfb-block-info">
							<div class="pfb-block-name">{{ element.label }}</div>
							<div class="pfb-block-desc text-muted">{{ element.desc }}</div>
						</div>
					</div>
				</template>
			</draggable>

			<div class="pfb-group-label mt-3">{{ __("Page") }}</div>
			<draggable
				:list="page_break_block"
				:group="{ name: 'sections', pull: 'clone', put: false }"
				:sort="false"
				:clone="clone_as_section"
				item-key="fieldname"
				v-bind="DRAG_OPTIONS"
				@start="setDragging(true)"
				@end="setDragging(false)"
			>
				<template #item="{ element }">
					<div class="pfb-block-card" :title="element.desc" @click="add_page_break">
						<span
							class="pfb-block-icon"
							v-html="frappe.utils.icon('scissors-line-dashed', 'sm')"
						></span>
						<div class="pfb-block-info">
							<div class="pfb-block-name">{{ element.label }}</div>
							<div class="pfb-block-desc text-muted">{{ element.desc }}</div>
						</div>
					</div>
				</template>
			</draggable>
		</div>

		<!-- ── Library ───────────────────────────────────────── -->
		<div v-else-if="activeTab === 'library'" class="pfb-tab-body">
			<div class="pfb-group-label">
				{{ __("Saved Snippets") }}
				<span class="pfb-label-actions">
					<button
						class="es-button"
						data-size="xs"
						data-variant="ghost"
						data-icon-button="true"
						:disabled="!store.snippets.value.length"
						:title="__('Export snippets')"
						@click="store.export_snippets()"
						v-html="frappe.utils.icon('download', 'xs')"
					></button>
					<button
						class="es-button"
						data-size="xs"
						data-variant="ghost"
						data-icon-button="true"
						:title="__('Import snippets')"
						@click="import_snippets"
						v-html="frappe.utils.icon('upload', 'xs')"
					></button>
				</span>
			</div>
			<div v-if="!store.snippets.value.length" class="pfb-empty">
				{{ __("Save a section or field as a snippet to reuse it here.") }}
			</div>
			<template v-for="grp in snippet_groups" :key="grp.type">
				<draggable
					v-if="grp.items.length"
					:list="grp.items"
					:group="{ name: grp.drag_group, pull: 'clone', put: false }"
					:sort="false"
					:clone="clone_snippet"
					item-key="name"
					filter="button"
					:preventOnFilter="false"
					v-bind="DRAG_OPTIONS"
					@start="setDragging(true)"
					@end="setDragging(false)"
				>
					<template #item="{ element: snip }">
						<div
							class="pfb-block-card"
							:title="__('Drag into the layout, or click to insert')"
							@click="store.insert_snippet(snip.name)"
						>
							<span
								class="pfb-block-icon"
								v-html="frappe.utils.icon(grp.icon, 'sm')"
							></span>
							<div class="pfb-block-info">
								<div class="pfb-block-name">{{ snip.name }}</div>
								<div class="pfb-block-desc text-muted">{{ grp.desc }}</div>
							</div>
							<button
								class="es-button"
								data-size="xs"
								data-variant="ghost"
								data-theme="red"
								data-icon-button="true"
								:title="__('Delete snippet')"
								@click.stop="confirm_delete_snippet(snip.name)"
								v-html="frappe.utils.icon('trash', 'xs')"
							></button>
						</div>
					</template>
				</draggable>
			</template>

			<div class="pfb-group-label mt-3">
				{{ __("Field Templates") }}
				<a
					:href="'/app/print-format-field-template'"
					target="_blank"
					class="pfb-manage-link text-muted"
				>
					{{ __("Manage") }}
				</a>
			</div>
			<div v-if="!print_templates_list.length" class="pfb-empty">
				{{
					__(
						"Field templates render a specific field with custom Jinja/HTML, e.g. a custom items table."
					)
				}}
				<a :href="new_template_link" target="_blank">{{ __("Create one") }}</a>
			</div>
			<draggable
				v-else
				:list="print_templates_list"
				:group="{ name: 'fields', pull: 'clone', put: false }"
				:sort="false"
				:clone="clone_field"
				item-key="fieldname"
				v-bind="DRAG_OPTIONS"
				@start="setDragging(true)"
				@end="setDragging(false)"
			>
				<template #item="{ element }">
					<div
						class="pfb-block-card"
						:title="element.fieldname"
						@click="add_to_layout(element)"
					>
						<span
							class="pfb-block-icon"
							v-html="frappe.utils.icon('code', 'sm')"
						></span>
						<div class="pfb-block-info">
							<div class="pfb-block-name">{{ element.display_label }}</div>
							<div class="pfb-block-desc text-muted">
								{{ element.field_label || __("Custom block") }}
							</div>
						</div>
					</div>
				</template>
			</draggable>
		</div>

		<!-- ── Outline ────────────────────────────────────────── -->
		<div v-else-if="activeTab === 'outline'" class="pfb-tab-body pfb-tree" role="tree">
			<div v-if="!outline_tree.length" class="pfb-empty">
				{{ __("No sections yet. Add sections to the canvas.") }}
			</div>
			<div v-for="(node, i) in outline_tree" :key="i" class="pfb-tree-node">
				<div
					class="pfb-tree-row"
					:class="{ active: store.selected_section.value === node.section }"
					role="treeitem"
					tabindex="0"
					:aria-expanded="!is_collapsed(node.section)"
					:aria-selected="store.selected_section.value === node.section"
					@click="select_section(node.section)"
					@keydown.enter.prevent="select_section(node.section)"
					@keydown.space.prevent="select_section(node.section)"
				>
					<button
						class="pfb-tree-chevron"
						:class="{ collapsed: is_collapsed(node.section) }"
						@click.stop="toggle_collapse(node.section)"
						v-html="frappe.utils.icon('chevron-down', 'sm')"
					></button>
					<span
						class="pfb-tree-icon"
						v-html="frappe.utils.icon('rectangle-horizontal', 'sm')"
					></span>
					<span class="pfb-tree-label">
						{{ node.section.label || __("Untitled section") }}
					</span>
				</div>
				<div v-if="!is_collapsed(node.section)" class="pfb-tree-children">
					<div v-for="(col, ci) in node.columns" :key="ci" class="pfb-tree-node">
						<div
							class="pfb-tree-row"
							role="treeitem"
							tabindex="0"
							@click="select_section(node.section)"
							@keydown.enter.prevent="select_section(node.section)"
							@keydown.space.prevent="select_section(node.section)"
						>
							<button
								v-if="col.fields.length"
								class="pfb-tree-chevron"
								:class="{ collapsed: is_collapsed(col.column) }"
								@click.stop="toggle_collapse(col.column)"
								v-html="frappe.utils.icon('chevron-down', 'sm')"
							></button>
							<span v-else class="pfb-tree-spacer"></span>
							<span
								class="pfb-tree-icon"
								v-html="frappe.utils.icon('columns-2', 'sm')"
							></span>
							<span class="pfb-tree-label text-muted">
								{{ __("Column {0}", [ci + 1]) }}
							</span>
						</div>
						<div v-if="!is_collapsed(col.column)" class="pfb-tree-children">
							<div
								v-for="(field, fi) in col.fields"
								:key="fi"
								class="pfb-tree-row"
								:class="{ active: store.selected_fields.value.includes(field) }"
								role="treeitem"
								tabindex="0"
								:aria-selected="store.selected_fields.value.includes(field)"
								@click="select_field(field, node.section, $event)"
								@keydown.enter.prevent="select_field(field, node.section, $event)"
								@keydown.space.prevent="select_field(field, node.section, $event)"
							>
								<span class="pfb-tree-spacer"></span>
								<span
									class="pfb-tree-icon"
									v-html="frappe.utils.icon(field_icon(field), 'sm')"
								></span>
								<span class="pfb-tree-label">{{ field_label(field) }}</span>
								<span
									v-if="field_broken(field)"
									class="pfb-tree-warn"
									:title="
										__('Field “{0}” no longer exists on {1}', [
											field.fieldname,
											meta.name,
										])
									"
									v-html="frappe.utils.icon('triangle-alert', 'sm')"
								></span>
								<span class="pfb-tree-badge">{{ field.fieldtype }}</span>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- ── Format ─────────────────────────────────────────── -->
		<div v-else-if="activeTab === 'format'" class="pfb-tab-body pfb-format-tab">
			<div class="form-group">
				<label class="control-label">{{ __("Style Preset") }}</label>
				<div class="pfb-preset-row">
					<select
						class="form-control form-control-sm"
						:value="active_preset"
						@change="apply_preset($event.target.value)"
					>
						<option value="">{{ __("Choose a preset…") }}</option>
						<option
							v-for="p in store.style_presets.value"
							:key="p.name"
							:value="p.name"
						>
							{{ p.name }}
						</option>
					</select>
					<button
						class="es-button"
						data-size="sm"
						data-variant="ghost"
						data-icon-button="true"
						:title="__('Save current style as a preset')"
						@click="save_preset"
						v-html="frappe.utils.icon('save', 'sm')"
					></button>
					<button
						v-if="active_preset"
						class="es-button"
						data-size="sm"
						data-variant="ghost"
						data-theme="red"
						data-icon-button="true"
						:title="__('Delete preset')"
						@click="delete_preset"
						v-html="frappe.utils.icon('trash', 'sm')"
					></button>
				</div>
			</div>
			<div class="form-group">
				<label class="control-label">{{ __("Page Margins (mm)") }}</label>
				<div class="pfb-margin-grid">
					<div class="pfb-margin-cell" v-for="df in margins" :key="df.fieldname">
						<label class="pfb-margin-label control-label">{{ df.label }}</label>
						<input
							type="number"
							class="form-control form-control-sm"
							:value="print_format[df.fieldname]"
							min="0"
							@change="(e) => update_margin(df.fieldname, e.target.value)"
						/>
					</div>
				</div>
			</div>
			<div class="form-group">
				<label class="control-label">{{ __("Google Font") }}</label>
				<Autocomplete
					:options="font_options"
					:model-value="print_format.font || ''"
					:placeholder="__('Default')"
					@select="(o) => (print_format.font = o.value)"
				/>
			</div>
			<div class="form-group">
				<label class="control-label">{{ __("Font Size (pt)") }}</label>
				<input
					type="number"
					class="form-control form-control-sm"
					placeholder="12, 13, 14"
					:value="print_format.font_size"
					@change="(e) => (print_format.font_size = parseFloat(e.target.value))"
				/>
			</div>
			<div class="form-group" v-for="c in color_settings" :key="c.fieldname">
				<label class="control-label">{{ c.label }}</label>
				<div :ref="(el) => (color_hosts[c.fieldname] = el)"></div>
			</div>
			<div class="form-group">
				<label class="control-label">{{ __("Page Number") }}</label>
				<select class="form-control form-control-sm" v-model="print_format.page_number">
					<option v-for="p in page_number_positions" :value="p.value">
						{{ p.label }}
					</option>
				</select>
			</div>
		</div>
	</div>
</template>

<script setup>
import draggable from "vuedraggable";
import Autocomplete from "../../vue-components/Autocomplete.vue";
import {
	BLOCK_FIELDTYPES,
	DRAG_OPTIONS,
	clone_plain,
	freshen_field,
	get_table_columns,
	pluck,
	setDragging,
} from "../utils";
import { mountColorControl } from "./inspector/useColorControl";
import { useStore } from "../stores";
import { computed, onMounted, onUnmounted, nextTick, ref, watch, inject } from "vue";

// state
let search_text = ref("");
let google_fonts = ref([]);
let font_options = computed(() => [
	{ label: __("Default"), value: "" },
	...google_fonts.value.map((f) => ({ label: f, value: f })),
]);
let activeTab = ref("fields");
let search_input = ref(null);
let raw_templates = ref([]);

function focus_search() {
	activeTab.value = "fields";
	nextTick(() => search_input.value?.focus());
}

// store
let store = inject("$store");
let { meta, print_format, layout } = useStore();

// ── tab definitions ───────────────────────────────────────
const tabs = computed(() => [
	{ id: "fields", label: __("Fields") },
	{ id: "blocks", label: __("Blocks") },
	{ id: "library", label: __("Library") },
	{ id: "outline", label: __("Outline") },
	{ id: "format", label: __("Setting") },
]);

// ── blocks tab items ──────────────────────────────────────
const page_break_block = [
	{
		label: __("Page Break"),
		fieldname: "page_break",
		desc: __("Force a new page"),
	},
];

const draggable_blocks = [
	{
		label: __("Custom HTML"),
		fieldname: "custom_html",
		fieldtype: "HTML",
		html: "",
		custom: 1,
		icon: "code",
		desc: __("Raw HTML or Jinja template"),
	},
	{
		label: __("Spacer"),
		fieldname: "spacer",
		fieldtype: "Spacer",
		custom: 1,
		icon: "minus",
		desc: __("Vertical whitespace"),
	},
	{
		label: __("Divider"),
		fieldname: "divider",
		fieldtype: "Divider",
		custom: 1,
		icon: "minus",
		desc: __("Horizontal rule"),
	},
	{
		label: __("Image"),
		fieldname: "image",
		fieldtype: "Image",
		custom: 1,
		icon: "image",
		desc: __("Upload an image or use a URL"),
		image_url: "",
		width: "",
	},
	{
		label: __("Barcode"),
		fieldname: "barcode",
		fieldtype: "Barcode",
		custom: 1,
		icon: "barcode",
		desc: __("Barcode or QR code from a field or static value"),
		barcode_field: "",
		barcode_value: "",
		barcode_format: "CODE128",
		show_text: true,
		width: "",
	},
	{
		label: __("Repeater"),
		fieldname: "repeater",
		fieldtype: "Repeater",
		custom: 1,
		icon: "list",
		desc: __("Repeat child table rows as templated lines"),
		source: "",
		repeater_columns: [
			{ template: [], align: "left" },
			{ template: [], align: "right" },
		],
	},
];

const color_settings = [
	{ fieldname: "label_color", label: __("Label Color") },
	{ fieldname: "value_color", label: __("Value Color") },
];
let color_hosts = ref({});
let color_controls = {};

function mount_color_controls() {
	for (const c of color_settings) {
		const host = color_hosts.value[c.fieldname];
		if (!host) continue;
		color_controls[c.fieldname] = mountColorControl(host, {
			value: print_format.value[c.fieldname] || "",
			placeholder: c.label,
			fieldname: c.fieldname,
			onChange(value) {
				const v = value || null;
				if ((print_format.value[c.fieldname] ?? null) !== v) {
					print_format.value[c.fieldname] = v;
				}
			},
		});
	}
}

// ── style presets ──────────────────────────────────────────
let active_preset = ref("");
function apply_preset(name) {
	active_preset.value = name;
	if (name) store.apply_style_preset(name);
}
function save_preset() {
	frappe.prompt(
		{
			label: __("Preset name"),
			fieldname: "name",
			fieldtype: "Data",
			reqd: 1,
			default: active_preset.value || "",
		},
		({ name }) => {
			store.save_style_preset(name);
			active_preset.value = name.trim();
			frappe.show_alert({ message: __("Style preset saved"), indicator: "green" });
		},
		__("Save Style Preset"),
		__("Save")
	);
}
function delete_preset() {
	const name = active_preset.value;
	if (!name) return;
	frappe.confirm(__("Delete the style preset '{0}'?", [name]), () => {
		store.delete_style_preset(name);
		active_preset.value = "";
	});
}
function confirm_delete_snippet(name) {
	frappe.confirm(__("Delete the snippet '{0}'?", [name]), () => store.delete_snippet(name));
}

function import_snippets() {
	const input = document.createElement("input");
	input.type = "file";
	input.accept = "application/json,.json";
	input.onchange = async () => {
		const file = input.files?.[0];
		if (!file) return;
		let payload;
		try {
			payload = JSON.parse(await file.text());
		} catch {
			frappe.throw(__("{0} is not a valid JSON file", [file.name]));
		}
		const { imported, other_doctypes, skipped } = await store.import_snippets(payload);
		let message = __("Imported {0} snippet(s)", [imported]);
		if (other_doctypes) {
			message += " " + __("({0} belong to other document types)", [other_doctypes]);
		}
		if (skipped.length) {
			message += " — " + __("skipped {0}", [skipped.join(", ")]);
		}
		frappe.show_alert(
			{ message, indicator: skipped.length ? "orange" : "green" },
			skipped.length ? 7 : 5
		);
	};
	input.click();
}

// ── helpers ────────────────────────────────────────────────
function update_margin(fieldname, value) {
	value = parseFloat(value);
	if (value < 0) value = 0;
	print_format.value[fieldname] = value;
}

function clone_field(df) {
	let cloned = pluck(df, [
		"label",
		"fieldname",
		"fieldtype",
		"options",
		"table_columns",
		"html",
		"field_template",
		"source",
		"repeater_columns",
		"custom",
		"image_url",
		"width",
		"barcode_field",
		"barcode_value",
		"barcode_format",
		"show_text",
	]);
	if (cloned.custom) {
		cloned.fieldname += "_" + frappe.utils.get_random(8);
	}
	// Repeater has no title by default — the palette label is only for the palette.
	if (cloned.fieldtype === "Repeater") cloned.label = "";
	return cloned;
}

function add_to_layout(df) {
	const lv = layout.value;
	const sections = lv?.sections;
	if (!sections || !sections.length) return;

	// If a field is selected, insert right after it in the same column.
	// Search body sections and header/footer zones so a selected header field
	// is used as the anchor when inserting from the panel.
	const selected_field = store.selected_field.value;
	if (selected_field && !selected_field.remove) {
		const all_zones = [lv?.header, lv?.footer, ...sections].filter(Boolean);
		for (const section of all_zones) {
			for (const column of section.columns) {
				const idx = column.fields.indexOf(selected_field);
				if (idx !== -1) {
					column.fields.splice(idx + 1, 0, clone_field(df));
					return;
				}
			}
		}
	}

	// Otherwise add to the last column of the selected (or last body) section.
	// Header/footer zone sections are valid targets when they are selected.
	const selected = store.selected_section.value;
	const is_valid_target =
		selected &&
		(sections.includes(selected) || selected === lv?.header || selected === lv?.footer);
	const target_section = is_valid_target ? selected : sections.slice(-1)[0];
	if (!target_section) return;
	const last_column = target_section.columns.slice(-1)[0];
	if (!last_column) return;
	last_column.fields.push(clone_field(df));
}

function build_field(df) {
	let out = {
		label: df.label,
		fieldname: df.fieldname,
		fieldtype: df.fieldtype,
		options: df.options,
	};
	if (df.fieldtype === "Table") {
		out.table_columns = get_table_columns(df);
	}
	return out;
}

function select_section(section) {
	store.scroll_to_section.value = section;
	store.select_section(section);
}

function select_field(field, section, e) {
	const additive = !!(e && (e.metaKey || e.ctrlKey || e.shiftKey));
	if (section && !additive) store.scroll_to_section.value = section;
	store.select_field(field, additive);
}

function field_label(f) {
	return f.label || f.fieldname || f.fieldtype || __("Field");
}

let known_fieldnames = computed(() => {
	const s = new Set((meta.value?.fields || []).map((df) => df.fieldname));
	s.add("name");
	return s;
});
function field_broken(f) {
	if (f.custom || f.fieldtype === "Field Template" || !f.fieldname) return false;
	if (BLOCK_FIELDTYPES.has(f.fieldtype)) return false;
	return !known_fieldnames.value.has(f.fieldname);
}

let outline_tree = computed(() =>
	visible_sections.value.map((section) => ({
		section,
		columns: (section.columns || []).map((column) => ({
			column,
			fields: (column.fields || []).filter((f) => !f.remove),
		})),
	}))
);

const FIELD_ICONS = {
	Table: "table",
	Repeater: "rows-3",
	Image: "image",
	"Attach Image": "image",
	Attach: "image",
	HTML: "file-text",
	"Text Editor": "file-text",
	"Small Text": "file-text",
	"Long Text": "file-text",
	Text: "file-text",
	Barcode: "square",
};
function field_icon(f) {
	return FIELD_ICONS[f.fieldtype] || "type";
}

let collapsed_nodes = ref(new Set());
function is_collapsed(node) {
	return collapsed_nodes.value.has(node);
}
function toggle_collapse(node) {
	const next = new Set(collapsed_nodes.value);
	next.has(node) ? next.delete(node) : next.add(node);
	collapsed_nodes.value = next;
}
watch(
	() => layout.value,
	() => (collapsed_nodes.value = new Set())
);

function clone_as_section() {
	return { label: "", columns: [{ label: "", fields: [] }], page_break: true };
}

// Drag-insert bypasses insert_field/insert_section, so freshen here too — a custom
// field dropped twice would otherwise carry the same fieldname into both copies.
function clone_snippet(snip) {
	const clone = clone_plain(snip.content);
	if (snip.snippet_type === "Field") return freshen_field(clone);
	delete clone.remove;
	(clone.columns || []).forEach((c) => (c.fields || []).forEach(freshen_field));
	return clone;
}

const SNIPPET_GROUPS = [
	{ type: "Section", drag_group: "sections", icon: "layout-template", desc: __("Section") },
	{ type: "Field", drag_group: "fields", icon: "text-cursor-input", desc: __("Field") },
];

let snippet_groups = computed(() =>
	SNIPPET_GROUPS.map((grp) => ({
		...grp,
		items: store.snippets.value.filter((s) => s.snippet_type === grp.type),
	}))
);

function add_page_break() {
	if (!layout.value) return;
	layout.value.sections.push(clone_as_section());
}

// ── computed: field groups (by section break labels) ────────
let field_groups = computed(() => {
	const q = search_text.value.toLowerCase();

	// Seed with ID (name) field
	const groups = [{ label: null, fields: [] }];
	let current = groups[0];

	// Always show ID field first
	const id_field = build_field({
		label: __("ID (name)"),
		fieldname: "name",
		fieldtype: "Data",
	});
	if (!q || "id name".includes(q)) {
		current.fields.push(id_field);
	}

	for (const df of meta.value.fields) {
		if (df.fieldtype === "Section Break") {
			if (df.label) {
				current = { label: df.label, fields: [] };
				groups.push(current);
			}
			continue;
		}
		if (df.fieldtype === "Column Break") continue;
		if (
			frappe.model.no_value_type.includes(df.fieldtype) &&
			df.fieldtype !== "Table" &&
			df.fieldtype !== "Table MultiSelect"
		)
			continue;

		if (q) {
			const match =
				(df.fieldname || "").toLowerCase().includes(q) ||
				(df.label || "").toLowerCase().includes(q);
			if (!match) continue;
		}

		current.fields.push(build_field(df));
	}

	return groups.filter((g) => g.fields.length);
});

// ── library tab ───────────────────────────────────────────
function fetch_templates() {
	const doctype = meta.value?.name;
	if (!doctype) return;
	Promise.all([
		frappe.db.get_list("Print Format Field Template", {
			fields: ["name", "template", "field"],
			filters: { document_type: doctype },
			limit: 100,
		}),
		frappe.db.get_list("Print Format Field Template", {
			fields: ["name", "template", "field"],
			filters: { document_type: ["is", "not set"] },
			limit: 100,
		}),
	])
		.then(([specific, generic]) => {
			raw_templates.value = [...(specific || []), ...(generic || [])];
		})
		.catch(() => {
			raw_templates.value = [];
		});
}

watch(activeTab, (tab) => {
	if (tab === "library") fetch_templates();
	if (tab === "format") nextTick(mount_color_controls);
});

watch(
	() => color_settings.map((c) => print_format.value?.[c.fieldname]),
	() => {
		for (const c of color_settings) {
			const ctrl = color_controls[c.fieldname];
			if (!ctrl) continue;
			const model = print_format.value?.[c.fieldname] || "";
			if ((ctrl.get_value() || "") !== model) ctrl.set_value(model);
		}
	}
);

let print_templates_list = computed(() => {
	const templates = raw_templates.value;
	return templates.map((template) => {
		let df;
		let field_label = null;
		if (template.field) {
			df = frappe.meta.get_docfield(meta.value.name, template.field);
			field_label = df ? __(df.label, null, df.parent) : template.field;
		} else {
			df = { label: template.name, fieldname: frappe.scrub(template.name) };
		}
		return {
			name: template.name,
			display_label: template.name,
			fieldname: (df?.fieldname || frappe.scrub(template.name)) + "_template",
			fieldtype: "Field Template",
			field_template: template.name,
			field_label,
		};
	});
});

// ── computed: outline tab ──────────────────────────────────
let visible_sections = computed(() => {
	if (!layout.value) return [];
	return layout.value.sections.filter((s) => !s.remove);
});

// ── computed: misc ─────────────────────────────────────────
let new_template_link = computed(
	() => `/app/print-format-field-template/new?document_type=${meta.value?.name || ""}`
);

let margins = computed(() => [
	{ label: __("Top"), fieldname: "margin_top" },
	{ label: __("Bottom"), fieldname: "margin_bottom" },
	{ label: __("Left", null, "alignment"), fieldname: "margin_left" },
	{ label: __("Right", null, "alignment"), fieldname: "margin_right" },
]);

let page_number_positions = computed(() => [
	{ label: __("Hide"), value: "Hide" },
	{ label: __("Top Left"), value: "Top Left" },
	{ label: __("Top Center"), value: "Top Center" },
	{ label: __("Top Right"), value: "Top Right" },
	{ label: __("Bottom Left"), value: "Bottom Left" },
	{ label: __("Bottom Center"), value: "Bottom Center" },
	{ label: __("Bottom Right"), value: "Bottom Right" },
]);

// ── lifecycle ──────────────────────────────────────────────
onMounted(() => {
	let method = "frappe.printing.page.print_format_builder.print_format_builder.get_google_fonts";
	frappe.call(method).then((r) => {
		google_fonts.value = r.message || [];
		if (print_format.value.font && !google_fonts.value.includes(print_format.value.font)) {
			google_fonts.value.push(print_format.value.font);
		}
	});

	document.addEventListener("keydown", handle_slash_key);
});

onUnmounted(() => {
	document.removeEventListener("keydown", handle_slash_key);
});

function handle_slash_key(e) {
	if (
		e.key === "/" &&
		!e.ctrlKey &&
		!e.metaKey &&
		document.activeElement.tagName !== "INPUT" &&
		document.activeElement.tagName !== "TEXTAREA"
	) {
		e.preventDefault();
		focus_search();
	}
}
</script>

<style scoped>
/* ── Sidebar shell ───────────────────────────────────────── */
.pfb-sidebar {
	width: 260px;
	flex-shrink: 0;
	height: calc(100vh - var(--pfb-chrome-offset, 95px));
	display: flex;
	flex-direction: column;
	border-right: 1px solid var(--border-color);
	background: var(--fg-color);
}

/* ── Tab bar ─────────────────────────────────────────────── */
.pfb-tabbar {
	display: flex;
	padding: 6px 6px 0;
	gap: 2px;
	border-bottom: 1px solid var(--border-color);
	flex-shrink: 0;
}

.pfb-tab {
	flex: 1;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 8px 2px;
	border: none;
	background: transparent;
	border-radius: var(--radius) var(--radius) 0 0;
	color: var(--text-muted);
	cursor: pointer;
	transition: color 0.12s, background 0.12s;
	font-size: var(--text-tiny);
	font-weight: var(--weight-medium);
	position: relative;
}

.pfb-tab:hover {
	color: var(--text-color);
	background: var(--gray-100);
}

.pfb-tab.active {
	color: var(--primary);
	background: var(--fg-color);
}

.pfb-tab.active::after {
	content: "";
	position: absolute;
	bottom: 0;
	left: 0;
	right: 0;
	height: 2px;
	background: var(--primary);
	border-radius: 2px 2px 0 0;
}

.pfb-tab-label {
	line-height: 1;
}

/* ── Tab body ─────────────────────────────────────────────── */
.pfb-tab-body {
	flex: 1;
	overflow-y: auto;
	padding: 10px;
}

/* ── Search (Fields tab) ─────────────────────────────────── */
.pfb-fields-tab {
	padding: 0;
}

.pfb-search-wrap {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 8px 10px;
	border-bottom: 1px solid var(--border-color);
}

.pfb-search-icon {
	flex-shrink: 0;
	color: var(--gray-500);
}

.pfb-search {
	flex: 1;
	border: none;
	background: transparent;
	font-size: var(--text-sm);
	color: var(--text-color);
	outline: none;
	padding: 0;
	min-width: 0;
}

.pfb-search::placeholder {
	color: var(--gray-400);
}

.pfb-search-kbd {
	flex-shrink: 0;
	font-family: inherit;
	font-size: var(--text-tiny);
	color: var(--gray-400);
	background: var(--gray-100);
	border: 1px solid var(--gray-300);
	border-radius: 3px;
	padding: 1px 5px;
	cursor: pointer;
	line-height: 1.6;
}

/* ── Fields header ───────────────────────────────────────── */
.pfb-fields-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 10px 10px 4px;
}

.pfb-fields-header-title {
	font-size: var(--text-tiny);
	font-weight: var(--weight-semibold);
	letter-spacing: 0.06em;
	color: var(--text-muted);
}

.pfb-fields-header-sep {
	margin: 0 4px;
	opacity: 0.5;
}

/* ── Group label ─────────────────────────────────────────── */
.pfb-group-label {
	font-size: var(--text-tiny);
	font-weight: var(--weight-semibold);
	letter-spacing: 0;
	color: var(--text-muted);
	padding: 8px 10px 2px;
	display: flex;
	justify-content: space-between;
	align-items: center;
}

/* ── Field row (Fields tab) ──────────────────────────────── */
.pfb-field-row {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 7px 10px;
	font-size: var(--text-sm);
	cursor: grab;
	border-bottom: 1px solid var(--gray-100);
}

.pfb-field-row:last-child {
	border-bottom: none;
}

.pfb-field-row:hover {
	background: var(--gray-50);
}

.pfb-field-drag {
	display: flex;
	align-items: center;
	color: var(--gray-300);
	flex-shrink: 0;
	transition: color 0.1s;
}

.pfb-field-row:hover .pfb-field-drag {
	color: var(--gray-500);
}

.pfb-field-label {
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	font-weight: 450;
}

.pfb-field-type {
	font-size: var(--text-tiny);
	color: var(--gray-500);
	padding: 2px 6px;
	white-space: nowrap;
	flex-shrink: 0;
}

/* ── Block card (Blocks + Templates tabs) ────────────────── */
.pfb-block-card {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 8px 10px;
	border-radius: var(--radius);
	border: 1px solid var(--border-color);
	background: var(--gray-50);
	cursor: grab;
	margin-top: 6px;
}

.pfb-block-card:hover {
	background: var(--gray-100);
	border-color: var(--gray-500);
}

.pfb-block-icon {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	border-radius: var(--radius);
	background: var(--gray-200);
	flex-shrink: 0;
}

.pfb-block-info {
	min-width: 0;
	flex: 1;
}

.pfb-block-name {
	font-size: var(--text-sm);
	font-weight: 500;
}

.pfb-block-desc {
	font-size: var(--text-tiny);
	margin-top: 1px;
}

.pfb-manage-link {
	font-size: var(--text-tiny);
	font-weight: 400;
	text-transform: none;
	letter-spacing: 0;
}

.pfb-label-actions {
	display: flex;
	gap: 2px;
	margin-right: -4px;
}

/* ── Outline tab (tree) ──────────────────────────────────── */
.pfb-tree {
	padding-top: 4px;
}

.pfb-tree-row {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 4px 6px;
	border-radius: var(--radius);
	cursor: pointer;
	font-size: var(--text-sm);
	user-select: none;
}

.pfb-tree-row:hover {
	background: var(--gray-100);
}

.pfb-tree-row.active {
	background: var(--gray-200);
	color: var(--gray-900);
	font-weight: 500;
}

.pfb-tree-chevron {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 16px;
	height: 16px;
	padding: 0;
	border: none;
	background: transparent;
	cursor: pointer;
	color: var(--gray-500);
	flex-shrink: 0;
	transition: transform 0.12s ease;
}

.pfb-tree-chevron.collapsed {
	transform: rotate(-90deg);
}

.pfb-tree-spacer {
	width: 16px;
	flex-shrink: 0;
}

.pfb-tree-icon {
	display: flex;
	align-items: center;
	color: var(--gray-500);
	flex-shrink: 0;
}

.pfb-tree-row.active .pfb-tree-icon {
	color: var(--gray-700);
}

.pfb-tree-label {
	flex: 1;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.pfb-tree-badge {
	font-size: var(--text-tiny);
	color: var(--gray-500);
	flex-shrink: 0;
}

.pfb-tree-warn {
	display: inline-flex;
	flex-shrink: 0;
	color: var(--text-on-orange, #b95000);
}

.pfb-tree-children {
	margin-left: 18px;
}

/* ── Format tab ──────────────────────────────────────────── */
.pfb-format-tab .form-group {
	margin-bottom: 10px;
}

.pfb-preset-row {
	display: flex;
	align-items: center;
	gap: 6px;
}

.pfb-preset-row select {
	flex: 1;
}

.pfb-format-tab .form-group:last-child {
	margin-bottom: 0;
}

.pfb-format-tab :deep(.frappe-control) {
	margin-bottom: 0;
}

.pfb-margin-grid {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 6px;
}

.pfb-margin-cell {
	display: flex;
	flex-direction: column;
	gap: 2px;
}

.pfb-margin-label {
	font-size: var(--text-tiny);
}

/* ── Empty state ─────────────────────────────────────────── */
.pfb-empty {
	color: var(--text-muted);
	font-size: var(--text-sm);
	text-align: center;
	padding: 16px 8px;
}

.pfb-fields-tab .pfb-empty {
	padding: 24px 16px;
}

.pfb-field-group {
	border-bottom: 1px solid var(--gray-100);
}

.pfb-field-group:last-child {
	border-bottom: none;
}
</style>
