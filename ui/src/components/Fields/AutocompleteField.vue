<template>
	<Combobox
		v-model="value"
		v-model:open="open"
		:options="options"
		v-bind="frame"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
		:openOnClick="true"
	>
		<template v-if="!panel && field.description && !error?.length" #description>
			<FieldDescription :html="field.description" />
		</template>
	</Combobox>
</template>

<script setup lang="ts">
// frappe-ui `Combobox` over newline-joined `field.options`. Combobox emits only
// `update:modelValue`; a selection is a commit, so we re-emit `change` too.
import { computed, ref } from "vue";
import { Combobox } from "frappe-ui";
import { fieldChoices } from "./choices";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import FieldDescription from "./FieldDescription.vue";
import { usePickerFrame } from "./inputFrame";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();
const frame = usePickerFrame(props);
const open = ref(!!props.openPicker);

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
