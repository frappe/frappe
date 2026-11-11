<template>
	<Password
		v-model="value"
		v-bind="frame"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
		@change="(e: Event) => emit('change', (e.target as HTMLInputElement).value)"
	>
		<template v-if="!panel && field.description && !error?.length" #description>
			<FieldDescription :html="field.description" />
		</template>
	</Password>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Password } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import FieldDescription from "./FieldDescription.vue";
import { useInputFrame } from "./inputFrame";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();
const frame = useInputFrame(props);

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	set: (v) => emit("update:modelValue", v),
});
</script>
