<template>
	<div class="flex flex-col gap-5">
		<!-- Component Filter -->
		<div class="sticky top-[41px] z-50 mt-[-15px] flex w-full bg-white py-3">
			<TextInput
				type="text"
				size="sm"
				class="w-full"
				variant="outline"
				placeholder="Search component"
				v-model="componentFilter"
				@input="(e: Event) => (componentFilter = (e.target as HTMLInputElement).value)"
			/>
		</div>

		<div class="grid grid-cols-3 items-center gap-x-2 gap-y-4">
			<div v-for="component in componentList" :key="component.name">
				<div class="flex flex-col items-center justify-center gap-2 text-gray-700">
					<div
						class="flex cursor-grab flex-col items-center justify-center gap-2 truncate rounded border-[1px] border-gray-300 bg-gray-50 p-4 transition duration-300 ease-in-out"
						draggable="true"
						@dragstart="(ev) => store.startDrag(ev, component.name)"
						@dragend="(_ev) => store.resetDnd()"
					>
						<LucideIcon :name="component.icon" class="h-6 w-6" />
					</div>
					<span class="truncate text-xs">{{ component.title }}</span>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { TextInput } from "frappe-ui"

import components from "@/data/components"

import LucideIcon from "@/components/LucideIcon.vue"
import useStudioStore from "@/stores/studioStore"

const store = useStudioStore()

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
</script>
