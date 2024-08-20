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

		<div class="grid grid-cols-3 items-center gap-x-2 gap-y-4">
			<div v-for="component in componentList" :key="component.name">
				<div class="flex flex-col items-center justify-center gap-2 text-gray-700">
					<div
						class="flex cursor-grab flex-col items-center justify-center gap-2 truncate rounded border-[1px] border-gray-300 bg-gray-50 p-4 transition duration-300 ease-in-out"
						draggable="true"
						@dragstart="(ev) => setComponentData(ev, component)"
					>
						<LucideIcon :name="component.icon" class="h-6 w-6" />
					</div>
					<span class="truncate text-xs">{{ component.title }}</span>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue"
import { TextInput } from "frappe-ui"

import components from "@/data/components"

import LucideIcon from "@/components/LucideIcon.vue"

const componentFilter = ref("")
const componentList = computed(() => {
	if (componentFilter.value) {
		return components.list.filter((component) =>
			component.name?.toLowerCase().includes(componentFilter.value.toLowerCase()),
		)
	} else {
		return components.list
	}
})

const setComponentData = (ev, component) => {
	ev.dataTransfer.setData("componentName", component.name)
}
</script>
