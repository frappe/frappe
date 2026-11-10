<template>
	<div
		:role="theme === 'gray' ? 'status' : 'alert'"
		class="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-6 p-3"
		:class="theme === 'amber' ? 'bg-surface-amber-1' : 'bg-surface-gray-1'"
	>
		<div class="flex min-w-0 flex-1 basis-64 items-center gap-3">
			<slot name="prefix">
				<span :class="icons[theme]" class="size-4 shrink-0" aria-hidden="true" />
			</slot>
			<div class="flex min-w-0 flex-1 flex-col gap-1">
				<span class="text-base-medium text-ink-gray-8">{{ title }}</span>
				<p v-if="description || $slots.description" class="text-p-base text-ink-gray-6">
					<slot name="description">{{ description }}</slot>
				</p>
			</div>
		</div>
		<div v-if="$slots.actions || dismissible" class="flex shrink-0 items-center gap-1">
			<slot name="actions" />
			<Button
				v-if="dismissible"
				variant="ghost"
				icon="lucide-x"
				:aria-label="__('Dismiss')"
				@click="emit('dismiss')"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { translate as __ } from "../../utils/translate";

withDefaults(
	defineProps<{
		theme?: "gray" | "red" | "amber";
		title: string;
		description?: string;
		dismissible?: boolean;
	}>(),
	{ theme: "gray", description: "" }
);
const emit = defineEmits<{ dismiss: [] }>();

const icons = {
	gray: "lucide-info text-ink-gray-7",
	red: "lucide-circle-x text-ink-red-5",
	amber: "lucide-triangle-alert text-ink-amber-5",
};
</script>
