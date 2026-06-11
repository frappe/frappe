<template>
	<div>
		<label v-if="field.label" class="mb-1.5 block text-p-sm text-ink-gray-5">
			{{ field.label }}
		</label>
		<div
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
		<p v-if="field.description" class="mt-1.5 text-p-xs text-ink-gray-5">
			{{ field.description }}
		</p>
	</div>
</template>

<script setup lang="ts">
// Display-only `Image` field. Frappe's `Image` fieldtype carries no value of its
// own — it renders the image at the URL held by a sibling field named in
// `field.options` (typically an `Attach Image`). Reads that sibling from the
// injected doc; falls back to its own `modelValue` if no `options` is set. No
// upload, no emit.
import { computed, inject, ref } from "vue";
import { DocKey } from "../types";
import type { FieldComponentProps } from "../types";

const props = defineProps<FieldComponentProps>();

const doc = inject(DocKey, ref<Record<string, any>>({}));

const url = computed<string | null>(() => {
	const sibling = props.field.options;
	if (sibling) return doc.value?.[sibling] ?? null;
	return props.modelValue ?? null;
});
</script>
