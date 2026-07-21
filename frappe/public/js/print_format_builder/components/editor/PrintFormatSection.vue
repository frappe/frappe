<template>
	<div
		class="print-format-section-container"
		data-pfb-section
		v-show="!preview_doc || has_visible_fields"
		:class="{ 'section-container--condition-hidden': preview_doc && !is_section_visible }"
		@click.stop="select_section"
	>
		<!-- Top-right actions pill shown on hover in clean-preview (toolbar is hidden) -->
		<div v-if="!is_header" class="section-preview-actions">
			<div
				class="drag-handle section-drag-handle"
				v-html="frappe.utils.icon('grip', 'xs')"
			></div>
			<button
				class="es-button"
				data-size="xs"
				data-variant="ghost"
				data-icon-button="true"
				:title="__('Copy section')"
				@click.stop="store.copy_section(section)"
				v-html="frappe.utils.icon('copy', 'xs')"
			></button>
			<button
				class="es-button"
				data-size="xs"
				data-variant="ghost"
				data-icon-button="true"
				:title="__('Duplicate section')"
				@click.stop="store.duplicate_section(section)"
				v-html="frappe.utils.icon('copy-plus', 'xs')"
			></button>
			<button
				class="es-button"
				data-size="xs"
				data-variant="ghost"
				data-icon-button="true"
				:title="__('Save as snippet')"
				@click.stop="save_as_snippet"
				v-html="frappe.utils.icon('bookmark-plus', 'xs')"
			></button>
			<button
				class="es-button"
				data-size="xs"
				data-variant="ghost"
				data-theme="red"
				data-icon-button="true"
				:title="__('Remove section')"
				@click.stop="remove_section"
				v-html="frappe.utils.icon('x', 'xs')"
			></button>
		</div>
		<div
			class="print-format-section"
			:class="{
				'section--selected': is_selected,
				'section--grid': is_grid,
				'section--grid-rows': is_grid && section.grid_borders === 'rows',
				'section--grid-columns': is_grid && section.grid_borders === 'columns',
			}"
			:style="section_inline_style"
			tabindex="0"
			:aria-label="section.label || __('Untitled section')"
			@click.stop="select_section"
			@keydown.enter.prevent="select_section"
			@keydown.space.prevent="select_section"
		>
			<div class="section-toolbar">
				<div class="section-toolbar-left">
					<div
						v-if="!is_header"
						class="drag-handle section-drag-handle"
						title="Drag to reorder"
						v-html="frappe.utils.icon('grip', 'sm')"
					></div>
					<span v-if="zone" class="es-badge">{{
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
						class="es-button"
						data-size="xs"
						data-variant="ghost"
						data-icon-button="true"
						:title="__('Copy section')"
						@click.stop="store.copy_section(section)"
					>
						<span v-html="frappe.utils.icon('copy', 'sm')"></span>
					</button>
					<button
						v-if="!is_header"
						class="es-button"
						data-size="xs"
						data-variant="ghost"
						data-icon-button="true"
						:title="__('Duplicate section')"
						@click.stop="store.duplicate_section(section)"
					>
						<span v-html="frappe.utils.icon('copy-plus', 'sm')"></span>
					</button>
					<button
						v-if="!is_header"
						class="es-button"
						data-size="xs"
						data-variant="ghost"
						data-icon-button="true"
						:title="__('Save as snippet')"
						@click.stop="save_as_snippet"
					>
						<span v-html="frappe.utils.icon('bookmark-plus', 'sm')"></span>
					</button>
					<button
						v-if="!is_header"
						class="es-button"
						data-size="xs"
						data-variant="ghost"
						data-theme="red"
						data-icon-button="true"
						:title="__('Remove section')"
						@click.stop="remove_section"
					>
						<span v-html="frappe.utils.icon('x', 'sm')"></span>
					</button>
				</div>
			</div>

			<div
				v-if="section.label && section.show_label !== 'hide'"
				class="section-title-display section-label"
			>
				{{ section.label }}
			</div>
			<div
				class="section-columns"
				:class="preview_doc ? ['row', row_layout] : []"
				:style="columns_gap_style"
			>
				<template v-for="(column, i) in section.columns" :key="i">
					<div v-if="i > 0 && !preview_doc" class="column-divider"></div>
					<div
						class="column"
						:class="{ col: !!preview_doc }"
						:style="column.width ? { flex: `${column.width} 1 0%` } : {}"
					>
						<div
							v-if="i < section.columns.length - 1"
							class="col-width-handle"
							:style="{ right: handle_offset }"
							@pointerdown.prevent.stop="start_col_width_resize($event, i)"
							@mousedown.prevent.stop
							@click.stop
						></div>
						<draggable
							class="drag-container"
							v-model="column.fields"
							group="fields"
							:animation="150"
							item-key="id"
							filter="a, input, textarea, select, button, label, summary, [contenteditable], [role='button'], [tabindex]:not(.field--chip):not(.field--preview)"
							:preventOnFilter="false"
							:emptyInsertThreshold="100"
							v-bind="DRAG_OPTIONS"
							@start="setDragging(true)"
							@end="setDragging(false)"
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
								class="es-button empty-col-remove"
								data-size="xs"
								data-variant="ghost"
								data-theme="red"
								data-icon-button="true"
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
				class="es-button"
				data-size="xs"
				data-variant="ghost"
				data-theme="red"
				data-icon-button="true"
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
import { useColumnResize } from "../../composables/useColumnResize";
import { DRAG_OPTIONS, evaluate_visible_if, parse_inline_style, setDragging } from "../../utils";

const props = defineProps(["section", "is_header", "zone"]);

let store = inject("$store");

let is_selected = computed(() => store.selected_section.value === props.section);
let preview_doc = computed(() => store.preview_doc.value);
let is_section_visible = computed(() =>
	evaluate_visible_if(props.section.visible_if, preview_doc.value)
);

let is_grid = computed(() => !!props.section.field_borders);

// Mirrors the row layout class print_format.html picks for right-aligned
// columns; the server computes it for body sections only, never header/footer
let row_layout = computed(() => {
	if (props.is_header) return "";
	const cols = props.section.columns || [];
	if (!cols.some((c) => c.align === "right")) return "";
	return cols.length === 1 ? "row-col-right-end" : "row-col-space-between";
});

// In preview the gap mirrors the server default (20px unless set, 0 for grid)
let columns_gap_style = computed(() => {
	if (preview_doc.value) {
		return { gap: is_grid.value ? "0" : `${props.section.gap ?? 20}px` };
	}
	return is_grid.value
		? { gap: "0" }
		: props.section.columns.length > 1 && props.section.gap
		? { gap: props.section.gap + "px" }
		: {};
});

let handle_offset = computed(() => {
	if (preview_doc.value) return `${-((props.section.gap ?? 20) / 2 + 4)}px`;
	const gap = props.section.columns.length > 1 && props.section.gap ? props.section.gap : 0;
	return `${-(gap + 12.5)}px`;
});

const { start: start_column_resize } = useColumnResize();

function start_col_width_resize(e, i) {
	const cols = props.section.columns;
	const handle = e.currentTarget;
	const container = handle.closest(".section-columns");
	const col_els = [...container.children].filter((el) => el.classList.contains("column"));
	const total = container.getBoundingClientRect().width;
	const widths = col_els.map((el) => (el.getBoundingClientRect().width / total) * 100);
	const start_x = e.clientX;
	const on_move = (ev) => {
		let delta = ((ev.clientX - start_x) / total) * 100;
		delta = Math.max(10 - widths[i], Math.min(widths[i + 1] - 10, delta));
		cols.forEach((c, j) => (c.width = Math.round(widths[j])));
		cols[i].width = Math.round(widths[i] + delta);
		cols[i + 1].width = Math.round(widths[i + 1] - delta);
	};
	start_column_resize(handle, "col-width-handle--active", on_move);
}

let has_visible_fields = computed(
	() =>
		!props.section.label ||
		props.section.columns.some((col) => col.fields.some((f) => !f.remove))
);

let section_inline_style = computed(() => {
	const style = {};
	if (props.section.background) style.backgroundColor = props.section.background;
	for (const prop of ["padding", "margin"]) {
		const box = props.section[prop];
		if (box) {
			style[prop] = `${box.top || 0}px ${box.right || 0}px ${box.bottom || 0}px ${
				box.left || 0
			}px`;
		}
	}
	if (is_grid.value) {
		const pad = props.section.cell_padding ?? 8;
		style["--pfb-cell-pad"] = `${pad}px`;
	}
	return { ...style, ...parse_inline_style(props.section.custom_style) };
});

function select_section() {
	store.select_section(props.section);
}

function remove_section() {
	store.remove_section(props.section);
}

function save_as_snippet() {
	frappe.prompt(
		{
			label: __("Snippet name"),
			fieldname: "name",
			fieldtype: "Data",
			reqd: 1,
			default: props.section.label || "",
		},
		({ name }) => {
			store.save_snippet(name, props.section, "Section").then(
				() =>
					frappe.show_alert(
						{ message: __("Section saved as snippet"), indicator: "green" },
						3
					),
				() => {}
			);
		},
		__("Save Section as Snippet"),
		__("Save")
	);
}

function remove_column(index) {
	if (props.section.columns.length <= 1) return;
	props.section.columns.splice(index, 1);
}
</script>

<style scoped>
.print-format-section-container {
	position: relative;
	/* flow-root keeps the section's own margin inside this box, so selection
	   outlines drawn on the container enclose the margin area */
	display: flow-root;
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

/* Section title — hidden in editor (toolbar shows it), revealed via parent :deep() */
.section-title-display {
	display: none;
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

.col-width-handle {
	position: absolute;
	top: 0;
	bottom: 0;
	width: 8px;
	cursor: col-resize;
	z-index: 2;
}

.col-width-handle::after {
	content: "";
	position: absolute;
	top: 2px;
	bottom: 2px;
	left: 3px;
	width: 2px;
	border-radius: 1px;
	background: var(--gray-400);
	opacity: 0;
	transition: opacity 0.15s;
}

.section-columns:hover .col-width-handle::after {
	opacity: 0.4;
}

.col-width-handle:hover::after,
.col-width-handle--active::after {
	opacity: 1;
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

.column:has(.pfb-drag-ghost) .empty-drop-zone {
	background: transparent;
	border-color: var(--gray-400);
	border-style: solid;
}

.column:has(.pfb-drag-ghost) .empty-drop-zone-hint {
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
	opacity: 0;
	transition: opacity 0.1s;
	pointer-events: auto;
}

.empty-drop-zone:hover .empty-col-remove {
	opacity: 1;
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

/* ── Section preview actions pill (only visible in clean-preview, hidden in edit) ── */
.section-preview-actions {
	display: none; /* shown via .pfb-clean-preview :deep() override */
	position: absolute;
	bottom: calc(100% + 2px);
	right: 4px;
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

/* ── Table layout (field borders) ───────────────────────── */
.section--grid {
	border: 1px solid var(--gray-300);
	border-radius: var(--border-radius-md, 8px);
	overflow: hidden;
	padding: 0;
}
.section--grid.section--selected {
	border-color: var(--gray-400);
}
.section--grid .section-title-display {
	padding: var(--pfb-cell-pad, 8px);
	margin: 0;
	border-bottom: 1px solid var(--gray-300);
}
.section--grid .section-columns {
	padding: 0;
}
.section--grid .column {
	padding: 0;
}
.section--grid .column:not(:last-child) {
	border-right: 1px solid var(--gray-300);
}
.section--grid .column-divider {
	display: none;
}
.section--grid :deep(.drag-container) {
	gap: 0;
}
.section--grid :deep(.field--chip) {
	padding: var(--pfb-cell-pad, 8px);
	border: none;
	border-bottom: 1px solid var(--gray-300);
	border-radius: 0;
	background: transparent;
}
.section--grid :deep(.field--chip:last-child) {
	border-bottom: none;
}
.section--grid-rows .column:not(:last-child) {
	border-right: none;
}
.section--grid-columns :deep(.field--chip) {
	border-bottom: none;
}
.section--grid :deep(.field--chip:hover),
.section--grid :deep(.field--preview:hover),
.section--grid :deep(.field--selected) {
	outline: 1px dashed var(--gray-400);
	outline-offset: -1px;
}
.section--grid :deep(.field--selected) {
	outline-style: solid;
}
</style>
