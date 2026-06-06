<!--
  Demo of a *fully custom* field via the registry override — the escape hatch for
  when an app needs more than the framework defaults give.

  NOTE: site-accurate formatting no longer requires this. The lib's own NumberField
  now reads the site defaults (`setFormatDefaults` / `window.sysdefaults`, see
  `formatDefaults.ts`) and formats correctly out of the box. This field exists to
  show that a custom component still wins when registered — it sources its own
  settings and calls the lib's *exported* formatting utils, with no FormLayout prop
  and no lib change. Currency resolves from the field's `options` (a sibling field
  on the doc) first, then the site default.
-->
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
import { DocKey } from "../types";
import type { FieldComponentEmits, FieldComponentProps } from "../types";
import { flt, formatCurrency } from "../formatNumber";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

// The app's own settings source — Frappe desk sets `window.sysdefaults`; the
// fallback keeps the story self-contained.
const sys = (typeof window !== "undefined" && (window as any).sysdefaults) || {
	number_format: "#.###,##", // european, to make the override visibly different
	currency: "EUR",
	currency_precision: 2,
};

const doc = inject(DocKey, null);
const focused = ref(false);
const draft = ref("");
const inputRef = ref<{ el?: HTMLInputElement } | null>(null);

function resolveCurrency(): string {
	const opt = props.field.options;
	const fromDoc = opt ? doc?.value?.[opt] : undefined;
	if (typeof fromDoc === "string" && fromDoc) return fromDoc;
	if (opt && !doc?.value?.[opt]) return opt; // literal code on the field
	return sys.currency ?? "USD";
}

function formatted(value: any): string {
	if (value == null || value === "") return "";
	return formatCurrency(value, {
		numberFormat: sys.number_format,
		currency: resolveCurrency(),
		precision: props.field.precision ?? sys.currency_precision,
	});
}

const display = computed(() => (focused.value ? draft.value : formatted(props.modelValue)));

function parse(s: string): number | null {
	return s === "" ? null : flt(s, { numberFormat: sys.number_format });
}

function onFocus() {
	focused.value = true;
	draft.value = props.modelValue == null ? "" : String(props.modelValue);
	nextTick(() => inputRef.value?.el?.select());
}
function onInput(v: string) {
	draft.value = v;
	emit("update:modelValue", parse(v));
}
function onChange(e: Event) {
	emit("change", parse((e.target as HTMLInputElement).value));
}
</script>
