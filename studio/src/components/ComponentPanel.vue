<template>
	<div class="flex flex-col gap-3">
		<div class="sticky top-[41px] z-50 mt-[-15px] flex w-full flex-col gap-3 bg-white py-3">
			<!-- Component Filter -->
			<Input
				type="text"
				variant="outline"
				placeholder="Search component"
				v-model="componentFilter"
				@input="
					(value: string) => {
						componentFilter = value
					}
				"
			/>
			<OptionToggle
				:options="[{ label: 'Standard' }, { label: 'Custom' }]"
				:modelValue="activeTab"
				@update:modelValue="
					(tab) => (store.studioLayout.leftPanelComponentTab = tab as leftPanelComponentTabOptions)
				"
			/>
		</div>

		<div class="grid grid-cols-3 items-center gap-x-2 gap-y-4">
			<EmptyState v-if="!componentList.length" message="No components found" class="col-span-3" />
			<div
				v-else
				v-for="component in componentList"
				:key="activeTab === 'Custom' ? component.component_id : component.name"
			>
				<div
					class="flex cursor-grab flex-col items-center justify-center gap-2 text-gray-700"
					draggable="true"
					@dragstart="
						(ev) =>
							canvasStore.handleDragStart(
								ev,
								activeTab === 'Custom' ? component.component_id : component.name,
							)
					"
					@dragend="(_ev) => canvasStore.handleDragEnd()"
				>
					<div
						class="flex flex-col items-center justify-center gap-2 truncate rounded border-[1px] border-gray-300 bg-gray-50 p-4 transition duration-300 ease-in-out"
					>
						<component :is="activeTab === 'Standard' ? component.icon : LucideBox" class="h-6 w-6" />
					</div>
					<span class="truncate text-xs">
						{{ activeTab === "Custom" ? component.component_name : component.title }}
					</span>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import OptionToggle from "@/components/OptionToggle.vue"
import Input from "@/components/Input.vue"
import EmptyState from "@/components/EmptyState.vue"

import components from "@/data/components"
import { studioComponents } from "@/data/studioComponents"

import useCanvasStore from "@/stores/canvasStore"
import useStudioStore from "@/stores/studioStore"
import type { leftPanelComponentTabOptions } from "@/types"
import type { StudioComponent } from "@/types/Studio/StudioComponent"

import LucideBox from "~icons/lucide/box"

const canvasStore = useCanvasStore()
const store = useStudioStore()

const componentFilter = ref("")
const componentList = computed(() => {
	if (componentFilter.value) {
		if (activeTab.value === "Standard") {
			return components.list.filter((component) =>
				component.name?.toLowerCase().includes(componentFilter.value.toLowerCase()),
			)
		} else {
			return studioComponents.data?.filter((component: StudioComponent) =>
				component.component_name?.toLowerCase().includes(componentFilter.value.toLowerCase()),
			)
		}
	} else {
		return activeTab.value === "Standard" ? components.list : studioComponents.data
	}
})

const activeTab = computed(() => store.studioLayout.leftPanelComponentTab)
</script>
