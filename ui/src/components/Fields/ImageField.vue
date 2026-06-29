<template>
	<div>
		<!-- Label / description come from frappe-ui's labeling primitives so the
		     markup, typography, and spacing match every other field (Image has no
		     underlying labeled control to delegate to). -->
		<InputLabel
			v-if="field.label"
			:id="labelId"
			:label="field.label"
			class="mb-1.5 text-p-sm-medium text-ink-gray-7"
		/>
		<!-- The preview box is the labelled region: `role="group"` tied to the label
		     and description ids so the (display-only) field reads as one named unit;
		     the inner <img> keeps its own `alt`. Ids are omitted when absent. -->
		<div
			role="group"
			:aria-labelledby="labelledBy"
			:aria-describedby="describedBy"
			class="flex items-center justify-center overflow-hidden rounded-lg border border-outline-gray-1 bg-surface-gray-1"
			:class="url ? 'min-h-32' : 'min-h-24'"
		>
			<img
				v-if="url"
				:src="url"
				:alt="field.label || ''"
				class="max-h-64 w-full object-contain"
			/>
			<span v-else class="py-6 text-p-sm text-ink-gray-4">No image</span>
		</div>
		<InputDescription
			v-if="field.description"
			:id="descriptionId"
			:description="field.description"
			class="mt-1.5"
		/>
	</div>
</template>

<script setup lang="ts">
// Display-only `Image` field. Frappe's `Image` fieldtype carries no value of its
// own — it renders the image at the URL held by a sibling field named in
// `field.options` (typically an `Attach Image`). Reads that sibling from the
// injected doc; falls back to its own `modelValue` if no `options` is set. No
// upload, no emit.
import { computed, inject, ref, useId } from "vue";
import { InputLabel, InputDescription } from "frappe-ui/experimental";
import { DocKey } from "./types";
import type { FieldComponentProps } from "./types";

const props = defineProps<FieldComponentProps>();

// Stable ids for the labeling primitives (frappe-ui's InputLabel/InputDescription
// require an explicit id).
const labelId = useId();
const descriptionId = useId();

// Associate the preview region with whichever labeling parts are actually rendered
// (aria-* must only reference ids that exist in the DOM).
const labelledBy = computed(() => (props.field.label ? labelId : undefined));
const describedBy = computed(() => (props.field.description ? descriptionId : undefined));

const doc = inject(DocKey, ref<Record<string, any>>({}));

const url = computed<string | null>(() => {
	const sibling = props.field.options;
	if (sibling) return doc.value?.[sibling] ?? null;
	return props.modelValue ?? null;
});
</script>
