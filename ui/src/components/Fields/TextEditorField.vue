<template>
	<div :class="panel ? undefined : 'space-y-1.5'">
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
			:describedBy="panel ? (hasError ? errorId : undefined) : describedBy"
			:invalid="hasError"
			:panel="panel"
			@update:modelValue="emit('update:modelValue', $event)"
			@change="emit('change', $event)"
		/>
		<p
			v-if="field.description && !hasError"
			:id="descriptionId"
			class="text-p-sm text-ink-gray-6"
		>
			<FieldDescription :html="field.description" />
		</p>
		<ErrorMessage v-if="!panel" :id="ownErrorId" :message="error" />
	</div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, h, useId } from "vue";
import { ErrorMessage, FormLabel } from "frappe-ui";
import RichTextView from "../RichText/RichTextView.vue";
import type { FieldComponentEmits, FieldComponentProps } from "./types";
import FieldDescription from "./FieldDescription.vue";

// The editor chunk loads only when an editable field draws; the empty box holds its place.
const TextEditorInput = defineAsyncComponent({
	loader: () => import("./TextEditorInput.vue"),
	loadingComponent: (props: { panel?: boolean }) =>
		h("div", {
			class: props.panel
				? "min-h-[var(--panel-rest-h,1.75rem)]"
				: "h-[10.8rem] rounded-4 bg-surface-gray-2",
		}),
	delay: 0,
});

const props = defineProps<FieldComponentProps>();
const emit = defineEmits<FieldComponentEmits>();

const labelId = useId();
const descriptionId = useId();
const ownErrorId = useId();

const hasError = computed(() => Boolean(props.error?.length));

const describedBy = computed(() => {
	if (hasError.value) return ownErrorId;
	return props.field.description ? descriptionId : undefined;
});
</script>
