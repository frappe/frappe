<template>
	<div class="flex flex-col gap-5">
		<!-- Component Filter -->
		<div class="sticky top-[41px] z-50 mt-[-15px] flex w-full bg-white py-3">
			<Input type="text" variant="outline" placeholder="Search component" v-model="componentFilter" />
		</div>

		<div class="grid grid-cols-3 items-center gap-x-2 gap-y-4">
			<div v-for="component in componentList" :key="component.name">
				<div
					class="flex cursor-grab flex-col items-center justify-center gap-2 text-gray-700"
					draggable="true"
					@dragstart="(ev) => canvasStore.handleDragStart(ev, component.name)"
					@dragend="(_ev) => canvasStore.handleDragEnd()"
				>
					<div
						class="flex flex-col items-center justify-center gap-2 truncate rounded border-[1px] border-gray-300 bg-gray-50 p-4 transition duration-300 ease-in-out"
					>
						<component :is="component.icon" class="h-6 w-6" />
					</div>
					<span class="truncate text-xs">{{ component.title }}</span>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import Input from "@/components/Input.vue"
import components from "@/data/components"

import useCanvasStore from "@/stores/canvasStore"

const canvasStore = useCanvasStore()

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
