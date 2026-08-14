<template>
	<div
		class="print-format-section-container"
		data-pfb-section
		:data-section-uid="field_uid(section)"
		v-show="!preview_doc || has_visible_fields"
		:class="{
			'section-container--condition-hidden': preview_doc && !is_section_visible,
			'pfb-section-active': is_selected,
			'pfb-layer-hover': store.hovered_node.value === section,
		}"
		@click.stop="select_section"
		@contextmenu="on_context_menu"
		@mouseenter="store.hovered_section.value = section"
		@mouseleave="store.hovered_section.value = null"
	>
		<!-- Top-right actions pill shown on hover in clean-preview (toolbar is hidden) -->
		<div v-if="!is_header" class="section-preview-actions">
			<div
				class="drag-handle section-drag-handle"
				v-html="frappe.utils.icon('grip', 'xs')"
			></div>
			<SectionActions
				:section="section"
				size="xs"
				@snippet="save_as_snippet"
				@remove="remove_section"
			/>
		</div>
		<div
			class="print-format-section"
			:class="{
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
					<SectionActions
						v-if="!is_header"
						:section="section"
						size="sm"
						@snippet="save_as_snippet"
						@remove="remove_section"
					/>
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
							@start="(e) => on_field_drag_start(column, e)"
							@end="on_field_drag_end"
							@add="(e) => select_dropped_field(column, e)"
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
		<div v-if="show_spacing_handles" class="pfb-section-chrome" :style="section_chrome_style">
			<SectionSpacingHandles :section="section" type="margin" />
			<SectionSpacingHandles :section="section" type="padding" />
			<SectionRadiusHandle :section="section" />
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
import SectionActions from "./SectionActions.vue";
import SectionSpacingHandles from "./SectionSpacingHandles.vue";
import SectionRadiusHandle from "./SectionRadiusHandle.vue";
import { computed, inject } from "vue";
import { useColumnResize } from "../../composables/useColumnResize";
import {
	DRAG_OPTIONS,
	JUSTIFY_CLASSES,
	evaluate_visible_if,
	parse_inline_style,
	setDragging,
	field_uid,
} from "../../utils";
import { useContextMenu } from "../../composables/useContextMenu";

const props = defineProps(["section", "is_header", "zone"]);

let store = inject("$store");

let is_selected = computed(() => store.selected_sections.value.includes(props.section));
// spacing handles only for a single, sole-selected body section
let show_spacing_handles = computed(
	() =>
		!props.is_header &&
		is_selected.value &&
		store.selected_sections.value.length === 1 &&
		store.selected_fields.value.length === 0
);
// the chrome overlay sits on the section's border box: inset from the container
// by the section's own margins (the flow-root reserves that space)
let section_chrome_style = computed(() => {
	const m = props.section.margin || {};
	return {
		top: (m.top || 0) + "px",
		right: (m.right || 0) + "px",
		bottom: (m.bottom || 0) + "px",
		left: (m.left || 0) + "px",
	};
});
let preview_doc = computed(() => store.preview_doc.value);
let is_section_visible = computed(() =>
	evaluate_visible_if(props.section.visible_if, preview_doc.value)
);

let is_grid = computed(() => !!props.section.field_borders);

// Mirrors the row layout class print_format.html picks for right-aligned
// columns; the server computes it for body sections only, never header/footer
let row_layout = computed(() => {
	if (JUSTIFY_CLASSES[props.section.justify]) return JUSTIFY_CLASSES[props.section.justify];
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
	const box_css = (box) =>
		`${box.top || 0}px ${box.right || 0}px ${box.bottom || 0}px ${box.left || 0}px`;
	if (props.section.margin) style.margin = box_css(props.section.margin);
	// In table mode, padding can't be element padding — child cell borders would
	// stop at the content and leave a borderless strip. Instead expose it as
	// per-side vars the grid CSS folds into the edge cells, so the dividers and
	// border wrap the padded box. Non-grid sections keep real padding.
	if (is_grid.value) {
		style["--pfb-cell-pad"] = `${props.section.cell_padding ?? 8}px`;
		const pad = props.section.padding;
		if (pad) {
			style["--pfb-pad-top"] = `${pad.top || 0}px`;
			style["--pfb-pad-right"] = `${pad.right || 0}px`;
			style["--pfb-pad-bottom"] = `${pad.bottom || 0}px`;
			style["--pfb-pad-left"] = `${pad.left || 0}px`;
		}
	} else if (props.section.padding) {
		style.padding = box_css(props.section.padding);
	}
	if (props.section.radius != null) {
		style.borderRadius = `${props.section.radius}px`;
		// clip content to the rounded corners (non-grid sections are overflow:visible)
		style.overflow = "hidden";
	}
	return { ...style, ...parse_inline_style(props.section.custom_style) };
});

function select_section() {
	store.select_section(props.section);
}

function select_dropped_field(column, e) {
	const field = column.fields[e.newIndex];
	if (field) store.select_field(field);
	else store.select_section(props.section);
}

// Bulk drag: if the grabbed field is part of a multi-selection, snapshot the
// whole group (document order) at drag start; on drop, Sortable has moved only
// the grabbed field, so we pull the rest over to sit contiguously around it.
let drag_group = null;
function on_field_drag_start(column, e) {
	setDragging(true);
	drag_group = null;
	const dragged = column.fields[e.oldIndex];
	const sel = store.selected_fields.value;
	if (dragged && sel.length > 1 && sel.includes(dragged)) {
		const group = store.ordered_body_fields().filter((f) => sel.includes(f));
		if (group.length > 1 && group.includes(dragged)) drag_group = { dragged, group };
	}
}
function on_field_drag_end() {
	setDragging(false);
	if (!drag_group) return;
	const { dragged, group } = drag_group;
	drag_group = null;
	store.reflow_dragged_group(dragged, group);
	store.set_selected(group);
}

function remove_section() {
	store.remove_section(props.section);
}

const { open: open_context_menu } = useContextMenu();

function on_context_menu(e) {
	select_section();
	open_context_menu(e, [
		!props.is_header && {
			label: __("Copy section"),
			icon: "copy",
			action: () => store.copy_section(props.section),
		},
		!props.is_header && {
			label: __("Duplicate section"),
			icon: "copy-plus",
			action: () => store.duplicate_section(props.section),
		},
		!props.is_header && {
			label: __("Save as snippet"),
			icon: "bookmark-plus",
			action: save_as_snippet,
		},
		store.clipboard.value && {
			label: __("Paste"),
			icon: "clipboard-paste",
			action: () => store.paste_clipboard(),
		},
		!props.is_header && { divider: true },
		!props.is_header && {
			label: __("Delete section"),
			icon: "trash",
			danger: true,
			action: remove_section,
		},
	]);
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
	/* flow-root keeps the section's own margin inside this box, so the spacing
	   handles can be positioned against it */
	display: flow-root;
}

.print-format-section-container:not(:last-child) {
	margin-bottom: 0.5rem;
}

/* One ring for every active section state — selected, hover (canvas), and
   layer-hover all look identical. The :has() guard keeps hover on the innermost
   element: when a field inside is hovered, the field's ring shows, not this.
   Drawn on the container with no offset: square corners (an outline always
   follows the element's own radius) and flush against the section's border. */
.print-format-section-container.pfb-section-active,
.print-format-section-container.pfb-layer-hover,
.print-format-section-container:hover:not(:has(.field--preview:hover, .field--chip:hover)) {
	outline: var(--pfb-ring);
}

.section-container--condition-hidden {
	opacity: 0.35;
	outline: 2px dashed var(--gray-400);
}

.print-format-section {
	background-color: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	overflow: hidden;
	cursor: default;
}

/* overlay carrying the padding/margin/radius handles — sits on the section's
   border box, outside the section so its content still clips to the radius */
.pfb-section-chrome {
	position: absolute;
	pointer-events: none;
	z-index: 3;
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

.column.col > .empty-drop-zone {
	left: 15px;
	right: 15px;
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
	/* section padding is folded into the edge cells (see below) so the grid
	   dividers and border wrap it; default 0 when no padding is set */
	--pfb-pad-top: 0px;
	--pfb-pad-right: 0px;
	--pfb-pad-bottom: 0px;
	--pfb-pad-left: 0px;
	border: 1px solid var(--gray-300);
	border-radius: var(--border-radius-md, 8px);
	overflow: hidden;
	padding: 0;
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
/* fold section padding into the outermost cells so the grid dividers and border
   wrap the padded box (builder mode — preview/PDF handled in print_format_doc.css) */
.section--grid :deep(.drag-container > .field--chip:first-child) {
	padding-top: calc(var(--pfb-cell-pad, 8px) + var(--pfb-pad-top));
}
.section--grid :deep(.drag-container > .field--chip:last-child) {
	padding-bottom: calc(var(--pfb-cell-pad, 8px) + var(--pfb-pad-bottom));
}
.section--grid .column:first-child :deep(.field--chip) {
	padding-left: calc(var(--pfb-cell-pad, 8px) + var(--pfb-pad-left));
}
.section--grid .column:last-child :deep(.field--chip) {
	padding-right: calc(var(--pfb-cell-pad, 8px) + var(--pfb-pad-right));
}
.section--grid-rows .column:not(:last-child) {
	border-right: none;
}
.section--grid-columns :deep(.field--chip) {
	border-bottom: none;
}
</style>
