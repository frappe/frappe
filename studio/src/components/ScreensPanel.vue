<template>
	<div class="flex h-full flex-col">
		<div class="flex flex-col space-y-1">
			<div class="w-full" v-for="screen in store.appScreens" :key="screen.name">
				<router-link
					:to="{
						name: 'StudioPage',
						params: { appID: store.activeApp, pageID: screen.screen_name },
					}"
					class="flex cursor-pointer items-center gap-2 truncate rounded px-2 py-2 transition duration-300 ease-in-out"
					:class="[
						store.activePage?.name === screen.screen_name
							? 'bg-gray-200 text-gray-900'
							: 'hover:bg-gray-50 hover:text-gray-700',
					]"
				>
					<div class="flex items-center gap-1 truncate text-base text-gray-700">
						{{ screen.screen_title }}
					</div>
				</router-link>
			</div>
		</div>
	</div>
</template>

<script setup>
import useStudioStore from "@/stores/studioStore"

const store = useStudioStore()
</script>
