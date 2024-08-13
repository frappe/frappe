<template>
	<div class="grid grid-cols-3 gap-y-4 gap-x-2 items-center">
		<div v-for="component in components" :key="component.name">
			<div class="flex flex-col items-center justify-center gap-2 text-gray-700">
				<div
					class="flex flex-col bg-gray-50 border-gray-300 border-[1px] p-4 items-center justify-center cursor-grab gap-2 truncate rounded transition duration-300 ease-in-out"
				>
					<LucideIcon :name="component.icon" class="h-6 w-6" />
				</div>
				<span class="text-xs truncate">{{ component.name }}</span>
			</div>
		</div>
	</div>
</template>

<script setup>
import { components } from "@/data/components"

import LucideIcon from "@/components/LucideIcon.vue"
</script>
