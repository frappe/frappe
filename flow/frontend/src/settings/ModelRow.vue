<template>
	<!-- a row of settings' lists: its name (which opens its form) over its id, and its switch -->
	<li class="flex items-center gap-3 px-3 py-2.5">
		<button type="button" class="min-w-0 flex-1 text-left" :title="__('{0} details', [model.title])" @click="emit('open')">
			<span class="flex items-center gap-2">
				<span class="min-w-0 truncate text-base-medium text-ink-gray-9">{{ model.title }}</span>
				<!-- for Knowledge's search, so not in the chat's model list -->
				<Badge v-if="model.embedding" :label="__('Embedding')" theme="gray" size="sm" class="flex-none" />
			</span>
			<span class="mt-1 block truncate text-xs text-ink-gray-5">{{ model.model_id }}</span>
		</button>
		<Switch
			:model-value="Boolean(model.enabled) && !paused"
			:disabled="!canWrite || paused"
			:aria-label="__('{0} on', [model.title])"
			@update:model-value="(on) => emit('toggle', on)"
		/>
	</li>
</template>

<script setup>
import { Badge, Switch } from "frappe-ui";
import { __ } from "@flow/ui-core/translate.js";

// A model on the Models tab: its name, and its switch.
defineProps({
	model: { type: Object, required: true },
	canWrite: { type: Boolean, default: false },
	paused: { type: Boolean, default: false }, // its provider is off
});
const emit = defineEmits(["toggle", "open"]);
</script>
