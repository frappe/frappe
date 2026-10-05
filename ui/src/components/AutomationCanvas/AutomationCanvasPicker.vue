<template>
	<Combobox
		:options="options"
		:disabled="disabled"
		trigger="button"
		:side="side"
		:placeholder="placeholder"
		@update:model-value="pick"
	>
		<template #item-prefix="{ item }">
			<AutomationCanvasIcon :icon="row(item).icon" :tone="row(item).tone" />
		</template>
		<template #item-label="{ item }">
			<AutomationCanvasOption :item="row(item)" />
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
import type { AutomationCanvasOptionGroup, AutomationCanvasPickerOption } from "./types";

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

/** Combobox types its rows as its own option shape, which has no `tone`. */
function row(item: unknown) {
	return item as AutomationCanvasPickerOption;
}

function pick(value: string | number | null | undefined) {
	if (value != null) emit("pick", String(value));
}
</script>
