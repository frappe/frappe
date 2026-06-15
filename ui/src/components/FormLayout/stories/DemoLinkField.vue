<!--
  Demo of the host-side override pattern: a Link field that wires the shared
  `Link`'s create / redirect / edit affordances to app behaviour. The lib ships a
  plain select-only `LinkField`; an app that wants these actions registers its
  own component via `registerFieldType('Link', …)` — no lib changes, no prop.
  Here the handlers just `console.log`; a real host would call vue-router / open
  a quick-entry modal.
-->
<template>
	<Link
		v-model="value"
		:doctype="field.options ?? ''"
		:filters="field.filters"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
		creatable
		redirectable
		editable
		@create="onCreate"
		@redirect="onRedirect"
		@edit="onEdit"
	/>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Link } from "../../Link";
import type { FieldComponentEmits, FieldComponentProps } from "../types";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	// A selection is a commit for a picker: sync the value and fire the trigger.
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});

function onCreate(query: string) {
	console.log("create", {
		doctype: props.field.options,
		fieldname: props.field.fieldname,
		query,
	});
	// Prove the round-trip: a freshly-created record auto-selects into `doc`.
	emit("update:modelValue", `${query || "New"} (created)`);
}

function onRedirect(name: string) {
	console.log("redirect", {
		doctype: props.field.options,
		fieldname: props.field.fieldname,
		name,
	});
}

function onEdit(name: string) {
	console.log("edit", { doctype: props.field.options, fieldname: props.field.fieldname, name });
}
</script>
