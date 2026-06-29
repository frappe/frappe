<template>
	<!-- The grid is a multi-element control (table + row actions), so the wrapper
	     itself is the labelled region (`role="group"`, fieldset/legend style) rather
	     than wiring aria onto one inner element. `labelledBy`/`describedBy` reference
	     the InputLabel/InputDescription/InputError ids below, so they're functional,
	     not decorative; `dataAttrs` carries `data-state="invalid"` etc. for styling. -->
	<div
		class="flex flex-col gap-2"
		role="group"
		:aria-labelledby="labelledBy"
		:aria-describedby="describedBy"
		:aria-errormessage="hasError ? errorMessageId : undefined"
		:aria-invalid="hasError || undefined"
		data-slot="control"
		v-bind="dataAttrs"
	>
		<!-- Label / description / error / required all come from frappe-ui's labeling
		     primitives so the markup, typography, spacing, and `*` match every
		     FormLayout field. -->
		<InputLabel
			v-if="label"
			:id="labelId"
			:label="label"
			:required="required"
			class="text-p-sm-medium text-ink-gray-7"
		/>

		<div
			v-if="columns.length"
			class="relative isolate overflow-hidden rounded border border-outline-gray-2"
			:class="{ 'grid-disabled': disabled }"
		>
			<!-- Scroller + shadows share a `relative` box so the shadows clamp to the
			     header/rows and don't bleed over the empty state below. -->
			<div class="relative">
				<!-- Header and rows share this scroller so they pan together. -->
				<div
					ref="scroller"
					class="grid-scroller overflow-x-auto"
					@scroll="updateScrollShadows"
				>
					<!-- Header -->
					<div
						class="grid items-stretch bg-surface-gray-2 text-sm text-ink-gray-5"
						:style="{ gridTemplateColumns: templateColumns, minWidth: gridMinWidth }"
					>
						<div
							v-if="!disabled"
							class="sticky left-0 z-10 flex items-center justify-center border-r border-outline-gray-2 bg-surface-gray-2"
							:style="{ left: '0' }"
						>
							<Checkbox
								:modelValue="allSelected"
								@update:modelValue="
									(checked: unknown) => toggleAll(checked as boolean)
								"
							/>
						</div>
						<div
							class="sticky z-10 flex items-center justify-center border-r border-outline-gray-2 bg-surface-gray-2 py-2"
							:style="{ left: numberColLeft }"
						>
							#
						</div>
						<div
							v-for="(col, i) in columns"
							:key="col.fieldname"
							class="relative truncate px-2 py-2"
							:class="[
								alignClass(col.align),
								{ 'border-r border-outline-gray-2': i < columns.length - 1 },
							]"
							:title="col.label"
						>
							{{ col.label ?? col.fieldname }}
							<span v-if="col.reqd" class="text-ink-red-5">*</span>
							<!-- Drag the right edge to resize this column. -->
							<span
								class="grid-col-resize"
								:class="{ 'is-resizing': resizingIndex === i }"
								@mousedown="startResize(i, $event)"
							/>
						</div>
						<div
							class="sticky right-0 z-10 border-l border-outline-gray-2 bg-surface-gray-2"
							:style="{ right: '0' }"
						/>
					</div>

					<!-- Rows -->
					<Draggable
						v-if="rows.length"
						:modelValue="rows"
						:item-key="keyOf"
						:disabled="disabled"
						handle=".grid-drag-handle"
						tag="div"
						@update:modelValue="reorder"
					>
						<template #item="{ element: row, index: rowIndex }">
							<div
								class="grid-row grid items-stretch border-t border-outline-gray-2 bg-surface-base"
								:class="{ 'cursor-pointer': disabled }"
								:style="{
									gridTemplateColumns: templateColumns,
									minWidth: gridMinWidth,
								}"
								@click="onRowClick(row, rowIndex)"
							>
								<div
									v-if="!disabled"
									class="sticky left-0 z-10 flex items-center justify-center border-r border-outline-gray-2 bg-surface-base"
									:style="{ left: '0' }"
								>
									<Checkbox
										:modelValue="isSelected(row)"
										@update:modelValue="
											(checked: unknown) => setRow(row, checked as boolean)
										"
									/>
								</div>
								<div
									class="sticky z-10 flex items-center justify-center border-r border-outline-gray-2 bg-surface-base py-2 text-sm text-ink-gray-7"
									:class="{ 'grid-drag-handle cursor-grab': !disabled }"
									:style="{ left: numberColLeft }"
									:title="disabled ? undefined : 'Drag to reorder'"
								>
									{{ rowIndex + 1 }}
								</div>
								<div
									v-for="(col, i) in columns"
									:key="col.fieldname"
									class="grid-cell flex min-w-0 items-stretch"
									:class="[
										alignClass(col.align),
										{
											'border-r border-outline-gray-2':
												i < columns.length - 1,
										},
										{ 'pointer-events-none': disabled },
									]"
								>
									<slot
										name="cell"
										:row="row"
										:column="col"
										:index="rowIndex"
										:value="row[col.fieldname]"
										:update="(v: any) => updateCell(rowIndex, col, v)"
										:commit="(v: any) => commitCell(rowIndex, col, v)"
									>
										<span class="truncate px-2 py-1 text-sm text-ink-gray-7">
											{{ row[col.fieldname] }}
										</span>
									</slot>
								</div>
								<div
									class="sticky right-0 z-10 flex items-center justify-center border-l border-outline-gray-2 bg-surface-base"
									:style="{ right: '0' }"
								>
									<Button
										variant="ghost"
										icon="lucide-square-pen"
										:tooltip="'Edit Row'"
										@click="emit('edit', { row, index: rowIndex })"
									/>
								</div>
							</div>
						</template>
					</Draggable>
				</div>

				<!-- Scroll shadows: full-height strips pinned just inside the frozen
			     columns and outside the scroller, so they stay put while the grid pans. -->
				<div
					class="grid-scroll-shadow grid-scroll-shadow-left"
					:class="{ 'is-visible': canScrollLeft }"
					:style="{ left: leftShadowOffset }"
				/>
				<div
					class="grid-scroll-shadow grid-scroll-shadow-right"
					:class="{ 'is-visible': canScrollRight }"
					:style="{ right: SIDE_COL_WIDTH }"
				/>
			</div>

			<!-- Empty state sits outside the scroller so "No rows" stays centred in view
			     instead of scrolling off when the columns overflow. -->
			<div
				v-if="!rows.length"
				class="border-t border-outline-gray-2 p-4 text-center text-sm text-ink-gray-4"
			>
				No rows
			</div>
		</div>

		<!-- No columns (e.g. child meta absent). -->
		<div v-else class="text-sm text-ink-gray-4">No columns to display</div>

		<div v-if="!disabled && columns.length" class="flex gap-2">
			<Button label="Add Row" icon-left="lucide-plus" @click="addRow" />
			<Button
				v-if="selectedCount"
				theme="red"
				variant="subtle"
				:label="`Delete (${selectedCount})`"
				icon-left="lucide-trash-2"
				@click="deleteSelected"
			/>
		</div>

		<!-- Help text and validation error sit below the control. `showDescription`
		     hides the description while an error is shown (frappe-ui convention). -->
		<InputDescription v-if="showDescription" :id="descriptionId" :description="description" />
		<InputError v-if="hasError" :id="errorMessageId" :lines="errorLines" />
	</div>
</template>

<script setup lang="ts" generic="T extends GridColumn">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Button, Checkbox } from "frappe-ui";
import {
	InputLabel,
	InputDescription,
	InputError,
	useInputLabeling,
} from "frappe-ui/experimental";
// @ts-ignore — vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import type { GridCellSlotProps, GridColumn, GridEmits } from "./types";

// Mirrors frappe-ui's `FrappeUIError` (an `Error` whose `messages?: string[]`
// render as stacked lines). Declared locally — the type isn't re-exported from
// `frappe-ui/experimental` — and is structurally compatible with what the composable
// expects.
interface GridError extends Error {
	messages?: string[];
}

const props = defineProps<{
	/** Columns to render, in order. */
	columns: T[];
	/** Disable structural actions (add/delete/reorder/select) and render read-only. */
	disabled?: boolean;
	/** Optional heading shown above the grid. */
	label?: string;
	/** Helper text rendered below the grid. Hidden while an error is shown. */
	description?: string;
	/** Validation error below the grid: a string, or an `Error` with `messages[]`. */
	error?: string | GridError;
	/** Renders a `*` next to the label. */
	required?: boolean;
}>();

const emit = defineEmits<GridEmits>();

// Canonical labeling state: stable ids, error parsing, hide-description-on-error,
// plus the aria associations (`labelledBy`/`describedBy`) and `dataAttrs` the
// wrapper applies as a `role="group"` region. `disabled` feeds `data-disabled`.
const {
	labelId,
	descriptionId,
	errorMessageId,
	labelledBy,
	describedBy,
	hasError,
	errorLines,
	showDescription,
	dataAttrs,
} = useInputLabeling(props, { disabled: () => props.disabled });

// Rows array. The slot's `update` writes it live; `commit` also emits `change`.
const rows = defineModel<Record<string, any>[]>({ default: () => [] });

defineSlots<{
	/** Render/edit one cell. Falls back to plain text when not provided. */
	cell(props: GridCellSlotProps<T>): any;
}>();

// Per-column track widths: `null` = flexible (`1fr`), a number = fixed px. Seeded
// from the column's `width`, overridden by a drag. Re-seeding on a columns change
// keeps existing drags (the drag wins over `width`) and adds/drops by index.
const MIN_COL_WIDTH = 48;
const colWidths = ref<(number | null)[]>([]);
watch(
	() => props.columns,
	(cols) => {
		colWidths.value = Array.from(
			{ length: cols.length },
			(_, i) => colWidths.value[i] ?? cols[i]?.width ?? null
		);
	},
	{ immediate: true }
);

// Header and rows are one css grid spanning every column, so there's no flex seam.
// A field track is `minmax(0, 1fr)` while flexible and a fixed `${w}px` once resized
// — fixed (not `minmax(w, 1fr)`) so a resized column stays put and can shrink.
const FIXED_COL = "2.5rem"; // checkbox / `#` / edit — matches `w-10`
const templateColumns = computed(() => {
	const fields = colWidths.value.map((w) => (w == null ? "minmax(0, 1fr)" : `${w}px`));
	const lead = props.disabled ? [FIXED_COL] : [FIXED_COL, FIXED_COL]; // (checkbox) + `#`
	return [...lead, ...fields, FIXED_COL].join(" "); // + edit
});

// Floor the grid box at the sum of fixed tracks + resized field widths, so the
// row/header backgrounds span the full content instead of stopping at the viewport
// when resized columns overflow. When columns fit, the `1fr` fields still fill it.
const gridMinWidth = computed(() => {
	const fixedCount = (props.disabled ? 1 : 2) + 1; // lead tracks + edit
	const fieldPx = colWidths.value.reduce<number>((sum, w) => sum + (w ?? 0), 0);
	return `calc(${fixedCount * 2.5}rem + ${fieldPx}px)`;
});

// Sticky offset for the `#` column: after the checkbox column when selection is on,
// else flush left. Inline style (not a `left-*` utility) so the JIT can't drop it.
const SIDE_COL_WIDTH = "2.5rem";
const numberColLeft = computed(() => (props.disabled ? "0" : SIDE_COL_WIDTH));

// Width of the frozen-left region the left shadow hugs: `#` alone, plus the
// checkbox column when selection is on. (The right shadow hugs the edit column.)
const leftShadowOffset = computed(() => (props.disabled ? "2.5rem" : "5rem"));

// Show each side's shadow while there's content scrolled off that way, so it's clear
// the grid pans. The `ceil()` epsilon absorbs sub-pixel rounding at the far right.
const scroller = ref<HTMLElement | null>(null);
const canScrollLeft = ref(false);
const canScrollRight = ref(false);
function updateScrollShadows() {
	const el = scroller.value;
	if (!el) return;
	canScrollLeft.value = el.scrollLeft > 0;
	canScrollRight.value = Math.ceil(el.scrollLeft + el.clientWidth) < el.scrollWidth;
}

let resizeObserver: ResizeObserver | null = null;
onMounted(() => {
	updateScrollShadows();
	resizeObserver = new ResizeObserver(updateScrollShadows);
	if (scroller.value) resizeObserver.observe(scroller.value);
});
onBeforeUnmount(() => resizeObserver?.disconnect());

// scrollWidth changes after the DOM updates, so recompute on the next tick.
watch([templateColumns, () => rows.value.length], () => nextTick(updateScrollShadows));

// Drag-to-resize: seed `startWidth` from the cell's rendered px width so the first
// drag off a flexible column doesn't jump. Listeners on `window` so the drag
// survives the pointer leaving the thin handle.
const resizingIndex = ref<number | null>(null);
let startX = 0;
let startWidth = 0;

function startResize(index: number, e: MouseEvent) {
	const cell = (e.currentTarget as HTMLElement).parentElement;
	if (!cell) return;
	resizingIndex.value = index;
	startX = e.clientX;
	startWidth = cell.offsetWidth;
	window.addEventListener("mousemove", onResize);
	window.addEventListener("mouseup", stopResize);
	e.preventDefault(); // don't start a text selection during the drag
}

function onResize(e: MouseEvent) {
	if (resizingIndex.value == null) return;
	const next = Math.max(MIN_COL_WIDTH, startWidth + (e.clientX - startX));
	const widths = colWidths.value.slice();
	widths[resizingIndex.value] = next;
	colWidths.value = widths;
}

function stopResize() {
	resizingIndex.value = null;
	window.removeEventListener("mousemove", onResize);
	window.removeEventListener("mouseup", stopResize);
}

onBeforeUnmount(stopResize);

// One alignment drives both the header label and the cells. `text-align` is
// inherited, so it flows down to the embedded control's text and the plain fallback.
function alignClass(align: GridColumn["align"]): string {
	if (align === "right") return "text-right";
	if (align === "center") return "text-center";
	return "text-left";
}

// Stable identity per row object (rows have no guaranteed id), minted in a WeakMap.
// Used for `v-for`/Draggable keys and selection, both surviving reorder/delete/edit
// since row objects are mutated in place, never replaced.
let uid = 0;
const rowKeys = new WeakMap<object, string>();
function keyOf(row: Record<string, any>): string {
	let key = rowKeys.get(row);
	if (!key) {
		key = `r${uid++}`;
		rowKeys.set(row, key);
	}
	return key;
}

// Selection by stable key, so it tracks rows across reorder/delete/edit.
const selected = ref(new Set<string>());
const selectedCount = computed(() => {
	// `rows` is the source of truth — count only keys still present.
	let n = 0;
	for (const row of rows.value) if (selected.value.has(keyOf(row))) n++;
	return n;
});
const allSelected = computed(
	() => rows.value.length > 0 && rows.value.every((row) => selected.value.has(keyOf(row)))
);

function isSelected(row: Record<string, any>): boolean {
	return selected.value.has(keyOf(row));
}
// Set membership from the emitted `checked`, NOT a blind toggle: frappe-ui's
// Checkbox emits `update:modelValue` twice per click, which would cancel a toggle.
// The idempotent set makes the double emit harmless (same for `toggleAll`).
function setRow(row: Record<string, any>, checked: boolean) {
	const key = keyOf(row);
	const next = new Set(selected.value);
	checked ? next.add(key) : next.delete(key);
	selected.value = next;
}
function toggleAll(checked: boolean) {
	selected.value = checked ? new Set(rows.value.map(keyOf)) : new Set();
}

// Live edits mutate the row IN PLACE: keeping array/row identities stable stops
// vuedraggable from reconciling the row DOM and stealing focus on each keystroke.
// The row is shared by reference with the parent, so the write is visible without a
// model reassignment. Structural ops below build a new array — no focused cell there.
function updateCell(index: number, col: T, value: any) {
	rows.value[index][col.fieldname] = value;
}

function commitCell(index: number, col: T, value: any) {
	rows.value[index][col.fieldname] = value;
	emit("change", rows.value);
}

function addRow() {
	const next = [...rows.value, {}];
	rows.value = next;
	emit("change", next);
}

function deleteSelected() {
	const next = rows.value.filter((row) => !selected.value.has(keyOf(row)));
	rows.value = next;
	selected.value = new Set();
	emit("change", next);
}

// Draggable hands back the reordered array (same row objects, so keys/selection
// survive). Forward it through the model and `change`.
function reorder(next: Record<string, any>[]) {
	rows.value = next;
	emit("change", next);
}

// In a read-only grid a row click opens the dialog (cells are `pointer-events-none`,
// so the click reaches the row). Editable grids keep inline editing — only the edit
// button opens the dialog there.
function onRowClick(row: Record<string, any>, index: number) {
	if (props.disabled) emit("edit", { row, index });
}
</script>

<style scoped>
/* Strip each control's chrome (border, radius, background, shadow) so a row reads
 * as a flat table, not a stack of bordered inputs.
 * `[data-slot="trigger"]` is frappe-ui's stable hook for the Combobox/Select/
 * Autocomplete/MultiSelect trigger (a `div`, not a `button`), so it needs targeting. */
.grid-cell :deep(input:not([type="checkbox"])),
.grid-cell :deep(textarea),
.grid-cell :deep(select),
.grid-cell
	:deep(button:not([data-slot="clear"]):not([data-slot="redirect"]):not([data-slot="edit"])),
.grid-cell :deep(.combobox),
.grid-cell :deep([data-slot="trigger"]) {
	border: none;
	border-radius: 0;
	background-color: var(--surface-base);
	box-shadow: none;
	min-height: 34px;
}

/* Text-like controls (and the trigger) fill the cell; compact controls
 * (checkbox/rating buttons) keep their natural size so they aren't stretched. */
.grid-cell :deep(input:not([type="checkbox"])),
.grid-cell :deep(textarea),
.grid-cell :deep(select),
.grid-cell :deep([data-slot="trigger"]) {
	width: 100%;
}

/* The trigger is `inline-flex` by default — make it stretch to the cell width. */
.grid-cell :deep([data-slot="trigger"]) {
	display: flex;
}

/* Controls reset their own `text-align`, so the value text needs an explicit rule
 * to follow the column's alignment. */
.grid-cell.text-right :deep(input:not([type="checkbox"])),
.grid-cell.text-right :deep(textarea) {
	text-align: right;
}

.grid-cell.text-center :deep(input:not([type="checkbox"])),
.grid-cell.text-center :deep(textarea) {
	text-align: center;
}

/* Single-row textarea inside the grid (the dialog form keeps the full height). */
.grid-cell :deep(textarea) {
	height: 34px;
	min-height: 34px;
	resize: none;
}

/* Kill the rubber-band when panning the grid. X axis only, else it would also
 * swallow vertical wheel scrolling and lock the page. Set directly so the JIT keeps it. */
.grid-scroller {
	overscroll-behavior-x: none;
}

/* One continuous gradient strip per side (vs. per-cell box-shadows, which seam at
 * row borders). Above the cells but `pointer-events: none`; fades via `is-visible`. */
.grid-scroll-shadow {
	position: absolute;
	top: 0;
	bottom: 0;
	width: 16px;
	z-index: 20;
	pointer-events: none;
	opacity: 0;
	transition: opacity 0.15s ease;
}

.grid-scroll-shadow.is-visible {
	opacity: 1;
}

.grid-scroll-shadow-left {
	background: linear-gradient(to right, rgb(0 0 0 / 0.05), transparent);
}

.grid-scroll-shadow-right {
	background: linear-gradient(to left, rgb(0 0 0 / 0.05), transparent);
}

/* Resize handle: thin hit-area on the header cell's right edge; the line shows on
 * hover/drag to signal the grab target. */
.grid-col-resize {
	position: absolute;
	top: 0;
	right: 0;
	bottom: 0;
	width: 7px;
	z-index: 3;
	cursor: col-resize;
	user-select: none;
}

.grid-col-resize::after {
	content: "";
	position: absolute;
	top: 0;
	right: 0;
	bottom: 0;
	width: 2px;
	background-color: var(--outline-gray-3);
	opacity: 0;
}

.grid-col-resize:hover::after,
.grid-col-resize.is-resizing::after {
	opacity: 1;
}

/* The cell is the focus ring for its control. Drawn as an overlay pseudo-element,
 * not an inset shadow, which the control's own background would paint over. */
.grid-cell {
	position: relative;
}

.grid-cell:focus-within::after {
	content: "";
	position: absolute;
	inset: 0;
	z-index: 2;
	pointer-events: none;
	box-shadow: inset 0 0 0 1px var(--outline-gray-3);
}

/* Suppress only the primary control's own ring so it doesn't double up with the
 * cell ring. Sub-controls (e.g. Link's clear/redirect/edit) keep their native ring. */
.grid-cell :deep(input:not([type="checkbox"]):focus),
.grid-cell :deep(textarea:focus),
.grid-cell :deep(select:focus),
.grid-cell :deep([data-slot="trigger"]:focus),
.grid-cell :deep([data-slot="trigger"]:focus-within),
.grid-cell :deep([data-slot="trigger"][data-state="open"]) {
	box-shadow: none !important;
	outline: none !important;
}

/* Read-only grid: cells are `pointer-events-none`, which also smothers a readonly
 * Link's redirect/edit buttons. Restore pointer events on just those two and reveal
 * them on ROW hover (the pointer falls through to the row). They `@click.stop`. */
.grid-disabled .grid-cell :deep([data-slot="redirect"]),
.grid-disabled .grid-cell :deep([data-slot="edit"]) {
	pointer-events: auto;
}

.grid-disabled .grid-row:hover :deep([data-slot="redirect"]),
.grid-disabled .grid-row:hover :deep([data-slot="edit"]) {
	display: grid;
}
</style>
