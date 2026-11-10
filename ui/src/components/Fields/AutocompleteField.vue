<template>
	<Combobox
		v-model="value"
		:options="options"
		:label="field.label"
		:description="field.description"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:error="error"
		:disabled="field.readOnly"
		:openOnClick="true"
	>
		<template v-if="field.description && !error?.length" #description>
			<FieldDescription :html="field.description" />
		</template>
	</Combobox>
</template>

<script setup lang="ts">
// frappe-ui `Combobox` over newline-joined `field.options`. Combobox emits only
// `update:modelValue`; a selection is a commit, so we re-emit `change` too.
import { computed } from "vue";
import { Combobox } from "frappe-ui";
import { fieldChoices } from "./choices";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import FieldDescription from "./FieldDescription.vue";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	set: (v) => {
		emit("update:modelValue", v);
		emit("change", v);
	},
});

/** Frappe `Autocomplete` options are a newline-joined string in meta; a script may set labelled pairs. */
const options = computed(() => fieldChoices(props.field, true));
</script>
