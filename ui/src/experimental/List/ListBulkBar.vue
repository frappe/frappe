<!-- The floating bar for a selection: the count, the actions, and a clear button. -->
<template>
	<Transition
		enter-active-class="duration-200 ease-out"
		enter-from-class="translate-y-2 opacity-0"
		leave-active-class="duration-200 ease-in"
		leave-to-class="translate-y-2 opacity-0"
	>
		<div v-if="selection.length" class="absolute inset-x-0 bottom-16 mx-auto w-max">
			<div
				class="flex items-center gap-3 rounded-5 bg-surface-base px-4 py-2 text-base shadow-2xl"
			>
				<Checkbox :modelValue="true" :disabled="true" aria-hidden="true" />
				<span class="text-ink-gray-9">{{ selection.length }} selected</span>
				<div class="flex items-center gap-1 border-l border-outline-gray-2 ps-3">
					<Button
						v-for="action in actions"
						:key="action.label"
						:label="action.label"
						:theme="action.theme"
						variant="ghost"
						@click="action.onClick(selection)"
					/>
					<Button
						variant="ghost"
						icon="lucide-x"
						label="Clear selection"
						@click="selection = []"
					/>
				</div>
			</div>
		</div>
	</Transition>
</template>

<script setup lang="ts">
import { Button, Checkbox } from "frappe-ui";
import type { BulkAction } from "./types";

withDefaults(defineProps<{ actions?: BulkAction[] }>(), { actions: () => [] });

const selection = defineModel<string[]>("selection", { default: () => [] });
</script>
