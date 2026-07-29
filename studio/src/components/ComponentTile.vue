<template>
	<!-- Draggable component tile. dragstart is delegated on the panel container
	     (reads `.user-component` + data-component-name), so no handler is needed here.
	     A family primary is `stacked` (a card peeks behind it) and shows its part
	     `count`; clicking it (vs dragging) is emitted so the panel can open the tray. -->
	<div
		class="user-component group relative flex cursor-grab flex-col items-center justify-center gap-3 text-ink-gray-6 transition-all duration-200 hover:scale-105"
		draggable="true"
		:data-component-name="component.name"
		@click="emit('click')"
	>
		<div class="relative h-16 w-16">
			<div
				v-if="stacked"
				class="bg-surface-white pointer-events-none absolute inset-0 -translate-y-1 translate-x-1 rounded-lg border border-outline-gray-2"
			/>
			<div
				class="relative flex h-16 w-16 items-center justify-center rounded-lg border bg-surface-gray-1 p-3 transition-all duration-200 group-hover:border-outline-gray-3 group-hover:bg-surface-gray-2 group-hover:shadow-sm"
				:class="stacked ? 'border-outline-gray-3' : 'border-outline-gray-2'"
			>
				<component :is="component.icon" class="h-6 w-6" />
			</div>
		</div>
		<span
			class="flex w-full items-center justify-center gap-1 text-balance text-center text-xs leading-normal"
		>
			{{ component.title }}
			<span v-if="count" class="text-ink-gray-4">{{ count }}</span>
		</span>
	</div>
</template>

<script setup lang="ts">
import type { FrappeUIComponent } from "@/types"

defineProps<{ component: FrappeUIComponent; stacked?: boolean; count?: number }>()
const emit = defineEmits<{ (e: "click"): void }>()
</script>
