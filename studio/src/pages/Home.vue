<template>
	<div class="h-screen flex-col overflow-hidden bg-white">
		<div
			class="toolbar sticky top-0 z-10 flex h-14 items-center justify-center bg-white p-2 shadow-sm"
		>
			<div class="absolute left-3 flex items-center">
				<router-link class="flex items-center gap-2" :to="{ name: 'Home' }">
					<h1 class="text-md mt-[2px] font-semibold leading-5 text-gray-800">Studio</h1>
				</router-link>
			</div>
		</div>

		<div class="flex flex-col items-center h-full px-20 py-10">
			<div class="flex flex-row justify-between w-full">
				<div class="text-lg font-semibold text-gray-800">All Pages</div>
				<router-link :to="{ name: 'StudioPage', params: { pageID: 'new' } }">
					<Button variant="solid" icon-left="plus">New Page</Button>
				</router-link>
			</div>
			<div class="grid grid-cols-5 items-start w-full mt-5">
				<router-link
					class="flex flex-col justify-center gap-1 border-2 p-5 rounded-lg"
					v-for="page in studioPages.data"
					:to="{ name: 'StudioPage', params: { pageID: page.name } }"
					:key="page.name"
				>
					<div class="font-semibold text-gray-800">{{ page.page_title }}</div>
					<UseTimeAgo v-slot="{ timeAgo }" :time="page.modified">
						<p class="mt-1 block text-xs text-gray-500">Edited {{ timeAgo }}</p>
					</UseTimeAgo>
				</router-link>
			</div>
		</div>
	</div>
</template>

<script setup>
import { studioPages } from "@/data/studioPages"
import { UseTimeAgo } from "@vueuse/components"
</script>
