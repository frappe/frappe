<template>
	<div class="sticky bottom-0 left-0 top-0 flex h-full w-60 shrink-0 flex-col bg-gray-50 px-2 pt-2">
		<button class="mb-1 flex w-56 items-center gap-2 rounded p-2 hover:bg-gray-200">
			<slot name="header">
				<div class="rounded-sm">
					<div v-if="logoSVG" class="flex items-center gap-2">
						<span v-html="logoSVG" />
					</div>
					<AppLogo v-else class="h-6 w-6" />
				</div>

				<span class="truncate text-xl font-bold text-gray-800">
					{{ title }}
				</span>
			</slot>
		</button>

		<nav class="mt-2 flex flex-1 flex-col space-y-1 overflow-y-auto">
			<div class="w-full" v-for="item in menuItems" :key="item.label">
				<component
					:is="item.route_to ? 'router-link' : 'div'"
					:to="item.route_to"
					class="flex cursor-pointer items-center gap-2 truncate rounded px-2 py-1 transition duration-300 ease-in-out"
					:class="[
						$router.currentRoute.value.path === item.route_to ? 'bg-white shadow-sm' : 'hover:bg-gray-200',
					]"
					@click="item.route_to && $router.push(item.route_to)"
				>
					<FeatherIcon :name="item.featherIcon || 'folder-normal'" class="h-5 w-5 text-gray-700" />
					<div class="flex items-center gap-1 truncate text-base text-gray-700">
						{{ item.label }}
					</div>
				</component>
			</div>
		</nav>
	</div>
</template>

<script setup lang="ts">
import AppLogo from "../Icons/AppLogo.vue"
import type { SidebarProps } from "@/types/studio_components/Sidebar"

withDefaults(defineProps<SidebarProps>(), {
	menuItems: () => [],
})
</script>
