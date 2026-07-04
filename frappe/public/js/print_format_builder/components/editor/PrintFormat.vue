<template>
	<div
		class="print-format-main"
		:style="rootStyles"
		:class="{
			'pfb-clean-preview': !!store.preview_doc.value,
		}"
	>
		<div v-if="!page_number_hidden" class="pfb-page-num" :style="page_number_style">
			{{ __("1 of 2") }}
		</div>

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
import { computed, inject, watch, nextTick, onUnmounted } from "vue";

let { layout, letterhead, print_format } = useStore();
let store = inject("$store");

const CUSTOM_CSS_ID = "pfb-letterhead-custom-css";
watch(
	letterhead,
	(lh) => {
		let el = document.getElementById(CUSTOM_CSS_ID);
		const css = lh?.custom_css;
		if (!css) {
			el?.remove();
			return;
		}
		if (!el) {
			el = document.createElement("style");
			el.id = CUSTOM_CSS_ID;
			document.head.appendChild(el);
		}
		el.textContent = css;
	},
	{ immediate: true, deep: true }
);
onUnmounted(() => document.getElementById(CUSTOM_CSS_ID)?.remove());

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
	const { font_size, font, label_color, value_color } = print_format.value;
	const styles = {};
	if (font_size) styles.fontSize = `${parseFloat(font_size)}px`;
	if (font) styles.fontFamily = `'${font}', sans-serif`;
	if (label_color) styles["--pfb-label-color"] = label_color;
	if (value_color) styles["--pfb-value-color"] = value_color;
	return styles;
});

let page_number_hidden = computed(() => print_format.value.page_number.includes("Hide"));

let page_number_style = computed(() => {
	const pn = print_format.value.page_number;
	const { margin_top, margin_bottom, margin_left, margin_right } = print_format.value;
	const style = { position: "absolute" };
	if (pn.includes("Top")) {
		style.top = margin_top / 2 + "mm";
		style.transform = "translateY(-50%)";
	}
	if (pn.includes("Bottom")) {
		style.bottom = margin_bottom / 2 + "mm";
		style.transform = "translateY(50%)";
	}
	if (pn.includes("Left")) style.left = margin_left + "mm";
	if (pn.includes("Right")) style.right = margin_right + "mm";
	if (pn.includes("Center")) {
		style.left = "50%";
		style.transform = (style.transform || "") + " translateX(-50%)";
	}
	return style;
});

watch(layout, () => (store.dirty.value = true), { deep: true });
watch(print_format, () => (store.dirty.value = true), { deep: true });
</script>

<style scoped>
.pfb-page-num {
	font-size: var(--text-xs);
	color: var(--text-muted);
	background: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	padding: var(--padding-xs) var(--padding-sm);
	line-height: 1.4;
	white-space: nowrap;
}

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
	font-size: var(--text-tiny);
	font-weight: var(--weight-bold);
	text-transform: uppercase;
	letter-spacing: 0.08em;
	white-space: nowrap;
	padding: 2px 8px;
	border-radius: var(--radius);
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

.section-with-insert:hover :deep(.section-insert) {
	opacity: 1;
}

/* ── Clean preview mode (when live data is loaded) ───────── */

/* Hide all editor chrome */
.pfb-clean-preview :deep(.section-toolbar),
.pfb-clean-preview :deep(.configure-columns-btn) {
	display: none;
}

/* Default section skin in clean-preview — grid sections style themselves */
.pfb-clean-preview :deep(.print-format-section:not(.section--grid)) {
	border: 1px solid transparent;
	border-radius: var(--radius);
	overflow: visible;
	transition: border-color 0.1s;
}

.pfb-clean-preview :deep(.print-format-section:hover) {
	outline: 1px dashed var(--gray-400);
	outline-offset: 2px;
}

.pfb-clean-preview :deep(.print-format-section.section--selected) {
	outline: 1px solid var(--gray-400);
	outline-offset: 2px;
}

.pfb-clean-preview :deep(.print-format-section-container) {
	margin-bottom: 0;
}

/* Default field skin in clean-preview — grid cells style themselves */
.pfb-clean-preview :deep(.field--preview:not(.section--grid *)) {
	border: 1px solid transparent;
	background: transparent;
	padding: 0;
	border-radius: var(--radius);
	transition: border-color 0.1s;
}

.pfb-clean-preview :deep(.field--preview:hover:not(.section--grid *)) {
	border: 1px dashed var(--gray-400);
	background: transparent;
}

.pfb-clean-preview :deep(.field--preview.field--selected:not(.section--grid *)) {
	border: 1px solid var(--gray-400);
	background: transparent;
}

.pfb-clean-preview :deep(.field--preview.field--condition-hidden:not(.section--grid *)) {
	border: 1px dashed var(--gray-400);
}

/* Section columns: no vertical padding in preview (matches PDF) */
.pfb-clean-preview :deep(.section-columns) {
	padding: 0;
}

/* Remove drag container min-height gaps; grid sections keep their own gap */
.pfb-clean-preview :deep(.drag-container) {
	min-height: 0;
}

.pfb-clean-preview :deep(.drag-container:not(.section--grid *)) {
	gap: 0.15rem;
}

/* Section drag handle in clean-preview: show on hover */
.pfb-clean-preview :deep(.section-preview-actions) {
	display: flex;
}

.pfb-clean-preview :deep(.print-format-section-container:hover .section-preview-actions),
.pfb-clean-preview :deep(.print-format-section.section--selected ~ .section-preview-actions),
.pfb-clean-preview
	:deep(.print-format-section-container:has(.section--selected) .section-preview-actions) {
	opacity: 1;
}

/* Section title: match PDF's .section-label look; grid sections keep their own box */
.pfb-clean-preview :deep(.section-title-display) {
	display: block;
	font-size: var(--text-lg);
	font-weight: var(--weight-bold);
	color: var(--text-color);
}

.pfb-clean-preview :deep(.section-title-display:not(.section--grid *)) {
	padding: 0 0 0.3rem;
	margin-bottom: 0.4rem;
	border-bottom: 1.5px solid var(--border-color);
}

.pfb-body :deep(.field--preview) {
	font-size: inherit;
}
.pfb-body :deep(.field--preview .field-preview-value) {
	font-size: 1em;
}
.pfb-body :deep(.field--preview .field-preview-label) {
	font-size: 1em;
}
.pfb-body :deep(.field--preview .preview-table) {
	font-size: 0.9em;
}
</style>
