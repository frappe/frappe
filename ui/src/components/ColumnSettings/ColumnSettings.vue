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
				@click="togglePopover"
			/>
		</template>
		<template #body>
			<div
				class="my-2 min-w-40 rounded-lg bg-surface-elevation-2 shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none"
			>
				<!-- List mode: reorder / edit / remove the shown columns, add more. -->
				<div v-if="editIndex === null" class="min-w-60 p-2">
					<Draggable
						v-if="model.length"
						class="mb-2 flex flex-col gap-1"
						:modelValue="model"
						:item-key="(c) => c.fieldname"
						handle=".column-drag-handle"
						tag="div"
						@update:modelValue="reorder"
					>
						<template #item="{ element: column, index: i }">
							<div
								class="flex items-center justify-between gap-2 rounded px-1 py-1 text-base text-ink-gray-8 hover:bg-surface-gray-2"
							>
								<div class="flex min-w-0 items-center gap-2">
									<div
										class="column-drag-handle flex h-5 w-5 items-center justify-center"
									>
										<span
											class="lucide-grip-vertical size-4 cursor-grab text-ink-gray-5"
											aria-hidden="true"
										/>
									</div>
									<div class="truncate">{{ column.label }}</div>
								</div>
								<div class="flex items-center gap-0.5">
									<Button
										variant="ghost"
										icon="lucide-pencil"
										@click="editColumn(i)"
									/>
									<Button
										variant="ghost"
										icon="lucide-x"
										@click="removeColumn(i)"
									/>
								</div>
							</div>
						</template>
					</Draggable>
					<div v-else class="mb-2 flex h-7 items-center px-2 text-sm text-ink-gray-5">
						Empty - Add a column to show
					</div>
					<div class="border-t border-outline-elevation-2 pt-2">
						<!-- Remount per add: the combobox's internal model would otherwise
						     retain the picked field and show it instead of "Add Column". -->
						<Combobox
							:key="model.length"
							trigger="button"
							variant="ghost"
							:options="addableOptions"
							:modelValue="null"
							placeholder="Add Column"
							@update:selectedOption="addColumn"
						>
							<template #prefix>
								<span class="lucide-plus size-4" aria-hidden="true" />
							</template>
						</Combobox>
					</div>
				</div>

				<!-- Edit mode: inline label/width edit with a local cancel buffer. -->
				<div v-else class="flex w-60 flex-col gap-3 p-3">
					<FormControl
						v-model="draft.label"
						type="text"
						size="md"
						label="Label"
						placeholder="First Name"
					/>
					<FormControl
						v-model="draft.width"
						type="text"
						size="md"
						label="Width"
						placeholder="Auto"
						description="Auto by default; set a number, pixel or rem (eg. 3, 30px, 10rem)"
					/>
					<div class="flex gap-2 border-t border-outline-elevation-2 pt-3">
						<Button
							class="flex-1"
							variant="subtle"
							label="Cancel"
							@click="cancelEdit"
						/>
						<Button class="flex-1" variant="solid" label="Update" @click="saveEdit" />
					</div>
				</div>
			</div>
		</template>
	</Popover>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Button, Combobox, FormControl, Popover } from "frappe-ui";
// @ts-ignore — vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { getColumnOptions } from "./getColumnOptions";
import type { Column, ColumnOption } from "./types";

const props = withDefaults(defineProps<{ doctype: string; hideLabel?: boolean }>(), {
	hideLabel: false,
});

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

// Inline label/width edit holds a component-local draft so a Cancel discards the
// edits without touching the model; only Update writes them back. An empty width
// clears the override (the column goes back to auto — serialize flexes it to fill).
const editIndex = ref<number | null>(null);
const draft = ref<{ label: string; width: string }>({ label: "", width: "" });

function editColumn(index: number) {
	const column = model.value[index];
	draft.value = { label: column.label, width: column.width ?? "" };
	editIndex.value = index;
}

function cancelEdit() {
	editIndex.value = null;
}

function saveEdit() {
	const index = editIndex.value;
	if (index === null) return;
	const width = draft.value.width.trim();
	model.value = model.value.map((c, i) =>
		i === index ? { ...c, label: draft.value.label, width: width || undefined } : c
	);
	editIndex.value = null;
}
</script>
