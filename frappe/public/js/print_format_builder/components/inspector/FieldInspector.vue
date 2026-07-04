<template>
	<div class="pfb-inspector" @click.stop>
		<!-- Header -->
		<div class="pfb-inspector-head">
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
				<span v-else class="pfb-inspector-eyebrow-inline">{{ __("Inspector") }}</span>
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
				<use href="#icon-text-cursor"></use>
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

let store = inject("$store");
let { letterhead, layout } = useStore();

let selected_field = computed(() => store.selected_field.value);
let selected_section = computed(() => store.selected_section.value);
let selected_letterhead = computed(() => store.selected_letterhead.value);
let selected_lh_footer = computed(() => store.selected_lh_footer.value);

let is_table_field = computed(() => selected_field.value?.fieldtype === "Table");
let is_repeater_field = computed(() => selected_field.value?.fieldtype === "Repeater");

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
	height: calc(100vh - 95px);
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

.pfb-inspector-eyebrow-inline {
	font-size: var(--text-sm);
	font-weight: var(--weight-medium);
	color: var(--text-muted);
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

/* ── Letter Head notice ──────────────────────────────────── */
.pfb-lh-notice {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: var(--text-tiny);
	color: var(--yellow-800);
	background: var(--yellow-50);
	border-bottom: 1px solid var(--yellow-200);
	padding: 7px 14px;
	flex-shrink: 0;
	line-height: 1.4;
}
</style>
