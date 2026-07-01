<!--
  SortBy — a controlled, meta-driven list-view control. Its `v-model` is a list of
  Sorts (`{ fieldname, direction }[]`); it owns no data resource and never touches
  CRM's Views concept. The host serializes the array to a Frappe `order_by` string
  (via the exported `serializeOrderBy`) and refetches.

  Field Options come from the doctype's Meta (`useDoctypeMeta` → `getSortOptions`),
  not a CRM endpoint. The empty state is purely literal: an empty array renders the
  plain "Sort" button — any "default = unsorted" rule belongs to the host.

  Field pickers use frappe-ui's `Combobox` (Autocomplete is deprecated upstream);
  drag-reorder uses `vuedraggable`; icons are lucide names.
-->
<template>
	<!-- Empty: a plain "Sort" button that opens the field picker. A custom
	     #trigger renders a real Button (matching the non-empty trigger, so it can
	     honor `hideLabel`) — full ink, no dropdown chevron, no placeholder hacks —
	     and ComboboxAnchor auto-wires the open click. -->
	<Combobox
		v-if="!model.length"
		:options="addableOptions"
		:modelValue="null"
		@update:selectedOption="addSort"
	>
		<template #trigger>
			<Button
				:label="hideLabel ? undefined : 'Sort'"
				:icon="hideLabel ? 'lucide-arrow-up-down' : undefined"
				:iconLeft="!hideLabel ? 'lucide-arrow-up-down' : undefined"
			/>
		</template>
	</Combobox>

	<!-- Non-empty: the sort popover (single-sort compact / multi-sort badge). -->
	<Popover v-else placement="bottom-end">
		<template #target="{ isOpen, togglePopover }">
			<Button
				v-if="model.length > 1"
				:label="'Sort'"
				:icon="hideLabel ? 'lucide-arrow-up-down' : undefined"
				:iconLeft="!hideLabel ? 'lucide-arrow-up-down' : undefined"
				@click="togglePopover"
			>
				<template #suffix>
					<div
						class="flex h-5 w-5 items-center justify-center rounded-[5px] bg-surface-base pt-px text-xs-medium text-ink-gray-8 shadow-sm"
					>
						{{ model.length }}
					</div>
				</template>
			</Button>
			<div v-else class="flex items-center justify-center">
				<Button
					class="relative rounded-r-none border-r focus-visible:z-10"
					:icon="directionIcon(model[0].direction)"
					@click.stop="toggleDirection(0)"
				/>
				<Button
					:label="firstSortLabel"
					class="relative shrink-0 rounded-l-none [&_svg]:text-ink-gray-5 focus-visible:z-10"
					:iconRight="isOpen ? 'lucide-chevron-up' : 'lucide-chevron-down'"
					@click.stop="togglePopover"
				/>
			</div>
		</template>
		<template #body="{ close }">
			<div
				class="my-2 min-w-40 rounded-lg bg-surface-elevation-2 shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none"
			>
				<div class="min-w-60 p-2">
					<Draggable
						v-if="model.length"
						class="mb-3 flex flex-col gap-2"
						:modelValue="model"
						:item-key="(s) => s.fieldname"
						handle=".sort-drag-handle"
						tag="div"
						@update:modelValue="reorder"
					>
						<template #item="{ element: sort, index: i }">
							<div class="flex items-center gap-1">
								<div
									class="sort-drag-handle flex h-7 w-7 items-center justify-center"
								>
									<span
										class="lucide-grip-vertical size-4 cursor-grab text-ink-gray-5"
										aria-hidden="true"
									/>
								</div>
								<div class="flex flex-1">
									<Button
										size="md"
										class="relative rounded-r-none border-r focus-visible:z-10"
										:icon="directionIcon(sort.direction)"
										@click="toggleDirection(i)"
									/>
									<Combobox
										class="relative flex-1 rounded-l-none focus-within:z-10"
										trigger="button"
										variant="subtle"
										size="md"
										:modelValue="sort.fieldname"
										:options="optionsFor(sort.fieldname)"
										placeholder="Select field"
										@update:selectedOption="(o) => updateSort(o, i)"
									/>
								</div>
								<Button variant="ghost" icon="lucide-x" @click="removeSort(i)" />
							</div>
						</template>
					</Draggable>
					<div v-else class="mb-3 flex h-7 items-center px-3 text-sm text-ink-gray-5">
						Empty - Choose a field to sort by
					</div>
					<div class="flex items-center justify-between gap-2">
						<!-- A custom #trigger renders the same ghost Button as "Clear Sort"
						     beside it (gray-5, `+` icon, no chevron). The label is static, so
						     the old per-add remount (`:key`) and the placeholder / chevron CSS
						     hacks are no longer needed. -->
						<Combobox
							:options="addableOptions"
							:modelValue="null"
							@update:selectedOption="addSort"
						>
							<template #trigger>
								<Button
									class="!text-ink-gray-5"
									variant="ghost"
									label="Add Sort"
									iconLeft="lucide-plus"
								/>
							</template>
						</Combobox>
						<Button
							v-if="model.length"
							class="!text-ink-gray-5"
							variant="ghost"
							:label="'Clear Sort'"
							@click="clearSort(close)"
						/>
					</div>
				</div>
			</div>
		</template>
	</Popover>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, Combobox, Popover } from "frappe-ui";
// @ts-ignore — vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { getSortOptions } from "./getSortOptions";
import type { Sort, SortOption } from "./types";

const props = withDefaults(defineProps<{ doctype: string; hideLabel?: boolean }>(), {
	hideLabel: false,
});

// `v-model` is the ordered list of Sorts. The component is controlled: it only
// reads and re-emits this array, never a data resource.
const model = defineModel<Sort[]>({ default: () => [] });

const { meta } = useDoctypeMeta(props.doctype);

// Field Options derived client-side from Meta — no CRM endpoint.
const allOptions = computed<SortOption[]>(() => getSortOptions(meta.value?.fields ?? []));

// Options offered by the "add" pickers: every sortable field not already chosen.
const addableOptions = computed<SortOption[]>(() => {
	const chosen = new Set(model.value.map((s) => s.fieldname));
	return allOptions.value.filter((o) => !chosen.has(o.fieldname));
});

// For an in-list row's picker: addable fields plus the row's own current field,
// so the selected value stays selectable.
function optionsFor(fieldname: string): SortOption[] {
	const own = allOptions.value.find((o) => o.fieldname === fieldname);
	return own ? [own, ...addableOptions.value] : addableOptions.value;
}

function labelFor(fieldname: string): string {
	return allOptions.value.find((o) => o.fieldname === fieldname)?.label ?? fieldname;
}

const firstSortLabel = computed(() =>
	model.value.length ? labelFor(model.value[0].fieldname) : "Sort"
);

function directionIcon(direction: Sort["direction"]): string {
	return direction === "asc" ? "lucide-arrow-up-z-a" : "lucide-arrow-down-a-z";
}

// Combobox's `update:selectedOption` hands back the chosen option (or null on
// clear); its `value` is the fieldname. Strings are tolerated defensively.
function fieldnameOf(option: unknown): string | null {
	if (!option) return null;
	if (typeof option === "string") return option;
	const o = option as { value?: string; fieldname?: string };
	return o.value ?? o.fieldname ?? null;
}

function addSort(option: unknown) {
	const fieldname = fieldnameOf(option);
	if (!fieldname || model.value.some((s) => s.fieldname === fieldname)) return;
	model.value = [...model.value, { fieldname, direction: "asc" }];
}

function updateSort(option: unknown, index: number) {
	const fieldname = fieldnameOf(option);
	if (!fieldname) return;
	model.value = model.value.map((s, i) =>
		i === index ? { fieldname, direction: s.direction } : s
	);
}

function toggleDirection(index: number) {
	model.value = model.value.map((s, i) =>
		i === index ? { ...s, direction: s.direction === "asc" ? "desc" : "asc" } : s
	);
}

function removeSort(index: number) {
	model.value = model.value.filter((_, i) => i !== index);
}

function reorder(next: Sort[]) {
	model.value = next;
}

function clearSort(close: () => void) {
	model.value = [];
	close();
}
</script>
