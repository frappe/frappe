<template>
	<div class="pfb-inspector" @click.stop>
		<!-- Header — hidden on the canvas (settings) view -->
		<div v-if="has_selection" class="pfb-inspector-head">
			<div class="pfb-inspector-title">
				<span class="pfb-inspector-kind">{{ inspector_kind }}</span>
				<span class="pfb-inspector-name">{{ inspector_subtitle }}</span>
			</div>
		</div>

		<!-- Breadcrumb: navigate up to parent section when a field is selected -->
		<div v-if="selected_field && parent_section && !is_multi_select" class="pfb-breadcrumb">
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

		<!-- Nothing selected: canvas-wide print settings -->
		<div v-if="!has_selection" class="pfb-insp-body pfb-canvas-settings">
			<PrintSettingsPanel />
		</div>

		<!-- ── Letter Head Footer inspector ──────────────────────── -->
		<template v-else-if="selected_lh_footer">
			<LetterHeadZoneInspector zone="footer" />
		</template>

		<!-- ── Letter Head inspector ──────────────────────────────── -->
		<template v-else-if="selected_letterhead">
			<LetterHeadZoneInspector zone="header" />
		</template>

		<!-- ── Multi-select bulk inspector ─────────────────────── -->
		<BulkPropertiesPanel v-else-if="is_multi_select" />

		<!-- ── Table field inspector ───────────────────────────────── -->
		<TableFieldInspector v-else-if="selected_field && is_table_field" />

		<!-- ── Repeater inspector ──────────────────────────────── -->
		<RepeaterFieldInspector v-else-if="selected_field && is_repeater_field" />

		<!-- ── Field inspector ─────────────────────────────────── -->
		<FieldPropertiesPanel v-else-if="selected_field" :field-is-inline="field_is_inline" />

		<!-- ── Section inspector ───────────────────────────────── -->
		<SectionPropertiesPanel v-else-if="selected_section" />
	</div>
</template>

<script setup>
import { computed, inject } from "vue";
import { useStore } from "../../stores";
import LetterHeadZoneInspector from "./LetterHeadZoneInspector.vue";
import SectionPropertiesPanel from "./SectionPropertiesPanel.vue";
import RepeaterFieldInspector from "./RepeaterFieldInspector.vue";
import TableFieldInspector from "./TableFieldInspector.vue";
import FieldPropertiesPanel from "./FieldPropertiesPanel.vue";
import BulkPropertiesPanel from "./BulkPropertiesPanel.vue";
import PrintSettingsPanel from "../PrintSettingsPanel.vue";

let store = inject("$store");
let { letterhead, layout, print_format } = useStore();

let selected_field = computed(() => store.selected_field.value);
let selected_count = computed(
	() => store.selected_fields.value.length + store.selected_sections.value.length
);
let is_multi_select = computed(() => store.is_multi_select.value);
let selected_section = computed(() => store.selected_section.value);
let selected_letterhead = computed(() => store.selected_letterhead.value);
let selected_lh_footer = computed(() => store.selected_lh_footer.value);
let has_selection = computed(
	() =>
		selected_field.value ||
		selected_section.value ||
		selected_letterhead.value ||
		selected_lh_footer.value
);

let is_table_field = computed(() => selected_field.value?.fieldtype === "Table");
let is_repeater_field = computed(() => selected_field.value?.fieldtype === "Repeater");

let inspector_kind = computed(() => {
	if (is_multi_select.value) return __("Selection");
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
	if (is_multi_select.value) {
		return store.selected_sections.value.length
			? __("{0} items", [selected_count.value])
			: __("{0} fields", [selected_count.value]);
	}
	if (selected_lh_footer.value) return __("Footer");
	if (selected_letterhead.value) return letterhead.value?.name || "";
	if (selected_field.value) {
		const df = selected_field.value;
		if (df.custom) return df.label || df.fieldname;
		return frappe.meta.get_label(print_format.value.doc_type, df.fieldname);
	}
	if (selected_section.value) return selected_section.value.label || __("Untitled section");
	return "";
});

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

let field_is_inline = computed(() => parent_section.value?.field_orientation === "left-right");
</script>

<style scoped>
.pfb-inspector {
	width: 280px;
	flex-shrink: 0;
	height: calc(100vh - var(--pfb-chrome-offset, 95px));
	overflow-y: auto;
	border-left: 1px solid var(--border-color);
	background: var(--fg-color);
	display: flex;
	flex-direction: column;
}

/* ── Header ─────────────────────────────────────────────── */
.pfb-inspector-head {
	padding: 8px 12px;
	border-bottom: 1px solid var(--border-color);
	flex-shrink: 0;
	min-height: 0;
}

.pfb-inspector-title {
	display: flex;
	align-items: center;
	gap: 6px;
	min-width: 0;
}

.pfb-inspector-kind {
	font-size: var(--text-sm);
	font-weight: var(--weight-semibold);
	white-space: nowrap;
	flex-shrink: 0;
}

.pfb-inspector-name {
	font-size: var(--text-sm);
	color: var(--text-muted);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	flex: 1;
	min-width: 0;
}

.pfb-inspector-name::before {
	content: "·";
	margin-right: 6px;
	opacity: 0.4;
}

/* ── Breadcrumb ──────────────────────────────────────────── */
.pfb-breadcrumb {
	padding: 4px 10px;
	border-bottom: 1px solid var(--border-color);
	background: var(--fg-color);
}

.pfb-breadcrumb-btn {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	padding: 2px 6px;
	border: none;
	background: transparent;
	cursor: pointer;
	border-radius: var(--radius);
	color: var(--text-muted);
	font-size: var(--text-xs);
	transition: background 0.1s, color 0.1s;
	max-width: 100%;
}

.pfb-breadcrumb-btn:hover {
	background: var(--gray-100);
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

/* ── Canvas settings (nothing selected) ──────────────────── */
.pfb-canvas-settings {
	padding: 12px 14px;
}
</style>
