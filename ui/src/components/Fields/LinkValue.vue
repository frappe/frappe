<!-- A read-only Link or Dynamic Link value: its title, as a link when the record has an address. -->
<template>
	<div class="space-y-1.5">
		<FormLabel v-if="label" :label="label" :required="required" />
		<div
			class="flex h-7 min-w-0 items-center rounded-4 border border-transparent bg-surface-gray-1 px-2 text-base"
			data-slot="link-value"
		>
			<RecordAnchor
				v-if="href && text"
				:href="href"
				:title="__('Open {0}', [text])"
				class="truncate text-ink-gray-8 underline-offset-2 hover:underline"
				@open="emit('open')"
			>
				{{ text }}
			</RecordAnchor>
			<span v-else class="truncate text-ink-gray-5">{{ text }}</span>
		</div>
		<p v-if="description" class="text-p-sm text-ink-gray-6">{{ description }}</p>
	</div>
</template>

<script setup lang="ts">
import { FormLabel } from "frappe-ui";
import { RecordAnchor } from "../Link";
import { translate as __ } from "../../utils/translate";

defineProps<{
	text: string | null;
	href: string | null;
	label?: string;
	description?: string;
	required?: boolean;
}>();
const emit = defineEmits<{ open: [] }>();
</script>
