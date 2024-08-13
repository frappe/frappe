<template>
	<div class="flex flex-col gap-5">
		<!-- Component Filter -->
		<TextInput
			type="text"
			size="sm"
			variant="outline"
			placeholder="Search component"
			v-model="componentFilter"
			@input="(e) => (componentFilter = e.target.value)"
		/>

		<div class="grid grid-cols-3 gap-y-4 gap-x-2 items-center">
			<div v-for="component in componentList" :key="component.name">
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
	</div>
</template>

<script setup>
import { computed, ref } from "vue"
import { TextInput } from "frappe-ui"

import { components } from "@/data/components"

import LucideIcon from "@/components/LucideIcon.vue"

const componentFilter = ref("")
const componentList = computed(() => {
	if (componentFilter.value) {
		return components.filter((component) =>
			component.name?.toLowerCase().includes(componentFilter.value.toLowerCase())
		)
	} else {
		return components
	}
})
</script>
