<template>
	<div class="flex flex-col gap-2">
		<div v-if="label" class="text-sm text-ink-gray-5">
			{{ label }}
			<span v-if="required" class="text-ink-red-2">*</span>
		</div>

		<div
			v-if="columns.length"
			class="relative overflow-hidden rounded border border-outline-gray-2"
		>
			<!-- Horizontal scroll once resized columns overflow the box; the header
			     and every row share this scroller so they pan together. -->
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
						<Checkbox :modelValue="allSelected" @update:modelValue="toggleAll" />
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
						<span v-if="col.reqd" class="text-ink-red-2">*</span>
						<!-- Drag the right edge to resize this column. Sits over the column
						     border; the header and every row follow because they share the
						     same `templateColumns`. -->
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
							class="grid items-stretch border-t border-outline-gray-2 bg-surface-white"
							:style="{
								gridTemplateColumns: templateColumns,
								minWidth: gridMinWidth,
							}"
						>
							<div
								v-if="!disabled"
								class="sticky left-0 z-10 flex items-center justify-center border-r border-outline-gray-2 bg-surface-white"
								:style="{ left: '0' }"
							>
								<Checkbox
									:modelValue="isSelected(row)"
									@update:modelValue="(checked: boolean) => setRow(row, checked)"
								/>
							</div>
							<div
								class="sticky z-10 flex items-center justify-center border-r border-outline-gray-2 bg-surface-white py-2 text-sm text-ink-gray-7"
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
									{ 'border-r border-outline-gray-2': i < columns.length - 1 },
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
								class="sticky right-0 z-10 flex items-center justify-center border-l border-outline-gray-2 bg-surface-white"
								:style="{ right: '0' }"
							>
								<Button
									variant="ghost"
									icon="lucide-pencil"
									:tooltip="'Edit Row'"
									@click="emit('edit', { row, index: rowIndex })"
								/>
							</div>
						</div>
					</template>
				</Draggable>

				<div
					v-else
					class="border-t border-outline-gray-2 p-4 text-center text-sm text-ink-gray-4"
				>
					No rows
				</div>
			</div>

			<!-- Scroll affordance. Two full-height strips pinned just inside the frozen
			     columns (so they fall over the scrolling content, not the frozen cells)
			     and OUTSIDE the scroller, so they stay put while the grid pans. One
			     continuous gradient per side — not a per-cell shadow, which segments at
			     every row border. -->
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

		<!-- No columns to render (e.g. child meta absent). -->
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
	</div>
</template>

<script setup lang="ts" generic="T extends GridColumn">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Button, Checkbox } from "frappe-ui";
// @ts-ignore — vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import type { GridCellSlotProps, GridColumn, GridEmits } from "./types";

const props = defineProps<{
	/** Columns to render, in order. */
	columns: T[];
	/** Disable structural actions (add/delete/reorder/select) and render read-only. */
	disabled?: boolean;
	/** Optional heading shown above the grid. */
	label?: string;
	/** Renders a `*` next to the label. */
	required?: boolean;
}>();

const emit = defineEmits<GridEmits>();

// `v-model` for the rows array. The slot's `update` writes it (live sync);
// `commit` additionally emits `change`.
const rows = defineModel<Record<string, any>[]>({ default: () => [] });

defineSlots<{
	/** Render/edit one cell. Falls back to plain text when not provided. */
	cell(props: GridCellSlotProps<T>): any;
}>();

// Per-column track widths. `null` = flexible (shares leftover space as `1fr`); a
// number = a fixed px width set by dragging the column's right edge. Kept in sync
// with the column count by index — an unseen column starts flexible, a dropped one
// falls off. The header and every row bind this same template, so a resize moves
// both in lockstep.
const MIN_COL_WIDTH = 48;
const colWidths = ref<(number | null)[]>([]);
watch(
	() => props.columns.length,
	(n) => {
		colWidths.value = Array.from({ length: n }, (_, i) => colWidths.value[i] ?? null);
	},
	{ immediate: true }
);

// The header and every row are a SINGLE css grid spanning all columns — the fixed
// checkbox/`#`/edit tracks plus the field tracks — so every column is a contiguous
// track with no flex seam that could open a gap before the (sticky) edit column.
// A field track is `minmax(0, 1fr)` while flexible (shares leftover space so the
// row always fills the box, no dead gap) and a *fixed* `${w}px` once resized. The
// fixed width is deliberate: a resized column must stay exactly where the user drags
// it, including narrower than its old flex size — `minmax(w, 1fr)` would spring it
// back up to its `1fr` share whenever free space exists, making it un-shrinkable.
const FIXED_COL = "2.5rem"; // checkbox / `#` / edit — matches `w-10`
const templateColumns = computed(() => {
	const fields = colWidths.value.map((w) => (w == null ? "minmax(0, 1fr)" : `${w}px`));
	const lead = props.disabled ? [FIXED_COL] : [FIXED_COL, FIXED_COL]; // (checkbox) + `#`
	return [...lead, ...fields, FIXED_COL].join(" "); // + edit
});

// Floor the grid box at the sum of every track's base size — the fixed
// checkbox/`#`/edit tracks (2.5rem each) plus each resized field's px width
// (flexible fields floor at 0). Block grids size their box to the *scroller's*
// width, so without this the box (and its row/header backgrounds) would only cover
// the viewport: scroll past it once the resized columns overflow and the uncovered
// tail shows through as a white gap. With the floor, the box grows to span the full
// content, so the backgrounds reach the end. When the columns fit, the floor is
// below the container width and the `1fr` fields still fill it.
const gridMinWidth = computed(() => {
	const fixedCount = (props.disabled ? 1 : 2) + 1; // lead tracks + edit
	const fieldPx = colWidths.value.reduce<number>((sum, w) => sum + (w ?? 0), 0);
	return `calc(${fixedCount * 2.5}rem + ${fieldPx}px)`;
});

// Sticky-offset for the `#` column: it sits flush after the checkbox column
// (`w-10` = 2.5rem) when selection is enabled, else at the left edge. Set as an
// inline style rather than a `left-*` utility so it can't be missed by Tailwind's
// JIT — a sticky cell with no `left` silently stops sticking and scrolls away.
const SIDE_COL_WIDTH = "2.5rem";
const numberColLeft = computed(() => (props.disabled ? "0" : SIDE_COL_WIDTH));

// Width of the frozen-left region the left shadow sits flush against: the `#` column
// alone (2.5rem) when selection is off, plus the checkbox column (another 2.5rem)
// when it's on. The right shadow always sits against the lone edit column
// (`SIDE_COL_WIDTH`).
const leftShadowOffset = computed(() => (props.disabled ? "2.5rem" : "5rem"));

// Scroll affordance: the frozen `#` column casts a shadow to its right while there's
// content scrolled off to the left, and the frozen edit column casts one to its left
// while more content sits off to the right — so it's clear the grid pans horizontally
// and which way. Driven by the scroller's position: a tiny ceil() epsilon absorbs
// sub-pixel rounding at the far right so the right shadow actually clears. Recomputed
// on scroll, on container/column resize (ResizeObserver), and whenever the template
// or row count changes the scrollable width.
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

// Layout changes (resize, add/remove rows) alter scrollWidth after the DOM updates,
// so recompute on the next tick.
watch([templateColumns, () => rows.value.length], () => nextTick(updateScrollShadows));

// Drag-to-resize: grab a header cell's right edge and track the pointer. We seed
// `startWidth` from the cell's *rendered* px width so the first drag off a flexible
// (`1fr`) column doesn't jump. Listeners live on `window` so the drag survives the
// pointer leaving the thin handle.
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
	// Stop the handle's mousedown from starting a text selection during the drag.
	e.preventDefault();
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

// One alignment value drives both a column's header label and its cells, so they
// can't drift apart. `text-align` is inherited, so applying it to the cell wrapper
// flows down to the embedded control's text (e.g. a right-aligned number input)
// and to the plain-text fallback alike.
function alignClass(align: GridColumn["align"]): string {
	if (align === "right") return "text-right";
	if (align === "center") return "text-center";
	return "text-left";
}

// Stable identity for each row object: rows are plain data the parent owns (no
// guaranteed `name`/id), so we mint a key per object in a WeakMap. Used for
// `v-for`/Draggable keys *and* selection — both survive reorder/delete/edit
// because the row objects are mutated in place, never replaced. Adding a row
// mints a fresh key; nothing leaks once the row drops.
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
// Drive selection from the checkbox's emitted state (add/remove), NOT a blind
// toggle. frappe-ui's Checkbox emits `update:modelValue` TWICE per click (once
// from its `defineModel` assignment, once from an explicit `emit`), so a toggle
// would fire twice and cancel itself — the row would never stay selected. Setting
// membership from `checked` is idempotent, so the double emit is harmless (same
// reason `toggleAll` works).
function setRow(row: Record<string, any>, checked: boolean) {
	const key = keyOf(row);
	const next = new Set(selected.value);
	checked ? next.add(key) : next.delete(key);
	selected.value = next;
}
function toggleAll(checked: boolean) {
	selected.value = checked ? new Set(rows.value.map(keyOf)) : new Set();
}

// Live cell edits mutate the row IN PLACE — the array and row-object identities
// stay stable, so Draggable's bound list ref never changes and the focused input
// is not re-rendered/remounted. (Reassigning a fresh array + row object on every
// keystroke made vuedraggable reconcile the row DOM via Sortable, stealing focus
// and firing a blur-triggered commit on each keypress.) The value is shared by
// reference with the parent (e.g. FormLayout's doc), so the in-place write is
// visible without a model reassignment. Structural ops below still build a new
// array — there's no focused cell to disturb when adding/deleting/reordering.
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
// survive). Forward it through the model and the intentful change signal.
function reorder(next: Record<string, any>[]) {
	rows.value = next;
	emit("change", next);
}
</script>

<style scoped>
/* Cells own the full width with no padding; the embedded control stays
 * focusable. Strip each control's chrome (border, radius, background, shadow) so
 * a row reads as a flat table, not a stack of bordered inputs. The consumer
 * (e.g. TableField) decides which controls fill vs. center per fieldtype — we
 * only normalise chrome and the single-row height here. */
/* `[data-slot="trigger"]` is frappe-ui's stable hook for the Combobox/Select/
 * Autocomplete/MultiSelect trigger — a `div` (not a `button`) in the editable
 * variant, with the gray `subtle` chrome — so it needs explicit targeting. */
.grid-cell :deep(input:not([type="checkbox"])),
.grid-cell :deep(textarea),
.grid-cell :deep(select),
.grid-cell
	:deep(button:not([data-slot="clear"]):not([data-slot="redirect"]):not([data-slot="edit"])),
.grid-cell :deep(.combobox),
.grid-cell :deep([data-slot="trigger"]) {
	border: none;
	border-radius: 0;
	background-color: var(--surface-white);
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

/* Column alignment reaches the embedded control's text. `text-align` on the cell
 * wrapper aligns the plain-text fallback, but the controls reset their own
 * `text-align`, so the value text (e.g. a number input) needs an explicit rule to
 * follow the column's alignment. */
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

/* Kill the elastic rubber-band at the scroll boundaries (and any chaining to the
 * page) so panning the grid left/right stops cleanly instead of bouncing. Set
 * directly rather than via a utility class so it can't be dropped by the JIT. */
.grid-scroller {
	overscroll-behavior: none;
}

/* Scroll affordance. One continuous gradient strip per side, full height of the box,
 * fading away from the frozen edge it hugs. Sits above the scrolling cells (`z-10`)
 * but is `pointer-events: none` so it never blocks them, and fades in/out with the
 * `is-visible` toggle. A single strip (vs. a per-cell box-shadow) means no seam at
 * the row borders. */
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

/* Column resize handle: a thin hit-area pinned to the header cell's right edge
 * (just inside the border, so the cell's `overflow: hidden` doesn't clip it). The
 * 1px line shows on hover/drag to signal the grab target. */
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

/* The cell itself is the focus indicator for its primary control: a clear ring
 * highlighting all four borders when anything in it is focused. Drawn as an
 * overlay pseudo-element (not an inset box-shadow on the cell) because the
 * control fills the cell with its own background and would paint over an inset
 * shadow. `pointer-events: none` keeps the overlay click-through. */
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

/* Suppress only the *primary* control's own ring (text input / textarea / select
 * / the Combobox trigger), so it doesn't stack with the cell ring into a doubled,
 * rounded outline. Sub-controls keep their native focus ring — notably Link's
 * clear/redirect/edit buttons, which the user tabs to individually. */
.grid-cell :deep(input:not([type="checkbox"]):focus),
.grid-cell :deep(textarea:focus),
.grid-cell :deep(select:focus),
.grid-cell :deep([data-slot="trigger"]:focus),
.grid-cell :deep([data-slot="trigger"]:focus-within),
.grid-cell :deep([data-slot="trigger"][data-state="open"]) {
	box-shadow: none !important;
	outline: none !important;
}
</style>
