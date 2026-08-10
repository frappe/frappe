<template>
	<div
		class="print-format-main print-format"
		data-theme="light"
		:style="rootStyles"
		:class="{
			'pfb-clean-preview': !!store.preview_doc.value,
			'print-format-doc': !!store.preview_doc.value,
			'show-label-colon': !!print_format.show_label_colon,
		}"
	>
		<component :is="'style'" v-if="color_css">{{ color_css }}</component>
		<component :is="'style'" v-if="user_css">{{ user_css }}</component>
		<div v-if="!page_number_hidden" class="pfb-page-num" :style="page_number_style">
			{{ __("1 of 2") }}
		</div>

		<LetterHeadZoneEditor zone="header" />

		<!-- Body wrapper: font size/family applied here so letterhead zones are unaffected -->
		<div class="pfb-body" :style="bodyStyles">
			<PrintFormatSection :section="layout.header" :is_header="true" zone="header" />

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
import { DRAG_OPTIONS, setDragging, field_uid } from "../../utils";
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
	() => store.scroll_target.value,
	(target) => {
		if (!target) return;
		nextTick(() => {
			// a field carries a fieldtype; a section carries columns — a field
			// scrolls to its own node so the exact row lands on screen, not just
			// the section it lives in
			if (target.columns) {
				const els = document.querySelectorAll("[data-pfb-section]");
				const idx = layout.value.sections.indexOf(target);
				if (idx >= 0 && els[idx]) {
					els[idx].scrollIntoView({ behavior: "smooth", block: "start" });
				}
			} else {
				const el = document.querySelector(`[data-field-uid="${field_uid(target)}"]`);
				el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
			}
			store.scroll_target.value = null;
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
	styles.fontSize = `${parseFloat(font_size) || 14}px`;
	if (font) styles.fontFamily = `'${font}', sans-serif`;
	return styles;
});

// The format's custom CSS applies to the whole document in the printed PDF;
// on the canvas that document is this component, so every selector is scoped
// to it before the style hits the desk DOM
let user_css = computed(() => scope_css(print_format.value.css, ".print-format-main"));

function scope_css(css, scope) {
	if (!(css || "").trim()) return "";
	const style = document.createElement("style");
	style.media = "not all";
	style.textContent = css;
	document.head.appendChild(style);
	const prefix_rule = (rule) => {
		if (rule.type === CSSRule.MEDIA_RULE || rule.type === CSSRule.SUPPORTS_RULE) {
			const inner = [...rule.cssRules].map(prefix_rule).join("\n");
			const head = rule.cssText.slice(0, rule.cssText.indexOf("{"));
			return `${head}{\n${inner}\n}`;
		}
		if (rule.selectorText) {
			const scoped = rule.selectorText
				.split(",")
				.map((sel) => {
					sel = sel.trim();
					const rootless = sel.replace(/^(html|body)(?![\w-])\s*/i, "");
					return rootless ? `${scope} ${rootless}` : scope;
				})
				.join(", ");
			return rule.cssText.replace(rule.selectorText, scoped);
		}
		return rule.cssText;
	};
	try {
		return [...(style.sheet?.cssRules || [])].map(prefix_rule).join("\n");
	} finally {
		style.remove();
	}
}

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

/* section hover/selection rings live in one place — PrintFormatSection.vue */

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
.pfb-clean-preview
	:deep(.print-format-section-container.pfb-section-active .section-preview-actions) {
	opacity: 1;
}

/* Section title: typography/border come from the shared .section-label rules */
.pfb-clean-preview :deep(.section-title-display) {
	display: block;
}
</style>
