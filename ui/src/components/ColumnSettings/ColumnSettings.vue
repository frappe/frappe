<!--
  ColumnSettings — a controlled, meta-driven list-view control. Its `v-model` is
  an ordered list of Columns (`{ fieldname, label, width? }[]`): presence means
  shown, array order is display order, and `width` is the slice a column resize
  co-writes (the host wires that sync via `useListView`, see ADR-0006). The
  control owns no data resource and never persists — changes go live into the
  model with no apply button; reset / reset-to-defaults are host concerns.

  Field Options come from the doctype's Meta (`useDoctypeMeta` → `getColumnOptions`),
  not a CRM endpoint. `align`/`type`/`options` are derived from Meta at serialize
  time (`serializeColumns`), never stored on a Column.

  Field picker uses frappe-ui's `Combobox` (Autocomplete is deprecated upstream,
  per SortBy); drag-reorder uses `vuedraggable`; icons are lucide names.
-->
<template>
	<Popover placement="bottom-end">
		<template #target="{ togglePopover }">
			<Button
				:label="hideLabel ? undefined : 'Columns'"
				:icon="hideLabel ? 'lucide-columns-3' : undefined"
				:iconLeft="!hideLabel ? 'lucide-columns-3' : undefined"
				@click="
					confirmingReset = false;
					togglePopover();
				"
			/>
		</template>
		<template #body>
			<div
				class="my-2 min-w-40 rounded-lg bg-surface-elevation-2 shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none"
			>
				<!-- Reorder / rename / remove the shown columns, add more. Width is
				     not edited here — drag-resize in the table owns it (ADR-0006). -->
				<div class="min-w-60 p-2">
					<Draggable
						v-if="model.length"
						class="mb-3 flex flex-col gap-2"
						:modelValue="model"
						:item-key="(c) => c.fieldname"
						handle=".column-drag-handle"
						tag="div"
						@update:modelValue="reorder"
					>
						<template #item="{ element: column, index: i }">
							<div class="flex items-center gap-1">
								<div
									class="column-drag-handle flex h-7 w-7 shrink-0 items-center justify-center"
								>
									<span
										class="lucide-grip-vertical size-4 cursor-grab text-ink-gray-5"
										aria-hidden="true"
									/>
								</div>
								<!-- The label is always a TextInput: read-only at rest, click to
								     rename. Editing writes a local `draft` (so Esc reverts and
								     typing doesn't churn the dragged list); commit on Enter/blur. -->
								<TextInput
									:ref="editIndex === i ? focusInput : undefined"
									size="sm"
									class="min-w-0 flex-1"
									:readonly="editIndex !== i"
									:modelValue="editIndex === i ? draft : column.label"
									@click="editColumn(i)"
									@update:modelValue="(value: string) => (draft = value)"
									@keydown.enter.prevent="commitEdit"
									@keydown.esc.prevent="cancelEdit"
									@blur="commitEdit"
								/>
								<Button variant="ghost" icon="lucide-x" @click="removeColumn(i)" />
							</div>
						</template>
					</Draggable>
					<div v-else class="mb-3 flex h-7 items-center px-3 text-sm text-ink-gray-5">
						Empty - Add a column to show
					</div>
					<div class="flex items-center justify-between gap-2">
						<!-- Remount per add: the combobox's internal model would otherwise
						     retain the picked field and show it instead of "Add Column". -->
						<Combobox
							:key="model.length"
							trigger="button"
							variant="ghost"
							:class="canReset ? undefined : 'flex-1'"
							:options="addableOptions"
							:modelValue="null"
							placeholder="Add Column"
							@update:selectedOption="addColumn"
						>
							<template #prefix>
								<span class="lucide-plus size-4" aria-hidden="true" />
							</template>
						</Combobox>
						<!-- Reset to the Meta defaults. The host owns the defaults (ADR-0006),
						     so this only emits; `canReset` hides it when nothing to undo. The
						     first click arms an inline confirm, the second emits. -->
						<Button
							v-if="canReset"
							:class="confirmingReset ? undefined : '!text-ink-gray-5'"
							:variant="confirmingReset ? 'subtle' : 'ghost'"
							:theme="confirmingReset ? 'red' : 'gray'"
							:label="confirmingReset ? 'Confirm Reset' : 'Reset'"
							@click="onResetClick"
						/>
					</div>
				</div>
			</div>
		</template>
	</Popover>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { Button, Combobox, Popover, TextInput } from "frappe-ui";
// @ts-ignore — vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { getColumnOptions } from "./getColumnOptions";
import type { Column, ColumnOption } from "./types";

const props = withDefaults(
	defineProps<{ doctype: string; hideLabel?: boolean; canReset?: boolean }>(),
	{
		hideLabel: false,
		canReset: false,
	}
);

// Reset is the host's job (ADR-0006): the controlled popover holds no defaults, so
// it only signals intent and the host restores them.
const emit = defineEmits<{ reset: [] }>();

// Reset discards every customization (columns shown, order, labels, widths), so
// it confirms inline: the first click arms the button (red "Confirm Reset"), the
// second emits. Re-opening the popover disarms it (see the trigger's @click).
const confirmingReset = ref(false);

function onResetClick() {
	if (confirmingReset.value) {
		emit("reset");
		confirmingReset.value = false;
	} else {
		confirmingReset.value = true;
	}
}

// `v-model` is the ordered list of Columns. The component is controlled: it only
// reads and re-emits this array, never a data resource and never persistence.
const model = defineModel<Column[]>({ default: () => [] });

const { meta } = useDoctypeMeta(props.doctype);

// Field Options derived client-side from Meta — no CRM endpoint.
const allOptions = computed<ColumnOption[]>(() => getColumnOptions(meta.value?.fields ?? []));

// The "add" picker offers every column not already shown.
const addableOptions = computed<ColumnOption[]>(() => {
	const shown = new Set(model.value.map((c) => c.fieldname));
	return allOptions.value.filter((o) => !shown.has(o.fieldname));
});

// Combobox's `update:selectedOption` hands back the chosen option (or null on
// clear); its `value` is the fieldname. Strings are tolerated defensively.
function fieldnameOf(option: unknown): string | null {
	if (!option) return null;
	if (typeof option === "string") return option;
	const o = option as { value?: string; fieldname?: string };
	return o.value ?? o.fieldname ?? null;
}

function addColumn(option: unknown) {
	const fieldname = fieldnameOf(option);
	if (!fieldname || model.value.some((c) => c.fieldname === fieldname)) return;
	const label = allOptions.value.find((o) => o.fieldname === fieldname)?.label ?? fieldname;
	model.value = [...model.value, { fieldname, label }];
}

function removeColumn(index: number) {
	model.value = model.value.filter((_, i) => i !== index);
}

function reorder(next: Column[]) {
	model.value = next;
}

// Inline rename holds a component-local draft so Esc discards the edit without
// touching the model; only commit writes it back. Width is never edited here —
// drag-resize in the table owns it (ADR-0006). An empty/whitespace label is
// rejected so a column never loses its header.
const editIndex = ref<number | null>(null);
const draft = ref("");

function editColumn(index: number) {
	// Clicking the already-active input must not reset the in-progress draft.
	if (editIndex.value === index) return;
	draft.value = model.value[index].label;
	editIndex.value = index;
}

// Focus and select the rename input the moment it mounts, so typing replaces
// the current label. TextInput exposes its native input as `.el`.
function focusInput(component: unknown) {
	const el = (component as { el?: HTMLInputElement } | null)?.el;
	if (el instanceof HTMLInputElement) {
		nextTick(() => {
			el.focus();
			el.select();
		});
	}
}

function cancelEdit() {
	editIndex.value = null;
}

// Enter and blur both commit; whichever fires first clears editIndex, so the
// other becomes a no-op.
function commitEdit() {
	const index = editIndex.value;
	if (index === null) return;
	const label = draft.value.trim();
	editIndex.value = null;
	if (!label || label === model.value[index].label) return;
	model.value = model.value.map((c, i) => (i === index ? { ...c, label } : c));
}
</script>
