<template>
	<TextInput
		type="tel"
		:modelValue="modelValue"
		v-bind="frame"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
		@update:modelValue="(value: any) => emit('update:modelValue', value)"
		@change="(e: Event) => emit('change', (e.target as HTMLInputElement).value)"
	>
		<template v-if="!panel && field.description && !error?.length" #description>
			<FieldDescription :html="field.description" />
		</template>
		<!-- A grid cell passes its row, and draws no actions. -->
		<template v-if="!row" #suffix>
			<FieldActions :field="field" :value="modelValue" :record="record" />
		</template>
	</TextInput>
</template>

<script setup lang="ts">
// Minimal `type=tel` text box; value is the raw string. Core's `controls/phone.js`
// adds an ISD picker and stores a composite `"ISD-number"` — a later upgrade.
import { TextInput } from "frappe-ui";
import FieldActions from "./FieldActions.vue";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import FieldDescription from "./FieldDescription.vue";
import { useInputFrame } from "./inputFrame";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();
const frame = useInputFrame(props);
</script>
