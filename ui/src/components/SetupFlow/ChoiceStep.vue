<template>
	<div class="flex flex-wrap gap-x-4 gap-y-3.5">
		<Button
			v-for="option in options"
			:key="String(option.value)"
			variant="outline"
			size="sm"
			:data-state="modelValue === option.value ? 'active' : 'inactive'"
			:aria-pressed="modelValue === option.value"
			@click="toggle(option)"
		>
			<template v-if="option.icon || $slots.icon" #prefix>
				<slot name="icon" :option="option">
					<span v-if="option.icon" :class="option.icon" class="size-4" />
				</slot>
			</template>
			{{ option.label }}
			<template v-if="modelValue === option.value" #suffix>
				<span class="lucide-x size-3.5 text-ink-gray-6" />
			</template>
		</Button>
	</div>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import type { ChoiceOption, ChoiceValue } from "./types";

/** One answer out of a few, shown as chips. Picking the chosen one again clears it. */
const props = defineProps<{
	options: ChoiceOption[];
	modelValue?: ChoiceValue | null;
}>();
const emit = defineEmits<{
	"update:modelValue": [value: ChoiceValue | null];
	select: [option: ChoiceOption];
	deselect: [option: ChoiceOption];
}>();

function toggle(option: ChoiceOption) {
	if (props.modelValue === option.value) {
		emit("update:modelValue", null);
		emit("deselect", option);
	} else {
		emit("update:modelValue", option.value);
		emit("select", option);
	}
}
</script>
