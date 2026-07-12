<template>
	<div
		ref="root_el"
		class="print-format-main"
		:style="rootStyles"
		:class="{
			'pfb-clean-preview': !!store.preview_doc.value,
			'print-format-doc': !!store.preview_doc.value,
		}"
	>
		<component :is="'style'" v-if="color_css">{{ color_css }}</component>
		<div v-if="!page_number_hidden" class="pfb-page-num" :style="page_number_style">
			{{ __("1 of {0}", [page_count]) }}
		</div>
		<div
			v-for="guide in page_guides"
			:key="guide.page"
			class="page-guide"
			:style="{ top: guide.top + 'px' }"
		>
			<span class="page-guide-label">{{ __("Page {0}", [guide.page]) }}</span>
		</div>

		<LetterHeadZoneEditor zone="header" />

		<!-- Body wrapper: font size/family applied here so letterhead zones are unaffected -->
		<div ref="body_el" class="pfb-body" :style="bodyStyles">
			<div class="zone-divider">
				<span class="zone-divider-label">{{ __("Header") }}</span>
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

			<div class="zone-divider">
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
import { computed, inject, watch, nextTick, onMounted, onUnmounted, ref } from "vue";

let { layout, letterhead, print_format } = useStore();
let store = inject("$store");

// Where the printed page boundaries fall on the canvas. Heights on the canvas
// match print heights (shared stylesheet, em spacing), so the boundary is
// page height minus margins minus the repeating letterhead zones, measured
// from where the body content starts.
const PAGE_SIZES_MM = { A4: [210, 297], Letter: [216, 279.4] };

let root_el = ref(null);
let body_el = ref(null);
let page_size = ref("A4");
let page_guides = ref([]);
let page_count = computed(() => page_guides.value.length + 1);
let resize_observer = null;

function update_guides() {
	const root = root_el.value;
	const body = body_el.value;
	if (!root || !body) return;
	const rr = root.getBoundingClientRect();
	const br = body.getBoundingClientRect();
	if (!rr.width || !br.height) {
		page_guides.value = [];
		return;
	}
	const [page_w, page_h] = PAGE_SIZES_MM[page_size.value] || PAGE_SIZES_MM.A4;
	const px_mm = rr.width / page_w;
	const { margin_top = 0, margin_bottom = 0 } = print_format.value;
	const zones = root.querySelectorAll(":scope > .lh-zone");
	const lh_head = zones[0]?.offsetHeight || 0;
	const lh_foot = zones.length > 1 ? zones[zones.length - 1].offsetHeight : 0;
	const usable = (page_h - margin_top - margin_bottom) * px_mm - lh_head - lh_foot;
	const guides = [];
	if (usable > 0) {
		const body_top = br.top - rr.top;
		const content_end = br.bottom - rr.top;
		for (let k = 1; body_top + k * usable < content_end - 1 && k <= 100; k++) {
			guides.push({ page: k + 1, top: Math.round(body_top + k * usable) });
		}
	}
	page_guides.value = guides;
}

onMounted(() => {
	frappe.db.get_single_value("Print Settings", "pdf_page_size").then((v) => {
		if (v && PAGE_SIZES_MM[v]) page_size.value = v;
		nextTick(update_guides);
	});
	resize_observer = new ResizeObserver(update_guides);
	if (root_el.value) resize_observer.observe(root_el.value);
	if (body_el.value) resize_observer.observe(body_el.value);
});
onUnmounted(() => resize_observer?.disconnect());

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
	color: var(--text-muted);
	background: var(--gray-100);
	border: 1px solid var(--gray-300);
}

.page-guide {
	position: absolute;
	left: 0;
	right: 0;
	border-top: 1px dashed var(--gray-400);
	pointer-events: none;
	z-index: 5;
}

.page-guide-label {
	position: absolute;
	left: 50%;
	top: 0;
	transform: translate(-50%, -50%);
	font-size: var(--text-tiny);
	font-weight: var(--weight-medium);
	color: var(--text-muted);
	background: var(--gray-100);
	border: 1px solid var(--gray-300);
	border-radius: var(--radius);
	padding: 1px 6px;
	white-space: nowrap;
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
