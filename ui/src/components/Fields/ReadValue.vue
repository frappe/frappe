<template>
	<div class="space-y-1.5">
		<FormLabel v-if="label" :label="label" :required="required" />
		<div
			class="flex min-h-7 min-w-0 items-center rounded-4 bg-surface-gray-1 px-2 py-1 text-base text-ink-gray-8"
			data-slot="read-value"
		>
			<span
				class="min-w-0 whitespace-pre-wrap break-words"
				:class="{ 'text-ink-gray-5': !text && placeholder }"
			>
				<slot>{{ text || placeholder }}</slot>
			</span>
		</div>
		<p v-if="description && !error?.length" class="text-p-sm text-ink-gray-6">
			{{ description }}
		</p>
		<ErrorMessage :message="error" />
	</div>
</template>

<script setup lang="ts">
import { ErrorMessage, FormLabel } from "frappe-ui";
import type { FieldError } from "./types";

defineProps<{
	text?: string;
	placeholder?: string;
	label?: string;
	description?: string;
	required?: boolean;
	error?: FieldError;
}>();
</script>
