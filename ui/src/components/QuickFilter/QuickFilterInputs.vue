<!--
  QuickFilterInputs — the normal-mode face of the QuickFilter strip: one inline
  value input per surfaced field, projecting over the SAME `Filter[]` the Filter
  control binds (ADR-0005). It owns no data resource; setting a quick input upserts
  a condition in the shared list and reading reflects whichever condition that
  input owns, so Filter ↔ QuickFilter stay in sync with no cross-control events.

  Which fields are surfaced (and in what order) is decided by the parent and passed
  as `fields`; this component only renders their value inputs. Projection is by
  canonical operator (`quickFilters.ts`): a quick input owns only conditions on its
  field whose operator is in that field's canonical set, so a precise popover
  condition (`Status in […]`) is left untouched. Free-text fields (and the `name`
  field) own BOTH `like` (default) and `equals`, surfaced as a `≈`/`=` toggle glued
  to the front of the input — substring-search by default, click to flip to an exact
  match. Link fields are an exact pick (`equals`, no toggle). The value inputs are
  the shared `Fields` components (ADR-0004); the `name` field swaps its text box for
  a Link picker when flipped to `equals`.
-->
<template>
	<!-- One inline row by default: inputs past the available width collapse behind a
	     "+N more" button rather than wrapping (which ate a second row). Clicking it
	     expands to show every input, wrapping freely. `overflow` stays `visible` so
	     the inputs' focus ring isn't clipped. -->
	<div ref="root" class="flex flex-wrap items-center gap-2">
		<!-- One inline value input per surfaced field. A definite width keeps each
		     input from growing on hover (e.g. a Link's clear button) — the label
		     truncates instead. -->
		<div v-for="field in visibleFields" :key="field.fieldname" class="w-40 shrink-0">
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
				:modelValue="displayValue(field)"
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
		<!-- Overflow affordance: collapsed inputs hide behind a count; expanding
		     shows all and lets them wrap. A `subtle` pill (not bare ghost text) so it
		     reads as a peer of the filled inputs beside it rather than floating. Only
		     shown once something overflows. -->
		<Button
			v-if="hiddenCount > 0 || expanded"
			class="shrink-0 whitespace-nowrap"
			variant="subtle"
			:label="expanded ? 'Show less' : `${hiddenCount} more`"
			@click="expanded = !expanded"
		>
			<template #suffix>
				<span
					class="size-3.5 text-ink-gray-5"
					:class="expanded ? 'lucide-chevron-left' : 'lucide-chevron-down'"
					aria-hidden="true"
				/>
			</template>
		</Button>
	</div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { Button, Checkbox, TextInput, debounce } from "frappe-ui";
import {
	applyQuick,
	hasOperatorToggle,
	hasOwnedCondition,
	isNameField,
	quickFilterOperator,
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

const props = defineProps<{
	/** The fields surfaced as value inputs, in display order (decided by the parent). */
	fields: FilterField[];
}>();

// The shared Filter[] — the SoT `useListView` hands both controls. This component
// only reads and re-emits it; it never owns a data resource.
const filters = defineModel<Filter[]>("filters", { default: () => [] });

// --- Overflow collapse -------------------------------------------------------
// Each value input is a fixed `w-40` box (160px) on an 8px gap, so how many fit on
// one row is pure arithmetic on the container width — no per-child measurement.
// Inputs past the fit collapse behind a "+N more" toggle; expanding shows all and
// lets the row wrap.
const ITEM_WIDTH = 160; // w-40
const GAP = 8; // gap-2
const MORE_WIDTH = 84; // room reserved for the "N more" button (+ its leading gap)

const root = ref<HTMLElement | null>(null);
const containerWidth = ref(0);
const expanded = ref(false);
let observer: ResizeObserver | null = null;

/** Max fixed-width inputs that fit in `width`, leaving `reserve` px aside. */
function fitCount(width: number, reserve: number): number {
	const usable = width - reserve;
	if (usable < ITEM_WIDTH) return 0;
	return Math.floor((usable + GAP) / (ITEM_WIDTH + GAP));
}

// How many inputs to render when collapsed. Until the width is measured (0), show
// all to avoid a first-paint flash of everything hidden.
const collapsedCount = computed<number>(() => {
	const total = props.fields.length;
	const width = containerWidth.value;
	if (width === 0) return total;
	if (fitCount(width, 0) >= total) return total; // no overflow
	return Math.max(1, fitCount(width, MORE_WIDTH + GAP)); // keep room for the toggle
});

const hiddenCount = computed<number>(() =>
	Math.max(0, props.fields.length - collapsedCount.value)
);
const visibleFields = computed<FilterField[]>(() =>
	expanded.value ? props.fields : props.fields.slice(0, collapsedCount.value)
);

onMounted(() => {
	if (typeof ResizeObserver === "undefined" || !root.value) return;
	observer = new ResizeObserver((entries) => {
		containerWidth.value = entries[0].contentRect.width;
	});
	observer.observe(root.value);
});

onBeforeUnmount(() => {
	observer?.disconnect();
	observer = null;
});

// --- Value projection -------------------------------------------------------
// Read with `quickValue`/`quickOperator`; write with `applyQuick`. The operator
// override keeps a toggle sticky while its input is still empty (no stored
// condition to read the operator back from yet); once a condition exists, that
// condition is the source of truth.
const operatorOverride = reactive<Record<string, FilterOperator>>({});

function activeOperator(field: FilterField): FilterOperator {
	// A stored owned condition is the source of truth — so an external delete or
	// change in the Filter popover is reflected, and a stale override can't
	// resurrect `equals`. The override only holds the toggle while the input is
	// still empty.
	if (hasOwnedCondition(filters.value, field)) {
		return quickOperator(filters.value, field);
	}
	return operatorOverride[field.fieldname] ?? quickFilterOperator(field);
}

// Clear stale overrides when a condition is externally removed from the Filter
// popover — prevents a stale `equals` override from re-activating on the next edit.
watch(filters, (newFilters, oldFilters) => {
	for (const fieldname of Object.keys(operatorOverride)) {
		const field = props.fields.find((f) => f.fieldname === fieldname);
		if (!field) {
			delete operatorOverride[fieldname];
			continue;
		}
		if (hasOwnedCondition(oldFilters, field) && !hasOwnedCondition(newFilters, field)) {
			delete operatorOverride[fieldname];
		}
	}
});

// Typed inputs (free-text / number) emit on every keystroke; committing each one
// straight into the shared Filter[] would re-run the list query per character. We
// hold the in-flight value in a local `draft` so the input stays responsive, and
// debounce the commit by 500ms. Discrete picks (Select/Link/Date/Check) have no
// keystroke stream to coalesce, so they commit immediately.
const COMMIT_DELAY = 500;
const draft = reactive<Record<string, FilterValue>>({});
const debouncedCommit = new Map<string, (value: FilterValue) => void>();

/** The value shown in a field's input: the in-flight draft while typing, else the
 *  committed value projected out of the shared Filter[]. */
function displayValue(field: FilterField): FilterValue {
	return field.fieldname in draft ? draft[field.fieldname] : quickValue(filters.value, field);
}

/** Typed inputs route through the same `valueControl` dispatch so this never
 *  drifts from how a field is actually rendered. */
function isTypedField(field: FilterField): boolean {
	const control = valueControl(field).is;
	return control === TextInput || control === NumberField;
}

function commitValue(field: FilterField, value: FilterValue) {
	filters.value = applyQuick(filters.value, field, value, activeOperator(field));
	// The operator now lives in the stored condition (if any), so drop the
	// transient override — otherwise a later external delete/change in the Filter
	// popover would let it resurrect a stale operator on the next edit.
	if (hasOwnedCondition(filters.value, field)) {
		delete operatorOverride[field.fieldname];
	}
	delete draft[field.fieldname];
}

/** A per-field debounced committer, so concurrent typing in two fields doesn't let
 *  one field's pending commit clobber the other's. */
function debouncedCommitFor(field: FilterField): (value: FilterValue) => void {
	let fn = debouncedCommit.get(field.fieldname);
	if (!fn) {
		fn = debounce((value: FilterValue) => commitValue(field, value), COMMIT_DELAY);
		debouncedCommit.set(field.fieldname, fn);
	}
	return fn;
}

function setValue(field: FilterField, value: FilterValue) {
	if (isTypedField(field)) {
		draft[field.fieldname] = value; // echo immediately
		debouncedCommitFor(field)(value); // commit after the typing settles
	} else {
		commitValue(field, value);
	}
}

const operatorSymbol = (op: FilterOperator) => (op === "equals" ? "=" : "≈");
const operatorLabel = (op: FilterOperator) => (op === "equals" ? "Equals" : "Like");

/** Flip the input's operator like ↔ equals on click (no menu). With a value, the
 *  stored condition flips in place under the new operator (and the override is
 *  dropped — the condition now carries it). While empty, the override holds the
 *  chosen operator until a value is typed. For `name`, this also swaps the text
 *  box for a Link picker (or back). */
function toggleOperator(field: FilterField) {
	const next: FilterOperator = activeOperator(field) === "equals" ? "like" : "equals";
	// Read the displayed value (the in-flight draft if typing hasn't settled), so a
	// toggle mid-type flips the latest text rather than the last committed value.
	const current = displayValue(field);
	if (current !== "" && current != null) {
		filters.value = applyQuick(filters.value, field, current, next);
		delete operatorOverride[field.fieldname];
		delete draft[field.fieldname];
	} else {
		operatorOverride[field.fieldname] = next;
	}
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
