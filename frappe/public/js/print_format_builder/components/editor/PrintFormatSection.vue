<template>
	<div
		class="print-format-section-container"
		data-pfb-section
		:class="{ 'section-container--condition-hidden': preview_doc && !is_section_visible }"
	>
		<!-- Top-left actions pill shown on hover in clean-preview (toolbar is hidden) -->
		<div v-if="!is_header" class="section-preview-actions">
			<div
				class="drag-handle section-drag-handle"
				v-html="frappe.utils.icon('drag', 'xs')"
			></div>
			<button
				class="btn btn-xs btn-icon"
				:title="__('Remove section')"
				@click.stop="remove_section"
				v-html="frappe.utils.icon('x', 'xs')"
			></button>
		</div>
		<div
			class="print-format-section"
			:class="{
				'section--selected': is_selected,
				'label-uppercase': section.label_case === 'uppercase',
				'section--grid': is_grid,
				'section--grid-rows': is_grid && grid_inner_rows,
			}"
			:style="section_inline_style"
			@click.stop="select_section"
		>
			<div class="section-toolbar">
				<div class="section-toolbar-left">
					<div
						v-if="!is_header"
						class="drag-handle section-drag-handle"
						title="Drag to reorder"
						v-html="frappe.utils.icon('drag', 'sm')"
					></div>
					<span v-if="zone" class="zone-badge">{{
						zone === "header" ? __("Header") : __("Footer")
					}}</span>
					<input
						class="input-section-label"
						type="text"
						:placeholder="__('Section Title')"
						v-model="section.label"
					/>
				</div>
				<div class="section-toolbar-right">
					<button
						v-if="!is_header"
						class="btn btn-xs btn-icon toolbar-btn toolbar-btn-danger"
						:title="__('Remove section')"
						@click.stop="remove_section"
					>
						<span v-html="frappe.utils.icon('x', 'sm')"></span>
					</button>
				</div>
			</div>

			<div
				v-if="section.label && section.show_label !== 'hide'"
				class="section-title-display"
			>
				{{ section.label }}
			</div>
			<div class="section-columns" :style="columns_style">
				<template v-for="(column, i) in section.columns" :key="i">
					<div
						v-if="i > 0 && show_col_divider"
						class="column-divider"
						:style="divider_style"
					></div>
					<div
						class="column"
						:class="{ 'column-align-right': column.align === 'right' }"
					>
						<draggable
							class="drag-container"
							v-model="column.fields"
							group="fields"
							:animation="150"
							item-key="id"
							handle=".drag-handle"
							:emptyInsertThreshold="100"
							@add="select_section"
						>
							<template #item="{ element }">
								<Field
									:df="element"
									:field_orientation="section.field_orientation"
								/>
							</template>
						</draggable>
						<div
							v-if="column.fields.filter((f) => !f.remove).length === 0"
							class="empty-drop-zone"
						>
							<button
								v-if="section.columns.length > 1"
								class="btn btn-xs btn-icon empty-col-remove"
								:title="__('Remove column')"
								@click.stop="remove_column(i)"
								v-html="frappe.utils.icon('x', 'xs')"
							></button>
							<div class="empty-drop-zone-hint">
								<span>{{ __("Drop fields here") }}</span>
							</div>
						</div>
					</div>
				</template>
			</div>
		</div>
		<div class="page-break-indicator" v-if="section.page_break">
			<span>— {{ __("Page Break") }} —</span>
			<button
				class="btn btn-xs page-break-remove"
				:title="__('Remove page break')"
				@click.stop="section.page_break = false"
				v-html="frappe.utils.icon('x', 'xs')"
			></button>
		</div>
	</div>
</template>

<script setup>
import draggable from "vuedraggable";
import Field from "./Field.vue";
import { computed, inject } from "vue";
import { evaluate_visible_if } from "../../utils";

const props = defineProps(["section", "is_header", "zone"]);

let store = inject("$store");

let is_selected = computed(() => store.selected_section.value === props.section);
let preview_doc = computed(() => store.preview_doc.value);
let is_section_visible = computed(() =>
	evaluate_visible_if(props.section.visible_if, preview_doc.value)
);

// ── Table-layout (field borders) state ────────────────────
let is_grid = computed(() => !!props.section.field_borders);
let grid_inner_rows = computed(() => props.section.inner_rows !== false);
let grid_inner_cols = computed(() => props.section.inner_cols !== false);
let grid_cell_pad = computed(() => props.section.cell_padding ?? 8);

// The shared "1px solid #color" edge used for both the outer box and inner lines
let grid_edge = computed(() => {
	const b = props.section.border || {};
	return `${b.width || 1}px ${b.style || "solid"} ${b.color || "#e5e7eb"}`;
});

// Apply the per-side border to a target style object using the border config
function apply_border(style, b) {
	if (!b || !b.width) return;
	const edge = `${b.width}px ${b.style || "solid"} ${b.color || "#000000"}`;
	if (b.top !== false) style.borderTop = edge;
	if (b.right !== false) style.borderRight = edge;
	if (b.bottom !== false) style.borderBottom = edge;
	if (b.left !== false) style.borderLeft = edge;
	if (b.radius) style.borderRadius = b.radius + "px";
}

let section_inline_style = computed(() => {
	const style = {};
	if (props.section.background) style.backgroundColor = props.section.background;
	if (props.section.padding) {
		const p = props.section.padding;
		style.padding = `${p.top || 0}px ${p.right || 0}px ${p.bottom || 0}px ${p.left || 0}px`;
	}
	// In grid mode the border/radius live on .section-columns instead of the wrapper
	if (!is_grid.value) apply_border(style, props.section.border);
	return style;
});

let columns_style = computed(() => {
	const style = {};
	if (props.section.columns.length > 1 && props.section.gap) {
		style.gap = props.section.gap + "px";
	}
	if (is_grid.value) {
		apply_border(style, props.section.border);
		style.padding = "0";
		style.gap = "0";
		if (props.section.border?.radius) style.overflow = "hidden";
		// CSS vars consumed by the scoped grid rules
		style["--pfb-line"] = grid_edge.value;
		style["--pfb-cell-pad"] = grid_cell_pad.value + "px";
	}
	return style;
});

// Column dividers double as the inner vertical lines in grid mode
let show_col_divider = computed(() => (is_grid.value ? grid_inner_cols.value : true));
let divider_style = computed(() => {
	if (!is_grid.value) return {};
	const b = props.section.border || {};
	return { width: (b.width || 1) + "px", background: b.color || "#e5e7eb", margin: "0" };
});

function select_section() {
	store.selected_section.value = props.section;
	store.selected_field.value = null;
	store.selected_letterhead.value = false;
	store.selected_lh_footer.value = false;
}

function remove_section() {
	const idx = store.layout.value.sections.indexOf(props.section);
	if (idx !== -1) {
		store.layout.value.sections.splice(idx, 1);
		if (store.selected_section.value === props.section) {
			store.selected_section.value = null;
		}
		if (
			store.selected_field.value &&
			props.section.columns.some((c) => c.fields.includes(store.selected_field.value))
		) {
			store.selected_field.value = null;
		}
	}
}

function remove_column(index) {
	if (props.section.columns.length <= 1) return;
	props.section.columns.splice(index, 1);
}
</script>

<style scoped>
.print-format-section-container {
	position: relative;
}

.print-format-section-container:not(:last-child) {
	margin-bottom: 0.5rem;
}

.section-container--condition-hidden {
	opacity: 0.35;
	outline: 2px dashed var(--gray-400);
	outline-offset: 2px;
	border-radius: var(--radius);
}

.print-format-section {
	background-color: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	overflow: hidden;
	cursor: default;
}

.section--selected {
	border-color: var(--gray-400);
}

.section-toolbar {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 0.4rem 0.6rem;
	background: var(--subtle-accent);
	border-bottom: 1px solid var(--border-color);
	gap: 0.5rem;
}

.section-toolbar-left {
	display: flex;
	align-items: center;
	gap: 0.4rem;
	flex: 1;
	min-width: 0;
}

.section-toolbar-right {
	display: flex;
	align-items: center;
	gap: 0.25rem;
	flex-shrink: 0;
}

.section-drag-handle {
	cursor: grab;
	color: var(--gray-400);
	display: flex;
	align-items: center;
	padding: 2px;
}

.section-drag-handle:hover {
	color: var(--gray-600);
}

.zone-badge {
	font-size: var(--text-tiny);
	font-weight: var(--weight-bold);
	text-transform: uppercase;
	letter-spacing: 0.07em;
	color: var(--text-muted);
	background: var(--gray-100);
	border: 1px solid var(--gray-300);
	border-radius: var(--radius);
	padding: 1px 6px;
	white-space: nowrap;
	flex-shrink: 0;
}

.input-section-label {
	border: 1px solid transparent;
	border-radius: var(--radius);
	font-size: var(--text-sm);
	font-weight: var(--weight-semibold);
	background: transparent;
	padding: 2px 4px;
	flex: 1;
	min-width: 0;
}

.input-section-label:hover {
	border-color: var(--border-color);
}

.input-section-label:focus {
	border-color: var(--gray-400);
	outline: none;
	background-color: var(--fg-color);
}

.input-section-label::placeholder {
	font-style: italic;
	font-weight: normal;
	color: var(--gray-400);
}

.toolbar-btn {
	padding: 3px;
	box-shadow: none;
	color: var(--text-muted);
	border-radius: var(--radius);
}

.toolbar-btn:hover {
	background: var(--gray-200);
	color: var(--text-color);
}

.toolbar-btn.active {
	background: var(--gray-200);
	color: var(--text-color);
}

.toolbar-btn-danger:hover {
	background: var(--red-50);
	color: var(--red-500);
}

/* Section title — hidden in editor (toolbar shows it), revealed via parent :deep() */
.section-title-display {
	display: none;
	font-size: var(--text-sm);
	font-weight: var(--weight-semibold);
	color: var(--text-muted);
	padding: 0;
}

.section-columns {
	display: flex;
	padding: 0.75rem;
	gap: 0;
	align-items: stretch;
}

.column {
	flex: 1;
	min-width: 0;
	display: flex;
	flex-direction: column;
	position: relative;
}

.column-divider {
	width: 1px;
	background: var(--border-color);
	margin: 0 0.5rem;
	flex-shrink: 0;
}

/* ── Table layout (field borders) ────────────────────────── */
/* Cells fill their column; reset each field's own chrome and use cell padding */
.section--grid .column {
	padding: 0;
}

.section--grid .drag-container {
	gap: 0;
	min-height: 0;
	border-radius: 0;
}

.section--grid :deep(.field) {
	border: none !important;
	border-radius: 0 !important;
	background: transparent !important;
	margin: 0 !important;
	padding: var(--pfb-cell-pad, 8px) !important;
}

.section--grid :deep(.field-preview-wrap) {
	padding: 0 !important;
}

/* Horizontal inner lines: between adjacent cells in a column */
.section--grid-rows :deep(.drag-container > .field + .field) {
	border-top: var(--pfb-line, 1px solid var(--border-color)) !important;
}

.drag-container {
	flex: 1;
	min-width: 0;
	min-height: 3rem;
	border-radius: var(--radius);
	display: flex;
	flex-direction: column;
	gap: 0.4rem;
	overflow: visible;
}

.column:has(.empty-drop-zone) {
	min-height: 3rem;
}

.column:has(.sortable-ghost) .empty-drop-zone {
	background: transparent;
	border-color: var(--blue-300);
	border-style: solid;
}

.column:has(.sortable-ghost) .empty-drop-zone-hint {
	display: none;
}

.empty-drop-zone {
	position: absolute;
	inset: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	border: 1.5px dashed var(--gray-400);
	border-radius: var(--radius);
	color: var(--text-muted);
	font-size: var(--text-xs);
	pointer-events: none;
	background: var(--gray-50);
	transition: border-color 0.15s, background 0.15s;
}

.empty-drop-zone-hint {
	color: var(--gray-500);
}

.empty-col-remove {
	position: absolute;
	top: 4px;
	right: 4px;
	padding: 2px;
	box-shadow: none;
	color: var(--gray-500);
	opacity: 0;
	transition: opacity 0.1s;
	pointer-events: auto;
}

.empty-drop-zone:hover .empty-col-remove {
	opacity: 1;
}

.empty-col-remove:hover {
	background: var(--red-50);
	color: var(--red-500);
}

.page-break-indicator {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 0.4rem;
	color: var(--text-muted);
	font-size: var(--text-xs);
	font-style: italic;
	padding: 0.25rem 0;
	border-top: 1px dashed var(--gray-300);
	border-bottom: 1px dashed var(--gray-300);
	margin: 0.25rem 0;
}

.page-break-remove {
	padding: 1px 3px;
	box-shadow: none;
	color: var(--gray-500);
	line-height: 1;
}

.page-break-remove:hover {
	background: var(--red-50);
	color: var(--red-500);
}

/* ── Section preview actions pill (only visible in clean-preview, hidden in edit) ── */
.section-preview-actions {
	display: none; /* shown via .pfb-clean-preview :deep() override */
	position: absolute;
	top: 4px;
	left: 4px;
	z-index: 2;
	gap: 2px;
	padding: 1px 2px;
	background: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	box-shadow: var(--shadow-xs);
	align-items: center;
	opacity: 0;
	transition: opacity 0.12s;
}

.section-preview-actions .section-drag-handle {
	cursor: grab;
	color: var(--gray-400);
	display: flex;
	align-items: center;
	padding: 2px;
}

.section-preview-actions .section-drag-handle:hover {
	color: var(--gray-600);
}

.section-preview-actions .btn-icon {
	box-shadow: none;
	padding: 2px;
	color: var(--text-muted);
}

.section-preview-actions .btn-icon:hover {
	background: var(--red-50);
	color: var(--red-500);
}

/* ── Label case: uppercase (mirrors print_format.css rules for builder canvas) */

/* section-title-display is in this same component — plain scoped selector */
.print-format-section.label-uppercase .section-title-display {
	text-transform: uppercase;
	letter-spacing: 0.06em;
}

/* field-preview-* and preview-table are inside child Field.vue — need :deep() */
.print-format-section.label-uppercase :deep(.field-preview-label) {
	text-transform: uppercase;
	letter-spacing: 0.04em;
}

.print-format-section.label-uppercase :deep(.field-preview-table > .field-preview-label) {
	text-transform: uppercase;
	letter-spacing: 0.03em;
}

.print-format-section.label-uppercase :deep(.preview-table th) {
	text-transform: uppercase;
	letter-spacing: 0.03em;
}
</style>
