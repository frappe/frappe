<template>
	<div class="pfb-inspector" @click.stop>
		<!-- Header -->
		<div class="pfb-inspector-head">
			<div class="pfb-inspector-eyebrow">{{ __("Inspector") }}</div>
			<div class="pfb-inspector-title">
				<span class="pfb-inspector-kind">{{ inspector_kind }}</span>
				<span
					class="pfb-inspector-name"
					v-if="
						selected_field ||
						selected_section ||
						selected_letterhead ||
						selected_lh_footer
					"
				>
					{{ inspector_subtitle }}
				</span>
			</div>
		</div>

		<!-- Breadcrumb: navigate up to parent section when a field is selected -->
		<div v-if="selected_field && parent_section" class="pfb-breadcrumb">
			<button
				class="pfb-breadcrumb-btn"
				@click="select_parent_section"
				:title="__('Select parent section (Esc)')"
			>
				<span v-html="frappe.utils.icon('arrow-up', 'xs')"></span>
				<span class="pfb-breadcrumb-label">{{ __("Section:") }}</span>
				<span class="pfb-breadcrumb-name">{{
					parent_section.label || __("Untitled")
				}}</span>
			</button>
		</div>

		<!-- Letter Head notice — shown whenever the letterhead is selected -->
		<div v-if="selected_letterhead || selected_lh_footer" class="pfb-lh-notice">
			<span v-html="frappe.utils.icon('alert-circle', 'xs')"></span>
			{{ __("Edits here update the Letter Head document directly.") }}
		</div>

		<!-- Empty state -->
		<div
			v-if="
				!selected_field && !selected_section && !selected_letterhead && !selected_lh_footer
			"
			class="pfb-inspector-empty"
		>
			<svg class="icon icon-md text-muted" style="margin-bottom: 8px">
				<use href="#icon-cursor-text"></use>
			</svg>
			<p class="text-muted">{{ __("Click a field to edit its properties") }}</p>
		</div>

		<!-- ── Letter Head Footer inspector ──────────────────────── -->
		<template v-else-if="selected_lh_footer">
			<LetterHeadZoneInspector zone="footer" />
		</template>

		<!-- ── Letter Head inspector ──────────────────────────────── -->
		<template v-else-if="selected_letterhead">
			<LetterHeadZoneInspector zone="header" />
		</template>

		<!-- ── Table field inspector ───────────────────────────────── -->
		<template v-else-if="selected_field && is_table_field">
			<div class="pfb-insp-tabs">
				<button
					v-for="tab in field_tabs"
					:key="tab.id"
					class="pfb-insp-tab"
					:class="{ active: active_tab === tab.id }"
					@click="active_tab = tab.id"
				>
					{{ tab.label }}
				</button>
			</div>

			<div v-if="active_tab === 'properties'" class="pfb-insp-body">
				<!-- TABLE section -->
				<div class="pfb-insp-section">
					<div class="pfb-insp-section-head" @click="toggle('t_table')">
						<span class="pfb-insp-section-label">{{ __("Table") }}</span>
						<span
							class="pfb-insp-chevron"
							:class="{ collapsed: !open.t_table }"
							v-html="frappe.utils.icon('chevron-down', 'xs')"
						></span>
					</div>
					<div v-show="open.t_table" class="pfb-insp-section-body">
						<!-- Source -->
						<div class="pfb-insp-row">
							<span class="pfb-insp-label">{{ __("Source") }}</span>
							<div class="pfb-source-display">
								<span class="pfb-source-name">{{
									selected_field.label || selected_field.fieldname
								}}</span>
								<span class="pfb-type-badge">{{ __("Table") }}</span>
							</div>
						</div>
						<!-- Title -->
						<div class="pfb-insp-row pfb-insp-row--col">
							<span class="pfb-insp-label">{{ __("Title") }}</span>
							<input
								class="pfb-insp-input"
								type="text"
								:placeholder="__('Table title')"
								v-model="selected_field.label"
							/>
						</div>
						<!-- Style -->
						<div class="pfb-insp-row">
							<span class="pfb-insp-label">{{ __("Style") }}</span>
							<div class="pfb-seg">
								<button
									v-for="s in table_style_opts"
									:key="s.value"
									:class="{ active: table_style === s.value }"
									@click="selected_field.table_style = s.value"
								>
									{{ s.label }}
								</button>
							</div>
						</div>
						<!-- Bordered -->
						<div class="pfb-insp-row">
							<span class="pfb-insp-label">{{ __("Bordered") }}</span>
							<div class="pfb-seg">
								<button
									:class="{ active: table_bordered !== false }"
									@click="selected_field.table_bordered = true"
								>
									{{ __("Yes") }}
								</button>
								<button
									:class="{ active: table_bordered === false }"
									@click="selected_field.table_bordered = false"
								>
									{{ __("No") }}
								</button>
							</div>
						</div>
						<!-- Header -->
						<div class="pfb-insp-row">
							<span class="pfb-insp-label">{{ __("Header") }}</span>
							<div class="pfb-seg">
								<button
									:class="{ active: table_header !== 'plain' }"
									@click="selected_field.table_header = 'styled'"
								>
									{{ __("Styled") }}
								</button>
								<button
									:class="{ active: table_header === 'plain' }"
									@click="selected_field.table_header = 'plain'"
								>
									{{ __("Plain") }}
								</button>
							</div>
						</div>
					</div>
				</div>

				<!-- COLUMNS section -->
				<div class="pfb-insp-section">
					<div class="pfb-insp-section-head" @click="toggle('t_columns')">
						<span class="pfb-insp-section-label">{{ __("Columns") }}</span>
						<div style="display: flex; align-items: center; gap: 8px">
							<span class="pfb-insp-col-count text-muted">{{
								(selected_field.table_columns || []).length
							}}</span>
							<span
								class="pfb-insp-chevron"
								:class="{ collapsed: !open.t_columns }"
								v-html="frappe.utils.icon('chevron-down', 'xs')"
							></span>
						</div>
					</div>
					<div v-show="open.t_columns">
						<!-- Column list -->
						<draggable
							:list="selected_field.table_columns"
							handle=".pfb-col-drag"
							:animation="150"
							item-key="fieldname"
							class="pfb-col-list"
						>
							<template #item="{ element: col, index: ci }">
								<div class="pfb-col-row">
									<span
										class="pfb-col-drag"
										v-html="frappe.utils.icon('drag', 'xs')"
									></span>
									<span class="pfb-col-label" :title="col.fieldname">{{
										col.label || col.fieldname
									}}</span>
									<input
										class="pfb-col-width-input"
										type="number"
										min="5"
										max="100"
										v-model.number="col.width"
										@blur="clamp_width(col)"
										:title="__('Width %')"
									/>
									<span class="pfb-col-width-unit">%</span>
									<button
										class="pfb-col-remove"
										@click="remove_table_column(ci)"
										:title="__('Remove column')"
										v-html="frappe.utils.icon('x', 'xs')"
									></button>
								</div>
							</template>
						</draggable>
						<!-- Add column picker -->
						<div class="pfb-col-add-row" v-if="available_columns.length">
							<select class="pfb-col-add-select" v-model="add_col_select">
								<option value="" disabled>{{ __("+ Add column...") }}</option>
								<option
									v-for="col in available_columns"
									:key="col.fieldname"
									:value="col.fieldname"
								>
									{{ col.label || col.fieldname }}
								</option>
							</select>
							<button
								class="pfb-col-add-btn"
								@click="add_table_column"
								:disabled="!add_col_select"
								v-html="frappe.utils.icon('plus', 'xs')"
							></button>
						</div>
						<div
							v-else
							class="pfb-insp-hint text-muted"
							style="padding: 8px 14px 10px"
						>
							{{ __("All available columns added.") }}
						</div>
					</div>
				</div>

				<!-- BEHAVIOR section -->
				<div class="pfb-insp-section">
					<div class="pfb-insp-section-head" @click="toggle('t_behavior')">
						<span class="pfb-insp-section-label">{{ __("Behavior") }}</span>
						<span
							class="pfb-insp-chevron"
							:class="{ collapsed: !open.t_behavior }"
							v-html="frappe.utils.icon('chevron-down', 'xs')"
						></span>
					</div>
					<div v-show="open.t_behavior" class="pfb-insp-section-body">
						<p class="pfb-insp-hint text-muted">{{ __("Coming soon.") }}</p>
					</div>
				</div>

				<div class="pfb-insp-actions">
					<button class="btn btn-xs btn-danger-subtle" @click="remove_field">
						<span v-html="frappe.utils.icon('x', 'xs')"></span>
						{{ __("Remove table") }}
					</button>
				</div>
			</div>

			<div v-else class="pfb-insp-body pfb-insp-placeholder">
				<p class="text-muted">{{ __("Coming soon.") }}</p>
			</div>
		</template>

		<!-- ── Field inspector ─────────────────────────────────── -->
		<template v-else-if="selected_field">
			<div class="pfb-insp-tabs">
				<button
					v-for="tab in field_tabs"
					:key="tab.id"
					class="pfb-insp-tab"
					:class="{ active: active_tab === tab.id }"
					@click="active_tab = tab.id"
				>
					{{ tab.label }}
				</button>
			</div>

			<div v-if="active_tab === 'properties'" class="pfb-insp-body">
				<div class="pfb-insp-section">
					<div class="pfb-insp-section-head" @click="toggle('f_field')">
						<span class="pfb-insp-section-label">{{ __("Field") }}</span>
						<span
							class="pfb-insp-chevron"
							:class="{ collapsed: !open.f_field }"
							v-html="frappe.utils.icon('chevron-down', 'xs')"
						></span>
					</div>
					<div v-show="open.f_field" class="pfb-insp-section-body">
						<div class="pfb-insp-row">
							<span class="pfb-insp-label">{{ __("Source") }}</span>
							<div class="pfb-source-display">
								<span class="pfb-source-name">{{
									selected_field.label || selected_field.fieldname
								}}</span>
								<span class="pfb-type-badge">{{ short_fieldtype }}</span>
							</div>
						</div>
						<template v-if="is_html_field">
							<div
								class="pfb-html-preview"
								v-if="selected_field.html"
								v-html="selected_field.html"
							></div>
							<div v-else class="pfb-insp-hint text-muted">
								{{ __("No HTML content yet.") }}
							</div>
							<button
								class="btn btn-xs btn-default pfb-lh-edit-btn"
								@click="edit_html_field"
							>
								<span v-html="frappe.utils.icon('edit', 'xs')"></span>
								{{ __("Edit HTML") }}
							</button>
						</template>
						<template v-else>
							<div class="pfb-insp-row pfb-insp-row--col">
								<span class="pfb-insp-label">{{ __("Label") }}</span>
								<input
									class="pfb-insp-input"
									type="text"
									:placeholder="__('Field label')"
									v-model="selected_field.label"
								/>
							</div>
							<div class="pfb-insp-row">
								<span class="pfb-insp-label">{{ __("Show label") }}</span>
								<div class="pfb-seg">
									<button
										v-for="opt in show_label_opts"
										:key="opt.value"
										:class="{ active: current_show_label === opt.value }"
										@click="selected_field.show_label = opt.value"
									>
										{{ opt.label }}
									</button>
								</div>
							</div>
							<div class="pfb-insp-row">
								<span class="pfb-insp-label">{{ __("Align") }}</span>
								<div class="pfb-seg">
									<button
										v-for="opt in align_opts"
										:key="opt.value"
										:class="{ active: current_align === opt.value }"
										:title="opt.title"
										@click="selected_field.align = opt.value"
										v-html="opt.icon"
									></button>
								</div>
							</div>
						</template>
					</div>
				</div>

				<div class="pfb-insp-section">
					<div class="pfb-insp-section-head" @click="toggle('f_format')">
						<span class="pfb-insp-section-label">{{ __("Format") }}</span>
						<span
							class="pfb-insp-chevron"
							:class="{ collapsed: !open.f_format }"
							v-html="frappe.utils.icon('chevron-down', 'xs')"
						></span>
					</div>
					<div v-show="open.f_format" class="pfb-insp-section-body">
						<p class="pfb-insp-hint text-muted">
							{{ __("Additional formatting options coming soon.") }}
						</p>
					</div>
				</div>

				<div class="pfb-insp-section">
					<div class="pfb-insp-section-head" @click="toggle('f_visibility')">
						<span class="pfb-insp-section-label">{{ __("Visibility") }}</span>
						<span
							class="pfb-insp-chevron"
							:class="{ collapsed: !open.f_visibility }"
							v-html="frappe.utils.icon('chevron-down', 'xs')"
						></span>
					</div>
					<div v-show="open.f_visibility" class="pfb-insp-section-body">
						<p class="pfb-insp-hint text-muted">
							{{ __("Conditional visibility coming soon.") }}
						</p>
					</div>
				</div>

				<div class="pfb-insp-actions">
					<button class="btn btn-xs btn-danger-subtle" @click="remove_field">
						<span v-html="frappe.utils.icon('x', 'xs')"></span>
						{{ __("Remove field") }}
					</button>
				</div>
			</div>

			<div v-else class="pfb-insp-body pfb-insp-placeholder">
				<p class="text-muted">{{ __("Coming soon.") }}</p>
			</div>
		</template>

		<!-- ── Section inspector ───────────────────────────────── -->
		<template v-else-if="selected_section">
			<div class="pfb-insp-tabs">
				<button
					v-for="tab in section_tabs"
					:key="tab.id"
					class="pfb-insp-tab"
					:class="{ active: active_tab === tab.id }"
					@click="active_tab = tab.id"
				>
					{{ tab.label }}
				</button>
			</div>

			<div v-if="active_tab === 'properties'" class="pfb-insp-body">
				<!-- SECTION properties -->
				<div class="pfb-insp-section">
					<div class="pfb-insp-section-head" @click="toggle('s_section')">
						<span class="pfb-insp-section-label">{{ __("Section") }}</span>
						<span
							class="pfb-insp-chevron"
							:class="{ collapsed: !open.s_section }"
							v-html="frappe.utils.icon('chevron-down', 'xs')"
						></span>
					</div>
					<div v-show="open.s_section" class="pfb-insp-section-body">
						<!-- Title -->
						<div class="pfb-insp-row pfb-insp-row--col">
							<span class="pfb-insp-label">{{ __("Title") }}</span>
							<input
								class="pfb-insp-input"
								type="text"
								:placeholder="__('Untitled section')"
								v-model="selected_section.label"
							/>
						</div>

						<!-- Show title -->
						<div class="pfb-insp-row">
							<span class="pfb-insp-label">{{ __("Show title") }}</span>
							<div class="pfb-seg">
								<button
									:class="{ active: section_show_label !== 'hide' }"
									@click="selected_section.show_label = 'show'"
								>
									{{ __("Yes") }}
								</button>
								<button
									:class="{ active: section_show_label === 'hide' }"
									@click="selected_section.show_label = 'hide'"
								>
									{{ __("No") }}
								</button>
							</div>
						</div>

						<!-- Columns -->
						<div class="pfb-insp-row">
							<span class="pfb-insp-label">{{ __("Columns") }}</span>
							<div class="pfb-seg">
								<button
									v-for="n in [1, 2, 3, 4]"
									:key="n"
									:class="{ active: selected_section.columns.length === n }"
									@click="set_columns(n)"
								>
									{{ n }}
								</button>
							</div>
						</div>

						<!-- Orientation -->
						<div class="pfb-insp-row">
							<span class="pfb-insp-label">{{ __("Label side") }}</span>
							<div class="pfb-seg">
								<button
									:class="{ active: section_orientation !== 'left-right' }"
									@click="selected_section.field_orientation = ''"
								>
									{{ __("Top") }}
								</button>
								<button
									:class="{ active: section_orientation === 'left-right' }"
									@click="selected_section.field_orientation = 'left-right'"
								>
									{{ __("Left") }}
								</button>
							</div>
						</div>

						<!-- Gap -->
						<div class="pfb-insp-row">
							<span class="pfb-insp-label">{{ __("Gap") }}</span>
							<div class="pfb-stepper">
								<button @click="adjust_gap(-4)">−</button>
								<input
									class="pfb-stepper-input"
									type="number"
									min="0"
									:value="section_gap"
									@change="
										(e) =>
											(selected_section.gap = Math.max(
												0,
												parseInt(e.target.value) || 0
											))
									"
								/>
								<span class="pfb-stepper-unit">px</span>
								<button @click="adjust_gap(4)">+</button>
							</div>
						</div>

						<!-- Label case -->
						<div class="pfb-insp-row">
							<span class="pfb-insp-label">{{ __("Label case") }}</span>
							<div class="pfb-seg">
								<button
									:class="{ active: section_label_case !== 'uppercase' }"
									@click="selected_section.label_case = 'normal'"
								>
									{{ __("Normal") }}
								</button>
								<button
									:class="{ active: section_label_case === 'uppercase' }"
									@click="selected_section.label_case = 'uppercase'"
								>
									{{ __("UPPER") }}
								</button>
							</div>
						</div>
					</div>
				</div>

				<!-- VISIBILITY -->
				<div class="pfb-insp-section">
					<div class="pfb-insp-section-head" @click="toggle('s_visibility')">
						<span class="pfb-insp-section-label">{{ __("Visibility") }}</span>
						<span
							class="pfb-insp-chevron"
							:class="{ collapsed: !open.s_visibility }"
							v-html="frappe.utils.icon('chevron-down', 'xs')"
						></span>
					</div>
					<div v-show="open.s_visibility" class="pfb-insp-section-body">
						<p class="pfb-insp-hint text-muted">
							{{ __("Conditional visibility coming soon.") }}
						</p>
					</div>
				</div>

				<div class="pfb-insp-actions">
					<button
						class="btn btn-xs btn-danger-subtle"
						@click="
							selected_section.remove = true;
							store.selected_section.value = null;
						"
					>
						<span v-html="frappe.utils.icon('x', 'xs')"></span>
						{{ __("Remove section") }}
					</button>
				</div>
			</div>

			<!-- ── Style tab ───────────────────────────────────────── -->
			<div v-else-if="active_tab === 'style'" class="pfb-insp-body">
				<!-- Background -->
				<div class="pfb-insp-section">
					<div class="pfb-insp-section-head" @click="toggle('s_bg')">
						<span class="pfb-insp-section-label">{{ __("Background") }}</span>
						<span
							class="pfb-insp-chevron"
							:class="{ collapsed: !open.s_bg }"
							v-html="frappe.utils.icon('chevron-down', 'xs')"
						></span>
					</div>
					<div v-show="open.s_bg" class="pfb-insp-section-body">
						<div class="pfb-color-swatches">
							<button
								v-for="swatch in bg_swatches"
								:key="swatch.value"
								class="pfb-swatch"
								:class="{ active: section_bg === swatch.value }"
								:title="swatch.label"
								:style="swatch.style"
								@click="selected_section.background = swatch.value"
							></button>
						</div>
					</div>
				</div>

				<!-- Padding -->
				<div class="pfb-insp-section">
					<div class="pfb-insp-section-head" @click="toggle('s_padding')">
						<span class="pfb-insp-section-label">{{ __("Padding") }}</span>
						<span
							class="pfb-insp-chevron"
							:class="{ collapsed: !open.s_padding }"
							v-html="frappe.utils.icon('chevron-down', 'xs')"
						></span>
					</div>
					<div v-show="open.s_padding" class="pfb-insp-section-body">
						<div class="pfb-padding-grid">
							<div
								v-for="side in ['top', 'right', 'bottom', 'left']"
								:key="side"
								class="pfb-padding-cell"
							>
								<div class="pfb-padding-label">
									{{ __(side[0].toUpperCase() + side.slice(1)) }}
								</div>
								<div class="pfb-stepper pfb-stepper--sm">
									<button @click="adjust_padding(side, -4)">−</button>
									<input
										class="pfb-stepper-input"
										type="number"
										min="0"
										:value="section_padding[side]"
										@change="
											(e) => set_padding(side, parseInt(e.target.value) || 0)
										"
									/>
									<button @click="adjust_padding(side, 4)">+</button>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>

			<div v-else class="pfb-insp-body pfb-insp-placeholder">
				<p class="text-muted">{{ __("Coming soon.") }}</p>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue";
import draggable from "vuedraggable";
import { useStore } from "../../stores";
import LetterHeadZoneInspector from "./LetterHeadZoneInspector.vue";

let store = inject("$store");
let { letterhead, layout } = useStore();

let selected_field = computed(() => store.selected_field.value);
let selected_section = computed(() => store.selected_section.value);
let selected_letterhead = computed(() => store.selected_letterhead.value);
let selected_lh_footer = computed(() => store.selected_lh_footer.value);

let active_tab = ref("properties");

const field_tabs = [
	{ id: "properties", label: __("Properties") },
	{ id: "style", label: __("Style") },
	{ id: "logic", label: __("Logic") },
];
const section_tabs = [
	{ id: "properties", label: __("Properties") },
	{ id: "style", label: __("Style") },
	{ id: "logic", label: __("Logic") },
];

const open = ref({
	f_field: true,
	f_format: false,
	f_visibility: false,
	s_section: true,
	s_bg: true,
	s_padding: true,
	s_visibility: false,
	t_table: true,
	t_columns: true,
	t_behavior: false,
});

function toggle(key) {
	open.value[key] = !open.value[key];
}

// ── Inspector header ───────────────────────────────────────
let is_table_field = computed(() => selected_field.value?.fieldtype === "Table");
let is_html_field = computed(() => selected_field.value?.fieldtype === "HTML");

let inspector_kind = computed(() => {
	if (selected_lh_footer.value) return __("Letter Head");
	if (selected_letterhead.value) return __("Letter Head");
	if (selected_field.value) {
		if (selected_field.value.fieldtype === "Table") return __("Table");
		return __("Field");
	}
	if (selected_section.value) return __("Section");
	return __("Canvas");
});

let inspector_subtitle = computed(() => {
	if (selected_lh_footer.value) return __("Footer");
	if (selected_letterhead.value) return letterhead.value?.name || "";
	if (selected_field.value) return selected_field.value.label || selected_field.value.fieldname;
	if (selected_section.value) return selected_section.value.label || __("Untitled section");
	return "";
});

// ── Breadcrumb: parent section of the selected field ──────
let parent_section = computed(() => {
	if (!selected_field.value || !layout.value) return null;
	const all_sections = [
		layout.value.header,
		...(layout.value.sections || []),
		layout.value.footer,
	].filter(Boolean);
	for (const section of all_sections) {
		for (const column of section.columns || []) {
			if (column.fields?.includes(selected_field.value)) return section;
		}
	}
	return null;
});

function select_parent_section() {
	if (parent_section.value) {
		store.selected_section.value = parent_section.value;
		store.selected_field.value = null;
	}
}

// ── Field helpers ──────────────────────────────────────────
let short_fieldtype = computed(() => {
	if (!selected_field.value) return "";
	const map = {
		Data: "Data",
		Currency: "Currency",
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
		HTML: "HTML",
		Spacer: "Spacer",
		Divider: "Divider",
		"Field Template": "Template",
	};
	return map[selected_field.value.fieldtype] || selected_field.value.fieldtype || "";
});

let current_show_label = computed(() => selected_field.value?.show_label ?? "show");
let current_align = computed(() => selected_field.value?.align ?? "left");

const show_label_opts = [
	{ value: "show", label: __("Show") },
	{ value: "hide", label: __("Hide") },
	{ value: "inline", label: __("Inline") },
];

const align_icons = {
	left: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="12" viewBox="0 0 14 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="0" y1="1" x2="14" y2="1"/><line x1="0" y1="5" x2="9" y2="5"/><line x1="0" y1="9" x2="11" y2="9"/></svg>`,
	center: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="12" viewBox="0 0 14 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="0" y1="1" x2="14" y2="1"/><line x1="2.5" y1="5" x2="11.5" y2="5"/><line x1="1.5" y1="9" x2="12.5" y2="9"/></svg>`,
	right: `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="12" viewBox="0 0 14 12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="0" y1="1" x2="14" y2="1"/><line x1="5" y1="5" x2="14" y2="5"/><line x1="3" y1="9" x2="14" y2="9"/></svg>`,
};

const align_opts = [
	{ value: "left", title: __("Align left"), icon: align_icons.left },
	{ value: "center", title: __("Align center"), icon: align_icons.center },
	{ value: "right", title: __("Align right"), icon: align_icons.right },
];

function remove_field() {
	if (selected_field.value) {
		selected_field.value.remove = true;
		store.selected_field.value = null;
	}
}

function open_html_split_dialog({ title, initial_html, on_save }) {
	let d = new frappe.ui.Dialog({
		title,
		size: "extra-large",
		fields: [
			{
				fieldname: "split_layout",
				fieldtype: "HTML",
				options: `<div class="pfb-html-split">
					<div class="pfb-html-split-pane pfb-html-split-editor">
						<div class="pfb-html-split-label">${__("HTML")}</div>
						<div class="pfb-html-ctrl-host"></div>
					</div>
					<div class="pfb-html-split-divider"></div>
					<div class="pfb-html-split-pane pfb-html-split-preview">
						<div class="pfb-html-split-label">${__("Preview")}</div>
						<div class="pfb-html-preview-content"></div>
					</div>
				</div>`,
			},
		],
		primary_action_label: __("Save"),
		primary_action: () => {
			const val = d._html_ctrl?.get_value?.() ?? "";
			on_save(frappe.dom.remove_script_and_style(val));
			d.hide();
		},
	});
	d.show();

	setTimeout(() => {
		const host = d.$wrapper.find(".pfb-html-ctrl-host")[0];
		const preview = d.$wrapper.find(".pfb-html-preview-content")[0];
		if (!host) return;

		const ctrl = frappe.ui.form.make_control({
			parent: host,
			df: {
				fieldtype: "Code",
				fieldname: "html_code",
				options: "HTML",
				show_label: false,
			},
			render_input: true,
		});
		ctrl.set_value(initial_html || "");
		d._html_ctrl = ctrl;

		// initial preview
		if (preview) preview.innerHTML = initial_html || "";

		// real-time preview via CodeMirror change event
		setTimeout(() => {
			if (ctrl.editor) {
				ctrl.editor.on(
					"change",
					frappe.utils.debounce(() => {
						if (preview) preview.innerHTML = ctrl.editor.getValue();
					}, 150)
				);
				ctrl.editor.refresh();
			}
		}, 300);
	}, 200);
}

function edit_html_field() {
	open_html_split_dialog({
		title: __("Edit HTML"),
		initial_html: selected_field.value?.html || "",
		on_save: (html) => {
			selected_field.value.html = html;
		},
	});
}

// ── Table helpers ──────────────────────────────────────────
let table_style = computed(() => selected_field.value?.table_style ?? "lined");
let table_bordered = computed(() => selected_field.value?.table_bordered ?? true);
let table_header = computed(() => selected_field.value?.table_header ?? "styled");

const table_style_opts = [
	{ value: "lined", label: __("Lined") },
	{ value: "striped", label: __("Striped") },
	{ value: "plain", label: __("Plain") },
];
let available_columns = computed(() => {
	if (!selected_field.value?.options) return [];
	const meta = frappe.get_meta(selected_field.value.options);
	if (!meta) return [];
	const existing = new Set((selected_field.value.table_columns || []).map((c) => c.fieldname));
	const standard = [{ label: __("Sr No."), fieldname: "idx", fieldtype: "Data" }];
	return standard
		.concat(
			meta.fields.filter(
				(f) => !frappe.model.no_value_type.includes(f.fieldtype) && f.fieldname !== "name"
			)
		)
		.filter((f) => !existing.has(f.fieldname));
});

let add_col_select = ref("");

function add_table_column() {
	if (!add_col_select.value) return;
	const fieldname = add_col_select.value;
	const meta = frappe.get_meta(selected_field.value.options);
	let col;
	if (fieldname === "idx") {
		col = { label: __("Sr No."), fieldname: "idx", fieldtype: "Data", width: 10 };
	} else {
		const df = meta?.fields.find((f) => f.fieldname === fieldname);
		if (!df) return;
		col = {
			label: df.label,
			fieldname: df.fieldname,
			fieldtype: df.fieldtype,
			options: df.options,
			width: 10,
		};
	}
	if (!selected_field.value.table_columns) selected_field.value.table_columns = [];
	selected_field.value.table_columns.push(col);
	add_col_select.value = "";
	// trigger reactivity
	selected_field.value.table_columns = [...selected_field.value.table_columns];
}

function remove_table_column(idx) {
	selected_field.value.table_columns.splice(idx, 1);
	selected_field.value.table_columns = [...selected_field.value.table_columns];
}

function clamp_width(col) {
	col.width = Math.max(5, Math.min(100, parseInt(col.width) || 10));
}

// ── Section helpers ────────────────────────────────────────
let section_show_label = computed(() => selected_section.value?.show_label ?? "show");
let section_orientation = computed(() => selected_section.value?.field_orientation ?? "");
let section_gap = computed(() => selected_section.value?.gap ?? 20);
let section_label_case = computed(() => selected_section.value?.label_case ?? "normal");
let section_bg = computed(() => selected_section.value?.background ?? "");
let section_padding = computed(() => ({
	top: selected_section.value?.padding?.top ?? 0,
	right: selected_section.value?.padding?.right ?? 0,
	bottom: selected_section.value?.padding?.bottom ?? 0,
	left: selected_section.value?.padding?.left ?? 0,
}));

const bg_swatches = [
	{
		value: "",
		label: __("None"),
		style: "background: repeating-conic-gradient(#ccc 0% 25%, #fff 0% 50%) 0 0 / 10px 10px",
	},
	{ value: "#ffffff", label: __("White"), style: "background:#ffffff; border-color:#e5e7eb" },
	{ value: "#EFF6FF", label: __("Blue"), style: "background:#EFF6FF" },
	{ value: "#F0FDF4", label: __("Green"), style: "background:#F0FDF4" },
	{ value: "#FFF7ED", label: __("Orange"), style: "background:#FFF7ED" },
];

function set_columns(n) {
	if (!selected_section.value) return;
	const current = selected_section.value.columns.length;
	if (n === current) return;
	const all_fields = selected_section.value.columns.flatMap((col) => col.fields);
	const new_columns = Array.from({ length: n }, () => ({ label: "", fields: [] }));
	all_fields.forEach((field, i) => new_columns[i % n].fields.push(field));
	selected_section.value.columns = new_columns;
}

function adjust_gap(delta) {
	const current = selected_section.value?.gap ?? 20;
	selected_section.value.gap = Math.max(0, current + delta);
}

function adjust_padding(side, delta) {
	if (!selected_section.value.padding) {
		selected_section.value.padding = { top: 0, right: 0, bottom: 0, left: 0 };
	}
	const current = selected_section.value.padding[side] ?? 0;
	selected_section.value.padding[side] = Math.max(0, current + delta);
}

function set_padding(side, value) {
	if (!selected_section.value.padding) {
		selected_section.value.padding = { top: 0, right: 0, bottom: 0, left: 0 };
	}
	selected_section.value.padding[side] = Math.max(0, value);
}
</script>

<style scoped>
.pfb-inspector {
	width: 280px;
	flex-shrink: 0;
	height: calc(100vh - 95px);
	overflow-y: auto;
	border-left: 1px solid var(--border-color);
	background: var(--fg-color);
	display: flex;
	flex-direction: column;
}

/* ── Header ─────────────────────────────────────────────── */
.pfb-inspector-head {
	padding: 12px 14px 10px;
	border-bottom: 1px solid var(--border-color);
	flex-shrink: 0;
}

.pfb-inspector-eyebrow {
	font-size: 10px;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.08em;
	color: var(--text-muted);
	margin-bottom: 3px;
}

.pfb-inspector-title {
	display: flex;
	align-items: baseline;
	gap: 6px;
}

.pfb-inspector-kind {
	font-size: var(--text-lg);
	font-weight: 700;
}

.pfb-inspector-name {
	font-size: var(--text-base);
	color: var(--text-muted);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

/* ── Breadcrumb ──────────────────────────────────────────── */
.pfb-breadcrumb {
	padding: 4px 10px;
	border-bottom: 1px solid var(--border-color);
	background: var(--gray-50);
}

.pfb-breadcrumb-btn {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	padding: 2px 6px;
	border: none;
	background: transparent;
	cursor: pointer;
	border-radius: var(--border-radius-sm);
	color: var(--text-muted);
	font-size: var(--text-xs);
	transition: background 0.1s, color 0.1s;
	max-width: 100%;
}

.pfb-breadcrumb-btn:hover {
	background: var(--gray-100);
	color: var(--blue-500);
}

.pfb-breadcrumb-label {
	font-weight: 500;
	flex-shrink: 0;
}

.pfb-breadcrumb-name {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

/* ── Empty state ─────────────────────────────────────────── */
.pfb-inspector-empty {
	flex: 1;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 24px;
	text-align: center;
	font-size: var(--text-sm);
}

/* ── Tabs ────────────────────────────────────────────────── */
.pfb-insp-tabs {
	display: flex;
	padding: 8px 10px 0;
	gap: 2px;
	border-bottom: 1px solid var(--border-color);
	flex-shrink: 0;
	background: var(--gray-50);
}

.pfb-insp-tab {
	flex: 1;
	padding: 6px 4px 8px;
	font-size: var(--text-sm);
	font-weight: 500;
	border: none;
	background: transparent;
	color: var(--text-muted);
	cursor: pointer;
	border-radius: var(--border-radius) var(--border-radius) 0 0;
	position: relative;
	transition: color 0.12s;
}

.pfb-insp-tab:hover {
	color: var(--text-color);
}

.pfb-insp-tab.active {
	color: var(--text-color);
	font-weight: 600;
}

.pfb-insp-tab.active::after {
	content: "";
	position: absolute;
	bottom: 0;
	left: 0;
	right: 0;
	height: 2px;
	background: var(--gray-700);
	border-radius: 2px 2px 0 0;
}

/* ── Body ────────────────────────────────────────────────── */
.pfb-insp-body {
	flex: 1;
	overflow-y: auto;
	display: flex;
	flex-direction: column;
}

.pfb-insp-placeholder {
	align-items: center;
	justify-content: center;
	padding: 24px;
	text-align: center;
}

/* ── Collapsible sections ────────────────────────────────── */
.pfb-insp-section {
	border-bottom: 1px solid var(--border-color);
}

.pfb-insp-section-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 10px 14px;
	cursor: pointer;
	user-select: none;
}

.pfb-insp-section-head:hover {
	background: var(--gray-50);
}

.pfb-insp-section-label {
	font-size: 10px;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: 0.08em;
	color: var(--text-muted);
}

.pfb-insp-chevron {
	display: flex;
	align-items: center;
	color: var(--gray-400);
	transition: transform 0.15s;
}

.pfb-insp-chevron.collapsed {
	transform: rotate(-90deg);
}

.pfb-insp-section-body {
	padding: 4px 14px 12px;
	display: flex;
	flex-direction: column;
	gap: 10px;
}

/* ── Rows ────────────────────────────────────────────────── */
.pfb-insp-row {
	display: grid;
	grid-template-columns: 80px 1fr;
	align-items: center;
	gap: 8px;
}

.pfb-insp-row--col {
	grid-template-columns: 1fr;
	gap: 4px;
}

.pfb-insp-label {
	font-size: var(--text-sm);
	color: var(--text-muted);
}

/* ── Source display ──────────────────────────────────────── */
.pfb-source-display {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 5px 8px;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	background: var(--gray-50);
	gap: 6px;
}

.pfb-source-name {
	font-size: var(--text-sm);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.pfb-type-badge {
	font-size: 10px;
	color: var(--text-muted);
	background: var(--gray-100);
	border: 1px solid var(--gray-300);
	border-radius: var(--border-radius-sm);
	padding: 1px 5px;
	white-space: nowrap;
	flex-shrink: 0;
}

/* ── Input ───────────────────────────────────────────────── */
.pfb-insp-input {
	width: 100%;
	padding: 6px 8px;
	font-size: var(--text-sm);
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	background: var(--fg-color);
	color: var(--text-color);
	outline: none;
	box-sizing: border-box;
}

.pfb-insp-input:focus {
	border-color: var(--gray-500);
}

/* ── Segmented control ───────────────────────────────────── */
.pfb-seg {
	display: inline-flex;
	background: var(--gray-100);
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	overflow: hidden;
	width: 100%;
}

.pfb-seg button {
	flex: 1;
	padding: 5px 6px;
	font-size: 11px;
	font-weight: 500;
	border: none;
	border-radius: 0;
	background: transparent;
	color: var(--text-muted);
	cursor: pointer;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	line-height: 1;
}

.pfb-seg button:not(:first-child) {
	border-left: 1px solid var(--border-color);
}

.pfb-seg button:hover {
	background: var(--gray-200);
	color: var(--text-color);
}

.pfb-seg button.active {
	background: var(--fg-color);
	color: var(--text-color);
	box-shadow: var(--shadow-xs);
}

/* ── Stepper (+/−) ───────────────────────────────────────── */
.pfb-stepper {
	display: inline-flex;
	align-items: center;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	overflow: hidden;
	background: var(--gray-50);
	width: 100%;
}

.pfb-stepper button {
	padding: 4px 8px;
	border: none;
	background: transparent;
	cursor: pointer;
	font-size: 14px;
	color: var(--text-muted);
	line-height: 1;
	flex-shrink: 0;
}

.pfb-stepper button:hover {
	background: var(--gray-100);
	color: var(--text-color);
}

.pfb-stepper-val {
	flex: 1;
	text-align: center;
	font-size: var(--text-sm);
	font-weight: 500;
	border-left: 1px solid var(--border-color);
	border-right: 1px solid var(--border-color);
	padding: 4px 4px;
}

.pfb-stepper-input {
	flex: 1;
	min-width: 0;
	width: 100%;
	text-align: center;
	font-size: var(--text-sm);
	font-weight: 500;
	border: none;
	border-left: 1px solid var(--border-color);
	border-right: 1px solid var(--border-color);
	background: transparent;
	color: var(--text-color);
	padding: 4px 2px;
	outline: none;
}

.pfb-stepper-input:focus {
	background: var(--fg-color);
}

/* hide number spin arrows */
.pfb-stepper-input::-webkit-inner-spin-button,
.pfb-stepper-input::-webkit-outer-spin-button {
	-webkit-appearance: none;
}

.pfb-stepper-unit {
	font-size: 10px;
	color: var(--text-muted);
	padding: 0 6px 0 2px;
}

.pfb-stepper--sm {
	width: auto;
}

/* ── Background swatches ─────────────────────────────────── */
.pfb-color-swatches {
	display: flex;
	gap: 6px;
	flex-wrap: wrap;
}

.pfb-swatch {
	width: 28px;
	height: 28px;
	border-radius: var(--border-radius);
	border: 1.5px solid var(--border-color);
	cursor: pointer;
	padding: 0;
	transition: transform 0.1s, border-color 0.1s;
}

.pfb-swatch:hover {
	transform: scale(1.1);
}

.pfb-swatch.active {
	border-color: var(--primary);
	box-shadow: 0 0 0 2px var(--primary-light);
}

/* ── Padding grid ────────────────────────────────────────── */
.pfb-padding-grid {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 8px;
}

.pfb-padding-cell {
	display: flex;
	flex-direction: column;
	gap: 3px;
}

.pfb-padding-label {
	font-size: 10px;
	color: var(--text-muted);
	text-align: center;
}

/* ── Hint ────────────────────────────────────────────────── */
.pfb-insp-hint {
	font-size: var(--text-sm);
	line-height: 1.5;
}

/* ── Actions ─────────────────────────────────────────────── */
.pfb-insp-actions {
	padding: 12px 14px;
	margin-top: auto;
	border-top: 1px solid var(--border-color);
}

.btn-danger-subtle {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	color: var(--red-500);
	background: transparent;
	border: 1px solid var(--red-200);
	border-radius: var(--border-radius);
	padding: 5px 10px;
	font-size: var(--text-sm);
	cursor: pointer;
}

.btn-danger-subtle:hover {
	background: var(--red-50);
	border-color: var(--red-300);
}

/* ── Table column list ───────────────────────────────────── */
.pfb-col-list {
	padding: 4px 0;
}

.pfb-col-row {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 5px 14px;
	border-bottom: 1px solid var(--gray-100);
}

.pfb-col-row:last-child {
	border-bottom: none;
}

.pfb-col-drag {
	cursor: grab;
	color: var(--gray-300);
	display: flex;
	align-items: center;
	flex-shrink: 0;
}

.pfb-col-drag:hover {
	color: var(--gray-500);
}

.pfb-col-label {
	flex: 1;
	font-size: var(--text-sm);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.pfb-col-width-input {
	width: 40px;
	padding: 2px 4px;
	font-size: 11px;
	text-align: right;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius-sm);
	background: var(--fg-color);
	flex-shrink: 0;
}

.pfb-col-width-input:focus {
	outline: none;
	border-color: var(--gray-500);
}

/* hide number spin arrows */
.pfb-col-width-input::-webkit-inner-spin-button,
.pfb-col-width-input::-webkit-outer-spin-button {
	-webkit-appearance: none;
}

.pfb-col-width-unit {
	font-size: 10px;
	color: var(--text-muted);
	flex-shrink: 0;
}

.pfb-col-remove {
	display: flex;
	align-items: center;
	padding: 2px;
	border: none;
	background: transparent;
	cursor: pointer;
	color: var(--gray-300);
	border-radius: var(--border-radius-sm);
	flex-shrink: 0;
}

.pfb-col-remove:hover {
	background: var(--red-50);
	color: var(--red-500);
}

.pfb-col-add-row {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 6px 14px 10px;
	border-top: 1px solid var(--gray-100);
}

.pfb-col-add-select {
	flex: 1;
	font-size: var(--text-sm);
	padding: 4px 6px;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	background: var(--fg-color);
	color: var(--text-color);
	outline: none;
	min-width: 0;
}

.pfb-col-add-select:focus {
	border-color: var(--gray-500);
}

.pfb-col-add-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 26px;
	height: 26px;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	background: var(--gray-50);
	cursor: pointer;
	color: var(--text-muted);
	flex-shrink: 0;
}

.pfb-col-add-btn:hover:not(:disabled) {
	background: var(--gray-100);
	color: var(--text-color);
	border-color: var(--gray-400);
}

.pfb-col-add-btn:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}

.pfb-insp-col-count {
	font-size: 11px;
}

/* ── Letter Head inspector ───────────────────────────────── */
.pfb-lh-zone-label {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 11px;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.06em;
	color: var(--blue-500);
	background: var(--blue-50);
	border-bottom: 1px solid var(--blue-200);
	padding: 7px 14px;
	flex-shrink: 0;
}

.pfb-lh-slider {
	width: 100%;
	accent-color: var(--primary);
}

.pfb-lh-actions {
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.pfb-lh-footer-preview {
	font-size: var(--text-sm);
	color: var(--text-muted);
	padding: 6px 8px;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	background: var(--gray-50);
	max-height: 80px;
	overflow: hidden;
	margin-bottom: 6px;
}

.pfb-lh-edit-btn {
	display: inline-flex;
	align-items: center;
	gap: 4px;
}

.pfb-lh-notice {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 11px;
	color: var(--yellow-800, #854d0e);
	background: var(--yellow-50, #fefce8);
	border-bottom: 1px solid var(--yellow-200, #fde68a);
	padding: 7px 14px;
	flex-shrink: 0;
	line-height: 1.4;
}

/* ── HTML field inline preview (inspector sidebar) ───────── */
.pfb-html-preview {
	font-size: var(--text-sm);
	color: var(--text-muted);
	padding: 6px 8px;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	background: var(--gray-50);
	max-height: 100px;
	overflow: hidden;
	margin-bottom: 2px;
}
</style>

<style>
/* ── HTML split editor dialog (global — renders in modal portal) ── */
.pfb-html-split {
	display: flex;
	height: 480px;
	gap: 0;
	overflow: hidden;
	margin: -15px;
}

.pfb-html-split-pane {
	display: flex;
	flex-direction: column;
	flex: 1;
	min-width: 0;
	overflow: hidden;
}

.pfb-html-split-divider {
	width: 1px;
	background: var(--border-color);
	flex-shrink: 0;
}

.pfb-html-split-label {
	font-size: 10px;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: 0.08em;
	color: var(--text-muted);
	padding: 10px 12px 8px;
	border-bottom: 1px solid var(--border-color);
	background: var(--gray-50);
	flex-shrink: 0;
}

.pfb-html-ctrl-host {
	flex: 1;
	overflow: hidden;
	display: flex;
	flex-direction: column;
	padding: 0 12px 12px;
}

.pfb-html-ctrl-host .frappe-control {
	flex: 1;
	display: flex;
	flex-direction: column;
	height: 100%;
}

.pfb-html-ctrl-host .form-group {
	flex: 1;
	margin: 0;
	display: flex;
	flex-direction: column;
}

.pfb-html-ctrl-host .CodeMirror {
	flex: 1;
	height: 100%;
	font-size: 13px;
	font-family: var(--monospace-font-family, monospace);
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
}

.pfb-html-ctrl-host .CodeMirror-scroll {
	height: 100%;
}

.pfb-html-preview-content {
	flex: 1;
	overflow-y: auto;
	padding: 16px 20px;
	font-size: var(--text-sm);
}
</style>
