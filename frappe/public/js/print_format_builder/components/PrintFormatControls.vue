<template>
	<div class="pfb-sidebar">
		<!-- Tab bar: the Espresso tabs contract (es-tabs), same markup the desk's
		     frappe.ui.Tabs and frappe-ui's Tabs.vue render -->
		<div class="es-tabs" data-orientation="horizontal">
			<div class="es-tabs__list" role="tablist" ref="tablist">
				<button
					v-for="tab in tabs"
					:key="tab.id"
					class="es-tabs__tab"
					:data-tab="tab.id"
					:data-state="activeTab === tab.id ? 'active' : 'inactive'"
					role="tab"
					:aria-selected="activeTab === tab.id"
					@click="activeTab = tab.id"
				>
					{{ tab.label }}
				</button>
				<span class="es-tabs__indicator" :style="indicator_style"></span>
			</div>
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
					{{ __("Document Fields") }}
					<span class="pfb-fields-header-sep">·</span>
					{{ meta.name }}
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
					<BlockCard
						:icon="element.icon"
						:name="element.label"
						:desc="element.desc"
						:title="element.desc"
						@click="add_to_layout(element)"
					/>
				</template>
			</draggable>

			<!-- Page Break drops into the sections container, not a column, so it
			     stays a separate draggable — just without its own heading -->
			<draggable
				class="mt-2"
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
					<BlockCard
						icon="scissors-line-dashed"
						:name="element.label"
						:desc="element.desc"
						:title="element.desc"
						@click="add_page_break"
					/>
				</template>
			</draggable>
		</div>

		<!-- ── Library ───────────────────────────────────────── -->
		<div v-else-if="activeTab === 'library'" class="pfb-tab-body">
			<div class="pfb-group-label">
				{{ __("Saved Snippets") }}
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
						<BlockCard
							:icon="grp.icon"
							:name="snip.name"
							:desc="grp.desc"
							:title="__('Drag into the layout, or click to insert')"
							@click="store.insert_snippet(snip.name)"
						>
							<template #action>
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
							</template>
						</BlockCard>
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
					<BlockCard
						icon="code"
						:name="element.display_label"
						:desc="element.field_label || __('Custom block')"
						:title="element.fieldname"
						@click="add_to_layout(element)"
					/>
				</template>
			</draggable>
		</div>

		<!-- ── Layers ─────────────────────────────────────────── -->
		<div v-else-if="activeTab === 'layers'" class="pfb-tab-body pfb-tree" role="tree">
			<div v-if="!layout" class="pfb-empty">
				{{ __("No sections yet. Add sections to the canvas.") }}
			</div>
			<draggable
				v-else
				v-model="tree_sections"
				group="pfb-tree-sections"
				handle=".pfb-drag-handle"
				item-key="id"
				:move="(e) => !!e.related?.querySelector('.pfb-drag-handle')"
				v-bind="DRAG_OPTIONS"
				@start="setDragging(true)"
				@end="setDragging(false)"
			>
				<template #item="{ element: section }">
					<div class="pfb-tree-node">
						<div
							class="pfb-tree-row"
							@mouseenter="store.hovered_section.value = section"
							@mouseleave="store.hovered_section.value = null"
							:class="{
								'pfb-drag-handle': !zone_of(section),
								active: store.selected_sections.value.includes(section),
								'pfb-tree-hover': store.hovered_node.value === section,
							}"
							role="treeitem"
							tabindex="0"
							:aria-expanded="!is_collapsed(section)"
							:aria-selected="store.selected_sections.value.includes(section)"
							@click="select_section(section)"
							@keydown.enter.prevent="select_section(section)"
							@keydown.space.prevent="select_section(section)"
						>
							<button
								class="pfb-tree-chevron"
								:class="{ collapsed: is_collapsed(section) }"
								@click.stop="toggle_collapse(section)"
								v-html="frappe.utils.icon('chevron-down', 'sm')"
							></button>
							<span
								class="pfb-tree-icon"
								v-html="frappe.utils.icon('rectangle-horizontal', 'sm')"
							></span>
							<span class="pfb-tree-label">
								{{ section.label || zone_of(section) || __("Untitled section") }}
							</span>
						</div>
						<div v-if="!is_collapsed(section)" class="pfb-tree-children">
							<div
								v-for="(col, ci) in section.columns"
								:key="ci"
								class="pfb-tree-node"
							>
								<!-- a lone column isn't a real division of the section, so it
								     only earns a row once there's more than one -->
								<div
									v-if="section.columns.length > 1"
									class="pfb-tree-row"
									role="treeitem"
									tabindex="0"
									@click="select_section(section)"
									@keydown.enter.prevent="select_section(section)"
									@keydown.space.prevent="select_section(section)"
								>
									<button
										v-if="col.fields.length"
										class="pfb-tree-chevron"
										:class="{ collapsed: is_collapsed(col) }"
										@click.stop="toggle_collapse(col)"
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
								<draggable
									v-if="section.columns.length === 1 || !is_collapsed(col)"
									v-model="col.fields"
									class="pfb-tree-children pfb-tree-fields"
									:class="{
										'pfb-tree-fields--flush': section.columns.length === 1,
									}"
									group="pfb-tree-fields"
									item-key="id"
									:emptyInsertThreshold="20"
									v-bind="DRAG_OPTIONS"
									@start="setDragging(true)"
									@end="setDragging(false)"
									@add="(e) => select_dropped_layer_field(col, e)"
								>
									<template #item="{ element: field }">
										<div
											v-show="!field.remove"
											class="pfb-tree-row"
											:class="{
												active: store.selected_fields.value.includes(
													field
												),
												'pfb-tree-hover':
													store.hovered_node.value === field,
											}"
											@mouseenter="store.hovered_field.value = field"
											@mouseleave="store.hovered_field.value = null"
											role="treeitem"
											tabindex="0"
											:aria-selected="
												store.selected_fields.value.includes(field)
											"
											@click="select_field(field, section, $event)"
											@keydown.enter.prevent="
												select_field(field, section, $event)
											"
											@keydown.space.prevent="
												select_field(field, section, $event)
											"
										>
											<span class="pfb-tree-spacer"></span>
											<span
												class="pfb-tree-icon"
												v-html="frappe.utils.icon(field_icon(field), 'sm')"
											></span>
											<span class="pfb-tree-label">{{
												field_label(field)
											}}</span>
											<span
												v-if="field_broken(field)"
												class="pfb-tree-warn"
												:title="
													__(
														'Field \u201c{0}\u201d no longer exists on {1}',
														[field.fieldname, meta.name]
													)
												"
												v-html="frappe.utils.icon('triangle-alert', 'sm')"
											></span>
										</div>
									</template>
								</draggable>
							</div>
						</div>
					</div>
				</template>
			</draggable>
			<div v-if="layout && !layout.sections.length" class="pfb-empty">
				{{ __("No sections yet. Add sections to the canvas.") }}
			</div>
		</div>
	</div>
</template>

<script setup>
import draggable from "vuedraggable";
import {
	BLOCK_FIELDTYPES,
	DRAG_OPTIONS,
	clone_plain,
	freshen_field,
	get_table_columns,
	pluck,
	setDragging,
	FIELD_PLUCK_KEYS,
} from "../utils";
import BlockCard from "./BlockCard.vue";
import { useStore } from "../stores";
import { computed, onMounted, onUnmounted, nextTick, ref, watch, inject } from "vue";

// state
let search_text = ref("");
let search_input = ref(null);
let raw_templates = ref([]);

// ── tab definitions ───────────────────────────────────────
const TAB_STORE_KEY = "pfb_active_tab";
const tabs = computed(() => [
	{ id: "layers", label: __("Layers") },
	{ id: "fields", label: __("Fields") },
	{ id: "blocks", label: __("Blocks") },
	{ id: "library", label: __("Library") },
]);

// A stale tab id would render an empty sidebar, so fall back to the first tab
function restore_tab() {
	const saved = localStorage.getItem(TAB_STORE_KEY);
	return tabs.value.some((t) => t.id === saved) ? saved : "layers";
}
let activeTab = ref(restore_tab());

function focus_search() {
	activeTab.value = "fields";
	nextTick(() => search_input.value?.focus());
}

// store
let store = inject("$store");
let { meta, layout, print_format, letterhead } = useStore();

// ── blocks tab items ──────────────────────────────────────
const page_break_block = [
	{
		label: __("Page Break"),
		fieldname: "page_break",
		desc: __("Force a new page"),
	},
];

const draggable_blocks = computed(() => [
	...(print_format.value?.pdf_generator === "Typst"
		? [
				{
					label: __("Typst"),
					fieldname: "typst_block",
					fieldtype: "Typst",
					typst: "",
					custom: 1,
					icon: "code",
					desc: __("Raw Typst markup"),
				},
		  ]
		: [
				{
					label: __("Custom HTML"),
					fieldname: "custom_html",
					fieldtype: "HTML",
					html: "",
					custom: 1,
					icon: "code",
					desc: __("Raw HTML or Jinja template"),
				},
		  ]),
	{
		label: __("Spacer"),
		fieldname: "spacer",
		fieldtype: "Spacer",
		custom: 1,
		height: 10,
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
	{
		label: __("Text"),
		fieldname: "static_text",
		fieldtype: "Static Text",
		custom: 1,
		icon: "type",
		desc: __("Fixed text like a title or a note"),
		text: "",
	},
	{
		label: __("Linked Field"),
		fieldname: "linked_field",
		fieldtype: "Linked Field",
		custom: 1,
		icon: "link",
		desc: __("A value from a linked document"),
		link_path: "",
		show_label: "inline",
	},
	{
		label: __("Summary Table"),
		fieldname: "summary_table",
		fieldtype: "Summary Table",
		custom: 1,
		icon: "sigma",
		desc: __("Group child rows and total them"),
		source: "",
		group_by: "",
		show_totals: 1,
		columns: [],
	},
]);

function confirm_delete_snippet(name) {
	frappe.confirm(__("Delete the snippet '{0}'?", [name]), () => store.delete_snippet(name));
}

// ── helpers ────────────────────────────────────────────────
function clone_field(df) {
	let cloned = pluck(df, FIELD_PLUCK_KEYS);
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
	store.scroll_target.value = section;
	store.select_section(section);
}

function select_field(field, section, e) {
	const additive = !!(e && (e.metaKey || e.ctrlKey || e.shiftKey));
	if (!additive) store.scroll_target.value = field;
	store.select_field(field, additive);
}

function select_dropped_layer_field(column, e) {
	const field = column.fields[e.newIndex];
	if (field) store.select_field(field);
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

const FIELD_ICONS = {
	Table: "table",
	"Static Text": "type",
	"Linked Field": "link",
	"Summary Table": "sigma",
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

// the zones are sections too, so the tree lists them alongside the body ones —
// only their order is fixed, since a header can't become a body section
let tree_sections = computed({
	get: () => {
		// an empty header merges into the letterhead region on the canvas, so it
		// isn't listed as a section either — it reappears once it holds fields
		const header_has_fields = (layout.value.header?.columns || []).some((c) =>
			(c.fields || []).some((f) => !f.remove)
		);
		const header = letterhead.value && !header_has_fields ? null : layout.value.header;
		return [header, ...layout.value.sections, layout.value.footer].filter(Boolean);
	},
	set: (v) => (layout.value.sections = v.filter((s) => !zone_of(s))),
});

function zone_of(section) {
	if (section && section === layout.value?.header) return __("Header");
	if (section && section === layout.value?.footer) return __("Footer");
	return "";
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

function enter_tab(tab) {
	if (tab === "library") fetch_templates();
}

// the indicator is the moving bar under the active tab; espresso's tabs.css
// reads its offset and width from these two custom properties
let tablist = ref(null);
let indicator_style = ref({});
function move_indicator() {
	const tab = tablist.value?.querySelector('[data-state="active"]');
	if (!tab) return;
	indicator_style.value = {
		"--es-tabs-indicator-x": `${tab.offsetLeft}px`,
		"--es-tabs-indicator-w": `${tab.offsetWidth}px`,
	};
}

watch(activeTab, (tab) => {
	localStorage.setItem(TAB_STORE_KEY, tab);
	enter_tab(tab);
	nextTick(move_indicator);
});

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

// ── computed: misc ─────────────────────────────────────────
let new_template_link = computed(
	() => `/app/print-format-field-template/new?document_type=${meta.value?.name || ""}`
);

// ── lifecycle ──────────────────────────────────────────────
onMounted(() => {
	document.addEventListener("keydown", handle_slash_key);

	// the watcher only fires on change, so a restored tab needs its setup run here
	enter_tab(activeTab.value);
	nextTick(move_indicator);
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

/* the tab bar itself is styled by espresso/components/tabs.css; the sidebar is
   narrower than a page, so it takes a tighter rhythm than the default */
.es-tabs {
	flex-shrink: 0;
}

.es-tabs__list {
	gap: calc(var(--spacing) * 3);
	padding-inline: calc(var(--spacing) * 3);
}

.es-tabs__tab {
	padding-block: calc(var(--spacing) * 2);
	font-size: var(--text-sm);
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

.pfb-tree-row:hover,
.pfb-tree-row.pfb-tree-hover {
	outline: 1px solid var(--pfb-accent);
	outline-offset: -1px;
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

.pfb-tree-warn {
	display: inline-flex;
	flex-shrink: 0;
	color: var(--text-on-orange, #b95000);
}

.pfb-tree-children {
	margin-left: 18px;
}

.pfb-tree-fields {
	min-height: 8px;
}

/* single-column sections have no Column row, so their fields sit directly
   under the section instead of indenting past a row that isn't there */
.pfb-tree-fields--flush {
	margin-left: 0;
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
