<!--
  Filter — a controlled, meta-driven list-view control. Its `v-model` is a list of
  Filter conditions (`{ fieldname, operator, value, field }[]`); it owns no data
  resource and never calls a CRM endpoint. Hosts that store a Frappe filters dict
  convert with the exported `serializeFilters` / `parseFilters`.

  Field Options come from the doctype's Meta (`useDoctypeMeta` → `getFilterableFields`),
  and the per-fieldtype operator table from `getOperators` — both pure ports of CRM's
  `crm.api.doc.get_filterable_fields` + `getOperators` (ADR-0001, ADR-0003).

  The value inputs are the shared `Fields` module's components (ADR-0004), not CRM's
  bespoke Link/Duration/Rating trio. Which control a condition gets — the
  operator-driven swaps as well as the fieldtype ones — is decided by
  `valueControl.ts`, a sibling module rather than this file, so the nested
  ConditionBuilder renders the same inputs from the same rules. Field pickers use
  frappe-ui's `Combobox`; icons are lucide names.
-->
<template>
	<!-- Empty: a plain "Filter" button that opens the field picker (the first
	     picked field seeds a condition and flips to the popover view). A custom
	     #trigger renders a real Button — full ink, no dropdown chevron, no
	     placeholder-recolor hacks — and ComboboxAnchor auto-wires the open click. -->
	<Combobox
		v-if="!model.length"
		:options="allFields"
		:modelValue="null"
		@update:selectedOption="addFilter"
	>
		<template #trigger>
			<Button label="Filter" iconLeft="lucide-list-filter" />
		</template>
	</Combobox>

	<!-- Non-empty: the filter popover with its condition rows. -->
	<Popover v-else ref="popoverRef" placement="bottom-end">
		<template #target="{ togglePopover, close }">
			<div class="flex items-center">
				<Button
					label="Filter"
					class="relative rounded-r-none focus-visible:z-10"
					iconLeft="lucide-list-filter"
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
				<Button
					tooltip="Clear All Filters"
					class="relative rounded-l-none border-l focus-visible:z-10"
					icon="lucide-x"
					@click.stop="clearAll(close)"
				/>
			</div>
		</template>
		<template #body="{ close }">
			<div
				class="my-2 min-w-40 rounded-lg bg-surface-elevation-2 shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none"
			>
				<div class="min-w-72 p-2 sm:min-w-[400px]">
					<!-- One grid for all rows so the field / operator / value columns
					     line up across rows instead of each row sizing to its own
					     content. Columns auto-size to the widest cell; the controls
					     fill their column (`w-full`) so every box shares a width. -->
					<div
						v-if="model.length"
						class="mb-3 grid grid-cols-[auto_auto_auto_auto_auto] items-center gap-x-2 gap-y-3"
					>
						<template v-for="(f, i) in model" :key="i">
							<div class="w-13 pl-2 text-end text-base text-ink-gray-5">
								{{ i == 0 ? "Where" : "And" }}
							</div>
							<div class="min-w-[140px]">
								<Combobox
									class="w-full"
									trigger="button"
									variant="subtle"
									size="md"
									:modelValue="f.fieldname"
									:options="allFields"
									placeholder="Select field"
									@update:selectedOption="(o) => updateField(o, i)"
								/>
							</div>
							<div>
								<Select
									class="w-full"
									:modelValue="f.operator"
									:options="getOperators(f.field?.fieldtype ?? '', f.fieldname)"
									placeholder="Equals"
									@update:modelValue="(v) => updateOperator(v, i)"
								/>
							</div>
							<div class="w-[180px]">
								<component
									:is="VALUE_CONTROLS[valueControl(f).control]"
									v-bind="valueControl(f).props"
									class="w-full"
									:modelValue="f.value"
									@update:modelValue="(v) => updateValue(v, i)"
								/>
							</div>
							<Button
								class="flex"
								variant="ghost"
								icon="lucide-x"
								@click="removeFilter(i)"
							/>
						</template>
					</div>
					<div v-else class="mb-3 flex h-7 items-center px-3 text-sm text-ink-gray-5">
						Empty - Choose a field to filter by
					</div>
					<div class="flex items-center justify-between gap-2">
						<!-- A custom #trigger renders the same ghost Button as "Clear All
						     Filters" beside it (gray-5, `+` icon, no chevron). The label is
						     static, so the old per-add remount (`:key`) and the placeholder /
						     chevron CSS hacks are no longer needed. -->
						<Combobox
							:options="allFields"
							:modelValue="null"
							@update:selectedOption="addFilter"
						>
							<template #trigger>
								<Button
									class="!text-ink-gray-5"
									variant="ghost"
									label="Add Filter"
									iconLeft="lucide-plus"
								/>
							</template>
						</Combobox>
						<Button
							v-if="model.length"
							class="!text-ink-gray-5"
							variant="ghost"
							label="Clear All Filters"
							@click="clearAll(close)"
						/>
					</div>
				</div>
			</div>
		</template>
	</Popover>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { Button, Combobox, Popover, Select } from "frappe-ui";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { getFilterableFields } from "./getFilterableFields";
import { getOperators, conditionFor, carryOver, defaultValueFor } from "./operators";
import type { Filter, FilterField, FilterOperator, FilterProps, FilterValue } from "./types";
// The operator/fieldtype → value-input dispatch. Lives in its own module so the
// nested ConditionBuilder can render the same value inputs from the same rules
// without duplicating them; it returns an id, and VALUE_CONTROLS maps that id to
// the component (see valueControl.ts for why the two are separate files).
import { valueControl } from "./valueControl";
import { VALUE_CONTROLS } from "./valueControlComponents";

const props = defineProps<FilterProps>();

// `v-model` is the list of Filter conditions. The component is controlled: it only
// reads and re-emits this array, never a data resource.
const model = defineModel<Filter[]>({ default: () => [] });

// The popover only mounts once a condition exists (`v-else`); a ref lets us open it
// right after the empty-state picker seeds the first one, so the user lands on the
// row to set its operator/value instead of having to click "Filter" again.
const popoverRef = ref<{ open: () => void } | null>(null);

const { meta } = useDoctypeMeta(props.doctype);

// Field Options derived client-side from Meta — no CRM endpoint.
const allFields = computed<FilterField[]>(() =>
	getFilterableFields(meta.value?.fields ?? [], props.doctype)
);

// Both the empty-state picker and the in-row picker offer every filterable field.
// Already-chosen fields are intentionally NOT excluded: a field can carry more
// than one condition (e.g. `amount > 100 AND amount < 500`), so the list form of
// `serializeFilters` can hold duplicates.

// Combobox's `update:selectedOption` hands back the chosen option (or null); its
// `value` is the fieldname. Resolve it to the full FilterField from Meta.
function fieldFromOption(option: unknown): FilterField | null {
	if (!option) return null;
	const fieldname =
		typeof option === "string" ? option : (option as { value?: string }).value ?? null;
	return allFields.value.find((o) => o.fieldname === fieldname) ?? null;
}

function addFilter(option: unknown) {
	const field = fieldFromOption(option);
	if (!field) return;
	model.value = [...model.value, conditionFor(field)];
	// Open the popover once it mounts (no-op when adding from inside an open one).
	nextTick(() => popoverRef.value?.open());
}

function updateField(option: unknown, index: number) {
	const field = fieldFromOption(option);
	if (!field) return;
	model.value = model.value.map((f, i) => (i === index ? carryOver(f, field) : f));
}

function updateOperator(operator: FilterOperator, index: number) {
	model.value = model.value.map((f, i) => {
		if (i !== index) return f;
		// Reset the value to a default that fits the new operator: 'set' for
		// Set/Not-Set, an empty list for a multi-select `in`/`not in`, else the
		// field's by-type default.
		return { ...f, operator, value: defaultValueFor(f.field!, operator) };
	});
}

function updateValue(value: FilterValue, index: number) {
	model.value = model.value.map((f, i) => (i === index ? { ...f, value } : f));
}

function removeFilter(index: number) {
	model.value = model.value.filter((_, i) => i !== index);
}

function clearAll(close: () => void) {
	model.value = [];
	close();
}
</script>
