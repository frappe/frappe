<!--
  QuickFilter — a controlled, meta-driven list-view control that projects over the
  SAME `Filter[]` list the Filter control binds (ADR-0005). It owns no data
  resource; setting a quick input upserts a condition in the shared list and
  reading reflects whichever condition that input owns, so Filter ↔ QuickFilter
  stay in sync with no cross-control events.

  Two `v-model`s: `filters` (the shared Filter[] — the SoT `useListView` hands
  both controls) and `fields` (the surfaced inputs, optional; defaults to the
  doctype's `in_standard_filter` fields from Meta via `getQuickFilterFields`, and
  a host may bind it to persist the user's customized set).

  Projection is by canonical operator (`quickFilters.ts`): a quick input owns only
  conditions on its field whose operator is in that field's canonical set, so a
  precise popover condition (`Status in […]`) is left untouched. Free-text fields
  (and the `name` field) own BOTH `like` (default) and `equals`, surfaced as a
  `≈`/`=` toggle glued to the front of the input — substring-search by default,
  click to flip to an exact match. Link fields are an exact pick (`equals`, no
  toggle). The value inputs are the shared `Fields` components (ADR-0004); the
  `name` field swaps its text box for a Link picker when flipped to `equals`.
-->
<template>
	<!-- Wrap extra inputs to a second row instead of scrolling: overflow stays
	     `visible` so the inputs' focus ring isn't clipped. -->
	<div class="flex flex-wrap items-center gap-2">
		<!-- Customize mode: chips of the surfaced fields with a remove affordance,
		     plus an "Add Filter" picker over every labelled field. -->
		<template v-if="customizing">
			<Button
				v-for="field in surfaced"
				:key="field.fieldname"
				class="group whitespace-nowrap"
				:label="field.label"
			>
				<template #suffix>
					<span
						class="lucide-x size-3.5 cursor-pointer"
						aria-hidden="true"
						@click.stop="removeField(field)"
					/>
				</template>
			</Button>
			<Combobox
				:key="surfaced.length"
				trigger="button"
				variant="ghost"
				:options="addableFields"
				:modelValue="null"
				placeholder="Add Filter"
				@update:selectedOption="addField"
			>
				<template #prefix>
					<span class="lucide-plus size-4" aria-hidden="true" />
				</template>
			</Combobox>
		</template>

		<!-- Normal mode: one inline value input per surfaced field. A definite
		     width keeps each input from growing on hover (e.g. a Link's clear
		     button) — the label truncates instead. -->
		<template v-else>
			<div v-for="field in surfaced" :key="field.fieldname" class="w-40 shrink-0">
				<!-- Check → a labelled checkbox (checked ⇔ equals "Yes"). -->
				<Checkbox
					v-if="field.fieldtype === 'Check'"
					:label="field.label"
					:modelValue="quickValue(filters, field) as boolean"
					@update:modelValue="(v: boolean) => setValue(field, v)"
				/>
				<!-- The fieldtype's value control. Free-text fields (and name) carry a
				     ≈/= operator toggle as a prefix inside the input; clicking it flips
				     like ↔ equals in place (and, for name, swaps text box ↔ Link pick). -->
				<component
					v-else
					:is="valueControl(field).is"
					v-bind="valueControl(field).props"
					class="w-full"
					:modelValue="quickValue(filters, field)"
					@update:modelValue="(v: FilterValue) => setValue(field, v)"
				>
					<template v-if="hasOperatorToggle(field)" #prefix>
						<button
							type="button"
							class="grid size-5 place-items-center rounded text-xs font-medium text-ink-gray-5 hover:bg-surface-gray-4 hover:text-ink-gray-8"
							:title="operatorLabel(activeOperator(field))"
							:aria-label="operatorLabel(activeOperator(field))"
							@pointerdown.stop
							@click.stop="toggleOperator(field)"
						>
							{{ operatorSymbol(activeOperator(field)) }}
						</button>
					</template>
				</component>
			</div>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive } from "vue";
import { Button, Checkbox, Combobox, TextInput } from "frappe-ui";
import { useDoctypeMeta } from "../../composables/useDoctypeMeta";
import { getFilterableFields } from "../Filter/getFilterableFields";
import { getQuickFilterFields } from "./getQuickFilterFields";
import {
	applyQuick,
	hasOperatorToggle,
	isNameField,
	quickOperator,
	quickValue,
} from "./quickFilters";
import type { Filter, FilterField, FilterOperator, FilterValue } from "../Filter/types";
// Shared, fieldtype-aware value inputs (ADR-0004), same subset the Filter control
// mounts. No form-context injections are provided, so deep-injection inputs fall
// back to site defaults — fine for a bare filter input.
import SelectField from "../Fields/SelectField.vue";
import LinkField from "../Fields/LinkField.vue";
import NumberField from "../Fields/NumberField.vue";
import DateField from "../Fields/DateField.vue";
import DatetimeField from "../Fields/DatetimeField.vue";
import DurationField from "../Fields/DurationField.vue";
import type { FieldMeta } from "../Fields/types";

const props = defineProps<{ doctype: string }>();

// Two controlled models on one element: the shared Filter[] and the surfaced
// fields. `fields` is left undefined when the host doesn't bind it, so the
// Meta-derived default is used locally.
const filters = defineModel<Filter[]>("filters", { default: () => [] });
const fields = defineModel<FilterField[] | undefined>("fields", { default: undefined });

const { meta } = useDoctypeMeta(props.doctype);

// Default surfaced fields from Meta until the host/user customizes (`fields`
// bound). Mutating in customize mode promotes the default into the model.
const defaultFields = computed<FilterField[]>(() =>
	getQuickFilterFields(meta.value?.fields ?? [], props.doctype)
);
const surfaced = computed<FilterField[]>(() => fields.value ?? defaultFields.value);

// Every labelled field offered by the customize/add picker (drawn from the Filter
// module's `getFilterableFields`, so `name` and any labelled field is addable),
// minus the already-surfaced ones.
const allFields = computed<FilterField[]>(() =>
	getFilterableFields(meta.value?.fields ?? [], props.doctype)
);
const addableFields = computed<FilterField[]>(() => {
	const shown = new Set(surfaced.value.map((f) => f.fieldname));
	return allFields.value.filter((f) => !shown.has(f.fieldname));
});

// Edit-state toggle is owned by the host (a button beside Sort), bound here so the
// strip swaps between value inputs and the customize chips.
const customizing = defineModel<boolean>("customizing", { default: false });

// --- Surfaced-field customization -------------------------------------------
// Mutating the surfaced set is independent of the values: removing a field only
// hides its input, any existing Filter[] condition survives (and still shows in
// the Filter popover). Writes go through the `fields` model so a host can persist.

function fieldFromOption(option: unknown): FilterField | null {
	if (!option) return null;
	const fieldname =
		typeof option === "string" ? option : (option as { value?: string }).value ?? null;
	return allFields.value.find((f) => f.fieldname === fieldname) ?? null;
}

function addField(option: unknown) {
	const field = fieldFromOption(option);
	if (!field || surfaced.value.some((f) => f.fieldname === field.fieldname)) return;
	fields.value = [...surfaced.value, field];
}

function removeField(field: FilterField) {
	fields.value = surfaced.value.filter((f) => f.fieldname !== field.fieldname);
}

// --- Value projection -------------------------------------------------------
// Read with `quickValue`/`quickOperator`; write with `applyQuick`. The operator
// override keeps a toggle sticky while its input is still empty (no stored
// condition to read the operator back from yet).
const operatorOverride = reactive<Record<string, FilterOperator>>({});

function activeOperator(field: FilterField): FilterOperator {
	return operatorOverride[field.fieldname] ?? quickOperator(filters.value, field);
}

function setValue(field: FilterField, value: FilterValue) {
	filters.value = applyQuick(filters.value, field, value, activeOperator(field));
}

const operatorSymbol = (op: FilterOperator) => (op === "equals" ? "=" : "≈");
const operatorLabel = (op: FilterOperator) => (op === "equals" ? "Equals" : "Like");

/** Flip the input's operator like ↔ equals on click (no menu). Re-applies the
 *  current value under the new operator so the shared condition flips in place,
 *  and — for `name` — swaps the text box for a Link picker (or back). */
function toggleOperator(field: FilterField) {
	const next: FilterOperator = activeOperator(field) === "equals" ? "like" : "equals";
	operatorOverride[field.fieldname] = next;
	const current = quickValue(filters.value, field);
	if (current !== "" && current != null) setValue(field, current);
}

// --- Value-control dispatch -------------------------------------------------
const NUMBER_TYPES = ["Float", "Int", "Currency", "Percent"];
const SELECT_TYPES = ["Select", "Autocomplete"];

interface ValueControl {
	is: unknown;
	props: Record<string, unknown>;
}

/** Bare field meta (no label/description) so the input renders compact, with the
 *  field's label as placeholder. */
function bareField(field: FilterField, overrides: Partial<FieldMeta> = {}): FieldMeta {
	return {
		fieldname: field.fieldname,
		fieldtype: field.fieldtype,
		options: field.options,
		placeholder: field.label,
		...overrides,
	};
}

/** The value control for a field's quick input, by fieldtype — and, for the
 *  toggle fields, the active operator. The `name` field is a text box in `like`
 *  mode and a Link picker (against its own doctype) in `equals` mode; a real Link
 *  is always an exact picker; Dynamic Link has no fixed target so it stays a text
 *  box. Select gets a leading blank option so the quick filter can clear to empty. */
function valueControl(field: FilterField): ValueControl {
	const fieldtype = field.fieldtype;
	if (isNameField(field)) {
		return activeOperator(field) === "equals"
			? { is: LinkField, props: { field: bareField(field) } }
			: { is: TextInput, props: { type: "text", placeholder: field.label } };
	}
	if (fieldtype === "Link") {
		return { is: LinkField, props: { field: bareField(field) } };
	}
	if (SELECT_TYPES.includes(fieldtype)) {
		const options = "\n" + (field.options ?? "");
		return { is: SelectField, props: { field: bareField(field, { options }) } };
	}
	if (NUMBER_TYPES.includes(fieldtype)) {
		return { is: NumberField, props: { field: bareField(field) } };
	}
	if (fieldtype === "Date") return { is: DateField, props: { field: bareField(field) } };
	if (fieldtype === "Datetime") return { is: DatetimeField, props: { field: bareField(field) } };
	if (fieldtype === "Duration") return { is: DurationField, props: { field: bareField(field) } };
	return { is: TextInput, props: { type: "text", placeholder: field.label } };
}
</script>
