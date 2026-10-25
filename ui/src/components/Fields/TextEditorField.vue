<template>
	<div class="space-y-1.5">
		<FormLabel v-if="field.label" :id="labelId" :label="field.label" :required="field.reqd" />
		<div
			v-if="field.readOnly"
			class="min-h-7 rounded-4 border border-transparent bg-surface-gray-1 px-2 py-1"
			data-slot="text-editor-value"
		>
			<RichTextView :html="modelValue" class="text-ink-gray-8" />
		</div>
		<TextEditorInput
			v-else
			:modelValue="modelValue"
			:field="field"
			:labelId="field.label ? labelId : undefined"
			:describedBy="describedBy"
			:invalid="hasError"
			@update:modelValue="emit('update:modelValue', $event)"
			@change="emit('change', $event)"
		/>
		<p
			v-if="field.description && !hasError"
			:id="descriptionId"
			class="text-p-sm text-ink-gray-6"
		>
			{{ field.description }}
		</p>
		<ErrorMessage :id="errorId" :message="error" />
	</div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, h, useId } from "vue";
import { ErrorMessage, FormLabel } from "frappe-ui";
import RichTextView from "../RichText/RichTextView.vue";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

// The editor chunk loads only when an editable field draws; the empty box holds its place.
const TextEditorInput = defineAsyncComponent({
	loader: () => import("./TextEditorInput.vue"),
	loadingComponent: () =>
		h("div", { class: "h-[10.8rem] rounded-4 border border-outline-gray-2" }),
	delay: 0,
});

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const labelId = useId();
const descriptionId = useId();
const errorId = useId();

const hasError = computed(() => Boolean(props.error?.length));

const describedBy = computed(() => {
	if (hasError.value) return errorId;
	return props.field.description ? descriptionId : undefined;
});
</script>
