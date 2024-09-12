<template>
	<div
		:style="{
			width: `${store.studioLayout.rightPanelWidth}px`,
		}"
	>
		<div class="relative min-h-full">
			<div
				class="dark:border-zinc-800 dark:bg-zinc-900 sticky top-0 z-[12] flex w-full border-gray-200 bg-white px-2 text-base"
			>
				<button
					v-for="tab of ['Props', 'Styles']"
					:key="tab"
					class="mx-2 flex-1 p-2 py-3"
					@click="setActiveTab(tab)"
					:class="{
						'dark:border-zinc-500 dark:text-zinc-300 border-b-[1px] border-gray-900': activeTab === tab,
						'dark:text-zinc-500 text-gray-700': activeTab !== tab,
					}"
				>
					{{ tab }}
				</button>
			</div>

			<ComponentProps v-show="activeTab === 'Props'" class="p-4" :block="store.selectedBlocks[0]" />
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue"
import useStore from "@/store"

import ComponentProps from "@/components/ComponentProps.vue"

const store = useStore()

const activeTab = ref("Props")
const setActiveTab = (tab) => (activeTab.value = tab)
</script>
