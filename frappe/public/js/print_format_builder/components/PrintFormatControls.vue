<template>
	<div class="pfb-sidebar">
		<!-- Tab bar -->
		<div class="pfb-tabbar">
			<button
				v-for="tab in tabs"
				:key="tab.id"
				class="pfb-tab"
				:class="{ active: activeTab === tab.id }"
				:title="tab.label"
				@click="activeTab = tab.id"
			>
				<span class="pfb-tab-label">{{ tab.label }}</span>
			</button>
		</div>

		<!-- ── Fields ────────────────────────────────────────── -->
		<div v-if="activeTab === 'fields'" class="pfb-tab-body pfb-fields-tab">
			<!-- Search -->
			<div class="pfb-search-wrap">
				<svg class="icon icon-xs pfb-search-icon text-muted">
					<use href="#icon-search"></use>
				</svg>
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
				{{ __("No fields match your search.") }}
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

		<!-- ── Templates ─────────────────────────────────────── -->
		<div v-else-if="activeTab === 'templates'" class="pfb-tab-body">
			<div v-if="!print_templates_list.length" class="pfb-templates-empty">
				<div class="pfb-empty">
					{{ __("No field templates for this document type.") }}
				</div>
				<p class="pfb-templates-hint text-muted">
					{{
						__(
							"Field templates let you render specific fields with custom Jinja/HTML, e.g. a custom items table layout."
						)
					}}
				</p>
				<a :href="new_template_link" target="_blank" class="es-button mt-2" data-size="xs">
					{{ __("Create Field Template") }}
				</a>
			</div>

			<template v-else>
				<div class="pfb-group-label">
					{{ __("Field Templates") }}
					<a
						:href="'/app/print-format-field-template'"
						target="_blank"
						class="pfb-manage-link text-muted"
					>
						{{ __("Manage") }}
					</a>
				</div>
				<draggable
					:list="print_templates_list"
					:group="{ name: 'fields', pull: 'clone', put: false }"
					:sort="false"
					:clone="clone_field"
					item-key="fieldname"
				>
					<template #item="{ element }">
						<div
							class="pfb-template-card"
							:title="element.fieldname"
							@click="add_to_layout(element)"
						>
							<div class="pfb-template-thumb">
								<svg class="icon icon-sm text-muted">
									<use href="#icon-table"></use>
								</svg>
							</div>
							<div class="pfb-template-info">
								<div class="pfb-template-name">{{ element.display_label }}</div>
								<div class="pfb-template-field text-muted">
									{{ element.field_label || __("Custom block") }}
								</div>
							</div>
						</div>
					</template>
				</draggable>
				<div class="pfb-templates-hint text-muted mt-2">
					{{ __("Drag or click to add a field template to the last section.") }}
				</div>
			</template>
		</div>

		<!-- ── Outline ────────────────────────────────────────── -->
		<div v-else-if="activeTab === 'outline'" class="pfb-tab-body">
			<div v-if="!visible_sections.length" class="pfb-empty">
				{{ __("No sections yet. Add sections to the canvas.") }}
			</div>
			<div
				v-for="(section, i) in visible_sections"
				:key="i"
				class="pfb-outline-item"
				:class="{ active: store.selected_section.value === section }"
				@click="select_section(section)"
			>
				<span class="pfb-outline-idx text-muted">{{ i + 1 }}</span>
				<span class="pfb-outline-label">
					{{ section.label || __("Untitled section") }}
				</span>
			</div>
		</div>

		<!-- ── Format ─────────────────────────────────────────── -->
		<div v-else-if="activeTab === 'format'" class="pfb-tab-body pfb-format-tab">
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
import { get_table_columns, pluck } from "../utils";
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
	{ id: "templates", label: __("Templates") },
	{ id: "outline", label: __("Outline") },
	{ id: "format", label: __("Format") },
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

// The Format tab is v-if, so its DOM is recreated on each visit — (re)mount the
// Frappe color controls into the fresh host divs when the tab is shown.
function mount_color_controls() {
	for (const c of color_settings) {
		const host = color_hosts.value[c.fieldname];
		if (!host) continue;
		host.innerHTML = "";
		const control = frappe.ui.form.make_control({
			parent: host,
			df: {
				fieldtype: "Color",
				fieldname: c.fieldname,
				placeholder: c.label,
				change() {
					const value = control.get_value() || null;
					if ((print_format.value[c.fieldname] ?? null) !== value) {
						print_format.value[c.fieldname] = value;
					}
				},
			},
			render_input: true,
			only_input: true,
		});
		control.set_value(print_format.value[c.fieldname] || "");
	}
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
	store.selected_section.value = section;
	store.selected_field.value = null;
	store.selected_letterhead.value = false;
	store.selected_lh_footer.value = false;
}

function clone_as_section() {
	return { label: "", columns: [{ label: "", fields: [] }], page_break: true };
}

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

// ── templates tab ─────────────────────────────────────────
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
	if (tab === "templates") fetch_templates();
	if (tab === "format") nextTick(mount_color_controls);
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

watch(print_format, () => (store.dirty.value = true), { deep: true });
</script>

<style scoped>
/* ── Sidebar shell ───────────────────────────────────────── */
.pfb-sidebar {
	width: 260px;
	flex-shrink: 0;
	height: calc(100vh - 95px);
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
	text-transform: uppercase;
	letter-spacing: 0.06em;
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
	background: var(--gray-100);
	border: 1px solid var(--gray-200);
	border-radius: var(--radius);
	padding: 2px 6px;
	white-space: nowrap;
	flex-shrink: 0;
}

/* ── Block card (Blocks tab) ─────────────────────────────── */
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
}

.pfb-block-name {
	font-size: var(--text-sm);
	font-weight: 500;
}

.pfb-block-desc {
	font-size: var(--text-tiny);
	margin-top: 1px;
}

/* ── Template card (Templates tab) ──────────────────────── */
.pfb-template-card {
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

.pfb-template-card:hover {
	background: var(--gray-100);
	border-color: var(--gray-500);
}

.pfb-template-thumb {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 32px;
	height: 32px;
	border-radius: var(--radius);
	background: var(--gray-200);
	flex-shrink: 0;
}

.pfb-template-info {
	flex: 1;
	min-width: 0;
}

.pfb-template-name {
	font-size: var(--text-sm);
	font-weight: 500;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.pfb-template-field {
	font-size: var(--text-tiny);
	margin-top: 1px;
}

.pfb-templates-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	padding: 16px 0;
}

.pfb-templates-hint {
	font-size: var(--text-tiny);
	line-height: 1.5;
	margin-top: 6px;
}

.pfb-manage-link {
	font-size: var(--text-tiny);
	font-weight: 400;
	text-transform: none;
	letter-spacing: 0;
}

/* ── Outline tab ─────────────────────────────────────────── */
.pfb-outline-item {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 6px 8px;
	border-radius: var(--radius);
	cursor: pointer;
	margin-top: 2px;
	font-size: var(--text-sm);
}

.pfb-outline-item:hover {
	background: var(--gray-100);
}

.pfb-outline-item.active {
	background: var(--blue-50);
	color: var(--primary);
	font-weight: 500;
}

.pfb-outline-idx {
	font-size: var(--text-tiny);
	font-variant-numeric: tabular-nums;
	min-width: 18px;
	text-align: right;
}

.pfb-outline-label {
	flex: 1;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

/* ── Format tab ──────────────────────────────────────────── */
.pfb-format-tab .form-group {
	margin-bottom: 10px;
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
