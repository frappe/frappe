<template>
	<div class="space-y-5">
		<div v-for="section in sections" :key="section.group">
			<div class="mb-2 text-base text-ink-gray-5">{{ section.group }}</div>
			<button
				v-for="trigger in section.options"
				:key="trigger.value"
				class="block w-full text-left"
				@click="$emit('update:modelValue', trigger.value)"
			>
				<ItemListRow
					size="md"
					class="hover:bg-surface-gray-2"
					:selected="modelValue === trigger.value"
				>
					<template #prefix>
						<component :is="trigger.icon" class="size-4 text-ink-gray-6" />
					</template>
					<div class="truncate">{{ trigger.label }}</div>
				</ItemListRow>
			</button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ItemListRow } from "frappe-ui";

defineProps({
	sections: { type: Array, required: true },
	modelValue: { type: String, default: "" },
});

defineEmits(["update:modelValue"]);
</script>
