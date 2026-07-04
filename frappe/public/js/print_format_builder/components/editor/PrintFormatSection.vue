<template>
	<div
		class="print-format-section-container"
		data-pfb-section
		v-show="!preview_doc || has_visible_fields"
		:class="{ 'section-container--condition-hidden': preview_doc && !is_section_visible }"
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
			@click.stop="select_section"
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
				class="section-title-display"
			>
				{{ section.label }}
			</div>
			<div
				class="section-columns"
				:style="
					is_grid
						? { gap: '0' }
						: section.columns.length > 1 && section.gap
						? { gap: section.gap + 'px' }
						: {}
				"
			>
				<template v-for="(column, i) in section.columns" :key="i">
					<div v-if="i > 0 && !preview_doc" class="column-divider"></div>
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
							filter="a, input, textarea, select, button, label, summary, [contenteditable], [role='button'], [tabindex]"
							:preventOnFilter="false"
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
import { evaluate_visible_if, parse_inline_style } from "../../utils";

const props = defineProps(["section", "is_header", "zone"]);

let store = inject("$store");

let is_selected = computed(() => store.selected_section.value === props.section);
let preview_doc = computed(() => store.preview_doc.value);
let is_section_visible = computed(() =>
	evaluate_visible_if(props.section.visible_if, preview_doc.value)
);

let is_grid = computed(() => !!props.section.field_borders);

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
	border: 1px solid var(--border-color);
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
	border-bottom: 1px solid var(--border-color);
}
.section--grid .section-columns {
	padding: 0;
}
.section--grid .column {
	padding: 0;
}
.section--grid .column:not(:last-child) {
	border-right: 1px solid var(--border-color);
}
.section--grid .column-divider {
	display: none;
}
.section--grid :deep(.drag-container) {
	gap: 0;
}
.section--grid :deep(.field) {
	padding: var(--pfb-cell-pad, 8px);
	border: none;
	border-bottom: 1px solid var(--border-color);
	border-radius: 0;
	background: transparent;
}
.section--grid :deep(.field:last-child) {
	border-bottom: none;
}
.section--grid-rows .column:not(:last-child) {
	border-right: none;
}
.section--grid-columns :deep(.field) {
	border-bottom: none;
}
.section--grid :deep(.field:hover),
.section--grid :deep(.field--selected) {
	outline: 1px dashed var(--gray-400);
	outline-offset: -1px;
}
.section--grid :deep(.field--selected) {
	outline-style: solid;
}
</style>
