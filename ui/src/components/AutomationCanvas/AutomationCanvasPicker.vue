<template>
	<Combobox
		:options="options"
		:disabled="disabled"
		trigger="button"
		:side="side"
		:placeholder="placeholder"
		@update:model-value="emit('pick', $event)"
	>
		<template #item-prefix="{ item }">
			<AutomationCanvasIcon :icon="item.icon" :tone="item.tone" />
		</template>
		<template #item-label="{ item }">
			<AutomationCanvasOption :item="item" />
		</template>
		<template #trigger>
			<slot />
		</template>
	</Combobox>
</template>

<script setup lang="ts">
import { Combobox } from "frappe-ui";
import AutomationCanvasIcon from "./AutomationCanvasIcon.vue";
import AutomationCanvasOption from "./AutomationCanvasOption.vue";
import type { AutomationCanvasOptionGroup } from "./types";

withDefaults(
	defineProps<{
		options: AutomationCanvasOptionGroup[];
		placeholder: string;
		side?: "bottom" | "right";
		disabled?: boolean;
	}>(),
	{ side: "bottom", disabled: false }
);
const emit = defineEmits<{ pick: [value: string] }>();
</script>
