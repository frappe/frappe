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
import { DocKey, ParentDocKey } from "../types";
import type { FieldComponentEmits, FieldComponentProps } from "../types";
import { flt, formatField } from "../formatNumber";
import { resolveFieldCurrency } from "../resolveCurrency";
import { getFormatDefaults } from "../formatDefaults";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// Format-on-blur / raw-on-focus (mirrors Frappe's FormattedInput): we override
// *only* the displayed string — formatted when not editing, raw while editing.
// Everything else (commit on blur/Enter, only-when-changed) rides on TextInput's
// native `@change`, exactly like TextField. The input is `type="text"` because
// grouped strings aren't a valid `type="number"` value.
const focused = ref(false);
const draft = ref("");
const inputRef = ref<{ el?: HTMLInputElement } | null>(null);

// Available so a Currency field can resolve its currency code from a sibling
// field on the doc (Frappe's `options`-points-to-a-field convention). Optional:
// the field renders fine standalone (no doc provided).
const doc = inject(DocKey, null);

// The parent doc, present only when this field belongs to a child-table row (the
// grid cell or the row-edit dialog). Lets a row's Currency `options` resolve a
// *parent* field — and keeps the dialog in sync with the grid, where the parent
// doc is the injected `doc`. Null at the top level.
const parentDoc = inject(ParentDocKey, null);

// A numeric field has no "empty" rendered state — Frappe shows `0` (formatted
// per fieldtype) when the value is null/blank. Coerce here, not in the pure
// `formatField` util, whose `'' for empty` contract other callers may rely on.
const display = computed(() =>
	focused.value ? draft.value : formatted(numericValue(props.modelValue))
);

/** Treat a null/blank model value as `0` (a number field's default). */
function numericValue(value: any): any {
	return value == null || value === "" ? 0 : value;
}

/**
 * Currency code for a Currency field, resolved like Frappe desk's
 * `get_field_currency` (see `resolveFieldCurrency`): the field's `options` names
 * a sibling field — the grid row's column when this is a child-table cell, else
 * the parent doc — or a `Doctype:link_field:currency_field` cross-record form;
 * an empty/absent value falls back to the site default (`getFormatDefaults`).
 *
 * The cross-record (`:`) form's record read is owned by `resolveCurrency`'s
 * built-in (overridable) reader — no wiring needed here.
 */
function resolveCurrency(): string | undefined {
	return resolveFieldCurrency(props.field.options, {
		doc: doc?.value,
		row: props.row,
		parentDoc: parentDoc?.value,
		defaultCurrency: getFormatDefaults().currency,
	});
}

/**
 * Resolve the decimal places: per-field `precision` (meta) wins; else the
 * matching site default (`currency_precision` for Currency, `float_precision`
 * for Float/Percent); else `undefined`, letting the pure util derive it from the
 * number format (and force 0 for Int).
 */
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
	// Currency is the only type needing the doc; resolve it here (Vue-coupled) and
	// hand a plain code to the pure formatter. Site number_format / rounding flow
	// in from the resolved framework defaults; per-field meta wins on precision.
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
	// A number field has no null state — an empty input commits `0`, matching the
	// displayed default (see `numericValue`). `flt('')` already returns 0.
	const defaults = getFormatDefaults();
	return flt(s, {
		numberFormat: defaults.number_format,
		roundingMethod: defaults.rounding_method,
	});
}

// Switch to the raw, editable value while focused (preserve exact keystrokes),
// and select it all so a fresh entry overwrites — matches Frappe's FormattedInput.
function onFocus() {
	focused.value = true;
	draft.value = String(numericValue(props.modelValue));
	nextTick(() => inputRef.value?.el?.select());
}

// Live value while typing — keeps `doc` and conditional visibility reactive.
function onInput(v: string) {
	draft.value = v;
	emit("update:modelValue", parse(v));
}

// Commit — the input's native `change` (blur or Enter, only when the value
// changed). Same funnel TextField uses; we just parse the raw string back.
function onChange(e: Event) {
	emit("change", parse((e.target as HTMLInputElement).value));
}
</script>
