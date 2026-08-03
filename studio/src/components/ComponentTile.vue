<template>
	<div
		class="user-component group relative flex cursor-grab flex-col items-center justify-center gap-2 text-ink-gray-6 transition-all duration-200 hover:scale-105"
		draggable="true"
		:data-component-name="component.name"
		@click="emit('click')"
	>
		<div class="relative h-16 w-full">
			<div
				v-if="stacked"
				class="bg-surface-white pointer-events-none absolute inset-0 -translate-y-1 translate-x-1 rounded-md border border-outline-gray-2"
			/>
			<div
				class="relative flex h-16 w-full items-center justify-center rounded-md border p-3 transition-all duration-200 group-hover:shadow-sm"
				:class="[
					inverted
						? 'border-outline-gray-1 bg-surface-base group-hover:border-outline-gray-2'
						: 'bg-surface-gray-1 group-hover:border-outline-gray-3 group-hover:bg-surface-gray-2',
					!inverted && (stacked ? 'border-outline-gray-3' : 'border-outline-gray-2'),
					expanded && '!border-outline-gray-4',
				]"
			>
				<component :is="component.icon" class="h-6 w-6" />
			</div>
		</div>
		<!-- reserve two lines so a wrapping label doesn't make its tile (and thus its whole
		     grid row) taller than its neighbours — keeps grid rows even. `compactLabel` opts
		     out (e.g. the parts tray) so the tile sizes to its content instead. -->
		<span
			class="line-clamp-2 w-full text-balance text-center text-xs leading-normal"
			:class="{ 'min-h-[2lh]': !compactLabel }"
			:title="component.title"
		>
			{{ component.title }}
		</span>
	</div>
</template>

<script setup lang="ts">
import type { FrappeUIComponent } from "@/types"

defineProps<{
	component: FrappeUIComponent
	stacked?: boolean
	expanded?: boolean
	compactLabel?: boolean
	inverted?: boolean
}>()
const emit = defineEmits<{ (e: "click"): void }>()
</script>
