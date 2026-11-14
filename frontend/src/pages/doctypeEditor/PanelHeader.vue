<!-- The panel's head: icon tile, title, subtitle, then remove and close, as frappe/crm#3419's
     PanelHeader. -->
<template>
	<div class="flex items-center gap-2.5 px-4 pb-3 pt-4">
		<div
			class="grid size-9 shrink-0 place-items-center rounded-4 bg-surface-gray-2 text-ink-gray-6"
		>
			<span class="size-4" :class="icon" aria-hidden="true" />
		</div>
		<div class="min-w-0 flex-1">
			<p class="truncate text-lg font-semibold text-ink-gray-9" data-panel-title>
				{{ title }}
			</p>
			<p class="mt-0.5 truncate text-sm text-ink-gray-5" data-panel-subtitle>
				{{ subtitle }}
			</p>
		</div>
		<div class="-mr-1 flex shrink-0 items-center">
			<Tooltip v-if="removeLabel" :text="removeLabel">
				<Button
					:variant="removeActive ? 'subtle' : 'ghost'"
					:icon="removeIcon"
					:label="removeLabel"
					@click="$emit('remove')"
				/>
			</Tooltip>
			<Tooltip :text="__('Close')">
				<Button
					variant="ghost"
					icon="lucide-x"
					:label="__('Close')"
					@click="$emit('close')"
				/>
			</Tooltip>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Button, Tooltip } from "frappe-ui";
import { __ } from "@/i18n";

withDefaults(
	defineProps<{
		icon: string;
		title: string;
		subtitle: string;
		removeLabel?: string;
		removeIcon?: string;
		removeActive?: boolean;
	}>(),
	{ removeLabel: "", removeIcon: "lucide-trash-2", removeActive: false }
);
defineEmits<{ remove: []; close: [] }>();
</script>
