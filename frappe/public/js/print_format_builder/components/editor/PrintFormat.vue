<template>
	<div
		class="print-format-main"
		:style="rootStyles"
		:class="{
			'pfb-clean-preview': !!store.preview_doc.value,
		}"
	>
		<div :style="page_number_style">{{ __("1 of 2") }}</div>

		<LetterHeadZoneEditor zone="header" />

		<!-- Body wrapper: font size/family applied here so letterhead zones are unaffected -->
		<div class="pfb-body" :style="bodyStyles">
			<div class="zone-divider zone-divider--header">
				<span class="zone-divider-label">{{ __("Header") }}</span>
			</div>
			<PrintFormatSection :section="layout.header" :is_header="true" zone="header" />
			<div class="zone-divider zone-divider--body">
				<span class="zone-divider-label">{{ __("Body") }}</span>
			</div>

			<draggable
				class="sections-container"
				v-model="layout.sections"
				group="sections"
				:animation="200"
				item-key="id"
				handle=".section-drag-handle"
				filter=".section-columns, .column, .field"
				@add="on_section_add"
			>
				<template #item="{ element, index }">
					<div class="section-with-insert">
						<SectionInsert @insert="add_section_at(index)" />
						<PrintFormatSection :section="element" />
					</div>
				</template>
				<template #footer>
					<SectionInsert @insert="add_section_at(layout.sections.length)" />
				</template>
			</draggable>

			<div class="zone-divider zone-divider--footer">
				<span class="zone-divider-label">{{ __("Footer") }}</span>
			</div>
			<PrintFormatSection :section="layout.footer" :is_header="true" zone="footer" />
		</div>

		<LetterHeadZoneEditor v-if="letterhead" zone="footer" />
	</div>
</template>

<script setup>
import draggable from "vuedraggable";
import LetterHeadZoneEditor from "../letterhead/LetterHeadZoneEditor.vue";
import PrintFormatSection from "./PrintFormatSection.vue";
import SectionInsert from "./SectionInsert.vue";
import { useStore } from "../../stores";
import { computed, inject, watch, nextTick } from "vue";

let { layout, letterhead, print_format } = useStore();
let store = inject("$store");

watch(
	() => store.scroll_to_section.value,
	(section) => {
		if (!section) return;
		nextTick(() => {
			const els = document.querySelectorAll("[data-pfb-section]");
			const idx = layout.value.sections.indexOf(section);
			if (idx >= 0 && els[idx]) {
				els[idx].scrollIntoView({ behavior: "smooth", block: "start" });
			}
			store.scroll_to_section.value = null;
		});
	}
);

function add_section_at(index) {
	layout.value.sections.splice(index, 0, {
		label: "",
		columns: [{ label: "", fields: [] }],
	});
}

function on_section_add(evt) {
	const { newIndex } = evt;
	const section = layout.value.sections[newIndex];
	// If a page-break placeholder was dropped, convert it: remove the placeholder
	// and toggle page_break on the section that now precedes it.
	if (section && section.page_break && section.columns.every((c) => !c.fields.length)) {
		layout.value.sections.splice(newIndex, 1);
		const prev = layout.value.sections[newIndex - 1];
		if (prev) {
			prev.page_break = !prev.page_break;
		} else {
			frappe.show_alert(
				{ message: __("Page break must follow a section"), indicator: "orange" },
				3
			);
		}
	}
}

let rootStyles = computed(() => {
	let {
		margin_top = 0,
		margin_bottom = 0,
		margin_left = 0,
		margin_right = 0,
	} = print_format.value;
	return {
		padding: `${margin_top}mm ${margin_right}mm ${margin_bottom}mm ${margin_left}mm`,
		width: "210mm",
		minHeight: "297mm",
	};
});

let bodyStyles = computed(() => {
	const { font_size, font } = print_format.value;
	const styles = {};
	if (font_size) styles.fontSize = `${font_size}pt`;
	if (font) styles.fontFamily = `'${font}', sans-serif`;
	return styles;
});

let page_number_style = computed(() => {
	let style = {
		position: "absolute",
		background: "var(--fg-color)",
		padding: "4px",
		borderRadius: "var(--border-radius)",
		border: "1px solid var(--border-color)",
		fontSize: "11px",
	};
	if (print_format.value.page_number.includes("Top")) {
		style.top = print_format.value.margin_top / 2 + "mm";
		style.transform = "translateY(-50%)";
	}
	if (print_format.value.page_number.includes("Left")) {
		style.left = print_format.value.margin_left + "mm";
	}
	if (print_format.value.page_number.includes("Right")) {
		style.right = print_format.value.margin_right + "mm";
	}
	if (print_format.value.page_number.includes("Bottom")) {
		style.bottom = print_format.value.margin_bottom / 2 + "mm";
		style.transform = "translateY(50%)";
	}
	if (print_format.value.page_number.includes("Center")) {
		style.left = "50%";
		style.transform += " translateX(-50%)";
	}
	if (print_format.value.page_number.includes("Hide")) {
		style.display = "none";
	}
	return style;
});

watch(layout, () => (store.dirty.value = true), { deep: true });
watch(print_format, () => (store.dirty.value = true), { deep: true });
</script>

<style scoped>
.print-format-main {
	position: relative;
	margin-right: auto;
	margin-left: auto;
	background-color: white;
	box-shadow: var(--shadow-lg);
}

.sections-container {
	margin-bottom: 1rem;
}

/* ── Zone dividers ────────────────────────────────────────── */
.zone-divider {
	display: flex;
	align-items: center;
	gap: 8px;
	margin: 0.75rem 0 0.5rem;
}

.zone-divider::before,
.zone-divider::after {
	content: "";
	flex: 1;
	height: 1px;
	background: var(--gray-300);
}

.zone-divider-label {
	font-size: 10px;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: 0.08em;
	white-space: nowrap;
	padding: 2px 8px;
	border-radius: var(--border-radius-sm);
}

.zone-divider--header .zone-divider-label {
	color: var(--blue-500);
	background: var(--blue-50);
	border: 1px solid var(--blue-200);
}

.zone-divider--body .zone-divider-label {
	color: var(--text-muted);
	background: var(--gray-100);
	border: 1px solid var(--gray-300);
}

.zone-divider--footer .zone-divider-label {
	color: var(--blue-500);
	background: var(--blue-50);
	border: 1px solid var(--blue-200);
}

.section-with-insert {
	display: flex;
	flex-direction: column;
}

/* ── Clean preview mode (when live data is loaded) ───────── */

/* Hide all editor chrome */
.pfb-clean-preview :deep(.section-toolbar),
.pfb-clean-preview :deep(.section-insert),
.pfb-clean-preview :deep(.configure-columns-btn) {
	display: none !important;
}

/* In clean-preview: keep the drag handle but hide only the remove button */
.pfb-clean-preview :deep(.field-remove-btn) {
	display: none !important;
}

/* Section hover/selected states in clean-preview */
.pfb-clean-preview :deep(.print-format-section) {
	border: 1px solid transparent;
	border-radius: var(--border-radius);
	overflow: visible;
	transition: border-color 0.1s;
}

.pfb-clean-preview :deep(.print-format-section:hover) {
	border: 1px dashed var(--gray-400);
}

.pfb-clean-preview :deep(.print-format-section.section--selected) {
	border: 1px solid var(--gray-400);
}

.pfb-clean-preview :deep(.print-format-section-container) {
	margin-bottom: 0;
}

/* Field hover/selected states in clean-preview */
.pfb-clean-preview :deep(.field--preview) {
	border: 1px solid transparent;
	background: transparent;
	padding: 0;
	border-radius: var(--border-radius-sm);
	transition: border-color 0.1s;
}

.pfb-clean-preview :deep(.field--preview:hover) {
	border: 1px dashed var(--gray-400);
	background: transparent;
}

.pfb-clean-preview :deep(.field--preview.field--selected) {
	border: 1px solid var(--gray-400);
	background: transparent;
}

/* Section columns: no vertical padding in preview (matches PDF) */
.pfb-clean-preview :deep(.section-columns) {
	padding: 0;
}

/* Remove drag container min-height gaps */
.pfb-clean-preview :deep(.drag-container) {
	min-height: 0;
	gap: 0.15rem;
}

/* Section drag handle in clean-preview: show on hover */
.pfb-clean-preview :deep(.section-preview-drag) {
	display: flex;
}

.pfb-clean-preview :deep(.print-format-section-container:hover .section-preview-drag),
.pfb-clean-preview :deep(.print-format-section.section--selected ~ .section-preview-drag),
.pfb-clean-preview
	:deep(.print-format-section-container:has(.section--selected) .section-preview-drag) {
	opacity: 1;
}

/* Section title: match PDF's .section-label look */
.pfb-clean-preview :deep(.section-title-display) {
	display: block;
	padding: 0 0 0.3rem;
	margin-bottom: 0.4rem;
	border-bottom: 1.5px solid var(--border-color);
	font-size: 1rem;
	font-weight: 700;
	color: var(--text-color);
}
</style>
