<template>
	<TextInput
		ref="inputRef"
		type="text"
		:modelValue="display"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:error="error"
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
import { flt, parseLongInt } from "../FormLayout/formatNumber";
import { getFormatDefaults } from "../FormLayout/formatDefaults";
import { useFieldDisplay } from "../FormLayout/useFieldDisplay";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// Format-on-blur / raw-on-focus (mirrors Frappe's FormattedInput): override only the
// displayed string; commit rides TextInput's native `@change`. `type="text"` because
// grouped strings aren't a valid `type="number"` value.
const focused = ref(false);
const draft = ref("");
const inputRef = ref<{ el?: HTMLInputElement } | null>(null);

// The doc, row and parent doc let a Currency field resolve its code from a sibling field.
// `ParentDocKey` is set only for a child-table row, so the dialog matches the grid.
const doc = inject(DocKey, null);
const parentDoc = inject(ParentDocKey, null);
const displayField = useFieldDisplay();

// A numeric field has no empty state — Frappe shows `0`. Coerce here, not in the shared
// formatter whose `'' for empty` contract the panel relies on.
const display = computed(() =>
	focused.value ? draft.value : formatted(numericValue(props.modelValue))
);

/** Treat a null/blank model value as `0` (a number field's default). */
function numericValue(value: any): any {
	return value == null || value === "" ? 0 : value;
}

/** The value as the panel and a read-only field show it, with the site's precision and the resolved currency. */
function formatted(value: any): string {
	return displayField(props.field, value, {
		doc: doc?.value,
		row: props.row,
		parentDoc: parentDoc?.value,
	});
}

function parse(s: string): number | string {
	// Empty input commits `0` (no null state); `flt('')` already returns 0.
	const defaults = getFormatDefaults();
	if (props.field.fieldtype === "Long Int") return parseLongInt(s, defaults.number_format);
	if (props.field.fieldtype === "Int") {
		return Math.trunc(flt(s, { numberFormat: defaults.number_format }));
	}
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
