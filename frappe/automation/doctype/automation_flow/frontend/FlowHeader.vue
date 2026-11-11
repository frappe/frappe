<!-- The builder's header row: where the flow is, its title, and the controls that act on it. -->
<template>
	<PageHeader>
		<div class="flex min-w-0 flex-1 items-center gap-1.5">
			<Breadcrumbs class="-ml-0.5 shrink-0" :items="crumbs" />
			<input
				ref="titleInput"
				v-model="title"
				class="min-w-0 max-w-sm flex-1 truncate rounded border-0 bg-transparent px-1.5 py-1 text-lg font-semibold text-ink-gray-9 placeholder:text-ink-gray-4 hover:bg-surface-gray-2 focus:bg-surface-gray-2 focus:outline-none focus:ring-2 focus:ring-outline-gray-3"
				:placeholder="__('Untitled flow')"
				:aria-label="__('Title')"
				data-flow-title
			/>
			<Badge v-if="unsaved" :label="__('Unsaved')" theme="amber" />
		</div>
		<div class="flex shrink-0 items-center gap-2">
			<Button
				variant="ghost"
				icon="lucide-undo-2"
				:aria-label="__('Undo')"
				:disabled="!canUndo"
				@click="$emit('undo')"
			/>
			<Button
				variant="ghost"
				icon="lucide-redo-2"
				:aria-label="__('Redo')"
				:disabled="!canRedo"
				@click="$emit('redo')"
			/>
			<Switch
				:model-value="!!enabled"
				:label="__('Enabled')"
				@update:model-value="enabled = $event ? 1 : 0"
			/>
			<Button variant="solid" :label="__('Save')" :loading="saving" @click="$emit('save')" />
		</div>
	</PageHeader>
</template>

<script setup>
import { ref } from "vue";
import { Badge, Breadcrumbs, Button, PageHeader, Switch } from "frappe-ui";
import { __ } from "frappe/i18n";
import { routeFor } from "@shell";
import { FLOW_DOCTYPE } from "./flow/flowDoc";

const title = defineModel("title", { type: String, default: "" });
const enabled = defineModel("enabled", { type: Number, default: 0 });
defineProps({
	unsaved: Boolean,
	saving: Boolean,
	canUndo: Boolean,
	canRedo: Boolean,
});
defineEmits(["save", "undo", "redo"]);
defineExpose({ focusTitle: () => titleInput.value?.focus() });

const titleInput = ref(null);
const crumbs = [{ label: __("Automation Flows"), route: routeFor(FLOW_DOCTYPE) }];
</script>
