<template>
	<TextInput
		ref="inputRef"
		type="text"
		:modelValue="display"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
		@focus="onFocus"
		@blur="focused = false"
		@update:modelValue="onInput"
		@change="onChange"
	/>
</template>

<script setup lang="ts">
import { computed, inject, nextTick, ref } from "vue";
import { TextInput } from "frappe-ui";
import { DocKey, ParentDocKey } from "./types";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import { flt, formatField } from "../FormLayout/formatNumber";
import { resolveFieldCurrency } from "../FormLayout/resolveCurrency";
import { getFormatDefaults } from "../FormLayout/formatDefaults";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// Format-on-blur / raw-on-focus (mirrors Frappe's FormattedInput): override only the
// displayed string; commit rides TextInput's native `@change`. `type="text"` because
// grouped strings aren't a valid `type="number"` value.
const focused = ref(false);
const draft = ref("");
const inputRef = ref<{ el?: HTMLInputElement } | null>(null);

// Lets a Currency field resolve its code from a sibling field on the doc. Optional.
const doc = inject(DocKey, null);

// Parent doc, present only for a child-table row, so a row's Currency `options` can
// resolve a parent field (keeps dialog in sync with the grid). Null at the top level.
const parentDoc = inject(ParentDocKey, null);

// A numeric field has no empty state — Frappe shows `0`. Coerce here, not in the pure
// `formatField` util whose `'' for empty` contract other callers rely on.
const display = computed(() =>
	focused.value ? draft.value : formatted(numericValue(props.modelValue))
);

/** Treat a null/blank model value as `0` (a number field's default). */
function numericValue(value: any): any {
	return value == null || value === "" ? 0 : value;
}

/** Currency code for a Currency field, resolved like desk's `get_field_currency` (see `resolveFieldCurrency`); falls back to the site default. */
function resolveCurrency(): string | undefined {
	return resolveFieldCurrency(props.field.options, {
		doc: doc?.value,
		row: props.row,
		parentDoc: parentDoc?.value,
		defaultCurrency: getFormatDefaults().currency,
	});
}

/** Decimal places: per-field `precision` wins, else the matching site default, else `undefined` (util derives it). */
function resolvePrecision(fieldtype: string | undefined): number | undefined {
	// Int has no precision — it renders as a plain integer (see formatField).
	if (fieldtype === "Int") return undefined;
	if (props.field.precision != null) return props.field.precision;
	const d = getFormatDefaults();
	const sys = fieldtype === "Currency" ? d.currency_precision : d.float_precision;
	if (sys == null || sys === "") return undefined;
	const n = Number(sys);
	return Number.isNaN(n) ? undefined : n;
}

function formatted(value: any): string {
	const { fieldtype } = props.field;
	const defaults = getFormatDefaults();
	// Resolve currency here (Vue-coupled) and hand a plain code to the pure formatter.
	const currency = fieldtype === "Currency" ? resolveCurrency() : undefined;
	return formatField(value, {
		fieldtype,
		precision: resolvePrecision(fieldtype),
		currency,
		numberFormat: defaults.number_format,
		roundingMethod: defaults.rounding_method,
	});
}

function parse(s: string): number {
	// Empty input commits `0` (no null state); `flt('')` already returns 0.
	const defaults = getFormatDefaults();
	return flt(s, {
		numberFormat: defaults.number_format,
		roundingMethod: defaults.rounding_method,
	});
}

// Show raw value while focused and select-all so a fresh entry overwrites (Frappe's FormattedInput).
function onFocus() {
	focused.value = true;
	draft.value = String(numericValue(props.modelValue));
	nextTick(() => inputRef.value?.el?.select());
}

// Emit live value while typing so `doc` and conditional visibility stay reactive.
function onInput(v: string) {
	draft.value = v;
	emit("update:modelValue", parse(v));
}

// Commit on native `change` (blur/Enter, only when changed), parsing the raw string back.
function onChange(e: Event) {
	emit("change", parse((e.target as HTMLInputElement).value));
}
</script>
