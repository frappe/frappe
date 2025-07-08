<template>
	<nav class="fixed bottom-0 z-[1000] h-15 w-full border-t border-gray-200 bg-white shadow-lg">
		<div class="flex items-center justify-around">
			<router-link
				v-for="(tab, index) in tabs"
				:key="index"
				:to="{ path: tab.route }"
				class="flex flex-col items-center px-4 py-2 text-gray-600 hover:text-gray-800"
				:class="[$router.currentRoute.value.path === tab.route ? 'text-gray-800' : '']"
			>
				<FeatherIcon :name="tab.icon" class="h-6 w-6" />
				<span class="mt-1 text-xs">{{ tab.label }}</span>
			</router-link>
		</div>
	</nav>
</template>

<script setup lang="ts">
import { FeatherIcon } from "frappe-ui"
import type { BottomTabsProps } from "@/types/studio_components/BottomTabs"

defineProps<{ tabs: BottomTabsProps }>()
</script>
