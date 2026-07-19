<template>
	<div
		class="print-format-main"
		data-theme="light"
		:style="rootStyles"
		:class="{
			'pfb-clean-preview': !!store.preview_doc.value,
			'print-format-doc': !!store.preview_doc.value,
		}"
	>
		<component :is="'style'" v-if="color_css">{{ color_css }}</component>
		<div v-if="!page_number_hidden" class="pfb-page-num" :style="page_number_style">
			{{ __("1 of 2") }}
		</div>

		<LetterHeadZoneEditor zone="header" />

		<!-- Body wrapper: font size/family applied here so letterhead zones are unaffected -->
		<div class="pfb-body" :style="bodyStyles">
			<div class="zone-divider">
				<span class="zone-divider-label">
					{{ __("Header") }}
					<span v-if="repeat_header_footer" class="zone-divider-hint"
						>· {{ __("repeats on all pages") }}</span
					>
				</span>
			</div>
			<PrintFormatSection :section="layout.header" :is_header="true" zone="header" />
			<div class="zone-divider">
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
				v-bind="DRAG_OPTIONS"
				@start="setDragging(true)"
				@end="setDragging(false)"
				@add="on_section_add"
			>
				<template #item="{ element, index }">
					<div class="section-with-insert">
						<SectionInsert @insert="add_section_at(index)" />
						<PrintFormatSection :section="element" />
					</div>
				</template>
				<template #footer>
					<SectionInsert
						v-if="layout.sections && layout.sections.length"
						@insert="add_section_at(layout.sections.length)"
					/>
				</template>
			</draggable>

			<button
				v-if="!layout.sections || !layout.sections.length"
				class="body-empty"
				@click="add_section_at(0)"
			>
				<span class="body-empty-icon" v-html="frappe.utils.icon('plus', 'md')"></span>
				<span class="body-empty-title">{{ __("Add a section") }}</span>
				<span class="body-empty-hint">
					{{ __("Sections hold the columns and fields of your document.") }}
				</span>
			</button>

			<div class="zone-divider">
				<span class="zone-divider-label">
					{{ __("Footer") }}
					<span v-if="repeat_header_footer" class="zone-divider-hint"
						>· {{ __("repeats on all pages") }}</span
					>
				</span>
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
import { DRAG_OPTIONS, setDragging } from "../../utils";
import { useStore } from "../../stores";
import { computed, inject, watch, nextTick, onMounted, onUnmounted, ref } from "vue";

let { layout, letterhead, print_format } = useStore();
let store = inject("$store");

const PAGE_SIZES_MM = { A4: [210, 297], Letter: [216, 279.4] };
let page_size = ref("A4");

onMounted(() => {
	frappe.db.get_single_value("Print Settings", "pdf_page_size").then((v) => {
		if (v && PAGE_SIZES_MM[v]) page_size.value = v;
	});
});

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
	const [page_w, page_h] = PAGE_SIZES_MM[page_size.value] || PAGE_SIZES_MM.A4;
	return {
		padding: `${margin_top}mm ${margin_right}mm ${margin_bottom}mm ${margin_left}mm`,
		width: `${page_w}mm`,
		minHeight: `${page_h}mm`,
	};
});

let bodyStyles = computed(() => {
	const { font_size, font } = print_format.value;
	const styles = {};
	if (font_size) styles.fontSize = `${parseFloat(font_size)}px`;
	if (font) styles.fontFamily = `'${font}', sans-serif`;
	return styles;
});

// Same scoped colour rules the server appends after the shared stylesheet;
// rendered as a style element inside the component so it dies with the DOM
let color_css = computed(() => {
	const { label_color, value_color } = print_format.value;
	let css = "";
	if (label_color) {
		css += `.print-format-doc .field .label,
.print-format-doc .field.left-right .label,
.print-format-doc .field.field-inline .label { color: ${label_color}; }\n`;
	}
	if (value_color) {
		css += `.print-format-doc .field .value,
.print-format-doc .field.left-right .value,
.print-format-doc .field.field-inline .value { color: ${value_color}; }\n`;
	}
	return css;
});

let repeat_header_footer = computed(
	() => !!frappe.model.get_doc(":Print Settings", "Print Settings")?.repeat_header_footer
);

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

/* ── Empty-body call to action ────────────────────────────── */
.body-empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 4px;
	width: 100%;
	padding: 2rem 1rem;
	border: 1px dashed var(--gray-300);
	border-radius: var(--radius);
	background: var(--gray-50);
	color: var(--text-muted);
	cursor: pointer;
	transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}

.body-empty:hover {
	border-color: var(--gray-500);
	background: var(--gray-100);
	color: var(--text-color);
}

.body-empty-icon {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	height: 28px;
	margin-bottom: 2px;
	border-radius: 50%;
	background: var(--gray-200);
	color: var(--gray-700);
}

.body-empty-title {
	font-size: var(--text-md);
	font-weight: var(--weight-medium);
}

.body-empty-hint {
	font-size: var(--text-sm);
}

/* ── Zone dividers ────────────────────────────────────────── */
.zone-divider {
	display: flex;
	align-items: center;
	gap: 12px;
	margin: 0.75rem 0 0.5rem;
}

.zone-divider::before,
.zone-divider::after {
	content: "";
	flex: 1;
	height: 1px;
	background: var(--gray-200);
}

.zone-divider-label {
	font-size: var(--text-tiny);
	font-weight: var(--weight-medium);
	letter-spacing: 0;
	white-space: nowrap;
	color: var(--gray-400);
}

.zone-divider-hint {
	text-transform: none;
	font-weight: var(--weight-regular);
	letter-spacing: 0.02em;
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

/* Outlines live on the container so they enclose the section's margin too */
.pfb-clean-preview :deep(.print-format-section-container:hover) {
	outline: 1px dashed var(--gray-400);
	outline-offset: 2px;
	border-radius: var(--radius);
}

.pfb-clean-preview :deep(.print-format-section-container:has(.section--selected)) {
	outline: 1px solid var(--gray-400);
	outline-offset: 2px;
	border-radius: var(--radius);
}

.pfb-clean-preview :deep(.print-format-section-container) {
	margin-bottom: 0;
}

/* Field selection chrome lives in Field.vue and is outline-only */

/* Section columns: no vertical padding in preview (matches PDF) */
.pfb-clean-preview :deep(.section-columns) {
	padding: 0;
}

/* Remove drag container min-height gaps; grid sections keep their own gap */
.pfb-clean-preview :deep(.drag-container) {
	min-height: 0;
}

/* Field spacing comes from the shared .field + .field margin, like the PDF */
.pfb-clean-preview :deep(.drag-container:not(.section--grid *)) {
	gap: 0;
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

/* Section title: typography/border come from the shared .section-label rules */
.pfb-clean-preview :deep(.section-title-display) {
	display: block;
}
</style>
