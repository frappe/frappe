<template>
	<div class="print-format-section-container" v-if="!section.remove" data-pfb-section>
		<!-- Section drag handle shown on hover in clean-preview (toolbar is hidden) -->
		<div
			v-if="!is_header"
			class="drag-handle section-drag-handle section-preview-drag"
			v-html="frappe.utils.icon('drag', 'sm')"
		></div>
		<div
			class="print-format-section"
			:class="{
				'section--selected': is_selected,
				'label-uppercase': section.label_case === 'uppercase',
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
						@click.stop="section['remove'] = true"
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
					section.columns.length > 1 && section.gap ? { gap: section.gap + 'px' } : {}
				"
			>
				<template v-for="(column, i) in section.columns" :key="i">
					<div v-if="i > 0" class="column-divider"></div>
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
						>
							<template #item="{ element }">
								<Field
									:df="element"
									:field_orientation="section.field_orientation"
								/>
							</template>
							<template #footer>
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
										<span
											class="text-muted"
											v-html="frappe.utils.icon('plus', 'sm')"
										></span>
										<span class="text-muted">{{
											__("Drop fields here")
										}}</span>
									</div>
								</div>
							</template>
						</draggable>
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

const props = defineProps(["section", "is_header", "zone"]);

let store = inject("$store");

let is_selected = computed(() => store.selected_section.value === props.section);

let section_inline_style = computed(() => {
	const style = {};
	if (props.section.background) style.backgroundColor = props.section.background;
	if (props.section.padding) {
		const p = props.section.padding;
		style.padding = `${p.top || 0}px ${p.right || 0}px ${p.bottom || 0}px ${p.left || 0}px`;
	}
	return style;
});

function select_section() {
	store.selected_section.value = props.section;
	store.selected_field.value = null;
	store.selected_letterhead.value = false;
	store.selected_lh_footer.value = false;
}

function set_columns(n) {
	const current = props.section.columns.length;
	if (n === current) return;

	// collect all fields preserving order
	const all_fields = props.section.columns.flatMap((col) => col.fields);

	// build n fresh columns and distribute fields round-robin
	const new_columns = Array.from({ length: n }, () => ({ label: "", fields: [] }));
	all_fields.forEach((field, i) => new_columns[i % n].fields.push(field));

	props.section.columns = new_columns;
}

function remove_column(index) {
	if (props.section.columns.length <= 1) return;
	props.section.columns.splice(index, 1);
}

function toggle_page_break() {
	props.section["page_break"] = !props.section.page_break;
}

function toggle_orientation() {
	props.section["field_orientation"] =
		props.section.field_orientation === "left-right" ? "" : "left-right";
}

function set_column_align(column, value) {
	column.align = value;
}
</script>

<style scoped>
.print-format-section-container {
	position: relative;
}

.print-format-section-container:not(:last-child) {
	margin-bottom: 0.5rem;
}

.print-format-section {
	background-color: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
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
	background: var(--gray-50);
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
	font-size: 10px;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: 0.07em;
	color: var(--text-muted);
	background: var(--gray-100);
	border: 1px solid var(--gray-300);
	border-radius: var(--border-radius-sm);
	padding: 1px 6px;
	white-space: nowrap;
	flex-shrink: 0;
}

.input-section-label {
	border: 1px solid transparent;
	border-radius: var(--border-radius);
	font-size: var(--text-sm);
	font-weight: 600;
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
	border-radius: var(--border-radius-sm);
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
	font-weight: 600;
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
	min-height: 2.5rem;
	border-radius: var(--border-radius);
	display: flex;
	flex-direction: column;
	gap: 0.4rem;
	overflow: visible;
}

.empty-drop-zone {
	position: relative;
	display: flex;
	align-items: center;
	justify-content: center;
	min-height: 3rem;
	border: 1.5px dashed var(--gray-300);
	border-radius: var(--border-radius);
	color: var(--text-muted);
	font-size: var(--text-xs);
}

.empty-drop-zone-hint {
	display: flex;
	align-items: center;
	gap: 0.25rem;
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

/* ── Section preview drag handle (only visible in clean-preview, hidden in edit) ── */
.section-preview-drag {
	display: none; /* hidden by default; shown via .pfb-clean-preview :deep() override */
	position: absolute;
	top: 4px;
	right: 4px;
	z-index: 2;
	padding: 3px 4px;
	background: var(--fg-color);
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius-sm);
	box-shadow: var(--shadow-xs);
	color: var(--gray-400);
	cursor: grab;
	opacity: 0;
	transition: opacity 0.12s;
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
