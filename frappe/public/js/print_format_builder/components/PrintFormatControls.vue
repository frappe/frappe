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
				<span class="pfb-tab-icon" v-html="frappe.utils.icon(tab.icon, 'sm')"></span>
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
								v-html="frappe.utils.icon('drag', 'xs')"
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
				<a :href="new_template_link" target="_blank" class="btn btn-xs btn-secondary mt-2">
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
							<svg class="icon icon-xs text-muted pfb-plus-icon">
								<use href="#icon-plus"></use>
							</svg>
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
		<div v-else-if="activeTab === 'format'" class="pfb-tab-body">
			<div class="pfb-group-label">{{ __("Page margins (mm)") }}</div>
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

			<div class="pfb-group-label mt-3">{{ __("Font") }}</div>
			<div class="form-group">
				<label class="control-label">{{ __("Google Font") }}</label>
				<select class="form-control form-control-sm" v-model="print_format.font">
					<option v-for="font in google_fonts" :value="font">{{ font }}</option>
				</select>
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

			<div class="pfb-group-label mt-3">{{ __("Page number") }}</div>
			<div class="form-group">
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
import { get_table_columns, pluck } from "../utils";
import { useStore } from "../stores";
import { computed, onMounted, onUnmounted, nextTick, ref, watch, inject } from "vue";

// state
let search_text = ref("");
let google_fonts = ref([]);
let activeTab = ref("fields");
let search_input = ref(null);

function focus_search() {
	activeTab.value = "fields";
	nextTick(() => search_input.value?.focus());
}

// store
let store = inject("$store");
let { meta, print_format, layout } = useStore();

// ── tab definitions ───────────────────────────────────────
const tabs = computed(() => [
	{ id: "fields", label: __("Fields"), icon: "list" },
	{ id: "blocks", label: __("Blocks"), icon: "blocks" },
	{ id: "templates", label: __("Templates"), icon: "table" },
	{ id: "outline", label: __("Outline"), icon: "layout-list" },
	{ id: "format", label: __("Format"), icon: "settings" },
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
];

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
	]);
	if (cloned.custom) {
		cloned.fieldname += "_" + frappe.utils.get_random(8);
	}
	return cloned;
}

function add_to_layout(df) {
	const sections = layout.value?.sections;
	if (!sections || !sections.length) return;
	const last_section = sections.filter((s) => !s.remove).slice(-1)[0];
	if (!last_section) return;
	const last_column = last_section.columns.slice(-1)[0];
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
		if (frappe.model.no_value_type.includes(df.fieldtype)) continue;

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

// ── computed: templates tab ────────────────────────────────
let print_templates_list = computed(() => {
	const templates = print_format.value.__onload?.print_templates || [];
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
		if (!google_fonts.value.includes(print_format.value.font)) {
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
	flex-direction: column;
	align-items: center;
	gap: 2px;
	padding: 6px 2px 8px;
	border: none;
	background: transparent;
	border-radius: var(--border-radius) var(--border-radius) 0 0;
	color: var(--text-muted);
	cursor: pointer;
	transition: color 0.12s, background 0.12s;
	font-size: 10px;
	font-weight: 500;
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

.pfb-tab-icon {
	display: flex;
	align-items: center;
	line-height: 1;
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
	font-size: 10px;
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
	font-size: 10px;
	font-weight: 600;
	letter-spacing: 0.06em;
	color: var(--text-muted);
}

.pfb-fields-header-sep {
	margin: 0 4px;
	opacity: 0.5;
}

/* ── Group label ─────────────────────────────────────────── */
.pfb-group-label {
	font-size: 10px;
	font-weight: 600;
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
	font-size: 10px;
	color: var(--gray-500);
	background: var(--gray-100);
	border: 1px solid var(--gray-200);
	border-radius: var(--border-radius-sm);
	padding: 2px 6px;
	white-space: nowrap;
	flex-shrink: 0;
}

.pfb-plus-icon {
	opacity: 0;
	flex-shrink: 0;
	transition: opacity 0.1s;
}

.pfb-template-card:hover .pfb-plus-icon {
	opacity: 1;
}

/* ── Block card (Blocks tab) ─────────────────────────────── */
.pfb-block-card {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 8px 10px;
	border-radius: var(--border-radius);
	border: 1px solid var(--border-color);
	background: var(--gray-50);
	cursor: grab;
	margin-top: 6px;
}

.pfb-block-card:hover {
	background: var(--gray-100);
	border-color: var(--gray-500);
}

.pfb-block-card--click {
	cursor: pointer;
}

.pfb-block-icon {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	border-radius: var(--border-radius);
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
	font-size: 10px;
	margin-top: 1px;
}

/* ── Template card (Templates tab) ──────────────────────── */
.pfb-template-card {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 8px 10px;
	border-radius: var(--border-radius);
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
	border-radius: var(--border-radius);
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
	font-size: 10px;
	margin-top: 1px;
}

.pfb-templates-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	padding: 16px 0;
}

.pfb-templates-hint {
	font-size: 11px;
	line-height: 1.5;
	margin-top: 6px;
}

.pfb-manage-link {
	font-size: 10px;
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
	border-radius: var(--border-radius);
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
	font-size: 10px;
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
.pfb-margin-grid {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 6px;
	margin-bottom: 6px;
}

.pfb-margin-cell {
	display: flex;
	flex-direction: column;
	gap: 2px;
}

.pfb-margin-label {
	font-size: 10px;
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
