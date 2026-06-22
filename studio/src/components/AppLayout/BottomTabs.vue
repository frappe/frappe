<template>
	<nav
		class="fixed bottom-0 z-[1000] h-15 w-full border-t border-outline-elevation-2 bg-surface-base shadow-lg"
	>
		<div class="flex items-center justify-around">
			<router-link
				v-for="(tab, index) in tabs"
				:key="index"
				:to="{ path: tab.route }"
				class="flex flex-col items-center px-4 py-2 text-ink-gray-5 hover:text-ink-gray-7"
				:class="[$router.currentRoute.value.path === tab.route ? 'text-ink-gray-7' : '']"
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
