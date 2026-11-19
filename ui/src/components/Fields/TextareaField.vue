<template>
	<Textarea
		ref="control"
		v-model="value"
		v-bind="frame"
		:placeholder="field.placeholder"
		:required="field.reqd"
		:disabled="field.readOnly"
		:rows="panel ? 1 : undefined"
		@change="(e: Event) => emit('change', (e.target as HTMLTextAreaElement).value)"
	>
		<template v-if="!panel && field.description && !error?.length" #description>
			<FieldDescription :html="field.description" />
		</template>
	</Textarea>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Textarea } from "frappe-ui";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import FieldDescription from "./FieldDescription.vue";
import { useInputFrame } from "./inputFrame";
import { useTextareaGrow } from "./useTextareaGrow";

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const value = computed<string | null>({
	get: () => props.modelValue ?? null,
	set: (v) => emit("update:modelValue", v),
});

const frame = useInputFrame(props);

// A panel row grows with its text, one line (28) to six (128), then scrolls.
const control = ref<{ inputElement: HTMLTextAreaElement | null } | null>(null);
useTextareaGrow(
	computed(() => control.value?.inputElement ?? null),
	() => value.value,
	() => !!props.panel
);
</script>
